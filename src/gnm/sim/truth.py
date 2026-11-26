"""Hidden ground truth of the synthetic world.

Only ``gnm.sim.generator`` (and ``gnm.eval.truth_recovery``) may import this module.
The event engine, forecasting, policy, optimiser, AOG and export code must never see it
(``tests/test_leakage.py`` and ``tests/test_sim_engine.py`` scan the source).

The table written to ``data/ground_truth/gt_part_truth.parquet`` follows the
``gt_part_truth`` schema in :mod:`gnm.schemas`, plus two compatible extra columns
(``repair_tat_cv_true``, ``lead_time_cv_true``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from gnm import schemas
from gnm.config import GROUND_TRUTH

GT_FILE = "gt_part_truth.parquet"


@dataclass
class GroundTruth:
    """True generator parameters per PN (index aligned with World.parts order)."""
    parts: pd.DataFrame                      # gt_part_truth columns (+ extras)
    world_seed: int
    planted: dict = field(default_factory=dict)   # PS id -> {pn, station, weeks, note}

    # convenient column accessors (numpy, aligned with parts order)
    def col(self, name: str) -> np.ndarray:
        return self.parts[name].to_numpy()

    def by_pn(self) -> pd.DataFrame:
        return self.parts.set_index("pn")

    def table(self) -> pd.DataFrame:
        cols = schemas.TABLES["gt_part_truth"].colnames + ["repair_tat_cv_true", "lead_time_cv_true"]
        df = self.parts[cols].copy()
        df["lead_time_change_week"] = df["lead_time_change_week"].astype("Int64")
        return df

    def write(self, directory: Path | None = None) -> Path:
        directory = Path(directory or GROUND_TRUTH)
        directory.mkdir(parents=True, exist_ok=True)
        df = self.table()
        errs = schemas.validate_table("gt_part_truth", df)
        if errs:
            raise ValueError(errs)
        path = directory / GT_FILE
        df.to_parquet(path, index=False)
        return path
