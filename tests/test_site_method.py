"""Browser tests for Data & Method."""
from __future__ import annotations

import pytest

from _sitefx import VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_method_renders_clean(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", vp)
    try:
        audit(page, problems, min_frames=2)
        for hook in ["method-provenance", "method-assumptions", "method-validation"]:
            assert page.locator(f'[data-story="{hook}"]').count() == 1, hook
        text = page.locator("#view").inner_text()
        assert "Akash Gajjar" in text and "University of Liverpool" in text
        assert page.locator('a[href="https://github.com/akashgajjar07-hue"]').count() == 1
        assert "LinkedIn: add link" in text
        assert "Independent educational simulation" in text
        assert page.locator('[data-story="method-provenance"] svg .dm-box').count() == 6
    finally:
        ctx.close()


def test_assumption_register_filters(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", "1440")
    try:
        showing = page.locator(".dm-showing")
        total = int(showing.inner_text().split(" of ")[1].replace(",", ""))
        assert total > 0
        page.locator('.dm-filters .seg button[data-value="REAL"]').click()
        n_real = int(showing.inner_text().split()[1].replace(",", ""))
        assert 0 < n_real < total
        rows = page.locator('[data-story="method-assumptions"] tbody tr')
        assert rows.count() == n_real
        page.locator('.dm-filters .seg button[data-value="ALL"]').click()
        page.fill(".dm-search[type=search]", "zzzz-no-such-key")
        assert showing.inner_text().startswith("Showing 0 of")
        assert not problems, problems
    finally:
        ctx.close()


def test_forced_rerun_disclosed_when_present(site, browser):  # noqa: F811
    import json
    from _sitefx import DOCS
    files = json.loads((DOCS / "data/manifest.json").read_text()).get("files", [])
    m = json.loads((DOCS / ("data/method.json" if "method" in files else "data/fixtures/method.json")).read_text())
    log = (m.get("freeze") or {}).get("holdout_log") or m.get("holdout_log") or []
    ctx, page, problems = open_page(browser, site + "#/method", "1440")
    try:
        if any(r.get("forced") for r in log):
            assert page.locator(".dm-callout").count() == 1
            assert page.locator(".dm-log-item.is-forced").count() == sum(1 for r in log if r.get("forced"))
        assert page.locator(".dm-log-item").count() == len(log)
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave2_validation_no_clamping(site, browser, vp):  # noqa: F811
    """Critic #7: every selection diamond lies inside the plot (shared % axis), headlines <= 90, ✓/✕ column is named."""
    ctx, page, problems = open_page(browser, site + "#/method", vp)
    try:
        page.wait_for_selector('[data-story="method-validation"] svg path')
        res = page.evaluate("""() => {
          const frames = [...document.querySelectorAll('#view figure.chart-frame')];
          const con = frames.find((f) => /selection-seed/.test(f.querySelector('.chart-headline')?.textContent || ''));
          const svg = con.querySelector('svg'); const sb = svg.getBoundingClientRect();
          const dia = [...svg.querySelectorAll('path')].filter((p) => p.getAttribute('transform')).map((p) => p.getBoundingClientRect());
          return { n: dia.length, inside: dia.every((r) => r.left >= sb.left + 1 && r.right <= sb.right - 1),
                   header: /IN CI/.test(svg.textContent), heads: frames.map((f) => f.querySelector('.chart-headline').textContent.trim()) };
        }""")
        assert res["n"] >= 1 and res["inside"], res
        assert res["header"], res
        assert all(len(t) <= 90 for t in res["heads"]), res["heads"]
        # assumption register prints a repeated rationale once
        if vp == "1440":
            assert page.locator('[data-story="method-assumptions"] .dm-same').count() >= 1
        assert not [p for p in problems if "pageerror" in p], problems
    finally:
        ctx.close()
