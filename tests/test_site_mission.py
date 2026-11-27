"""Browser tests for 01 Mission Control — the v2.1 landing + Results section (and the story overlay it launches)."""
from __future__ import annotations

import json
import re

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

KPIS = json.loads((DOCS / "data/kpis.json").read_text())
POL = {p["policy_id"]: p for p in json.loads((DOCS / "data/policies.json").read_text())["policies"]}
SCOPE = "across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part"
MODES = ["simple", "expert"]


def _open(browser, url, vp, mode):  # noqa: F811
    ctx, page, problems = open_page(browser, url, vp)
    if mode != "simple":
        page.evaluate(f"import('./js/lib/mode.js').then(m => m.setMode('{mode}'))")
        page.wait_for_function(f"document.body.classList.contains('mode-{mode}') && document.documentElement.dataset.ready === 'true'")
        page.wait_for_timeout(600)
    return ctx, page, problems


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_landing_hero_a1(site, browser, vp, mode):  # noqa: F811
    L = KPIS["landing"]
    ctx, page, problems = _open(browser, site + "#/", vp, mode)
    try:
        audit(page, problems, min_frames=1)
        hero = page.locator('[data-story="mission-hero"]')
        assert hero.locator("h1.mc-title").inner_text().strip() == L["title"]
        assert hero.locator('[data-role="landing-sub"]').inner_text().strip() == L["sub"]
        assert re.sub(r"\s+", " ", hero.locator('[data-role="landing-stats"]').inner_text()).strip() == L["text"]
        assert hero.locator('[data-role="landing-footer"]').inner_text().strip() == L["footer"]
        txt = hero.inner_text()
        # no result claims in the hero (they live on Results)
        for bad in ["1,480", "88%", "1480", "AED"]:
            assert bad not in txt, bad
        # the art mount slot holds the aircraft drawing (hotspots + accessible list)
        page.wait_for_selector('#hero-art [data-story="mission-aircraft"] svg .ata-hotspot')
        assert page.locator("#hero-art ul.sr-only li a").count() == 8
        if vp == "1440":
            assert hero.bounding_box()["y"] + hero.bounding_box()["height"] <= 900
        assert page.locator(".disclaimer").count() == 1
    finally:
        ctx.close()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_results_section(site, browser, vp, mode):  # noqa: F811
    ctx, page, problems = _open(browser, site + "#/mission", vp, mode)
    try:
        res = page.locator("#results")
        assert res.count() == 1
        # intro3 at the top of Results, not in the hero
        assert res.locator('[data-role="intro3"]').count() == 1
        assert page.locator('[data-story="mission-hero"] [data-role="intro3"]').count() == 0
        # four plans by display name, values from policies.json
        bars = res.locator('[data-story="mission-compare"] .mc-bar')
        assert bars.count() == 4
        names = [bars.nth(i).locator(".name-tag").evaluate("e => e.firstChild.textContent") for i in range(4)]
        assert names == ["Simple Rulebook (naive reference)", "Each Airport for Itself (simplified local comparator)", "Network Plan", "Network Plan + Extra Spares"]
        for i, code in enumerate(["P0", "P1", "P2", "I125"]):
            assert f"{round(POL[code]['kpi']['aog_hours']['mean']):,} h" in bars.nth(i).locator(".mc-bar-v").inner_text()
        ranges = res.locator(".mc-bar-ci").count()
        assert ranges == (4 if mode == "expert" else 0)
        # scope line under the chart, tiles carry it too
        assert res.locator('[data-story="mission-compare"] [data-role="scope"]').inner_text().strip() == SCOPE
        tiles = res.locator('[data-story="mission-kpis"] .kpi')
        assert tiles.count() == 3
        for i in range(3):
            assert tiles.nth(i).locator('[data-role="scope"]').inner_text().strip() == SCOPE
        # A2 directly after the numbers
        assert page.evaluate("document.querySelector('[data-story=\"mission-kpis\"]').nextElementSibling.dataset.role") == "reading-note"
        # A4 capital table with both gross rows (never the net alone)
        cap = res.locator('[data-role="capital-table"]')
        assert cap.count() == 1 and cap.locator("[data-row=buy]").count() == 1 and cap.locator("[data-row=shed]").count() == 1
        assert "+68 units" in cap.inner_text() and "+AED 0.6M" in cap.inner_text()
        # A6 stress worlds + ranges
        sw = KPIS["stress_worlds"]
        # v2.2: reading order easier -> tougher, built from the scales (CEO review row 18)
        sc = sw["scales"]
        want = f"reliability \u00d7{sc['low_stress']:.2f} (easier) / \u00d7{sc['central']:.2f} / \u00d7{sc['high_stress']:.2f} (tougher) \u2014 a narrow range"
        assert want in res.locator('[data-role="stress-worlds"]').inner_text()
        assert res.locator('[data-role="ranges-note"]').inner_text().strip() == sw["ranges_note"]
        # donor recount: post-plan, not reconstructible where so, history kept apart
        dr = res.locator('[data-role="donor-recount"]')
        assert page.locator('[data-story="mission-donor"] [data-role="postplan"]').count() == 1
        assert "not reconstructible from current logs" in dr.inner_text()
        hist = dr.locator('[data-role="historical-p0"]')
        assert "history" in hist.inner_text().lower()
        assert "5,285 h" in hist.locator('[data-role="hist-gross"]').inner_text()
        assert "1,282 h" in hist.locator('[data-role="hist-counted"]').inner_text()
        assert page.evaluate("[...document.querySelectorAll('#view *')].filter(e => !e.children.length && /5,285/.test(e.textContent) && !e.closest('[data-role=historical-p0]')).length") == 0
        # honest findings
        hf = res.locator('[data-role="honest-findings"] li')
        assert hf.count() == 4
        t = res.locator('[data-role="honest-findings"]').inner_text()
        assert "3 of 9" in t and "6th of 9" in t and "7%" in t and "14%" in t and "1.25" in t
        # priorities after the findings, deep-linking to the action centre
        links = page.locator('[data-story="mission-actions"] a.mc-pr')
        assert 1 <= links.count() <= 5 and "#/actions?id=" in links.first.get_attribute("href")
        pns = [links.nth(i).locator(".mc-pr-pn").inner_text() for i in range(links.count())]
        assert len(pns) == len(set(pns))
        # Simple mode: no bare policy codes visible
        if mode == "simple":
            vis = page.evaluate("document.querySelector('#view').innerText")
            assert not re.search(r"\b(P0|P1|P2|I125)\b", vis), re.findall(r".{20}\b(?:P0|P1|P2|I125)\b.{20}", vis)
        assert not problems, problems
    finally:
        ctx.close()


def test_results_deep_link_and_cta(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission?section=results", "1440")
    try:
        page.wait_for_timeout(600)
        top = page.evaluate("document.getElementById('results').getBoundingClientRect().top")
        assert -5 <= top <= 140, top
        page.evaluate("window.scrollTo(0, 0)")
        page.goto(site + "#/mission")
        page.wait_for_function("document.documentElement.dataset.ready === 'true'")
        page.locator('[data-role="to-results"]').click()
        page.wait_for_timeout(1000)
        assert page.evaluate("location.hash") == "#/mission?section=results"
        top = page.evaluate("document.getElementById('results').getBoundingClientRect().top")
        assert -5 <= top <= 140, top
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("mode", MODES)
def test_routes_off_line_under_reading_note(site, browser, mode):  # noqa: F811
    """v2.2: one plain line under the A2 reading note, computed from kpis.headline.honest.routes_off."""
    ro = KPIS["headline"]["honest"]["routes_off"]
    approx = lambda v: f"\u2248{round(v):,} h"  # noqa: E731
    want = ("All four plans rely on emergency sourcing (borrowing from another aircraft, loans, local purchase). "
            "With those routes switched off, every plan\u2019s downtime rises sharply \u2014 e.g. Network Plan from "
            f"{approx(ro['central_p2_aog_hours'])} to {approx(ro['p2_aog_hours'])} a year (selection runs). See Limitations.")
    assert approx(ro["central_p2_aog_hours"]) == "\u2248235 h" and approx(ro["p2_aog_hours"]) == "\u224818,320 h"
    ctx, page, problems = _open(browser, site + "#/mission?section=results", "1440", mode)
    try:
        line = page.locator('#results [data-role="routes-off"]')
        assert line.count() == 1
        assert re.sub(r"\s+", " ", line.inner_text()).strip() == want
        # directly after the A2 reading note
        assert page.evaluate("document.querySelector('[data-role=\"routes-off\"]').previousElementSibling.classList.contains('mc-reading')")
        a = line.locator('a[data-role="routes-limitations"]')
        assert a.get_attribute("href") == "https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/LIMITATIONS.md"
        assert a.get_attribute("target") == "_blank" and "noopener" in (a.get_attribute("rel") or "")
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("mode", MODES)
def test_readability_simple(site, browser, mode):  # noqa: F811
    ctx, page, problems = _open(browser, site + "#/mission", "1440", mode)
    try:
        r = page.evaluate("import('./js/lib/readability.js').then(R => R.readability())")
        if mode == "simple":
            (DOCS.parent / "reports/readability").mkdir(parents=True, exist_ok=True)
            (DOCS.parent / "reports/readability/mission.json").write_text(json.dumps(
                {"grade": r["grade"], "maxSentenceWords": r["maxSentenceWords"], "longSentences": r["longSentences"]}, indent=2, ensure_ascii=False))
            assert r["grade"] <= 9 and r["maxSentenceWords"] <= 25, r
    finally:
        ctx.close()


def test_action_deep_link_and_hotspot_navigation(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        href = page.locator('[data-story="mission-actions"] a.mc-pr').first.get_attribute("href")
        page.locator('[data-story="mission-actions"] a.mc-pr').first.click()
        page.wait_for_function(f"location.hash === {json.dumps(href)}")
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
        page.locator('[data-story="mission-start"]').click()
        page.wait_for_selector(".story .story-card")
        page.wait_for_function("!document.querySelector('.story').hasAttribute('aria-busy')", timeout=8000)
        assert "STEP 01" in page.locator(".story-step").inner_text()
        page.evaluate("document.getElementById('story-btn').click()")
        page.wait_for_timeout(300)
        assert page.locator(".story").count() == 1
        page.keyboard.press("ArrowRight")
        page.wait_for_function("document.querySelector('.story-step')?.textContent.includes('STEP 02')")
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_hero_tour_starts_playing(site, browser):  # noqa: F811
    """Addendum: the hero's 60-second tour opens already in Play mode, visibly within 1 s."""
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        page.evaluate("window.__gnmTourStepMs = 60000")
        page.locator('[data-story="mission-start"]').click()
        page.wait_for_function("window.__gnmStory && window.__gnmStory.state().playing && document.querySelector('.story-play')?.getAttribute('aria-pressed') === 'true'", timeout=1000)
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_kpi_count_up_once(site, browser):  # noqa: F811
    """Addendum: KPI values count up once per session; a mode re-render prints the final value at once."""
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        k = {x["id"]: x for x in KPIS["kpis"]}["aog_hours"]
        sel = '[data-kpi="aog_hours"] .mc-kpi-num'
        page.locator(sel).scroll_into_view_if_needed()
        page.wait_for_function(f"document.querySelector('{sel}').dataset.counting === 'true'", timeout=2000)
        page.wait_for_function(f"!document.querySelector('{sel}').dataset.counting", timeout=3000)
        assert page.locator(sel).inner_text().strip() == f"{round(k['value']):,}"
        page.evaluate("import('./js/lib/mode.js').then(m => m.setMode('expert'))")
        page.wait_for_function("document.body.classList.contains('mode-expert') && document.documentElement.dataset.ready === 'true'")
        page.wait_for_timeout(50)
        assert page.evaluate(f"!document.querySelector('{sel}').dataset.counting")
        assert page.locator(sel).inner_text().strip() == f"{round(k['value']):,}"
        assert not problems, problems
    finally:
        ctx.close()
