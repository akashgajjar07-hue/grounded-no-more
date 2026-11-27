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
DOCS = ["README.md", "METHODOLOGY.md", "MODEL_CARD.md", "LIMITATIONS.md", "reports/VALIDATION_REPORT.md"]
KPIS = ROOT / "docs" / "data" / "kpis.json"
MINUS = "−"
BANNED = ["at every tested setting", "aircraft risk score", "aircraft ready", "approved to fly", "live data"]
# v2.1 release rules
SCOPE = "across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part"
NAMES = {"P0": "Simple Rulebook (naive reference)", "P1": "Each Airport for Itself (simplified local comparator)",
         "P2": "Network Plan", "I125": "Network Plan + Extra Spares"}
RELEASE_DOCS = ["README.md", "METHODOLOGY.md", "MODEL_CARD.md", "LIMITATIONS.md", "reports/VALIDATION_REPORT.md",
                "data/data_dictionary.md", "docs/assumption_register.md"]
FORBIDDEN = [r"\bvalidated\b", r"\boptimal\b", r"representative legacy airline practice", r"panel-proof",
             r"robust across worlds", r"saves the airline AED", r"\bA320", r"\bAirbus\b", r"\bBoeing\b",
             r"(?<![\d,.])787(?![\d,.])", r"\bEtihad\b"]


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


@pytest.mark.parametrize("name", DOCS[:4])
def test_template_exists_for_each_doc(name):
    assert (ROOT / "docs" / "templates" / f"{name}.tmpl").exists()


@pytest.mark.parametrize("name", DOCS[:4])
def test_banned_wording_absent(name):
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


def _col(cols: list[str], code: str) -> int:
    return next(i for i, c in enumerate(cols) if c.endswith(f"`{code}`"))


@pytest.mark.parametrize("kpi_id", HEADLINE)
def test_readme_results_table_matches_kpis(kpi_id):
    """README results table: P0, P2 and I125 cells equal the Mission Control KPIs (holdout)."""
    k = {x["id"]: x for x in _kpis()["kpis"]}[kpi_id]
    readme = _read("README.md")
    head = next(ln for ln in readme.splitlines() if ln.startswith("| KPI |"))
    cols = [c.strip() for c in head.strip("|").split("|")]
    assert cols[_col(cols, "P0")] == f"{NAMES['P0']} `P0`"
    i0, i2, i125 = _col(cols, "P0"), _col(cols, "P2"), _col(cols, "I125")
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
    expect = (f"{NAMES['P2']} `P2` vs {NAMES['P0']} `P0`: {_h(-red['mean'])} a year "
              f"[{_neg(f'{-round(hi):,.0f}')} to {_neg(f'{-round(lo):,.0f}')}]")
    assert expect in readme
    assert "holds in all three stress worlds" in readme and core["holds_all_worlds"]
    assert "×0.5–×2" in readme and core["holds_penalty_range"]
    # the core finding comes before the frontier option
    assert readme.index(expect) < readme.index("Frontier option: if you invest an additional")


def test_readme_baseline_sentence_8_vs_44():
    n = _kpis()["headline"]["core"]["outstation_rotables"]
    readme = _read("README.md")
    assert f"holds {n['P2']} rotables at the six outstations instead of {n['P0']}" in readme


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


# ----------------------------------------------------------------------------- v2.1 release wording
def _opening() -> str:
    readme = _read("README.md")
    assert "## For specialists" in readme
    return readme.split("## For specialists", 1)[0]


@pytest.mark.parametrize("name", RELEASE_DOCS)
def test_no_forbidden_words_or_manufacturer_names(name):
    text = _read(name)
    for pat in FORBIDDEN:
        m = re.search(pat, text, re.I)
        assert not m, (name, pat, text[max(0, m.start() - 60):m.end() + 60])


def test_display_names_used():
    for name in ("README.md", "METHODOLOGY.md", "MODEL_CARD.md", "LIMITATIONS.md"):
        text = _read(name)
        for code, label in NAMES.items():
            assert f"{label}** `{code}`" in text or f"{label} `{code}`" in text, (name, code)


def test_scope_line_beside_headline_kpis():
    readme = _read("README.md")
    lines = readme.splitlines()
    # README opening KPI table and the specialist results table are each followed by the scope line
    for header in ("| Plan | Downtime waiting for parts", "| KPI |"):
        i = next(n for n, ln in enumerate(lines) if ln.startswith(header))
        assert any(SCOPE in ln for ln in lines[i:i + 20]), header
    # the specialist paired headline
    i = next(n for n, ln in enumerate(lines) if f"{NAMES['P2']} `P2` vs {NAMES['P0']} `P0`:" in ln)
    assert any(SCOPE in ln for ln in lines[i:i + 4])
    assert SCOPE in _read("MODEL_CARD.md")


def test_capital_table_has_gross_lines():
    rmx = _kpis()["headline"]["core"]["remix"]
    readme = _read("README.md")
    bought = f"| New rotables bought | +{rmx['buy_units']} units ≈ AED {rmx['buy_aed'] / 1e6:.1f}M assumed value |"
    removed = f"| Rotables removed | {MINUS}{rmx['shed_units']} units ≈ AED {rmx['shed_aed'] / 1e6:.1f}M |"
    net = "| Net change in average simulated spare inventory | "
    note = "Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a discount."
    for text in (readme, _opening()):
        assert bought in text and removed in text and net in text and note in text
    assert readme.count(bought) == readme.count(net)


def test_readme_opening_has_no_headline_reduction_claim():
    core = _kpis()["headline"]["core"]
    red = core["aog_reduction"]["mean"]
    p0 = core["aog_reduction"]["mean"] + {k["id"]: k for k in _kpis()["kpis"]}["aog_hours"]["value"]
    opening = _opening()
    assert f"{round(red):,.0f}" not in opening
    assert f"{red / p0 * 100:.0f}%" not in opening
    assert "88%" not in opening and "1,480" not in opening
    assert not re.search(r"\d+% (lower|less|fewer|reduction|cut)", opening)


def test_readme_opening_plain_sections():
    opening = _opening()
    for h in ("## What this is", "## Why it matters", "## What I found", "## How to read it", "## Limits"):
        assert h in opening, h
    assert "How to read these numbers: simulated downtime of the aircraft waiting for the part" in opening
    assert "Likely ranges reflect simulation randomness only" in opening
    assert "Faster repair can beat buying spares" in opening
    assert "Relevant to Abu Dhabi hub carriers" in _read("README.md")


def _a5() -> str:
    var = json.loads((ROOT / "outputs" / "calibration" / "v2_p0_variants.json").read_text())
    v3 = next(v for k, v in var.items() if k.startswith("V3"))
    return ("The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the "
            f"model, not benchmarked against real airline KPIs. A line-kit variant (≈{round(v3['history']['aog_hours_per_year']):,.0f} h) "
            "was measured but not adopted because it fell outside that range. All results are conditional on this choice.")


@pytest.mark.parametrize("name", ["METHODOLOGY.md", "reports/VALIDATION_REPORT.md"])
def test_calibration_wording_present(name):
    assert _a5() in _read(name)


def test_limitations_review_table_and_next_experiments():
    text = _read("LIMITATIONS.md")
    for n in range(1, 26):
        row = next((ln for ln in text.splitlines() if ln.startswith(f"| AV2-{n:02d} |")), None)
        assert row, n
        assert re.search(r"\| (Fixed|Disclosed|Next experiment)", row), row
    assert "## Next experiments" in text
    for item in ("P0-R", "Incremental donor unavailability", "Combined disruption scenarios", "MRO-side model"):
        assert item in text, item
    assert "invalid recommendation — brakes are not changed outside the hub in this model" in text
