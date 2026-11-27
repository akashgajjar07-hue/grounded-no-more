"""Demand classification: Syntetos-Boylan (ADI / CV^2) and ABC by annual usage value.

Both dimensions are computed independently and over the TRAINING window only.

Rules (also in internal development notes (kept privately))
------------------------------------------------
* Buckets: weekly demand quantities (int >= 0).
* ADI  = mean inter-demand interval, in periods, measured between successive
  non-zero periods inside the window (``np.diff`` of non-zero indices). The gap
  before the first demand is not counted because the true start of the
  "interval clock" is unknown (left censoring).
* CV^2 = (std / mean)^2 of the NON-ZERO demand sizes, population std (ddof=0).
* insufficient_data: fewer than ``min_nonzero`` (default 3) non-zero periods,
  i.e. fewer than 2 observed intervals. ADI / CV^2 are still reported when
  computable, but the class is ``insufficient_data``.
* Syntetos & Boylan (2005) cut-offs, ADI 1.32 and CV^2 0.49:
    ADI <  1.32, CV^2 <  0.49 -> smooth
    ADI <  1.32, CV^2 >= 0.49 -> erratic
    ADI >= 1.32, CV^2 <  0.49 -> intermittent
    ADI >= 1.32, CV^2 >= 0.49 -> lumpy
* ABC: annual usage value = mean weekly training demand x 52 x unit cost.
  Parts are sorted by value (descending; ties by pn). A part is A while the
  cumulative share of the parts ranked ABOVE it is < 80 %, B while < 95 %, else C
  (so the part that crosses 80 % is still A: A ~ 80 %, B ~ 15 %, C ~ 5 % of value).
  Zero-usage parts are always C.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from gnm.schemas import DemandClass

ADI_CUTOFF = 1.32
CV2_CUTOFF = 0.49
MIN_NONZERO = 3
TRAIN_WEEKS = (0, 77)


def adi_cv2(y: Sequence[float]) -> tuple[float, float, int]:
    """Return (ADI, CV^2, n_nonzero) for one bucketed series.

    ADI is NaN with < 2 non-zero periods; CV^2 is NaN with 0 non-zero periods.
    """
    y = np.asarray(y, dtype=float)
    nz = np.flatnonzero(y > 0)
    n = int(nz.size)
    adi = float(np.diff(nz).mean()) if n >= 2 else float("nan")
    if n == 0:
        cv2 = float("nan")
    else:
        sizes = y[nz]
        cv2 = float((sizes.std(ddof=0) / sizes.mean()) ** 2)
    return adi, cv2, n


def sb_class(adi: float, cv2: float, n_nonzero: int, min_nonzero: int = MIN_NONZERO) -> str:
    """Syntetos-Boylan class label (a DemandClass value)."""
    if n_nonzero < min_nonzero or not np.isfinite(adi) or not np.isfinite(cv2):
        return DemandClass.INSUFFICIENT.value
    if adi < ADI_CUTOFF:
        return (DemandClass.SMOOTH if cv2 < CV2_CUTOFF else DemandClass.ERRATIC).value
    return (DemandClass.INTERMITTENT if cv2 < CV2_CUTOFF else DemandClass.LUMPY).value


def _window_cols(demand: pd.DataFrame, weeks: tuple[int, int]) -> list:
    lo, hi = weeks
    return [c for c in demand.columns if lo <= int(c) <= hi]


def classify_demand(demand: pd.DataFrame, train_weeks: tuple[int, int] = TRAIN_WEEKS,
                    min_nonzero: int = MIN_NONZERO) -> pd.DataFrame:
    """Classify every pn of a weekly demand matrix (index = pn, columns = week ints).

    Only columns inside ``train_weeks`` (inclusive) are used.
    Returns a frame indexed by pn with adi, cv2, n_nonzero, n_periods, demand_class.
    """
    cols = _window_cols(demand, train_weeks)
    rows = []
    for pn, y in demand[cols].iterrows():
        adi, cv2, n = adi_cv2(y.to_numpy())
        rows.append({"pn": pn, "adi": adi, "cv2": cv2, "n_nonzero": n, "n_periods": len(cols),
                     "demand_class": sb_class(adi, cv2, n, min_nonzero)})
    return pd.DataFrame(rows).set_index("pn")


def abc_from_values(annual_value: pd.Series, a_share: float = 0.80, b_share: float = 0.95) -> pd.Series:
    """ABC label per index entry from annual usage value (see module docstring)."""
    v = annual_value.astype(float).fillna(0.0).clip(lower=0)
    order = sorted(v.index, key=lambda k: (-v[k], str(k)))
    total = v.sum()
    out = {}
    cum_before = 0.0
    for k in order:
        if total <= 0 or v[k] <= 0:
            out[k] = "C"
        else:
            share = cum_before / total
            out[k] = "A" if share < a_share else ("B" if share < b_share else "C")
        cum_before += v[k]
    return pd.Series(out, name="abc").reindex(annual_value.index)


def abc_classify(demand: pd.DataFrame, unit_cost: pd.Series,
                 train_weeks: tuple[int, int] = TRAIN_WEEKS) -> pd.DataFrame:
    """ABC by annual usage value over the training window. Returns pn-indexed frame."""
    cols = _window_cols(demand, train_weeks)
    annual_qty = demand[cols].mean(axis=1) * 52.0
    value = annual_qty * unit_cost.reindex(demand.index).astype(float)
    return pd.DataFrame({"annual_usage_qty": annual_qty, "annual_usage_value_aed": value,
                         "abc": abc_from_values(value)})


def build_part_attributes(demand: pd.DataFrame, part_master: pd.DataFrame | None = None,
                          train_weeks: tuple[int, int] = TRAIN_WEEKS,
                          min_nonzero: int = MIN_NONZERO) -> pd.DataFrame:
    """Part-attributes frame for the evaluation harness.

    ``part_master`` (optional) needs columns pn, part_class and unit_cost_aed.
    Output index = pn; columns: demand_class, adi, cv2, n_nonzero, part_class, abc, ...
    """
    attrs = classify_demand(demand, train_weeks, min_nonzero)
    if part_master is not None:
        pm = part_master.set_index("pn") if "pn" in part_master.columns else part_master
        pm = pm.reindex(attrs.index)
        attrs["part_class"] = pm["part_class"]
        if "unit_cost_aed" in pm:
            attrs = attrs.join(abc_classify(demand, pm["unit_cost_aed"], train_weeks))
        for c in ("unit_cost_aed", "driver", "mtbur_quoted", "lead_time_mean_d"):
            if c in pm:
                attrs[c] = pm[c]
    else:
        attrs["part_class"] = "all"
    return attrs
