"""Interaction audit harness for the GROUNDED NO MORE site (v2.1).

For one route it discovers every interactive element (buttons, links, tabs, chips, toggles, selects, sliders, inputs,
glossary terms / tooltips, "View data" expanders, modal and tour controls) plus the global keyboard shortcuts
(1-8, 0, ?, S, Esc). It operates each one and checks that it produces a visible effect within 1 s. Effects counted:
DOM mutation in a visible area, navigation (hash change), chart update, modal / drawer / tooltip, download, or a
focus change for keyboard-only controls. Console errors, unhandled rejections, page errors and failed requests are
failures.

Library use (parametrisable by browser / viewport / mode):

    from audit_lib import AuditConfig, serve_docs, audit_route, write_report
    with serve_docs() as base, sync_playwright() as p:
        rep = audit_route(p, base, AuditConfig(route="mission", browser="chromium", viewport=(1440, 900), mode="simple"))
        write_report([rep], "tests/e2e/reports/mission.json")

CLI:

    python tests/e2e/audit_lib.py --route about --browser chromium --viewport 390x844 --mode expert \
        --out tests/e2e/reports/about.json [--max 80] [--no-shortcuts] [--reduced]

Each element result has: id, kind, label, selector, action, effects[], ok, ms, note. ok=None means skipped
(disabled, or a re-render removed / hid it); every skip carries its reason in `note` (a skip without a reason is
counted as failed) and the report lists the reasons with counts (summary.skip_reasons, totals.skip_reasons).
v2.2: links to the current route (and shortcut keys for the current route) are NOT skippable: they must scroll the
page or move focus to a target other than the clicked link (the router re-runs the section scroll / scrolls to the top
and focuses the view), or they count as failed. External links are checked by href only (ok=True, effect
"external-href"), not skipped.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import json
import socketserver
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
EFFECT_TIMEOUT_MS = 1000

# --------------------------------------------------------------------------------------------- server


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass


@contextlib.contextmanager
def serve_docs(directory: Path = DOCS):
    """Serve docs/ on an ephemeral localhost port; yields the index URL."""
    handler = functools.partial(_Quiet, directory=str(directory))

    class _Server(socketserver.ThreadingTCPServer):
        request_queue_size = 128
        allow_reuse_address = True
        daemon_threads = True

    httpd = _Server(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    finally:
        httpd.shutdown()


# --------------------------------------------------------------------------------------------- data


@dataclass
class AuditConfig:
    route: str = "mission"                 # route id or hash with params ("parts?ata=32")
    browser: str = "chromium"              # chromium | firefox | webkit
    viewport: tuple[int, int] = (1440, 900)
    mode: str = "simple"                   # simple | expert (localStorage gnm-mode before load)
    reduced_motion: bool = False
    max_elements: int = 250
    timeout_ms: int = EFFECT_TIMEOUT_MS
    shortcuts: bool = True
    skip: list[str] = field(default_factory=list)   # extra CSS selectors never operated


@dataclass
class ElementResult:
    id: str
    kind: str
    label: str
    selector: str
    action: str = ""
    effects: list[str] = field(default_factory=list)
    ok: bool | None = None
    ms: float | None = None
    note: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class RouteReport:
    route: str
    browser: str
    viewport: str
    mode: str
    reduced_motion: bool
    url: str
    started: str
    seconds: float = 0.0
    elements: list[ElementResult] = field(default_factory=list)
    shortcuts: list[ElementResult] = field(default_factory=list)
    load_errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        allr = self.elements + self.shortcuts
        return {"total": len(allr), "ok": sum(r.ok is True for r in allr), "failed": sum(r.ok is False for r in allr),
                "skipped": sum(r.ok is None for r in allr), "load_errors": len(self.load_errors),
                "skip_reasons": _reasons(allr),
                "by_kind": {k: {"ok": sum(r.ok is True for r in allr if r.kind == k), "failed": sum(r.ok is False for r in allr if r.kind == k)}
                            for k in sorted({r.kind for r in allr})}}

    def to_json(self) -> dict:
        d = asdict(self)
        d["summary"] = self.summary
        return d


def _reasons(results) -> dict:
    out: dict[str, int] = {}
    for r in results:
        if r.ok is None:
            k = (r.note or "").split(" | ")[0] or "no reason recorded"
            out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# --------------------------------------------------------------------------------------------- page-side JS

# Discover interactive elements: returns descriptors with a robust CSS path (re-locatable after a re-render).
DISCOVER_JS = r"""(skip) => {
  const SEL = [
    'a[href]', 'button', 'summary', 'select', 'textarea', 'input:not([type=hidden])',
    '[role=button]', '[role=tab]', '[role=radio]', '[role=switch]', '[role=checkbox]', '[role=menuitem]', '[role=option]', '[role=slider]',
    '[tabindex="0"]', '.term[data-term]', '.chip[onclick]', '[data-tip]', '[aria-haspopup]'
  ].join(',');
  const skipSel = ['.sr-only', '#gnm-term-defs', 'script', 'template', ...skip].join(',');
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && !e.closest('[hidden], details:not([open]) > :not(summary)'); };
  const path = (e) => {
    if (e.id && document.querySelectorAll('#' + CSS.escape(e.id)).length === 1) return '#' + CSS.escape(e.id);
    const parts = [];
    for (let n = e; n && n.nodeType === 1 && n !== document.documentElement; n = n.parentElement) {
      if (n.id && document.querySelectorAll('#' + CSS.escape(n.id)).length === 1) { parts.unshift('#' + CSS.escape(n.id)); break; }
      let i = 1, s = n; while ((s = s.previousElementSibling)) if (s.tagName === n.tagName) i++;
      parts.unshift(`${n.tagName.toLowerCase()}:nth-of-type(${i})`);
    }
    return parts.join(' > ');
  };
  const kindOf = (e) => {
    const t = e.tagName.toLowerCase(), role = e.getAttribute('role'), type = (e.getAttribute('type') || '').toLowerCase();
    if (e.matches('.term[data-term]')) return 'term';
    if (t === 'summary') return 'expander';
    if (t === 'select') return 'select';
    if (t === 'input' && type === 'range' || role === 'slider') return 'slider';
    if (t === 'input' && (type === 'checkbox' || type === 'radio') || role === 'checkbox' || role === 'switch') return 'toggle';
    if (t === 'input' || t === 'textarea') return 'input';
    if (role === 'tab') return 'tab';
    if (role === 'radio' || e.hasAttribute('aria-pressed')) return 'toggle';
    if (e.closest('.story')) return 'tour';
    if (e.closest('.modal, .drawer')) return 'overlay-control';
    if (t === 'a') return e.hasAttribute('download') ? 'download' : 'link';
    if (e.classList.contains('chip') || e.closest('.chip')) return 'chip';
    if (t === 'button' || role === 'button') return 'button';
    return 'focusable';
  };
  const seen = new Set(), out = [];
  document.querySelectorAll(SEL).forEach((e) => {
    if (seen.has(e) || e.closest(skipSel) || !vis(e)) return;
    if (e.matches('[tabindex="0"]') && !e.matches('.term, [role], button, a, summary, input, select, textarea') && e.closest('.table-wrap, .chart-body, .view')) {
      // a bare tabindex=0 region (scrollable table, chart) is focusable for scrolling, not an action
      if (!e.onclick && !e.hasAttribute('aria-describedby')) return;
    }
    seen.add(e);
    const label = (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || e.getAttribute('href') || e.tagName).replace(/\s+/g, ' ').trim().slice(0, 80);
    const href = e.getAttribute('href') || '';
    out.push({ kind: kindOf(e), label, selector: path(e), disabled: !!(e.disabled || e.getAttribute('aria-disabled') === 'true'),
      href, external: /^https?:/i.test(href) && !href.startsWith(location.origin) || e.getAttribute('target') === '_blank',
      inShell: !e.closest('#view') });
  });
  return out;
}"""

# Install / read the effect observer. Counts mutations in VISIBLE elements (ignoring the observer's own noise).
OBSERVE_JS = r"""() => {
  if (window.__audit) { window.__audit.n = 0; window.__audit.kinds = new Set(); return; }
  const a = window.__audit = { n: 0, kinds: new Set() };
  const visible = (n) => { const e = n.nodeType === 1 ? n : n.parentElement; if (!e || !e.isConnected) return true; const r = e.getBoundingClientRect(); return r.width > 0 || r.height > 0; };
  new MutationObserver((ms) => { ms.forEach((m) => {
    if (m.target.closest?.('.story-fill')) return;                       // the tour progress fill ticks every frame
    if (m.type === 'attributes' && m.attributeName === 'style' && m.target.classList?.contains('kpi-spark')) return;
    if (!visible(m.target)) return;
    a.n++;
    if (m.target.closest?.('svg, .chart-body')) a.kinds.add('chart');
  }); }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true,
    attributeFilter: ['class', 'style', 'aria-expanded', 'aria-selected', 'aria-checked', 'aria-pressed', 'open', 'hidden', 'value', 'd', 'transform', 'width', 'height', 'x', 'y', 'cx', 'cy', 'r'] });
}"""

STATE_JS = r"""() => ({
  hash: location.hash, n: window.__audit ? window.__audit.n : 0, chart: window.__audit ? window.__audit.kinds.has('chart') : false,
  modal: !!document.querySelector('.modal'), drawer: !!document.querySelector('.drawer.is-open'), story: !!document.querySelector('.story'),
  tooltip: !!document.querySelector('.tooltip.is-on, .term-pop.is-on, [role=tooltip]:not([hidden]):not(#gnm-term-defs *)'),
  focus: document.activeElement ? (document.activeElement.id || document.activeElement.className || document.activeElement.tagName) + '' : '',
  focusIsLink: !!(document.activeElement && document.activeElement.matches && document.activeElement.matches('a[href]')),
  y: Math.round(window.scrollY),
  ready: document.documentElement.dataset.ready === 'true'
})"""


# --------------------------------------------------------------------------------------------- runner


def _hash_of(route: str) -> str:
    return route if route.startswith("#") else f"#/{route}"


def _new_page(pw, cfg: AuditConfig, base_url: str):
    btype = getattr(pw, cfg.browser)
    browser = btype.launch()
    ctx = browser.new_context(viewport={"width": cfg.viewport[0], "height": cfg.viewport[1]},
                              reduced_motion="reduce" if cfg.reduced_motion else "no-preference", accept_downloads=True)
    ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', {json.dumps(cfg.mode)}); }} catch (e) {{}}")
    page = ctx.new_page()
    page.set_default_timeout(8000)   # a control that vanished fails in 8 s instead of hanging 30 s
    errors: list[str] = []
    # WebKit reports requests that a page load cancels as errors ("Load failed", "Importing a module script failed",
    # "... due to access control checks"); within 3 s of a main-frame navigation they are not failures of the control
    nav_t = [0.0]
    page.on("framenavigated", lambda f: nav_t.__setitem__(0, time.perf_counter()) if f == page.main_frame else None)
    ABORT = ("Importing a module script failed", "TypeError: Load failed", "due to access control checks")
    after_nav = lambda m: any(a in m for a in ABORT) and time.perf_counter() - nav_t[0] < 3.0
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" and not after_nav(m.text) else None)
    page.on("pageerror", lambda e: None if after_nav(str(e)) else errors.append(f"pageerror: {e}"))
    # fetches the browser cancels because the user navigated on are invisible to the user: not failures
    page.on("requestfailed", lambda r: None if any(x in str(r.failure) for x in ("cancelled", "ERR_ABORTED", "NS_BINDING_ABORTED"))
            else errors.append(f"requestfailed: {r.url} {r.failure}"))
    page.on("response", lambda r: errors.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    page.add_init_script("window.addEventListener('unhandledrejection', (e) => console.error('unhandledrejection: ' + (e.reason && e.reason.message || e.reason)));")
    return browser, ctx, page, errors


def _goto(page, base_url: str, route: str):
    page.goto(base_url + _hash_of(route))
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=20000)
    page.wait_for_timeout(600)
    page.evaluate(OBSERVE_JS)


def _restore(page, base_url: str, route: str, mode: str | None = None):
    """Close overlays / tour and return to the route if the action navigated away."""
    for _ in range(2):
        st = page.evaluate(STATE_JS)
        if st["modal"] or st["drawer"] or st["story"] or st["tooltip"]:
            page.keyboard.press("Escape")
            page.wait_for_timeout(120)
    # the mobile navigation rail (#menu-btn) is not a modal/drawer in STATE_JS: close it explicitly,
    # otherwise its scrim blocks every later control at 390 px (found by the PAGE-4 audit)
    if page.evaluate("document.getElementById('app')?.classList.contains('rail-open') || false"):
        page.keyboard.press("Escape")
        page.wait_for_timeout(120)
        if page.evaluate("document.getElementById('app')?.classList.contains('rail-open') || false"):
            page.evaluate("document.getElementById('menu-btn')?.click()")
            page.wait_for_timeout(200)
    if page.evaluate("location.hash").split("?")[0] != _hash_of(route).split("?")[0]:
        _goto(page, base_url, route)
    # after the Simple/Expert toggle was operated, return to the audited mode (found by the PAGE-3 audit)
    if mode and not page.evaluate(f"document.body.classList.contains('mode-{mode}')"):
        page.evaluate(f"document.querySelector('[data-mode=\"{mode}\"], button[data-set-mode=\"{mode}\"]')?.click()")
        page.wait_for_timeout(200)


def _wait_effect(page, before: dict, timeout_ms: int, download_box: list) -> tuple[list[str], float]:
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) * 1000 < timeout_ms:
        st = page.evaluate(STATE_JS)
        eff = []
        if download_box:
            eff.append("download")
        if st["hash"] != before["hash"]:
            eff.append("navigation")
        if abs(st["y"] - before["y"]) > 2:
            eff.append("scroll")
        for k in ("modal", "drawer", "story", "tooltip"):
            if st[k] and not before[k]:
                eff.append(k)
        if st["n"] > 0:
            eff.append("chart-update" if st["chart"] else "dom-mutation")
        if eff:
            return eff, round((time.perf_counter() - t0) * 1000, 1)
        page.wait_for_timeout(40)
    st = page.evaluate(STATE_JS)
    return (["focus-change"] if st["focus"] != before["focus"] else []), round((time.perf_counter() - t0) * 1000, 1)


def _open_rail_if_needed(page, loc) -> bool:
    """At narrow widths the navigation rail is off-canvas until #menu-btn opens it (as a user would)."""
    inside = loc.evaluate("(e) => !!e.closest('#app > nav, #nav') && e.id !== 'menu-btn'")
    if not inside:
        return False
    closed = page.evaluate("(() => { const a = document.getElementById('app'); const m = document.getElementById('menu-btn');"
                           " return !!(a && m && m.offsetParent !== null && !a.classList.contains('rail-open')); })()")
    if closed:
        page.evaluate("document.getElementById('menu-btn').click()")
        page.wait_for_timeout(350)
        return True
    return False


def _operate(page, d: dict, cfg: AuditConfig, download_box: list) -> str:
    loc = page.locator(d["selector"]).first
    k = d["kind"]
    _open_rail_if_needed(page, loc)
    # a drawer/modal already open (e.g. a deep link that opens a part drawer at load) covers controls
    # outside it: close it first, as a user would, unless the control lives inside that overlay
    outside = loc.evaluate("(e) => { const o = [...document.querySelectorAll('[role=dialog].is-open, .drawer.is-open, .modal-card')]"
                           ".find((d) => !d.classList.contains('story') && d.getBoundingClientRect().width > 0"
                           " && (d.classList.contains('is-open') || !!document.querySelector('.scrim.is-open')));"
                           " return !!o && !o.contains(e) && !e.closest('.story, .story-card, [role=dialog], .drawer, .modal-card'); }")
    if outside:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    # a control inside a collapsed <details> is reached by opening it first, as a user would
    # (the control's own <summary> is left alone: toggling it is the action under test)
    if loc.evaluate("(e) => { let o = false; for (let d = e.parentElement?.closest('details'); d; d = d.parentElement?.closest('details')) {"
                    " if (!d.open && !(e.tagName === 'SUMMARY' && e.parentElement === d)) { d.open = true; o = true; } } return o; }"):
        page.wait_for_timeout(120)
    # keep the control clear of the sticky top bar after earlier scrolling
    loc.evaluate("(e) => e.scrollIntoView({block: 'center', inline: 'nearest'})")
    page.wait_for_timeout(60)
    if loc.evaluate("(e) => e.classList.contains('skip-link')"):
        loc.focus()
        page.keyboard.press("Enter")
        return "focus+Enter(skip-link)"
    if k == "select":
        opts = loc.evaluate("(s) => [...s.options].map((o) => o.value)")
        cur = loc.evaluate("(s) => s.value")
        other = next((o for o in opts if o != cur), None)
        if other is None:
            return "select:single-option"
        loc.select_option(other)
        return f"select:{other}"
    if k == "slider":
        loc.focus()
        page.keyboard.press("ArrowRight")
        return "key:ArrowRight"
    if k == "input":
        typ = (loc.get_attribute("type") or "text").lower()
        if typ in ("number",):
            loc.focus()
            page.keyboard.press("ArrowUp")
            return "key:ArrowUp"
        loc.fill("a")
        return "fill:a"
    if k == "term":
        loc.hover()
        return "hover"
    if k == "focusable":
        loc.focus()
        page.keyboard.press("Enter")
        return "focus+Enter"
    if k == "download":
        with page.expect_download(timeout=cfg.timeout_ms) as dl:
            loc.click()
        download_box.append(dl.value.suggested_filename)
        return "click(download)"
    loc.click(timeout=cfg.timeout_ms)
    return "click"


def audit_route(pw, base_url: str, cfg: AuditConfig) -> RouteReport:
    """Audit one route. pw = a sync_playwright() instance."""
    browser, ctx, page, errors = _new_page(pw, cfg, base_url)
    rep = RouteReport(route=cfg.route, browser=cfg.browser, viewport=f"{cfg.viewport[0]}x{cfg.viewport[1]}", mode=cfg.mode,
                      reduced_motion=cfg.reduced_motion, url=base_url + _hash_of(cfg.route), started=time.strftime("%Y-%m-%dT%H:%M:%S"))
    t_start = time.perf_counter()
    try:
        _goto(page, base_url, cfg.route)
        rep.load_errors = list(errors)
        errors.clear()
        found = page.evaluate(DISCOVER_JS, cfg.skip)[: cfg.max_elements]
        for n, d in enumerate(found):
            r = ElementResult(id=f"e{n:03d}", kind=d["kind"], label=d["label"], selector=d["selector"])
            if d["disabled"]:
                r.note = "disabled"
                rep.elements.append(r)
                continue
            if d["external"]:
                r.note, r.ok, r.effects = "external link (not followed; href checked)", (True if d["href"] else False), ["external-href"]
                rep.elements.append(r)
                continue
            # an in-shell nav link that points at the current route is a valid no-op
            try:
                if page.locator(d["selector"]).count() == 0:
                    r.note = "not found after a re-render"
                    rep.elements.append(r)
                    continue
                vis_js = "(e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; }"
                if not page.locator(d["selector"]).first.evaluate(vis_js, timeout=5000) and not page.locator(d["selector"]).first.evaluate("(e) => !!e.closest('details:not([open]), #app > nav, #nav')", timeout=5000):
                    _goto(page, base_url, cfg.route)   # e.g. a deep-link drawer closed by an earlier control: reopen it
                    try:
                        page.locator(d["selector"]).first.wait_for(state="visible", timeout=5000)
                    except Exception:  # noqa: BLE001
                        pass
                    if page.locator(d["selector"]).count() == 0 or not page.locator(d["selector"]).first.evaluate(vis_js, timeout=5000):
                        # positional selectors into body-level overlays (drawer, tour card) go stale when a reload appends
                        # them in another order: re-find the control by kind + label among visible elements
                        found = page.evaluate("""([label, tag]) => {
                          document.querySelectorAll('[data-audit-target]').forEach((e) => e.removeAttribute('data-audit-target'));
                          const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
                          const name = (e) => (e.getAttribute('aria-label') || e.textContent || '').replace(/\\s+/g, ' ').trim();
                          const hit = [...document.querySelectorAll(tag)].find((e) => vis(e) && name(e).startsWith(label));
                          if (hit) hit.setAttribute('data-audit-target', '1');
                          return !!hit; }""", [d["label"].strip()[:60], d["selector"].split(">")[-1].strip().split(":")[0] or "*"])
                        if not found:
                            r.note = "hidden after a re-render"
                            rep.elements.append(r)
                            continue
                        d = {**d, "selector": '[data-audit-target="1"]'}
                selected = page.locator(d["selector"]).first.evaluate(
                    "(e) => e.getAttribute('role') === 'radio' && e.getAttribute('aria-checked') === 'true'", timeout=5000)
                if d["kind"] == "link" and d["href"].startswith("#") and (
                        not d["href"].startswith("#/") or d["href"].split("?")[0] == page.evaluate("location.hash").split("?")[0]):
                    # a link to the current route / an in-page anchor has to PROVE it scrolls or moves focus: start
                    # from a page scrolled away (shell links stay put) with nothing focused; wait out the ~0.8 s
                    # settle window of an earlier section jump first (it re-focuses its heading)
                    page.wait_for_timeout(900)
                    if d["inShell"]:
                        page.evaluate("window.scrollTo(0, Math.min(400, document.documentElement.scrollHeight - innerHeight))")
                    page.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
                    page.wait_for_timeout(60)
                page.evaluate(OBSERVE_JS)
                before = page.evaluate(STATE_JS)
                page.wait_for_timeout(60)
                idle = page.evaluate(STATE_JS)["n"]
                page.evaluate(OBSERVE_JS)
                box: list = []
                r.action = _operate(page, d, cfg, box)
                r.effects, r.ms = _wait_effect(page, before, cfg.timeout_ms, box)
                if idle and r.effects == ["dom-mutation"]:
                    r.note = f"page mutates while idle ({idle} in 60 ms): effect may be background noise"
                same_route_link = d["kind"] == "link" and d["href"].startswith("#") and before["hash"] == page.evaluate("location.hash")
                if same_route_link:
                    # v2.2: a link to the current URL (or an in-page anchor) must scroll or move focus to a target
                    # that is not the clicked link itself; a DOM mutation alone does not count
                    st = page.evaluate(STATE_JS)
                    moved_focus = st["focus"] != before["focus"] and not st["focusIsLink"]
                    if moved_focus and "focus-change" not in r.effects:
                        r.effects.append("focus-change")
                    r.ok = "scroll" in r.effects or moved_focus
                    r.note = "link to the current URL: " + ("scrolled / focused its target" if r.ok else "no scroll and no focus move (FAILED)")
                else:
                    r.ok = bool(r.effects) or selected
                if selected and not r.effects:
                    r.note = "option already selected (no-op)"
            except Exception as exc:  # noqa: BLE001
                if "Execution context was destroyed" in str(exc):
                    # the control loaded another document (e.g. a cutaway part opens the parts page): that is its effect
                    page.wait_for_load_state("load")
                    r.ok, r.effects, r.note = True, ["navigation"], "loaded another page"
                else:
                    r.ok, r.note = False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
            r.errors = list(errors)
            if errors:
                r.ok = False
            errors.clear()
            rep.elements.append(r)
            try:
                _restore(page, base_url, cfg.route, cfg.mode)
            except Exception as exc:  # noqa: BLE001
                r.note += f" | restore failed: {exc}"
                _goto(page, base_url, cfg.route)
        if cfg.shortcuts:
            rep.shortcuts = _audit_shortcuts(page, base_url, cfg, errors)
        for r in rep.elements + rep.shortcuts:     # v2.2: a skip must state its reason
            if r.ok is None and not r.note.strip():
                r.ok, r.note = False, "skipped without a stated reason"
            elif r.ok is None and "skipped:" not in r.note:
                r.note = f"skipped: {r.note}"

    finally:
        rep.seconds = round(time.perf_counter() - t_start, 1)
        ctx.close()
        browser.close()
    return rep


SHORTCUTS = [("?", "modal"), ("s", "story"), ("1", "navigation"), ("2", "navigation"), ("3", "navigation"), ("4", "navigation"),
             ("5", "navigation"), ("6", "navigation"), ("7", "navigation"), ("8", "navigation"), ("0", "navigation")]


def _audit_shortcuts(page, base_url: str, cfg: AuditConfig, errors: list) -> list[ElementResult]:
    out = []
    for key, want in SHORTCUTS:
        r = ElementResult(id=f"k-{key}", kind="shortcut", label=f"key {key}", selector="body", action=f"key:{key}")
        _goto(page, base_url, cfg.route)
        before = page.evaluate(STATE_JS)
        if want == "navigation":
            target = page.evaluate(f"import('./js/app.js').then((m) => (m.ROUTES.find((x) => x.key === '{key}') || {{}}).id || null)")
            if target and _hash_of(cfg.route).split("?")[0] == f"#/{target}":
                # v2.2: the key for the current route is not a skip: it must scroll to the top / focus the view
                want = "same-route"
                page.evaluate("window.scrollTo(0, Math.min(400, document.documentElement.scrollHeight - innerHeight))")
                page.wait_for_timeout(80)
                before = page.evaluate(STATE_JS)
        page.locator("body").press(key)
        r.effects, r.ms = _wait_effect(page, before, cfg.timeout_ms, [])
        if want == "same-route":
            st = page.evaluate(STATE_JS)
            if st["focus"] != before["focus"] and "focus-change" not in r.effects:
                r.effects.append("focus-change")
            r.ok = "scroll" in r.effects or "focus-change" in r.effects or "navigation" in r.effects
            r.note = "key for the current route: " + ("scrolled / focused the view" if r.ok else "no scroll and no focus move (FAILED)")
        else:
            r.ok = want in r.effects
        if r.ok and want in ("modal", "story"):
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
            closed = not page.evaluate(STATE_JS)[want]
            r.effects.append("esc-closes" if closed else "esc-did-not-close")
            r.ok = closed
        r.errors = list(errors)
        if errors:
            r.ok = False
        errors.clear()
        out.append(r)
    return out


def write_report(reports: list[RouteReport], path: str | Path) -> dict:
    """Write a JSON report (routes + per-element results + totals). Returns the written dict."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "effect_timeout_ms": EFFECT_TIMEOUT_MS,
            "routes": [r.to_json() for r in reports]}
    data["totals"] = {k: sum(r.summary[k] for r in reports) for k in ("total", "ok", "failed", "skipped", "load_errors")}
    reasons: dict[str, int] = {}
    for r in reports:
        for k, v in r.summary["skip_reasons"].items():
            reasons[k] = reasons.get(k, 0) + v
    data["totals"]["skip_reasons"] = dict(sorted(reasons.items(), key=lambda kv: -kv[1]))
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--route", action="append", help="route id (repeatable); default mission")
    ap.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    ap.add_argument("--viewport", default="1440x900")
    ap.add_argument("--mode", default="simple", choices=["simple", "expert"])
    ap.add_argument("--reduced", action="store_true")
    ap.add_argument("--max", type=int, default=250)
    ap.add_argument("--no-shortcuts", action="store_true")
    ap.add_argument("--out", default="tests/e2e/reports/audit.json")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    w, h = (int(x) for x in a.viewport.lower().split("x"))
    reps = []
    with serve_docs() as base, sync_playwright() as pw:
        for route in a.route or ["mission"]:
            cfg = AuditConfig(route=route, browser=a.browser, viewport=(w, h), mode=a.mode, reduced_motion=a.reduced,
                              max_elements=a.max, shortcuts=not a.no_shortcuts)
            reps.append(audit_route(pw, base, cfg))
            s = reps[-1].summary
            print(f"{route:12s} {a.browser} {a.viewport} {a.mode}: {s['ok']} ok, {s['failed']} failed, {s['skipped']} skipped ({reps[-1].seconds}s)")
            for reason, n in s["skip_reasons"].items():
                print(f"{'':14s}skipped {n} x {reason}")
    d = write_report(reps, a.out)
    print(json.dumps(d["totals"]), "->", a.out)


if __name__ == "__main__":
    main()
