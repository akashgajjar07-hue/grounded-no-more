"""AOG sourcing-option rules and cost arithmetic on hand-built fixtures (no history needed)."""
import copy

import pytest

from gnm.aog.data import load_aog_config, network_from_config, poisson_protection
from gnm.aog.options import Snapshot, evaluate_options, exposure, human_panel
from gnm.config import load_config

CFG = load_config()
ACFG = load_aog_config()
NET = network_from_config(CFG, ACFG)
STATIONS = list(NET.stations)
PEN_NB = CFG["economics"]["aog_penalty_aed_per_hour"]["narrowbody"]


def snap(**kw):
    base = dict(pn="GN-99-R001", part_class="R", unit_cost=100_000.0, quoted_lead_d=90.0, station="BOM", need_h=1000,
                qty=1, deadline_class="D0", archetype="narrowbody", penalty_per_h=PEN_NB,
                on_hand={s: 0 for s in STATIONS})
    base.update(kw)
    return Snapshot(**base)


def opts(s, acfg=ACFG):
    return {o["key"]: o for o in evaluate_options(s, NET, CFG, acfg)}


def test_no_stock_anywhere_is_infeasible_with_no_stock():
    o = opts(snap())
    for k in "abc":
        assert o[k]["feasible"] is False
        assert "NO_STOCK" in o[k]["reason_codes"]
    assert o["f"]["feasible"]            # the market buy is always available
    assert o["f"]["rank"] == 1


def test_local_stock_wins_with_zero_wait_and_cost():
    o = opts(snap(on_hand={**{s: 0 for s in STATIONS}, "BOM": 1, "AUH": 5}))
    assert o["a"]["feasible"] and o["a"]["wait_h"] == 0 and o["a"]["exposure_aed"] == 0
    assert o["a"]["rank"] == 1


def test_auh_emergency_transfer_uses_transport_matrix_and_cost():
    o = opts(snap(on_hand={**{s: 0 for s in STATIONS}, "AUH": 2}))
    b = o["b"]
    assert b["feasible"] and b["wait_h"] == CFG["network"]["aog_transport_hours"]["AUH"]["BOM"]
    assert b["direct_cost"] == pytest.approx(NET.em_cost[("AUH", "BOM")])
    lo, hi = CFG["economics"]["emergency_logistics_aed"]
    assert lo <= b["direct_cost"] <= hi
    assert b["rank"] == 1 and "EXCEEDS_DEADLINE" in b["reason_codes"]


def test_hub_request_has_no_hub_transfer():
    o = opts(snap(station="AUH", on_hand={**{s: 0 for s in STATIONS}, "AUH": 0}))
    assert not o["b"]["feasible"] and o["b"]["reason_codes"] == ["NOT_APPLICABLE_AT_HUB"]


def test_lateral_respects_protection_level():
    oh = {**{s: 0 for s in STATIONS}, "JED": 1, "SIN": 2}
    # JED holds 1 but protects 1 for its own D0 demand; SIN holds 2 and protects 1 -> SIN donates
    o = opts(snap(on_hand=oh, protection={"JED": 1, "SIN": 1}))
    c = o["c"]
    assert c["feasible"] and c["source"] == "SIN"
    assert c["wait_h"] == NET.hours("SIN", "BOM")
    # if SIN also protects 2, nobody can give -> BELOW_PROTECTION_LEVEL
    o = opts(snap(on_hand=oh, protection={"JED": 1, "SIN": 2}))
    assert not o["c"]["feasible"] and o["c"]["reason_codes"] == ["BELOW_PROTECTION_LEVEL"]


def test_lateral_picks_nearest_donor():
    oh = {**{s: 0 for s in STATIONS}, "JED": 1, "SIN": 1}
    o = opts(snap(on_hand=oh))           # no protection -> both can give; SIN (14 h) is nearer BOM than JED (20 h)
    assert o["c"]["source"] == "SIN"


def test_pool_not_contracted_is_greyed_and_infeasible():
    o = opts(snap())
    d = o["d"]
    assert d["feasible"] is False and d["reason_codes"] == ["NOT_CONTRACTED"] and d["greyed"]
    assert d["rank"] is None
    o = opts(snap(part_class="C"))
    assert o["d"]["reason_codes"] == ["NOT_POOLED_PART_CLASS"]
    a2 = copy.deepcopy(ACFG)
    a2["pool_exchange"]["contracted"] = True
    o = opts(snap(), a2)
    assert o["d"]["feasible"] and o["d"]["wait_h"] == CFG["pool_exchange_P3"]["response_hours"]
    assert o["d"]["direct_cost"] == pytest.approx(CFG["pool_exchange_P3"]["fee_pct_of_unit"] * 100_000)


def test_accelerated_repair_rules_and_cost():
    o = opts(snap())
    assert o["e"]["reason_codes"] == ["NO_OPEN_RO"]
    assert opts(snap(part_class="E"))["e"]["reason_codes"] == ["NOT_REPAIRABLE"]
    # in-house RO due in 8 days, nothing else in the network: accelerate to 4 days (beats the 5-day expedite)
    ro = [{"ro_id": 7, "shop": "AUH_INHOUSE", "quoted_due_h": 1000 + 192, "serial": "X"}]
    o = opts(snap(open_ros=ro))
    e = o["e"]
    assert e["feasible"] and "ACCELERATION_OK" in e["reason_codes"]
    assert e["wait_h"] == pytest.approx(96 + NET.hours("AUH", "BOM"))
    rate = CFG["economics"]["repair_acceleration_cost_aed_per_day_per_unit"]
    assert e["direct_cost"] == pytest.approx(4 * rate + NET.em_cost[("AUH", "BOM")])
    assert e["rank"] == 1
    # AUH holds stock: a 9 h transfer beats acceleration -> infeasible
    o = opts(snap(open_ros=ro, on_hand={**{s: 0 for s in STATIONS}, "AUH": 1}))
    assert not o["e"]["feasible"] and "DOES_NOT_BEAT_ALTERNATIVES" in o["e"]["reason_codes"]


def test_robbery_never_ranked_or_recommended():
    donors = [{"tail": "A6-FHZ", "why": "grounded"}]
    o = opts(snap(donors=donors))
    g = o["g"]
    assert g["human_decision"] and not g["feasible"] and g["rank"] is None
    assert "HUMAN_DECISION_REQUIRED" in g["reason_codes"]
    panel = human_panel(snap(donors=donors), list(o.values()))
    assert panel["recommended"] != "g"
    assert "human decision" in panel["robbery_note"]
    assert any("Form 1" in c for c in human_panel(snap(on_hand={**{s: 0 for s in STATIONS}, "AUH": 1}),
                                                  evaluate_options(snap(on_hand={**{s: 0 for s in STATIONS}, "AUH": 1}),
                                                                   NET, CFG, ACFG))["checks"])


def test_exposure_arithmetic_on_every_option():
    assert exposure(30, 0, 15_000, 2_000) == 30 * 15_000 + 2_000
    assert exposure(30, 72, 15_000, 2_000) == 2_000
    assert exposure(100, 72, 30_000, 0) == 28 * 30_000
    ro = [{"ro_id": 7, "shop": "AUH_INHOUSE", "quoted_due_h": 1300, "serial": "X"}]
    pos = [{"po_id": 3, "qty": 1, "due_h": 1400, "reason": "reorder"}]
    for dc in ("D0", "D3", "D10"):
        s = snap(deadline_class=dc, open_ros=ro, open_pos=pos, on_hand={**{s_: 0 for s_ in STATIONS}, "SIN": 1})
        for o in evaluate_options(s, NET, CFG, ACFG):
            if o["wait_h"] is None:
                continue
            slack = {"D0": 0, "D3": 72, "D10": 240}[dc]
            assert o["exposure_aed"] == pytest.approx(max(0, o["wait_h"] - slack) * PEN_NB + o["direct_cost"])
            assert o["deadline_met"] == (o["wait_h"] <= slack)


def test_d3_within_slack_costs_only_direct_cost_and_ranks_cheapest():
    oh = {**{s: 0 for s in STATIONS}, "AUH": 1, "SIN": 1}
    o = opts(snap(deadline_class="D3", on_hand=oh))
    b, c = o["b"], o["c"]
    assert b["deadline_met"] and b["exposure_aed"] == b["direct_cost"]
    assert b["rank"] < c["rank"]          # AUH->BOM is cheaper than SIN->BOM


def test_d10_ships_routine_when_slack_allows():
    o = opts(snap(deadline_class="D10", on_hand={**{s: 0 for s in STATIONS}, "AUH": 1}))
    assert "ROUTINE_SHIPMENT" in o["b"]["reason_codes"]
    assert o["b"]["direct_cost"] == CFG["economics"]["routine_shipment_aed_per_line"]


def test_kit_commitments_block_deferrable_but_not_aog_needs():
    oh = {**{s: 0 for s in STATIONS}, "BOM": 1}
    o = opts(snap(deadline_class="D3", on_hand=oh, committed={"BOM": 1}))
    assert not o["a"]["feasible"] and o["a"]["reason_codes"] == ["COMMITTED_TO_KIT"]
    o = opts(snap(deadline_class="D0", on_hand=oh, committed={"BOM": 1}))
    assert o["a"]["feasible"]


def test_open_supply_queues_behind_earlier_backorders():
    pos = [{"po_id": 1, "qty": 1, "due_h": 1100, "reason": "reorder"},
           {"po_id": 2, "qty": 1, "due_h": 1500, "reason": "reorder"}]
    h0 = opts(snap(station="AUH", open_pos=pos))["h"]
    h1 = opts(snap(station="AUH", open_pos=pos, backorders_ahead=1))["h"]
    assert h0["wait_h"] == 100 and h1["wait_h"] == 500 and "QUEUED_BEHIND_BACKORDERS" in h1["reason_codes"]
    h2 = opts(snap(station="AUH", open_pos=pos, backorders_ahead=2))["h"]
    assert not h2["feasible"]


def test_poisson_protection_level():
    L = NET.routine_h
    assert poisson_protection(0.0, L, 0.95) == 0
    assert poisson_protection(2 / 8760, L, 0.95) == 1      # P(X=0) ~ 0.98
    assert poisson_protection(8 / 8760, L, 0.95) == 2      # P(X=0) ~ 0.92 < 0.95
