"""Browser tests for 02 Parts Intelligence (screens-B)."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


def _parts():
    files = json.loads((DOCS / "data/manifest.json").read_text()).get("files", [])
    name = "parts" if "parts" in files else "fixtures/parts"
    return json.loads((DOCS / f"data/{name}.json").read_text())


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("route", ["#/parts", "#/parts?ata=32", "#/parts?ata=all&cls=R", "#/parts?ata=49"])
def test_parts_renders_clean(site, browser, vp, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, vp)
    try:
        page.wait_for_selector(".pi-aircraft svg .ata-hotspot")
        audit(page, problems, min_frames=2)
        # 8 risk-coloured hotspots, each with a text risk label (not colour alone) + story ids
        assert page.locator(".pi-aircraft .ata-hotspot[class*='risk-']").count() == 8
        assert page.locator(".pi-aircraft .hs-risk").count() == 8
        assert page.locator('[data-story="parts-hotspot-32"]').count() == 1
        # accessible list alternative: one button per system, with a text pill
        assert page.locator(".pi-syslist button.pi-sys").count() == 8
        assert page.locator(".pi-syslist .pill").count() == 8
        assert page.locator('[data-story="parts-table"] tbody tr').count() >= 1
        assert page.locator(".disclaimer").count() == 1
    finally:
        ctx.close()


def test_select_system_filters_and_deep_links(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", "1440")
    try:
        parts = _parts()["parts"]
        n29 = sum(p["ata"] == "29" for p in parts)
        page.locator('.pi-syslist button[data-ata="29"]').click()
        page.wait_for_timeout(500)
        assert "ata=29" in page.url
        assert page.locator('[data-story="parts-table"] tbody tr').count() == n29
        assert page.locator(".pi-exploded .pi-xlabel").count() >= 1
        # hotspot click also selects
        page.locator('.pi-aircraft .ata-hotspot[data-ata="21"]').click()
        page.wait_for_timeout(400)
        assert "ata=21" in page.url
        assert page.locator('.pi-syslist button[data-ata="21"][aria-pressed="true"]').count() == 1
        # search narrows the table
        page.fill(".pi-search", "zzzz-no-match")
        assert page.locator('[data-story="parts-table"] tbody tr').count() == 0
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_part_drawer_deep_link(site, browser, vp):  # noqa: F811
    parts = {p["pn"]: p for p in _parts()["parts"]}
    pn = "GN-32-R014" if "GN-32-R014" in parts else next(iter(parts))
    ctx, page, problems = open_page(browser, site + f"#/parts?pn={pn}", vp)
    try:
        drawer = page.locator(".drawer.is-open")
        drawer.wait_for()
        page.wait_for_timeout(600)
        assert pn in drawer.inner_text()
        assert drawer.locator("figure.chart-frame .chip-prov").count() == 1
        assert drawer.locator(".chart-body svg").count() == 1
        assert drawer.locator(".strip-split").count() == 1  # train / selection split marked
        assert drawer.locator('a[href^="#/forecast"]').count() == 1
        if parts[pn]["cls"] == "R":
            assert drawer.locator('a[href^="#/rotables"]').count() == 1
        if parts[pn].get("planted"):
            assert drawer.locator(".pi-planted-banner").count() == 1
        overflow = page.evaluate("""() => [...document.querySelectorAll('.drawer *')].filter(e => !e.closest('svg') && !e.closest('.table-wrap') && !e.closest('.sr-only') && !e.children.length && e.textContent.trim() && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible').map(e => e.textContent.slice(0, 40))""")
        assert not overflow, overflow
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        assert "pn=" not in page.url
        assert not problems, problems
    finally:
        ctx.close()


def test_matrix_excludes_unclassified_and_states_training_window(site, browser):  # noqa: F811
    parts = _parts()["parts"]
    plotted = [p for p in parts if p.get("adi") is not None and p.get("cv2") is not None and p["demand_class"] != "insufficient_data"]
    # v2.1: the method cut-offs are Expert-mode detail; Simple keeps the training window
    ctx, page, problems = open_mode(browser, site + "#/parts?ata=all", "1440", "expert")
    try:
        frame = page.locator('[data-story="parts-adi-matrix"]')
        assert frame.locator("circle.pi-dot").count() == len(plotted)
        sub = frame.locator(".chart-subtitle").inner_text()
        assert "W0" in sub and "W77" in sub and "1.32" in sub and "0.49" in sub
        assert not problems, problems
    finally:
        ctx.close()


def test_hotspots_keyboard_reachable(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", "1440")
    try:
        spot = page.locator('.pi-aircraft .ata-hotspot[data-ata="34"] .pi-hs-btn')
        spot.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        assert "ata=34" in page.url
        assert not problems, problems
    finally:
        ctx.close()


# ----------------------------------------------------------------------------- design wave 2 (agent B)
OVERLAP_JS = r"""(sel) => {
  const els = [...document.querySelectorAll(sel)].map((e) => e.getBoundingClientRect()).filter((r) => r.width && r.height);
  const hits = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = els[i], b = els[j];
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) hits.push([i, j]);
  }
  return hits;
}"""


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_urgent_part_pip_and_callout(site, browser, vp):  # noqa: F811
    parts = _parts()["parts"]
    atas = ["21", "24", "27", "29", "32", "34", "36", "49"]
    with_urgent = [a for a in atas if any(p["ata"] == a and p["risk_level"] == "urgent" for p in parts)]
    in32 = sorted([p for p in parts if p["ata"] == "32"], key=lambda p: -p["risk_score"])
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", vp)
    try:
        # phones (< 480 px drawing): the top-part callout is an HTML line under the drawing (no room between badges)
        if vp == "390":
            page.wait_for_selector(".pi-air-note-btn")
            note = page.locator(".pi-air-note-btn")
            assert in32[0]["pn"] in note.inner_text() and f"is-{in32[0]['risk_level']}" in note.get_attribute("class")
            assert page.locator(".pi-aircraft .pi-hs-callout").count() == 0
            note.click()
            page.locator(".drawer.is-open").wait_for()
            assert in32[0]["pn"] in page.locator(".drawer.is-open").inner_text()
            assert not problems, problems
            return
        page.wait_for_selector(".pi-aircraft .pi-hs-callout")
        # a red pip with the urgent-PN count on every system that holds an urgent part, whatever the system level
        assert page.locator(".pi-aircraft .hs-pip").count() == len(with_urgent)
        for a in with_urgent:
            n = sum(p["ata"] == a and p["risk_level"] == "urgent" for p in parts)
            assert page.locator(f'.ata-hotspot[data-ata="{a}"] .hs-pip text').text_content() == str(n)
        # the selected system names its top-risk part with the part's own level
        call = page.locator('[data-story="parts-hotspot-32"] .pi-hs-callout')
        assert call.count() == 1 and in32[0]["pn"] in call.text_content()
        assert f"is-{in32[0]['risk_level']}" in call.get_attribute("class")
        # every aircraft label renders at >= 11 px on screen
        sizes = page.evaluate("""() => { const svg = document.querySelector('.pi-aircraft svg'); const k = svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
          return [...svg.querySelectorAll('.hs-risk, .hs-pip text, .pi-hs-text')].map((t) => parseFloat(t.style.fontSize) * k); }""")
        assert sizes and min(sizes) >= 10.9, sizes
        # risk words do not sit on other badges or leave the drawing
        assert not page.evaluate(OVERLAP_JS, ".pi-aircraft .hs-risk, .pi-aircraft .pi-hs-box")
        call.focus()
        page.keyboard.press("Enter")  # keyboard-operable (role=button, tabindex 0)
        page.locator(".drawer.is-open").wait_for()
        assert in32[0]["pn"] in page.locator(".drawer.is-open").inner_text()
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_exploded_labels_html_and_hot_part(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", vp)
    try:
        page.wait_for_selector(".pi-exploded .pi-xlabel")
        fs = page.evaluate("() => [...document.querySelectorAll('.pi-xlabel-pn, .pi-xlabel-desc, .pi-xlabel-risk')].filter((e) => e.offsetParent).map((e) => parseFloat(getComputedStyle(e).fontSize))")
        assert fs and min(fs) >= 11, fs
        assert page.locator(".pi-exploded svg .bp-label").first.is_hidden()
        assert not page.evaluate(OVERLAP_JS, ".pi-exploded .pi-xlabel")
        hot = page.locator(".pi-exploded .pi-xlabel.is-hot")
        if hot.count():
            assert page.locator(".pi-exploded svg .bp-part.pi-hot").count() == 1
            assert "risk" in hot.inner_text().lower()
        assert not problems, problems
    finally:
        ctx.close()


def test_mobile_table_keeps_risk_and_heatmap_headers_clear(site, browser):  # noqa: F811
    n32 = sum(p["ata"] == "32" for p in _parts()["parts"])
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", "390")
    try:
        stack = page.locator('[data-story="parts-table"] .data-table-stack')
        assert stack.is_visible()
        metrics = stack.locator(".dts-metric")
        assert metrics.count() == n32
        assert "risk" in metrics.first.inner_text().lower()
        assert not page.evaluate(OVERLAP_JS, ".pi-hm-col")
        assert page.locator(".pi-hm-key").is_visible()
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_matrix_labels_clear_and_reference_lines_neutral(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", vp)
    try:
        frame = page.locator('[data-story="parts-adi-matrix"]')
        assert frame.locator(".pi-cut").count() == 0  # no amber cut lines
        assert frame.locator(".gnm-ref-line").count() == 2
        assert frame.locator(".pi-quad-t").count() == 4
        # quadrant labels, cut-off labels and the annotation never overlap each other
        assert not page.evaluate(OVERLAP_JS, '[data-story="parts-adi-matrix"] .pi-quad-t, [data-story="parts-adi-matrix"] .gnm-ref-label, [data-story="parts-adi-matrix"] .gnm-annot-text, [data-story="parts-adi-matrix"] .gnm-annot-sub, [data-story="parts-adi-matrix"] .pi-axis-t')
        heads = page.evaluate("() => [...document.querySelectorAll('#view .chart-headline')].map((e) => e.textContent.trim())")
        assert heads and all(len(h) <= 90 for h in heads), heads
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave3_system_status_exploded_top_pn_and_neutral_zone(site, browser, vp):  # noqa: F811
    """Review 2: never a bare OK pill beside urgent PNs; exploded view draws the chapter's top-risk PN; the
    Croston/sparse zone is not teal; the callout never sits on another badge or risk word."""
    data = _parts()
    parts = data["parts"]
    ctx, page, problems = open_page(browser, site + "#/parts?ata=34", vp)
    try:
        for b in page.locator(".pi-sys").all():
            a = b.get_attribute("data-ata")
            n_urg = sum(p["ata"] == a and p["risk_level"] == "urgent" for p in parts)
            pill_t = b.locator(".pill").inner_text().strip().upper()
            if n_urg:
                assert pill_t != "OK", (a, pill_t)
                assert f"{n_urg} urgent" in b.locator(".pi-sys-urg").inner_text()
        top = sorted([p for p in parts if p["ata"] == "34"], key=lambda p: -p["risk_score"])[0]
        page.wait_for_selector(".pi-exploded .pi-xlabel")
        assert top["pn"] in page.locator(".pi-exploded").inner_text()
        fill = page.evaluate("getComputedStyle(document.querySelector('.pi-quad--sparse')).fill")
        assert "34, 199, 184" not in fill, fill
        if vp == "1440":
            hit = page.evaluate("""() => { const box = document.querySelector('.pi-hs-box'); if (!box) return 'none';
              const b = box.getBoundingClientRect();
              return [...document.querySelectorAll('.ata-hotspot .hs-badge > circle, .ata-hotspot .hs-risk')].filter((e) => {
                const r = e.getBoundingClientRect(); return r.left < b.right && b.left < r.right && r.top < b.bottom && b.top < r.bottom; }).length; }""")
            assert hit == 0, hit
        assert not problems, problems
    finally:
        ctx.close()



# ----------------------------------------------------------------------------- v2.1 (PAGE-2): plain English, A7, A9
import re  # noqa: E402

REPO = DOCS.parent


def open_mode(browser, url, vp, mode):  # noqa: F811
    """open_page with the reading mode preset in localStorage (Simple is the default)."""
    w, h = VIEWPORTS[vp]
    ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
    ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', '{mode}'); }} catch (e) {{}}")
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


SIMPLE_JARGON = [r"\bPNs?\b", r"\bADI\b", "CV²", "Syntetos", "material shortage exposure", r"\bP2 target", r"\bABC\b",
                 "Planted situation", "AOG h/yr", "log-scaled", r"\bP0\b", r"\bP1\b", r"\bP2\b", r"\bI125\b"]


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_modes_render_clean(site, browser, vp, mode):  # noqa: F811
    ctx, page, problems = open_mode(browser, site + "#/parts?ata=32", vp, mode)
    try:
        page.wait_for_selector(".pi-aircraft svg .ata-hotspot")
        audit(page, problems, min_frames=2)
        assert page.evaluate(f"document.body.classList.contains('mode-{mode}')")
        intro = page.locator('#view [data-role="intro3"]')
        assert intro.count() == 1 and intro.locator(".intro3-row").count() == 3
        assert page.locator('#view [data-role="scope"]').count() >= 2  # panel stats + table foot
        txt = page.inner_text("#view")
        if mode == "simple":
            hits = [p for p in SIMPLE_JARGON if re.search(p, txt)]
            assert not hits, hits
            assert page.locator("#view .term").count() >= 2
        else:
            assert "ATA 32" in txt and "material shortage exposure" in txt
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_v21_a7_escalation_in_panel_and_drawer(site, browser, vp):  # noqa: F811
    data = _parts()
    hero = [p for p in data["parts"] if p.get("escalation")]
    assert hero, "parts.json has no escalation flag"
    p = hero[0]
    text = p["escalation"]["text"]
    assert "escalate to reliability engineering and warranty review first" in text
    ctx, page, problems = open_mode(browser, site + f"#/parts?ata={p['ata']}", vp, "simple")
    try:
        block = page.locator('.pi-panel [data-role="escalation"]')
        assert block.count() == 1 and block.is_visible()
        assert block.locator('[data-role="escalation-text"]').inner_text().strip() == text
        # the panel's escalation block comes before the stats (prominent), and opens the drawer
        order = page.evaluate("() => { const a = document.querySelector('.pi-panel [data-role=escalation]'); const b = document.querySelector('.pi-panel .pi-pstats'); return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING); }")
        assert order
        block.locator(".pi-escalation-open").click()
        drawer = page.locator(".drawer.is-open")
        drawer.wait_for()
        dtext = drawer.locator('[data-role="escalation-text"]')
        assert dtext.count() == 1 and dtext.inner_text().strip() == text
        assert dtext.is_visible()
        assert dtext.bounding_box()["y"] < VIEWPORTS[vp][1], "escalation text is below the fold of the drawer"
        # only flagged parts carry it
        others = [x for x in data["parts"] if not x.get("escalation")]
        page.keyboard.press("Escape")
        page.goto(site + f"#/parts?pn={others[0]['pn']}")
        page.locator(".drawer.is-open").wait_for()
        page.wait_for_timeout(300)
        assert page.locator('.drawer.is-open [data-role="escalation"]').count() == 0
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_a9_invalid_brake_allocations_flagged_not_removed(site, browser, mode):  # noqa: F811
    data = _parts()
    inv = data["invalid_allocations"]
    text = data["invalid_allocation_text"]
    assert inv and text == "invalid recommendation — brakes are not changed outside the hub in this model"
    basis = data.get("stock_basis_id") or "P2"
    flagged = sorted({f["pn"] for f in inv})
    ctx, page, problems = open_mode(browser, site + "#/parts?ata=32", "1440", mode)
    try:
        # table: every flagged PN row carries a visible flag chip; the table foot lists all of them
        for pn in flagged:
            row = page.locator(f'[data-story="parts-table"] tbody tr[data-key="{pn}"]')
            assert row.locator('[data-role="alloc-flag"]').count() == 1, pn
        foot = page.locator('[data-story="parts-table"] [data-role="invalid-allocations"]')
        assert foot.count() == 1 and text in foot.inner_text()
        for f in inv:
            assert f["pn"] in foot.inner_text() and f["station"] in foot.inner_text()
        assert page.locator('.pi-panel [data-role="invalid-allocations"]').count() == 1
        # drawer: frozen station numbers unchanged, flagged stations marked
        byp = {p["pn"]: p for p in data["parts"]}
        for pn in flagged:
            page.goto(site + f"#/parts?pn={pn}")
            page.locator(".drawer.is-open").wait_for()
            page.wait_for_timeout(300)
            box = page.locator('.drawer.is-open [data-role="stock-by-station"]')
            items = box.locator(".pi-stock > li")
            got = {items.nth(i).locator(".mono").first.inner_text(): (int(items.nth(i).locator(".num").inner_text()), items.nth(i).get_attribute("data-flag")) for i in range(items.count())}
            assert {k: v[0] for k, v in got.items()} == byp[pn]["stock_by_station"], pn
            want = {f["station"] for f in inv if f["pn"] == pn and f["policy"] == basis}
            assert {k for k, v in got.items() if v[1] == "invalid_recommendation"} == want, pn
            assert text in box.locator('[data-role="invalid-allocations"]').inner_text()
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_fleet_filter_still_recomputes(site, browser):  # noqa: F811
    parts = _parts()["parts"]
    wb = [p for p in parts if not p.get("applicability") or p["applicability"] in ("both", "WB")]
    ctx, page, problems = open_mode(browser, site + "#/parts?ata=32", "1440", "simple")
    try:
        page.locator('[data-role="fleet-filter"]').get_by_role("radio", name="Widebody").click()
        page.wait_for_timeout(800)
        assert "fleet=WB" in page.url
        assert str(len(wb)) in page.locator('[data-role="all-label"]').inner_text()
        ata = page.evaluate("new URLSearchParams(location.hash.split('?')[1]).get('ata')")
        n = sum(p["ata"] == ata for p in wb)
        assert page.locator('[data-story="parts-table"] tbody tr').count() == n
        assert f"{n} parts" in page.locator(f'.pi-sys[data-ata="{ata}"] .pi-sys-meta').inner_text()
        assert "widebody" in page.locator(".pi-panel .card-kicker").inner_text().lower()
        # brake disclosure kept
        assert page.locator('[data-role="brake-note"]').count() == 1
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_readability_simple(site, browser):  # noqa: F811
    ctx, page, problems = open_mode(browser, site + "#/parts?ata=32", "1440", "simple")
    try:
        r = page.evaluate("import('./js/lib/readability.js').then(R => R.readability())")
        out = REPO / "reports/readability/parts-intelligence.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"view": "parts-intelligence", "mode": "simple", "grade": r["grade"], "maxSentenceWords": r["maxSentenceWords"],
                                   "words": r["words"], "sentences": r["sentences"], "longSentences": r["longSentences"]}, indent=2, ensure_ascii=False) + "\n")
        assert r["grade"] <= 9, r
        assert r["maxSentenceWords"] <= 25, r["longest"]
    finally:
        ctx.close()


# ----------------------------------------------------------------------------- v2.1 addendum: motion + keyboard
def test_addendum_keyed_joins_keep_marks_across_filters(site, browser):  # noqa: F811
    """ATA / fleet changes update the matrix and heatmap in place (keyed joins): the same DOM nodes survive."""
    ctx, page, problems = open_mode(browser, site + "#/parts?ata=32", "1440", "simple")
    try:
        page.evaluate("""() => { document.querySelectorAll('[data-story="parts-adi-matrix"] circle.pi-dot').forEach((c) => { c.__mark = 1; });
          document.querySelectorAll('.pi-hm-cell').forEach((c) => { c.__mark = 1; }); window.__svg = document.querySelector('[data-story="parts-adi-matrix"] svg'); }""")
        page.locator('.pi-syslist button[data-ata="27"]').click()
        page.wait_for_timeout(600)
        page.locator('[data-role="fleet-filter"]').get_by_role("radio", name="Narrowbody").click()
        page.wait_for_timeout(900)
        res = page.evaluate("""() => { const dots = [...document.querySelectorAll('[data-story="parts-adi-matrix"] circle.pi-dot')];
          return { same: document.querySelector('[data-story="parts-adi-matrix"] svg') === window.__svg, kept: dots.filter((c) => c.__mark).length, n: dots.length,
                   cells: [...document.querySelectorAll('.pi-hm-cell')].filter((c) => c.__mark).length, opac: dots.map((c) => getComputedStyle(c).opacity).filter((o) => o !== '1').length }; }""")
        nb = [p for p in _parts()["parts"] if (not p.get("applicability") or p["applicability"] in ("both", "NB")) and p.get("adi") is not None and p.get("cv2") is not None and p["demand_class"] != "insufficient_data"]
        assert res["same"], "matrix svg was redrawn from zero"
        assert res["n"] == len(nb) and res["kept"] == len(nb), res
        assert res["cells"] > 0 and res["opac"] == 0, res
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_addendum_keyboard_tab_order_and_escape(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_mode(browser, site + "#/parts?ata=32", vp, "simple")
    try:
        page.locator("#view").evaluate("(v) => { v.setAttribute('tabindex', '-1'); v.focus(); }")
        seq = []
        for _ in range(40):
            page.keyboard.press("Tab")
            seq.append(page.evaluate("""() => { const a = document.activeElement; if (!a || a === document.body) return null;
              const all = [...document.querySelectorAll('#view *')]; return { i: all.indexOf(a), inView: !!a.closest('#view'), tag: a.tagName }; }"""))
        assert all(s is not None for s in seq), "focus was lost to <body>"
        idx = [s["i"] for s in seq if s["inView"]]
        assert len(idx) >= 20
        backs = sum(1 for a, b in zip(idx, idx[1:]) if b < a)
        assert backs <= 1, f"tab order jumps backwards {backs} times: {idx}"
        # Enter on a focused system button selects it; Esc closes the drawer and focus returns into the page
        page.locator('.pi-syslist button[data-ata="21"]').focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        assert "ata=21" in page.url
        page.goto(site + "#/parts?pn=GN-32-R014")
        page.locator(".drawer.is-open").wait_for()
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        assert page.locator(".drawer.is-open").count() == 0
        assert page.evaluate("document.activeElement && document.activeElement !== document.body")
        assert not problems, problems
    finally:
        ctx.close()
