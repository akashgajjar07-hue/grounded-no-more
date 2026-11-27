#!/usr/bin/env python3
"""Record the demo video, README hero screenshot and README GIF with Playwright.

    python scripts/record_demo.py                 # all three, from a local `python -m http.server` of docs/ (default)
    python scripts/record_demo.py --only video|hero|gif
    python scripts/record_demo.py --url https://akashgajjar07-hue.github.io/grounded-no-more/   # the live site instead

Outputs
* presentations/demo.webm      1440x900, ~75 s, following the private walkthrough script: the landing (Mission Control,
                               Simple mode) -> the 60-second tour started from its own button and run in the tour's
                               Play mode (auto-advance, no manual presses; the step count is read from
                               docs/data/story.json, six in v2.1) -> Pause at the last step -> Skip tour -> a pass over
                               the Readiness Frontier budget slider -> back to the landing.
                               The step length is the tour's own clock (MOTION.tourStep) unless --step-ms sets the
                               tour's window.__gnmTourStepMs hook; the default here is 9 s so the narration fits.
* docs/assets/readme/hero.png  1440x900 screenshot of Mission Control above the fold.
* docs/assets/readme/demo.gif  ~10 s GIF of the Capital Optimiser budget slider (Pillow, no ffmpeg needed), <= 6 MB.

Nothing is posted anywhere; the script only reads the public site.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LIVE = "https://akashgajjar07-hue.github.io/grounded-no-more/"
VIEW = {"width": 1440, "height": 900}
STEP_MS = 9000  # tour step length for the video (the narration in the private walkthrough script is timed to it)
INTRO_MS = 6000  # landing hold before the tour starts


@contextlib.contextmanager
def local_server():
    """Serve docs/ with `python -m http.server` on a free port; yields the base URL."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                             "--directory", str(DOCS)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}/"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base + "data/story.json", timeout=1).read()
                break
            except Exception:
                time.sleep(0.2)
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def wait_ready(page, selector, timeout=30000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.evaluate("document.fonts && document.fonts.ready")
    page.wait_for_timeout(1200)


def n_story_steps():
    """Story step count from docs/data/story.json (the file the site serves)."""
    return len(json.loads((DOCS / "data" / "story.json").read_text())["steps"])


def tour_play(page):
    """Press the tour's own Play button (auto-advance). Falls back to the Space key, which toggles Play in the tour."""
    st = tour_state(page)
    if st and st.get("playing"):
        return  # v2.1: the '60-second tour' button opens the tour already playing; pressing Play would pause it
    loc = page.locator(".story-card .story-play")
    try:
        if loc.count() and loc.first.is_visible():
            loc.first.click()
            return
    except Exception:
        pass
    page.keyboard.press("Space")


def tour_state(page):
    """{index, playing, elapsed, stepMs, ...} from the tour's test API (window.__gnmStory.state())."""
    return page.evaluate("() => window.__gnmStory && window.__gnmStory.state ? window.__gnmStory.state() : null")


def tour_exit(page):
    """Leave the tour with its Skip button (Esc as a fallback)."""
    loc = page.locator(".story-card .story-skip")
    try:
        if loc.count() and loc.first.is_visible():
            loc.first.click()
            return
    except Exception:
        pass
    page.keyboard.press("Escape")


def capital_slider(page):
    sl = page.locator("#main input[type=range], main input[type=range], input[type=range]").first
    sl.wait_for(state="attached", timeout=30000)
    return sl


def frame_chart(page, sl):
    """Focus the slider without scrolling, then put the top of the frontier card at the top of the viewport."""
    sl.evaluate("e => e.focus({preventScroll: true})")
    page.evaluate("""() => { const c = document.querySelector("[data-story='frontier-chart']");
        (c.closest('.card') || c).scrollIntoView({block: 'start'}); }""")
    page.wait_for_timeout(500)


def sweep_slider(page, sl, steps, dwell_ms, on_frame=None):
    """Move the budget slider from its minimum to its maximum in `steps` keyboard steps."""
    frame_chart(page, sl)
    page.keyboard.press("Home")
    page.wait_for_timeout(dwell_ms)
    mn, mx, st = (float(sl.get_attribute(a) or d) for a, d in (("min", 0), ("max", 100), ("step", 1)))
    total = max(1, round((mx - mn) / st))
    per = max(1, total // steps)
    for _ in range(steps):
        for _ in range(per):
            page.keyboard.press("ArrowRight")
        page.wait_for_timeout(dwell_ms)
        if on_frame:
            on_frame()


def start_story(page):
    """Open the guided tour from the landing's own '60-second tour' button, else the top-bar Story button."""
    for loc in (page.locator("[data-story='mission-start']"), page.locator("#story-btn"),
                page.get_by_role("button", name="60-second tour")):
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                break
        except Exception:
            pass
    page.wait_for_selector(".story-card", state="visible", timeout=10000)


def story_state(page):
    return page.evaluate("""() => { const c = document.querySelector('.story-card');
        return c ? {hash: location.hash, text: c.innerText.split(String.fromCharCode(10)).slice(0, 3).join(' | ')} : null; }""")


def record_video(base, out, stills_dir=None, step_ms=STEP_MS):
    from playwright.sync_api import sync_playwright
    tmp = Path(tempfile.mkdtemp(prefix="gnm-video-"))
    t0 = time.time()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport=VIEW, record_video_dir=str(tmp), record_video_size=VIEW, device_scale_factor=1)
        if step_ms:
            ctx.add_init_script(f"window.__gnmTourStepMs = {int(step_ms)};")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "#/mission", wait_until="networkidle")
        wait_ready(page, "[data-story='mission-hero']")
        n = n_story_steps()
        page.wait_for_timeout(INTRO_MS)  # the landing: title, subtitle, stat strip
        start_story(page)
        page.wait_for_timeout(800)
        tour_play(page)  # Play mode: the tour advances itself
        st = tour_state(page) or {}
        per = int(st.get("stepMs") or step_ms or 7000)
        log, seen, deadline = [], set(), time.time() + n * per / 1000 + 30
        while time.time() < deadline:
            st = tour_state(page)
            if st is None:
                break
            if st["index"] not in seen:
                seen.add(st["index"])
                page.wait_for_timeout(1500)  # let the step settle before logging / stills
                log.append(story_state(page))
                if stills_dir:
                    page.screenshot(path=str(Path(stills_dir) / f"step-{st['index'] + 1}.png"))
            if st["index"] == n - 1 and not st["playing"]:
                break  # the last step's bar filled and the tour stopped itself (Play resets)
            page.wait_for_timeout(250)
        for i, s_ in enumerate(log, 1):
            print(f"  step {i}: {s_}")
        if len(seen) != n:
            print(f"  ! tour showed {len(seen)} of {n} steps in Play mode")
        page.wait_for_timeout(1200)
        tour_exit(page)
        page.wait_for_timeout(600)
        page.goto(base + "#/capital")
        wait_ready(page, "[data-story='frontier-chart']")
        page.wait_for_timeout(1500)
        sl = capital_slider(page)
        sweep_slider(page, sl, steps=12, dwell_ms=700)
        if stills_dir:
            page.screenshot(path=str(Path(stills_dir) / "capital.png"))
        page.wait_for_timeout(1500)
        page.goto(base + "#/mission")
        wait_ready(page, "[data-story='mission-hero']")
        page.wait_for_timeout(3000)  # closing frame on the landing
        if errors:
            print(f"  ! page errors: {errors}")
        video = page.video
        ctx.close()
        src = Path(video.path())
        b.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), out)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"video: {out} ({out.stat().st_size / 1e6:.1f} MB, ~{time.time() - t0:.0f} s wall clock, {n} tour steps "
          f"at {per / 1000:g} s)")


def hero(base, out):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport=VIEW, device_scale_factor=1)
        page.goto(base + "#/mission", wait_until="networkidle")
        wait_ready(page, "[data-story='mission-kpis']")
        page.wait_for_timeout(2500)  # map + charts
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out))
        b.close()
    print(f"hero: {out} ({out.stat().st_size / 1e3:.0f} kB)")


def gif(base, out, width=960, max_mb=6.0):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    frames = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport=VIEW, device_scale_factor=1)
        page.goto(base + "#/capital", wait_until="networkidle")
        wait_ready(page, "[data-story='frontier-chart']")
        page.wait_for_timeout(1500)
        sl = capital_slider(page)
        frame_chart(page, sl)

        def grab():
            frames.append(Image.open(io.BytesIO(page.screenshot())).convert("RGB"))

        page.keyboard.press("Home")
        page.wait_for_timeout(500)
        grab()
        mn, mx, st = (float(sl.get_attribute(a) or d) for a, d in (("min", 0), ("max", 100), ("step", 1)))
        total = max(1, round((mx - mn) / st))
        nfr = 40
        per = max(1, total // nfr)
        for _ in range(nfr):
            for _ in range(per):
                page.keyboard.press("ArrowRight")
            page.wait_for_timeout(180)
            grab()
        b.close()
    h = round(width * VIEW["height"] / VIEW["width"])
    small = [f.resize((width, h), Image.LANCZOS) for f in frames]
    pal = [s.quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE) for s in small]
    durs = [900] + [220] * (len(pal) - 2) + [1600]
    out.parent.mkdir(parents=True, exist_ok=True)
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durs, loop=0, optimize=True, disposal=1)
    if out.stat().st_size > max_mb * 1e6 and width > 640:
        return gif(base, out, width=width - 160, max_mb=max_mb)
    print(f"gif: {out} ({out.stat().st_size / 1e6:.2f} MB, {len(pal)} frames, {sum(durs) / 1000:.1f} s, {width}px)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None, help=f"site to record (default: local server of docs/; live: {LIVE})")
    ap.add_argument("--only", choices=["video", "hero", "gif"])
    ap.add_argument("--stills", default=None, help="directory for per-step stills taken during the video")
    ap.add_argument("--step-ms", type=int, default=STEP_MS,
                    help="tour step length in Play mode (0 = the tour's own MOTION.tourStep); default %(default)s")
    a = ap.parse_args()
    ctx = local_server() if a.url is None else contextlib.nullcontext(a.url)
    with ctx as url:
        base = url if url.endswith("/") else url + "/"
        print(f"recording from {base}")
        if a.only in (None, "hero"):
            hero(base, ROOT / "docs" / "assets" / "readme" / "hero.png")
        if a.only in (None, "gif"):
            gif(base, ROOT / "docs" / "assets" / "readme" / "demo.gif")
        if a.only in (None, "video"):
            record_video(base, ROOT / "presentations" / "demo.webm", a.stills, a.step_ms)


if __name__ == "__main__":
    main()
