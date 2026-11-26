"""Browser tests for 03 Forecast Lab (screens-B)."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


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
        assert "holdout" in board.locator(".chart-subtitle").inner_text()
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
