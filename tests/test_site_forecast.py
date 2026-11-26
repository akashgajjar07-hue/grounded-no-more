"""Browser tests for 03 Forecast Lab (screens-B; v2.1 Simple / Expert modes)."""
from __future__ import annotations

import json
import re

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


def set_mode(page, mode):
    """Switch the reading mode in place; the router re-renders the view."""
    page.evaluate(f"import('./js/lib/mode.js').then((m) => m.setMode('{mode}'))")
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=15000)
    page.wait_for_timeout(900)
    assert page.evaluate("document.body.classList.contains('mode-' + %r)" % mode)


def _forecast():
    files = json.loads((DOCS / "data/manifest.json").read_text()).get("files", [])
    name = "forecast" if "forecast" in files else "fixtures/forecast"
    return json.loads((DOCS / f"data/{name}.json").read_text())


ROUTES = [
    "#/forecast",
    "#/forecast?class=intermittent&part=R",
    "#/forecast?class=intermittent&part=R&win=holdout",
    "#/forecast?class=smooth&part=C",
    "#/forecast?pn=GN-32-R014",
]


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("route", ROUTES)
def test_forecast_renders_clean(site, browser, vp, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, vp)
    try:
        audit(page, problems, min_frames=6)
        assert page.locator('[data-story="forecast-demand-strip"]').count() == 1
        assert page.locator(".disclaimer").count() == 1
    finally:
        ctx.close()


def test_leaderboard_is_dot_plot_with_champion_and_zero_excluded(site, browser):  # noqa: F811
    f = _forecast()
    ctx, page, problems = open_page(browser, site + "#/forecast?class=intermittent&part=R", "1440")
    try:
        set_mode(page, "expert")
        board = page.locator('[data-story="forecast-leaderboard"]')
        n = sum(1 for r in f["leaderboard"] if r["demand_class"] == "intermittent" and r["part_class"] == "R" and r.get("split", "selection") == "selection")
        assert board.locator("g.fl-row").count() == n
        assert board.locator("g.fl-row.is-champ").count() == 1
        assert board.locator("rect.fl-bar").count() == 0  # not bars
        if any(r["method"] == "zero" for r in f["leaderboard"]):
            assert board.locator("g.fl-row.is-zero").count() == 1
        txt = page.locator(".fl-champ").inner_text()
        assert "excluded from champion eligibility" in txt
        champ = next(c for c in f["champions"] if c["demand_class"] == "intermittent" and c["part_class"] == "R")
        assert f"{champ['mase']:.2f}" in txt   # wave 4: card precision matches the chart (0.85, not 0.848)
        # selection / holdout toggle
        page.locator('.seg[aria-label="Evaluation window"] button[data-value="holdout"]').click()
        page.wait_for_timeout(400)
        assert "win=holdout" in page.url
        assert "holdout" in board.locator('[data-role="board-key"]').inner_text()
        assert not problems, problems
    finally:
        ctx.close()


def test_holdout_check_and_naive_rank(site, browser):  # noqa: F811
    f = _forecast()
    chk = f.get("champion_check") or []
    ctx, page, problems = open_page(browser, site + "#/forecast", "1440")
    try:
        frame = page.locator('[data-story="forecast-holdout-check"]')
        assert frame.locator("g.fl-rank").count() == len(chk)
        naive = [r for r in chk if r["champion"] == "naive" and r["part_class"] == "R"]
        if naive:
            r = naive[0]
            assert f"{r['champion_rank']}/{r['n_methods']}" in frame.inner_text()
        assert not problems, problems
    finally:
        ctx.close()


def test_monash_real_panel_has_attribution(site, browser):  # noqa: F811
    mo = _forecast().get("monash", {})
    ctx, page, problems = open_page(browser, site + "#/forecast", "1440")
    try:
        panel = page.locator('[data-story="forecast-monash"]')
        txt = panel.inner_text()
        if mo.get("status") == "ok":
            assert panel.locator(".chip-prov--real").count() >= 1
            assert panel.locator(".chip-prov--derived").count() >= 1
            assert "CC BY 4.0" in txt
            assert panel.locator('a[href*="zenodo"]').count() == 1
        else:
            assert "not run" in txt
        assert not problems, problems
    finally:
        ctx.close()


def test_ltd_marks_reorder_point_and_truth_note(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/forecast", "1440")
    try:
        set_mode(page, "expert")
        ltd = page.locator('[data-story="forecast-ltd"]')
        assert ltd.locator("rect.fl-bar").count() >= 2
        assert ltd.locator("line.fl-rop").count() == 1
        assert "quantile" in ltd.inner_text()
        assert "hidden truth" in page.locator('[data-story="forecast-truth"]').locator("xpath=..").inner_text()
        assert page.locator('[data-story="forecast-stock-eval"] .fl-pt').count() >= 2
        assert not problems, problems
    finally:
        ctx.close()


# ----------------------------------------------------------------------------- design wave 2 (agent B)
HITS_JS = r"""([labels, marks]) => {
  const R = (s) => [...document.querySelectorAll(s)].map((e) => e.getBoundingClientRect()).filter((r) => r.width && r.height);
  const L = R(labels), M = marks ? R(marks) : L;
  const hits = [];
  L.forEach((a, i) => M.forEach((b, j) => { if (marks || j > i) if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) hits.push([i, j]); }));
  return hits;
}"""


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_forecast_labels_clear_of_marks(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/forecast", vp)
    try:
        se = '[data-story="forecast-stock-eval"]'
        assert page.locator(f"{se} .gnm-label").count() >= 1
        assert not page.evaluate(HITS_JS, [f"{se} .gnm-label", f"{se} .fl-pt circle"])
        assert not page.evaluate(HITS_JS, [f"{se} .gnm-label", None])
        ltd = '[data-story="forecast-ltd"]'
        assert not page.evaluate(HITS_JS, [f"{ltd} .gnm-label", f"{ltd} rect.fl-bar"])
        # reference lines are neutral (no amber .fl-ref), copper only on the vendor-quoted baseline
        assert page.locator(".fl-ref").count() == 0
        assert page.locator('[data-story="forecast-leaderboard"] .gnm-ref-line').count() == 1
        copper = page.evaluate("() => [...document.querySelectorAll('#view svg *')].filter((e) => /196, 127, 82/.test(getComputedStyle(e).fill + getComputedStyle(e).stroke)).map((e) => `${e.getAttribute('class')} ${e.textContent}`)")
        assert all("fl-db" in c or "vendor" in c for c in copper), copper
        heads = page.evaluate("() => [...document.querySelectorAll('#view .chart-headline')].map((e) => e.textContent.trim())")
        assert heads and all(len(h) <= 90 for h in heads), heads
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave3_colour_discipline(site, browser, vp):  # noqa: F811
    """Review 2: vendor-quoted is not copper, the frozen champion is not teal, at most one teal series per chart,
    half-width headlines stay short enough for two lines."""
    ctx, page, problems = open_page(browser, site + "#/forecast", vp)
    try:
        res = page.evaluate("""() => {
          const col = (e) => getComputedStyle(e).fill;
          const q = [...document.querySelectorAll('.fl-db-q')].map(col);
          const champ = [...document.querySelectorAll('.fl-row.is-champ .fl-dot')].map(col);
          const tealPts = [...document.querySelectorAll('.fl-pt circle')].filter((c) => /34, 199, 184/.test(getComputedStyle(c).fill)).length;
          const lbTeal = [...document.querySelectorAll('[data-story="forecast-leaderboard"] .fl-dot')].filter((c) => /34, 199, 184/.test(col(c))).length;
          const heads = ['forecast-ltd', 'forecast-stock-eval', 'forecast-truth'].map((s) => document.querySelector(`[data-story="${s}"] .chart-headline`)?.textContent.trim() || '');
          return { q, champ, tealPts, lbTeal, heads };
        }""")
        assert res["q"] and not any("196, 127, 82" in c for c in res["q"]), res["q"]
        assert res["champ"] and not any("34, 199, 184" in c for c in res["champ"]), res["champ"]
        assert res["tealPts"] <= 1 and res["lbTeal"] <= 1, res
        assert all(0 < len(h) <= 72 for h in res["heads"]), res["heads"]
        assert page.locator(".gnm-annot-text", has_text="Frozen champion").count() == 0
        assert not problems, problems
    finally:
        ctx.close()


# ----------------------------------------------------------------------------- v2.1 (PAGE-3): modes, honest result, readability
METHOD_NAMES = r"\b(Croston|SBA|TSB|ADIDA|IMAPA|Willemain|MASE|Naive|Reliability-exposure)\b"


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_modes_render_clean(site, browser, vp, mode):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/forecast", vp)
    try:
        if mode == "expert":
            set_mode(page, "expert")
        audit(page, problems, min_frames=7)
        assert page.locator('[data-role="intro3"]').count() == 1
        assert page.locator('[data-story="forecast-honest"] [data-role="scope"]').count() == 1
        # the grey first-use bracket (.term-expert) is the one allowed place for an expert term in Simple mode
        text = page.evaluate("""() => { const v = document.querySelector('#view');
          const hid = [...v.querySelectorAll('.term-expert')]; hid.forEach((e) => { e.dataset.t = e.textContent; e.textContent = ''; });
          const t = v.innerText; hid.forEach((e) => { e.textContent = e.dataset.t; }); return t; }""")
        names = re.findall(METHOD_NAMES, text)
        if mode == "simple":
            assert not names, f"method names visible in Simple mode: {sorted(set(names))}"
            assert not re.search(r"\b(P0|P1|P2|I125)\b", text)
        else:
            assert {"SBA", "MASE"} <= set(names), sorted(set(names))
    finally:
        ctx.close()


@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_honest_result_from_data(site, browser, mode):  # noqa: F811
    """The three findings: champions held in N of M groups, the intermittent-rotable champion's holdout rank,
    history-fitted vs supplier-quoted removal-rate error. Every number from forecast.json."""
    f = _forecast()
    chk = f["champion_check"]
    held = sum(1 for r in chk if r["champion_rank"] == 1)
    ir = next(r for r in chk if r["demand_class"] == "intermittent" and r["part_class"] == "R")
    tr = next(t for t in f["truth_recovery"] if t.get("vendor_quoted") is not None and "MTBUR" in t["param"] and "+" in t["param"])
    ctx, page, problems = open_page(browser, site + "#/forecast", "1440")
    try:
        if mode == "expert":
            set_mode(page, "expert")
        txt = page.locator('[data-story="forecast-honest"]').inner_text()
        assert f"{held} of {len(chk)}" in txt
        est, quo = f"{round(tr['estimated'] * 100)}%", f"{round(tr['vendor_quoted'] * 100)}%"
        if mode == "simple":
            sfx = {1: "st", 2: "nd", 3: "rd"}.get(ir["champion_rank"] % 10, "th")
            assert f"best in only {held} of {len(chk)} groups of parts" in txt
            assert f"ranked {ir['champion_rank']}{sfx} of {ir['n_methods']}" in txt
            assert f"about {est} off the truth" in txt and f"about {quo} off" in txt
            assert "Only the scoring step reads them" in txt
        else:
            assert f"{ir['champion_rank']} of {ir['n_methods']} on the holdout" in txt and "SBA" in txt
            assert f"{tr['estimated']:.3f}" in txt and f"{tr['vendor_quoted']:.3f}" in txt
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_v21_readability_simple(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/forecast", vp)
    try:
        r = page.evaluate("import('./js/lib/readability.js').then((R) => R.readability())")
        assert r["grade"] <= 9, r
        assert r["maxSentenceWords"] <= 25, r["longSentences"]
    finally:
        ctx.close()


# ----------------------------------------------------------------------------- v2.1 addendum: keyboard walk
KB_TARGETS_JS = r"""() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !e.closest('[hidden], details:not([open]) > :not(summary), [inert]'); };
  const sel = 'a[href], button:not([disabled]), input:not([type=hidden]):not([disabled]), select, textarea, summary, [tabindex]:not([tabindex="-1"])';
  return [...document.querySelectorAll('#view ' + sel.split(', ').join(', #view '))].filter(vis).filter((e) => e.tabIndex >= 0).length;
}"""
KB_STEP_JS = r"""() => {
  const a = document.activeElement;
  if (!a || a === document.body) return { where: 'body' };
  const inView = !!a.closest('#view');
  if (!window.__kbSeen) window.__kbSeen = [];
  let order = 'ok';
  const last = window.__kbSeen.at(-1);
  if (inView && last && last.isConnected && (last.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_PRECEDING)) order = 'back';
  if (inView) window.__kbSeen.push(a);
  const cs = getComputedStyle(a);
  const ring = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== 'none' || a.matches('g, svg *');
  return { where: inView ? 'view' : 'shell', order, ring, tag: a.tagName, label: (a.getAttribute('aria-label') || a.textContent || '').trim().slice(0, 40) };
}"""


def keyboard_walk(page, max_tabs=400):
    """Tab from the top through the whole page: focus never lost to <body> after entering the view, view controls
    visited in document order, every visible view control reached, focus ring visible, and the walk leaves the view
    (no trap). Returns (visited_in_view, expected)."""
    expected = page.evaluate(KB_TARGETS_JS)
    page.evaluate("window.__kbSeen = []; document.activeElement?.blur(); window.scrollTo(0, 0)")
    seen_view, left_after_view, problems = 0, False, []
    for _ in range(max_tabs):
        page.keyboard.press("Tab")
        st = page.evaluate(KB_STEP_JS)
        if st["where"] == "view":
            seen_view += 1
            if st["order"] == "back":
                problems.append(f"focus moved backwards to {st['tag']} {st['label']}")
            if not st["ring"]:
                problems.append(f"no visible focus ring on {st['tag']} {st['label']}")
        elif seen_view and st["where"] in ("shell", "body"):
            left_after_view = True
            break
    unique = page.evaluate("new Set(window.__kbSeen).size")
    assert left_after_view, "keyboard focus trapped inside the view"
    assert not problems, problems[:5]
    assert unique >= expected, f"Tab reached {unique} of {expected} view controls"
    return unique, expected


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_v21_keyboard(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/forecast", vp)
    try:
        keyboard_walk(page)
        # Enter / Space on a segmented option switches it and the chart morphs (no console errors)
        btn = page.locator('.seg[aria-label="Evaluation window"] button[data-value="holdout"]')
        btn.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        assert btn.get_attribute("aria-checked") == "true" and "win=holdout" in page.url
        sel = page.locator('.seg[aria-label="Evaluation window"] button[data-value="selection"]')
        sel.focus()
        page.keyboard.press(" ")
        page.wait_for_timeout(400)
        assert sel.get_attribute("aria-checked") == "true"
        # a term opens its tooltip on focus; Esc closes it and focus stays on the term
        t = page.locator('#view .term').first
        t.focus()
        assert page.locator(".term-pop.is-on").count() == 1
        page.keyboard.press("Escape")
        assert page.locator(".term-pop.is-on").count() == 0
        assert page.evaluate("document.activeElement.classList.contains('term')")
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_motion_keyed_transition(site, browser):  # noqa: F811
    """Switching the window interpolates the leaderboard dots from old to new values (no redraw from zero)."""
    ctx, page, problems = open_page(browser, site + "#/forecast?class=intermittent&part=R", "1440", reduced=False)
    try:
        js = "() => [...document.querySelectorAll('[data-story=forecast-leaderboard] circle.fl-dot')].map((c) => +c.getAttribute('cx'))"
        before = page.evaluate(js)
        page.locator('.seg[aria-label="Evaluation window"] button[data-value="holdout"]').click()
        page.wait_for_timeout(60)
        mid = page.evaluate(js)
        page.wait_for_timeout(700)
        after = page.evaluate(js)
        assert len(before) == len(mid) == len(after)
        assert min(mid) > 0, "dots restarted from zero"
        moved = [i for i in range(len(after)) if abs(after[i] - before[i]) > 2]
        assert moved and any(min(before[i], after[i]) - 0.5 <= mid[i] <= max(before[i], after[i]) + 0.5 and abs(mid[i] - after[i]) > 0.5 for i in moved), (before, mid, after)
        assert not problems, problems
    finally:
        ctx.close()
