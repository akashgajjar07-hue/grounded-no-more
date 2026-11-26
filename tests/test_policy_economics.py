"""Economics and evaluation plumbing: capital never in opex, totals add up, paired CIs, seed discipline."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from gnm.config import OUTPUTS
from gnm.policy import evaluate_policies as ep
from gnm.policy.policies import build_p1, build_p2
from gnm.sim.api import load_or_generate_scenario
from gnm.sim.baseline import build_p0
from gnm.sim.engine import run_policy

from _polfx import forecasts, world

KPIS = {"immediate_fill_rate": 0.95, "aog_hours": 100.0, "aog_events": 3, "backorder_unit_hours": 10.0,
        "spare_capital_aed": 5e7, "holding_cost_aed": 1e7, "repair_cost_aed": 2e6, "logistics_cost_aed": 1e5,
        "expedite_cost_aed": 3e5, "aog_penalty_aed": 2e6, "purchase_spend_aed": 9e6}


def test_total_cost_is_sum_of_components_and_excludes_capital():
    tot = ep.total_annual_cost(KPIS)
    assert tot == pytest.approx(1e7 + 2e6 + 1e5 + 3e5 + 2e6)
    k2 = dict(KPIS, spare_capital_aed=9e9, purchase_spend_aed=1e12)
    assert ep.total_annual_cost(k2) == tot
    assert "spare_capital_aed" not in ep.COST_COMPONENTS and "purchase_spend_aed" not in ep.COST_COMPONENTS


def test_penalty_sensitivity_linear():
    df = pd.DataFrame([KPIS, dict(KPIS, aog_penalty_aed=5e6)])
    out = ep.penalty_sensitivity(df, [0.5, 1.0, 2.0])
    base = df[ep.COST_COMPONENTS].sum(axis=1)
    assert np.allclose(out["total_cost_pen_x1"], base)
    assert np.allclose(out["total_cost_pen_x2"] - out["total_cost_pen_x1"], df.aog_penalty_aed)
    assert np.allclose(out["total_cost_pen_x1"] - out["total_cost_pen_x0.5"], 0.5 * df.aog_penalty_aed)


def test_paired_ci_matches_scipy():
    rng = np.random.default_rng(3)
    d = rng.normal(2.0, 1.5, 20)
    ci = ep.paired_ci(d)
    lo, hi = stats.t.interval(0.95, 19, loc=d.mean(), scale=stats.sem(d))
    assert ci["ci_lo"] == pytest.approx(lo) and ci["ci_hi"] == pytest.approx(hi)
    b = ep.bootstrap_ci(d, 2000, 0)
    assert b[0] < d.mean() < b[1]


def test_holdout_seeds_refused():
    with pytest.raises(ValueError):
        ep.evaluate(variants=["central"], seeds=[1000])


def test_paired_seed_equivalence_and_engine_economics():
    """P0/P1/P2 see the same requests on a selection seed; every run's total = sum of components."""
    w, ff = world(), forecasts()
    sc = load_or_generate_scenario(100, 78, 155)
    pols = [build_p0(w), build_p1(w, ff), build_p2(w, ff)]
    runs = [run_policy(w, sc, p, 104, 155, detail=True) for p in pols]
    sig = ep.request_signature(runs[0])
    for r in runs[1:]:
        pd.testing.assert_frame_equal(sig, ep.request_signature(r))
    for r in runs:
        k = r.kpis
        assert ep.total_annual_cost(k) == pytest.approx(sum(k[c] for c in ep.COST_COMPONENTS))
        assert k["holding_cost_aed"] == pytest.approx(w.cfg["economics"]["carrying_cost_pct_per_year"]
                                                      * k["spare_capital_aed"])
        srows, crows = ep.reduce_detail(w, r, "central", 104, 155)
        assert sum(x["aog_hours"] for x in srows) == pytest.approx(k["aog_hours"])
        assert sum(x["aog_hours"] for x in crows) == pytest.approx(k["aog_hours"])
    # same exogenous repairs: repair spend identical (no TAT lever in P0/P1/P2)
    assert runs[0].kpis["repair_cost_aed"] == pytest.approx(runs[1].kpis["repair_cost_aed"])


def test_selection_outputs_consistent():
    p = OUTPUTS / "policies" / "selection_results.parquet"
    if not p.exists():
        pytest.skip("run scripts/evaluate_policies.py first")
    df = pd.read_parquet(p)
    assert set(df.seed) <= set(range(100, 120))
    assert {"central", "low_stress", "high_stress"} <= set(df.variant)
    import json
    s = json.loads((OUTPUTS / "policies" / "selection_summary.json").read_text())
    for v, g in df.groupby("variant"):
        for pid, gp in g.groupby("policy_id"):
            m = gp[ep.COST_COMPONENTS].sum(axis=1).mean()
            assert s["variants"][v]["policies"][pid]["total_annual_cost_aed"]["mean"] == pytest.approx(m)
