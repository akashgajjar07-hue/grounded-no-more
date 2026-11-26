"""04 Rotable & Repair: browser checks (routes, deep links, both viewports) and float-calculator parity."""
from __future__ import annotations

import pytest

from _sitefx_c import VIEWPORTS, assert_clean, open_route, serve_docs

pytestmark = pytest.mark.browser
playwright = pytest.importorskip("playwright.sync_api")

ROUTES = ["#/rotables", "#/rotables?pn=GN-32-R014", "#/rotables?shop=EU_VENDOR"]


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
        for hook in ["rotable-lifecycle", "repair-queue", "rotable-tat", "rotable-float-calc", "palm-vs-sim"]:
            assert page.locator(f'[data-story="{hook}"]').count() >= 1, hook
        # v2.1: Simple mode (the default) names the calculator plainly; the method name is Expert-only
        assert "spares calculator" in page.inner_text("#view").lower()
    finally:
        ctx.close()


def test_filters_keep_page_clean(site):
    b, base = site
    ctx, page, problems = open_route(b, base, "#/rotables", "1440")
    try:
        for label in ["Open", "Overdue", "Open + recent"]:
            page.get_by_role("radio", name=label, exact=True).click()
            page.wait_for_timeout(150)
        assert_clean(page, problems, "filters")
    finally:
        ctx.close()


INPUT_SETS = [
    {"rate": 1.25, "tat": 42, "spares": 3, "cost": 180000, "extra": 1, "cut": 10},
    {"rate": 0.4, "tat": 95.5, "spares": 1, "cost": 52000, "extra": 2, "cut": 30},
]


@pytest.mark.parametrize("inp", INPUT_SETS)
def test_float_calculator_matches_floatcalc_js(site, inp):
    """Type inputs into the UI, then compare displayed outputs with floatcalc.js evaluated in the page."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/rotables", "1440")
    try:
        for k, v in inp.items():
            page.fill(f'[data-input="{k}"]', str(v))
        # wave 5: the lever tool defaults to the station view; compare against the calculator inputs here
        if page.locator('[data-basis="inputs"]').count():
            page.locator('[data-basis="inputs"]').click()
        page.wait_for_timeout(200)
        shown = page.evaluate(
            # wave 4: displays are rounded for reading ("< 0.01", "> 99.9%"); the exact value is in data-value
            """() => Object.fromEntries([...document.querySelectorAll('[data-out]')].map((e) => [e.dataset.out, e.dataset.value ?? e.textContent.trim()]))"""
        )
        ref = page.evaluate(
            """async (i) => {
              const m = await import('./js/lib/floatcalc.js');
              const r = m.floatCalc(i.rate, i.tat, i.spares, i.cost);
              const c = m.compareLevers(i.rate, i.tat, i.spares, i.cost, i.cut, i.extra, 0);
              return { r, c };
            }""",
            inp,
        )
        r, c = ref["r"], ref["c"]
        def num(s):
            try:
                return float(s)          # data-value: the exact number (may be in e-notation)
            except ValueError:
                return float("".join(ch for ch in s.split(" ")[0] if ch in "0123456789.-"))
        assert num(shown["pipeline_mean"]) == pytest.approx(r["pipeline_mean"], abs=0.006)
        assert num(shown["availability"]) == pytest.approx(r["availability"], abs=0.0006)
        assert num(shown["ebo"]) == pytest.approx(r["ebo"], abs=0.0006)
        assert num(shown["expected_wait_days"]) == pytest.approx(r["expected_wait_days"], abs=0.006)
        assert num(shown["extra_spares_availability"]) == pytest.approx(c["extra_spares"]["availability"], abs=0.0006)
        assert num(shown["tat_cut_availability"]) == pytest.approx(c["tat_cut"]["availability"], abs=0.0006)
        assert num(shown["extra_spares_ebo"]) == pytest.approx(c["extra_spares"]["ebo"], abs=0.0006)
        assert num(shown["tat_cut_ebo"]) == pytest.approx(c["tat_cut"]["ebo"], abs=0.0006)
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

CHIPS_JS = """() => {
  const boxes = [...document.querySelectorAll('[data-story="rotable-lifecycle"] .rr-flow-chip rect')].map((r) => { const b = r.getBoundingClientRect(); return { x: b.x, y: b.y, width: b.width, height: b.height }; });
  const inter = (a, b) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
  let overlaps = 0;
  boxes.forEach((a, i) => boxes.slice(i + 1).forEach((b) => { if (inter(a, b)) overlaps += 1; }));
  const backColours = [...document.querySelectorAll('[data-story="rotable-lifecycle"] .rr-arc--back line, [data-story="rotable-lifecycle"] .rr-arc--back rect:not([fill="transparent"])')].map((p) => (p.getAttribute('stroke') || p.getAttribute('fill') || '').toLowerCase());
  return { n: boxes.length, overlaps, backColours };
}"""


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_wave2_design_fixes(site, viewport):
    """Design wave 2: lifecycle values in chips that do not overlap, no copper return flows,
    headlines <= 90 chars, <= 2 accents per chart, decision column visible on phones."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/rotables", viewport)
    try:
        flows = page.evaluate("""async () => { const r = await (await fetch('./data/rotables.json')).json();
          return (r.lifecycle?.flows || []).filter((f) => f.from !== f.to && +f.count).length; }""")
        chips = page.evaluate(CHIPS_JS)
        assert chips["n"] == flows
        assert chips["overlaps"] == 0
        assert chips["backColours"] and all(c != "#c47f52" for c in chips["backColours"])
        for f in page.evaluate(FRAME_JS):
            assert len(f["headline"]) <= 90, f["headline"]
            assert len(f["accents"]) <= 2, f
        assert page.locator(".rr-chase .rr-alert").count() >= 1
        assert page.locator('[data-lever="extra_spares"]').count() == 1
        if viewport == "390":
            assert page.locator(".data-table-stack .dts-metric-label", has_text="vs due").count() >= 1
            # calculator outputs come before the inputs on a phone
            out_y = page.locator(".fc-outs").bounding_box()["y"]
            in_y = page.locator(".fc-inputs").bounding_box()["y"]
            assert out_y < in_y
        assert not problems, problems
    finally:
        ctx.close()


TEAL = ("#22c7b8", "34, 199, 184", "34,199,184")


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_wave3_rotables(site, viewport):
    """Design wave 3: state ladder (one connector per row), chase list sorted by days late, no teal shop
    category, condemned is not red, thousands separators in the unit-cost input, slider aria-valuetext."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/rotables", viewport)
    try:
        res = page.evaluate("""() => {
          const lc = document.querySelector('[data-story="rotable-lifecycle"]');
          const rows = [...lc.querySelectorAll('.rr-arc')].map((g) => Math.round(g.getBoundingClientRect().top));
          const late = [...document.querySelectorAll('.rr-chase .rr-alert-late')].map((e) => parseFloat(e.textContent.replace(/[^0-9.]/g, '')));
          const condemned = [...lc.querySelectorAll('.rr-node.is-bad')].map((n) => getComputedStyle(n).stroke);
          const tat = [...document.querySelectorAll('[data-story="rotable-tat"] svg circle, [data-story="rotable-tat"] svg rect')].map((n) => `${n.getAttribute('fill')} ${n.getAttribute('stroke')}`.toLowerCase());
          const cost = document.querySelector('[data-input="cost"]').value;
          const vt = [...document.querySelectorAll('[data-range]')].map((r) => r.getAttribute('aria-valuetext'));
          return { rows, late, condemned, tat, cost, vt, rule: document.querySelector('.rr-chase-rule')?.textContent || '' };
        }""")
        assert len(res["rows"]) == len(set(res["rows"])), "two lifecycle connectors share a row"
        assert res["late"] == sorted(res["late"], reverse=True), res["late"]
        assert "days past" in res["rule"]
        assert all("231, 107, 100" not in s for s in res["condemned"]), res["condemned"]
        assert not [t for t in res["tat"] if "#22c7b8" in t], "teal used as a shop category"
        assert "," in res["cost"], res["cost"]
        assert res["vt"] and all(v for v in res["vt"])
        assert not problems, problems
    finally:
        ctx.close()



# ----------------------------------------------------------------------------- v2.1 (PAGE-2): A10 views, A7, A9, plain English
import json  # noqa: E402
import re  # noqa: E402

from _sitefx_c import DOCS  # noqa: E402

REPO = DOCS.parent


def _rot():
    return json.loads((DOCS / "data/rotables.json").read_text())


def _parts():
    return json.loads((DOCS / "data/parts.json").read_text())


def open_mode(browser, base, route, viewport, mode, patch=None):
    """open_route with the reading mode preset; patch(rotables_dict) rewrites rotables.json for this page."""
    w, h = VIEWPORTS[viewport]
    ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
    ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', '{mode}'); }} catch (e) {{}}")
    if patch is not None:
        data = _rot()
        patch(data)
        ctx.route("**/data/rotables.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(data)))
    page = ctx.new_page()
    problems: list[str] = []
    page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.goto(f"{base}/index.html{route}")
    page.wait_for_selector('html[data-ready="true"]', timeout=15000)
    page.wait_for_timeout(900)
    return ctx, page, problems


def _shown(page):
    return page.evaluate("() => Object.fromEntries([...document.querySelectorAll('[data-out]')].map((e) => [e.dataset.out, e.dataset.value ?? e.textContent.trim()]))")


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_modes_clean_intro_and_wording(site, mode, viewport):
    b, base = site
    ctx, page, problems = open_mode(b, base, "#/rotables?pn=GN-32-R014", viewport, mode)
    try:
        assert_clean(page, problems, f"{mode}@{viewport}")
        intro = page.locator('#view [data-role="intro3"]')
        assert intro.count() == 1 and intro.locator(".intro3-row").count() == 3
        txt = page.inner_text("#view")
        if mode == "simple":
            hits = [p for p in ["λT", "Poisson", "Palm", "METRIC", r"\bEBO\b", r"\bTAT\b(?!\))", r"\bP0\b", r"\bP2\b", r"\bI125\b", r"\bROs\b", r"\d RO\b", "U/S", r"\bBER\b"] if re.search(p, txt)]
            assert not hits, hits
            assert "chance the part is on the shelf" in txt.lower()
        else:
            assert "METRIC-inspired" in txt and "Palm" in txt
    finally:
        ctx.close()


def test_v21_a10_hub_and_outstation_views(site):
    b, base = site
    rot = _rot()
    modes = rot["calculator_modes"]
    ex = next(e for e in rot["float_examples"] if e["pn"] == "GN-32-R014")
    ctx, page, problems = open_mode(b, base, "#/rotables?pn=GN-32-R014", "1440", "expert")
    try:
        label = page.locator('[data-role="calc-mode-label"]')
        assert modes["hub"]["basis"] in label.inner_text() and label.get_attribute("data-mode") == "hub"
        assert page.locator('[data-role="calc-mode"] [data-mode="hub"]').get_attribute("aria-checked") == "true"
        assert page.locator('[data-role="outstation-disabled"]').is_hidden()
        hub = _shown(page)
        assert float(page.input_value('[data-input="tat"]')) == pytest.approx(round(ex["pipeline_days"]), abs=0.01)
        page.locator('[data-role="calc-mode"] [data-mode="outstation"]').click()
        page.wait_for_timeout(250)
        assert label.get_attribute("data-mode") == "outstation"
        assert modes["outstation"]["basis"] in label.inner_text()
        assert "view=outstation" in page.url
        for sv in ex["station_views"]:
            page.select_option("#fc-station", sv["station"])
            page.wait_for_timeout(200)
            assert sv["station"] in label.inner_text()
            assert float(page.input_value('[data-input="rate"]')) == pytest.approx(sv["rate_per_30d"], abs=1e-4)
            assert float(page.input_value('[data-input="tat"]')) == pytest.approx(sv["resupply_days"], abs=0.01)
            assert int(page.input_value('[data-input="spares"]')) == sv["units"]["P2"]
            shown = _shown(page)
            # same Palm formula as the exporter's station availability
            assert float(shown["availability"]) == pytest.approx(sv["availability"]["P2"], abs=0.0006), sv["station"]
            ref = page.evaluate("async (a) => (await import('./js/lib/floatcalc.js')).floatCalc(a[0], a[1], a[2], a[3]).availability", [sv["rate_per_30d"], sv["resupply_days"], sv["units"]["P2"], ex["unit_cost_aed"]])
            assert float(shown["availability"]) == pytest.approx(ref, abs=1e-6)
        assert float(shown["pipeline_mean"]) != pytest.approx(float(hub["pipeline_mean"]))
        page.locator('[data-role="calc-mode"] [data-mode="hub"]').click()
        page.wait_for_timeout(200)
        assert label.get_attribute("data-mode") == "hub"
        assert "view=outstation" not in page.url
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("case", ["missing_input", "mode_off"])
def test_v21_a10_outstation_disabled_when_inputs_missing(site, case):
    b, base = site

    def patch(d):
        if case == "mode_off":
            d["outstation_mode"] = "disabled"
        else:
            ex = next(e for e in d["float_examples"] if e["pn"] == "GN-32-R014")
            ex["station_views"][0].pop("resupply_days")

    ctx, page, problems = open_mode(b, base, "#/rotables?pn=GN-32-R014&view=outstation", "1440", "simple", patch=patch)
    try:
        btn = page.locator('[data-role="calc-mode"] [data-mode="outstation"]')
        assert btn.is_disabled()
        note = page.locator('[data-role="outstation-disabled"]')
        assert note.is_visible() and "outstation view is off" in note.inner_text().lower()
        assert page.locator('[data-role="calc-mode-label"]').get_attribute("data-mode") == "hub"
        assert page.locator("#fc-station").is_hidden()
        if case == "missing_input":
            # another part with complete inputs keeps the outstation view
            page.select_option("#fc-pn", "GN-34-R018")
            page.wait_for_timeout(200)
            assert not btn.is_disabled() and note.is_hidden()
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_a7_hero_and_a9_brake_flags(site):
    b, base = site
    P = _parts()
    hero = next(p for p in P["parts"] if p.get("escalation"))
    ctx, page, problems = open_mode(b, base, f"#/rotables?pn={hero['pn']}", "1440", "simple")
    try:
        t = page.locator('[data-story="rotable-float-calc"] [data-role="escalation-text"]')
        assert t.count() == 1 and t.inner_text().strip() == hero["escalation"]["text"]
        page.select_option("#fc-pn", "GN-34-R018")
        page.wait_for_timeout(200)
        assert page.locator('[data-role="escalation"]').count() == 0
        # A9: brake outstation units are kept and flagged in the outstation view
        page.select_option("#fc-pn", "GN-32-R013")
        page.wait_for_timeout(200)
        page.locator('[data-role="calc-mode"] [data-mode="outstation"]').click()
        page.wait_for_timeout(200)
        rot = next(e for e in _rot()["float_examples"] if e["pn"] == "GN-32-R013")
        for sv in [s for s in rot["station_views"] if s.get("invalid_recommendation")]:
            page.select_option("#fc-station", sv["station"])
            page.wait_for_timeout(150)
            box = page.locator('[data-out="station"]')
            assert P["invalid_allocation_text"] in box.locator('[data-role="invalid-allocations"]').inner_text(), sv["station"]
            assert int(page.input_value('[data-input="spares"]')) == sv["units"]["P2"]  # frozen units kept
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_readability_simple(site):
    b, base = site
    ctx, page, problems = open_mode(b, base, "#/rotables", "1440", "simple")
    try:
        r = page.evaluate("import('./js/lib/readability.js').then(R => R.readability())")
        out = REPO / "reports/readability/rotable-repair.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"view": "rotable-repair", "mode": "simple", "grade": r["grade"], "maxSentenceWords": r["maxSentenceWords"],
                                   "words": r["words"], "sentences": r["sentences"], "longSentences": r["longSentences"]}, indent=2, ensure_ascii=False) + "\n")
        assert r["grade"] <= 9, r
        assert r["maxSentenceWords"] <= 25, r["longest"]
    finally:
        ctx.close()
