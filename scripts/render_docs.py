"""Render the result numbers into the project docs (v2 world).

Templates live in ``docs/templates/<NAME>.md.tmpl`` and carry ``{{RESULT:<key>}}`` placeholders.
This script computes every key from pipeline outputs (``outputs/``, ``docs/data/*.json``, the P0
history in ``data/processed/history/``, ``reports/junit.xml`` and ``git log``), formats it consistently
and writes the rendered files to the repository root (README.md, METHODOLOGY.md, MODEL_CARD.md,
LIMITATIONS.md, STUDY_GUIDE.md) and ``reports/VALIDATION_REPORT.md``.

Rules:
* No number is typed by hand: every value is read or computed from an output file.
* Headline numbers are the v2 HOLDOUT (seeds 2000-2019, central world). Selection numbers are labelled.
* An unknown placeholder is an error: nothing is written and the script exits non-zero.
* STUDY_GUIDE keys may be extended by an optional module ``scripts/render_keys_study.py`` exposing
  ``keys() -> dict[str, str]`` (owned by the study-guide author). A key it returns that this script also
  computes must carry the same value, otherwise the script fails.

Formatting: money "AED 49.0M" (>= 1M) or "AED 2,650"; rates "97.7%"; hours "210 h";
CIs "[146–274]" ("[−1,629 to −1,332]" when negative values are involved; money CIs in AED M).

Usage:  python scripts/render_docs.py [--check] [--only NAME ...]
        --check  render in memory and fail if a rendered file differs from the one on disk.
        --only   render only the named docs (e.g. --only README.md reports/VALIDATION_REPORT.md).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
DATA = ROOT / "docs" / "data"
HIST = ROOT / "data" / "processed" / "history"
TEMPLATES = ROOT / "docs" / "templates"
DOCS = ["README.md", "METHODOLOGY.md", "MODEL_CARD.md", "LIMITATIONS.md", "STUDY_GUIDE.md"]
VALIDATION = ("VALIDATION_REPORT.md", ROOT / "reports" / "VALIDATION_REPORT.md")
STUDY_KEYS = ROOT / "scripts" / "render_keys_study.py"
V2_REVIEW_HEADING = "### v2 reviews"
PLACEHOLDER = re.compile(r"\{\{RESULT:([A-Za-z0-9_.]+)\}\}")
MINUS = "−"
HUB = "AUH"

sys.path.insert(0, str(ROOT / "src"))


# ----------------------------------------------------------------------------- formatting
def _neg(s: str) -> str:
    return s.replace("-", MINUS)


def fmt_int(x: float) -> str:
    return _neg(f"{round(x):,.0f}")


def fmt_num(x: float, d: int = 2) -> str:
    return _neg(f"{x:,.{d}f}")


def fmt_signed(x: float, d: int = 0) -> str:
    s = f"{abs(x):,.{d}f}"
    return ("+" if x > 0 else MINUS if x < 0 else "") + s


def fmt_aed(x: float, signed: bool = False) -> str:
    sign = ("+" if x > 0 else MINUS if x < 0 else "") if signed else (MINUS if x < 0 else "")
    a = abs(x)
    body = f"AED {a / 1e6:.1f}M" if a >= 1e6 else f"AED {a:,.0f}"
    return sign + body


def fmt_m(x: float, signed: bool = False, d: int = 1) -> str:
    """Money always in AED millions: AED 0.6M, +AED 7.6M."""
    sign = ("+" if x > 0 else MINUS if x < 0 else "") if signed else (MINUS if x < 0 else "")
    return f"{sign}AED {abs(x) / 1e6:.{d}f}M"


def fmt_pct(x: float, d: int = 1) -> str:
    return _neg(f"{x * 100:.{d}f}%")


def fmt_h(x: float, signed: bool = False) -> str:
    return (fmt_signed(x) if signed else fmt_int(x)) + " h"


def _range(lo: str, hi: str, any_neg: bool) -> str:
    return f"[{lo} to {hi}]" if any_neg else f"[{lo}–{hi}]"


def ci_int(lo: float, hi: float) -> str:
    return _range(fmt_int(lo), fmt_int(hi), lo < 0 or hi < 0)


def ci_num(lo: float, hi: float, d: int = 2) -> str:
    return _range(fmt_num(lo, d), fmt_num(hi, d), lo < 0 or hi < 0)


def ci_pct(lo: float, hi: float, d: int = 1) -> str:
    return _range(_neg(f"{lo * 100:.{d}f}"), _neg(f"{hi * 100:.{d}f}"), lo < 0 or hi < 0)


def ci_pts(lo: float, hi: float, d: int = 2) -> str:
    """CI on a difference already expressed in percentage points."""
    return _range(_neg(f"{lo:.{d}f}"), _neg(f"{hi:.{d}f}"), lo < 0 or hi < 0)


def ci_aed_m(lo: float, hi: float, d: int = 1) -> str:
    """Money CI in AED millions, e.g. [41.4–42.3]."""
    return _range(_neg(f"{lo / 1e6:.{d}f}"), _neg(f"{hi / 1e6:.{d}f}"), lo < 0 or hi < 0)


def fmt_aed_ci(mean: float, lo: float, hi: float, signed: bool = False) -> str:
    """Money with CI on one scale: AED 41.9M [41.4–42.3], AED 0.95M [0.73–1.17] or AED 2,650 [2,000–3,000]."""
    big = max(abs(mean), abs(lo), abs(hi))
    sign = ("+" if mean > 0 else MINUS if mean < 0 else "") if signed else (MINUS if mean < 0 else "")
    if abs(mean) >= 1e6:
        return f"{sign}AED {abs(mean) / 1e6:.1f}M {ci_aed_m(lo, hi)}"
    if big >= 1e5:
        return f"{sign}AED {abs(mean) / 1e6:.2f}M {ci_aed_m(lo, hi, 2)}"
    return f"{sign}AED {abs(mean):,.0f} {_range(fmt_int(lo), fmt_int(hi), lo < 0 or hi < 0)}"


def seeds_txt(seeds) -> str:
    s = sorted(int(x) for x in seeds)
    assert s == list(range(s[0], s[-1] + 1)), "seed list is not contiguous"
    return f"{s[0]}–{s[-1]}"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ----------------------------------------------------------------------------- loaders
def jload(path: Path):
    return json.loads(path.read_text())


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def git_log() -> list[tuple[str, str]]:
    """(short hash, subject), oldest first."""
    rows = []
    for ln in git("log", "--format=%h\t%s", "--reverse").splitlines():
        h, _, s = ln.partition("\t")
        rows.append((h, s))
    return rows


def find_commit(log: list[tuple[str, str]], prefix: str) -> tuple[int, str, str]:
    hits = [(i, h, s) for i, (h, s) in enumerate(log) if s.startswith(prefix)]
    if not hits:
        raise SystemExit(f"no commit whose subject starts with {prefix!r}")
    return hits[-1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def junit_root() -> ET.Element:
    return ET.parse(ROOT / "reports" / "junit.xml").getroot()


def junit_counts() -> tuple[Counter, Counter, Counter, dict]:
    root = junit_root()
    n, bad, skip = Counter(), Counter(), Counter()
    for tc in root.iter("testcase"):
        mod = tc.get("classname").split(".")[-1]
        n[mod] += 1
        if any(ch.tag in ("failure", "error") for ch in tc):
            bad[mod] += 1
        if any(ch.tag == "skipped" for ch in tc):
            skip[mod] += 1
    suite = next(root.iter("testsuite")).attrib
    return n, bad, skip, suite


def junit_case_passed(module: str, name: str) -> bool:
    for tc in junit_root().iter("testcase"):
        if tc.get("classname").endswith(module) and tc.get("name") == name:
            return not any(ch.tag in ("failure", "error", "skipped") for ch in tc)
    return False


def per_part(err: pd.DataFrame, method: str, metric: str = "mase") -> pd.Series:
    e = err[err.method == method]
    if metric == "mase":
        e = e[e.mase_status == "ok"]
    return e.groupby("pn")[metric].mean()


def boot_ci(x: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    bs = x[rng.integers(0, x.size, size=(n_boot, x.size))].mean(axis=1)
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def t_ci(x: np.ndarray) -> tuple[float, float, float]:
    from scipy import stats
    m = float(x.mean())
    hw = float(stats.t.ppf(0.975, x.size - 1) * x.std(ddof=1) / math.sqrt(x.size))
    return m, m - hw, m + hw


METHOD_LABEL = {"zero": "Zero", "naive": "naive", "ma": "moving average", "croston": "Croston", "sba": "SBA",
                "tsb": "TSB", "adida": "ADIDA", "imapa": "IMAPA", "bootstrap": "bootstrap",
                "reliability": "reliability-exposure"}
CLASS_LABEL = {"C": "consumables", "E": "expendables", "R": "rotables"}
WORLD_LABEL = {"low_stress": "low stress", "central": "central", "high_stress": "high stress"}


# ----------------------------------------------------------------------------- compute
def compute() -> dict[str, str]:  # noqa: C901, PLR0915 - one flat list of keys is easier to audit
    import yaml

    V: dict[str, str] = {}
    kpis = jload(DATA / "kpis.json")
    pol = jload(DATA / "policies.json")
    fr = jload(DATA / "frontier.json")
    fc = jload(DATA / "forecast.json")
    parts = jload(DATA / "parts.json")
    aog = jload(DATA / "aog_lab.json")
    act = jload(DATA / "actions.json")
    method = jload(DATA / "method.json")
    fsum = jload(OUT / "frontier" / "summary.json")
    tr = jload(OUT / "holdout" / "truth_recovery.json")
    post = jload(OUT / "holdout" / "postplan_i125_stress.json")
    cal = jload(OUT / "calibration" / "p0_history_summary.json")
    cfg = yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())

    H = kpis["headline"]
    core, fo, hon = H["core"], H["frontier_option"], H["honest"]
    if kpis["core_id"] != "P2" or kpis["baseline_id"] != "P0" or kpis["reference_id"] != "I125":
        raise SystemExit("templates are written for core P2, baseline P0 and frontier option I125")
    if not (core["holds_all_worlds"] and core["holds_penalty_range"]):
        raise SystemExit("the templates state that P2 holds in all worlds and penalty settings; it no longer does")
    K = {k["id"]: k for k in kpis["kpis"]}
    P = {p["policy_id"]: p for p in pol["policies"]}
    pts = {p["id"]: p for p in fr["points"]}
    spts = {p["id"]: p for p in fr["selection_points"]}
    paired = pol["paired"]

    # ---------------------------------------------------------------- seeds, calendar
    V["seeds.holdout"] = seeds_txt(kpis["seeds"])
    V["seeds.selection"] = seeds_txt(pol["selection"]["seeds"])
    V["seeds.n"] = str(len(kpis["seeds"]))
    V["seeds.kpi_weeks"] = f"{kpis['kpi_weeks'][0]}–{kpis['kpi_weeks'][1]}"
    v1 = method["v1_archive"]
    V["seeds.v1_holdout"] = v1["holdout_seeds"]
    hs = cfg["seeds"]["holdout_seeds"]
    if f"{hs[0]}–{hs[1]}" != V["seeds.holdout"]:
        raise SystemExit("config holdout seeds differ from the exported holdout seeds")

    # ---------------------------------------------------------------- policies table (holdout, central)
    def put_metric(pid: str, kpi: dict):
        def m(name):
            return kpi[name]["mean"], kpi[name]["ci_lo"], kpi[name]["ci_hi"]
        mu, lo, hi = m("immediate_fill_rate")
        V[f"policies.{pid}.immediate_fill_rate"] = fmt_pct(mu)
        V[f"policies.{pid}.immediate_fill_rate_ci"] = ci_pct(lo, hi)
        mu, lo, hi = m("aog_hours")
        V[f"policies.{pid}.aog_hours"] = fmt_h(mu)
        V[f"policies.{pid}.aog_hours_ci"] = ci_int(lo, hi)
        mu, lo, hi = m("aog_events")
        V[f"policies.{pid}.aog_events"] = fmt_num(mu, 1)
        V[f"policies.{pid}.aog_events_ci"] = ci_num(lo, hi, 1)
        mu, lo, hi = m("spare_capital_aed")
        V[f"policies.{pid}.spare_capital_aed"] = fmt_aed(mu)
        V[f"policies.{pid}.spare_capital_aed_ci"] = ci_aed_m(lo, hi)
        mu, lo, hi = m("total_annual_cost_aed")
        V[f"policies.{pid}.total_annual_cost_aed"] = fmt_aed(mu)
        V[f"policies.{pid}.total_annual_cost_aed_ci"] = ci_aed_m(lo, hi)
        mu, lo, hi = m("expedite_cost_aed")
        V[f"policies.{pid}.expedite_cost_aed"] = fmt_aed(mu)
        pen = kpi["aog_penalty_aed"]["mean"]
        V[f"policies.{pid}.aog_penalty_aed"] = fmt_aed(pen)
        V[f"policies.{pid}.opex_ex_penalty_aed"] = fmt_aed(kpi["total_annual_cost_aed"]["mean"] - pen)

    for pid in ("P0", "P1", "P2", "I125"):
        put_metric(pid, P[pid]["kpi"])
    # the site's KPI tiles must equal the policy table (README test relies on it)
    assert abs(K["aog_hours"]["value"] - P["P2"]["kpi"]["aog_hours"]["mean"]) < 1e-6
    assert abs(K["aog_hours"]["reference"]["value"] - P["I125"]["kpi"]["aog_hours"]["mean"]) < 1e-6

    def put_pair(key: str, d: dict):
        x = d["aog_hours"]
        V[f"{key}.delta_aog_hours"] = fmt_h(x["mean"], signed=True)
        V[f"{key}.delta_aog_hours_ci"] = ci_int(x["ci_lo"], x["ci_hi"])
        x = d["immediate_fill_rate"]
        V[f"{key}.delta_fill_pts"] = fmt_signed(x["mean"] * 100, 2) + " pts"
        V[f"{key}.delta_fill_pts_ci"] = ci_pts(x["ci_lo"] * 100, x["ci_hi"] * 100)
        x = d["spare_capital_aed"]
        V[f"{key}.delta_capital"] = fmt_m(x["mean"], signed=True, d=2 if abs(x["mean"]) < 1e6 else 1)
        V[f"{key}.delta_capital_ci"] = ci_aed_m(x["ci_lo"], x["ci_hi"], 2 if abs(x["mean"]) < 1e6 else 1)
        x = d["total_annual_cost_aed"]
        V[f"{key}.delta_total_cost"] = fmt_aed_ci(x["mean"], x["ci_lo"], x["ci_hi"], signed=True)
        x = d["expedite_cost_aed"]
        V[f"{key}.delta_expedite"] = fmt_aed_ci(x["mean"], x["ci_lo"], x["ci_hi"], signed=True)

    put_pair("policies.P1_vs_P0", paired["P1-P0"])
    put_pair("policies.P2_vs_P0", paired["P2-P0"])
    put_pair("policies.P2_vs_P1", paired["P2-P1"])
    p20 = paired["P2-P0"]["aog_hours"]
    V["policies.P0_vs_P2.delta_aog_hours"] = fmt_h(-p20["mean"], signed=True)
    V["policies.P0_vs_P2.delta_aog_hours_ci"] = ci_int(-p20["ci_hi"], -p20["ci_lo"])
    p21 = paired["P2-P1"]["aog_hours"]
    V["policies.P1_vs_P2.delta_aog_hours"] = fmt_h(-p21["mean"], signed=True)
    V["policies.P1_vs_P2.delta_aog_hours_ci"] = ci_int(-p21["ci_hi"], -p21["ci_lo"])

    # ---------------------------------------------------------------- headline: P2 core finding
    sp = {pid: pd.read_csv(OUT / "policies" / f"{pid}_stock_params.csv") for pid in ("P0", "P1", "P2")}

    def out_rot(df):
        r = df[df.part_class == "R"]
        return int(r[r.station != HUB].base_stock.sum())
    n_out = {pid: out_rot(sp[pid]) for pid in sp}
    if n_out != {k: int(v) for k, v in core["outstation_rotables"].items()}:
        raise SystemExit(f"outstation rotable units {n_out} differ from the export {core['outstation_rotables']}")
    for pid, v in n_out.items():
        V[f"network.{pid}.outstation_rotables"] = str(v)
    red, cap = core["aog_reduction"], core["capital_aed"]
    assert abs(red["mean"] + p20["mean"]) < 1e-6, "kpis headline and policies paired P2-P0 disagree"
    V["core.aog_reduction"] = fmt_h(red["mean"])
    V["core.aog_reduction_ci"] = ci_int(*red["ci"])
    V["core.aog_reduction_pct"] = fmt_pct(red["mean"] / P["P0"]["kpi"]["aog_hours"]["mean"], 0)
    V["core.capital"] = fmt_m(cap["mean"], signed=True)
    V["core.capital_ci"] = ci_aed_m(*cap["ci"], 2)
    tc = core["total_cost_aed"]
    V["core.total_cost"] = fmt_aed_ci(tc["mean"], tc["ci"][0], tc["ci"][1], signed=True)
    V["core.baseline_sentence"] = f"vs a legacy OEM-quote policy holding only {n_out['P0']} outstation rotables"
    V["core.headline"] = (
        f"**Network positioning (P2) cuts material AOG by {V['core.aog_reduction']} a year "
        f"{V['core.aog_reduction_ci']} {V['core.baseline_sentence']}, for about {V['core.capital']} of spares "
        f"capital.** P2 holds {n_out['P2']} rotables at the six outstations instead of {n_out['P0']} and pools "
        f"the rest at the hub. Material AOG falls from {V['policies.P0.aog_hours']} to {V['policies.P2.aog_hours']} "
        f"a year ({V['core.aog_reduction_pct']} lower) on the holdout (seeds {V['seeds.holdout']}, paired 95% CI). "
        f"It holds in all three calibrated worlds and across the ×0.5–×2 range of the hourly AOG penalty.")
    wtxt = []
    for w in core["worlds"]:
        wtxt.append(f"{WORLD_LABEL[w['variant']]} {fmt_h(w['aog_hours']['mean'], signed=True)} "
                    f"{ci_int(*w['aog_hours']['ci'])} at {fmt_m(w['capital_aed']['mean'], signed=True)} capital")
    V["core.worlds_summary"] = "; ".join(wtxt)
    pr = core["penalty_range"]
    V["core.penalty_summary"] = "; ".join(
        f"{lab} {fmt_aed_ci(pr[k]['mean'], pr[k]['ci'][0], pr[k]['ci'][1], signed=True)}"
        for k, lab in (("x0.5", "×0.5"), ("x1", "×1"), ("x2", "×2")))
    # world-re-planned policy holdout (P1/P2 rebuilt from each world's own history)
    sens = pol["sensitivity"]
    rows = ["| World | P0 h/yr | P1 h/yr | P2 h/yr | P2 − P0 h/yr [95% CI] | P2 − P0 capital | P2 − P0 total annual cost |",
            "|---|---|---|---|---|---|---|"]
    for w in ("low_stress", "central", "high_stress"):
        if w == "central":
            pp_, pa = {p["policy_id"]: p for p in pol["policies"]}, pol["paired"]
        else:
            pp_, pa = {p["policy_id"]: p for p in sens[w]["policies"]}, sens[w]["paired"]
        d = pa["P2-P0"]
        rows.append(f"| {WORLD_LABEL[w]} | {fmt_int(pp_['P0']['kpi']['aog_hours']['mean'])} | "
                    f"{fmt_int(pp_['P1']['kpi']['aog_hours']['mean'])} | {fmt_int(pp_['P2']['kpi']['aog_hours']['mean'])} | "
                    f"{fmt_h(d['aog_hours']['mean'], signed=True)} {ci_int(d['aog_hours']['ci_lo'], d['aog_hours']['ci_hi'])} | "
                    f"{fmt_m(d['spare_capital_aed']['mean'], signed=True)} | "
                    f"{fmt_aed_ci(d['total_annual_cost_aed']['mean'], d['total_annual_cost_aed']['ci_lo'], d['total_annual_cost_aed']['ci_hi'], signed=True)} |")
    V["core.worlds_table"] = "\n".join(rows)

    # ---------------------------------------------------------------- frontier option I125
    rv = pol["recommended_vs_P2"]
    assert abs(rv["aog_hours"]["mean"] + fo["aog_reduction"]["mean"]) < 1e-6
    V["policies.I125_vs_P2.delta_aog_hours"] = fmt_h(rv["aog_hours"]["mean"], signed=True)
    V["policies.I125_vs_P2.delta_aog_hours_ci"] = ci_int(rv["aog_hours"]["ci_lo"], rv["aog_hours"]["ci_hi"])
    V["fo.extra_capital"] = fmt_m(fo["extra_capital_aed"]["mean"])
    V["fo.extra_capital_ci"] = ci_aed_m(*fo["extra_capital_aed"]["ci"], 2)
    V["fo.aog_reduction"] = fmt_h(fo["aog_reduction"]["mean"])
    V["fo.aog_reduction_ci"] = ci_int(*fo["aog_reduction"]["ci"])
    V["fo.aog_hours"] = fmt_h(fo["aog_hours"])
    V["fo.capital"] = fmt_aed(fo["capital_aed"])
    t = fo["total_cost_aed"]
    V["fo.total_cost_saving"] = fmt_aed_ci(-t["mean"], -t["ci"][1], -t["ci"][0])
    tat = fo["repair_tat_x0_75"]
    if tat["net_benefit_significant"]:
        raise SystemExit("templates say the I125 cost lead is not significant at repair TAT x0.75")
    nb = tat["net_benefit_aed"]
    V["fo.tat075_net"] = fmt_aed_ci(nb["mean"], nb["ci"][0], nb["ci"][1], signed=True)
    V["fo.tat075_aog"] = f"{fmt_h(tat['aog_reduction']['mean'])} {ci_int(*tat['aog_reduction']['ci'])}"
    shifts = {s["setting"]: s["recommended"] for s in fo["rule_shifts"]}
    V["fo.rule_shift"] = f"{shifts['x0.5']} at ×0.5 and {shifts['x2.0']} at ×2 the hourly rate"
    stab = {(s["factor"], s["setting"]): s["recommended"] for s in fr["recommendation"]["stability"]}
    V["fo.carrying_stable"] = ("unchanged at carrying cost 15% and 25%"
                               if stab[("carrying_cost", "0.15")] == stab[("carrying_cost", "0.25")] == "I125"
                               else "different at carrying cost 15% or 25%")
    pw = {w: {r["id"]: r for r in rows_} for w, rows_ in post["worlds"].items()}
    ptxt = []
    for w in ("low_stress", "high_stress"):
        r = pw[w]["I125"]
        ptxt.append(f"{WORLD_LABEL[w]} {fmt_h(r['d_aog_hours_vs_base_mean'], signed=True)} "
                    f"{ci_int(r['d_aog_hours_vs_base_lo'], r['d_aog_hours_vs_base_hi'])} a year and total annual cost "
                    f"{fmt_aed_ci(r['d_total_cost_vs_base_mean'], r['d_total_cost_vs_base_lo'], r['d_total_cost_vs_base_hi'], signed=True)} "
                    f"for {fmt_m(r['d_capital_vs_base_mean'], signed=True)} capital (I125 {fmt_h(r['aog_hours_mean'])} vs "
                    f"central-built P2 {fmt_h(pw[w]['P2']['aog_hours_mean'])})")
    V["fo.postplan_summary"] = "; ".join(ptxt)
    V["fo.headline"] = (
        f"**Frontier option: if you invest an additional {V['fo.extra_capital']}**, the frontier point I125 (P2 plus "
        f"greedy rotable additions) cuts a further {V['fo.aog_reduction']} a year {V['fo.aog_reduction_ci']} vs P2 "
        f"({V['fo.aog_hours']} vs {V['policies.P2.aog_hours']}) and lowers total annual cost by "
        f"{V['fo.total_cost_saving']} (holdout, paired). Sensitivity, on the selection seeds and one factor at a time: "
        f"its cost lead over P2 is not significant if repair is 25% faster ({V['fo.tat075_net']} a year), and the "
        f"pre-stated rule moves to {V['fo.rule_shift']}. Post-plan check (D015, added after the main holdout, no "
        f"re-selection): {V['fo.postplan_summary']}.")

    # ---------------------------------------------------------------- honest findings
    ch = fc["champions"]
    n_best = sum(c["holdout_rank"] == 1 for c in ch)
    assert n_best == hon["forecast_champions_best"] and len(ch) == hon["forecast_cells"]
    ir = next(c for c in ch if c["demand_class"] == "intermittent" and c["part_class"] == "R")
    V["honest.champions_best"] = f"{n_best} of {len(ch)}"
    V["honest.ir_champion"] = METHOD_LABEL[ir["method"]]
    V["honest.ir_rank"] = f"{ordinal(ir['holdout_rank'])} of {ir['n_methods']}"
    V["honest.ir_best"] = METHOD_LABEL[ir["holdout_best"]]
    trr = tr["reliability"]["all"]
    V["honest.mtbur_hist"] = f"{trr['estimated_mdale'] * 100:.0f}%"
    V["honest.mtbur_quote"] = f"{trr['quoted_mdale'] * 100:.0f}%"
    V["honest.mtbur_closer"] = fmt_pct(trr["share_estimate_closer"], 0)
    V["honest.mtbur_n"] = str(trr["n_parts"])
    ro = fr["aog_desk_dependence"]
    V["honest.routes_off"] = (
        f"with the routes switched off (selection seeds, a structural stress) material AOG rises from "
        f"{fmt_h(ro['central_p0_aog_hours'])} to {fmt_h(ro['p0_aog_hours'])} a year under P0, from "
        f"{fmt_h(ro['central_base_aog_hours'])} to {fmt_h(ro['base_aog_hours'])} under P2 and from "
        f"{fmt_h(ro['central_rec_aog_hours'])} to {fmt_h(ro['rec_aog_hours'])} under I125")
    cons = kpis["consistency"]
    n_in = sum(c["selection_inside_holdout_ci"] for c in cons)
    i125_in = pts["I125"]["aog_ci"][0] <= spts["I125"]["aog_hours"] <= pts["I125"]["aog_ci"][1]
    V["honest.consistency"] = (
        f"for P2 the selection-seed value of {n_in} of {len(cons)} headline KPIs lies inside the holdout 95% CI "
        f"(material AOG {fmt_h(spts['P2']['aog_hours'])} on selection, {V['policies.P2.aog_hours']} "
        f"{V['policies.P2.aog_hours_ci']} on holdout); I125 scored {fmt_h(spts['I125']['aog_hours'])} on selection "
        f"and {V['policies.I125.aog_hours']} {V['policies.I125.aog_hours_ci']} on holdout "
        f"({'inside' if i125_in else 'outside'} the CI)")
    lo_w, hi_w = cal["variants"]["low_stress"], cal["variants"]["high_stress"]
    tg = cal["targets"]
    V["honest.band_ends"] = (
        f"the low-stress world reaches the AOG end of the band (pooled history and selection "
        f"{fmt_int(lo_w['pooled_history_selection']['aog_hours_per_year'])} h/yr; band end {fmt_int(tg['aog_hours_per_year'][0])}) "
        f"at {lo_w['pooled_history_selection']['rotable_immediate_fill_rate']:.3f} rotable fill, and the high-stress world "
        f"reaches the fill end ({hi_w['pooled_history_selection']['rotable_immediate_fill_rate']:.3f}; band end "
        f"{tg['rotable_immediate_fill_rate'][0]:.2f}) at about {fmt_int(hi_w['pooled_history_selection']['aog_hours_per_year'])} "
        f"h/yr, well short of the {fmt_int(tg['aog_hours_per_year'][1])} h end, because fill binds first")

    # ---------------------------------------------------------------- calibration
    V["cal.band"] = (f"P0 network rotable immediate fill {tg['rotable_immediate_fill_rate'][0]:.2f}–"
                     f"{tg['rotable_immediate_fill_rate'][1]:.2f}, material AOG {fmt_int(tg['aog_hours_per_year'][0])}–"
                     f"{fmt_int(tg['aog_hours_per_year'][1])} h/yr, AOG events {tg['aog_events_per_year'][0]}–"
                     f"{tg['aog_events_per_year'][1]}/yr")
    vb = cfg["calibration_targets"]["v1_band"]
    V["cal.v1_band"] = (f"rotable fill {vb['rotable_immediate_fill_rate'][0]:.2f}–{vb['rotable_immediate_fill_rate'][1]:.2f}, "
                        f"AOG {fmt_int(vb['aog_hours_per_year'][0])}–{fmt_int(vb['aog_hours_per_year'][1])} h/yr, events "
                        f"{vb['aog_events_per_year'][0]}–{vb['aog_events_per_year'][1]}/yr")
    su = cal["settings_used"]
    V["cal.settings"] = (f"`quoted_mtbur_optimism` {su['parts.quoted_mtbur_optimism']:.2f}, `quoted_mtbur_noise_sd_log` "
                         f"{su['parts.quoted_mtbur_noise_sd_log']:.2f}, `quoted_tat_optimism` "
                         f"{su['generator.quoted_tat_optimism']:.2f}, `quoted_tat_noise_sd_log` "
                         f"{su['generator.quoted_tat_noise_sd_log']:.2f}")
    sv = su["generator.variants"]
    V["cal.low_scale"] = f"{sv['low_stress']['true_mtbur_scale']:.2f}"
    V["cal.high_scale"] = f"{sv['high_stress']['true_mtbur_scale']:.2f}"
    V["cal.not_applied"] = " and the ".join(su["not_applied"])
    gap = jload(OUT / "calibration" / "v2_p0_gap_diagnosis.json")
    var = jload(OUT / "calibration" / "v2_p0_variants.json")
    pre, postfx = gap["raw_p0_prefix"]["history"], gap["raw_p0_postfix"]["history"]
    afterA = gap["decisions_A_to_C"]["raw_p0_after_A"]["history"]
    v1h = var["V1 quote accuracy"]["history"]
    chain = ["| Step (central world, P0, history weeks 0–103) | What changed | Rotable fill | Material AOG h/yr | Events/yr | In band |",
             "|---|---|---|---|---|---|"]

    def inband(f, a, e):
        return all([tg["rotable_immediate_fill_rate"][0] <= f <= tg["rotable_immediate_fill_rate"][1],
                    tg["aog_hours_per_year"][0] <= a <= tg["aog_hours_per_year"][1],
                    tg["aog_events_per_year"][0] <= e <= tg["aog_events_per_year"][1]])
    for lab, what, h in (
            ("1. Raw v2 P0", "domain rebuild (V2-SIM-1..9), uncalibrated", pre),
            ("2. Gap diagnosis fixes", "V2-SIM-10..12: P0 fill definition, pipeline weighting, reservation bug", postfx),
            ("3. Realism corrections A", "V2-SIM-13..15: planned brake supply, AOG route retries, hub wheel shop", afterA),
            ("4. Calibration V1 (locked)", "quote accuracy only (V2-SIM-CAL)", v1h)):
        chain.append(f"| {lab} | {what} | {h['rotable_immediate_fill_rate']:.3f} | {fmt_int(h['aog_hours_per_year'])} | "
                     f"{fmt_int(h['aog_events_per_year'])} | "
                     f"{'yes' if inband(h['rotable_immediate_fill_rate'], h['aog_hours_per_year'], h['aog_events_per_year']) else 'no'} |")
    V["cal.history_table"] = "\n".join(chain)
    vt = ["| Variant (measured in memory, nothing applied) | Rotable fill, history / selection | Material AOG h/yr, history / selection | Events/yr, history / selection | All in band |",
          "|---|---|---|---|---|"]
    for name, v in var.items():
        h, s = v["history"], v["selection_mean"]
        vt.append(f"| {name}{' (chosen)' if name.startswith('V1') else ''} | {h['rotable_immediate_fill_rate']:.3f} / "
                  f"{s['rotable_immediate_fill_rate']:.3f} | {fmt_int(h['aog_hours_per_year'])} / {fmt_int(s['aog_hours_per_year'])} | "
                  f"{fmt_int(h['aog_events_per_year'])} / {fmt_int(s['aog_events_per_year'])} | {'yes' if v['all_inside'] else 'no'} |")
    V["cal.variants_table"] = "\n".join(vt)
    v3 = next(v for k, v in var.items() if k.startswith("V3"))
    V["limits.linekit"] = (
        f"the in-memory variant V3 (the calibrated quote settings plus a legacy line-station kit of "
        f"{v3['line_kit_units']} units; [METHODOLOGY section 6](METHODOLOGY.md#6-calibration-p0-only-and-the-lock)) gave "
        f"P0 {fmt_int(v3['history']['aog_hours_per_year'])} h/yr of history downtime instead of "
        f"{fmt_int(v1h['aog_hours_per_year'])} h, at {fmt_int(v3['history']['aog_events_per_year'])} events/yr "
        f"({'inside' if v3['all_inside'] else 'outside'} the band), and was not applied")
    n_in_band = [k for k, v in var.items() if v["all_inside"]]
    V["cal.variants_in_band"] = ", ".join(n_in_band)
    ex = gap["experiments_postfix"]
    full = ex["full (as built)"]["rotable_fill"]

    def gain(k):
        return fmt_signed(ex[k]["rotable_fill"] - full, 2)
    V["cal.diagnosis"] = (
        f"with P0's own assumptions true the engine reproduces Poisson availability (simulated rotable fill "
        f"{ex['ideal (P0 assumptions hold)']['rotable_fill']:.3f} against a demand-weighted analytic "
        f"{gap['analytic_weighted_hub']['postfix']:.3f}; it was {gap['analytic_weighted_hub']['prefix']:.3f} on paper "
        f"before the V2-SIM-10 fix). What remains is intended realism. Switching one factor off at a time from the "
        f"as-built fill of {full:.3f}: quoted-vs-true removal rates {gain('rates = quoted')}, quoted-vs-true TAT "
        f"{gain('TAT mean = quoted')}, unstocked outstation demand under the legacy line-station rule "
        f"{gain('all rotable demand at AUH')}, and NFF works the other way ({gain('no NFF')} if removed)")
    ctab = ["| World (true-MTBUR scale) | Target | Rotable fill, history / selection | Material AOG h/yr, history / selection | Events/yr, history / selection | In the central band |",
            "|---|---|---|---|---|---|"]
    for w in ("central", "low_stress", "high_stress"):
        v = cal["variants"][w]
        h, s = v["history"], v["selection_p0_mean"]
        tgt = ("central band" if w == "central" else
               ", ".join(f"{'fill' if 'fill' in k else 'AOG'} {x if 'fill' in k else fmt_int(x)}"
                         for k, x in cal["variant_targets"][w].items()))
        inb = all(tg[k][0] <= h[k] <= tg[k][1] for k in tg)
        ctab.append(f"| {WORLD_LABEL[w]} (×{v['true_mtbur_scale']:.2f}) | {tgt} | {h['rotable_immediate_fill_rate']:.3f} / "
                    f"{s['rotable_immediate_fill_rate']:.3f} | {fmt_int(h['aog_hours_per_year'])} / {fmt_int(s['aog_hours_per_year'])} | "
                    f"{fmt_int(h['aog_events_per_year'])} / {fmt_int(s['aog_events_per_year'])} | {'yes' if inb else 'no'} |")
    V["cal.worlds_table"] = "\n".join(ctab)

    # ---------------------------------------------------------------- freeze / git chain
    log = git_log()
    i_arch, h_arch, _ = find_commit(log, "Archive v1")
    i_cal, h_cal, _ = find_commit(log, "v2 CALIBRATION LOCK")
    i_fix, h_fix, _ = find_commit(log, "v2 bug fixes before freeze")
    i_frz, h_frz, _ = find_commit(log, "v2 FREEZE")
    i_hol, h_hol, _ = find_commit(log, "v2 HOLDOUT")
    i_pp, h_pp, _ = find_commit(log, "Post-plan robustness check")
    if not (i_arch < i_cal < i_fix < i_frz < i_hol < i_pp):
        raise SystemExit("v2 commit chain is out of order")
    V["freeze.archive_commit"] = f"`{h_arch}`"
    V["freeze.cal_commit"] = f"`{h_cal}`"
    V["freeze.fix_commit"] = f"`{h_fix}`"
    V["freeze.commit_sha"] = f"`{h_frz}`"
    V["freeze.holdout_commit_sha"] = f"`{h_hol}`"
    V["freeze.postplan_commit"] = f"`{h_pp}`"
    manifest_path = OUT / "freeze" / "manifest.json"
    manifest = jload(manifest_path)
    V["freeze.manifest_sha256"] = sha256(manifest_path)
    V["freeze.n_artefacts"] = str(len(manifest["artefacts"]))
    V["freeze.frozen_at"] = method["freeze"]["frozen_at"][:19].replace("T", " ") + " UTC"
    V["freeze.verified"] = ("verified (`gnm.freeze.verify()` passed at export)" if method["freeze"]["verified"]
                            else "NOT verified")
    V["freeze.v1_incident"] = method["freeze"]["forced_rerun_note"].removeprefix("Holdout incident, disclosed. ")
    hl = jload(OUT / "freeze" / "holdout_log.json")
    v2runs = [r for r in hl if r["run"].startswith("v2_")]
    n_pp = sum("postplan" in r["run"] for r in v2runs)
    V["freeze.v2_runs"] = f"{len(v2runs) - n_pp} main v2 runs and {n_pp} post-plan run{'s' if n_pp != 1 else ''}"
    V["freeze.v2_forced"] = str(sum(r["forced"] for r in v2runs))
    V["freeze.candidates_sha"] = fsum["candidates_sha256"][:8] + "…"
    lock = jload(OUT / "freeze" / "calibration_lock.json")
    V["freeze.cal_lock_files"] = str(len(lock["artefacts"]))
    V["meta.git_sha"] = kpis["meta"]["git_sha"]
    import tomllib
    V["meta.model_version"] = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]

    # ---------------------------------------------------------------- v1 archive
    v1h_ = {r["policy"]: r for r in v1["headline"]}
    V["v1.tag"] = f"`{v1['tag']}` ({v1['commit']})"
    V["v1.n_reasons"] = str(len(v1["superseded_because"]))
    V["v1.reasons"] = "\n".join(f"- {r}" for r in v1["superseded_because"])
    vt1 = ["| Policy (v1, archived) | Material AOG h/yr [95% CI] | Spare capital |", "|---|---|---|"]
    for pid in ("P0", "P1", "P2", "I125"):
        r = v1h_[pid]
        vt1.append(f"| {r['label']} | {fmt_int(r['aog_hours'])} {ci_int(*r['aog_ci'])} | {fmt_aed(r['capital_aed'])} |")
    V["v1.headline_table"] = "\n".join(vt1)

    # ---------------------------------------------------------------- frontier and optimiser
    recm = fr["recommendation"]
    V["frontier.n_candidates"] = str(fsum["n_candidates"])
    V["frontier.recommendation_rule"] = recm["rule"]
    V["frontier.h_star"] = fmt_num(recm["h_star_per_aed_1m"], 1)
    V["frontier.aed_per_aog_hour"] = fmt_aed(recm["aed_per_aog_hour"])
    V["frontier.carrying_pct"] = fmt_pct(recm["carrying_pct"], 0)
    rs = recm["recommended_vs_P2_selection"]
    V["frontier.sel.I125_vs_P2"] = (f"{fmt_h(-rs['aog_reduction_mean'], signed=True)} "
                                    f"{ci_int(-rs['aog_reduction_hi'], -rs['aog_reduction_lo'])}")
    V["frontier.sel.I125_net"] = fmt_aed_ci(rs["net_benefit_mean"], rs["net_benefit_lo"], rs["net_benefit_hi"], signed=True)
    V["frontier.sel.I125_aog"] = f"{fmt_h(spts['I125']['aog_hours'])} {ci_int(*spts['I125']['aog_ci'])}"
    V["frontier.sel.P2_aog"] = f"{fmt_h(spts['P2']['aog_hours'])} {ci_int(*spts['P2']['aog_ci'])}"
    V["frontier.sel.P0_aog"] = f"{fmt_h(spts['P0']['aog_hours'])} {ci_int(*spts['P0']['aog_ci'])}"
    b = pts["B100"]
    V["frontier.B100_vs_P2"] = f"{fmt_h(b['d_aog_vs_P2'], signed=True)} {ci_int(*b['d_aog_vs_P2_ci'])}"
    g = spts["P2_GUARD"]
    V["frontier.guard_cost"] = f"{fmt_h(g['d_aog_vs_P2'], signed=True)} {ci_int(*g['d_aog_vs_P2_ci'])}"
    mx = np.array([p["model_aog_hours"] for p in fr["points"]], float)
    sx = np.array([p["aog_hours"] for p in fr["points"]], float)
    r_hold = float(np.corrcoef(mx, sx)[0, 1])
    V["frontier.model_vs_sim"] = (
        f"the analytic model predicts {fmt_h(pts['P0']['model_aog_hours'])} a year for P0 against "
        f"{fmt_h(pts['P0']['aog_hours'])} simulated on the holdout, {fmt_h(pts['P2']['model_aog_hours'])} against "
        f"{fmt_h(pts['P2']['aog_hours'])} for P2 and {fmt_h(pts['I125']['model_aog_hours'])} against "
        f"{fmt_h(pts['I125']['aog_hours'])} for I125. It overstates P0 and understates the network plans, so it is a "
        f"ranking heuristic, not a forecast of AOG hours; it ranks well (r = {r_hold:.2f} across the "
        f"{len(fr['points'])} frontier points on the holdout, r = {fsum['model_vs_sim_corr_aog']:.2f} on selection seeds)")
    rt = pd.read_csv(OUT / "frontier" / "rotable_totals.csv").groupby("candidate")[["total_spares", "loop_units"]].sum()
    for pid in ("P0", "P1", "P2", "I125"):
        V[f"policy.{pid}.rotable_total_spares"] = fmt_int(rt.loc[pid, "total_spares"])
    V["policy.loop_units"] = fmt_int(rt.loc["P2", "loop_units"])
    rmx = json.loads((ROOT / "docs/data/kpis.json").read_text())["headline"]["core"]["remix"]
    V["policy.remix.buy_units"] = fmt_int(rmx["buy_units"])
    V["policy.remix.buy_aed"] = fmt_aed(rmx["buy_aed"])
    V["policy.remix.shed_units"] = fmt_int(rmx["shed_units"])
    V["policy.remix.shed_aed"] = fmt_aed(rmx["shed_aed"])
    _H = ROOT / "data/processed/history"
    _rb = pd.read_parquet(_H / "aog_robberies.parquet")
    _rq = pd.read_parquet(_H / "material_requests.parquet")[["request_id", "deadline_class"]]
    _ae = pd.read_parquet(_H / "aog_events.parquet")
    _yrs = 2.0
    V["limits.robbery_per_yr"] = fmt_int(len(_rb) / _yrs)
    V["limits.donor_h_per_yr"] = fmt_int((_rb.reinstated_h - _rb.robbed_h).sum() / _yrs)
    V["limits.donor_days_mean"] = f"{(_rb.reinstated_h - _rb.robbed_h).mean() / 24:.0f} days"
    V["limits.robbery_d3d10_share"] = f"{_rb.merge(_rq, on='request_id', how='left').deadline_class.isin(['D3', 'D10']).mean():.0%}"
    V["limits.p0_history_aog_per_yr"] = fmt_int(_ae.hours.sum() / _yrs)
    _p0 = pd.read_csv(OUT / "policies" / "P0_stock_params.csv")
    _pm = pd.read_parquet(_H / "part_master.parquet")[["pn", "removal_mode"]]
    _o = _p0[(_p0.station != "AUH") & (_p0.base_stock > 0)].merge(_pm, on="pn")
    V["limits.p0_out_total"] = fmt_int(_o.base_stock.sum())
    V["limits.p0_out_brakes"] = fmt_int(_o[_o.removal_mode == "wear_planned"].base_stock.sum())
    V["scope.pn_count"] = fmt_int(len(pd.read_parquet(ROOT / "data/processed/history/part_master.parquet")))
    passed = junit_case_passed("test_optim_greedy", "test_greedy_equals_brute_force_at_breakpoints")
    V["optim.greedy_gap_small_case_pct"] = (
        "on a small separable, convex toy case the greedy allocation equals the brute-force optimum at every greedy "
        "breakpoint (unit test `tests/test_optim_greedy.py::test_greedy_equals_brute_force_at_breakpoints`, passing); "
        "no exact comparison exists for the full, non-separable network problem" if passed else
        "no passing exact comparison is recorded in `reports/junit.xml`")
    tor = {t["factor"]: t for t in fr["tornado"]}
    tp = tor["aog_penalty"]
    V["frontier.sensitivity.penalty_half_vs_double"] = (
        f"on the selection seeds I125's net annual benefit over P2 is {fmt_aed_ci(tp['low_value'], *tp['low_ci'], signed=True)} "
        f"at hourly penalty ×0.5 and {fmt_aed_ci(tp['high_value'], *tp['high_ci'], signed=True)} at ×2, against "
        f"{fmt_aed(tp['base'], signed=True)} at ×1, and the rule's pick moves to {V['fo.rule_shift']}")
    trows = ["| Factor (one at a time, selection seeds) | Setting | I125 − P2 net annual benefit [95% CI] | Material AOG h saved vs P2 |",
             "|---|---|---|---|"]
    trows.append(f"| base case | — | {fmt_aed_ci(rs['net_benefit_mean'], rs['net_benefit_lo'], rs['net_benefit_hi'], signed=True)} | "
                 f"{fmt_h(rs['aog_reduction_mean'])} |")
    for t_ in fr["tornado"]:
        for side in ("low", "high"):
            trows.append(f"| {t_['factor'].replace('_', ' ')} | {t_[side + '_setting']} | "
                         f"{fmt_aed_ci(t_[side + '_value'], *t_[side + '_ci'], signed=True)} | {fmt_h(t_[side + '_aog_saved'])} |")
    V["frontier.tornado_table"] = "\n".join(trows)
    vr = {v["variant"]: v for v in fr["variant_robustness"]}
    V["frontier.sel_worlds"] = "; ".join(
        f"{WORLD_LABEL[w]} {fmt_h(-vr[w]['rec_vs_P2']['aog_reduction'], signed=True)} "
        f"{ci_int(-vr[w]['rec_vs_P2']['aog_reduction_ci'][1], -vr[w]['rec_vs_P2']['aog_reduction_ci'][0])}, net "
        f"{fmt_aed_ci(vr[w]['rec_vs_P2']['net_benefit_aed'], *vr[w]['rec_vs_P2']['net_benefit_ci'], signed=True)}"
        for w in ("low_stress", "central", "high_stress"))

    # ---------------------------------------------------------------- network / hub vs outstation (holdout)
    sk = pd.read_parquet(OUT / "holdout" / "policy_station_kpis.parquet")
    sk = sk[sk.variant == "central"]
    by = sk.groupby(["policy_id", "station"]).aog_hours.mean().unstack(0)
    out_share_p0 = by.loc[by.index != HUB, "P0"].sum() / by["P0"].sum()
    V["network.P0.outstation_share"] = fmt_pct(out_share_p0, 0)
    V["network.P0.outstation_hours"] = fmt_h(by.loc[by.index != HUB, "P0"].sum())
    st = ["| Station | P0 h/yr | P1 h/yr | P2 h/yr |", "|---|---|---|---|"]
    for s_ in [HUB] + sorted(x for x in by.index if x != HUB):
        st.append(f"| {s_} | {fmt_int(by.loc[s_, 'P0'])} | {fmt_int(by.loc[s_, 'P1'])} | {fmt_int(by.loc[s_, 'P2'])} |")
    V["network.station_table"] = "\n".join(st)
    V["network.P2_vs_P1.aog_hours_reduction_pct"] = fmt_pct(-p21["mean"] / P["P1"]["kpi"]["aog_hours"]["mean"], 0)
    V["network.P2_vs_P1.delta_aog_hours"] = fmt_h(p21["mean"], signed=True)
    V["network.P2_vs_P1.delta_aog_hours_ci"] = ci_int(p21["ci_lo"], p21["ci_hi"])
    dcap = paired["P2-P1"]["spare_capital_aed"]["mean"]
    V["network.P2_vs_P1.delta_capital_aed"] = f"{fmt_aed(abs(dcap))} {'less' if dcap < 0 else 'more'} capital"
    # STUDY_GUIDE compatibility names
    for pid in ("P0", "P1", "P2"):
        V[f"network.{pid}.units_forward_positioned"] = str(n_out[pid])
    V["policies.P2_vs_P0.delta_aog_hours_pct"] = V["core.aog_reduction_pct"]
    # by-class fill (count parts explain the lower immediate fill)
    bc = pd.DataFrame(pol["by_class"])
    bc = bc[bc.variant == "central"].set_index(["policy_id", "part_class"])
    V["policies.fill_by_class"] = "; ".join(
        f"{CLASS_LABEL[c]} P0 {bc.loc[('P0', c), 'immediate_fill_rate']:.3f} vs P2 {bc.loc[('P2', c), 'immediate_fill_rate']:.3f}"
        for c in ("C", "E", "R"))
    routes = ["| Policy | Robbery / yr | Exchange/loan / yr | Local borrow / yr | Local buy / yr |", "|---|---|---|---|---|"]
    rsum = pd.DataFrame(pol["by_class"])
    rsum = rsum[rsum.variant == "central"].groupby("policy_id")[[
        "route_robbery_per_year", "route_exchange_loan_per_year", "route_local_borrow_per_year", "route_local_buy_per_year"]].sum()
    for pid in ("P0", "P1", "P2"):
        r = rsum.loc[pid]
        routes.append(f"| {pid} | {r.route_robbery_per_year:.1f} | {r.route_exchange_loan_per_year:.1f} | "
                      f"{r.route_local_borrow_per_year:.1f} | {r.route_local_buy_per_year:.1f} |")
    V["policies.routes_table"] = "\n".join(routes)

    # ---------------------------------------------------------------- legacy line-station weakness, brakes, shop queue
    pm = pd.read_parquet(HIST / "part_master.parquet").set_index("pn")
    ae = pd.read_parquet(HIST / "aog_events.parquet")
    rows_ = []
    for e in ae.itertuples(index=False):
        pns = str(e.pns).split(";")
        for pn in pns:
            rows_.append((pn, e.station, e.hours / len(pns)))
    split = pd.DataFrame(rows_, columns=["pn", "station", "h"])
    years = 2.0  # history weeks 0-103
    weak = pm[(pm.description.str.contains("wheel and tyre|oxygen mask", case=False, regex=True)
               | pm.planted.astype(str).str.contains("PS1", na=False)) & (pm.deadline_class == "D0")]
    lw = ["| D0 part | Material AOG h/yr (P0 history, weeks 0–103) | Share at outstations | P0 outstation units | P2 outstation units |",
          "|---|---|---|---|---|"]
    tot_w = tot_w_out = 0.0

    def out_units(df, pn, cls):
        d = df[(df.pn == pn) & (df.station != HUB)]
        return int(d.base_stock.sum()) if cls == "R" else int(d.s.clip(lower=0).sum())
    for pn, r in weak.iterrows():
        s_ = split[split.pn == pn]
        h_all, h_out = s_.h.sum(), s_[s_.station != HUB].h.sum()
        tot_w += h_all
        tot_w_out += h_out
        unit = "units" if r.part_class == "R" else "reorder-point units (min)"
        lw.append(f"| {pn} {r.description} | {h_all / years:.0f} | {fmt_pct(h_out / h_all, 0) if h_all else '—'} | "
                  f"{out_units(sp['P0'], pn, r.part_class)} {unit} | {out_units(sp['P2'], pn, r.part_class)} |")
    mask = weak[weak.description.str.contains("oxygen mask", case=False)]
    if len(mask):
        mpn = mask.index[0]
        ms = split[split.pn == mpn]
        V["limits.mask_out_share"] = fmt_pct(ms[ms.station != HUB].h.sum() / ms.h.sum(), 0) if ms.h.sum() else "0%"
        V["limits.mask_pn"] = f"{mpn} {mask.iloc[0].description}"
    V["limits.line_station_table"] = "\n".join(lw)
    V["limits.line_station_share"] = fmt_pct(tot_w / split.h.sum(), 0)
    V["limits.line_station_out_share"] = fmt_pct(tot_w_out / tot_w, 0)
    brakes = pm[pm.removal_mode == "wear_planned"]
    V["limits.brake_history"] = ", ".join(
        f"{pn} {r.description} {split[split.pn == pn].h.sum() / years:.0f} h/yr" for pn, r in brakes.iterrows())
    V["limits.bench_share"] = fmt_pct(cfg["engine"]["shop_bench_time_share"], 0)
    qj = [o for i in aog["incidents"] for o in i["options"] if o["key"] == "repair_queue_jump"]
    nq = sum("NO_QUEUE_TO_JUMP" in o["reason_codes"] for o in qj)
    n_rot = sum("ROTABLES_ONLY" not in o["reason_codes"] for o in qj)
    V["limits.queue_jump"] = f"{nq} of the {n_rot} rotable showcase incidents"

    # ---------------------------------------------------------------- AOG lab, actions, parts
    s = aog["summary"]
    cf = s["counterfactual"]
    V["aog.n_incidents"] = str(s["n_incidents"])
    V["aog.hours"] = fmt_h(s["aog_hours_total"])
    V["aog.reconcile"] = (f"{fmt_int(s['aog_hours_reconstructed'])} of {fmt_int(s['aog_hours_total'])} history "
                          f"material AOG hours reconstructed request by request across {s['n_incidents']} incidents "
                          f"({'reconciles' if s['reconciles'] else 'DOES NOT reconcile'})")
    ex_r = cf["excluding_history_robbery"]
    V["aog.counterfactual"] = (
        f"history took the rank-1 option in {cf['history_took_best_option']} of {cf['requests_compared']} requests; "
        f"excluding the {cf['history_used_robbery']} robbery cases (never ranked), the actual route gave "
        f"{fmt_h(ex_r['actual_request_aog_h'])} against {fmt_h(ex_r['best_option_request_aog_h'])} for the ranked "
        f"option, so the legacy AOG desk already takes about the best per-incident route and the lever is positioning")
    inc = next(i for i in aog["incidents"] if i["id"] == aog["ps1_incident_id"])
    ts = pd.Timestamp(inc["need_datetime"].replace("Z", ""))
    tz = {"BOM": 330, "CAI": 120, "JED": 180, "LHR": 0, "FRA": 60, "SIN": 480, "AUH": 240}[inc["station"]]
    local = ts + pd.to_timedelta(tz, unit="min")
    tl = {x["step"]: x for x in inc["timeline"]}
    V["story.local_time"] = f"{local:%H:%M} local ({ts:%H:%M} UTC)"
    V["story.tail"] = inc["tail"]
    V["story.incident_id"] = inc["id"]
    V["story.station"] = inc["station"]
    V["story.pn"] = inc["pn"]
    V["story.desc"] = inc["desc"]
    V["story.aog_hours"] = fmt_h(inc["aog_hours"])
    V["story.wait_h"] = fmt_h(tl["arrived"]["t_h"])
    V["story.fitting_h"] = fmt_h(tl["released"]["evidence"]["fitting_h"])
    V["story.auh_on_hand"] = str(inc["snapshot"]["on_hand"][HUB])
    for pid in ("P0", "P2"):
        V[f"story.{pid}_station_units"] = str(int(sp[pid].query("pn == @inc['pn'] and station == @inc['station']").base_stock.sum()))
        V[f"story.{pid}_outstation_units"] = str(int(sp[pid].query("pn == @inc['pn'] and station != @HUB").base_stock.sum()))
    V["story.p0_line_rule"] = cfg["calibration_targets"]["p0_rule"].split(": ", 1)[-1]
    acts = act["actions"]
    V["actions.week.as_of"] = str(act["as_of_week"])
    V["actions.week.count_total"] = str(len(acts))
    V["actions.week.count_urgent"] = str(act["counts"]["by_severity"]["urgent"])
    for i in range(3):
        a = acts[i]
        V[f"actions.top{i + 1}.summary"] = (f"{a['summary']} ({a['severity']}: {a['recommended_action'][0].lower()}"
                                            f"{a['recommended_action'][1:]})")
    plist = parts["parts"]
    urgent = [p for p in plist if p["risk_level"] == "urgent"]
    tot = sum(p["aog_hours_hist_per_yr"] for p in plist)
    V["parts.top_risk.count"] = str(len(urgent))
    V["parts.top_risk.share_of_aog_hours_pct"] = fmt_pct(sum(p["aog_hours_hist_per_yr"] for p in urgent) / tot, 0)
    top = max(plist, key=lambda p: p["risk_hours"])
    V["parts.top_risk.rank1.pn"] = f"{top['pn']}, {top['desc']}"
    V["parts.top_risk.rank1.risk_hours"] = fmt_int(top["risk_hours"])
    stt = split[split.pn == top["pn"]].groupby("station").h.sum().sort_values(ascending=False)
    V["parts.top_risk.rank1.station"] = f"{stt.index[0]} ({fmt_pct(stt.iloc[0] / stt.sum(), 0)} of its history AOG hours)"
    ps1 = pm[pm.planted.astype(str).str.contains("PS1", na=False)]
    V["story.ps1"] = f"{ps1.index[0]} ({ps1.iloc[0].description})" if len(ps1) else "PS1"

    # ---------------------------------------------------------------- forecasting
    champs = pd.read_csv(OUT / "forecasting" / "champions.csv")
    cm = Counter(p["demand_class"] for p in plist)
    V["forecast.class_counts"] = " / ".join(str(cm.get(c, 0)) for c in
                                           ("smooth", "erratic", "intermittent", "lumpy", "insufficient_data"))
    lines = ["| Demand class | Part class | Parts | Champion (frozen) | Selection MASE | Holdout MASE | Holdout rank | Best on holdout |",
             "|---|---|---|---|---|---|---|---|"]
    for c in ch:
        lines.append(f"| {c['demand_class']} | {c['part_class']} | {c['n_parts']} | {METHOD_LABEL[c['method']]} | "
                     f"{c['mase']:.3f} | {c['holdout_mase']:.3f} | {c['holdout_rank']} of {c['n_methods']} | "
                     f"{METHOD_LABEL[c['holdout_best']]} |")
    V["forecast.champions_table"] = "\n".join(lines)
    herr = pd.read_parquet(OUT / "holdout" / "forecast_errors.parquet")
    serr = pd.read_parquet(OUT / "forecasting" / "errors.parquet")

    def champion_rows(err):
        m_ = err.merge(champs[["demand_class", "part_class", "champion"]], on=["demand_class", "part_class"])
        return m_[m_.method == m_.champion]

    hc = champion_rows(herr)
    V["forecast.holdout.champion_mase"] = f"{hc[hc.mase_status == 'ok'].groupby('pn').mase.mean().mean():.3f}"
    V["forecast.holdout.naive_mase"] = f"{per_part(herr, 'naive').mean():.3f}"
    V["forecast.holdout.champion_bias"] = fmt_num(hc.groupby("pn").bias.mean().mean(), 3)
    V["forecast.holdout.champion_pis"] = fmt_num(hc.groupby("pn").pis.mean().mean(), 2)
    V["forecast.holdout.coverage_q90"] = f"{hc.groupby('pn').cov_q90.mean().mean():.3f}"

    def rel_vs_croston(err):
        rem = err[err.part_class.isin(["E", "R"])]
        rel = per_part(rem, "reliability")
        fam = {m_: per_part(rem, m_) for m_ in ("croston", "sba", "tsb")}
        best = min(fam, key=lambda m_: fam[m_].mean())
        d = (rel - fam[best]).dropna()
        lo, hi = boot_ci(d.to_numpy())
        return dict(rel=rel.mean(), best=best, best_mase=fam[best].mean(), d=d.mean(), lo=lo, hi=hi, n=d.size)

    h_ = rel_vs_croston(herr)
    s_ = rel_vs_croston(serr)
    V["forecast.reliability.mase"] = f"{h_['rel']:.3f}"
    V["forecast.best_croston_family.mase"] = f"{h_['best_mase']:.3f}"
    V["forecast.best_croston_family.method"] = METHOD_LABEL[h_["best"]]
    V["forecast.reliability_vs_croston.delta_mase"] = fmt_signed(h_["d"], 3)
    V["forecast.reliability_vs_croston.delta_mase_ci"] = ci_num(h_["lo"], h_["hi"], 3)

    def verdict(x):
        if x["hi"] < 0:
            return "the reliability model beats the best Croston-family method on MASE"
        if x["lo"] > 0:
            return ("the reliability model does not beat the best Croston-family method on MASE; it is "
                    "significantly worse on point accuracy")
        return ("the reliability model does not beat the best Croston-family method on MASE; the difference is "
                "not significant, so it is a tie on point accuracy")

    V["forecast.reliability_vs_croston.verdict"] = verdict(h_) + f" ({h_['n']} parts, 95% bootstrap CI over parts)"
    V["forecast.reliability_vs_croston.selection_summary"] = (
        f"reliability {s_['rel']:.3f} vs {METHOD_LABEL[s_['best']]} {s_['best_mase']:.3f}, difference "
        f"{fmt_signed(s_['d'], 3)} {ci_num(s_['lo'], s_['hi'], 3)} ({s_['n']} parts); {verdict(s_).split(';')[-1].strip()}")
    lbc = pd.DataFrame(fc["leaderboard_by_class_holdout"])
    lbc = lbc[(lbc.demand_class == "all") & (lbc.method != "zero")]
    pin_txt = []
    for pc in ("E", "R"):
        gg = lbc[lbc.part_class == pc].set_index("method")
        bestpin = gg.pinball_q90.idxmin()
        other = gg.drop(index="reliability").pinball_q90.min()
        pin_txt.append(f"{CLASS_LABEL[pc]} {gg.loc['reliability', 'pinball_q90']:.3f} vs next best {other:.3f}"
                       + ("" if bestpin == "reliability" else f" (best: {METHOD_LABEL[bestpin]})"))
    best_ER = all(lbc[lbc.part_class == pc].set_index("method").pinball_q90.idxmin() == "reliability" for pc in ("E", "R"))
    V["forecast.reliability.pinball_summary"] = (
        ("it has the lowest q90 pinball loss of all methods for both expendables and rotables on the holdout ("
         if best_ER else "q90 pinball loss on the holdout (") + "; ".join(pin_txt) + ")")
    lb = pd.DataFrame(fc["leaderboard_by_class_holdout"])
    lb = lb[lb.demand_class == "all"]
    methods = [m_ for m_ in METHOD_LABEL if m_ in set(lb.method)]
    head = "| Method | " + " | ".join(f"{CLASS_LABEL[pc].capitalize()} MASE [CI] | {CLASS_LABEL[pc].capitalize()} q90 pinball"
                                     for pc in ("C", "E", "R")) + " |"
    rows_md = [head, "|---|" + "---|" * 6]
    best_mase = {pc: lb[(lb.part_class == pc) & (lb.method != "zero")].set_index("method").mase.idxmin() for pc in "CER"}
    best_pin = {pc: lb[(lb.part_class == pc) & (lb.method != "zero")].set_index("method").pinball_q90.idxmin() for pc in "CER"}
    for m_ in methods:
        cells = []
        for pc in "CER":
            r = lb[(lb.part_class == pc) & (lb.method == m_)].iloc[0]
            mtxt = f"{r['mase']:.3f} [{r['mase_ci'][0]:.3f}–{r['mase_ci'][1]:.3f}]"
            ptxt = f"{r['pinball_q90']:.3f}"
            if m_ == best_mase[pc]:
                mtxt = f"**{mtxt}**"
            if m_ == best_pin[pc]:
                ptxt = f"**{ptxt}**"
            cells += [mtxt, ptxt]
        label = METHOD_LABEL[m_] + (" (benchmark, not eligible)" if m_ == "zero" else "")
        rows_md.append(f"| {label} | " + " | ".join(cells) + " |")
    rows_md += ["", "Full tables: `outputs/holdout/forecast_leaderboard.csv` (by demand class × part class) and "
                    "`outputs/forecasting/leaderboard.csv` (selection window)."]
    V["forecast.leaderboard_table"] = "\n".join(rows_md)
    V["forecast.truth_recovery.estimated_vs_quoted_improvement"] = (
        f"across {trr['n_parts']} removal-driven parts the median absolute log error of MTBUR is "
        f"{trr['quoted_mdale']:.3f} for the vendor quote (about {V['honest.mtbur_quote']} off) and "
        f"{trr['estimated_mdale']:.3f} for the history-based estimate (about {V['honest.mtbur_hist']} off); the estimate is "
        f"closer to the hidden truth for {V['honest.mtbur_closer']} of parts")
    V["forecast.truth_recovery.median_ape_pct"] = V["forecast.truth_recovery.estimated_vs_quoted_improvement"]
    mon = fc["monash"]
    mres = {r["method"]: r for r in mon["results"]}
    elig = {m_: r for m_, r in mres.items() if m_ != "zero"}
    mb = min(elig, key=lambda m_: elig[m_]["mase"])
    V["monash.summary"] = (
        f"Dataset: {mon['dataset']}, {mon['info']['n_series']:,} monthly series, licence {mon['licence']}, data "
        f"provenance {mon['data_provenance']} (metrics DERIVED). Best eligible method {METHOD_LABEL[mb]} with mean MASE "
        f"{elig[mb]['mase']:.3f} [{elig[mb]['mase_ci_lo']:.3f}–{elig[mb]['mase_ci_hi']:.3f}]; the all-zero forecast scores "
        f"{mres['zero']['mase']:.3f}, which is why zero is never allowed to be a champion. Attribution: "
        f"{mon['attribution'].rstrip('.')}.")

    # ---------------------------------------------------------------- Palm vs sim (P1, selection)
    pvs = pd.read_csv(OUT / "policies" / "palm_vs_sim.csv")
    pvs = pvs[pvs.sim_requests > 0]
    hub_rows = pvs[pvs.station == HUB]
    V["policy.palm_vs_sim.summary"] = (
        f"at AUH mean Palm fill {hub_rows.palm_availability.mean():.3f} vs simulated immediate fill "
        f"{hub_rows.sim_immediate_fill.mean():.3f} over {len(hub_rows)} rotables (mean absolute gap "
        f"{(hub_rows.sim_immediate_fill - hub_rows.palm_availability).abs().mean():.3f}): the simulated hub is below Palm "
        f"because the next serviceable unit first reinstates robbed donors and hands back loans; at outstations "
        f"{pvs[pvs.station != HUB].palm_availability.mean():.3f} vs {pvs[pvs.station != HUB].sim_immediate_fill.mean():.3f}, "
        f"because Palm with a local repair loop ignores resupply from AUH")

    # ---------------------------------------------------------------- config-quoted parameters (ASSUMED)
    pc, fl, gen, eco = cfg["parts"], cfg["fleet"], cfg["generator"], cfg["economics"]
    V["config.mtbur_ranges"] = (f"{pc['mtbur_fh'][0]:,}–{pc['mtbur_fh'][1]:,} FH or {pc['mtbur_fc'][0]:,}–"
                                f"{pc['mtbur_fc'][1]:,} FC by default, with family-specific ranges in the config")
    V["config.utilisation"] = (f"narrowbody about {fl['narrowbody']['fh_per_day']['mean']} FH and "
                               f"{fl['narrowbody']['fc_per_day']['mean']} FC per day, widebody about "
                               f"{fl['widebody']['fh_per_day']['mean']} FH and {fl['widebody']['fc_per_day']['mean']} FC per day")
    V["config.quote_noise"] = (f"truth × lognormal noise (σ_log {pc['quoted_mtbur_noise_sd_log']:.2f}) and "
                               f"{(pc['quoted_mtbur_optimism'] - 1) * 100:.0f}% optimistic on average; quoted shop TAT is "
                               f"{(1 - gen['quoted_tat_optimism']) * 100:.0f}% optimistic (σ_log {gen['quoted_tat_noise_sd_log']:.2f})")
    nffs = sorted({v["nff_share"] for v in gen["families"].values() if v.get("nff_share")})
    V["config.nff"] = (f"family share {nffs[0] * 100:.0f}–{nffs[-1] * 100:.0f}% (0 for brakes and wheels), "
                       f"{gen['nff_shop_days'][0]}–{gen['nff_shop_days'][1]} shop days at "
                       f"{gen['nff_cost_pct_of_repair'] * 100:.0f}% of the repair cost, never condemned")
    wt = gen["families"]["wheel_tyre"]
    V["config.wheel_shop"] = (f"rebuilt in the AUH wheel and tyre shop in {wt['repair_tat_days'][0]}–{wt['repair_tat_days'][1]} "
                              f"days at {wt['repair_cost_pct_of_unit'][0] * 100:.0f}–{wt['repair_cost_pct_of_unit'][1] * 100:.0f}% "
                              f"of unit cost")
    V["config.wear_notice"] = f"{gen['wear_planned_notice_days'][0]}–{gen['wear_planned_notice_days'][1]} days"
    V["config.deferred_share"] = fmt_pct(gen["deferred_to_hub_share"], 0)
    V["config.windows_disclaimer"] = cfg["deadline_classes"]["disclaimer"]
    a_ = cfg["aog_sourcing"]
    el, lb_, rb, lbuy = a_["exchange_loan"], a_["local_borrow"], a_["robbery"], a_["local_buy"]
    lbn, lbw = lb_["availability"]["narrowbody"], lb_["availability"]["widebody"]
    V["config.routes_table"] = "\n".join([
        "| Route | Where | Parts | Availability per attempt | Response | Cost |", "|---|---|---|---|---|---|",
        f"| Robbery from a same-type donor | AUH only | Rotables | {rb['availability']:.2f} | {rb['response_hours'][0]}–{rb['response_hours'][1]} h | "
        f"double fitting labour; flagged \"{rb['flag']}\" |",
        f"| Local borrow | outstations | Rotables | NB {min(lbn.values()):.2f}–{max(lbn.values()):.2f}, WB {min(lbw.values()):.2f}–{max(lbw.values()):.2f} by station | "
        f"{lb_['response_hours'][0]}–{lb_['response_hours'][1]} h | AED {lb_['fee_aed_fixed']:,} + {lb_['loan_fee_pct_of_list_per_day'] * 100:.1f}% of list per day |",
        f"| Exchange / loan | any station | Rotables | NB {el['availability']['narrowbody']:.2f}, WB {el['availability']['widebody']:.2f} | "
        f"NB {el['response_hours']['narrowbody'][0]}–{el['response_hours']['narrowbody'][1]} h, WB {el['response_hours']['widebody'][0]}–{el['response_hours']['widebody'][1]} h | "
        f"{el['fee_pct_of_list']['narrowbody'] * 100:.0f}% (NB) / {el['fee_pct_of_list']['widebody'] * 100:.0f}% (WB) of list + "
        f"{el['loan_fee_pct_of_list_per_day'] * 100:.1f}% per day |",
        f"| Local buy / borrow | every station | Consumables, expendables | {lbuy['availability']:.2f} | {lbuy['response_hours'][0]}–{lbuy['response_hours'][1]} h | "
        f"+{lbuy['premium_pct'] * 100:.0f}% |"])
    V["config.retry"] = (f"every {a_['retry_hours']['R']} h for rotables and {a_['retry_hours']['C']} h for consumables and "
                         f"expendables")
    V["config.aog_cost"] = (f"AED {eco['aog_penalty_aed_per_hour']['narrowbody']:,}/h (narrowbody) or "
                            f"{eco['aog_penalty_aed_per_hour']['widebody']:,}/h (widebody), plus a fixed AED "
                            f"{eco['aog_event_cost_aed']['narrowbody']:,} (NB) / {eco['aog_event_cost_aed']['widebody']:,} (WB) per merged event")
    V["config.aog_hour_definition"] = eco["aog_hour_definition"]
    p0c = cfg["policy_baseline_P0"]
    V["config.p0_protection"] = (f"{p0c['rotable_protection_level']['D0'] * 100:.0f}% for D0 and "
                                 f"{p0c['rotable_protection_level']['D3'] * 100:.0f}% for D3/D10")
    V["config.p0_line_min"] = str(p0c["rotable_outstation_min_quoted_removals_per_year"])
    V["config.p0_ce"] = (f"min = {p0c['consumable_min_weeks_of_avg_demand']['C']} weeks (C) / "
                         f"{p0c['consumable_min_weeks_of_avg_demand']['E']} weeks (E) of quoted demand, max = "
                         f"{p0c['consumable_max_multiple_of_min']:g} × min")

    # ---------------------------------------------------------------- tests (junit)
    n, bad, skip, suite = junit_counts()
    tot_n, tot_bad, tot_skip = sum(n.values()), sum(bad.values()), sum(skip.values())
    V["tests.summary"] = (f"{tot_n - tot_bad - tot_skip}/{tot_n} passing, {tot_bad} failing, {tot_skip} skipped (fast, "
                          f"slow and browser suites, `GNM_RELEASE=1`; `reports/junit.xml`, run at "
                          f"{suite['timestamp'][:16].replace('T', ' ')})")
    V.update(v21_keys(V, kpis=kpis, pol=pol, fo=fo, var=var, sp=sp, pm=pm, cal=cal))
    return V


# ----------------------------------------------------------------------------- v2.1 release wording
# Verbatim texts from docs/agent_notes/v21_brief.md. Numbers inside them are computed, never typed.
SCOPE_LINE = "across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part"
NAMES = {"P0": "Simple Rulebook (naive reference)", "P1": "Each Airport for Itself (simplified local comparator)",
         "P2": "Network Plan", "I125": "Network Plan + Extra Spares", "P2_GUARD": "Network Plan held to guardrails"}
# Locked config strings -> release labels (V21-0: frozen artefacts keep their strings, every surface relabels).
RELABEL = [("A320- and 787-family archetypes", "narrowbody and widebody archetypes"),
           ("A320-family and 787-family archetypes", "narrowbody and widebody archetypes"),
           ("A320-family archetype", "narrowbody archetype"), ("787-family archetype", "widebody archetype"),
           ("A320-family", "narrowbody"), ("787-family", "widebody")]
RELABELLED_DOCS = {"README.md", "METHODOLOGY.md", "MODEL_CARD.md", "LIMITATIONS.md", "VALIDATION_REPORT.md"}
POSTPLAN = ROOT / "outputs" / "postplan"


def relabel(text: str) -> str:
    for a, b in RELABEL:
        text = text.replace(a, b)
    return text


def display_name(pid: str) -> str:
    """'**Network Plan** `P2`' (frontier ids: 'Frontier point B150 `B150`')."""
    return f"**{NAMES.get(pid, f'Frontier point {pid}')}** `{pid}`"


def _first_json(*names: str):
    for n in names:
        p = POSTPLAN / n
        if p.exists():
            return jload(p)
    return None


def _donor_recount(kpis: dict) -> dict | None:
    """Post-plan donor recount exported by the DATA agent, if any (docs/agent_notes/v21_data.md)."""
    for src in (kpis.get("headline", {}).get("donor_recount"), kpis.get("donor_recount"),
                _first_json("donor_recount.json")):
        if src:
            return src
    return None


def v21_keys(V: dict[str, str], *, kpis, pol, fo, var, sp, pm, cal) -> dict[str, str]:  # noqa: PLR0915
    import yaml
    cfg = yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())
    W: dict[str, str] = {}
    W["v21.scope"] = SCOPE_LINE
    W["v21.scope_line"] = f"*{SCOPE_LINE}*"
    for pid in ("P0", "P1", "P2", "I125", "P2_GUARD"):
        W[f"v21.name.{pid}"] = display_name(pid)
        W[f"v21.plain.{pid}"] = NAMES[pid]
    W["v21.reading_note"] = (
        "How to read these numbers: simulated downtime of the aircraft waiting for the part, across 120 modelled part "
        "numbers. Downtime of aircraft that donated a part (cannibalisation) is shown separately, not included. The "
        "Simple Rulebook is a deliberately simplified starting point, not a model of a competent airline. Part costs, "
        "reliability and sourcing are assumed. These are not forecasts of achievable airline savings.")
    if V["scope.pn_count"] != "120":
        raise SystemExit("the scope line says 120 modelled part numbers; the part master disagrees")

    # ---- A4 capital table (never the net alone)
    core = kpis["headline"]["core"]
    rmx = core["remix"]
    cap_net = pol["paired"]["P2-P0"]["spare_capital_aed"]["mean"]
    ct = kpis.get("capital_table")
    if ct:  # DATA agent export (docs/agent_notes/v21_data.md) must agree with the policy tables
        assert (ct["bought_units"], ct["bought_aed"], ct["removed_units"], ct["removed_aed"]) == (
            rmx["buy_units"], rmx["buy_aed"], rmx["shed_units"], rmx["shed_aed"]), "capital_table vs remix"
        assert abs(ct["net_inventory_change_aed"] - cap_net) < 1, "capital_table net vs paired P2-P0 capital"
    buy_u, buy_a, shed_u, shed_a = rmx["buy_units"], rmx["buy_aed"], rmx["shed_units"], rmx["shed_aed"]
    W["v21.capital.bought"] = f"+{fmt_int(buy_u)} units ≈ {fmt_m(buy_a)} assumed value"
    W["v21.capital.removed"] = f"{MINUS}{fmt_int(shed_u)} units ≈ {fmt_m(shed_a)}"
    W["v21.capital.net"] = fmt_m(cap_net, signed=True)
    W["v21.capital.note"] = ("Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a "
                             "discount.")
    if ct:
        txt = {r["id"]: r["text"] for r in ct["rows"]}
        assert (txt["bought"], txt["removed"], txt["net_inventory"]) == (
            W["v21.capital.bought"], W["v21.capital.removed"], W["v21.capital.net"]), "capital_table text"
        assert ct["note"] == W["v21.capital.note"]
    W["v21.capital_table"] = "\n".join([
        f"| Capital change, {NAMES['P0']} `P0` → {NAMES['P2']} `P2` | Amount |", "|---|---|",
        f"| New rotables bought | {W['v21.capital.bought']} |",
        f"| Rotables removed | {W['v21.capital.removed']} |",
        f"| Net change in average simulated spare inventory | {W['v21.capital.net']} |",
        "", f"*{W['v21.capital.note']}* Units and values: target units × assumed unit cost from the policy tables; the "
            "net is the paired holdout change in time-averaged simulated spare inventory, so it differs slightly from "
            "bought minus removed."])

    # ---- A5 calibration (verbatim; the line-kit hours come from the variants file)
    v3 = next(v for k, v in var.items() if k.startswith("V3"))
    if v3["all_inside"]:
        raise SystemExit("A5 says the line-kit variant fell outside the band; the variants file disagrees")
    W["v21.calibration"] = (
        "The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the model, "
        f"not benchmarked against real airline KPIs. A line-kit variant (≈{fmt_int(v3['history']['aog_hours_per_year'])} h) "
        "was measured but not adopted because it fell outside that range. All results are conditional on this choice.")

    # ---- A6 stress worlds
    sv = cal["settings_used"]["generator.variants"]
    scales = sorted([sv["low_stress"]["true_mtbur_scale"], 1.0, sv["high_stress"]["true_mtbur_scale"]])
    W["v21.stress_worlds"] = "reliability scaled " + " / ".join(f"×{s:.2f}" for s in scales) + " — a narrow range"
    W["v21.ranges"] = ("Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, "
                       "suppliers or contracts.")

    # ---- A8 frontier insight (the 25% comes from the stored repair-TAT factor)
    tat_key = next(k for k in fo if k.startswith("repair_tat_x"))
    factor = float(tat_key.removeprefix("repair_tat_x").replace("_", "."))
    if fo[tat_key]["net_benefit_significant"]:
        raise SystemExit("A8 says faster repair removes the clear cost advantage; the export disagrees")
    W["v21.insight"] = (f"Faster repair can beat buying spares: with {(1 - factor) * 100:.0f}% shorter repair time, the "
                        "extra-investment option loses its clear cost advantage.")
    W["v21.levers"] = "faster repair · pool access · better reliability · more spares"

    # ---- A7 hero part
    for key, path in (("v21.stress_worlds", ("stress_worlds", "text")), ("v21.ranges", ("stress_worlds", "ranges_note")),
                      ("v21.insight", ("frontier_insight", "text")), ("v21.levers", ("frontier_insight", "levers_text")),
                      ("v21.reading_note", ("reading_note",)), ("v21.scope", ("scope_line",))):
        node = kpis
        for k_ in path:
            node = node.get(k_) if isinstance(node, dict) else None
        if node is not None and node != W[key]:
            raise SystemExit(f"{key} differs from the site export kpis.json {'/'.join(path)}")
    ps1_mult = cfg["generator"]["planted"]["PS1"]["quoted_multiple"]
    W["v21.hero_part"] = (f"Removing {ps1_mult:g}× faster than quoted → escalate to reliability engineering and "
                          "warranty review "
                          "first. Extra spares are interim cover, compared against faster repair or pool access.")

    # ---- A11 the AOG clock
    W["v21.aog_clock"] = (
        "The downtime clock starts when the part is removed (for no-go items; for deferrable items, when the "
        "rectification window runs out), not at the next scheduled departure, and overnight and other non-flying hours "
        "count in full. Fitting and release-to-service time is included. A departure-based count would be lower for "
        "every plan.")

    # ---- donor recount: post-plan if exported, otherwise the historical scale only (never mixed with holdout)
    dr = _donor_recount(kpis)
    hp = (dr or {}).get("historical_p0")
    if hp:  # the export must agree with the history recomputed here
        assert fmt_int(hp["gross_donor_hours_per_year"]) == V["limits.donor_h_per_yr"]
        assert fmt_int(hp["counted_material_aog_hours_per_year"]) == V["limits.p0_history_aog_per_yr"]
    hist = (f"For scale only, in the historical record of the {NAMES['P0']} `P0` (history weeks 0–103, one simulated "
            f"history, not the test runs), donor aircraft were held about {V['limits.donor_h_per_yr']} h a year, beside "
            f"{V['limits.p0_history_aog_per_yr']} h a year of counted waiting-for-part downtime in that same history. "
            f"Gross donor hours are an upper bound: a donor may already be in maintenance or not scheduled to fly.")
    ho = (dr or {}).get("holdout", {})
    dh = ho.get("donor_hours")
    if isinstance(dh, dict) and dh:  # per-plan donor hours exported (post-plan, exploratory)
        rows = ["| Plan | Donor aircraft hours / yr [likely range] (post-plan, exploratory) |", "|---|---|"]
        for pid in ("P0", "P1", "P2", "I125"):
            r = dh.get(pid, {})
            rows.append(f"| {NAMES[pid]} `{pid}` | "
                        + (f"{fmt_h(r['mean'])} {ci_int(*r['ci'])}" if "mean" in r else str(r.get("status", "—"))) + " |")
        W["v21.donor_body"] = ("Hours that donor aircraft (aircraft that gave up a part to another) spent waiting for a "
                               "replacement, recounted from the frozen test-run logs and kept separate from the "
                               "headline:\n\n" + "\n".join(rows) + "\n\n" + hist)
        W["v21.donor"] = "**Donor downtime, recounted (post-plan, exploratory).** " + W["v21.donor_body"]
    else:
        rob = ho.get("robberies_per_year", {})
        rtxt = [f"{NAMES[pid]} `{pid}` {fmt_num(rob[pid]['mean'], 1)} {ci_num(*rob[pid]['ci'], 1)}"
                for pid in ("P0", "P1", "P2") if "mean" in rob.get(pid, {})]
        rob_s = (f" What the logs do allow (post-plan, exploratory): parts borrowed from another of our aircraft per "
                 f"year in the test runs, {'; '.join(rtxt)}; for the {NAMES['I125']} `I125` this is not "
                 f"reconstructible either." if rtxt else "")
        W["v21.donor_body"] = ("Hours that donor aircraft (aircraft that gave up a part to another) spend waiting for a "
                               "replacement are not reconstructible from current logs for the frozen test runs, so no "
                               "per-plan figure is given." + rob_s + " " + hist)
        W["v21.donor"] = "**Donor downtime.** " + W["v21.donor_body"]

    # ---- A9 outstation brakes and wheels in the frozen plans
    cands = {c["id"]: c["policy"]["stock_params"] for c in jload(OUT / "frontier" / "candidates.json")["candidates"]}
    brakes = set(pm[pm.removal_mode == "wear_planned"].index)
    wheels = set(pm[pm.description.str.contains("wheel and tyre", case=False)].index)

    def out_units(pid, pns):
        return sum(int(r[4]) for r in cands[pid] if r[0] in pns and r[1] != HUB and r[4] > 0)

    def out_lines(pid, pns):
        return [f"{r[0]} at {r[1]}" for r in cands[pid] if r[0] in pns and r[1] != HUB and r[4] > 0]
    for pid in ("P0", "P2", "I125"):
        W[f"v21.out_brakes.{pid}"] = fmt_int(out_units(pid, brakes))
        W[f"v21.out_wheels.{pid}"] = fmt_int(out_units(pid, wheels))
    assert W["v21.out_brakes.P0"] == V["limits.p0_out_brakes"]
    W["v21.brakes_invalid"] = (
        f"Outstation brake allocations in the frozen plans are flagged as an **invalid recommendation — brakes are not "
        f"changed outside the hub in this model**: {W['v21.out_brakes.P2']} in the {NAMES['P2']} `P2` "
        f"({', '.join(out_lines('P2', brakes))}), {W['v21.out_brakes.I125']} in the {NAMES['I125']} `I125` and "
        f"{W['v21.out_brakes.P0']} in the {NAMES['P0']} `P0`. They stay in the frozen results so the numbers are "
        f"unchanged, but no planner should act on them.")
    W["v21.wheels_note"] = (
        f"Wheel-and-tyre assemblies are modelled as rare, unscheduled no-go removals (AV2-04), so the "
        f"frozen plans hold {W['v21.out_wheels.P0']} wheel assemblies at outstations under the {NAMES['P0']} `P0` "
        f"(none on the nose wheel or the widebody), {W['v21.out_wheels.P2']} under the {NAMES['P2']} `P2` and "
        f"{W['v21.out_wheels.I125']} under the {NAMES['I125']} `I125`. A real operator holds wheels at every station "
        f"and changes most of them on planned tread wear, so these counts follow from the modelling assumption and are "
        f"not a wheel-sizing recommendation. Most of the gap between the {NAMES['P0']} and the {NAMES['P2']} at "
        f"outstations comes from no-go actuators and wheels.")

    # ---- headline sentence with display names and the scope line (no percentage claim)
    red = core["aog_reduction"]
    hk = {x["policy_id"]: x["kpi"] for x in pol["policies"]}
    if not (hk["P0"]["aog_hours"]["mean"] > hk["P1"]["aog_hours"]["mean"] > hk["P2"]["aog_hours"]["mean"]
            > hk["I125"]["aog_hours"]["mean"] and hk["I125"]["spare_capital_aed"]["mean"] > hk["P2"]["spare_capital_aed"]["mean"]):
        raise SystemExit("the README headline states the plan ordering P0 > P1 > P2 > I125; the data disagrees")
    W["v21.headline"] = (
        f"Hours aircraft spent waiting for a part, per year, in the simulation: about {V['policies.P0.aog_hours']} under "
        f"the {NAMES['P0']} `P0` and {V['policies.P2.aog_hours']} under the {NAMES['P2']} `P2`. The {NAMES['P1']} `P1` "
        f"sits between them at {V['policies.P1.aog_hours']}, and the {NAMES['I125']} `I125` goes lower, to "
        f"{V['policies.I125.aog_hours']}, for extra capital.")
    W["v21.headline_paired"] = (
        f"**{NAMES['P2']} `P2` vs {NAMES['P0']} `P0`: {fmt_h(-red['mean'], signed=True)} a year "
        f"{ci_int(-red['ci'][1], -red['ci'][0])}** of material AOG (paired over the {V['seeds.n']} holdout seeds "
        f"{V['seeds.holdout']}, 95% t-interval), from {V['policies.P0.aog_hours']} to {V['policies.P2.aog_hours']}. "
        f"The {NAMES['P2']} holds {core['outstation_rotables']['P2']} rotables at the six outstations instead of "
        f"{core['outstation_rotables']['P0']}, pools the rest at the hub. The lead over the {NAMES['P0']} holds in all three stress worlds "
        f"and across the ×0.5–×2 range of the hourly AOG cost.")
    n_ac = cfg["fleet"]["narrowbody"]["count"] + cfg["fleet"]["widebody"]["count"]
    W["v21.stat_strip"] = (f"{n_ac} aircraft · {V['scope.pn_count']} part numbers · "
                           f"{len(cfg['network']['stations'])} stations · {V['seeds.n']} fresh test runs")
    if V["seeds.n"] != "20":
        raise SystemExit("the wording says 20 fresh test runs; the holdout seed count differs")
    W["v21.kpi_table"] = "\n".join([
        f"| Plan | Downtime waiting for parts, h / yr [likely range] | Average spare inventory |", "|---|---|---|",
        *(f"| {NAMES[p]} `{p}` | {V[f'policies.{p}.aog_hours']} {V[f'policies.{p}.aog_hours_ci']} | "
          f"{V[f'policies.{p}.spare_capital_aed']} |" for p in ("P0", "P1", "P2", "I125")),
        "", f"*{SCOPE_LINE}*"])
    W["v21.fill_abs"] = f"{abs(pol['paired']['P2-P0']['immediate_fill_rate']['mean']) * 100:.2f}"
    return W


# ----------------------------------------------------------------------------- validation report
def validation_values(V: dict[str, str]) -> dict[str, str]:
    n, bad, skip, suite = junit_counts()
    areas = {
        "Data contracts, leakage, simulator, calibration lock": ["test_contracts", "test_leakage", "test_leakage_runtime",
                                                                 "test_sim_engine", "test_sim_generator",
                                                                 "test_calibration", "test_calibration_lock"],
        "Forecasting (incl. Monash benchmark)": [m for m in n if m.startswith("test_forecasting")],
        "Inventory policy and Palm/EBO maths": ["test_analytic", "test_floatcalc_mirror"] +
                                                [m for m in n if m.startswith("test_policy")],
        "Optimiser / Readiness Frontier (guardrails, levers)": [m for m in n if m.startswith("test_optim")],
        "AOG Response Lab and Planner Action Centre": [m for m in n if m.startswith("test_aog")],
        "Freeze and holdout discipline": ["test_freeze"],
        "Site data export, reconciliation, rendered docs": ["test_reconciliation", "test_site_data", "test_docs_rendered"],
        "SQL, workbook, notebooks": ["test_sql", "test_workbook", "test_notebooks"],
        "Web app screens (browser)": [m for m in n if m.startswith("test_site_") and m != "test_site_data"],
    }
    rows = ["| Area | Test modules | Tests | Failed | Skipped |", "|---|---|---|---|---|"]
    seen = set()
    for area, mods in areas.items():
        mods = [m for m in mods if m in n]
        seen |= set(mods)
        rows.append(f"| {area} | {', '.join('`' + m + '`' for m in mods)} | {sum(n[m] for m in mods)} | "
                    f"{sum(bad[m] for m in mods)} | {sum(skip[m] for m in mods)} |")
    rest = [m for m in n if m not in seen]
    if rest:
        rows.append(f"| Other | {', '.join('`' + m + '`' for m in rest)} | {sum(n[m] for m in rest)} | "
                    f"{sum(bad[m] for m in rest)} | {sum(skip[m] for m in rest)} |")
    rows.append(f"| **Total** | {len(n)} modules | **{sum(n.values())}** | **{sum(bad.values())}** | **{sum(skip.values())}** |")
    W = dict(V)
    W["val.tests_table"] = "\n".join(rows)
    W["val.tests_suite"] = (f"{suite['tests']} tests, {suite['failures']} failures, {suite['errors']} errors, "
                            f"{suite['skipped']} skipped, {float(suite['time']):.0f} s, run at {suite['timestamp']}")
    failed = [f"`{tc.get('classname').split('.')[-1]}::{tc.get('name')}`" for tc in junit_root().iter("testcase")
              if any(ch.tag in ("failure", "error") for ch in tc)]
    W["val.failed_list"] = ("No test failed." if not failed else
                            "Failing in this run: " + ", ".join(failed) + ".")

    # git chain
    log = git_log()
    i_arch = find_commit(log, "Archive v1")[0]
    keys_v1 = ("Phase 2: simulator", "FREEZE:", "HOLDOUT:", "Holdout runner")
    keys_v2 = ("Archive v1", "v2 simulator", "v2 P0 gap diagnosis", "v2 realism corrections", "v2 calibration variants",
               "v2 CALIBRATION LOCK", "v2: forecasting champions", "v2: AOG Response Lab", "v2 bug fixes before freeze",
               "v2: Readiness Frontier", "v2 FREEZE", "v2 HOLDOUT", "Post-plan robustness check", "v2 site export",
               "v2 regeneration brief")
    v1c = [f"- `{h}` {s}" for i, (h, s) in enumerate(log) if i < i_arch and s.startswith(keys_v1)]
    v2c = [f"- `{h}` {s}" for i, (h, s) in enumerate(log) if i >= i_arch and s.startswith(keys_v2)]
    W["val.git_chain_v1"] = "\n".join(v1c)
    W["val.git_chain_v2"] = "\n".join(v2c)
    hl = jload(OUT / "freeze" / "holdout_log.json")
    hrows = ["| # | Run | World | Logged at (UTC) | After the v2 freeze | Forced |", "|---|---|---|---|---|---|"]
    method = jload(DATA / "method.json")
    frozen = method["freeze"]["frozen_at"]
    for i, r in enumerate(hl, 1):
        world = "v2" if r["run"].startswith("v2_") else "v1 (archived)"
        after = "yes" if r["run"].startswith("v2_") and r["at"] > frozen else ("—" if world != "v2" else "NO")
        hrows.append(f"| {i} | `{r['run']}` | {world} | {r['at'][:19].replace('T', ' ')} | {after} | "
                     f"{'yes' if r['forced'] else 'no'} |")
    W["val.holdout_log_table"] = "\n".join(hrows)

    # selection vs holdout
    kpis = jload(DATA / "kpis.json")
    K = {k["id"]: k for k in kpis["kpis"]}
    fmtk = {"immediate_fill_rate": fmt_pct, "aog_hours": fmt_h, "spare_capital_aed": fmt_aed,
            "total_annual_cost_aed": fmt_aed, "expedite_cost_aed": fmt_aed, "aog_events": lambda v: fmt_num(v, 1)}
    fmtci = {"immediate_fill_rate": ci_pct, "aog_hours": ci_int, "spare_capital_aed": ci_aed_m,
             "total_annual_cost_aed": ci_aed_m, "expedite_cost_aed": ci_aed_m, "aog_events": lambda a, b: ci_num(a, b, 1)}
    cons = [f"| KPI | Plan | Selection (seeds {V['seeds.selection']}) | Holdout (seeds {V['seeds.holdout']}) [95% CI] | "
            f"Selection inside holdout CI |", "|---|---|---|---|---|"]
    for c in kpis["consistency"]:
        kid = c["id"]
        bci = K[kid]["baseline_ci"]
        cons.append(f"| {K[kid]['label']} | P0 | {fmtk[kid](c['selection_baseline'])} | {fmtk[kid](c['holdout_baseline'])} "
                    f"{fmtci[kid](*bci)} | {'yes' if bci[0] <= c['selection_baseline'] <= bci[1] else 'no'} |")
        cons.append(f"| | P2 | {fmtk[kid](c['selection_recommended'])} | {fmtk[kid](c['holdout_recommended'])} "
                    f"{fmtci[kid](*c['holdout_ci'])} | {'yes' if c['selection_inside_holdout_ci'] else 'no'} |")
    fr = jload(DATA / "frontier.json")
    pts = {p["id"]: p for p in fr["points"]}
    spts = {p["id"]: p for p in fr["selection_points"]}
    pol = jload(DATA / "policies.json")
    selp = {p["policy_id"]: p for p in pol["selection"]["policies"]}
    h1 = next(p for p in pol["policies"] if p["policy_id"] == "P1")["kpi"]["aog_hours"]
    s1 = selp["P1"]["kpi"]["aog_hours"]["mean"]
    cons.append(f"| Material AOG hours / year | P1 | {fmt_h(s1)} | {fmt_h(h1['mean'])} {ci_int(h1['ci_lo'], h1['ci_hi'])} | "
                f"{'yes' if h1['ci_lo'] <= s1 <= h1['ci_hi'] else 'no'} |")
    for pid in ("I125", "I110", "B150"):
        s, h = spts[pid], pts[pid]
        cons.append(f"| Material AOG hours / year | {pid} (frontier) | {fmt_h(s['aog_hours'])} | {fmt_h(h['aog_hours'])} "
                    f"{ci_int(*h['aog_ci'])} | {'yes' if h['aog_ci'][0] <= s['aog_hours'] <= h['aog_ci'][1] else 'no'} |")
    d_s, d_h = spts["I125"]["d_aog_vs_P2"], pts["I125"]
    cons.append(f"| I125 − P2 material AOG (paired) | I125 | {fmt_h(d_s, signed=True)} | {fmt_h(d_h['d_aog_vs_P2'], signed=True)} "
                f"{ci_int(*d_h['d_aog_vs_P2_ci'])} | {'yes' if d_h['d_aog_vs_P2_ci'][0] <= d_s <= d_h['d_aog_vs_P2_ci'][1] else 'no'} |")
    W["val.consistency_table"] = "\n".join(cons)

    chk = pd.read_csv(OUT / "holdout" / "forecast_champion_check.csv")
    cc = ["| Demand class | Part class | Parts | Frozen champion | Holdout MASE | Rank | Best in hindsight |",
          "|---|---|---|---|---|---|---|"]
    for r in chk.itertuples():
        cc.append(f"| {r.demand_class} | {r.part_class} | {r.n_parts} | {METHOD_LABEL[r.champion]} | {r.champion_mase:.3f} | "
                  f"{r.champion_rank} of {r.n_methods} | {METHOD_LABEL[r.best_in_hindsight]} ({r.best_mase:.3f}) |")
    W["val.champion_check_table"] = "\n".join(cc)
    tr = jload(OUT / "holdout" / "truth_recovery.json")
    tt = ["| Parameter | Parts | Median abs log error, vendor quote | Median abs log error, history estimate | Estimate closer |",
          "|---|---|---|---|---|"]
    for key, lab in (("all", "MTBUR, rotables + expendables"), ("R", "MTBUR, rotables"), ("E", "MTBUR, expendables")):
        r = tr["reliability"][key]
        tt.append(f"| {lab} | {r['n_parts']} | {r['quoted_mdale']:.3f} | {r['estimated_mdale']:.3f} | "
                  f"{fmt_pct(r['share_estimate_closer'], 0)} |")
    lt = tr["lead_time"]
    tt.append(f"| Purchase lead time, all parts | {lt['n_parts']} | {lt['quoted_mdale']:.3f} | {lt['estimated_mdale']:.3f} | — |")
    W["val.truth_table"] = "\n".join(tt)
    chg = lt["changed_parts"][0]
    W["val.truth_ps4"] = (f"PS4 {chg['pn']}: true lead time {chg['true']:.1f} d after the planted change, planner estimate "
                          f"{chg['est']:.1f} d, quoted {chg['quoted']:.1f} d")
    pvs = pd.read_csv(OUT / "policies" / "palm_vs_sim.csv")
    pvs = pvs[pvs.sim_requests > 0]
    pr = ["| Group | Rows with demand | Simulated requests | Palm fill (mean) | Simulated fill (mean) | Mean abs gap | ΣEBO / Σ simulated backorders |",
          "|---|---|---|---|---|---|---|"]
    for lab, g in ((HUB, pvs[pvs.station == HUB]), ("Outstations", pvs[pvs.station != HUB])):
        pr.append(f"| {lab} | {len(g)} | {int(g.sim_requests.sum()):,} | {g.palm_availability.mean():.3f} | "
                  f"{g.sim_immediate_fill.mean():.3f} | {(g.sim_immediate_fill - g.palm_availability).abs().mean():.3f} | "
                  f"{g.palm_ebo.sum():.2f} / {g.sim_avg_backorders.sum():.2f} |")
    W["val.palm_table"] = "\n".join(pr)

    post = jload(OUT / "holdout" / "postplan_i125_stress.json")
    pp = ["| World | Plan | Material AOG h/yr [95% CI] | Δ vs central-built P2 [95% CI] | Δ total annual cost vs P2 | Δ capital vs P2 |",
          "|---|---|---|---|---|---|"]
    for w, rows_ in post["worlds"].items():
        for r in sorted(rows_, key=lambda x: ("P0", "P2", "I125").index(x["id"])):
            pp.append(f"| {WORLD_LABEL[w]} | {r['id']} | {fmt_h(r['aog_hours_mean'])} {ci_int(r['aog_hours_lo'], r['aog_hours_hi'])} | "
                      + ("— | — | — |" if r["id"] == "P2" else
                         f"{fmt_h(r['d_aog_hours_vs_base_mean'], signed=True)} {ci_int(r['d_aog_hours_vs_base_lo'], r['d_aog_hours_vs_base_hi'])} | "
                         f"{fmt_aed_ci(r['d_total_cost_vs_base_mean'], r['d_total_cost_vs_base_lo'], r['d_total_cost_vs_base_hi'], signed=True)} | "
                         f"{fmt_m(r['d_capital_vs_base_mean'], signed=True)} |"))
    W["val.postplan_table"] = "\n".join(pp)

    # v1-era reviews
    rev = []
    for p in sorted((ROOT / "reports").glob("review_*.md")):
        txt = p.read_text()
        title = txt.splitlines()[0].lstrip("# ").strip()
        sev = Counter(m.group(1).strip("* ").lower() for m in
                      re.finditer(r"^\| ?(?:AV|C)-\d+ \| ?\**([A-Za-z]+)\**", txt, re.M))
        score = re.search(r"Overall average: ([0-9.]+) ?/ ?5", txt)
        if sev:
            what = ", ".join(f"{sev[k]} {k}" for k in ("critical", "major", "minor") if sev.get(k))
            if "critical" not in sev:
                what = "0 critical, " + what
        elif score:
            what = f"overall {score.group(1)} / 5"
        else:
            what = "see file"
        rev.append(f"- [`reports/{p.name}`]({p.name}): {title}; {what}.")
    W["val.v1_reviews"] = "\n".join(rev)
    return W


# ----------------------------------------------------------------------------- render
def render_text(text: str, values: dict[str, str], name: str) -> str:
    missing = sorted({k for k in PLACEHOLDER.findall(text) if k not in values})
    if missing:
        raise KeyError(f"{name}: no value for {missing}")
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def keep_v2_reviews(rendered: str, existing: str | None) -> str:
    """Carry over whatever the lead wrote under the v2 reviews heading (if it is no longer the placeholder)."""
    if not existing or V2_REVIEW_HEADING not in existing or V2_REVIEW_HEADING not in rendered:
        return rendered
    old = existing.split(V2_REVIEW_HEADING, 1)[1]
    if "*To be completed by the lead" in old:
        return rendered
    return rendered.split(V2_REVIEW_HEADING, 1)[0] + V2_REVIEW_HEADING + old


def study_keys(V: dict[str, str]) -> dict[str, str]:
    """Merge the optional study-guide key module into a copy of V."""
    if not STUDY_KEYS.exists():
        return V
    spec = importlib.util.spec_from_file_location("render_keys_study", STUDY_KEYS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    extra = mod.keys()
    clash = sorted(k for k, v in extra.items() if k in V and V[k] != v)
    if clash:
        raise KeyError(f"render_keys_study.keys() disagrees with render_docs on {clash}")
    return {**V, **extra}


def render_all(only: list[str] | None = None) -> dict[Path, str]:
    V = compute()
    out = {}
    want = (lambda name: True) if not only else (lambda name: name in only)
    for name in DOCS:
        if not want(name):
            continue
        tmpl = (TEMPLATES / f"{name}.tmpl").read_text()
        values = study_keys(V) if name == "STUDY_GUIDE.md" else V
        txt = render_text(tmpl, values, name)
        out[ROOT / name] = relabel(txt) if name in RELABELLED_DOCS else txt
    if want("reports/VALIDATION_REPORT.md") or want(VALIDATION[0]):
        W = validation_values(V)
        tmpl = (TEMPLATES / f"{VALIDATION[0]}.tmpl").read_text()
        existing = VALIDATION[1].read_text() if VALIDATION[1].exists() else None
        out[VALIDATION[1]] = keep_v2_reviews(relabel(render_text(tmpl, W, VALIDATION[0])), existing)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if any rendered file differs from disk")
    ap.add_argument("--only", nargs="+", help="render only these docs (README.md, ..., reports/VALIDATION_REPORT.md)")
    args = ap.parse_args()
    try:
        out = render_all(args.only)
    except KeyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.check:
        stale = [p for p, txt in out.items() if not p.exists() or p.read_text() != txt]
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)}")
        return 1 if stale else 0
    for p, txt in out.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
        print(f"rendered {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
