"""End-to-end Readiness Frontier run on selection seeds (called by scripts/run_frontier.py)."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from gnm.contracts import PolicySpec
from gnm.optim.frontier import (OUT_DIR, RECOMMENDATION_RULE, build_candidates, evaluate, indistinguishable,
                                lever_findings, mark_frontier, prepare, recommend, recost, scale_lead_times,
                                selection_seeds, summarise, t_ci, write_candidates, allocation_rows, doubled_pns)
from gnm.optim.inputs import load_demand_inputs, load_opt_config


AOG_DESK_NOTE = ("Every policy here, P0/P1/P2 included, relies on the v2 AOG-desk routes (V2-SIM-5/14, config "
                 "aog_sourcing, ASSUMED): robbery at AUH (engineering/quality approval required), local borrow at "
                 "outstations and exchange/loan by fleet, retried every 72 h for rotables, plus local buy for C/E; "
                 "in practice this means access to an AOG exchange/loan market and to borrow agreements. Borrowed "
                 "units never join the owned pool. With the routes switched off (tornado row 'aog_desk_expedite off'), "
                 "expected material-related downtime rises sharply for every policy, so the frontier is conditional "
                 "on those markets existing at the assumed availability.")


def _points(long, cands, base_id, level, p0_id=None):
    pts = summarise(long, base_id, level)
    if p0_id and p0_id != base_id and p0_id in set(long.policy_id):
        p0 = summarise(long, p0_id, level)
        dcols = [c for c in p0.columns if c.startswith("d_")]
        p0 = p0[["id"] + dcols].rename(columns={c: c.replace("_vs_base_", "_vs_P0_") for c in dcols})
        pts = pts.merge(p0, on="id", how="left")
    meta = pd.DataFrame([{"id": c.cid, "kind": c.kind, "label": c.label, "budget_aed": c.budget_aed,
                          "allocation_capital_aed": c.allocation_capital_aed, "model_aog_hours": c.model_aog_hours}
                         for c in cands])
    pts = meta.merge(pts, on="id", how="right")
    return mark_frontier(pts)


def _aed_per_h(long, pid):
    d = long[long.policy_id == pid]
    return float(d.aog_penalty_aed.sum() / max(d.aog_hours.sum(), 1e-9))


def _net_benefit(long, base_id, rec_id, level):
    piv_c = long.pivot(index="seed", columns="policy_id", values="total_annual_cost_aed")
    piv_h = long.pivot(index="seed", columns="policy_id", values="aog_hours")
    piv_k = long.pivot(index="seed", columns="policy_id", values="spare_capital_aed")
    nb = t_ci((piv_c[base_id] - piv_c[rec_id]).to_numpy(), level)
    dh = t_ci((piv_h[base_id] - piv_h[rec_id]).to_numpy(), level)
    return {"net_benefit_mean": nb[0], "net_benefit_lo": nb[1], "net_benefit_hi": nb[2],
            "aog_reduction_mean": dh[0], "aog_reduction_lo": dh[1], "aog_reduction_hi": dh[2],
            "rec_aog_hours": float(piv_h[rec_id].mean()), "base_aog_hours": float(piv_h[base_id].mean()),
            "rec_capital_aed": float(piv_k[rec_id].mean()), "base_capital_aed": float(piv_k[base_id].mean())}


def _with_tat_factor(p: PolicySpec, rot_pns, f: float) -> PolicySpec:
    q = copy.copy(p)
    tm = dict(p.repair_tat_multiplier or {})
    q.repair_tat_multiplier = {pn: round(tm.get(pn, 1.0) * f, 6) for pn in rot_pns}
    return q


def run_frontier(out_dir: Path | str = OUT_DIR, base_policy: PolicySpec | None = None, demand=None,
                 variants=None, processes=None, verbose: bool = True) -> dict:
    t0 = time.time()
    from gnm.sim.api import load_world
    from gnm.sim.baseline import build_p0
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    oc = load_opt_config()
    fc = oc["frontier"]
    level = float(fc["ci_level"])
    weeks, kpi = tuple(fc["scenario_weeks"]), tuple(fc["kpi_weeks"])
    seeds = selection_seeds()
    processes = processes or fc.get("processes")
    world = load_world("central")
    from gnm.optim.frontier import reference_policies
    refs = reference_policies(world, tuple(oc["demand_inputs"].get("reference_policies", ["P0"])))
    if base_policy is None:
        bid = oc["demand_inputs"].get("base_policy", "P0")
        base_policy = refs[bid] if bid in refs else build_p0(world)
    refs[base_policy.policy_id] = base_policy
    if "P0" not in refs:
        refs["P0"] = build_p0(world)
    demand = demand if demand is not None else load_demand_inputs()

    def log(msg):
        if verbose:
            print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    ctx = prepare(world, base_policy, demand, oc, references=refs)
    cands = build_candidates(ctx)
    base_id = base_policy.policy_id
    p0_id = "P0"
    sha = write_candidates(out / "candidates.json", cands, base_policy.policy_id)
    log(f"{len(cands)} candidates, candidates.json sha256 {sha[:12]}")
    pols = [c.policy for c in cands]

    # ---- central, full sweep
    long_c = evaluate(world, pols, seeds, "central", weeks, kpi, processes=processes)
    pts_c = _points(long_c, cands, base_id, level, p0_id)
    aed_h = _aed_per_h(long_c, base_id)
    rec = recommend(pts_c, ctx.carry, aed_h)
    rid = rec["recommended"]
    nd_ids = pts_c[~pts_c.dominated].id.tolist()
    indist = indistinguishable(long_c, sorted(set(nd_ids) | {base_id}), rid, level)
    log(f"central evaluated: recommended {rid}")

    # ---- recommendation stability under the economic factors (no re-simulation needed)
    tc = oc["tornado"]
    stability = []
    for f in tc["aog_penalty_factors"]:
        stability.append({"factor": "aog_penalty", "setting": f"x{f}",
                          "recommended": recommend(pts_c, ctx.carry, aed_h * f)["recommended"]})
    for c in tc["carrying_cost"]:
        stability.append({"factor": "carrying_cost", "setting": f"{c:.2f}",
                          "recommended": recommend(pts_c, c, aed_h)["recommended"]})

    # ---- tornado on the recommended point (paired vs baseline)
    rc = next(c for c in cands if c.cid == rid)
    byid = {c.cid: c.policy for c in cands}
    pair = [byid[i] for i in dict.fromkeys([p0_id, base_id, rid])]      # P0, base, recommended (deduplicated)
    long_pair = long_c[long_c.policy_id.isin([p.policy_id for p in pair])]

    def _nb(lp):
        d = _net_benefit(lp, base_id, rid, level) if rid != base_id else {}
        d.update({f"p0_{k}": v for k, v in _net_benefit(lp, p0_id, rid, level).items()})
        return d
    base_nb = _nb(long_pair)
    torn = [{"factor": "base case", "setting": "central", "method": "simulation", **base_nb}]
    for f in tc["aog_penalty_factors"]:
        torn.append({"factor": "aog_penalty", "setting": f"x{f}", "method": "simulated KPIs re-costed",
                     **_nb(recost(long_pair, penalty_factor=f))})
    for c in tc["carrying_cost"]:
        torn.append({"factor": "carrying_cost", "setting": f"{c:.2f}", "method": "simulated KPIs re-costed",
                     **_nb(recost(long_pair, carry=c))})
    rot = sorted(pn for pn, it in ctx.items.items() if it.is_rotable)
    for f in tc["tat_factors"]:
        lp = evaluate(world, [_with_tat_factor(p, rot, f) for p in pair], seeds, "central", weeks, kpi,
                      processes=processes)
        torn.append({"factor": "repair_tat", "setting": f"x{f}",
                     "method": "simulation (repair_tat_multiplier on all rotables; acceleration surcharge on x<1 "
                               "applies to both policies and cancels in the paired difference up to timing)",
                     **_nb(lp)})
    for f in tc["lead_time_factors"]:
        lp = evaluate(world, pair, seeds, "central", weeks, kpi, processes=processes,
                      scenario_transform=lambda sc, f=f: scale_lead_times(sc, f))
        torn.append({"factor": "lead_time", "setting": f"x{f}",
                     "method": "simulation (Scenario lead-time draws scaled; copy, sim code untouched)",
                     **_nb(lp)})
    if tc.get("expedite_off", True):
        def _noexp(p):
            q = copy.copy(p)
            q.expedite_purchase_on_aog = False
            return q
        lp = evaluate(world, [_noexp(p) for p in pair], seeds, "central", weeks, kpi, processes=processes)
        torn.append({"factor": "aog_desk_expedite", "setting": "off",
                     "method": "simulation (PolicySpec.expedite_purchase_on_aog=False for both policies)",
                     **_nb(lp)})
    tornado = pd.DataFrame(torn)
    if "net_benefit_mean" in tornado:
        tornado["swing_vs_base_aed"] = tornado.net_benefit_mean - base_nb["net_benefit_mean"]
    tornado["swing_vs_p0_aed"] = tornado.p0_net_benefit_mean - base_nb["p0_net_benefit_mean"]
    log("tornado done")

    # ---- stress variants
    variants = variants or [v for v in fc["variants"] if v != "central"]
    var_pts, var_summary, var_long = [], {}, []
    for v in variants:
        wv = load_world(v)
        vp = pols if fc.get("full_variant_sweeps", True) else pair
        lv = evaluate(wv, vp, seeds, v, weeks, kpi, processes=processes)
        vids = {p.policy_id for p in vp}
        pv = _points(lv, [c for c in cands if c.cid in vids], base_id, level, p0_id)
        var_long.append(lv)
        pv["variant"] = v
        var_pts.append(pv)
        vr = recommend(pv, ctx.carry, _aed_per_h(lv, base_id)) if fc.get("full_variant_sweeps", True) else None
        var_summary[v] = {"recommended_point_vs_base_policy": _net_benefit(lv, base_id, rid, level),
                          "recommended_point_vs_P0": _net_benefit(lv, p0_id, rid, level),
                          "references": {i: {"capital_mean": float(pv.set_index("id").loc[i, "capital_mean"]),
                                             "aog_hours_mean": float(pv.set_index("id").loc[i, "aog_hours_mean"])}
                                         for i in refs if i in set(pv.id)},
                          "rule_would_recommend": vr["recommended"] if vr else None,
                          "central_recommended_dominated": bool(pv.set_index("id").loc[rid, "dominated"])}
        log(f"variant {v} done")

    # ---- outputs
    pts_c["variant"] = "central"
    pts_c["on_hull"] = pts_c.id.isin(rec["hull"])
    pts_c["recommended"] = pts_c.id == rid
    pts_c["indistinguishable_from_recommended"] = pts_c.id.map(
        lambda i: indist.get(i, {}).get("indistinguishable") if i != rid else None)
    allp = pd.concat([pts_c] + var_pts, ignore_index=True)
    allp.to_csv(out / "selection_points.csv", index=False)
    pd.concat([long_c] + var_long, ignore_index=True).to_csv(out / "selection_runs.csv", index=False)
    ctx.levers.to_csv(out / "levers.csv", index=False)
    tornado.to_csv(out / "tornado.csv", index=False)
    allocs = {c.cid: allocation_rows(ctx, c) for c in cands if c.kind != "policy"}
    (out / "allocations.json").write_text(json.dumps({"provenance": "SIMULATED", "base_policy_id": base_policy.policy_id,
                                                      "note": "rows only where proposed != current (base policy). Rotable rows show total spares = "
                                                              "base stock + engine loop units (hub) next to every base stock. "
                                                              "modelled_aog_hour_reduction = leave-one-out on the "
                                                              "analytic model, not simulated.",
                                                      "allocations": allocs}, indent=1, default=float))
    gp = pd.DataFrame([{"direction": "down", "pn": s.pn, "station": s.station, "capital_aed": s.capital,
                        "model_aog_hours": s.aog_hours, "ratio": s.ratio} for s in ctx.path.down][::-1]
                      + [{"direction": "start", "pn": None, "station": None, "capital_aed": ctx.path.start_capital,
                          "model_aog_hours": ctx.path.start_aog_hours, "ratio": None}]
                      + [{"direction": "up", "pn": s.pn, "station": s.station, "capital_aed": s.capital,
                          "model_aog_hours": s.aog_hours, "ratio": s.ratio} for s in ctx.path.up])
    gp.to_csv(out / "greedy_path.csv", index=False)
    from gnm.optim.frontier import rotable_totals
    rt = pd.DataFrame([r for c in cands for r in rotable_totals(ctx, c)])
    rt.to_csv(out / "rotable_totals.csv", index=False)
    guard_viol = {c.cid: sorted(set(rt[(rt.candidate == c.cid) & (rt.exceeds_guardrail_at != "")].pn))
                  for c in cands}

    rp = pts_c.set_index("id")
    tat_label = f"tat_cut_{int(round(float(oc['levers']['tat_cut_days'])))}d"
    summary = {
        "provenance": "SIMULATED",
        "split": "selection", "seeds": seeds, "scenario_weeks": list(weeks), "kpi_weeks": list(kpi),
        "base_policy_id": base_policy.policy_id, "demand_source": str(oc["demand_inputs"]["source"]),
        "candidates_sha256": sha, "n_candidates": len(cands),
        "base_allocation_capital_aed": ctx.base_capital,
        "recommendation_rule": RECOMMENDATION_RULE, "recommendation": rec,
        "recommended": {k: (None if pd.isna(v) else v) for k, v in rp.loc[rid].to_dict().items()
                        if not isinstance(v, (list, dict))},
        "base_policy": {k: (None if pd.isna(v) else v) for k, v in rp.loc[base_id].to_dict().items()
                     if not isinstance(v, (list, dict))},
        "recommended_vs_base_policy": _net_benefit(long_c, base_id, rid, level) if rid != base_id else None,
        "recommended_vs_P0": _net_benefit(long_c, p0_id, rid, level),
        "recommended_beats_base_policy_significantly": (
            None if rid == base_id else bool(_net_benefit(long_c, base_id, rid, level)["aog_reduction_lo"] > 0)),
        "references": {i: {k: rp.loc[i, k] for k in ["capital_mean", "capital_lo", "capital_hi", "aog_hours_mean",
                                                      "aog_hours_lo", "aog_hours_hi", "total_cost_mean",
                                                      "model_aog_hours"]} for i in refs},
        "non_dominated": nd_ids, "indistinguishable_vs_recommended": indist,
        "recommendation_stability": stability,
        "variants": var_summary,
        "flagged_more_than_doubles_p0": {"recommended": doubled_pns(ctx, rc),
                                         "rule": "rotable PN whose proposed network units > 2 x P0 units (or >= 2 "
                                                 "when P0 holds 0); reason recorded per row in allocations.json"},
        "aog_desk_dependence": AOG_DESK_NOTE,
        "guardrails": {"config": ctx.guard, "pns_exceeding_by_candidate": guard_viol},
        "break_even": {"formula": "h* = carrying % x AED 1M / (P2 realised (hourly penalty + fixed per-event "
                                  "cost) per downtime hour)", "aed_per_downtime_hour": aed_h,
                       "h_star_per_aed_1m": ctx.carry * 1e6 / aed_h},
        "lever_findings": {"tat_vs_buy_1": lever_findings(ctx.levers, tat_label, "buy_1"),
                           "tat_vs_buy_2": lever_findings(ctx.levers, tat_label, "buy_2")},
        "model_vs_sim_corr_aog": float(np.corrcoef(pts_c.model_aog_hours, pts_c.aog_hours_mean)[0, 1]),
        "runtime_s": round(time.time() - t0, 1),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    log(f"done, outputs in {out}")
    return summary
