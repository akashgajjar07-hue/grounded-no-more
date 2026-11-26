"""Slow policy checks: run_many pairing on selection seeds, variant re-planning, Palm-vs-sim plumbing."""
import numpy as np
import pytest

from gnm.policy import evaluate_policies as ep
from gnm.policy import forecast_pipeline as fp
from gnm.policy.policies import build_p1

from _polfx import champions, forecasts, world

pytestmark = pytest.mark.slow


def test_run_variant_pairs_and_breakdowns():
    w = world()
    pv = ep.policies_for_variant(w, "central", champions())
    ecfg = fp.load_policy_config()["evaluation"]
    r = ep.run_variant(w, "central", pv["policies"], [100, 101], ecfg, processes=2)
    k = r["kpis"]
    assert len(k) == 6 and set(k.policy_id) == {"P0", "P1", "P2"}
    st = r["stations"].groupby(["policy_id", "seed"]).aog_hours.sum()
    kk = k.set_index(["policy_id", "seed"]).aog_hours
    assert np.allclose(st.loc[kk.index].to_numpy(), kk.to_numpy())


def test_variant_history_replanning_differs():
    w = world()
    a = ep.variant_history(w, "high_stress")
    assert a["material_requests"].week.max() <= 103
    ff = fp.final_forecasts(a, w, champions())
    base = forecasts()
    r_hi = ff[ff.part_class == "R"].drop_duplicates("pn").net_weekly_rate.sum()
    r_c = base[base.part_class == "R"].drop_duplicates("pn").net_weekly_rate.sum()
    assert r_hi > r_c        # high_stress = lower true MTBUR -> more removals seen in its history


def test_palm_vs_sim_runs():
    w, ff = world(), forecasts()
    out = ep.palm_vs_sim(w, build_p1(w, ff), ff, [100, 101], processes=2)
    assert {"palm_availability", "sim_immediate_fill", "total_spares"} <= set(out.columns)
    hub = out[(out.station == "AUH") & (out.sim_requests > 0)]
    assert abs(hub.palm_availability.mean() - hub.sim_immediate_fill.mean()) < 0.1

# v2 rebuild (D012): these tests read v1 outputs / docs/data exports; skipped until v2 regeneration.
import pytest as _pytest_v2  # noqa: E402
pytestmark = (pytestmark if isinstance(pytestmark, list) else [pytestmark]) + [_pytest_v2.mark.v1_outputs, _pytest_v2.mark.skip(reason="awaiting v2 regeneration")]
