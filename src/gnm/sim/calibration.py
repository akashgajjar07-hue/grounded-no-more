"""P0-only calibration metrics (SIM-CAL). Uses P0 and the history seed / selection seeds only;
never runs any other policy."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from gnm.config import OUTPUTS, load_config

SUMMARY = OUTPUTS / "calibration" / "p0_history_summary.json"


def history_metrics(world, result, week_from: int, week_to: int) -> dict:
    """Fill rates, AOG hours/events per year for requests / AOG events starting in [week_from, week_to]."""
    rq = result.requests.merge(world.parts[["pn", "part_class"]], on="pn")
    h0, h1 = week_from * 168, (week_to + 1) * 168
    rq = rq[(rq.need_h >= h0) & (rq.need_h < h1)]
    imm = rq.immediate_fill.astype(bool)
    rot = rq.part_class == "R"
    ev = result.aog_events
    ev = ev[(ev.start_h >= h0) & (ev.start_h < h1)]
    yrs = (week_to - week_from + 1) / 52.0
    return {
        "immediate_fill_rate": float((rq.qty * imm).sum() / rq.qty.sum()),
        "rotable_immediate_fill_rate": float(imm[rot].mean()),
        "expendable_immediate_fill_rate": float(imm[rq.part_class == "E"].mean()),
        "consumable_immediate_fill_rate": float((rq.qty * imm)[rq.part_class == "C"].sum() / rq.qty[rq.part_class == "C"].sum()),
        "aog_hours_per_year": float(ev.hours.sum() / yrs),
        "aog_events_per_year": float(len(ev) / yrs),
    }


def in_band(metrics: dict, targets: dict) -> dict:
    return {k: bool(targets[k][0] <= metrics[k] <= targets[k][1]) for k in targets if k in metrics}


def calibrate(variants=None, n_selection_seeds: int = 5) -> dict:
    """Run P0 on the history (weeks 0–103, history_seed) and on the first selection seeds
    (weeks 78–155, KPIs 104–155) for each variant; write outputs/calibration/p0_history_summary.json."""
    from gnm.sim.api import load_or_generate_scenario, load_world
    from gnm.sim.baseline import build_p0
    from gnm.sim.engine import run_policy
    from gnm.sim.generator import VARIANTS

    cfg = load_config()
    cal = cfg["calibration_targets"]
    targets = {k: v for k, v in cal.items() if isinstance(v, list)}
    var_targets = cal.get("sensitivity_variants", {})
    w0, w1 = cfg["calendar"]["history_weeks"]
    ev0, ev1 = cfg["calendar"]["evaluation_weeks"]
    start = ev0 - cfg["calendar"]["warmup_weeks"]
    hseed = int(cfg["seeds"]["history_seed"])
    sel = list(range(cfg["seeds"]["selection_seeds"][0], cfg["seeds"]["selection_seeds"][1] + 1))[:n_selection_seeds]
    out = {"targets": targets, "variant_targets": var_targets, "policy": "P0 only", "variants": {}}
    for v in (variants or VARIANTS):
        world = load_world(v)
        p0 = build_p0(world)
        res = run_policy(world, load_or_generate_scenario(hseed, w0, w1, variant=v), p0, w0, w1)
        hist = history_metrics(world, res, w0, w1)
        y1 = history_metrics(world, res, w0, w0 + 51)
        y2 = history_metrics(world, res, w0 + 52, w1)
        ks = [run_policy(world, load_or_generate_scenario(s, start, ev1, variant=v), p0, ev0, ev1, detail=False).kpis
              for s in sel]
        selm = {k: float(np.mean([x[k] for x in ks])) for k in ["immediate_fill_rate", "aog_hours", "aog_events",
                                                                 "spare_capital_aed"]}
        out["variants"][v] = {"history": hist, "history_year1": y1, "history_year2": y2,
                              "history_kpis": {k: float(x) for k, x in res.kpis.items()},
                              "in_central_band": in_band(hist, targets),
                              "selection_p0_mean": {"seeds": sel, "weeks": [ev0, ev1], "start_week": start, **selm}}
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(out, indent=2))
    return out


# ------------------------------------------------------------------------------------------------
# v2 P0 diagnostics (NOT a calibration: no target band, no tuning, no lock)
# ------------------------------------------------------------------------------------------------
V2_DIAG = OUTPUTS / "calibration" / "v2_p0_diagnostics.json"
V2_DIAG_MD = OUTPUTS / "calibration" / "v2_p0_diagnostics.md"
ROUTE_LABEL = {"local": "local stock", "transfer": "AUH/network transfer", "lateral": "lateral",
               "exchange_loan": "AOG exchange/loan", "local_borrow": "local borrow", "robbery": "robbery (AUH)",
               "local_buy": "AOG local buy", "repair": "backorder -> repair return",
               "purchase": "backorder -> PO receipt", "none": "unfilled at end"}


def _request_aog(world, res, end_h):
    """Per-request material-late interval (same rule as the engine): [need + window, filled + fitting]."""
    from gnm import schemas
    rq = res.requests.merge(world.parts[["pn", "part_class", "unit_cost_aed", "description"]], on="pn")
    dl = rq.deadline_class.map(lambda d: schemas.DEADLINE_HOURS[d] if schemas.DEADLINE_HOURS[d] is not None else np.inf)
    start = rq.need_h + dl
    filled = rq.filled_h.astype("float")
    end = np.where(filled.isna(), end_h, filled + rq.fitting_h)
    late = (filled.isna() | (filled > start)) & np.isfinite(dl)
    rq["aog_h"] = np.where(late, np.clip(end - start, 0, None), 0.0)
    rq["trigger"] = np.where(rq.deadline_class == "D0", "D0_no_stock", "deadline_expired")
    rq["archetype"] = rq["tail"].map(dict(zip(world.aircraft["tail"], world.aircraft.archetype)))
    rq["wait_h"] = filled - rq.need_h
    return rq


def analytic_rotable_fill(world, station_share: dict | None = None) -> float:
    """Immediate rotable fill implied by the P0 Poisson rule on QUOTED data.

    AUH: P(pipeline <= S - 1), pipeline ~ Poisson(quoted mean); an outstation with a line-station unit:
    P(Poisson(quoted station rate x routine resupply) = 0); an outstation without one: 0. Demand weights are the
    quoted station split (``station_share=None``) or a given {pn: {station: share}}."""
    from scipy.stats import poisson
    from gnm.sim.baseline import p0_rotable_plan
    from gnm.sim.quoted import quoted_weekly_demand
    cfg = world.cfg
    hub = cfg["network"]["hub"]
    resup_d = cfg["network"]["routine_transport_days"]["mean"]
    plan = p0_rotable_plan(world).set_index("pn")
    dem = quoted_weekly_demand(world)
    num = den = 0.0
    for pn, g in dem[dem.pn.isin(plan.index)].groupby("pn"):
        tot = g.weekly_demand.sum()
        if tot <= 0:
            continue
        pr = plan.loc[pn]
        share = station_share.get(pn) if station_share else dict(zip(g.station, g.weekly_demand / tot))
        if not share:
            continue
        outs = set(pr.outstation_units.split(";")) if pr.outstation_units else set()
        for st, sh in share.items():
            if st == hub:
                f = poisson.cdf(pr.S_total - 1, pr.pipeline_mean) if pr.S_total > 0 else 0.0
            elif st in outs:
                f = poisson.pmf(0, tot * 52 * sh / 365 * resup_d)
            else:
                f = 0.0
            num += tot * sh * f
            den += tot * sh
    return float(num / den) if den else float("nan")


def v2_diagnostics(n_selection_seeds: int = 5, variant: str = "central") -> dict:
    """P0 on the v2 history (weeks 0–103, history seed) + P0 on the first selection seeds (diagnostic only)."""
    from gnm.sim.api import load_or_generate_scenario, load_world
    from gnm.sim.baseline import build_p0, p0_rotable_plan
    from gnm.sim.engine import run_policy

    cfg = load_config()
    w0, w1 = cfg["calendar"]["history_weeks"]
    ev0, ev1 = cfg["calendar"]["evaluation_weeks"]
    start = ev0 - cfg["calendar"]["warmup_weeks"]
    hseed = int(cfg["seeds"]["history_seed"])
    world = load_world(variant)
    p0 = build_p0(world)
    res = run_policy(world, load_or_generate_scenario(hseed, w0, w1, variant=variant), p0, w0, w1)
    yrs = (w1 - w0 + 1) / 52.0
    n_ac = len(world.aircraft)
    end_h = (w1 + 1) * 168
    rq = _request_aog(world, res, end_h)
    ev = res.aog_events
    hm = history_metrics(world, res, w0, w1)
    y1, y2 = history_metrics(world, res, w0, w0 + 51), history_metrics(world, res, w0 + 52, w1)
    tot_req_aog = float(rq.aog_h.sum())

    def by(col):
        g = rq[rq.aog_h > 0].groupby(col).agg(n=("aog_h", "size"), hours=("aog_h", "sum"))
        g["hours_per_year"] = g.hours / yrs
        g["share"] = g.hours / tot_req_aog if tot_req_aog else 0.0
        return {str(k): {"requests": int(r.n), "hours_per_year": round(float(r.hours_per_year), 1),
                         "share": round(float(r.share), 4)} for k, r in g.sort_values("hours", ascending=False).iterrows()}

    top = (rq[rq.aog_h > 0].groupby(["pn", "description", "part_class", "deadline_class", "unit_cost_aed"])
           .agg(n=("aog_h", "size"), hours=("aog_h", "sum")).sort_values("hours", ascending=False).head(10).reset_index())
    routes = {}
    src = rq.fill_source.fillna("none")
    for k, g in rq.groupby(src):
        w = g.wait_h.dropna()
        routes[ROUTE_LABEL.get(k, k)] = {"requests": int(len(g)), "units": int(g.qty.sum()),
                                         "mean_wait_h": round(float(w.mean()), 1) if len(w) else None,
                                         "median_wait_h": round(float(w.median()), 1) if len(w) else None}
    # rotable demand split as simulated (for the analytic comparison)
    rr = rq[rq.part_class == "R"]
    sim_share = {pn: dict(g.station.value_counts(normalize=True)) for pn, g in rr.groupby("pn")}
    ks = []
    for s in list(range(cfg["seeds"]["selection_seeds"][0], cfg["seeds"]["selection_seeds"][1] + 1))[:n_selection_seeds]:
        r2 = run_policy(world, load_or_generate_scenario(s, start, ev1, variant=variant), p0, ev0, ev1)
        m2 = history_metrics(world, r2, ev0, ev1)
        ks.append({"seed": s, **{k: round(v, 4) for k, v in m2.items()}, "spare_capital_aed": r2.kpis["spare_capital_aed"],
                   "aog_hours_kpi": r2.kpis["aog_hours"], "aog_events_kpi": r2.kpis["aog_events"]})
    selm = {k: float(np.mean([x[k] for x in ks])) for k in ks[0] if k != "seed"}
    plan = p0_rotable_plan(world)
    out = {
        "status": "DIAGNOSTIC ONLY - v2 P0, no target band, nothing tuned or locked",
        "variant": variant, "policy": "P0 (OEM-recommended provisioning on quoted data)",
        "history": {"weeks": [w0, w1], "seed": hseed, **{k: round(v, 4) for k, v in hm.items()},
                    "aog_hours_per_aircraft_year": round(hm["aog_hours_per_year"] / n_ac, 1),
                    "year1": {k: round(v, 4) for k, v in y1.items()}, "year2": {k: round(v, 4) for k, v in y2.items()},
                    "spare_capital_aed": round(res.kpis["spare_capital_aed"], 0),
                    "kpis": {k: round(float(v), 2) for k, v in res.kpis.items()}, "extra": res.kpis_extra},
        "aog_note": "breakdowns use per-request material-late hours (unmerged); the fleet totals use merged per-aircraft events",
        "aog_by_trigger": by("trigger"), "aog_by_class": by("part_class"), "aog_by_station": by("station"),
        "aog_by_archetype": by("archetype"),
        "consumable_share_of_aog": round(float(rq[rq.part_class == "C"].aog_h.sum() / tot_req_aog), 4) if tot_req_aog else 0.0,
        "top10_aog_pns": [{"pn": r.pn, "description": r.description, "class": r.part_class, "deadline": r.deadline_class,
                           "unit_cost_aed": round(float(r.unit_cost_aed), 0), "aog_requests": int(r.n),
                           "aog_hours_per_year": round(float(r.hours / yrs), 1)} for r in top.itertuples()],
        "sourcing_routes": routes,
        "rotable_fill_analytic_vs_sim": {
            "analytic_quoted_plan_split": round(analytic_rotable_fill(world), 4),
            "analytic_simulated_station_split": round(analytic_rotable_fill(world, sim_share), 4),
            "simulated_history": round(hm["rotable_immediate_fill_rate"], 4),
            "note": "analytic = P0's own expectation from quoted MTBUR/TAT (Poisson pipeline at AUH, line-station unit "
                    "at outstations); simulated reflects true rates (quotes are optimistic), queueing and variability"},
        "p0_rotable_plan_totals": {"S_total": int(plan.S_total.sum()), "loop_units": int(plan.loop_units.sum()),
                                   "auh_serviceable_target": int(plan.auh_base_stock.sum()),
                                   "outstation_units": int(sum(len(x.split(";")) for x in plan.outstation_units if x))},
        "selection_p0": {"seeds": [k["seed"] for k in ks], "weeks": [ev0, ev1], "start_week": start, "mean": selm,
                         "per_seed": ks},
    }
    V2_DIAG.parent.mkdir(parents=True, exist_ok=True)
    V2_DIAG.write_text(json.dumps(out, indent=2, default=float))
    V2_DIAG_MD.write_text(_diag_md(out))
    return out


def _diag_md(d: dict) -> str:
    h, s = d["history"], d["selection_p0"]["mean"]
    L = ["# v2 P0 diagnostics (diagnostic only: no band, nothing tuned or locked)", "",
         f"Policy: {d['policy']}. History = weeks {h['weeks'][0]}–{h['weeks'][1]}, seed {h['seed']}. "
         f"Selection = seeds {d['selection_p0']['seeds']}, weeks {d['selection_p0']['weeks']} (start week {d['selection_p0']['start_week']}).", "",
         "| Metric | History | Year 1 | Year 2 | Selection mean |", "|---|---|---|---|---|"]
    for k, lab in [("immediate_fill_rate", "Immediate fill (all)"), ("rotable_immediate_fill_rate", "Rotable fill"),
                   ("expendable_immediate_fill_rate", "Expendable fill"), ("consumable_immediate_fill_rate", "Consumable fill"),
                   ("aog_hours_per_year", "Material AOG h/yr (fleet)"), ("aog_events_per_year", "AOG events/yr")]:
        L.append(f"| {lab} | {h[k]:,.3f} | {h['year1'][k]:,.3f} | {h['year2'][k]:,.3f} | {s[k]:,.3f} |")
    L += ["", f"AOG h per aircraft-year: {h['aog_hours_per_aircraft_year']}. P0 spare capital: AED {h['spare_capital_aed']:,.0f} "
              f"(selection mean AED {s['spare_capital_aed']:,.0f}). Consumable share of AOG hours: {d['consumable_share_of_aog']:.1%}.", ""]
    for key, title in [("aog_by_trigger", "AOG by trigger"), ("aog_by_class", "AOG by class"),
                       ("aog_by_station", "AOG by station"), ("aog_by_archetype", "AOG by archetype")]:
        L += [f"**{title}** (per-request hours/yr, share): " + "; ".join(
            f"{k} {v['hours_per_year']:,.0f} h ({v['share']:.0%})" for k, v in d[key].items()), ""]
    L += ["| Top AOG PN | Description | Class | Deadline | Unit cost AED | AOG h/yr |", "|---|---|---|---|---|---|"]
    for r in d["top10_aog_pns"]:
        L.append(f"| {r['pn']} | {r['description']} | {r['class']} | {r['deadline']} | {r['unit_cost_aed']:,.0f} | {r['aog_hours_per_year']:,.0f} |")
    L += ["", "| Sourcing route | Requests | Mean wait h | Median wait h |", "|---|---|---|---|"]
    for k, v in sorted(d["sourcing_routes"].items(), key=lambda kv: -kv[1]["requests"]):
        L.append(f"| {k} | {v['requests']:,} | {v['mean_wait_h']} | {v['median_wait_h']} |")
    a = d["rotable_fill_analytic_vs_sim"]
    L += ["", f"Rotable fill implied by the 90–95% Poisson rule on quoted data: {a['analytic_quoted_plan_split']:.3f} (quoted "
              f"station split) / {a['analytic_simulated_station_split']:.3f} (simulated station split); simulated: "
              f"{a['simulated_history']:.3f}. {a['note']}.", ""]
    return "\n".join(L) + "\n"
