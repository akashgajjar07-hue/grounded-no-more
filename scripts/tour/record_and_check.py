"""Record the full 6-step guided tour and check every transition automatically (v2.2).

For each engine (Chromium, WebKit) x viewport (1440x900, 390x844) the tour is opened from the Mission Control
"60-second tour" button (it opens in Play mode) and played to the end at window.__gnmTourStepMs (default 4000 ms,
never below 4000). Two passes per combination:

  A. instrumented (no video, no screenshots, so the timing is clean): an in-page sampler reads the tour every 50 ms
     (card / spotlight rects + opacity, step, phase, the spotlit target), a PerformanceObserver sums layout shifts and a
     rAF loop records frame times.
  B. recorded: Playwright video (kept local in private/tour_videos/, git-ignored) + the same 50 ms state sampler. The
     video is decoded at 10 fps by Chromium itself (<video> + canvas; ffmpeg is not needed) and every frame carries the
     state sampled nearest to it. No screenshots are taken (a forced capture during a View Transition can itself present
     a blank frame in headless Chromium).

Checks (all must pass):
  a  no blank / dark frames: the content-area mean luminance of every transition frame stays within a threshold of the
     darker of the two neighbouring steps' steady frames and its contrast (luminance stddev) does not collapse (a blank
     or displaced page is a large flat area), no frame shows #view empty/hidden while the card is visible,
     and no frame shows an empty #view at all unless the old page is held as a still (View Transition)
  b  the card's position changes at most once per transition and never while it is visible
  c  the spotlight is never on a zero-size / skeleton / missing target, and it sits on that target
  c2 the visible card never covers the spotlit area
  c3 every step's text fits the fixed-size card without scrolling
  d  layout-shift total during the tour < 0.001 (Chromium; WebKit has no layout-shift API) and >= 58 fps from rAF
     timing (Chromium)

Outputs: reports/tour/frame_check.json, reports/tour/strip_<engine>_<width>.jpg (JPEG contact sheets, < 300 KB each),
private/tour_videos/tour_<engine>_<width>.webm.

  .venv/bin/python scripts/tour/record_and_check.py                 # all 4 combinations
  .venv/bin/python scripts/tour/record_and_check.py --only chromium-1440 --step-ms 4000
"""
from __future__ import annotations

import argparse
import functools
import http.server
import io
import json
import shutil
import socketserver
import statistics
import sys
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports" / "tour"
VIDEOS = ROOT / "private" / "tour_videos"
COMBOS = [("chromium", 1440, 900), ("chromium", 390, 844), ("webkit", 1440, 900), ("webkit", 390, 844)]
LUM_REL, LUM_ABS = 0.85, 3.0       # a transition frame may not be darker than 85% of the darker steady step, minus 3
DUMP: Path | None = None
STD_REL = 0.6                      # ... nor flatter (blank / displaced page) than 60% of the flatter steady step's contrast
CLS_MAX, FPS_MIN = 0.001, 58.0
STRIP_MAX_BYTES = 300_000

# ------------------------------------------------------------------------------------------------ in-page probes
INIT_JS = r"""
(() => {
  window.__tour = { shifts: [], frames: [], samples: [], t0: 0, on: false };
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__tour.shifts.push({ t: e.startTime, v: e.value }); })
      .observe({ type: 'layout-shift', buffered: true });
    window.__tour.clsSupported = true;
  } catch { window.__tour.clsSupported = false; }
  let last = 0;
  const raf = (t) => { if (window.__tour.on) { if (last) window.__tour.frames.push(t - last); last = t; } else last = 0; requestAnimationFrame(raf); };
  requestAnimationFrame(raf);
})();
"""

STATE_JS = r"""() => {
  const st = window.__gnmStory?.state?.() || null;
  const card = document.querySelector('.story-card'), spot = document.querySelector('.story-spot');
  const view = document.getElementById('view');
  const box = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map((v) => Math.round(v * 10) / 10); };
  const op = (el) => (el ? +getComputedStyle(el).opacity : 0);
  const tgt = window.__gnmStory?.target?.() || null;
  const vr = view ? view.getBoundingClientRect() : null;
  const text = card ? card.querySelector('.story-text') : null;
  return {
    t: performance.now(), index: st ? st.index : null, phase: st ? st.phase : null, held: st ? !!st.held : false,
    playing: st ? st.playing : null, card: box(card), cardOp: op(card), spot: box(spot), spotOp: op(spot),
    target: tgt ? box(tgt) : null, targetConnected: !!(tgt && tgt.isConnected),
    targetSkeleton: !!(tgt && (tgt.matches('.skeleton, .state') || tgt.closest('.skeleton') || tgt.querySelector('.skeleton'))),
    viewHidden: !view || view.style.visibility === 'hidden' || getComputedStyle(view).visibility === 'hidden',
    viewEmpty: !view || !view.querySelector('.card, section, figure, h1, h2') || !!view.querySelector(':scope > .stack[aria-busy="true"]'),
    viewBox: vr ? [vr.left, Math.max(vr.top, 0), vr.width, Math.min(vr.bottom, innerHeight) - Math.max(vr.top, 0)].map(Math.round) : null,
    bar: Math.round(document.querySelector('.topbar')?.getBoundingClientRect().bottom || 0),
    textFit: text ? [text.scrollHeight, text.clientHeight] : null, sheet: !!card?.classList.contains('is-sheet'), step: card?.querySelector('.story-step')?.textContent || '',
  };
}"""

SAMPLER_JS = r"""(stateSrc) => {
  const read = eval(stateSrc);
  window.__tour.samples = [];
  window.__tour.on = true;
  window.__tour.t0 = performance.now();
  window.__tour.timer = setInterval(() => window.__tour.samples.push(read()), 50);
}"""

STOP_JS = r"""() => { clearInterval(window.__tour.timer); window.__tour.on = false;
  return { samples: window.__tour.samples, frames: window.__tour.frames, shifts: window.__tour.shifts.filter((s) => s.t >= window.__tour.t0),
           clsSupported: window.__tour.clsSupported, t0: window.__tour.t0 }; }"""

DONE_JS = "window.__gnmStory && window.__gnmStory.state().index === 5 && window.__gnmStory.state().phase === 'steady'"


# ------------------------------------------------------------------------------------------------ server
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass


def serve() -> tuple[str, socketserver.TCPServer]:
    class _Server(socketserver.ThreadingTCPServer):
        request_queue_size = 128
        allow_reuse_address = True
        daemon_threads = True
    httpd = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(DOCS)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}/index.html", httpd


# ------------------------------------------------------------------------------------------------ helpers
def overlap(a, b) -> float:
    if not a or not b:
        return 0.0
    ox = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    oy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return ox * oy


def open_tour(page, url: str, step_ms: int) -> None:
    page.goto(url + "#/mission")
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=20000)
    page.wait_for_timeout(1000)
    page.evaluate(f"window.__gnmTourStepMs = {step_ms}")


def transitions(samples: list[dict]) -> list[tuple[int, int, int]]:
    """[(to_index, first_sample, steady_sample)]: from the sample where the step index changes (or the tour opens) to the
    first sample where that step is steady."""
    out, start, cur = [], None, None
    for k, s in enumerate(samples):
        if s["index"] is None:
            continue
        if cur != s["index"]:
            cur, start = s["index"], k
        if start is not None and s["phase"] == "steady":
            out.append((cur, start, k))
            start = None
    return out


# ------------------------------------------------------------------------------------------------ pass A
def pass_a(pw, engine: str, w: int, h: int, url: str, step_ms: int) -> dict:
    b = getattr(pw, engine).launch()
    ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion="no-preference")
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.add_init_script(INIT_JS)
    open_tour(page, url, step_ms)
    page.evaluate(SAMPLER_JS, f"({STATE_JS})")
    page.locator('[data-story="mission-start"]').click()
    page.wait_for_function("window.__gnmStory && window.__gnmStory.state().playing", timeout=3000)
    page.wait_for_function(DONE_JS, timeout=6 * (step_ms + 8000), polling=100)
    page.wait_for_timeout(800)
    data = page.evaluate(STOP_JS)
    texts = []
    page.keyboard.press("Escape")
    ctx.close()
    b.close()
    data["errors"] = errors
    data["texts"] = texts
    return data


def check_a(d: dict, engine: str) -> dict:
    S = [s for s in d["samples"] if s["index"] is not None]
    res: dict = {}
    # b: card position changes per transition
    moves, vis_moves = [], []
    for to, a, z in transitions(S):
        win = S[max(0, a - 1): z + 1]
        pos = [tuple(s["card"][:2]) if s["card"] else None for s in win]
        changes = sum(1 for p, q in zip(pos, pos[1:]) if p != q)
        vis = sum(1 for s0, s1 in zip(win, win[1:]) if s0["cardOp"] > 0.01 and s1["cardOp"] > 0.01 and tuple(s0["card"][:2]) != tuple(s1["card"][:2]))
        moves.append({"to_step": to + 1, "position_changes": changes, "changes_while_visible": vis})
    steady_vis = 0
    for s0, s1 in zip(S, S[1:]):
        if s0["phase"] == s1["phase"] == "steady" and s0["index"] == s1["index"] and s0["card"][:2] != s1["card"][:2]:
            steady_vis += 1
    res["b_card_moves"] = {"per_transition": moves, "moves_while_steady": steady_vis,
                           "pass": all(m["position_changes"] <= 1 and m["changes_while_visible"] == 0 for m in moves) and steady_vis == 0
                           and len(moves) == 6}
    # c: spotlight on a real target
    bad_spot, cover = [], []
    for s in S:
        if s["spotOp"] > 0.01:
            sp, tg = s["spot"], s["target"]
            ok = bool(sp and sp[2] > 8 and sp[3] > 8 and tg and tg[2] > 8 and tg[3] > 8 and s["targetConnected"] and not s["targetSkeleton"])
            if ok and overlap(sp, tg) < 0.5 * sp[2] * sp[3] * 0.5:
                ok = False
            if not ok:
                bad_spot.append({"t": round(s["t"] - d["t0"]), "index": s["index"], "phase": s["phase"], "spot": sp, "target": tg})
            if s["cardOp"] > 0.01 and sp and sp[2] > 0:
                ov = overlap(s["card"], sp)
                if ov > 0.02 * sp[2] * sp[3] and ov > 24 * min(sp[2], s["card"][2]):
                    cover.append({"t": round(s["t"] - d["t0"]), "index": s["index"], "overlap_px2": round(ov), "card": s["card"], "spot": sp})
    res["c_spotlight_target"] = {"bad_samples": bad_spot[:10], "n_bad": len(bad_spot), "pass": not bad_spot}
    res["c2_card_covers_spot"] = {"bad_samples": cover[:10], "n_bad": len(cover), "pass": not cover}
    # c3: text fits (steady samples)
    fits = {}
    for s in S:
        if s["phase"] == "steady" and s["textFit"]:
            fits.setdefault(s["index"] + 1, s["textFit"])
    res["c3_text_fits"] = {"per_step": {k: {"scrollHeight": v[0], "clientHeight": v[1]} for k, v in fits.items()},
                           "pass": len(fits) == 6 and all(v[0] <= v[1] + 1 for v in fits.values())}
    # d: CLS + fps
    cls = round(sum(x["v"] for x in d["shifts"]), 5)
    fr = [f for f in d["frames"] if f > 0]
    mean = statistics.mean(fr) if fr else 0
    fps = round(1000 / mean, 1) if mean else 0
    p95 = round(sorted(fr)[int(0.95 * (len(fr) - 1))], 1) if fr else None
    long = sum(1 for f in fr if f > 34)
    chromium = engine == "chromium"
    res["d_cls_fps"] = {"cls": cls if d["clsSupported"] else None, "cls_supported": d["clsSupported"], "fps": fps,
                        "frame_ms_p95": p95, "frames_over_34ms": long, "n_frames": len(fr),
                        "pass": (cls < CLS_MAX if d["clsSupported"] else True) and (fps >= FPS_MIN if chromium else True),
                        "note": None if chromium else "WebKit: layout-shift API unavailable; fps reported, not gated"}
    res["errors"] = {"list": d["errors"][:10], "pass": not d["errors"]}
    res["steps_seen"] = sorted({s["index"] + 1 for s in S})
    return res


# ------------------------------------------------------------------------------------------------ pass B
DECODE_JS = r"""async (fps) => {
  const v = document.querySelector('video');
  await new Promise((r) => (v.readyState >= 1 ? r() : v.addEventListener('loadedmetadata', r, { once: true })));
  if (!isFinite(v.duration)) { v.currentTime = 1e6; await new Promise((r) => v.addEventListener('seeked', r, { once: true })); }
  const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight;
  const g = c.getContext('2d'); const out = [];
  for (let t = 0; t < v.duration; t += 1 / fps) {
    v.currentTime = t; await new Promise((r) => v.addEventListener('seeked', r, { once: true }));
    g.drawImage(v, 0, 0); out.push([t, c.toDataURL('image/jpeg', 0.7)]);
  }
  return out;
}"""


def decode_video(pw, path: Path, fps: int = 10) -> list[tuple[float, bytes]]:
    """Frames at `fps` from a Playwright .webm, decoded by Chromium itself (<video> + canvas): no ffmpeg needed, and no
    forced screenshot ever touches the page under test."""
    import base64
    b = pw.chromium.launch()
    page = b.new_page()
    page.set_content(f"<video muted src='data:video/webm;base64,{base64.b64encode(path.read_bytes()).decode()}'></video>")
    raw = page.evaluate(DECODE_JS, fps)
    b.close()
    return [(t, base64.b64decode(u.split(",", 1)[1])) for t, u in raw]


def pass_b(pw, engine: str, w: int, h: int, url: str, step_ms: int, vid_dir: Path) -> tuple[list[dict], Path | None]:
    """Record the tour on video (no screenshots: a forced capture during a View Transition can itself present a blank
    frame in headless Chromium), sample the tour state every 50 ms in the page, then decode the video at 10 fps and give
    every frame the state sampled nearest to it (wall clock: video t=0 is the page's creation)."""
    b = getattr(pw, engine).launch()
    ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion="no-preference",
                        record_video_dir=str(vid_dir), record_video_size={"width": w, "height": h})
    page = ctx.new_page()
    t_wall0 = time.time() * 1000
    page.add_init_script(INIT_JS)
    open_tour(page, url, step_ms)
    page.evaluate(SAMPLER_JS.replace("window.__tour.samples.push(read())", "window.__tour.samples.push({ ...read(), wall: Date.now() })"), f"({STATE_JS})")
    page.locator('[data-story="mission-start"]').click()
    page.wait_for_function(DONE_JS, timeout=6 * (step_ms + 8000), polling=100)
    page.wait_for_timeout(900)
    samples = page.evaluate(STOP_JS)["samples"]
    page.keyboard.press("Escape")
    video = page.video.path() if page.video else None
    ctx.close()
    b.close()
    if not video:
        return [], None
    frames = []
    walls = [x["wall"] for x in samples]
    for t, jpg in decode_video(pw, Path(video)):
        wall = t_wall0 + t * 1000
        if wall < walls[0] - 60 or wall > walls[-1] + 60:
            continue
        k = min(range(len(samples)), key=lambda j: abs(walls[j] - wall))
        frames.append({**samples[k], "t": wall, "png": jpg})
    return frames, Path(video)


def lum(fr: dict) -> tuple[float, float]:
    """(mean, stddev) luminance of the content area (#view inside the viewport, below the top bar). A blank or
    displaced page shows as a large flat area: a low stddev."""
    im = Image.open(io.BytesIO(fr["png"])).convert("L")
    vb = fr["viewBox"]
    if vb and vb[2] > 20 and vb[3] > 20:
        x0, y0 = max(0, vb[0]), max(fr["bar"], vb[1])
        y1 = min(im.height, vb[1] + vb[3])
        if fr.get("sheet") and fr.get("card"):
            y1 = min(y1, int(fr["card"][1]))   # phones: the bottom sheet is the card slot, not page content
        im = im.crop((x0, y0, min(im.width, vb[0] + vb[2]), y1))
    st = ImageStat.Stat(im)
    return st.mean[0], st.stddev[0]


def check_b(frames: list[dict]) -> tuple[dict, list]:
    F = [f for f in frames if f["index"] is not None]
    for f in F:
        f["lum"], f["std"] = lum(f)
    steady, steady_sd = {}, {}
    for f in F:
        if f["phase"] == "steady":
            steady.setdefault(f["index"], []).append(f["lum"])
            steady_sd.setdefault(f["index"], []).append(f["std"])
    steady_l = {k: statistics.median(v) for k, v in steady.items()}
    steady_s = {k: statistics.median(v) for k, v in steady_sd.items()}
    dark, blank_card, blank_any = [], [], []
    windows = []
    for to, a, z in transitions(F):
        win = F[a: z + 1]
        windows.append((to, max(0, a - 3), min(len(F) - 1, z + 3)))
        ref = [steady_l.get(to - 1), steady_l.get(to)]
        ref = [x for x in ref if x is not None]
        if not ref:
            continue
        floor = min(ref) * LUM_REL - LUM_ABS
        sref = [x for x in (steady_s.get(to - 1), steady_s.get(to)) if x is not None]
        sfloor = min(sref) * STD_REL
        for f in win:
            if f["lum"] < floor or f["std"] < sfloor:
                if DUMP:
                    (DUMP / f"dark_{len(dark):02d}_{to + 1}_{f['phase']}.jpg").write_bytes(f["png"])
                dark.append({"to_step": to + 1, "phase": f["phase"], "lum": round(f["lum"], 1), "floor": round(floor, 1),
                             "std": round(f["std"], 1), "std_floor": round(sfloor, 1)})
    for f in F:
        empty = f["viewHidden"] or f["viewEmpty"]
        if empty and f["cardOp"] > 0.01:
            blank_card.append({"index": f["index"], "phase": f["phase"]})
        if empty and not f["held"]:
            blank_any.append({"index": f["index"], "phase": f["phase"], "lum": round(f["lum"], 1)})
    flat = [{"index": f["index"], "phase": f["phase"], "std": round(f["std"], 1)} for f in F if f["std"] < 3]   # any flat frame at all
    dt = [b["t"] - a["t"] for a, b in zip(F, F[1:])]
    res = {
        "a_no_dark_frames": {"steady_luminance": {k + 1: round(v, 1) for k, v in sorted(steady_l.items())},
                             "steady_contrast": {k + 1: round(v, 1) for k, v in sorted(steady_s.items())}, "dark_frames": dark[:10],
                             "n_dark": len(dark), "pass": not dark and len(steady_l) == 6},
        "a_no_flat_frames": {"frames": flat[:10], "n": len(flat), "pass": not flat},
        "a_no_blank_view_with_card": {"frames": blank_card[:10], "n": len(blank_card), "pass": not blank_card},
        "a_no_blank_view_on_screen": {"frames": blank_any[:10], "n": len(blank_any), "pass": not blank_any},
        "capture": {"video_frames": len(F), "mean_interval_ms": round(statistics.mean(dt), 1) if dt else None},
    }
    return res, windows


def contact_sheet(frames: list[dict], windows: list, out: Path, w: int, h: int) -> int:
    """One row per transition, frames resampled to 10 fps (nearest screenshot), downscaled, JPEG."""
    F = [f for f in frames if f["index"] is not None]
    tw = 200 if w > 500 else 96
    th = round(tw * h / w)
    rows = []
    for to, a, z in windows:
        t0, t1 = F[a]["t"], F[z]["t"]
        slots, t = [], t0
        while t <= t1 and len(slots) < 16:
            k = min(range(a, z + 1), key=lambda j: abs(F[j]["t"] - t))
            slots.append(k)
            t += 100
        rows.append((to, slots))
    cols = max(len(s) for _, s in rows) if rows else 1
    label_w = 40
    sheet = Image.new("RGB", (label_w + cols * (tw + 4), len(rows) * (th + 18) + 4), (20, 24, 30))
    d = ImageDraw.Draw(sheet)
    for r, (to, slots) in enumerate(rows):
        y = 4 + r * (th + 18)
        d.text((4, y + th // 2), f"->{to + 1}", fill=(200, 210, 220))
        for c, k in enumerate(slots):
            im = Image.open(io.BytesIO(F[k]["png"])).convert("RGB").resize((tw, th), Image.LANCZOS)
            x = label_w + c * (tw + 4)
            sheet.paste(im, (x, y))
            d.text((x + 2, y + th + 2), f"{(F[k]['t'] - F[slots[0]]['t']) / 1000:.1f}s {str(F[k]['phase'])[:5]}", fill=(150, 160, 170))
    q = 70
    while True:
        buf = io.BytesIO()
        sheet.save(buf, "JPEG", quality=q, optimize=True)
        if buf.tell() <= STRIP_MAX_BYTES or q <= 30:
            break
        q -= 8
    out.write_bytes(buf.getvalue())
    return buf.tell()


# ------------------------------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step-ms", type=int, default=4000)
    ap.add_argument("--only", default=None, help="e.g. chromium-1440")
    ap.add_argument("--dump", default=None, help="directory: save every flagged frame there (debugging)")
    args = ap.parse_args()
    global DUMP
    if args.dump:
        DUMP = Path(args.dump)
        DUMP.mkdir(parents=True, exist_ok=True)
    step_ms = max(4000, args.step_ms)
    from playwright.sync_api import sync_playwright

    REPORTS.mkdir(parents=True, exist_ok=True)
    VIDEOS.mkdir(parents=True, exist_ok=True)
    url, httpd = serve()
    out_path = REPORTS / "frame_check.json"
    report = json.loads(out_path.read_text()) if (args.only and out_path.exists()) else {}
    report.setdefault("combos", {})
    report.update({"step_ms": step_ms, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "thresholds": {"lum_rel": LUM_REL, "lum_abs": LUM_ABS, "std_rel": STD_REL, "cls_max": CLS_MAX, "fps_min": FPS_MIN}})
    try:
        with sync_playwright() as pw:
            for engine, w, h in COMBOS:
                key = f"{engine}-{w}"
                if args.only and args.only != key:
                    continue
                print(f"== {key}: pass A (instrumented)", flush=True)
                res = check_a(pass_a(pw, engine, w, h, url, step_ms), engine)
                print(f"== {key}: pass B (video + frames)", flush=True)
                tmp = VIDEOS / f"_tmp_{key}"
                shutil.rmtree(tmp, ignore_errors=True)
                frames, vid = pass_b(pw, engine, w, h, url, step_ms, tmp)
                rb, windows = check_b(frames)
                res.update(rb)
                strip = REPORTS / f"strip_{engine}_{w}.jpg"
                res["strip"] = {"path": str(strip.relative_to(ROOT)), "bytes": contact_sheet(frames, windows, strip, w, h)}
                if vid and vid.exists():
                    dest = VIDEOS / f"tour_{engine}_{w}.webm"
                    shutil.move(str(vid), dest)
                    res["video"] = str(dest.relative_to(ROOT))
                shutil.rmtree(tmp, ignore_errors=True)
                gates = [v["pass"] for k, v in res.items() if isinstance(v, dict) and "pass" in v]
                res["pass"] = all(gates)
                report["combos"][key] = res
                print(json.dumps({k: (v.get("pass") if isinstance(v, dict) else v) for k, v in res.items()}, indent=None), flush=True)
    finally:
        httpd.shutdown()
    report["pass"] = all(c.get("pass") for c in report["combos"].values()) and len(report["combos"]) == len(COMBOS)
    out_path.write_text(json.dumps(report, indent=1) + "\n")
    print(f"wrote {out_path.relative_to(ROOT)} pass={report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
