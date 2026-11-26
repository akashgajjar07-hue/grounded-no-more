"""Lever arithmetic (gnm.optim.levers)."""
import numpy as np
import pandas as pd
import pytest

from gnm.optim.levers import best_actions, lever_table, tat_multiplier
from gnm.optim.model import ItemModel
from gnm.policy.analytic import compare_levers


def _item(work=30.0):
    return ItemModel(pn="T-R1", part_class="R", stations=("AUH", "BOM"), rates=np.array([[0.1, 0.05, 0.05], [0.02, 0.0, 0.0]]),
                     resupply_days=45.0, work_days=work, route_days=4.0, transport_h=np.array([0.0, 9.0]),
                     cap_days_class=5.0, lead_time_days=90.0, expedite_factor=0.5, unit_cost=50000.0,
                     penalty_per_h=20000.0, heal=False)


def test_tat_multiplier_and_cap():
    it = _item(work=30.0)
    assert tat_multiplier(it, 10.0) == pytest.approx((1 - 10 / 30, 10.0))
    m, d = tat_multiplier(_item(work=12.0), 10.0, max_share=0.5)
    assert d == pytest.approx(6.0) and m == pytest.approx(0.5)


def test_lever_annual_costs_and_benefits():
    it = _item()
    lv = {"T-R1": np.array([5, 0])}
    t = lever_table({"T-R1": it}, lv, carry=0.2, accel_cost_per_day=400.0, tat_cut_days=10.0, extra_spares=(1, 2))
    row = t.set_index("lever")
    lam = 0.22
    assert row.loc["tat_cut_10d", "annual_cost_aed"] == pytest.approx(lam * 365 * 10 * 400)
    assert row.loc["buy_1", "annual_cost_aed"] == pytest.approx(50000 * 0.2)
    assert row.loc["buy_2", "annual_cost_aed"] == pytest.approx(2 * 50000 * 0.2)
    assert row.loc["buy_2", "incremental_capital_aed"] == pytest.approx(100000)
    assert row.loc["reposition_1", "annual_cost_aed"] == 0.0
    # benefit = modelled AOG-hour reduction x penalty; net = benefit - annual cost
    for lev, r in row.iterrows():
        assert r.penalty_saved_aed == pytest.approx(r.aog_hours_reduction * 20000.0)
        assert r.net_annual_benefit_aed == pytest.approx(r.penalty_saved_aed - r.annual_cost_aed)
    assert row.loc["buy_2", "aog_hours_reduction"] >= row.loc["buy_1", "aog_hours_reduction"] >= 0
    # the TAT annual cost is the compare_levers figure
    cl = compare_levers(lam * 30, 45.0, 5, 50000.0, 10.0, 2, 400.0)
    assert row.loc["tat_cut_10d", "annual_cost_aed"] == pytest.approx(cl["tat_cut"]["incremental_annual_aed"])
    assert row.loc["buy_2", "palm_ebo_extra"] == pytest.approx(cl["extra_spares"]["ebo"])


def test_best_actions_picks_max_net_or_hold():
    lv = pd.DataFrame([
        {"pn": "A", "lever": "buy_1", "detail": "", "net_annual_benefit_aed": 10.0},
        {"pn": "A", "lever": "tat_cut_10d", "detail": "", "net_annual_benefit_aed": 25.0},
        {"pn": "B", "lever": "buy_1", "detail": "", "net_annual_benefit_aed": -5.0},
    ])
    b = best_actions(lv).set_index("pn")
    assert b.loc["A", "best_action"] == "tat_cut_10d"
    assert b.loc["B", "best_action"] == "hold"
