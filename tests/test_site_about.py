"""Browser tests for About (v2.1): author, AI note, questions, downloads + E2 MRO, E3 real data, next experiments."""
from __future__ import annotations

import json
import re
import urllib.request

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser
MODES = ["simple", "expert"]


def _open(browser, url, vp, mode):  # noqa: F811
    ctx, page, problems = open_page(browser, url, vp)
    if mode != "simple":
        page.evaluate(f"import('./js/lib/mode.js').then(m => m.setMode('{mode}'))")
        page.wait_for_function(f"document.body.classList.contains('mode-{mode}') && document.documentElement.dataset.ready === 'true'")
        page.wait_for_timeout(600)
    return ctx, page, problems


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_about_content(site, browser, vp, mode):  # noqa: F811
    ctx, page, problems = _open(browser, site + "#/about", vp, mode)
    try:
        audit(page, problems, min_frames=0)
        assert page.locator('[data-role="intro3"]').count() == 1
        assert page.locator('[data-role="ai-note"]').inner_text().strip() == "Built with AI-assisted development; analysis, decisions and validation reviewed by the author."
        assert page.locator('[data-role="why-questions"] .ab-q-item').count() == 6
        assert page.locator('[data-role="why-note"]').inner_text().strip() == "Author’s answers to follow."
        body = page.locator("#view").inner_text()
        for t in ["Akash Gajjar", "University of Liverpool (2025)", "Primark", "Uniqlo"]:
            assert t in body
        assert not re.search(r"\boptimal\b|\bvalidated\b", body, re.I)
        # the three content sections, titles from the .md files
        for sid, title in [("mro", "How this transfers to an MRO"), ("real-data", "What real data would make this useful"), ("next-experiments", "Next experiments")]:
            sec = page.locator(f"#ab-{sid}")
            assert sec.count() == 1 and title in sec.locator(".card-title").inner_text()
        assert page.locator("#ab-real-data table tbody tr").count() >= 8
        # cross links became on-page section links; no raw HTML from the markdown
        hrefs = page.evaluate("[...document.querySelectorAll('.ab-md a')].map(a => a.getAttribute('href'))")
        assert "#/about?section=next-experiments" in hrefs and "#/about?section=real-data" in hrefs and "#/about?section=mro" in hrefs
        assert not any(h.endswith(".md") and not h.startswith("https://") for h in hrefs), hrefs
        # v2.2: Expert adds specialist depth to the content sections (<!-- expert --> blocks); Simple hides it
        blocks = page.locator(".ab-md .md-expert")
        assert blocks.count() >= 6
        docs_text = page.locator("#ab-mro").inner_text() + page.locator("#ab-real-data").inner_text()
        if mode == "expert":
            assert all(blocks.nth(i).is_visible() for i in range(blocks.count()))
            for t in ["Kit-completeness % at work start", "Work-order hold hours", "≈ 3.9 units in repair", "illustrative, not a model output", "Exchange", "no-fault-found"]:
                assert t in docs_text, t
        else:
            assert not any(blocks.nth(i).is_visible() for i in range(blocks.count()))
            assert "Kit-completeness" not in docs_text and "3.9 units" not in docs_text
        # section headings take focus on a jump
        for sid in ["mro", "real-data", "next-experiments"]:
            assert page.locator(f"#ab-{sid}-h").get_attribute("tabindex") == "-1"
        # policy codes only in Expert mode
        if mode == "simple":
            assert not re.search(r"\(P0\)", page.locator("#ab-next-experiments").inner_text())
        links = page.evaluate("[...document.querySelectorAll('.ab-links a')].map((a) => a.getAttribute('href'))")
        assert "https://github.com/akashgajjar07-hue" in links
        base = site.rsplit("/", 1)[0]
        for href in links:
            if href.startswith("downloads/"):
                with urllib.request.urlopen(f"{base}/{href}") as r:
                    assert r.status == 200
        assert not problems, problems
    finally:
        ctx.close()


def test_about_section_deep_link(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about?section=real-data", "1440")
    try:
        page.wait_for_timeout(600)
        top = page.evaluate("document.getElementById('ab-real-data').getBoundingClientRect().top")
        assert -5 <= top <= 140, top
        page.locator("#ab-real-data a", has_text="Next experiments").click()
        page.wait_for_timeout(1000)
        top = page.evaluate("document.getElementById('ab-next-experiments').getBoundingClientRect().top")
        assert -5 <= top <= 140, top
        assert page.evaluate("document.activeElement.id") == "ab-next-experiments-h"
        assert page.evaluate("location.hash") == "#/about?section=next-experiments"
        # v2.2: a repeat click on the link of the section already in the URL still jumps (no hashchange fires)
        page.evaluate("window.scrollTo({ top: 0, behavior: 'instant' }); document.activeElement.blur()")
        page.locator("#ab-real-data a", has_text="Next experiments").click()
        page.wait_for_timeout(600)
        top = page.evaluate("document.getElementById('ab-next-experiments').getBoundingClientRect().top")
        assert -5 <= top <= 140, top
        assert page.evaluate("document.activeElement.id") == "ab-next-experiments-h"
        assert not problems, problems
    finally:
        ctx.close()


def test_markdown_renderer_is_safe(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "1440")
    try:
        r = page.evaluate("""async () => {
          const m = await import('./js/views/about/md.js');
          const { title, nodes } = m.renderMarkdown('# T\\n\\nHi <script>x()</script> **b** *i* [ok](https://a.b) [bad](javascript:alert(1))\\n\\n- a\\n- b\\n\\n| h1 | h2 |\\n|---|---|\\n| c | d |', { dropTitle: true });
          const d = document.createElement('div'); d.append(...nodes);
          return { title, html: d.innerHTML, scripts: d.querySelectorAll('script').length, links: [...d.querySelectorAll('a')].map(a => a.getAttribute('href')),
            li: d.querySelectorAll('li').length, td: d.querySelectorAll('td').length };
        }""")
        assert r["title"] == "T" and r["scripts"] == 0 and "&lt;script&gt;" in r["html"]
        assert r["links"] == ["https://a.b"] and r["li"] == 2 and r["td"] == 1
        assert "<strong>b</strong>" in r["html"] and "<em>i</em>" in r["html"]
        # v2.2 mode blocks: <!-- expert --> … <!-- /expert --> → .md-expert.expert-only; other comments dropped
        r = page.evaluate("""async () => {
          const m = await import('./js/views/about/md.js');
          const { nodes } = m.renderMarkdown('A\\n\\n<!-- expert -->\\nB **x**\\n\\n- c\\n<!-- /expert -->\\n\\n<!-- note -->\\nD\\n\\n<!-- simple -->\\nE\\n<!-- /simple -->');
          const d = document.createElement('div'); d.append(...nodes);
          const ex = d.querySelector('.md-expert');
          return { top: [...d.children].map((n) => n.tagName + '.' + n.className), ex: ex && ex.classList.contains('expert-only'), exText: ex && ex.textContent,
                   simple: !!d.querySelector('.md-simple.simple-only'), comment: d.innerHTML.includes('note') };
        }""")
        assert r["top"] == ["P.", "DIV.md-expert expert-only", "P.", "DIV.md-simple simple-only"], r
        assert r["ex"] and "B x" in r["exText"] and r["exText"].endswith("c") and r["simple"] and not r["comment"], r
    finally:
        ctx.close()


def test_readability_simple(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "1440")
    try:
        r = page.evaluate("import('./js/lib/readability.js').then(R => R.readability())")
        (DOCS.parent / "reports/readability").mkdir(parents=True, exist_ok=True)
        (DOCS.parent / "reports/readability/about.json").write_text(json.dumps(
            {"grade": r["grade"], "maxSentenceWords": r["maxSentenceWords"], "longSentences": r["longSentences"]}, indent=2, ensure_ascii=False))
        assert r["grade"] <= 9, r
        # long sentences may only come from the AUTHOR's content files (reported to the lead)
        own = [s for s in r["longSentences"] if not any(s[:40] in (DOCS / f"content/{f}.md").read_text() for f in ("mro", "real_data", "next_experiments"))]
        assert not own, own
    finally:
        ctx.close()
