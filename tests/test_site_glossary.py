"""Glossary (#/glossary): every glossaryEntries() item, grouped, searchable, ?term= deep link, linked from tooltips,
both reading modes, readable at 390 (v2.1, PAGE-3)."""
from __future__ import annotations

import pytest

from _sitefx import VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

ENTRIES_JS = "import('./js/lib/glossary.js').then((g) => ({ keys: g.glossaryEntries().map((e) => e.key), cats: g.GLOSSARY_CATEGORIES }))"


def set_mode(page, mode):
    page.evaluate(f"import('./js/lib/mode.js').then((m) => m.setMode('{mode}'))")
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=15000)
    page.wait_for_timeout(700)


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_glossary_lists_every_entry(site, browser, vp, mode):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/glossary", vp)
    try:
        if mode == "expert":
            set_mode(page, "expert")
        audit(page, problems, min_frames=0)
        g = page.evaluate(ENTRIES_JS)
        ids = page.eval_on_selector_all(".gl-entry", "els => els.map((e) => e.dataset.term)")
        assert sorted(ids) == sorted(g["keys"])
        # every entry carries a definition, an example and why it matters
        for sel in [".gl-def", ".gl-ex", ".gl-why"]:
            assert page.locator(f".gl-entry {sel}").count() == len(g["keys"]), sel
        groups = page.eval_on_selector_all(".gl-group-title", "els => els.map((e) => e.firstChild.textContent)")
        assert groups == [c for c in g["cats"] if c in groups] and len(groups) >= 6
        assert page.locator('[data-role="intro3"]').count() == 1
        first = page.locator('#g-tat .gl-term').inner_text()
        assert first.startswith("Repair time" if mode == "simple" else "TAT")
    finally:
        ctx.close()


def test_glossary_search_filters(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/glossary", "390")
    try:
        page.fill("#gl-search", "repair time")
        page.wait_for_timeout(150)
        visible = page.eval_on_selector_all(".gl-entry", "els => els.filter((e) => !e.hidden).map((e) => e.dataset.term)")
        assert "tat" in visible and len(visible) < 10
        assert "match" in page.locator("#gl-count").inner_text()
        assert "q=repair" in page.url
        page.fill("#gl-search", "zzzqqq")
        page.wait_for_timeout(150)
        assert page.locator(".gl-empty").is_visible()
        page.fill("#gl-search", "")
        page.wait_for_timeout(150)
        assert page.locator(".gl-entry:not([hidden])").count() == len(page.evaluate(ENTRIES_JS)["keys"])
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_glossary_term_param_highlights(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/glossary?term=fill_rate", vp)
    try:
        art = page.locator("#g-fill_rate")
        assert "is-target" in art.get_attribute("class")
        assert page.locator(".gl-entry.is-target").count() == 1
        box = art.bounding_box()
        assert box and 0 <= box["y"] < VIEWPORTS[vp][1], box
        # alias resolves too, and a same-route change re-highlights without a re-render
        page.evaluate("location.hash = '#/glossary?term=cannibalisation'")
        page.wait_for_timeout(500)
        assert "is-target" in page.locator("#g-robbery").get_attribute("class")
        assert page.locator(".gl-entry.is-target").count() == 1
        assert not problems, problems
    finally:
        ctx.close()


def test_tooltip_links_to_glossary(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/forecast", "1440")
    try:
        t = page.locator('.intro3 .term[data-term="forecast_methods"]').first
        t.click()
        link = page.locator(".term-pop.is-on .term-pop-link")
        assert link.get_attribute("href") == "#/glossary?term=forecast_methods"
        link.click()
        page.wait_for_function("document.documentElement.dataset.ready === 'true' && location.hash.startsWith('#/glossary')", timeout=15000)
        page.wait_for_timeout(600)
        assert "is-target" in page.locator("#g-forecast_methods").get_attribute("class")
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_glossary_readability_simple(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/glossary", vp)
    try:
        r = page.evaluate("import('./js/lib/readability.js').then((R) => R.readability())")
        assert r["grade"] <= 9, r
        assert r["maxSentenceWords"] <= 25, r["longSentences"]
    finally:
        ctx.close()
