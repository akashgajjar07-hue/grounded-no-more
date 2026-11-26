#!/usr/bin/env python
"""v2 P0-only calibration summary: writes outputs/calibration/p0_history_summary.json."""
from gnm.sim.calibration import calibrate

if __name__ == "__main__":
    out = calibrate()
    for v, b in out["variants"].items():
        h, s = b["history"], b["selection_p0_mean"]
        print(f"{v} (scale {b['true_mtbur_scale']}): rotable fill {h['rotable_immediate_fill_rate']:.3f}/{s['rotable_immediate_fill_rate']:.3f}"
              f" AOG {h['aog_hours_per_year']:.0f}/{s['aog_hours_per_year']:.0f} events {h['aog_events_per_year']:.0f}/{s['aog_events_per_year']:.0f}"
              f" capital {s['spare_capital_aed']/1e6:.1f}M in_band(pooled)={b['in_central_band']}")
