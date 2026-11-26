"""Aviation Readiness Frontier on the selection seeds (100–119). Never touches holdout seeds.

    python scripts/run_frontier.py [--demand PATH] [--out outputs/frontier] [--processes N]

--demand swaps the demand-input source (default from config/optimiser.yaml: forecasts) for e.g. the champion
forecast table (columns pn, station, rate_per_day [, deadline_class, pipeline_days, ...]).
"""
from __future__ import annotations

import argparse
import json

from gnm.optim.frontier import OUT_DIR
from gnm.optim.inputs import load_demand_inputs
from gnm.optim.pipeline import run_frontier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demand", default=None)
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--processes", type=int, default=None)
    a = ap.parse_args()
    s = run_frontier(a.out, demand=load_demand_inputs(a.demand) if a.demand else None, processes=a.processes)
    print(json.dumps({"recommended": s["recommendation"]["recommended"], "vs_base_policy": s["recommended_vs_base_policy"], "vs_P0": s["recommended_vs_P0"], "beats_base_significantly": s["recommended_beats_base_policy_significantly"],
                      "candidates_sha256": s["candidates_sha256"], "runtime_s": s["runtime_s"]}, indent=2, default=float))


if __name__ == "__main__":
    main()
