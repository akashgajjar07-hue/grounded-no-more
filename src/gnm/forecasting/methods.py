"""Forecasting methods for intermittent / lumpy spare-parts demand.

All methods share ONE interface::

    fit_predict(y_train: np.ndarray, h: int, **ctx) -> Forecast

* ``y_train`` holds the demand buckets strictly BEFORE the forecast origin. Nothing
  else about the series is visible to the method, so smoothing parameters, windows
  and bootstrap transition matrices are chosen from training data only.
* ``ctx`` carries optional side information (``seed``, exposure arrays, priors).
  Unknown keys are ignored, so the harness can pass the same ctx to every method.
* ``Forecast.mean`` is the per-period point forecast (length h).
* ``Forecast.dist`` (optional) is the distribution of TOTAL demand over the h
  periods (lead-time demand, LTD). ``Forecast.ltd_dist()`` falls back to a
  Poisson with mean ``sum(mean)`` for point-only methods.

Formulas and references: internal development notes (kept privately).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy import optimize, stats

ALPHA_GRID = (0.05, 0.1, 0.15, 0.2, 0.25, 0.3)
MA_WINDOWS = (2, 3, 4, 6, 8, 13, 26)


# --------------------------------------------------------------------------- containers
@dataclass
class LTDDist:
    """Distribution of total demand over a horizon (lead-time demand)."""
    kind: str                         # "empirical" | "poisson" | "nbinom" | "degenerate"
    samples: np.ndarray | None = None
    mu: float = 0.0                   # poisson mean
    n: float = 0.0                    # nbinom size (scipy parametrisation)
    p: float = 1.0                    # nbinom success prob

    def mean(self) -> float:
        if self.kind == "empirical":
            return float(np.mean(self.samples))
        if self.kind == "poisson":
            return float(self.mu)
        if self.kind == "nbinom":
            return float(stats.nbinom.mean(self.n, self.p))
        return float(self.mu)

    def var(self) -> float:
        if self.kind == "empirical":
            return float(np.var(self.samples))
        if self.kind == "poisson":
            return float(self.mu)
        if self.kind == "nbinom":
            return float(stats.nbinom.var(self.n, self.p))
        return 0.0

    def ppf(self, q):
        """Smallest integer k with P(X <= k) >= q (vectorised over q)."""
        q = np.asarray(q, dtype=float)
        if self.kind == "empirical":
            s = np.sort(np.asarray(self.samples))
            idx = np.clip(np.ceil(q * s.size).astype(int) - 1, 0, s.size - 1)
            return s[idx].astype(float)
        if self.kind == "poisson":
            return stats.poisson.ppf(q, self.mu) if self.mu > 0 else np.zeros_like(q)
        if self.kind == "nbinom":
            return stats.nbinom.ppf(q, self.n, self.p)
        return np.full_like(q, self.mu)

    def cdf(self, k):
        k = np.asarray(k, dtype=float)
        if self.kind == "empirical":
            s = np.sort(np.asarray(self.samples))
            return np.searchsorted(s, k, side="right") / s.size
        if self.kind == "poisson":
            return stats.poisson.cdf(k, self.mu) if self.mu > 0 else (k >= 0).astype(float)
        if self.kind == "nbinom":
            return stats.nbinom.cdf(k, self.n, self.p)
        return (k >= self.mu).astype(float)


@dataclass
class Forecast:
    mean: np.ndarray
    dist: LTDDist | None = None
    method: str = ""
    params: dict = field(default_factory=dict)

    def ltd_dist(self) -> LTDDist:
        if self.dist is not None:
            return self.dist
        mu = float(np.sum(self.mean))
        return LTDDist("poisson", mu=max(mu, 0.0))


def _flat(value: float, h: int) -> np.ndarray:
    return np.full(h, float(value))


def _as1d(y) -> np.ndarray:
    y = np.asarray(y, dtype=float).ravel()
    if np.any(~np.isfinite(y)):
        raise ValueError("y_train must be finite (impute or drop missing values first)")
    return y


# --------------------------------------------------------------------------- SES helpers
def ses(x: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    """Simple exponential smoothing, level initialised to x[0].

    fitted[0] = NaN, fitted[1] = x[0], fitted[t+1] = alpha*x[t] + (1-alpha)*fitted[t];
    returns (one-step forecast after the last obs, fitted). Same convention as
    statsforecast's ``_ses_forecast``.
    """
    x = np.asarray(x, dtype=float)
    fitted = np.full(x.size, np.nan)
    level = x[0]
    for t in range(1, x.size):
        fitted[t] = level
        level = alpha * x[t] + (1 - alpha) * level
    return float(level), fitted


def ses_sse(x: np.ndarray, alpha: float) -> float:
    _, f = ses(x, alpha)
    return float(np.nansum((x[1:] - f[1:]) ** 2)) if x.size > 1 else 0.0


def optimized_ses(x: np.ndarray, bounds=(0.1, 0.3)) -> tuple[float, float]:
    """SES with alpha minimising in-sample one-step SSE inside ``bounds``.

    Returns (forecast, alpha). Bounded scalar minimisation (Brent/golden), the same
    search space as statsforecast's optimised SES.
    """
    x = np.asarray(x, dtype=float)
    if x.size < 2:
        return float(x[0]) if x.size else 0.0, bounds[0]
    res = optimize.minimize_scalar(lambda a: ses_sse(x, a), bounds=bounds, method="bounded",
                                   options={"xatol": 1e-8})
    alpha = float(res.x)
    return ses(x, alpha)[0], alpha


def intervals(y: np.ndarray) -> np.ndarray:
    """Inter-demand intervals; the first one is counted from period -1 (index+1)."""
    nz = np.flatnonzero(y != 0)
    return np.diff(nz + 1, prepend=0).astype(float)


# --------------------------------------------------------------------------- simple methods
def zero(y_train, h, **ctx) -> Forecast:
    return Forecast(np.zeros(h), method="zero")


def naive(y_train, h, **ctx) -> Forecast:
    y = _as1d(y_train)
    last = y[-1] if y.size else 0.0
    return Forecast(_flat(last, h), method="naive", params={"last": float(last)})


def moving_average(y_train, h, window: int | None = None, windows=MA_WINDOWS, **ctx) -> Forecast:
    """Moving average; window chosen by in-sample one-step MSE on y_train only.

    All candidate windows are scored on the same periods t >= max(candidate) so the
    comparison is fair. Ties -> the longer window (smoother).
    """
    y = _as1d(y_train)
    n = y.size
    if n == 0:
        return Forecast(np.zeros(h), method="ma", params={"window": 0})
    if window is None:
        cands = [k for k in windows if k <= max(n // 2, 1)] or [max(min(n, 2), 1)]
        kmax = max(cands)
        best, window = np.inf, cands[0]
        if n > kmax:
            cs = np.concatenate([[0.0], np.cumsum(y)])
            for k in cands:
                t = np.arange(kmax, n)
                f = (cs[t] - cs[t - k]) / k
                mse = float(np.mean((y[t] - f) ** 2))
                if mse <= best + 1e-12:
                    best, window = mse, k
    window = int(min(window, n))
    return Forecast(_flat(y[-window:].mean(), h), method="ma", params={"window": window})


# --------------------------------------------------------------------------- Croston family
def croston_states(y: np.ndarray, alpha_z: float, alpha_p: float):
    """Croston (1972) recursion.

    z = smoothed non-zero demand size, p = smoothed inter-demand interval.
    Init (statsforecast 'classic' convention): z_1 = first non-zero size,
    p_1 = index of first demand + 1. Both are updated ONLY in periods with demand:
        z <- z + alpha_z (y_t - z),  p <- p + alpha_p (q_t - p)
    where q_t = periods since the previous demand.

    Returns (z_final, p_final, fitted) with fitted[t] = z/p as known at end of t-1
    (NaN up to and including the first demand period).
    """
    y = np.asarray(y, dtype=float)
    nz = np.flatnonzero(y > 0)
    fitted = np.full(y.size, np.nan)
    if nz.size == 0:
        return 0.0, np.nan, fitted
    z, p = y[nz[0]], float(nz[0] + 1)
    last = nz[0]
    for t in range(nz[0] + 1, y.size):
        fitted[t] = z / p
        if y[t] > 0:
            z = z + alpha_z * (y[t] - z)
            p = p + alpha_p * ((t - last) - p)
            last = t
    return float(z), float(p), fitted


def _croston_like(y_train, h, alpha, sba: bool, name: str, alphas=ALPHA_GRID) -> Forecast:
    y = _as1d(y_train)
    nz = np.flatnonzero(y > 0)
    if nz.size == 0:
        return Forecast(np.zeros(h), method=name, params={"alpha": np.nan, "z": 0.0, "p": np.nan})

    def factor(a):
        return (1 - a / 2) if sba else 1.0

    chosen = "fixed"
    if alpha is None or alpha == "opt":
        chosen = "opt"
        if nz.size < 2:
            alpha = 0.1
            chosen = "default(<2 demands)"
        else:
            best = np.inf
            for a in alphas:
                _, _, f = croston_states(y, a, a)
                m = ~np.isnan(f)
                mse = float(np.mean((y[m] - factor(a) * f[m]) ** 2)) if m.any() else np.inf
                if mse < best - 1e-12:
                    best, alpha = mse, a
    z, p, _ = croston_states(y, alpha, alpha)
    level = factor(alpha) * z / p
    return Forecast(_flat(level, h), method=name,
                    params={"alpha": float(alpha), "z": z, "p": p, "alpha_choice": chosen})


def croston(y_train, h, alpha=None, **ctx) -> Forecast:
    """Croston: forecast = z / p. ``alpha=None`` -> grid search on training MSE."""
    return _croston_like(y_train, h, alpha, sba=False, name="croston")


def sba(y_train, h, alpha=None, **ctx) -> Forecast:
    """Syntetos-Boylan approximation: (1 - alpha/2) * z / p."""
    return _croston_like(y_train, h, alpha, sba=True, name="sba")


def tsb_states(y: np.ndarray, alpha_p: float, alpha_z: float):
    """Teunter-Syntetos-Babai (2011).

    d = smoothed demand-occurrence probability, updated EVERY period:
        d <- d + alpha_p (1{y_t>0} - d)
    z = smoothed size, updated only when y_t > 0:  z <- z + alpha_z (y_t - z)
    Init: d_1 = 1{y_0 > 0}; z_1 = first non-zero size. Forecast = d * z.
    fitted[t] = d*z as known at end of t-1 (NaN until z exists).
    """
    y = np.asarray(y, dtype=float)
    nz = np.flatnonzero(y > 0)
    fitted = np.full(y.size, np.nan)
    if nz.size == 0:
        return 0.0, 0.0, fitted
    d = float(y[0] > 0)
    z = np.nan
    for t in range(y.size):
        if t > 0:
            # update d with period t-1 already done; d currently reflects 0..t-1
            if not np.isnan(z):
                fitted[t] = d * z
            d = d + alpha_p * (float(y[t] > 0) - d)
        if y[t] > 0:
            z = y[t] if np.isnan(z) else z + alpha_z * (y[t] - z)
    return float(d), float(z), fitted


def tsb(y_train, h, alpha_p=None, alpha_z=None, alphas=ALPHA_GRID, **ctx) -> Forecast:
    """TSB; (alpha_p, alpha_z) by grid search on training one-step MSE if not given."""
    y = _as1d(y_train)
    if not np.any(y > 0):
        return Forecast(np.zeros(h), method="tsb", params={"alpha_p": np.nan, "alpha_z": np.nan})
    chosen = "fixed"
    if alpha_p is None or alpha_z is None:
        chosen = "opt"
        best = np.inf
        ap0, az0 = alpha_p, alpha_z
        for ap in ([ap0] if ap0 is not None else alphas):
            for az in ([az0] if az0 is not None else alphas):
                _, _, f = tsb_states(y, ap, az)
                m = ~np.isnan(f)
                mse = float(np.mean((y[m] - f[m]) ** 2)) if m.any() else np.inf
                if mse < best - 1e-12:
                    best, alpha_p, alpha_z = mse, ap, az
        if alpha_p is None:
            alpha_p, alpha_z = 0.1, 0.1
    d, z, _ = tsb_states(y, alpha_p, alpha_z)
    return Forecast(_flat(d * z, h), method="tsb",
                    params={"alpha_p": float(alpha_p), "alpha_z": float(alpha_z), "d": d, "z": z,
                            "alpha_choice": chosen})


# --------------------------------------------------------------------------- temporal aggregation
def _chunk_sums_recent(y: np.ndarray, level: int) -> np.ndarray:
    """Non-overlapping bucket sums, dropping the OLDEST remainder (keeps recent data)."""
    cut = y.size % level
    yc = y[cut:]
    return yc.reshape(-1, level).sum(axis=1)


def adida(y_train, h, **ctx) -> Forecast:
    """ADIDA (Nikolopoulos et al. 2011): aggregate to buckets of
    round(mean inter-demand interval) periods, optimised SES on bucket sums
    (alpha in [0.1, 0.3]), disaggregate by equal weights."""
    y = _as1d(y_train)
    if not np.any(y != 0):
        return Forecast(np.zeros(h), method="adida", params={"level": 0})
    level = max(int(round(float(intervals(y).mean()))), 1)
    sums = _chunk_sums_recent(y, level)
    if sums.size == 0:
        sums = np.array([y.sum()])
    f, a = optimized_ses(sums)
    return Forecast(_flat(f / level, h), method="adida", params={"level": level, "alpha": a})


def imapa(y_train, h, **ctx) -> Forecast:
    """IMAPA (Petropoulos & Kourentzes 2015): mean of ADIDA-style forecasts over
    aggregation levels 1..round(mean inter-demand interval)."""
    y = _as1d(y_train)
    if not np.any(y != 0):
        return Forecast(np.zeros(h), method="imapa", params={"max_level": 0})
    kmax = max(int(round(float(intervals(y).mean()))), 1)
    fs = []
    for level in range(1, kmax + 1):
        sums = _chunk_sums_recent(y, level)
        if sums.size == 0:
            continue
        fs.append(optimized_ses(sums)[0] / level)
    return Forecast(_flat(np.mean(fs), h), method="imapa", params={"max_level": kmax})


# --------------------------------------------------------------------------- bootstrap
def willemain_bootstrap(y_train, h, n_samples: int = 2000, seed: int = 0, jitter: bool = True,
                        **ctx) -> Forecast:
    """Willemain, Smart & Schwarz (2004) bootstrap of lead-time demand over h periods.

    1. Occurrence: 2-state Markov chain (zero / non-zero) with transition
       probabilities = observed transition counts in y_train; a state never left in
       the history falls back to the marginal occurrence rate. The chain starts
       from the state of the LAST training period.
    2. Sizes: resampled with replacement from the historical non-zero sizes.
    3. Jitter: J = round(X + Z sqrt(X)), Z ~ N(0,1); if J < 1 use X. (WSS use
       1 + INT(X + Z sqrt(X)); nearest-integer rounding avoids its +0.5 upward drift.)
    Returns per-period means and the empirical LTD distribution (sum over h).
    """
    y = _as1d(y_train)
    rng = np.random.default_rng(seed)
    occ = (y > 0).astype(int)
    sizes = y[y > 0]
    if sizes.size == 0:
        return Forecast(np.zeros(h), LTDDist("empirical", samples=np.zeros(n_samples)),
                        method="bootstrap", params={"p01": 0.0, "p11": 0.0})
    marg = occ.mean()
    trans = np.zeros((2, 2))
    for a, b in zip(occ[:-1], occ[1:]):
        trans[a, b] += 1
    p_next1 = np.empty(2)
    for s in (0, 1):
        tot = trans[s].sum()
        p_next1[s] = trans[s, 1] / tot if tot > 0 else marg
    state = np.full(n_samples, occ[-1])
    paths = np.zeros((n_samples, h))
    for t in range(h):
        u = rng.random(n_samples)
        state = (u < p_next1[state]).astype(int)
        draw = rng.choice(sizes, size=n_samples)
        if jitter:
            j = np.rint(draw + rng.standard_normal(n_samples) * np.sqrt(draw))
            draw = np.where(j < 1, draw, j)
        paths[:, t] = state * draw
    ltd = paths.sum(axis=1)
    return Forecast(paths.mean(axis=0), LTDDist("empirical", samples=ltd), method="bootstrap",
                    params={"p01": float(p_next1[0]), "p11": float(p_next1[1]),
                            "n_sizes": int(sizes.size), "seed": seed})


# --------------------------------------------------------------------------- reliability-exposure
def reliability_exposure(y_train, h, exposure_train=None, exposure_future=None,
                         mtbur_prior: float | None = None, prior_strength: float = 2.0,
                         **ctx) -> Forecast:
    """Removal rate per unit of exposure x planned future exposure.

    * ``y_train``: historical removal (demand) counts per period.
    * ``exposure_train``: component exposure per period over the same periods
      (installed qty x FH or FC flown), same length as y_train.
    * ``exposure_future``: PLANNED component exposure for the h forecast periods
      (input array). If None, the mean training exposure is carried forward.
    * MLE: lambda = sum(removals) / sum(exposure). LTD ~ Poisson(lambda * E_future).
    * With ``mtbur_prior`` (vendor-quoted MTBUR, same exposure unit) and
      ``prior_strength`` = k > 0: gamma prior Gamma(a0 = k, b0 = k * MTBUR), i.e. the
      quote counts as k pseudo-removals observed over k*MTBUR units of exposure
      (prior mean rate 1/MTBUR). Posterior Gamma(a0 + N, b0 + E). Point rate = a/b,
      LTD = posterior predictive negative binomial (size a, p = b / (b + E_future)).
    """
    y = _as1d(y_train)
    if exposure_train is None:
        raise ValueError("reliability_exposure needs exposure_train")
    e = _as1d(exposure_train)
    if e.size != y.size:
        raise ValueError("exposure_train must align with y_train")
    if exposure_future is None:
        ef = _flat(e.mean() if e.size else 0.0, h)
    else:
        ef = _as1d(exposure_future)[:h]
        if ef.size != h:
            raise ValueError("exposure_future must have length h")
    n_rem, e_tot, e_fut = float(y.sum()), float(e.sum()), float(ef.sum())
    use_prior = mtbur_prior is not None and np.isfinite(mtbur_prior) and mtbur_prior > 0 \
        and prior_strength > 0
    if use_prior:
        a = prior_strength + n_rem
        b = prior_strength * float(mtbur_prior) + e_tot
        rate = a / b
        dist = LTDDist("nbinom", n=a, p=b / (b + e_fut)) if e_fut > 0 else LTDDist("degenerate", mu=0.0)
        params = {"rate": rate, "a_post": a, "b_post": b, "rate_mle": n_rem / e_tot if e_tot > 0 else np.nan,
                  "prior_rate": 1.0 / float(mtbur_prior), "prior_strength": prior_strength}
    else:
        rate = n_rem / e_tot if e_tot > 0 else 0.0
        dist = LTDDist("poisson", mu=rate * e_fut)
        params = {"rate": rate, "rate_mle": rate}
    params.update({"exposure_train": e_tot, "removals_train": n_rem, "exposure_future": e_fut})
    return Forecast(rate * ef, dist, method="reliability", params=params)


# --------------------------------------------------------------------------- registry
METHODS: dict[str, Callable[..., Forecast]] = {
    "zero": zero,
    "naive": naive,
    "ma": moving_average,
    "croston": croston,
    "sba": sba,
    "tsb": tsb,
    "adida": adida,
    "imapa": imapa,
    "bootstrap": willemain_bootstrap,
    "reliability": reliability_exposure,
}
EXPOSURE_METHODS = {"reliability"}
# preference order used as the last tie-break (simpler first)
METHOD_ORDER = list(METHODS)


def fit_predict(method: str, y_train, h: int, **ctx) -> Forecast:
    """Dispatch by method name."""
    return METHODS[method](y_train, h, **ctx)
