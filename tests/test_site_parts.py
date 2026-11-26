"""Browser tests for 02 Parts Intelligence (screens-B)."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


def _parts():
    files = json.loads((DOCS / "data/manifest.json").read_text()).get("files", [])
    name = "parts" if "parts" in files else "fixtures/parts"
    return json.loads((DOCS / f"data/{name}.json").read_text())


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("route", ["#/parts", "#/parts?ata=32", "#/parts?ata=all&cls=R", "#/parts?ata=49"])
def test_parts_renders_clean(site, browser, vp, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, vp)
    try:
        page.wait_for_selector(".pi-aircraft svg .ata-hotspot")
        audit(page, problems, min_frames=2)
        # 8 risk-coloured hotspots, each with a text risk label (not colour alone) + story ids
        assert page.locator(".pi-aircraft .ata-hotspot[class*='risk-']").count() == 8
        assert page.locator(".pi-aircraft .hs-risk").count() == 8
        assert page.locator('[data-story="parts-hotspot-32"]').count() == 1
        # accessible list alternative: one button per system, with a text pill
        assert page.locator(".pi-syslist button.pi-sys").count() == 8
        assert page.locator(".pi-syslist .pill").count() == 8
        assert page.locator('[data-story="parts-table"] tbody tr').count() >= 1
        assert page.locator(".disclaimer").count() == 1
    finally:
        ctx.close()


def test_select_system_filters_and_deep_links(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", "1440")
    try:
        parts = _parts()["parts"]
        n29 = sum(p["ata"] == "29" for p in parts)
        page.locator('.pi-syslist button[data-ata="29"]').click()
        page.wait_for_timeout(500)
        assert "ata=29" in page.url
        assert page.locator('[data-story="parts-table"] tbody tr').count() == n29
        assert page.locator(".pi-exploded svg .pi-slot").count() >= 1
        # hotspot click also selects
        page.locator('.pi-aircraft .ata-hotspot[data-ata="21"]').click()
        page.wait_for_timeout(400)
        assert "ata=21" in page.url
        assert page.locator('.pi-syslist button[data-ata="21"][aria-pressed="true"]').count() == 1
        # search narrows the table
        page.fill(".pi-search", "zzzz-no-match")
        assert page.locator('[data-story="parts-table"] tbody tr').count() == 0
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_part_drawer_deep_link(site, browser, vp):  # noqa: F811
    parts = {p["pn"]: p for p in _parts()["parts"]}
    pn = "GN-32-R014" if "GN-32-R014" in parts else next(iter(parts))
    ctx, page, problems = open_page(browser, site + f"#/parts?pn={pn}", vp)
    try:
        drawer = page.locator(".drawer.is-open")
        drawer.wait_for()
        page.wait_for_timeout(600)
        assert pn in drawer.inner_text()
        assert drawer.locator("figure.chart-frame .chip-prov").count() == 1
        assert drawer.locator(".chart-body svg").count() == 1
        assert drawer.locator(".strip-split").count() == 1  # train / selection split marked
        assert drawer.locator('a[href^="#/forecast"]').count() == 1
        if parts[pn]["cls"] == "R":
            assert drawer.locator('a[href^="#/rotables"]').count() == 1
        if parts[pn].get("planted"):
            assert drawer.locator(".pi-planted-banner").count() == 1
        overflow = page.evaluate("""() => [...document.querySelectorAll('.drawer *')].filter(e => !e.closest('svg') && !e.closest('.table-wrap') && !e.children.length && e.textContent.trim() && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible').map(e => e.textContent.slice(0, 40))""")
        assert not overflow, overflow
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        assert "pn=" not in page.url
        assert not problems, problems
    finally:
        ctx.close()


def test_matrix_excludes_unclassified_and_states_training_window(site, browser):  # noqa: F811
    parts = _parts()["parts"]
    plotted = [p for p in parts if p.get("adi") is not None and p.get("cv2") is not None and p["demand_class"] != "insufficient_data"]
    ctx, page, problems = open_page(browser, site + "#/parts?ata=all", "1440")
    try:
        frame = page.locator('[data-story="parts-adi-matrix"]')
        assert frame.locator("circle.pi-dot").count() == len(plotted)
        sub = frame.locator(".chart-subtitle").inner_text()
        assert "W0" in sub and "W77" in sub and "1.32" in sub and "0.49" in sub
        assert not problems, problems
    finally:
        ctx.close()


def test_hotspots_keyboard_reachable(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", "1440")
    try:
        spot = page.locator('.pi-aircraft .ata-hotspot[data-ata="34"]')
        spot.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        assert "ata=34" in page.url
        assert not problems, problems
    finally:
        ctx.close()
