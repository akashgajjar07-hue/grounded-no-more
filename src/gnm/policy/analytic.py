"""Closed-form spares maths shared by policy, optimiser, AOG lab and the web float calculator.

The JS mirror in docs/js/lib/floatcalc.js must give identical results
(tests/test_floatcalc_mirror.py).

Rotables (Palm's theorem): with Poisson removals at rate lambda per day and i.i.d.
repair turnaround with mean T days (any distribution, infinite-server
approximation), the number of units in the repair pipeline X is Poisson with mean
lambda*T. With base stock S:
    availability (immediate)  A(S)  = P(X < S) = P(X <= S-1)
    expected backorders       EBO(S)= E[max(X-S, 0)]
Finite shop capacity, condemnation and transport break the assumptions, so the
event simulation validates these ("METRIC-inspired", not full METRIC).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def poisson_pmf(k: int, mu: float) -> float:
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(k * math.log(mu) - mu - math.lgamma(k + 1))


def poisson_cdf(k: int, mu: float) -> float:
    if k < 0:
        return 0.0
    return float(sum(poisson_pmf(i, mu) for i in range(k + 1)))


def pipeline_mean(rate_per_30d: float, tat_days: float) -> float:
    return rate_per_30d / 30.0 * tat_days


def availability(S: int, mu: float) -> float:
    """P(X < S): probability a serviceable spare is on the shelf at a random demand."""
    return poisson_cdf(S - 1, mu)


def fill_rate_poisson(S: int, mu: float) -> float:
    """Immediate fill rate under base-stock S (PASTA: equals P(X < S))."""
    return availability(S, mu)


def ebo(S: int, mu: float) -> float:
    """E[max(X-S,0)] = mu - S + sum_{x<S} (S-x) P(x)."""
    if S <= 0:
        return float(mu)
    tail = sum((S - x) * poisson_pmf(x, mu) for x in range(S))
    return float(mu - S + tail)


def ebo_curve(mu: float, s_max: int) -> np.ndarray:
    return np.array([ebo(s, mu) for s in range(s_max + 1)])


def expected_wait_days(S: int, mu: float, rate_per_day: float) -> float:
    """Little's law: mean backorder delay per demand = EBO / lambda."""
    if rate_per_day <= 0:
        return 0.0
    return ebo(S, mu) / rate_per_day


def float_calc(rate_per_30d: float, tat_days: float, spares: int, unit_cost_aed: float) -> dict:
    """The web float calculator, mirrored in JS."""
    mu = pipeline_mean(rate_per_30d, tat_days)
    lam = rate_per_30d / 30.0
    return {
        "pipeline_mean": mu,
        "availability": availability(spares, mu),
        "ebo": ebo(spares, mu),
        "expected_wait_days": expected_wait_days(spares, mu, lam),
        "capital_aed": spares * unit_cost_aed,
    }


def compare_levers(rate_per_30d: float, tat_days: float, spares: int, unit_cost_aed: float,
                   tat_cut_days: float, extra_spares: int, accel_cost_per_day_per_unit: float) -> dict:
    """'Buy N more spares' vs 'cut repair TAT by d days' (annual removals x d x cost/day)."""
    base = float_calc(rate_per_30d, tat_days, spares, unit_cost_aed)
    more = float_calc(rate_per_30d, tat_days, spares + extra_spares, unit_cost_aed)
    faster = float_calc(rate_per_30d, max(tat_days - tat_cut_days, 0.0), spares, unit_cost_aed)
    annual_removals = rate_per_30d * 365.0 / 30.0
    return {
        "base": base,
        "extra_spares": {**more, "incremental_capital_aed": extra_spares * unit_cost_aed,
                         "incremental_annual_aed": 0.0},
        "tat_cut": {**faster, "incremental_capital_aed": 0.0,
                    "incremental_annual_aed": annual_removals * tat_cut_days * accel_cost_per_day_per_unit},
    }


# ---- consumables / expendables: lead-time demand ----

def nb_params(mean: float, var: float) -> tuple[float, float] | None:
    """scipy nbinom (n, p) from mean/variance; None if not overdispersed."""
    if var <= mean or mean <= 0:
        return None
    p = mean / var
    n = mean * p / (1 - p)
    return n, p


def reorder_point(ltd_mean: float, service: float, ltd_var: float | None = None) -> int:
    """Smallest s with P(LTD <= s) >= service (cycle service level).

    Poisson when var is None or <= mean; negative binomial when overdispersed.
    """
    if ltd_mean <= 0:
        return 0
    nb = nb_params(ltd_mean, ltd_var) if ltd_var is not None else None
    if nb is None:
        return int(stats.poisson.ppf(service, ltd_mean))
    return int(stats.nbinom.ppf(service, nb[0], nb[1]))


def reorder_point_empirical(samples: np.ndarray, service: float) -> int:
    """From a bootstrap LTD distribution (e.g. Willemain)."""
    samples = np.asarray(samples)
    if samples.size == 0:
        return 0
    return int(np.ceil(np.quantile(samples, service, method="higher")))
