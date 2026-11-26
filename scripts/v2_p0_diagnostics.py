#!/usr/bin/env python
"""v2 P0 diagnostics (NOT a calibration): history + P0 on 5 selection seeds.

Writes outputs/calibration/v2_p0_diagnostics.json and .md. No target band, nothing tuned or locked.
"""
from gnm.sim.calibration import V2_DIAG_MD, v2_diagnostics

if __name__ == "__main__":
    v2_diagnostics()
    print(V2_DIAG_MD.read_text())
