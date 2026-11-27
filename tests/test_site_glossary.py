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


# ----------------------------------------------------------------------------- v2.1 addendum: keyboard walk
KB_TARGETS_JS = r"""() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !e.closest('[hidden], details:not([open]) > :not(summary), [inert]'); };
  const sel = 'a[href], button:not([disabled]), input:not([type=hidden]):not([disabled]), select, textarea, summary, [tabindex]:not([tabindex="-1"])';
  return [...document.querySelectorAll('#view ' + sel.split(', ').join(', #view '))].filter(vis).filter((e) => e.tabIndex >= 0).length;
}"""
KB_STEP_JS = r"""() => {
  const a = document.activeElement;
  if (!a || a === document.body) return { where: 'body' };
  const inView = !!a.closest('#view');
  if (!window.__kbSeen) window.__kbSeen = [];
  let order = 'ok';
  const last = window.__kbSeen.at(-1);
  if (inView && last && last.isConnected && (last.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_PRECEDING)) order = 'back';
  if (inView) window.__kbSeen.push(a);
  const cs = getComputedStyle(a);
  const ring = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== 'none' || a.matches('g, svg *');
  return { where: inView ? 'view' : 'shell', order, ring, tag: a.tagName, label: (a.getAttribute('aria-label') || a.textContent || '').trim().slice(0, 40) };
}"""


def keyboard_walk(page, max_tabs=400):
    """Tab from the top through the whole page: focus never lost to <body> after entering the view, view controls
    visited in document order, every visible view control reached, focus ring visible, and the walk leaves the view
    (no trap). Returns (visited_in_view, expected)."""
    expected = page.evaluate(KB_TARGETS_JS)
    page.evaluate("window.__kbSeen = []; document.activeElement?.blur(); window.scrollTo(0, 0)")
    seen_view, left_after_view, problems = 0, False, []
    for _ in range(max_tabs):
        page.keyboard.press("Tab")
        st = page.evaluate(KB_STEP_JS)
        if st["where"] == "view":
            seen_view += 1
            if st["order"] == "back":
                problems.append(f"focus moved backwards to {st['tag']} {st['label']}")
            if not st["ring"]:
                problems.append(f"no visible focus ring on {st['tag']} {st['label']}")
        elif seen_view and st["where"] in ("shell", "body"):
            left_after_view = True
            break
    unique = page.evaluate("new Set(window.__kbSeen).size")
    assert left_after_view, "keyboard focus trapped inside the view"
    assert not problems, problems[:5]
    assert unique >= expected, f"Tab reached {unique} of {expected} view controls"
    return unique, expected


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_glossary_keyboard(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/glossary", vp)
    try:
        keyboard_walk(page)
        chip = page.locator('.gl-jump[data-cat="Repair"]')
        chip.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        assert chip.get_attribute("aria-current") == "true"
        assert page.evaluate("document.activeElement.classList.contains('gl-group-title')")
        # v2.2: the group chips are deep links (the URL updates; Back / reload return to the group)
        assert page.evaluate("location.hash") == "#/glossary?section=repair"
        page.locator("#gl-search").focus()
        page.keyboard.type("tat")
        page.keyboard.press("Escape")
        assert page.locator("#gl-search").input_value() == ""
        assert not problems, problems
    finally:
        ctx.close()
