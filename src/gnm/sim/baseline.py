"""P0 — "OEM-recommended provisioning on quoted data" (v2, AV-04; config: policy_baseline_P0).

P0 uses only public master data: part-master quoted figures (quoted MTBUR / quoted usage, quoted shop
TAT, deadline class, part class), the applicability table, planned fleet utilisation in aircraft_master,
the planned route mix, the maintenance programme and the quoted vendor transit / core-return times.
It never looks at removal history.

* Rotables: total spares S = smallest S with P(Poisson(m) <= S - 1) >= protection level (95% D0, 90% D3/D10),
  m = quoted annual removals x quoted pipeline days / 365. Held at AUH as serviceable target
  S - (repair-loop units the engine seeds at the start; POL-6), plus 1 outstation unit for a D0 PN where the
  quoted station rate is >= 4/yr (line-station kit).
* C/E: min = 26 weeks (C) / 13 weeks (E) of quoted demand, max = 2 x min, at every station with quoted demand.

``build_p0_naive`` keeps the v1 rule ("P0-naive: stock to the mean") for illustration only.
"""
from __future__ import annotations

import math

import pandas as pd
from scipy.stats import poisson

from gnm.contracts import PolicySpec, World
from gnm.sim.quoted import pipeline_days, quoted_weekly_demand  # noqa: F401  (quoted_weekly_demand re-exported)


def poisson_spares(mean: float, protection: float) -> int:
    """Smallest total spares S such that a demand finds a serviceable spare with probability >= protection,
    i.e. P(Poisson(mean) <= S - 1) >= protection (V2-SIM-10: the protection level is defined on the same
    quantity the engine measures as immediate fill, not on the ready rate P(N <= S))."""
    if mean <= 0:
        return 0
    return int(poisson.ppf(protection, mean)) + 1


def _cs_rows(world, weeks_min_by_class, max_mult, dmap, net, stations, hub):
    rows = []
    for p in world.parts.itertuples(index=False):
        if p.part_class not in ("C", "E"):
            continue
        wmin = weeks_min_by_class[p.part_class] if isinstance(weeks_min_by_class, dict) else float(weeks_min_by_class)
        for st in stations:
            d = net.get(p.pn, 0.0) if st == hub else dmap.get((p.pn, st), 0.0)
            if d <= 0:
                rows.append((p.pn, st, -1, 0, 0))
                continue
            s = math.ceil(wmin * d)
            S = max(s + 1, math.ceil(max_mult * s))
            rows.append((p.pn, st, s, S, 0))
    return rows


def _emergency(stations, hub):
    outs = [s for s in stations if s != hub]
    return {**{st: [hub] for st in outs}, hub: []}


def p0_rotable_plan(world: World) -> pd.DataFrame:
    """Per rotable PN: quoted annual removals, quoted pipeline mean, protection, S, loop units, AUH and outstation units."""
    cfg = world.cfg
    pb = cfg["policy_baseline_P0"]
    hub = cfg["network"]["hub"]
    outs = [s for s in world.stations.station if s != hub]
    out_min = float(pb["rotable_outstation_min_quoted_removals_per_year"])
    dem = quoted_weekly_demand(world)
    dmap = {(r.pn, r.station): r.weekly_demand for r in dem.itertuples(index=False)}
    net = dem.groupby("pn").weekly_demand.sum().to_dict()
    rows = []
    for p in world.parts[world.parts.part_class == "R"].itertuples(index=False):
        annual = net.get(p.pn, 0.0) * 52
        days = pipeline_days(world, p.pn)
        mean = annual * days / 365.0
        prot = float(pb["rotable_protection_level"][p.deadline_class])
        S = poisson_spares(mean, prot)
        loop = int(round(net.get(p.pn, 0.0) / 7.0 * days))          # units the engine seeds in the repair loop
        out_units = [st for st in outs if p.deadline_class == "D0" and dmap.get((p.pn, st), 0.0) * 52 >= out_min]
        rows.append({"pn": p.pn, "deadline_class": p.deadline_class, "quoted_annual_removals": annual,
                     "quoted_pipeline_days": days, "pipeline_mean": mean, "protection": prot, "S_total": S,
                     "loop_units": loop, "auh_base_stock": max(0, S - loop), "outstation_units": ";".join(out_units)})
    return pd.DataFrame(rows)


def build_p0(world: World) -> PolicySpec:
    cfg = world.cfg
    pb = cfg["policy_baseline_P0"]
    hub = cfg["network"]["hub"]
    stations = world.stations.station.tolist()
    dem = quoted_weekly_demand(world)
    dmap = {(r.pn, r.station): r.weekly_demand for r in dem.itertuples(index=False)}
    net = dem.groupby("pn").weekly_demand.sum().to_dict()
    rows = _cs_rows(world, pb["consumable_min_weeks_of_avg_demand"], float(pb["consumable_max_multiple_of_min"]),
                    dmap, net, stations, hub)
    for r in p0_rotable_plan(world).itertuples(index=False):
        outs = set(r.outstation_units.split(";")) if r.outstation_units else set()
        for st in stations:
            bs = r.auh_base_stock if st == hub else (1 if st in outs else 0)
            rows.append((r.pn, st, -1, 0, bs))
    sp = pd.DataFrame(rows, columns=["pn", "station", "s", "S", "base_stock"])
    return PolicySpec(policy_id="P0", label="OEM-recommended provisioning on quoted data", stock_params=sp,
                      emergency_sources=_emergency(stations, hub), lateral_transfers=False, rebalance=False,
                      expedite_purchase_on_aog=True,
                      notes=pb["rotable_float_rule"] + " | " + pb["cs_rule"])


def build_p0_naive(world: World) -> PolicySpec:
    """v1 rule kept for illustration only (NOT a policy in the comparison): rotable float =
    ceil(quoted annual removals x quoted shop TAT / 365) at AUH (+1 at outstations for D0 PNs with >= 4 quoted
    removals/yr there, taken from the float); C/E min = 6 weeks, max = 2 x min."""
    cfg = world.cfg
    pb = cfg["policy_baseline_P0"]
    hub = cfg["network"]["hub"]
    stations = world.stations.station.tolist()
    outs = [s for s in stations if s != hub]
    out_min = float(pb["rotable_outstation_min_quoted_removals_per_year"])
    dem = quoted_weekly_demand(world)
    dmap = {(r.pn, r.station): r.weekly_demand for r in dem.itertuples(index=False)}
    net = dem.groupby("pn").weekly_demand.sum().to_dict()
    rows = _cs_rows(world, float(pb["naive_consumable_min_weeks_of_avg_demand"]),
                    float(pb["consumable_max_multiple_of_min"]), dmap, net, stations, hub)
    for p in world.parts[world.parts.part_class == "R"].itertuples(index=False):
        float_n = math.ceil(net.get(p.pn, 0.0) * 52 * float(p.repair_tat_mean_d) / 365.0)
        ou = [st for st in outs if p.deadline_class == "D0" and dmap.get((p.pn, st), 0.0) * 52 >= out_min][:float_n]
        for st in stations:
            bs = max(0, float_n - len(ou)) if st == hub else (1 if st in ou else 0)
            rows.append((p.pn, st, -1, 0, bs))
    sp = pd.DataFrame(rows, columns=["pn", "station", "s", "S", "base_stock"])
    return PolicySpec(policy_id="P0-naive", label="P0-naive: stock to the mean (illustration only)", stock_params=sp,
                      emergency_sources=_emergency(stations, hub), expedite_purchase_on_aog=True,
                      notes=pb["naive_rule"])
