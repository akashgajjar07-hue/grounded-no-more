#!/usr/bin/env python
"""Build excel/grounded_no_more_planner_workbook.xlsx (openpyxl, live formulas).

Every number written as a constant comes from a pipeline output or the config:
  docs/data/parts.json, docs/data/rotables.json, docs/data/kpis.json, docs/data/manifest.json,
  outputs/forecasting/final_forecasts.parquet, outputs/policies/P1_stock_params.csv,
  outputs/actions/actions.json, outputs/aog_lab/incidents.json,
  config/assumptions.yaml (service targets, AOG penalty, deadline slack, carrying rate) and
  config/policy.yaml (PO ordering cost).
Everything the calculators compute is an Excel formula, so the sheets recalculate when inputs change.
The "Python reference" rows are computed here with gnm.policy.analytic for the default inputs only.

Usage:  python scripts/build_workbook.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from gnm.config import load_config
from gnm.policy import analytic
from gnm.policy.policies import reorder_point_from_row

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "excel" / "grounded_no_more_planner_workbook.xlsx"
DISCLAIMER = ("Independent educational simulation. Not an airline system or an approved maintenance, "
              "airworthiness or dispatch tool.")

# ---------------------------------------------------------------- design tokens (docs/design/tokens.json)
TOK = json.loads((ROOT / "docs" / "design" / "tokens.json").read_text())["color"]
HEX = {k: v.lstrip("#").upper() for k, v in TOK.items() if v.startswith("#")}
FONT = "Inter"  # Excel substitutes Calibri / the system UI font where Inter is not installed
PROV_COLOR = {"REAL": HEX["aero_teal"], "DERIVED": HEX["titanium"], "ASSUMED": HEX["amber"], "SIMULATED": HEX["copper"]}

F_MID = PatternFill("solid", fgColor=HEX["midnight"])
F_STEEL = PatternFill("solid", fgColor=HEX["deep_steel"])
F_CARD = PatternFill("solid", fgColor=HEX["card"])
F_INPUT = PatternFill("solid", fgColor="1B3550")
F_OUT = PatternFill("solid", fgColor="0E2A33")
TEAL_SIDE = Side(style="thin", color=HEX["aero_teal"])
HAIR = Side(style="thin", color="2A3C50")
B_INPUT = Border(left=TEAL_SIDE, right=TEAL_SIDE, top=TEAL_SIDE, bottom=TEAL_SIDE)
B_HAIR = Border(bottom=HAIR)

AED = '"AED "#,##0'
PCT = "0.0%"
PCT2 = "0.00%"
NUM1 = "#,##0.0"
NUM2 = "#,##0.00"
NUM3 = "0.000"
INT = "#,##0"


def font(color="titanium", size=11, bold=False, italic=False):
    return Font(name=FONT, size=size, bold=bold, italic=italic, color=HEX.get(color, color))


def paint(ws, rows: int, cols: int, fill=F_MID):
    """Dark canvas: fill the visible working area and set the default text colour."""
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            cell = ws.cell(r, c)
            cell.fill = fill
            cell.font = font()
    ws.sheet_view.showGridLines = False


def put(ws, ref, value, *, f=None, fill=None, fmt=None, align=None, border=None):
    cell = ws[ref]
    cell.value = value
    if f is not None:
        cell.font = f
    if fill is not None:
        cell.fill = fill
    if fmt is not None:
        cell.number_format = fmt
    if align is not None:
        cell.alignment = align
    if border is not None:
        cell.border = border
    return cell


def title(ws, text, sub=None):
    put(ws, "B1", text, f=font("ice", 18, bold=True))
    ws.row_dimensions[1].height = 30
    if sub:
        put(ws, "B2", sub, f=font("titanium", 11, italic=True))
    put(ws, "B3", DISCLAIMER, f=font("amber", 9, italic=True))


def header_row(ws, row, col0, labels, widths=None):
    for i, lab in enumerate(labels):
        c = ws.cell(row, col0 + i, lab)
        c.fill = F_STEEL
        c.font = font("aero_teal", 11, bold=True)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    if widths:
        for i, w in enumerate(widths):
            ws.column_dimensions[get_column_letter(col0 + i)].width = w


def prov(ws, ref, tag):
    put(ws, ref, tag, f=font(PROV_COLOR[tag], 10, bold=True))


def as_input(cell, fmt=None):
    cell.fill = F_INPUT
    cell.border = B_INPUT
    cell.font = font("ice", 11, bold=True)
    if fmt:
        cell.number_format = fmt


def as_output(cell, fmt=None):
    cell.fill = F_OUT
    cell.font = font("aero_teal", 12, bold=True)
    if fmt:
        cell.number_format = fmt


def section(ws, ref, text):
    put(ws, ref, text, f=font("aero_teal", 13, bold=True))


# ---------------------------------------------------------------- data
def load_inputs() -> dict:
    cfg = load_config()
    pcfg = yaml.safe_load((ROOT / "config" / "policy.yaml").read_text())
    parts = json.loads((ROOT / "docs" / "data" / "parts.json").read_text())
    rot = json.loads((ROOT / "docs" / "data" / "rotables.json").read_text())
    kpis = json.loads((ROOT / "docs" / "data" / "kpis.json").read_text())
    manifest = json.loads((ROOT / "docs" / "data" / "manifest.json").read_text())
    actions = json.loads((ROOT / "outputs" / "actions" / "actions.json").read_text())
    incidents = json.loads((ROOT / "outputs" / "aog_lab" / "incidents.json").read_text())
    ff = pd.read_parquet(ROOT / "outputs" / "forecasting" / "final_forecasts.parquet")
    p1 = pd.read_csv(ROOT / "outputs" / "policies" / "P1_stock_params.csv")
    return dict(cfg=cfg, pcfg=pcfg, parts=parts, rot=rot, kpis=kpis, manifest=manifest, actions=actions,
                incidents=incidents, ff=ff, p1=p1)


def order_cost(pcfg: dict) -> float:
    def walk(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "ordering_cost_aed_per_po":
                    return float(v)
                r = walk(v)
                if r is not None:
                    return r
        return None
    return walk(pcfg)


def rop_examples(ff: pd.DataFrame, p1: pd.DataFrame, parts: dict) -> pd.DataFrame:
    """Hub (AUH) C/E planning rows: network demand over the planner lead-time estimate."""
    hub = ff[(ff.station == "AUH") & (ff.part_class != "R")].copy()
    s1 = p1[(p1.station == "AUH")].set_index("pn")
    desc = {p["pn"]: p["desc"] for p in parts["parts"]}
    cost = {p["pn"]: p["unit_cost"] for p in parts["parts"]}
    planted = {p["pn"]: p["planted"] or "" for p in parts["parts"]}
    hub["desc"] = hub.pn.map(desc)
    hub["unit_cost_aed"] = hub.pn.map(cost)
    hub["p1_s"] = hub.pn.map(s1["s"])
    hub["p1_S"] = hub.pn.map(s1["S"])
    hub["planted"] = hub.pn.map(planted)
    return hub.sort_values(["planted", "pn"], ascending=[False, True]).reset_index(drop=True)


# ---------------------------------------------------------------- sheets
def sheet_readme(wb, d):
    ws = wb.active
    ws.title = "README"
    paint(ws, 70, 8)
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 70
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 14
    title(ws, "GROUNDED NO MORE · Planner workbook",
          "Falcon Hub Airways (fictional): spare-parts planning calculators built on the frozen pipeline outputs")
    put(ws, "B5", "DISCLAIMER", f=font("amber", 12, bold=True))
    put(ws, "C5", DISCLAIMER, f=font("ice", 12, bold=True), align=Alignment(wrap_text=True))
    ws.row_dimensions[5].height = 34
    put(ws, "C6", "All data is SIMULATED for a fictional airline. No real airline, OEM or operator data is used; "
                  "deadline classes D0/D3/D10 are hypothetical simulation classes, not MEL categories.",
        f=font("titanium", 10, italic=True), align=Alignment(wrap_text=True))
    ws.row_dimensions[6].height = 28

    section(ws, "B8", "Purpose")
    put(ws, "C8", "A hands-on companion to the GROUNDED NO MORE case study. A materials planner can size a rotable "
                  "float, set a reorder point, triage the week-103 exception list and price an AOG decision, with "
                  "every result shown as a live Excel formula.",
        align=Alignment(wrap_text=True, vertical="top"))
    ws.row_dimensions[8].height = 48

    section(ws, "B10", "Sheets")
    header_row(ws, 11, 2, ["Sheet", "What it does", "Provenance"])
    sheets = [
        ("Part list", "120 fictional PNs with master attributes, demand class, P0 / P2 / I125 stock units and risk hours. "
                      "Δ units and stock value are formulas.", "SIMULATED"),
        ("Float calculator", "Palm / Poisson rotable float: pipeline mean, availability P(X<S), EBO from a 0..60 table, "
                             "expected wait and capital. PN picker looks up the 40 example rotables.", "DERIVED"),
        ("Rotable examples", "Lookup table for the float calculator (docs/data/rotables.json float_examples).", "DERIVED"),
        ("ROP calculator", "Consumable / expendable reorder point: lead-time demand mean and variance, Poisson or "
                           "negative-binomial cumulative table, service level by deadline class.", "DERIVED"),
        ("ROP examples", "Lookup table for the ROP calculator: AUH planning rows from final_forecasts.parquet and the "
                         "frozen P1/P2 hub reorder point.", "DERIVED"),
        ("Exception list", "The 75 planner exceptions for week 103 (outputs/actions/actions.json) with filters, "
                           "severity colours and a live COUNTIFS summary.", "DERIVED"),
        ("AOG exposure", "Exposure = max(0, wait − deadline slack) × AOG penalty by archetype + direct cost; two worked "
                         "incidents checked against the AOG lab output.", "ASSUMED"),
    ]
    r = 12
    for name, what, tag in sheets:
        put(ws, f"B{r}", name, f=font("ice", 11, bold=True))
        put(ws, f"C{r}", what, align=Alignment(wrap_text=True, vertical="top"))
        prov(ws, f"D{r}", tag)
        ws.row_dimensions[r].height = 32
        r += 1

    r += 1
    section(ws, f"B{r}", "Provenance legend")
    r += 1
    legend = [
        ("REAL", "Public real-world data (station coordinates, the Monash Car Parts benchmark)."),
        ("DERIVED", "Computed by the project's code from other data (forecasts, policies, aggregations)."),
        ("ASSUMED", "A planning assumption set in config (AOG penalty, service targets, costs); sensitivity-tested."),
        ("SIMULATED", "Produced by the simulator for the fictional airline (history, parts master, KPIs)."),
    ]
    for tag, text in legend:
        c = put(ws, f"B{r}", tag, f=Font(name=FONT, bold=True, color=HEX["midnight"]),
                fill=PatternFill("solid", fgColor=PROV_COLOR[tag]), align=Alignment(horizontal="center"))
        c.border = B_HAIR
        put(ws, f"C{r}", text, align=Alignment(wrap_text=True))
        r += 1

    r += 1
    section(ws, f"B{r}", "Cell conventions")
    r += 1
    c = put(ws, f"B{r}", "Input")
    as_input(c)
    put(ws, f"C{r}", "Editable input (teal border). Override cells are blank by default: leave blank to use the looked-up value.")
    r += 1
    c = put(ws, f"B{r}", "Output")
    as_output(c)
    put(ws, f"C{r}", "Live formula result. Money is AED #,##0; shares are 0.0%.")
    r += 2

    section(ws, f"B{r}", "Headline (holdout, seeds 1000–1019)")
    r += 1
    header_row(ws, r, 2, ["KPI", "Note", "P0 legacy", "I125 recommended", "Provenance"])
    r += 1
    labels = {"immediate_fill_rate": ("Immediate fill rate", PCT), "aog_hours": ("Material AOG hours / year", INT),
              "spare_capital_aed": ("Spare capital", AED), "total_annual_cost_aed": ("Total annual cost (excl. capital)", AED),
              "aog_events": ("AOG events / year", NUM1)}
    for k in d["kpis"]["kpis"]:
        if k["id"] not in labels:
            continue
        lab, fmt = labels[k["id"]]
        put(ws, f"B{r}", lab, f=font("ice"))
        put(ws, f"C{r}", "mean over 20 holdout seeds (docs/data/kpis.json)", f=font("slate", 10, italic=True))
        put(ws, f"D{r}", k["baseline"], fmt=fmt)
        put(ws, f"E{r}", k["value"], fmt=fmt, f=font("aero_teal", 11, bold=True))
        prov(ws, f"F{r}", k["provenance"])
        r += 1

    r += 1
    section(ws, f"B{r}", "Sources and rebuild")
    r += 1
    meta = d["manifest"]["meta"]
    srcs = [
        ("Site data", f"docs/data/*.json, exported {meta['generated_at']} (git {meta['git_sha']})"),
        ("Pipeline outputs", "outputs/forecasting/final_forecasts.parquet, outputs/policies/P1_stock_params.csv, "
                             "outputs/actions/actions.json, outputs/aog_lab/incidents.json"),
        ("Assumptions", "config/assumptions.yaml (service targets, AOG penalty, deadline slack, carrying rate), "
                        "config/policy.yaml (PO ordering cost)"),
        ("Rebuild", "python scripts/build_workbook.py   ·   verify: pytest tests/test_workbook.py"),
    ]
    for a, b in srcs:
        put(ws, f"B{r}", a, f=font("ice", 11, bold=True))
        put(ws, f"C{r}", b, align=Alignment(wrap_text=True))
        ws.row_dimensions[r].height = 30
        r += 1


def sheet_parts(wb, d):
    ws = wb.create_sheet("Part list")
    rows = d["parts"]["parts"]
    n = len(rows)
    cols = [  # (header, key or formula, width, fmt, provenance)
        ("PN", "pn", 13, None, "SIMULATED"),
        ("Description", "desc", 34, None, "SIMULATED"),
        ("ATA", "ata", 6, None, "SIMULATED"),
        ("ATA chapter", "ata_name", 20, None, "SIMULATED"),
        ("Class", "cls", 7, None, "SIMULATED"),
        ("Deadline", "deadline", 9, None, "ASSUMED"),
        ("Demand class", "demand_class", 15, None, "DERIVED"),
        ("ADI", "adi", 7, NUM2, "DERIVED"),
        ("CV²", "cv2", 7, NUM2, "DERIVED"),
        ("ABC", "abc", 6, None, "DERIVED"),
        ("Unit cost", "unit_cost", 14, AED, "SIMULATED"),
        ("Quoted LT (d)", "lt_quoted_d", 10, NUM1, "SIMULATED"),
        ("Est. LT (d)", "lt_est_d", 10, NUM1, "DERIVED"),
        ("Annual usage (qty)", "annual_usage_qty", 11, NUM1, "DERIVED"),
        ("Annual usage value", "annual_usage_value_aed", 15, AED, "DERIVED"),
        ("P0 units", "stock_total_p0", 9, INT, "DERIVED"),
        ("P2 units", "stock_total_p2", 9, INT, "DERIVED"),
        ("I125 units", "stock_total", 9, INT, "DERIVED"),
        ("Δ I125 − P0", "=S{r}-Q{r}", 10, '+#,##0;-#,##0;0', "DERIVED"),
        ("I125 value at target", "=S{r}*L{r}", 16, AED, "DERIVED"),
        ("Risk h / yr", "risk_hours", 10, NUM1, "DERIVED"),
        ("Risk level", "risk_level", 10, None, "DERIVED"),
        ("Champion", "champion", 11, None, "DERIVED"),
        ("Planted", "planted", 8, None, "SIMULATED"),
        ("Row provenance", "provenance", 13, None, "SIMULATED"),
    ]
    last_col = len(cols) + 1
    paint(ws, n + 8, last_col + 1)
    ws.column_dimensions["A"].width = 3
    title(ws, "Part list (120 fictional PNs)",
          "docs/data/parts.json · units: P0 legacy, P2 network, I125 recommended (targets across all stations). "
          "Row 4 shows each column's provenance.")
    for i, (h, _, w, _, tag) in enumerate(cols):
        col = get_column_letter(i + 2)
        prov(ws, f"{col}4", tag)
        ws.column_dimensions[col].width = w
    header_row(ws, 5, 2, [c[0] for c in cols])
    ws.row_dimensions[5].height = 32
    for j, p in enumerate(rows):
        r = 6 + j
        for i, (_, key, _, fmt, _) in enumerate(cols):
            col = get_column_letter(i + 2)
            if key.startswith("="):
                v = key.format(r=r)
            else:
                v = p.get(key)
                if key == "planted" and v is None:
                    v = ""
            c = ws[f"{col}{r}"]
            c.value = v
            c.fill = F_CARD if j % 2 == 0 else F_MID
            c.font = font("ice" if i == 0 else "titanium", 10, bold=(i == 0))
            if fmt:
                c.number_format = fmt
        ws[f"Z{r}"].font = font(PROV_COLOR.get(p.get("provenance", "SIMULATED"), HEX["titanium"]), 10, bold=True)
    end = 5 + n
    ws.auto_filter.ref = f"B5:{get_column_letter(last_col)}{end}"
    ws.freeze_panes = "D6"
    risk = f"W6:W{end}"
    ws.conditional_formatting.add(risk, CellIsRule(operator="equal", formula=['"urgent"'], font=Font(color=HEX["red"], bold=True)))
    ws.conditional_formatting.add(risk, CellIsRule(operator="equal", formula=['"review"'], font=Font(color=HEX["amber"], bold=True)))
    ws.conditional_formatting.add(f"Y6:Y{end}", FormulaRule(formula=['LEN($Y6)>0'], font=Font(color=HEX["copper"], bold=True)))
    put(ws, f"B{end + 2}", "Total (all 120 PNs)", f=font("ice", 11, bold=True))
    put(ws, f"B{end + 3}", "Visible rows (filtered)", f=font("ice", 11, bold=True))
    for col in ("Q", "R", "S", "T", "U"):
        c = put(ws, f"{col}{end + 2}", f"=SUM({col}6:{col}{end})")
        as_output(c, AED if col == "U" else INT)
        c = put(ws, f"{col}{end + 3}", f"=SUBTOTAL(9,{col}6:{col}{end})")
        as_output(c, AED if col == "U" else INT)
    put(ws, f"B{end + 4}", "SUBTOTAL respects the filter: filter by class, ATA or risk level to see the subset.",
        f=font("slate", 9, italic=True))


def sheet_rotable_examples(wb, d):
    ws = wb.create_sheet("Rotable examples")
    ex = d["rot"]["float_examples"]
    paint(ws, len(ex) + 8, 15)
    ws.column_dimensions["A"].width = 13
    title_cells = ["PN", "Description", "Deadline", "Removals / 30 d", "Pipeline days", "Unit cost", "Loop units",
                   "P0", "P1", "P2", "I125", "Planted", "Provenance"]
    put(ws, "A1", "Rotable examples (float calculator lookup)", f=font("ice", 16, bold=True))
    put(ws, "A2", "docs/data/rotables.json float_examples: network removal rate, hub T_eff (pipeline days), serviceable "
                  "base stock by policy; Palm total spares = units + loop units (units the engine seeds in the repair loop).",
        f=font("titanium", 10, italic=True))
    put(ws, "A3", DISCLAIMER, f=font("amber", 9, italic=True))
    header_row(ws, 4, 1, title_cells, [13, 30, 9, 13, 12, 13, 10, 7, 7, 7, 7, 9, 11])
    for j, e in enumerate(ex):
        r = 5 + j
        vals = [e["pn"], e["desc"], e["deadline"], e["rate_per_30d"], e["pipeline_days"], e["unit_cost_aed"],
                e["loop_units"], e["p0_units"], e["p1_units"], e["p2_units"], e["rec_units"], e["planted"] or "",
                e["provenance"]]
        fmts = [None, None, None, NUM3, NUM1, AED, INT, INT, INT, INT, INT, None, None]
        for i, (v, fm) in enumerate(zip(vals, fmts)):
            c = ws.cell(r, i + 1, v)
            c.fill = F_CARD if j % 2 == 0 else F_MID
            c.font = font("ice" if i == 0 else "titanium", 10)
            if fm:
                c.number_format = fm
        ws.cell(r, 13).font = font(PROV_COLOR[e["provenance"]], 10, bold=True)
    ws.freeze_panes = "B5"
    return len(ex)


def sheet_float(wb, d, n_ex):
    ws = wb.create_sheet("Float calculator")
    paint(ws, 95, 16)
    for col, w in zip("ABCDEFGH", [3, 38, 18, 16, 18, 10, 12, 60]):
        ws.column_dimensions[col].width = w
    title(ws, "Rotable float calculator (Palm / Poisson)",
          "Pipeline X ~ Poisson(μ), μ = removals per day × pipeline days. Availability = P(X < S), which by PASTA equals "
          "the immediate fill rate. EBO = E[max(X − S, 0)].")
    exr = f"'Rotable examples'!$A$5:$M${4 + n_ex}"
    pncol = f"'Rotable examples'!$A$5:$A${4 + n_ex}"

    put(ws, "B5", "Pick a PN", f=font("ice", 11, bold=True))
    c = put(ws, "C5", "GN-28-R031")
    as_input(c)
    put(ws, "B6", "Policy preset for S", f=font("ice", 11, bold=True))
    c = put(ws, "C6", "I125")
    as_input(c)
    put(ws, "D5", f"=VLOOKUP($C$5,{exr},2,FALSE)", f=font("titanium", 11, italic=True))
    put(ws, "D6", "P0 legacy · P1 local · P2 network · I125 recommended", f=font("slate", 9, italic=True))
    dv = DataValidation(type="list", formula1=f"={pncol}", allow_blank=False)
    dv2 = DataValidation(type="list", formula1='"P0,P1,P2,I125"', allow_blank=False)
    ws.add_data_validation(dv)
    ws.add_data_validation(dv2)
    dv.add("C5")
    dv2.add("C6")

    header_row(ws, 8, 2, ["Input", "From example", "Override", "Used", "Unit", "Provenance", "Note"])
    rows = [
        (9, "Removals per 30 days", f"=VLOOKUP($C$5,{exr},4,FALSE)", NUM3, "per 30 d", "DERIVED",
         "Network reliability-exposure removal rate (Gamma–Poisson posterior × planned exposure)"),
        (10, "Repair pipeline / TAT (days)", f"=VLOOKUP($C$5,{exr},5,FALSE)", NUM1, "days", "DERIVED",
         "Hub T_eff: transport + quoted TAT + observed lateness, with condemnation via purchase lead time"),
        (11, "Spares S (total float)",
         f"=INDEX('Rotable examples'!$H$5:$K${4 + n_ex},MATCH($C$5,{pncol},0),MATCH($C$6,'Rotable examples'!$H$4:$K$4,0))"
         f"+VLOOKUP($C$5,{exr},7,FALSE)", INT, "units", "DERIVED",
         "Serviceable base stock for the chosen policy + units seeded in the repair loop (Palm counts both)"),
        (12, "Unit cost", f"=VLOOKUP($C$5,{exr},6,FALSE)", AED, "AED", "SIMULATED", "Fictional master-data price"),
    ]
    for r, lab, fx, fmt, unit, tag, note in rows:
        put(ws, f"B{r}", lab, f=font("ice"))
        put(ws, f"C{r}", fx, fmt=fmt)
        c = put(ws, f"D{r}", None)
        as_input(c, fmt)
        c = put(ws, f"E{r}", f'=IF(D{r}="",C{r},D{r})')
        as_output(c, fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        prov(ws, f"G{r}", tag)
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))
    put(ws, "B13", "of which loop units", f=font("slate", 10, italic=True))
    put(ws, "C13", f"=VLOOKUP($C$5,{exr},7,FALSE)", fmt=INT, f=font("slate", 10, italic=True))

    header_row(ws, 15, 2, ["Output", "", "", "Value", "Unit", "", "Formula"])
    T0, T1 = 31, 91  # x = 0..60 table rows
    xs, pmf = f"$B${T0}:$B${T1}", f"$C${T0}:$C${T1}"
    outs = [
        (16, "Pipeline mean μ", "=E9*E10/30", NUM2, "units", "μ = (removals / 30) × pipeline days"),
        (17, "Availability P(X < S)", "=IF(E11<=0,0,_xlfn.POISSON.DIST(E11-1,E16,TRUE))", PCT, "",
         "POISSON.DIST(S−1, μ, TRUE)"),
        (18, "Expected backorders (EBO)", f"=E16-E11+SUMPRODUCT(({xs}<E11)*(E11-{xs})*{pmf})", NUM3, "units",
         "μ − S + Σ_(x<S) (S − x)·P(X=x), SUMPRODUCT over the 0..60 table (exact for S ≤ 61)"),
        (19, "Expected wait per removal", "=IF(E9>0,E18/(E9/30),0)", NUM2, "days", "Little's law: EBO / λ"),
        (20, "Capital in the float", "=E11*E12", AED, "AED", "S × unit cost (total float incl. loop units)"),
        (21, "Annual removals", "=E9*365/30", NUM1, "per yr", "λ × 365"),
        (22, "Expected backorder-days per year", "=E18*365", NUM1, "unit-days", "EBO × 365"),
    ]
    for r, lab, fx, fmt, unit, note in outs:
        put(ws, f"B{r}", lab, f=font("ice"))
        c = put(ws, f"E{r}", fx)
        as_output(c, fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))

    # Python reference for the default inputs
    ex = next(e for e in d["rot"]["float_examples"] if e["pn"] == "GN-28-R031")
    s_def = ex["rec_units"] + ex["loop_units"]
    ref = analytic.float_calc(ex["rate_per_30d"], ex["pipeline_days"], s_def, ex["unit_cost_aed"])
    section(ws, "B24", "Python reference for the default inputs (GN-28-R031, I125)")
    put(ws, "B25", "gnm.policy.analytic.float_calc", f=font("slate", 10, italic=True))
    for i, (lab, key, fmt) in enumerate([("μ", "pipeline_mean", NUM2), ("Availability", "availability", PCT2),
                                          ("EBO", "ebo", NUM3), ("Wait (d)", "expected_wait_days", NUM2),
                                          ("Capital", "capital_aed", AED)]):
        col = get_column_letter(3 + i)
        put(ws, f"{col}25", lab, f=font("slate", 10))
        put(ws, f"{col}26", ref[key], fmt=fmt, f=font("titanium", 10))
    prov(ws, "H26", "DERIVED")
    put(ws, "H25", "Matches the outputs above while the inputs are the defaults.", f=font("slate", 9, italic=True))

    section(ws, "B29", "Poisson table (x = 0..60)")
    header_row(ws, 30, 2, ["x", "P(X = x)", "P(X ≤ x)", "Availability if S = x", "EBO if S = x"])
    for k in range(61):
        r = T0 + k
        put(ws, f"B{r}", k, fmt=INT)
        put(ws, f"C{r}", f"=_xlfn.POISSON.DIST(B{r},$E$16,FALSE)", fmt="0.0000")
        put(ws, f"D{r}", f"=_xlfn.POISSON.DIST(B{r},$E$16,TRUE)", fmt="0.0000")
        put(ws, f"E{r}", f"=IF(B{r}=0,0,D{r - 1})" if k else "=0", fmt=PCT)
        put(ws, f"F{r}", f"=$E$16-B{r}+SUMPRODUCT(({xs}<B{r})*(B{r}-{xs})*{pmf})", fmt=NUM3)
        for col in "BCDEF":
            ws[f"{col}{r}"].fill = F_CARD if k % 2 == 0 else F_MID
    ch = LineChart()
    ch.title = "Availability vs spares S"
    ch.y_axis.title = "P(X < S)"
    ch.x_axis.title = "S"
    ch.height, ch.width = 8, 16
    ch.add_data(Reference(ws, min_col=5, min_row=30, max_row=T1), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=2, min_row=T0, max_row=T1))
    ch.series[0].graphicalProperties.line.solidFill = HEX["aero_teal"]
    ch.series[0].graphicalProperties.line.width = 22000
    ch.legend = None
    ws.add_chart(ch, "J5")
    ws.freeze_panes = "A8"


def sheet_rop_examples(wb, rop: pd.DataFrame):
    ws = wb.create_sheet("ROP examples")
    paint(ws, len(rop) + 8, 16)
    cols = [("PN", "pn", 13, None), ("Description", "desc", 30, None), ("Class", "part_class", 7, None),
            ("Deadline", "deadline_class", 9, None), ("Weekly network demand", "net_weekly_rate", 12, NUM3),
            ("Weekly VMR", "vmr_net_week", 10, NUM3), ("Lead time (d)", "lead_time_d", 10, NUM1),
            ("Lead time sd (d)", "lead_time_sd_d", 10, NUM1), ("Quoted LT (d)", "lt_quoted_d", 10, NUM1),
            ("Unit cost", "unit_cost_aed", 12, AED), ("LTD mean", "ltd_mean", 10, NUM2), ("LTD var", "ltd_var", 10, NUM2),
            ("Dist", "dist_kind", 9, None), ("P1/P2 hub s", "p1_s", 9, INT), ("P1/P2 hub S", "p1_S", 9, INT),
            ("Planted", "planted", 8, None)]
    put(ws, "A1", "ROP examples (reorder-point calculator lookup)", f=font("ice", 16, bold=True))
    put(ws, "A2", "AUH rows of outputs/forecasting/final_forecasts.parquet (network demand over the planner lead-time "
                  "estimate) and the frozen hub reorder point from outputs/policies/P1_stock_params.csv. All DERIVED.",
        f=font("titanium", 10, italic=True))
    put(ws, "A3", DISCLAIMER, f=font("amber", 9, italic=True))
    header_row(ws, 4, 1, [c[0] for c in cols], [c[2] for c in cols])
    ws.row_dimensions[4].height = 32
    for j, row in rop.iterrows():
        r = 5 + j
        for i, (_, key, _, fm) in enumerate(cols):
            v = row[key]
            v = v.item() if hasattr(v, "item") else v
            c = ws.cell(r, i + 1, v)
            c.fill = F_CARD if j % 2 == 0 else F_MID
            c.font = font("ice" if i == 0 else "titanium", 10)
            if fm:
                c.number_format = fm
    ws.freeze_panes = "B5"
    return len(rop)


def sheet_rop(wb, d, n_rop, rop: pd.DataFrame):
    ws = wb.create_sheet("ROP calculator")
    K_MAX = 800
    T0 = 46
    T1 = T0 + K_MAX
    paint(ws, 50, 16)
    for col, w in zip("ABCDEFGH", [3, 40, 18, 16, 18, 12, 12, 62]):
        ws.column_dimensions[col].width = w
    title(ws, "Reorder-point calculator (consumables and expendables)",
          "s = smallest stock level with P(lead-time demand ≤ s) ≥ cycle service level. Poisson, or negative binomial "
          "when the lead-time demand is overdispersed (variance / mean ≥ 1.05, the pipeline's rule).")
    exr = f"'ROP examples'!$A$5:$P${4 + n_rop}"
    pncol = f"'ROP examples'!$A$5:$A${4 + n_rop}"
    cfg = d["cfg"]
    st = {k: float(v) for k, v in cfg["service_targets"].items() if k in ("D0", "D3", "D10")}
    carry = float(cfg["economics"]["carrying_cost_pct_per_year"])
    k_po = order_cost(d["pcfg"])

    put(ws, "B5", "Pick a PN (AUH planning row)", f=font("ice", 11, bold=True))
    c = put(ws, "C5", "GN-30-E025")
    as_input(c)
    put(ws, "D5", f"=VLOOKUP($C$5,{exr},2,FALSE)", f=font("titanium", 11, italic=True))
    put(ws, "B6", "Distribution", f=font("ice", 11, bold=True))
    c = put(ws, "C6", "Auto")
    as_input(c)
    put(ws, "D6", "Auto · Poisson · Negative binomial", f=font("slate", 9, italic=True))
    dv = DataValidation(type="list", formula1=f"={pncol}", allow_blank=False)
    dv2 = DataValidation(type="list", formula1='"Auto,Poisson,Negative binomial"', allow_blank=False)
    dv3 = DataValidation(type="list", formula1='"D0,D3,D10"', allow_blank=True)
    for v in (dv, dv2, dv3):
        ws.add_data_validation(v)
    dv.add("C5")
    dv2.add("C6")
    dv3.add("D13")

    header_row(ws, 8, 2, ["Input", "From pipeline", "Override", "Used", "Unit", "Provenance", "Note"])
    rows = [
        (9, "Weekly demand (network, at the hub)", f"=VLOOKUP($C$5,{exr},5,FALSE)", NUM3, "units/wk", "DERIVED",
         "Champion forecast (frozen) of network demand"),
        (10, "Weekly variance-to-mean ratio", f"=VLOOKUP($C$5,{exr},6,FALSE)", NUM3, "", "DERIVED",
         "Last 52 history weeks, network level"),
        (11, "Lead time mean (days)", f"=VLOOKUP($C$5,{exr},7,FALSE)", NUM1, "days", "DERIVED",
         "Planner estimate (recency-weighted receipts; catches PS4). Quoted value in row 14"),
        (12, "Lead time sd (days)", f"=VLOOKUP($C$5,{exr},8,FALSE)", NUM1, "days", "DERIVED", ""),
        (13, "Deadline class", f"=VLOOKUP($C$5,{exr},4,FALSE)", None, "", "ASSUMED",
         "Hypothetical D0/D3/D10 simulation class (not MEL)"),
    ]
    for r, lab, fx, fmt, unit, tag, note in rows:
        put(ws, f"B{r}", lab, f=font("ice"))
        put(ws, f"C{r}", fx, fmt=fmt)
        c = put(ws, f"D{r}", None)
        as_input(c, fmt)
        c = put(ws, f"E{r}", f'=IF(D{r}="",C{r},D{r})')
        as_output(c, fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        prov(ws, f"G{r}", tag)
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))
    put(ws, "B14", "Quoted lead time (master data)", f=font("slate", 10, italic=True))
    put(ws, "C14", f"=VLOOKUP($C$5,{exr},9,FALSE)", fmt=NUM1, f=font("slate", 10, italic=True))
    prov(ws, "G14", "SIMULATED")
    # service level: lookup from the deadline class, override allowed
    put(ws, "B15", "Cycle service level", f=font("ice"))
    put(ws, "C15", "=VLOOKUP(E13,$J$9:$K$11,2,FALSE)", fmt=PCT)
    c = put(ws, "D15", None)
    as_input(c, PCT)
    c = put(ws, "E15", '=IF(D15="",C15,D15)')
    as_output(c, PCT)
    prov(ws, "G15", "ASSUMED")
    put(ws, "H15", "config service_targets by deadline class (table at J8)", f=font("titanium", 9, italic=True))
    for r, lab, v, fmt, unit, tag, note in [
        (16, "Unit cost", f"=VLOOKUP($C$5,{exr},10,FALSE)", AED, "AED", "SIMULATED", "Fictional master-data price"),
        (17, "Ordering cost K per PO", k_po, AED, "AED", "ASSUMED", "config/policy.yaml ordering_cost_aed_per_po"),
        (18, "Carrying rate per year", carry, PCT, "", "ASSUMED", "config economics.carrying_cost_pct_per_year"),
    ]:
        put(ws, f"B{r}", lab, f=font("ice"))
        if isinstance(v, str):
            put(ws, f"C{r}", v, fmt=fmt)
            c = put(ws, f"D{r}", None)
            as_input(c, fmt)
            c = put(ws, f"E{r}", f'=IF(D{r}="",C{r},D{r})')
            as_output(c, fmt)
        else:
            c = put(ws, f"E{r}", v)
            as_input(c, fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        prov(ws, f"G{r}", tag)
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True))

    header_row(ws, 8, 10, ["Deadline", "Service target"])
    ws.column_dimensions["J"].width = 11
    ws.column_dimensions["K"].width = 14
    for i, k in enumerate(("D0", "D3", "D10")):
        put(ws, f"J{9 + i}", k, f=font("ice"))
        c = put(ws, f"K{9 + i}", st[k])
        as_input(c, PCT)
    prov(ws, "J12", "ASSUMED")

    header_row(ws, 20, 2, ["Output", "", "", "Value", "Unit", "", "Formula"])
    kx = f"$B${T0}:$B${T1}"
    pc = f"$C${T0}:$C${T1}"
    nc = f"$E${T0}:$E${T1}"
    outs = [
        (21, "Lead-time demand mean", "=E9*E11/7", NUM2, "units", "weekly demand × lead time / 7"),
        (22, "Lead-time demand variance", "=E10*E21+E9^2*(E12/7)^2", NUM2, "units²",
         "VMR × mean + demand² × (lead-time sd in weeks)²"),
        (23, "Variance / mean", "=IF(E21>0,E22/E21,0)", NUM2, "", ""),
        (24, "Distribution used", '=IF(C6="Auto",IF(E23>=1.05,"Negative binomial","Poisson"),C6)', None, "",
         "Auto: negative binomial when variance / mean ≥ 1.05"),
        (25, "NB success probability p", "=IF(E22>E21,E21/E22,1)", "0.0000", "", "p = mean / variance"),
        (26, "NB size n", "=IF(E25<1,E21*E25/(1-E25),0)", NUM3, "", "n = mean · p / (1 − p)"),
        (27, "Reorder point s (Poisson)", f'=IF(E21<=0,0,COUNTIF({pc},"<"&E15))', INT, "units",
         "count of k with POISSON.DIST(k, mean, TRUE) < SL = smallest s meeting SL"),
        (28, "Reorder point s (negative binomial)", f'=IF(E22>E21,COUNTIF({nc},"<"&E15),E27)', INT, "units",
         "same count over the NB cumulative column (GAMMALN pmf, any real n)"),
        (29, "Reorder point s (used)", '=IF(E24="Negative binomial",E28,E27)', INT, "units", ""),
        (30, "Achieved cycle service P(LTD ≤ s)",
         f'=IF(E24="Negative binomial",INDEX({nc},E29+1),INDEX({pc},E29+1))', PCT2, "", ""),
        (31, "Safety stock (s − mean)", "=E29-E21", NUM1, "units", ""),
        (32, "EOQ (uncapped)", "=MAX(1,ROUND(SQRT(2*E9*52*E17/(E18*E16)),0))", INT, "units",
         "√(2·D·K / (h·c)); the pipeline also caps at 52 weeks of cover and half the shelf life"),
        (33, "Order-up-to S ≈ s + EOQ", "=E29+E32", INT, "units", ""),
        (34, "Stock value at S", "=E33*E16", AED, "AED", ""),
    ]
    for r, lab, fx, fmt, unit, note in outs:
        put(ws, f"B{r}", lab, f=font("ice"))
        c = put(ws, f"E{r}", fx)
        as_output(c, fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))

    section(ws, "B36", "Check against the frozen pipeline")
    put(ws, "B37", "Pipeline P1/P2 hub reorder point s", f=font("ice"))
    put(ws, "E37", f"=VLOOKUP($C$5,{exr},14,FALSE)", fmt=INT, f=font("titanium", 12, bold=True))
    prov(ws, "G37", "DERIVED")
    put(ws, "B38", "Pipeline order-up-to S (with EOQ caps)", f=font("ice"))
    put(ws, "E38", f"=VLOOKUP($C$5,{exr},15,FALSE)", fmt=INT, f=font("titanium", 12, bold=True))
    put(ws, "B39", "Reorder point matches the pipeline?", f=font("ice"))
    c = put(ws, "E39", '=IF(E29=E37,"MATCH","DIFFERS")')
    as_output(c)
    put(ws, "H39", "Expect MATCH with Auto and no overrides (gnm.policy.policies.reorder_point_from_row).",
        f=font("titanium", 9, italic=True))
    ws.conditional_formatting.add("E39", CellIsRule(operator="equal", formula=['"DIFFERS"'],
                                                    font=Font(color=HEX["amber"], bold=True)))
    # Python reference for the default PN
    row = rop.set_index("pn").loc["GN-30-E025"]
    s_ref = reorder_point_from_row(row, st[row["deadline_class"]])
    put(ws, "B40", "Python reference s for the default PN (GN-30-E025)", f=font("slate", 10, italic=True))
    put(ws, "E40", int(s_ref), fmt=INT, f=font("titanium", 10))
    prov(ws, "G40", "DERIVED")

    section(ws, "B43", f"Cumulative tables (k = 0..{K_MAX})")
    header_row(ws, 45, 2, ["k", "Poisson P(LTD ≤ k)", "NB P(LTD = k)", "NB P(LTD ≤ k)"])
    for k in range(K_MAX + 1):
        r = T0 + k
        ws[f"B{r}"] = k
        ws[f"C{r}"] = f"=_xlfn.POISSON.DIST(B{r},$E$21,TRUE)"
        ws[f"D{r}"] = (f"=IF($E$25<1,EXP(GAMMALN(B{r}+$E$26)-GAMMALN($E$26)-GAMMALN(B{r}+1)"
                       f"+$E$26*LN($E$25)+B{r}*LN(1-$E$25)),0)")
        ws[f"E{r}"] = f"=D{r}" if k == 0 else f"=E{r - 1}+D{r}"
        for col in "BCDE":
            cell = ws[f"{col}{r}"]
            cell.font = font("titanium", 9)
            cell.number_format = INT if col == "B" else "0.000000"
    ws.freeze_panes = "A8"


def sheet_exceptions(wb, d):
    ws = wb.create_sheet("Exception list")
    acts = d["actions"]["actions"]
    n = len(acts)
    H = 18  # header row of the table
    paint(ws, H + n + 3, 13)
    title(ws, f"Planner exception list (week {d['actions']['as_of_week']})",
          "outputs/actions/actions.json · rules in docs/agent_notes/aog-lab.md · QUARANTINE_DOCS rows are SIMULATED "
          "by a seeded RNG (workflow illustration, not data); all other rows DERIVED from the SIMULATED history.")
    cols = [("ID", "exception_id", 12), ("Week", "week", 7), ("Type", "type", 30), ("Severity", "severity", 10),
            ("PN", "pn", 13), ("Station", "station", 9), ("Summary", "summary", 70),
            ("Recommended action", "recommended_action", 60), ("Owner", "owner", 28), ("Due week", "due_week", 9),
            ("Provenance", None, 12)]
    end = H + n
    rng = {k: f"${get_column_letter(2 + i)}${H + 1}:${get_column_letter(2 + i)}${end}"
           for i, (_, k, _) in enumerate(cols) if k}

    section(ws, "B5", "Summary (live COUNTIFS over the table below)")
    types = sorted({a["type"] for a in acts} | {"KIT_SHORTAGE"})
    header_row(ws, 6, 2, ["Type", "urgent", "review", "info", "Total"])
    for i, t in enumerate(types):
        r = 7 + i
        put(ws, f"B{r}", t, f=font("ice"))
        for j, sev in enumerate(("urgent", "review", "info")):
            col = get_column_letter(3 + j)
            put(ws, f"{col}{r}", f'=COUNTIFS({rng["type"]},$B{r},{rng["severity"]},"{sev}")', fmt=INT)
        c = put(ws, f"F{r}", f"=SUM(C{r}:E{r})")
        as_output(c, INT)
    rt = 7 + len(types)
    put(ws, f"B{rt}", "Total", f=font("ice", 11, bold=True))
    for col in "CDEF":
        c = put(ws, f"{col}{rt}", f"=SUM({col}7:{col}{rt - 1})")
        as_output(c, INT)

    header_row(ws, H, 2, [c[0] for c in cols], [c[2] for c in cols])
    ws.column_dimensions["A"].width = 3
    for j, a in enumerate(acts):
        r = H + 1 + j
        for i, (_, key, _) in enumerate(cols):
            col = get_column_letter(2 + i)
            if key is None:
                v = "SIMULATED" if a["type"] == "QUARANTINE_DOCS" else "DERIVED"
            else:
                v = a.get(key)
            c = ws[f"{col}{r}"]
            c.value = v
            c.fill = F_CARD if j % 2 == 0 else F_MID
            c.font = font("ice" if i == 0 else "titanium", 10)
            c.alignment = Alignment(vertical="top", wrap_text=key in ("summary", "recommended_action"))
        ws[f"L{r}"].font = font(PROV_COLOR[ws[f"L{r}"].value], 10, bold=True)
    ws.auto_filter.ref = f"B{H}:L{end}"
    ws.freeze_panes = f"C{H + 1}"
    sev = f"E{H + 1}:E{end}"
    for word, colr in (("urgent", "red"), ("review", "amber"), ("info", "slate")):
        ws.conditional_formatting.add(sev, CellIsRule(operator="equal", formula=[f'"{word}"'],
                                                      fill=PatternFill("solid", fgColor=HEX[colr]),
                                                      font=Font(color=HEX["midnight"], bold=True)))
    # whole-row accent for urgent rows
    ws.conditional_formatting.add(f"B{H + 1}:D{end}", FormulaRule(formula=[f'$E{H + 1}="urgent"'],
                                                                  font=Font(color=HEX["ice"], bold=True)))


def sheet_aog(wb, d):
    ws = wb.create_sheet("AOG exposure")
    paint(ws, 60, 14)
    for col, w in zip("ABCDEFGHIJKL", [3, 36, 30, 12, 14, 16, 16, 9, 16, 14, 3, 14]):
        ws.column_dimensions[col].width = w
    title(ws, "AOG exposure calculator",
          "Exposure = max(0, wait hours − deadline slack) × AOG penalty per hour (by archetype, ASSUMED) + direct cost. "
          "Same rule the AOG Response Lab uses to rank options.")
    cfg = d["cfg"]
    pen = cfg["economics"]["aog_penalty_aed_per_hour"]
    slack = {k: float(v["hours"]) for k, v in cfg["deadline_classes"].items() if k in ("D0", "D3", "D10")}

    header_row(ws, 5, 2, ["Input", "Value", "Unit", "Provenance"])
    ins = [(6, "Aircraft archetype", "narrowbody", None, "", "SIMULATED"),
           (7, "Deadline class", "D0", None, "", "ASSUMED"),
           (8, "Expected wait for the part", 9, NUM1, "hours", "DERIVED"),
           (9, "Direct cost (logistics, premium)", 2650, AED, "AED", "DERIVED"),
           (10, "AOG penalty multiplier", 1, "0.0×", "×", "ASSUMED")]
    for r, lab, v, fmt, unit, tag in ins:
        put(ws, f"B{r}", lab, f=font("ice"))
        c = put(ws, f"C{r}", v)
        as_input(c, fmt)
        put(ws, f"D{r}", unit, f=font("slate", 10))
        prov(ws, f"E{r}", tag)
    dva = DataValidation(type="list", formula1='"narrowbody,widebody"', allow_blank=False)
    dvd = DataValidation(type="list", formula1='"D0,D3,D10"', allow_blank=False)
    ws.add_data_validation(dva)
    ws.add_data_validation(dvd)
    dva.add("C6")
    dvd.add("C7")

    header_row(ws, 5, 9, ["Archetype", "AED / AOG h"])
    put(ws, "I6", "narrowbody", f=font("ice"))
    c = put(ws, "J6", float(pen["narrowbody"]))
    as_input(c, AED)
    put(ws, "I7", "widebody", f=font("ice"))
    c = put(ws, "J7", float(pen["widebody"]))
    as_input(c, AED)
    prov(ws, "I8", "ASSUMED")
    put(ws, "J8", "config economics", f=font("slate", 9, italic=True))
    header_row(ws, 10, 9, ["Deadline", "Slack (h)"])
    for i, k in enumerate(("D0", "D3", "D10")):
        put(ws, f"I{11 + i}", k, f=font("ice"))
        c = put(ws, f"J{11 + i}", slack[k])
        as_input(c, INT)
    prov(ws, "I14", "ASSUMED")
    put(ws, "J14", "config deadline_classes", f=font("slate", 9, italic=True))

    header_row(ws, 12, 2, ["Output", "Value", "Formula"])
    outs = [(13, "Deadline slack", "=VLOOKUP(C7,$I$11:$J$13,2,FALSE)", INT, "lookup by deadline class"),
            (14, "AOG hours beyond slack", "=MAX(0,C8-C13)", NUM1, "max(0, wait − slack)"),
            (15, "AOG penalty per hour", "=VLOOKUP(C6,$I$6:$J$7,2,FALSE)*C10", AED, "lookup by archetype × multiplier"),
            (16, "AOG penalty cost", "=C14*C15", AED, "hours × AED/h"),
            (17, "Exposure", "=C16+C9", AED, "penalty cost + direct cost"),
            (18, "Deadline met?", '=IF(C8<=C13,"Yes","No")', None, "wait ≤ slack")]
    for r, lab, fx, fmt, note in outs:
        put(ws, f"B{r}", lab, f=font("ice", 11, bold=(r == 17)))
        c = put(ws, f"C{r}", fx)
        as_output(c, fmt)
        put(ws, f"D{r}", note, f=font("titanium", 9, italic=True))

    # Worked incidents from the AOG lab
    incs = {i["id"]: i for i in d["incidents"]["incidents"]}
    r = 21
    blocks = []
    for iid in ("AOG-0001", "AOG-0177"):
        inc = incs[iid]
        section(ws, f"B{r}", f"Worked incident {iid}: {inc['pn']} {inc['desc']} at {inc['station']}"
                             f"{' (PS1)' if iid == 'AOG-0001' else ''}")
        r += 1
        put(ws, f"B{r}", "Archetype / deadline", f=font("slate", 10))
        c = put(ws, f"C{r}", inc["archetype"])
        as_input(c)
        c = put(ws, f"D{r}", inc["deadline"])
        as_input(c)
        arch_ref, dl_ref = f"$C${r}", f"$D${r}"
        r += 1
        header_row(ws, r, 2, ["Option", "Ranked?", "Wait h", "Direct cost", "Exposure (formula)", "Rank (formula)",
                              "", "Pipeline exposure", "Check"])
        r += 1
        opts = [o for o in inc["options"] if o.get("wait_h") is not None]
        first = r
        last = r + len(opts) - 1
        for o in opts:
            ranked = "Yes" if (o["feasible"] and not o.get("greyed") and not o.get("human_decision")) else "No"
            put(ws, f"B{r}", f"{o['key']}. {o['option']}", f=font("ice", 10))
            put(ws, f"C{r}", ranked, f=font("titanium", 10))
            c = put(ws, f"D{r}", float(o["wait_h"]))
            as_input(c, NUM1)
            c = put(ws, f"E{r}", float(o["direct_cost"]))
            as_input(c, AED)
            c = put(ws, f"F{r}", f"=MAX(0,D{r}-VLOOKUP({dl_ref},$I$11:$J$13,2,FALSE))"
                                 f"*VLOOKUP({arch_ref},$I$6:$J$7,2,FALSE)*$C$10+E{r}")
            as_output(c, AED)
            c = put(ws, f"G{r}", f'=IF(C{r}="Yes",COUNTIFS($C${first}:$C${last},"Yes",$F${first}:$F${last},"<"&F{r})'
                                 f'+COUNTIFS($C${first}:$C${last},"Yes",$F${first}:$F${last},F{r},$D${first}:$D${last},"<"&D{r})+1,"—")')
            as_output(c, INT)
            put(ws, f"I{r}", o["exposure_aed"], fmt=AED, f=font("titanium", 10))
            c = put(ws, f"J{r}", f'=IF(ABS(F{r}-I{r})<0.5,"OK","CHECK")')
            c.font = font("aero_teal", 10, bold=True)
            blocks.append((iid, o["key"], r, o["exposure_aed"], o.get("rank")))
            r += 1
        put(ws, f"B{r}", "Pipeline exposure from outputs/aog_lab/incidents.json (DERIVED); penalty multiplier C10 = 1 "
                         "reproduces it. Unranked rows: infeasible, greyed (pool not contracted) or estimate only.",
            f=font("slate", 9, italic=True))
        r += 3
    ws.conditional_formatting.add("J20:J60", CellIsRule(operator="equal", formula=['"CHECK"'],
                                                        font=Font(color=HEX["amber"], bold=True)))
    ws.freeze_panes = "A5"
    return blocks


def build(out: Path = OUT) -> Path:
    d = load_inputs()
    wb = Workbook()
    sheet_readme(wb, d)
    sheet_parts(wb, d)
    n_ex = sheet_rotable_examples(wb, d)
    rop = rop_examples(d["ff"], d["p1"], d["parts"])
    sheet_float(wb, d, n_ex)
    n_rop = sheet_rop_examples(wb, rop)
    sheet_rop(wb, d, n_rop, rop)
    sheet_exceptions(wb, d)
    sheet_aog(wb, d)
    # order: calculators next to their lookup tables
    order = ["README", "Part list", "Float calculator", "Rotable examples", "ROP calculator", "ROP examples",
             "Exception list", "AOG exposure"]
    wb._sheets = [wb[n] for n in order]
    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = HEX["aero_teal"] if "calculator" in ws.title or ws.title == "AOG exposure" else HEX["deep_steel"]
    wb.properties.title = "GROUNDED NO MORE planner workbook"
    wb.properties.creator = "grounded-no-more (scripts/build_workbook.py)"
    wb.properties.description = DISCLAIMER
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    p = build(a.out)
    print(f"wrote {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}")


if __name__ == "__main__":
    main()
