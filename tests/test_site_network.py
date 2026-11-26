"""05 Network Positioning: browser checks (routes, station deep links, replay, metric toggle, both viewports)."""
from __future__ import annotations

import pytest

from _sitefx_c import VIEWPORTS, assert_clean, open_route, serve_docs

pytestmark = pytest.mark.browser
playwright = pytest.importorskip("playwright.sync_api")

ROUTES = ["#/network", "#/network?station=BOM", "#/network?station=AUH", "#/network?station=BOM&metric=fill_rate"]


@pytest.fixture(scope="module")
def site():
    with serve_docs() as base, playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b, base
        b.close()


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
@pytest.mark.parametrize("route", ROUTES)
def test_route_clean(site, route, viewport):
    b, base = site
    ctx, page, problems = open_route(b, base, route, viewport)
    try:
        assert_clean(page, problems, f"{route}@{viewport}")
        for hook in ["map", "network-replay", "network-policy", "network-hub-finding"]:
            assert page.locator(f'[data-story="{hook}"]').count() >= 1, hook
        if "station=" in route:
            st = route.split("station=")[1].split("&")[0]
            assert page.locator(".np-drill-code").inner_text().strip() == st
            assert page.locator(f'.np-picker button[data-station="{st}"]').get_attribute("aria-pressed") == "true"
            assert page.locator(f'[data-story="network-{st.lower()}"]').count() == 1
    finally:
        ctx.close()


def test_station_select_updates_url_and_replay_runs(site):
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network", "1440")
    try:
        btn = page.locator('.np-picker button[data-station="BOM"]')
        btn.focus()
        page.keyboard.press("Enter")
        assert "station=BOM" in page.url
        assert page.locator(".np-drill-code").inner_text().strip() == "BOM"
        page.get_by_role("button", name="Replay transfer").click()
        page.wait_for_timeout(1200)  # reduced motion: arcs flash for ~600 ms
        assert page.get_by_role("button", name="Replay transfer").is_enabled()
        radios = page.locator('[data-story="network-policy"] [role="radio"]')
        for i in range(radios.count()):
            radios.nth(i).click()
            page.wait_for_timeout(150)
        assert_clean(page, problems, "interactions")
    finally:
        ctx.close()


def test_map_nodes_keyboard_reachable(site):
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network", "1440")
    try:
        node = page.locator('svg.map-main g[data-station="JED"]')
        node.focus()
        page.keyboard.press("Enter")
        assert "station=JED" in page.url
        label = node.get_attribute("aria-label")
        assert "exposure" in label.lower()   # wave A wording: material shortage exposure
        assert not problems, problems
    finally:
        ctx.close()


FRAME_JS = """async () => {
  const { lintAccents } = await import('./js/charts/theme.js');
  return [...document.querySelectorAll('#view .chart-frame')].map((f) => ({
    headline: (f.querySelector('.chart-headline')?.textContent || '').trim(),
    accents: lintAccents(f),
  }));
}"""


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_wave2_design_fixes(site, viewport):
    """Design wave 2: headlines <= 90, <= 2 accents per chart, sub-labels without bullets, visible chip row (v2.1), stacked table."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", viewport)
    try:
        frames = page.evaluate(FRAME_JS)
        for f in frames:
            assert len(f["headline"]) <= 90, f["headline"]
            assert len(f["accents"]) <= 2, f
        subs = page.eval_on_selector_all("svg.map-main .map-label-sub", "els => els.map(e => e.textContent)")
        assert all("●" not in t and "▲" not in t for t in subs), subs
        # v2.1 addendum: the station chip row is visible (pointer + keyboard), not hidden until focus
        picker = page.locator(".np-picker")
        assert picker.bounding_box()["width"] > 40
        assert page.locator(".np-picker button").count() == 7
        # no copper on the emergency encodings (legend, replay dots)
        legend = page.locator(".np-legend").inner_html().lower()
        assert "196, 127, 82" not in legend and "#c47f52" not in legend
        fills = page.eval_on_selector_all('[data-story="network-replay"] .np-ev circle', "els => els.map(e => (e.getAttribute('fill') || '').toLowerCase())")
        assert "#c47f52" not in fills
        if viewport == "390":
            # the decision column (projected risk) stays visible on a phone
            assert page.locator('.data-table-stack .dts-metric--pill[aria-label^="Exposure"]').count() >= 1
        assert not problems, problems
    finally:
        ctx.close()


def test_ci_clamp_note(site):
    """Negative CI lower ends are drawn at 0 and the clamp is stated (drill table + compare subtitle)."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", "1440")
    try:
        clamped = page.evaluate("""async () => {
          const n = await (await fetch('./data/network.json')).json();
          return (n.policy_compare || []).some((r) => Object.entries(r).some(([k, v]) =>
            (Array.isArray(v) && /_ci$/.test(k) && v[0] < 0) || (/_(ci_)?lo$/.test(k) && v < 0) || (v && typeof v === 'object' && !Array.isArray(v) && (v.ci_lo ?? v.lo) < 0)));
        }""")
        sub = page.locator('[data-story="network-policy"] .chart-subtitle').get_attribute("title") or ""
        if clamped:
            assert "drawn at 0" in sub
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_wave3_network(site, viewport):
    """Design wave 3: replay ticks read "200 h", the riskiest outstation never wears an OK pill,
    the lowest-AOG policy row and the hub bars are not teal."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", viewport)
    try:
        res = page.evaluate("""async () => {
          const n = await (await fetch('./data/network.json')).json();
          const outs = n.stations.filter((s) => s.role !== 'hub').sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0));
          const ticks = [...document.querySelectorAll('[data-story="network-replay"] .tick text')].map((t) => t.textContent.trim());
          const drillPill = document.querySelector('[data-story^="network-"] .np-drill-head .pill');
          const best = document.querySelector('.np-pol tr.is-best td');
          const shareTeal = [...document.querySelectorAll('[data-story="network-hub-finding"] svg rect')].filter((r) => (r.getAttribute('fill') || '').toLowerCase() === '#22c7b8').length;
          return { top: outs[0]?.station, ticks, pillCls: drillPill?.className || '', pillTxt: drillPill?.textContent || '', bestColor: best ? getComputedStyle(best).color : '', shareTeal };
        }""")
        assert res["ticks"] and not any(t.startswith("h ") for t in res["ticks"]), res["ticks"]
        if res["top"] == "BOM":
            assert "pill--ok" not in res["pillCls"], res
            assert "LOW" not in res["pillTxt"]
        assert res["bestColor"] and "34, 199, 184" not in res["bestColor"] and "127, 243, 230" not in res["bestColor"]
        assert res["shareTeal"] == 0
        assert not problems, problems
    finally:
        ctx.close()


# ----------------------------------------------------------------------------- v2.1 (PAGE-3): modes, names, shares, scope
def set_mode(page, mode):
    page.evaluate(f"import('./js/lib/mode.js').then((m) => m.setMode('{mode}'))")
    page.wait_for_selector('html[data-ready="true"]', timeout=15000)
    page.wait_for_timeout(900)
    assert page.evaluate("document.body.classList.contains('mode-' + %r)" % mode)


TEXT_JS = """() => { const v = document.querySelector('#view');
  const hid = [...v.querySelectorAll('.term-expert, .mono-tag')]; hid.forEach((e) => { e.dataset.t = e.textContent; e.textContent = ''; });
  const t = v.innerText; hid.forEach((e) => { e.textContent = e.dataset.t; }); return t; }"""


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
@pytest.mark.parametrize("mode", ["simple", "expert"])
def test_v21_modes(site, mode, viewport):
    import re
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", viewport)
    try:
        if mode == "expert":
            set_mode(page, "expert")
        assert_clean(page, problems, f"{mode}@{viewport}")
        assert page.locator('[data-role="intro3"]').count() == 1
        # scope line under every downtime block: map, hub finding, station drill, compare chart, station table
        assert page.locator('#view [data-role="scope"]').count() >= 5
        assert page.locator('[data-role="share-note"]').count() == 1
        text = page.evaluate(TEXT_JS)
        assert "Network Plan" in text and "Simple Rulebook" in text and "Each Airport for Itself" in text
        if mode == "simple":
            assert not re.search(r"\b(P0|P1|P2|I125)\b", text), re.findall(r".{30}\b(?:P0|P1|P2|I125)\b.{10}", text)[:5]
            lede = page.locator(".page-head .lede").inner_text()
            assert "other airports (outstations)" in lede
            assert "AOG" not in text and "outstation" not in text.replace("(outstation", "")
        else:
            assert re.search(r"\bP2\b", text)
    finally:
        ctx.close()


def test_v21_station_shares_one_denominator(site):
    """Every station share uses the same denominator: P0 holdout AOG h of the station / sum over all stations.
    Pills in the table, the drill-down fact and the hub-finding headline agree, and the shares sum to ~100%."""
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", "1440")
    try:
        res = page.evaluate("""async () => {
          const n = await (await fetch('./data/network.json')).json();
          const tot = n.stations.reduce((a, s) => a + s.aog_hours_by_policy.P0.mean, 0);
          const exp = Object.fromEntries(n.stations.map((s) => [s.station, Math.round(100 * s.aog_hours_by_policy.P0.mean / tot)]));
          const hub = n.stations.find((s) => s.role === 'hub');
          const pills = [...document.querySelectorAll('.data-table tbody tr, .dts-row')].map((r) => r.innerText).filter(Boolean);
          const fact = [...document.querySelectorAll('.np-fact')].find((f) => /share of grounded time/i.test(f.innerText))?.innerText || '';
          const head = document.querySelector('[data-story="network-hub-finding"] .chart-headline').textContent;
          return { exp, pills, fact, head, hubOut: 100 - exp[hub.station] };
        }""")
        for st, pct in res["exp"].items():
            assert any(st in r and f"{pct}% of all" in r for r in res["pills"]), (st, pct, res["pills"])
        assert f"{res['exp']['BOM']}% of all" in res["fact"]
        assert f"{res['hubOut']}%" in res["head"]
        assert abs(sum(res["exp"].values()) - 100) <= 3
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_v21_readability_simple(site, viewport):
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network?station=BOM", viewport)
    try:
        r = page.evaluate("import('./js/lib/readability.js').then((R) => R.readability())")
        assert r["grade"] <= 9, r
        assert r["maxSentenceWords"] <= 25, r["longSentences"]
    finally:
        ctx.close()


# ----------------------------------------------------------------------------- v2.1 addendum: keyboard walk
KB_TARGETS_JS = r"""() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !e.closest('[hidden], details:not([open]) > :not(summary), [inert]'); };
  const sel = 'a[href], button:not([disabled]), input:not([type=hidden]):not([disabled]), select, textarea, summary, [tabindex]:not([tabindex="-1"])';
  return [...document.querySelectorAll('#view ' + sel.split(', ').join(', #view '))].filter(vis).filter((e) => e.tabIndex >= 0).length;
}"""
KB_STEP_JS = r"""() => {
  const a = document.activeElement;
  if (!a || a === document.body) return { where: 'body' };
  const inView = !!a.closest('#view');
  if (!window.__kbSeen) window.__kbSeen = [];
  let order = 'ok';
  const last = window.__kbSeen.at(-1);
  if (inView && last && last.isConnected && (last.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_PRECEDING)) order = 'back';
  if (inView) window.__kbSeen.push(a);
  const cs = getComputedStyle(a);
  const ring = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== 'none' || a.matches('g, svg *');
  return { where: inView ? 'view' : 'shell', order, ring, tag: a.tagName, label: (a.getAttribute('aria-label') || a.textContent || '').trim().slice(0, 40) };
}"""


def keyboard_walk(page, max_tabs=400):
    """Tab from the top through the whole page: focus never lost to <body> after entering the view, view controls
    visited in document order, every visible view control reached, focus ring visible, and the walk leaves the view
    (no trap). Returns (visited_in_view, expected)."""
    expected = page.evaluate(KB_TARGETS_JS)
    page.evaluate("window.__kbSeen = []; document.activeElement?.blur(); window.scrollTo(0, 0)")
    seen_view, left_after_view, problems = 0, False, []
    for _ in range(max_tabs):
        page.keyboard.press("Tab")
        st = page.evaluate(KB_STEP_JS)
        if st["where"] == "view":
            seen_view += 1
            if st["order"] == "back":
                problems.append(f"focus moved backwards to {st['tag']} {st['label']}")
            if not st["ring"]:
                problems.append(f"no visible focus ring on {st['tag']} {st['label']}")
        elif seen_view and st["where"] in ("shell", "body"):
            left_after_view = True
            break
    unique = page.evaluate("new Set(window.__kbSeen).size")
    assert left_after_view, "keyboard focus trapped inside the view"
    assert not problems, problems[:5]
    assert unique >= expected, f"Tab reached {unique} of {expected} view controls"
    return unique, expected


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_v21_keyboard(site, viewport):
    b, base = site
    ctx, page, problems = open_route(b, base, "#/network", viewport)
    try:
        keyboard_walk(page, max_tabs=600)
        # Enter on a map node selects it and opens the station drawer; Esc closes it and focus is not lost
        node = page.locator('svg.map-main g[data-station="CAI"]')
        node.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        assert page.locator(".drawer.is-open").count() == 1
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        assert page.locator(".drawer.is-open").count() == 0
        assert page.evaluate("document.activeElement && document.activeElement !== document.body")
        # metric radios work from the keyboard (Space)
        r = page.locator('[data-story="network-policy"] [role="radio"][data-value="fill_rate"]')
        r.focus()
        page.keyboard.press(" ")
        page.wait_for_timeout(400)
        assert r.get_attribute("aria-checked") == "true" and "metric=fill_rate" in page.url
        assert not problems, problems
    finally:
        ctx.close()


def test_v21_motion_metric_morph(site):
    """The station comparison morphs between metrics: dots interpolate, the metric control gets a sliding thumb."""
    b, base = site
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="no-preference")
    page = ctx.new_page()
    try:
        page.goto(f"{base}/index.html#/network")
        page.wait_for_selector('html[data-ready="true"]', timeout=15000)
        page.wait_for_timeout(1200)
        assert page.locator('[data-story="network-policy"] .seg .seg-thumb').count() == 1
        js = "() => [...document.querySelectorAll('[data-story=network-policy] .np-cmp-pt circle')].map((c) => +c.getAttribute('cx'))"
        before = page.evaluate(js)
        page.locator('[data-story="network-policy"] [role="radio"][data-value="fill_rate"]').click()
        page.wait_for_timeout(60)
        mid = page.evaluate(js)
        page.wait_for_timeout(700)
        after = page.evaluate(js)
        assert len(before) == len(after) == len(mid)
        moved = [i for i in range(len(after)) if abs(after[i] - before[i]) > 2]
        assert moved and any(abs(mid[i] - after[i]) > 0.5 and abs(mid[i] - before[i]) > 0.5 for i in moved)
    finally:
        ctx.close()
