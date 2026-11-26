"""Browser tests for 07 AOG Response Lab (screen agent D)."""
from __future__ import annotations

import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser


def _lab():
    p = DOCS / "data" / "aog_lab.json"
    return json.loads(p.read_text()) if p.exists() else json.loads((DOCS / "data" / "fixtures" / "aog_lab.json").read_text())


LAB = _lab()
IDS = LAB.get("showcase_ids") or [i["id"] for i in LAB["incidents"]]


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("inc", [None, IDS[0], IDS[len(IDS) // 2], IDS[-1]])
def test_aog_renders_clean(site, browser, vp, inc):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/aog" + (f"?incident={inc}" if inc else ""), vp)
    try:
        audit(page, problems, min_frames=2)
        assert page.locator(".aog-tile").count() == len(IDS)
        assert page.locator(".disclaimer").count() == 1
        if inc:
            assert page.locator(f'.aog-tile[data-id="{inc}"]').get_attribute("aria-checked") == "true"
    finally:
        ctx.close()


@pytest.mark.parametrize("inc_id", IDS)
def test_recommended_is_rank1_not_double_counted(site, browser, inc_id):  # noqa: F811
    inc = next(i for i in LAB["incidents"] if i["id"] == inc_id)
    ctx, page, problems = open_page(browser, site + f"#/aog?incident={inc_id}", "1440")
    try:
        rec = page.locator('.aog-opt[data-state="rec"]')
        expected = (inc.get("decision") or {}).get("recommended") or next((o["key"] for o in inc["options"] if o.get("rank") == 1), None)
        if expected:
            assert rec.count() == 1 and rec.get_attribute("data-key") == expected
        # robbery is always a human decision, never "No"/recommended
        rob = page.locator('.aog-opt[data-key="g"]')
        if rob.count():
            assert rob.get_attribute("data-state") == "human"
            assert "engineering/quality approval" in rob.inner_text()
        # pool shown as not contracted
        pool = page.locator('.aog-opt[data-key="d"]')
        if pool.count() and any(o["key"] == "d" and "NOT_CONTRACTED" in o["reason_codes"] for o in inc["options"]):
            assert "Not contracted" in pool.inner_text()
        assert "Human decision required" in page.locator(".aog-human").inner_text() or "HUMAN DECISION REQUIRED" in page.locator(".aog-human").inner_text().upper()
        assert not problems, problems
    finally:
        ctx.close()


def test_picker_and_story_hook(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/aog?incident=AOG-0001", "1440")
    try:
        if "AOG-0001" in IDS:
            assert page.locator('[data-story="aog-incident-ps1"]').count() == 1
        page.locator(f'.aog-tile[data-id="{IDS[1]}"]').click()
        page.wait_for_timeout(200)
        assert f"incident={IDS[1]}" in page.url
        assert IDS[1] in page.locator(".aog-head").inner_text()
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(200)
        assert f"incident={IDS[2]}" in page.url
        assert not problems, problems
    finally:
        ctx.close()


# ---- design wave 2 (critic item #6)
import re  # noqa: E402

CODE_RE = re.compile(r"\b[A-Z]{2,}(?:_[A-Z]+)+\b")


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("inc_id", [IDS[0], IDS[len(IDS) // 2]])
def test_aog_wave2_design(site, browser, vp, inc_id):  # noqa: F811
    inc = next(i for i in LAB["incidents"] if i["id"] == inc_id)
    ctx, page, problems = open_page(browser, site + f"#/aog?incident={inc_id}", vp)
    try:
        heads = page.locator("#view .chart-headline").all_inner_texts()
        assert all(len(t.strip()) <= 90 for t in heads), heads
        # no raw enum codes as visible copy; codes survive in title attributes
        opts_text = page.locator('[data-story="aog-options"]').inner_text()
        assert not CODE_RE.search(opts_text), CODE_RE.findall(opts_text)
        codes = {c for o in inc["options"] for c in o.get("reason_codes") or []}
        titles = set(page.locator(".aog-codes li[title]").evaluate_all("(els) => els.map((e) => e.title)"))
        assert codes <= titles
        # no real calendar dates on screen (simulated weeks and T+ hours only)
        assert not re.search(r"\b20\d\d-\d\d-\d\d\b", page.locator("#view").inner_text())
        # cards: feasible group ordered by rank, then a "not available" group
        feas = page.locator('.aog-optgroup[data-group="feasible"] .aog-opt').evaluate_all("(els) => els.map((e) => e.dataset.key)")
        exp = [o["key"] for o in sorted((o for o in inc["options"] if o.get("feasible") and not o.get("human_decision") and not o.get("indicative") and "NOT_CONTRACTED" not in (o.get("reason_codes") or [])), key=lambda o: o.get("rank") or 99)]
        assert feas == exp
        assert "FEASIBLE (" in page.locator('.aog-optgroup[data-group="feasible"] .aog-optgroup-head h4').inner_text()
        # MISSED on the recommended card is explained
        rec = page.locator('.aog-opt[data-state="rec"]')
        if rec.count() and "Missed" in rec.inner_text():
            note = rec.locator('[data-role="missed-note"]').inner_text()
            assert "ranked by exposure" in note.lower() or "lowest exposure" in note.lower()
        # wave 4: when every feasible option misses, one banner replaces the per-card red MISSED pills
        feas_opts = [o for o in inc["options"] if o.get("feasible") and not o.get("human_decision") and o.get("wait_h") is not None]
        if feas_opts and all(not o.get("deadline_met") for o in feas_opts):
            assert page.locator('[data-role="none-meets"]').count() == 1
            assert page.locator('.aog-opt .pill--urgent', has_text="Missed").count() == 0
        # swimlane: every step has its own position (no stacked cluster at T+0)
        pos = page.locator('[data-story="aog-timeline"] svg g.aog-sl-step').evaluate_all("(els) => els.map((e) => e.getAttribute('transform'))")
        assert len(pos) == len(inc["timeline"]) and len(set(pos)) == len(pos)
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave3_aog_copy(site, browser, vp):  # noqa: F811
    """Design wave 3: no "(s)" or duplicated source, compact money, neutral deadline chips, the
    counterfactual footnote is HTML (F2), and AOG-0177 explains the slack tie-break."""
    lab = _lab()
    ctx, page, problems = open_page(browser, site + "#/aog?incident=AOG-0001", vp)
    try:
        txt = page.locator("#view").inner_text()
        assert "(s)" not in txt
        title = page.locator('[data-story="aog-decision"] .card-title').inner_text()
        src = next((i for i in lab["incidents"] if i["id"] == "AOG-0001"), {}).get("decision", {}).get("source")
        if src:
            assert title.count(src) <= 1, title
        import re
        assert not re.search(r"AED \d{1,3}(,\d{3}){1,}", page.locator('[data-story="aog-decision"]').inner_text())
        colors = page.evaluate("""() => [...document.querySelectorAll('.aog-dl')].map((e) => getComputedStyle(e).color)""")
        assert all("245, 185, 66" not in c and "231, 107, 100" not in c for c in colors), colors
        assert page.locator(".aog-cf-foot").count() <= 1
        edge = page.evaluate("""() => [...document.querySelectorAll('#view svg text')].filter((t) => t.getBoundingClientRect().right > innerWidth + 1).length""")
        assert edge == 0
        assert not problems, problems
    finally:
        ctx.close()
    inc = next((i for i in lab["incidents"] if i["id"] == "AOG-0177"), None)
    if inc:
        feas = [o for o in inc["options"] if o.get("feasible") and not o.get("human_decision")]
        if len(feas) >= 2 and all(o.get("deadline_met") for o in feas):
            ctx, page, problems = open_page(browser, site + "#/aog?incident=AOG-0177", vp)
            try:
                heads = page.locator(".chart-headline").all_inner_texts()
                assert any("slack" in hd for hd in heads), heads
            finally:
                ctx.close()
