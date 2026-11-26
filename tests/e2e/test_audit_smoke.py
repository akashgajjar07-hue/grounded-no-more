"""Smoke run of the interaction-audit harness on one route (the full audit runs after the page agents finish)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_lib import AuditConfig, audit_route, serve_docs, write_report  # noqa: E402

pytestmark = pytest.mark.browser


def test_audit_harness_smoke_about(tmp_path):
    sync = pytest.importorskip("playwright.sync_api")
    with serve_docs() as base, sync.sync_playwright() as pw:
        rep = audit_route(pw, base, AuditConfig(route="about", viewport=(1440, 900), mode="simple", shortcuts=True))
    out = write_report([rep], tmp_path / "smoke.json")
    d = json.loads((tmp_path / "smoke.json").read_text())
    assert d["totals"] == out["totals"] and d["routes"][0]["route"] == "about"
    kinds = {e["kind"] for e in d["routes"][0]["elements"]}
    assert {"link", "button", "toggle", "download"} <= kinds, kinds          # discovery covers shell + view controls
    assert len(d["routes"][0]["elements"]) >= 20
    # every element on this route (shell + About) produces a visible effect within 1 s
    bad = [e for e in d["routes"][0]["elements"] if e["ok"] is False]
    assert not bad, bad
    assert not d["routes"][0]["load_errors"]
    # shortcuts were exercised; "?" opens the help modal and Esc closes it
    k = {s["label"]: s for s in d["routes"][0]["shortcuts"]}
    assert k["key ?"]["ok"] and "esc-closes" in k["key ?"]["effects"]
    assert all(s["ms"] is None or s["ms"] <= 1000 for s in d["routes"][0]["shortcuts"])
