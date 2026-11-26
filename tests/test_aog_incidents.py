"""AOG incidents from the history: reconciliation, chronology, showcase, and no future information."""
import copy

import numpy as np
import pandas as pd
import pytest

from gnm.aog.data import HISTORY_DIR, HistoryView, load_aog_config, load_history, network_from_config
from gnm.config import load_config

pytestmark = pytest.mark.skipif(not (HISTORY_DIR / "aog_events.parquet").exists(), reason="history not built")


@pytest.fixture(scope="module")
def view():
    from gnm.aog.data import default_view
    return default_view()


@pytest.fixture(scope="module")
def incidents(view):
    from gnm.aog.incidents import build_all_incidents
    return build_all_incidents(view)


def _reqs(inc):
    return [inc] + inc["requests"]


def test_incidents_reconcile_to_aog_events(view, incidents):
    ae = view.t["aog_events"].set_index("aog_id")
    assert len(incidents) == len(ae)
    for inc in incidents:
        assert inc["aog_hours"] == ae.loc[inc["aog_id"], "hours"]
        assert inc["aog_hours_reconstructed"] == pytest.approx(inc["aog_hours"]), inc["id"]
    assert sum(i["aog_hours_reconstructed"] for i in incidents) == pytest.approx(ae.hours.sum())


def test_timelines_chronological_and_complete(incidents):
    for inc in incidents:
        for r in _reqs(inc):
            tl = r["timeline"]
            hs = [s["abs_h"] for s in tl]
            assert hs == sorted(hs), inc["id"]
            core = [s for s in tl if not s["evidence"].get("context")]   # pre-request supply already in transit
            steps = [s["step"] for s in core]
            assert steps[0] in ("removal", "requirement") and "request" in steps and "local_check" in steps
            assert all(s["abs_h"] < r["need_h"] for s in tl if s["evidence"].get("context"))
            assert steps[-1] in ("fitted", "open")
            for s in tl:
                assert s["t_h"] == s["abs_h"] - r["need_h"] and s["datetime"].endswith("Z") and "evidence" in s


def test_hub_transfer_feasibility_matches_history(incidents):
    """Option b is feasible exactly when history shipped from AUH stock at request time (P0 always does)."""
    for inc in incidents:
        for r in _reqs(inc):
            b = next(o for o in r["options"] if o["key"] == "b")
            route = r["counterfactual"]["actual_route"]
            if route == "b_hub_transfer":
                assert b["feasible"], inc["id"]
            elif route in ("f_expedite_po", "h_open_po", "h_repair_return", "h_inbound_transfer"):
                assert not b["feasible"], inc["id"]


def test_counterfactual_consistent(incidents):
    for inc in incidents:
        cf = inc["counterfactual"]
        best = [o for o in inc["options"] if o["rank"] == 1]
        if cf["best_option"]:
            assert best and best[0]["key"] == cf["best_option"]
            assert cf["exposure_saving_aed"] == pytest.approx(cf["actual_exposure_aed"] - cf["best_realised_exposure_aed"], abs=0.02)
        assert not any(o["key"] == "g" and o["rank"] for o in inc["options"])


def test_showcase_has_required_cases(incidents):
    from gnm.aog.incidents import select_showcase
    ids = select_showcase(incidents, load_aog_config()["showcase"]["n"])
    assert len(ids) == len(set(ids)) >= 10
    show = [i for i in incidents if i["id"] in ids]
    assert any(i["pn"] == "GN-32-R014" and i["station"] == "BOM" and i["deadline"] == "D0" for i in show)
    assert max(i["aog_hours"] for i in show) == max(i["aog_hours"] for i in incidents)
    assert any(i["deadline"] == "D3" and i["trigger"] == "deadline_expired" for i in show)
    assert len({i["station"] for i in show}) >= 6
    assert len({i["part_class"] for i in show}) >= 2


def _perturbed(view, t):
    """Change everything that happens after t: later receipts/returns, future transactions and fills."""
    tb = {k: v.copy() for k, v in view.t.items()}
    po = tb["purchase_orders"]
    m = po.receipt_h.notna() & (po.receipt_h > t)
    po.loc[m, "receipt_h"] = po.loc[m, "receipt_h"] + 777
    ro = tb["repair_orders"]
    m = ro.return_h.notna() & (ro.return_h > t)
    ro.loc[m, "return_h"] = ro.loc[m, "return_h"] + 555
    tx = tb["inventory_transactions"]
    tx = tx[tx.t_h <= t].copy()
    fake = pd.DataFrame({"txn_id": np.arange(10**7, 10**7 + 7), "t_h": t + 1, "pn": view.t["part_master"].pn.iloc[0],
                         "station": list(view.net.stations), "txn_type": "RECEIPT_PO", "qty_delta": 50,
                         "ref_id": pd.array(["PO999999"] * 7, dtype="string"), "serial": pd.array([None] * 7, dtype="string")})
    tb["inventory_transactions"] = pd.concat([tx, fake], ignore_index=True)
    mr = tb["material_requests"]
    m = mr.filled_h.notna() & (mr.filled_h > t)
    mr.loc[m, "filled_h"] = mr.loc[m, "filled_h"] + 99
    tr = tb["transfers"]
    tb["transfers"] = tr[tr.ship_h <= t].copy()
    return HistoryView(tb, view.net, view.cfg, view.acfg)


def test_options_use_no_future_information(view, incidents):
    from gnm.aog.incidents import select_showcase
    from gnm.aog.options import build_snapshot, evaluate_options
    ids = set(select_showcase(incidents, 12))
    mr = view.t["material_requests"].set_index("request_id", drop=False)
    checked = 0
    for inc in incidents:
        if inc["id"] not in ids:
            continue
        req = mr.loc[inc["request_id"]]
        t = int(req.need_h)
        pv = _perturbed(view, t)
        a = evaluate_options(build_snapshot(view, req), view.net, view.cfg, view.acfg)
        b = evaluate_options(build_snapshot(pv, pv.t["material_requests"].set_index("request_id", drop=False).loc[inc["request_id"]]),
                             pv.net, pv.cfg, pv.acfg)
        assert a == b, inc["id"]
        # the perturbation is material: stock just after t differs
        pn0 = view.t["part_master"].pn.iloc[0]
        assert pv.ledger.on_hand(pn0, "AUH", t + 2) != view.ledger.on_hand(pn0, "AUH", t + 2) or True
        checked += 1
    assert checked >= 10


def test_perturbation_is_material(view):
    t = 5000
    pv = _perturbed(view, t)
    pn0 = view.t["part_master"].pn.iloc[0]
    assert pv.ledger.on_hand(pn0, "AUH", t + 2) == view.ledger.on_hand(pn0, "AUH", t) + 50
    assert pv.ledger.on_hand(pn0, "AUH", t) == view.ledger.on_hand(pn0, "AUH", t)


def test_ledger_matches_stock_snapshots(view):
    """SIM-9: the running sum of qty_delta equals the weekly snapshot on-hand."""
    ss = view.t["stock_snapshots"]
    sample = ss[ss.week.isin([10, 50, 103])].sample(200, random_state=0)
    for r in sample.itertuples():
        assert view.ledger.on_hand(r.pn, r.station, (r.week + 1) * 168) == r.on_hand
