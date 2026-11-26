"""AOG incidents from the v2 history: reconciliation, chronology, showcase, and no future information."""
import numpy as np
import pandas as pd
import pytest

from gnm.aog.data import HISTORY_DIR, HistoryView

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
        assert inc["aog_hours_reconstructed"] == pytest.approx(inc["aog_hours"]), inc["id"]   # incl. fitting/RTS
    assert sum(i["aog_hours_reconstructed"] for i in incidents) == pytest.approx(ae.hours.sum())


def test_timelines_chronological_and_complete(incidents):
    for inc in incidents:
        for r in _reqs(inc):
            tl = r["timeline"]
            hs = [s["abs_h"] for s in tl]
            assert hs == sorted(hs), inc["id"]
            core = [s for s in tl if not s["evidence"].get("context")]
            steps = [s["step"] for s in core]
            assert steps[0] in ("removal", "requirement") and "request" in steps and "local_check" in steps
            assert "released" in steps or "open" in steps
            assert all(s["abs_h"] < r["need_h"] for s in tl if s["evidence"].get("context"))
            for s in tl:
                assert s["t_h"] == s["abs_h"] - r["need_h"] and s["datetime"].endswith("Z")
            assert not any("ready" in s["event"].lower() for s in tl)       # wording: never "aircraft ready"


def test_hub_transfer_feasibility_matches_history(incidents):
    """Option hub_transfer is feasible whenever history shipped from AUH stock at request time."""
    n = 0
    for inc in incidents:
        for r in _reqs(inc):
            if r["counterfactual"]["actual_route"] == "hub_transfer":
                assert next(o for o in r["options"] if o["key"] == "hub_transfer")["feasible"], inc["id"]
                n += 1
    assert n > 0


def test_routes_match_engine_rules(view, incidents):
    for inc in incidents:
        for r in _reqs(inc):
            route = r["counterfactual"]["actual_route"]
            if route == "robbery":
                assert r["station"] == view.net.hub and r["approval_flag"] == view.cfg["aog_sourcing"]["robbery"]["flag"]
            if route == "local_borrow":
                assert r["station"] != view.net.hub
            if route == "local_buy":
                assert view.parts.loc[r["pn"]].part_class in ("C", "E")


def test_counterfactual_consistent(incidents):
    for inc in incidents:
        cf = inc["counterfactual"]
        best = [o for o in inc["options"] if o["rank"] == 1]
        assert not any(o["key"] == "robbery" and o["rank"] for o in inc["options"])
        if cf["best_option"]:
            assert best and best[0]["key"] == cf["best_option"]
            assert cf["exposure_saving_aed"] == pytest.approx(cf["actual_exposure_aed"] - cf["best_realised_exposure_aed"], abs=0.05)


def test_showcase_has_required_cases(view, incidents):
    from gnm.aog.incidents import select_showcase
    ids = select_showcase(incidents, 12, view)
    assert len(ids) == len(set(ids)) == 12
    show = [i for i in incidents if i["id"] in ids]
    pm = view.t["part_master"]
    ps1 = pm[pm.planted == "PS1"].pn.iloc[0]                          # from planted metadata, never hard-coded
    assert any(i["pn"] == ps1 and i["planted"] == "PS1" and i["station"] != view.net.hub for i in show)
    assert max(i["aog_hours"] for i in show) == max(i["aog_hours"] for i in incidents)
    assert any(i["deadline"] in ("D3", "D10") and i["trigger"] == "deadline_expired" for i in show)
    routes = {i["counterfactual"]["actual_route"] for i in show}
    assert {"robbery", "exchange_loan", "local_borrow", "local_buy", "hub_transfer"} <= routes
    assert len({i["station"] for i in show}) >= 4


def _perturbed(view, t):
    """Change everything that happens after t: later receipts/returns, future transactions, fills and loans."""
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
    rb = tb["aog_robberies"]
    tb["aog_robberies"] = rb[rb.robbed_h <= t].copy()
    return HistoryView(tb, view.net, view.cfg, view.acfg)


def test_options_use_no_future_information(view, incidents):
    from gnm.aog.incidents import select_showcase
    from gnm.aog.options import build_snapshot, evaluate_options
    ids = set(select_showcase(incidents, 12, view))
    mr = view.t["material_requests"].set_index("request_id", drop=False)
    checked = 0
    for inc in incidents:
        if inc["id"] not in ids:
            continue
        req = mr.loc[inc["request_id"]]
        pv = _perturbed(view, int(req.need_h))
        a = evaluate_options(build_snapshot(view, req), view.net, view.cfg, view.acfg)
        preq = pv.t["material_requests"].set_index("request_id", drop=False).loc[inc["request_id"]]
        b = evaluate_options(build_snapshot(pv, preq), pv.net, pv.cfg, pv.acfg)
        assert a == b, inc["id"]
        checked += 1
    assert checked == 12


def test_perturbation_is_material(view):
    t = 5000
    pv = _perturbed(view, t)
    pn0 = view.t["part_master"].pn.iloc[0]
    assert pv.ledger.on_hand(pn0, "AUH", t + 2) == view.ledger.on_hand(pn0, "AUH", t) + 50
    assert pv.ledger.on_hand(pn0, "AUH", t) == view.ledger.on_hand(pn0, "AUH", t)


def test_ledger_matches_stock_snapshots(view):
    """SIM-9: the running sum of qty_delta equals the weekly snapshot on-hand (owned serviceable stock)."""
    ss = view.t["stock_snapshots"]
    sample = ss[ss.week.isin([10, 50, 103])].sample(200, random_state=0)
    for r in sample.itertuples():
        assert view.ledger.on_hand(r.pn, r.station, (r.week + 1) * 168) == r.on_hand
