#!/usr/bin/env python
"""Build excel/grounded_no_more_planner_workbook.xlsx (v2, openpyxl, live formulas).

Every number written as a constant comes from a pipeline output or the config (nothing is typed by hand):
  docs/data/parts.json, docs/data/rotables.json, docs/data/kpis.json, docs/data/frontier.json,
  docs/data/manifest.json, outputs/forecasting/final_forecasts.parquet, outputs/policies/P1_stock_params.csv,
  outputs/actions/actions.json, outputs/aog_lab/incidents.json,
  config/assumptions.yaml (service targets, AOG hourly rate and fixed per-event cost, rectification windows,
  fitting/RTS hours, AOG recovery routes, carrying rate) and config/policy.yaml (PO ordering cost, NONE target).
The worked AOG incidents are chosen by rule (the PS1 incident from incidents.json `ps1_incident_id`, plus the first
showcase incident on the other archetype with a non-zero rectification window), never by a typed id.
Everything the calculators compute is an Excel formula, so the sheets recalculate when inputs change.
The "Python reference" rows are computed here with gnm.policy.analytic for the default inputs only.

Usage:  python scripts/build_workbook.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import shutil
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
from gnm.export import v21
from gnm.policy import analytic
from gnm.policy.policies import reorder_point_from_row

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "excel" / "grounded_no_more_planner_workbook.xlsx"
DOWNLOAD = ROOT / "docs" / "downloads" / "grounded_no_more_planner_workbook.xlsx"
DISCLAIMER = ("Independent educational simulation. Not an airline system or an approved maintenance, "
              "airworthiness or dispatch tool.")
SHEETS = ["README", "Part list", "Poisson float calculator", "Rotable examples", "ROP calculator", "ROP examples",
          "Exception list", "AOG exposure calculator", "AOG recovery routes"]
WINDOW_NOTE = ("Rectification windows are hypothetical: D3/D10 are simplified analogues of MEL repair-interval "
               "categories B and C, not operator MEL decisions. NONE = servicing fluid, never an AOG driver.")
POLICIES = ["P0", "P1", "P2", "I125"]

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
    dd = ROOT / "docs" / "data"
    parts = json.loads((dd / "parts.json").read_text())
    rot = json.loads((dd / "rotables.json").read_text())
    kpis = json.loads((dd / "kpis.json").read_text())
    frontier = json.loads((dd / "frontier.json").read_text())
    manifest = json.loads((dd / "manifest.json").read_text())
    method = json.loads((dd / "method.json").read_text())
    actions = json.loads((ROOT / "outputs" / "actions" / "actions.json").read_text())
    incidents = json.loads((ROOT / "outputs" / "aog_lab" / "incidents.json").read_text())
    ff = pd.read_parquet(ROOT / "outputs" / "forecasting" / "final_forecasts.parquet")
    p1 = pd.read_csv(ROOT / "outputs" / "policies" / "P1_stock_params.csv")
    return dict(cfg=cfg, pcfg=pcfg, parts=parts, rot=rot, kpis=kpis, frontier=frontier, manifest=manifest,
                actions=actions, incidents=incidents, ff=ff, p1=p1, method=method)


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


def service_targets(d: dict) -> dict:
    """Cycle service level by rectification window class: config service_targets + policy.yaml NONE target."""
    st = {k: float(v) for k, v in d["cfg"]["service_targets"].items() if k in ("D0", "D3", "D10")}
    st["NONE"] = float(d["pcfg"]["service_target_none"])
    return st


def window_hours(cfg: dict) -> dict:
    return {k: float(v["hours"]) for k, v in cfg["deadline_classes"].items()
            if isinstance(v, dict) and v.get("hours") is not None}


def fitting_hours(cfg: dict) -> dict:
    """Midpoint of engine.fitting_hours per part class (as gnm.aog.data.fitting_mid_h)."""
    out = {}
    for k, v in cfg["engine"]["fitting_hours"].items():
        out[k] = float(sum(v) / 2) if isinstance(v, list) else float(v)
    return out


def default_float_pn(rot: dict) -> str:
    ex = rot["float_examples"]
    return next((e["pn"] for e in ex if e.get("planted") == "PS1"), ex[0]["pn"])


def default_rop_pn(rop: pd.DataFrame) -> str:
    ps4 = rop[rop.planted == "PS4"]
    return str(ps4.pn.iloc[0] if len(ps4) else rop.pn.iloc[0])


def showcase_incidents(incidents: dict, cfg: dict) -> list[dict]:
    """[PS1 incident, second showcase incident]: the first showcase id on the other archetype with a window > 0."""
    incs = {i["id"]: i for i in incidents["incidents"]}
    ps1 = incs[incidents["ps1_incident_id"]]
    win = window_hours(cfg)
    second = next((incs[s] for s in incidents["showcase_ids"]
                   if s != ps1["id"] and incs[s]["archetype"] != ps1["archetype"] and win.get(incs[s]["deadline"], 0) > 0),
                  None)
    if second is None:
        second = next(incs[s] for s in incidents["showcase_ids"] if s != ps1["id"])
    return [ps1, second]


def option_ranked(o: dict) -> bool:
    return bool(o["feasible"] and not o.get("greyed") and not o.get("human_decision"))


def exposure_rule(wait_h, window_h, fit_h, rate_h, event_cost, direct, mult=1.0) -> tuple[float, float]:
    """v2 material shortage exposure (gnm.aog.options.exposure); mult scales the hourly rate only (V2-POL-5)."""
    late = float(wait_h) > float(window_h)
    h = float(wait_h) + float(fit_h) - float(window_h) if late else 0.0
    return h, h * float(rate_h) * float(mult) + (float(event_cost) if late else 0.0) + float(direct)


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


def _fmt_ci(d, scale=1.0, fmt="{:,.0f}"):
    return f"{fmt.format(d['mean'] / scale)} [{fmt.format(d['ci'][0] / scale)}, {fmt.format(d['ci'][1] / scale)}]"


# ---------------------------------------------------------------- sheets
def sheet_readme(wb, d):
    ws = wb.active
    ws.title = "README"
    paint(ws, 90, 8)
    for col, w in zip("ABCDEFG", [3, 30, 74, 18, 18, 20, 14]):
        ws.column_dimensions[col].width = w
    title(ws, "GROUNDED NO MORE · Planner workbook (v2)",
          "Falcon Hub Airways (fictional): spare-parts planning calculators on a simulated planning snapshot "
          "built from the frozen v2 pipeline outputs")
    put(ws, "B5", "DISCLAIMER", f=font("amber", 12, bold=True))
    put(ws, "C5", DISCLAIMER, f=font("ice", 12, bold=True), align=Alignment(wrap_text=True))
    ws.row_dimensions[5].height = 34
    put(ws, "C6", "All data is SIMULATED for a fictional airline. No real airline, OEM or operator data is used. "
                  + WINDOW_NOTE, f=font("titanium", 10, italic=True), align=Alignment(wrap_text=True))
    ws.row_dimensions[6].height = 42

    section(ws, "B8", "Purpose")
    put(ws, "C8", "A hands-on companion to the GROUNDED NO MORE case study. A materials planner can size a rotable "
                  "float, set a reorder point, triage the week-%d exception list and price the material shortage "
                  "exposure of an AOG sourcing decision, with every result shown as a live Excel formula."
        % d["actions"]["as_of_week"], align=Alignment(wrap_text=True, vertical="top"))
    ws.row_dimensions[8].height = 48

    section(ws, "B10", "Sheets")
    header_row(ws, 11, 2, ["Sheet", "What it does", "Provenance"])
    n_parts = len(d["parts"]["parts"])
    sheets = [
        ("Part list", f"{n_parts} fictional PNs from the v2 catalogue: type applicability (NB / WB / both), QPA, "
                      "removal mode, rectification window class, demand class, P0 / P2 / I125 stock units. "
                      "Δ units and stock value are formulas.", "SIMULATED"),
        ("Poisson float calculator", "Palm / Poisson rotable float: pipeline mean, immediate fill P(X ≤ S − 1), EBO, "
                                     "expected wait and capital. Total spares S = base stock + repair-loop units.",
         "DERIVED"),
        ("Rotable examples", "Lookup table for the float calculator (docs/data/rotables.json float_examples).", "DERIVED"),
        ("ROP calculator", "Consumable / expendable reorder point: lead-time demand mean and variance, Poisson or "
                           "negative-binomial cumulative table, service level by window class.", "DERIVED"),
        ("ROP examples", "Lookup table for the ROP calculator: AUH planning rows from final_forecasts.parquet and the "
                         "frozen P1/P2 hub reorder point.", "DERIVED"),
        ("Exception list", f"The {len(d['actions']['actions'])} planner actions for week {d['actions']['as_of_week']} "
                           "(outputs/actions/actions.json) with owners, trigger, quantity, source → destination, "
                           "expected availability, constraints and live COUNTIFS summaries.", "DERIVED"),
        ("AOG exposure calculator", "Material shortage exposure = expected material-related downtime hours (wait beyond "
                                    "the window + fitting/RTS, only if late) × hourly rate + fixed cost per event + "
                                    "direct cost; two AOG-lab incidents recomputed and checked.", "ASSUMED"),
        ("AOG recovery routes", "Reference: the ASSUMED odds, response times and fees of the AOG recovery routes "
                                "(robbery, exchange/loan, local borrow, local buy, retries) from config.", "ASSUMED"),
    ]
    r = 12
    for name, what, tag in sheets:
        put(ws, f"B{r}", name, f=font("ice", 11, bold=True))
        put(ws, f"C{r}", what, align=Alignment(wrap_text=True, vertical="top"))
        prov(ws, f"D{r}", tag)
        ws.row_dimensions[r].height = 34
        r += 1

    r += 1
    section(ws, f"B{r}", "Provenance legend")
    r += 1
    legend = [
        ("REAL", "Public real-world data (station coordinates, the Monash Car Parts benchmark)."),
        ("DERIVED", "Computed by the project's code from other data (forecasts, policies, aggregations)."),
        ("ASSUMED", "A planning assumption set in config (AOG cost, service targets, route odds); sensitivity-tested."),
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

    k = d["kpis"]
    core, fo = k["headline"]["core"], k["headline"]["frontier_option"]
    seeds = k["seeds"]
    section(ws, f"B{r}", f"Headline (v2 holdout, seeds {seeds[0]}–{seeds[-1]}, central world)")
    r += 1
    osr = core["outstation_rotables"]
    dn = k["display_names"]
    nm = lambda c: f"{dn[c]['display_name']} ({c})"  # noqa: E731  A3 display name + code tag
    put(ws, f"C{r}", k["scope_line"], f=font("slate", 10, italic=True), align=Alignment(wrap_text=True))
    r += 1
    cap_t, sw, ins = k["capital_table"], k["stress_worlds"], k["frontier_insight"]
    lines = [
        ("Plans compared",
         " · ".join(nm(c) for c in POLICIES)
         + ". The Simple Rulebook is a deliberately simplified starting point, not a model of a competent "
         "airline."),
        (f"Core finding: {dn['P2']['display_name']}",
         f"The {nm('P2')} ({osr['P2']} vs {osr['P0']} outstation rotables) cuts expected downtime of aircraft waiting "
         f"for a part by {_fmt_ci(core['aog_reduction'])} h/yr vs the {nm('P0')} (paired 95% CI). It holds in all three "
         "stress worlds and across the ×0.5–×2 hourly-rate range. It is not a free move of stock: see the capital "
         "table below."),
        (f"Frontier option: {dn['I125']['display_name']}",
         f"If you invest an additional AED {fo['extra_capital_aed']['mean'] / 1e6:.1f}M, the {nm('I125')} cuts a further "
         f"{_fmt_ci(fo['aog_reduction'], fmt='{:,.0f}')} h/yr vs the {dn['P2']['display_name']} (paired 95% CI). Its "
         "cost lead is not significant if repair is 25% faster, and the rule's pick shifts to "
         + " / ".join(f"{s['recommended']} at {s['setting'].replace('x', '×')}" for s in fo["rule_shifts"])
         + " the hourly rate."),
        ("Insight", f"{ins['text']} Levers: {ins['levers_text']}."),
        ("Honest trade-off",
         f"The {dn['P2']['display_name']} has {abs(core['immediate_fill_pts']['mean']):.2f} pts lower immediate fill "
         f"than the {dn['P0']['short_name']} ({core['immediate_fill_pts']['ci'][0]:.2f} to "
         f"{core['immediate_fill_pts']['ci'][1]:.2f} pts); results depend heavily on the AOG recovery routes (see the "
         "'AOG recovery routes' sheet)."),
        ("Stress worlds", f"The three simulated worlds differ only in {sw['text']}. {sw['ranges_note']}"),
        ("Calibration", d["method"]["calibration_note"]["text"]),
        ("How to read", k["reading_note"]),
        ("Archive note", "A v1 world was archived after a domain review; see archive/v1."),
    ]
    for a, b in lines:
        put(ws, f"B{r}", a, f=font("ice", 11, bold=True), align=Alignment(wrap_text=True, vertical="top"))
        put(ws, f"C{r}", b, align=Alignment(wrap_text=True, vertical="top"))
        ws.row_dimensions[r].height = 64 if len(b) > 300 else 48
        r += 1
    r += 1
    section(ws, f"B{r}", f"Capital change, {nm(cap_t['from'])} → {nm(cap_t['to'])}")
    r += 1
    header_row(ws, r, 2, ["Line", "Amount", "Units", "AED (assumed value)", "", "Provenance"])
    r += 1
    for row_ in cap_t["rows"]:
        put(ws, f"B{r}", row_["label"], f=font("ice", 11, bold=True), align=Alignment(wrap_text=True))
        put(ws, f"C{r}", row_["text"], f=font("aero_teal", 11, bold=True))
        if row_["units"] is not None:
            put(ws, f"D{r}", row_["units"], fmt='+#,##0;-#,##0;0')
        put(ws, f"E{r}", row_["aed"], fmt=AED)
        prov(ws, f"G{r}", cap_t["provenance"])
        r += 1
    put(ws, f"C{r}", cap_t["note"], f=font("amber", 10, italic=True), align=Alignment(wrap_text=True))
    r += 1
    put(ws, f"C{r}", "Basis: " + cap_t["basis"], f=font("slate", 9, italic=True), align=Alignment(wrap_text=True))
    ws.row_dimensions[r].height = 30
    r += 2
    header_row(ws, r, 2, ["KPI", "Note", nm("P0"), nm("P2"), nm("I125"), "Provenance"])
    r += 1
    labels = {"immediate_fill_rate": ("Immediate fill rate", PCT),
              "aog_hours": ("Expected material-related downtime h / year", INT),
              "aog_events": ("AOG events / year", NUM1), "spare_capital_aed": ("Spare capital", AED),
              "total_annual_cost_aed": ("Total annual cost", AED)}
    for kp in k["kpis"]:
        if kp["id"] not in labels:
            continue
        lab, fmt = labels[kp["id"]]
        put(ws, f"B{r}", lab, f=font("ice"))
        put(ws, f"C{r}", f"mean over {kp['n_seeds']} holdout seeds (docs/data/kpis.json)"
            + (f" · {kp['scope']}" if kp.get("scope") else ""), f=font("slate", 10, italic=True),
            align=Alignment(wrap_text=True))
        put(ws, f"D{r}", kp["baseline"], fmt=fmt)
        put(ws, f"E{r}", kp["value"], fmt=fmt, f=font("aero_teal", 11, bold=True))
        put(ws, f"F{r}", kp["reference"]["value"], fmt=fmt)
        prov(ws, f"G{r}", kp["provenance"])
        r += 1

    r += 1
    section(ws, f"B{r}", "Sources and rebuild")
    r += 1
    meta = d["manifest"]["meta"]
    srcs = [
        ("World", "v2 simulated world (D012–D015 in docs/DECISIONS.md): calibrated on P0 only, frozen, then a single "
                  "holdout on fresh seeds."),
        ("Site data", f"docs/data/*.json, exported {meta['generated_at']} (git {meta['git_sha']})"),
        ("Pipeline outputs", "outputs/forecasting/final_forecasts.parquet, outputs/policies/P1_stock_params.csv, "
                             "outputs/actions/actions.json, outputs/aog_lab/incidents.json"),
        ("Assumptions", "config/assumptions.yaml (service targets, hourly rate, fixed cost per event, rectification "
                        "windows, fitting/RTS, aog_sourcing, carrying rate), config/policy.yaml (PO cost, NONE target)"),
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
        ("PN", "pn", 13, None, "SIMULATED"),                                   # B
        ("Description", "desc", 34, None, "SIMULATED"),                        # C
        ("ATA", "ata", 6, None, "SIMULATED"),                                  # D
        ("ATA chapter", "ata_name", 20, None, "SIMULATED"),                    # E
        ("Family", "family", 14, None, "SIMULATED"),                           # F
        ("Class", "cls", 7, None, "SIMULATED"),                                # G
        ("Applicability", "applicability", 11, None, "SIMULATED"),             # H
        ("QPA NB", "qpa_nb", 7, INT, "SIMULATED"),                             # I
        ("QPA WB", "qpa_wb", 7, INT, "SIMULATED"),                             # J
        ("Removal mode", "removal_mode", 13, None, "SIMULATED"),               # K
        ("Rectification window (hypothetical)", "deadline", 13, None, "ASSUMED"),  # L
        ("Demand class", "demand_class", 15, None, "DERIVED"),                 # M
        ("ABC", "abc", 6, None, "DERIVED"),                                    # N
        ("Unit cost", "unit_cost", 14, AED, "SIMULATED"),                      # O
        ("Quoted LT (d)", "lt_quoted_d", 10, NUM1, "SIMULATED"),               # P
        ("Est. LT (d)", "lt_est_d", 10, NUM1, "DERIVED"),                      # Q
        ("Annual usage (qty)", "annual_usage_qty", 11, NUM1, "DERIVED"),       # R
        ("P0 units", "stock_total_p0", 9, INT, "DERIVED"),                     # S
        ("P2 units", "stock_total_p2", 9, INT, "DERIVED"),                     # T
        ("I125 units", "stock_total", 9, INT, "DERIVED"),                      # U
        ("Δ P2 − P0", "=T{r}-S{r}", 10, '+#,##0;-#,##0;0', "DERIVED"),         # V
        ("P2 value at target", "=T{r}*O{r}", 16, AED, "DERIVED"),              # W
        ("Champion", "champion", 11, None, "DERIVED"),                         # X
        ("Planted", "planted", 8, None, "SIMULATED"),                          # Y
        ("Row provenance", "provenance", 13, None, "SIMULATED"),               # Z
    ]
    last_col = len(cols) + 1
    paint(ws, n + 8, last_col + 1)
    ws.column_dimensions["A"].width = 3
    title(ws, f"Part list ({n} fictional PNs, v2 catalogue)",
          "docs/data/parts.json · units: P0 = Simple Rulebook (naive reference), P2 = Network Plan (core finding), "
          "I125 = Network Plan + Extra Spares (frontier option) "
          "(targets across all stations). Row 4 shows each column's provenance. " + WINDOW_NOTE)
    for i, (h, _, w, _, tag) in enumerate(cols):
        col = get_column_letter(i + 2)
        prov(ws, f"{col}4", tag)
        ws.column_dimensions[col].width = w
    header_row(ws, 5, 2, [c[0] for c in cols])
    ws.row_dimensions[5].height = 44
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
    ws.conditional_formatting.add(f"L6:L{end}", CellIsRule(operator="equal", formula=['"D0"'],
                                                           font=Font(color=HEX["red"], bold=True)))
    ws.conditional_formatting.add(f"Y6:Y{end}", FormulaRule(formula=['LEN($Y6)>0'], font=Font(color=HEX["copper"], bold=True)))
    put(ws, f"B{end + 2}", f"Total (all {n} PNs)", f=font("ice", 11, bold=True))
    put(ws, f"B{end + 3}", "Visible rows (filtered)", f=font("ice", 11, bold=True))
    for col in ("S", "T", "U", "V", "W"):
        c = put(ws, f"{col}{end + 2}", f"=SUM({col}6:{col}{end})")
        as_output(c, AED if col == "W" else INT)
        c = put(ws, f"{col}{end + 3}", f"=SUBTOTAL(9,{col}6:{col}{end})")
        as_output(c, AED if col == "W" else INT)
    put(ws, f"B{end + 4}", "SUBTOTAL respects the filter: filter by class, applicability or window class to see the subset.",
        f=font("slate", 9, italic=True))
    return end


ROT_COLS = ["PN", "Description", "Window", "Removals / 30 d", "Pipeline days", "Unit cost", "Loop units",
            "P0", "P1", "P2", "I125", "S P0", "S P1", "S P2", "S I125", "Planted", "Provenance"]


def sheet_rotable_examples(wb, d):
    ws = wb.create_sheet("Rotable examples")
    ex = d["rot"]["float_examples"]
    paint(ws, len(ex) + 8, 18)
    put(ws, "A1", "Rotable examples (float calculator lookup)", f=font("ice", 16, bold=True))
    put(ws, "A2", "docs/data/rotables.json float_examples: network removal rate, hub T_eff (pipeline days), serviceable "
                  "base stock by policy (P0/P1/P2/I125) and the exported total spares S = base stock + loop units "
                  "(units the engine seeds in the repair loop; V2-POL-3).", f=font("titanium", 10, italic=True))
    put(ws, "A3", DISCLAIMER, f=font("amber", 9, italic=True))
    header_row(ws, 4, 1, ROT_COLS, [13, 30, 8, 13, 12, 13, 10, 7, 7, 7, 7, 7, 7, 7, 8, 9, 11])
    for j, e in enumerate(ex):
        r = 5 + j
        st = e["spares_total"]
        vals = [e["pn"], e["desc"], e["deadline"], e["rate_per_30d"], e["pipeline_days"], e["unit_cost_aed"],
                e["loop_units"], e["p0_units"], e["p1_units"], e["p2_units"], e["rec_units"],
                st["P0"], st["P1"], st["P2"], st["recommended"], e["planted"] or "", e["provenance"]]
        fmts = [None, None, None, NUM3, NUM1, AED] + [INT] * 9 + [None, None]
        for i, (v, fm) in enumerate(zip(vals, fmts)):
            c = ws.cell(r, i + 1, v)
            c.fill = F_CARD if j % 2 == 0 else F_MID
            c.font = font("ice" if i == 0 else "titanium", 10)
            if fm:
                c.number_format = fm
        ws.cell(r, 17).font = font(PROV_COLOR[e["provenance"]], 10, bold=True)
    ws.freeze_panes = "B5"
    return len(ex)


def sheet_float(wb, d, n_ex):
    ws = wb.create_sheet("Poisson float calculator")
    paint(ws, 97, 16)
    for col, w in zip("ABCDEFGH", [3, 38, 18, 16, 18, 10, 12, 60]):
        ws.column_dimensions[col].width = w
    title(ws, "Rotable float calculator (Palm / Poisson)",
          "Pipeline X ~ Poisson(μ), μ = removals per day × pipeline days. Immediate fill = P(X ≤ S − 1): a demand is "
          "filled only if a spare is on the shelf (V2-SIM-10). Total spares S = base stock + repair-loop units. "
          "EBO = E[max(X − S, 0)].")
    exr = f"'Rotable examples'!$A$5:$Q${4 + n_ex}"
    pncol = f"'Rotable examples'!$A$5:$A${4 + n_ex}"
    row_m = f"MATCH($C$5,{pncol},0)"
    pn0 = default_float_pn(d["rot"])

    put(ws, "B5", "Pick a PN", f=font("ice", 11, bold=True))
    as_input(put(ws, "C5", pn0))
    put(ws, "B6", "Policy for the base stock", f=font("ice", 11, bold=True))
    as_input(put(ws, "C6", "I125"))
    put(ws, "D5", f"=VLOOKUP($C$5,{exr},2,FALSE)", f=font("titanium", 11, italic=True))
    put(ws, "D6", "P0 Simple Rulebook (naive reference) · P1 Each Airport for Itself (simplified local comparator) · "
                  "P2 Network Plan · I125 Network Plan + Extra Spares", f=font("slate", 9, italic=True))
    dv = DataValidation(type="list", formula1=f"={pncol}", allow_blank=False)
    dv2 = DataValidation(type="list", formula1='"' + ",".join(POLICIES) + '"', allow_blank=False)
    ws.add_data_validation(dv)
    ws.add_data_validation(dv2)
    dv.add("C5")
    dv2.add("C6")

    header_row(ws, 8, 2, ["Input", "From example", "Override", "Used", "Unit", "Provenance", "Note"])
    rows = [
        (9, "Removals per 30 days", f"=VLOOKUP($C$5,{exr},4,FALSE)", NUM3, "per 30 d", "DERIVED",
         "Network reliability-exposure removal rate (Gamma–Poisson posterior × planned exposure)"),
        (10, "Repair pipeline (days)", f"=VLOOKUP($C$5,{exr},5,FALSE)", NUM1, "days", "DERIVED",
         "Hub T_eff: transport + quoted TAT + observed lateness, with condemnation via purchase lead time"),
        (11, "Base stock (serviceable, chosen policy)",
         f"=INDEX('Rotable examples'!$H$5:$K${4 + n_ex},{row_m},MATCH($C$6,'Rotable examples'!$H$4:$K$4,0))",
         INT, "units", "DERIVED", "Serviceable base stock for the chosen policy (all stations)"),
        (12, "Repair-loop units", f"=VLOOKUP($C$5,{exr},7,FALSE)", INT, "units", "DERIVED",
         "Units the engine seeds in the repair loop (P0 plan); Palm counts them in the total"),
        (13, "Unit cost", f"=VLOOKUP($C$5,{exr},6,FALSE)", AED, "AED", "SIMULATED", "Fictional master-data price"),
    ]
    for r, lab, fx, fmt, unit, tag, note in rows:
        put(ws, f"B{r}", lab, f=font("ice"))
        put(ws, f"C{r}", fx, fmt=fmt)
        as_input(put(ws, f"D{r}", None), fmt)
        as_output(put(ws, f"E{r}", f'=IF(D{r}="",C{r},D{r})'), fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        prov(ws, f"G{r}", tag)
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))
    put(ws, "B14", "Total spares S = base stock + loop units", f=font("ice", 11, bold=True))
    as_output(put(ws, "E14", "=E11+E12"), INT)
    put(ws, "F14", "units", f=font("slate", 10))
    prov(ws, "G14", "DERIVED")
    put(ws, "H14", "One definition of total spares for P0, P1, P2 and I125 (V2-POL-3), so capital is comparable",
        f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))

    header_row(ws, 16, 2, ["Output", "", "", "Value", "Unit", "", "Formula"])
    T0, T1 = 35, 95  # x = 0..60 table rows
    xs, pmf = f"$B${T0}:$B${T1}", f"$C${T0}:$C${T1}"
    outs = [
        (17, "Pipeline mean μ", "=E9*E10/30", NUM2, "units", "μ = (removals / 30) × pipeline days"),
        (18, "Immediate fill P(X ≤ S − 1)", "=IF(E14<=0,0,_xlfn.POISSON.DIST(E14-1,E17,TRUE))", PCT, "",
         "POISSON.DIST(S − 1, μ, TRUE): the share of demands filled from the shelf (PASTA)"),
        (19, "Expected backorders (EBO)", f"=E17-E14+SUMPRODUCT(({xs}<E14)*(E14-{xs})*{pmf})", NUM3, "units",
         "μ − S + Σ_(x<S) (S − x)·P(X=x), SUMPRODUCT over the 0..60 table (exact for S ≤ 61)"),
        (20, "Expected wait per removal", "=IF(E9>0,E19/(E9/30),0)", NUM2, "days", "Little's law: EBO / λ"),
        (21, "Capital in the float", "=E14*E13", AED, "AED", "S × unit cost (total spares incl. loop units)"),
        (22, "Annual removals", "=E9*365/30", NUM1, "per yr", "λ × 365"),
        (23, "Expected backorder-days per year", "=E19*365", NUM1, "unit-days", "EBO × 365"),
    ]
    for r, lab, fx, fmt, unit, note in outs:
        put(ws, f"B{r}", lab, f=font("ice"))
        as_output(put(ws, f"E{r}", fx), fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))
    put(ws, "B24", "Exported total spares S for this policy", f=font("slate", 10, italic=True))
    put(ws, "C24", f"=INDEX('Rotable examples'!$L$5:$O${4 + n_ex},{row_m},MATCH($C$6,'Rotable examples'!$H$4:$K$4,0))",
        fmt=INT, f=font("slate", 10, italic=True))
    as_output(put(ws, "E24", '=IF(E14=C24,"MATCH","DIFFERS")'))
    put(ws, "H24", "Expect MATCH with no overrides (docs/data/rotables.json spares_total).", f=font("titanium", 9, italic=True))
    ws.conditional_formatting.add("E24", CellIsRule(operator="equal", formula=['"DIFFERS"'],
                                                    font=Font(color=HEX["amber"], bold=True)))

    ex = next(e for e in d["rot"]["float_examples"] if e["pn"] == pn0)
    s_def = ex["rec_units"] + ex["loop_units"]
    ref = analytic.float_calc(ex["rate_per_30d"], ex["pipeline_days"], s_def, ex["unit_cost_aed"])
    section(ws, "B27", f"Python reference for the default inputs ({pn0}, I125)")
    put(ws, "B28", "gnm.policy.analytic.float_calc", f=font("slate", 10, italic=True))
    for i, (lab, key, fmt) in enumerate([("μ", "pipeline_mean", NUM2), ("Immediate fill", "availability", PCT2),
                                          ("EBO", "ebo", NUM3), ("Wait (d)", "expected_wait_days", NUM2),
                                          ("Capital", "capital_aed", AED)]):
        col = get_column_letter(3 + i)
        put(ws, f"{col}28", lab, f=font("slate", 10))
        put(ws, f"{col}29", ref[key], fmt=fmt, f=font("titanium", 10))
    prov(ws, "H29", "DERIVED")
    put(ws, "H28", "Matches the outputs above while the inputs are the defaults.", f=font("slate", 9, italic=True))

    section(ws, "B33", "Poisson table (x = 0..60)")
    header_row(ws, 34, 2, ["x", "P(X = x)", "P(X ≤ x)", "Immediate fill if S = x", "EBO if S = x"])
    for k in range(61):
        r = T0 + k
        put(ws, f"B{r}", k, fmt=INT)
        put(ws, f"C{r}", f"=_xlfn.POISSON.DIST(B{r},$E$17,FALSE)", fmt="0.0000")
        put(ws, f"D{r}", f"=_xlfn.POISSON.DIST(B{r},$E$17,TRUE)", fmt="0.0000")
        put(ws, f"E{r}", f"=D{r - 1}" if k else "=0", fmt=PCT)
        put(ws, f"F{r}", f"=$E$17-B{r}+SUMPRODUCT(({xs}<B{r})*(B{r}-{xs})*{pmf})", fmt=NUM3)
        for col in "BCDEF":
            ws[f"{col}{r}"].fill = F_CARD if k % 2 == 0 else F_MID
    ch = LineChart()
    ch.title = "Immediate fill vs total spares S"
    ch.y_axis.title = "P(X ≤ S − 1)"
    ch.x_axis.title = "S"
    ch.height, ch.width = 8, 16
    ch.add_data(Reference(ws, min_col=5, min_row=34, max_row=T1), titles_from_data=True)
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
            ("Window", "deadline_class", 9, None), ("Weekly network demand", "net_weekly_rate", 12, NUM3),
            ("Weekly VMR", "vmr_net_week", 10, NUM3), ("Lead time (d)", "lead_time_d", 10, NUM1),
            ("Lead time sd (d)", "lead_time_sd_d", 10, NUM1), ("Quoted LT (d)", "lt_quoted_d", 10, NUM1),
            ("Unit cost", "unit_cost_aed", 12, AED), ("LTD mean", "ltd_mean", 10, NUM2), ("LTD var", "ltd_var", 10, NUM2),
            ("Dist", "dist_kind", 9, None), ("P1/P2 hub s", "p1_s", 9, INT), ("P1/P2 hub S", "p1_S", 9, INT),
            ("Planted", "planted", 8, None)]
    put(ws, "A1", "ROP examples (reorder-point calculator lookup)", f=font("ice", 16, bold=True))
    put(ws, "A2", "AUH rows of outputs/forecasting/final_forecasts.parquet (network demand over the planner lead-time "
                  "estimate) and the frozen v2 hub reorder point from outputs/policies/P1_stock_params.csv (P1 and P2 "
                  "share the hub C/E parameters). All DERIVED.", f=font("titanium", 10, italic=True))
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
    st = service_targets(d)
    carry = float(d["cfg"]["economics"]["carrying_cost_pct_per_year"])
    k_po = order_cost(d["pcfg"])
    pn0 = default_rop_pn(rop)

    put(ws, "B5", "Pick a PN (AUH planning row)", f=font("ice", 11, bold=True))
    as_input(put(ws, "C5", pn0))
    put(ws, "D5", f"=VLOOKUP($C$5,{exr},2,FALSE)", f=font("titanium", 11, italic=True))
    put(ws, "B6", "Distribution", f=font("ice", 11, bold=True))
    as_input(put(ws, "C6", "Auto"))
    put(ws, "D6", "Auto · Poisson · Negative binomial", f=font("slate", 9, italic=True))
    dv = DataValidation(type="list", formula1=f"={pncol}", allow_blank=False)
    dv2 = DataValidation(type="list", formula1='"Auto,Poisson,Negative binomial"', allow_blank=False)
    dv3 = DataValidation(type="list", formula1='"' + ",".join(st) + '"', allow_blank=True)
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
        (13, "Rectification window class", f"=VLOOKUP($C$5,{exr},4,FALSE)", None, "", "ASSUMED",
         "Hypothetical D0/D3/D10/NONE simulation class (not an MEL decision)"),
    ]
    for r, lab, fx, fmt, unit, tag, note in rows:
        put(ws, f"B{r}", lab, f=font("ice"))
        put(ws, f"C{r}", fx, fmt=fmt)
        as_input(put(ws, f"D{r}", None), fmt)
        as_output(put(ws, f"E{r}", f'=IF(D{r}="",C{r},D{r})'), fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        prov(ws, f"G{r}", tag)
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))
    put(ws, "B14", "Quoted lead time (master data)", f=font("slate", 10, italic=True))
    put(ws, "C14", f"=VLOOKUP($C$5,{exr},9,FALSE)", fmt=NUM1, f=font("slate", 10, italic=True))
    prov(ws, "G14", "SIMULATED")
    st_end = 8 + len(st)
    put(ws, "B15", "Cycle service level", f=font("ice"))
    put(ws, "C15", f"=VLOOKUP(E13,$J$9:$K${st_end},2,FALSE)", fmt=PCT)
    as_input(put(ws, "D15", None), PCT)
    as_output(put(ws, "E15", '=IF(D15="",C15,D15)'), PCT)
    prov(ws, "G15", "ASSUMED")
    put(ws, "H15", "config service_targets by window class; NONE from config/policy.yaml service_target_none (table at J8)",
        f=font("titanium", 9, italic=True))
    for r, lab, v, fmt, unit, tag, note in [
        (16, "Unit cost", f"=VLOOKUP($C$5,{exr},10,FALSE)", AED, "AED", "SIMULATED", "Fictional master-data price"),
        (17, "Ordering cost K per PO", k_po, AED, "AED", "ASSUMED", "config/policy.yaml ordering_cost_aed_per_po"),
        (18, "Carrying rate per year", carry, PCT, "", "ASSUMED", "config economics.carrying_cost_pct_per_year"),
    ]:
        put(ws, f"B{r}", lab, f=font("ice"))
        if isinstance(v, str):
            put(ws, f"C{r}", v, fmt=fmt)
            as_input(put(ws, f"D{r}", None), fmt)
            as_output(put(ws, f"E{r}", f'=IF(D{r}="",C{r},D{r})'), fmt)
        else:
            as_input(put(ws, f"E{r}", v), fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        prov(ws, f"G{r}", tag)
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True))

    header_row(ws, 8, 10, ["Window", "Service target"])
    ws.column_dimensions["J"].width = 11
    ws.column_dimensions["K"].width = 14
    for i, k in enumerate(st):
        put(ws, f"J{9 + i}", k, f=font("ice"))
        as_input(put(ws, f"K{9 + i}", st[k]), PCT)
    prov(ws, f"J{st_end + 1}", "ASSUMED")

    header_row(ws, 20, 2, ["Output", "", "", "Value", "Unit", "", "Formula"])
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
        as_output(put(ws, f"E{r}", fx), fmt)
        put(ws, f"F{r}", unit, f=font("slate", 10))
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))

    section(ws, "B36", "Check against the frozen v2 pipeline")
    put(ws, "B37", "Pipeline P1/P2 hub reorder point s", f=font("ice"))
    put(ws, "E37", f"=VLOOKUP($C$5,{exr},14,FALSE)", fmt=INT, f=font("titanium", 12, bold=True))
    prov(ws, "G37", "DERIVED")
    put(ws, "B38", "Pipeline order-up-to S (with EOQ caps)", f=font("ice"))
    put(ws, "E38", f"=VLOOKUP($C$5,{exr},15,FALSE)", fmt=INT, f=font("titanium", 12, bold=True))
    put(ws, "B39", "Reorder point matches the pipeline?", f=font("ice"))
    as_output(put(ws, "E39", '=IF(E29=E37,"MATCH","DIFFERS")'))
    put(ws, "H39", "Expect MATCH with Auto and no overrides (gnm.policy.policies.reorder_point_from_row).",
        f=font("titanium", 9, italic=True))
    ws.conditional_formatting.add("E39", CellIsRule(operator="equal", formula=['"DIFFERS"'],
                                                    font=Font(color=HEX["amber"], bold=True)))
    row = rop.set_index("pn").loc[pn0]
    s_ref = reorder_point_from_row(row, st[row["deadline_class"]])
    put(ws, "B40", f"Python reference s for the default PN ({pn0})", f=font("slate", 10, italic=True))
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


def _availability_text(ea) -> str:
    if not ea:
        return ""
    s = f"week {ea['week']} ({ea['basis']})"
    if ea.get("past_quote"):
        s += ", past quote"
    return s


def _benefit_text(b) -> str:
    if not b:
        return ""
    if "observed_downtime_h_lookback" in b:
        return (f"{b['observed_downtime_h_lookback']:,.0f} h downtime observed in the lookback at AED "
                f"{b['observed_exposure_rate_aed_per_h']:,.0f}/h ({b.get('note', 'upper bound, not a forecast')})")
    if "capital_above_26w_cover_aed" in b:
        return (f"AED {b['capital_above_26w_cover_aed']:,.0f} capital above 26 weeks of cover; "
                f"AED {b['annual_carrying_cost_aed']:,.0f}/yr carrying cost")
    if "units_expired_in_history" in b:
        return (f"{b['units_expired_in_history']:,.0f} units (AED {b['value_expired_in_history_aed']:,.0f}) expired "
                "in the history")
    return "; ".join(f"{k}: {v}" for k, v in b.items())


EXC_COLS = [("ID", "exception_id", 12), ("Week", "week", 7), ("Type", "type", 28), ("Severity", "severity", 10),
            ("PN", "pn", 13), ("Station", "station", 9), ("Summary", "summary", 60), ("Trigger", "trigger", 34),
            ("Quantity", "quantity", 9), ("Source", "source", 12), ("Destination", "destination", 12),
            ("Required-by week", "required_by_week", 10), ("Expected availability", "expected_availability", 40),
            ("Constraints", "constraints", 44), ("Recommended action", "recommended_action", 60),
            ("Owner", "owner", 18), ("Due week", "due_week", 9), ("Expected benefit", "expected_benefit", 50),
            ("Provenance", None, 12)]


def exception_layout(actions: dict) -> dict:
    types = sorted({a["type"] for a in actions["actions"]})
    owners = list(actions.get("owners") or sorted({a["owner"] for a in actions["actions"]}))
    total_row = 7 + len(types)
    header = max(total_row, 7 + len(owners)) + 3
    return dict(types=types, owners=owners, total_row=total_row, header=header,
                end=header + len(actions["actions"]))


def sheet_exceptions(wb, d):
    ws = wb.create_sheet("Exception list")
    A = d["actions"]
    acts = A["actions"]
    L = exception_layout(A)
    H, end = L["header"], L["end"]
    last = get_column_letter(1 + len(EXC_COLS))
    paint(ws, end + 3, len(EXC_COLS) + 2)
    title(ws, f"Planner exception list (week {A['as_of_week']})",
          "outputs/actions/actions.json · Planner Action Centre rules (V2-AOG-4): only types the v2 simulation "
          "produces, with owners, trigger, quantity, source → destination, expected availability and constraints. "
          "All rows DERIVED from the SIMULATED history (a simulated planning snapshot).")
    rng = {k: f"${get_column_letter(2 + i)}${H + 1}:${get_column_letter(2 + i)}${end}"
           for i, (_, k, _) in enumerate(EXC_COLS) if k}

    section(ws, "B5", "Summary by type and severity (live COUNTIFS over the table below)")
    header_row(ws, 6, 2, ["Type", "urgent", "review", "info", "Total"])
    for i, t in enumerate(L["types"]):
        r = 7 + i
        put(ws, f"B{r}", t, f=font("ice"))
        for j, sev in enumerate(("urgent", "review", "info")):
            put(ws, f"{get_column_letter(3 + j)}{r}",
                f'=COUNTIFS({rng["type"]},$B{r},{rng["severity"]},"{sev}")', fmt=INT)
        as_output(put(ws, f"F{r}", f"=SUM(C{r}:E{r})"), INT)
    rt = L["total_row"]
    put(ws, f"B{rt}", "Total", f=font("ice", 11, bold=True))
    for col in "CDEF":
        as_output(put(ws, f"{col}{rt}", f"=SUM({col}7:{col}{rt - 1})"), INT)

    put(ws, "H5", "By owner", f=font("aero_teal", 13, bold=True))
    header_row(ws, 6, 8, ["Owner", "Actions", "urgent"])
    for i, o in enumerate(L["owners"]):
        r = 7 + i
        put(ws, f"H{r}", o, f=font("ice"))
        as_output(put(ws, f"I{r}", f'=COUNTIF({rng["owner"]},$H{r})'), INT)
        put(ws, f"J{r}", f'=COUNTIFS({rng["owner"]},$H{r},{rng["severity"]},"urgent")', fmt=INT)

    header_row(ws, H, 2, [c[0] for c in EXC_COLS], [c[2] for c in EXC_COLS])
    ws.column_dimensions["A"].width = 3
    ws.row_dimensions[H].height = 32
    wrap = {"summary", "recommended_action", "constraints", "expected_availability", "expected_benefit", "trigger"}
    for j, a in enumerate(acts):
        r = H + 1 + j
        for i, (_, key, _) in enumerate(EXC_COLS):
            col = get_column_letter(2 + i)
            if key is None:
                v = A.get("provenance", "DERIVED")
            elif key == "expected_availability":
                v = _availability_text(a.get(key))
            elif key == "expected_benefit":
                v = _benefit_text(a.get(key))
            elif key == "constraints":
                v = "; ".join(a.get(key) or [])
            else:
                v = a.get(key)
            c = ws[f"{col}{r}"]
            c.value = v
            c.fill = F_CARD if j % 2 == 0 else F_MID
            c.font = font("ice" if i == 0 else "titanium", 10)
            c.alignment = Alignment(vertical="top", wrap_text=key in wrap)
        pc = ws[f"{last}{r}"]
        pc.font = font(PROV_COLOR.get(pc.value, HEX["titanium"]), 10, bold=True)
    ws.auto_filter.ref = f"B{H}:{last}{end}"
    ws.freeze_panes = f"C{H + 1}"
    sev = f"E{H + 1}:E{end}"
    for word, colr in (("urgent", "red"), ("review", "amber"), ("info", "slate")):
        ws.conditional_formatting.add(sev, CellIsRule(operator="equal", formula=[f'"{word}"'],
                                                      fill=PatternFill("solid", fgColor=HEX[colr]),
                                                      font=Font(color=HEX["midnight"], bold=True)))
    ws.conditional_formatting.add(f"B{H + 1}:D{end}", FormulaRule(formula=[f'$E{H + 1}="urgent"'],
                                                                  font=Font(color=HEX["ice"], bold=True)))
    return L


def sheet_aog(wb, d):
    ws = wb.create_sheet("AOG exposure calculator")
    paint(ws, 70, 14)
    for col, w in zip("ABCDEFGHIJKL", [3, 40, 30, 12, 12, 14, 18, 14, 18, 16, 16, 3]):
        ws.column_dimensions[col].width = w
    title(ws, "AOG exposure calculator (material shortage exposure)",
          "Exposure = expected material-related downtime hours × hourly rate × multiplier + fixed cost per event + "
          "direct cost. Downtime counts only if the part is late: wait − window + fitting/RTS (V2-SIM-7, V2-AOG-2). "
          "Same rule the AOG Response Lab uses to rank options.")
    cfg = d["cfg"]
    eco = cfg["economics"]
    pen, evc = eco["aog_penalty_aed_per_hour"], eco["aog_event_cost_aed"]
    win = window_hours(cfg)
    wins = [k for k in ("D0", "D3", "D10") if k in win]
    fit = fitting_hours(cfg)
    fits = [k for k in ("R", "C", "E") if k in fit]

    header_row(ws, 5, 2, ["Input", "Value", "Unit", "Provenance"])
    ins = [(6, "Aircraft archetype", "narrowbody", None, "", "SIMULATED"),
           (7, "Rectification window class (hypothetical)", "D0", None, "", "ASSUMED"),
           (8, "Expected wait for the part", 9, NUM1, "hours", "DERIVED"),
           (9, "Part class (sets the fitting/RTS default)", "R", None, "", "SIMULATED"),
           (10, "Fitting/RTS override (blank = default)", None, NUM1, "hours", "ASSUMED"),
           (11, "Direct cost (logistics, loan fee, premium)", 2650, AED, "AED", "DERIVED"),
           (12, "Hourly-rate multiplier (×0.5 … ×2)", 1, "0.0×", "×", "ASSUMED")]
    for r, lab, v, fmt, unit, tag in ins:
        put(ws, f"B{r}", lab, f=font("ice"))
        as_input(put(ws, f"C{r}", v), fmt)
        put(ws, f"D{r}", unit, f=font("slate", 10))
        prov(ws, f"E{r}", tag)
    for formula, ref in (('"narrowbody,widebody"', "C6"), ('"' + ",".join(wins) + '"', "C7"),
                         ('"' + ",".join(fits) + '"', "C9")):
        v = DataValidation(type="list", formula1=formula, allow_blank=False)
        ws.add_data_validation(v)
        v.add(ref)
    put(ws, "B13", "The multiplier scales the hourly rate only; the fixed cost per event stays ×1 (V2-POL-5).",
        f=font("slate", 9, italic=True))

    header_row(ws, 5, 9, ["Archetype", "AED / downtime h", "Fixed AED / event"])
    for i, a in enumerate(("narrowbody", "widebody")):
        put(ws, f"I{6 + i}", a, f=font("ice"))
        as_input(put(ws, f"J{6 + i}", float(pen[a])), AED)
        as_input(put(ws, f"K{6 + i}", float(evc[a])), AED)
    prov(ws, "I8", "ASSUMED")
    put(ws, "J8", "config economics", f=font("slate", 9, italic=True))
    header_row(ws, 10, 9, ["Window", "Hours"])
    for i, k in enumerate(wins):
        put(ws, f"I{11 + i}", k, f=font("ice"))
        as_input(put(ws, f"J{11 + i}", win[k]), INT)
    wend = 10 + len(wins)
    prov(ws, f"I{wend + 1}", "ASSUMED")
    put(ws, f"J{wend + 1}", "config deadline_classes (NONE never drives AOG)", f=font("slate", 9, italic=True))
    f0 = wend + 3
    header_row(ws, f0, 9, ["Part class", "Fitting/RTS h"])
    for i, k in enumerate(fits):
        put(ws, f"I{f0 + 1 + i}", k, f=font("ice"))
        as_input(put(ws, f"J{f0 + 1 + i}", fit[k]), NUM1)
    fend = f0 + len(fits)
    prov(ws, f"I{fend + 1}", "ASSUMED")
    put(ws, f"J{fend + 1}", "midpoint of config engine.fitting_hours", f=font("slate", 9, italic=True))
    WT = f"$I$11:$J${wend}"
    FT = f"$I${f0 + 1}:$J${fend}"
    RT = "$I$6:$K$7"

    header_row(ws, 15, 2, ["Output", "Value", "Formula"])
    outs = [(16, "Window hours", f"=VLOOKUP(C7,{WT},2,FALSE)", INT, "lookup by window class"),
            (17, "Fitting/RTS hours used", f'=IF(C10="",VLOOKUP(C9,{FT},2,FALSE),C10)', NUM1, "default by part class"),
            (18, "Part late?", '=IF(C8>C16,"Yes","No")', None, "wait > window"),
            (19, "Expected material-related downtime h", "=IF(C8>C16,C8+C17-C16,0)", NUM1,
             "wait + fitting − window, only if late"),
            (20, "Hourly rate used", f"=VLOOKUP(C6,{RT},2,FALSE)*C12", AED, "rate by archetype × multiplier"),
            (21, "Downtime cost", "=C19*C20", AED, "hours × AED/h"),
            (22, "Fixed cost per event", f"=IF(C8>C16,VLOOKUP(C6,{RT},3,FALSE),0)", AED, "only if late, ×1"),
            (23, "Material shortage exposure", "=C21+C22+C11", AED, "downtime + event + direct cost"),
            (24, "Window met?", '=IF(C8<=C16,"Yes","No")', None, "wait ≤ window")]
    for r, lab, fx, fmt, note in outs:
        put(ws, f"B{r}", lab, f=font("ice", 11, bold=(r == 23)))
        as_output(put(ws, f"C{r}", fx), fmt)
        put(ws, f"D{r}", note, f=font("titanium", 9, italic=True))

    incs = showcase_incidents(d["incidents"], cfg)
    ps1_id = d["incidents"]["ps1_incident_id"]
    r = 27
    blocks = []
    first_block = r
    for inc in incs:
        tag = f" ({inc['planted']})" if inc.get("planted") else ""
        section(ws, f"B{r}", f"Worked incident {inc['id']}: {inc['pn']} {inc['desc']} at {inc['station']}{tag}")
        r += 1
        put(ws, f"B{r}", "Archetype / window class", f=font("slate", 10))
        as_input(put(ws, f"C{r}", inc["archetype"]))
        as_input(put(ws, f"D{r}", inc["deadline"]))
        arch_ref, dl_ref = f"$C${r}", f"$D${r}"
        r += 1
        header_row(ws, r, 2, ["Option", "Ranked?", "Wait h", "Fitting h", "Direct cost", "Exposure (formula)",
                              "Rank (formula)", "Pipeline exposure", "Pipeline rank", "Check"])
        r += 1
        opts = [o for o in inc["options"] if o.get("wait_h") is not None]
        first, last = r, r + len(opts) - 1
        wv = f"VLOOKUP({dl_ref},{WT},2,FALSE)"
        for o in opts:
            put(ws, f"B{r}", o["option"] + (" (human decision)" if o.get("human_decision") else
                                            " (not contracted)" if o.get("greyed") else ""), f=font("ice", 10))
            put(ws, f"C{r}", "Yes" if option_ranked(o) else "No", f=font("titanium", 10))
            as_input(put(ws, f"D{r}", float(o["wait_h"])), NUM1)
            as_input(put(ws, f"E{r}", float(o["fitting_h"])), NUM1)
            as_input(put(ws, f"F{r}", float(o["direct_cost"])), AED)
            as_output(put(ws, f"G{r}", f"=IF(D{r}>{wv},(D{r}+E{r}-{wv})*VLOOKUP({arch_ref},{RT},2,FALSE)*$C$12"
                                       f"+VLOOKUP({arch_ref},{RT},3,FALSE),0)+F{r}"), AED)
            as_output(put(ws, f"H{r}", f'=IF(C{r}="Yes",COUNTIFS($C${first}:$C${last},"Yes",$G${first}:$G${last},"<"&G{r})'
                                       f'+COUNTIFS($C${first}:$C${last},"Yes",$G${first}:$G${last},G{r},$D${first}:$D${last},"<"&D{r})+1,"—")'),
                      INT)
            put(ws, f"I{r}", o["exposure_aed"], fmt=AED, f=font("titanium", 10))
            put(ws, f"J{r}", o["rank"] if o.get("rank") is not None else "—", f=font("titanium", 10))
            c = put(ws, f"K{r}", f'=IF(ABS(G{r}-I{r})<0.5,"OK","CHECK")')
            c.font = font("aero_teal", 10, bold=True)
            blocks.append(dict(incident=inc["id"], key=o["key"], row=r, exposure=o["exposure_aed"], rank=o.get("rank"),
                               ps1=inc["id"] == ps1_id))
            r += 1
        put(ws, f"B{r}", "Pipeline exposure from outputs/aog_lab/incidents.json (DERIVED); multiplier C12 = 1 reproduces "
                         "it. Unranked rows: infeasible, pool not contracted, or robbery (engineering/quality approval "
                         "required — human decision, never ranked).", f=font("slate", 9, italic=True))
        r += 3
    ws.conditional_formatting.add(f"K{first_block}:K{r}", CellIsRule(operator="equal", formula=['"CHECK"'],
                                                                     font=Font(color=HEX["amber"], bold=True)))
    ws.freeze_panes = "A5"
    return blocks


def sheet_routes(wb, d):
    ws = wb.create_sheet("AOG recovery routes")
    paint(ws, 60, 10)
    for col, w in zip("ABCDEFGH", [3, 30, 26, 16, 16, 16, 12, 60]):
        ws.column_dimensions[col].width = w
    title(ws, "AOG recovery routes (assumed planning odds)",
          "config/assumptions.yaml aog_sourcing: ASSUMED odds, response times and fees used by the simulated AOG desk "
          "and by the AOG lab. These are planning assumptions, not market data. Borrowed units never join the owned pool.")
    a = d["cfg"]["aog_sourcing"]
    r = 5
    header_row(ws, r, 2, ["Route", "Parameter", "Narrowbody", "Widebody", "All", "Provenance", "Note"])
    r += 1

    def row(route, par, nb=None, wb_=None, al=None, fmt=None, note=""):
        nonlocal r
        put(ws, f"B{r}", route, f=font("ice", 10, bold=True))
        put(ws, f"C{r}", par, f=font("titanium", 10))
        for col, v in (("D", nb), ("E", wb_), ("F", al)):
            if v is not None:
                put(ws, f"{col}{r}", v, fmt=fmt, f=font("ice", 10))
        prov(ws, f"G{r}", "ASSUMED")
        put(ws, f"H{r}", note, f=font("titanium", 9, italic=True), align=Alignment(wrap_text=True))
        r += 1

    def rng(v):
        return f"{v[0]}–{v[1]} h" if isinstance(v, list) else f"{v} h"

    rb = a["robbery"]
    row("Robbery (AUH)", "availability", al=float(rb["availability"]), fmt=PCT,
        note=f"{rb['flag']} — human decision; never ranked by the AOG lab. {rb.get('assumption', '')}")
    row("Robbery (AUH)", "response", al=rng(rb["response_hours"]))
    row("Robbery (AUH)", "labour multiplier", al=float(rb["labour_multiplier"]), fmt="0.0×", note="double fitting labour")
    ex = a["exchange_loan"]
    row("Exchange / loan", "availability", float(ex["availability"]["narrowbody"]), float(ex["availability"]["widebody"]),
        fmt=PCT, note="thinner surplus market for the widebody type")
    row("Exchange / loan", "response", rng(ex["response_hours"]["narrowbody"]), rng(ex["response_hours"]["widebody"]))
    row("Exchange / loan", "exchange fee (% of list)", float(ex["fee_pct_of_list"]["narrowbody"]),
        float(ex["fee_pct_of_list"]["widebody"]), fmt=PCT)
    row("Exchange / loan", "loan fee per day (% of list)", al=float(ex["loan_fee_pct_of_list_per_day"]), fmt=PCT2,
        note="accrues until the own unit replaces the borrowed unit")
    lb = a["local_borrow"]
    row("Local borrow (outstations)", "response", al=rng(lb["response_hours"]))
    row("Local borrow (outstations)", "fixed fee", al=float(lb["fee_aed_fixed"]), fmt=AED)
    row("Local borrow (outstations)", "loan fee per day (% of list)", al=float(lb["loan_fee_pct_of_list_per_day"]), fmt=PCT2)
    lu = a["local_buy"]
    row("Local buy / borrow (C/E)", "availability", al=float(lu["availability"]), fmt=PCT, note="every station")
    row("Local buy / borrow (C/E)", "response", al=rng(lu["response_hours"]))
    row("Local buy / borrow (C/E)", "premium", al=float(lu["premium_pct"]), fmt=PCT)
    for cls, h in a["retry_hours"].items():
        row("Retry interval", f"part class {cls}", al=f"{h} h", note="a failed route is retried with fresh draws while the need is open")
    r += 1
    section(ws, f"B{r}", "Local borrow availability by outstation")
    r += 1
    header_row(ws, r, 2, ["Station", "Narrowbody", "Widebody", "Provenance"])
    r += 1
    av = lb["availability"]
    for stn in av["narrowbody"]:
        put(ws, f"B{r}", stn, f=font("ice", 10))
        put(ws, f"C{r}", float(av["narrowbody"][stn]), fmt=PCT)
        put(ws, f"D{r}", float(av["widebody"].get(stn, 0.0)), fmt=PCT)
        prov(ws, f"E{r}", "ASSUMED")
        r += 1
    r += 1
    section(ws, f"B{r}", "Why this matters")
    r += 1
    dep = d["frontier"].get("aog_desk_dependence") or {}
    txt = ("Results depend heavily on these routes. ")
    if dep.get("p0_aog_hours") is not None:
        txt += (f"With the routes switched off (a structural stress, selection seeds), expected material-related "
                f"downtime rises to about {dep['p0_aog_hours']:,.0f} h/yr for the Simple Rulebook (P0), "
                f"{dep['base_aog_hours']:,.0f} for the Network Plan (P2) and "
                f"{dep['rec_aog_hours']:,.0f} for the Network Plan + Extra Spares (I125), against {dep['central_p0_aog_hours']:,.0f} / "
                f"{dep['central_base_aog_hours']:,.0f} / {dep['central_rec_aog_hours']:,.0f} with them "
                "(docs/data/frontier.json aog_desk_dependence).")
    put(ws, f"B{r}", txt, f=font("titanium", 10), align=Alignment(wrap_text=True, vertical="top"))
    ws.merge_cells(f"B{r}:H{r}")
    ws.row_dimensions[r].height = 48
    prov(ws, f"B{r + 1}", "SIMULATED")


def text_gate(wb) -> None:
    """v2.1 text rules (docs/agent_notes/v21_brief.md): scrub every text cell with the exporter's scrub (narrowbody /
    widebody archetype names, forbidden words), then fail the build if anything is left."""
    bad = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and not c.value.startswith("="):
                    c.value = v21.scrub_text(c.value)
                    for kind, pat in v21.FORBIDDEN_PATTERNS.items():
                        if pat.search(c.value):
                            bad.append((kind, ws.title, c.coordinate, c.value[:80]))
    if bad:
        raise SystemExit(f"workbook text gate failed: {bad[:5]}")


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
    sheet_routes(wb, d)
    wb._sheets = [wb[n] for n in SHEETS]
    text_gate(wb)
    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = HEX["aero_teal"] if "calculator" in ws.title else HEX["deep_steel"]
    wb.properties.title = "GROUNDED NO MORE planner workbook (v2)"
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
    if p.resolve() == OUT.resolve():
        DOWNLOAD.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, DOWNLOAD)
        print(f"copied to {DOWNLOAD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
