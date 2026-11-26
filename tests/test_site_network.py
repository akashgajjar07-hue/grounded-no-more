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
        # the chip row is a keyboard-only selector now (visually hidden until focused)
        btn = page.locator('.np-picker button[data-station="BOM"]')
        btn.focus()
        page.keyboard.press("Enter")
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
        assert "exposure" in label.lower()   # wave A wording: material shortage exposure
        assert not problems, problems
    finally:
        ctx.close()


FRAME_JS = """async () => {
  const { lintAccents } = await import('./js/charts/theme.js');
  return [...document.querySelectorAll('#view .chart-frame')].map((f) => ({
    headline: (f.querySelector('.chart-headline')?.textContent || '').trim(),
    accents: lintAccents(f),
  }));
}"""


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_wave2_design_fixes(site, viewport):
    """Design wave 2: headlines <= 90, <= 2 accents per chart, sub-labels without bullets, hidden chip row, stacked table."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", viewport)
    try:
        frames = page.evaluate(FRAME_JS)
        for f in frames:
            assert len(f["headline"]) <= 90, f["headline"]
            assert len(f["accents"]) <= 2, f
        subs = page.eval_on_selector_all("svg.map-main .map-label-sub", "els => els.map(e => e.textContent)")
        assert all("●" not in t and "▲" not in t for t in subs), subs
        # chip row is visually hidden until focus, then shown
        picker = page.locator(".np-picker")
        assert picker.bounding_box()["width"] <= 2
        page.locator('.np-picker button[data-station="AUH"]').focus()
        assert picker.bounding_box()["width"] > 40
        # no copper on the emergency encodings (legend, replay dots)
        legend = page.locator(".np-legend").inner_html().lower()
        assert "196, 127, 82" not in legend and "#c47f52" not in legend
        fills = page.eval_on_selector_all('[data-story="network-replay"] .np-ev circle', "els => els.map(e => (e.getAttribute('fill') || '').toLowerCase())")
        assert "#c47f52" not in fills
        if viewport == "390":
            # the decision column (projected risk) stays visible on a phone
            assert page.locator('.data-table-stack .dts-metric--pill[aria-label^="Exposure"]').count() >= 1
        assert not problems, problems
    finally:
        ctx.close()


def test_ci_clamp_note(site):
    """Negative CI lower ends are drawn at 0 and the clamp is stated (drill table + compare subtitle)."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", "1440")
    try:
        clamped = page.evaluate("""async () => {
          const n = await (await fetch('./data/network.json')).json();
          return (n.policy_compare || []).some((r) => Object.entries(r).some(([k, v]) =>
            (Array.isArray(v) && /_ci$/.test(k) && v[0] < 0) || (/_(ci_)?lo$/.test(k) && v < 0) || (v && typeof v === 'object' && !Array.isArray(v) && (v.ci_lo ?? v.lo) < 0)));
        }""")
        sub = page.locator('[data-story="network-policy"] .chart-subtitle').get_attribute("title") or ""
        if clamped:
            assert "drawn at 0" in sub
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_wave3_network(site, viewport):
    """Design wave 3: replay ticks read "200 h", the riskiest outstation never wears an OK pill,
    the lowest-AOG policy row and the hub bars are not teal."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", viewport)
    try:
        res = page.evaluate("""async () => {
          const n = await (await fetch('./data/network.json')).json();
          const outs = n.stations.filter((s) => s.role !== 'hub').sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0));
          const ticks = [...document.querySelectorAll('[data-story="network-replay"] .tick text')].map((t) => t.textContent.trim());
          const drillPill = document.querySelector('[data-story^="network-"] .np-drill-head .pill');
          const best = document.querySelector('.np-pol tr.is-best td');
          const shareTeal = [...document.querySelectorAll('[data-story="network-hub-finding"] svg rect')].filter((r) => (r.getAttribute('fill') || '').toLowerCase() === '#22c7b8').length;
          return { top: outs[0]?.station, ticks, pillCls: drillPill?.className || '', pillTxt: drillPill?.textContent || '', bestColor: best ? getComputedStyle(best).color : '', shareTeal };
        }""")
        assert res["ticks"] and not any(t.startswith("h ") for t in res["ticks"]), res["ticks"]
        if res["top"] == "BOM":
            assert "pill--ok" not in res["pillCls"], res
            assert "LOW" not in res["pillTxt"]
        assert res["bestColor"] and "34, 199, 184" not in res["bestColor"] and "127, 243, 230" not in res["bestColor"]
        assert res["shareTeal"] == 0
        assert not problems, problems
    finally:
        ctx.close()
