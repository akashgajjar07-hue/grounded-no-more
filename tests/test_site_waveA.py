"""Design wave A (external design review): shell, hero copy, typography, colour, aircraft archetypes, About route."""
from __future__ import annotations

import json
import re
import urllib.request

import pytest

from _sitefx import DOCS, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

ROUTES = ["#/mission", "#/parts?ata=32&pn=GN-32-R014", "#/forecast", "#/rotables", "#/network?station=BOM", "#/capital",
          "#/aog?incident=AOG-0001", "#/actions", "#/method", "#/about"]

# visible text that carries meaning must be fully opaque (no opacity, no alpha colour)
OPACITY_JS = r"""() => {
  const out = [];
  const alphaOf = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return 1; const p = m[1].split(/[ ,\/]+/).filter(Boolean); return p.length > 3 ? parseFloat(p[3]) : 1; };
  const skip = (el) => el.closest('.sr-only, [hidden], [aria-hidden="true"], details:not([open]) > :not(summary), .tooltip, .story, button[disabled], .hs-zone-t, .bp-callout, .bp-frameset, .bp-tblock, .bp-dims, .drawer:not(.is-open)');
  for (const root of [document.querySelector('#view'), document.querySelector('.rail'), document.querySelector('.topbar')].filter(Boolean)) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const el = n.parentElement;
      if (!el || !n.textContent.trim() || skip(el)) continue;
      const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') continue;
      let op = 1;
      for (let a = el; a && a !== document.documentElement; a = a.parentElement) op *= parseFloat(getComputedStyle(a).opacity);
      if (el instanceof SVGElement) { const fo = parseFloat(cs.fillOpacity); if (!Number.isNaN(fo)) op *= fo; }
      const col = el instanceof SVGElement ? (cs.fill || '') : cs.color;
      const al = /^url|none/.test(col) ? 1 : alphaOf(col);
      if (op < 0.995 || al < 0.995) out.push(`${(el.getAttribute('class') || el.tagName).toString().slice(0, 40)} op=${op.toFixed(2)} a=${al.toFixed(2)}: ${n.textContent.trim().slice(0, 30)}`);
    }
  }
  return [...new Set(out)];
}"""

TYPE_JS = r"""() => {
  const px = (e) => parseFloat(getComputedStyle(e).fontSize);
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !e.closest('.sr-only, details:not([open]) > :not(summary)'); };
  const small = [...document.querySelectorAll('#view .data-table td, #view .dts-row, #view .dts-row *, #view .pill, #view .pill *')]
    .filter((e) => vis(e) && [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()))
    .filter((e) => px(e) < 12.95).map((e) => `${e.className}: ${px(e)} ${e.textContent.trim().slice(0, 24)}`);
  const monoLabels = [...document.querySelectorAll('#view .card-kicker, #view .kpi-label, .nav-label, #view .field-label, #view .data-table thead th, #view .chart-headline, #view .card-title, #view .eyebrow, .crumb-group')]
    .filter((e) => vis(e) && /Plex Mono/i.test(getComputedStyle(e).fontFamily)).map((e) => `${e.className}: ${e.textContent.trim().slice(0, 24)}`);
  const upperPills = [...document.querySelectorAll('#view .pill')].filter((e) => vis(e) && getComputedStyle(e).textTransform === 'uppercase').length;
  return { small: [...new Set(small)].slice(0, 12), monoLabels: [...new Set(monoLabels)].slice(0, 12), upperPills };
}"""

BANNED = ["aircraft risk score", "aircraft ready", "approved to fly", "live data"]


@pytest.mark.parametrize("route", ROUTES)
def test_text_opacity_type_and_wording(site, browser, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, "1440")
    try:
        assert not page.evaluate(OPACITY_JS), page.evaluate(OPACITY_JS)
        t = page.evaluate(TYPE_JS)
        assert not t["small"], f"table / decision text under 13 px: {t['small']}"
        assert not t["monoLabels"], f"labels set in Plex Mono (mono is for codes and numbers only): {t['monoLabels']}"
        assert t["upperPills"] == 0
        text = page.locator("body").inner_text().lower()
        assert not [w for w in BANNED if w in text]
        # one persistent Simulation indicator; no visible per-card SIMULATED badges outside Data & Method
        assert page.locator("#sim-indicator").count() == 1
        if not route.startswith("#/method"):
            vis = page.evaluate("[...document.querySelectorAll('#view .chip-prov--simulated')].filter((e) => e.getBoundingClientRect().width > 2).length")
            assert vis == 0
        assert not problems, problems
    finally:
        ctx.close()


def test_opacity_audit_catches_faded_text(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", "1440")
    try:
        page.evaluate("""() => { const v = document.querySelector('#view');
          const a = document.createElement('p'); a.className = 'bad-op'; a.style.opacity = '0.6'; a.textContent = 'faded'; v.append(a);
          const b = document.createElement('p'); b.className = 'bad-rgba'; b.style.color = 'rgba(242,246,250,0.5)'; b.textContent = 'washed'; v.append(b); }""")
        found = " ".join(page.evaluate(OPACITY_JS))
        assert "bad-op" in found and "bad-rgba" in found
    finally:
        ctx.close()


def test_navigation_groups_and_shortcuts(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        groups = page.evaluate("[...document.querySelectorAll('.nav-group')].map((g) => [g.querySelector('.nav-label').textContent, [...g.querySelectorAll('.nav-item')].map((i) => i.dataset.route)])")
        assert groups == [["Operations", ["mission", "actions", "aog"]], ["Material intelligence", ["parts", "forecast", "rotables"]],
                          ["Strategic planning", ["network", "capital"]], ["Project", ["tour", "method", "about"]]], groups
        for key, route in [("4", "rotables"), ("8", "actions"), ("0", "method"), ("1", "mission")]:
            page.locator("body").press(key)
            page.wait_for_function(f"location.hash.startsWith('#/{route}') && document.documentElement.dataset.ready === 'true'")
        page.keyboard.press("?")
        page.wait_for_selector(".modal")
        help_text = page.locator(".modal").inner_text()
        assert "Rotable & Repair" in help_text and "Data & Method" in help_text
        page.keyboard.press("Escape")
        # deep links are stable
        page.goto(site + "#/parts?ata=32&pn=GN-32-R014")
        page.wait_for_selector(".drawer.is-open", timeout=8000)
        assert not problems, problems
    finally:
        ctx.close()


def test_mission_hero_copy_and_fold(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/mission", "1440")
    try:
        hero = page.locator('[data-story="mission-hero"]')
        assert page.locator(".mc-title").inner_text().strip() == "GROUNDED NO MORE"
        assert page.locator(".mc-tagline").inner_text().strip() == "The right spare. The right station. Before the aircraft needs it."
        assert page.locator(".mc-oneline").inner_text().strip() == "An aviation materials-planning simulation connecting intermittent-demand forecasting, rotable repair planning and inventory optimisation to aircraft readiness."
        # wave C: the scope names the modelled part-number universe (count read from parts.json)
        n_pn = len(json.load(open(DOCS / "data" / "parts.json"))["parts"])
        assert page.locator(".mc-scope").inner_text().strip() == f"40 aircraft · 2 fleet families · 7 stations · {n_pn} AOG-critical part numbers · Independent simulation"
        assert page.locator(".mc-byline").inner_text().strip() == "Portfolio project by Akash Gajjar, MSc Supply Chain Management, University of Liverpool"
        assert hero.locator("a", has_text="Methodology").get_attribute("href") == "#/method"
        hh = hero.bounding_box()["height"]
        assert 240 <= hh <= 305, hh  # wave C: the scope line now names the part-number universe
        tops = page.evaluate("[...document.querySelectorAll('[data-story=\"mission-kpis\"] .kpi')].map((k) => Math.round(k.getBoundingClientRect().top))")
        assert len(tops) == 4 and len(set(tops)) == 1, tops
        prio_top = page.locator('[data-story="mission-actions"]').bounding_box()["y"]
        assert prio_top < 900, prio_top
        assert page.locator('[data-story="mission-actions"] .card-kicker').inner_text().lower().startswith("today")
        # the comparison is simple bars (no CI whiskers here)
        assert page.locator('[data-story="mission-compare"] svg rect').count() >= 4
        hero.locator("button", has_text="60-second tour").click()
        page.wait_for_selector(".story .story-card")
        assert not problems, problems
    finally:
        ctx.close()


def test_aircraft_archetypes(site, browser):  # noqa: F811
    nb = (DOCS / "assets/svg/aircraft-narrowbody.svg").read_text()
    wb = (DOCS / "assets/svg/aircraft-widebody.svg").read_text()
    for svg in (nb, wb):
        assert sorted(set(re.findall(r'id="ata-(\d\d)"', svg))) == ["21", "24", "27", "29", "32", "34", "36", "49"]
        assert "indicative zone" in svg.lower() and "data-compact-viewbox" in svg
        assert "#B9C8D6" in svg and "#334C61" in svg
    assert "bleed" not in wb.lower()
    ctx, page, problems = open_page(browser, site + "#/parts?ata=32", "1440")
    try:
        assert page.locator('[data-story="aircraft"] svg[data-archetype="narrowbody"]').count() == 1
        page.goto(site + "#/mission")
        page.wait_for_selector('[data-story="mission-aircraft"] svg[data-archetype="narrowbody"] .ata-hotspot')
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", ["1440", "390"])
def test_about_route(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/about", vp)
    try:
        assert page.locator('.nav-item[data-route="about"]').count() == 1
        assert page.locator('[data-role="ai-note"]').inner_text().strip() == "Built with AI-assisted development; analysis, decisions and validation reviewed by the author."
        qs = [t.strip() for t in page.locator('[data-role="why-questions"] .ab-q-t').all_inner_texts()]
        assert qs == ["Intermittent demand handling", "Why maximum local stock isn’t optimal", "How TAT drives float", "Why point accuracy isn’t enough",
                      "How the optimiser balances readiness and capital", "What data I’d request from a real airline"]
        # wave C: an intentional list of the questions only (no drafted answers), with the one-line note
        assert page.locator('[data-role="why-note"]').inner_text().strip() == "Author’s answers to follow."
        assert page.evaluate("[...document.querySelectorAll('[data-role=\"why-questions\"] .ab-q-item')].every((s) => s.children.length === 1)")
        body = page.locator("#view").inner_text()
        for t in ["Akash Gajjar", "University of Liverpool (2025)", "Primark", "Uniqlo"]:
            assert t in body
        hrefs = page.evaluate("[...document.querySelectorAll('.ab-links a')].map((a) => a.getAttribute('href'))")
        assert "https://github.com/akashgajjar07-hue" in hrefs
        base = site.rsplit("/", 1)[0]
        for href in hrefs:
            if href.startswith("downloads/"):
                with urllib.request.urlopen(f"{base}/{href}") as r:
                    assert r.status == 200 and len(r.read()) > 1000
        assert not problems, problems
    finally:
        ctx.close()
