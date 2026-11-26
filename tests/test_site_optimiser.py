"""Browser tests for 06 Capital Optimiser (screen agent D)."""
from __future__ import annotations

import json
import re

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
        rec_name = F["display_names"][F["recommended"]]["short_name"]
        assert rec_name in page.locator('[data-story="frontier-chart"]').text_content()
        assert page.locator('[data-story="allocation-table"]').get_attribute("data-point") == F["recommended"]
        assert rec_name in page.locator('[data-story="allocation-table"] .card-kicker').text_content()
        txt = page.locator("#view").inner_text()
        assert "heuristic" in txt and "AOG-desk" in txt
        # low-stress honesty note is present when the data says the point does not pay there
        low = next((v for v in F.get("variant_robustness", []) if v.get("variant") == "low_stress"), None)
        if low and low["rec_vs_P2"]["net_benefit_aed"] < 0:
            assert "not worth its extra" in txt
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
        assert re.search(r"capital|spares", cap.locator(".kpi-delta").first.inner_text())
        # no copper on P1/P2 policy labels; P0 keeps copper (baseline)
        fills = page.evaluate("""() => [...document.querySelectorAll('[data-story="frontier-chart"] svg text.gnm-label--strong')]
            .map((t) => [t.textContent.trim(), getComputedStyle(t).fill])""")
        for txt, fill in fills:
            if txt.startswith("Each Airport") or txt.startswith("Network Plan"):
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
            assert "H AVOIDED" in card.locator(".dts-metric").first.inner_text().upper()
            sec = card.locator(".dts-secondary").first.inner_text()
            assert "Units" in sec and "Spares AED" in sec
        else:
            ths = card.locator("thead th").all_inner_texts()
            assert any("CHANGE" in t.upper() for t in ths) and any("AVOIDED" in t.upper() for t in ths)
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave3_capital(site, browser, vp):  # noqa: F811
    """Design wave 3: slider aria-valuetext (F5), neutral tornado bars with × settings, the unstable
    whisker is annotated from data, and the frontier card is not stretched by the side column."""
    F = _frontier()
    ctx, page, problems = open_page(browser, site + "#/capital", vp)
    try:
        vt = page.locator('[data-role="budget-slider"]').get_attribute("aria-valuetext") or ""
        assert "AED" in vt and F["recommended"] in vt, vt
        tor = page.evaluate("""() => {
          const t = document.querySelector('[data-story="tornado"]');
          return { teal: [...t.querySelectorAll('svg rect')].filter((r) => (r.getAttribute('fill') || '').toLowerCase() === '#22c7b8').length,
                   text: t.querySelector('svg').textContent };
        }""")
        assert tor["teal"] == 0
        assert "x0" not in tor["text"] and "×" in tor["text"]
        unstable = [p["id"] for p in F["points"] if p.get("aog_ci") and p["aog_ci"][0] is not None and p["aog_ci"][0] <= 0 and p.get("kind") != "policy"]
        if unstable:
            ann = page.evaluate("() => [...document.querySelectorAll('[data-story=\"frontier-chart\"] .co-unstable')].map((t) => t.textContent)")
            assert ann, ann
        if vp == "1440":
            gap = page.evaluate("""() => { const c = document.querySelector('[data-story="frontier-chart"]'); const det = c.querySelector('details'); return c.getBoundingClientRect().bottom - det.getBoundingClientRect().bottom; }""")
            assert gap < 80, gap
        assert not problems, problems
    finally:
        ctx.close()


# ---- v2.1 final release (PAGE-4): plain English, display names, A4 / A6 / A8 / A9, both modes, both viewports
def _open_mode(browser, url, vp, mode):
    w, h = VIEWPORTS[vp]
    ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
    ctx.add_init_script(f"try{{localStorage.setItem('gnm-mode','{mode}')}}catch(e){{}}")
    page = ctx.new_page()
    problems: list[str] = []
    page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=15000)
    page.wait_for_timeout(1000)
    return ctx, page, problems


FORBIDDEN = re.compile(r"\b(validated|optimal|optimum)\b|representative legacy airline practice|panel-proof|robust across worlds|saves the airline AED|Etihad|A320|Airbus|Boeing|787", re.I)
BARE_CODE = re.compile(r"(?<![\w-])(P0|P1|P2|I125|P2_GUARD)(?![\w-])")


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_capital(site, browser, vp, mode):  # noqa: F811
    F = _frontier()
    ctx, page, problems = _open_mode(browser, site + "#/capital", vp, mode)
    try:
        audit(page, problems, min_frames=4)
        view = page.locator("#view")
        txt = view.inner_text()
        assert not FORBIDDEN.search(txt), FORBIDDEN.findall(txt)
        # name and subtitle; the intro block; the scope line on every KPI and under the frontier
        assert "The Readiness Frontier" in txt
        assert page.locator('[data-role="frontier-subtitle"]').inner_text().strip() == F["subtitle"]
        assert page.locator('[data-role="intro3"]').count() == 1
        assert page.locator('[data-story="capital-kpis"] .kpi-scope').count() >= 3
        assert page.locator('[data-story="frontier-chart"] [data-role="scope"]').count() == 1
        # A4: gross buys and removals, then the net; never the net alone
        ct = page.locator('[data-story="capital-table"] [data-role="capital-table"]')
        assert ct.count() == 1
        rows = {r: ct.locator(f'tr[data-row="{r}"]').inner_text() for r in ("buy", "shed", "net")}
        cap = F["capital_table"]
        assert f"+{cap['bought_units']} units" in rows["buy"] and "AED 8.4M" in rows["buy"]
        assert f"{cap['removed_units']} units" in rows["shed"] and "AED 3.1M" in rows["shed"]
        assert "+AED 0.6M" in rows["net"]
        assert "Removed stock is not cash back" in ct.inner_text()
        title = page.locator('[data-story="capital-table"] .card-title').inner_text()
        assert "Network Plan" in title and "Simple Rulebook" in title
        assert txt.count("Net change in average simulated spare inventory") == 1
        # A8 verbatim with the four levers
        ins = page.locator('[data-story="frontier-insight"]')
        assert ins.locator('[data-role="insight-text"]').inner_text().strip() == F["insight"]["text"]
        assert ins.locator('[data-role="levers"] li').all_inner_texts() == F["insight"]["levers"]
        # A6 under the frontier results
        a6 = page.locator('[data-story="frontier-chart"] [data-role="stress-ranges"]').inner_text()
        assert F["stress_worlds"]["text"] in a6 and F["stress_worlds"]["ranges_note"] in a6
        # A9: the frontier option's outstation brake rows carry the verbatim flag
        flags = page.locator('[data-role="invalid-allocations"]').inner_text()
        assert F["invalid_allocation_text"] in flags
        n_inv = sum(1 for r in F["allocations"][F["recommended"]] if r.get("invalid_recommendation"))
        assert page.locator('[data-story="allocation-table"] [data-role="invalid-flag"]').count() >= (n_inv if vp == "1440" else 1)
        # wording + display names
        assert "best evaluated allocation under the stated scenario" in txt
        assert "Network Plan + Extra Spares" in txt and "Simple Rulebook" in txt
        if mode == "simple":
            vis = page.evaluate("""() => { const c = document.querySelector('#view').cloneNode(true);
              c.querySelectorAll('.mono-tag, .expert-only, .term-expert, table, svg, .sr-only, [hidden]').forEach((e) => e.remove()); return c.textContent; }""")
            assert not BARE_CODE.search(vis), BARE_CODE.findall(vis)
            assert not re.search(r"\b(TAT|holdout|CI)\b", vis), re.findall(r"\b(TAT|holdout|CI)\b", vis)
            r = page.evaluate("import('./js/lib/readability.js').then(R => R.readability(document.querySelector('#view')))")
            assert r["grade"] <= 9 and r["maxSentenceWords"] <= 25, r["longSentences"]
        else:
            assert page.locator('[data-story="capital-paired"]').count() == 1
            assert "Holdout" in txt or "holdout" in txt
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_capital_frozen_p2_flags(site, browser):  # noqa: F811
    """Selecting the Network Plan itself lists its frozen outstation brake allocations (parts.json), flagged, not deleted."""
    parts = json.loads((DOCS / "data" / "parts.json").read_text())
    p2 = [r for r in parts.get("invalid_allocations", []) if r["policy"] == "P2"]
    ctx, page, problems = _open_mode(browser, site + "#/capital?point=P2", "1440", "simple")
    try:
        if page.locator('[data-story="allocation-table"]').get_attribute("data-point") == "P2" and p2:
            t = page.locator('[data-role="invalid-allocations"]').inner_text()
            assert parts["invalid_allocation_text"] in t
            assert all(f"{r['pn']} at {r['station']}" in t for r in p2)
        assert not problems, problems
    finally:
        ctx.close()
