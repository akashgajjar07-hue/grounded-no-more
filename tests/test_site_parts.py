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
        assert page.locator(".pi-exploded .pi-xlabel").count() >= 1
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


# ----------------------------------------------------------------------------- design wave 2 (agent B)
OVERLAP_JS = r"""(sel) => {
  const els = [...document.querySelectorAll(sel)].map((e) => e.getBoundingClientRect()).filter((r) => r.width && r.height);
  const hits = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = els[i], b = els[j];
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) hits.push([i, j]);
  }
  return hits;
}"""


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_urgent_part_pip_and_callout(site, browser, vp):  # noqa: F811
    parts = _parts()["parts"]
    atas = ["21", "24", "27", "29", "32", "34", "36", "49"]
    with_urgent = [a for a in atas if any(p["ata"] == a and p["risk_level"] == "urgent" for p in parts)]
    in32 = sorted([p for p in parts if p["ata"] == "32"], key=lambda p: -p["risk_score"])
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", vp)
    try:
        page.wait_for_selector(".pi-aircraft .pi-hs-callout")
        # a red pip with the urgent-PN count on every system that holds an urgent part, whatever the system level
        assert page.locator(".pi-aircraft .hs-pip").count() == len(with_urgent)
        for a in with_urgent:
            n = sum(p["ata"] == a and p["risk_level"] == "urgent" for p in parts)
            assert page.locator(f'.ata-hotspot[data-ata="{a}"] .hs-pip text').text_content() == str(n)
        # the selected system names its top-risk part with the part's own level
        call = page.locator('[data-story="parts-hotspot-32"] .pi-hs-callout')
        assert call.count() == 1 and in32[0]["pn"] in call.text_content()
        assert f"is-{in32[0]['risk_level']}" in call.get_attribute("class")
        # every aircraft label renders at >= 11 px on screen
        sizes = page.evaluate("""() => { const svg = document.querySelector('.pi-aircraft svg'); const k = svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
          return [...svg.querySelectorAll('.hs-risk, .hs-pip text, .pi-hs-text')].map((t) => parseFloat(t.style.fontSize) * k); }""")
        assert sizes and min(sizes) >= 10.9, sizes
        # risk words do not sit on other badges or leave the drawing
        assert not page.evaluate(OVERLAP_JS, ".pi-aircraft .hs-risk, .pi-aircraft .pi-hs-box")
        call.focus()
        page.keyboard.press("Enter")  # keyboard-operable (role=button, tabindex 0)
        page.locator(".drawer.is-open").wait_for()
        assert in32[0]["pn"] in page.locator(".drawer.is-open").inner_text()
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_exploded_labels_html_and_hot_part(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", vp)
    try:
        page.wait_for_selector(".pi-exploded .pi-xlabel")
        fs = page.evaluate("() => [...document.querySelectorAll('.pi-xlabel-pn, .pi-xlabel-desc, .pi-xlabel-risk')].filter((e) => e.offsetParent).map((e) => parseFloat(getComputedStyle(e).fontSize))")
        assert fs and min(fs) >= 11, fs
        assert page.locator(".pi-exploded svg .bp-label").first.is_hidden()
        assert not page.evaluate(OVERLAP_JS, ".pi-exploded .pi-xlabel")
        hot = page.locator(".pi-exploded .pi-xlabel.is-hot")
        if hot.count():
            assert page.locator(".pi-exploded svg .bp-part.pi-hot").count() == 1
            assert "risk" in hot.inner_text().lower()
        assert not problems, problems
    finally:
        ctx.close()


def test_mobile_table_keeps_risk_and_heatmap_headers_clear(site, browser):  # noqa: F811
    n32 = sum(p["ata"] == "32" for p in _parts()["parts"])
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", "390")
    try:
        stack = page.locator('[data-story="parts-table"] .data-table-stack')
        assert stack.is_visible()
        metrics = stack.locator(".dts-metric")
        assert metrics.count() == n32
        assert "risk" in metrics.first.inner_text().lower()
        assert not page.evaluate(OVERLAP_JS, ".pi-hm-col")
        assert page.locator(".pi-hm-key").is_visible()
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_matrix_labels_clear_and_reference_lines_neutral(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", vp)
    try:
        frame = page.locator('[data-story="parts-adi-matrix"]')
        assert frame.locator(".pi-cut").count() == 0  # no amber cut lines
        assert frame.locator(".gnm-ref-line").count() == 2
        assert frame.locator(".pi-quad-t").count() == 4
        # quadrant labels, cut-off labels and the annotation never overlap each other
        assert not page.evaluate(OVERLAP_JS, '[data-story="parts-adi-matrix"] .pi-quad-t, [data-story="parts-adi-matrix"] .gnm-ref-label, [data-story="parts-adi-matrix"] .gnm-annot-text, [data-story="parts-adi-matrix"] .gnm-annot-sub, [data-story="parts-adi-matrix"] .pi-axis-t')
        heads = page.evaluate("() => [...document.querySelectorAll('#view .chart-headline')].map((e) => e.textContent.trim())")
        assert heads and all(len(h) <= 90 for h in heads), heads
        assert not problems, problems
    finally:
        ctx.close()
