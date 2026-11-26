"""Planner workbook v2 (excel/grounded_no_more_planner_workbook.xlsx, built by scripts/build_workbook.py).

Three layers of verification:
1. Structure: sheets, the disclaimer, wording rules, live formula strings (POISSON.DIST, SUMPRODUCT, COUNTIF,
   GAMMALN, VLOOKUP), data validation, filters and conditional formatting.
2. Python cross-check of the defaults: the "Python reference" rows equal gnm.policy.analytic /
   gnm.policy.policies results, and the ROP formula logic reproduces the frozen v2 P1/P2 hub reorder point for every
   AUH consumable/expendable row.
3. Formula evaluation: the workbook is recalculated with the `formulas` package for 3 input sets per calculator
   and compared with values computed independently in Python; the default recalculation reproduces the AOG-lab
   exposures and the actions.json counts (skipped if `formulas` is not installed).
No incident id, PN or count is typed here: everything is derived from the pipeline outputs the same way the
builder derives it.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import stats
from scipy.special import gammaln

openpyxl = pytest.importorskip("openpyxl")

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "excel" / "grounded_no_more_planner_workbook.xlsx"
DOWNLOAD = ROOT / "docs" / "downloads" / XLSX.name
NAME = XLSX.name
DISCLAIMER = ("Independent educational simulation. Not an airline system or an approved maintenance, "
              "airworthiness or dispatch tool.")
FLOAT, ROP, EXC, AOG, ROUTES = ("Poisson float calculator", "ROP calculator", "Exception list",
                                "AOG exposure calculator", "AOG recovery routes")
BANNED = ("aircraft risk score", "aircraft ready", "approved to fly", "live data", "quarantine", "1000–1019")

needs_inputs = pytest.mark.skipif(
    not (ROOT / "docs" / "data" / "parts.json").exists()
    or not (ROOT / "outputs" / "forecasting" / "final_forecasts.parquet").exists(),
    reason="pipeline outputs missing")


def _bw():
    spec = importlib.util.spec_from_file_location("build_workbook", ROOT / "scripts" / "build_workbook.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bw():
    return _bw()


@pytest.fixture(scope="module")
def built(tmp_path_factory, bw):
    """Build a fresh copy so the test checks the current script and outputs, not a stale file."""
    if not (ROOT / "docs" / "data" / "parts.json").exists():
        pytest.skip("pipeline outputs missing")
    out = tmp_path_factory.mktemp("wb") / NAME
    bw.build(out)
    return out


@pytest.fixture(scope="module")
def wb(built):
    return openpyxl.load_workbook(built)


@pytest.fixture(scope="module")
def inputs(bw):
    return bw.load_inputs()


def _all_text(wb):
    return " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row
                    if isinstance(c.value, str) and not c.value.startswith("="))


# ------------------------------------------------------------------ 1. structure
def test_committed_workbook_exists_and_download_copy():
    assert XLSX.exists(), "run python scripts/build_workbook.py"
    assert DOWNLOAD.exists() and DOWNLOAD.read_bytes() == XLSX.read_bytes(), "docs/downloads copy is stale"


def test_sheets_and_disclaimer(wb, bw):
    assert wb.sheetnames == bw.SHEETS
    assert wb["README"]["C5"].value == DISCLAIMER
    for ws in wb.worksheets:
        texts = " ".join(str(c.value) for row in ws.iter_rows(max_row=6) for c in row if c.value)
        assert "Independent educational simulation" in texts, ws.title
    legend = {wb["README"].cell(r, 2).value for r in range(1, 80)}
    assert {"REAL", "DERIVED", "ASSUMED", "SIMULATED"} <= legend


def test_wording_rules_and_v2_framing(wb, inputs):
    txt = _all_text(wb)
    low = txt.lower()
    for b in BANNED:
        assert b not in low, b
    used = {i["id"] for i in _bw().showcase_incidents(inputs["incidents"], inputs["cfg"])}
    for inc_id in {i["id"] for i in inputs["incidents"]["incidents"]} - used:
        assert f"Worked incident {inc_id}" not in txt
    assert "simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions" in txt
    k = inputs["kpis"]
    for code in ("P0", "P1", "P2", "I125"):
        assert k["display_names"][code]["display_name"] in txt, code
    assert "legacy OEM-quote" not in txt and "P0 legacy" not in txt
    assert k["scope_line"] in txt and k["reading_note"] in txt
    for row in k["capital_table"]["rows"]:
        assert row["text"] in txt, row["id"]
    assert k["capital_table"]["note"] in txt
    assert k["stress_worlds"]["text"] in txt and k["stress_worlds"]["ranges_note"] in txt
    assert k["frontier_insight"]["text"] in txt
    assert "if you invest an additional aed" in low
    assert txt.count("A v1 world was archived after a domain review; see archive/v1") == 1
    assert "material shortage exposure" in low and "simulated planning snapshot" in low
    seeds = inputs["kpis"]["seeds"]
    assert f"seeds {seeds[0]}–{seeds[-1]}" in txt


def test_v21_text_gate(wb):
    """No OEM names, airline brand or forbidden words anywhere in the workbook text (v2.1 brief)."""
    from gnm.export import v21
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and not c.value.startswith("="):
                    for kind, pat in v21.FORBIDDEN_PATTERNS.items():
                        assert not pat.search(c.value), (kind, ws.title, c.coordinate, c.value[:80])


def test_design_tokens_applied(wb):
    ws = wb[FLOAT]
    assert ws["B8"].fill.fgColor.rgb.endswith("132638")        # deep steel header
    assert ws["B8"].font.color.rgb.endswith("22C7B8")          # teal header text
    assert ws["A1"].fill.fgColor.rgb.endswith("09131F")        # midnight canvas
    assert ws["E21"].number_format == '"AED "#,##0'
    assert ws["E18"].number_format == "0.0%"
    assert ws["B5"].font.name == "Inter"


def test_part_list(wb, inputs):
    ws = wb["Part list"]
    parts = inputs["parts"]["parts"]
    n = len(parts)
    pns = [ws.cell(r, 2).value for r in range(6, 6 + n)]
    assert pns == [p["pn"] for p in parts] and len(set(pns)) == n
    hdr = {ws.cell(5, c).value: c for c in range(2, 27)}
    for h in ("Applicability", "Removal mode", "Family", "QPA NB", "QPA WB", "Rectification window (hypothetical)"):
        assert h in hdr, h
    col = lambda h: [ws.cell(r, hdr[h]).value for r in range(6, 6 + n)]
    assert col("Applicability") == [p["applicability"] for p in parts]
    assert set(col("Rectification window (hypothetical)")) <= {"D0", "D3", "D10", "NONE"}
    assert "NONE" in col("Rectification window (hypothetical)")
    assert ws["V6"].value == "=T6-S6" and ws["W6"].value == "=T6*O6"
    assert ws["Z5"].value == "Row provenance" and ws["Z6"].value == "SIMULATED"
    assert {ws.cell(4, c).value for c in range(2, 27)} <= {"REAL", "DERIVED", "ASSUMED", "SIMULATED"}
    end = 5 + n
    assert ws.auto_filter.ref == f"B5:Z{end}"
    assert ws[f"S{end + 2}"].value == f"=SUM(S6:S{end})" and "SUBTOTAL(9" in ws[f"S{end + 3}"].value


def test_float_formulas(wb, inputs):
    ws = wb[FLOAT]
    n_ex = len(inputs["rot"]["float_examples"])
    assert "POISSON.DIST(E14-1,E17,TRUE)" in ws["E18"].value          # immediate fill P(X <= S-1)
    assert ws["E14"].value == "=E11+E12"                               # total spares = base stock + loop
    assert ws["E19"].value.startswith("=E17-E14+SUMPRODUCT(") and "$B$35:$B$95" in ws["E19"].value
    assert ws["E17"].value == "=E9*E10/30"
    assert "VLOOKUP($C$5" in ws["C9"].value and "INDEX(" in ws["C11"].value
    assert [ws.cell(r, 2).value for r in (35, 95)] == [0, 60]
    dv = {str(v.sqref): v.formula1 for v in ws.data_validations.dataValidation}
    assert f"'Rotable examples'!$A$5:$A${4 + n_ex}" in dv["C5"] and dv["C6"] == '"P0,P1,P2,I125"'
    assert ws._charts, "fill chart missing"
    assert ws["C5"].value == _bw().default_float_pn(inputs["rot"])


def test_rop_formulas(wb):
    ws = wb[ROP]
    assert ws["E21"].value == "=E9*E11/7"
    assert ws["E22"].value == "=E10*E21+E9^2*(E12/7)^2"
    assert 'COUNTIF($C$46:$C$846,"<"&E15)' in ws["E27"].value
    assert 'COUNTIF($E$46:$E$846,"<"&E15)' in ws["E28"].value
    assert "POISSON.DIST(B46,$E$21,TRUE)" in ws["C46"].value
    assert "GAMMALN" in ws["D46"].value and ws["E47"].value == "=E46+D47"
    assert ws["B846"].value == 800
    assert [ws[f"J{r}"].value for r in range(9, 13)] == ["D0", "D3", "D10", "NONE"]


def test_exception_sheet(wb, inputs, bw):
    ws = wb[EXC]
    A = inputs["actions"]
    acts = A["actions"]
    L = bw.exception_layout(A)
    H = L["header"]
    last = openpyxl.utils.get_column_letter(1 + len(bw.EXC_COLS))
    assert ws.auto_filter.ref == f"B{H}:{last}{H + len(acts)}"
    assert [ws.cell(r, 2).value for r in range(H + 1, H + 1 + len(acts))] == [a["exception_id"] for a in acts]
    hdr = [ws.cell(H, c).value for c in range(2, 2 + len(bw.EXC_COLS))]
    for h in ("Trigger", "Quantity", "Source", "Destination", "Required-by week", "Expected availability",
              "Constraints", "Owner", "Expected benefit"):
        assert h in hdr
    owners = {ws.cell(r, hdr.index("Owner") + 2).value for r in range(H + 1, H + 1 + len(acts))}
    assert owners <= set(A["owners"])
    assert {ws.cell(r, hdr.index("Provenance") + 2).value for r in range(H + 1, H + 1 + len(acts))} == {"DERIVED"}
    assert any("COUNTIFS(" in str(c.value) for row in ws.iter_rows(min_row=7, max_row=H - 1) for c in row)
    rules = [r for cf in ws.conditional_formatting for r in cf.rules]
    assert len(rules) >= 4


def test_aog_formulas(wb):
    ws = wb[AOG]
    assert ws["C19"].value == "=IF(C8>C16,C8+C17-C16,0)"
    assert ws["C23"].value == "=C21+C22+C11"
    assert ws["C20"].value == "=VLOOKUP(C6,$I$6:$K$7,2,FALSE)*C12"
    assert ws["C22"].value.startswith("=IF(C8>C16,VLOOKUP(C6,$I$6:$K$7,3,FALSE)")


def test_routes_sheet(wb, inputs):
    ws = wb[ROUTES]
    a = inputs["cfg"]["aog_sourcing"]
    txt = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
    assert "engineering/quality approval required" in txt and "human decision" in txt
    assert "not market data" in txt
    vals = [c.value for row in ws.iter_rows() for c in row]
    assert float(a["robbery"]["availability"]) in vals
    assert float(a["exchange_loan"]["availability"]["widebody"]) in vals
    for stn, p in a["local_borrow"]["availability"]["narrowbody"].items():
        assert stn in vals and float(p) in vals
    tags = [ws.cell(r, 7).value for r in range(6, 20) if ws.cell(r, 2).value]
    assert tags and set(tags) == {"ASSUMED"}


# ------------------------------------------------------------------ 2. Python cross-check of the defaults
@needs_inputs
def test_float_reference_row_matches_analytic(wb, inputs, bw):
    from gnm.policy.analytic import float_calc
    pn = bw.default_float_pn(inputs["rot"])
    ex = next(e for e in inputs["rot"]["float_examples"] if e["pn"] == pn)
    ref = float_calc(ex["rate_per_30d"], ex["pipeline_days"], ex["rec_units"] + ex["loop_units"], ex["unit_cost_aed"])
    ws = wb[FLOAT]
    got = [ws.cell(29, c).value for c in range(3, 8)]
    exp = [ref[k] for k in ("pipeline_mean", "availability", "ebo", "expected_wait_days", "capital_aed")]
    assert got == pytest.approx(exp)
    assert ref["availability"] == pytest.approx(stats.poisson.cdf(ex["spares_total"]["recommended"] - 1,
                                                                  ref["pipeline_mean"]))


def _rop_like_sheet(rate, vmr, lt, lt_sd, sl, method="Auto", k_max=800):
    """Python mirror of the ROP sheet formulas (independent of the openpyxl file)."""
    m = rate * lt / 7
    v = vmr * m + rate ** 2 * (lt_sd / 7) ** 2
    use_nb = (method == "Negative binomial") or (method == "Auto" and m > 0 and v / m >= 1.05)
    k = np.arange(k_max + 1)
    if m <= 0:
        return 0
    if use_nb and v > m:
        p = m / v
        n = m * p / (1 - p)
        cdf = np.cumsum(np.exp(gammaln(k + n) - gammaln(n) - gammaln(k + 1) + n * np.log(p) + k * np.log(1 - p)))
    else:
        cdf = stats.poisson.cdf(k, m)
    return int((cdf < sl).sum())


@needs_inputs
def test_rop_logic_reproduces_frozen_hub_reorder_points(inputs, bw):
    import pandas as pd
    from gnm.policy.policies import reorder_point_from_row
    rop = bw.rop_examples(inputs["ff"], inputs["p1"], inputs["parts"])
    p2 = pd.read_csv(ROOT / "outputs" / "policies" / "P2_stock_params.csv").query("station == 'AUH'").set_index("pn")
    st = bw.service_targets(inputs)
    n_ce = sum(p["cls"] != "R" for p in inputs["parts"]["parts"])
    assert len(rop) == n_ce
    for _, r in rop.iterrows():
        sl = st[r.deadline_class]
        s_sheet = _rop_like_sheet(r.net_weekly_rate, r.vmr_net_week, r.lead_time_d, r.lead_time_sd_d, sl)
        assert s_sheet == r.p1_s == reorder_point_from_row(r, sl) == p2.loc[r.pn, "s"], r.pn


def test_rop_reference_row(wb, inputs, bw):
    from gnm.policy.policies import reorder_point_from_row
    rop = bw.rop_examples(inputs["ff"], inputs["p1"], inputs["parts"]).set_index("pn")
    pn = bw.default_rop_pn(rop.reset_index())
    assert wb[ROP]["C5"].value == pn
    r = rop.loc[pn]
    assert wb[ROP]["E40"].value == reorder_point_from_row(r, bw.service_targets(inputs)[r.deadline_class]) == r.p1_s


@needs_inputs
def test_aog_incidents_chosen_by_rule(wb, inputs, bw):
    incs = bw.showcase_incidents(inputs["incidents"], inputs["cfg"])
    assert incs[0]["id"] == inputs["incidents"]["ps1_incident_id"]
    assert incs[1]["id"] in inputs["incidents"]["showcase_ids"] and incs[1]["id"] != incs[0]["id"]
    txt = _all_text(wb)
    for inc in incs:
        assert f"Worked incident {inc['id']}" in txt
    # the pipeline exposures are reproduced by the Python rule
    win, eco = bw.window_hours(inputs["cfg"]), inputs["cfg"]["economics"]
    n = 0
    for inc in incs:
        for o in inc["options"]:
            if o["wait_h"] is None:
                continue
            _, ex = bw.exposure_rule(o["wait_h"], win[inc["deadline"]], o["fitting_h"],
                                     eco["aog_penalty_aed_per_hour"][inc["archetype"]],
                                     eco["aog_event_cost_aed"][inc["archetype"]], o["direct_cost"])
            assert ex == pytest.approx(o["exposure_aed"], abs=0.5)
            n += 1
    assert n >= 4


# ------------------------------------------------------------------ 3. formula evaluation (formulas package)
def _key(sheet, cell):
    return f"'[{NAME}]{sheet.upper()}'!{cell}"


@pytest.fixture(scope="module")
def model(built):
    formulas = pytest.importorskip("formulas")
    return formulas.ExcelModel().loads(str(built)).finish()


def _val(v):
    return v.value[0, 0] if hasattr(v, "value") else v


def _calc(model, sheet, inputs, outputs):
    sol = model.calculate(inputs={_key(sheet, c): v for c, v in inputs.items() if v is not None},
                          outputs=[_key(sheet, c) for c in outputs])
    return {c: _val(sol[_key(sheet, c)]) for c in outputs}


def _float_cases(inputs, bw):
    ex = inputs["rot"]["float_examples"]
    ps1 = bw.default_float_pn(inputs["rot"])
    others = [e["pn"] for e in ex if e["pn"] != ps1]
    return [({"C5": ps1, "C6": "I125"}, None),
            ({"C5": others[0], "C6": "P0"}, None),
            ({"C5": others[-1], "C6": "P2", "D9": 3.0, "D10": 40.0, "D11": 4, "D12": 1, "D13": 100000.0},
             (3.0, 40.0, 5, 100000.0))]


@needs_inputs
@pytest.mark.parametrize("case", range(3))
def test_float_calculator_evaluates(model, inputs, bw, case):
    from gnm.policy.analytic import float_calc
    ins, manual = _float_cases(inputs, bw)[case]
    ins = dict(ins)
    if manual is None:
        ex = next(e for e in inputs["rot"]["float_examples"] if e["pn"] == ins["C5"])
        units = {"P0": ex["p0_units"], "P1": ex["p1_units"], "P2": ex["p2_units"], "I125": ex["rec_units"]}[ins["C6"]]
        manual = (ex["rate_per_30d"], ex["pipeline_days"], units + ex["loop_units"], ex["unit_cost_aed"])
        assert manual[2] == ex["spares_total"]["recommended" if ins["C6"] == "I125" else ins["C6"]]
        for c in ("D9", "D10", "D11", "D12", "D13"):
            ins[c] = None
    exp = float_calc(*manual)
    got = _calc(model, FLOAT, ins, ["E14", "E17", "E18", "E19", "E20", "E21", "E24"])
    assert got["E14"] == manual[2]
    assert got["E17"] == pytest.approx(exp["pipeline_mean"], rel=1e-9)
    assert got["E18"] == pytest.approx(exp["availability"], rel=1e-9, abs=1e-12)
    assert got["E19"] == pytest.approx(exp["ebo"], rel=1e-7, abs=1e-9)
    assert got["E20"] == pytest.approx(exp["expected_wait_days"], rel=1e-7, abs=1e-9)
    assert got["E21"] == pytest.approx(exp["capital_aed"])
    if case < 2:
        assert got["E24"] == "MATCH"


def _rop_cases(inputs, bw):
    rop = bw.rop_examples(inputs["ff"], inputs["p1"], inputs["parts"])
    pn0 = bw.default_rop_pn(rop)
    pois = rop[(rop.dist_kind == "poisson") & (rop.pn != pn0)]
    other = (pois if len(pois) else rop[rop.pn != pn0]).pn.iloc[0]
    third = rop[~rop.pn.isin([pn0, other])].pn.iloc[0]
    return [(pn0, "Auto", {}), (other, "Auto", {}),
            (third, "Poisson", {"D9": 2.0, "D10": 1.0, "D11": 30.0, "D12": 0.0, "D15": 0.95})]


@needs_inputs
@pytest.mark.parametrize("case", range(3))
def test_rop_calculator_evaluates(model, inputs, bw, case):
    from gnm.policy.analytic import reorder_point
    pn, method, overrides = _rop_cases(inputs, bw)[case]
    rop = bw.rop_examples(inputs["ff"], inputs["p1"], inputs["parts"]).set_index("pn")
    ins = {"C5": pn, "C6": method, "D9": None, "D10": None, "D11": None, "D12": None, "D15": None}
    ins.update(overrides)
    got = _calc(model, ROP, ins, ["E21", "E22", "E24", "E29", "E37", "E39"])
    r = rop.loc[pn]
    if not overrides:
        assert got["E21"] == pytest.approx(r.ltd_mean, rel=1e-9)
        assert got["E22"] == pytest.approx(r.ltd_var, rel=1e-9)
        assert got["E29"] == r.p1_s == got["E37"]
        assert got["E39"] == "MATCH"
    else:
        mean = 2.0 * 30.0 / 7
        assert got["E21"] == pytest.approx(mean)
        assert got["E24"] == "Poisson"
        assert got["E29"] == reorder_point(mean, 0.95)


AOG_CASES = [  # archetype, window class, wait h, part class, fitting override, direct AED, hourly multiplier
    ("narrowbody", "D0", 9.0, "R", None, 2650.0, 1.0),
    ("widebody", "D3", 156.0, "R", 6.0, 1000.0, 0.5),
    ("narrowbody", "D10", 50.0, "E", None, 500.0, 2.0),   # on time: exposure = direct cost only
]


@needs_inputs
@pytest.mark.parametrize("case", AOG_CASES)
def test_aog_calculator_evaluates(model, inputs, bw, case):
    arch, dl, wait, pc, fit_o, direct, mult = case
    cfg = inputs["cfg"]
    win = bw.window_hours(cfg)[dl]
    fit = fit_o if fit_o is not None else bw.fitting_hours(cfg)[pc]
    eco = cfg["economics"]
    h, exp = bw.exposure_rule(wait, win, fit, eco["aog_penalty_aed_per_hour"][arch], eco["aog_event_cost_aed"][arch],
                              direct, mult)
    got = _calc(model, AOG, {"C6": arch, "C7": dl, "C8": wait, "C9": pc, "C10": fit_o, "C11": direct, "C12": mult},
                ["C16", "C17", "C19", "C22", "C23", "C24"])
    assert got["C16"] == win and got["C17"] == fit
    assert got["C19"] == pytest.approx(h)
    assert got["C23"] == pytest.approx(exp)
    assert got["C22"] == (float(eco["aog_event_cost_aed"][arch]) if wait > win else 0)
    assert got["C24"] == ("Yes" if wait <= win else "No")


@needs_inputs
def test_default_evaluation_checks(model, inputs, wb, bw):
    """Default recalculation: worked incidents reproduce the AOG lab, exception counts match actions.json."""
    sol = model.calculate()

    def val(sheet, cell):
        return _val(sol[_key(sheet, cell)])

    ws = wb[AOG]
    n_opts = 0
    for r in range(25, ws.max_row + 1):
        if ws[f"K{r}"].value and str(ws[f"K{r}"].value).startswith("=IF(ABS("):
            n_opts += 1
            assert val(AOG, f"K{r}") == "OK", r
            assert val(AOG, f"G{r}") == pytest.approx(ws[f"I{r}"].value, abs=0.5)
            if ws[f"J{r}"].value != "—":
                assert val(AOG, f"H{r}") == ws[f"J{r}"].value, r
    incs = bw.showcase_incidents(inputs["incidents"], inputs["cfg"])
    assert n_opts == sum(o["wait_h"] is not None for i in incs for o in i["options"])

    A = inputs["actions"]
    L = bw.exception_layout(A)
    rt = L["total_row"]
    assert wb[EXC][f"B{rt}"].value == "Total"
    assert val(EXC, f"F{rt}") == len(A["actions"]) == sum(A["counts"]["by_type"].values())
    sev = A["counts"]["by_severity"]
    assert [val(EXC, f"{c}{rt}") for c in "CDE"] == [sev.get("urgent", 0), sev.get("review", 0), sev.get("info", 0)]
    for i, t in enumerate(L["types"]):
        assert val(EXC, f"F{7 + i}") == A["counts"]["by_type"][t]
    for i, o in enumerate(L["owners"]):
        assert val(EXC, f"I{7 + i}") == sum(a["owner"] == o for a in A["actions"])
    assert val(ROP, "E39") == "MATCH"
    assert val(FLOAT, "E24") == "MATCH"
    n = len(inputs["parts"]["parts"])
    assert val("Part list", f"T{n + 7}") == sum(p["stock_total_p2"] for p in inputs["parts"]["parts"])
