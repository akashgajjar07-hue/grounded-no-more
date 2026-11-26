"""Guided tour motion (release polish): one persistent spotlight that glides, a scaleX progress bar that freezes on
pause, instant steps under reduced motion, and auto-advance in both motion modes."""
from __future__ import annotations

import pytest

from _sitefx import browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

READY = "window.__gnmStory && window.__gnmStory.state().ready"

# sample the tour every animation frame for `ms` after `act` runs (in the page, so no round-trip gaps)
SAMPLE_JS = r"""async ([ms, act]) => {
  const spot = document.querySelector('.story-spot');
  const out = [];
  if (act === 'next') document.querySelector('.story .btn--primary').click();
  const t0 = performance.now();
  await new Promise((res) => {
    const f = () => {
      const s = document.querySelector('.story-spot');
      const cs = getComputedStyle(s);
      out.push({ t: performance.now() - t0, same: s === spot, count: document.querySelectorAll('.story-spot').length,
                 inline: s.style.transform, shadow: cs.boxShadow, opacity: cs.opacity,
                 anims: document.getAnimations().filter((a) => a.effect?.target?.closest?.('.story')).length,
                 gliding: window.__gnmStory?.state().gliding, index: window.__gnmStory?.state().index, y: scrollY });
      if (performance.now() - t0 < ms) requestAnimationFrame(f); else res();
    };
    requestAnimationFrame(f);
  });
  return out;
}"""


def _start(page, step_ms=60000):
    page.evaluate(f"window.__gnmTourStepMs = {step_ms}")
    page.locator("#story-btn").click()
    page.wait_for_function(READY, timeout=20000)


def test_one_spotlight_persists_and_glides(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        _start(page)
        page.evaluate("window.__spot0 = document.querySelector('.story-spot')")
        glided = False
        for _ in range(3):
            frames = page.evaluate(SAMPLE_JS, [1400, "next"])
            assert all(f["same"] and f["count"] == 1 for f in frames), "the spotlight node was re-created"
            # the dim backdrop never changes (no blink): same shadow, fully opaque, every frame
            assert len({f["shadow"] for f in frames}) == 1 and all(f["opacity"] == "1" for f in frames)
            glided = glided or any(f["gliding"] and "scale(" in f["inline"] for f in frames)
            page.wait_for_function(READY, timeout=20000)
        assert glided, "no step change glided the spotlight"
        assert page.evaluate("document.querySelector('.story-spot') === window.__spot0")
        # settles with no residue: placed by a plain translate (never left/top, so it is not a layout shift)
        tr = page.evaluate("document.querySelector('.story-spot').style.transform")
        assert tr.startswith("translate(") and "scale(" not in tr, tr
        assert page.evaluate("getComputedStyle(document.querySelector('.story-spot')).left") == "0px"
        page.keyboard.press("Escape")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_progress_bar_scalex_freezes_on_pause(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        _start(page, step_ms=6000)
        fill = "document.querySelector('.story-progress .is-current .story-fill')"
        assert page.evaluate(f"getComputedStyle({fill}).transitionDuration") in ("0s", "")   # no CSS transition to keep running
        page.evaluate("window.__gnmStory.play()")
        page.wait_for_timeout(1200)
        page.keyboard.press("Space")   # Space toggles Play → paused
        assert not page.evaluate("window.__gnmStory.state().playing")
        inline = page.evaluate(f"{fill}.style.transform")
        assert inline.startswith("scaleX(") and 0 < float(inline[7:-1]) < 1, inline
        a = page.evaluate(f"getComputedStyle({fill}).transform")
        e1 = page.evaluate("window.__gnmStory.state().elapsed")
        page.wait_for_timeout(500)
        b = page.evaluate(f"getComputedStyle({fill}).transform")
        assert a == b and page.evaluate("window.__gnmStory.state().elapsed") == e1, (a, b)
        assert abs(float(inline[7:-1]) - e1 / 6000) < 0.01   # the bar shows exactly the elapsed fraction
        page.keyboard.press("Space")   # resume continues from there
        page.wait_for_timeout(400)
        assert page.evaluate("window.__gnmStory.state().elapsed") > e1
        assert page.evaluate(f"getComputedStyle({fill}).transform") != b
        page.keyboard.press("Escape")
    finally:
        ctx.close()


def test_reduced_motion_steps_are_instant(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=True)
    try:
        _start(page)
        for _ in range(2):
            frames = page.evaluate(SAMPLE_JS, [900, "next"])
            assert all("scale(" not in f["inline"] for f in frames), "spotlight glided under reduced motion"
            assert len({f["inline"] for f in frames}) <= 4, "spotlight moved through intermediate positions"
            assert all(f["anims"] == 0 for f in frames), "crossfade / card animation under reduced motion"
            assert not any(f["gliding"] for f in frames)
            ys = [f["y"] for f in frames]
            # no smooth scroll: only a few jumps (route change, framing, async-layout corrections); a 450 ms ramp would
            # change the scroll position on ~25 consecutive frames
            changes = sum(1 for a, b in zip(ys, ys[1:]) if a != b)
            assert changes <= 6, ys
            page.wait_for_function(READY, timeout=20000)
        page.keyboard.press("Escape")
    finally:
        ctx.close()


@pytest.mark.parametrize("reduced", [False, True])
def test_tour_auto_advances(site, browser, reduced):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=reduced)
    try:
        page.evaluate("window.__gnmTourStepMs = 1500")
        page.locator('[data-story="mission-start"]').click()   # the 60-second tour opens already playing
        page.wait_for_function("window.__gnmStory && window.__gnmStory.state().playing", timeout=2000)
        page.wait_for_function("window.__gnmStory.state().index >= 2", timeout=20000)
        assert page.evaluate("window.__gnmStory.state().playing")
        assert page.evaluate("document.querySelectorAll('.story-spot').length") == 1
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()
