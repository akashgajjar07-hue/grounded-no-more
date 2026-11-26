"""Rendered docs: no placeholder survives, and the README headline numbers match docs/data/kpis.json (v2).

The docs are rendered by scripts/render_docs.py from docs/templates/*.md.tmpl. The expected strings
here are formatted independently of the renderer (same conventions: AED 49.0M, 97.7%, 210 h, [146–274]).
kpis.json: `baseline` = P0, `value` = P2 (the core finding), `reference` = I125 (the frontier option).
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
BANNED = ["at every tested setting", "aircraft risk score", "aircraft ready", "approved to fly", "live data"]


def _read(name: str) -> str:
    p = ROOT / name
    if not p.exists():
        pytest.skip(f"{name} not rendered")
    return p.read_text()


def _kpis() -> dict:
    if not KPIS.exists():
        pytest.skip("site data absent")
    return json.loads(KPIS.read_text())


@pytest.mark.parametrize("name", DOCS)
def test_no_placeholder_left(name):
    assert "{{RESULT:" not in _read(name)


@pytest.mark.parametrize("name", DOCS[:5])
def test_template_exists_for_each_doc(name):
    assert (ROOT / "docs" / "templates" / f"{name}.tmpl").exists()


@pytest.mark.parametrize("name", DOCS[:4])
def test_banned_wording_absent(name):
    """STUDY_GUIDE is excluded: it quotes these phrases in its 'what not to say' table."""
    text = _read(name).lower()
    for phrase in BANNED:
        assert phrase not in text, (name, phrase)


def test_readme_never_says_every_tested_setting():
    assert not re.search(r"(at|across|in) (every|all) tested (setting|settings|scenario|scenarios)",
                         _read("README.md"), re.I)


def _neg(s: str) -> str:
    return s.replace("-", MINUS)


def _aed(x: float) -> str:
    return f"AED {x / 1e6:.1f}M" if abs(x) >= 1e6 else f"AED {x:,.0f}"


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _h(x: float) -> str:
    return _neg(f"{round(x):,.0f}") + " h"


def _rng(lo: str, hi: str) -> str:
    return f"[{lo}–{hi}]"


def _cell(kid: str, v: float, lo: float, hi: float) -> str:
    if kid == "immediate_fill_rate":
        return f"{_pct(v)} {_rng(f'{lo * 100:.1f}', f'{hi * 100:.1f}')}"
    if kid == "aog_hours":
        return f"{_h(v)} {_rng(f'{round(lo):,.0f}', f'{round(hi):,.0f}')}"
    if kid in ("spare_capital_aed", "total_annual_cost_aed"):
        return f"{_aed(v)} {_rng(f'{lo / 1e6:.1f}', f'{hi / 1e6:.1f}')}"
    if kid == "aog_events":
        return f"{v:,.1f} {_rng(f'{lo:.1f}', f'{hi:.1f}')}"
    raise KeyError(kid)


HEADLINE = ["immediate_fill_rate", "aog_hours", "aog_events", "spare_capital_aed", "total_annual_cost_aed"]
LABEL = {"immediate_fill_rate": "Immediate fill rate", "aog_hours": "Material AOG hours / yr",
         "aog_events": "AOG events / yr", "spare_capital_aed": "Spares capital",
         "total_annual_cost_aed": "Total annual cost"}


@pytest.mark.parametrize("kpi_id", HEADLINE)
def test_readme_results_table_matches_kpis(kpi_id):
    """README results table: P0, P2 and I125 cells equal the Mission Control KPIs (holdout)."""
    k = {x["id"]: x for x in _kpis()["kpis"]}[kpi_id]
    readme = _read("README.md")
    head = next(ln for ln in readme.splitlines() if ln.startswith("| KPI | P0"))
    cols = [c.strip() for c in head.strip("|").split("|")]
    i0 = next(i for i, c in enumerate(cols) if c.startswith("P0"))
    i2 = next(i for i, c in enumerate(cols) if c.startswith("P2"))
    i125 = next(i for i, c in enumerate(cols) if c.startswith("I125"))
    row = next(ln for ln in readme.splitlines() if ln.startswith(f"| {LABEL[kpi_id]} |"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[i0] == _cell(kpi_id, k["baseline"], *k["baseline_ci"]), (kpi_id, "P0", cells[i0])
    assert cells[i2] == _cell(kpi_id, k["value"], *k["ci"]), (kpi_id, "P2", cells[i2])
    ref = k["reference"]
    assert ref["id"] == "I125"
    assert cells[i125] == _cell(kpi_id, ref["value"], *ref["ci"]), (kpi_id, "I125", cells[i125])


def test_readme_p2_headline_matches_kpis():
    kp = _kpis()
    core = kp["headline"]["core"]
    assert kp["core_id"] == "P2" and core["vs"] == "P0"
    readme = _read("README.md")
    red = core["aog_reduction"]
    lo, hi = red["ci"]
    cap = core["capital_aed"]["mean"]
    expect = (f"Network positioning (P2) cuts material AOG by {_h(red['mean'])} a year "
              f"{_rng(f'{round(lo):,.0f}', f'{round(hi):,.0f}')}")
    assert expect in readme
    assert f"for about {'+' if cap > 0 else MINUS}AED {abs(cap) / 1e6:.1f}M of spares capital" in readme
    assert "holds in all three calibrated worlds" in readme and core["holds_all_worlds"]
    assert "×0.5–×2" in readme and core["holds_penalty_range"]
    # the P2 headline comes before the frontier option
    assert readme.index("Network positioning (P2) cuts") < readme.index("Frontier option: if you invest an additional")


def test_readme_baseline_sentence_8_vs_44():
    kp = _kpis()
    n = kp["headline"]["core"]["outstation_rotables"]
    readme = _read("README.md")
    assert f"vs a legacy OEM-quote policy holding only {n['P0']} outstation rotables" in readme
    assert f"P2 holds {n['P2']} rotables at the six outstations instead of {n['P0']}" in readme


def test_readme_frontier_option_matches_kpis():
    fo = _kpis()["headline"]["frontier_option"]
    readme = _read("README.md")
    assert f"if you invest an additional AED {fo['extra_capital_aed']['mean'] / 1e6:.1f}M" in readme
    r = fo["aog_reduction"]
    assert (f"cuts a further {_h(r['mean'])} a year {_rng(f'{round(r['ci'][0]):,.0f}', f'{round(r['ci'][1]):,.0f}')} vs P2"
            in readme)
    assert "not significant if repair is 25% faster" in readme
    shifts = {s["setting"]: s["recommended"] for s in fo["rule_shifts"]}
    assert f"{shifts['x0.5']} at ×0.5 and {shifts['x2.0']} at ×2" in readme
    assert "Post-plan check (D015" in readme


def test_open_actions_match():
    oe = {k["id"]: k for k in _kpis()["kpis"]}["open_exceptions"]
    readme = _read("README.md")
    assert f"raises {oe['value']} actions, {oe['by_severity']['urgent']} urgent" in readme


def test_v1_mentioned_once_as_archived():
    readme = _read("README.md")
    assert "a v1 world was archived after a domain review" in readme.lower()
    assert "archive/v1" in readme


def test_no_unformatted_floats_in_readme():
    """Guard against raw floats such as 0.9811 or 41853427.0 leaking into prose."""
    readme = _read("README.md")
    assert not re.search(r"\b\d{5,}\.\d+\b", readme)
    head = readme.split("## Author")[0]
    assert not re.search(r"\b(NaN|nan|None|null|undefined)\b", head)


def test_validation_report_keeps_review_sections():
    text = _read("reports/VALIDATION_REPORT.md")
    assert "## Phase 5 reviewer findings and fixes" in text
    assert "### v1-era reviews (archived world)" in text
    assert "### v2 reviews" in text
