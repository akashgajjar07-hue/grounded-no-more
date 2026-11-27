"""Every internal link works every time (v2.2 router contract, docs/js/app.js header).

For every route (one test per route x browser, so pytest-xdist shards by route):
  * discover EVERY internal link on the page as it loads: `a[href^="#/"]` (shell rail, brand, view links) plus
    in-page anchors (`a[href^="#"]` that are not routes, e.g. the skip link; the glossary group chips are ?section= links);
  * for each link, 3 starting states x 5 repeated clicks:
      fresh  - a cold document load of the source route, then the clicks;
      other  - a cold load of a different route, an in-app hop (hash change) to the source route, then the clicks;
      same   - the browser already shows the link's target URL: for a link to its own route the hash is set to the
               link's href first (so every click is a click on the current URL); for a link to another route the
               target is visited first and the source route reached again with Back;
    between clicks that left the source route the test returns with browser Back (so Back is exercised every time);
  * after every click: the URL equals the link's href (an in-page anchor keeps the route URL), the target route
    rendered (nav item current, data-ready, no error state, a finished render was counted), and for section links
    (`?section=` or an in-page anchor) the target heading is in the viewport and has focus.
There is NO skip allowance: a link to the current route must scroll / focus like any other.

Run:  pytest -m browser tests/e2e/test_links_every_time.py -n 8 -p no:cacheprovider -o addopts=""
      GNM_LINK_BROWSERS=chromium GNM_LINK_ROUTES=mission,about ...   (subset)
Per-shard JSON: reports/audit/links_every_time/<browser>_<route>.json; reports/LINK_CHECK.md (internal part) is rebuilt
from all shard files after every shard.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import audit_lib as AL  # noqa: E402

pytestmark = pytest.mark.browser

ROUTES = ["mission", "parts", "forecast", "rotables", "network", "capital", "aog", "actions", "method", "about", "glossary", "planner"]
OUT = ROOT / "reports" / "audit" / "links_every_time"
LINK_MD = ROOT / "reports" / "LINK_CHECK.md"
STATES = ("fresh", "other", "same")
REPEATS = 5


def _env(name, default):
    v = os.environ.get(name)
    return [x.strip() for x in v.split(",") if x.strip()] if v else default


BROWSERS = _env("GNM_LINK_BROWSERS", ["chromium", "webkit"])
SEL_ROUTES = _env("GNM_LINK_ROUTES", ROUTES)

DISCOVER = r"""() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return (r.width > 0 && r.height > 0 && cs.visibility !== 'hidden') || e.classList.contains('skip-link'); };
  const seen = new Set(), out = [];
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    if (!vis(a) || a.closest('.sr-only, [hidden]')) return;
    const href = a.getAttribute('href');
    const label = (a.getAttribute('aria-label') || a.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60);
    const zone = a.closest('#view') ? 'view' : 'shell';
    const key = href + '|' + zone + '|' + label;
    if (seen.has(key)) return; seen.add(key);
    const same = [...document.querySelectorAll('a[href^="#"]')].filter((b) => b.getAttribute('href') === href && (b.closest('#view') ? 'view' : 'shell') === zone);
    out.push({ href, label, zone, nth: same.indexOf(a) });
  });
  return out;
}"""

# state after a click: route rendered + (for a section) target in view and focused
CHECK = r"""([section, anchor]) => {
  const h = location.hash, raw = h.replace(/^#\/?/, '').split('?')[0];
  const cur = document.querySelector('.nav-item[aria-current="page"]');
  const view = document.getElementById('view');
  const res = { hash: h, route: raw, navCurrent: cur ? cur.dataset.route : null, ready: document.documentElement.dataset.ready === 'true',
    error: !!view.querySelector('.state--error, [data-state="error"]'), empty: !view.textContent.trim(), renders: window.__gnmRenderCount ? window.__gnmRenderCount() : -1 };
  let t = null;
  if (section) t = window.__gnmSectionTarget ? window.__gnmSectionTarget(section) : null;
  if (anchor) t = document.getElementById(anchor);
  // a view that owns its sections (contract §3) may name the target differently: accept the focused element when it,
  // or an ancestor, carries an id that names the section (ab-mro-h, gl-cat-parts, next-experiments, ...)
  if (section) {
    const a = document.activeElement, key = String(section).toLowerCase();
    if (a && a !== document.body && (!t || !t.contains(a))) {
      for (let n = a; n && n !== view; n = n.parentElement) {
        if (n.id && n.id.toLowerCase().split(/[^a-z0-9]+/).join('-').includes(key)) { t = n; break; }
      }
    }
  }
  if (section || anchor) {
    res.target = !!t;
    if (t) {
      const r = t.getBoundingClientRect(), vh = innerHeight;
      const a = document.activeElement;
      const heading = (t.matches('h1,h2,h3,h4,[role=heading]') ? t : t.querySelector('h1,h2,h3,h4,[role=heading]')) || t;
      const hr = heading.getBoundingClientRect();
      res.inView = hr.bottom > 0 && hr.top < vh && r.top < vh;
      // scrolled to the top unless the page cannot scroll that far
      const maxY = document.documentElement.scrollHeight - vh;
      res.atTop = r.top < vh * 0.45 || scrollY >= maxY - 2;
      res.focused = !!a && (a === t || t.contains(a)) && (a === heading || a === t || a.matches('h1,h2,h3,h4,[role=heading]'));
      res.active = a ? (a.id || a.tagName) : null;
    }
  }
  return res;
}"""


def _ready(page, timeout=20000):
    page.wait_for_function("document.documentElement.dataset.ready === 'true' && !!window.__gnmRenderCount", timeout=timeout)


def _cold(page, base, hash_):
    page.goto("about:blank")
    page.goto(base + hash_)
    _ready(page)
    page.evaluate("window.__gnmRendered()")


def _hop(page, hash_):
    n = page.evaluate("window.__gnmRenderCount()")
    page.evaluate(f"location.hash = {json.dumps(hash_)}")
    page.wait_for_function(f"window.__gnmRenderCount() > {n}", timeout=15000)
    page.evaluate("window.__gnmRendered()")


def _back(page):
    n = page.evaluate("window.__gnmRenderCount()")
    page.go_back(wait_until="commit")
    page.wait_for_function(f"window.__gnmRenderCount() > {n}", timeout=15000)
    page.evaluate("window.__gnmRendered()")


def _params(h: str) -> dict:
    q = h.split("?", 1)[1] if "?" in h else ""
    return dict(parse_qsl(q))


def _route_of(h: str) -> str:
    p = h.lstrip("#").lstrip("/").split("?")[0]
    return p if p in ROUTES else "mission"


def _same_url(a: str, b: str) -> bool:
    return _route_of(a) == _route_of(b) and a.lstrip("#").lstrip("/").split("?")[0] == b.lstrip("#").lstrip("/").split("?")[0] and _params(a) == _params(b)


def _locate(page, link):
    zone = "#view " if link["zone"] == "view" else ""
    sel = f'{zone}a[href="{link["href"]}"]'
    loc = page.locator(sel)
    if link["zone"] == "shell":
        loc = page.locator(f'a[href="{link["href"]}"]:not(#view a)')
    return loc.nth(link["nth"]) if loc.count() > link["nth"] else loc.first


def _click_once(page, link, src_hash):
    """Click the link once (from the source page) and return (problems, info)."""
    href = link["href"]
    is_route = href.startswith("#/")
    anchor = None if is_route else href[1:]
    section = _params(href).get("section") if is_route else None
    # make the check meaningful: nothing focused, page scrolled away from the target
    page.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
    loc = _locate(page, link)
    if loc.count() == 0:
        return [f"link not found on {src_hash}"], {}
    n0 = page.evaluate("window.__gnmRenderCount()")
    changes = is_route and not _same_url(href, src_hash)     # a click on the current URL fires no hashchange
    if link["href"] == "#view" or "skip-link" in (loc.get_attribute("class") or ""):
        loc.focus()
        page.keyboard.press("Enter")
    else:
        loc.scroll_into_view_if_needed(timeout=5000)
        loc.click(timeout=5000)
    if changes:
        try:
            page.wait_for_function(f"window.__gnmRenderCount() > {n0}", timeout=15000)
        except Exception:  # noqa: BLE001
            return [f"no finished render / update after the click (hash {page.evaluate('location.hash')})"], {}
    else:
        page.wait_for_timeout(50)
    page.evaluate("window.__gnmRendered()")
    st = None
    t0 = time.perf_counter()
    while True:   # the section settles within ~0.7 s; poll up to 2.5 s
        st = page.evaluate(CHECK, [section, anchor])
        good = (not (section or anchor)) or (st.get("target") and st.get("inView") and st.get("atTop") and st.get("focused"))
        if good or time.perf_counter() - t0 > 2.5:
            break
        page.wait_for_timeout(80)
    probs = []
    want_hash = href if is_route else src_hash
    if not _same_url(st["hash"], want_hash):
        probs.append(f"URL {st['hash']} != {want_hash}")
    want_route = _route_of(want_hash)
    if st["navCurrent"] != want_route:
        probs.append(f"route {st['navCurrent']} rendered, want {want_route}")
    if not st["ready"] or st["error"] or st["empty"]:
        probs.append(f"view not rendered (ready={st['ready']} error={st['error']} empty={st['empty']})")
    if section or anchor:
        if not st.get("target"):
            probs.append(f"section target '{section or anchor}' not found")
        else:
            if not st.get("inView"):
                probs.append("target heading not in the viewport")
            elif not st.get("atTop"):
                probs.append("target not scrolled to the top")
            if not st.get("focused"):
                probs.append(f"target heading not focused (active: {st.get('active')})")
    return probs, st


def _start(page, base, state, src, link):
    href = link["href"]
    if state == "fresh":
        _cold(page, base, src)
    elif state == "other":
        other = next(r for r in ROUTES if r not in (_route_of(src), _route_of(href) if href.startswith("#/") else ""))
        _cold(page, base, f"#/{other}")
        _hop(page, src)
    else:  # same
        if href.startswith("#/") and _route_of(href) == _route_of(src):
            _cold(page, base, src)
            if not _same_url(href, src):
                _hop(page, href)
        elif href.startswith("#/"):
            _cold(page, base, href)
            _hop(page, src)
        else:
            _cold(page, base, src)


@pytest.fixture(scope="module")
def site():
    with AL.serve_docs() as index:
        yield index.rsplit("/", 1)[0] + "/"


def _write_md():
    rows, tot_links, tot_clicks, tot_fail, fails = [], 0, 0, 0, []
    for f in sorted(OUT.glob("*.json")):
        d = json.loads(f.read_text())
        rows.append((d["browser"], d["route"], d["links"], d["clicks"], d["failed_clicks"], d["seconds"]))
        tot_links += d["links"]; tot_clicks += d["clicks"]; tot_fail += d["failed_clicks"]
        fails += [f"| {d['browser']} | {d['route']} | `{x['href']}` ({x['zone']}) | {x['state']} #{x['click']} | {'; '.join(x['problems'])} |" for x in d["failures"][:40]]
    browsers = sorted({r[0] for r in rows})
    internal = [
        "<!-- internal:start (written by tests/e2e/test_links_every_time.py) -->",
        f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `tests/e2e/test_links_every_time.py` ({', '.join(browsers)}, 1440 x 900, Simple mode).",
        "",
        "Every internal link found on every route (`a[href^=\"#/\"]` in the shell and the page, plus in-page anchors such as the",
        "skip link; the glossary group chips are `?section=` links) was clicked 5 times from each of 3 starting states (fresh load, coming from",
        "another page, already on the target URL), returning with browser Back between clicks that left the page. After every",
        "click: the URL equals the link, the target route rendered, and for section links the target heading is in the",
        "viewport and focused. Links to the current route have no skip allowance.",
        "",
        f"**Totals: {tot_links} link checks, {tot_clicks} clicks, {tot_fail} failed.**",
        "",
        "| Browser | Route | Links | Clicks | Failed | Seconds |",
        "|---|---|---:|---:|---:|---:|",
        *[f"| {b} | {r} | {n} | {c} | {x} | {s} |" for b, r, n, c, x, s in rows],
        "",
    ]
    if fails:
        internal += ["### Failures", "", "| Browser | Route | Link | State / click | Problem |", "|---|---|---|---|---|", *fails, ""]
    else:
        internal += ["No failures.", ""]
    internal.append("<!-- internal:end -->")
    block = "\n".join(internal)
    old = LINK_MD.read_text() if LINK_MD.exists() else "# Link check\n\n"
    if "<!-- internal:start" in old:
        new = re.sub(r"<!-- internal:start.*?<!-- internal:end -->", lambda _m: block, old, flags=re.S)
    else:
        new = old.rstrip() + "\n\n## Internal links (ROUTER)\n\n" + block + "\n"
    LINK_MD.write_text(new)


@pytest.mark.parametrize("browser_name", BROWSERS)
@pytest.mark.parametrize("route", SEL_ROUTES)
def test_links_every_time(site, route, browser_name):
    from playwright.sync_api import sync_playwright
    t0 = time.perf_counter()
    failures, clicks = [], 0
    src = f"#/{route}"
    with sync_playwright() as pw:
        browser = getattr(pw, browser_name).launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("try { localStorage.setItem('gnm-mode', 'simple'); } catch (e) {}")
        page = ctx.new_page()
        page.set_default_timeout(10000)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        try:
            _cold(page, site, src)
            links = page.evaluate(DISCOVER)
            assert links, f"no internal links on {src}"
            for link in links:
                for state in STATES:
                    try:
                        _start(page, site, state, src, link)
                    except Exception as exc:  # noqa: BLE001
                        failures.append({"href": link["href"], "zone": link["zone"], "state": state, "click": 0, "problems": [f"start failed: {str(exc).splitlines()[0][:160]}"]})
                        continue
                    for k in range(1, REPEATS + 1):
                        clicks += 1
                        errors.clear()
                        try:
                            if _route_of(page.evaluate("location.hash")) != route:
                                _back(page)                     # the last click left the page: browser Back
                            if _route_of(page.evaluate("location.hash")) != route:
                                _hop(page, src)
                            page.evaluate("window.scrollTo(0, 0)")
                            probs, _st = _click_once(page, link, page.evaluate("location.hash"))
                        except Exception as exc:  # noqa: BLE001
                            probs = [f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"]
                        if errors:
                            probs += errors[:3]
                        if probs:
                            failures.append({"href": link["href"], "zone": link["zone"], "state": state, "click": k, "problems": probs})
        finally:
            ctx.close()
            browser.close()
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {"route": route, "browser": browser_name, "links": len(links) * len(STATES), "unique_links": len(links), "clicks": clicks,
           "failed_clicks": len(failures), "failures": failures, "seconds": round(time.perf_counter() - t0, 1),
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (OUT / f"{browser_name}_{route}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    _write_md()
    assert not failures, f"{len(failures)} failed clicks on {src} ({browser_name}); first: {failures[:5]}"
