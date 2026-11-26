"""Shared Playwright helpers for the site browser tests (screens-A: mission, method)."""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"
VIEWPORTS = {"1440": (1440, 900), "390": (390, 844)}

AUDIT_JS = r"""() => {
  const out = { overflow: [], frames: [], words: [], hscroll: document.documentElement.scrollWidth > window.innerWidth };
  document.querySelectorAll('#view .card *').forEach((e) => {
    if (e.closest('svg') || e.closest('.table-wrap') || e.closest('.sr-only') || e.closest('details')) return;
    if (e.children.length || !e.textContent.trim()) return;
    if (e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible') out.overflow.push(`${e.className}: ${e.textContent.slice(0, 50)}`);
  });
  document.querySelectorAll('#view figure.chart-frame').forEach((f) => {
    out.frames.push({ headline: (f.querySelector('.chart-headline')?.textContent || '').trim(),
      subtitle: (f.querySelector('.chart-subtitle')?.textContent || '').trim(),
      chip: !!f.querySelector('.chart-head .chip-prov') });
  });
  const text = document.body.innerText;
  out.words = ['NaN', 'undefined', 'null'].filter((w) => new RegExp(`\\b${w}\\b`).test(text));
  return out;
}"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass


@pytest.fixture(scope="module")
def site():
    handler = functools.partial(_Quiet, directory=str(DOCS))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_page(browser, url, vp, reduced=True):
    w, h = VIEWPORTS[vp]
    ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce" if reduced else "no-preference")
    page = ctx.new_page()
    problems: list[str] = []
    page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"requestfailed: {r.url}"))
    page.on("response", lambda r: problems.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=15000)
    page.wait_for_timeout(1200)
    return ctx, page, problems


def audit(page, problems, min_frames=1):
    res = page.evaluate(AUDIT_JS)
    assert not problems, problems
    assert not res["words"], f"visible {res['words']}"
    assert not res["hscroll"], "horizontal page scroll"
    assert not res["overflow"], res["overflow"]
    assert len(res["frames"]) >= min_frames, res["frames"]
    for f in res["frames"]:
        assert f["headline"] and f["subtitle"] and f["chip"], f
    return res
