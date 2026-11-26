"""Paired selection evaluation of P0 / P1 / P2 (inventory-policy agent).

Selection seeds 100-119 only; weeks 78-155, KPIs from week 104; every calibration variant.
Requires outputs/forecasting/champions.csv (scripts/run_forecasting.py).

Writes outputs/policies/: {P0,P1,P2}_stock_params.csv, policies.json, variants/<v>/...,
selection_results.parquet, selection_station_kpis.parquet, selection_class_kpis.parquet,
selection_summary.json, palm_vs_sim.csv, p2_positioning.csv, p2_threshold_sensitivity.csv.

    python scripts/evaluate_policies.py
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from gnm.config import seeds
from gnm.policy import evaluate_policies as ep
from gnm.policy import forecast_pipeline as fp
from gnm.policy.policies import build_p1, p2_positioning
from gnm.sim.api import load_world


def main(variants=None) -> dict:
    summ = ep.evaluate(variants=variants)
    world = load_world()
    ff = pd.read_parquet(fp.FC_OUT / "final_forecasts.parquet")
    p2_positioning(world, ff).to_csv(ep.POL_OUT / "p2_positioning.csv", index=False, float_format="%.4f")
    pvs = ep.palm_vs_sim(world, build_p1(world, ff), ff, seeds()["selection"])
    pvs.to_csv(ep.POL_OUT / "palm_vs_sim.csv", index=False, float_format="%.4f")
    ts = ep.threshold_sensitivity(world, ff, [0.05, 0.2, 1.0, 5.0], seeds()["selection"])
    ts.to_csv(ep.POL_OUT / "p2_threshold_sensitivity.csv", index=False)
    return {"runtime_s": summ["runtime_s"], "variants": list(summ["variants"])}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:] or None), indent=2))
