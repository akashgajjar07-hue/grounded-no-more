"""Paired evaluation of P0 / P1 / P2 on the SELECTION seeds (inventory-policy agent).

Every policy runs on the same Scenario per seed (common random numbers), weeks 78-155 with KPIs
counted from week 104 (26-week warm-up), via :func:`gnm.sim.engine.run_many`, for each calibration
variant (central, low_stress, high_stress). Holdout seeds are never touched here.

Policies per variant: P0 (legacy, quoted data only, identical in every variant); P1 and P2 rebuilt
from that variant's own history (weeks 0-103 of history_seed under P0, i.e. what the planner of that
world would have seen); in the stress variants also ``P1@central`` / ``P2@central`` (the central
policies dropped unchanged into the stressed world) as a robustness check.

Economics: total annual cost = holding + repair + logistics + expedite + AOG penalty. Spare capital
is reported separately and never added (data contract §1/§4). The AOG-penalty sensitivity
(x0.5 / x1 / x2) only rescales the penalty term, because the penalty does not change operations.
"""
from __future__ import annotations

import json
import math
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from gnm import schemas
from gnm.config import HOURS_PER_WEEK, OUTPUTS, load_config, seeds as cfg_seeds
from gnm.contracts import PolicySpec, World
from gnm.policy import forecast_pipeline as fp
from gnm.policy.policies import build_p1, build_p2, write_policy_tables

POL_OUT = OUTPUTS / "policies"
KPI_COLS = [c.name for c in schemas.TABLES["policy_results"].cols if c.name not in ("policy_id", "seed", "split")]
COST_COMPONENTS = ["holding_cost_aed", "repair_cost_aed", "logistics_cost_aed", "expedite_cost_aed", "aog_penalty_aed"]
SUMMARY_KPIS = ["immediate_fill_rate", "aog_hours", "aog_events", "backorder_unit_hours", "spare_capital_aed",
                "total_annual_cost_aed"] + COST_COMPONENTS + ["purchase_spend_aed"]
PAIRS = [("P1", "P0"), ("P2", "P0"), ("P2", "P1")]


# ---------------------------------------------------------------------------------- economics
def total_annual_cost(k) -> float:
    """holding + repair + logistics + expedite + AOG penalty. Capital is never part of it."""
    return float(sum(float(k[c]) for c in COST_COMPONENTS))


def penalty_sensitivity(df: pd.DataFrame, mults=None) -> pd.DataFrame:
    """Total annual cost with the AOG penalty scaled by m (operations unchanged, so recomputed from KPIs)."""
    mults = mults or load_config()["economics"]["aog_penalty_sensitivity"]
    out = df.copy()
    base = out[COST_COMPONENTS].sum(axis=1) - out["aog_penalty_aed"]
    for m in mults:
        out[f"total_cost_pen_x{m:g}"] = base + float(m) * out["aog_penalty_aed"]
    return out


# ---------------------------------------------------------------------------------- statistics
def paired_ci(diff: np.ndarray, level: float = 0.95) -> dict:
    d = np.asarray(diff, float)
    n = d.size
    m = float(d.mean())
    if n < 2:
        return {"mean": m, "ci_lo": float("nan"), "ci_hi": float("nan"), "sd": float("nan"), "n": n}
    sd = float(d.std(ddof=1))
    t = float(stats.t.ppf(0.5 + level / 2, n - 1))
    hw = t * sd / math.sqrt(n)
    return {"mean": m, "ci_lo": m - hw, "ci_hi": m + hw, "sd": sd, "n": n}


def bootstrap_ci(x: np.ndarray, n_boot: int = 2000, seed: int = 0, level: float = 0.95) -> list[float]:
    x = np.asarray(x, float)
    if x.size < 2:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    bs = x[rng.integers(0, x.size, size=(n_boot, x.size))].mean(axis=1)
    a = (1 - level) / 2 * 100
    return [float(v) for v in np.percentile(bs, [a, 100 - a])]


def summarise(df: pd.DataFrame, kpis=SUMMARY_KPIS, pairs=PAIRS, n_boot: int = 2000) -> dict:
    """Per variant: mean + 95 % t-CI per policy and KPI, and paired differences (t-CI + bootstrap)."""
    out = {}
    for v, g in df.groupby("variant", sort=False):
        res = {"n_seeds": int(g.seed.nunique()), "policies": {}, "paired": {}}
        for pid, gp in g.groupby("policy_id", sort=False):
            res["policies"][pid] = {}
            for k in kpis:
                x = gp.sort_values("seed")[k].to_numpy(float)
                ci = paired_ci(x)
                res["policies"][pid][k] = {"mean": ci["mean"], "ci_lo": ci["ci_lo"], "ci_hi": ci["ci_hi"],
                                           "sd": ci["sd"], "n": ci["n"]}
        piv = {k: g.pivot(index="seed", columns="policy_id", values=k) for k in kpis}
        for a, b in pairs + [(p, "P0") for p in g.policy_id.unique() if "@" in p]:
            if a not in g.policy_id.values or b not in g.policy_id.values:
                continue
            key = f"{a}-{b}"
            res["paired"][key] = {}
            for k in kpis:
                d = (piv[k][a] - piv[k][b]).dropna().to_numpy(float)
                ci = paired_ci(d)
                ci["boot_ci"] = bootstrap_ci(d, n_boot=n_boot, seed=zlib.crc32(f"{v}|{key}|{k}".encode()))
                ci["share_seeds_better"] = float(np.mean(d > 0)) if k == "immediate_fill_rate" else float(np.mean(d < 0))
                res["paired"][key][k] = ci
        out[v] = res
    return out


# ---------------------------------------------------------------------------------- detail reduction
def reduce_detail(world: World, res, variant: str, k0w: int, k1w: int) -> tuple[list, list]:
    """Per-station and per-class KPI rows from a detailed RunResult (KPI window only)."""
    k0, k1 = k0w * HOURS_PER_WEEK, (k1w + 1) * HOURS_PER_WEEK
    ann = 52.0 / (k1w - k0w + 1)
    cls = world.parts.set_index("pn").part_class
    rq = res.requests
    rq = rq[(rq.need_h >= k0) & (rq.need_h < k1)]
    rq = rq.assign(part_class=rq.pn.map(cls), imm_qty=rq.qty * rq.immediate_fill.astype(bool),
                   aog_d0=rq.deadline_class.eq("D0"))
    ev = res.aog_events
    ov = (np.minimum(ev.end_h.to_numpy(), k1) - np.maximum(ev.start_h.to_numpy(), k0)).clip(0)
    ev = ev.assign(win_h=ov, part_class=ev.pns.str.split(";").str[0].map(cls),
                   started=(ev.start_h >= k0) & (ev.start_h < k1))
    base = {"variant": variant, "policy_id": res.policy_id, "seed": res.seed}
    srows, crows = [], []
    for st in world.stations.station:
        r = rq[rq.station == st]
        e = ev[ev.station == st]
        srows.append({**base, "station": st, "requests": int(len(r)), "qty": int(r.qty.sum()),
                      "immediate_fill_rate": float(r.imm_qty.sum() / r.qty.sum()) if r.qty.sum() else np.nan,
                      "rotable_fill_rate": float(r[r.part_class == "R"].immediate_fill.astype(bool).mean())
                      if (r.part_class == "R").any() else np.nan,
                      "aog_hours": float(e.win_h.sum() * ann), "aog_events": int(e.started.sum()),
                      "aog_hours_D0": float(e[e.trigger == "D0_no_stock"].win_h.sum() * ann)})
    for c in ("C", "E", "R"):
        r = rq[rq.part_class == c]
        e = ev[ev.part_class == c]
        crows.append({**base, "part_class": c, "requests": int(len(r)), "qty": int(r.qty.sum()),
                      "immediate_fill_rate": float(r.imm_qty.sum() / r.qty.sum()) if r.qty.sum() else np.nan,
                      "aog_hours": float(e.win_h.sum() * ann), "aog_events": int(e.started.sum())})
    return srows, crows


def request_signature(res) -> pd.DataFrame:
    """Exogenous request columns (must be identical across policies for one seed)."""
    return res.requests[["request_id", "pn", "station", "tail", "need_h", "known_h", "qty", "deadline_class",
                         "source"]].reset_index(drop=True)


# ---------------------------------------------------------------------------------- policies per variant
def variant_history(world: World, variant: str) -> dict:
    """History tables (weeks 0-103, history_seed, P0) for a calibration variant. Central = the
    on-disk history; other variants are re-run in memory from the public API (never weeks >= 104)."""
    if variant == "central":
        return fp.load_history()
    from gnm.sim.api import load_or_generate_scenario
    from gnm.sim.baseline import build_p0
    from gnm.sim.engine import run_policy
    cfg = load_config()
    w0, w1 = cfg["calendar"]["history_weeks"]
    assert w1 < 104
    sc = load_or_generate_scenario(int(cfg["seeds"]["history_seed"]), w0, w1, variant=variant)
    res = run_policy(world, sc, build_p0(world), w0, w1)
    return fp.history_from_run(world, sc, res)


def policies_for_variant(world: World, variant: str, champions: pd.DataFrame, central: dict | None = None) -> dict:
    from gnm.sim.baseline import build_p0
    hist = variant_history(world, variant)
    ff = fp.final_forecasts(hist, world, champions)
    pols = {"P0": build_p0(world), "P1": build_p1(world, ff), "P2": build_p2(world, ff)}
    if central is not None and variant != "central":
        for k in ("P1", "P2"):
            c = central[k]
            pols[f"{k}@central"] = PolicySpec(**{**c.__dict__, "policy_id": f"{k}@central",
                                                 "label": c.label + " (central history)"})
    return {"policies": pols, "forecasts": ff}


# ---------------------------------------------------------------------------------- runner
def run_variant(world: World, variant: str, policies: dict, seeds, ecfg: dict, processes=None,
                check_pairing: bool = True) -> dict:
    from gnm.sim.engine import run_many
    pl = list(policies.values())
    kpi_rows, srows, crows = [], [], []
    batch = int(ecfg.get("seeds_per_batch", 5))
    seeds = list(seeds)
    for i in range(0, len(seeds), batch):
        chunk = seeds[i:i + batch]
        scs = [(s, ecfg["week_from"], ecfg["week_to"], True, variant) for s in chunk]
        outs = run_many(world, scs, pl, ecfg["kpi_from_week"], ecfg["kpi_to_week"], processes=processes, detail=True)
        for j, s in enumerate(chunk):
            group = outs[j * len(pl):(j + 1) * len(pl)]
            if check_pairing:
                sig0 = request_signature(group[0])
                for r in group[1:]:
                    if not sig0.equals(request_signature(r)):
                        raise AssertionError(f"requests differ across policies for seed {s} ({variant})")
            for r in group:
                assert r.seed == s
                kpi_rows.append({"policy_id": r.policy_id, "seed": int(s), "split": "selection", **r.kpis,
                                 "variant": variant})
                a, b = reduce_detail(world, r, variant, ecfg["kpi_from_week"], ecfg["kpi_to_week"])
                srows += a
                crows += b
        del outs
    return {"kpis": pd.DataFrame(kpi_rows), "stations": pd.DataFrame(srows), "classes": pd.DataFrame(crows)}


def _agg_breakdown(df: pd.DataFrame, key: str) -> list:
    rows = []
    for (v, pid, k), g in df.groupby(["variant", "policy_id", key], sort=False):
        row = {"variant": v, "policy_id": pid, key: k}
        for m in ("immediate_fill_rate", "aog_hours", "aog_events") + (("rotable_fill_rate", "aog_hours_D0")
                                                                        if key == "station" else ()):
            x = g[m].dropna().to_numpy(float)
            ci = paired_ci(x) if x.size else {"mean": np.nan, "ci_lo": np.nan, "ci_hi": np.nan}
            row[m] = ci["mean"]
            row[f"{m}_ci"] = [ci["ci_lo"], ci["ci_hi"]]
        rows.append(row)
    return rows


def _paired_breakdown(df: pd.DataFrame, key: str, metric: str, pairs=PAIRS) -> list:
    rows = []
    for (v, k), g in df.groupby(["variant", key], sort=False):
        piv = g.pivot(index="seed", columns="policy_id", values=metric)
        for a, b in pairs:
            if a in piv and b in piv:
                d = (piv[a] - piv[b]).dropna().to_numpy(float)
                ci = paired_ci(d)
                rows.append({"variant": v, key: k, "pair": f"{a}-{b}", "metric": metric, "mean": ci["mean"],
                             "ci_lo": ci["ci_lo"], "ci_hi": ci["ci_hi"]})
    return rows


def evaluate(variants=None, seeds=None, processes=None, out_dir: Path | None = None) -> dict:
    """Full selection evaluation. Writes outputs/policies/selection_results.parquet,
    selection_station_kpis.parquet, selection_class_kpis.parquet, selection_summary.json, and the
    per-variant policy parameter tables."""
    t0 = time.time()
    pcfg = fp.load_policy_config()
    ecfg = pcfg["evaluation"]
    variants = variants or ecfg["variants"]
    seeds = list(seeds or cfg_seeds()["selection"])
    hold = set(cfg_seeds()["holdout"])
    if set(seeds) & hold:
        raise ValueError("holdout seeds must not be used in the selection evaluation")
    out = Path(out_dir or POL_OUT)
    out.mkdir(parents=True, exist_ok=True)
    from gnm.sim.api import load_world
    champs = pd.read_csv(fp.FC_OUT / "champions.csv")
    world = load_world("central")
    central = None
    kp, st, cl, pol_info = [], [], [], {}
    for v in variants:
        wv = load_world(v)
        pv = policies_for_variant(wv, v, champs, central)
        if v == "central":
            central = pv["policies"]
        vdir = out if v == "central" else out / "variants" / v
        info = write_policy_tables(list(pv["policies"].values()), wv, vdir)
        pol_info[v] = {p["policy_id"]: {"capital_at_target_aed": p["capital_at_target_aed"],
                                        "outstation_rotable_units": p["outstation_rotable_units"]}
                       for p in info["policies"]}
        r = run_variant(wv, v, pv["policies"], seeds, ecfg, processes=processes)
        kp.append(r["kpis"])
        st.append(r["stations"])
        cl.append(r["classes"])
    res = pd.concat(kp, ignore_index=True)
    stations = pd.concat(st, ignore_index=True)
    classes = pd.concat(cl, ignore_index=True)
    cols = schemas.TABLES["policy_results"].colnames + ["variant"]
    res = res[cols]
    for v, g in res.groupby("variant"):
        errs = schemas.validate_table("policy_results", g)
        if errs:
            raise ValueError(errs)
    res.to_parquet(out / "selection_results.parquet", index=False)
    stations.to_parquet(out / "selection_station_kpis.parquet", index=False)
    classes.to_parquet(out / "selection_class_kpis.parquet", index=False)
    ext = penalty_sensitivity(res)
    ext["total_annual_cost_aed"] = ext[COST_COMPONENTS].sum(axis=1)
    mults = load_config()["economics"]["aog_penalty_sensitivity"]
    kpis = SUMMARY_KPIS + [f"total_cost_pen_x{m:g}" for m in mults]
    summary = {
        "provenance": "SIMULATED",
        "split": "selection",
        "seeds": seeds, "weeks": [ecfg["week_from"], ecfg["week_to"]],
        "kpi_weeks": [ecfg["kpi_from_week"], ecfg["kpi_to_week"]],
        "ci_method": "95% paired t over seeds (n-1 df); bootstrap percentile CI over seeds as a check",
        "total_cost_definition": "holding + repair + logistics + expedite + AOG penalty (capital excluded)",
        "aog_penalty_multipliers": mults,
        "variants": summarise(ext, kpis=kpis, n_boot=int(ecfg["n_boot"])),
        "by_station": _agg_breakdown(stations, "station"),
        "by_class": _agg_breakdown(classes, "part_class"),
        "paired_by_station": _paired_breakdown(stations, "station", "aog_hours")
        + _paired_breakdown(stations, "station", "immediate_fill_rate"),
        "paired_by_class": _paired_breakdown(classes, "part_class", "aog_hours")
        + _paired_breakdown(classes, "part_class", "immediate_fill_rate"),
        "policy_capital_at_target": pol_info,
        "runtime_s": round(time.time() - t0, 1),
    }
    (out / "selection_summary.json").write_text(json.dumps(summary, indent=2, default=_json_default) + "\n")
    return summary


def palm_vs_sim(world: World, policy: PolicySpec, forecasts: pd.DataFrame, seeds, variant: str = "central",
                ecfg: dict | None = None, processes=None) -> pd.DataFrame:
    """Rotable float validation: analytic Palm availability / EBO (the P1 sizing assumption) against
    the simulated immediate fill and time-average backorders per rotable x station, pooled over seeds.

    Also reports an alternative analytic availability with the outstation resupplied from the hub
    (routine transit + expected hub backorder delay), which is how the engine actually replenishes."""
    from gnm.policy import analytic
    from gnm.sim.engine import run_many
    ecfg = ecfg or fp.load_policy_config()["evaluation"]
    k0w, k1w = ecfg["kpi_from_week"], ecfg["kpi_to_week"]
    k0, k1 = k0w * HOURS_PER_WEEK, (k1w + 1) * HOURS_PER_WEEK
    hub = world.cfg["network"]["hub"]
    rot = forecasts[forecasts.part_class == "R"].copy()
    from gnm.policy.policies import pipeline_units_at_start
    bs = policy.stock_params.set_index(["pn", "station"]).base_stock
    seeded = pipeline_units_at_start(world)
    acc = {}
    seeds = list(seeds)
    for i in range(0, len(seeds), int(ecfg.get("seeds_per_batch", 5))):
        chunk = seeds[i:i + int(ecfg.get("seeds_per_batch", 5))]
        outs = run_many(world, [(s, ecfg["week_from"], ecfg["week_to"], True, variant) for s in chunk], [policy],
                        k0w, k1w, processes=processes, detail=True)
        for r in outs:
            rq = r.requests
            rq = rq[(rq.need_h >= k0) & (rq.need_h < k1) & rq.pn.isin(rot.pn)]
            g = rq.groupby(["pn", "station"]).agg(n=("request_id", "size"),
                                                  imm=("immediate_fill", lambda x: int(x.astype(bool).sum())))
            sn = r.stock_snapshots
            sn = sn[(sn.week >= k0w) & (sn.week <= k1w) & sn.pn.isin(rot.pn)]
            sg = sn.groupby(["pn", "station"]).agg(bo=("backorders", "mean"), oh=("on_hand", "mean"))
            for key in set(g.index) | set(sg.index):
                a = acc.setdefault(key, {"n": 0, "imm": 0, "bo": [], "oh": []})
                if key in g.index:
                    a["n"] += int(g.loc[key, "n"])
                    a["imm"] += int(g.loc[key, "imm"])
                if key in sg.index:
                    a["bo"].append(float(sg.loc[key, "bo"]))
                    a["oh"].append(float(sg.loc[key, "oh"]))
        del outs
    rows = []
    for pn, g in rot.groupby("pn"):
        lam_net = float(g.removal_rate_day.sum())
        mu_net = float((g.removal_rate_day * g.pipeline_days).sum())
        S_h = int(bs.get((pn, hub), 0)) + seeded.get(pn, 0)
        wait = analytic.expected_wait_days(S_h, mu_net, lam_net) if lam_net > 0 else 0.0
        for r in g.itertuples(index=False):
            # total spares = serviceable target + (at the hub) the units seeded in the repair loop
            S = int(bs.get((pn, r.station), 0)) + (seeded.get(pn, 0) if r.station == hub else 0)
            mu = float(r.removal_rate_day) * float(r.pipeline_days)
            a = acc.get((pn, r.station), {"n": 0, "imm": 0, "bo": [], "oh": []})
            mu_net_res = float(r.removal_rate_day) * (float(r.transit_d) + wait) if r.station != hub else mu
            rows.append({"pn": pn, "station": r.station, "deadline_class": r.deadline_class,
                         "base_stock": int(bs.get((pn, r.station), 0)), "total_spares": S,
                         "rate_per_year": float(r.removal_rate_day) * 365.0, "pipeline_days": float(r.pipeline_days),
                         "pipeline_mean": mu, "palm_availability": analytic.availability(S, mu) if S > 0 else 0.0,
                         "palm_ebo": analytic.ebo(S, mu),
                         "palm_availability_hub_resupply": analytic.availability(S, mu_net_res) if S > 0 else 0.0,
                         "sim_requests": a["n"], "sim_immediate_fill": a["imm"] / a["n"] if a["n"] else np.nan,
                         "sim_avg_backorders": float(np.mean(a["bo"])) if a["bo"] else np.nan,
                         "sim_avg_on_hand": float(np.mean(a["oh"])) if a["oh"] else np.nan,
                         "n_seeds": len(seeds)})
    out = pd.DataFrame(rows)
    out["fill_gap_sim_minus_palm"] = out.sim_immediate_fill - out.palm_availability
    return out


def threshold_sensitivity(world: World, forecasts: pd.DataFrame, thetas, seeds, variant: str = "central",
                          processes=None) -> pd.DataFrame:
    """P2 with alternative positioning thresholds (sensitivity only; the adopted threshold is fixed in
    config/policy.yaml and was not chosen from this table). Paired against P0 on the same seeds."""
    import copy
    from gnm.sim.baseline import build_p0
    from gnm.sim.engine import run_many
    ecfg = fp.load_policy_config()["evaluation"]
    pols = [build_p0(world)]
    for th in thetas:
        pc = copy.deepcopy(fp.load_policy_config())
        pc["p2_network"]["positioning_threshold_aed_per_aed_year"] = float(th)
        sp = build_p2(world, forecasts, pc)
        sp.policy_id = f"P2_theta{th:g}"
        pols.append(sp)
    outs = run_many(world, [(s, ecfg["week_from"], ecfg["week_to"], True, variant) for s in seeds], pols,
                    ecfg["kpi_from_week"], ecfg["kpi_to_week"], processes=processes, detail=False)
    df = pd.DataFrame([{"policy_id": r.policy_id, "seed": r.seed, **r.kpis} for r in outs])
    df["total_annual_cost_aed"] = df[COST_COMPONENTS].sum(axis=1)
    rows = []
    p0 = df[df.policy_id == "P0"].set_index("seed")
    for pid, g in df.groupby("policy_id", sort=False):
        g = g.set_index("seed")
        row = {"policy_id": pid}
        for k in ("immediate_fill_rate", "aog_hours", "spare_capital_aed", "total_annual_cost_aed"):
            ci = paired_ci(g[k].to_numpy(float))
            row[k] = ci["mean"]
            row[f"{k}_ci"] = [ci["ci_lo"], ci["ci_hi"]]
            if pid != "P0":
                dci = paired_ci((g[k] - p0.loc[g.index, k]).to_numpy(float))
                row[f"d_{k}_vs_P0"] = dci["mean"]
                row[f"d_{k}_vs_P0_ci"] = [dci["ci_lo"], dci["ci_hi"]]
        rows.append(row)
    return pd.DataFrame(rows)


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


__all__ = ["evaluate", "run_variant", "summarise", "paired_ci", "bootstrap_ci", "total_annual_cost",
           "penalty_sensitivity", "reduce_detail", "palm_vs_sim", "threshold_sensitivity", "policies_for_variant", "variant_history", "request_signature"]
