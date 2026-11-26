"""Browser tests for 08 Planner Action Centre (screen agent D)."""
from __future__ import annotations

import csv
import io
import json

import pytest

from _sitefx import DOCS, VIEWPORTS, audit, browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser
HEADER = ["exception_id", "week", "type", "severity", "pn", "station", "summary", "recommended_action", "owner", "due_week", "evidence"]


def _actions():
    p = DOCS / "data" / "actions.json"
    return json.loads(p.read_text()) if p.exists() else json.loads((DOCS / "data" / "fixtures" / "actions.json").read_text())


A = _actions()["actions"]
FIRST_URGENT = next(a for a in A if a["severity"] == "urgent")


@pytest.mark.parametrize("vp", list(VIEWPORTS))
@pytest.mark.parametrize("route", ["#/actions", "#/actions?severity=urgent", f"#/actions?type={A[0]['type']}&station={A[0]['station'] or 'Network'}", f"#/actions?id={FIRST_URGENT['exception_id']}"])
def test_actions_renders_clean(site, browser, vp, route):  # noqa: F811
    ctx, page, problems = open_page(browser, site + route, vp)
    try:
        audit(page, problems, min_frames=1)
        assert page.locator('[data-story="action-inbox"]').count() == 1
        assert page.locator(".disclaimer").count() == 1
        # severity is icon + text
        first = page.locator(".pac-row .pill").first
        assert first.locator("svg").count() == 1 and first.inner_text().strip()
        if "id=" in route:
            dr = page.locator(".drawer.is-open")
            dr.wait_for()
            assert FIRST_URGENT["exception_id"] in dr.inner_text()
            assert FIRST_URGENT["recommended_action"][:30] in dr.inner_text()
    finally:
        ctx.close()


def test_filters_and_counts(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/actions?severity=urgent", "1440")
    try:
        n_urg = sum(a["severity"] == "urgent" for a in A)
        assert f"Showing {n_urg} of {len(A)}" in page.locator(".pac-shown").inner_text()
        page.locator('[data-action="show-all"]').click()
        assert page.locator(".pac-row").count() == n_urg
        page.select_option("#pac-owner", A[0]["owner"])
        assert f"owner=" in page.url
        assert not problems, problems
    finally:
        ctx.close()


def test_drawer_deep_link_roundtrip(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/actions", "1440")
    try:
        page.locator(".pac-row").first.click()
        page.locator(".drawer.is-open").wait_for()
        assert "id=" in page.url
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        assert "id=" not in page.url
        assert not problems, problems
    finally:
        ctx.close()


def test_csv_export_header_and_rows(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/actions?severity=urgent", "1440")
    try:
        with page.expect_download() as dl:
            page.locator('[data-action="export-csv"]').click()
        d = dl.value
        assert d.suggested_filename.endswith(".csv")
        text = open(d.path(), encoding="utf-8").read()
        rows = list(csv.reader(io.StringIO(text)))
        assert rows[0] == HEADER
        body = rows[1:]
        assert len(body) == sum(a["severity"] == "urgent" for a in A)
        assert all(r[3] == "urgent" for r in body)
        json.loads(body[0][10])  # evidence column is JSON
        assert not problems, problems
    finally:
        ctx.close()


# ---- design wave 2 (critic item #5: column grid grouped by PN, rationale in the drawer)
@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_actions_wave2_grid(site, browser, vp):  # noqa: F811
    from collections import Counter
    ctx, page, problems = open_page(browser, site + "#/actions", vp)
    try:
        assert "Week " not in page.locator(".page-head, #view h1").first.inner_text()
        # every exception row is a grid with the scannable columns
        r0 = page.locator(".pac-row").first
        for cls in ("pac-c-sev", "pac-c-part", "pac-c-stock", "pac-c-aog", "pac-c-d0", "pac-c-action", "pac-c-due"):
            assert r0.locator(f".{cls}").count() == 1, cls
        # the long sentence is not in the row; it is in the drawer
        assert A[0]["summary"] not in page.locator(".pac-list").inner_text()
        # same-PN exceptions are grouped under one header
        page.locator('[data-action="show-all"]').click()
        multi = [pn for pn, n in Counter(a["pn"] for a in A if a["pn"]).items() if n > 1]
        for pn in multi:
            g = page.locator(f'.pac-group[data-pn="{pn}"]')
            assert g.count() == 1, pn
            assert g.locator(".pac-row").count() == sum(a["pn"] == pn for a in A)
        if vp == "1440":
            assert page.locator(".pac-grid-head").is_visible()
        page.locator(".pac-row").first.click()
        dr = page.locator(".drawer.is-open")
        dr.wait_for()
        first_id = page.locator(".pac-row").first.get_attribute("data-id")
        a = next(x for x in A if x["exception_id"] == first_id)
        assert a["summary"] in dr.locator(".pac-why").inner_text()
        assert len(dr.locator(".drawer-head h2").first.inner_text()) < len(a["summary"]) or len(a["summary"]) < 60
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_wave3_actions(site, browser, vp):  # noqa: F811
    """Design wave 3: the action column shows whole first sentences, no raw enums or "(s)" in the drawer,
    and the group AOG metric is the exporter's worst-station 52-week value (as on Mission)."""
    import re
    parts = json.loads((DOCS / "data" / "parts.json").read_text())
    by = {p["pn"]: p for p in parts.get("parts", [])}
    ctx, page, problems = open_page(browser, site + "#/actions", vp)
    try:
        acts = page.locator(".pac-c-action").all_inner_texts()
        assert acts and all(not a.rstrip().endswith((",", " or", " an", " a", " the")) for a in acts), acts[:5]
        heads = page.evaluate("""() => [...document.querySelectorAll('.pac-group')].map((g) => ({ pn: g.dataset.pn, t: g.querySelector('.pac-ghead-meta').textContent }))""")
        for g in heads:
            v = by.get(g["pn"], {}).get("aog_h_52w_max_station")
            if v:
                assert f"max {round(v):,} AOG h at one station" in g["t"], g
        page.locator(".pac-row").first.click()
        page.wait_for_timeout(400)
        dr = page.locator(".drawer").inner_text()
        assert not re.search(r"\b[A-Z]+_[A-Z_]+\b", dr), re.findall(r"\b[A-Z]+_[A-Z_]+\b", dr)
        assert "(s)" not in dr
        assert not problems, problems
    finally:
        ctx.close()
