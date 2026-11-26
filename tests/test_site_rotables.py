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
            """() => Object.fromEntries([...document.querySelectorAll('[data-out]')].map((e) => [e.dataset.out, e.textContent.trim()]))"""
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
        num = lambda s: float("".join(ch for ch in s.split(" ")[0] if ch in "0123456789.-"))  # noqa: E731
        assert num(shown["pipeline_mean"]) == pytest.approx(r["pipeline_mean"], abs=0.006)
        assert num(shown["availability"]) / 100 == pytest.approx(r["availability"], abs=0.0006)
        assert num(shown["ebo"]) == pytest.approx(r["ebo"], abs=0.0006)
        assert num(shown["expected_wait_days"]) == pytest.approx(r["expected_wait_days"], abs=0.006)
        assert num(shown["extra_spares_availability"]) / 100 == pytest.approx(c["extra_spares"]["availability"], abs=0.0006)
        assert num(shown["tat_cut_availability"]) / 100 == pytest.approx(c["tat_cut"]["availability"], abs=0.0006)
        assert num(shown["extra_spares_ebo"]) == pytest.approx(c["extra_spares"]["ebo"], abs=0.0006)
        assert num(shown["tat_cut_ebo"]) == pytest.approx(c["tat_cut"]["ebo"], abs=0.0006)
        assert not problems, problems
    finally:
        ctx.close()
