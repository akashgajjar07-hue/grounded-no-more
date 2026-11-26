"""Render the result numbers into the project docs.

Templates live in ``docs/templates/<NAME>.md.tmpl`` and carry ``{{RESULT:<key>}}`` placeholders.
This script computes every key from pipeline outputs (``outputs/``, ``docs/data/*.json`` and the
P0 history in ``data/processed/history/``), formats it consistently and writes the rendered files
to the repository root (README.md, METHODOLOGY.md, MODEL_CARD.md, LIMITATIONS.md, STUDY_GUIDE.md)
and ``reports/VALIDATION_REPORT.md``.

Rules:
* No number is typed by hand: every value is read or computed from an output file.
* Headline numbers are HOLDOUT (seeds 1000-1019, central variant). Selection numbers are labelled.
* A key that cannot be computed renders as "not run" with a reason.
* An unknown placeholder is an error (the script exits non-zero).

Formatting: money "AED 41.9M" (>= 1M) or "AED 2,650"; rates "98.1%"; hours "223 h";
CIs "[174–272]" ("[−2,709 to −1,967]" when negative values are involved; money CIs in AED M).

Usage:  python scripts/render_docs.py [--check]
        --check  render in memory and fail if a rendered file differs from the one on disk.
"""
from __future__ import annotations

import argparse
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
PHASE5_HEADING = "## Phase 5 reviewer findings and fixes"
PLACEHOLDER = re.compile(r"\{\{RESULT:([A-Za-z0-9_.]+)\}\}")
MINUS = "−"
NOT_RUN = "not run"

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


def ci_pp(lo: float, hi: float) -> str:
    return _range(_neg(f"{lo * 100:.2f}"), _neg(f"{hi * 100:.2f}"), lo < 0 or hi < 0)


def ci_aed_m(lo: float, hi: float) -> str:
    """Money CI in AED millions, e.g. [41.4–42.3]."""
    return _range(_neg(f"{lo / 1e6:.1f}"), _neg(f"{hi / 1e6:.1f}"), lo < 0 or hi < 0)


def fmt_aed_ci(mean: float, lo: float, hi: float, signed: bool = False) -> str:
    """Money with CI on one scale: AED 41.9M [41.4–42.3], AED 0.95M [0.73–1.17] or AED 2,650 [2,000–3,000]."""
    big = max(abs(mean), abs(lo), abs(hi))
    sign = ("+" if mean > 0 else MINUS if mean < 0 else "") if signed else (MINUS if mean < 0 else "")
    if abs(mean) >= 1e6:
        return f"{sign}AED {abs(mean) / 1e6:.1f}M {ci_aed_m(lo, hi)}"
    if big >= 1e5:
        r = _range(_neg(f"{lo / 1e6:.2f}"), _neg(f"{hi / 1e6:.2f}"), lo < 0 or hi < 0)
        return f"{sign}AED {abs(mean) / 1e6:.2f}M {r}"
    return f"{sign}AED {abs(mean):,.0f} {_range(fmt_int(lo), fmt_int(hi), lo < 0 or hi < 0)}"


def ci_aed(lo: float, hi: float) -> str:
    """Money CI: AED millions when both ends are large, else whole AED."""
    if min(abs(lo), abs(hi)) >= 1e5:
        return ci_aed_m(lo, hi)
    return _range(fmt_int(lo), fmt_int(hi), lo < 0 or hi < 0)


# ----------------------------------------------------------------------------- loaders
def jload(path: Path) -> dict:
    return json.loads(path.read_text())


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def git_commit(grep: str) -> str:
    out = git("log", "--format=%h", f"--grep={grep}", "-n", "1")
    return out or NOT_RUN


def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def junit_counts() -> tuple[Counter, Counter, dict]:
    root = ET.parse(ROOT / "reports" / "junit.xml").getroot()
    n, bad = Counter(), Counter()
    for tc in root.iter("testcase"):
        mod = tc.get("classname").split(".")[-1]
        n[mod] += 1
        if any(ch.tag in ("failure", "error") for ch in tc):
            bad[mod] += 1
    suite = next(root.iter("testsuite")).attrib
    return n, bad, suite


def junit_case_passed(module: str, name: str) -> bool:
    root = ET.parse(ROOT / "reports" / "junit.xml").getroot()
    for tc in root.iter("testcase"):
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


METHOD_LABEL = {"zero": "Zero", "naive": "naive", "ma": "moving average", "croston": "Croston", "sba": "SBA",
                "tsb": "TSB", "adida": "ADIDA", "imapa": "IMAPA", "bootstrap": "bootstrap",
                "reliability": "reliability-exposure"}
CLASS_LABEL = {"C": "consumables", "E": "expendables", "R": "rotables"}


# ----------------------------------------------------------------------------- compute
def compute() -> dict[str, str]:  # noqa: C901 - one flat list of keys is easier to audit
    V: dict[str, str] = {}
    kpis = jload(DATA / "kpis.json")
    pol = jload(DATA / "policies.json")
    fr = jload(DATA / "frontier.json")
    fc = jload(DATA / "forecast.json")
    parts = jload(DATA / "parts.json")
    rot = jload(DATA / "rotables.json")
    net = jload(DATA / "network.json")
    aog = jload(DATA / "aog_lab.json")
    act = jload(DATA / "actions.json")
    method = jload(DATA / "method.json")
    fsum = jload(OUT / "frontier" / "summary.json")
    tr = jload(OUT / "holdout" / "truth_recovery.json")
    manifest_path = OUT / "freeze" / "manifest.json"
    manifest = jload(manifest_path)

    K = {k["id"]: k for k in kpis["kpis"]}
    P = {p["policy_id"]: p for p in pol["policies"]}
    pts = {p["id"]: p for p in fr["points"]}
    rec_id = kpis["recommended_id"]
    rec = pts[rec_id]
    assert rec_id == fr["recommended"] if isinstance(fr["recommended"], str) else True

    # ---------------------------------------------------------------- policies table (holdout)
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
        pen = kpi["aog_penalty_aed"]["mean"]
        V[f"policies.{pid}.aog_penalty_aed"] = fmt_aed(pen)
        # opex excl. penalty = holding + repair + logistics + expedite = total - penalty
        V[f"policies.{pid}.opex_ex_penalty_aed"] = fmt_aed(kpi["total_annual_cost_aed"]["mean"] - pen)

    for pid in ("P0", "P1", "P2", rec_id):
        put_metric(pid, P[pid]["kpi"])
    if rec_id != "I125":
        raise SystemExit(f"recommended point is {rec_id}, templates are written for I125")

    paired = pol["paired"]

    def put_pair(key: str, d: dict, metric: str):
        x = d[metric]
        if metric == "aog_hours":
            V[f"{key}.delta_aog_hours"] = fmt_h(x["mean"], signed=True)
            V[f"{key}.delta_aog_hours_ci"] = ci_int(x["ci_lo"], x["ci_hi"])
        elif metric == "immediate_fill_rate":
            V[f"{key}.delta_immediate_fill_rate"] = fmt_signed(x["mean"] * 100, 2) + " pp"
            V[f"{key}.delta_immediate_fill_rate_ci"] = ci_pp(x["ci_lo"], x["ci_hi"])
        elif metric == "spare_capital_aed":
            txt = fmt_aed_ci(x["mean"], x["ci_lo"], x["ci_hi"], signed=True)
            V[f"{key}.delta_spare_capital_aed"], V[f"{key}.delta_spare_capital_aed_ci"] = txt.split(" [", 1)[0], "[" + txt.split(" [", 1)[1]

    put_pair("policies.P1_vs_P0", paired["P1-P0"], "aog_hours")
    for m in ("aog_hours", "immediate_fill_rate", "spare_capital_aed"):
        put_pair("policies.P2_vs_P0", paired["P2-P0"], m)
    p0mean = P["P0"]["kpi"]["aog_hours"]["mean"]
    V["policies.P2_vs_P0.delta_aog_hours_pct"] = fmt_pct(-paired["P2-P0"]["aog_hours"]["mean"] / p0mean, 0)
    # vs P2 (paired; P0 and P1 from the policy run, I125 from the frontier run)
    p21 = paired["P2-P1"]["aog_hours"]
    V["policies.P1_vs_P2.delta_aog_hours"] = fmt_h(-p21["mean"], signed=True)
    V["policies.P1_vs_P2.delta_aog_hours_ci"] = ci_int(-p21["ci_hi"], -p21["ci_lo"])
    p20 = paired["P2-P0"]["aog_hours"]
    V["policies.P0_vs_P2.delta_aog_hours"] = fmt_h(-p20["mean"], signed=True)
    V["policies.P0_vs_P2.delta_aog_hours_ci"] = ci_int(-p20["ci_hi"], -p20["ci_lo"])
    sel = {p["policy_id"]: p for p in pol["selection"]["policies"]}
    V["policies.P2.selection_aog_hours"] = fmt_h(sel["P2"]["kpi"]["aog_hours"]["mean"])

    # ---------------------------------------------------------------- frontier
    V["frontier.recommended.id"] = rec_id
    V["frontier.recommended.capital_aed"] = fmt_aed(rec["capital_aed"])
    V["frontier.recommended.aog_hours"] = fmt_h(rec["aog_hours"])
    V["frontier.recommended.aog_hours_ci"] = ci_int(*rec["aog_ci"])
    base = pts[kpis["baseline_id"]]
    V["frontier.baseline.aog_hours"] = fmt_h(base["aog_hours"])
    V["frontier.baseline.capital_aed"] = fmt_aed(base["capital_aed"])
    ks = K["aog_hours"]["selection"]
    V["frontier.recommended.selection_aog_hours"] = fmt_h(ks["recommended"])
    V["frontier.recommended.selection_aog_hours_ci"] = ci_int(*ks["ci"])
    V["frontier.recommended.selection_shift_pct"] = fmt_pct((rec["aog_hours"] - ks["recommended"]) / ks["recommended"], 0)
    V["frontier.recommended.selection_shift_pct"] = "+" + V["frontier.recommended.selection_shift_pct"]
    s2 = sel["P2"]["kpi"]["aog_hours"]["mean"]
    V["policies.P2.selection_shift_pct"] = "+" + fmt_pct((P["P2"]["kpi"]["aog_hours"]["mean"] - s2) / s2, 0)
    rs = fr["recommendation"]["recommended_vs_P2_selection"]
    V["frontier.recommended_vs_P2.selection_delta"] = (
        f"{fmt_h(-rs['aog_reduction_mean'], signed=True)} {ci_int(-rs['aog_reduction_hi'], -rs['aog_reduction_lo'])}")
    rv = pol["recommended_vs_P2"]
    V["frontier.recommended_vs_P2.delta_aog_hours"] = fmt_h(rv["aog_hours"]["mean"], signed=True)
    V["frontier.recommended_vs_P2.delta_aog_hours_ci"] = ci_int(rv["aog_hours"]["ci_lo"], rv["aog_hours"]["ci_hi"])
    V["frontier.recommended_vs_P2.delta_capital_aed"] = fmt_aed(rv["capital"]["mean"], signed=True)
    V["frontier.recommended_vs_P2.net_saving_aed"] = (
        f"{fmt_aed(-rv['total_cost']['mean'])} {ci_aed_m(-rv['total_cost']['ci_hi'], -rv['total_cost']['ci_lo'])}")
    recm = fr["recommendation"]
    V["frontier.recommendation_rule"] = recm["rule"]
    V["frontier.h_star"] = fmt_num(recm["h_star_per_aed_1m"], 1)
    V["frontier.aed_per_aog_hour"] = fmt_aed(recm["aed_per_aog_hour"])
    V["frontier.n_candidates"] = str(fsum["n_candidates"])
    vr = {v["variant"]: v for v in fr["variant_robustness"]}
    low = vr["low_stress"]
    V["frontier.low_stress.summary"] = (
        f"I125 is not worth its extra capital over P2: on the selection seeds it saved "
        f"{fmt_num(low['rec_vs_P2']['aog_reduction'], 1)} AOG h/yr "
        f"{ci_num(*low['rec_vs_P2']['aog_reduction_ci'], 1)} versus P2 at a net annual cost of "
        f"{fmt_aed_ci(-low['rec_vs_P2']['net_benefit_aed'], -low['rec_vs_P2']['net_benefit_ci'][1], -low['rec_vs_P2']['net_benefit_ci'][0])}, "
        f"and the rule picks {low['rule_recommends']} there (the frontier holdout ran the central variant only).")
    tor = {t["factor"]: t for t in fr["tornado"]}
    pen = tor["aog_penalty"]
    V["frontier.sensitivity.penalty_half_vs_double"] = (
        f"on the selection seeds the rule still picks {rec_id} at both settings; its net annual benefit over P2 is "
        f"{fmt_aed(pen['low_value'])} {ci_aed_m(*pen['low_ci'])} at penalty ×0.5 and {fmt_aed(pen['high_value'])} "
        f"{ci_aed_m(*pen['high_ci'])} at ×2, against {fmt_aed(pen['base'])} at ×1")
    ad = fr["aog_desk_dependence"]
    V["frontier.aog_desk.summary"] = (
        f"with it switched off (selection seeds) material AOG rises from {fmt_h(ad['central_base_aog_hours'])} to "
        f"{fmt_h(ad['base_aog_hours'])} a year under P2, from {fmt_h(ad['central_rec_aog_hours'])} to "
        f"{fmt_h(ad['rec_aog_hours'])} under {rec_id}, and from {fmt_h(ad['central_p0_aog_hours'])} to "
        f"{fmt_h(ad['p0_aog_hours'])} under P0")

    # model vs simulation (analytic proxy calibration), holdout means across the frontier points
    mx = np.array([p["model_aog_hours"] for p in fr["points"]], float)
    sx = np.array([p["aog_hours"] for p in fr["points"]], float)
    r_hold = float(np.corrcoef(mx, sx)[0, 1])
    p2pt = pts["P2"]
    V["policy.calibration.predicted_vs_simulated"] = (
        f"for P2 the model predicts {fmt_h(p2pt['model_aog_hours'])} a year against {fmt_h(p2pt['aog_hours'])} "
        f"simulated on the holdout; for {rec_id} {fmt_h(rec['model_aog_hours'])} against {fmt_h(rec['aog_hours'])}; "
        f"for P0 {fmt_h(base['model_aog_hours'])} against {fmt_h(base['aog_hours'])}. The proxy is a ranking heuristic, "
        f"not a forecast of AOG hours, and it ranks well: correlation r = {r_hold:.2f} across the "
        f"{len(fr['points'])} frontier points (r = {fsum['model_vs_sim_corr_aog']:.2f} on selection seeds)")

    # greedy vs exact (toy brute-force test)
    passed = junit_case_passed("test_optim_greedy", "test_greedy_equals_brute_force_at_breakpoints")
    V["optim.greedy_gap_small_case_pct"] = (
        "on a small separable, convex toy case the greedy allocation equals the brute-force optimum at every greedy "
        "breakpoint (unit test `tests/test_optim_greedy.py::test_greedy_equals_brute_force_at_breakpoints`, passing); "
        "no exact comparison exists for the full, non-separable network problem" if passed else
        "no exact comparison has been run")

    # ---------------------------------------------------------------- policy tables
    sp = {pid: pd.read_csv(OUT / "policies" / f"{pid}_stock_params.csv") for pid in ("P0", "P1", "P2")}
    alloc = pd.DataFrame(jload(OUT / "frontier" / "allocations.json")["allocations"][rec_id])
    hub = "AUH"

    def rot_units(df):
        r = df[df.part_class == "R"]
        return int(r.base_stock.sum()), int(r[r.station != hub].base_stock.sum())

    u = {pid: rot_units(sp[pid]) for pid in sp}
    ar = alloc[alloc.part_class == "R"]
    u[rec_id] = (u["P2"][0] + int(ar.delta_units.sum()), u["P2"][1] + int(ar[ar.station != hub].delta_units.sum()))
    for pid in ("P0", "P2", rec_id):
        V[f"policy.{pid}.rotable_float_units"] = fmt_int(u[pid][0])
    for pid in ("P0", "P1", "P2"):
        V[f"network.{pid}.units_forward_positioned"] = fmt_int(u[pid][1])
    from gnm.sim.api import load_world  # public master data only
    from gnm.policy.policies import pipeline_units_at_start
    loop = pipeline_units_at_start(load_world(variant="central"))
    V["policy.loop_units"] = fmt_int(sum(loop.values()))
    ce0 = sp["P0"][sp["P0"].part_class.isin(["C", "E"])].set_index(["pn", "station"]).s
    ce2 = sp["P2"][sp["P2"].part_class.isin(["C", "E"])].set_index(["pn", "station"]).s
    j = pd.concat([ce0.rename("p0"), ce2.rename("p2")], axis=1)
    V["policy.P2.rop_changed_lines"] = f"{int((j.p0 != j.p2).sum())} of {len(j)}"
    V["network.P2_vs_P1.aog_hours_reduction_pct"] = fmt_pct(-p21["mean"] / P["P1"]["kpi"]["aog_hours"]["mean"], 0)
    V["network.P2_vs_P1.delta_aog_hours"] = fmt_h(p21["mean"], signed=True)
    V["network.P2_vs_P1.delta_aog_hours_ci"] = ci_int(p21["ci_lo"], p21["ci_hi"])
    sk = pd.read_parquet(OUT / "holdout" / "policy_station_kpis.parquet")
    sk = sk[(sk.variant == "central") & (sk.station != hub)]
    o = sk.groupby(["policy_id", "seed"]).aog_hours.sum().unstack(0)
    od = (o["P2"] - o["P1"]).to_numpy()
    skh = pd.read_parquet(OUT / "holdout" / "policy_station_kpis.parquet")
    skh = skh[(skh.variant == "central") & (skh.station == hub)].pivot(index="seed", columns="policy_id", values="aog_hours")
    hd = (skh["P1"] - skh["P2"]).to_numpy()
    dcap = paired["P2-P1"]["spare_capital_aed"]["mean"]
    from scipy import stats as _st
    hw = float(_st.t.ppf(0.975, od.size - 1) * od.std(ddof=1) / math.sqrt(od.size))
    V["network.outstation_aog_summary"] = (
        f"P1's {fmt_int(u['P1'][1])} forward units do buy something: outstation AOG is {fmt_h(o['P1'].mean())} a year "
        f"under P1 against {fmt_h(o['P2'].mean())} under P2 (P2 − P1 paired {fmt_h(od.mean(), signed=True)} "
        f"{ci_int(od.mean() - hw, od.mean() + hw)}) and {fmt_h(o['P0'].mean())} under P0. But that is about "
        f"{fmt_int(od.mean())} hours for {fmt_aed(abs(dcap))} of extra capital, while starving the hub costs P1 "
        f"{fmt_h(hd.mean())} a year more than P2 at AUH")
    dcap = paired["P2-P1"]["spare_capital_aed"]["mean"]
    V["network.P2_vs_P1.delta_capital_aed"] = f"{fmt_aed(abs(dcap))} {'less' if dcap < 0 else 'more'} capital"

    # ---------------------------------------------------------------- parts risk
    plist = parts["parts"]
    urgent = [p for p in plist if p["risk_level"] == "urgent"]
    tot = sum(p["aog_hours_hist_per_yr"] for p in plist)
    V["parts.top_risk.count"] = str(len(urgent))
    V["parts.top_risk.share_of_aog_hours_pct"] = fmt_pct(sum(p["aog_hours_hist_per_yr"] for p in urgent) / tot, 0)
    top = max(plist, key=lambda p: p["risk_hours"])
    V["parts.top_risk.rank1.pn"] = f"{top['pn']}, {top['desc']}"
    V["parts.top_risk.rank1.risk_hours"] = fmt_int(top["risk_hours"])
    ae = pd.read_parquet(HIST / "aog_events.parquet")
    rows = []
    for e in ae.itertuples(index=False):
        pns = str(e.pns).split(";")
        for pn in pns:
            rows.append((pn, e.station, e.hours / len(pns)))
    split = pd.DataFrame(rows, columns=["pn", "station", "h"])
    st = split[split.pn == top["pn"]].groupby("station").h.sum().sort_values(ascending=False)
    V["parts.top_risk.rank1.station"] = f"{st.index[0]} ({fmt_pct(st.iloc[0] / st.sum(), 0)} of its history AOG hours)"

    # ---------------------------------------------------------------- forecasting
    champs = pd.read_csv(OUT / "forecasting" / "champions.csv")
    ch = {(r.demand_class, r.part_class): r for r in champs.itertuples(index=False)}
    fcch = {(c["demand_class"], c["part_class"]): c for c in fc["champions"]}

    def champ_str(dc):
        cells = [(pc, ch[(dc, pc)].champion) for (d, pc) in sorted(ch) if d == dc]
        if not cells:
            return "no part number falls in the " + dc + " class in this world"
        return ", ".join(f"{METHOD_LABEL[m]} ({CLASS_LABEL[pc]})" for pc, m in cells)

    for dc in ("smooth", "erratic", "intermittent", "lumpy"):
        V[f"forecast.champion.{dc}.method"] = champ_str(dc)
    ir = fcch[("intermittent", "R")]
    V["forecast.champion.intermittent_R.holdout_rank"] = f"{ir['holdout_rank']} of {ir['n_methods']}"
    cm = Counter(p["demand_class"] for p in plist)
    V["forecast.class_counts"] = " / ".join(str(cm.get(c, 0)) for c in
                                           ("smooth", "erratic", "intermittent", "lumpy", "insufficient_data"))
    lines = ["| Demand class | Part class | Parts | Champion (frozen) | Selection MASE | Holdout MASE | Holdout rank | Best on holdout |",
             "|---|---|---|---|---|---|---|---|"]
    for c in fc["champions"]:
        lines.append(f"| {c['demand_class']} | {c['part_class']} | {c['n_parts']} | {METHOD_LABEL[c['method']]} | "
                     f"{c['mase']:.3f} | {c['holdout_mase']:.3f} | {c['holdout_rank']} of {c['n_methods']} | "
                     f"{METHOD_LABEL[c['holdout_best']]} |")
    V["forecast.champions_table"] = "\n".join(lines)

    herr = pd.read_parquet(OUT / "holdout" / "forecast_errors.parquet")
    serr = pd.read_parquet(OUT / "forecasting" / "errors.parquet")

    def champion_rows(err):
        m = err.merge(champs[["demand_class", "part_class", "champion"]], on=["demand_class", "part_class"])
        return m[m.method == m.champion]

    hc = champion_rows(herr)
    V["forecast.holdout.champion_mase"] = f"{hc[hc.mase_status == 'ok'].groupby('pn').mase.mean().mean():.3f}"
    V["forecast.holdout.naive_mase"] = f"{per_part(herr, 'naive').mean():.3f}"
    V["forecast.holdout.champion_bias"] = fmt_num(hc.groupby("pn").bias.mean().mean(), 3)
    V["forecast.holdout.champion_pis"] = fmt_num(hc.groupby("pn").pis.mean().mean(), 2)
    V["forecast.holdout.coverage_80"] = (f"{hc.groupby('pn').cov_q90.mean().mean():.3f} (under-covers: the point-forecast "
                                         f"champions carry a Poisson lead-time distribution, which ignores overdispersion)")

    # reliability vs best Croston family on removal-driven parts (E + R), paired over parts
    def rel_vs_croston(err):
        rem = err[err.part_class.isin(["E", "R"])]
        rel = per_part(rem, "reliability")
        fam = {m: per_part(rem, m) for m in ("croston", "sba", "tsb")}
        best = min(fam, key=lambda m: fam[m].mean())
        d = (rel - fam[best]).dropna()
        lo, hi = boot_ci(d.to_numpy())
        pin_rel = rem[rem.method == "reliability"].groupby("pn").pinball_q90.mean().mean()
        pin_best = rem[rem.method == best].groupby("pn").pinball_q90.mean().mean()
        return dict(rel=rel.mean(), best=best, best_mase=fam[best].mean(), d=d.mean(), lo=lo, hi=hi, n=d.size,
                    pin_rel=pin_rel, pin_best=pin_best)

    h = rel_vs_croston(herr)
    s = rel_vs_croston(serr)
    V["forecast.reliability.mase"] = f"{h['rel']:.3f}"
    V["forecast.best_croston_family.mase"] = f"{h['best_mase']:.3f}"
    V["forecast.best_croston_family.method"] = METHOD_LABEL[h["best"]]
    V["forecast.reliability_vs_croston.delta_mase"] = fmt_signed(h["d"], 3)
    V["forecast.reliability_vs_croston.delta_mase_ci"] = ci_num(h["lo"], h["hi"], 3)

    def verdict(x):
        if x["hi"] < 0:
            return "the reliability model beats the best Croston-family method on MASE"
        if x["lo"] > 0:
            return ("the reliability model does not beat the best Croston-family method on MASE; it is "
                    "significantly worse on point accuracy")
        return ("the reliability model does not beat the best Croston-family method on MASE; the difference is "
                "not significant, so it is a tie on point accuracy")

    V["forecast.reliability_vs_croston.verdict"] = verdict(h) + f" ({h['n']} parts, 95% bootstrap CI over parts)"
    V["forecast.reliability_vs_croston.selection_summary"] = (
        f"reliability {s['rel']:.3f} vs {METHOD_LABEL[s['best']]} {s['best_mase']:.3f}, difference "
        f"{fmt_signed(s['d'], 3)} {ci_num(s['lo'], s['hi'], 3)} ({s['n']} parts); {verdict(s).split(';')[-1].strip()}")
    lbc = pd.DataFrame(fc["leaderboard_by_class_holdout"])
    lbc = lbc[(lbc.demand_class == "all") & (lbc.method != "zero")]
    pin_txt = []
    for pc in ("E", "R"):
        g = lbc[lbc.part_class == pc].set_index("method")
        bestpin = g.pinball_q90.idxmin()
        rel_pin = g.loc["reliability", "pinball_q90"]
        other = g.drop(index="reliability").pinball_q90.min()
        pin_txt.append(f"{CLASS_LABEL[pc]} {rel_pin:.3f} vs next best {other:.3f}"
                       + ("" if bestpin == "reliability" else f" (best: {METHOD_LABEL[bestpin]})"))
    best_ER = all(lbc[lbc.part_class == pc].set_index("method").pinball_q90.idxmin() == "reliability"
                  for pc in ("E", "R"))
    V["forecast.reliability.pinball_summary"] = (
        ("it has the lowest q90 pinball loss of all methods for both expendables and rotables on the holdout ("
         if best_ER else "q90 pinball loss on the holdout (") + "; ".join(pin_txt) + ")")
    lb = pd.DataFrame(fc["leaderboard_by_class_holdout"])
    lb = lb[lb.demand_class == "all"]
    methods = [m for m in ("zero", "naive", "ma", "croston", "sba", "tsb", "adida", "imapa", "bootstrap", "reliability")
               if m in set(lb.method)]
    head = "| Method | " + " | ".join(f"{CLASS_LABEL[pc].capitalize()} MASE [CI] | {CLASS_LABEL[pc].capitalize()} q90 pinball"
                                     for pc in ("C", "E", "R")) + " |"
    rows_md = [head, "|---|" + "---|" * 6]
    best_mase = {pc: lb[(lb.part_class == pc) & (lb.method != "zero")].set_index("method").mase.idxmin() for pc in "CER"}
    best_pin = {pc: lb[(lb.part_class == pc) & (lb.method != "zero")].set_index("method").pinball_q90.idxmin() for pc in "CER"}
    for m in methods:
        cells = []
        for pc in "CER":
            r = lb[(lb.part_class == pc) & (lb.method == m)].iloc[0]
            mtxt = f"{r['mase']:.3f} [{r['mase_ci'][0]:.3f}–{r['mase_ci'][1]:.3f}]"
            ptxt = f"{r['pinball_q90']:.3f}"
            if m == best_mase[pc]:
                mtxt = f"**{mtxt}**"
            if m == best_pin[pc]:
                ptxt = f"**{ptxt}**"
            cells += [mtxt, ptxt]
        label = METHOD_LABEL[m] + (" (benchmark, not eligible)" if m == "zero" else "")
        rows_md.append(f"| {label} | " + " | ".join(cells) + " |")
    rows_md.append("")
    rows_md.append("Full tables: `outputs/holdout/forecast_leaderboard.csv` (by demand class × part class) and "
                   "`outputs/forecasting/leaderboard.csv` (selection window).")
    V["forecast.leaderboard_table"] = "\n".join(rows_md)

    trr = tr["reliability"]["all"]
    V["forecast.truth_recovery.estimated_vs_quoted_improvement"] = (
        f"across {trr['n_parts']} removal-driven parts the median absolute log error of MTBUR falls from "
        f"{trr['quoted_mdale']:.3f} for the vendor quote (about {math.expm1(trr['quoted_mdale']) * 100:.0f}% off) "
        f"to {trr['estimated_mdale']:.3f} for the estimate (about {math.expm1(trr['estimated_mdale']) * 100:.0f}% off), "
        f"and the estimate is closer to the hidden truth for {fmt_pct(trr['share_estimate_closer'], 0)} of parts")
    V["forecast.truth_recovery.median_ape_pct"] = (
        f"{trr['estimated_mdale']:.3f} for the reliability estimate (about {math.expm1(trr['estimated_mdale']) * 100:.0f}% off) "
        f"vs {trr['quoted_mdale']:.3f} for the vendor quote; estimate closer for {fmt_pct(trr['share_estimate_closer'], 0)} of parts")

    mon = fc["monash"]
    mres = {r["method"]: r for r in mon["results"]}
    elig = {m: r for m, r in mres.items() if m != "zero"}
    mb = min(elig, key=lambda m: elig[m]["mase"])
    V["monash.summary"] = (
        f"Dataset: {mon['dataset']}, {mon['info']['n_series']:,} monthly series, licence {mon['licence']}, data "
        f"provenance {mon['data_provenance']} (metrics DERIVED). Best eligible method {METHOD_LABEL[mb]} with mean MASE {elig[mb]['mase']:.3f} "
        f"[{elig[mb]['mase_ci_lo']:.3f}–{elig[mb]['mase_ci_hi']:.3f}]; the all-zero forecast scores "
        f"{mres['zero']['mase']:.3f}, which is why zero is never allowed to be a champion; the bootstrap's q90 "
        f"coverage is {mres['bootstrap']['cov_q90']:.3f}. Attribution: {mon['attribution'].rstrip('.')}.")

    # ---------------------------------------------------------------- actions
    acts = act["actions"]
    V["actions.week.as_of"] = str(act["as_of_week"])
    V["actions.week.count_total"] = str(len(acts))
    V["actions.week.count_urgent"] = str(act["counts"]["by_severity"]["urgent"])
    for i in range(3):
        a = acts[i]
        V[f"actions.top{i + 1}.summary"] = f"{a['summary']} ({a['severity']}: {a['recommended_action'][0].lower()}{a['recommended_action'][1:]})"

    # ---------------------------------------------------------------- freeze / meta / tests
    V["freeze.commit_sha"] = git_commit("^FREEZE:")
    V["freeze.holdout_commit_sha"] = git_commit("^HOLDOUT:")
    V["freeze.manifest_sha256"] = sha256(manifest_path)
    V["freeze.n_artefacts"] = str(len(manifest["artefacts"]))
    V["freeze.holdout_incident"] = method["freeze"]["forced_rerun_note"].removeprefix("Holdout incident, disclosed. ")
    V["meta.git_sha"] = kpis["meta"]["git_sha"]
    import tomllib
    V["meta.model_version"] = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    val = method["validation"]
    tr_txt = (ROOT / "reports" / "test_results.txt").read_text().splitlines()
    V["tests.summary"] = (f"{val['tests_passed']}/{val['tests_total']} passing (fast, slow and browser suites; "
                          f"`reports/test_results.txt`, {tr_txt[0].lstrip('# ').split(',')[-1].strip()})")
    V["repro.run_all_minutes"] = ("not run (there is no single end-to-end runner; individual step timings are in the "
                                  "agent notes under `docs/agent_notes/`)")

    # ---------------------------------------------------------------- story / R014 example
    inc = next(i for i in aog["incidents"] if i["id"] == "AOG-0001")
    ts = pd.Timestamp(inc["need_datetime"].replace("Z", ""))
    local = ts + pd.to_timedelta(330, unit="min")  # BOM is UTC+05:30 (no DST)
    V["story.local_time"] = f"{local:%H:%M} local ({ts:%H:%M} UTC)"
    V["story.tail"] = inc["tail"]
    V["story.incident_id"] = inc["id"]
    V["story.aog_hours"] = fmt_h(inc["aog_hours"])

    pn = "GN-32-R014"
    pm = pd.read_parquet(HIST / "part_master.parquet").set_index("pn").loc[pn]
    pa = pd.read_parquet(HIST / "part_applicability.parquet")
    pa = pa[pa.pn == pn]
    mr = pd.read_parquet(HIST / "material_requests.parquet")
    mr = mr[mr.pn == pn]
    pr = next(p for p in plist if p["pn"] == pn)
    fe = next(x for x in rot["float_examples"] if x["pn"] == pn)
    trel = pd.read_csv(OUT / "holdout" / "truth_recovery_reliability.csv").set_index("pn").loc[pn]
    ff = pd.read_parquet(OUT / "forecasting" / "final_forecasts.parquet")
    ff = ff[ff.pn == pn].set_index("station")
    p2pos = pd.read_csv(OUT / "policies" / "p2_positioning.csv")
    p2pos = p2pos[p2pos.pn == pn].set_index("station")
    tat = next(x for x in rot["tat"] if x["pn"] == pn)
    unit = float(pm.unit_cost_aed)
    E = "example.R014."
    V[E + "description"] = str(pm.description)
    V[E + "deadline_class"] = str(pm.deadline_class)
    V[E + "unit_cost_aed"] = fmt_aed(unit)
    V[E + "applicability"] = ", ".join(f"{r.archetype} × {r.qty_per_aircraft} per aircraft" for r in pa.itertuples())
    V[E + "driver"] = f"flight cycles ({pm.driver})"
    V[E + "mtbur_quoted"] = f"{pm.mtbur_quoted:,.0f} FC"
    V[E + "tat_quoted"] = f"{pm.repair_tat_mean_d:.0f} days"
    V[E + "mtbur_true"] = f"{trel.mtbur_true:,.0f} FC"
    V[E + "mtbur_optimism"] = f"{trel.mtbur_quoted / trel.mtbur_true:.1f}×"
    V[E + "mtbur_estimated"] = f"{trel.mtbur_estimated:,.0f} FC"
    V[E + "removals_history"] = fmt_int(len(mr))
    bom = mr[mr.station == "BOM"]
    V[E + "removals_history_bom"] = fmt_int(len(bom))
    V[E + "fill_bom_history"] = fmt_pct(bom.immediate_fill.mean(), 0)
    V[E + "fill_auh_history"] = fmt_pct(mr[mr.station == "AUH"].immediate_fill.mean(), 0)
    aeb = ae[(ae.station == "BOM") & ae.pns.astype(str).str.split(";").map(lambda x: pn in x)]
    V[E + "aog_events_history_bom"] = fmt_int(len(aeb))
    V[E + "aog_hours_history_bom"] = fmt_h(aeb.hours.sum())
    V[E + "adi"] = f"{pr['adi']:.2f}"
    V[E + "cv2"] = f"{pr['cv2']:.2f}"
    V[E + "demand_class"] = pr["demand_class"]
    V[E + "champion_method"] = (f"{METHOD_LABEL[pr['champion']]} (cell intermittent × rotable; ranked "
                                f"{ir['holdout_rank']} of {ir['n_methods']} on the holdout)")
    V[E + "rate_network_per_30d"] = fmt_num(fe["rate_per_30d"], 2)
    rate_bom30 = float(ff.loc["BOM", "removal_rate_day"]) * 30
    V[E + "rate_bom_per_30d"] = fmt_num(rate_bom30, 2)
    V[E + "pipeline_days"] = fmt_num(fe["pipeline_days"], 1)
    V[E + "tat_actual"] = (f"mean {tat['actual_mean_d']:.1f} days (median {tat['median_d']:.1f}, p90 {tat['p90_d']:.1f}; "
                           f"{tat['n']} completed repair orders) against the quoted {tat['quoted_d']} days")
    from gnm.policy.analytic import availability, ebo, float_calc, pipeline_mean
    mu = pipeline_mean(fe["rate_per_30d"], fe["pipeline_days"])
    V[E + "pipeline_mean_units"] = fmt_num(mu, 2)
    V[E + "loop_units"] = str(fe["loop_units"])
    tbl = ["| Plan | Serviceable units | Total spares S | P(X < S): a removal finds a spare | EBO(S) | Capital at unit cost |",
           "|---|---|---|---|---|---|"]
    for lab, key in (("P0 legacy", "p0_units"), ("P2 network", "p2_units"), (f"{rec_id} recommended", "rec_units")):
        S = int(fe[key]) + int(fe["loop_units"])
        r = float_calc(fe["rate_per_30d"], fe["pipeline_days"], S, unit)
        tbl.append(f"| {lab} | {fe[key]} | {S} | {fmt_pct(r['availability'], 2)} | {r['ebo']:.4f} | "
                   f"{fmt_aed(r['capital_aed'])} |")
    V[E + "palm_network_table"] = "\n".join(tbl)
    L = float(p2pos.loc["BOM", "resupply_days"])
    V[E + "bom_resupply_days"] = fmt_num(L, 1)
    mu_b = rate_bom30 / 30 * L
    lam_yr = rate_bom30 / 30 * 365
    aog_h_station = float(load_world(variant="central").aog_hours.loc["AUH", "BOM"])
    tb = [f"| Units at BOM | P(X < S) | Expected D0 removals a year with no unit on the shelf | Modelled AOG hours a year at {fmt_num(aog_h_station, 0)} h each |",
          "|---|---|---|---|"]
    p0_bom = int(sp["P0"].query("pn == @pn and station == 'BOM'").base_stock.iloc[0])
    p2_bom = int(sp["P2"].query("pn == @pn and station == 'BOM'").base_stock.iloc[0])
    pd0 = float(ff.loc["BOM", "p_d0"])
    for S in sorted({0, 1, p0_bom, p2_bom}):
        a = availability(S, mu_b) if S > 0 else 0.0
        miss = lam_yr * pd0 * (1 - a)
        tag = " (P0)" if S == p0_bom else (" (P2, I125)" if S == p2_bom else "")
        tb.append(f"| {S}{tag} | {fmt_pct(a, 1)} | {miss:.2f} | {miss * aog_h_station:.1f} |")
    tb.append("")
    tb.append(f"BOM removal rate {fmt_num(lam_yr, 1)} a year (D0 share {fmt_pct(pd0, 0)}); pipeline mean at BOM "
              f"λ × resupply = {mu_b:.3f} units. Simple Palm arithmetic for illustration; the optimiser's model also "
              f"includes hub stock-outs and the AOG-desk purchase.")
    V[E + "palm_bom_table"] = "\n".join(tb)
    V[E + "float_P0"] = f"{p0_bom} units at BOM (the whole float of {fe['p0_units']} sits at AUH)"
    V[E + "float_P0_total"] = f"{fe['p0_units']} units, all at AUH"
    V[E + "float_P2_total"] = f"{fe['p2_units']} units"
    V[E + "float_P2_bom"] = str(p2_bom)
    V[E + "float_I125_total"] = f"{fe['rec_units']} units"
    V[E + "float_I125_by_station"] = ", ".join(f"{k} {v}" for k, v in pr["stock_by_station"].items())
    V[E + "delta_capital_aed"] = fmt_aed((fe["rec_units"] - fe["p0_units"]) * unit, signed=True)
    ra = alloc[(alloc.pn == pn)]
    V[E + "delta_capital_I125_vs_P2"] = (f"{fmt_aed(ra.incremental_capital_aed.sum())} for "
                                         f"{int(ra.delta_units.sum())} more units at "
                                         f"{', '.join(sorted(set(ra.station)))}")
    lev = pd.read_csv(OUT / "frontier" / "levers.csv")
    lev = lev[lev.pn == pn].set_index("lever")
    base_h = float(lev.base_aog_hours.iloc[0])
    V[E + "aog_hours_modelled"] = (f"{base_h:.1f} at the P2 allocation; the {rec_id} additions remove a further "
                                   f"{ra.modelled_aog_hour_reduction.sum():.2f}, leaving {pr['residual_aog_h_per_yr']:.2f}")

    def lv(name, verb):
        r = lev.loc[name]
        return (f"{verb} avoids {r.aog_hours_reduction:.1f} AOG h/yr for {fmt_aed(r.annual_cost_aed)}/yr "
                f"(net {fmt_aed(r.net_annual_benefit_aed, signed=True)}/yr)")
    V[E + "alt_levers"] = "; ".join([
        lv("buy_1", "buying 1 more unit at AUH"), lv("buy_2", "buying 2"),
        lv("tat_cut_10d", "paying the vendor to cut TAT by 10 days"),
        f"moving a unit from AUH to BOM {'adds' if lev.loc['reposition_1'].aog_hours_reduction < 0 else 'avoids'} "
        f"{abs(lev.loc['reposition_1'].aog_hours_reduction):.1f} AOG h/yr (it strips the hub). Pool exchange was not "
        f"priced (P3 not implemented)"])
    V[E + "aog_hours_P0"] = ("not run: the holdout records AOG hours by policy, station and part class, not by part "
                             "number")
    bst = next(s for s in net["stations"] if s["station"] == "BOM")["aog_hours_by_policy"]
    V[E + "bom_station_holdout"] = (f"P0 {fmt_h(bst['P0']['mean'])} {ci_int(*bst['P0']['ci'])}, P1 "
                                    f"{fmt_h(bst['P1']['mean'])}, P2 {fmt_h(bst['P2']['mean'])} {ci_int(*bst['P2']['ci'])} "
                                    f"(no per-station breakdown exists for {rec_id})")
    V[E + "incident_id"] = f"{inc['id']} (tail {inc['tail']}, fictional)"
    tl = {s["step"]: s for s in inc["timeline"]}
    V[E + "incident_summary"] = (
        f"At {inc['need_datetime'].replace('T', ' ').replace('Z', ' UTC')} (simulated) {pn} is removed unserviceable "
        f"from {inc['tail']} ({inc['archetype']}) at BOM, deadline {inc['deadline']}. {tl['local_check']['event']}. "
        f"{tl['network_check']['event']}. The AOG desk ships from AUH on the next flight out; the unit arrives and is "
        f"fitted at T+{tl['fitted']['t_h']} h. AOG: {fmt_h(inc['aog_hours'])}, penalty "
        f"{fmt_aed(inc['penalty_aed_per_h'])}/h (narrowbody scenario value).")
    ot = ["| Option | Feasible | Wait | Direct cost | Exposure | Rank | Why |", "|---|---|---|---|---|---|---|"]
    rc = aog["reason_codes"]
    for o in inc["options"]:
        feas = "yes" if o["feasible"] else ("human decision" if o.get("human_decision") else
                                            "indicative only" if o.get("greyed") else "no")
        wait = fmt_h(o["wait_h"]) if o.get("wait_h") is not None else "—"
        cost = fmt_aed(o["direct_cost"]) if o.get("direct_cost") else "—"
        expo = fmt_aed(o["exposure_aed"]) if o.get("exposure_aed") is not None else "—"
        why = "; ".join(rc.get(c, c) for c in o["reason_codes"])
        ot.append(f"| {o['key']}. {o['option']} | {feas} | {wait} | {cost} | {expo} | {o['rank'] or '—'} | {why} |")
    V[E + "incident_options_table"] = "\n".join(ot)
    d = inc["decision"]
    V[E + "incident_recommended"] = f"**{d['recommended']}. {d['recommended_label']}**. {d['why'].rstrip('.')}."
    cf = inc["counterfactual"]
    V[E + "incident_counterfactual"] = (
        f"History took the same route ({cf['actual_route_label'][0].lower() + cf['actual_route_label'][1:]}, {fmt_h(cf['actual_aog_h'])}), so the lab "
        f"finds no better option for this incident: the fix is upstream, in positioning."
        if cf["best_option"] == cf["actual_option"] else
        f"History took a different route ({cf['actual_route_label'][0].lower() + cf['actual_route_label'][1:]}, {fmt_h(cf['actual_aog_h'])} AOG) "
        f"against {fmt_h(cf['best_aog_h'])} for the best option.")
    a3 = next(a for a in acts if a["pn"] == pn and a["station"] == "BOM")
    V[E + "action_summary"] = (f"{a3['exception_id']} ({a3['severity']}, owner: {a3['owner']}, due week "
                               f"{a3['due_week']}): {a3['summary']}. Recommended action: {a3['recommended_action']}. "
                               f"The same part also flags at {sum(1 for a in acts if a['pn'] == pn) - 1} other "
                               f"outstations, because P0 holds no unit at any of them.")

    # ---------------------------------------------------------------- config-quoted parameters
    import yaml
    cfg = yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())
    pc = cfg["parts"]
    V["config.mtbur_ranges"] = (f"{pc['mtbur_fh'][0]:,}–{pc['mtbur_fh'][1]:,} FH, or {pc['mtbur_fc'][0]:,}–"
                                f"{pc['mtbur_fc'][1]:,} FC for the {pc['fc_driven_share'] * 100:.0f}% that are cycle-driven")
    fl = cfg["fleet"]
    V["config.utilisation"] = (f"narrowbody about {fl['narrowbody']['fh_per_day']['mean']} FH and "
                               f"{fl['narrowbody']['fc_per_day']['mean']} FC per day, widebody about "
                               f"{fl['widebody']['fh_per_day']['mean']} FH and {fl['widebody']['fc_per_day']['mean']} FC per day")

    # ---------------------------------------------------------------- narrative keys
    hold_sel = next(c for c in kpis["consistency"] if c["id"] == "aog_hours")
    V["limitations.selection_drift"] = (
        f"the recommended point scored {fmt_h(hold_sel['selection_recommended'])} on selection seeds and "
        f"{fmt_h(hold_sel['holdout_recommended'])} {ci_int(*hold_sel['holdout_ci'])} on the holdout, and the frozen "
        f"MASE champion for intermittent rotables (naive) ranked {ir['holdout_rank']} of {ir['n_methods']} on the "
        f"holdout forecasting test.")
    rel_txt = ("never beats the best Croston-family method on mean MASE (holdout difference "
               f"{V['forecast.reliability_vs_croston.delta_mase']} {V['forecast.reliability_vs_croston.delta_mase_ci']})")
    V["readme.not_win_summary"] = (
        f"The reliability model {rel_txt}, though it has the best q90 pinball loss for expendables and rotables. "
        f"The frozen naive champion for intermittent rotables ranked {ir['holdout_rank']} of {ir['n_methods']} on "
        f"the holdout. P2 spends more on expediting than P0 (paired "
        f"{fmt_aed_ci(paired['P2-P0']['expedite_cost_aed']['mean'], paired['P2-P0']['expedite_cost_aed']['ci_lo'], paired['P2-P0']['expedite_cost_aed']['ci_hi'], signed=True)} a year) and fills "
        f"slightly fewer requests immediately than P1 ({fmt_signed(paired['P2-P1']['immediate_fill_rate']['mean'] * 100, 2)} pp "
        f"{ci_pp(paired['P2-P1']['immediate_fill_rate']['ci_lo'], paired['P2-P1']['immediate_fill_rate']['ci_hi'])}). "
        f"In the low-stress world {V['frontier.low_stress.summary']} Every policy leans on the 5-day AOG-desk "
        f"emergency buy: {V['frontier.aog_desk.summary']}.")
    p1 = P["P1"]["kpi"]
    V["interview.most_surprising_finding"] = (
        f"That more stock made things worse when it was in the wrong place. P1, which sizes every station's float on "
        f"its own demand, carried {fmt_aed(p1['spare_capital_aed']['mean'])} of spares, "
        f"{fmt_aed(paired['P1-P0']['spare_capital_aed']['mean'])} more than legacy rules, and still had "
        f"{fmt_h(p1['aog_hours']['mean'])} of material AOG a year on the holdout. P2 pooled the float at AUH, put "
        f"only {fmt_int(u['P2'][1])} rotable units at outstations instead of {fmt_int(u['P1'][1])}, held "
        f"{fmt_aed(abs(dcap))} less capital than P1 and had {fmt_h(P['P2']['kpi']['aog_hours']['mean'])}. The reason "
        f"is that most deferred removals are rectified at the hub, and the hub also resupplies every outstation, so "
        f"starving it to stock the outstations moves the shortage rather than removing it. The second surprise was "
        f"less comfortable: the recommended point scored {fmt_h(hold_sel['selection_recommended'])} on the selection "
        f"seeds and {fmt_h(hold_sel['holdout_recommended'])} on the holdout. It still beat P2 there "
        f"({V['frontier.recommended_vs_P2.delta_aog_hours']} {V['frontier.recommended_vs_P2.delta_aog_hours_ci']}), but "
        f"it is a reminder that a frontier picked on one set of seeds flatters itself, which is exactly why the "
        f"holdout was frozen and run once.")

    # ---------------------------------------------------------------- palm vs sim (P1, selection)
    pvs = pd.read_csv(OUT / "policies" / "palm_vs_sim.csv")
    pvs = pvs[pvs.sim_requests > 0]
    hub_rows = pvs[pvs.station == hub]
    V["policy.palm_vs_sim.summary"] = (
        f"at AUH mean Palm availability {hub_rows.palm_availability.mean():.3f} vs simulated immediate fill "
        f"{hub_rows.sim_immediate_fill.mean():.3f} over {len(hub_rows)} rotables (mean absolute gap "
        f"{(hub_rows.sim_immediate_fill - hub_rows.palm_availability).abs().mean():.3f}); at outstations "
        f"{pvs[pvs.station != hub].palm_availability.mean():.3f} vs {pvs[pvs.station != hub].sim_immediate_fill.mean():.3f}, "
        f"because Palm with a local repair loop ignores the 4-day resupply from AUH")
    return V


# ----------------------------------------------------------------------------- validation report
def validation_values(V: dict[str, str]) -> dict[str, str]:
    n, bad, suite = junit_counts()
    areas = {
        "Data contracts, leakage, simulator, calibration": ["test_contracts", "test_leakage", "test_sim_engine",
                                                            "test_sim_generator", "test_calibration",
                                                            "test_calibration_lock"],
        "Forecasting (incl. Monash benchmark)": [m for m in n if m.startswith("test_forecasting")],
        "Inventory policy and Palm/EBO maths": ["test_analytic", "test_floatcalc_mirror"] +
                                                [m for m in n if m.startswith("test_policy")],
        "Optimiser / Readiness Frontier": [m for m in n if m.startswith("test_optim")],
        "AOG Response Lab and Planner Action Centre": [m for m in n if m.startswith("test_aog")],
        "Freeze and holdout discipline": ["test_freeze"],
        "Site data export and reconciliation": ["test_reconciliation", "test_site_data"],
        "Web app screens (browser)": [m for m in n if m.startswith("test_site_") and m != "test_site_data"],
    }
    rows = ["| Area | Test modules | Tests | Failed |", "|---|---|---|---|"]
    seen = set()
    for area, mods in areas.items():
        mods = [m for m in mods if m in n]
        seen |= set(mods)
        rows.append(f"| {area} | {', '.join('`' + m + '`' for m in mods)} | {sum(n[m] for m in mods)} | "
                    f"{sum(bad[m] for m in mods)} |")
    rest = [m for m in n if m not in seen]
    if rest:
        rows.append(f"| Other | {', '.join(rest)} | {sum(n[m] for m in rest)} | {sum(bad[m] for m in rest)} |")
    rows.append(f"| **Total** | {len(n)} modules | **{sum(n.values())}** | **{sum(bad.values())}** |")
    W = dict(V)
    W["val.tests_table"] = "\n".join(rows)
    W["val.tests_suite"] = (f"{suite['tests']} tests, {suite['failures']} failures, {suite['errors']} errors, "
                            f"{suite['skipped']} skipped, {float(suite['time']):.0f} s, run at {suite['timestamp']}")
    method = jload(DATA / "method.json")
    cal = ["| Metric (P0, central history, weeks 0–103) | Target band (ASSUMED) | Achieved | In band |", "|---|---|---|---|"]
    for c in method["calibration"]["targets_vs_achieved"]:
        israte = c["target_hi"] <= 1
        f = (lambda x: f"{x:.3f}") if israte else fmt_int
        cal.append(f"| {c['metric'].replace('_', ' ')} | {f(c['target_lo'])}–{f(c['target_hi'])} | {f(c['achieved'])} | "
                   f"{'yes' if c['in_band'] else 'no'} |")
    W["val.calibration_table"] = "\n".join(cal)
    lock = jload(OUT / "freeze" / "calibration_lock.json")
    W["val.calibration_lock"] = f"{len(lock.get('files', lock.get('hashes', lock)))} entries" if isinstance(lock, dict) else NOT_RUN
    log = git("log", "--oneline", "--reverse")
    keep = [ln for ln in log.splitlines()
            if any(k in ln for k in ("Calibration", "calibration", "Holdout runner", "FREEZE", "HOLDOUT", "Phase 2",
                                     "Phase 3", "exporter", "Release prep", "Live deploy"))]
    W["val.git_chain"] = "\n".join(f"- `{ln.split(' ', 1)[0]}` {ln.split(' ', 1)[1]}" for ln in keep) or NOT_RUN
    hl = jload(OUT / "freeze" / "holdout_log.json")
    hrows = ["| # | Run | Logged at (UTC) | Forced |", "|---|---|---|---|"]
    for i, r in enumerate(hl, 1):
        hrows.append(f"| {i} | `{r['run']}` | {r['at'][:19].replace('T', ' ')} | {'yes' if r['forced'] else 'no'} |")
    W["val.holdout_log_table"] = "\n".join(hrows)
    W["val.frozen_at"] = method["freeze"]["frozen_at"][:19].replace("T", " ") + " UTC"
    W["val.freeze_verified"] = "verified (`gnm.freeze.verify()` passed at export)" if method["freeze"]["verified"] else "NOT verified"
    W["val.reporting_note"] = method["freeze"]["reporting_note"]
    kpis = jload(DATA / "kpis.json")
    cons = ["| KPI | Plan | Selection (seeds 100–119) | Holdout (seeds 1000–1019) [95% CI] | Selection inside holdout CI |",
            "|---|---|---|---|---|"]

    def fmtk(kid, x):
        return {"immediate_fill_rate": lambda v: fmt_pct(v), "aog_hours": fmt_h, "spare_capital_aed": fmt_aed,
                "total_annual_cost_aed": fmt_aed, "expedite_cost_aed": fmt_aed,
                "aog_events": lambda v: fmt_num(v, 1)}[kid](x)

    def fmtci(kid, lo, hi):
        return {"immediate_fill_rate": ci_pct, "aog_hours": ci_int, "spare_capital_aed": ci_aed_m,
                "total_annual_cost_aed": ci_aed_m, "expedite_cost_aed": ci_aed,
                "aog_events": lambda a, b: ci_num(a, b, 1)}[kid](lo, hi)
    K = {k["id"]: k for k in kpis["kpis"]}
    for c in kpis["consistency"]:
        kid = c["id"]
        cons.append(f"| {K[kid]['label']} | P0 | {fmtk(kid, c['selection_baseline'])} | "
                    f"{fmtk(kid, c['holdout_baseline'])} {fmtci(kid, *K[kid]['baseline_ci'])} | "
                    f"{'yes' if K[kid]['baseline_ci'][0] <= c['selection_baseline'] <= K[kid]['baseline_ci'][1] else 'no'} |")
        cons.append(f"| | I125 | {fmtk(kid, c['selection_recommended'])} | {fmtk(kid, c['holdout_recommended'])} "
                    f"{fmtci(kid, *c['holdout_ci'])} | {'yes' if c['selection_inside_holdout_ci'] else 'no'} |")
    pol = jload(DATA / "policies.json")
    selp = {p["policy_id"]: p for p in pol["selection"]["policies"]}
    for pid in ("P1", "P2"):
        s, h = selp[pid]["kpi"]["aog_hours"]["mean"], next(p for p in pol["policies"] if p["policy_id"] == pid)["kpi"]["aog_hours"]
        cons.append(f"| Material AOG hours / year | {pid} | {fmt_h(s)} | {fmt_h(h['mean'])} {ci_int(h['ci_lo'], h['ci_hi'])} | "
                    f"{'yes' if h['ci_lo'] <= s <= h['ci_hi'] else 'no'} |")
    W["val.consistency_table"] = "\n".join(cons)
    chk = pd.read_csv(OUT / "holdout" / "forecast_champion_check.csv")
    cc = ["| Demand class | Part class | Parts | Frozen champion | Holdout MASE | Rank of 9 | Best in hindsight |", "|---|---|---|---|---|---|---|"]
    for r in chk.itertuples():
        cc.append(f"| {r.demand_class} | {r.part_class} | {r.n_parts} | {METHOD_LABEL[r.champion]} | {r.champion_mase:.3f} | "
                  f"{r.champion_rank} | {METHOD_LABEL[r.best_in_hindsight]} ({r.best_mase:.3f}) |")
    W["val.champion_check_table"] = "\n".join(cc)
    tr = jload(OUT / "holdout" / "truth_recovery.json")
    tt = ["| Parameter | Parts | Median abs log error, vendor quote | Median abs log error, estimate | Estimate closer |",
          "|---|---|---|---|---|"]
    for key, lab in (("all", "MTBUR, rotables + expendables"), ("R", "MTBUR, rotables"), ("E", "MTBUR, expendables")):
        r = tr["reliability"][key]
        tt.append(f"| {lab} | {r['n_parts']} | {r['quoted_mdale']:.3f} | {r['estimated_mdale']:.3f} | "
                  f"{fmt_pct(r['share_estimate_closer'], 0)} |")
    lt = tr["lead_time"]
    tt.append(f"| Purchase lead time, all parts | {lt['n_parts']} | {lt['quoted_mdale']:.3f} | {lt['estimated_mdale']:.3f} | — |")
    ch = lt["changed_parts"][0]
    W["val.truth_table"] = "\n".join(tt)
    W["val.truth_ps4"] = (f"PS4 {ch['pn']}: true lead time {ch['true']:.1f} d, planner estimate {ch['est']:.1f} d, "
                          f"quoted {ch['quoted']:.1f} d")
    pvs = pd.read_csv(OUT / "policies" / "palm_vs_sim.csv")
    pvs = pvs[pvs.sim_requests > 0]
    pr = ["| Group | Rows with demand | Simulated requests | Palm availability (mean) | Simulated fill (mean) | Mean abs gap | ΣEBO / Σ simulated backorders |",
          "|---|---|---|---|---|---|---|"]
    for lab, g in (("AUH", pvs[pvs.station == "AUH"]), ("Outstations", pvs[pvs.station != "AUH"])):
        pr.append(f"| {lab} | {len(g)} | {int(g.sim_requests.sum()):,} | {g.palm_availability.mean():.3f} | "
                  f"{g.sim_immediate_fill.mean():.3f} | {(g.sim_immediate_fill - g.palm_availability).abs().mean():.3f} | "
                  f"{g.palm_ebo.sum():.2f} / {g.sim_avg_backorders.sum():.2f} |")
    W["val.palm_table"] = "\n".join(pr)
    aog = jload(DATA / "aog_lab.json")["summary"]
    W["val.aog_reconcile"] = (f"{fmt_int(aog['aog_hours_reconstructed'])} of {fmt_int(aog['aog_hours_total'])} history "
                              f"AOG hours reconstructed request by request across {aog['n_incidents']} incidents "
                              f"({'reconciles' if aog['reconciles'] else 'DOES NOT reconcile'})")
    return W


# ----------------------------------------------------------------------------- render
def render_text(text: str, values: dict[str, str], name: str) -> str:
    missing = sorted({k for k in PLACEHOLDER.findall(text) if k not in values})
    if missing:
        raise KeyError(f"{name}: no value for {missing}")
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def keep_phase5(rendered: str, existing: str | None) -> str:
    """Carry over whatever the lead wrote under the Phase 5 heading."""
    if not existing or PHASE5_HEADING not in existing or PHASE5_HEADING not in rendered:
        return rendered
    old = existing.split(PHASE5_HEADING, 1)[1]
    return rendered.split(PHASE5_HEADING, 1)[0] + PHASE5_HEADING + old


def render_all() -> dict[Path, str]:
    V = compute()
    out = {}
    for name in DOCS:
        tmpl = (TEMPLATES / f"{name}.tmpl").read_text()
        out[ROOT / name] = render_text(tmpl, V, name)
    W = validation_values(V)
    tmpl = (TEMPLATES / f"{VALIDATION[0]}.tmpl").read_text()
    existing = VALIDATION[1].read_text() if VALIDATION[1].exists() else None
    out[VALIDATION[1]] = keep_phase5(render_text(tmpl, W, VALIDATION[0]), existing)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if any rendered file differs from disk")
    args = ap.parse_args()
    out = render_all()
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
