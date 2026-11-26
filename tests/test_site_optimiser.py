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


# ---- design wave 2 (critic items #2, #3, #4, duplicate KPI, headline length)
@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_capital_wave2_design(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/capital", vp)
    try:
        heads = page.locator("#view .chart-headline").all_inner_texts()
        assert heads and all(len(t.strip()) <= 90 for t in heads), heads
        kpis = page.locator('[data-story="capital-kpis"] .kpi')
        # one AOG tile with two deltas instead of the same AOG value twice
        assert kpis.count() <= 3
        assert page.locator('[data-story="capital-kpis"] .co-delta2').count() == 1
        # capital delta is neutral, never red
        cap = kpis.first
        assert cap.locator(".kpi-delta.is-bad").count() == 0
        assert "capital" in cap.locator(".kpi-delta").first.inner_text()
        # no copper on P1/P2 policy labels; P0 keeps copper (baseline)
        fills = page.evaluate("""() => [...document.querySelectorAll('[data-story="frontier-chart"] svg text.gnm-label--strong')]
            .map((t) => [t.textContent.trim(), getComputedStyle(t).fill])""")
        for txt, fill in fills:
            if txt.startswith("P1") or txt.startswith("P2"):
                assert "196, 127, 82" not in fill, (txt, fill)
        # cost chart: every total label clears the end of its bar
        overlaps = page.evaluate("""() => {
            const svg = [...document.querySelectorAll('svg')].find((s) => (s.getAttribute('aria-label') || '').includes('Annual cost breakdown'));
            if (!svg) return ['no svg'];
            const rects = [...svg.querySelectorAll('rect')].map((r) => r.getBBox());
            const bad = [];
            svg.querySelectorAll('text.gnm-label--strong').forEach((t) => {
                if (!/^AED/.test(t.textContent)) return;
                const b = t.getBBox();
                rects.forEach((r) => { if (r.width > 2 && b.x < r.x + r.width - 0.5 && b.x + b.width > r.x && b.y < r.y + r.height && b.y + b.height > r.y) bad.push(t.textContent); });
            });
            return bad;
        }""")
        assert not overlaps, overlaps
        # allocation table keeps the decision columns at 390
        card = page.locator('[data-story="allocation-table"]')
        if vp == "390":
            assert card.locator(".dts-row").first.is_visible()
            assert "AOG H AVOIDED" in card.locator(".dts-metric").first.inner_text().upper()
            sec = card.locator(".dts-secondary").first.inner_text()
            assert "Units" in sec and "cap" in sec
        else:
            ths = card.locator("thead th").all_inner_texts()
            assert any("CHANGE" in t.upper() for t in ths) and any("AVOIDED" in t.upper() for t in ths)
        assert not problems, problems
    finally:
        ctx.close()
