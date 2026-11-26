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
        # top 5 priority part numbers deep-link into the action centre
        links = page.locator('[data-story="mission-actions"] a.mc-pr')
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
        href = page.locator('[data-story="mission-actions"] a.mc-pr').first.get_attribute("href")
        page.locator('[data-story="mission-actions"] a.mc-pr').first.click()
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


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave2_priorities_grid_and_headlines(site, browser, vp):  # noqa: F811
    """Critic #5/#8: priorities are a grid grouped by PN (no repeated PN), headlines <= 90 chars, no clipped cells."""
    acts = json.loads((DOCS / "data/actions.json").read_text())["actions"]
    ctx, page, problems = open_page(browser, site + "#/mission", vp)
    try:
        rows = page.locator('[data-story="mission-actions"] a.mc-pr')
        pns = [rows.nth(i).locator(".mc-pr-pn").inner_text() for i in range(rows.count())]
        assert len(pns) == len(set(pns)) and set(pns) <= {a["pn"] for a in acts}
        # every row shows the deciding number and the due week
        for i in range(rows.count()):
            assert rows.nth(i).locator(".mc-pr-v").inner_text().strip()
            assert rows.nth(i).locator(".mc-pr-due").inner_text().strip()
        heads = page.evaluate("[...document.querySelectorAll('#view .chart-headline')].map(e => e.textContent.trim())")
        assert heads and all(len(t) <= 90 for t in heads), heads
        # the open-actions tile has a severity ruler, so its footer lines up with the other KPI tiles
        assert page.locator('[data-kpi="open_exceptions"] .mc-sev, [data-kpi="open_actions"] .mc-sev').count() == 1
        if vp == "1440":
            foots = page.evaluate("[...document.querySelectorAll('[data-story=\"mission-kpis\"] .kpi-foot')].map(e => Math.round(e.getBoundingClientRect().top))")
            assert max(foots) - min(foots) <= 24, foots
            # the fault callout keeps clear of the fuselage centreline (critic: it butted against the nose)
            gap = page.evaluate("""() => { const f = document.querySelector('.mc-fault').getBoundingClientRect();
              const s = document.querySelector('.mc-fig svg').getBoundingClientRect(); return (s.left + s.width / 2) - f.right; }""")
            assert gap >= 40, gap
        # the part-level risk badge sits in the fault callout, so the status matches story step 2
        assert page.locator('.mc-fault-risk').count() == 1
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_wave2_story_targets_are_tight(site, browser):  # noqa: F811
    """Critic #10: the story card never covers the spotlit target on the steps my content controls (1440)."""
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        page.locator('[data-story="mission-start"]').click()
        for i in range(1, 5):
            page.wait_for_function("document.querySelector('.story') && !document.querySelector('.story').hasAttribute('aria-busy')", timeout=15000)
            page.wait_for_timeout(500)
            ov = page.evaluate("""() => { const c = document.querySelector('.story-card').getBoundingClientRect(), s = document.querySelector('.story-spot').getBoundingClientRect();
              return Math.max(0, Math.min(c.right, s.right) - Math.max(c.left, s.left)) * Math.max(0, Math.min(c.bottom, s.bottom) - Math.max(c.top, s.top)); }""")
            assert ov == 0, (i, ov)
            assert page.evaluate("document.querySelector('.story-spot').getBoundingClientRect().height") > 40, i
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(300)
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave3_consistency_colour_and_balance(site, browser, vp):  # noqa: F811
    """Review 2: system level shown with the urgent part, canonical AOG metric, no teal on the station list,
    KPI rulers read baseline → recommended left to right, columns end level, short policy names at 390."""
    parts = json.loads((DOCS / "data/parts.json").read_text())
    by_pn = {p["pn"]: p for p in parts["parts"]}
    sys_by = {a["ata"]: a for a in parts["ata_systems"]}
    ctx, page, problems = open_page(browser, site + "#/mission", vp)
    try:
        # hero callout: urgent PART + its system level as Parts rates it
        pn = page.locator(".mc-fault-pn").inner_text().strip()
        ata = pn.split("-")[1]
        lvl = (sys_by[ata].get("status_label") or "").split(" · ")[0].lower() or sys_by[ata].get("system_level") or sys_by[ata]["risk_level"]
        assert "part" in page.locator(".mc-fault-k").inner_text().lower()
        assert f"system {'ok' if lvl == 'ok' else lvl}" in page.locator(".mc-fault-sys").inner_text().lower()
        # priorities AOG column = parts.json aog_h_52w_max_station (same metric as the Action Centre)
        rows = page.locator('[data-story="mission-actions"] a.mc-pr')
        for i in range(rows.count()):
            p = by_pn[rows.nth(i).locator(".mc-pr-pn").inner_text().strip()]
            if "aog_h_52w_max_station" in p:
                # wave 4 (C1): "120 h · AUH" — the number travels with its station; 0 h prints as "—"
                v = round(p["aog_h_52w_max_station"])
                cell = rows.nth(i).locator(".mc-pr-aog").inner_text()
                if v:
                    assert f"{v:,} h" in cell and (p.get("aog_h_52w_max_station_id") or "") in cell, cell
                else:
                    assert "—" in cell, cell
        # no "System OK" pill without its urgent-part count
        for r in page.locator(".mc-sys-row").all():
            t = r.inner_text()
            assert not (t.strip().endswith("OK") and "urgent" in t), t
        # station list carries no teal (teal = the recommended plan)
        fills = page.evaluate("[...document.querySelectorAll('.mc-st-bar > span')].map(e => getComputedStyle(e).backgroundColor)")
        assert fills and not any("34, 199, 184" in f for f in fills), fills
        # every dumbbell: baseline dot left of the recommended dot
        dbs = page.evaluate("""() => [...document.querySelectorAll('.mc-db-track')].map((t) => [
          t.querySelector('.mc-db-dot--base').getBoundingClientRect().left, t.querySelector('.mc-db-dot--rec').getBoundingClientRect().left])""")
        assert dbs and all(b < r for b, r in dbs), dbs
        if vp == "1440":
            cols = page.evaluate("[...document.querySelectorAll('.mc-grid > .mc-col')].map(c => Math.round(c.lastElementChild.getBoundingClientRect().bottom))")
            assert max(cols) - min(cols) <= 24, cols
        else:
            labels = page.evaluate("[...document.querySelectorAll('[data-story=\"mission-compare\"] svg text')].map(t => t.textContent)")
            assert not any("…" in t for t in labels), labels
        assert not problems, problems
    finally:
        ctx.close()
