"""AOG sourcing-option rules (v2) and exposure arithmetic on hand-built fixtures (no history needed)."""
import copy

import pytest

from gnm.aog.data import fitting_mid_h, load_aog_config, network_from_config, poisson_protection
from gnm.aog.options import KEYS, Snapshot, evaluate_options, exposure, human_panel
from gnm.config import load_config

CFG = load_config()
ACFG = load_aog_config()
NET = network_from_config(CFG, ACFG)
STATIONS = list(NET.stations)
ECO = CFG["economics"]
AGS = CFG["aog_sourcing"]
RATE_NB = ECO["aog_penalty_aed_per_hour"]["narrowbody"]
EV_NB = ECO["aog_event_cost_aed"]["narrowbody"]
FIT_R = fitting_mid_h(CFG, "R")


def snap(**kw):
    base = dict(pn="GN-99-R001", part_class="R", unit_cost=100_000.0, station="BOM", need_h=1000, qty=1,
                deadline_class="D0", archetype="narrowbody", on_hand={s: 0 for s in STATIONS},
                repair_cost=20_000.0, quoted_tat_d=30.0, repair_shop="AUH_INHOUSE", donor_candidates=5)
    base.update(kw)
    return Snapshot(**base)


def opts(s, acfg=ACFG):
    return {o["key"]: o for o in evaluate_options(s, NET, CFG, acfg)}


def oh(**kw):
    return {**{s: 0 for s in STATIONS}, **kw}


def test_every_option_present_in_order():
    assert [o["key"] for o in evaluate_options(snap(), NET, CFG, ACFG)] == list(KEYS)


def test_no_stock_is_infeasible_with_no_stock():
    o = opts(snap())
    for k in ("local", "hub_transfer", "lateral"):
        assert not o[k]["feasible"] and "NO_STOCK" in o[k]["reason_codes"]
    assert o["exchange_loan"]["feasible"] and o["local_borrow"]["feasible"]     # market routes remain


def test_local_stock_has_no_exposure():
    o = opts(snap(on_hand=oh(BOM=1, AUH=5)))
    assert o["local"]["feasible"] and o["local"]["wait_h"] == 0 and o["local"]["exposure_aed"] == 0
    assert o["local"]["rank"] == 1


def test_auh_transfer_uses_transport_matrix_cost_and_fitting():
    o = opts(snap(on_hand=oh(AUH=2)))
    b = o["hub_transfer"]
    w = CFG["network"]["aog_transport_hours"]["AUH"]["BOM"]
    assert b["feasible"] and b["wait_h"] == w and b["direct_cost"] == pytest.approx(NET.em_cost[("AUH", "BOM")])
    assert b["aog_h"] == pytest.approx(w + FIT_R)
    assert b["exposure_aed"] == pytest.approx((w + FIT_R) * RATE_NB + EV_NB + b["direct_cost"])
    assert b["rank"] == 1


def test_lateral_respects_protection_level():
    stock = oh(JED=1, SIN=2)
    o = opts(snap(on_hand=stock, protection={"JED": 1, "SIN": 1}))
    assert o["lateral"]["feasible"] and o["lateral"]["source"] == "SIN"
    o = opts(snap(on_hand=stock, protection={"JED": 1, "SIN": 2}))
    assert not o["lateral"]["feasible"] and o["lateral"]["reason_codes"] == ["BELOW_PROTECTION_LEVEL"]


def test_local_borrow_outstation_only_with_station_odds_and_exchange_fallback():
    o = opts(snap(station="AUH"))
    assert o["local_borrow"]["reason_codes"] == ["OUTSTATION_ONLY"]
    o = opts(snap(station="BOM"))
    lb, ex = o["local_borrow"], o["exchange_loan"]
    p = AGS["local_borrow"]["availability"]["narrowbody"]["BOM"]
    assert lb["availability_p"] == p and lb["fallback"] == "exchange_loan"
    pe = AGS["exchange_loan"]["availability"]["narrowbody"]
    s = 1 - (1 - p) * (1 - pe)
    assert lb["evidence"]["cycle_success_p"] == pytest.approx(s, abs=1e-3)
    assert lb["wait_h"] < ex["wait_h"]              # trying the local market first shortens the expected wait
    # widebody odds are lower than narrowbody at the same station
    w = opts(snap(station="BOM", archetype="widebody"))["local_borrow"]
    assert w["availability_p"] < p


def test_exchange_loan_expected_wait_and_fees():
    o = opts(snap(station="AUH", archetype="widebody"))
    ex = o["exchange_loan"]
    p = AGS["exchange_loan"]["availability"]["widebody"]
    lo, hi = AGS["exchange_loan"]["response_hours"]["widebody"]
    R = AGS["retry_hours"]["R"]
    assert ex["wait_h"] == pytest.approx((lo + hi) / 2 + R * (1 - p) / p, abs=0.1)
    fee = AGS["exchange_loan"]["fee_pct_of_list"]["widebody"] * 100_000
    assert ex["direct_cost"] >= fee                  # fee + daily fee until the own unit is expected
    assert ex["evidence"]["pool_growth"] is False
    assert opts(snap(part_class="E"))["exchange_loan"]["reason_codes"] == ["ROTABLES_ONLY"]


def test_robbery_hub_only_human_decision_never_ranked():
    o = opts(snap(station="BOM"))
    assert "HUB_ONLY" in o["robbery"]["reason_codes"]
    o = opts(snap(station="AUH"))
    g = o["robbery"]
    assert g["human_decision"] and not g["feasible"] and g["rank"] is None and g["wait_h"] is not None
    assert "HUMAN_DECISION_REQUIRED" in g["reason_codes"] and g["flag"] == AGS["robbery"]["flag"]
    assert "NO_DONOR_AIRCRAFT" in opts(snap(station="AUH", donor_candidates=0))["robbery"]["reason_codes"]
    panel = human_panel(snap(station="AUH"), list(o.values()))
    assert panel["recommended"] != "robbery" and "human decision" in panel["robbery_note"]


def test_local_buy_for_consumables_and_expendables_only():
    o = opts(snap(part_class="E", unit_cost=2_000.0))
    b = o["local_buy"]
    assert b["feasible"] and b["direct_cost"] == pytest.approx(AGS["local_buy"]["premium_pct"] * 2_000.0)
    assert opts(snap())["local_buy"]["reason_codes"] == ["CONSUMABLES_EXPENDABLES_ONLY"]


def test_pool_not_contracted_is_greyed():
    d = opts(snap())["pool"]
    assert not d["feasible"] and d["reason_codes"] == ["NOT_CONTRACTED"] and d["greyed"] and d["rank"] is None
    a2 = copy.deepcopy(ACFG)
    a2["pool_exchange"]["contracted"] = True
    assert opts(snap(), a2)["pool"]["feasible"]


def test_repair_queue_jump_rules():
    assert opts(snap())["repair_queue_jump"]["reason_codes"] == ["NO_OPEN_RO"]
    started = [{"ro_id": 1, "shop": "AUH_INHOUSE", "quoted_due_h": 1100, "serial": "X", "started": True}]
    assert "NO_QUEUE_TO_JUMP" in opts(snap(open_ros=started))["repair_queue_jump"]["reason_codes"]
    queued = [{"ro_id": 2, "shop": "AUH_INHOUSE", "quoted_due_h": 5000, "serial": "Y", "started": False}]
    q = opts(snap(station="AUH", quoted_tat_d=2.0, open_ros=queued))["repair_queue_jump"]
    # queue wait removed, quoted work time kept; flat surcharge on the repair cost; labelled estimate
    assert q["estimate"] and q["wait_h"] == pytest.approx(48.0)
    assert q["direct_cost"] == pytest.approx(ACFG["repair_queue_jump"]["surcharge_pct_of_repair_cost"] * 20_000.0)
    assert q["feasible"] and q["rank"] == 1
    slow = opts(snap(station="AUH", quoted_tat_d=60.0, open_ros=queued))["repair_queue_jump"]
    assert not slow["feasible"] and "DOES_NOT_BEAT_ALTERNATIVES" in slow["reason_codes"]


def test_exposure_arithmetic_on_every_option():
    assert exposure(30, 0, 4, 15_000, 40_000, 2_000) == (34.0, 34 * 15_000 + 40_000 + 2_000)
    assert exposure(30, 72, 4, 15_000, 40_000, 2_000) == (0.0, 2_000.0)
    assert exposure(72, 72, 4, 15_000, 40_000, 0) == (0.0, 0.0)          # exactly on time is not late
    pos = [{"po_id": 3, "qty": 1, "due_h": 1400, "reason": "reorder"}]
    for dc, win in (("D0", 0), ("D3", 72), ("D10", 240)):
        for cls in ("R", "E"):
            s = snap(deadline_class=dc, part_class=cls, open_pos=pos, on_hand=oh(SIN=1))
            fit = fitting_mid_h(CFG, cls)
            for o in evaluate_options(s, NET, CFG, ACFG):
                if o["wait_h"] is None:
                    continue
                late = o["wait_h"] > win
                a = (o["wait_h"] + fit - win) if late else 0.0
                assert o["aog_h"] == pytest.approx(a, abs=0.1)
                assert o["exposure_aed"] == pytest.approx(a * RATE_NB + (EV_NB if late else 0) + o["direct_cost"], abs=2)
                assert o["deadline_met"] == (not late)


def test_deferred_need_ranks_cheapest_on_time_option_and_ships_routine():
    o = opts(snap(deadline_class="D10", on_hand=oh(AUH=1, SIN=1)))
    b = o["hub_transfer"]
    assert "ROUTINE_SHIPMENT" in b["reason_codes"] and b["direct_cost"] == ECO["routine_shipment_aed_per_line"]
    assert b["exposure_aed"] == b["direct_cost"] and b["rank"] == 1
    d3 = opts(snap(deadline_class="D3", on_hand=oh(AUH=1)))["hub_transfer"]
    assert "NEXT_FLIGHT_OUT" in d3["reason_codes"]       # 72 h window < planned routine transit + margin


def test_reservations_block_deferred_but_not_d0():
    o = opts(snap(deadline_class="D3", on_hand=oh(BOM=1), committed={"BOM": 1}))
    assert o["local"]["reason_codes"] == ["COMMITTED_TO_KIT"]
    assert opts(snap(deadline_class="D0", on_hand=oh(BOM=1), committed={"BOM": 1}))["local"]["feasible"]


def test_inbound_queues_behind_earlier_backorders():
    pos = [{"po_id": 1, "qty": 1, "due_h": 1100, "reason": "reorder"},
           {"po_id": 2, "qty": 1, "due_h": 1500, "reason": "reorder"}]
    h0 = opts(snap(station="AUH", open_pos=pos))["inbound"]
    h1 = opts(snap(station="AUH", open_pos=pos, backorders_ahead=1))["inbound"]
    assert h0["wait_h"] == 100 and h1["wait_h"] == 500 and "QUEUED_BEHIND_BACKORDERS" in h1["reason_codes"]
    assert not opts(snap(station="AUH", open_pos=pos, backorders_ahead=2))["inbound"]["feasible"]
    tr = [{"transfer_id": 9, "from": "AUH", "qty": 1, "eta_h": 1030}]
    assert opts(snap(inbound_transfers=tr))["inbound"]["reason_codes"][0] == "INBOUND_TRANSFER"


def test_poisson_protection_level():
    L = NET.routine_h
    assert poisson_protection(0.0, L, 0.95) == 0
    assert poisson_protection(2 / 8760, L, 0.95) == 1
    assert poisson_protection(8 / 8760, L, 0.95) == 2
