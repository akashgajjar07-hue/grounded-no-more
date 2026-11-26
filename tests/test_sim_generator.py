"""Generator: reproducibility, slice-consistency of streams, schema validity, rate sanity."""
import numpy as np
import pandas as pd
import pytest

from gnm import schemas
from gnm.sim.generator import generate_scenario, generate_world, small_config

from _simfx import expected_removals, full_world, small_scenario, small_world


def test_world_reproducible_and_counts():
    w1, t1 = generate_world(small_config())
    w2, t2 = small_world()
    pd.testing.assert_frame_equal(w1.parts, w2.parts)
    pd.testing.assert_frame_equal(t1.parts, t2.parts)
    assert len(w1.parts) == 20 and set(w1.stations.station) == {"AUH", "BOM"}


def test_full_world_master_data():
    w, gt = full_world()
    assert w.parts.part_class.value_counts().to_dict() == {"C": 45, "R": 40, "E": 35}
    assert w.parts.pn.str.match(r"^GN-\d{2}-[CER]\d{3}$").all()
    assert w.parts.pn.str.slice(3, 5).eq(w.parts.ata).all()
    assert len(w.aircraft) == 40 and w.aircraft["tail"].str.match(r"^A6-F[HW][A-Z]$").all()
    assert sorted(w.parts.planted.dropna()) == ["PS1", "PS2", "PS3", "PS4"]
    for name, df in [("aircraft_master", w.aircraft), ("station_master", w.stations), ("part_master", w.parts),
                     ("part_applicability", w.applicability), ("gt_part_truth", gt.table())]:
        assert schemas.validate_table(name, df) == [], name
    # quoted MTBUR is optimistic on average (generator.quoted_mtbur_optimism)
    re_ = w.parts.part_class != "C"
    ratio = (w.parts.loc[re_, "mtbur_quoted"].to_numpy() / gt.parts.loc[re_, "mtbur_true"].to_numpy())
    assert np.median(ratio) > 1.0
    # some PNs both archetypes, some only one
    n_arch = w.applicability.groupby("pn").size()
    assert (n_arch == 2).any() and (n_arch == 1).any()


def test_scenario_same_seed_identical_different_seed_differs():
    w, gt = small_world()
    a = generate_scenario(w, gt, 7, 0, 29)
    b = small_scenario()
    c = generate_scenario(w, gt, 8, 0, 29)
    pd.testing.assert_frame_equal(a.requests, b.requests)
    pd.testing.assert_frame_equal(a.removals, b.removals)
    assert a.repair_days == b.repair_days and a.condemn_flag == b.condemn_flag
    assert all(np.array_equal(a.lead_time_days[k], b.lead_time_days[k]) for k in a.lead_time_days)
    assert not a.removals[["tail", "pn", "removal_h"]].equals(c.removals[["tail", "pn", "removal_h"]])


def test_scenario_slice_equals_longer_range():
    """Weeks [24, 29] generated alone == the same slice of [0, 29] (per-(seed, week) streams)."""
    w, gt = small_world()
    full = small_scenario()
    part = generate_scenario(w, gt, 7, 24, 29)
    h0 = 24 * 168
    f_req = full.requests[full.requests.need_h >= h0].reset_index(drop=True)
    pd.testing.assert_frame_equal(f_req, part.requests.reset_index(drop=True))
    f_rem = full.removals[full.removals.removal_h >= h0].reset_index(drop=True)
    pd.testing.assert_frame_equal(f_rem, part.removals.reset_index(drop=True))
    for rid, d in part.repair_days.items():
        assert full.repair_days[rid] == d and full.condemn_flag[rid] == part.condemn_flag[rid]
    pd.testing.assert_frame_equal(full.flights[full.flights.week >= 24].reset_index(drop=True), part.flights)


@pytest.mark.slow
def test_holdout_slice_full_scale():
    w, gt = full_world()
    a = generate_scenario(w, gt, 7, 96, 155)
    b = generate_scenario(w, gt, 7, 104, 155)
    pd.testing.assert_frame_equal(a.requests[a.requests.week >= 104].reset_index(drop=True), b.requests)


def test_scenario_tables_valid():
    w, gt = small_world()
    sc = small_scenario()
    for name, df in [("flight_exposure", sc.flights), ("maintenance_schedule", sc.maintenance),
                     ("removal_events", sc.removals), ("material_requests", sc.requests)]:
        assert schemas.validate_table(name, df) == [], name
    assert schemas.validate_fks({"aircraft_master": w.aircraft, "part_master": w.parts, "removal_events": sc.removals,
                                 "material_requests": sc.requests, "flight_exposure": sc.flights,
                                 "maintenance_schedule": sc.maintenance}) == []
    rq = sc.requests
    assert (rq.qty > 0).all() and (rq.known_h <= rq.need_h).all()
    # every removal has exactly one unscheduled request; rotable removals carry CRNs
    um = rq[rq.source == "unscheduled_removal"]
    assert sorted(um.removal_id.astype(int)) == sorted(sc.removals.removal_id)
    rot = sc.removals.merge(w.parts[["pn", "part_class"]])
    assert set(rot[rot.part_class == "R"].removal_id) == set(sc.repair_days) == set(sc.condemn_flag)
    # removals happen at the arrival station of a leg of that tail at that hour
    legs = set(zip(sc.flights["tail"], sc.flights.arr_station, sc.flights.arr_h))
    assert all(k in legs for k in zip(sc.removals["tail"], sc.removals.station, sc.removals.removal_h))


def test_utilisation_close_to_config():
    w, _ = full_world()
    from gnm.sim.generator import build_schedule
    fl, ms = build_schedule(w, 104)
    nb = w.aircraft[w.aircraft.archetype == "narrowbody"]["tail"]
    f = fl[fl["tail"].isin(nb)]
    fh_day = f.fh.sum() / len(nb) / (104 * 7)
    fc_day = len(f) / len(nb) / (104 * 7)
    assert abs(fh_day - 10.5) / 10.5 < 0.08 and abs(fc_day - 4.2) / 4.2 < 0.10
    assert (ms.station == "AUH").all() and len(ms) > 0


def test_removal_rate_matches_truth_small():
    w, gt = small_world()
    sc = small_scenario()
    exp = expected_removals(w, gt, sc)
    obs = sc.removals.groupby("pn").size().reindex(list(exp)).fillna(0)
    tot_e, tot_o = sum(exp.values()), obs.sum()
    assert abs(tot_o - tot_e) < 4 * np.sqrt(tot_e) + 0.15 * tot_e


@pytest.mark.slow
def test_removal_rate_matches_truth_long_run():
    w, gt = full_world()
    sc = generate_scenario(w, gt, 1234, 0, 155)
    exp = pd.Series(expected_removals(w, gt, sc))
    obs = sc.removals.groupby("pn").size().reindex(exp.index).fillna(0)
    assert abs(obs.sum() / exp.sum() - 1) < 0.05
    # per-PN: most PNs within a generous band (NB frailty widens the spread)
    big = exp > 30
    assert ((obs[big] / exp[big] - 1).abs() < 0.35).mean() > 0.9
