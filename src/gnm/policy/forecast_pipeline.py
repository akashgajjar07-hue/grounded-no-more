"""Forecasting integration for the inventory policies (inventory-policy agent).

Builds, from the PUBLIC history tables only (``data/processed/history``, weeks 0-103):

* the weekly demand matrix (pn x week) and its per-station version (pn, station) x week,
* the component exposure matrix (installed qty x FH or FC per week, from flight_exposure x
  applicability) and its per-arrival-station version,
* the rolling-origin forecast evaluation, leaderboard, champions and stock-based evaluation,
* the final per-PN, per-station forecasts that feed P1/P2 (weekly rates, lead-time-demand
  moments and distribution kind, estimated lead times, rotable pipeline times).

Leakage rules: this module never imports the simulator's generator/truth modules and never
opens the hidden truth directory (tests/test_leakage.py). Every function that takes an
``origin`` uses only events strictly before ``origin`` (week < origin, receipts and returns
before the origin hour), which tests/test_policy_forecast.py checks by perturbation.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from gnm.config import HOURS_PER_WEEK, OUTPUTS, PROCESSED, ROOT, load_config
from gnm.forecasting.classify import build_part_attributes
from gnm.forecasting.evaluate import (aggregate_errors, base_stock_policy, default_origins, freeze_champions,
                                      rolling_origin_evaluate, select_champions, stock_based_eval)
from gnm.forecasting.methods import METHODS, fit_predict

POLICY_CONFIG = ROOT / "config" / "policy.yaml"
HISTORY_DIR = PROCESSED / "history"
FC_OUT = OUTPUTS / "forecasting"
HISTORY_NEEDED = ["part_master", "part_applicability", "aircraft_master", "station_master", "flight_exposure",
                  "material_requests", "removal_events", "purchase_orders", "repair_orders", "transfers"]
DRIVER_COL = {"FH": "fh", "FC": "fc", "FC_usage": "fc", "none": None}
STOCK_EVAL_METHODS = ["ma", "croston", "sba", "tsb", "imapa", "bootstrap", "reliability"]


@lru_cache(maxsize=1)
def load_policy_config() -> dict:
    with open(POLICY_CONFIG) as f:
        return yaml.safe_load(f)


def load_history(hist_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Read the public history tables needed by the pipeline."""
    d = Path(hist_dir or HISTORY_DIR)
    return {t: pd.read_parquet(d / f"{t}.parquet") for t in HISTORY_NEEDED}


def history_from_run(world, scenario, result) -> dict[str, pd.DataFrame]:
    """The same dict built in memory from a P0 run (used for the calibration-variant histories)."""
    from gnm.sim.api import history_tables
    t = history_tables(world, scenario, result)
    return {k: t[k] for k in HISTORY_NEEDED}


def truncate_history(hist: dict, origin: int) -> dict:
    """Keep only what a planner standing at ``origin`` (week) could know.

    Requests/removals/flights with week < origin; POs ordered before the origin with receipts
    after it set to open; ROs with shop_in before the origin with later outcomes set to open;
    transfers shipped before the origin with arrival before it."""
    oh = origin * HOURS_PER_WEEK
    h = dict(hist)
    h["material_requests"] = hist["material_requests"][hist["material_requests"].week < origin].copy()
    h["removal_events"] = hist["removal_events"][hist["removal_events"].week < origin].copy()
    h["flight_exposure"] = hist["flight_exposure"][hist["flight_exposure"].week < origin].copy()
    po = hist["purchase_orders"]
    po = po[po.order_h < oh].copy()
    rec = po.receipt_h.astype("Float64")
    po["receipt_h"] = rec.where(rec < oh).astype("Int64")
    h["purchase_orders"] = po
    ro = hist["repair_orders"]
    ro = ro[ro.shop_in_h < oh].copy()
    ret = ro.return_h.astype("Float64")
    ro["return_h"] = ret.where(ret < oh).astype("Int64")
    st = ro.start_h.astype("Float64")
    ro["start_h"] = st.where(st < oh).astype("Int64")
    # a condemnation is known once decided; the decision time is not in the table, so treat
    # condemnations of units that entered the shop within the last 3 days as not yet known
    ro["condemned"] = ro.condemned & (ro.shop_in_h < oh - 72)
    h["repair_orders"] = ro
    tr = hist["transfers"]
    h["transfers"] = tr[tr.arrive_h < oh].copy()
    return h


# ---------------------------------------------------------------------------------- matrices
def weekly_demand(requests: pd.DataFrame, pns, week_from: int, week_to: int) -> pd.DataFrame:
    """pn x week (inclusive range) matrix of requested qty (unconstrained demand)."""
    weeks = list(range(week_from, week_to + 1))
    r = requests[(requests.week >= week_from) & (requests.week <= week_to)]
    m = r.groupby(["pn", "week"]).qty.sum().unstack(fill_value=0)
    return m.reindex(index=list(pns), columns=weeks, fill_value=0).astype(float)


def station_weekly_demand(requests: pd.DataFrame, pns, stations, week_from: int, week_to: int) -> pd.DataFrame:
    """(pn, station) x week matrix of requested qty."""
    weeks = list(range(week_from, week_to + 1))
    r = requests[(requests.week >= week_from) & (requests.week <= week_to)]
    m = r.groupby(["pn", "station", "week"]).qty.sum().unstack(fill_value=0)
    idx = pd.MultiIndex.from_product([list(pns), list(stations)], names=["pn", "station"])
    return m.reindex(index=idx, columns=weeks, fill_value=0).astype(float)


def _arch_exposure(flights: pd.DataFrame, aircraft: pd.DataFrame, weeks, by_station: bool) -> pd.DataFrame:
    arch = dict(zip(aircraft["tail"], aircraft["archetype"]))
    fl = flights.assign(archetype=flights["tail"].map(arch))
    keys = ["archetype", "arr_station", "week"] if by_station else ["archetype", "week"]
    g = fl.groupby(keys)[["fh", "fc"]].sum()
    return g


def exposure_matrix(flights, aircraft, applicability, parts, week_from: int, week_to: int) -> pd.DataFrame:
    """pn x week component exposure in the part's driver unit: sum over applicable archetypes of
    installed qty x (FH or FC) flown that week. Consumables (driver FC_usage) use qty 1 x FC, in
    line with the quoted 'FC per unit consumed per aircraft'."""
    weeks = list(range(week_from, week_to + 1))
    g = _arch_exposure(flights, aircraft, weeks, by_station=False)
    pm = parts.set_index("pn")
    out = pd.DataFrame(0.0, index=pm.index, columns=weeks)
    for a in applicability.itertuples(index=False):
        col = DRIVER_COL.get(pm.loc[a.pn, "driver"])
        if col is None or a.archetype not in g.index.get_level_values(0):
            continue
        s = g.loc[a.archetype][col].reindex(weeks, fill_value=0.0)
        out.loc[a.pn] += float(a.qty_per_aircraft) * s.to_numpy()
    return out


def station_exposure_matrix(flights, aircraft, applicability, parts, stations, week_from: int,
                            week_to: int) -> pd.DataFrame:
    """(pn, arrival station) x week exposure (legs attributed to their arrival station, where
    removals and line usage are found)."""
    weeks = list(range(week_from, week_to + 1))
    g = _arch_exposure(flights, aircraft, weeks, by_station=True)
    pm = parts.set_index("pn")
    idx = pd.MultiIndex.from_product([list(pm.index), list(stations)], names=["pn", "station"])
    out = pd.DataFrame(0.0, index=idx, columns=weeks)
    archs = set(g.index.get_level_values(0))
    for a in applicability.itertuples(index=False):
        col = DRIVER_COL.get(pm.loc[a.pn, "driver"])
        if col is None or a.archetype not in archs:
            continue
        ga = g.loc[a.archetype][col]
        for st in stations:
            if st in ga.index.get_level_values(0):
                s = ga.loc[st].reindex(weeks, fill_value=0.0)
                out.loc[(a.pn, st)] += float(a.qty_per_aircraft) * s.to_numpy()
    return out


def build_inputs(hist: dict, origin: int = 104, train_weeks=(0, 77)) -> dict:
    """Demand / exposure matrices for weeks 0..origin-1 plus the part-attribute frame
    (demand classes and ABC on ``train_weeks``, the same basis as the frozen champions)."""
    h = truncate_history(hist, origin)
    pm = h["part_master"]
    pns = pm.pn.tolist()
    stations = h["station_master"].station.tolist()
    w1 = origin - 1
    demand = weekly_demand(h["material_requests"], pns, 0, w1)
    expo = exposure_matrix(h["flight_exposure"], h["aircraft_master"], h["part_applicability"], pm, 0, w1)
    sdem = station_weekly_demand(h["material_requests"], pns, stations, 0, w1)
    sexpo = station_exposure_matrix(h["flight_exposure"], h["aircraft_master"], h["part_applicability"], pm,
                                    stations, 0, w1)
    parts = build_part_attributes(demand, pm, train_weeks=train_weeks)
    return {"hist": h, "origin": origin, "pns": pns, "stations": stations, "demand": demand, "exposure": expo,
            "station_demand": sdem, "station_exposure": sexpo, "parts": parts}


# ---------------------------------------------------------------------------------- evaluation
def run_forecast_evaluation(inputs: dict, origins=None, seed: int = 0) -> dict:
    """Rolling-origin evaluation of all methods (reliability with the vendor-quoted MTBUR prior)
    on the selection origins; leaderboard with bootstrap CIs; champions per cell."""
    pc = load_policy_config()["forecast"]
    origins = origins or default_origins()
    err = rolling_origin_evaluate(inputs["demand"], inputs["parts"], exposure=inputs["exposure"], origins=origins,
                                  method_kwargs={"reliability": {"prior_strength": pc["reliability_prior_strength"]}},
                                  seed=seed)
    board = aggregate_errors(err, by=("demand_class", "part_class"))
    board_cls = aggregate_errors(err, by=("part_class",))
    champs = select_champions(err)
    return {"errors": err, "leaderboard": board, "leaderboard_by_class": board_cls, "champions": champs}


def service_level(deadline: str) -> float:
    """Cycle-service / fill target by rectification window: config service_targets (D0/D3/D10); the v2
    class NONE (servicing fluids, never an AOG driver) uses config/policy.yaml service_target_none."""
    st = load_config()["service_targets"]
    if deadline in st:
        return float(st[deadline])
    return float(load_policy_config()["service_target_none"])


_service = service_level


def run_stock_eval(hist: dict, origins=(78, 86), methods=STOCK_EVAL_METHODS, end_week: int = 103) -> pd.DataFrame:
    """Stock-based evaluation (forecasting.evaluate.stock_based_eval) on selection origins.

    For each origin o: forecasts use weeks < o only (h = protection interval in weeks: quoted
    purchase lead time for C/E, quoted repair pipeline for R), base-stock S at the deadline-class
    service target, simulated on the realised demand of weeks o..end_week."""
    rows = []
    wcfg = load_config()
    for o in origins:
        inp = build_inputs(hist, origin=o)
        pm = inp["hist"]["part_master"].set_index("pn")
        full = weekly_demand(hist["material_requests"], inp["pns"], 0, end_week)
        fut = full[[w for w in full.columns if o <= w <= end_week]]
        D = inp["demand"]
        E = inp["exposure"]
        e_plan = E.iloc[:, -52:].mean(axis=1)
        L = {}
        for pn, p in pm.iterrows():
            if p.part_class == "R":
                shop = wcfg["repair_shops"]["vendor_transit_days_from_auh"].get(p.repair_shop, 0)
                days = float(p.repair_tat_mean_d) + 2 * float(shop)
            else:
                days = float(p.lead_time_mean_d)
            L[pn] = max(1, int(math.ceil(days / 7.0)))
        ctx = {pn: {"service_level": _service(pm.loc[pn, "deadline_class"])} for pn in pm.index}
        for m in methods:
            fcs = {}
            for i, pn in enumerate(D.index):
                h = L[pn]
                kw = {"seed": 1000 + 7919 * i + o}
                if m == "reliability":
                    kw.update(exposure_train=E.loc[pn].to_numpy(), exposure_future=np.full(h, e_plan[pn]),
                              mtbur_prior=float(pm.loc[pn, "mtbur_quoted"]) if pd.notna(pm.loc[pn, "mtbur_quoted"]) else None)
                fcs[pn] = fit_predict(m, D.loc[pn].to_numpy(), h, **kw)
            res = stock_based_eval(fcs, fut, base_stock_policy(), pd.Series(L),
                                   unit_cost=pm.unit_cost_aed, ctx_by_pn=ctx)
            res["origin"] = o
            res["demand_units"] = res.pn.map(fut.sum(axis=1))
            rows.append(res)
    out = pd.concat(rows, ignore_index=True)
    out["part_class"] = out.pn.map(hist["part_master"].set_index("pn").part_class)
    return out


def summarise_stock_eval(se: pd.DataFrame) -> pd.DataFrame:
    """Per method x part class: qty-weighted fill rate, backorder units, mean stock value (capital)."""
    se = se.assign(filled_units=se.fill_rate.fillna(0) * se.demand_units)
    g = se.groupby(["part_class", "method"])
    out = g.agg(n_part_origins=("pn", "size"), demand_units=("demand_units", "sum"),
                filled_units=("filled_units", "sum"), backorder_units=("backorder_units", "sum"),
                avg_stock_value_aed=("avg_stock_value", "sum"), n_origins=("origin", "nunique")).reset_index()
    out["fill_rate"] = out.filled_units / out.demand_units
    out["avg_stock_value_aed"] = out.avg_stock_value_aed / out.n_origins     # capital per origin (all parts)
    out["backorder_units"] = out.backorder_units / out.n_origins
    return out[["part_class", "method", "n_part_origins", "fill_rate", "backorder_units", "avg_stock_value_aed"]]


# ---------------------------------------------------------------------------------- lead times
def estimate_lead_times(pos: pd.DataFrame, parts: pd.DataFrame, origin: int) -> pd.DataFrame:
    """Recency-weighted purchase lead time per PN from history PO receipts (before ``origin``).

    weight = 0.5 ** (age_weeks / half_life) on the order week; the quoted mean enters as
    ``prior_weight_orders`` observations of full weight; open POs older than the current estimate
    contribute their elapsed age (a lower bound: right-censoring)."""
    lc = load_policy_config()["lead_time"]
    oh = origin * HOURS_PER_WEEK
    po = pos[(pos.reason.isin(lc["reasons"])) & (pos.order_h < oh)].copy()
    rec = po.receipt_h.astype("Float64")
    po["done"] = rec.notna() & (rec < oh)
    po["lt_d"] = np.where(po.done, (rec.fillna(0).astype(float) - po.order_h) / 24.0, np.nan)
    po["age_w"] = (oh - po.order_h) / HOURS_PER_WEEK
    po["w"] = 0.5 ** (po.age_w / float(lc["half_life_weeks"]))
    rows = []
    pm = parts.set_index("pn") if "pn" in parts.columns else parts
    w0 = float(lc["prior_weight_orders"])
    for pn, p in pm.iterrows():
        q = float(p.lead_time_mean_d)
        cv = float(p.lead_time_cv) if pd.notna(p.lead_time_cv) else 0.3
        g = po[po.pn == pn]
        d = g[g.done]
        vals = list(d.lt_d.astype(float))
        ws = list(d.w.astype(float))
        num = w0 * q + float(np.dot(ws, vals)) if vals else w0 * q
        den = w0 + float(np.sum(ws)) if vals else w0
        est = num / den
        n_cens = 0
        if lc.get("use_open_po_censoring", True):
            op = g[~g.done]
            for r in op.itertuples(index=False):
                age = (oh - r.order_h) / 24.0
                if age > est:
                    vals.append(age)
                    ws.append(float(r.w))
                    num += float(r.w) * age
                    den += float(r.w)
                    est = num / den
                    n_cens += 1
        # supplier-change (regime shift) check: if the last ``shift_last_n`` observations (receipts, or
        # open POs already older than the estimate) all exceed shift_factor x the estimate from the
        # older data, re-baseline on those recent observations only.
        shifted = False
        nlast = int(lc.get("shift_last_n", 2))
        obs = [(float(r.order_h), float(r.lt_d), True) for r in d.itertuples(index=False)]
        if lc.get("use_open_po_censoring", True):
            obs += [(float(r.order_h), (oh - r.order_h) / 24.0, False) for r in g[~g.done].itertuples(index=False)
                    if (oh - r.order_h) / 24.0 > est]
        obs.sort()
        if nlast > 0 and len(obs) > nlast:
            recent = [o[1] for o in obs[-nlast:]]
            older = [o[1] for o in obs[:-nlast]]
            base = (w0 * q + sum(older)) / (w0 + len(older))
            if min(recent) > float(lc.get("shift_factor", 1.5)) * base:
                est = float(np.mean(recent))
                shifted = True
        if len(vals) >= 3 and not shifted:
            v = np.asarray(vals)
            wv = np.asarray(ws)
            sd_emp = math.sqrt(float(np.dot(wv, (v - est) ** 2) / wv.sum()))
        else:
            sd_emp = 0.0
        sd = max(cv * est, sd_emp)
        rows.append({"pn": pn, "lt_quoted_d": q, "lt_est_d": est, "lt_sd_d": sd, "n_receipts": int(d.shape[0]),
                     "n_open_censored": n_cens, "regime_shift": shifted,
                     "lt_recent_mean_d": float(np.average(d.lt_d, weights=d.w)) if len(d) else np.nan})
    return pd.DataFrame(rows).set_index("pn")


def routine_transit(transfers: pd.DataFrame, stations, hub: str) -> pd.DataFrame:
    """Observed hub -> outstation routine transit (days): mean, sd per destination."""
    t = transfers[(transfers.kind == "routine") & (transfers.from_station == hub)]
    t = t.assign(d=(t.arrive_h - t.ship_h) / 24.0)
    g = t.groupby("to_station").d.agg(["mean", "std", "size"])
    cfg = load_config()["network"]["routine_transport_days"]
    rows = []
    for st in stations:
        if st == hub:
            continue
        if st in g.index and g.loc[st, "size"] >= 5:
            rows.append((st, float(g.loc[st, "mean"]), float(g.loc[st, "std"]), int(g.loc[st, "size"])))
        else:
            rows.append((st, float(cfg["mean"]), float(cfg["sd"]), int(g.loc[st, "size"]) if st in g.index else 0))
    return pd.DataFrame(rows, columns=["station", "transit_mean_d", "transit_sd_d", "n"]).set_index("station")


# ---------------------------------------------------------------------------------- rotable pipeline
def rotable_pipeline(hist: dict, world, origin: int, lead_times: pd.DataFrame) -> pd.DataFrame:
    """Per rotable PN: repair-pipeline days as a planner estimates them from history ROs.

    T_repair(station) = observed transport to the shop (hub / outstation removals, pooled by shop)
                        + quoted shop TAT + vendor return transit + observed lateness vs quoted due
    (lateness per PN shrunk towards the shop mean with 3 pseudo-ROs; open ROs past their quoted due
    are censored at the origin). Condemnation probability p is shrunk towards the quoted rate; a
    condemned unit is replaced by a PO, so T_eff = (1-p) T_repair + p (transport + purchase LT)."""
    rc = load_policy_config()["rotable"]
    oh = origin * HOURS_PER_WEEK
    hub = world.cfg["network"]["hub"]
    pm = hist["part_master"].set_index("pn")
    ro = hist["repair_orders"]
    ro = ro[(ro.shop_in_h < oh) & ro.removal_id.notna()].copy()
    rem_st = hist["removal_events"].set_index("removal_id").station
    ro["rem_station"] = ro.removal_id.astype("Int64").map(rem_st)
    ro["at_hub"] = ro.rem_station == hub
    ro["to_shop_d"] = (ro.shop_in_h - ro.removed_h) / 24.0
    ret = ro.return_h.astype("Float64")
    ro["returned"] = ret.notna() & (ret < oh)
    ro["late_d"] = np.where(ro.returned, (ret.fillna(0).astype(float) - ro.quoted_due_h) / 24.0, np.nan)
    openo = (~ro.returned) & (~ro.condemned) & (ro.quoted_due_h < oh)
    ro.loc[openo, "late_d"] = (oh - ro.loc[openo, "quoted_due_h"]) / 24.0       # censored lower bound
    shops = world.repair_shops
    trans = ro.groupby(["shop", "at_hub"]).to_shop_d.mean()
    shop_late = ro.groupby("shop").late_d.mean()
    rows = []
    for pn, p in pm[pm.part_class == "R"].iterrows():
        sh = p.repair_shop
        tr_back = float(shops[sh]["transit_days"])
        t_hub = float(trans.get((sh, True), tr_back))
        ret_mean = world.cfg["network"]["removed_unit_return_days"]["mean"]
        t_out = float(trans.get((sh, False), tr_back + ret_mean))
        g = ro[ro.pn == pn]
        lv = g.late_d.dropna()
        k = 3.0
        prior_late = float(shop_late.get(sh, 0.0)) if pd.notna(shop_late.get(sh, np.nan)) else 0.0
        late = (lv.sum() + k * prior_late) / (len(lv) + k)
        resolved = g[g.returned | g.condemned]
        qc = float(p.condemnation_prob_quoted) if pd.notna(p.condemnation_prob_quoted) else 0.03
        w = float(rc["condemn_prior_weight"])
        pc = (float(resolved.condemned.sum()) + w * qc) / (len(resolved) + w)
        qtat = float(p.repair_tat_mean_d)
        lt = float(lead_times.loc[pn, "lt_est_d"])
        out = {"pn": pn, "shop": sh, "quoted_tat_d": qtat, "shop_return_transit_d": tr_back,
               "to_shop_hub_d": t_hub, "to_shop_out_d": t_out, "late_d": late, "n_ro": int(len(g)),
               "n_late_obs": int(len(lv)), "condemn_p": pc, "lt_po_d": lt}
        for tag, tt in (("hub", t_hub), ("out", t_out)):
            trep = max(tt + 1.0, tt + qtat + tr_back + late)
            out[f"t_repair_{tag}_d"] = trep
            out[f"t_eff_{tag}_d"] = (1 - pc) * trep + pc * (tt + lt)
        rows.append(out)
    return pd.DataFrame(rows).set_index("pn")


# ---------------------------------------------------------------------------------- final forecasts
def station_shares(inputs: dict, hub: str) -> pd.DataFrame:
    """(pn, station) share of each PN's demand: observed station counts shrunk towards an
    empirical-Bayes prior = planned arrival-exposure share x pooled (observed / exposure-expected)
    ratio over PNs of the same part class and deadline class."""
    pc = load_policy_config()["forecast"]
    alpha = float(pc["station_share_prior_strength"])
    win = int(pc["planned_exposure_window_weeks"])
    sd = inputs["station_demand"].sum(axis=1).unstack("station")                  # pn x station counts
    se = inputs["station_exposure"].iloc[:, -win:].sum(axis=1).unstack("station")
    stations = inputs["stations"]
    sd, se = sd[stations], se[stations]
    es = se.div(se.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    # parts without exposure (should not happen) fall back to hub
    es.loc[es.sum(axis=1) == 0, hub] = 1.0
    pm = inputs["hist"]["part_master"].set_index("pn")
    grp = pm.part_class + "_" + pm.deadline_class
    N = sd.sum(axis=1)
    prior = pd.DataFrame(0.0, index=sd.index, columns=stations)
    for g, pns in grp.groupby(grp).groups.items():
        obs = sd.loc[pns].sum(axis=0)
        exp_ = es.loc[pns].mul(N.loc[pns], axis=0).sum(axis=0)
        ratio = (obs + 0.5) / (exp_ + 0.5)
        pr = es.loc[pns] * ratio
        prior.loc[pns] = pr.div(pr.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    share = (sd + alpha * prior).div(N + alpha, axis=0)
    return share


def station_context(hist: dict, world, stations, prior_weight: float = 4.0) -> dict:
    """Per (pn, station): deadline mix of the requests seen there (p_d0, p_d10; shrunk towards the
    PN's network mix) and the AOG penalty rate (AED/h) weighted by arrivals of applicable archetypes."""
    rq = hist["material_requests"]
    pm = hist["part_master"].set_index("pn")
    pen_cfg = world.cfg["economics"]["aog_penalty_aed_per_hour"]
    ev_cfg = world.cfg["economics"].get("aog_event_cost_aed", {a: 0.0 for a in pen_cfg})
    arch = dict(zip(hist["aircraft_master"]["tail"], hist["aircraft_master"]["archetype"]))
    fl = hist["flight_exposure"]
    arr = fl.assign(a=fl["tail"].map(arch)).groupby(["arr_station", "a"]).size()
    appl = hist["part_applicability"].groupby("pn").archetype.apply(list).to_dict()
    cnt = rq.groupby(["pn", "station", "deadline_class"]).size()
    net = rq.groupby(["pn", "deadline_class"]).size()
    out = {}
    for pn in pm.index:
        nt = net.loc[pn] if pn in net.index.get_level_values(0) else pd.Series(dtype=float)
        ntot = float(nt.sum())
        d0n = float(nt.get("D0", 0.0)) / ntot if ntot else float(pm.loc[pn, "deadline_class"] == "D0")
        d10n = float(nt.get("D10", 0.0)) / ntot if ntot else float(pm.loc[pn, "deadline_class"] == "D10")
        archs = appl.get(pn, [])
        for st in stations:
            c = cnt.loc[(pn, st)] if (pn, st) in cnt.index.droplevel(2) else pd.Series(dtype=float)
            n = float(c.sum())
            p0 = (float(c.get("D0", 0.0)) + prior_weight * d0n) / (n + prior_weight)
            p10 = (float(c.get("D10", 0.0)) + prior_weight * d10n) / (n + prior_weight)
            w = {a: float(arr.get((st, a), 0.0)) for a in archs}
            tw = sum(w.values())
            pen = (sum(w[a] * float(pen_cfg[a]) for a in w) / tw) if tw > 0 else \
                float(np.mean([pen_cfg[a] for a in archs])) if archs else float(np.mean(list(pen_cfg.values())))
            if tw > 0:
                ev = sum(w[a] * float(ev_cfg[a]) for a in w) / tw
                nb = w.get("narrowbody", 0.0) / tw
            else:
                ev = float(np.mean([ev_cfg[a] for a in archs])) if archs else float(np.mean(list(ev_cfg.values())))
                nb = (float(np.mean([a == "narrowbody" for a in archs])) if archs else 0.5)
            out[(pn, st)] = {"p_d0": p0, "p_d10": p10, "aog_penalty_aed_h": pen, "aog_event_cost_aed": ev,
                             "nb_share": nb, "n_requests_hist": int(n)}
    return out


def _vmr(y: np.ndarray) -> float:
    m = float(np.mean(y))
    if m <= 0:
        return 1.0
    return max(1.0, float(np.var(y, ddof=1)) / m)


def _ltd_moments(rate_w: float, vmr: float, L_d: float, sd_L_d: float) -> tuple[float, float]:
    """Lead-time demand moments for a compound process: E = r L, Var = phi r L + r^2 sd_L^2."""
    mean = rate_w * L_d / 7.0
    var = vmr * mean + (rate_w / 7.0) ** 2 * sd_L_d ** 2
    return mean, var


def final_forecasts(hist: dict, world, champions: pd.DataFrame, origin: int | None = None,
                    seed: int = 0) -> pd.DataFrame:
    """Per (pn, station) planning forecast fitted on weeks < origin with each part's champion.

    Columns: pn, station, part_class, deadline_class, demand_class, champion, net_weekly_rate,
    station_share, weekly_rate, vmr_week, lead_time_d, lead_time_sd_d, ltd_mean, ltd_var, dist_kind,
    ltd_samples (bootstrap champion, hub row only), and for rotables removal_rate_day,
    net_removal_rate_day, mtbur_post, pipeline_days (P1 station pipeline), t_eff_hub_d, t_eff_out_d.
    Hub rows of C/E describe NETWORK demand over the purchase lead time (the hub is the supply
    point that replenishes the outstations); outstation rows describe local demand over the
    routine hub->station transit.
    """
    pcfg = load_policy_config()
    fcfg = pcfg["forecast"]
    origin = int(origin or fcfg["final_origin_week"])
    inputs = build_inputs(hist, origin=origin)
    h = inputs["hist"]
    hub = world.cfg["network"]["hub"]
    stations = inputs["stations"]
    pm = h["part_master"].set_index("pn")
    parts = inputs["parts"]
    D, E = inputs["demand"], inputs["exposure"]
    win = int(fcfg["planned_exposure_window_weeks"])
    dwin = int(fcfg["dispersion_window_weeks"])
    e_plan = E.iloc[:, -win:].mean(axis=1)                      # planned weekly exposure
    share = station_shares(inputs, hub)
    lts = estimate_lead_times(h["purchase_orders"], h["part_master"], origin)
    trn = routine_transit(h["transfers"], stations, hub)
    pipe = rotable_pipeline(h, world, origin, lts)
    ctx_st = station_context(h, world, stations)
    ch = champions.set_index(["demand_class", "part_class"]).champion.to_dict()
    glob = champions.champion.mode().iloc[0] if len(champions) else "sba"
    rows = []
    H = 13
    for i, pn in enumerate(pm.index):
        p = pm.loc[pn]
        dc = parts.loc[pn, "demand_class"]
        champ = ch.get((dc, p.part_class), glob)
        y = D.loc[pn].to_numpy()
        ctx = {"seed": seed + 7919 * i}
        mt = float(p.mtbur_quoted) if pd.notna(p.mtbur_quoted) else None
        rel_ctx = {"exposure_train": E.loc[pn].to_numpy(), "exposure_future": np.full(H, e_plan[pn]),
                   "mtbur_prior": mt, "prior_strength": float(fcfg["reliability_prior_strength"])}
        if champ == "reliability":
            ctx.update(rel_ctx)
        fc = fit_predict(champ, y, H, **ctx)
        net_rate = float(np.mean(fc.mean))
        rel = fit_predict("reliability", y, H, **rel_ctx)
        rel_rate_w = float(rel.params["rate"]) * float(e_plan[pn])
        vmr_net = _vmr(y[-dwin:])
        rec = {"pn": pn, "part_class": p.part_class, "deadline_class": p.deadline_class, "demand_class": dc,
               "champion": champ, "champion_net_weekly_rate": net_rate,
               "reliability_net_weekly_rate": rel_rate_w, "vmr_net_week": vmr_net,
               "mtbur_post": (1.0 / float(rel.params["rate"])) if rel.params["rate"] > 0 else np.nan,
               "mtbur_quoted": mt, "lt_quoted_d": float(lts.loc[pn, "lt_quoted_d"]),
               "lt_est_d": float(lts.loc[pn, "lt_est_d"]), "lt_sd_d": float(lts.loc[pn, "lt_sd_d"])}
        # rotables: Palm needs a removal rate -> reliability-exposure model regardless of champion
        if p.part_class == "R":
            rate_net = rel_rate_w
            rec["rate_source"] = "reliability"
        else:
            rate_net = net_rate
            rec["rate_source"] = champ
        boot = None
        if champ == "bootstrap" and p.part_class != "R":
            Lw = max(1, int(round(rec["lt_est_d"] / 7.0)))
            b = fit_predict("bootstrap", y, Lw, seed=seed + 7919 * i + 1)
            boot = np.asarray(b.ltd_dist().samples, float) * (rec["lt_est_d"] / 7.0) / Lw
        for st in stations:
            pi = float(share.loc[pn, st])
            r = dict(rec, station=st, net_weekly_rate=rate_net, station_share=pi, weekly_rate=rate_net * pi,
                     vmr_week=1.0 + pi * (vmr_net - 1.0), **ctx_st[(pn, st)],
                     transit_d=0.0 if st == hub else float(trn.loc[st, "transit_mean_d"]),
                     transit_sd_d=0.0 if st == hub else float(trn.loc[st, "transit_sd_d"]))
            if p.part_class == "R":
                lam_day = rate_net * pi / 7.0
                r["removal_rate_day"] = lam_day
                r["net_removal_rate_day"] = rate_net / 7.0
                tag = "hub" if st == hub else "out"
                r["pipeline_days"] = float(pipe.loc[pn, f"t_eff_{tag}_d"])
                r["t_eff_hub_d"] = float(pipe.loc[pn, "t_eff_hub_d"])
                r["t_eff_out_d"] = float(pipe.loc[pn, "t_eff_out_d"])
                r["lead_time_d"] = r["pipeline_days"]
                r["lead_time_sd_d"] = 0.0
                r["ltd_mean"] = lam_day * r["pipeline_days"]
                r["ltd_var"] = r["ltd_mean"]                       # Palm: pipeline ~ Poisson
                r["dist_kind"] = "poisson"
                r["ltd_samples"] = None
            else:
                if st == hub:
                    L, sL, rate, vmr = rec["lt_est_d"], rec["lt_sd_d"], rate_net, vmr_net
                else:
                    L, sL = float(trn.loc[st, "transit_mean_d"]), float(trn.loc[st, "transit_sd_d"])
                    rate, vmr = rate_net * pi, r["vmr_week"]
                m, v = _ltd_moments(rate, vmr, L, sL)
                r.update(lead_time_d=L, lead_time_sd_d=sL, ltd_mean=m, ltd_var=v)
                if boot is not None and st == hub:
                    r["dist_kind"] = "empirical"
                    r["ltd_samples"] = boot.tolist()
                else:
                    r["dist_kind"] = "nbinom" if (m > 0 and v / m >= float(fcfg["nb_min_vmr"])) else "poisson"
                    r["ltd_samples"] = None
            rows.append(r)
    out = pd.DataFrame(rows)
    first = ["pn", "station", "part_class", "deadline_class", "demand_class", "champion", "rate_source",
             "net_weekly_rate", "station_share", "weekly_rate", "vmr_week", "lead_time_d", "lead_time_sd_d",
             "ltd_mean", "ltd_var", "dist_kind"]
    out = out[first + [c for c in out.columns if c not in first]]
    out.attrs["origin"] = origin
    return out


def pipeline_tables(hist: dict, world, origin: int = 104) -> dict:
    """Lead-time, transit and rotable-pipeline estimates (for reporting)."""
    h = truncate_history(hist, origin)
    lts = estimate_lead_times(h["purchase_orders"], h["part_master"], origin)
    trn = routine_transit(h["transfers"], h["station_master"].station.tolist(), world.cfg["network"]["hub"])
    pipe = rotable_pipeline(h, world, origin, lts)
    return {"lead_times": lts, "transit": trn, "rotable_pipeline": pipe}


def reliability_vs_croston(leaderboard_by_class: pd.DataFrame) -> pd.DataFrame:
    """Per part class: reliability vs the best Croston-family method (croston/sba/tsb) on MASE,
    with CIs and whether the CIs overlap (honest comparison)."""
    rows = []
    for cls, g in leaderboard_by_class.groupby("part_class"):
        g = g.set_index("method")
        if "reliability" not in g.index:
            continue
        fam = g.loc[[m for m in ("croston", "sba", "tsb") if m in g.index]]
        best = fam.mase.idxmin()
        r, b = g.loc["reliability"], g.loc[best]
        tie = abs(float(r.mase) - float(b.mase)) < 1e-3
        rows.append({"part_class": cls, "reliability_mase": float(r.mase),
                     "reliability_ci": [round(float(r.mase_ci_lo), 4), round(float(r.mase_ci_hi), 4)],
                     "best_croston_family": best, "croston_family_mase": float(b.mase),
                     "croston_family_ci": [round(float(b.mase_ci_lo), 4), round(float(b.mase_ci_hi), 4)],
                     "mase_verdict": "tie (|diff| < 0.001)" if tie else ("reliability better" if r.mase < b.mase
                                                                          else "croston family better"),
                     "reliability_better": bool(r.mase < b.mase and not tie),
                     "cis_overlap": bool(not (r.mase_ci_hi < b.mase_ci_lo or b.mase_ci_hi < r.mase_ci_lo)),
                     "reliability_pinball_q90": r.get("pinball_q90", np.nan),
                     "croston_family_pinball_q90": b.get("pinball_q90", np.nan)})
    return pd.DataFrame(rows)


__all__ = ["load_history", "history_from_run", "truncate_history", "weekly_demand", "station_weekly_demand",
           "exposure_matrix", "station_exposure_matrix", "build_inputs", "run_forecast_evaluation",
           "run_stock_eval", "summarise_stock_eval", "estimate_lead_times", "routine_transit",
           "rotable_pipeline", "station_shares", "final_forecasts", "pipeline_tables", "reliability_vs_croston",
           "freeze_champions", "METHODS", "FC_OUT"]
