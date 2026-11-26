"""v2.1 lab: interactive systems cutaway of a generic narrowbody (docs/lab/cutaway.html, post-plan, exploratory)."""
from __future__ import annotations

import json
import re

import pytest

from _sitefx import DOCS, browser, site  # noqa: F401

pytestmark = pytest.mark.browser

VIEWPORTS = {"1440": (1440, 900), "390": (390, 844)}
FORBIDDEN = [
    "validated", "optimal", "representative legacy airline practice", "panel-proof", "robust across worlds",
    "saves the airline AED", "Etihad", "Airbus", "Boeing", "A320", "A321", "737", "787", "Embraer", "Bombardier",
    "COMAC", "CFM", "Pratt", "Rolls-Royce", "Honeywell", "Safran", "Collins", "Thales", "Goodrich", "Liebherr",
]
PARTS = {p["pn"]: p for p in json.loads((DOCS / "data/parts.json").read_text())["parts"]}


def _open(browser, site, vp, reduced=True):  # noqa: F811
    w, h = VIEWPORTS[vp]
    ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce" if reduced else "no-preference")
    page = ctx.new_page()
    problems: list[str] = []
    page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.on("response", lambda r: problems.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    page.goto(site.replace("/index.html", "/lab/cutaway.html"))
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=15000)
    page.wait_for_timeout(400)
    return ctx, page, problems


def _text(page):
    return page.evaluate("() => document.body.innerText + ' ' + [...document.querySelectorAll('svg text, svg title, svg desc')].map((t) => t.textContent).join(' ') + ' ' + [...document.querySelectorAll('[aria-label]')].map((e) => e.getAttribute('aria-label')).join(' ')")


@pytest.mark.parametrize("vp", ["1440", "390"])
def test_loads_clean_without_overflow(site, browser, vp):  # noqa: F811
    ctx, page, problems = _open(browser, site, vp, reduced=False)
    try:
        page.wait_for_timeout(2200)  # the draw-in finishes within 2 s
        assert not problems, problems
        assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth"), "horizontal scroll"
        svg = page.locator("#cutaway svg.cw-svg")
        assert svg.count() == 1
        assert svg.get_attribute("data-mode") == ("full" if vp == "1440" else "simple")
        assert "is-drawing" not in (svg.get_attribute("class") or "")
        assert "Built by Akash Gajjar with AI-assisted development (Claude Code). Fictional airline, simulated data." in page.inner_text("body")
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", ["1440", "390"])
def test_no_forbidden_words_or_oem_names(site, browser, vp):  # noqa: F811
    ctx, page, problems = _open(browser, site, vp)
    try:
        text = _text(page)
        for w in FORBIDDEN:
            assert not re.search(rf"\b{re.escape(w)}\b", text, re.I), w
        assert not re.search(r"\b(NaN|undefined|null)\b", page.inner_text("body"))
    finally:
        ctx.close()


def test_hotspots_focusable_in_number_order_with_labels_1440(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "1440")
    try:
        spots = page.evaluate("""() => [...document.querySelectorAll('.cw-focus')].map((g) => ({ pn: g.dataset.pn, n: +g.dataset.n,
          tab: g.getAttribute('tabindex'), label: g.getAttribute('aria-label') || '' }))""")
        assert len(spots) >= 20
        assert [s["n"] for s in spots] == list(range(1, len(spots) + 1)), "DOM / tab order follows callout numbers"
        for s in spots:
            assert s["pn"] in PARTS and PARTS[s["pn"]]["applicability"] in ("NB", "both"), s
            assert s["tab"] == "0" and s["pn"] in s["label"] and len(s["label"]) > 20, s
        # every part has a drawing and a callout
        assert page.locator(".cw-part").count() == len(spots) == page.locator(".cw-callout").count()
        # real keyboard: Tab moves through the hotspots in number order and shows the card
        page.locator("body").focus()
        seen = []
        for _ in range(60):
            page.keyboard.press("Tab")
            n = page.evaluate("document.activeElement.classList.contains('cw-focus') ? +document.activeElement.dataset.n : null")
            if n is not None:
                seen.append(n)
                if len(seen) == 3:
                    break
        assert seen == [1, 2, 3], seen
        assert page.locator(".cw-card").is_visible()
        assert not problems, problems
    finally:
        ctx.close()


def test_hover_and_focus_show_card_with_parts_json_data(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "1440")
    try:
        pn = "GN-32-R014"
        p = PARTS[pn]
        page.locator(f'.cw-part[data-pn="{pn}"] .cw-body').hover(force=True)
        card = page.locator(".cw-card")
        card.wait_for(state="visible")
        txt = card.inner_text()
        assert pn in txt and "Nose wheel steering actuator" in txt
        assert f"About {round(p['annual_usage_qty'])} times a year" in txt
        assert f"{p['stock_total_p2']} in total" in txt and f"up from {p['stock_total_p0']}" in txt
        for st, v in p["stock_by_station"].items():
            if v:
                assert st in txt
        assert "Removing 2.5× faster than quoted" in txt  # A7 hero part
        assert "Repair time" in txt and "Network Plan" in txt
        href = card.locator("a.cw-link").get_attribute("href")
        assert href.endswith(f"#/parts?pn={pn}")
        # keyboard focus on a different hotspot swaps the card
        brake = "GN-32-R013"
        page.locator(f'.cw-focus[data-pn="{brake}"]').focus()
        page.wait_for_timeout(150)
        txt = card.inner_text()
        assert brake in txt and "Invalid recommendation — brakes are not changed outside the hub in this model." in txt
        # click → the part page
        page.locator(f'.cw-focus[data-pn="{brake}"]').press("Enter")
        page.wait_for_url(re.compile(rf"#/parts\?pn={brake}$"))
        assert not [x for x in problems if "lab/" in x], problems
    finally:
        ctx.close()


def test_mobile_list_is_tappable_and_shows_facts(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "390")
    try:
        items = page.locator(".cw-item")
        assert items.count() >= 20
        labels = page.evaluate("[...document.querySelectorAll('.cw-item')].map((b) => b.getAttribute('aria-label'))")
        assert all(lbl and re.match(r"^\d\d · ", lbl) for lbl in labels)
        nums = page.evaluate("[...document.querySelectorAll('.cw-item .cw-num')].map((n) => +n.textContent)")
        assert nums == list(range(1, len(nums) + 1))
        b = items.nth(0)
        pn = b.get_attribute("data-pn")
        b.focus()
        page.keyboard.press("Enter")
        assert b.get_attribute("aria-expanded") == "true"
        detail = page.locator(f'[id="cw-d-{pn}"]')
        assert detail.is_visible()
        assert f"{PARTS[pn]['stock_total_p2']} in total" in detail.inner_text()
        assert page.locator(f'.cw-part[data-pn="{pn}"].is-active').count() == 1
        box = b.bounding_box()
        assert box["height"] >= 44, "touch target"
        assert not problems, problems
    finally:
        ctx.close()


def test_generator_output_is_current():
    """cutaway.svg is generated (node docs/assets/svg/src/cutaway.mjs); it must carry the verbatim title-block line."""
    svg = (DOCS / "assets/svg/cutaway.svg").read_text()
    assert "GROUNDED NO MORE · GENERIC NARROWBODY · SCHEMATIC — NOT ENGINEERING DATA · NTS" in svg
    pns = set(re.findall(r'<g data-pn="([^"]+)" data-n="\d+"[^>]*class="cw-part"', svg))
    assert len(pns) >= 20 and pns <= set(PARTS)
    assert all(PARTS[pn]["applicability"] in ("NB", "both") for pn in pns)
