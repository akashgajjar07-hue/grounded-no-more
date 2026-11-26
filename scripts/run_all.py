"""Reproduce the whole pipeline end to end (selection stage), then check reproducibility.

    python scripts/run_all.py            # history -> forecasting -> policies -> frontier -> AOG lab -> exports -> docs
    python scripts/run_all.py --check    # + verify every frozen artefact re-derives byte-identically

The holdout is NOT re-run here: it runs once (scripts/run_holdout.py) and its log refuses a
second run. The exporter reads the committed holdout outputs in outputs/holdout/.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("Simulated history (weeks 0-103, P0)", ["scripts/build_history.py"]),
    ("Forecasting evaluation + champions", ["scripts/run_forecasting.py"]),
    ("P0/P1/P2 selection evaluation", ["scripts/evaluate_policies.py"]),
    ("Readiness Frontier (selection)", ["scripts/run_frontier.py"]),
    ("AOG Response Lab + Planner actions", ["scripts/run_aog_lab.py"]),
    ("Site data export", ["scripts/export_site.py"]),
    ("Render docs from outputs", ["scripts/render_docs.py"]),
]


def main() -> int:
    t0 = time.time()
    for label, cmd in STEPS:
        path = ROOT / cmd[0]
        if not path.exists():
            print(f"-- skip  {label}: {cmd[0]} not present")
            continue
        s = time.time()
        r = subprocess.run([sys.executable, *cmd], cwd=ROOT)
        print(f"{'ok  ' if r.returncode == 0 else 'FAIL'}  {label}  ({time.time() - s:.1f}s)")
        if r.returncode:
            return r.returncode
    if "--check" in sys.argv:
        from gnm.freeze import verify
        verify()   # raises if any frozen artefact no longer re-derives identically
        print("ok    frozen artefacts re-derive byte-identically (gnm.freeze.verify)")
    print(f"done in {(time.time() - t0) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
