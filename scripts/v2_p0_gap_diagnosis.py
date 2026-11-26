#!/usr/bin/env python
"""Diagnose the gap between P0's analytic Poisson availability and simulated rotable fill (v2).

Diagnostic tool, NOT calibration: generator defaults are untouched. Counterfactual worlds are built in
memory (truth edits, scenario edits, engine-config edits) to switch one factor at a time. This script
reads the hidden truth on purpose (it diagnoses the simulator); it is not planning code.
Writes outputs/calibration/v2_p0_gap_diagnosis.{json,md}.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy.stats import poisson

from gnm.config import OUTPUTS, load_config
from gnm.sim.baseline import build_p0, p0_rotable_plan
from gnm.sim.engine import run_policy
from gnm.sim.generator import generate_scenario, generate_world
from gnm.sim.quoted import pipeline_days, quoted_weekly_demand

OUT_JSON = OUTPUTS / "calibration" / os.environ.get("GAP_JSON", "v2_p0_gap_diagnosis.json")
OUT_MD = OUTPUTS / "calibration" / "v2_p0_gap_diagnosis.md"
HUB = "AUH"


def world_truth():
    return generate_world(load_config())


def edit_truth(truth, world, **flags):
    gt = copy.deepcopy(truth)
    t = gt.parts.set_index("pn")
    p = world.parts.set_index("pn")
    rot = p.index[p.part_class == "R"]
    if flags.get("rates_quoted"):
        t.loc[rot, "mtbur_true"] = p.loc[rot, "mtbur_quoted"]
    if flags.get("tat_quoted"):
        t.loc[rot, "repair_tat_mean_true_d"] = p.loc[rot, "repair_tat_mean_d"]
    if flags.get("tat_deterministic"):
        t.loc[rot, "repair_tat_cv_true"] = 1e-3
    if flags.get("poisson"):
        t.loc[rot, "nb_k"] = np.nan
    if flags.get("no_condemn"):
        t.loc[rot, "condemnation_prob_true"] = 0.0
    if flags.get("no_nff"):
        t.loc[rot, "nff_prob_true"] = 0.0
    gt.parts = t.reset_index()[truth.parts.columns]
    return gt


def edit_world_engine(world, **flags):
    """World copy whose cfg/shops change only what the ENGINE sees (P0 is built on the original world)."""
    w = copy.copy(world)
    cfg = copy.deepcopy(world.cfg)
    shops = copy.deepcopy(world.repair_shops)
    if flags.get("no_transport"):
        cfg["network"]["removed_unit_return_days"] = {"mean": 0.0, "sd": 0.0}
        cfg["network"]["routine_transport_days"] = {"mean": 0.0, "sd": 0.0}
        cfg["engine"]["routine_transport_min_days"] = 0.0
        for s in shops.values():
            s["transit_days"] = 0.0
    if flags.get("no_queue"):
        for s in shops.values():
            s["capacity_slots"] = 10 ** 6
    if flags.get("routes_off"):
        cfg["aog_sourcing"]["robbery"]["enabled"] = False
    w.cfg, w.repair_shops = cfg, shops
    return w


def edit_scenario(sc, world, **flags):
    if flags.get("all_at_hub"):
        sc = copy.copy(sc)
        rot = set(world.parts.pn[world.parts.part_class == "R"])
        rq = sc.requests.copy()
        rq.loc[rq.pn.isin(rot), "station"] = HUB
        sc.requests = rq
    return sc


EXPERIMENTS = {
    # name: (truth flags, engine flags, scenario flags, policy flags)
    "full (as built)": ({}, {}, {}, {}),
    "rates = quoted": ({"rates_quoted": 1}, {}, {}, {}),
    "TAT mean = quoted": ({"tat_quoted": 1}, {}, {}, {}),
    "deterministic TAT": ({"tat_deterministic": 1}, {}, {}, {}),
    "Poisson (no NB frailty)": ({"poisson": 1}, {}, {}, {}),
    "no condemnation": ({"no_condemn": 1}, {}, {}, {}),
    "no NFF": ({"no_nff": 1}, {}, {}, {}),
    "no transport": ({}, {"no_transport": 1}, {}, {}),
    "no shop queue": ({}, {"no_queue": 1}, {}, {}),
    "all rotable demand at AUH": ({}, {}, {"all_at_hub": 1}, {}),
    "AOG routes + robbery off": ({}, {"routes_off": 1}, {}, {"routes_off": 1}),
    "104-week warm-up (selection seeds)": ({}, {}, {"long_warmup": 1}, {}),
    "ideal (P0 assumptions hold)": ({"rates_quoted": 1, "tat_quoted": 1, "poisson": 1, "no_condemn": 1, "no_nff": 1},
                                    {"no_queue": 1}, {"all_at_hub": 1}, {}),
}


def rotable_fill(world, res, w0, w1):
    rq = res.requests.merge(world.parts[["pn", "part_class"]], on="pn")
    rq = rq[(rq.part_class == "R") & (rq.need_h >= w0 * 168) & (rq.need_h < (w1 + 1) * 168)]
    rq = rq.assign(imm=rq.immediate_fill.astype(bool), hub=rq.station == HUB)
    return rq[["pn", "station", "hub", "imm", "source"]]


def run_experiment(world, truth, name, seeds_windows):
    tf, ef, sf, pf = EXPERIMENTS[name]
    gt = edit_truth(truth, world, **tf)
    weng = edit_world_engine(world, **ef)
    p0 = build_p0(world)                       # P0 always on the ORIGINAL public data
    if pf.get("routes_off"):
        p0 = replace(p0, expedite_purchase_on_aog=False)
    rows, aog = [], []
    for seed, (s0, s1, k0, k1) in seeds_windows:
        if sf.get("long_warmup") and s0 > 0:
            s0 = 0
        sc = edit_scenario(generate_scenario(world, gt, seed, s0, s1), world, **sf)
        res = run_policy(weng, sc, p0, k0, k1)
        rows.append(rotable_fill(world, res, k0, k1).assign(seed=seed))
        aog.append(res.kpis["aog_hours"])
    return pd.concat(rows, ignore_index=True), float(np.mean(aog))


def getattr_row(per, pn, col):
    v = per.loc[per.pn == pn, col]
    return float(v.iloc[0]) if len(v) and not pd.isna(v.iloc[0]) else float("nan")


def main():
    cfg = load_config()
    world, truth = world_truth()
    hseed = cfg["seeds"]["history_seed"]
    sel = list(range(cfg["seeds"]["selection_seeds"][0], cfg["seeds"]["selection_seeds"][0] + 5))
    sw = [(hseed, (0, 103, 0, 103))] + [(s, (78, 155, 104, 155)) for s in sel]
    plan = p0_rotable_plan(world).set_index("pn")
    parts = world.parts.set_index("pn")
    gtp = truth.parts.set_index("pn")
    dem = quoted_weekly_demand(world).groupby("pn").weekly_demand.sum()

    results = {}
    for name in EXPERIMENTS:
        print("running", name, file=sys.stderr)
        results[name] = run_experiment(world, truth, name, sw)

    full = results["full (as built)"][0]
    # per-PN table
    rows = []
    for pn, pr in plan.iterrows():
        g = full[full.pn == pn]
        m_q = pr.pipeline_mean
        S = int(pr.S_total)
        a_q = poisson.cdf(S - 1, m_q) if S > 0 else 0.0
        # truth-implied (engine definition): true rate, true TAT, actual hub-share transport
        rate_ratio = parts.loc[pn, "mtbur_quoted"] / gtp.loc[pn, "mtbur_true"]
        tat_true = gtp.loc[pn, "repair_tat_mean_true_d"]
        rows.append({
            "pn": pn, "description": parts.loc[pn, "description"], "deadline": parts.loc[pn, "deadline_class"],
            "removal_mode": parts.loc[pn, "removal_mode"], "S_total": S, "loop_units": int(pr.loop_units),
            "auh_base": int(pr.auh_base_stock), "quoted_annual": round(pr.quoted_annual_removals, 2),
            "quoted_pipeline_d": round(pr.quoted_pipeline_days, 1), "quoted_pipeline_mean": round(m_q, 2),
            "analytic_quoted_avail": round(a_q, 4),
            "true_over_quoted_rate": round(rate_ratio, 3), "true_tat_d": round(tat_true, 1),
            "quoted_tat_d": parts.loc[pn, "repair_tat_mean_d"], "nb_k": gtp.loc[pn, "nb_k"],
            "condemn_p": round(gtp.loc[pn, "condemnation_prob_true"], 3), "nff_p": round(gtp.loc[pn, "nff_prob_true"], 3),
            "requests": int(len(g)), "outstation_share": round(float((~g.hub).mean()), 3) if len(g) else np.nan,
            "sim_fill": round(float(g.imm.mean()), 4) if len(g) else np.nan,
            "sim_fill_hub": round(float(g[g.hub].imm.mean()), 4) if g.hub.any() else np.nan,
        })
        for name, (df, _) in results.items():
            gg = df[df.pn == pn]
            rows[-1]["fill: " + name] = round(float(gg.imm.mean()), 4) if len(gg) else np.nan
    per = pd.DataFrame(rows)
    per["gap"] = per.analytic_quoted_avail - per.sim_fill
    worst = per.sort_values("gap", ascending=False).head(10)

    summary = {name: {"rotable_fill": round(float(df.imm.mean()), 4),
                      "rotable_fill_hub": round(float(df[df.hub].imm.mean()), 4),
                      "outstation_share": round(float((~df.hub).mean()), 4),
                      "aog_hours_per_year_mean": round(a, 1)} for name, (df, a) in results.items()}
    # factor decomposition for the worst 10: change in fill when ONE factor is switched off (vs full)
    factors = [n for n in EXPERIMENTS if n not in ("full (as built)", "ideal (P0 assumptions hold)")]
    dec = []
    for r in worst.itertuples():
        row = {"pn": r.pn, "description": r.description, "analytic": r.analytic_quoted_avail, "sim": r.sim_fill,
               "gap": round(r.gap, 4)}
        for f in factors:
            row[f] = round(getattr_row(per, r.pn, "fill: " + f) - r.sim_fill, 4)
        row["ideal"] = round(getattr_row(per, r.pn, "fill: ideal (P0 assumptions hold)"), 4)
        dec.append(row)
    rate = np.array([parts.loc[pn, "mtbur_quoted"] / gtp.loc[pn, "mtbur_true"] for pn in plan.index])
    tat = np.array([gtp.loc[pn, "repair_tat_mean_true_d"] / parts.loc[pn, "repair_tat_mean_d"] for pn in plan.index])
    gc = load_config()["generator"]
    pc = load_config()["parts"]
    design = {"rate_ratio_by_design_mean": round(pc["quoted_mtbur_optimism"] * float(np.exp(pc["quoted_mtbur_noise_sd_log"] ** 2 / 2)), 3),
              "rate_ratio_realised": {"mean": round(float(rate.mean()), 3), "median": round(float(np.median(rate)), 3),
                                      "min": round(float(rate.min()), 3), "max": round(float(rate.max()), 3)},
              "tat_ratio_by_design_mean": round(1 / gc["quoted_tat_optimism"] * float(np.exp(gc["quoted_tat_noise_sd_log"] ** 2 / 2)), 3),
              "tat_ratio_realised": {"mean": round(float(tat.mean()), 3), "median": round(float(np.median(tat)), 3),
                                     "min": round(float(tat.min()), 3), "max": round(float(tat.max()), 3)}}
    wq = per.requests.clip(lower=1)
    out = {"seeds_windows": sw, "experiments": summary, "per_pn": per.to_dict(orient="records"),
           "worst10": worst.pn.tolist(), "decomposition_worst10": dec, "quote_vs_truth_design": design,
           "analytic_weighted_hub": round(float(np.average(per.analytic_quoted_avail, weights=wq)), 4)}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(summary, indent=1))
    cols = ["pn", "description", "deadline", "S_total", "quoted_pipeline_mean", "analytic_quoted_avail", "sim_fill",
            "sim_fill_hub", "outstation_share", "true_over_quoted_rate", "true_tat_d", "quoted_tat_d", "nb_k"]
    print(worst[cols].to_string())
    return out


if __name__ == "__main__":
    main()
