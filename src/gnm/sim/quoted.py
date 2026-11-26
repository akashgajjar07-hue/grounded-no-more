"""Expected demand from PUBLIC quoted figures (part master + planned schedule + maintenance programme).

Shared by P0 (gnm.sim.baseline) and the engine's steady-state initialisation. Never reads truth.
"""
from __future__ import annotations

import pandas as pd

from gnm.contracts import World


def quoted_weekly_demand(world: World) -> pd.DataFrame:
    """Expected weekly demand per (pn, station) from quoted figures and the planned schedule."""
    cfg = world.cfg
    hub = cfg["network"]["hub"]
    mix = cfg["network"]["route_mix"]
    ac = world.aircraft
    util = {a: {"n": int((ac.archetype == a).sum()), "FH": float(ac.loc[ac.archetype == a, "fh_per_day_mean"].mean()),
                "FC": float(ac.loc[ac.archetype == a, "fc_per_day_mean"].mean())} for a in ac.archetype.unique()}
    parts = world.parts.set_index("pn")
    rows = []
    for a in world.applicability.itertuples(index=False):
        p = parts.loc[a.pn]
        u = util.get(a.archetype)
        if u is None or not p.mtbur_quoted or pd.isna(p.mtbur_quoted):
            continue
        if p.part_class == "C":
            wk = u["n"] * u["FC"] * 7 / p.mtbur_quoted                    # quoted FC per unit consumed, per aircraft
        else:
            wk = u["n"] * a.qty_per_aircraft * u[p.driver] * 7 / p.mtbur_quoted
        rows.append((a.pn, hub, 0.5 * wk))                                  # half of all arrivals are at the hub
        tot = sum(mix[a.archetype].values())
        for st, w in mix[a.archetype].items():
            rows.append((a.pn, st, 0.5 * wk * w / tot))
    # scheduled A-check kits at the check station (maintenance programme = planning data, not history)
    sc = cfg["maintenance"]["scheduled_checks"]
    lines = (sc["kit_lines_per_check"][0] + sc["kit_lines_per_check"][1]) / 2
    kq = sum(cfg["generator"]["kit_line_qty"]) / 2
    for arch, u in util.items():
        pool = [p for p in world.kit_eligible if ((world.applicability.pn == p) & (world.applicability.archetype == arch)).any()]
        if not pool:
            continue
        checks_wk = u["n"] * u["FH"] * 7 / sc["A_check_interval_fh"][arch]
        for p in pool:
            rows.append((p, sc["A_check_station"], checks_wk * min(1.0, lines / len(pool)) * kq))
    d = pd.DataFrame(rows, columns=["pn", "station", "weekly_demand"])
    return d.groupby(["pn", "station"], as_index=False).weekly_demand.sum()



def pipeline_days(world: World, pn: str) -> float:
    """Quoted rotable pipeline time, on the engine's definition (V2-SIM-11): quoted shop TAT + vendor transit
    both ways + core return (outstation -> AUH) weighted by the share of removals rectified at an outstation
    under the airline's own practice: D0 removals stay where found (planning split 50% outstation arrivals);
    deferrable D3/D10 removals are mostly rectified at the hub (generator.deferred_to_hub_share, the airline's
    deferral practice); wear-planned removals are always done at the hub."""
    cfg = world.cfg
    p = world.parts.set_index("pn").loc[pn]
    shop = world.repair_shops.get(p.repair_shop, {"transit_days": 0.0})
    out_share = 0.5
    if getattr(p, "removal_mode", "unscheduled") == "wear_planned":
        out_share = 0.0
    elif p.deadline_class != "D0":
        out_share = 0.5 * (1.0 - float(cfg["generator"].get("deferred_to_hub_share", 0.0)))
    ret = cfg["network"]["removed_unit_return_days"]["mean"] * out_share
    return float(p.repair_tat_mean_d) + 2 * float(shop["transit_days"]) + ret
