"""Performance audit (v2.1 §2.9): Lighthouse + Playwright/CDP animation metrics.

    python scripts/perf/run_perf.py [--label baseline] [--no-lighthouse] [--throttle 4]

1. Route weights: every route is loaded in Chromium and the JS + JSON bytes it pulls are summed; the landing (#/mission)
   and the two heaviest numbered workspaces are the Lighthouse targets.
2. Lighthouse 12 (`npx -y lighthouse@12`, CHROME_PATH = Playwright's Chromium, headless) on those three pages, mobile
   (default) and desktop presets: Performance (target >= 85), Accessibility (>= 90), CLS (< 0.05), LCP, TBT.
   If Lighthouse cannot be fetched or run, the fallback is Playwright + CDP Performance metrics; the summary says so.
3. CLS on load for every route (PerformanceObserver layout-shift, 5 s, excluding input-driven shifts).
4. Animations, sampled with a requestAnimationFrame frame-time recorder + PerformanceObserver('longtask'):
     tour      the guided tour playing (steps shortened to 3 s) for ~20 s from Mission
     slider    the Capital budget slider swept min -> max -> min on rAF (~4 s)
     cutaway   lab/cutaway.html draw-in, from navigation start for 4 s
   Reported: fps, frame-interval p50/p95/max, frames > 33 ms, long tasks > 50 / > 200 ms, the longest task,
   CDP Performance.getMetrics deltas. Run unthrottled and with CDP CPU throttling (--throttle, default 4x).
Writes reports/perf/{weights,lighthouse_summary,cls,animations,perf_summary}.json (full Lighthouse reports: reports/perf/traces/lighthouse/, gitignored).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "e2e"))
import audit_lib as AL  # noqa: E402

OUT = ROOT / "reports" / "perf"
ROUTES = ["mission", "parts", "forecast", "rotables", "network", "capital", "aog", "actions", "method", "about", "glossary", "planner"]
WORKSPACES = ROUTES[:8]
TARGETS = {"performance": 85, "accessibility": 90, "cls": 0.05, "longtask_ms": 200, "fps": 55}

SAMPLER_JS = r"""
(() => {
  const S = window.__perf = { frames: [], longtasks: [], shifts: [], on: false, t0: 0 };
  try { new PerformanceObserver((l) => l.getEntries().forEach((e) => S.longtasks.push({ start: e.startTime, dur: e.duration })))
          .observe({ type: 'longtask', buffered: true }); } catch (e) {}
  try { new PerformanceObserver((l) => l.getEntries().forEach((e) => { if (!e.hadRecentInput) S.shifts.push({ t: e.startTime, v: e.value }); }))
          .observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
  let last = 0;
  const tick = (t) => { if (S.on) { if (last) S.frames.push(t - last); last = t; } else last = 0; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
  S.start = () => { S.frames = []; S.lt0 = S.longtasks.length; S.t0 = performance.now(); S.on = true; };
  S.stop = () => { S.on = false; const dur = performance.now() - S.t0; const lts = S.longtasks.slice(S.lt0).filter((x) => x.start >= S.t0 - 1);
    return { ms: dur, frames: S.frames.slice(), longtasks: lts }; };
})();
"""


def pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))], 1)


def frame_stats(raw: dict) -> dict:
    fr = raw["frames"]
    lt = raw["longtasks"]
    return {"duration_ms": round(raw["ms"]), "frames": len(fr), "fps": round(len(fr) / (raw["ms"] / 1000), 1) if raw["ms"] else None,
            "frame_p50_ms": pct(fr, 50), "frame_p95_ms": pct(fr, 95), "frame_max_ms": round(max(fr), 1) if fr else None,
            "frames_over_33ms": sum(f > 33.4 for f in fr), "longtasks_over_50ms": len(lt), "longtasks_over_200ms": sum(x["dur"] > 200 for x in lt),
            "longest_task_ms": round(max((x["dur"] for x in lt), default=0), 1)}


# --------------------------------------------------------------------------------------------- weights


def route_weights(pw, base: str) -> dict:
    b = pw.chromium.launch()
    out = {}
    for r in ROUTES:
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        sizes: dict = {}

        def on_resp(resp, sizes=sizes):
            try:
                if resp.url.startswith("http://127.0.0.1"):
                    sizes[resp.url] = (resp.request.resource_type, len(resp.body()))
            except Exception:  # noqa: BLE001
                pass
        page.on("response", on_resp)
        page.goto(base + f"#/{r}")
        page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=30000)
        page.wait_for_timeout(1500)
        js = sum(s for u, (t, s) in sizes.items() if u.split("?")[0].endswith((".js", ".mjs")))
        js_view = sum(s for u, (t, s) in sizes.items() if "/js/views/" in u)
        data = sum(s for u, (t, s) in sizes.items() if u.split("?")[0].endswith(".json"))
        out[r] = {"js_bytes": js, "view_js_bytes": js_view, "json_bytes": data, "total_bytes": sum(s for _, s in sizes.values()),
                  "requests": len(sizes), "data_files": sorted(Path(u.split("?")[0]).name for u in sizes if u.split("?")[0].endswith(".json"))}
        ctx.close()
    b.close()
    return out


# --------------------------------------------------------------------------------------------- lighthouse


def run_lighthouse(url: str, name: str, preset: str, chrome: str) -> dict:
    d = OUT / "traces" / "lighthouse"      # full Lighthouse JSON: gitignored; the summary is reports/perf/lighthouse_summary.json
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{name}_{preset}.json"
    cmd = ["npx", "-y", "lighthouse@12", url, "--quiet", "--output=json", f"--output-path={out}",
           "--only-categories=performance,accessibility", "--chrome-flags=--headless=new --no-sandbox --disable-gpu"]
    if preset == "desktop":
        cmd.append("--preset=desktop")
    env = dict(os.environ, CHROME_PATH=chrome)
    t0 = time.time()
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    if p.returncode != 0 or not out.exists():
        return {"ok": False, "error": (p.stderr or p.stdout)[-800:]}
    lh = json.loads(out.read_text())
    a = lh["audits"]
    res = {"ok": True, "url": url, "preset": preset, "seconds": round(time.time() - t0),
           "performance": round(100 * (lh["categories"]["performance"]["score"] or 0)),
           "accessibility": round(100 * (lh["categories"]["accessibility"]["score"] or 0)),
           "cls": a["cumulative-layout-shift"].get("numericValue"), "lcp_ms": a["largest-contentful-paint"].get("numericValue"),
           "fcp_ms": a["first-contentful-paint"].get("numericValue"), "tbt_ms": a["total-blocking-time"].get("numericValue"),
           "si_ms": a["speed-index"].get("numericValue"), "lighthouse_version": lh.get("lighthouseVersion"),
           "a11y_failures": [{"id": k, "title": v["title"], "items": len((v.get("details") or {}).get("items", []))}
                             for k, v in a.items() if k in {r["id"] for r in lh["categories"]["accessibility"]["auditRefs"]}
                             and v.get("score") is not None and v["score"] < 1],
           "perf_opportunities": sorted([{"id": k, "title": v["title"], "savings_ms": round(v.get("numericValue") or 0)}
                                         for k, v in a.items() if (v.get("details") or {}).get("type") == "opportunity" and (v.get("numericValue") or 0) > 50],
                                        key=lambda x: -x["savings_ms"])[:6]}
    # keep the full report small: drop screenshots
    for k in ("final-screenshot", "screenshot-thumbnails", "full-page-screenshot"):
        lh.get("audits", {}).pop(k, None)
    lh.pop("fullPageScreenshot", None)
    out.write_text(json.dumps(lh))
    return res


# --------------------------------------------------------------------------------------------- CDP scenarios


def _ctx(b, throttle: float, vp=(1440, 900)):
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]})
    ctx.add_init_script(SAMPLER_JS)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Performance.enable")
    if throttle and throttle > 1:
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
    return ctx, page, cdp


def _metrics(cdp) -> dict:
    return {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}


def _delta(a, b):
    keys = ("TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "LayoutCount", "RecalcStyleCount")
    return {k: round(b.get(k, 0) - a.get(k, 0), 3) for k in keys}


def cls_on_load(pw, base) -> dict:
    b = pw.chromium.launch()
    out = {}
    for r in ROUTES + ["@lab/cutaway.html"]:
        for vp in ((1440, 900), (390, 844)):
            ctx, page, _ = _ctx(b, 1, vp)
            url = base.rsplit("/", 1)[0] + "/lab/cutaway.html" if r.startswith("@") else base + f"#/{r}"
            page.goto(url)
            page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=30000)
            page.wait_for_timeout(5000)
            shifts = page.evaluate("window.__perf.shifts")
            out[f"{r.lstrip('@')}@{vp[0]}"] = {"cls": round(sum(s["v"] for s in shifts), 4), "shifts": len(shifts),
                                               "largest": round(max((s["v"] for s in shifts), default=0), 4)}
            ctx.close()
    b.close()
    return out


def scenario_tour(b, base, throttle):
    ctx, page, cdp = _ctx(b, throttle)
    page.goto(base + "#/mission")
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=30000)
    page.wait_for_timeout(800)
    page.evaluate("window.__gnmTourStepMs = 3000")
    m0 = _metrics(cdp)
    page.evaluate("window.__perf.start()")
    page.locator("body").press("s")
    page.wait_for_selector(".story", timeout=5000)
    try:
        page.evaluate("window.__gnmStory && window.__gnmStory.play()")
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(20000)
    raw = page.evaluate("window.__perf.stop()")
    state = page.evaluate("window.__gnmStory ? window.__gnmStory.state() : null")
    m1 = _metrics(cdp)
    ctx.close()
    return {**frame_stats(raw), "tour_state_end": state, "cdp": _delta(m0, m1)}


def scenario_slider(b, base, throttle):
    ctx, page, cdp = _ctx(b, throttle)
    page.goto(base + "#/capital")
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=30000)
    page.wait_for_timeout(1000)
    sl = page.locator("[data-role=budget-slider]").first
    if sl.count() == 0:
        ctx.close()
        return {"error": "no [data-role=budget-slider] on #/capital"}
    sl.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    m0 = _metrics(cdp)
    page.evaluate("window.__perf.start()")
    page.evaluate("""() => new Promise((done) => {
      const s = document.querySelector('[data-role=budget-slider]'); const min = +s.min, max = +s.max, step = +s.step || 1;
      const T = 2000; let t0 = null;
      const set = (v) => { s.value = String(Math.round(v / step) * step); s.dispatchEvent(new Event('input', { bubbles: true })); };
      const f = (t) => { if (t0 === null) t0 = t; const k = (t - t0) / T;
        if (k <= 1) set(min + (max - min) * k); else if (k <= 2) set(max - (max - min) * (k - 1));
        if (k < 2) requestAnimationFrame(f); else { s.dispatchEvent(new Event('change', { bubbles: true })); setTimeout(done, 600); } };
      requestAnimationFrame(f); })""")
    raw = page.evaluate("window.__perf.stop()")
    m1 = _metrics(cdp)
    ctx.close()
    return {**frame_stats(raw), "cdp": _delta(m0, m1)}


def scenario_cutaway(b, base, throttle):
    ctx, page, cdp = _ctx(b, throttle)
    page.add_init_script("document.addEventListener('DOMContentLoaded', () => window.__perf && window.__perf.start())")
    m0 = _metrics(cdp)
    page.goto(base.rsplit("/", 1)[0] + "/lab/cutaway.html")
    page.wait_for_timeout(4000)
    raw = page.evaluate("window.__perf.stop()")
    ready = page.evaluate("document.documentElement.dataset.ready === 'true'")
    m1 = _metrics(cdp)
    ctx.close()
    return {**frame_stats(raw), "ready": ready, "cdp": _delta(m0, m1)}


# --------------------------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="run")
    ap.add_argument("--no-lighthouse", action="store_true")
    ap.add_argument("--throttle", type=float, default=4.0)
    ap.add_argument("--base", default=None, help="measure a deployed site instead of a local server, e.g. https://…/index.html")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {"label": a.label, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "targets": TARGETS,
               "environment": {"headless": True, "machine_note": "local macOS; headless Chromium (Playwright build); timings are indicative"}}
    import contextlib
    if a.base:
        summary["environment"]["machine_note"] = f"live site {a.base} measured from local macOS; headless Chromium (Playwright build)"
    with (contextlib.nullcontext(a.base) if a.base else AL.serve_docs()) as base, sync_playwright() as pw:
        chrome = pw.chromium.executable_path
        print("weights ...", flush=True)
        w = route_weights(pw, base)
        (OUT / "weights.json").write_text(json.dumps(w, indent=1))
        heavy = sorted(WORKSPACES[1:], key=lambda r: -(w[r]["view_js_bytes"] + w[r]["json_bytes"]))[:2]
        summary["weights"] = {r: {k: w[r][k] for k in ("view_js_bytes", "json_bytes", "total_bytes")} for r in ROUTES}
        summary["lighthouse_targets"] = ["mission"] + heavy
        print("heaviest workspaces:", heavy, flush=True)

        lh = {"available": False, "results": {}}
        if not a.no_lighthouse and shutil.which("npx"):
            for r in summary["lighthouse_targets"]:
                for preset in ("mobile", "desktop"):
                    print(f"lighthouse {r} {preset} ...", flush=True)
                    try:
                        res = run_lighthouse(base + f"#/{r}", r, preset, chrome)
                    except Exception as exc:  # noqa: BLE001
                        res = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                    lh["results"][f"{r}:{preset}"] = res
                    lh["available"] = lh["available"] or res.get("ok", False)
                    print("   ", {k: res.get(k) for k in ("performance", "accessibility", "cls", "lcp_ms", "tbt_ms", "error")}, flush=True)
        if not lh["available"]:
            lh["note"] = "Lighthouse unavailable (could not be fetched or run headless); fallback = Playwright + CDP metrics below."
        (OUT / "lighthouse_summary.json").write_text(json.dumps(lh, indent=1))
        summary["lighthouse"] = {k: {kk: v.get(kk) for kk in ("ok", "performance", "accessibility", "cls", "lcp_ms", "tbt_ms", "fcp_ms", "error")}
                                 for k, v in lh["results"].items()}
        summary["lighthouse_available"] = lh["available"]

        print("CLS on load ...", flush=True)
        cls = cls_on_load(pw, base)
        (OUT / "cls.json").write_text(json.dumps(cls, indent=1))
        summary["cls_on_load"] = cls
        summary["cls_max"] = max(v["cls"] for v in cls.values())

        anim = {}
        b = pw.chromium.launch()
        for thr in (1, a.throttle):
            for name, fn in (("tour", scenario_tour), ("slider", scenario_slider), ("cutaway", scenario_cutaway)):
                print(f"animation {name} throttle x{thr} ...", flush=True)
                try:
                    anim[f"{name}@x{thr:g}"] = fn(b, base, thr)
                except Exception as exc:  # noqa: BLE001
                    anim[f"{name}@x{thr:g}"] = {"error": f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"}
                print("   ", {k: anim[f'{name}@x{thr:g}'].get(k) for k in ("fps", "frame_p95_ms", "longtasks_over_200ms", "longest_task_ms", "error")}, flush=True)
        b.close()
        (OUT / "animations.json").write_text(json.dumps(anim, indent=1))
        summary["animations"] = anim

    # verdicts
    v = {}
    for k, r in summary["lighthouse"].items():
        if r.get("ok"):
            v[f"lighthouse {k}"] = {"performance>=85": r["performance"] >= TARGETS["performance"], "accessibility>=90": r["accessibility"] >= TARGETS["accessibility"],
                                    "cls<0.05": (r["cls"] or 0) < TARGETS["cls"]}
    v["cls_on_load<0.05 (all routes)"] = summary["cls_max"] < TARGETS["cls"]
    for k, r in summary["animations"].items():
        if "error" not in r:
            v[f"anim {k}"] = {"no longtask>200ms": r["longtasks_over_200ms"] == 0, "fps>=55": (r["fps"] or 0) >= TARGETS["fps"]}
    summary["verdicts"] = v
    (OUT / "perf_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(v, indent=1))


if __name__ == "__main__":
    main()
