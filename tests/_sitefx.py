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

# Text that runs past the right edge of its card (or the viewport): the F2 class of bug (an SVG footnote clipped at
# 409 px on a 390 px screen). Exposed on window so any test can call it: page.evaluate(EDGE_JS) → list of strings.
EDGE_JS = r"""() => {
  const out = [];
  const vw = document.documentElement.clientWidth;
  const label = (el, t) => `${(el.getAttribute('class') || el.tagName).toString().slice(0, 40)}: ${t.trim().slice(0, 50)}`;
  const boxOf = (el) => el.closest('.card, .chart-frame, .drawer, .modal-card, .kpi');
  const scrolls = (el, stop) => { for (let a = el.parentElement; a && a !== stop; a = a.parentElement) { const ox = getComputedStyle(a).overflowX; if (ox === 'auto' || ox === 'scroll') return true; } return false; };
  const hidden = (el) => el.closest('.sr-only, [hidden], details:not([open]) > :not(summary)');
  // SVG text: must stay inside its <svg>, its card and the viewport
  document.querySelectorAll('#view svg text').forEach((t) => {
    if (hidden(t) || !t.textContent.trim()) return;
    const r = t.getBoundingClientRect();
    if (!r.width || !r.height) return;
    let svg = t.ownerSVGElement; while (svg && svg.ownerSVGElement) svg = svg.ownerSVGElement;
    const box = boxOf(t);
    if (scrolls(svg || t, box && box.parentElement)) return;
    const lim = Math.min(vw, svg ? svg.getBoundingClientRect().right : vw, box ? box.getBoundingClientRect().right : vw);
    if (r.right > lim + 1.5) out.push(`${label(t, t.textContent)} (right ${Math.round(r.right)} > ${Math.round(lim)})`);
  });
  // HTML text nodes: the rendered glyph boxes must stay inside the card and the viewport (scroll containers and
  // deliberate ellipsis clipping are exempt; those are judged by the overflow audit)
  const walker = document.createTreeWalker(document.querySelector('#view') || document.body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  let n;
  while ((n = walker.nextNode())) {
    const el = n.parentElement;
    if (!el || !n.textContent.trim() || el.closest('svg') || hidden(el)) continue;
    const box = boxOf(el);
    if (scrolls(el, box ? box.parentElement : null)) continue;
    let clip = null;
    for (let a = el; a && a !== box; a = a.parentElement) { const cs = getComputedStyle(a); if (cs.overflowX !== 'visible') { clip = a; break; } }
    if (clip) continue;
    range.selectNodeContents(n);
    const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
    if (!rects.length) continue;
    const right = Math.max(...rects.map((r) => r.right));
    const lim = Math.min(vw, box ? box.getBoundingClientRect().right : vw);
    if (right > lim + 1.5) out.push(`${label(el, n.textContent)} (right ${Math.round(right)} > ${Math.round(lim)})`);
  }
  return out;
}"""

AUDIT_JS = r"""() => {
  const out = { overflow: [], frames: [], words: [], edge: [], hscroll: document.documentElement.scrollWidth > window.innerWidth };
  const norm = (s) => String(s || '').replace(/[\s\u2026]+/g, ' ').replace(/\.\.\.$/, '').trim().toLowerCase();
  // a deliberate single-line ellipsis is fine when the full text is in a title attribute (the element or an ancestor)
  const okEllipsis = (e, cs) => {
    if (cs.textOverflow !== 'ellipsis' || !/nowrap|pre/.test(cs.whiteSpace)) return false;
    const t = e.closest('[title]');
    return !!t && norm(t.getAttribute('title')).includes(norm(e.textContent));
  };
  document.querySelectorAll('#view .card *').forEach((e) => {
    if (e.closest('svg') || e.closest('.table-wrap') || e.closest('.sr-only') || e.closest('details')) return;
    if (e.children.length || !e.textContent.trim()) return;
    const cs = getComputedStyle(e);
    if (e.scrollWidth > e.clientWidth + 1 && cs.overflow !== 'visible' && !okEllipsis(e, cs)) out.overflow.push(`${e.className}: ${e.textContent.slice(0, 50)}`);
  });
  document.querySelectorAll('#view figure.chart-frame').forEach((f) => {
    out.frames.push({ headline: (f.querySelector('.chart-headline')?.textContent || '').trim(),
      subtitle: (f.querySelector('.chart-subtitle')?.textContent || '').trim(),
      chip: !!f.querySelector('.chart-head .chip-prov') });
  });
  const text = document.body.innerText;
  out.words = ['NaN', 'undefined', 'null'].filter((w) => new RegExp(`\\b${w}\\b`).test(text));
  out.edge = (EDGE_FN)();
  return out;
}""".replace("EDGE_FN", EDGE_JS)


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
    assert not res["edge"], f"text past the card / viewport right edge: {res['edge']}"
    assert len(res["frames"]) >= min_frames, res["frames"]
    for f in res["frames"]:
        assert f["headline"] and f["subtitle"] and f["chip"], f
    return res
