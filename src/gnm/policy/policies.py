"""P1 'Local optimised' and P2 'Network' policies (inventory-policy agent).

Both are pure functions of the public World and the planner's forecasts
(:func:`gnm.policy.forecast_pipeline.final_forecasts`, fitted on history weeks 0-103). They return
a :class:`~gnm.contracts.PolicySpec` that the one policy-agnostic engine runs.

P1 Local optimised (single-echelon, each stocking point on its own)
  * C/E: continuous-review (s, S) per station. s = lead-time-demand quantile at the deadline-class
    cycle-service target (Poisson / negative binomial / Willemain bootstrap per the forecast row);
    S = s + EOQ. The hub row is the supply point of the network (it replenishes the outstations), so
    it is sized on network demand over the estimated purchase lead time; outstation rows on local
    demand over the routine hub->station transit.
  * R: each station holds its own float: smallest S with Palm availability P(X < S) >= target,
    X ~ Poisson(local removal rate x pipeline days). Emergency source for outstations: AUH only.
P2 Network (pooled hub + economically justified outstation positioning)
  * Hub: rotable float sized on NETWORK pipeline demand at the target; C/E as P1's hub row.
  * Outstation j gets its k-th unit only while
        annual requests_j x [F(k) - F(k-1)] x cost of a local miss / unit cost >= threshold
    (config/policy.yaml p2_network.positioning_threshold_aed_per_aed_year). F is the immediate-fill
    probability with resupply from the hub (routine transit + expected hub backorder delay EBO/lambda,
    METRIC-style). v2 cost of a local miss (:func:`p2_positioning`): with probability A_H the hub ships
    (AOG transport hours), otherwise the v2 AOG routes apply (local borrow / exchange-loan for rotables,
    local buy for C/E, retried; public config ``aog_sourcing``); D0 misses pay (wait + fitting) x penalty
    rate + the fixed per-event cost; every miss pays shipment or route fees. C/E outstations that
    qualify run (k-1, k-1+EOQ).
  * lateral_transfers=True, rebalance=True. Both policies: repair_tat_multiplier = 1.
v2 semantics (V2-SIM-10/11): the rotable protection level is the immediate fill P(X <= S-1) = P(X < S),
the quantity the engine measures; S is TOTAL spares, so the serviceable target handed to the engine at
the hub is S minus the repair-loop units the run starts with, counted exactly as P0 does
(gnm.sim.baseline.p0_rotable_plan, quoted pipeline per gnm.sim.quoted.pipeline_days).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from gnm.config import OUTPUTS
from gnm.contracts import PolicySpec, World
from gnm.policy import analytic
from gnm.policy.forecast_pipeline import load_policy_config

POL_OUT = OUTPUTS / "policies"


# ---------------------------------------------------------------------------------- helpers
def service_target(world: World, deadline: str) -> float:
    st = world.cfg["service_targets"]
    if deadline in st:
        return float(st[deadline])
    return float(load_policy_config()["service_target_none"])


def reorder_point_from_row(row, service: float) -> int:
    """Cycle-service reorder point from a forecast row (uses gnm.policy.analytic)."""
    m = float(row["ltd_mean"])
    if m <= 0:
        return -1
    kind = row["dist_kind"]
    if kind == "empirical":
        samp = row.get("ltd_samples")
        if samp is not None and len(samp):
            return analytic.reorder_point_empirical(np.asarray(samp, float), service)
    if kind == "nbinom":
        return analytic.reorder_point(m, service, float(row["ltd_var"]))
    return analytic.reorder_point(m, service)


def eoq(annual_demand: float, order_cost: float, unit_cost: float, carry: float, weekly: float,
        max_cover_weeks: float, shelf_cap_units: float | None = None) -> int:
    """Harris-Wilson EOQ, capped (cover weeks, shelf life), rounded, >= 1."""
    if annual_demand <= 0 or unit_cost <= 0:
        return 1
    q = math.sqrt(2.0 * annual_demand * order_cost / (carry * unit_cost))
    q = min(q, max(1.0, weekly * max_cover_weeks))
    if shelf_cap_units is not None:
        q = min(q, max(1.0, shelf_cap_units))
    return max(1, int(round(q)))


def palm_base_stock(mu: float, target: float, s_max: int = 60) -> int:
    """Smallest S with P(X < S) >= target, X ~ Poisson(mu). 0 when there is no demand."""
    if mu <= 0:
        return 0
    for S in range(1, s_max + 1):
        if analytic.availability(S, mu) >= target:
            return S
    return s_max


def pipeline_units_at_start(world: World) -> dict:
    """Rotable units already owned in the repair loop (U/S or in the shop) when a run starts.

    The engine seeds each rotable's loop with round(quoted removal rate x quoted pipeline days) units ON
    TOP of the stations' serviceable base stock (data contract §4; public quoted figures, identical
    across policies). Palm's S is TOTAL spares, so the serviceable target is S minus these units (POL-6).
    Taken from P0's own plan (``p0_rotable_plan.loop_units``) so P0, P1 and P2 use one definition
    (V2-SIM-11 pipeline). The planner's analogue: count the units currently in the repair loop."""
    from gnm.sim.baseline import p0_rotable_plan
    plan = p0_rotable_plan(world)
    return {r.pn: int(r.loop_units) for r in plan.itertuples(index=False)}


def emergency_cost(world: World, frm: str, to: str) -> float:
    """Emergency (AOG) shipment cost, same public formula as the engine: config
    economics.emergency_logistics_aed scaled linearly by AOG transport hours."""
    aog = world.aog_hours.to_numpy(float)
    nz = aog[aog > 0]
    a = float(world.aog_hours.loc[frm, to])
    if a == 0:
        return 0.0
    lo, hi = world.cfg["economics"]["emergency_logistics_aed"]
    return lo + (hi - lo) * (a - nz.min()) / max(1e-9, nz.max() - nz.min())


def _shelf_cap(world: World, pn: str, weekly: float, share: float) -> float | None:
    sl = world.parts.set_index("pn").loc[pn, "shelf_life_months"]
    if pd.isna(sl):
        return None
    return weekly * float(sl) * 4.345 * share


def _ce_params(world: World, row, order_cost: float, pcfg: dict) -> tuple[int, int]:
    """(s, S) for one C/E (pn, station) forecast row."""
    s = reorder_point_from_row(row, service_target(world, row["deadline_class"]))
    if s < 0:
        return -1, 0
    hub = world.cfg["network"]["hub"]
    weekly = float(row["net_weekly_rate"] if row["station"] == hub else row["weekly_rate"])
    unit = float(world.parts.set_index("pn").loc[row["pn"], "unit_cost_aed"])
    oc = pcfg["ordering"]
    q = eoq(weekly * 52.0, order_cost, unit, float(world.cfg["economics"]["carrying_cost_pct_per_year"]), weekly,
            float(oc["max_cover_weeks"]), _shelf_cap(world, row["pn"], weekly, float(oc["shelf_life_cover_share"])))
    return int(s), int(s + q)


def _order_costs(world: World, pcfg: dict) -> tuple[float, float]:
    k_po = float(pcfg["ordering"]["ordering_cost_aed_per_po"])
    k_sto = pcfg["ordering"].get("ordering_cost_aed_per_sto")
    k_sto = float(k_sto) if k_sto is not None else float(world.cfg["economics"]["routine_shipment_aed_per_line"])
    return k_po, k_sto


def _check_forecasts(world: World, forecasts: pd.DataFrame) -> None:
    need = {(p, s) for p in world.parts.pn for s in world.stations.station}
    have = set(zip(forecasts.pn, forecasts.station))
    missing = need - have
    if missing:
        raise ValueError(f"forecasts missing {len(missing)} (pn, station) rows, e.g. {sorted(missing)[:3]}")


def _spec(policy_id: str, label: str, rows: list, world: World, **kw) -> PolicySpec:
    sp = pd.DataFrame(rows, columns=["pn", "station", "s", "S", "base_stock"])
    sp = sp.astype({"s": "int64", "S": "int64", "base_stock": "int64"})
    hub = world.cfg["network"]["hub"]
    outs = [s for s in world.stations.station if s != hub]
    return PolicySpec(policy_id=policy_id, label=label, stock_params=sp,
                      emergency_sources={**{st: [hub] for st in outs}, hub: []},
                      repair_tat_multiplier={p: 1.0 for p in world.parts.pn}, expedite_purchase_on_aog=True, **kw)


# ---------------------------------------------------------------------------------- P1
def build_p1(world: World, forecasts: pd.DataFrame, pcfg: dict | None = None) -> PolicySpec:
    """P1 'Local optimised': every station optimised on its own demand (see module docstring)."""
    pcfg = pcfg or load_policy_config()
    _check_forecasts(world, forecasts)
    hub = world.cfg["network"]["hub"]
    k_po, k_sto = _order_costs(world, pcfg)
    smax = int(pcfg["rotable"]["palm_max_units"])
    seed = pipeline_units_at_start(world) if pcfg["rotable"].get("subtract_initial_pipeline", True) else {}
    rows = []
    for r in forecasts.to_dict("records"):
        if r["part_class"] == "R":
            mu = float(r["removal_rate_day"]) * float(r["pipeline_days"])
            bs = palm_base_stock(mu, service_target(world, r["deadline_class"]), smax)
            if r["station"] == hub:          # repair returns (incl. the seeded pipeline) land at the hub
                bs = max(0, bs - seed.get(r["pn"], 0))
            rows.append((r["pn"], r["station"], -1, 0, bs))
        else:
            s, S = _ce_params(world, r, k_po if r["station"] == hub else k_sto, pcfg)
            rows.append((r["pn"], r["station"], s, S, 0))
    return _spec("P1", "Local optimised", rows, world, lateral_transfers=False, rebalance=False,
                 notes="C/E (s,S): s = LTD quantile at the deadline-class target (hub on network demand over the "
                       "estimated PO lead time, outstations on local demand over routine transit), S = s + EOQ. "
                       "R: Palm base stock per station on local rate x pipeline days. Emergency source AUH only.")


# ---------------------------------------------------------------------------------- P2
def _fill_ce(k: int, mean: float, var: float) -> float:
    """P(LTD < k) for an outstation base level k (Poisson or NB by moments)."""
    if k <= 0:
        return 0.0
    if mean <= 0:
        return 1.0
    nb = analytic.nb_params(mean, var)
    if nb is None:
        return float(stats.poisson.cdf(k - 1, mean))
    return float(stats.nbinom.cdf(k - 1, nb[0], nb[1]))


def route_expectation(world: World, cls: str, station: str, nb_share: float, unit_cost: float,
                      loan_days: float = 14.0) -> dict:
    """Expected outcome of the v2 AOG recovery routes for one uncovered need (config ``aog_sourcing``,
    public ASSUMED figures, never the hidden truth).

    Rotables: at the hub, robbery (availability x response) then exchange/loan; at an outstation, local
    borrow (station x fleet availability) then exchange/loan. C/E: local buy. A failed attempt is
    retried every ``retry_hours`` (V2-SIM-14), so with per-attempt success P the expected wait is
    (1-P)/P x retry + E[response | success]. Fees: exchange fee % of list + per-day loan fee x
    ``loan_days``; local borrow fixed fee + per-day fee; local buy premium; robbery double labour.
    Mixed over fleet types with ``nb_share``."""
    ags = world.cfg["aog_sourcing"]
    hub = world.cfg["network"]["hub"]
    eco = world.cfg["economics"]
    fit = world.cfg["engine"]["fitting_hours"]
    out = {"wait_h": 0.0, "fee_aed": 0.0, "p_success_attempt": 0.0}
    mid = lambda r: (float(r[0]) + float(r[1])) / 2.0  # noqa: E731
    for arch, w in (("narrowbody", nb_share), ("widebody", 1.0 - nb_share)):
        if w <= 0:
            continue
        opts = []        # (probability this route is the one used in an attempt, response h, fee)
        if cls == "R":
            ex = ags["exchange_loan"]
            p_ex, r_ex = float(ex["availability"][arch]), mid(ex["response_hours"][arch])
            f_ex = unit_cost * (float(ex["fee_pct_of_list"][arch]) + float(ex["loan_fee_pct_of_list_per_day"]) * loan_days)
            if station == hub:
                rb = ags["robbery"]
                p1 = float(rb["availability"]) if rb.get("enabled", True) else 0.0
                f1 = float(eco.get("fitting_labour_aed_per_hour", 0.0)) * mid(fit["R"]) * float(rb["labour_multiplier"])
                r1 = mid(rb["response_hours"])
            else:
                lb = ags["local_borrow"]
                p1 = float(lb["availability"][arch].get(station, 0.0))
                r1 = mid(lb["response_hours"])
                f1 = float(lb["fee_aed_fixed"]) + unit_cost * float(lb["loan_fee_pct_of_list_per_day"]) * loan_days
            opts = [(p1, r1, f1), ((1 - p1) * p_ex, r_ex, f_ex)]
        else:
            lb = ags["local_buy"]
            opts = [(float(lb["availability"]), mid(lb["response_hours"]), unit_cost * float(lb["premium_pct"]))]
        P = sum(o[0] for o in opts)
        retry = float(ags["retry_hours"][cls])
        if P <= 0:
            wait, fee = 30 * 24.0, 0.0
        else:
            wait = (1 - P) / P * retry + sum(o[0] * o[1] for o in opts) / P
            fee = sum(o[0] * o[2] for o in opts) / P
        out["wait_h"] += w * min(wait, 30 * 24.0)
        out["fee_aed"] += w * fee
        out["p_success_attempt"] += w * P
    return out


def p2_positioning(world: World, forecasts: pd.DataFrame, pcfg: dict | None = None) -> pd.DataFrame:
    """Greedy outstation positioning table for P2 (v2 cost of a local miss).

    A need at outstation j that finds no local stock is covered by an emergency transfer from the hub
    when the hub has stock (probability A_H; AOG transport hours AUH->j), otherwise by the AOG routes
    (local borrow / exchange-loan for R, local buy for C/E, with retries; :func:`route_expectation`).
    Cost per miss = p_D0 x [(A_H x transport h + (1-A_H) x route wait + fitting h) x penalty AED/h +
    fixed cost per AOG event] + A_H x shipment cost + (1-A_H) x route fee. Deferred (D3/D10) misses
    are assumed covered inside their window (shipment or route cost only). The k-th unit is added while
    annual requests x [F(k) - F(k-1)] x cost per miss / unit cost >= threshold."""
    pcfg = pcfg or load_policy_config()
    hub = world.cfg["network"]["hub"]
    theta = float(pcfg["p2_network"]["positioning_threshold_aed_per_aed_year"])
    use_wait = bool(pcfg["p2_network"]["include_auh_wait_in_outstation_lead_time"])
    smax = int(pcfg["rotable"]["palm_max_units"])
    routine = float(world.cfg["economics"]["routine_shipment_aed_per_line"])
    fit = world.cfg["engine"]["fitting_hours"]
    unit = world.parts.set_index("pn").unit_cost_aed.astype(float)
    rows = []
    for pn, g in forecasts.groupby("pn"):
        g = g.set_index("station")
        cls = g.iloc[0]["part_class"]
        dl = g.iloc[0]["deadline_class"]
        c = float(unit[pn])
        # hub availability and expected hub backorder delay (days): Palm at the pooled hub, EBO/lambda
        wait_d, cond_wait_d = 0.0, 7.0
        if cls == "R":
            lam_net = float(g["removal_rate_day"].sum())
            mu_net = float((g["removal_rate_day"] * g["pipeline_days"]).sum())
            S_h = palm_base_stock(mu_net, service_target(world, dl), smax)
            A_h = analytic.availability(S_h, mu_net) if S_h > 0 else 0.0
            if lam_net > 0:
                w_all = analytic.expected_wait_days(S_h, mu_net, lam_net)
                wait_d = w_all if use_wait else 0.0
                cond_wait_d = w_all / max(1e-6, 1.0 - A_h) if A_h < 1 else 0.0
        else:
            A_h = service_target(world, dl)
        fit_h = float(np.mean(fit[cls])) if isinstance(fit[cls], list) else float(fit[cls])
        for st, r in g.iterrows():
            if st == hub:
                continue
            L = float(r["transit_d"]) + wait_d
            lam_yr = float(r["weekly_rate"]) * 52.0
            aog_h = float(world.aog_hours.loc[hub, st])
            p_d0 = float(r["p_d0"]) if dl != "NONE" else 0.0
            p_d10 = float(r["p_d10"])
            loan_days = float(r["transit_d"]) + min(cond_wait_d, 60.0)
            route = route_expectation(world, cls, st, float(r["nb_share"]), c, loan_days)
            ship = p_d10 * routine + (1.0 - p_d10) * emergency_cost(world, hub, st)
            exp_aog_h = A_h * aog_h + (1.0 - A_h) * route["wait_h"] + fit_h
            per_miss = (p_d0 * (exp_aog_h * float(r["aog_penalty_aed_h"]) + float(r["aog_event_cost_aed"]))
                        + A_h * ship + (1.0 - A_h) * route["fee_aed"])
            if cls == "R":
                mu = float(r["removal_rate_day"]) * L
                F = lambda k, mu=mu: analytic.availability(k, mu) if k > 0 else 0.0  # noqa: E731
            else:
                m = float(r["weekly_rate"]) * L / 7.0
                v = float(r["vmr_week"]) * m + (float(r["weekly_rate"]) / 7.0) ** 2 * float(r["transit_sd_d"]) ** 2
                F = lambda k, m=m, v=v: _fill_ce(k, m, v)  # noqa: E731
            k, last_ratio, next_ratio = 0, np.nan, np.nan
            while k < smax and lam_yr > 0:
                gain = lam_yr * (F(k + 1) - F(k)) * per_miss
                ratio = gain / c if c > 0 else np.inf
                if ratio >= theta:
                    k += 1
                    last_ratio = ratio
                else:
                    next_ratio = ratio
                    break
            rows.append({"pn": pn, "station": st, "part_class": cls, "deadline_class": dl, "units": k,
                         "annual_requests": lam_yr, "resupply_days": L, "hub_wait_days": wait_d, "hub_avail": A_h,
                         "p_d0": p_d0, "route_wait_h": route["wait_h"], "route_fee_aed": route["fee_aed"],
                         "expected_aog_h_per_d0_miss": exp_aog_h, "cost_per_miss_aed": per_miss,
                         "last_ratio": last_ratio, "next_ratio": next_ratio, "unit_cost_aed": c})
    return pd.DataFrame(rows)


def build_p2(world: World, forecasts: pd.DataFrame, pcfg: dict | None = None) -> PolicySpec:
    """P2 'Network': pooled hub stock + outstation positioning by marginal AOG-cost per AED."""
    pcfg = pcfg or load_policy_config()
    _check_forecasts(world, forecasts)
    hub = world.cfg["network"]["hub"]
    k_po, k_sto = _order_costs(world, pcfg)
    smax = int(pcfg["rotable"]["palm_max_units"])
    pos = p2_positioning(world, forecasts, pcfg).set_index(["pn", "station"])
    seed = pipeline_units_at_start(world) if pcfg["rotable"].get("subtract_initial_pipeline", True) else {}
    carry = float(world.cfg["economics"]["carrying_cost_pct_per_year"])
    unit = world.parts.set_index("pn").unit_cost_aed.astype(float)
    rows = []
    for pn, g in forecasts.groupby("pn", sort=False):
        g = g.set_index("station")
        cls = g.iloc[0]["part_class"]
        dl = g.iloc[0]["deadline_class"]
        for st, r in g.iterrows():
            if st == hub:
                if cls == "R":
                    mu_net = float((g["removal_rate_day"] * g["pipeline_days"]).sum())
                    S_net = palm_base_stock(mu_net, service_target(world, dl), smax)
                    rows.append((pn, st, -1, 0, max(0, S_net - seed.get(pn, 0))))
                else:
                    s, S = _ce_params(world, dict(r, station=st, pn=pn), k_po, pcfg)
                    rows.append((pn, st, s, S, 0))
                continue
            k = int(pos.loc[(pn, st), "units"])
            if cls == "R":
                rows.append((pn, st, -1, 0, k))
            elif k <= 0:
                rows.append((pn, st, -1, 0, 0))
            else:
                weekly = float(r["weekly_rate"])
                q = eoq(weekly * 52.0, k_sto, float(unit[pn]), carry, weekly,
                        float(pcfg["ordering"]["max_cover_weeks"]),
                        _shelf_cap(world, pn, weekly, float(pcfg["ordering"]["shelf_life_cover_share"])))
                rows.append((pn, st, k - 1, k - 1 + q, 0))
    return _spec("P2", "Network", rows, world, lateral_transfers=True, rebalance=True,
                 notes="Hub: rotable float on network pipeline demand at the target (Palm, fill definition), C/E "
                       "(s,S) on network LTD over the estimated PO lead time. Outstations: units added while the "
                       "annual expected cost of local misses avoided (v2 AOG routes, downtime hours x rate, fixed "
                       "per-event cost, shipment/route fees) per AED of capital >= %.2f. Lateral transfers and "
                       "weekly rebalancing on." % float(pcfg["p2_network"]["positioning_threshold_aed_per_aed_year"]))


# ---------------------------------------------------------------------------------- tables
def stock_param_table(spec: PolicySpec, world: World) -> pd.DataFrame:
    """Reproducible parameter table with the capital at target (units x unit cost; C/E at S)."""
    pm = world.parts.set_index("pn")
    sp = spec.stock_params.copy()
    sp["part_class"] = sp.pn.map(pm.part_class)
    sp["deadline_class"] = sp.pn.map(pm.deadline_class)
    sp["unit_cost_aed"] = sp.pn.map(pm.unit_cost_aed).astype(float)
    sp["target_units"] = np.where(sp.part_class == "R", sp.base_stock, sp.S.clip(lower=0))
    # C/E average cycle stock ~ s + (S - s)/2 is a better capital estimate than S
    sp["avg_units_est"] = np.where(sp.part_class == "R", sp.base_stock,
                                   np.where(sp.s >= 0, sp.s.clip(lower=0) + (sp.S - sp.s.clip(lower=0)) / 2.0, 0.0))
    sp["capital_at_target_aed"] = sp.target_units * sp.unit_cost_aed
    sp["capital_avg_est_aed"] = sp.avg_units_est * sp.unit_cost_aed
    sp.insert(0, "policy_id", spec.policy_id)
    return sp.sort_values(["pn", "station"]).reset_index(drop=True)


def summarise_spec(spec: PolicySpec, world: World) -> dict:
    t = stock_param_table(spec, world)
    hub = world.cfg["network"]["hub"]
    return {
        "policy_id": spec.policy_id, "label": spec.label, "notes": spec.notes,
        "lateral_transfers": spec.lateral_transfers, "rebalance": spec.rebalance,
        "capital_at_target_aed": float(t.capital_at_target_aed.sum()),
        "capital_avg_est_aed": float(t.capital_avg_est_aed.sum()),
        "capital_at_target_by_class": t.groupby("part_class").capital_at_target_aed.sum().round(2).to_dict(),
        "capital_at_target_by_deadline": t.groupby("deadline_class").capital_at_target_aed.sum().round(2).to_dict(),
        "units_by_station": t.groupby("station").target_units.sum().astype(int).to_dict(),
        "rotable_units_by_station": t[t.part_class == "R"].groupby("station").target_units.sum().astype(int).to_dict(),
        "capital_by_station": t.groupby("station").capital_at_target_aed.sum().round(2).to_dict(),
        "stocked_pn_station_pairs": int(((t.part_class == "R") & (t.base_stock > 0)).sum()
                                        + ((t.part_class != "R") & (t.s >= 0)).sum()),
        "outstation_rotable_units": int(t[(t.part_class == "R") & (t.station != hub)].base_stock.sum()),
        "rotable_serviceable_target_units": int(t[t.part_class == "R"].base_stock.sum()),
        "rotable_pipeline_units_at_start": int(sum(pipeline_units_at_start(world).values())),
        "provenance": "DERIVED",
    }


def write_policy_tables(specs: list[PolicySpec], world: World, out_dir: Path | None = None,
                        extra: dict | None = None) -> dict:
    out = Path(out_dir or POL_OUT)
    out.mkdir(parents=True, exist_ok=True)
    summ = {"provenance": "DERIVED", "source": "history weeks 0-103 (public tables) + config/policy.yaml",
            "policies": []}
    for sp in specs:
        t = stock_param_table(sp, world)
        t.to_csv(out / f"{sp.policy_id}_stock_params.csv", index=False, float_format="%.2f", lineterminator="\n")
        summ["policies"].append(summarise_spec(sp, world))
    if extra:
        summ.update(extra)
    (out / "policies.json").write_text(json.dumps(summ, indent=2, default=str) + "\n")
    return summ


def load_forecasts(path: Path | None = None) -> pd.DataFrame:
    return pd.read_parquet(path or (OUTPUTS / "forecasting" / "final_forecasts.parquet"))


__all__ = ["build_p1", "build_p2", "p2_positioning", "route_expectation", "stock_param_table", "summarise_spec", "write_policy_tables",
           "reorder_point_from_row", "palm_base_stock", "eoq", "emergency_cost", "load_forecasts",
           "pipeline_units_at_start"]
