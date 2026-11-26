"""Design wave B: chart implications, fleet filter + system panel, v2 action fields + walkthrough, six-step story
with play/pause/skip, Capital paired differences."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

ROUTES = ["#/mission", "#/parts?ata=32", "#/forecast", "#/rotables", "#/network?station=BOM", "#/capital",
          "#/aog", "#/actions", "#/method"]


@pytest.mark.parametrize("route", ROUTES)
def test_every_chart_has_a_conclusion_and_implication(site, browser, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, "1440")
    try:
        frames = page.evaluate("""() => [...document.querySelectorAll('#view figure.chart-frame')].map((f) => ({
          h: f.querySelector('.chart-headline')?.textContent.trim() || '',
          i: f.querySelector('.chart-implication:not([hidden]) .chart-implication-t')?.textContent.trim() || '' }))""")
        assert frames
        for f in frames:
            if "not run" in f["h"]:
                continue
            assert f["h"] and f["i"], f
        assert not problems, problems
    finally:
        ctx.close()


def test_fleet_filter_and_system_panel(site, browser):  # noqa: F811
    parts = json.loads((DOCS / "data/parts.json").read_text())["parts"]
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32&fleet=WB", "1440")
    try:
        assert page.locator('[data-story="aircraft"] svg[data-archetype="widebody"]').count() == 1
        hidden = page.evaluate("[...document.querySelectorAll('[data-story=\"aircraft\"] .ata-hotspot')].filter((g) => g.style.display === 'none').map((g) => g.dataset.ata)")
        no_wb = sorted({p["ata"] for p in parts} - {p["ata"] for p in parts if p["applicability"] in ("WB", "both")})
        assert all(a in no_wb for a in hidden)
        panel = page.locator('[data-story="parts-system-panel"]')
        assert "ATA 32" in panel.inner_text() and panel.locator(".pi-pstat").count() == 3
        assert panel.locator('a[href^="#/actions"]').count() == 1
        rows = page.evaluate("[...document.querySelectorAll('[data-story=\"parts-table\"] tbody tr')].map((r) => r.dataset.key)")
        app = {p["pn"]: p["applicability"] for p in parts}
        assert rows and all(app[pn] in ("WB", "both") for pn in rows)
        page.locator('[data-role="fleet-filter"] button', has_text="Narrowbody").click()
        page.wait_for_selector('[data-story="aircraft"] svg[data-archetype="narrowbody"]')
        assert "fleet=NB" in page.url
        assert not problems, problems
    finally:
        ctx.close()


def test_action_fields_and_monday_walkthrough(site, browser):  # noqa: F811
    allowed = {"Exception trigger", "Quantity", "Source → destination", "Required by", "Expected availability", "Constraints",
               "Expected benefit", "Owner", "Due", "Part"}
    ctx, page, problems = open_page(browser, site + "#/actions", "1440")
    try:
        walk = page.locator('[data-story="action-walkthrough"]')
        assert "01 / 0" in walk.inner_text()
        n = int(walk.locator(".pac-walk-step").inner_text().split("/")[1].split("·")[0])
        for _ in range(n - 1):
            walk.locator("button", has_text="Next").click()
        assert f"0{n} / 0{n}" in walk.locator(".pac-walk-step").inner_text()
        walk.locator("button", has_text="Open the full exception").click()
        page.wait_for_selector(".drawer.is-open")
        labels = page.locator('.drawer [data-role="action-fields"] dt').evaluate_all("(els) => els.map((e) => e.textContent.trim())")
        assert labels and set(labels) <= allowed, labels
        assert not problems, problems
    finally:
        ctx.close()


def test_six_step_story_play_pause_skip(site, browser):  # noqa: F811
    steps = json.loads((DOCS / "data/story.json").read_text())["steps"]
    assert len(steps) == 6 and steps[0]["story_id"] == "aog-incident-ps1" and steps[-1]["story_id"] == "frontier-chart"
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        page.keyboard.press("s")
        page.wait_for_function("document.querySelector('.story') && !document.querySelector('.story').hasAttribute('aria-busy')", timeout=20000)
        assert "/ 06" in page.locator(".story-step").inner_text()
        play = page.locator(".story-play")
        play.click()
        assert play.get_attribute("aria-pressed") == "true"
        page.keyboard.press("Space")
        assert play.get_attribute("aria-pressed") == "false"
        page.keyboard.press("ArrowRight")
        page.wait_for_function("document.querySelector('.story-step')?.textContent.includes('STEP 02')")
        page.locator(".story button", has_text="Skip tour").click()
        page.wait_for_function("!document.querySelector('.story')")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_capital_paired_differences(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/capital", "1440")
    try:
        card = page.locator('[data-story="capital-paired"]')
        txt = card.inner_text()
        rec = json.loads((DOCS / "data/frontier.json").read_text())["recommended"]
        assert rec in txt and "conditional on the simulation assumptions" in txt and "[" in txt
        assert not problems, problems
    finally:
        ctx.close()
