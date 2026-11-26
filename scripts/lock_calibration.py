#!/usr/bin/env python
"""Lock the P0-only calibration (SIM-CAL).

Hashes config/assumptions.yaml, src/gnm/sim/*.py and outputs/calibration/p0_history_summary.json
into outputs/freeze/calibration_lock.json (separate from the holdout freeze manifest.json).
tests/test_calibration_lock.py fails if any of these files change afterwards. Re-lock only for
documented non-calibration fixes, logged in docs/DECISIONS.md.

Usage: python scripts/lock_calibration.py [--recalibrate] [--note "..."]
"""
import argparse
import datetime as dt
import json

from gnm.config import ROOT
from gnm.freeze import FREEZE_DIR, sha256_file

LOCK = FREEZE_DIR / "calibration_lock.json"
SUMMARY = ROOT / "outputs" / "calibration" / "p0_history_summary.json"


def locked_paths():
    return [ROOT / "config" / "assumptions.yaml", *sorted((ROOT / "src" / "gnm" / "sim").glob("*.py")), SUMMARY]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recalibrate", action="store_true", help="re-run the P0-only calibration summary first")
    ap.add_argument("--note", default="SIM-CAL: P0-only calibration locked before any P1/P2 run")
    a = ap.parse_args()
    if a.recalibrate or not SUMMARY.exists():
        from gnm.sim.calibration import calibrate
        calibrate()
    summary = json.loads(SUMMARY.read_text())
    entries = {str(p.relative_to(ROOT)): sha256_file(p) for p in locked_paths()}
    lock = {"locked_at": dt.datetime.now(dt.timezone.utc).isoformat(), "note": a.note, "policy_used": summary["policy"],
            "targets": summary["targets"],
            "achieved": {v: {"history": b["history"], "in_central_band": b["in_central_band"]}
                         for v, b in summary["variants"].items()},
            "artefacts": entries}
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(lock, indent=2))
    print(f"locked {len(entries)} files -> {LOCK.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
