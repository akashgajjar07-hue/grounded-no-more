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
