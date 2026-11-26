#!/usr/bin/env python
"""MEASURE ONLY: raw P0 variants V1–V4 (after decisions A), in memory. Nothing is written to config.

V1 quote accuracy; V2 legacy line-station kit (wheel/tyre assemblies + crew oxygen masks at every outstation
the applicable fleet type serves, min 1 per PN per station); V3 = V1 + V2; V4 = V3 + AOG-market settings (reference).
Writes outputs/calibration/v2_p0_variants.json.
"""
import copy
import json

import numpy as np

from gnm.config import OUTPUTS, load_config
from gnm.sim.baseline import build_p0
from gnm.sim.calibration import _request_aog, history_metrics
from gnm.sim.engine import run_policy
from gnm.sim.generator import generate_scenario, generate_world

BAND = {"rotable_immediate_fill_rate": (0.78, 0.85), "aog_hours_per_year": (1200, 2700), "aog_events_per_year": (60, 100)}
LINE_KIT_FAMILIES = ("wheel_tyre", "crew_mask")
LINE_KIT_MIN = 1


def quotes(cfg):
    cfg["parts"]["quoted_mtbur_optimism"] = 1.10
    cfg["parts"]["quoted_mtbur_noise_sd_log"] = 0.20
    cfg["generator"]["quoted_tat_optimism"] = 0.95
    cfg["generator"]["quoted_tat_noise_sd_log"] = 0.10


def market(cfg):
    a = cfg["aog_sourcing"]
    a["robbery"]["availability"] = 0.75
    a["exchange_loan"]["availability"] = {"narrowbody": 0.90, "widebody": 0.65}
    a["exchange_loan"]["response_hours"] = {"narrowbody": [18, 36], "widebody": [36, 96]}
    a["local_buy"]["availability"] = 0.99


def line_kit(world, pol):
    """Add a minimum line-station kit (>= LINE_KIT_MIN) at every outstation served by an applicable fleet type."""
    sp = pol.stock_params.copy()
    mix = world.cfg["network"]["route_mix"]
    parts = world.parts.set_index("pn")
    for pn in parts.index[parts.family.isin(LINE_KIT_FAMILIES)]:
        archs = world.applicability.archetype[world.applicability.pn == pn]
        served = {st for a in archs for st in mix[a]}
        for st in served:
            m = (sp.pn == pn) & (sp.station == st)
            if parts.loc[pn, "part_class"] == "R":
                sp.loc[m, "base_stock"] = np.maximum(sp.loc[m, "base_stock"], LINE_KIT_MIN)
            else:
                sp.loc[m, "s"] = np.maximum(sp.loc[m, "s"], LINE_KIT_MIN - 1)
                sp.loc[m, "S"] = np.maximum(sp.loc[m, "S"], np.maximum(LINE_KIT_MIN, sp.loc[m, "s"] + 1))
    pol.stock_params = sp
    pol.policy_id += "+linekit"
    return pol


VARIANTS = {"V0 raw P0 (after A)": (False, False, False), "V1 quote accuracy": (True, False, False),
            "V2 legacy line-kit": (False, True, False), "V3 = V1 + V2": (True, True, False),
            "V4 = V3 + AOG market (reference)": (True, True, True)}


def measure(name, q, k, m):
    cfg = copy.deepcopy(load_config())
    if q:
        quotes(cfg)
    if m:
        market(cfg)
    w, gt = generate_world(cfg)
    pol = build_p0(w)
    if k:
        pol = line_kit(w, pol)
    runs = [(7, 0, 103, 0, 103)] + [(s, 78, 155, 104, 155) for s in range(100, 105)]
    hist, sel, top, trig, stat = None, [], None, None, None
    for seed, s0, s1, k0, k1 in runs:
        res = run_policy(w, generate_scenario(w, gt, seed, s0, s1), pol, k0, k1)
        met = history_metrics(w, res, k0, k1)
        met["capital"] = res.kpis["spare_capital_aed"]
        if seed == 7:
            hist = met
            rq = _request_aog(w, res, (s1 + 1) * 168).merge(w.parts[["pn", "removal_mode"]], on="pn")
            a = rq[rq.aog_h > 0]
            yrs = 2.0
            top = (a.groupby(["pn", "description", "part_class", "deadline_class", "removal_mode", "unit_cost_aed"]).aog_h.sum()
                   .div(yrs).sort_values(ascending=False).head(10).round(0).reset_index().to_dict(orient="records"))
            tot = a.aog_h.sum()
            trig = (a.groupby("trigger").aog_h.sum() / tot).round(3).to_dict()
            stat = (a.groupby("station").aog_h.sum() / tot).round(3).sort_values(ascending=False).to_dict()
        else:
            sel.append(met)
    selm = {x: float(np.mean([s[x] for s in sel])) for x in sel[0]}
    inside = {k: bool(lo <= hist[k] <= hi and lo <= selm[k] <= hi) for k, (lo, hi) in BAND.items()}
    return {"history": hist, "selection_mean": selm, "inside_band": inside, "all_inside": all(inside.values()),
            "top10_history": top, "aog_share_by_trigger": trig, "aog_share_by_station": stat,
            "line_kit_units": int((pol.stock_params.base_stock.sum())) if k else None}


def main():
    out = {}
    for name, (q, k, m) in VARIANTS.items():
        out[name] = measure(name, q, k, m)
        h, s = out[name]["history"], out[name]["selection_mean"]
        print(f"{name}: rot {h['rotable_immediate_fill_rate']:.3f}/{s['rotable_immediate_fill_rate']:.3f} "
              f"hub {h['rotable_hub_pool_fill_rate']:.3f}/{s['rotable_hub_pool_fill_rate']:.3f} "
              f"all {h['immediate_fill_rate']:.3f}/{s['immediate_fill_rate']:.3f} "
              f"AOG {h['aog_hours_per_year']:.0f}/{s['aog_hours_per_year']:.0f} ev {h['aog_events_per_year']:.0f}/{s['aog_events_per_year']:.0f} "
              f"cap {h['capital']/1e6:.1f}/{s['capital']/1e6:.1f} inside={out[name]['inside_band']}")
    (OUTPUTS / "calibration" / "v2_p0_variants.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
