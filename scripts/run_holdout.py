"""The ONE holdout run (seeds 1000-1019 + history-seed continuation weeks 104-155).

Refuses unless outputs/freeze/manifest.json verifies. Each block is logged once via
gnm.freeze.require_frozen. Writes outputs/holdout/*.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from gnm.config import OUTPUTS, load_config, seeds as cfg_seeds
from gnm.freeze import require_frozen, verify

OUT = OUTPUTS / "holdout"
DRY = False   # --dry: exercise every path on 2 selection seeds + history only, no freeze needed


FORCE = set()   # --force=<block>: logged re-run of a block that crashed before producing results


def _gate(name):
    if not DRY:
        require_frozen(name, force=name in FORCE)


def warm_cache(seeds, variants, wf, wt):
    """Generate scenarios sequentially before multiprocessing: parallel workers generating the same
    uncached scenario raced on the pickle cache (truncated read) in the first holdout attempt."""
    from gnm.sim.api import load_or_generate_scenario
    for v in variants:
        for s in seeds:
            load_or_generate_scenario(int(s), wf, wt, variant=v)


def _jd(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def policy_holdout(hold):
    from gnm.policy import evaluate_policies as ep
    from gnm.policy import forecast_pipeline as fp
    from gnm.policy.policies import stock_param_table
    from gnm.sim.api import load_world
    _gate("v2_policy_holdout")
    pcfg = fp.load_policy_config()["evaluation"]
    warm_cache(hold, pcfg["variants"], pcfg["week_from"], pcfg["week_to"])
    champs = pd.read_csv(fp.FC_OUT / "champions.csv")
    kp, st, cl, central = [], [], [], None
    for v in pcfg["variants"]:
        w = load_world(v)
        pv = ep.policies_for_variant(w, v, champs, central)
        if v == "central":
            central = pv["policies"]
        vdir = ep.POL_OUT if v == "central" else ep.POL_OUT / "variants" / v
        for pid, pol in pv["policies"].items():   # rebuilt policies must equal the frozen tables
            frozen = pd.read_csv(vdir / f"{pid}_stock_params.csv")
            now = stock_param_table(pol, w) if "world" in stock_param_table.__code__.co_varnames else stock_param_table(pol)
            cols = [c for c in ["pn", "station", "s", "S", "base_stock"] if c in frozen.columns]
            a = frozen[cols].sort_values(["pn", "station"]).reset_index(drop=True)
            b = now[cols].sort_values(["pn", "station"]).reset_index(drop=True)
            if not a.equals(b.astype(a.dtypes.to_dict())):
                raise RuntimeError(f"rebuilt {v}/{pid} differs from frozen table")
        r = ep.run_variant(w, v, pv["policies"], hold, pcfg)
        for d in (r["kpis"],):
            d["split"] = "holdout"
        kp.append(r["kpis"]); st.append(r["stations"]); cl.append(r["classes"])
    res = pd.concat(kp, ignore_index=True)
    stations = pd.concat(st, ignore_index=True)
    classes = pd.concat(cl, ignore_index=True)
    res.to_parquet(OUT / "policy_results.parquet", index=False)
    stations.to_parquet(OUT / "policy_station_kpis.parquet", index=False)
    classes.to_parquet(OUT / "policy_class_kpis.parquet", index=False)
    ext = ep.penalty_sensitivity(res)
    ext["total_annual_cost_aed"] = ext[ep.COST_COMPONENTS].sum(axis=1)
    mults = load_config()["economics"]["aog_penalty_sensitivity"]
    kpis = ep.SUMMARY_KPIS + [f"total_cost_pen_x{m:g}" for m in mults]
    summary = {"provenance": "SIMULATED", "split": "holdout", "seeds": list(hold),
               "ci_method": "95% paired t over seeds; bootstrap check",
               "variants": ep.summarise(ext, kpis=kpis),
               "by_station": ep._agg_breakdown(stations, "station"),
               "by_class": ep._agg_breakdown(classes, "part_class"),
               "paired_by_station": ep._paired_breakdown(stations, "station", "aog_hours")
               + ep._paired_breakdown(stations, "station", "immediate_fill_rate")}
    (OUT / "policy_summary.json").write_text(json.dumps(summary, indent=2, default=_jd))
    return summary


def frontier_holdout(hold):
    from gnm.optim.frontier import run_frontier_holdout
    if DRY:
        from gnm.optim.frontier import evaluate, load_candidates, summarise
        from gnm.sim.api import load_world
        from gnm.config import ROOT
        cfgc = load_config()["calendar"]
        cands = load_candidates(ROOT / "outputs/frontier/candidates.json")
        long = evaluate(load_world("central"), [p for _, p in cands], hold, "central",
                        weeks=(cfgc["evaluation_weeks"][0] - cfgc["warmup_weeks"], cfgc["evaluation_weeks"][1]),
                        kpi=tuple(cfgc["evaluation_weeks"]))
        res = summarise(long, long.policy_id.iloc[0])
    else:
        res = run_frontier_holdout("outputs/frontier/candidates.json", hold)
    if isinstance(res, pd.DataFrame):
        res.to_csv(OUT / "frontier_points.csv", index=False)
    else:
        (OUT / "frontier_points.json").write_text(json.dumps(res, indent=2, default=_jd))
    return res


def forecast_holdout():
    """Champions frozen on weeks 78-103 are scored on the history seed's continuation (104-155)."""
    from gnm.forecasting.evaluate import aggregate_errors, rolling_origin_evaluate
    from gnm.policy import forecast_pipeline as fp
    from gnm.sim.api import load_or_generate_scenario
    _gate("v2_forecast_holdout")
    cfg = load_config()
    hist = fp.load_history()
    if DRY:   # never touch weeks >= 104: fake a "continuation" from history weeks 52-103
        ext = dict(hist)
        origins = list(range(84, 100, 4)); last = 104; win = (84, 103)
    else:
        sc = load_or_generate_scenario(int(cfg["seeds"]["history_seed"]), 104, 155)
        ext = dict(hist); origins = list(range(104, 152, 4)); last = 156; win = (104, 155)
    if not DRY:
      req = sc.requests.copy()
      ext["material_requests"] = pd.concat([hist["material_requests"], req[hist["material_requests"].columns.intersection(req.columns)]], ignore_index=True)
      ext["flight_exposure"] = pd.concat([hist["flight_exposure"], sc.flights[hist["flight_exposure"].columns]], ignore_index=True)
    inp = fp.build_inputs(ext, origin=last)
    pc = fp.load_policy_config()["forecast"]
    err = rolling_origin_evaluate(inp["demand"], inp["parts"], exposure=inp["exposure"], origins=origins,
                                  method_kwargs={"reliability": {"prior_strength": pc["reliability_prior_strength"]}},
                                  selection_weeks=win)
    err.to_parquet(OUT / "forecast_errors.parquet", index=False)
    board = aggregate_errors(err, by=("demand_class", "part_class"))
    board_cls = aggregate_errors(err, by=("part_class",))
    champs = pd.read_csv(fp.FC_OUT / "champions.csv").set_index(["demand_class", "part_class"])["champion"]
    per_cell = []
    for (dc, pc_), g in err.groupby(["demand_class", "part_class"]):
        means = g.groupby("method").mase.mean().drop("zero", errors="ignore").dropna().sort_values()
        champ = champs.get((dc, pc_))
        per_cell.append({"demand_class": dc, "part_class": pc_, "n_parts": int(g.pn.nunique()), "champion": champ,
                         "champion_mase": float(means.get(champ, np.nan)) if champ else None,
                         "best_in_hindsight": means.index[0] if len(means) else None,
                         "best_mase": float(means.iloc[0]) if len(means) else None,
                         "champion_rank": int(list(means.index).index(champ) + 1) if champ in means.index else None,
                         "n_methods": int(len(means))})
    board.to_csv(OUT / "forecast_leaderboard.csv", index=False)
    board_cls.to_csv(OUT / "forecast_leaderboard_by_class.csv", index=False)
    pd.DataFrame(per_cell).to_csv(OUT / "forecast_champion_check.csv", index=False)
    return {"origins": origins, "cells": per_cell}


def truth_recovery():
    from gnm.eval import truth_recovery as tr
    ff = pd.read_parquet(OUTPUTS / "forecasting" / "final_forecasts.parquet")
    lt = pd.read_csv(OUTPUTS / "forecasting" / "lead_times.csv") if (OUTPUTS / "forecasting" / "lead_times.csv").exists() else None
    res = tr.run(ff, lt, OUT)
    (OUT / "truth_recovery.json").write_text(json.dumps(res, indent=2, default=_jd))
    return res


if __name__ == "__main__":
    import sys
    DRY = "--dry" in sys.argv
    FORCE = {a.split("=", 1)[1] for a in sys.argv if a.startswith("--force=")}
    if DRY:
        OUT = OUTPUTS / "holdout_dryrun"
        hold = cfg_seeds()["selection"][:2]
    else:
        verify()
        hold = cfg_seeds()["holdout"]
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log = {}
    log["policy"] = "done" if policy_holdout(hold) else "empty"
    print("policy holdout", round(time.time() - t0, 1), "s")
    frontier_holdout(hold); print("frontier holdout", round(time.time() - t0, 1), "s")
    forecast_holdout(); print("forecast holdout", round(time.time() - t0, 1), "s")
    truth_recovery(); print("truth recovery", round(time.time() - t0, 1), "s")
