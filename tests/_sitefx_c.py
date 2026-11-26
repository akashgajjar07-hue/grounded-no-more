"""Shared Playwright helpers for the screens-C site tests (04 Rotable & Repair, 05 Network)."""
from __future__ import annotations

import functools
import http.server
import threading
from contextlib import contextmanager
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
VIEWPORTS = {"1440": (1440, 900), "390": (390, 844)}


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass


class _Server(http.server.ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


@contextmanager
def serve_docs():
    srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(DOCS)))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


def open_route(browser, base, route, viewport):
    """Open index.html<route>, wait for render; returns (context, page, problems list)."""
    w, h = VIEWPORTS[viewport]
    ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
    page = ctx.new_page()
    problems: list[str] = []
    page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"request failed: {r.url}"))
    page.on("response", lambda r: problems.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    page.goto(f"{base}/index.html{route}")
    page.wait_for_selector('html[data-ready="true"]', timeout=15000)
    page.wait_for_timeout(900)
    return ctx, page, problems


CHECK_JS = """() => {
  const view = document.querySelector('#view');
  const text = view.innerText;
  const bad = ['NaN', 'undefined', 'null'].filter((t) => new RegExp(`\\\\b${t}\\\\b`).test(text));
  const frames = [...view.querySelectorAll('.chart-frame')].map((f) => ({
    headline: (f.querySelector('.chart-headline')?.textContent || '').trim(),
    subtitle: (f.querySelector('.chart-subtitle')?.textContent || '').trim(),
    chip: !!f.querySelector('.chip-prov'),
  }));
  const overflow = [...view.querySelectorAll('.card *, .rr-stat *')].filter((e) => {
    if (e.closest('.table-wrap') || e.closest('.sr-only') || e.closest('svg') || e.closest('select') || e.tagName === 'SELECT' || e.tagName === 'INPUT') return false;
    if (!e.textContent.trim() || e.children.length) return false;
    return e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0 && getComputedStyle(e).overflow !== 'visible';
  }).map((e) => `${e.tagName}.${e.className}: ${e.textContent.slice(0, 40)}`);
  const hscroll = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;
  const disclaimer = !!document.querySelector('.disclaimer');
  return { bad, frames, overflow, hscroll, disclaimer };
}"""


def assert_clean(page, problems, label):
    r = page.evaluate(CHECK_JS)
    assert not problems, f"{label}: {problems}"
    assert not r["bad"], f"{label}: visible {r['bad']}"
    assert r["frames"], f"{label}: no chart frames"
    for f in r["frames"]:
        assert f["headline"] and f["subtitle"] and f["chip"], f"{label}: chart frame incomplete {f}"
    assert not r["overflow"], f"{label}: text overflow {r['overflow'][:5]}"
    assert not r["hscroll"], f"{label}: horizontal page scroll"
    assert r["disclaimer"], f"{label}: footer disclaimer missing"
    return r
