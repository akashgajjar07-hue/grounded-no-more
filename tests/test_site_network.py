"""05 Network Positioning: browser checks (routes, station deep links, replay, metric toggle, both viewports)."""
from __future__ import annotations

import pytest

from _sitefx_c import VIEWPORTS, assert_clean, open_route, serve_docs

pytestmark = pytest.mark.browser
playwright = pytest.importorskip("playwright.sync_api")

ROUTES = ["#/network", "#/network?station=BOM", "#/network?station=AUH", "#/network?station=BOM&metric=fill_rate"]


@pytest.fixture(scope="module")
def site():
    with serve_docs() as base, playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b, base
        b.close()


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
@pytest.mark.parametrize("route", ROUTES)
def test_route_clean(site, route, viewport):
    b, base = site
    ctx, page, problems = open_route(b, base, route, viewport)
    try:
        assert_clean(page, problems, f"{route}@{viewport}")
        for hook in ["map", "network-replay", "network-policy", "network-hub-finding"]:
            assert page.locator(f'[data-story="{hook}"]').count() >= 1, hook
        if "station=" in route:
            st = route.split("station=")[1].split("&")[0]
            assert page.locator(".np-drill-code").inner_text().strip() == st
            assert page.locator(f'.np-picker button[data-station="{st}"]').get_attribute("aria-pressed") == "true"
            assert page.locator(f'[data-story="network-{st.lower()}"]').count() == 1
    finally:
        ctx.close()


def test_station_select_updates_url_and_replay_runs(site):
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network", "1440")
    try:
        page.locator('.np-picker button[data-station="BOM"]').click()
        assert "station=BOM" in page.url
        assert page.locator(".np-drill-code").inner_text().strip() == "BOM"
        page.get_by_role("button", name="Replay transfer").click()
        page.wait_for_timeout(1200)  # reduced motion: arcs flash for ~600 ms
        assert page.get_by_role("button", name="Replay transfer").is_enabled()
        radios = page.locator('[data-story="network-policy"] [role="radio"]')
        for i in range(radios.count()):
            radios.nth(i).click()
            page.wait_for_timeout(150)
        assert_clean(page, problems, "interactions")
    finally:
        ctx.close()


def test_map_nodes_keyboard_reachable(site):
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network", "1440")
    try:
        node = page.locator('svg.map-main g[data-station="JED"]')
        node.focus()
        page.keyboard.press("Enter")
        assert "station=JED" in page.url
        label = node.get_attribute("aria-label")
        assert "risk" in label.lower()
        assert not problems, problems
    finally:
        ctx.close()
