"""Section links on the page views (v2.2, PAGES): About, The Planner Behind the Project, Glossary, Data & Method.

Every in-page / section link that lives on these four pages, or points into them, must land on its target every time.

* test_section_links_repeat[browser-page]   for every section link on the page: 3 starting states (same page after
      scrolling away, arrived from another page through the rail, fresh load) x 5 repeated clicks. Same-route links
      are clicked 5 times in a row (scrolled back to the top between clicks, so each click has to move the page);
      cross-page links (Planner / Data & Method -> About) are re-entered from their page each time. After every
      click: the URL hash is the link's href, the target heading's top sits 0-200 px below the sticky bar(s), focus
      is on that heading, and on clicks 1 and 5 it is still there after the settle window. No skips.
* test_section_deep_links[browser]          every section target as a deep link: fresh load, hard refresh
      (page.reload) and from another page (hash change).
* test_section_back_forward[browser-family] Back / Forward once per link family (About same-route, About from
      another page, Planner -> About, Data & Method next, Glossary groups).
* test_section_modes_viewports[browser-mode-vp] Simple + Expert at 1440 and 390: every deep-link target plus one
      click per page.
Chromium + WebKit. Motion is NOT reduced (the entry animation runs, as for most readers).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_lib as AL  # noqa: E402

pytestmark = pytest.mark.browser
BROWSERS = ["chromium", "webkit"]
VPS = {"1440": (1440, 900), "390": (390, 844)}
BAND = (0, 200)

# heading checks: the target heading's top relative to the bottom of the sticky bar(s), focus and URL
STATE_JS = r"""(sel) => {
  const t = document.querySelector(sel);
  if (!t) return { found: false };
  let bar = 0;
  const tb = document.querySelector('.topbar');
  if (tb) bar = tb.getBoundingClientRect().bottom;
  document.querySelectorAll('.gl-tools').forEach((g) => {
    const r = g.getBoundingClientRect();
    if (getComputedStyle(g).position === 'sticky' && r.top <= bar + 1 && r.bottom > bar) bar = r.bottom;
  });
  const a = document.activeElement;
  return { found: true, rel: Math.round(t.getBoundingClientRect().top - bar), focus: a === t, active: a ? (a.id || a.tagName) : null,
           hash: decodeURIComponent(location.hash), ready: document.documentElement.dataset.ready === 'true' };
}"""
OK_JS = "([sel, hash, lo, hi]) => { const s = (" + STATE_JS + ")(sel); return s.found && s.ready && s.focus && s.hash === hash && s.rel >= lo && s.rel <= hi; }"

ABOUT_T = {"mro": "#ab-mro-h", "real-data": "#ab-real-data-h", "next-experiments": "#ab-next-experiments-h"}


def _links(page_id: str, page) -> list[dict]:
    """Section links on a page: {sel, href, target (heading selector)}. Glossary chips are read from the page."""
    if page_id == "about":
        out = [{"sel": f'.ab-jump a[href="#/about?section={s}"]', "href": f"#/about?section={s}", "target": t} for s, t in ABOUT_T.items()]
        for src, dst in [("mro", "real-data"), ("mro", "next-experiments"), ("real-data", "next-experiments"), ("next-experiments", "mro"), ("next-experiments", "real-data")]:
            out.append({"sel": f'#ab-{src} .ab-md a[href="#/about?section={dst}"]', "href": f"#/about?section={dst}", "target": ABOUT_T[dst]})
        return out
    if page_id == "planner":
        return [{"sel": '.pl-next a[href="#/about?section=real-data"]', "href": "#/about?section=real-data", "target": ABOUT_T["real-data"]}]
    if page_id == "method":
        return [{"sel": '#next-experiments .dm-next-body a[href="#/about?section=mro"]', "href": "#/about?section=mro", "target": ABOUT_T["mro"]},
                {"sel": '#next-experiments [data-role="next-back"] a[href="#/about?section=real-data"]', "href": "#/about?section=real-data", "target": ABOUT_T["real-data"]}]
    if page_id == "glossary":
        chips = page.evaluate("[...document.querySelectorAll('.gl-jump')].map((a) => [a.getAttribute('href'), a.dataset.cat])")
        assert len(chips) >= 5, chips
        out = []
        for href, cat in chips:
            key = href.split("section=")[1]
            out.append({"sel": f'.gl-jump[href="{href}"]', "href": href, "target": f"#gl-cat-{re.sub('[^a-z]+', '-', cat.lower())}-h", "key": key})
        return out
    raise ValueError(page_id)


@pytest.fixture(scope="module")
def site():
    with AL.serve_docs() as index:
        yield index


@pytest.fixture(scope="module")
def pw():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        yield p


_BROWSERS: dict = {}


@pytest.fixture(scope="module")
def browsers(pw):
    yield _BROWSERS
    for b in _BROWSERS.values():
        b.close()
    _BROWSERS.clear()


def _new(pw, browsers, name, vp="1440", mode="simple"):
    if name not in browsers:
        browsers[name] = getattr(pw, name).launch()
    w, h = VPS[vp]
    ctx = browsers[name].new_context(viewport={"width": w, "height": h}, reduced_motion="no-preference")
    ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', '{mode}') }} catch (e) {{}}")
    page = ctx.new_page()
    errs: list[str] = []
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    page.on("console", lambda m: errs.append(f"console.error: {m.text}") if m.type == "error" else None)
    return ctx, page, errs


def _ready(page):
    page.wait_for_function("document.documentElement.dataset.ready === 'true' && !document.querySelector('#view [aria-busy=true]') && document.getElementById('view').style.visibility !== 'hidden'", timeout=15000)


def _goto(page, site, route):
    page.goto("about:blank")
    page.goto(f"{site}#/{route}")
    _ready(page)
    page.wait_for_timeout(250)


def _route(page, route):
    """Arrive from another page: a hash change, as an in-site link does."""
    page.evaluate(f"location.hash = '#/{route}'")
    page.wait_for_function(f"location.hash.startsWith('#/{route.split('?')[0]}')")
    _ready(page)


def _expect(page, target, href, label, problems, stable=False):
    try:
        page.wait_for_function(OK_JS, arg=[target, href, BAND[0], BAND[1]], timeout=4000)
        if stable:
            page.wait_for_timeout(1000)   # past the settle window: still in place
            st = page.evaluate(STATE_JS, target)
            if not (st["focus"] and BAND[0] <= st["rel"] <= BAND[1] and st["hash"] == href):
                problems.append(f"{label}: drifted after settle {st}")
    except Exception:  # noqa: BLE001
        problems.append(f"{label}: {page.evaluate(STATE_JS, target)} (want hash {href}, top {BAND[0]}-{BAND[1]} px below the bar, focus on {target})")


def _click(page, sel):
    loc = page.locator(sel).first
    loc.scroll_into_view_if_needed()
    loc.click()


# ---------------------------------------------------------------------------------------- repeated clicks


@pytest.mark.parametrize("page_id", ["about", "planner", "method", "glossary"])
@pytest.mark.parametrize("bname", BROWSERS)
def test_section_links_repeat(site, pw, browsers, bname, page_id):
    ctx, page, errs = _new(pw, browsers, bname)
    problems: list[str] = []
    clicks = 0
    try:
        _goto(page, site, page_id)
        links = _links(page_id, page)
        for link in links:
            same_route = link["href"].startswith(f"#/{page_id}")
            for state in ("same", "other", "fresh"):
                if state == "fresh":
                    _goto(page, site, page_id)
                elif state == "other":
                    _goto(page, site, "mission")
                    page.locator(f'#nav .nav-item[data-route="{page_id}"]').click()
                    page.wait_for_function(f"location.hash === '#/{page_id}'")
                    _ready(page)
                else:
                    if not page.url.endswith(f"#/{page_id}") and not same_route:
                        _route(page, page_id)
                    if same_route:   # same page: land somewhere else on it first (the bottom)
                        page.evaluate("window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })")
                        page.wait_for_timeout(100)
                    else:
                        _ready(page)
                for i in range(5):
                    if i and same_route:
                        page.evaluate("document.activeElement && document.activeElement.blur(); window.scrollTo({ top: 0, behavior: 'instant' })")
                        page.wait_for_timeout(60)
                    if i and not same_route:
                        _route(page, page_id)
                    _click(page, link["sel"])
                    clicks += 1
                    _expect(page, link["target"], link["href"], f"{bname} {page_id} [{state} #{i + 1}] {link['sel']}", problems, stable=i in (0, 4))
        assert clicks == len(links) * 15
        assert not errs, errs[:5]
        assert not problems, f"{len(problems)} of {clicks} clicks failed:\n" + "\n".join(problems[:25])
    finally:
        ctx.close()


# ---------------------------------------------------------------------------------------- deep links

DEEP = [("about?section=mro", ABOUT_T["mro"]), ("about?section=real-data", ABOUT_T["real-data"]),
        ("about?section=next-experiments", ABOUT_T["next-experiments"]), ("method?section=next", "#next-experiments .section-title h2")]


def _deep_targets(page, site):
    _goto(page, site, "glossary")
    out = list(DEEP)
    for link in _links("glossary", page):
        out.append((link["href"][2:], link["target"]))
    key = page.evaluate("document.querySelector('.gl-entry').dataset.term")
    out.append((f"glossary?term={key}", f"#g-{key}"))
    return out


@pytest.mark.parametrize("bname", BROWSERS)
def test_section_deep_links(site, pw, browsers, bname):
    ctx, page, errs = _new(pw, browsers, bname)
    problems: list[str] = []
    try:
        for route, target in _deep_targets(page, site):
            href = f"#/{route}"
            _goto(page, site, route)
            _expect(page, target, href, f"{bname} {route} [fresh load]", problems, stable=True)
            page.reload()
            _ready(page)
            _expect(page, target, href, f"{bname} {route} [hard refresh]", problems, stable=True)
            _goto(page, site, "mission")
            _route(page, route)
            _expect(page, target, href, f"{bname} {route} [from another page]", problems, stable=True)
        assert not errs, errs[:5]
        assert not problems, "\n".join(problems)
    finally:
        ctx.close()


# ---------------------------------------------------------------------------------------- Back / Forward


@pytest.mark.parametrize("family", ["about-same", "about-cross", "planner", "method", "glossary"])
@pytest.mark.parametrize("bname", BROWSERS)
def test_section_back_forward(site, pw, browsers, bname, family):
    ctx, page, errs = _new(pw, browsers, bname)
    problems: list[str] = []
    lab = f"{bname} {family}"
    try:
        if family == "about-same":
            _goto(page, site, "about")
            _click(page, '.ab-jump a[href="#/about?section=mro"]')
            _expect(page, ABOUT_T["mro"], "#/about?section=mro", f"{lab} click mro", problems)
            _click(page, '#ab-mro .ab-md a[href="#/about?section=real-data"]')
            _expect(page, ABOUT_T["real-data"], "#/about?section=real-data", f"{lab} click real-data", problems)
            page.go_back()
            _expect(page, ABOUT_T["mro"], "#/about?section=mro", f"{lab} Back", problems, stable=True)
            page.go_forward()
            _expect(page, ABOUT_T["real-data"], "#/about?section=real-data", f"{lab} Forward", problems, stable=True)
        elif family == "about-cross":
            _goto(page, site, "about?section=next-experiments")
            _expect(page, ABOUT_T["next-experiments"], "#/about?section=next-experiments", f"{lab} load", problems)
            page.locator('#nav .nav-item[data-route="mission"]').click()
            page.wait_for_function("location.hash === '#/mission'")
            _ready(page)
            page.go_back()
            _ready(page)
            _expect(page, ABOUT_T["next-experiments"], "#/about?section=next-experiments", f"{lab} Back", problems, stable=True)
            page.go_forward()
            page.wait_for_function("location.hash === '#/mission'")
            page.go_back()
            _ready(page)
            _expect(page, ABOUT_T["next-experiments"], "#/about?section=next-experiments", f"{lab} Back again", problems, stable=True)
        elif family in ("planner", "method"):
            link = _links(family, None)[0] if family == "planner" else None
            if family == "method":
                _goto(page, site, "method")
                link = _links("method", page)[0]
            else:
                _goto(page, site, "planner")
            _click(page, link["sel"])
            _expect(page, link["target"], link["href"], f"{lab} click", problems)
            page.go_back()
            page.wait_for_function(f"location.hash === '#/{family}'")
            _ready(page)
            page.go_forward()
            _ready(page)
            _expect(page, link["target"], link["href"], f"{lab} Forward", problems, stable=True)
            if family == "method":   # and the page's own deep link survives Back
                _goto(page, site, "method?section=next")
                _route(page, "mission")
                page.go_back()
                _ready(page)
                _expect(page, "#next-experiments .section-title h2", "#/method?section=next", f"{lab} Back to next", problems, stable=True)
        else:
            _goto(page, site, "glossary")
            a, b = _links("glossary", page)[1:3]
            _click(page, a["sel"])
            _expect(page, a["target"], a["href"], f"{lab} click A", problems)
            _click(page, b["sel"])
            _expect(page, b["target"], b["href"], f"{lab} click B", problems)
            page.go_back()
            _expect(page, a["target"], a["href"], f"{lab} Back", problems, stable=True)
            page.go_forward()
            _expect(page, b["target"], b["href"], f"{lab} Forward", problems, stable=True)
        assert not errs, errs[:5]
        assert not problems, "\n".join(problems)
    finally:
        ctx.close()


# ---------------------------------------------------------------------------------------- modes x viewports


@pytest.mark.parametrize("vp", list(VPS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
@pytest.mark.parametrize("bname", BROWSERS)
def test_section_modes_viewports(site, pw, browsers, bname, mode, vp):
    ctx, page, errs = _new(pw, browsers, bname, vp=vp, mode=mode)
    problems: list[str] = []
    lab = f"{bname} {mode} {vp}"
    try:
        for route, target in _deep_targets(page, site):
            _goto(page, site, route)
            _expect(page, target, f"#/{route}", f"{lab} {route} [load]", problems, stable=route.startswith("about"))
        for page_id in ("about", "planner", "method", "glossary"):
            _goto(page, site, page_id)
            links = _links(page_id, page)
            link = links[-1]
            for i in range(2):   # first click and a repeat (same route) / re-entry (cross page)
                if i and not link["href"].startswith(f"#/{page_id}"):
                    _route(page, page_id)
                elif i:
                    page.evaluate("window.scrollTo({ top: 0, behavior: 'instant' })")
                _click(page, link["sel"])
                _expect(page, link["target"], link["href"], f"{lab} {page_id} click {i + 1} {link['sel']}", problems)
        assert not errs, errs[:5]
        assert not problems, "\n".join(problems)
    finally:
        ctx.close()
