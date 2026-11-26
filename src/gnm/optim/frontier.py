"""Aviation Readiness Frontier: capital tied up in spares vs expected material AOG hours per year.

Pipeline (scripts/run_frontier.py):
  1. demand inputs (history by default, swappable) -> ItemModels -> greedy allocation path;
  2. candidates: ~14 budget points on the path + baseline + "base + additions" + lever variants;
  3. paired simulation of every candidate on the SAME selection-seed scenarios (100–119 only);
  4. non-dominated set, the pre-stated knee rule -> recommended "balanced" point;
  5. allocation tables, levers, tornado, stress variants; candidates.json for the freeze.

Holdout seeds are refused everywhere except run_frontier_holdout(), which checks the freeze
manifest first. Nothing here reads the hidden truth.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from gnm.config import OUTPUTS, load_config, seeds as cfg_seeds
from gnm.contracts import PolicySpec, World
from gnm.optim.greedy import allocation_capital, default_bounds, greedy_path, reposition_only
from gnm.optim.inputs import load_demand_inputs, load_opt_config, penalty_per_hour_by_pn
from gnm.optim.levers import best_actions, lever_findings, lever_table, tat_multiplier
from gnm.optim.model import ItemModel, base_levels, build_items

OUT_DIR = OUTPUTS / "frontier"
CANDIDATES_SCHEMA = "gnm.frontier.candidates/v1"
KPI_COST_KEYS = ["holding_cost_aed", "repair_cost_aed", "logistics_cost_aed", "expedite_cost_aed", "aog_penalty_aed"]
CAPITAL_ONLY_KINDS = ("baseline", "policy", "budget", "incremental", "reposition")


# ---------------------------------------------------------------------------------- candidates
@dataclass
class Candidate:
    cid: str
    kind: str                       # baseline | budget | incremental | reposition | lever | combo
    label: str
    policy: PolicySpec
    budget_aed: float | None = None
    allocation_capital_aed: float = 0.0
    model_aog_hours: float = 0.0
    levels: dict = field(default_factory=dict)
    tat_mult: dict = field(default_factory=dict)


def policy_from_levels(base: PolicySpec, items: dict[str, ItemModel], levels: dict[str, np.ndarray], cid: str,
                       label: str, tat_mult: dict | None = None) -> PolicySpec:
    """Base policy with the modelled PNs' levels replaced (rotables: base_stock; C/E: S, s = S - q)."""
    sp = base.stock_params.copy().reset_index(drop=True)
    idx = {(p, s): i for i, (p, s) in enumerate(zip(sp.pn, sp.station))}
    s_col, S_col, b_col = sp["s"].to_numpy().copy(), sp["S"].to_numpy().copy(), sp["base_stock"].to_numpy().copy()
    for pn, lv in levels.items():
        it = items[pn]
        for j, st in enumerate(it.stations):
            i = idx.get((pn, st))
            if i is None:
                continue
            if it.is_rotable:
                b_col[i] = int(lv[j])
            else:
                S_new = int(lv[j])
                if S_new == int(S_col[i]):
                    continue
                s_col[i] = S_new - int(it.q[j])
                S_col[i] = S_new
    sp["s"], sp["S"], sp["base_stock"] = s_col.astype(int), S_col.astype(int), b_col.astype(int)
    tm = dict(base.repair_tat_multiplier or {})
    tm.update(tat_mult or {})
    return PolicySpec(policy_id=cid, label=label, stock_params=sp,
                      emergency_sources=copy.deepcopy(base.emergency_sources), lateral_transfers=base.lateral_transfers,
                      rebalance=base.rebalance, expedite_purchase_on_aog=base.expedite_purchase_on_aog,
                      repair_tat_multiplier=tm, pool_exchange=base.pool_exchange,
                      notes=f"frontier candidate {cid} on base {base.policy_id}: {label}")


def model_aog(items: dict[str, ItemModel], levels: dict, tat_mult: dict | None = None) -> float:
    tm = tat_mult or {}
    return float(sum(it.aog_hours(levels[pn], tat_mult=tm.get(pn, 1.0)) for pn, it in items.items()))


@dataclass
class Context:
    world: World
    base: PolicySpec
    items: dict
    base_levels: dict
    base_capital: float
    path: object
    incr_path: object
    levers: pd.DataFrame
    best: pd.DataFrame
    carry: float
    accel: float
    ocfg: dict
    references: dict = field(default_factory=dict)     # id -> PolicySpec (P0/P1/P2 reference points)
    ref_levels: dict = field(default_factory=dict)     # id -> {pn: levels}
    p0_levels: dict = field(default_factory=dict)
    ref_model_aog: dict = field(default_factory=dict)


def reference_policies(world: World, ids=("P0", "P1", "P2"), forecasts: pd.DataFrame | None = None) -> dict:
    """The project's policies as frontier reference points. P1/P2 are rebuilt from the frozen forecasts
    with gnm.policy.policies (deterministic; identical to outputs/policies/P*_stock_params.csv)."""
    from gnm.sim.baseline import build_p0
    out = {}
    if "P0" in ids:
        out["P0"] = build_p0(world)
    if any(i in ids for i in ("P1", "P2")):
        from gnm.policy.policies import build_p1, build_p2, load_forecasts
        ff = forecasts if forecasts is not None else load_forecasts()
        if "P1" in ids:
            out["P1"] = build_p1(world, ff)
        if "P2" in ids:
            out["P2"] = build_p2(world, ff)
    return out


def engine_loop_units(world: World) -> dict:
    """POL-6: rotable units the engine seeds in the repair loop at t0 (public quoted figures)."""
    from gnm.policy.policies import pipeline_units_at_start
    return pipeline_units_at_start(world)


def prepare(world: World, base_policy: PolicySpec, demand: pd.DataFrame | None = None,
            ocfg: dict | None = None, references: dict | None = None) -> Context:
    ocfg = ocfg or load_opt_config()
    mc, fc, lc = ocfg["model"], ocfg["frontier"], ocfg["levers"]
    demand = demand if demand is not None else load_demand_inputs()
    cal = world.cfg["calendar"]
    pen, loops = penalty_per_hour_by_pn(world), engine_loop_units(world)

    def _items(pol):
        return build_items(demand, world, pol, pen, include_count_parts=bool(mc["include_count_parts"]),
                           value_classes=tuple(mc["count_part_classes_with_value"]),
                           warmup_weeks=float(cal["warmup_weeks"]),
                           kpi_weeks=float(fc["kpi_weeks"][1] - fc["kpi_weeks"][0] + 1), loop_units=loops)
    items = _items(base_policy)
    base = base_levels(items, base_policy)
    cap0 = allocation_capital(items, base)
    fr = sorted(fc["budget_fractions"])
    floors, ceils = default_bounds(items, base, base, max_out=int(mc["max_outstation_units"]),
                                   hub_sd=float(mc["hub_ceiling_sd"]), ce_sd=float(mc["count_part_max_increments_sd"]),
                                   min_hub_ready=float(mc.get("rotable_min_hub_ready_rate", 0.0)))
    # zero start = re-optimise the rotable float from its floor; base start = only add/remove vs the base
    start = {pn: (floors[pn].copy() if items[pn].is_rotable and fc["rotable_start"] == "zero" else v.copy())
             for pn, v in base.items()}
    # the base policy may sit below a floor: floors apply to the re-optimised path, not to the base path
    base_floors = {pn: np.minimum(floors[pn], base[pn]) for pn in base}
    path = greedy_path(items, start, floors, ceils, budget_max=max(fr) * cap0 * 1.001,
                       budget_min=min(fr) * cap0 * 0.999)
    inc = max(fc.get("incremental_fractions") or [1.0])
    incr = greedy_path(items, base, base_floors, ceils, budget_max=inc * cap0 * 1.001, budget_min=cap0)
    eco = world.cfg["economics"]
    carry, accel = float(eco["carrying_cost_pct_per_year"]), float(eco["repair_acceleration_cost_aed_per_day_per_unit"])
    lev = lever_table(items, base, carry, accel, tat_cut_days=float(lc["tat_cut_days"]),
                      extra_spares=tuple(lc["extra_spares"]), max_cut_share=float(lc["max_cut_share_of_work"]))
    refs = dict(references or {})
    refs.setdefault(base_policy.policy_id, base_policy)
    if "P0" not in refs:
        from gnm.sim.baseline import build_p0
        p0 = build_p0(world)
    else:
        p0 = refs["P0"]
    return Context(world=world, base=base_policy, items=items, base_levels=base, base_capital=cap0, path=path,
                   incr_path=incr, levers=lev, best=best_actions(lev), carry=carry, accel=accel, ocfg=ocfg,
                   references=refs, ref_levels={k: base_levels(items, v) for k, v in refs.items()},
                   p0_levels=base_levels(items, p0),
                   # each reference policy is modelled with its OWN (s,S) order quantities
                   ref_model_aog={k: model_aog(it_k, base_levels(it_k, v))
                                  for k, v in refs.items() for it_k in [_items(v)]})


def build_candidates(ctx: Context) -> list[Candidate]:
    fc, lc = ctx.ocfg["frontier"], ctx.ocfg["levers"]
    items, base, cap0 = ctx.items, ctx.base_levels, ctx.base_capital
    out = []
    # reference policies first (base policy first of all), labelled kind = "policy"
    order = [ctx.base.policy_id] + sorted(k for k in ctx.references if k != ctx.base.policy_id)
    for rid in order:
        pol = copy.copy(ctx.references[rid])
        pol.policy_id = rid
        lv = ctx.ref_levels[rid]
        tag = " (base policy)" if rid == ctx.base.policy_id else ""
        out.append(Candidate(rid, "policy", f"{rid} {pol.label} as built{tag}", pol, None,
                             allocation_capital(items, lv), ctx.ref_model_aog[rid], {k: v.copy() for k, v in lv.items()}))
    seen = set()
    for f in sorted(fc["budget_fractions"]):
        lv, cap = ctx.path.allocation_at(f * cap0)
        key = tuple(np.concatenate([lv[k] for k in sorted(lv)]).tolist())
        if key in seen:
            continue
        seen.add(key)
        cid = f"B{int(round(f * 100)):03d}"
        lab = f"Re-optimised allocation, budget {f:.2f} x base allocation capital"
        out.append(Candidate(cid, "budget", lab, policy_from_levels(ctx.base, items, lv, cid, lab), f * cap0, cap,
                             model_aog(items, lv), lv))
    for f in sorted(fc.get("incremental_fractions") or []):
        lv, cap = ctx.incr_path.allocation_at(f * cap0)
        cid = f"I{int(round(f * 100)):03d}"
        lab = f"Base + greedy additions only, budget {f:.2f} x base allocation capital"
        out.append(Candidate(cid, "incremental", lab, policy_from_levels(ctx.base, items, lv, cid, lab), f * cap0, cap,
                             model_aog(items, lv), lv))
    # lever: reposition only (zero capital)
    lv, moves = reposition_only(items, base)
    if moves:      # skipped when the base policy is already positioned (the candidate would equal the base)
        lab = f"Reposition only: {len(moves)} existing rotable units moved AUH -> outstation (zero capital)"
        out.append(Candidate("LEV_REPOS", "reposition", lab,
                             policy_from_levels(ctx.base, items, lv, "LEV_REPOS", lab),
                             cap0, allocation_capital(items, lv), model_aog(items, lv), lv))
    # lever: TAT -d days on the top-N PNs by net annual benefit of the TAT cut
    tat = _tat_targets(ctx, int(lc["tat_top_n"]))
    d = int(round(float(lc["tat_cut_days"])))
    lab = f"Repair TAT -{d} d on top-{len(tat)} PNs by net benefit (base allocation)"
    out.append(Candidate(f"LEV_TAT{d}_TOP{len(tat)}", "lever", lab,
                         policy_from_levels(ctx.base, items, base, f"LEV_TAT{d}_TOP{len(tat)}", lab, tat),
                         None, cap0, model_aog(items, base, tat), {k: v.copy() for k, v in base.items()}, tat))
    # combo: re-optimised allocation at the base budget + the same TAT cuts
    lv, cap = ctx.path.allocation_at(1.0 * cap0)
    cid = f"COMBO_B100_TAT{d}"
    lab = f"Re-optimised allocation at base budget + repair TAT -{d} d on the same {len(tat)} PNs"
    out.append(Candidate(cid, "combo", lab, policy_from_levels(ctx.base, items, lv, cid, lab, tat), cap0, cap,
                         model_aog(items, lv, tat), lv, tat))
    return out


def _tat_targets(ctx: Context, n: int) -> dict:
    lv = ctx.levers
    if lv.empty:
        return {}
    t = lv[lv.lever.str.startswith("tat_cut")].sort_values(["net_annual_benefit_aed", "pn"], ascending=[False, True])
    t = t[t.net_annual_benefit_aed > 0].head(n)
    return {r.pn: round(float(r.tat_multiplier), 4) for r in t.itertuples(index=False)}


# ---------------------------------------------------------------------------------- freeze support
def _policy_payload(p: PolicySpec) -> dict:
    sp = p.stock_params[["pn", "station", "s", "S", "base_stock"]].sort_values(["pn", "station"])
    return {"policy_id": p.policy_id, "label": p.label,
            "emergency_sources": {k: list(v) for k, v in sorted((p.emergency_sources or {}).items())},
            "lateral_transfers": bool(p.lateral_transfers), "rebalance": bool(p.rebalance),
            "expedite_purchase_on_aog": bool(p.expedite_purchase_on_aog),
            "repair_tat_multiplier": {k: round(float(v), 6) for k, v in sorted((p.repair_tat_multiplier or {}).items())},
            "stock_params": [[r.pn, r.station, int(r.s), int(r.S), int(r.base_stock)] for r in sp.itertuples(index=False)]}


def candidates_payload(cands: list[Candidate], base_policy_id: str) -> dict:
    return {"schema": CANDIDATES_SCHEMA, "base_policy_id": base_policy_id,
            "candidates": [{"id": c.cid, "kind": c.kind, "label": c.label,
                            "budget_aed": None if c.budget_aed is None else round(float(c.budget_aed), 2),
                            "policy": _policy_payload(c.policy)} for c in sorted(cands, key=lambda c: c.cid)]}


def dumps_deterministic(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def write_candidates(path: Path | str, cands: list[Candidate], base_policy_id: str) -> str:
    """Write candidates.json deterministically; returns its SHA-256."""
    text = dumps_deterministic(candidates_payload(cands, base_policy_id))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def load_candidates(path: Path | str) -> list[tuple[dict, PolicySpec]]:
    obj = json.loads(Path(path).read_text())
    if obj.get("schema") != CANDIDATES_SCHEMA:
        raise ValueError("unknown candidates schema")
    out = []
    for c in obj["candidates"]:
        p = c["policy"]
        sp = pd.DataFrame(p["stock_params"], columns=["pn", "station", "s", "S", "base_stock"])
        out.append((c, PolicySpec(policy_id=p["policy_id"], label=p["label"], stock_params=sp,
                                  emergency_sources=p["emergency_sources"], lateral_transfers=p["lateral_transfers"],
                                  rebalance=p["rebalance"], expedite_purchase_on_aog=p["expedite_purchase_on_aog"],
                                  repair_tat_multiplier=p["repair_tat_multiplier"])))
    return out


# ---------------------------------------------------------------------------------- evaluation
def selection_seeds() -> list[int]:
    return list(cfg_seeds()["selection"])


def _check_seeds(seeds, allow_holdout: bool):
    sel, hold = set(cfg_seeds()["selection"]), set(cfg_seeds()["holdout"])
    bad_hold = [s for s in seeds if s in hold]
    if bad_hold and not allow_holdout:
        raise PermissionError(f"holdout seeds {bad_hold} are only allowed through run_frontier_holdout() after freeze")
    if not allow_holdout and any(s not in sel for s in seeds):
        raise ValueError(f"frontier selection uses selection seeds {sorted(sel)} only")


def scale_lead_times(sc, factor: float):
    """Copy of a Scenario with every pre-sampled purchase lead time scaled (what-if; sim code untouched)."""
    s2 = copy.copy(sc)
    s2.lead_time_days = {k: np.asarray(v, float) * factor for k, v in (sc.lead_time_days or {}).items()}
    s2.lead_time_regimes = {k: [(h, np.asarray(a, float) * factor) for h, a in v]
                            for k, v in (sc.lead_time_regimes or {}).items()}
    return s2


def evaluate(world: World, policies: list[PolicySpec], seeds, variant: str = "central",
             weeks=(78, 155), kpi=(104, 155), runner=None, scenario_transform=None, processes=None,
             allow_holdout: bool = False) -> pd.DataFrame:
    """Paired evaluation: every policy runs on the SAME scenario per seed (common random numbers).

    Returns one row per (policy_id, seed) with the engine KPIs + total_annual_cost_aed."""
    from gnm.sim.api import load_or_generate_scenario
    seeds = [int(s) for s in seeds]
    _check_seeds(seeds, allow_holdout)
    if runner is None:
        from gnm.sim.engine import run_many as runner
    if scenario_transform is None:
        for s in seeds:   # make sure the cache exists before workers read it (no concurrent writes)
            load_or_generate_scenario(s, weeks[0], weeks[1], use_cache=True, variant=variant)
        scen = [(s, weeks[0], weeks[1], True, variant) for s in seeds]
    else:
        scen = [scenario_transform(load_or_generate_scenario(s, weeks[0], weeks[1], use_cache=True, variant=variant))
                for s in seeds]
    res = runner(world, scen, policies, kpi[0], kpi[1], processes=processes)
    rows = []
    k = 0
    for s in seeds:
        for p in policies:
            r = res[k]
            k += 1
            if r.policy_id != p.policy_id or int(r.seed) != s:
                raise RuntimeError("run_many order mismatch")
            row = {"policy_id": p.policy_id, "seed": s, "variant": variant}
            row.update({kk: float(v) for kk, v in r.kpis.items()})
            row["total_annual_cost_aed"] = float(sum(r.kpis[c] for c in KPI_COST_KEYS))
            rows.append(row)
    return pd.DataFrame(rows)


def t_ci(x: np.ndarray, level: float = 0.95) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    n = len(x)
    m = float(x.mean())
    if n < 2:
        return m, m, m
    h = float(stats.t.ppf(0.5 + level / 2, n - 1) * x.std(ddof=1) / math.sqrt(n))
    return m, m - h, m + h


def recost(long: pd.DataFrame, penalty_factor: float = 1.0, carry: float | None = None,
           base_carry: float = 0.20) -> pd.DataFrame:
    """Recompute annual cost under a different AOG penalty scale / carrying %, from simulated KPIs
    (both enter the total linearly, so no re-simulation is needed)."""
    d = long.copy()
    d["aog_penalty_aed"] = d.aog_penalty_aed * penalty_factor
    if carry is not None:
        d["holding_cost_aed"] = d.spare_capital_aed * carry
    d["total_annual_cost_aed"] = d[KPI_COST_KEYS].sum(axis=1)
    return d


def summarise(long: pd.DataFrame, baseline_id: str, level: float = 0.95) -> pd.DataFrame:
    """Mean + t CI per policy, and paired differences vs the baseline (same seeds)."""
    piv = {m: long.pivot(index="seed", columns="policy_id", values=m)
           for m in ["spare_capital_aed", "aog_hours", "total_annual_cost_aed", "aog_penalty_aed", "holding_cost_aed",
                     "expedite_cost_aed", "repair_cost_aed", "immediate_fill_rate", "aog_events"]}
    rows = []
    for pid in long.policy_id.unique():
        r = {"id": pid, "n_seeds": int(piv["aog_hours"][pid].notna().sum())}
        for m, short in [("spare_capital_aed", "capital"), ("aog_hours", "aog_hours"),
                         ("total_annual_cost_aed", "total_cost"), ("aog_penalty_aed", "aog_penalty"),
                         ("holding_cost_aed", "holding_cost"), ("expedite_cost_aed", "expedite_cost"),
                         ("repair_cost_aed", "repair_cost"), ("immediate_fill_rate", "fill_rate"),
                         ("aog_events", "aog_events")]:
            mu, lo, hi = t_ci(piv[m][pid].to_numpy(), level)
            r[f"{short}_mean"], r[f"{short}_lo"], r[f"{short}_hi"] = mu, lo, hi
            if short in ("capital", "aog_hours", "total_cost"):
                dm, dlo, dhi = t_ci((piv[m][pid] - piv[m][baseline_id]).to_numpy(), level)
                r[f"d_{short}_vs_base_mean"], r[f"d_{short}_vs_base_lo"], r[f"d_{short}_vs_base_hi"] = dm, dlo, dhi
        rows.append(r)
    return pd.DataFrame(rows)


def nondominated(x: np.ndarray, y: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Mask of points not dominated when minimising both x and y (weakly better in both, strictly in one)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    keep = np.ones(n, bool)
    for i in range(n):
        dom = (x <= x[i] + tol) & (y <= y[i] + tol) & ((x < x[i] - tol) | (y < y[i] - tol))
        if dom.any():
            keep[i] = False
    return keep


def lower_hull(x: np.ndarray, y: np.ndarray) -> list[int]:
    """Indices of the lower convex hull (sorted by x) — monotone chain."""
    order = sorted(range(len(x)), key=lambda i: (x[i], y[i]))
    hull: list[int] = []
    for i in order:
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            cross = (x[b] - x[a]) * (y[i] - y[a]) - (y[b] - y[a]) * (x[i] - x[a])
            if cross <= 0:
                hull.pop()
            else:
                break
        hull.append(i)
    # keep the decreasing part only (frontier): drop trailing points where y rises
    out = [hull[0]]
    for i in hull[1:]:
        if y[i] < y[out[-1]]:
            out.append(i)
    return out


RECOMMENDATION_RULE = (
    "Stated before computing. Among the capital-only candidates (baseline/reference policies, budget points, "
    "base+additions, reposition), take the non-dominated set on the selection-seed means (minimise simulated capital and "
    "material AOG h/yr) and its lower convex hull, sorted by capital. Walking up the hull, each segment's "
    "marginal value is the AOG-hour reduction per extra AED 1M of capital. The break-even value implied by "
    "the AOG penalty is h* = carrying % x AED 1M / (baseline AED per AOG hour), i.e. the AOG hours whose "
    "penalty equals the extra annual holding cost of AED 1M. The recommended 'balanced' point is the last hull "
    "vertex before the first segment whose marginal value falls below h* (equivalently the hull point that "
    "minimises carrying % x capital + AED/h x AOG hours). If no segment falls below h*, the highest-capital "
    "vertex is recommended and flagged 'frontier not saturated'.")


def recommend(points: pd.DataFrame, carry: float, aed_per_aog_h: float) -> dict:
    cand = points[points.kind.isin(CAPITAL_ONLY_KINDS)].reset_index(drop=True)
    x, y = cand.capital_mean.to_numpy(), cand.aog_hours_mean.to_numpy()
    nd = nondominated(x, y)
    sub = cand[nd].reset_index(drop=True)
    hx, hy = sub.capital_mean.to_numpy(), sub.aog_hours_mean.to_numpy()
    hull = lower_hull(hx, hy)
    h_star = carry * 1e6 / aed_per_aog_h
    segs = []
    rec = hull[-1]
    saturated = False
    for a, b in zip(hull[:-1], hull[1:]):
        slope = (hy[a] - hy[b]) / ((hx[b] - hx[a]) / 1e6)
        segs.append({"from": sub.id[a], "to": sub.id[b], "h_per_aed_1m": float(slope)})
    for k, sg in enumerate(segs):
        if sg["h_per_aed_1m"] < h_star:
            rec = hull[k]
            saturated = True
            break
    obj = carry * hx + aed_per_aog_h * hy
    return {"recommended": str(sub.id[rec]), "h_star_per_aed_1m": float(h_star), "aed_per_aog_hour": float(aed_per_aog_h),
            "carrying_pct": float(carry), "hull": [str(sub.id[i]) for i in hull], "segments": segs,
            "frontier_saturated": bool(saturated),
            "min_holding_plus_penalty_on_hull": str(sub.id[min(hull, key=lambda i: obj[i])])}


def mark_frontier(points: pd.DataFrame) -> pd.DataFrame:
    p = points.copy()
    p["dominated"] = ~nondominated(p.capital_mean.to_numpy(), p.aog_hours_mean.to_numpy())
    return p


def indistinguishable(long: pd.DataFrame, ids: list[str], ref: str, level: float = 0.95) -> dict:
    """For each id: paired AOG-hour difference vs `ref`; True if the CI contains 0."""
    piv = long.pivot(index="seed", columns="policy_id", values="aog_hours")
    out = {}
    for i in ids:
        if i == ref:
            continue
        m, lo, hi = t_ci((piv[i] - piv[ref]).to_numpy(), level)
        out[i] = {"d_aog_mean": m, "d_aog_lo": lo, "d_aog_hi": hi, "indistinguishable": bool(lo <= 0 <= hi)}
    return out


# ---------------------------------------------------------------------------------- tables
DOUBLING_FACTOR = 2.0


def doubling_reason(ctx: Context, pn: str, lv: np.ndarray, tm: float = 1.0) -> str:
    """Plain-language reason why a rotable's proposed network units more than double P0's (OPT-8)."""
    it = ctx.items[pn]
    p0 = int(ctx.p0_levels[pn].sum())
    lam = it.lam_net
    T = it.resupply_days - it.work_days + it.work_days * tm
    mu = it.hub_mu(tat_mult=tm)
    d0 = float(it.rates[:, 0].sum() / lam) if lam > 0 else 0.0
    hold = ctx.carry * it.unit_cost
    tags = []
    if d0 >= 0.5 and it.penalty_per_h > hold / 10.0:
        tags.append("high D0 penalty x low unit cost")
    if mu > p0 + it.loop_units:
        tags.append("P0 float + seeded loop below the forecast pipeline (P0 sized on quoted MTBUR/TAT)")
    if int(lv[1:].sum()) > int(ctx.p0_levels[pn][1:].sum()):
        tags.append("outstation units avoid AOG transport for D0 demand")
    # value of the last hub unit
    dh = 0.0
    if lv[0] > 0:
        rev = lv.copy()
        rev[0] -= 1
        dh = it.aog_hours(rev, tat_mult=tm) - it.aog_hours(lv, tat_mult=tm)
    return (f"{'; '.join(tags) or 'greedy marginal value'}: pipeline mean {mu:.1f} units "
            f"({lam * 365:.0f} removals/yr x {T:.0f} d, completed-RO trimmed mean) vs {p0} P0 base_stock units "
            f"+ {it.loop_units} seeded loop units; "
            f"D0 share {d0:.0%}; AOG penalty AED {it.penalty_per_h:,.0f}/h vs unit cost AED {it.unit_cost:,.0f} "
            f"(holding AED {hold:,.0f}/yr per unit); last hub unit avoids {dh:.2f} modelled AOG h/yr "
            f"= AED {dh * it.penalty_per_h:,.0f}/yr")


def doubled_pns(ctx: Context, c: Candidate) -> dict[str, str]:
    """Rotable PNs whose proposed network units exceed DOUBLING_FACTOR x P0 units (P0 = 0: >= 2 units)."""
    out = {}
    for pn in sorted(ctx.items):
        it = ctx.items[pn]
        if not it.is_rotable:
            continue
        p0 = int(ctx.p0_levels[pn].sum())
        new = int(c.levels.get(pn, ctx.base_levels[pn]).sum())
        if (p0 > 0 and new > DOUBLING_FACTOR * p0) or (p0 == 0 and new >= 2):
            out[pn] = doubling_reason(ctx, pn, c.levels[pn], c.tat_mult.get(pn, 1.0))
    return out


def allocation_rows(ctx: Context, c: Candidate) -> list[dict]:
    items, base = ctx.items, ctx.base_levels
    best = ctx.best.set_index("pn") if not ctx.best.empty else pd.DataFrame()
    flagged = doubled_pns(ctx, c)
    rows = []
    for pn in sorted(items):
        it = items[pn]
        lv, b = c.levels.get(pn, base[pn]), base[pn]
        tm = c.tat_mult.get(pn, 1.0)
        if np.array_equal(lv, b) and tm == 1.0:
            continue
        h_new = it.aog_hours(lv, tat_mult=tm)
        alt = best.loc[pn, "best_action"] if (len(best) and pn in best.index) else "n/a (count part)"
        flag = {"flag_more_than_doubles_p0": pn in flagged, "reason": flagged.get(pn, "")}
        for j, st in enumerate(it.stations):
            if lv[j] == b[j]:
                continue
            rev = lv.copy()
            rev[j] = b[j]
            rows.append({"pn": pn, "station": st, "part_class": it.part_class,
                         "level": "base_stock" if it.is_rotable else "order_up_to_S",
                         "current": int(b[j]), "proposed": int(lv[j]), "delta_units": int(lv[j] - b[j]),
                         "incremental_capital_aed": round(float((lv[j] - b[j]) * it.unit_cost), 2),
                         "modelled_aog_hour_reduction": round(float(it.aog_hours(rev, tat_mult=tm) - h_new), 3),
                         "best_alternative_action": alt, **flag})
        if tm != 1.0:
            rows.append({"pn": pn, "station": "(repair shop)", "part_class": it.part_class,
                         "level": "repair_tat_multiplier", "current": 1.0, "proposed": tm, "delta_units": 0,
                         "incremental_capital_aed": 0.0,
                         "modelled_aog_hour_reduction": round(float(it.aog_hours(lv) - h_new), 3),
                         "best_alternative_action": alt, **flag,
                         "annual_acceleration_cost_aed": round(it.lam_net * 365 * (1 - tm) * it.work_days * ctx.accel, 2)})
    return rows


# ---------------------------------------------------------------------------------- holdout (not run here)
def run_frontier_holdout(candidates_path: Path | str, seeds, variant: str = "central", world: World | None = None,
                         processes=None) -> pd.DataFrame:
    """Evaluate the FROZEN candidate set on holdout seeds — once, after scripts/freeze.py.

    Refuses unless outputs/freeze/manifest.json lists candidates_path with a matching hash; the run is
    logged by gnm.freeze.require_frozen (a second run is refused)."""
    from gnm.freeze import require_frozen, sha256_file, verify
    from gnm.config import ROOT
    p = Path(candidates_path)
    p = p if p.is_absolute() else ROOT / p
    m = verify()
    rel = str(p.relative_to(ROOT))
    if rel not in m["artefacts"] or m["artefacts"][rel] != sha256_file(p):
        raise RuntimeError(f"{rel} is not in the freeze manifest (or changed since freeze)")
    require_frozen("frontier_holdout")
    from gnm.sim.api import load_world
    world = world or load_world(variant)
    cands = load_candidates(p)
    cfg = load_config()["calendar"]
    w0 = cfg["evaluation_weeks"][0] - cfg["warmup_weeks"]
    long = evaluate(world, [pol for _, pol in cands], seeds, variant, weeks=(w0, cfg["evaluation_weeks"][1]),
                    kpi=tuple(cfg["evaluation_weeks"]), processes=processes, allow_holdout=True)
    base_id = json.loads(p.read_text())["base_policy_id"]
    return summarise(long, base_id if base_id in set(long.policy_id) else long.policy_id.iloc[0])
