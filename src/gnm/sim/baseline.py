"""P0 — the 'legacy' static min/max + rule-of-thumb float (config: policy_baseline_P0).

P0 uses only public master data: part-master quoted figures (quoted MTBUR / quoted usage,
deadline class, part class), the applicability table, planned fleet utilisation in
aircraft_master and the planned route mix. It never looks at removal history.
"""
from __future__ import annotations

import math

import pandas as pd

from gnm.contracts import PolicySpec, World
from gnm.sim.quoted import quoted_weekly_demand  # noqa: F401  (re-exported)


def build_p0(world: World) -> PolicySpec:
    cfg = world.cfg
    pb = cfg["policy_baseline_P0"]
    hub = cfg["network"]["hub"]
    stations = world.stations.station.tolist()
    outs = [s for s in stations if s != hub]
    weeks_min = float(pb["consumable_min_weeks_of_avg_demand"])
    max_mult = float(pb["consumable_max_multiple_of_min"])
    out_min = float(pb["rotable_outstation_min_quoted_removals_per_year"])
    dem = quoted_weekly_demand(world)
    dmap = {(r.pn, r.station): r.weekly_demand for r in dem.itertuples(index=False)}
    net = dem.groupby("pn").weekly_demand.sum().to_dict()
    rows = []
    for p in world.parts.itertuples(index=False):
        if p.part_class in ("C", "E"):
            for st in stations:
                d = net.get(p.pn, 0.0) if st == hub else dmap.get((p.pn, st), 0.0)
                if d <= 0:
                    rows.append((p.pn, st, -1, 0, 0))
                    continue
                s = math.ceil(weeks_min * d)
                S = max(s + 1, math.ceil(max_mult * s))
                rows.append((p.pn, st, s, S, 0))
        else:
            annual = net.get(p.pn, 0.0) * 52
            float_n = math.ceil(annual * float(p.repair_tat_mean_d) / 365.0)
            out_units = {st: 1 for st in outs
                         if p.deadline_class == "D0" and dmap.get((p.pn, st), 0.0) * 52 >= out_min}
            out_units = dict(list(out_units.items())[:float_n])     # outstation units come out of the float
            for st in stations:
                bs = max(0, float_n - len(out_units)) if st == hub else out_units.get(st, 0)
                rows.append((p.pn, st, -1, 0, bs))
    sp = pd.DataFrame(rows, columns=["pn", "station", "s", "S", "base_stock"])
    return PolicySpec(policy_id="P0", label="Legacy static min/max + rule-of-thumb float", stock_params=sp,
                      emergency_sources={**{st: [hub] for st in outs}, hub: []}, lateral_transfers=False,
                      rebalance=False, expedite_purchase_on_aog=True,
                      notes="C/E: min = ceil(%g weeks of quoted demand), max = %g x min (AUH sized on network demand); "
                            "R: float = ceil(quoted annual removals x quoted TAT / 365), at AUH except 1 unit at an "
                            "outstation for D0 PNs with >= %g quoted removals/yr there" % (weeks_min, max_mult, out_min))
