"""Rolling-origin harness: no leakage, selection-window-only champions, freeze hash,
stock-based evaluation, and a source scan of gnm.forecasting for forbidden imports."""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gnm.forecasting import evaluate as EV
from gnm.forecasting.classify import build_part_attributes
from gnm.forecasting.methods import croston


def _world(n_parts=12, n_weeks=104, seed=0):
    rng = np.random.default_rng(seed)
    pns = [f"GN-32-R{i:03d}" for i in range(n_parts)]
    p = rng.uniform(0.1, 0.9, n_parts)
    D = (rng.random((n_parts, n_weeks)) < p[:, None]) * rng.poisson(3, (n_parts, n_weeks))
    E = rng.uniform(800, 1200, (n_parts, n_weeks))
    demand = pd.DataFrame(D, index=pns, columns=range(n_weeks))
    expo = pd.DataFrame(E, index=pns, columns=range(n_weeks))
    pm = pd.DataFrame({"pn": pns, "part_class": ["R" if i % 2 else "C" for i in range(n_parts)],
                       "unit_cost_aed": rng.uniform(100, 5000, n_parts),
                       "mtbur_quoted": rng.uniform(500, 3000, n_parts)})
    parts = build_part_attributes(demand, pm, train_weeks=(0, 77))
    return demand, expo, parts


def test_default_origins():
    assert EV.default_origins() == [78, 82, 86, 90, 94, 98]


def test_harness_shape_and_windows():
    demand, expo, parts = _world()
    err = EV.rolling_origin_evaluate(demand, parts, exposure=expo)
    n_methods = len(EV.DEFAULT_METHODS) + 1
    assert len(err) == len(demand) * 6 * n_methods
    assert set(err["window"]) == {"selection"}
    assert {"mase", "mase_status", "bias", "pis", "cov_q90", "pinball_q95"} <= set(err.columns)
    assert not np.isinf(err["mase"]).any()


@pytest.mark.parametrize("origin", [78, 90, 98])
def test_harness_never_uses_data_at_or_after_origin(origin):
    demand, expo, parts = _world(seed=1)
    kw = dict(origins=[origin], exposure=expo, return_forecasts=True)
    err1, fc1 = EV.rolling_origin_evaluate(demand, parts, **kw)
    # perturb every demand value at or after the origin (exposure after the origin is the
    # PLANNED flying programme, a legitimate input, so it is left unchanged)
    d2 = demand.copy()
    future = [c for c in d2.columns if c >= origin]
    d2[future] = d2[future] * 7 + 13
    err2, fc2 = EV.rolling_origin_evaluate(d2, parts, **kw)
    assert fc1.keys() == fc2.keys()
    for k in fc1:
        np.testing.assert_array_equal(fc1[k].mean, fc2[k].mean, err_msg=str(k))
        assert fc1[k].params == fc2[k].params, k
        if fc1[k].dist is not None and fc1[k].dist.samples is not None:
            np.testing.assert_array_equal(fc1[k].dist.samples, fc2[k].dist.samples)
    # MASE scale is in-sample only -> unchanged; the realised errors do change
    np.testing.assert_array_equal(err1["mase_scale"].to_numpy(), err2["mase_scale"].to_numpy())
    assert not np.allclose(err1["mae"], err2["mae"])


def test_harness_matches_direct_call():
    demand, _, parts = _world(seed=2)
    _, fcs = EV.rolling_origin_evaluate(demand, parts, methods=["croston"], origins=[82],
                                        return_forecasts=True)
    pn = demand.index[3]
    direct = croston(demand.loc[pn, list(range(0, 82))].to_numpy(float), 4)
    np.testing.assert_allclose(fcs[(pn, "croston", 82)].mean, direct.mean)


def _err_rows(method, origin, mase, bias, pns, dc="intermittent", pc="R", h=4):
    return [{"pn": p, "method": method, "origin": origin, "horizon": h, "demand_class": dc,
             "part_class": pc, "mase": mase, "bias": bias,
             "window": "selection" if 78 <= origin and origin + h - 1 <= 103 else "other"} for p in pns]


def test_champion_uses_selection_window_only():
    pns = [f"P{i}" for i in range(6)]
    rows = []
    for o in (78, 82, 86):
        rows += _err_rows("croston", o, 0.8, 0.1, pns) + _err_rows("naive", o, 1.0, 0.0, pns)
    # evaluation-window rows strongly favour naive; they must be ignored
    for o in (104, 108):
        rows += _err_rows("croston", o, 9.0, 3.0, pns) + _err_rows("naive", o, 0.1, 0.0, pns)
    # a training-window origin too
    rows += _err_rows("croston", 60, 9.0, 3.0, pns) + _err_rows("naive", 60, 0.1, 0.0, pns)
    err = pd.DataFrame(rows)
    ch = EV.select_champions(err)
    assert ch.loc[0, "champion"] == "croston" and ch.loc[0, "mean_mase"] == pytest.approx(0.8)
    # mutating non-selection rows cannot change the result
    err2 = err.copy()
    err2.loc[err2["window"] != "selection", "mase"] = 0.0
    pd.testing.assert_frame_equal(ch, EV.select_champions(err2))
    # selection rows only -> identical
    pd.testing.assert_frame_equal(ch, EV.select_champions(err[err["window"] == "selection"]))


def test_champion_tie_break_by_abs_bias_and_fallback():
    pns = [f"P{i}" for i in range(6)]
    rows = _err_rows("croston", 78, 0.9, 0.5, pns) + _err_rows("tsb", 78, 0.9, -0.1, pns)
    rows += _err_rows("croston", 78, 0.7, 0.0, ["Q1", "Q2"], pc="C") + _err_rows("tsb", 78, 1.2, 0.0, ["Q1", "Q2"], pc="C")
    ch = EV.select_champions(pd.DataFrame(rows), min_parts=5).set_index("part_class")
    assert ch.loc["R", "champion"] == "tsb" and ch.loc["R", "basis"] == "cell"       # |−0.1| < |0.5|
    # C cell has 2 parts < 5 -> pooled intermittent: croston (6*.9+2*.7)/8=.85 vs tsb (6*.9+2*1.2)/8=.975
    assert ch.loc["C", "basis"] == "pooled_demand_class" and ch.loc["C", "champion"] == "croston"


def test_champion_all_undefined_cell_falls_back_global():
    rows = _err_rows("croston", 78, 0.8, 0.0, [f"P{i}" for i in range(6)])
    rows += _err_rows("naive", 78, 1.0, 0.0, [f"P{i}" for i in range(6)])
    rows += _err_rows("croston", 78, np.nan, 0.0, ["Z1"], dc="insufficient_data")
    rows += _err_rows("naive", 78, np.nan, 0.0, ["Z1"], dc="insufficient_data")
    ch = EV.select_champions(pd.DataFrame(rows)).set_index("demand_class")
    assert ch.loc["insufficient_data", "basis"] == "global"
    assert ch.loc["insufficient_data", "champion"] == "croston"


def test_aggregate_bootstrap_ci():
    demand, _, parts = _world(seed=3)
    err = EV.rolling_origin_evaluate(demand, parts, methods=["zero", "croston"])
    agg = EV.aggregate_errors(err, n_boot=200)
    ok = agg.dropna(subset=["mase_ci_lo"])
    assert len(ok) > 0
    assert (ok["mase_ci_lo"] <= ok["mase"] + 1e-12).all() and (ok["mase"] <= ok["mase_ci_hi"] + 1e-12).all()


def test_freeze_champions_hash(tmp_path):
    demand, _, parts = _world(seed=4)
    err = EV.rolling_origin_evaluate(demand, parts, methods=["zero", "naive", "croston", "sba"])
    ch = EV.select_champions(err)
    info = EV.freeze_champions(ch, tmp_path / "champions.csv")
    digest = hashlib.sha256(Path(info["csv"]).read_bytes()).hexdigest()
    assert info["sha256"] == digest
    assert Path(info["sha256_file"]).read_text().split()[0] == digest
    js = json.loads(Path(info["json"]).read_text())
    assert js["csv_sha256"] == digest and js["provenance"] == "DERIVED"
    # deterministic: shuffled input -> same bytes
    info2 = EV.freeze_champions(ch.sample(frac=1, random_state=1), tmp_path / "again")
    assert info2["sha256"] == digest


def test_single_item_sim_hand_fixture():
    # s=1,S=2,L=1, start 2. t0 d1: fill1 net1 IP1<=1 -> order1 (arr t1). t1 net2. t2 d2: fill2
    # net0 IP0 -> order2 (arr t3). t3 net2. fill 3/3; on-hand 1,2,0,2 -> 1.25
    r = EV.simulate_single_item([1, 0, 2, 0], s=1, S=2, lead_time=1, unit_cost=10.0)
    assert r["fill_rate"] == 1.0 and r["avg_on_hand"] == pytest.approx(1.25)
    assert r["avg_stock_value"] == pytest.approx(12.5) and r["n_orders"] == 2
    r2 = EV.simulate_single_item([3, 0], s=1, S=2, lead_time=1)
    # t0: fill 2 of 3, net -1, order 3 arriving t1; t1: net 2
    assert r2["fill_rate"] == pytest.approx(2 / 3) and r2["backorder_units"] == 1.0
    assert r2["avg_backorders"] == pytest.approx(0.5)


def test_stock_based_eval_base_stock():
    rng = np.random.default_rng(5)
    from gnm.forecasting.methods import willemain_bootstrap
    pns = ["A", "B"]
    hist = rng.poisson(1.0, (2, 200)).astype(float)
    fut = pd.DataFrame(rng.poisson(1.0, (2, 400)), index=pns)
    L = 3
    fcs = {pn: willemain_bootstrap(hist[i], L, n_samples=4000, seed=i) for i, pn in enumerate(pns)}
    res = EV.stock_based_eval(fcs, fut, EV.base_stock_policy(0.95), lead_time_weeks=L,
                              unit_cost=pd.Series({"A": 100.0, "B": 200.0}))
    assert list(res["pn"]) == pns
    assert (res["fill_rate"] > 0.85).all()      # Poisson(3) 95% quantile ~ 6
    hi = EV.stock_based_eval(fcs, fut, EV.base_stock_policy(0.99), lead_time_weeks=L)
    assert (hi["avg_on_hand"].to_numpy() >= res["avg_on_hand"].to_numpy()).all()


def test_forecasting_package_has_no_forbidden_imports():
    root = Path(__file__).resolve().parents[1] / "src" / "gnm" / "forecasting"
    bad = re.compile(r"gnm\.sim\.(truth|generator)|ground_truth")
    for f in root.rglob("*.py"):
        assert not bad.search(f.read_text()), f
