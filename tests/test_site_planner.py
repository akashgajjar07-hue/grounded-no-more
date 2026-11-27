"""Browser tests for The Planner Behind the Project (#/planner): essay from docs/content/planner.md, DRAFT, links."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser
SRC = (DOCS / "content/planner.md").read_text()


@pytest.mark.parametrize("mode", ["simple", "expert"])
@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_planner_essay(site, browser, vp, mode):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/planner", vp)
    try:
        if mode == "expert":
            page.evaluate("import('./js/lib/mode.js').then(m => m.setMode('expert'))")
            page.wait_for_function("document.body.classList.contains('mode-expert') && document.documentElement.dataset.ready === 'true'")
            page.wait_for_timeout(500)
        audit(page, problems, min_frames=0)
        assert page.locator("#view h1").inner_text().strip() == "The Planner Behind the Project"
        assert page.locator('[data-role="intro3"]').count() == 1
        if "*Draft*" in SRC:
            assert page.locator('[data-role="draft"]').inner_text().strip() == "DRAFT"
        essay = page.locator('[data-role="planner-essay"]')
        heads = [t.strip() for t in essay.locator("h2").all_inner_texts()]
        expected = [l[3:].strip() for l in SRC.splitlines() if l.startswith("## ")]
        assert heads == expected
        q = page.locator('[data-role="pull-quote"] p').inner_text().strip()
        assert q and q in SRC.replace("*", "")
        assert page.locator('a[data-role="link-about"]').get_attribute("href") == "#/about"
        docs = page.evaluate("[...document.querySelectorAll('[data-role=project-docs] a')].map(a => a.getAttribute('href'))")
        assert len(docs) == 5 and all(h.startswith("https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/") for h in docs)
        assert page.locator('[data-role="study-pack"]').count() == 0   # v2.2: no study material on the public site
        for h in docs:
            assert (DOCS.parent / h.split("/blob/main/")[1]).exists(), h
        assert page.locator("#view img").count() == 0  # portrait-free
        assert not problems, problems
    finally:
        ctx.close()


def test_readability_simple(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/planner", "1440")
    try:
        r = page.evaluate("import('./js/lib/readability.js').then(R => R.readability())")
        (DOCS.parent / "reports/readability").mkdir(parents=True, exist_ok=True)
        (DOCS.parent / "reports/readability/planner.json").write_text(json.dumps(
            {"grade": r["grade"], "maxSentenceWords": r["maxSentenceWords"], "longSentences": r["longSentences"]}, indent=2, ensure_ascii=False))
        assert r["grade"] <= 9, r
        own = [s for s in r["longSentences"] if s[:40] not in SRC]
        assert not own, own
    finally:
        ctx.close()
