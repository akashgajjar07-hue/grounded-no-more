"""Rendered docs: no placeholder survives, and headline KPI numbers match docs/data/kpis.json.

The docs are rendered by scripts/render_docs.py from docs/templates/*.md.tmpl. The expected strings
here are formatted independently of the renderer (same conventions: AED 41.9M, 98.1%, 223 h, [174–272]).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "METHODOLOGY.md", "MODEL_CARD.md", "LIMITATIONS.md", "STUDY_GUIDE.md",
        "reports/VALIDATION_REPORT.md"]
KPIS = ROOT / "docs" / "data" / "kpis.json"
MINUS = "−"


def _read(name: str) -> str:
    p = ROOT / name
    if not p.exists():
        pytest.skip(f"{name} not rendered")
    return p.read_text()


@pytest.mark.parametrize("name", DOCS)
def test_no_placeholder_left(name):
    assert "{{RESULT:" not in _read(name)


@pytest.mark.parametrize("name", DOCS[:5])
def test_template_exists_for_each_doc(name):
    assert (ROOT / "docs" / "templates" / f"{name}.tmpl").exists()


def _aed(x: float) -> str:
    return f"AED {x / 1e6:.1f}M" if abs(x) >= 1e6 else f"AED {x:,.0f}"


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _h(x: float) -> str:
    return f"{round(x):,.0f} h"


def _rng(lo: str, hi: str) -> str:
    return f"[{lo}–{hi}]"


def _expected(k: dict, which: str) -> tuple[str, str]:
    v = k["value"] if which == "rec" else k["baseline"]
    lo, hi = k["ci"] if which == "rec" else k["baseline_ci"]
    if k["id"] == "immediate_fill_rate":
        return _pct(v), _rng(f"{lo * 100:.1f}", f"{hi * 100:.1f}")
    if k["id"] == "aog_hours":
        return _h(v), _rng(f"{round(lo):,.0f}", f"{round(hi):,.0f}")
    if k["id"] in ("spare_capital_aed", "total_annual_cost_aed"):
        return _aed(v), _rng(f"{lo / 1e6:.1f}", f"{hi / 1e6:.1f}")
    if k["id"] == "aog_events":
        return f"{v:,.1f}", _rng(f"{lo:.1f}", f"{hi:.1f}")
    raise KeyError(k["id"])


HEADLINE = ["immediate_fill_rate", "aog_hours", "aog_events", "spare_capital_aed", "total_annual_cost_aed"]


@pytest.mark.parametrize("kpi_id", HEADLINE)
def test_readme_results_table_matches_kpis(kpi_id):
    """The README results table's P0 and I125 cells equal the Mission Control KPIs (holdout)."""
    if not KPIS.exists():
        pytest.skip("site data absent")
    kp = {k["id"]: k for k in json.loads(KPIS.read_text())["kpis"]}[kpi_id]
    readme = _read("README.md")
    table = [ln for ln in readme.splitlines() if ln.startswith("| ") and "P0 Legacy rules" not in ln]
    label = {"immediate_fill_rate": "Immediate fill rate", "aog_hours": "Material AOG hours / yr",
             "aog_events": "AOG events / yr", "spare_capital_aed": "Spares capital",
             "total_annual_cost_aed": "Total annual cost"}[kpi_id]
    row = next(ln for ln in table if ln.startswith(f"| {label}"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    p0, i125 = cells[1], cells[4]
    for cell, which in ((p0, "base"), (i125, "rec")):
        mean, ci = _expected(kp, which)
        assert cell == f"{mean} {ci}", (kpi_id, which, cell, mean, ci)


def test_readme_headline_sentence_matches_kpis():
    if not KPIS.exists():
        pytest.skip("site data absent")
    kp = {k["id"]: k for k in json.loads(KPIS.read_text())["kpis"]}
    readme = _read("README.md")
    a, c = kp["aog_hours"], kp["spare_capital_aed"]
    mean, ci = _expected(a, "rec")
    assert f"At a spares capital of {_aed(c['value'])}, material AOG falls to {mean} a year (95% CI {ci})" in readme
    assert f"against {_h(a['baseline'])} for the legacy baseline at {_aed(c['baseline'])}" in readme
    sel = a["selection"]["recommended"]
    assert f"scored {_h(sel)}" in readme


def test_open_actions_match():
    if not KPIS.exists():
        pytest.skip("site data absent")
    oe = {k["id"]: k for k in json.loads(KPIS.read_text())["kpis"]}["open_exceptions"]
    readme = _read("README.md")
    assert f"raises {oe['value']} actions, {oe['by_severity']['urgent']} urgent" in readme


def test_no_unformatted_floats_in_readme():
    """Guard against raw floats such as 0.9811 or 41853427.0 leaking into prose."""
    readme = _read("README.md")
    assert not re.search(r"\b\d{5,}\.\d+\b", readme)
    head = readme.split("## Author")[0]
    assert not re.search(r"\b(NaN|nan|None|null|undefined)\b", head)
