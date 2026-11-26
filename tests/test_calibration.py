"""V2-SIM-CAL: v2 P0-only calibration is inside the configured band (fast: recorded summary; slow: recompute)."""
import json

import pytest

from gnm.config import load_config
from gnm.sim.calibration import SUMMARY

KEYS = ["rotable_immediate_fill_rate", "aog_hours_per_year", "aog_events_per_year"]


def _targets():
    t = load_config()["calibration_targets"]
    return {k: t[k] for k in KEYS}


def test_recorded_v2_summary_in_band():
    s = json.loads(SUMMARY.read_text())
    assert s["policy"] == "P0 only" and s["version"] == "v2"
    t = _targets()
    c = s["variants"]["central"]
    for k in KEYS:          # central world: history AND selection mean inside the band
        assert t[k][0] <= c["history"][k] <= t[k][1], (k, c["history"][k], t[k])
        assert t[k][0] <= c["selection_p0_mean"][k] <= t[k][1], (k, c["selection_p0_mean"][k], t[k])
    v = s["variants"]
    pooled = {w: v[w]["pooled_history_selection"] for w in v}
    # stress worlds sit near the band ends and keep the ordering low < central < high (AOG), reverse for fill
    assert pooled["low_stress"]["aog_hours_per_year"] < pooled["central"]["aog_hours_per_year"] < pooled["high_stress"]["aog_hours_per_year"]
    assert pooled["low_stress"]["rotable_immediate_fill_rate"] > pooled["central"]["rotable_immediate_fill_rate"] > pooled["high_stress"]["rotable_immediate_fill_rate"]
    lo, hi = t["aog_hours_per_year"], t["rotable_immediate_fill_rate"]
    assert abs(pooled["low_stress"]["aog_hours_per_year"] - lo[0]) / lo[0] < 0.10            # AOG end binds
    assert abs(pooled["high_stress"]["rotable_immediate_fill_rate"] - hi[0]) < 0.01           # fill end binds
    for w in v:
        assert 55 <= pooled[w]["aog_events_per_year"] <= 105
    # year 1 vs year 2 comparable (steady-state initialisation)
    y1, y2 = c["history_year1"]["aog_hours_per_year"], c["history_year2"]["aog_hours_per_year"]
    assert max(y1, y2) / min(y1, y2) < 1.5
    # the user's choice: V1 applied, market settings and line kit not applied
    su = s["settings_used"]
    assert su["parts.quoted_mtbur_optimism"] == 1.10 and su["parts.quoted_mtbur_noise_sd_log"] == 0.20
    assert su["generator.quoted_tat_optimism"] == 0.95 and su["generator.quoted_tat_noise_sd_log"] == 0.10
    assert load_config()["aog_sourcing"]["robbery"]["availability"] == 0.60
    assert "line_station_kit" not in load_config()["policy_baseline_P0"]


@pytest.mark.slow
def test_p0_history_in_band_recomputed():
    from gnm.sim.api import load_or_generate_scenario, load_world
    from gnm.sim.baseline import build_p0
    from gnm.sim.calibration import history_metrics
    from gnm.sim.engine import run_policy
    cfg = load_config()
    w0, w1 = cfg["calendar"]["history_weeks"]
    world = load_world()
    res = run_policy(world, load_or_generate_scenario(cfg["seeds"]["history_seed"], w0, w1, use_cache=False),
                     build_p0(world), w0, w1)
    m = history_metrics(world, res, w0, w1)
    t = _targets()
    for k in KEYS:
        assert t[k][0] <= m[k] <= t[k][1], (k, m[k])
    recorded = json.loads(SUMMARY.read_text())["variants"]["central"]["history"]
    assert all(abs(recorded[k] - m[k]) < 1e-9 for k in KEYS)
