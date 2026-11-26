"""Router / overlay lifecycle tests (design-fix-shared, review issue #1).

A drawer opened by a deep link (#/parts?ata=32&pn=GN-32-R014) must never survive a route change:
in-app navigation, location.hash, Back/Forward or a query change that re-renders. No scrim may be
left intercepting clicks, and scroll locks / focus traps must be released.
"""
from __future__ import annotations

import pytest

from _sitefx import browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

DEEP = "#/parts?ata=32&pn=GN-32-R014"

STATE_JS = """() => ({
  scrims: document.querySelectorAll('.scrim').length,
  openScrims: document.querySelectorAll('.scrim.is-open').length,
  drawers: document.querySelectorAll('.drawer').length,
  openDrawers: document.querySelectorAll('.drawer.is-open').length,
  modals: document.querySelectorAll('.modal').length,
  tooltipOn: !!document.querySelector('.tooltip.is-on'),
  locked: document.documentElement.classList.contains('has-overlay'),
  route: location.hash,
})"""


def _settle(page):
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=15000)
    page.wait_for_timeout(700)


def _go(page, hash_):
    page.evaluate("(h) => { location.hash = h; }", hash_)
    page.wait_for_function("(h) => location.hash === h", arg=hash_)
    _settle(page)


def _assert_clear(page):
    st = page.evaluate(STATE_JS)
    assert st["scrims"] == 0 and st["drawers"] == 0 and st["modals"] == 0, st
    assert not st["tooltipOn"], st
    assert not st["locked"], st
    # nothing sits on top of the page centre (a leftover scrim would)
    top = page.evaluate("() => { const e = document.elementFromPoint(innerWidth / 2, innerHeight / 2); return e ? (e.closest('.scrim, .drawer, .modal') ? 'overlay' : 'page') : 'none'; }")
    assert top == "page", st


def _assert_drawer_open(page, n=1):
    page.wait_for_selector(".drawer.is-open", timeout=5000)
    page.wait_for_timeout(400)
    st = page.evaluate(STATE_JS)
    assert st["openDrawers"] == n and st["drawers"] == n and st["scrims"] == n, st
    assert st["locked"], st
    return st


@pytest.mark.parametrize("vp", ["1440", "390"])
def test_deep_link_drawer_closes_on_every_route_change(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + DEEP, vp)
    try:
        _assert_drawer_open(page)
        for route in ["#/forecast", "#/rotables", "#/mission"]:
            _go(page, route)
            _assert_clear(page)
        # "Start the story" must be clickable (no scrim intercepting pointer events)
        page.locator('[data-story="mission-start"]').click(timeout=3000)
        page.wait_for_selector(".story .story-card", timeout=5000)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        assert page.locator(".story").count() == 0
        # number-key shortcuts are no longer swallowed
        page.keyboard.press("3")
        page.wait_for_function("location.hash.startsWith('#/forecast')")
        assert not problems, problems
    finally:
        ctx.close()


def test_back_forward_and_in_drawer_links(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        _go(page, DEEP)
        _assert_drawer_open(page)
        # a link inside the drawer (hash change that bypasses drawer.close) closes it
        page.locator(".drawer.is-open .drawer-foot a", has_text="Forecast").click()
        _settle(page)
        assert page.evaluate("location.hash").startswith("#/forecast")
        _assert_clear(page)
        # the stale drawer's onClose must not rewrite the new route's URL (pn survives on forecast)
        assert "pn=GN-32-R014" in page.evaluate("location.hash")
        # Back: returns to the deep link, which re-opens exactly one drawer
        page.go_back()
        _settle(page)
        assert page.evaluate("location.hash").startswith("#/parts")
        _assert_drawer_open(page)
        # Forward: drawer closes again
        page.go_forward()
        _settle(page)
        _assert_clear(page)
        # Back to mission (two steps) – clear as well
        page.go_back()
        _settle(page)
        page.go_back()
        _settle(page)
        assert page.evaluate("location.hash").startswith("#/mission")
        _assert_clear(page)
        assert not problems, problems
    finally:
        ctx.close()


def test_same_route_param_updates_keep_one_drawer(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + DEEP, "1440")
    try:
        _assert_drawer_open(page)
        # replaceState-style deep-link updates (ctx.setParams) do not re-render: drawer stays open
        page.evaluate("history.replaceState(null, '', location.hash + '&q=brake')")
        page.wait_for_timeout(400)
        _assert_drawer_open(page)
        # a query change that re-renders the same route keeps the drawer (it is in the URL) – never two
        _go(page, "#/parts?ata=32&pn=GN-32-R014&cls=R")
        _assert_drawer_open(page)
        # removing pn from the query closes it
        _go(page, "#/parts?ata=32")
        _assert_clear(page)
        # user close (Esc) releases the scroll lock and strips pn from the URL
        _go(page, DEEP)
        _assert_drawer_open(page)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        _assert_clear(page)
        assert "pn=" not in page.evaluate("location.hash")
        assert not problems, problems
    finally:
        ctx.close()


def test_modal_and_tooltip_close_on_route_change(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        page.keyboard.press("?")
        page.wait_for_selector(".modal .modal-card")
        assert page.evaluate("document.documentElement.classList.contains('has-overlay')")
        _go(page, "#/capital")
        _assert_clear(page)
        assert not problems, problems
    finally:
        ctx.close()
