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
        assert "METRIC-inspired" in page.inner_text("#view")
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
