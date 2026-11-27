"""Guided tour (v2.2): one calm rhythm per step (out -> move -> spotlight in -> card in), a fixed-size card that moves at
most once per transition and never covers its target, a page cross-fade on route changes with no blank view under a
visible card, quiet page motion while the tour is open, a scaleX progress bar that freezes on pause, instant steps under
reduced motion, and auto-advance in both motion modes. The full recorded frame check lives in
scripts/tour/record_and_check.py (reports/tour/frame_check.json)."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

READY = "window.__gnmStory && window.__gnmStory.state().ready"

# sample the tour every animation frame for `ms` after `act` runs (in the page, so no round-trip gaps)
SAMPLE_JS = r"""async ([ms, act]) => {
  const out = [];
  if (act === 'next') document.querySelector('.story .btn--primary').click();
  const t0 = performance.now();
  const box = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  await new Promise((res) => {
    const f = () => {
      const card = document.querySelector('.story-card'), spot = document.querySelector('.story-spot');
      const view = document.getElementById('view');
      const st = window.__gnmStory?.state();
      const tgt = window.__gnmStory?.target?.();
      out.push({ t: performance.now() - t0, card: card ? box(card) : null, cardOp: card ? +getComputedStyle(card).opacity : 0,
                 cardAnim: card ? card.getAnimations().length > 0 : false, spotAnim: spot ? spot.getAnimations().length > 0 : false,
                 freezes: document.querySelectorAll('.story-freeze').length,
                 text: card ? card.querySelector('.story-step').textContent + '|' + card.querySelector('.btn--primary').textContent : '',
                 spot: spot ? box(spot) : null, spotOp: spot ? +getComputedStyle(spot).opacity : 0, spots: document.querySelectorAll('.story-spot').length,
                 index: st?.index, phase: st?.phase, held: st?.held,
                 target: tgt && tgt.isConnected ? box(tgt) : null, skeleton: !!(tgt && (tgt.closest('.skeleton') || tgt.querySelector('.skeleton'))),
                 viewHidden: !view || getComputedStyle(view).visibility === 'hidden', viewEmpty: !view.querySelector('.card, section, figure, h1, h2'),
                 anims: document.getAnimations().filter((a) => a.effect?.target?.closest?.('.story')).length,
                 y: scrollY, tourActive: document.documentElement.classList.contains('tour-active') });
      if (performance.now() - t0 < ms) requestAnimationFrame(f); else res();
    };
    requestAnimationFrame(f);
  });
  return out;
}"""


def _start(page, step_ms=60000):
    page.evaluate(f"window.__gnmTourStepMs = {step_ms}")
    if page.locator("#story-btn").is_visible():
        page.locator("#story-btn").click()
    else:
        page.locator("body").press("s")   # phones: the top-bar Story button is hidden; S opens the same tour
    page.wait_for_function(READY, timeout=20000)


def _overlap(a, b):
    ox = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    oy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return ox * oy


@pytest.mark.parametrize("vp", ["1440", "390"])
def test_each_step_moves_card_once_and_never_blank(site, browser, vp):  # noqa: F811
    """Every Next: the dim stays up, a still copy holds the old page while the next one loads, the card's box changes at most
    once and never while visible, its text changes only while hidden, the spotlight is only on a real target and sits fully
    inside the free band, and #view is never hidden / empty while the card is visible."""
    ctx, page, problems = open_page(browser, site + "#/mission", vp, reduced=False)
    try:
        _start(page)
        n = len(json.loads((DOCS / "data" / "story.json").read_text())["steps"])
        for k in range(1, n):
            frames = page.evaluate(SAMPLE_JS, [2600, "next"])
            page.wait_for_function(READY, timeout=20000)
            assert all(f["spots"] == 1 for f in frames)
            assert all(f["tourActive"] for f in frames)
            # the dim never lifts between steps: the spotlight stays visible throughout
            assert all(f["spotOp"] > 0.99 for f in frames), ("dim lifted", k)
            still = [f for f in frames if not f["cardAnim"]]   # the phone sheet's slide is its entrance, not a move
            boxes = [tuple(f["card"][:2]) for f in still]
            changes = sum(1 for a, b in zip(boxes, boxes[1:]) if a != b)
            assert changes <= 1, (k, changes)
            for a, b in zip(still, still[1:]):
                if a["cardOp"] > 0.01 and b["cardOp"] > 0.01:
                    assert a["card"] == b["card"], ("card moved while visible", k, a, b)
            for a, b in zip(frames, frames[1:]):
                if a["text"] != b["text"]:
                    assert a["cardOp"] < 0.01 or b["cardOp"] < 0.01, ("card text changed while visible", k, a, b)
            assert any(f["freezes"] >= 1 for f in frames), "no still copy held the old page"
            for a, b in zip(frames, frames[1:]):   # the spotlight never moves while the card shows
                if a["cardOp"] > 0.01 and b["cardOp"] > 0.01:
                    assert a["spot"] == b["spot"], ("spotlight moved under a visible card", k, a, b)
            assert frames[-1]["freezes"] == 0
            for f in frames:
                if f["spotOp"] > 0.01 and not f["spotAnim"] and f["phase"] == "steady":
                    assert f["target"] and f["target"][2] > 8 and f["target"][3] > 8 and not f["skeleton"], (k, f)
                    assert f["spot"][2] > 8 and f["spot"][3] > 8, (k, f)
                if f["cardOp"] > 0.01:
                    assert not f["viewHidden"] and not f["viewEmpty"], ("blank view under a visible card", k, f)
            last = frames[-1]
            assert last["index"] == k and last["phase"] == "steady", last
            # the spotlight sits fully inside the free band (below the top bar, above the viewport edge or the sheet)
            bar = page.evaluate("document.querySelector('.topbar').getBoundingClientRect().bottom")
            sheet = page.evaluate("document.querySelector('.story-card').classList.contains('is-sheet')")
            low = last["card"][1] if sheet else page.evaluate("innerHeight")
            assert last["spot"][1] >= bar and last["spot"][1] + last["spot"][3] <= low, (k, last["spot"], bar, low)
            # the card does not cover the spotlit area
            assert _overlap(last["card"], last["spot"]) <= 24 * min(last["card"][2], last["spot"][2]), last
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
        assert not page.evaluate("document.documentElement.classList.contains('tour-active')")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_card_fixed_width_fitted_height_and_text_fits(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        _start(page)
        sizes, fits = set(), []
        for k in range(6):
            if k:
                page.keyboard.press("ArrowRight")
                page.wait_for_function(f"window.__gnmStory.state().index === {k} && window.__gnmStory.state().ready", timeout=20000)
            sizes.add(page.evaluate("document.querySelector('.story-card').getBoundingClientRect().width"))
            fits.append(page.evaluate("(() => { const t = document.querySelector('.story-text'); return t.scrollHeight <= t.clientHeight + 1; })()"))
            # the controls sit right under the text (no empty band inside the card)
            gap = page.evaluate("document.querySelector('.story-lower').getBoundingClientRect().top - document.querySelector('.story-text').getBoundingClientRect().bottom")
            assert -1 <= gap <= 4, gap
            # no height animation on the card (no FLIP layer, no running animation once steady)
            assert page.evaluate("document.querySelectorAll('.story-card-bg').length") == 0
            assert page.evaluate("document.querySelector('.story-card').getAnimations().length") == 0
        assert len(sizes) == 1, sizes
        assert all(fits), fits
        page.keyboard.press("Escape")
    finally:
        ctx.close()


def test_page_motion_is_quiet_while_tour_open(site, browser):  # noqa: F811
    """lib/motion.js goes instant while html.tour-active is set (chart draw-ins / count-ups never replay behind the card)."""
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        q = "import('./js/lib/motion.js').then((m) => [m.dur('slow'), m.reducedMotion(), m.prefersReducedMotion()])"
        assert page.evaluate(q) == [450, False, False]
        _start(page)
        assert page.evaluate(q) == [0, True, False]
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
        assert page.evaluate(q) == [450, False, False]
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


def test_controls_mid_transition_cancel_cleanly(site, browser):  # noqa: F811
    """Next / Back / Esc fired during a cross-page transition: the newest request wins, nothing stacks, focus returns."""
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        _start(page)
        page.evaluate("window.__t = window.__gnmStory")
        for _ in range(3):
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(120)
        page.keyboard.press("ArrowLeft")
        page.wait_for_function(READY, timeout=20000)
        s = page.evaluate("window.__gnmStory.state()")
        assert s["index"] == 2 and s["phase"] == "steady", s
        assert page.evaluate("document.querySelectorAll('.story-spot').length") == 1
        assert page.evaluate("+getComputedStyle(document.querySelector('.story-card')).opacity") == 1
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(200)          # mid transition
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
        s = page.evaluate("window.__t.state()")
        assert s["timers"] == 0 and s["loops"] == 0, s
        assert page.evaluate("document.activeElement && !document.activeElement.closest('.story') && document.activeElement !== document.body")
        assert page.evaluate("[...document.querySelectorAll('#view, .main > .disclaimer')].every((e) => !e.style.translate)")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_reduced_motion_steps_are_instant(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=True)
    try:
        _start(page)
        for _ in range(2):
            frames = page.evaluate(SAMPLE_JS, [900, "next"])
            assert all(f["anims"] == 0 for f in frames), "fade / card animation under reduced motion"
            assert all(f["cardOp"] in (0, 1) and f["spotOp"] in (0, 1) for f in frames), "partial opacity under reduced motion"
            ys = [f["y"] for f in frames]
            changes = sum(1 for a, b in zip(ys, ys[1:]) if a != b)
            assert changes <= 4, ys   # jumps, never a smooth ramp
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


def test_rail_tour_button_opens_playing(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        page.evaluate("window.__gnmTourStepMs = 60000")
        page.locator('.nav-item[data-route="tour"]').click()
        page.wait_for_function("window.__gnmStory && window.__gnmStory.state().playing", timeout=2000)
        page.keyboard.press("Escape")
        # the top-bar Story button opens paused
        page.locator("#story-btn").click()
        page.wait_for_function("window.__gnmStory", timeout=2000)
        page.wait_for_timeout(300)
        assert not page.evaluate("window.__gnmStory.state().playing")
        page.keyboard.press("Escape")
    finally:
        ctx.close()


def test_story_text_fits_card_budget():
    steps = json.loads((DOCS / "data" / "story.json").read_text())["steps"]
    for s in steps:
        assert len(s["body"]) <= 240 and len(s["body_simple"]) <= 240, (s["story_id"], len(s["body"]), len(s["body_simple"]))
