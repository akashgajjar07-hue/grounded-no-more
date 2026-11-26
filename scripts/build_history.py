#!/usr/bin/env python
"""Build the airline history (weeks 0-103, history_seed, policy P0).

Writes data/processed/history/*.parquet, data/processed/grounded.duckdb and
data/ground_truth/gt_part_truth.parquet. Use --verify-stations to re-check station
coordinates against OurAirports (downloads airports.csv to data/raw/, gitignored).
"""
import argparse
import json
import time

from gnm.sim.api import build_history


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify-stations", action="store_true", help="verify station coordinates against OurAirports first")
    a = ap.parse_args()
    t = time.time()
    out = build_history(verify_stations=a.verify_stations)
    out["seconds"] = round(time.time() - t, 2)
    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
