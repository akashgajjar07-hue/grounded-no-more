#!/usr/bin/env python
"""P0-only calibration check (SIM-CAL): writes outputs/calibration/p0_history_summary.json."""
import json

from gnm.sim.calibration import calibrate

if __name__ == "__main__":
    out = calibrate()
    for v, b in out["variants"].items():
        print(v, json.dumps({k: round(x, 3) for k, x in b["history"].items()}), b["in_central_band"])
        print("   y1", round(b["history_year1"]["aog_hours_per_year"]), "y2", round(b["history_year2"]["aog_hours_per_year"]),
              "sel", {k: round(x, 3) for k, x in b["selection_p0_mean"].items() if k not in ("seeds", "weeks")})
