"""The simulator, catalogue and config must not change after the v2 P0-only calibration lock (V2-SIM-CAL)."""
import json
from pathlib import Path

from gnm.config import ROOT
from gnm.freeze import FREEZE_DIR, sha256_file

LOCK = FREEZE_DIR / "calibration_lock.json"


def test_calibration_lock_exists_and_covers_sim():
    lock = json.loads(LOCK.read_text())
    arts = lock["artefacts"]
    assert "config/assumptions.yaml" in arts and "outputs/calibration/p0_history_summary.json" in arts
    assert "config/part_catalogue.csv" in arts and lock["version"] == "v2" and lock.get("superseded_v1")
    sim = {str(p.relative_to(ROOT)) for p in (ROOT / "src" / "gnm" / "sim").glob("*.py")}
    assert sim <= set(arts), f"sim files not covered by the lock: {sorted(sim - set(arts))}"
    assert lock["policy_used"] == "P0 only"


def test_locked_files_unchanged():
    lock = json.loads(LOCK.read_text())
    changed = [k for k, v in lock["artefacts"].items() if not (ROOT / k).exists() or sha256_file(ROOT / k) != v]
    assert not changed, ("calibration-locked files changed since the lock (re-lock only for documented "
                         f"non-calibration fixes, logged in docs/DECISIONS.md): {changed}")
