"""Browser tests for 06 Capital Optimiser (screen agent D)."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


def _frontier():
    p = DOCS / "data" / "frontier.json"
    return json.loads(p.read_text()) if p.exists() else json.loads((DOCS / "data" / "fixtures" / "frontier.json").read_text())


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("route", ["#/capital", "#/capital?point=B080", "#/capital?view=overlay", "#/capital?view=selection&point=I110"])
def test_capital_renders_clean(site, browser, vp, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, vp)
    try:
        audit(page, problems, min_frames=4)
        assert page.locator('[data-story="frontier-chart"] svg path.co-pt').count() >= 10
        assert page.locator(".disclaimer").count() == 1
        assert page.locator('[data-story="capital-kpis"] .kpi .chip-prov').count() >= 3
    finally:
        ctx.close()


def test_recommended_point_from_data(site, browser):  # noqa: F811
    F = _frontier()
    ctx, page, problems = open_page(browser, site + "#/capital", "1440")
    try:
        assert F["recommended"] in page.locator('[data-story="frontier-chart"] .chart-headline').inner_text()
        assert page.locator('[data-story="allocation-table"]').get_attribute("data-point") == F["recommended"]
        txt = page.locator("#view").inner_text()
        assert "heuristic" in txt and "AOG-desk" in txt
        # low-stress honesty note is present when the data says the point does not pay there
        low = next((v for v in F.get("variant_robustness", []) if v.get("variant") == "low_stress"), None)
        if low and low["rec_vs_P2"]["net_benefit_aed"] < 0:
            assert "not worth its extra capital" in txt
        assert not problems, problems
    finally:
        ctx.close()


def test_slider_changes_allocation_table(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/capital", "1440")
    try:
        card = page.locator('[data-story="allocation-table"]')
        before_point = card.get_attribute("data-point")
        before_rows = card.locator("tbody tr").all_inner_texts()
        slider = page.locator('input[data-role="budget-slider"]')
        lo = slider.get_attribute("min")
        slider.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }", lo)
        page.wait_for_timeout(300)
        after_point = card.get_attribute("data-point")
        assert after_point != before_point
        assert card.locator("tbody tr").all_inner_texts() != before_rows
        assert after_point in card.locator(".card-title").inner_text()
        assert f"point={after_point}" in page.url
        assert not problems, problems
    finally:
        ctx.close()


def test_view_toggle_and_keyboard(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/capital", "1440")
    try:
        page.locator('.co-controls .seg button[data-value="overlay"]').click()
        page.wait_for_timeout(200)
        assert "view=overlay" in page.url
        assert page.locator('[data-story="frontier-chart"] svg circle[stroke-dasharray], [data-story="frontier-chart"] svg g circle').count() > 0
        # a frontier point is keyboard-operable
        pt = page.locator('[data-story="frontier-chart"] path.co-pt[tabindex="0"]').first
        pt.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        assert "point=" in page.url
        assert not problems, problems
    finally:
        ctx.close()
