"""Freeze every selection artefact before the holdout (writes outputs/freeze/manifest.json).

Frozen: forecasting champions, P0/P1/P2 parameter tables (central + variants), frontier
candidate set, policy/optimiser config and the assumption register. Commit the manifest
BEFORE running scripts/run_holdout.py so git history shows freeze -> holdout.
"""
from pathlib import Path

from gnm.config import ROOT
from gnm.freeze import freeze

ART = [
    "outputs/forecasting/champions.csv",
    "outputs/policies/P0_stock_params.csv",
    "outputs/policies/P1_stock_params.csv",
    "outputs/policies/P2_stock_params.csv",
    "outputs/frontier/candidates.json",
    "config/assumptions.yaml",
    "config/policy.yaml",
    "config/optimiser.yaml",
    "config/aog_lab.yaml",
]
ART += sorted(str(p.relative_to(ROOT)) for p in (ROOT / "outputs/policies/variants").glob("*/*_stock_params.csv"))

if __name__ == "__main__":
    m = freeze([Path(a) for a in ART], note="Selection complete: champions, policy tables, frontier candidates frozen before holdout")
    for k, v in m["artefacts"].items():
        print(f"{v[:16]}  {k}")
    print("frozen_at", m["frozen_at"])
