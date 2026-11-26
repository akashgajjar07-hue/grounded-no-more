"""Browser tests for 01 Mission Control (and the story overlay it launches)."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("route", ["#/mission", "#/"])
def test_mission_renders_clean(site, browser, vp, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, vp)
    try:
        audit(page, problems, min_frames=2)
        for hook in ["mission-hero", "mission-aircraft", "mission-kpis", "mission-compare", "mission-actions", "mission-map"]:
            assert page.locator(f'[data-story="{hook}"]').count() == 1, hook
        assert "GROUNDED" in page.locator(".mc-title").inner_text().upper()
        assert "A single missing part can ground an aircraft" in page.locator(".mc-tagline").inner_text()
        # 4 KPI instruments, each with a provenance chip
        tiles = page.locator('[data-story="mission-kpis"] .kpi')
        assert tiles.count() == 4
        for i in range(4):
            assert tiles.nth(i).locator(".chip-prov").count() == 1
        # top 5 actions deep-link into the action centre
        links = page.locator('[data-story="mission-actions"] a.mc-action')
        assert 1 <= links.count() <= 5
        assert "#/actions?id=" in links.first.get_attribute("href")
        # the aircraft drawing has hotspots and an accessible list alternative
        page.wait_for_selector('[data-story="mission-aircraft"] svg .ata-hotspot')
        assert page.locator('.mc-figwrap ul.sr-only li a').count() == 8
        assert page.locator(".disclaimer").count() == 1
    finally:
        ctx.close()


def test_mission_hero_and_kpis_above_the_fold(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        bottom = page.evaluate("Math.max(...[...document.querySelectorAll('[data-story=\"mission-kpis\"] .kpi')].map(e => e.getBoundingClientRect().bottom))")
        assert bottom <= 900, bottom
        assert not problems, problems
    finally:
        ctx.close()


def test_numbers_come_from_data(site, browser):  # noqa: F811
    """The hero sentence and KPI values are built from kpis.json (no hard-coded results)."""
    name = "kpis" if "kpis" in json.loads((DOCS / "data/manifest.json").read_text()).get("files", []) else "fixtures/kpis"
    kpis = {k["id"]: k for k in json.loads((DOCS / f"data/{name}.json").read_text())["kpis"]}
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        fr = kpis["immediate_fill_rate"]
        story = page.locator(".mc-story").inner_text()
        assert f"{fr['value'] * 100:.1f}%" in story and f"{fr['baseline'] * 100:.1f}%" in story
        tile = page.locator('[data-kpi="immediate_fill_rate"] .kpi-value').inner_text()
        assert f"{fr['value'] * 100:.1f}" in tile
    finally:
        ctx.close()


def test_action_deep_link_and_hotspot_navigation(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        href = page.locator('[data-story="mission-actions"] a.mc-action').first.get_attribute("href")
        page.locator('[data-story="mission-actions"] a.mc-action').first.click()
        page.wait_for_function(f"location.hash === {json.dumps(href)}")
        page.wait_for_function("document.querySelector('.nav-item[aria-current=\"page\"]')?.dataset.route === 'actions'")
        page.goto(site + "#/mission")
        page.wait_for_selector('[data-story="mission-aircraft"] svg .ata-hotspot')
        page.locator('[data-story="mission-aircraft"] .ata-hotspot').first.focus()
        page.keyboard.press("Enter")
        page.wait_for_function("location.hash.startsWith('#/parts?ata=')")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_story_overlay_keyboard(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", vp)
    try:
        page.locator('[data-story="mission-hero"] button.btn--primary').click()
        page.wait_for_selector(".story .story-card")
        page.wait_for_function("!document.querySelector('.story').hasAttribute('aria-busy')", timeout=8000)
        assert "STEP 01" in page.locator(".story-step").inner_text()
        # a second launch does not stack overlays
        page.evaluate("document.getElementById('rail-story').click()")
        page.wait_for_timeout(300)
        assert page.locator(".story").count() == 1
        page.keyboard.press("ArrowRight")
        page.wait_for_function("document.querySelector('.story-step')?.textContent.includes('STEP 02')")
        page.wait_for_function("!document.querySelector('.story').hasAttribute('aria-busy')", timeout=8000)
        page.keyboard.press("ArrowLeft")
        page.wait_for_function("document.querySelector('.story-step')?.textContent.includes('STEP 01')")
        page.wait_for_function("location.hash.startsWith('#/mission')", timeout=8000)
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()
