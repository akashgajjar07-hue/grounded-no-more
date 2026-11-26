"""Forecast pipeline: matrices, lead-time estimation, no use of future data, no hidden-truth access."""
import builtins
import pathlib

import numpy as np
import pandas as pd
import pytest

from gnm.policy import forecast_pipeline as fp
from gnm.policy.policies import build_p1, build_p2

from _polfx import champions, forecasts, history, world


def test_demand_and_exposure_matrices():
    h, w = history(), world()
    inp = fp.build_inputs(h, origin=104)
    assert list(inp["demand"].columns) == list(range(104))
    rq = h["material_requests"]
    assert inp["demand"].to_numpy().sum() == rq.qty.sum()
    assert np.isclose(inp["station_demand"].to_numpy().sum(), rq.qty.sum())
    # exposure of one FH-driven PN = sum over applicable archetypes of qty x FH flown
    pm = h["part_master"].set_index("pn")
    pn = pm[(pm.driver == "FH") & (pm.part_class == "R")].index[0]
    arch = dict(zip(h["aircraft_master"]["tail"], h["aircraft_master"]["archetype"]))
    fl = h["flight_exposure"].assign(a=lambda d: d["tail"].map(arch))
    ap = h["part_applicability"].set_index(["pn", "archetype"]).qty_per_aircraft
    exp = sum(ap.get((pn, a), 0) * fl[fl.a == a].fh.sum() for a in ("narrowbody", "widebody"))
    assert np.isclose(inp["exposure"].loc[pn].sum(), exp)
    assert np.isclose(inp["station_exposure"].loc[pn].to_numpy().sum(), exp, rtol=1e-6)


def test_station_shares_sum_to_one():
    inp = fp.build_inputs(history(), origin=104)
    sh = fp.station_shares(inp, "AUH")
    assert np.allclose(sh.sum(axis=1), 1.0)
    assert (sh.to_numpy() >= 0).all()


def test_lead_time_catches_ps4_only_after_the_jump():
    h = history()
    pm = h["part_master"]
    late = fp.estimate_lead_times(h["purchase_orders"], pm, 104)
    early = fp.estimate_lead_times(h["purchase_orders"], pm, 70)
    ps4 = pm.loc[pm.planted == "PS4", "pn"].iloc[0]
    assert late.loc[ps4, "lt_est_d"] > 1.8 * late.loc[ps4, "lt_quoted_d"]
    assert early.loc[ps4, "lt_est_d"] < 1.3 * early.loc[ps4, "lt_quoted_d"]


def test_lead_time_fixture():
    parts = pd.DataFrame({"pn": ["X"], "lead_time_mean_d": [30.0], "lead_time_cv": [0.2]})
    po = pd.DataFrame({"pn": ["X"] * 3, "reason": ["reorder"] * 3, "order_h": [0, 168 * 10, 168 * 20],
                       "receipt_h": pd.array([30 * 24, 168 * 10 + 30 * 24, 168 * 20 + 30 * 24], dtype="Int64")})
    est = fp.estimate_lead_times(po, parts, origin=40)
    assert np.isclose(est.loc["X", "lt_est_d"], 30.0)
    po2 = po.copy()
    po2["receipt_h"] = pd.array([30 * 24, 168 * 10 + 80 * 24, 168 * 20 + 80 * 24], dtype="Int64")
    est2 = fp.estimate_lead_times(po2, parts, origin=40)
    assert est2.loc["X", "regime_shift"] and np.isclose(est2.loc["X", "lt_est_d"], 80.0)


def _perturb(h, origin):
    oh = origin * 168
    p = {k: v.copy() for k, v in h.items()}
    rq = p["material_requests"]
    rq.loc[rq.week >= origin, "qty"] *= 5
    p["material_requests"] = pd.concat([rq, rq[rq.week >= origin].assign(request_id=lambda d: d.request_id + 10**7)])
    fl = p["flight_exposure"]
    fl.loc[fl.week >= origin, "fh"] *= 3.0
    po = p["purchase_orders"]
    late = po.receipt_h.astype("Float64") >= oh
    po.loc[late.fillna(False).to_numpy(), "receipt_h"] = po.loc[late.fillna(False).to_numpy(), "receipt_h"] + 5000
    ro = p["repair_orders"]
    lr = ro.return_h.astype("Float64") >= oh
    ro.loc[lr.fillna(False).to_numpy(), "return_h"] = ro.loc[lr.fillna(False).to_numpy(), "return_h"] + 9000
    tr = p["transfers"]
    tr.loc[tr.ship_h >= oh, "arrive_h"] += 777
    return p


def test_final_forecasts_use_only_pre_origin_data():
    h, w = history(), world()
    origin = 90
    a = fp.final_forecasts(h, w, champions(), origin=origin)
    b = fp.final_forecasts(_perturb(h, origin), w, champions(), origin=origin)
    cols = [c for c in a.columns if c != "ltd_samples"]
    pd.testing.assert_frame_equal(a[cols], b[cols])
    sa = a.ltd_samples.dropna().map(tuple).tolist()
    sb = b.ltd_samples.dropna().map(tuple).tolist()
    assert sa == sb
    # and the perturbation is visible at a later origin (the test is not vacuous)
    c = fp.final_forecasts(_perturb(h, origin), w, champions(), origin=104)
    d = forecasts(104)
    assert not np.allclose(c.ltd_mean.to_numpy(), d.ltd_mean.to_numpy())


def test_rolling_evaluation_ignores_future():
    h = history()
    inp = fp.build_inputs(h, origin=90)
    assert max(inp["demand"].columns) == 89 and max(inp["exposure"].columns) == 89
    assert inp["hist"]["material_requests"].week.max() < 90


def test_no_hidden_truth_access_at_runtime(monkeypatch):
    """Reading anything under the hidden truth directory raises; the pipeline and P1/P2 still run."""
    def guard(path):
        if "ground_truth" in str(path):
            raise AssertionError(f"hidden truth accessed: {path}")

    real_open, real_rp = builtins.open, pd.read_parquet
    real_po, real_rb = pathlib.Path.open, pathlib.Path.read_bytes

    def g_open(file, *a, **k):
        guard(file)
        return real_open(file, *a, **k)

    def g_rp(path, *a, **k):
        guard(path)
        return real_rp(path, *a, **k)

    def g_po(self, *a, **k):
        guard(self)
        return real_po(self, *a, **k)

    def g_rb(self):
        guard(self)
        return real_rb(self)

    monkeypatch.setattr(builtins, "open", g_open)
    monkeypatch.setattr(pd, "read_parquet", g_rp)
    monkeypatch.setattr(pathlib.Path, "open", g_po)
    monkeypatch.setattr(pathlib.Path, "read_bytes", g_rb)
    with pytest.raises(AssertionError):
        pd.read_parquet("data/ground_truth/gt_part_truth.parquet")
    w = world()
    h = fp.load_history()
    ff = fp.final_forecasts(h, w, champions(), origin=104)
    assert len(build_p1(w, ff).stock_params) == len(build_p2(w, ff).stock_params) == 840
