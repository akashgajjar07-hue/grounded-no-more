"""v2.1 shell: Simple/Expert mode, E4 footer on every route, term() glossary helper, names.js, capitalTable, KPI
scope line, readability helper and the PROJECT navigation group."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

CREDIT = "Built by Akash Gajjar with AI-assisted development (Claude Code). Fictional airline, simulated data."
SCOPE = "across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part"
NOTE = "Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a discount."


def _aed(v: float) -> str:
    return f"AED {abs(v) / 1e6:.1f}M"


def test_mode_toggle_persists_and_switches_body_class(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        assert page.evaluate("document.body.classList.contains('mode-simple') && !document.body.classList.contains('mode-expert')")
        toggle = page.locator(".topbar .mode-toggle[role=radiogroup]")
        assert toggle.count() == 1
        assert toggle.locator('[role=radio][aria-checked="true"]').inner_text() == "Simple"
        page.evaluate("window.__modeEvents = []; document.addEventListener('gnm:mode', (e) => window.__modeEvents.push(e.detail.mode))")
        toggle.locator('[data-mode="expert"]').click()
        page.wait_for_function("document.body.classList.contains('mode-expert') && !document.body.classList.contains('mode-simple')")
        assert page.evaluate("localStorage.getItem('gnm-mode')") == "expert"
        assert page.evaluate("window.__modeEvents") == ["expert"]
        # persisted across a reload
        page.reload()
        page.wait_for_function("document.documentElement.dataset.ready === 'true'")
        assert page.evaluate("document.body.classList.contains('mode-expert')")
        assert page.locator('.mode-toggle [data-mode="expert"]').get_attribute("aria-checked") == "true"
        # keyboard operable: the checked radio is the tab stop; arrows move and select
        assert page.locator('.mode-toggle [data-mode="expert"]').get_attribute("tabindex") == "0"
        assert page.locator('.mode-toggle [data-mode="simple"]').get_attribute("tabindex") == "-1"
        page.locator('.mode-toggle [data-mode="expert"]').focus()
        page.keyboard.press("ArrowLeft")
        page.wait_for_function("document.body.classList.contains('mode-simple')")
        assert page.evaluate("document.activeElement.dataset.mode") == "simple"
        assert page.evaluate("localStorage.getItem('gnm-mode')") == "simple"
        # the view re-rendered in place without errors
        page.wait_for_function("document.documentElement.dataset.ready === 'true'")
        assert not problems, problems
    finally:
        ctx.close()


def test_mode_survives_blocked_storage(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "390")
    try:
        page.evaluate("Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } })")
        page.locator('.mode-toggle [data-mode="expert"]').click()
        page.wait_for_function("document.body.classList.contains('mode-expert')")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "toggle overflows at 390 px"
        assert not problems, problems
    finally:
        ctx.close()


def test_footer_credit_on_every_route(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        routes = page.evaluate("import('./js/app.js').then((m) => m.ROUTES.map((r) => r.id))")
        assert {"glossary", "planner", "about", "method", "mission"} <= set(routes)
        for rid in routes:
            page.evaluate(f"import('./js/app.js').then((m) => m.navigate('#/{rid}'))")
            page.wait_for_function(f"location.hash.startsWith('#/{rid}') && document.documentElement.dataset.ready === 'true'")
            assert page.locator("footer.disclaimer").count() == 1, rid
            assert page.locator('footer.disclaimer [data-role="credit"]').inner_text().strip() == CREDIT, rid
            assert page.locator("footer.disclaimer").is_visible(), rid
            # a net capital figure is never shown without the gross lines
            bad = page.evaluate("""() => [...document.querySelectorAll('#view *')].filter((e) => !e.children.length
                && /Net change in average simulated spare inventory/.test(e.textContent)
                && !(e.closest('[data-role=capital-table]')?.querySelector('[data-row=buy]') && e.closest('[data-role=capital-table]')?.querySelector('[data-row=shed]'))).length""")
            assert bad == 0, rid
        assert not problems, problems
    finally:
        ctx.close()


def test_project_nav_group(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/glossary", "1440")
    try:
        items = page.evaluate("[...document.querySelectorAll('.nav-group[data-group=project] .nav-item')].map((i) => [i.dataset.route, i.textContent.trim()])")
        ids = [i[0] for i in items]
        assert ids == ["tour", "method", "about", "glossary", "planner"], ids
        assert any("The Planner Behind the Project" in t for _, t in items)
        assert page.locator('.nav-item[data-route="glossary"]').get_attribute("aria-current") == "page"
        assert page.locator("#view h1").inner_text() == "Glossary"
        assert not problems, problems
    finally:
        ctx.close()


def test_term_helper_first_use_and_tooltip(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "1440")
    try:
        r = page.evaluate("""async () => {
          const g = await import('./js/lib/glossary.js');
          const m = await import('./js/lib/mode.js');
          m.setMode('simple');
          g.resetTermUses();
          const host = document.createElement('p'); host.id = 'tt'; document.body.append(host);
          const a = g.term('aog_hours'), b = g.term('aog_hours'), c = g.term('frontier');
          host.append('We cut ', a, '. Later: ', b, '. ', c);
          const out = { first: a.textContent, firstSmall: a.querySelector('small.term-expert')?.textContent,
            second: b.textContent, secondSmall: !!b.querySelector('small'), frontier: c.textContent,
            desc: document.getElementById(a.getAttribute('aria-describedby'))?.textContent, tab: a.tabIndex,
            plain: g.termText('tat'), plainExpert: g.termText('tat', { mode: 'expert' }), sub: g.FRONTIER_SUBTITLE,
            entries: g.glossaryEntries().length, keys: g.glossaryEntries().map((e) => e.key) };
          m.setMode('expert');
          g.resetTermUses();
          const d = g.term('aog_hours');
          out.expert = d.textContent; out.expertSmall = !!d.querySelector('small');
          m.setMode('simple');
          return out;
        }""")
        assert r["first"] == "hours planes sat grounded waiting for a part (material AOG hours)"
        assert r["firstSmall"] == "(material AOG hours)"
        assert r["second"] == "hours planes sat grounded waiting for a part" and not r["secondSmall"]
        assert r["frontier"] == "Readiness Frontier"  # keeps its name: no bracket
        assert r["desc"] and "part" in r["desc"]
        assert r["tab"] == 0
        assert (r["plain"], r["plainExpert"]) == ("repair time", "TAT")
        assert r["sub"] == "how much readiness each extra dirham buys"
        assert r["expert"] == "material AOG hours" and not r["expertSmall"]
        need = {"aog_hours", "rotable", "float", "tat", "mtbur", "qpa", "holdout", "ci", "ebo", "fill_rate", "robbery", "forecast_methods", "frontier",
                "d0", "d3", "d10", "exchange", "local_borrow", "nff", "condemnation", "pipeline", "base_stock", "line_station", "hub", "outstation",
                "lead_time", "reorder_point", "adi_cv2", "mase", "pinball", "holdout", "palm", "guardrails"}
        assert need <= set(r["keys"]), need - set(r["keys"])
        # C3 wording is binding
        c3 = page.evaluate("import('./js/lib/glossary.js').then((g) => Object.fromEntries(g.glossaryEntries().map((e) => [e.key, e.simple])))")
        assert c3["rotable"] == "repairable part" and c3["float"] == "pool of repairable spares" and c3["ci"] == "likely range"
        assert c3["holdout"] == "20 fresh test runs the model never saw, each policy facing identical events"
        assert c3["robbery"] == "borrowing a part from another of our aircraft" and c3["ebo"] == "expected waits for a part"
        # tooltip: keyboard focus shows it, Esc hides it
        page.locator("#tt .term").first.focus()
        page.wait_for_selector(".term-pop.is-on")
        assert "grounded" in page.locator(".term-pop").inner_text().lower() or "part" in page.locator(".term-pop").inner_text()
        page.keyboard.press("Escape")
        page.wait_for_selector(".term-pop.is-on", state="detached", timeout=2000) if page.locator(".term-pop.is-on").count() else None
        assert page.locator(".term-pop.is-on").count() == 0
        # touch/click toggles it
        page.locator("#tt .term").nth(1).click()
        assert page.locator(".term-pop.is-on").count() == 1
        page.locator("#view h1").click()
        assert page.locator(".term-pop.is-on").count() == 0
        assert not problems, problems
    finally:
        ctx.close()


def test_names_mapping(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "1440")
    try:
        nb, wb = "A" + "320-family archetype", "7" + "87-family archetype"
        r = page.evaluate("""async ([nb, wb]) => {
          const n = await import('./js/lib/names.js');
          const t = n.nameTag('P2'), f = n.nameTag('B150');
          return { p0: n.displayName('P0'), p1: n.displayName('P1'), p2: n.displayName('P2'), i125: n.displayName('I125'),
            guard: n.displayName('P2_GUARD'), b150: n.displayName('B150'), short0: n.displayName('P0', { mode: 'short' }),
            code2: n.displayName('P2', { mode: 'code' }), unknown: n.displayName('XYZ'),
            tagText: t.textContent, tagCode: t.querySelector('.mono-tag')?.textContent, tagExpertOnly: t.querySelector('.mono-tag')?.classList.contains('expert-only'),
            frontierTags: f.querySelectorAll('.mono-tag').length, frontierText: f.textContent,
            nb: n.relabelArchetype(nb), wb: n.relabelArchetype('The ' + wb + ' has no bleed parts'),
            deep: n.relabelDeep({ a: [nb] }).a[0], repl: n.replaceCodes('P2 beats P0') };
        }""", [nb, wb])
        assert r["p0"] == "Simple Rulebook (naive reference)"
        assert r["p1"] == "Each Airport for Itself (simplified local comparator)"
        assert r["p2"] == "Network Plan" and r["i125"] == "Network Plan + Extra Spares"
        assert r["guard"] == "Network Plan held to guardrails" and r["b150"] == "Frontier point B150"
        assert r["short0"] == "Simple Rulebook" and r["code2"] == "Network Plan (P2)" and r["unknown"] == "XYZ"
        assert r["tagText"] == "Network Plan P2" and r["tagCode"] == "P2" and r["tagExpertOnly"]
        assert r["frontierTags"] == 0 and r["frontierText"] == "Frontier point B150"
        assert r["nb"] == "narrowbody archetype" and r["wb"] == "The widebody archetype has no bleed parts" and r["deep"] == "narrowbody archetype"
        assert r["repl"] == "Network Plan beats Simple Rulebook"
        # the tag is hidden in Simple mode, shown in Expert
        page.evaluate("import('./js/lib/names.js').then((n) => { const t = n.nameTag('P2'); t.id = 'nt'; document.body.append(t); })")
        assert not page.locator("#nt .mono-tag").is_visible()
        page.locator('.mode-toggle [data-mode="expert"]').click()
        page.wait_for_function("document.body.classList.contains('mode-expert')")
        page.evaluate("import('./js/lib/names.js').then((n) => { const t = n.nameTag('P2'); t.id = 'nt2'; document.body.append(t); })")
        assert page.locator("#nt2 .mono-tag").is_visible()
        assert not problems, problems
    finally:
        ctx.close()


def test_capital_table_never_shows_net_alone(site, browser):  # noqa: F811
    core = json.loads((DOCS / "data" / "kpis.json").read_text())["headline"]["core"]
    rm = core["remix"]
    ctx, page, problems = open_page(browser, site + "#/about", "1440")
    try:
        r = page.evaluate("""async () => {
          const ui = await import('./js/ui.js');
          const k = await (await fetch('data/kpis.json')).json();
          const rows = (el) => [...el.querySelectorAll('tr')].map((tr) => [tr.dataset.row, [...tr.children].map((c) => c.textContent.trim())]);
          const full = ui.capitalTable(k.headline.core);
          const noNet = ui.capitalTable({ ...k.headline.core.remix });
          const netOnly = ui.capitalTable({ net_aed: 614985 }, { net: 614985 });
          return { full: rows(full), note: full.querySelector('.capital-note')?.textContent, role: full.dataset.role,
            noNet: rows(noNet), netOnly: netOnly.textContent, netOnlyRows: netOnly.querySelectorAll('tr').length };
        }""")
        assert r["role"] == "capital-table" and r["note"] == NOTE
        full = dict(r["full"])
        assert [k for k, _ in r["full"]] == ["buy", "shed", "net"]
        assert full["buy"] == ["New rotables bought", f"+{rm['buy_units']} units", f"≈ {_aed(rm['buy_aed'])} assumed value"]
        assert full["shed"] == ["Rotables removed", f"−{rm['shed_units']} units", f"≈ {_aed(rm['shed_aed'])}"]
        assert full["net"][0] == "Net change in average simulated spare inventory"
        assert full["net"][2] == f"+{_aed(core['capital_aed']['mean'])}"
        # the expected values from the brief
        assert full["buy"][1:] == ["+68 units", "≈ AED 8.4M assumed value"] and full["shed"][1:] == ["−20 units", "≈ AED 3.1M"] and full["net"][2] == "+AED 0.6M"
        assert [k for k, _ in r["noNet"]] == ["buy", "shed"]
        assert r["netOnlyRows"] == 0 and "0.6" not in r["netOnly"]
        assert not problems, problems
    finally:
        ctx.close()


def test_shared_blocks_and_kpi_scope(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        tiles = page.locator("#view .kpi")
        assert tiles.count() >= 1
        for i in range(tiles.count()):
            assert tiles.nth(i).locator('[data-role="scope"]').inner_text().strip() == SCOPE
        r = page.evaluate("""async () => {
          const ui = await import('./js/ui.js');
          const t = ui.kpiTile({ label: 'x', value: 1, baseline: 2, delta: -1, better: 'lower', provenance: 'SIMULATED' }, { scope: '' });
          const i = ui.intro3({ what: 'A', why: 'B', action: 'C' });
          return { tileScope: t.querySelector('[data-role=scope]').textContent, scope: ui.scopeLine().textContent,
            reading: ui.readingNote().textContent, badge: ui.postPlanBadge().textContent,
            intro: [...i.querySelectorAll('.intro3-row')].map((r) => [r.querySelector('dt').textContent, r.querySelector('dd').textContent]) };
        }""")
        assert r["tileScope"] == SCOPE and r["scope"] == SCOPE
        assert r["reading"].startswith("How to read these numbers: simulated downtime of the aircraft waiting for the part")
        assert r["reading"].endswith("These are not forecasts of achievable airline savings.")
        assert r["badge"] == "post-plan, exploratory"
        assert r["intro"] == [["What this shows", "A"], ["Why it matters", "B"], ["What a planner would do", "C"]]
        assert not problems, problems
    finally:
        ctx.close()


def test_readability_helper(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/planner", "1440")
    try:
        r = page.evaluate("""async () => {
          const R = await import('./js/lib/readability.js');
          const easy = R.readabilityOfText('The cat sat on the mat. It was a good day.');
          const long = R.readabilityOfText(Array(30).fill('word').join(' ') + '.');
          const host = document.createElement('div');
          host.innerHTML = '<h2>Short title</h2><p>One plain sentence here. Another one.</p><p class="sr-only">Hidden extraordinarily complicated terminology.</p><div class="table-wrap"><p>Ignored table text.</p></div>';
          document.querySelector('#view').append(host);
          const dom = R.readability(host);
          return { easy, long, dom, view: R.readability() };
        }""")
        assert r["easy"]["sentences"] == 2 and r["easy"]["grade"] < 3
        assert r["long"]["maxSentenceWords"] == 30 and len(r["long"]["longSentences"]) == 1
        assert r["dom"]["sentences"] == 3 and r["dom"]["words"] == 8, r["dom"]
        assert r["view"]["words"] > 10
        assert not problems, problems
    finally:
        ctx.close()


# ---------------------------------------------------------------------------------------------- tour engine (v2.1 addendum)
READY_STEP = "window.__gnmStory && window.__gnmStory.state().ready"


def _start_tour(page, how="#story-btn", step_ms=1200):
    page.evaluate(f"window.__gnmTourStepMs = {step_ms}")
    t0 = page.evaluate("performance.now()")
    if how.startswith("key:"):
        page.locator("body").press(how[4:])
    else:
        page.locator(how).first.click()
    page.wait_for_selector(".story .story-card", timeout=1000)   # visibly does something within 1 s
    assert page.evaluate("performance.now()") - t0 < 1000
    page.wait_for_function(READY_STEP, timeout=20000)


@pytest.mark.parametrize("how", ["#story-btn", '.nav-item[data-route="tour"]', "key:s"])
def test_tour_entry_points_open_within_1s(site, browser, how):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        _start_tour(page, how)
        assert page.locator(".story").count() == 1
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.story')")
    finally:
        ctx.close()


def test_tour_auto_advances_with_filling_bar(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        _start_tour(page, step_ms=1500)
        page.locator(".story-play").click()
        assert page.locator(".story-play").get_attribute("aria-pressed") == "true"
        page.wait_for_timeout(500)
        a = page.evaluate("window.__gnmStory.state().elapsed")
        fa = page.evaluate("document.querySelector('.story-progress .is-current .story-fill').style.transform")
        page.wait_for_timeout(400)
        b = page.evaluate("window.__gnmStory.state().elapsed")
        fb = page.evaluate("document.querySelector('.story-progress .is-current .story-fill').style.transform")
        assert b > a and fa != fb and fb.startswith("scaleX(")
        page.wait_for_function("window.__gnmStory.state().index === 1", timeout=5000)
        # the counter crossfades with the title/body (150 ms out), so it reads STEP 02 once the swap lands
        page.wait_for_function("document.querySelector('.story-step').textContent.includes('STEP 02')", timeout=1000)
        assert page.evaluate("window.__gnmStory.state().playing")
        # the first segment is complete once the tour moved on
        assert page.evaluate("document.querySelectorAll('.story-progress .story-fill')[0].style.transform") == "scaleX(1)"
        # Next/Back still work while playing
        page.wait_for_function(READY_STEP, timeout=20000)
        page.locator(".story button", has_text="Back").click()
        page.wait_for_function("window.__gnmStory.state().index === 0")
        assert page.evaluate("window.__gnmStory.state().playing")
        page.keyboard.press("Escape")
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_tour_pause_freezes_timer_and_bar(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        _start_tour(page, step_ms=4000)
        page.evaluate("window.__gnmStory.play()")
        page.wait_for_timeout(1300)
        page.locator(".story-play").click()   # pause
        assert page.locator(".story-play").inner_text().strip() == "Play"
        s1 = page.evaluate("window.__gnmStory.state()")
        f1 = page.evaluate("document.querySelector('.story-progress .is-current .story-fill').style.transform")
        page.wait_for_timeout(1500)
        s2 = page.evaluate("window.__gnmStory.state()")
        f2 = page.evaluate("document.querySelector('.story-progress .is-current .story-fill').style.transform")
        assert s1["elapsed"] > 0 and s2["elapsed"] == s1["elapsed"] and f1 == f2 and s2["index"] == 0
        assert s2["loops"] == 0 and not s2["playing"]
        # resume continues from where it froze
        page.evaluate("window.__gnmStory.play()")
        page.wait_for_timeout(600)
        assert page.evaluate("window.__gnmStory.state().elapsed") > s1["elapsed"]
        page.keyboard.press("Escape")
    finally:
        ctx.close()


def test_tour_repeated_play_never_overlaps(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        _start_tour(page, step_ms=60000)
        for _ in range(10):
            page.evaluate("window.__gnmStory.play()")
        assert page.evaluate("window.__gnmStory.state().loops") == 1
        for _ in range(7):
            page.locator(".story-play").click()
        assert page.evaluate("window.__gnmStory.state().loops") in (0, 1)
        page.evaluate("window.__gnmStory.play()")
        a = page.evaluate("[performance.now(), window.__gnmStory.state().elapsed]")
        page.wait_for_timeout(1000)
        b = page.evaluate("[performance.now(), window.__gnmStory.state().elapsed]")
        rate = (b[1] - a[1]) / (b[0] - a[0])
        assert 0.6 < rate < 1.3, rate   # one clock, real time (overlapping loops would run it 2-10x fast)
        page.keyboard.press("Escape")
    finally:
        ctx.close()


def test_tour_escape_and_skip_clear_all_timers(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        for close in ("Escape", "skip"):
            page.evaluate("import('./js/app.js').then((m) => m.navigate('#/mission'))")
            page.wait_for_function("location.hash === '#/mission' && document.documentElement.dataset.ready === 'true'")
            _start_tour(page, step_ms=2000)
            page.evaluate("window.__t = window.__gnmStory; window.__gnmStory.play()")
            page.locator(".story button", has_text="Next").click()   # a step change with pending waits
            if close == "Escape":
                page.keyboard.press("Escape")
            else:
                page.locator(".story-skip").click()
            page.wait_for_function("!document.querySelector('.story')")
            s = page.evaluate("window.__t.state()")
            assert s["loops"] == 0 and s["timers"] == 0 and not s["playing"], s
            assert page.evaluate("window.__gnmStory === undefined")
            h0 = page.evaluate("location.hash")
            page.wait_for_timeout(2500)
            assert page.evaluate("location.hash") == h0 and page.locator(".story").count() == 0   # nothing fires later
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()


def test_tour_stops_at_last_step_and_resets_to_play(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        _start_tour(page, step_ms=800)
        page.evaluate("window.__gnmStory.go(5)")
        page.wait_for_function("window.__gnmStory.state().index === 5 && window.__gnmStory.state().ready", timeout=20000)
        page.evaluate("window.__gnmStory.play()")
        page.wait_for_function("!window.__gnmStory.state().playing", timeout=5000)
        s = page.evaluate("window.__gnmStory.state()")
        assert s["index"] == 5 and s["loops"] == 0
        assert page.locator(".story-play").inner_text().strip() == "Play"
        assert page.locator(".story-play").get_attribute("aria-pressed") == "false"
        assert page.locator(".story").count() == 1   # stays open on the last step
        page.keyboard.press("Escape")
    finally:
        ctx.close()


def test_tour_reduced_motion_still_auto_advances_at_7s(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")   # reduced motion context
    try:
        page.locator("#story-btn").click()
        page.wait_for_function(READY_STEP, timeout=20000)
        assert page.evaluate("window.__gnmStory.state().stepMs") == 7000
        page.evaluate("window.__gnmStory.play()")
        page.wait_for_timeout(5500)
        assert page.evaluate("window.__gnmStory.state().index") == 0
        page.wait_for_function("window.__gnmStory.state().index === 1", timeout=4000)
        page.keyboard.press("Escape")
    finally:
        ctx.close()


def test_tour_text_follows_reading_mode(site, browser):  # noqa: F811
    steps = json.loads((DOCS / "data" / "story.json").read_text())["steps"]
    assert all(s.get("body_simple") and s.get("title_simple") for s in steps)
    assert all(len(s["body_simple"]) <= 300 for s in steps)
    import re
    for s in steps:
        for k in ("body", "body_simple", "title", "title_simple"):
            assert not re.search(r"\b(P[012]|I125|P2_GUARD)\b", s[k]), (k, s[k])     # display names, never bare codes
            assert "88%" not in s[k]
            if "AED 0.6M" in s[k] or "inventory" in s[k] or "stock value" in s[k]:
                assert "8.4M" in s[k] and "3.1M" in s[k], s[k]                          # A4: never the net alone
            if re.search(r"\d[\d,]* (h|hours) a year", s[k]) and "network" in s[k].lower():
                assert "in this simulation" in s[k].lower() and "120 modelled part numbers" in s[k], s[k]
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        _start_tour(page, step_ms=60000)
        assert page.locator(".story-card p").inner_text() == steps[0]["body_simple"]
        assert page.locator(".story-card h3").inner_text() == steps[0]["title_simple"]
        page.evaluate("import('./js/lib/mode.js').then((m) => m.setMode('expert'))")
        page.wait_for_function(f"document.querySelector('.story-card p').textContent === {json.dumps(steps[0]['body'])}")
        assert page.locator(".story").count() == 1
        page.evaluate("import('./js/lib/mode.js').then((m) => m.setMode('simple'))")
        page.keyboard.press("Escape")
        r = page.evaluate("""async () => { const R = await import('./js/lib/readability.js');
          return %s.map((t) => R.readabilityOfText(t)); }""" % json.dumps([s["body_simple"] for s in steps]))
        assert max(x["maxSentenceWords"] for x in r) <= 25
    finally:
        ctx.close()


# ---------------------------------------------------------------------------------------------- motion tokens
TOKENS = {"--motion-fast": "150ms", "--motion-base": "250ms", "--motion-slow": "450ms", "--motion-hero": "1200ms",
          "--ease-standard": "cubic-bezier(0.2, 0, 0, 1)", "--ease-enter": "cubic-bezier(0, 0, 0, 1)", "--ease-exit": "cubic-bezier(0.3, 0, 1, 1)"}
TOKENS_JS = "() => Object.fromEntries(%s.map((k) => [k, getComputedStyle(document.documentElement).getPropertyValue(k).trim()]))" % json.dumps(list(TOKENS))


def test_motion_tokens_and_helpers(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440", reduced=False)
    try:
        assert page.evaluate(TOKENS_JS) == TOKENS
        r = page.evaluate("""async () => {
          const M = await import('./js/lib/motion.js');
          let calls = 0, last = null;
          const f = M.throttleRAF((v) => { calls++; last = v; });
          for (let k = 0; k < 50; k++) f(k);
          await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
          const el = document.createElement('span'); document.body.append(el);
          M.countUpOnce(el, 1480, (v) => Math.round(v).toLocaleString('en-GB'), { key: 'test-count' });
          await new Promise((res) => setTimeout(res, 150));
          const mid = el.textContent, counting = el.dataset.counting;
          await new Promise((res) => setTimeout(res, 650));
          const end = el.textContent;
          const el2 = document.createElement('span'); document.body.append(el2);
          M.countUpOnce(el2, 1480, (v) => Math.round(v).toLocaleString('en-GB'), { key: 'test-count' });
          const t = M.chartTransition();
          return { calls, last, mid, counting, end, again: el2.textContent, again2: el2.dataset.counting || null,
            m: [M.MOTION.fast, M.MOTION.base, M.MOTION.slow, M.MOTION.hero, M.MOTION.ease.standard],
            td: t.duration(), tds: M.chartTransition({ duration: 'slow' }).duration(), dur: M.dur('base') };
        }""")
        assert r["calls"] == 1 and r["last"] == 49
        assert r["counting"] == "true" and r["mid"] != "1,480" and r["end"] == "1,480"
        assert r["again"] == "1,480" and r["again2"] is None   # once per key per session: no re-count on re-render
        assert r["m"] == [150, 250, 450, 1200, "cubic-bezier(0.2, 0, 0, 1)"]
        assert r["td"] == 250 and r["tds"] == 450 and r["dur"] == 250
        # workspace change: the view fades + rises (250 ms), cards stagger 40 ms (max 6)
        page.evaluate("import('./js/app.js').then((m) => m.navigate('#/about'))")
        page.wait_for_function("location.hash === '#/about' && document.documentElement.dataset.ready === 'true'")
        v = page.evaluate("(() => { const cs = getComputedStyle(document.querySelector('#view')); return [cs.animationName, cs.animationDuration]; })()")
        assert v == ["motion-rise", "0.25s"], v
        st = page.evaluate("[...document.querySelectorAll('#view .motion-stagger')].map((e) => getComputedStyle(e).animationDelay)")
        assert 0 < len(st) <= 6 and st[:2] == ["0s", "0.04s"][:len(st)], st
        # modal scale + fade
        page.keyboard.press("?")
        page.wait_for_selector(".modal-card")
        assert page.evaluate("getComputedStyle(document.querySelector('.modal-card')).animationName") == "motion-pop"
        page.keyboard.press("Escape")
        # sliding toggle: the mode thumb moves by transform
        t1 = page.evaluate("document.querySelector('.mode-toggle .seg-thumb').style.transform")
        page.locator('.mode-toggle [data-mode="expert"]').click()
        page.wait_for_timeout(100)
        t2 = page.evaluate("document.querySelector('.mode-toggle .seg-thumb').style.transform")
        assert t1 != t2 and t2.startswith("translateX(")
        page.locator('.mode-toggle [data-mode="simple"]').click()
        assert not problems, problems
    finally:
        ctx.close()


def test_motion_reduced_honoured(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")   # reduced motion
    try:
        tok = page.evaluate(TOKENS_JS)
        assert tok["--motion-fast"] == "0ms" and tok["--motion-base"] == "0ms" and tok["--motion-slow"] == "0ms"
        page.evaluate("import('./js/app.js').then((m) => m.navigate('#/about'))")
        page.wait_for_function("location.hash === '#/about' && document.documentElement.dataset.ready === 'true'")
        assert page.evaluate("getComputedStyle(document.querySelector('#view')).animationName") == "none"
        assert page.locator("#view .motion-stagger").count() == 0
        r = page.evaluate("""async () => {
          const M = await import('./js/lib/motion.js');
          const el = document.createElement('span'); document.body.append(el);
          M.countUpOnce(el, 42, String, { key: 'rm-count' });
          return { text: el.textContent, dur: M.dur('slow'), td: M.chartTransition().duration(), reduced: M.reducedMotion() };
        }""")
        assert r == {"text": "42", "dur": 0, "td": 0, "reduced": True}
        page.keyboard.press("?")
        page.wait_for_selector(".modal-card")
        assert page.evaluate("getComputedStyle(document.querySelector('.modal-card')).animationName") == "none"
        assert not problems, problems
    finally:
        ctx.close()


def test_glossary_lookup_precedence(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "1440")
    try:
        r = page.evaluate("""import('./js/lib/glossary.js').then((g) => ({
          croston: g.glossaryEntry('Croston')?.key, crostonKey: g.glossaryEntry('croston')?.key, sba: g.glossaryEntry('SBA')?.key,
          tsb: g.glossaryEntry('tsb')?.key, tat: g.glossaryEntry('TAT')?.key, cannibal: g.glossaryEntry('cannibalisation')?.key,
          group: g.glossaryEntry('Croston / SBA / TSB')?.key, ci: g.glossaryEntry('95% CI')?.key, none: g.glossaryEntry('nope') }))""")
        assert r == {"croston": "croston", "crostonKey": "croston", "sba": "sba", "tsb": "tsb", "tat": "tat", "cannibal": "robbery",
                     "group": "forecast_methods", "ci": "ci", "none": None}, r
    finally:
        ctx.close()


def test_term_bracket_wraps_at_390(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "390")
    try:
        r = page.evaluate("""async () => {
          const g = await import('./js/lib/glossary.js'); g.resetTermUses();
          const p = document.createElement('p'); p.style.maxWidth = '100%'; document.querySelector('#view').prepend(p);
          const t = g.term('holdout', { first: true }); p.append('Results use ', t, ' only.');
          const short = document.createElement('p'); document.querySelector('#view').prepend(short);
          const s = g.term('tat', { first: true }); short.append('Cut the ', s, ' now.');
          const sm = s.querySelector('.term-expert');
          return { hscroll: document.documentElement.scrollWidth > innerWidth, right: t.querySelector('.term-expert').getBoundingClientRect().right,
            vw: document.documentElement.clientWidth, ws: getComputedStyle(t.querySelector('.term-expert')).whiteSpace,
            shortLines: sm.getClientRects().length };
        }""")
        assert not r["hscroll"] and r["right"] <= r["vw"] + 1 and r["ws"] == "normal", r
        assert r["shortLines"] == 1, r          # a short bracket stays on one line
    finally:
        ctx.close()
