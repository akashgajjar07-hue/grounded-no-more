"""Sourcing-option engine evaluated at the moment of a material request.

Inputs are a :class:`Snapshot` holding only what the AOG desk knew at ``need_h``: serviceable
on-hand per station from transactions before the request, kit commitments already notified,
open repair orders with their *quoted* due dates, open purchase orders with their *quoted* due
dates, trailing D0 demand per station (for protection levels), and aircraft grounded or in check.
Actual receipt/return times are never read (tests/test_aog_options.py perturbs them).

Options
-------
a  Local serviceable stock
b  AUH emergency transfer (next-flight-out; routine shipment when the deadline allows)
c  Lateral transfer from another outstation, keeping its protection level
d  Pool exchange (P3 terms; NOT_CONTRACTED unless config/aog_lab.yaml says so)
e  Accelerated repair of the earliest unit at the shop
f  Expedited new purchase (AOG-desk market buy)
g  Robbery / cannibalisation from a grounded or in-check aircraft (human decision, never ranked)
h  Await supply already inbound (open PO / RO at its quoted due date, after earlier backorders)

exposure_aed = max(0, wait_h - deadline_slack_h) x AOG penalty per hour (archetype) + direct cost.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from gnm.config import load_config
from gnm.schemas import DEADLINE_HOURS

from .data import HistoryView, Network, load_aog_config, poisson_protection

OPTION_LABELS = {
    "a": "Local serviceable stock",
    "b": "Emergency transfer from AUH",
    "c": "Lateral transfer from another outstation",
    "d": "Pool exchange",
    "e": "Accelerated repair (earliest unit at shop)",
    "f": "Expedite new purchase",
    "g": "Robbery / cannibalisation",
    "h": "Await inbound supply (open order)",
}

REASON_CODES = {
    "LOCAL_STOCK": "Serviceable unit on the shelf at the requesting station",
    "NO_STOCK": "No serviceable unit at the source(s)",
    "COMMITTED_TO_KIT": "Units on hand are committed to notified scheduled-check kits (only AOG needs may break them)",
    "ROBS_KIT_RESERVATION": "Feasible only by breaking a scheduled-check kit reservation (allowed for an aircraft already AOG)",
    "NOT_APPLICABLE_AT_HUB": "The request is at AUH itself",
    "STOCK_AT_HUB": "Serviceable unit available at AUH",
    "NEXT_FLIGHT_OUT": "Ships next-flight-out / hand-carry",
    "ROUTINE_SHIPMENT": "Deadline slack covers routine transport; ships routine at line cost",
    "BELOW_PROTECTION_LEVEL": "Donor stations hold stock but only at or below their own D0 protection level",
    "LATERAL_OK": "Donor outstation keeps its protection level after shipping",
    "NOT_CONTRACTED": "No pool-exchange agreement in force (P0 history); P3 terms shown for reference",
    "NOT_POOLED_PART_CLASS": "Pool covers rotables only",
    "POOL_OK": "Pool exchange contracted",
    "NOT_REPAIRABLE": "Part class is not repaired (consumable/expendable)",
    "NO_OPEN_RO": "No unit of this PN at a repair shop",
    "RO_OVERDUE": "Earliest RO is already past its quoted due date; remaining time assumed",
    "NO_TIME_SAVED": "Acceleration cannot shorten the remaining shop time",
    "DOES_NOT_BEAT_ALTERNATIVES": "Accelerated return is not faster than another feasible option",
    "ACCELERATION_OK": "Paying the shop to prioritise beats the other feasible options",
    "EXPEDITE_MARKET_BUY": "AOG-desk purchase at expedite lead time and premium",
    "OPEN_PO_EXISTS": "An order for this PN is already open (see option h)",
    "NO_OPEN_SUPPLY": "No open PO or RO for this PN",
    "OPEN_PO_INBOUND": "Earliest usable inbound unit is an open purchase order",
    "INBOUND_TRANSFER": "A replenishment shipment to this station is already in transit (ETA from ship time + planned transit)",
    "RO_RETURN_INBOUND": "Earliest usable inbound unit is a repair return",
    "QUEUED_BEHIND_BACKORDERS": "Earlier unfilled requests claim the first inbound units",
    "SUPPLY_OVERDUE": "Inbound order is past its quoted due date; remaining time assumed",
    "EXCEEDS_DEADLINE": "Wait is longer than the deadline slack: the aircraft is AOG for the difference",
    "HUMAN_DECISION_REQUIRED": "Requires engineering/quality approval — human decision; never auto-recommended",
    "NO_DONOR_AIRCRAFT": "No aircraft grounded or in check at this station with this PN fitted",
}

HUMAN_CHECKS = {
    "common": [
        "Confirm the deadline class against the actual deferral decision (the simulation's D0/D3/D10 are hypothetical classes, not MEL categories).",
        "Confirm part applicability for the tail: part number interchangeability, effectivity and modification / service-bulletin status.",
    ],
    "transfer": [
        "Confirm the unit's release certificate (EASA Form 1 / FAA 8130-3 or equivalent) and traceability travel with it.",
        "Check shelf-life / storage limits and packaging for the move.",
        "Book next-flight-out or hand-carry and pre-clear customs at the receiving station.",
    ],
    "lateral": [
        "Agree with the donor station; raise its replenishment so its own D0 cover is restored.",
    ],
    "repair": [
        "Get the shop's committed release date in writing before approving the acceleration fee.",
        "Confirm the unit is released with a certificate of airworthiness for the repair performed.",
    ],
    "purchase": [
        "Verify the seller's traceability and release certificate (new or overhauled) before committing.",
        "Approve the expedite premium within delegated financial authority.",
    ],
    "supply": [
        "Confirm the open order's status with the supplier/shop and earmark the inbound unit for this aircraft.",
    ],
    "local": [
        "Confirm the shelf unit's certificate and condition before issue.",
    ],
    "robbery": [
        "Robbery is never automatic: it needs engineering and quality approval, and owner/lessor approval where the donor is leased.",
        "Both aircraft records must be updated; the donor aircraft now carries the shortage and needs its own sourcing plan.",
    ],
}
_CHECK_GROUP = {"a": "local", "b": "transfer", "c": "transfer", "d": "transfer", "e": "repair", "f": "purchase", "h": "supply"}


@dataclass
class Snapshot:
    """What the AOG desk knows at need_h (built from history, or by hand in tests)."""
    pn: str
    part_class: str
    unit_cost: float
    quoted_lead_d: float
    station: str
    need_h: int
    qty: int
    deadline_class: str
    archetype: str
    penalty_per_h: float
    on_hand: dict                 # station -> serviceable on-hand
    committed: dict = field(default_factory=dict)      # station -> notified kit qty not yet started
    protection: dict = field(default_factory=dict)     # station -> protection level for own D0 demand
    d0_counts: dict = field(default_factory=dict)      # station -> trailing D0 requests (evidence)
    open_ros: list = field(default_factory=list)       # [{ro_id, shop, quoted_due_h, serial}]
    open_pos: list = field(default_factory=list)       # [{po_id, qty, due_h, reason}]
    backorders_ahead: int = 0     # earlier unfilled requests for this PN (network), not yet covered by a shipment
    inbound_transfers: list = field(default_factory=list)   # [{transfer_id, from, qty, eta_h}] in transit to station
    station_backorders_ahead: int = 0   # of which at this station
    donors: list = field(default_factory=list)         # [{tail, why}]
    request_id: int | None = None
    tail: str | None = None

    @property
    def slack_h(self) -> int:
        return int(DEADLINE_HOURS[self.deadline_class])


def exposure(wait_h: float, slack_h: float, penalty_per_h: float, direct_cost: float) -> float:
    return max(0.0, float(wait_h) - float(slack_h)) * float(penalty_per_h) + float(direct_cost)


def _opt(key, feasible, codes, wait_h=None, cost=0.0, snap=None, **kw):
    o = {"key": key, "option": OPTION_LABELS[key], "feasible": bool(feasible), "reason_codes": list(codes),
         "wait_h": (None if wait_h is None else float(round(wait_h, 1))), "direct_cost": float(round(cost, 2)),
         "greyed": False, "human_decision": False, "rank": None}
    o.update(kw)
    if wait_h is not None and snap is not None:
        o["aog_h"] = float(round(max(0.0, wait_h - snap.slack_h), 1))
        o["exposure_aed"] = float(round(exposure(wait_h, snap.slack_h, snap.penalty_per_h, cost), 2))
        o["deadline_met"] = bool(wait_h <= snap.slack_h)
        if feasible and wait_h > snap.slack_h and "EXCEEDS_DEADLINE" not in o["reason_codes"]:
            o["reason_codes"].append("EXCEEDS_DEADLINE")
    else:
        o.update(aog_h=None, exposure_aed=None, deadline_met=False)
    return o


def _avail(snap: Snapshot, st: str) -> tuple[int, int]:
    """(available, on_hand). D0 needs may break kit reservations (engine SIM-6); D3/D10 may not."""
    oh = int(snap.on_hand.get(st, 0))
    com = 0 if snap.slack_h == 0 else int(snap.committed.get(st, 0))
    return oh - com, oh


def evaluate_options(snap: Snapshot, net: Network, cfg: dict | None = None, acfg: dict | None = None) -> list[dict]:
    cfg = cfg or load_config()
    acfg = acfg or load_aog_config()
    eco = cfg["economics"]
    hub, st, q = net.hub, snap.station, snap.qty
    opts = {}

    # (a) local
    av, oh = _avail(snap, st)
    if av >= q:
        opts["a"] = _opt("a", True, ["LOCAL_STOCK"], 0, 0.0, snap, source=st, evidence={"on_hand": oh})
    else:
        codes = ["COMMITTED_TO_KIT"] if oh >= q else ["NO_STOCK"]
        opts["a"] = _opt("a", False, codes, None, 0.0, snap, source=st,
                         evidence={"on_hand": oh, "kit_committed": int(snap.committed.get(st, 0))})

    # (b) AUH transfer
    def ship(src, elapsed_h=0.0):
        """Hub/outstation -> station leg: routine if the remaining slack covers routine transit."""
        if src == st:
            return 0.0, 0.0, "AT_STATION"
        if snap.slack_h - elapsed_h >= net.routine_ok_h:
            return net.routine_h, net.line_cost, "ROUTINE_SHIPMENT"
        return net.hours(src, st), net.em_cost[(src, st)], "NEXT_FLIGHT_OUT"

    if st == hub:
        opts["b"] = _opt("b", False, ["NOT_APPLICABLE_AT_HUB"], None, 0.0, snap, source=hub)
    else:
        oh_h = int(snap.on_hand.get(hub, 0))
        com_h = int(snap.committed.get(hub, 0))
        av_h = oh_h - (0 if snap.slack_h == 0 else com_h)
        ev = {"on_hand_auh": oh_h, "kit_committed_auh": com_h}
        if av_h >= q:
            w, c, mode = ship(hub)
            codes = ["STOCK_AT_HUB", mode]
            if snap.slack_h == 0 and oh_h - com_h < q:
                codes.append("ROBS_KIT_RESERVATION")
            opts["b"] = _opt("b", True, codes, w, c * (1 if mode == "NEXT_FLIGHT_OUT" else q), snap, source=hub,
                             mode=("routine" if mode == "ROUTINE_SHIPMENT" else "next_flight_out"), evidence=ev)
        else:
            opts["b"] = _opt("b", False, ["COMMITTED_TO_KIT" if oh_h >= q else "NO_STOCK"], None, 0.0, snap,
                             source=hub, evidence=ev)

    # (c) lateral from another outstation
    rows = []
    for k in net.stations:
        if k in (hub, st):
            continue
        oh_k = int(snap.on_hand.get(k, 0))
        com_k = int(snap.committed.get(k, 0))
        pl = int(snap.protection.get(k, 0))
        spare = oh_k - com_k - pl
        rows.append({"station": k, "on_hand": oh_k, "kit_committed": com_k, "protection_level": pl,
                     "d0_requests_lookback": int(snap.d0_counts.get(k, 0)), "spare": spare,
                     "hours": net.hours(k, st)})
    ok = sorted([r for r in rows if r["spare"] >= q], key=lambda r: (r["hours"], r["station"]))
    if ok:
        k = ok[0]["station"]
        opts["c"] = _opt("c", True, ["LATERAL_OK", "NEXT_FLIGHT_OUT"], net.hours(k, st), net.em_cost[(k, st)], snap,
                         source=k, evidence={"donors": rows})
    else:
        codes = ["BELOW_PROTECTION_LEVEL"] if any(r["on_hand"] - r["kit_committed"] >= q for r in rows) else ["NO_STOCK"]
        opts["c"] = _opt("c", False, codes, None, 0.0, snap, source=None, evidence={"donors": rows})

    # (d) pool exchange
    pcfg, pool = acfg["pool_exchange"], cfg["pool_exchange_P3"]
    pw = float(pool["response_hours"])
    pc = float(pool["fee_pct_of_unit"]) * snap.unit_cost * q
    if snap.part_class not in pcfg["scope_part_classes"]:
        opts["d"] = _opt("d", False, ["NOT_POOLED_PART_CLASS"], None, 0.0, snap, greyed=True)
    elif not pcfg["contracted"]:
        o = _opt("d", False, ["NOT_CONTRACTED"], pw, pc, snap, greyed=True,
                 evidence={"terms": "pool_exchange_P3", "response_hours": pw, "fee_pct_of_unit": pool["fee_pct_of_unit"],
                           "annual_access_fee_aed": pool["annual_access_fee_aed"]})
        o["indicative"] = True
        opts["d"] = o
    else:
        opts["d"] = _opt("d", True, ["POOL_OK"], pw, pc, snap)

    # (f) expedite purchase (needed before (e) is judged)
    ec = cfg["engine"]
    cap = (ec.get("expedite_max_days") or {}).get(snap.part_class)
    lead_d = snap.quoted_lead_d * float(ec["expedite_lead_time_factor"])
    if cap is not None:
        lead_d = min(lead_d, float(cap))
    sw, sc, _ = ship(hub, lead_d * 24)
    fw = lead_d * 24 + sw
    prem = float(eco["expedite_purchase_premium_pct"]) * snap.unit_cost * q
    fc = prem + sc
    fcodes = ["EXPEDITE_MARKET_BUY"] + (["OPEN_PO_EXISTS"] if snap.open_pos else [])
    opts["f"] = _opt("f", True, fcodes, fw, fc, snap, source="market",
                     evidence={"expedite_lead_d": round(lead_d, 2), "premium_aed": round(prem, 2),
                               "unit_price_aed_excluded": round(snap.unit_cost * q, 2)})

    # (h) await inbound supply, after earlier backorders
    racc = acfg["repair_acceleration"]
    over_h = float(racc["overdue_assumed_remaining_days"]) * 24
    cands = []   # (ready_h from need, cost, ref, kind, extra)
    trs = sorted(snap.inbound_transfers, key=lambda x: (x["eta_h"], x["transfer_id"]))
    for tr_ in trs[snap.station_backorders_ahead:]:
        for _ in range(int(tr_.get("qty", 1))):
            rem = max(1.0, float(tr_["eta_h"] - snap.need_h))
            cands.append((rem, 0.0, f"T{tr_['transfer_id']}", "T", {"eta_h": int(tr_["eta_h"]), "from": tr_["from"],
                                                                  "remaining_h": round(rem, 1), "leg_h": 0.0}))
    hubq = []
    for p in snap.open_pos:
        for _ in range(int(p.get("qty", 1))):
            hubq.append((int(p["due_h"]), "PO", p["po_id"]))
    for r in snap.open_ros:
        hubq.append((int(r["quoted_due_h"]), "RO", r["ro_id"]))
    hubq.sort(key=lambda x: (x[0], x[1], x[2]))
    for due, kind, ref in hubq[snap.backorders_ahead:]:
        rem, over = due - snap.need_h, False
        if rem <= 0:
            rem, over = over_h, True
        sw, sc, _ = ship(hub, rem)
        cands.append((rem + sw, sc, f"{kind}{ref}", kind, {"quoted_due_h": due, "remaining_h": round(rem, 1),
                                                         "leg_h": round(sw, 1), "overdue": over}))
    cands.sort(key=lambda x: (x[0], x[1], x[2]))
    n_in = len(trs) + len(hubq)
    if len(cands) >= q:
        w, c, ref, kind, extra = cands[q - 1]
        codes = [{"T": "INBOUND_TRANSFER", "PO": "OPEN_PO_INBOUND", "RO": "RO_RETURN_INBOUND"}[kind]]
        if (kind == "T" and snap.station_backorders_ahead) or (kind != "T" and snap.backorders_ahead):
            codes.append("QUEUED_BEHIND_BACKORDERS")
        if extra.pop("overdue", False):
            codes.append("SUPPLY_OVERDUE")
        opts["h"] = _opt("h", True, codes, w, c, snap, source=ref,
                         evidence={"inbound_ref": ref, **extra, "backorders_ahead": snap.backorders_ahead,
                                   "station_backorders_ahead": snap.station_backorders_ahead, "inbound_units": n_in})
    else:
        opts["h"] = _opt("h", False, ["NO_OPEN_SUPPLY" if not n_in else "QUEUED_BEHIND_BACKORDERS"], None, 0.0, snap,
                         evidence={"inbound_units": n_in, "backorders_ahead": snap.backorders_ahead})

    # (e) accelerated repair
    if snap.part_class != "R":
        opts["e"] = _opt("e", False, ["NOT_REPAIRABLE"], None, 0.0, snap)
    elif not snap.open_ros:
        opts["e"] = _opt("e", False, ["NO_OPEN_RO"], None, 0.0, snap)
    else:
        r = sorted(snap.open_ros, key=lambda x: (x["quoted_due_h"], x["ro_id"]))[0]
        codes = []
        rem = r["quoted_due_h"] - snap.need_h
        if rem <= 0:
            rem = over_h
            codes.append("RO_OVERDUE")
        floor = float(racc["min_remaining_days"]) * 24 + float(net.shop_transit_h.get(r.get("shop"), 0))
        acc = max(floor, rem * (1 - float(racc["max_cut_share"])))
        acc = min(acc, rem)
        saved_d = (rem - acc) / 24
        sw, sc, _ = ship(hub, acc)
        w = acc + sw
        c = saved_d * float(eco["repair_acceleration_cost_aed_per_day_per_unit"]) + sc
        others = [o["wait_h"] for k, o in opts.items() if o["feasible"] and k in "abcdfh" and o["wait_h"] is not None]
        best_other = min(others) if others else math.inf
        ev = {"ro_id": int(r["ro_id"]), "serial": r.get("serial"), "shop": r.get("shop"),
              "quoted_due_h": int(r["quoted_due_h"]), "remaining_h": round(rem, 1),
              "accelerated_remaining_h": round(acc, 1), "days_saved": round(saved_d, 2),
              "best_alternative_wait_h": (None if best_other == math.inf else best_other)}
        if saved_d <= 0:
            opts["e"] = _opt("e", False, codes + ["NO_TIME_SAVED"], w, c, snap, evidence=ev)
        elif w >= best_other:
            opts["e"] = _opt("e", False, codes + ["DOES_NOT_BEAT_ALTERNATIVES"], w, c, snap, evidence=ev)
        else:
            opts["e"] = _opt("e", True, codes + ["ACCELERATION_OK"], w, c, snap, evidence=ev)

    # (g) robbery — shown, never ranked
    rb = acfg["robbery"]
    if snap.donors:
        opts["g"] = _opt("g", False, ["HUMAN_DECISION_REQUIRED"], float(rb["work_hours"]), float(rb["labour_cost_aed"]),
                         snap, human_decision=True, evidence={"donors": snap.donors})
    else:
        opts["g"] = _opt("g", False, ["HUMAN_DECISION_REQUIRED", "NO_DONOR_AIRCRAFT"], None, 0.0, snap,
                         human_decision=True, evidence={"donors": []})
    # a robbery option's exposure/deadline fields are informational only
    out = [opts[k] for k in "abcdefgh"]
    rank_options(out)
    return out


def rank_options(options: list[dict]) -> list[dict]:
    """Rank feasible, non-human options by (exposure, wait, direct cost, key)."""
    fe = [o for o in options if o["feasible"] and not o["human_decision"]]
    fe.sort(key=lambda o: (o["exposure_aed"], o["wait_h"], o["direct_cost"], o["key"]))
    for o in options:
        o["rank"] = None
    for i, o in enumerate(fe, 1):
        o["rank"] = i
    return options


def best_option(options: list[dict]) -> dict | None:
    r = [o for o in options if o["rank"] == 1]
    return r[0] if r else None


def human_panel(snap: Snapshot, options: list[dict]) -> dict:
    best = best_option(options)
    ranked = sorted([o for o in options if o["rank"]], key=lambda o: o["rank"])
    rob = next(o for o in options if o["key"] == "g")
    if best is None:
        return {"recommended": None, "why": "No feasible sourcing option was found at request time.",
                "checks": HUMAN_CHECKS["common"], "robbery_note": "Robbery may be the only route — human decision."}
    why = (f"Lowest AOG exposure of {len(ranked)} feasible option(s): wait {best['wait_h']:.0f} h against a "
           f"{snap.slack_h} h deadline slack ({best['aog_h']:.0f} h AOG), direct cost AED {best['direct_cost']:,.0f}, "
           f"exposure AED {best['exposure_aed']:,.0f}.")
    if len(ranked) > 1:
        ru = ranked[1]
        why += (f" Runner-up: {ru['option']} (wait {ru['wait_h']:.0f} h, exposure AED {ru['exposure_aed']:,.0f}).")
    checks = HUMAN_CHECKS["common"] + HUMAN_CHECKS[_CHECK_GROUP[best["key"]]]
    if best["key"] == "c":
        checks = checks + HUMAN_CHECKS["lateral"]
    rob_note = ("Robbery from " + ", ".join(d["tail"] for d in rob["evidence"]["donors"]) +
                " is possible but requires engineering/quality approval — human decision.") if rob["evidence"]["donors"] \
        else "No donor aircraft grounded or in check at this station."
    return {"recommended": best["key"], "recommended_label": best["option"], "source": best.get("source"),
            "why": why, "checks": checks, "robbery_note": rob_note, "robbery_checks": HUMAN_CHECKS["robbery"]}


# ---------------------------------------------------------------------------------------------
def build_snapshot(view: HistoryView, req) -> Snapshot:
    """Snapshot for a material_requests row, using only information available at need_h."""
    rid, pn, st, t = int(req.request_id), str(req.pn), str(req.station), int(req.need_h)
    cutoff = view.request_cutoff(rid, t)
    part = view.parts.loc[pn]
    pl_cfg = view.acfg["protection_level"]
    on_hand = view.stock_at(pn, t, cutoff)
    committed = {s: view.kit_commitments(pn, s, t) for s in view.net.stations}
    prot, d0 = {}, {}
    for s in view.net.stations:
        n, rate = view.d0_demand_rate(pn, s, t, int(pl_cfg["lookback_weeks"]))
        d0[s] = n
        prot[s] = poisson_protection(rate, view.net.routine_h, float(pl_cfg["service_level"]))
    ros = [{"ro_id": int(r.ro_id), "shop": r.shop, "quoted_due_h": int(r.quoted_due_h), "serial": r.serial}
           for r in view.open_ros(pn, t).itertuples()]
    pos = [{"po_id": int(p.po_id), "qty": int(p.qty), "due_h": int(p.due_h), "reason": p.reason}
           for p in view.open_pos(pn, t).itertuples()]
    # earlier requests still unfilled at t: known to the desk as the backorder list
    mr = view.t["material_requests"]
    ahead = mr[(mr.pn == pn) & (mr.need_h < t) & (mr.request_id != rid)]
    ahead = ahead[ahead.filled_h.isna() | (ahead.filled_h > t)]
    # a request already covered by a shipment in transit does not claim inbound supply
    tr = view.t["transfers"]
    covered = set(tr[(tr.pn == pn) & (tr.ship_h <= t) & tr.request_id.notna()].request_id.astype(int))
    ahead = ahead[~ahead.request_id.astype(int).isin(covered)]
    intr = tr[(tr.pn == pn) & (tr.to_station == st) & (tr.ship_h < t) & (tr.arrive_h >= t) & tr.request_id.isna()]
    inbound = [{"transfer_id": int(x.transfer_id), "from": x.from_station, "qty": int(x.qty),
                "eta_h": int(x.ship_h + (view.net.routine_h if x.kind == "routine" else view.net.hours(x.from_station, st)))}
               for x in intr.itertuples()]
    tail = None if pd_isna(req["tail"]) else str(req["tail"])
    arch = view.arch.get(tail, "narrowbody")
    return Snapshot(pn=pn, part_class=str(part.part_class), unit_cost=float(part.unit_cost_aed),
                    quoted_lead_d=float(part.lead_time_mean_d), station=st, need_h=t, qty=int(req.qty),
                    deadline_class=str(req.deadline_class), archetype=arch, penalty_per_h=view.penalty(tail),
                    on_hand=on_hand, committed=committed, protection=prot, d0_counts=d0, open_ros=ros, open_pos=pos,
                    backorders_ahead=int(ahead.qty.sum()), inbound_transfers=inbound,
                    station_backorders_ahead=int(ahead[ahead.station == st].qty.sum()), donors=find_donors(view, pn, st, t, tail),
                    request_id=rid, tail=tail)


def pd_isna(x) -> bool:
    try:
        return x is None or bool(x != x) or str(x) in ("<NA>", "nan", "None")
    except (TypeError, ValueError):
        return False


def find_donors(view: HistoryView, pn: str, station: str, t: int, tail: str | None) -> list[dict]:
    """Aircraft at the station at t that are grounded (open AOG) or in a scheduled check and carry the PN."""
    app = view.t["part_applicability"]
    fits = set(app[(app.pn == pn) & (app.qty_per_aircraft > 0)].archetype)
    out = []
    ae = view.t["aog_events"]
    g = ae[(ae.station == station) & (ae.start_h <= t) & (ae.end_h > t) & (ae["tail"] != tail)]
    for r in g.itertuples():
        if view.arch.get(r.tail) in fits:
            out.append({"tail": r.tail, "why": f"grounded since h{int(r.start_h)} (AOG {int(r.aog_id)})"})
    ms = view.t["maintenance_schedule"]
    dt = int(view.cfg.get("generator", {}).get("a_check_downtime_h", 12))
    chk = ms[(ms.station == station) & (ms.due_h <= t) & (ms.due_h + dt > t) & (ms["tail"] != tail)].drop_duplicates("task_id")
    for r in chk.itertuples():
        if view.arch.get(r.tail) in fits and r.tail not in {d["tail"] for d in out}:
            out.append({"tail": r.tail, "why": f"in {r.check_type} since h{int(r.due_h)}"})
    return out


def snapshot_dict(snap: Snapshot) -> dict:
    return asdict(snap)
