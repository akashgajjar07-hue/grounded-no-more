"""Frontier: non-dominated set, recommendation rule, budgets, candidates.json, paired evaluation, holdout guard."""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gnm.optim import frontier as fr

SRC = Path(__file__).resolve().parents[1] / "src" / "gnm" / "optim"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_frontier.py"


# ---------------------------------------------------------------- hand fixtures
def test_nondominated_hand_fixture():
    #          A    B    C    D    E    F (duplicate of B)
    cap = [1.0, 2.0, 3.0, 2.5, 4.0, 2.0]
    aog = [9.0, 5.0, 2.0, 6.0, 2.0, 5.0]
    nd = fr.nondominated(np.array(cap), np.array(aog))
    # D dominated by B (cheaper, fewer hours); E dominated by C (same hours, more capital)
    assert nd.tolist() == [True, True, True, False, False, True]


def test_lower_hull_drops_non_convex_point():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([10.0, 8.5, 4.0, 3.5])     # (2, 8.5) lies above the chord (1,10)-(3,4)
    assert fr.lower_hull(x, y) == [0, 2, 3]


def test_recommend_rule_on_fixture():
    pts = pd.DataFrame({"id": ["P0", "B1", "B2", "B3", "L"], "kind": ["baseline", "budget", "budget", "budget", "lever"],
                        "capital_mean": [10e6, 11e6, 12e6, 13e6, 9e6],
                        "aog_hours_mean": [1000.0, 600.0, 450.0, 440.0, 100.0]})
    # carry 0.2, AED 20,000/h -> h* = 10 h per AED 1M; slopes 400, 150, 10 ... 10 is not < 10
    r = fr.recommend(pts, carry=0.2, aed_per_aog_h=20000.0)
    assert r["h_star_per_aed_1m"] == pytest.approx(10.0)
    assert r["hull"] == ["P0", "B1", "B2", "B3"]          # the lever point is not capital-only
    assert r["recommended"] == "B3" and not r["frontier_saturated"]
    r2 = fr.recommend(pts, carry=0.2, aed_per_aog_h=10000.0)   # h* = 20 -> stop before B2->B3 (slope 10)
    assert r2["recommended"] == "B2" and r2["frontier_saturated"]
    assert r2["min_holding_plus_penalty_on_hull"] == "B2"


def test_t_ci_and_recost():
    m, lo, hi = fr.t_ci(np.array([1.0, 2.0, 3.0, 4.0]))
    assert m == 2.5 and lo < m < hi
    long = pd.DataFrame({"policy_id": ["a"], "seed": [100], "spare_capital_aed": [1e6], "aog_penalty_aed": [2e6],
                         "holding_cost_aed": [2e5], "repair_cost_aed": [1.0], "logistics_cost_aed": [1.0],
                         "expedite_cost_aed": [1.0]})
    r = fr.recost(long, penalty_factor=2.0, carry=0.25)
    assert r.aog_penalty_aed[0] == 4e6 and r.holding_cost_aed[0] == 2.5e5
    assert r.total_annual_cost_aed[0] == pytest.approx(4e6 + 2.5e5 + 3.0)


# ---------------------------------------------------------------- real candidate set (no simulation)
@pytest.fixture(scope="module")
def ctx_and_cands():
    from gnm.sim.api import load_world
    from gnm.sim.baseline import build_p0
    w = load_world()
    ctx = fr.prepare(w, build_p0(w))
    return ctx, fr.build_candidates(ctx)


def test_budget_points_respect_budget(ctx_and_cands):
    ctx, cands = ctx_and_cands
    max_unit = max(it.unit_cost for it in ctx.items.values())
    budgeted = [c for c in cands if c.budget_aed is not None and c.kind in ("budget", "incremental")]
    assert len(budgeted) >= 10
    for c in budgeted:
        floor_cap = ctx.path.start_capital if c.kind == "budget" else ctx.base_capital
        assert c.allocation_capital_aed <= max(c.budget_aed, floor_cap) + max_unit + 1e-6, c.cid
        assert c.allocation_capital_aed == pytest.approx(fr.allocation_capital(ctx.items, c.levels))


def test_candidate_policies_change_only_levels(ctx_and_cands):
    ctx, cands = ctx_and_cands
    base = ctx.base.stock_params.sort_values(["pn", "station"]).reset_index(drop=True)
    for c in cands:
        sp = c.policy.stock_params.sort_values(["pn", "station"]).reset_index(drop=True)
        assert (sp[["pn", "station"]] == base[["pn", "station"]]).all().all()
        assert (sp.base_stock >= 0).all() and (sp.S >= sp.s).all()
        assert c.policy.emergency_sources == ctx.base.emergency_sources


def test_candidates_json_deterministic(tmp_path, ctx_and_cands):
    from gnm.sim.api import load_world
    from gnm.sim.baseline import build_p0
    ctx, cands = ctx_and_cands
    h1 = fr.write_candidates(tmp_path / "a.json", cands, "P0")
    w = load_world()
    cands2 = fr.build_candidates(fr.prepare(w, build_p0(w)))      # rebuilt from scratch
    h2 = fr.write_candidates(tmp_path / "b.json", list(reversed(cands2)), "P0")
    assert h1 == h2
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    back = fr.load_candidates(tmp_path / "a.json")
    assert sorted(m["id"] for m, _ in back) == sorted(c.cid for c in cands)
    m, pol = next((m, p) for m, p in back if m["id"] == cands[1].cid)
    orig = cands[1].policy.stock_params.sort_values(["pn", "station"]).reset_index(drop=True)
    got = pol.stock_params.sort_values(["pn", "station"]).reset_index(drop=True)
    assert (orig[["s", "S", "base_stock"]].to_numpy() == got[["s", "S", "base_stock"]].to_numpy()).all()


# ---------------------------------------------------------------- paired evaluation
class _Res:
    def __init__(self, pid, seed):
        self.policy_id, self.seed = pid, seed
        self.kpis = {k: 1.0 for k in ["immediate_fill_rate", "aog_hours", "aog_events", "spare_capital_aed",
                                      "holding_cost_aed", "repair_cost_aed", "logistics_cost_aed", "expedite_cost_aed",
                                      "aog_penalty_aed", "purchase_spend_aed", "backorder_unit_hours"]}


def test_paired_evaluation_uses_identical_scenarios(ctx_and_cands):
    ctx, cands = ctx_and_cands
    seen = []

    def fake_runner(world, scenarios, policies, kf, kt, processes=None):
        out = []
        for sc in scenarios:
            for p in policies:
                seen.append((p.policy_id, sc))
                out.append(_Res(p.policy_id, sc[0]))
        return out

    pols = [c.policy for c in cands[:4]]
    long = fr.evaluate(ctx.world, pols, [100, 101, 102], runner=fake_runner)
    assert len(long) == 12
    by_pol = {}
    for pid, sc in seen:
        by_pol.setdefault(pid, []).append(sc)
    ref = by_pol[pols[0].policy_id]
    assert all(v == ref for v in by_pol.values())       # same scenario keys, same order, for every candidate
    assert {s[0] for s in ref} == {100, 101, 102}


def test_paired_evaluation_real_engine_same_demand(ctx_and_cands):
    """Two candidates on one cached selection scenario: identical demand, different outcomes possible."""
    from gnm.sim.api import load_or_generate_scenario
    from gnm.sim.engine import run_policy
    ctx, cands = ctx_and_cands
    sc = load_or_generate_scenario(100, 78, 155)
    a = run_policy(ctx.world, sc, cands[0].policy, 104, 155, detail=True)
    b = run_policy(ctx.world, sc, cands[-1].policy, 104, 155, detail=True)
    cols = ["request_id", "pn", "station", "need_h", "qty", "deadline_class"]
    pd.testing.assert_frame_equal(a.requests[cols].reset_index(drop=True), b.requests[cols].reset_index(drop=True))
    long = fr.evaluate(ctx.world, [cands[0].policy, cands[-1].policy], [100], processes=1)
    assert long.aog_hours.tolist() == pytest.approx([a.kpis["aog_hours"], b.kpis["aog_hours"]])


def test_holdout_seeds_refused():
    from gnm.sim.api import load_world
    with pytest.raises(PermissionError):
        fr.evaluate(load_world(), [], [1000, 1001])        # retired v1 holdout (D012)
    with pytest.raises(PermissionError):
        fr.evaluate(load_world(), [], [2000])              # v2 holdout (D013)
    with pytest.raises(ValueError):
        fr.evaluate(load_world(), [], [7])


def test_holdout_runner_requires_freeze(tmp_path, monkeypatch):
    import gnm.freeze as fz
    monkeypatch.setattr(fz, "MANIFEST", tmp_path / "missing.json")
    monkeypatch.setattr(fz, "HOLDOUT_LOG", tmp_path / "log.json")
    (tmp_path / "c.json").write_text("{}")
    with pytest.raises(RuntimeError):
        fr.run_frontier_holdout(tmp_path / "c.json", [1000])
    assert not (tmp_path / "log.json").exists()


# ---------------------------------------------------------------- leakage
def test_optim_has_no_truth_access():
    bad = []
    files = list(SRC.rglob("*.py")) + [SCRIPT]
    for f in files:
        text = f.read_text()
        for n in ast.walk(ast.parse(text)):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                mods = [n.module or ""] + [f"{n.module}.{a.name}" for a in n.names]
            for m in mods:
                if m.startswith("gnm.sim.truth") or m.startswith("gnm.sim.generator") or m.endswith(".truth"):
                    bad.append(f"{f.name}: {m}")
        if "ground_truth" in text or "gt_part_truth" in text or "holdout_seeds" in text.replace('"holdout"', ""):
            bad.append(f"{f.name}: truth/holdout reference")
    assert not bad, bad


# ---------------------------------------------------------------- final configuration (forecasts, P2 base, references)
@pytest.fixture(scope="module")
def ctx_p2():
    from gnm.optim.inputs import load_demand_inputs
    from gnm.sim.api import load_world
    w = load_world()
    refs = fr.reference_policies(w)
    ctx = fr.prepare(w, refs["P2"], load_demand_inputs("forecasts"), references=refs)
    return ctx, fr.build_candidates(ctx)


def test_reference_policies_are_frozen_with_the_candidates(ctx_p2, tmp_path):
    ctx, cands = ctx_p2
    kinds = {c.cid: c.kind for c in cands}
    assert all(kinds.get(i) == "policy" for i in ("P0", "P1", "P2"))
    assert cands[0].cid == "P2"                                         # base policy first
    fr.write_candidates(tmp_path / "c.json", cands, "P2")
    ids = {m["id"] for m, _ in fr.load_candidates(tmp_path / "c.json")}
    assert {"P0", "P1", "P2"} <= ids
    # P2 reference is exactly gnm.policy's table; budget points keep P2's network rules
    p2 = next(c for c in cands if c.cid == "P2").policy
    assert p2.lateral_transfers and p2.rebalance
    assert all(c.policy.lateral_transfers == p2.lateral_transfers for c in cands if c.kind in ("budget", "incremental"))


def test_engine_loop_units_enter_the_hub_level(ctx_p2):
    """POL-6/OPT-9: the engine's base_stock sits on top of the seeded repair loop."""
    ctx, _ = ctx_p2
    loops = fr.engine_loop_units(ctx.world)
    assert sum(loops.values()) == sum(it.loop_units for it in ctx.items.values() if it.is_rotable)
    it = next(i for i in ctx.items.values() if i.is_rotable and i.loop_units > 0)
    lv = ctx.base_levels[it.pn].copy()
    import copy as _c
    no_loop = _c.copy(it)
    no_loop.loop_units, no_loop._cache = 0, {}
    assert it.aog_hours(lv) <= no_loop.aog_hours(lv) + 1e-9
    lv2 = lv.copy()
    lv2[0] += it.loop_units
    assert no_loop.aog_hours(lv2) == pytest.approx(it.aog_hours(lv), rel=0.05)


def test_forecast_demand_inputs_match_forecast_rates():
    from gnm.optim.inputs import forecast_demand_inputs
    ff = pd.read_parquet(Path(__file__).resolve().parents[1] / "outputs" / "forecasting" / "final_forecasts.parquet")
    d = forecast_demand_inputs()
    ff = ff[ff.deadline_class != "NONE"]                    # fluids never drive downtime (V2-SIM-2)
    r = ff[ff.part_class == "R"]
    assert d[d.part_class == "R"].rate_per_day.sum() == pytest.approx(r.removal_rate_day.sum(), rel=1e-9)
    c = ff[ff.part_class != "R"]
    assert d[d.part_class != "R"].rate_per_day.sum() == pytest.approx(c.weekly_rate.sum() / 7, rel=1e-9)
    assert set(d.deadline_class) <= {"D0", "D3", "D10"}
    # v2 pipeline = the forecast table's per-station pipeline (P1/P2 definition)
    m = d[d.part_class == "R"].merge(r[["pn", "station", "pipeline_days"]], on=["pn", "station"], suffixes=("", "_ff"))
    assert np.allclose(m.pipeline_days, m.pipeline_days_ff)


def test_doubling_flag_has_reason(ctx_p2):
    ctx, cands = ctx_p2
    big = max((c for c in cands if c.kind == "budget"), key=lambda c: c.allocation_capital_aed)
    flagged = fr.doubled_pns(ctx, big)
    assert flagged
    for pn, why in flagged.items():
        assert int(big.levels[pn].sum()) > 2 * int(ctx.p0_levels[pn].sum()) or int(ctx.p0_levels[pn].sum()) == 0
        assert "pipeline mean" in why and "unit cost" in why
    rows = [r for r in fr.allocation_rows(ctx, big) if r["flag_more_than_doubles_p0"]]
    assert rows and all(r["reason"] for r in rows)



# ---------------------------------------------------------------- AV-09 guardrails (v2)
def _toy_rot(rates, loop=0):
    from gnm.optim.model import ItemModel
    return ItemModel(pn="T-R9", part_class="R", stations=("AUH", "BOM", "LHR"), rates=np.array(rates),
                     resupply_days=40.0, work_days=30.0, route_days=4.0, transport_h=np.array([0.0, 9.0, 16.0]),
                     unit_cost=10000.0, penalty_per_h=20000.0, loop_units=loop)


def test_guardrail_g1_stocking_point_quantile_and_loop():
    from gnm.optim.greedy import guardrail_caps
    from gnm.optim.model import avail_vec, poisson_fill_quantile
    it = _toy_rot([[0.2, 0.0, 0.0], [0.05, 0.0, 0.0], [0.0, 0.0, 0.0]], loop=3)
    caps, why = guardrail_caps(it, {"fill_quantile": 0.995, "low_rate_per_year": 6.0, "low_rate_max_units": 1})
    mu0 = it.hub_mu()
    S = poisson_fill_quantile(mu0, 0.995)
    assert avail_vec(np.array([S]), mu0)[0] >= 0.995 > avail_vec(np.array([S - 1]), mu0)[0]
    assert caps[0] == S - 3                      # hub cap on TOTAL spares: base stock = cap - loop
    assert caps[2] == 0                          # no demand at LHR
    assert caps[1] >= 1 and "G1" in why[1]       # BOM 18/yr > 6/yr -> only the quantile cap


def test_guardrail_g2_low_rate_outstation_and_override():
    from gnm.optim.greedy import guardrail_caps
    it = _toy_rot([[0.2, 0.0, 0.0], [0.01, 0.0, 0.0], [0.5, 0.0, 0.0]])
    g = {"fill_quantile": 0.995, "low_rate_per_year": 6.0, "low_rate_max_units": 1}
    caps, why = guardrail_caps(it, g)
    assert caps[1] == 1 and why[1].startswith("G2")            # 3.65/yr <= 6/yr -> at most 1
    assert caps[2] >= 2                                         # 182/yr: the quantile cap allows more
    with pytest.raises(ValueError):
        guardrail_caps(it, {**g, "overrides": {"T-R9@BOM": {"max_units": 3, "reason": " "}}})
    caps2, why2 = guardrail_caps(it, {**g, "overrides": {"T-R9@BOM": {"max_units": 3, "reason": "ETOPS dispatch"}}})
    assert caps2[1] == 3 and "ETOPS" in why2[1]


def test_frontier_candidates_respect_guardrails(ctx_p2):
    """Every generated candidate (not the as-built reference policies) stays within the AV-09 caps, and the
    outputs show total spares = base stock + loop."""
    ctx, cands = ctx_p2
    assert ctx.guard and ctx.guard.get("enabled")
    for c in cands:
        if c.kind == "policy":
            continue
        rt = fr.rotable_totals(ctx, c)
        assert all(r["exceeds_guardrail_at"] == "" for r in rt), (c.cid, [r["pn"] for r in rt if r["exceeds_guardrail_at"]])
        for r in rt:
            assert r["total_spares"] == r["hub_base_stock"] + r["outstation_base_stock"] + r["loop_units"]
    big = max((c for c in cands if c.kind == "budget"), key=lambda c: c.allocation_capital_aed)
    for r in fr.allocation_rows(ctx, big):
        if r["part_class"] == "R":
            assert r["pn_total_spares_proposed"] >= r["proposed"]
            assert "proposed_total_spares_at_point" in r and r["guardrail_cap_base_stock"] is not None
            assert r["proposed"] <= r["guardrail_cap_base_stock"]


def test_v2_model_uses_route_waits_and_event_cost(ctx_p2):
    ctx, _ = ctx_p2
    it = next(i for i in ctx.items.values() if i.is_rotable and i.rates[:, 0].sum() > 0)
    assert it.event_cost > 0 and it.fitting_h > 0 and (it.route_wait_h > 0).all() and not it.heal
    lv = ctx.base_levels[it.pn].copy()
    lv[:] = 0
    h, e, r, fee = it._rates(lv, 1.0, 1.0)
    assert e > 0 and h > 0 and fee >= 0
    assert it.cost(lv) == pytest.approx(it.penalty_per_h * h + it.event_cost * e + fee)
