#!/usr/bin/env python
"""Lock the v2 P0-only calibration (V2-SIM-CAL).

Hashes config/assumptions.yaml, config/part_catalogue.csv, src/gnm/sim/*.py and
outputs/calibration/p0_history_summary.json into outputs/freeze/calibration_lock.json (separate from the
holdout freeze manifest.json). The previous (v1) lock is kept inside under "superseded_v1".
tests/test_calibration_lock.py fails if any locked file changes afterwards. Re-lock only for documented
non-calibration fixes, logged in docs/DECISIONS.md.

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
    return [ROOT / "config" / "assumptions.yaml", ROOT / "config" / "part_catalogue.csv",
            *sorted((ROOT / "src" / "gnm" / "sim").glob("*.py")), SUMMARY]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recalibrate", action="store_true", help="re-run the P0-only calibration summary first")
    ap.add_argument("--note", default="V2-SIM-CAL: v2 P0-only calibration locked before any v2 P1/P2/optimiser run")
    a = ap.parse_args()
    if a.recalibrate or not SUMMARY.exists():
        from gnm.sim.calibration import calibrate
        calibrate()
    summary = json.loads(SUMMARY.read_text())
    prev = json.loads(LOCK.read_text()) if LOCK.exists() else None
    superseded = None
    if prev is not None:
        superseded = prev.get("superseded_v1") if prev.get("version") == "v2" else prev
    entries = {str(p.relative_to(ROOT)): sha256_file(p) for p in locked_paths()}
    lock = {"version": "v2", "locked_at": dt.datetime.now(dt.timezone.utc).isoformat(), "note": a.note,
            "policy_used": summary["policy"], "targets": summary["targets"], "variant_targets": summary["variant_targets"],
            "settings_used": summary["settings_used"],
            "achieved": {v: {"history": b["history"], "selection_p0_mean": b["selection_p0_mean"],
                             "pooled_history_selection": b["pooled_history_selection"],
                             "in_central_band": b["in_central_band"], "true_mtbur_scale": b["true_mtbur_scale"]}
                         for v, b in summary["variants"].items()},
            "artefacts": entries, "superseded_v1": superseded}
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(lock, indent=2))
    print(f"locked {len(entries)} files -> {LOCK.relative_to(ROOT)}")
    print("lock sha256:", sha256_file(LOCK))


if __name__ == "__main__":
    main()
