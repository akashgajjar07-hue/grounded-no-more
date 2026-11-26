"""Greedy marginal allocation + the analytic delay model (gnm.optim.greedy / gnm.optim.model)."""
import itertools

import numpy as np
import pytest

from gnm.optim.greedy import allocation_capital, default_bounds, greedy_path, greedy_separable
from gnm.optim.model import ItemModel, ebo_vec, sS_ebo_avail
from gnm.policy.analytic import availability, ebo


def _toy():
    mus = [0.8, 2.5, 1.4, 4.0]
    costs = [3.0, 1.0, 2.0, 1.5]
    fns = [lambda x, m=m: ebo(x, m) for m in mus]
    return fns, costs, [6, 7, 6, 8]


def test_greedy_equals_brute_force_at_breakpoints():
    """Separable convex, non-increasing items, linear capital: every greedy breakpoint is optimal
    for its own capital (Lagrangian argument; Fox 1966 / Sherbrooke ch. 2)."""
    fns, costs, ub = _toy()
    path = greedy_separable(fns, costs, ub, budget=25.0)
    assert len(path) > 10
    grid = list(itertools.product(*[range(u + 1) for u in ub]))
    caps = np.array([sum(c * x for c, x in zip(costs, g)) for g in grid])
    objs = np.array([sum(f(x) for f, x in zip(fns, g)) for g in grid])
    for cap, obj, alloc in path:
        best = objs[caps <= cap + 1e-9].min()
        assert obj == pytest.approx(best, abs=1e-9), (cap, alloc)
        assert obj == pytest.approx(sum(f(x) for f, x in zip(fns, alloc)))


def test_greedy_ratios_non_increasing_on_convex_toy():
    fns, costs, ub = _toy()
    path = greedy_separable(fns, costs, ub, budget=25.0)
    ratios = [(path[k - 1][1] - path[k][1]) / (path[k][0] - path[k - 1][0]) for k in range(1, len(path))]
    assert all(a >= b - 1e-12 for a, b in zip(ratios, ratios[1:]))


def test_ebo_vec_and_sS_match_analytic():
    for mu in [0.3, 2.0, 7.5]:
        for S in range(0, 12):
            assert ebo_vec(np.array([S]), mu)[0] == pytest.approx(ebo(S, mu), abs=1e-10)
            e, a = sS_ebo_avail(S - 1, S, mu)          # q = 1 -> pure base stock
            assert e == pytest.approx(ebo(S, mu), abs=1e-10)
            assert a == pytest.approx(availability(S, mu), abs=1e-10)


def _item(pc="R", heal=False, rates=None):
    rates = np.array(rates if rates is not None else
                     [[0.05, 0.05, 0.10], [0.01, 0.0, 0.0], [0.004, 0.002, 0.0]])
    return ItemModel(pn="T-R1", part_class=pc, stations=("AUH", "BOM", "LHR"), rates=rates, resupply_days=40.0,
                     work_days=30.0, route_days=4.0, transport_h=np.array([0.0, 9.0, 16.0]), cap_days_class=5.0,
                     lead_time_days=90.0, expedite_factor=0.5, unit_cost=100.0, penalty_per_h=20000.0, heal=heal)


@pytest.mark.parametrize("heal", [False, True])
def test_model_adding_stock_never_increases_aog(heal):
    """Static model: monotone. With expedite self-healing an outstation unit also removes some AOG-desk
    buys (fewer hub stock-outs seen by aircraft), so the hub drifts up less: allow a 1% wobble."""
    it = _item(heal=heal)
    tol = 0.01 if heal else 0.0
    for S0 in range(0, 12):
        for s1 in range(0, 3):
            lv = np.array([S0, s1, 0])
            h = it.aog_hours(lv)
            assert it.aog_hours(lv + np.array([1, 0, 0])) <= h * (1 + tol) + 1e-9
            assert it.aog_hours(lv + np.array([0, 1, 0])) <= h * (1 + tol) + 1e-9
    assert it.aog_hours(np.array([0, 0, 0])) > it.aog_hours(np.array([8, 1, 1])) >= 0


def test_model_outstation_unit_saves_transport_for_d0_only():
    d0 = _item(rates=[[0.0, 0.0, 0.0], [0.02, 0.0, 0.0], [0.0, 0.0, 0.0]])
    d3 = _item(rates=[[0.0, 0.0, 0.0], [0.0, 0.02, 0.0], [0.0, 0.0, 0.0]])
    hub_rich = np.array([10, 0, 0])
    # D0 at BOM with stock at AUH: every miss costs the 9 h emergency transfer
    assert d0.aog_hours(hub_rich) == pytest.approx(0.02 * 365 * 9.0, rel=0.02)
    assert d0.aog_hours(hub_rich + np.array([0, 2, 0])) < 0.2 * d0.aog_hours(hub_rich)
    # D3 needs never wait beyond 72 h when AUH has stock
    assert d3.aog_hours(hub_rich) < 1e-3


def test_tat_cut_reduces_rotable_aog():
    it = _item()
    lv = np.array([2, 0, 0])
    assert it.aog_hours(lv, tat_mult=0.7) < it.aog_hours(lv)


def test_greedy_path_budget_floors_and_monotone():
    items = {"A": _item(), "B": _item(rates=[[0.2, 0.0, 0.1], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])}
    items["B"].pn = "B"
    items["B"].unit_cost = 40.0
    base = {k: np.array([2, 0, 0]) for k in items}
    floors, ceils = default_bounds(items, base, base, max_out=2)
    start = {k: floors[k].copy() for k in items}
    gp = greedy_path(items, start, floors, ceils, budget_max=2000.0)
    caps = [s.capital for s in gp.up]
    assert all(b > a for a, b in zip(caps, caps[1:]))
    hours = [gp.start_aog_hours] + [s.aog_hours for s in gp.up]
    assert all(b <= a + 1e-9 for a, b in zip(hours, hours[1:]))
    for B in [0.0, 150.0, 333.0, 1000.0, 2000.0]:
        lv, cap = gp.allocation_at(B)
        assert cap <= max(B, gp.start_capital) + 1e-6
        assert cap == pytest.approx(allocation_capital(items, lv))
        for k in items:
            assert (lv[k] >= floors[k]).all() and (lv[k] <= ceils[k]).all()


def test_greedy_downward_sweep_respects_floor_and_budget():
    items = {"A": _item()}
    base = {"A": np.array([6, 2, 1])}
    floors, ceils = default_bounds(items, base, base, max_out=3)
    gp = greedy_path(items, base, floors, ceils, budget_max=allocation_capital(items, base), budget_min=250.0)
    lv, cap = gp.allocation_at(450.0)
    assert cap <= 450.0 + 1e-6 and cap >= 450.0 - items["A"].unit_cost - 1e-6
    assert (lv["A"] >= floors["A"]).all()
