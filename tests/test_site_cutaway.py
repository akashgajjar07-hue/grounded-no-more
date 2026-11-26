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
LEADER_MAX = 320


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
        page.wait_for_timeout(2200)  # the sequenced draw-in finishes within 2 s
        assert not problems, problems
        assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth"), "horizontal scroll"
        svg = page.locator("#cutaway svg.cw-svg")
        assert svg.count() == 1
        assert svg.get_attribute("data-mode") == ("full" if vp == "1440" else "simple")
        assert "is-drawing" not in (svg.get_attribute("class") or "")
        assert "Built by Akash Gajjar with AI-assisted development (Claude Code). Fictional airline, simulated data." in page.inner_text("body")
        if vp == "1440":  # the whole poster sits above the fold at 1440×900
            box = svg.bounding_box()
            assert box["y"] >= 0 and box["y"] + box["height"] <= 900, box
    finally:
        ctx.close()


def test_resize_never_replays_the_draw_in(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "1440", reduced=False)
    try:
        page.wait_for_timeout(2200)
        page.set_viewport_size({"width": 1200, "height": 800})
        page.wait_for_timeout(150)
        assert "is-drawing" not in (page.locator("#cutaway svg.cw-svg").get_attribute("class") or "")
        page.set_viewport_size({"width": 390, "height": 844})  # crosses the phone breakpoint: new drawing, no replay
        page.wait_for_selector('#cutaway svg.cw-svg[data-mode="simple"]')
        page.wait_for_timeout(150)
        assert "is-drawing" not in (page.locator("#cutaway svg.cw-svg").get_attribute("class") or "")
        assert not problems, problems
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


def test_generic_dimensions_and_mono_callouts(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "1440")
    try:
        svgtext = page.evaluate("[...document.querySelectorAll('#cutaway svg text')].map((t) => t.textContent).join(' | ')")
        assert "LENGTH 36.8 m" in svgtext and "SPAN 33.9 m" in svgtext and "37.6" not in svgtext
        fams = page.evaluate("[...new Set([...document.querySelectorAll('.cw-name, .cw-num')].map((t) => getComputedStyle(t).fontFamily))]")
        assert all("Plex Mono" in f for f in fams), fams
        sizes = page.evaluate("[...document.querySelectorAll('.cw-name')].map((t) => t.getBoundingClientRect().height / t.querySelectorAll('tspan').length)")
        assert min(sizes) >= 11.5, sizes  # ≥ 12 px-ish names at 1440
        # elbow leaders: no two cross, none longer than the cap (viewBox units)
        leaders = page.evaluate("""[...document.querySelectorAll('.cw-leader')].map((p) => p.getAttribute('d').slice(1).split('L').map((s) => s.trim().split(/\\s+/).map(Number)))""")
        assert len(leaders) >= 20

        def cross(a, b, c, d):
            o = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])  # noqa: E731
            return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0
        for i, L in enumerate(leaders):
            length = sum(((L[k + 1][0] - L[k][0]) ** 2 + (L[k + 1][1] - L[k][1]) ** 2) ** 0.5 for k in range(len(L) - 1))
            assert length <= LEADER_MAX + 1, (i, length)
            for M in leaders[i + 1:]:
                for k in range(len(L) - 1):
                    for m in range(len(M) - 1):
                        assert not cross(L[k], L[k + 1], M[m], M[m + 1])
    finally:
        ctx.close()


def test_hotspots_focusable_in_number_order_and_tab_leaves_cleanly(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "1440")
    try:
        spots = page.evaluate("""() => [...document.querySelectorAll('.cw-focus')].map((g) => ({ pn: g.dataset.pn, n: +g.dataset.n,
          tab: g.getAttribute('tabindex'), label: g.getAttribute('aria-label') || '' }))""")
        assert len(spots) >= 20
        assert [s["n"] for s in spots] == list(range(1, len(spots) + 1)), "DOM / tab order follows callout numbers"
        for s in spots:
            assert s["pn"] in PARTS and PARTS[s["pn"]]["applicability"] in ("NB", "both"), s
            assert s["tab"] == "0" and s["pn"] in s["label"] and len(s["label"]) > 20, s
        assert page.locator(".cw-part").count() == len(spots) == page.locator(".cw-callout").count()
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
        # Tab from the last part leaves the drawing to the next page control (focus is never dropped to <body>)
        page.locator(f'.cw-focus[data-n="{len(spots)}"]').focus()
        page.keyboard.press("Tab")
        page.wait_for_timeout(250)
        where = page.evaluate("() => { const a = document.activeElement; return { body: a === document.body, inSvg: !!a.closest('svg'), inCard: !!a.closest('.cw-card'), text: a.textContent.trim().slice(0, 40) }; }")
        assert not where["body"] and not where["inSvg"] and not where["inCard"], where
        assert not problems, problems
    finally:
        ctx.close()


def test_hover_shows_docked_card_with_parts_json_data(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "1440")
    try:
        pn = "GN-32-R014"
        p = PARTS[pn]
        page.locator(f'.cw-part[data-pn="{pn}"] .cw-body').hover(force=True)
        card = page.locator(".cw-card")
        card.wait_for(state="visible")
        txt = card.inner_text()
        assert pn in txt and "Nose wheel steering actuator" in txt
        assert f"About {round(p['annual_usage_qty'])} a year" in txt
        assert f"{p['stock_total_p2']} in total" in txt and f"up from {p['stock_total_p0']}" in txt
        for st, v in p["stock_by_station"].items():
            if v:
                assert st in txt
        assert "Removing 2.5× faster than quoted" in txt  # A7 hero part (line-clamped, full text in the DOM)
        assert "Repair time" in txt and "Network Plan" in txt
        assert card.locator("a.cw-link").get_attribute("href").endswith(f"#/parts?pn={pn}")
        # docked: compact, inside the viewport, never over the active part or its label; connector drawn
        geo = page.evaluate(f"""() => {{
          const c = document.querySelector('.cw-card').getBoundingClientRect();
          const part = document.querySelector('.cw-part[data-pn="{pn}"] .cw-body').getBoundingClientRect();
          const lab = document.querySelector('.cw-callout[data-pn="{pn}"] .cw-hitlabel').getBoundingClientRect();
          const hit = (a, b) => !(a.right < b.left || b.right < a.left || a.bottom < b.top || b.bottom < a.top);
          return {{ h: c.height, w: c.width, bottom: c.bottom, right: c.right, vw: innerWidth, vh: innerHeight, overPart: hit(c, part), overLabel: hit(c, lab),
                   scroll: document.querySelector('.cw-card').scrollHeight - document.querySelector('.cw-card').clientHeight,
                   conn: +(document.querySelector('.cw-conn')?.getAttribute('opacity') || 0),
                   leaderLit: !!document.querySelector('.cw-callout.is-active') }};
        }}""")
        assert geo["h"] <= 360 and geo["w"] <= 340, geo
        assert geo["bottom"] <= geo["vh"] and geo["right"] <= geo["vw"], geo
        assert not geo["overPart"] and not geo["overLabel"], geo
        assert geo["scroll"] <= 2, f"card content clipped: {geo}"
        assert geo["conn"] == 0 and geo["leaderLit"], geo  # no connector across the drawing: the active leader + tag glow instead
        # the active part's system runs light up (hydraulics for the steering actuator)
        assert page.locator('.cw-sys[data-sys="hyd"].is-on').count() == 1
        assert page.locator('.cw-sys.is-on').count() == 1
        # keyboard focus swaps the card; the brake carries the A9 flag; Enter opens the part page
        brake = "GN-32-R013"
        page.locator(f'.cw-focus[data-pn="{brake}"]').focus()
        page.wait_for_timeout(150)
        txt = card.inner_text()
        assert brake in txt and "Invalid recommendation — brakes are not changed outside the hub in this model." in txt
        page.locator(f'.cw-focus[data-pn="{brake}"]').press("Enter")
        page.wait_for_url(re.compile(rf"#/parts\?pn={brake}$"))
        assert not [x for x in problems if "lab/" in x], problems
    finally:
        ctx.close()


def test_plural_spare_wording(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "1440")
    try:
        recs = page.evaluate("""async () => { const m = await import('./cutaway.js');
          const base = { pn: 'GN-00-R000', desc: 'Test part', cls: 'R', ata: '00', annual_usage_qty: 1, stock_by_station: { AUH: 1 }, exceptions: [] };
          return [m.partFacts({ ...base, stock_total_p0: 0, stock_total_p2: 1 }).rec[0], m.partFacts({ ...base, stock_total_p0: 1, stock_total_p2: 2 }).rec[0]]; }""")
        assert "holds 1 spare," in recs[0] and "1 spares" not in recs[0]
        assert "holds 2 spares," in recs[1]
    finally:
        ctx.close()


def test_mobile_zoned_list_dots_and_inset(site, browser):  # noqa: F811
    ctx, page, problems = _open(browser, site, "390")
    try:
        assert page.locator(".cw-lede-phone").is_visible() and "Tap a number or a row" in page.inner_text(".cw-head")
        heads = page.evaluate("[...document.querySelectorAll('.cw-zone-h')].map((h) => h.textContent)")
        assert len(heads) >= 6 and "Landing gear" in heads
        items = page.locator(".cw-item")
        assert items.count() >= 20
        labels = page.evaluate("[...document.querySelectorAll('.cw-item')].map((b) => b.getAttribute('aria-label'))")
        assert all(lbl and re.match(r"^\d\d · ", lbl) for lbl in labels)
        # number dots on the drawing: one per part, mono numerals ≥ 9 px
        dots = page.evaluate("[...document.querySelectorAll('.cw-ndot text')].map((t) => t.getBoundingClientRect().height)")
        assert len(dots) == items.count() and min(dots) >= 9, dots
        # 44 CSS px tap circles under every dot, and no two badges overlap
        hits = page.evaluate("[...document.querySelectorAll('.cw-ndot-hit')].map((c) => c.getBoundingClientRect().width)")
        assert len(hits) == len(dots) and min(hits) >= 43.5, hits
        circ = page.evaluate("[...document.querySelectorAll('.cw-ndot')].map((g) => { const r = g.querySelector('circle').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, r.width / 2]; })")
        for i, a in enumerate(circ):
            for b2 in circ[i + 1:]:
                assert ((a[0] - b2[0]) ** 2 + (a[1] - b2[1]) ** 2) ** 0.5 >= a[2] + b2[2] - 0.5
        # the drawing fills the width
        fig = page.locator(".cw-mfig svg").bounding_box()
        assert fig["width"] >= 340
        b = items.nth(0)
        pn = b.get_attribute("data-pn")
        b.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        assert b.get_attribute("aria-expanded") == "true"
        detail = page.locator(f'[id="cw-d-{pn}"]')
        assert detail.is_visible()
        assert f"{PARTS[pn]['stock_total_p2']} in total" in detail.inner_text()
        assert page.locator(f'.cw-part[data-pn="{pn}"].is-active').count() == 1
        assert page.locator(".cw-inset").is_visible()
        assert "is-on" in (page.locator(".cw-caption").get_attribute("class") or "")  # zone caption on the sticky figure
        assert b.bounding_box()["height"] >= 44, "touch target"
        # tapping a number dot selects that part
        dpn = next(d for d in page.evaluate("[...document.querySelectorAll('.cw-ndot')].map((d) => d.dataset.pn)") if d != pn)
        dot = page.locator(f'.cw-ndot[data-pn="{dpn}"]')
        dot.locator("circle").click(force=True)
        page.wait_for_timeout(300)
        assert page.locator(f'.cw-item[data-pn="{dpn}"]').get_attribute("aria-expanded") == "true"
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
    assert 'class="cw-sys"' in svg and "url(#cw-hatch)" in svg
