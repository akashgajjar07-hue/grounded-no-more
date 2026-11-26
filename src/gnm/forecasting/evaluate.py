"""Rolling-origin evaluation, aggregation with bootstrap CIs, champion selection and
freezing, plus a stock-based evaluation hook with a small single-item simulator.

Input shapes
------------
* ``demand``: DataFrame, index = pn, columns = int weeks (contiguous), values = weekly
  demand qty (unconstrained). Must contain at least ``train_start .. max(origin)+h-1``.
* ``exposure`` (optional): DataFrame with the same index/columns: component exposure
  per pn per week in the part's driver unit (installed qty x FH or FC). Used only by
  the ``reliability`` method; weeks >= origin are treated as PLANNED exposure (the
  flying programme is known in advance; see D004 in docs/DECISIONS.md).
* ``parts``: DataFrame indexed by pn (or with a ``pn`` column) holding at least
  ``demand_class`` and ``part_class``; optional ``mtbur_quoted`` (reliability prior).
  Build it with :func:`gnm.forecasting.classify.build_part_attributes` so classes are
  computed on the training window only.

Leakage guarantee: for origin o the methods see ``demand[train_start .. o-1]`` only,
and the MASE scale is computed from those same columns.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from gnm.forecasting import metrics as M
from gnm.forecasting.methods import EXPOSURE_METHODS, METHOD_ORDER, METHODS, Forecast

SELECTION_WEEKS = (78, 103)
HORIZON = 4
STEP = 4
DEFAULT_METHODS = ["zero", "naive", "ma", "croston", "sba", "tsb", "adida", "imapa", "bootstrap"]
QUANTILES = (0.5, 0.9, 0.95)
NOT_ELIGIBLE = ("zero",)


def default_origins(selection_weeks=SELECTION_WEEKS, horizon: int = HORIZON, step: int = STEP) -> list[int]:
    """Origins every ``step`` weeks such that origin..origin+h-1 stays inside the window.

    Default: 78, 82, 86, 90, 94, 98 (forecast weeks 78-101).
    """
    lo, hi = selection_weeks
    return list(range(lo, hi - horizon + 2, step))


def _parts_frame(parts: pd.DataFrame) -> pd.DataFrame:
    p = parts.set_index("pn") if "pn" in parts.columns else parts
    for c in ("demand_class", "part_class"):
        if c not in p.columns:
            raise ValueError(f"parts frame needs column {c!r}")
    return p


def rolling_origin_evaluate(demand: pd.DataFrame, parts: pd.DataFrame,
                            methods: Sequence[str] | None = None,
                            origins: Iterable[int] | None = None,
                            horizon: int = HORIZON,
                            exposure: pd.DataFrame | None = None,
                            method_kwargs: dict | None = None,
                            quantiles: Sequence[float] = QUANTILES,
                            train_start: int = 0,
                            seasonality: int = 1,
                            seed: int = 0,
                            selection_weeks=SELECTION_WEEKS,
                            return_forecasts: bool = False):
    """Long error table: one row per pn x method x origin.

    Columns: pn, method, origin, horizon, window ("selection" if every forecast week is
    inside ``selection_weeks`` else "other"), demand_class, part_class, [abc],
    actual_sum, forecast_sum, mae, mase, mase_status, mase_scale, bias, cum_error,
    pis, ltd_q*, cov_q*, pinball_q*.
    With ``return_forecasts`` also returns {(pn, method, origin): Forecast}.
    """
    parts = _parts_frame(parts)
    if methods is None:
        methods = list(DEFAULT_METHODS) + (["reliability"] if exposure is not None else [])
    origins = list(origins) if origins is not None else default_origins(selection_weeks, horizon)
    method_kwargs = method_kwargs or {}
    weeks = np.array([int(c) for c in demand.columns])
    order = np.argsort(weeks)
    weeks = weeks[order]
    D = demand.to_numpy(dtype=float)[:, order]
    E = None
    if exposure is not None:
        E = exposure.reindex(index=demand.index, columns=demand.columns).to_numpy(dtype=float)[:, order]
    pos = {w: i for i, w in enumerate(weeks)}
    sel_lo, sel_hi = selection_weeks
    rows, fcs = [], {}
    for i, pn in enumerate(demand.index):
        attrs = parts.loc[pn] if pn in parts.index else None
        for o in origins:
            if train_start not in pos or (o + horizon - 1) not in pos or o not in pos:
                continue
            a, b = pos[train_start], pos[o]
            y_tr = D[i, a:b]
            y_te = D[i, b:b + horizon]
            base = {"pn": pn, "origin": o, "horizon": horizon,
                    "window": "selection" if (o >= sel_lo and o + horizon - 1 <= sel_hi) else "other",
                    "demand_class": attrs["demand_class"] if attrs is not None else "unknown",
                    "part_class": attrs["part_class"] if attrs is not None else "unknown"}
            if attrs is not None and "abc" in attrs.index:
                base["abc"] = attrs["abc"]
            ms = M.mase_scale(y_tr, seasonality)
            for meth in methods:
                ctx = dict(method_kwargs.get(meth, {}))
                ctx.setdefault("seed", int(seed + 7919 * i + o))
                if meth in EXPOSURE_METHODS:
                    if E is None:
                        continue
                    ctx["exposure_train"] = E[i, a:b]
                    ctx["exposure_future"] = E[i, b:b + horizon]
                    if attrs is not None and "mtbur_quoted" in attrs.index and "mtbur_prior" not in ctx:
                        mt = attrs["mtbur_quoted"]
                        ctx["mtbur_prior"] = float(mt) if pd.notna(mt) else None
                fc = METHODS[meth](y_tr.copy(), horizon, **ctx)
                f = np.asarray(fc.mean, dtype=float)
                mres = M.mase(y_te, f, y_tr, seasonality)
                cfe = M.cumulative_error(y_te, f)
                row = dict(base, method=meth, actual_sum=float(y_te.sum()), forecast_sum=float(f.sum()),
                           mae=M.mae(y_te, f), mase=mres.value, mase_status=mres.status, mase_scale=ms,
                           bias=M.bias(y_te, f), cum_error=float(cfe[-1]), pis=M.pis(y_te, f))
                row.update(M.ltd_metrics(float(y_te.sum()), fc.ltd_dist(), quantiles))
                rows.append(row)
                if return_forecasts:
                    fcs[(pn, meth, o)] = fc
    out = pd.DataFrame(rows)
    return (out, fcs) if return_forecasts else out


# --------------------------------------------------------------------------- aggregation
def _per_part(errors: pd.DataFrame, by: Sequence[str], cols: Sequence[str]) -> pd.DataFrame:
    keys = list(by) + ["method", "pn"]
    return errors.groupby(keys, dropna=False)[list(cols)].mean().reset_index()


def aggregate_errors(errors: pd.DataFrame, by: Sequence[str] = ("demand_class", "part_class"),
                     metrics: Sequence[str] | None = None, n_boot: int = 1000, seed: int = 0,
                     window: str | None = "selection") -> pd.DataFrame:
    """Mean metric per cell x method with percentile-bootstrap 95 % CIs over PARTS.

    Each part is first averaged over its origins; parts are then resampled with
    replacement ``n_boot`` times. Parts with undefined MASE are excluded from the MASE
    mean (``n_undefined`` counts them). ``abs_bias`` = mean over parts of |part bias|.
    """
    e = errors if window is None else errors[errors["window"] == window]
    if metrics is None:
        metrics = ["mase", "mae", "bias", "pis"] + [c for c in e.columns if c.startswith(("cov_q", "pinball_q"))]
    pp = _per_part(e, by, metrics)
    pp["abs_bias"] = pp["bias"].abs()
    rng = np.random.default_rng(seed)
    rows = []
    for key, g in pp.groupby(list(by) + ["method"], dropna=False):
        row = dict(zip(list(by) + ["method"], key if isinstance(key, tuple) else (key,)))
        row["n_parts"] = int(g["pn"].nunique())
        row["n_undefined"] = int(g["mase"].isna().sum())
        for m in list(metrics) + ["abs_bias"]:
            v = g[m].dropna().to_numpy()
            row[m] = float(v.mean()) if v.size else float("nan")
            if v.size >= 2 and n_boot > 0:
                bs = v[rng.integers(0, v.size, size=(n_boot, v.size))].mean(axis=1)
                row[f"{m}_ci_lo"], row[f"{m}_ci_hi"] = (float(x) for x in np.percentile(bs, [2.5, 97.5]))
            else:
                row[f"{m}_ci_lo"] = row[f"{m}_ci_hi"] = float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- champions
def _rank(pp: pd.DataFrame, tie_tol: float) -> tuple[str | None, float, float, int, str | None]:
    """Champion within one pool of per-part rows (all methods)."""
    defined = pp.dropna(subset=["mase"])
    if defined.empty:
        return None, float("nan"), float("nan"), 0, None
    s = defined.groupby("method").agg(mase=("mase", "mean"), bias=("bias", "mean"), n=("pn", "nunique"))
    s["abs_bias"] = s["bias"].abs()
    s["order"] = [METHOD_ORDER.index(m) if m in METHOD_ORDER else 999 for m in s.index]
    best = s["mase"].min()
    tied = s[s["mase"] <= best + tie_tol].sort_values(["abs_bias", "order"])
    champ = tied.index[0]
    rest = s.drop(index=champ).sort_values(["mase", "abs_bias", "order"])
    runner = rest.index[0] if len(rest) else None
    return champ, float(s.loc[champ, "mase"]), float(s.loc[champ, "bias"]), int(s.loc[champ, "n"]), runner


def select_champions(errors: pd.DataFrame, by: Sequence[str] = ("demand_class", "part_class"),
                     selection_weeks=SELECTION_WEEKS, min_parts: int = 5,
                     tie_tol: float = 1e-3,
                     exclude: Sequence[str] = NOT_ELIGIBLE) -> pd.DataFrame:
    """Champion method per cell, using SELECTION-WINDOW errors only.

    Methods in ``exclude`` (default: the ``zero`` benchmark) are scored by the harness
    but are not eligible: absolute-error metrics such as MASE reward an all-zero
    forecast on intermittent series, which would leave no stock at all (FC-4).

    Rule: lowest mean MASE over parts (each part averaged over its origins; parts with
    undefined MASE excluded). Methods within ``tie_tol`` (absolute MASE) of the best
    are tied and broken by smallest |mean bias|, then by the fixed METHOD_ORDER
    (simpler first). Fallback for small cells: if a cell has < ``min_parts`` parts with
    defined MASE, its champion is taken from the pooled ``by[0]`` group (e.g. the
    demand_class across all part classes); if that is also too small, from the global
    pool. ``basis`` records which level was used.
    """
    lo, hi = selection_weeks
    e = errors[(errors["origin"] >= lo) & (errors["origin"] + errors["horizon"] - 1 <= hi)]
    if e.empty:
        raise ValueError("no errors inside the selection window")
    by = list(by)
    e = e[~e["method"].isin(list(exclude))]
    if e.empty:
        raise ValueError("no eligible methods")
    pp = _per_part(e, by, ["mase", "bias"])
    glob = _rank(pp, tie_tol)
    pooled = {k: _rank(g, tie_tol) for k, g in pp.groupby(by[0], dropna=False)} if len(by) > 1 else {}
    rows = []
    for key, g in pp.groupby(by, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        cell = _rank(g, tie_tol)
        n_cell = int(g.dropna(subset=["mase"])["pn"].nunique())
        if cell[0] is not None and n_cell >= min_parts:
            res, basis = cell, "cell"
        elif len(by) > 1 and pooled.get(key[0], (None, 0, 0, 0))[0] is not None \
                and pooled[key[0]][3] >= min_parts:
            res, basis = pooled[key[0]], f"pooled_{by[0]}"
        else:
            res, basis = glob, "global"
        row = dict(zip(by, key))
        row.update({"champion": res[0], "mean_mase": res[1], "mean_bias": res[2], "n_parts_basis": res[3],
                    "n_parts_cell": int(g["pn"].nunique()), "n_parts_cell_defined": n_cell,
                    "basis": basis, "runner_up": res[4], "selection_weeks": f"{lo}-{hi}",
                    "n_origins": int(e["origin"].nunique())})
        rows.append(row)
    return pd.DataFrame(rows).sort_values(by).reset_index(drop=True)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def freeze_champions(df: pd.DataFrame, path) -> dict:
    """Write the champion table as <stem>.csv and <stem>.json plus <stem>.sha256.

    The CSV is written deterministically (sorted rows, fixed float format, '\\n' line
    endings); its SHA-256 is the freeze hash. Returns {csv, json, sha256_file, sha256}.
    """
    path = Path(path)
    stem = path.with_suffix("") if path.suffix in (".csv", ".json", ".sha256") else path
    stem.parent.mkdir(parents=True, exist_ok=True)
    keys = [c for c in ("demand_class", "part_class") if c in df.columns]
    d = df.sort_values(keys).reset_index(drop=True) if keys else df.reset_index(drop=True)
    csv_p, json_p, sha_p = (stem.with_suffix(s) for s in (".csv", ".json", ".sha256"))
    d.to_csv(csv_p, index=False, float_format="%.6f", lineterminator="\n")
    digest = _sha256(csv_p)
    recs = json.loads(d.to_json(orient="records", double_precision=6))
    json_p.write_text(json.dumps({"provenance": "DERIVED", "champions": recs, "csv_sha256": digest},
                                 indent=2, sort_keys=True) + "\n")
    sha_p.write_text(f"{digest}  {csv_p.name}\n")
    return {"csv": str(csv_p), "json": str(json_p), "sha256_file": str(sha_p), "sha256": digest}


# --------------------------------------------------------------------------- stock-based evaluation
def simulate_single_item(demand, s: float, S: float, lead_time: int, unit_cost: float = 1.0,
                         initial_on_hand: float | None = None) -> dict:
    """Weekly periodic-review (s, S) single-item simulation with full backordering.

    Timing per week t: (1) receive orders due at t, which first clear backorders;
    (2) demand d_t is met from on-hand stock, the rest is backordered; (3) end-of-week
    review: if inventory position (net + on order) <= s, order S - IP, arriving at the
    start of week t + lead_time (lead_time >= 1). Under this timing the protection
    interval is ``lead_time`` weeks, so forecast LTD over h = lead_time.
    Returns fill_rate (immediate fill from stock), backorder_units, avg_backorders,
    avg_on_hand, avg_stock_value (avg_on_hand x unit_cost), n_orders.
    """
    d = np.asarray(demand, dtype=float)
    L = max(int(lead_time), 1)
    net = float(S if initial_on_hand is None else initial_on_hand)
    pipe = np.zeros(d.size + L + 1)
    filled = short = 0.0
    on_hand_hist, bo_hist, n_orders = [], [], 0
    for t in range(d.size):
        net += pipe[t]
        avail = max(net, 0.0)
        f = min(avail, d[t])
        filled += f
        short += d[t] - f
        net -= d[t]
        ip = net + pipe[t + 1:].sum()
        if ip <= s:
            q = S - ip
            if q > 0:
                pipe[t + L] += q
                n_orders += 1
        on_hand_hist.append(max(net, 0.0))
        bo_hist.append(max(-net, 0.0))
    tot = d.sum()
    avg_oh = float(np.mean(on_hand_hist)) if on_hand_hist else 0.0
    return {"fill_rate": float(filled / tot) if tot > 0 else float("nan"), "backorder_units": float(short),
            "avg_backorders": float(np.mean(bo_hist)) if bo_hist else 0.0, "avg_on_hand": avg_oh,
            "avg_stock_value": avg_oh * unit_cost, "n_orders": n_orders}


def base_stock_policy(service_level: float = 0.95) -> Callable[[Forecast, dict], tuple[float, float]]:
    """Base-stock: S = LTD quantile at ``service_level`` (cycle service), s = S - 1.

    ``ctx['service_level']`` overrides the default per pn (e.g. from the deadline
    class targets in config ``service_targets``).
    """
    def policy(fc: Forecast, ctx: dict) -> tuple[float, float]:
        sl = float(ctx.get("service_level", service_level))
        S = float(np.ceil(float(np.atleast_1d(fc.ltd_dist().ppf([sl]))[0])))
        return S - 1.0, S
    return policy


def ss_policy(service_level: float = 0.95, cover_periods: float = 4.0):
    """(s, S): s = LTD quantile, S = s + max(1, ceil(mean per-period forecast x cover))."""
    def policy(fc: Forecast, ctx: dict) -> tuple[float, float]:
        sl = float(ctx.get("service_level", service_level))
        s = float(np.ceil(float(np.atleast_1d(fc.ltd_dist().ppf([sl]))[0])))
        q = max(1.0, math.ceil(float(np.mean(fc.mean)) * cover_periods))
        return s, s + q
    return policy


def stock_based_eval(forecasts: dict, demand_future: pd.DataFrame, policy_fn: Callable,
                     lead_time_weeks, unit_cost=None, ctx_by_pn: dict | None = None,
                     sim_fn: Callable = simulate_single_item) -> pd.DataFrame:
    """Turn forecasts into (s, S) targets via ``policy_fn`` and simulate each pn.

    * ``forecasts``: {pn: Forecast} made at the evaluation origin with h = lead time
      (the protection interval of :func:`simulate_single_item`).
    * ``demand_future``: pn x week demand AFTER the origin (simulation horizon).
    * ``policy_fn(forecast, ctx) -> (s, S)``; ``lead_time_weeks`` / ``unit_cost``:
      scalar or pn-indexed Series. ``sim_fn`` can be swapped for the real engine.
    """
    ctx_by_pn = ctx_by_pn or {}
    rows = []
    for pn, fc in forecasts.items():
        if pn not in demand_future.index:
            continue
        L = lead_time_weeks[pn] if isinstance(lead_time_weeks, (pd.Series, dict)) else lead_time_weeks
        c = 1.0 if unit_cost is None else (unit_cost[pn] if isinstance(unit_cost, (pd.Series, dict)) else unit_cost)
        s, S = policy_fn(fc, ctx_by_pn.get(pn, {}))
        res = sim_fn(demand_future.loc[pn].to_numpy(dtype=float), s, S, int(L), float(c))
        rows.append({"pn": pn, "method": fc.method, "s": s, "S": S, "lead_time_weeks": int(L), **res})
    return pd.DataFrame(rows)
