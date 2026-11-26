"""Browser tests for Data & Method."""
from __future__ import annotations

import pytest

import json
import re

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser
METHOD = json.loads((DOCS / "data" / "method.json").read_text())


def _mode(page, mode):
    page.evaluate(f"import('./js/lib/mode.js').then(m => m.setMode('{mode}'))")
    page.wait_for_timeout(300)
    page.wait_for_function("document.documentElement.dataset.ready === 'true'")
    page.wait_for_timeout(900)


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
        # wave 3: no placeholder chip; LinkedIn appears only once a real URL exists
        assert "add link" not in text
        assert "Independent educational simulation" in text
        assert page.locator('[data-story="method-provenance"] svg .dm-box').count() == 6
    finally:
        ctx.close()


def test_assumption_register_filters(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", "1440")
    try:
        _mode(page, "expert")
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
        _mode(page, "expert")
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


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave3_no_raw_iso_tests_card_and_register_keys(site, browser, vp):  # noqa: F811
    """Review 2: no raw ISO timestamps, the pytest card is not a stretched empty column, register keys never truncate."""
    import re
    ctx, page, problems = open_page(browser, site + "#/method", vp)
    try:
        _mode(page, "expert")
        text = page.locator("#view").inner_text()
        # config values (e.g. calendar.epoch) are data; build timestamps outside the register must be humanised
        outside = page.evaluate("""() => { const v = document.querySelector('#view').cloneNode(true);
          v.querySelectorAll('[data-story="method-assumptions"]').forEach((e) => e.remove()); return v.innerText; }""")
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", outside), re.findall(r"\S*\d{4}-\d{2}-\d{2}T\S*", outside)[:3]
        assert "UTC" in text
        # tests card: little empty space below its content
        gap = page.evaluate("""() => { const c = document.querySelector('.dm-tests-card'); const last = c.querySelector('.dm-checks').getBoundingClientRect();
          return c.getBoundingClientRect().bottom - last.bottom; }""")
        assert gap < 80, gap
        if vp == "390":
            bad = page.evaluate("""() => [...document.querySelectorAll('.dm-wrap .dts-primary')].slice(0, 40)
              .filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.textContent)""")
            assert not bad, bad
        assert not problems, problems
    finally:
        ctx.close()


# ---- v2.1 (PAGE-5): plain-English Simple mode, verbatim A5/A6, AV2 table, next experiments, donor recount
@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_method_content(site, browser, vp, mode):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", vp)
    try:
        if mode == "expert":
            _mode(page, "expert")
        assert page.evaluate("document.body.classList.contains('mode-%s')" % mode)
        audit(page, problems, min_frames=2)
        assert page.locator('#view [data-role="intro3"]').count() == 1
        view = page.locator("#view")
        text = view.inner_text()
        # A5 verbatim, A6 verbatim + ranges note
        assert page.locator('[data-role="a5"]').inner_text().strip() == METHOD["calibration_note"]["text"]
        assert page.locator('[data-role="a6"]').inner_text().strip() == METHOD["stress_worlds"]["text"]
        assert METHOD["stress_worlds"]["ranges_note"] in text
        # AV2 status table: all 25 rows, statuses from method.json; closed in Simple, open in Expert
        xp = page.locator('[data-role="av2-table"]')
        assert xp.evaluate("e => e.open") == (mode == "expert")
        if mode == "simple":
            xp.locator("summary").click()
        tbl = xp.inner_text()
        for f in METHOD["av2_findings"]:
            assert f["id"] in tbl, f["id"]
        c = METHOD["av2_counts"]
        assert f"{c['fixed']} fixed" in text and f"{c['disclosed']} disclosed" in text
        # next experiments hosted here
        nx = page.locator('[data-role="next-experiments"] .dm-next-item')
        assert nx.count() == len(METHOD["next_experiments"])
        assert "proposed, not run" in page.locator('[data-role="next-experiments"]').inner_text().lower()
        # donor recount note is post-plan; frozen chain and superseded v1 present
        dr = page.locator('[data-role="donor-recount"]')
        assert dr.count() == 1 and page.locator('[data-role="postplan"]').count() >= 1
        assert page.locator('[data-role="holdout-chain"]').count() == 1
        assert page.locator('[data-role="superseded"]').count() == 1
        # wording
        low = text.lower()
        assert "verified" in low and "validated" not in low and "optimal" not in low
        if mode == "simple":
            assert not re.search(r"\b(P0|P1|P2|I125)\b", page.evaluate(
                "(() => { const v = document.querySelector('#view').cloneNode(true); v.querySelectorAll('.mono-tag,.expert-only,[data-readability=skip],details:not([open]),.table-wrap,.data-table-stack,svg').forEach(e => e.remove()); return v.innerText; })()")), "bare policy code in Simple prose"
            r = page.evaluate("import('./js/lib/readability.js').then(R => R.readability())")
            assert r["grade"] <= 9 and r["maxSentenceWords"] <= 25, r
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_next_section_deep_link(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method?section=next", "1440")
    try:
        top = page.evaluate("document.getElementById('next-experiments').getBoundingClientRect().top")
        assert -5 < top < 300, top
        assert not problems, problems
    finally:
        ctx.close()
