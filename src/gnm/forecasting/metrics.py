"""Forecast accuracy and inventory-oriented metrics.

Sign convention: error e_t = forecast_t - actual_t, so positive bias = over-forecast
and positive PIS = stock carried (Wallström & Segerstedt 2010).
"""
from __future__ import annotations

from typing import NamedTuple, Sequence

import numpy as np


class MASEResult(NamedTuple):
    value: float          # NaN when undefined
    status: str           # "ok" | "undefined"
    scale: float          # in-sample naive MAE (denominator)


def _arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float).ravel()


def errors(y_true, y_pred) -> np.ndarray:
    return _arr(y_pred) - _arr(y_true)


def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(errors(y_true, y_pred))))


def bias(y_true, y_pred) -> float:
    """Mean error (forecast - actual)."""
    return float(np.mean(errors(y_true, y_pred)))


def cumulative_error(y_true, y_pred) -> np.ndarray:
    """Cumulative forecast error CFE_i = sum_{j<=i} (f_j - y_j)."""
    return np.cumsum(errors(y_true, y_pred))


def pis(y_true, y_pred) -> float:
    """Periods in stock, PIS = sum_i sum_{j<=i} (f_j - y_j) (Wallström & Segerstedt 2010).

    Interpretation: forecasts are treated as stock arriving each period; PIS > 0 counts
    unit-periods of stock carried, PIS < 0 unit-periods short.
    """
    return float(np.sum(cumulative_error(y_true, y_pred)))


def spis(y_true, y_pred, y_train) -> float:
    """Scaled PIS = PIS / mean(y_train); NaN if the training mean is 0."""
    m = float(np.mean(_arr(y_train))) if len(_arr(y_train)) else 0.0
    return pis(y_true, y_pred) / m if m > 0 else float("nan")


def mase_scale(y_train, m: int = 1) -> float:
    """In-sample one-step (lag-m) naive MAE on the training window. NaN if < m+1 obs."""
    y = _arr(y_train)
    if y.size <= m:
        return float("nan")
    return float(np.mean(np.abs(y[m:] - y[:-m])))


def mase(y_true, y_pred, y_train, m: int = 1) -> MASEResult:
    """MASE (Hyndman & Koehler 2006) with EXPLICIT naive scaling.

    MASE = MAE(test) / mean_{t=m+1..n} |y_t - y_{t-m}| (training window only).
    A zero (or undefined) denominator returns NaN with status "undefined", never inf.
    """
    scale = mase_scale(y_train, m)
    if not np.isfinite(scale) or scale <= 0:
        return MASEResult(float("nan"), "undefined", scale)
    return MASEResult(mae(y_true, y_pred) / scale, "ok", scale)


def pinball(y_true, q_pred, tau: float) -> float:
    """Mean pinball (quantile) loss: max(tau (y-q), (tau-1)(y-q))."""
    d = _arr(y_true) - _arr(q_pred)
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def quantile_coverage(actual, q_pred) -> float:
    """Share of cases with actual <= predicted quantile (target = tau)."""
    return float(np.mean(_arr(actual) <= _arr(q_pred)))


def interval_coverage(actual, lower, upper) -> float:
    """Share of cases with lower <= actual <= upper."""
    a = _arr(actual)
    return float(np.mean((a >= _arr(lower)) & (a <= _arr(upper))))


def ltd_metrics(actual_ltd: float, dist, quantiles: Sequence[float] = (0.5, 0.9, 0.95)) -> dict:
    """Lead-time-demand coverage indicator and pinball loss per quantile for one case."""
    out = {}
    qs = np.asarray(quantiles, dtype=float)
    vals = np.atleast_1d(dist.ppf(qs))
    for tau, qv in zip(qs, vals):
        key = f"{int(round(tau * 100))}"
        out[f"ltd_q{key}"] = float(qv)
        out[f"cov_q{key}"] = float(actual_ltd <= qv)
        out[f"pinball_q{key}"] = pinball([actual_ltd], [qv], float(tau))
    return out
