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
        assert f"{champ['mase']:.3f}" in txt
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
