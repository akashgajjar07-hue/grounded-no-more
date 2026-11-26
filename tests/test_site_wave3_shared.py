"""Browser checks for the wave-3 shared layer (wave3-S): formatters, slider aria-valuetext, teal linter, edge audit,
shortcuts while a drawer is open (F1) and story framing (top bar offset, mobile_selector, collapsible sheet)."""
from __future__ import annotations

import json

import pytest

from _sitefx import AUDIT_JS, DOCS, EDGE_JS, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

FMT_JS = r"""async () => {
  const T = await import('./js/charts/theme.js');
  const U = await import('./js/ui.js');
  const out = {
    money: [T.fmtMoney(137650), T.fmtMoney(1944847), T.fmtMoney(41853427), T.fmtMoney(950)],
    count: [T.fmtCount(47977), T.fmtCount('1450'), T.fmtCount(null)],
    sim: [T.fmtSimTime('2023-01-18T01:00Z'), T.fmtSimTime(103 * 168 + 3 * 24 + 6), T.fmtSimTime(0), T.fmtSimTime(null)],
    stamp: [T.fmtStamp('2026-11-26T02:25:21Z'), T.fmtStamp('2026-11-26T02:25:21.525168+00:00', { year: true })],
    mult: [T.fmtMult(2), T.fmtMult(0.5), T.TIMES],
    enums: [T.fmtEnum('OVERDUE_REPAIR'), T.fmtEnum('EU_VENDOR'), T.fmtEnum('shop_return'), T.fmtEnum('Already prose')],
    plural: [T.plural(3, 'option'), T.plural(1, 'option'), T.plural(1200, 'unit')],
  };
  // slider: aria-valuetext from valueText (else format), kept in sync on input and setValue
  const s = U.slider({ label: 'Capital', min: 0, max: 2, value: 1, format: (i) => ['a', 'b', 'c'][i], valueText: (i) => `plan ${i}` });
  document.body.append(s);
  out.vt0 = s.input.getAttribute('aria-valuetext');
  s.input.value = 2; s.input.dispatchEvent(new Event('input'));
  out.vt1 = s.input.getAttribute('aria-valuetext');
  s.setValue(0);
  out.vt2 = [s.input.getAttribute('aria-valuetext'), s.querySelector('output').textContent];
  const s2 = U.slider({ label: 'AED', min: 0, max: 5e7, step: 1, value: 41850000, format: T.fmtAED });
  out.vt3 = s2.input.getAttribute('aria-valuetext');
  const r = document.createElement('input'); r.type = 'range'; r.min = 0; r.max = 10; r.value = 4;
  const up = U.bindValueText(r, (v) => `${v} units`); out.vt4 = r.getAttribute('aria-valuetext');
  r.value = 7; up(); out.vt5 = r.getAttribute('aria-valuetext');
  s.remove(); s2.remove();
  // teal linter: two teal-labelled categories → 2; one teal series + neutral others → 1
  const mk = (labels) => {
    const host = document.createElement('div'); document.body.append(host);
    const svg = T.svgIn(host, 300, 100);
    labels.forEach(([t, c], i) => {
      T.markSeries(svg.append('rect').attr('x', 0).attr('y', i * 20).attr('width', 50).attr('height', 10).attr('fill', c), t);
      T.directLabel(svg, { x: 60, y: i * 20 + 5, text: t, color: c });
    });
    const n = T.lintTeal(host); host.remove(); return n;
  };
  out.tealBad = mk([['EU vendor', T.theme.series.recommended], ['Willemain', T.theme.series.recommended], ['Other', T.theme.series.neutral]]);
  out.tealOk = mk([['I125', T.theme.series.recommended], ['P2', T.theme.series.neutral], ['P0', T.theme.series.baseline]]);
  out.pick = T.pickSeries('recommended', 'I125', 'test') === T.theme.series.recommended && T.pickSeries('nope') === T.theme.series.neutral;
  return out;
}"""


def test_wave3_formatters_slider_and_teal_lint(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", "1440")
    try:
        out = page.evaluate(FMT_JS)
    finally:
        ctx.close()
    assert out["money"] == ["AED 138k", "AED 1.9M", "AED 41.9M", "AED 950"]
    assert out["count"] == ["47,977", "1,450", "—"]
    assert out["sim"] == ["W2 · d3 01:00", "W103 · d4 06:00", "W0 · d1 00:00", "—"]
    assert out["stamp"] == ["26 Nov 02:25 UTC", "26 Nov 2026 02:25 UTC"]
    assert out["mult"] == ["×2.0", "×0.5", "×"]
    assert out["enums"] == ["Overdue repair", "EU vendor", "Shop return", "Already prose"]
    assert out["plural"] == ["3 options", "1 option", "1,200 units"]
    assert out["vt0"] == "plan 1" and out["vt1"] == "plan 2" and out["vt2"] == ["plan 0", "a"]
    assert out["vt3"] == "AED 41.9M" and out["vt4"] == "4 units" and out["vt5"] == "7 units"
    assert sorted(out["tealBad"]) == ["EU vendor", "Willemain"]
    assert out["tealOk"] == ["I125"]
    assert out["pick"]
    assert not [p for p in problems if "pickSeries" not in p], problems


AUDIT_FIXTURE_JS = r"""async () => {
  const T = await import('./js/charts/theme.js');
  const view = document.querySelector('#view');
  const card = document.createElement('section'); card.className = 'card'; card.style.width = '300px';
  card.innerHTML = '<p class="ok-ellipsis" title="A deliberately long single line that is clipped with an ellipsis" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:120px">A deliberately long single line that is clipped with an ellipsis</p>'
    + '<p class="bad-clip" style="white-space:nowrap;overflow:hidden;width:120px">A long single line that is silently clipped without a title</p>';
  view.prepend(card);
  const sh = document.createElement('div'); card.append(sh);   // svgIn() replaces its host's children
  const svg = T.svgIn(sh, 280, 60);
  svg.append('text').attr('class', 'bad-svg').attr('x', 200).attr('y', 30).text('1,890 h fewer AOG hours than the ex post replay');
  svg.append('text').attr('class', 'ok-svg').attr('x', 10).attr('y', 50).text('fits');
  const wide = document.createElement('p'); wide.className = 'bad-html'; wide.style.cssText = 'white-space:nowrap;margin-left:200px';
  wide.textContent = 'This sentence runs past the right edge of its card';
  card.append(wide);
  await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 30)));
  const res = (AUDIT)();
  card.remove();
  return res;
}"""


def test_edge_and_ellipsis_audit(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", "390")
    try:
        res = page.evaluate(AUDIT_FIXTURE_JS.replace("AUDIT", AUDIT_JS))
    finally:
        ctx.close()
    over = " ".join(res["overflow"])
    edge = " ".join(res["edge"])
    assert "bad-clip" in over and "ok-ellipsis" not in over, res["overflow"]
    assert "bad-svg" in edge and "bad-html" in edge, res["edge"]
    assert "ok-svg" not in edge and "ok-ellipsis" not in edge, res["edge"]


def _hash(page):
    return page.evaluate("location.hash")


def _overlays(page):
    return page.evaluate("document.querySelectorAll('.drawer, .modal, .scrim').length")


@pytest.mark.parametrize("vp", ["1440", "390"])
def test_number_keys_work_while_a_drawer_is_open(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32&pn=GN-32-R014", vp)
    try:
        page.wait_for_selector(".drawer.is-open", timeout=8000)
        page.keyboard.press("Escape")                      # Esc still closes the drawer first, route unchanged
        page.wait_for_timeout(400)
        assert _overlays(page) == 0 and _hash(page).startswith("#/parts")
        page.goto(site + "#/parts?ata=32&pn=GN-32-R014")
        page.wait_for_selector(".drawer.is-open", timeout=8000)
        page.keyboard.press("4")
        page.wait_for_function("location.hash.startsWith('#/rotables') && document.documentElement.dataset.ready === 'true'")
        page.wait_for_timeout(500)
        assert _overlays(page) == 0, "drawer left open after shortcut"
        assert not page.evaluate("document.documentElement.classList.contains('has-overlay')")
        # help modal → number key navigates too
        page.keyboard.press("?")
        page.wait_for_selector(".modal", timeout=3000)
        page.keyboard.press("0")
        page.wait_for_function("location.hash.startsWith('#/method')")
        page.wait_for_timeout(400)
        assert _overlays(page) == 0
        # actions drawer → 1 goes to mission
        page.evaluate("location.hash = '#/actions'")
        page.wait_for_selector(".pac-row", timeout=8000)
        page.locator(".pac-row").first.click()
        page.wait_for_selector(".drawer.is-open", timeout=5000)
        page.keyboard.press("1")
        page.wait_for_function("location.hash.startsWith('#/mission')")
        page.wait_for_timeout(500)
        assert _overlays(page) == 0
        # S starts the story from an open drawer
        page.evaluate("location.hash = '#/parts?ata=32&pn=GN-32-R014'")
        page.wait_for_selector(".drawer.is-open", timeout=8000)
        page.keyboard.press("s")
        page.wait_for_selector(".story", timeout=5000)
        assert page.evaluate("document.querySelectorAll('.drawer.is-open').length") == 0
        assert not problems, problems
    finally:
        ctx.close()


FRAME_JS = r"""() => {
  const spot = document.querySelector('.story-spot').getBoundingClientRect();
  const card = document.querySelector('.story-card');
  const c = card.getBoundingClientRect();
  const bar = document.querySelector('.topbar').getBoundingClientRect().bottom;
  return { bar, spotTop: spot.top, spotBottom: spot.bottom, spotH: spot.height, cardTop: c.top, cardBottom: c.bottom, cardH: c.height,
           sheet: card.classList.contains('is-sheet'), peek: card.classList.contains('is-peek'), vh: innerHeight,
           grab: !!card.querySelector('.story-grab') && getComputedStyle(card.querySelector('.story-grab')).display !== 'none',
           step: document.querySelector('.story-step').textContent };
}"""


def _story_steps(page, n):
    """Start the tour and yield the frame metrics of each of the first n steps."""
    page.keyboard.press("s")
    out = []
    for i in range(n):
        page.wait_for_function("document.querySelector('.story') && !document.querySelector('.story').hasAttribute('aria-busy')", timeout=20000)
        page.wait_for_timeout(250)
        out.append(page.evaluate(FRAME_JS))
        if i < n - 1:
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(100)
    return out


def test_story_framing_desktop(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        frames = _story_steps(page, 8)
        for f in frames:
            assert f["spotTop"] >= f["bar"] + 1, f            # the spotlight never sits under the sticky bar
            assert f["cardTop"] >= f["bar"] + 15, f           # nor does the card
            assert f["cardBottom"] <= f["vh"], f
        for f in frames[3:7]:                                  # steps 4-7: headline sits >= 8 px below the bar
            assert f["spotTop"] >= f["bar"] + 4, f
        assert not problems, problems
    finally:
        ctx.close()


def test_story_mobile_selector_and_peek(site, browser):  # noqa: F811
    story = json.load(open(DOCS / "data" / "story.json"))
    assert any(s.get("mobile_selector") for s in story["steps"])
    ctx, page, problems = open_page(browser, site + "#/mission", "390")
    try:
        frames = _story_steps(page, 8)
        for i, (f, s) in enumerate(zip(frames, story["steps"])):
            assert f["sheet"] and f["grab"], f
            assert f["spotTop"] >= f["bar"] + 1, f
            if f["peek"]:
                assert f["cardH"] <= max(0.25 * f["vh"], 184) + 2, f
            # the sheet covers at most 24 px of a target that fits above a peek sheet
            if f["spotH"] <= f["vh"] - f["bar"] - max(0.25 * f["vh"], 184) - 16:
                assert f["spotBottom"] - f["cardTop"] <= 32, (i + 1, f)
            if s.get("mobile_selector"):
                h = page.evaluate("(s) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().height : null; }", s["mobile_selector"])
                if i == 7 and h is not None:
                    assert abs(f["spotH"] - (h + 16)) < 3, (s["mobile_selector"], f, h)
        # the grab handle toggles the sheet
        before = page.evaluate("document.querySelector('.story-card').classList.contains('is-peek')")
        page.click(".story-grab")
        page.wait_for_timeout(150)
        after = page.evaluate("document.querySelector('.story-card').classList.contains('is-peek')")
        assert before != after
        assert not problems, problems
    finally:
        ctx.close()
