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
