"""Sourcing-option engine evaluated at the moment of a material request (v2).

A :class:`Snapshot` holds only what the AOG desk knew at ``need_h``: serviceable on-hand per station
from transactions before the request, notified kit commitments, open repair orders and purchase
orders at their *quoted* dates (and whether an RO had started work), transfers already in transit,
trailing D0 demand per station, and which same-type aircraft are already robbed. The per-request
random draws the engine uses for route availability and response are never read: probabilistic
routes are valued from their published odds (``assumptions.yaml: aog_sourcing``).

Options (mirroring the v2 engine's routes)
------------------------------------------
local              Local serviceable stock
hub_transfer       AUH transfer (next-flight-out; routine when the window allows, AV-07)
lateral            Lateral transfer from another outstation, keeping its protection level
local_borrow       Outstation third-party loan / inter-airline borrow (rotables, odds by station x type)
robbery            Robbery from a same-type aircraft at AUH — engineering/quality approval, human decision
exchange_loan      AOG exchange / loan (rotables, odds and response by type, fee + daily fee, no pool growth)
local_buy          Local AOG buy / borrow (consumables and expendables)
inbound            Await supply already in the pipeline (transfer in transit, open PO, RO return)
repair_queue_jump  Pay the shop to jump its queue (AV-21: queue wait removed, work time kept) — estimate
pool               Pool exchange — NOT_CONTRACTED (greyed)

Material shortage exposure (consistent with the v2 engine accounting, AV-10):
    late      = wait_h > window_h
    aog_h     = wait_h + fitting_h - window_h   if late else 0
    exposure  = aog_h x rate/h (archetype) + fixed cost per event (archetype, if late) + direct cost
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import pandas as pd

from gnm.config import load_config

from .data import HistoryView, Network, deadline_hours, fitting_mid_h, load_aog_config, poisson_protection

KEYS = ("local", "hub_transfer", "lateral", "local_borrow", "robbery", "exchange_loan", "local_buy", "inbound",
        "repair_queue_jump", "pool")
OPTION_LABELS = {
    "local": "Local serviceable stock",
    "hub_transfer": "Transfer from AUH",
    "lateral": "Lateral transfer from another outstation",
    "local_borrow": "Local borrow / third-party loan at the outstation",
    "robbery": "Robbery from an aircraft at AUH (human decision)",
    "exchange_loan": "AOG exchange / loan",
    "local_buy": "Local AOG buy / borrow",
    "inbound": "Await supply already inbound",
    "repair_queue_jump": "Repair queue-jump with AOG surcharge (estimate)",
    "pool": "Pool exchange",
}

REASON_CODES = {
    "LOCAL_STOCK": "Serviceable unit on the shelf at the requesting station",
    "NO_STOCK": "No serviceable unit at the source(s)",
    "COMMITTED_TO_KIT": "Units on hand are reserved for notified scheduled needs (only D0 needs may break them)",
    "ROBS_KIT_RESERVATION": "Feasible only by breaking a scheduled-need reservation (allowed for a D0 need)",
    "NOT_APPLICABLE_AT_HUB": "The request is at AUH itself",
    "STOCK_AT_HUB": "Serviceable unit available at AUH",
    "NEXT_FLIGHT_OUT": "Ships next-flight-out / hand-carry",
    "ROUTINE_SHIPMENT": "Window covers routine transit + margin; ships routine at line cost",
    "BELOW_PROTECTION_LEVEL": "Donor stations hold stock only at or below their own D0 protection level",
    "LATERAL_OK": "Donor outstation keeps its protection level after shipping",
    "ROTABLES_ONLY": "Route applies to rotables only",
    "CONSUMABLES_EXPENDABLES_ONLY": "Route applies to consumables and expendables only",
    "OUTSTATION_ONLY": "Local borrow exists only at outstations",
    "HUB_ONLY": "Robbery is modelled at AUH only (hangar aircraft in check / parked)",
    "NO_LOCAL_MARKET": "No local borrow source at this station for this fleet type",
    "AVAILABILITY_UNCERTAIN": "Route available only with probability p; failed attempts are retried",
    "NO_DONOR_AIRCRAFT": "No same-type aircraft with the PN fitted that is not already a donor",
    "HUMAN_DECISION_REQUIRED": "Engineering/quality approval required — human decision; never auto-recommended",
    "LOAN_FEE_ACCRUES": "Daily fee accrues until the own unit replaces the borrowed unit (estimated)",
    "NOT_CONTRACTED": "No pool-exchange agreement in force (P0); P3 terms shown for reference",
    "NOT_POOLED_PART_CLASS": "Pool covers rotables only",
    "POOL_OK": "Pool exchange contracted",
    "NO_OPEN_RO": "No unit of this PN at a repair shop",
    "NO_QUEUE_TO_JUMP": "Every unit at the shop has already started work: priority cannot shorten work content",
    "DOES_NOT_BEAT_ALTERNATIVES": "Queue-jump return is not faster than another feasible option",
    "QUEUE_JUMP_OK": "Queue-jump return beats the other feasible options",
    "ESTIMATE": "Estimate: quoted TAT and a flat surcharge, not a shop quote",
    "NO_OPEN_SUPPLY": "Nothing inbound for this PN",
    "OPEN_PO_INBOUND": "Earliest usable inbound unit is an open purchase order",
    "INBOUND_TRANSFER": "A shipment to this station is already in transit (ETA = ship time + planned transit)",
    "RO_RETURN_INBOUND": "Earliest usable inbound unit is a repair return",
    "QUEUED_BEHIND_BACKORDERS": "Earlier unfilled requests claim the first inbound units",
    "SUPPLY_OVERDUE": "Inbound order is past its quoted date; remaining time assumed",
    "EXCEEDS_DEADLINE": "Wait exceeds the rectification window: material-related downtime for the difference plus fitting",
}

HUMAN_CHECKS = {
    "common": [
        "Confirm the rectification window against the actual deferral decision (D0/D3/D10 are hypothetical simulation classes, not operator MEL decisions).",
        "Confirm part applicability for the tail: interchangeability, effectivity and modification / service-bulletin status.",
    ],
    "transfer": [
        "Confirm the unit's release certificate (EASA Form 1 / FAA 8130-3 or equivalent) and traceability travel with it.",
        "Book next-flight-out or hand-carry and pre-clear customs at the receiving station.",
    ],
    "lateral": ["Agree with the donor station and raise its replenishment so its own D0 cover is restored."],
    "loan": [
        "Check the lender's release certificate, back-to-birth traceability where required, and mod status.",
        "Agree the commercial terms: exchange/loan fee, daily fee, core-return condition and return date.",
        "Plan the hand-back: the own unit replaces the borrowed unit when it becomes serviceable.",
    ],
    "buy": ["Buy only from an approved source with a release certificate; record the AOG premium."],
    "supply": ["Confirm the inbound unit's status with the supplier/shop/stores and earmark it for this aircraft."],
    "repair": ["Get the shop's written priority and release date before approving the surcharge (estimate only)."],
    "local": ["Confirm the shelf unit's certificate and condition before issue."],
    "robbery": [
        "Robbery needs engineering and quality approval (and owner/lessor approval where the donor is leased).",
        "Both aircraft records must be updated; the donor carries the shortage until it is reinstated from the next AUH unit.",
    ],
}
_CHECK_GROUP = {"local": "local", "hub_transfer": "transfer", "lateral": "transfer", "local_borrow": "loan",
                "exchange_loan": "loan", "local_buy": "buy", "inbound": "supply", "repair_queue_jump": "repair",
                "pool": "loan", "robbery": "robbery"}


@dataclass
class Snapshot:
    """What the AOG desk knows at need_h (built from history, or by hand in tests)."""
    pn: str
    part_class: str
    unit_cost: float
    station: str
    need_h: int
    qty: int
    deadline_class: str
    archetype: str
    on_hand: dict                                      # station -> serviceable on-hand
    repair_cost: float = 0.0
    quoted_tat_d: float = 0.0
    repair_shop: str | None = None
    committed: dict = field(default_factory=dict)      # station -> reserved for notified scheduled needs
    protection: dict = field(default_factory=dict)     # station -> protection level for own D0 demand
    d0_counts: dict = field(default_factory=dict)
    open_ros: list = field(default_factory=list)       # [{ro_id, shop, quoted_due_h, serial, started}]
    open_pos: list = field(default_factory=list)       # [{po_id, qty, due_h, reason}]
    inbound_transfers: list = field(default_factory=list)   # [{transfer_id, from, qty, eta_h}]
    backorders_ahead: int = 0
    station_backorders_ahead: int = 0
    donor_candidates: int = 0                          # same-type tails with the PN fitted, not already donors
    request_id: int | None = None
    tail: str | None = None

    @property
    def window_h(self):
        return deadline_hours(self.deadline_class)


def exposure(wait_h, window_h, fit_h, rate_h, event_cost, direct_cost) -> tuple[float, float]:
    """(aog_h, exposure_aed). Material counts as late only if it arrives after the window (AV-10)."""
    late = float(wait_h) > float(window_h)
    aog = (float(wait_h) + float(fit_h) - float(window_h)) if late else 0.0
    return aog, aog * float(rate_h) + (float(event_cost) if late else 0.0) + float(direct_cost)


class _Ctx:
    def __init__(self, snap, net, cfg, acfg):
        self.s, self.net, self.cfg, self.acfg = snap, net, cfg, acfg
        eco = cfg["economics"]
        self.rate = float(eco["aog_penalty_aed_per_hour"][snap.archetype])
        self.ev = float(eco["aog_event_cost_aed"][snap.archetype])
        self.fit = fitting_mid_h(cfg, snap.part_class)
        self.win = snap.window_h if snap.window_h is not None else math.inf

    def opt(self, key, feasible, codes, wait_h=None, cost=0.0, **kw):
        o = {"key": key, "option": OPTION_LABELS[key], "feasible": bool(feasible), "reason_codes": list(codes),
             "wait_h": None if wait_h is None else float(round(wait_h, 1)), "direct_cost": float(round(cost, 2)),
             "greyed": False, "human_decision": False, "estimate": False, "rank": None,
             "availability_p": 1.0, "fitting_h": self.fit}
        o.update(kw)
        if wait_h is not None:
            aog, ex = exposure(wait_h, self.win, self.fit, self.rate, self.ev, cost)
            o.update(aog_h=float(round(aog, 1)), exposure_aed=float(round(ex, 2)), deadline_met=bool(aog == 0))
            if feasible and aog > 0 and "EXCEEDS_DEADLINE" not in o["reason_codes"]:
                o["reason_codes"].append("EXCEEDS_DEADLINE")
        else:
            o.update(aog_h=None, exposure_aed=None, deadline_met=False)
        return o

    def leg(self, src, elapsed=0.0):
        """src -> station: routine if the remaining window covers planned routine transit + margin (AV-07)."""
        st = self.s.station
        if src == st:
            return 0.0, 0.0, "AT_STATION"
        if self.win - elapsed >= self.net.routine_ok_h:
            return self.net.routine_h, self.net.line_cost, "ROUTINE_SHIPMENT"
        return float(self.net.hours(src, st)), self.net.em_cost[(src, st)], "NEXT_FLIGHT_OUT"


def _sequence(routes, retry_h):
    """Expected (wait, cost, cycle success prob, share won by the first route) when the desk tries
    `routes` [(p, mid_wait, cost), ...] in order in one attempt and retries the cycle every retry_h."""
    fail, ew, ec, wins = 1.0, 0.0, 0.0, []
    for p, mid, cost in routes:
        w = fail * p
        ew += w * mid
        ec += w * cost
        wins.append(w)
        fail *= (1.0 - p)
    s = 1.0 - fail
    if s <= 0:
        return None, None, 0.0, 0.0
    return ew / s + (retry_h or 0.0) * fail / s, ec / s, s, wins[0] / s


def _expected_wait(p, lo, hi, retry_h):
    mid = (lo + hi) / 2.0
    if p <= 0:
        return None
    return mid + (retry_h or 0.0) * (1.0 - p) / p


def evaluate_options(snap: Snapshot, net: Network, cfg: dict | None = None, acfg: dict | None = None) -> list[dict]:
    cfg = cfg or load_config()
    acfg = acfg or load_aog_config()
    c = _Ctx(snap, net, cfg, acfg)
    ags = cfg["aog_sourcing"]
    hub, st, q, cls = net.hub, snap.station, snap.qty, snap.part_class
    rot = cls == "R"
    retry = float((ags.get("retry_hours") or {}).get(cls) or 0.0)
    opts = {}

    def avail(station):
        oh = int(snap.on_hand.get(station, 0))
        com = 0 if snap.window_h == 0 else int(snap.committed.get(station, 0))
        return oh - com, oh

    # local
    av, oh = avail(st)
    if av >= q:
        opts["local"] = c.opt("local", True, ["LOCAL_STOCK"], 0.0, 0.0, source=st, evidence={"on_hand": oh})
    else:
        opts["local"] = c.opt("local", False, ["COMMITTED_TO_KIT" if oh >= q else "NO_STOCK"], source=st,
                              evidence={"on_hand": oh, "reserved": int(snap.committed.get(st, 0))})

    # AUH transfer
    if st == hub:
        opts["hub_transfer"] = c.opt("hub_transfer", False, ["NOT_APPLICABLE_AT_HUB"], source=hub)
    else:
        av_h, oh_h = avail(hub)
        ev = {"on_hand_auh": oh_h, "reserved_auh": int(snap.committed.get(hub, 0))}
        if av_h >= q:
            w, cost, mode = c.leg(hub)
            codes = ["STOCK_AT_HUB", mode]
            if snap.window_h == 0 and oh_h - int(snap.committed.get(hub, 0)) < q:
                codes.append("ROBS_KIT_RESERVATION")
            opts["hub_transfer"] = c.opt("hub_transfer", True, codes, w, cost, source=hub,
                                         mode="routine" if mode == "ROUTINE_SHIPMENT" else "next_flight_out", evidence=ev)
        else:
            opts["hub_transfer"] = c.opt("hub_transfer", False, ["COMMITTED_TO_KIT" if oh_h >= q else "NO_STOCK"],
                                         source=hub, evidence=ev)

    # lateral
    rows = []
    for k in net.stations:
        if k in (hub, st):
            continue
        oh_k = int(snap.on_hand.get(k, 0))
        com_k = int(snap.committed.get(k, 0))
        pl = int(snap.protection.get(k, 0))
        rows.append({"station": k, "on_hand": oh_k, "reserved": com_k, "protection_level": pl,
                     "d0_requests_lookback": int(snap.d0_counts.get(k, 0)), "spare": oh_k - com_k - pl,
                     "hours": net.hours(k, st)})
    ok = sorted([r for r in rows if r["spare"] >= q], key=lambda r: (r["hours"], r["station"]))
    if ok:
        k = ok[0]["station"]
        opts["lateral"] = c.opt("lateral", True, ["LATERAL_OK", "NEXT_FLIGHT_OUT"], net.hours(k, st), net.em_cost[(k, st)],
                                source=k, evidence={"donors": rows})
    else:
        codes = ["BELOW_PROTECTION_LEVEL"] if any(r["on_hand"] - r["reserved"] >= q for r in rows) else ["NO_STOCK"]
        opts["lateral"] = c.opt("lateral", False, codes, evidence={"donors": rows})

    # inbound supply (needed for loan-duration estimates)
    over_h = 7 * 24.0
    cands = []
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
        sw, sc, _ = c.leg(hub, rem)
        cands.append((rem + sw, sc, f"{kind}{ref}", kind, {"quoted_due_h": due, "remaining_h": round(rem, 1),
                                                         "leg_h": round(sw, 1), "overdue": over}))
    cands.sort(key=lambda x: (x[0], x[1], x[2]))
    n_in = len(trs) + len(hubq)
    if len(cands) >= q:
        w, cost, ref, kind, extra = cands[q - 1]
        codes = [{"T": "INBOUND_TRANSFER", "PO": "OPEN_PO_INBOUND", "RO": "RO_RETURN_INBOUND"}[kind]]
        if (kind == "T" and snap.station_backorders_ahead) or (kind != "T" and snap.backorders_ahead):
            codes.append("QUEUED_BEHIND_BACKORDERS")
        if extra.pop("overdue", False):
            codes.append("SUPPLY_OVERDUE")
        opts["inbound"] = c.opt("inbound", True, codes, w, cost, source=ref,
                                evidence={"inbound_ref": ref, **extra, "backorders_ahead": snap.backorders_ahead,
                                          "station_backorders_ahead": snap.station_backorders_ahead, "inbound_units": n_in})
        own_unit_h = w
    else:
        opts["inbound"] = c.opt("inbound", False, ["NO_OPEN_SUPPLY" if not n_in else "QUEUED_BEHIND_BACKORDERS"],
                                evidence={"inbound_units": n_in, "backorders_ahead": snap.backorders_ahead})
        sw, _, _ = c.leg(hub, 1e9)
        transit = float(net.shop_transit_h.get(snap.repair_shop, 0.0)) if snap.repair_shop else 0.0
        own_unit_h = snap.quoted_tat_d * 24 + transit + (0 if st == hub else net.hours(hub, st))

    def loan_cost(fixed, daily_pct, wait):
        days = max(0.0, own_unit_h - wait) / 24.0
        return fixed + daily_pct * snap.unit_cost * days * q, round(days, 1)

    # exchange / loan (rotables): the desk's fall-back market route at every station
    ex = ags["exchange_loan"]
    ex_route = None
    if not rot:
        opts["exchange_loan"] = c.opt("exchange_loan", False, ["ROTABLES_ONLY"])
    else:
        p_ex = float(ex["availability"][snap.archetype])
        lo, hi = ex["response_hours"][snap.archetype]
        w = _expected_wait(p_ex, lo, hi, retry)
        cost, days = loan_cost(float(ex["fee_pct_of_list"][snap.archetype]) * snap.unit_cost * q,
                               float(ex["loan_fee_pct_of_list_per_day"]), w)
        ex_route = (p_ex, (lo + hi) / 2.0, cost)
        opts["exchange_loan"] = c.opt("exchange_loan", True, ["AVAILABILITY_UNCERTAIN", "LOAN_FEE_ACCRUES"], w, cost,
                                      availability_p=p_ex, response_h=[lo, hi], source="AOG exchange/loan market",
                                      evidence={"wait_if_available_h": (lo + hi) / 2, "retry_h": retry,
                                                "fee_pct_of_list": ex["fee_pct_of_list"][snap.archetype],
                                                "est_loan_days": days, "pool_growth": False})

    # local borrow (rotables, outstations), with exchange/loan as the same-attempt fall-back (engine order)
    lb = ags["local_borrow"]
    if not rot:
        opts["local_borrow"] = c.opt("local_borrow", False, ["ROTABLES_ONLY"])
    elif st == hub:
        opts["local_borrow"] = c.opt("local_borrow", False, ["OUTSTATION_ONLY"])
    else:
        p = float(lb["availability"][snap.archetype].get(st, 0.0))
        lo, hi = lb["response_hours"]
        if p <= 0:
            opts["local_borrow"] = c.opt("local_borrow", False, ["NO_LOCAL_MARKET"], availability_p=0.0)
        else:
            mid = (lo + hi) / 2.0
            bcost, days = loan_cost(float(lb["fee_aed_fixed"]) * q, float(lb["loan_fee_pct_of_list_per_day"]), mid)
            w, cost, s_, share = _sequence([(p, mid, bcost), ex_route], retry)
            opts["local_borrow"] = c.opt("local_borrow", True, ["AVAILABILITY_UNCERTAIN", "LOAN_FEE_ACCRUES"], w, cost,
                                         availability_p=p, response_h=[lo, hi], source=f"local market {st}",
                                         fallback="exchange_loan",
                                         evidence={"wait_if_available_h": mid, "retry_h": retry, "est_loan_days": days,
                                                   "cycle_success_p": round(s_, 3), "share_won_by_borrow": round(share, 3),
                                                   "borrow_cost_aed": round(bcost, 2)})

    # robbery (AUH only; human decision), with exchange/loan as the same-attempt fall-back (engine order)
    rb = ags["robbery"]
    if not rot:
        opts["robbery"] = c.opt("robbery", False, ["ROTABLES_ONLY", "HUMAN_DECISION_REQUIRED"], human_decision=True)
    elif st != hub or not rb.get("enabled", True):
        opts["robbery"] = c.opt("robbery", False, ["HUB_ONLY", "HUMAN_DECISION_REQUIRED"], human_decision=True)
    elif snap.donor_candidates <= 0:
        opts["robbery"] = c.opt("robbery", False, ["NO_DONOR_AIRCRAFT", "HUMAN_DECISION_REQUIRED"], human_decision=True)
    else:
        p = float(rb["availability"])
        lo, hi = rb["response_hours"]
        mid = (lo + hi) / 2.0
        labour = float(cfg["economics"]["fitting_labour_aed_per_hour"]) * c.fit * float(rb["labour_multiplier"]) * q
        w, cost, s_, share = _sequence([(p, mid, labour), ex_route], retry)
        opts["robbery"] = c.opt("robbery", False, ["HUMAN_DECISION_REQUIRED", "AVAILABILITY_UNCERTAIN"], w, cost,
                                human_decision=True, availability_p=p, response_h=[lo, hi], flag=rb["flag"],
                                fallback="exchange_loan",
                                evidence={"donor_candidates": snap.donor_candidates, "wait_if_available_h": mid,
                                          "labour_aed": round(labour, 2), "cycle_success_p": round(s_, 3),
                                          "share_won_by_robbery": round(share, 3), "assumption": rb.get("assumption")})

    # local buy (C/E)
    bu = ags["local_buy"]
    if rot:
        opts["local_buy"] = c.opt("local_buy", False, ["CONSUMABLES_EXPENDABLES_ONLY"])
    else:
        p = float(bu["availability"])
        lo, hi = bu["response_hours"]
        w = _expected_wait(p, lo, hi, retry)
        prem = float(bu["premium_pct"]) * snap.unit_cost * q
        opts["local_buy"] = c.opt("local_buy", True, ["AVAILABILITY_UNCERTAIN"], w, prem, availability_p=p,
                                  response_h=[lo, hi], source=f"local supplier {st}",
                                  evidence={"premium_aed": round(prem, 2), "unit_price_aed_excluded": round(snap.unit_cost * q, 2),
                                            "wait_if_available_h": (lo + hi) / 2, "retry_h": retry})

    # repair queue-jump (AV-21)
    qj = acfg["repair_queue_jump"]
    if not rot:
        opts["repair_queue_jump"] = c.opt("repair_queue_jump", False, ["ROTABLES_ONLY"], estimate=True)
    elif not snap.open_ros:
        opts["repair_queue_jump"] = c.opt("repair_queue_jump", False, ["NO_OPEN_RO"], estimate=True)
    else:
        queued = [r for r in snap.open_ros if not r.get("started")]
        if not queued:
            opts["repair_queue_jump"] = c.opt("repair_queue_jump", False, ["NO_QUEUE_TO_JUMP", "ESTIMATE"], estimate=True,
                                              evidence={"open_ros": len(snap.open_ros)})
        else:
            r = sorted(queued, key=lambda x: (x["quoted_due_h"], x["ro_id"]))[0]
            back = snap.quoted_tat_d * 24 + float(net.shop_transit_h.get(r.get("shop"), 0.0))
            sw, sc, _ = c.leg(hub, back)
            w = back + sw
            cost = float(qj["surcharge_pct_of_repair_cost"]) * snap.repair_cost + sc
            others = [o["wait_h"] for k, o in opts.items() if o["feasible"] and not o["human_decision"] and o["wait_h"] is not None]
            best_other = min(others) if others else math.inf
            ev = {"ro_id": int(r["ro_id"]), "serial": r.get("serial"), "shop": r.get("shop"),
                  "quoted_due_h": int(r["quoted_due_h"]), "estimated_return_h": round(back, 1),
                  "surcharge_pct": qj["surcharge_pct_of_repair_cost"],
                  "best_alternative_wait_h": None if best_other == math.inf else best_other}
            if w < best_other:
                opts["repair_queue_jump"] = c.opt("repair_queue_jump", True, ["QUEUE_JUMP_OK", "ESTIMATE"], w, cost,
                                                  estimate=True, source=f"RO{r['ro_id']}", evidence=ev)
            else:
                opts["repair_queue_jump"] = c.opt("repair_queue_jump", False, ["DOES_NOT_BEAT_ALTERNATIVES", "ESTIMATE"],
                                                  w, cost, estimate=True, evidence=ev)

    # pool (not contracted)
    pcfg, pool = acfg["pool_exchange"], cfg["pool_exchange_P3"]
    pw = float(pool["response_hours"])
    pc = float(pool["fee_pct_of_unit"]) * snap.unit_cost * q
    if cls not in pcfg["scope_part_classes"]:
        opts["pool"] = c.opt("pool", False, ["NOT_POOLED_PART_CLASS"], greyed=True)
    elif not pcfg["contracted"]:
        opts["pool"] = c.opt("pool", False, ["NOT_CONTRACTED"], pw, pc, greyed=True, indicative=True,
                             evidence={"terms": "pool_exchange_P3", "response_hours": pw,
                                       "fee_pct_of_unit": pool["fee_pct_of_unit"]})
    else:
        opts["pool"] = c.opt("pool", True, ["POOL_OK"], pw, pc)

    out = [opts[k] for k in KEYS]
    rank_options(out)
    return out


def rank_options(options: list[dict]) -> list[dict]:
    """Rank feasible, non-human options by (exposure, wait, direct cost, key order)."""
    fe = [o for o in options if o["feasible"] and not o["human_decision"]]
    fe.sort(key=lambda o: (o["exposure_aed"], o["wait_h"], o["direct_cost"], KEYS.index(o["key"])))
    for o in options:
        o["rank"] = None
    for i, o in enumerate(fe, 1):
        o["rank"] = i
    return options


def best_option(options: list[dict]) -> dict | None:
    return next((o for o in options if o["rank"] == 1), None)


def human_panel(snap: Snapshot, options: list[dict]) -> dict:
    best = best_option(options)
    ranked = sorted([o for o in options if o["rank"]], key=lambda o: o["rank"])
    rob = next(o for o in options if o["key"] == "robbery")
    rob_note = None
    if rob["wait_h"] is not None:
        rob_note = (f"Robbery from a same-type aircraft at AUH: p = {rob['availability_p']:.2f}, expected wait "
                    f"{rob['wait_h']:.0f} h, exposure AED {rob['exposure_aed']:,.0f} — engineering/quality approval "
                    f"required, human decision; not auto-recommended.")
    if best is None:
        return {"recommended": None, "why": "No feasible sourcing option at request time.",
                "checks": HUMAN_CHECKS["common"], "robbery_note": rob_note, "robbery_checks": HUMAN_CHECKS["robbery"]}
    win = snap.window_h
    p_txt = "" if best["availability_p"] >= 1 else f" (first-attempt odds {best['availability_p']:.0%}, expected wait incl. retries)"
    why = (f"Lowest material shortage exposure of {len(ranked)} feasible option(s): wait {best['wait_h']:.0f} h{p_txt} "
           f"against a {win} h window, expected material-related downtime {best['aog_h']:.0f} h, direct cost "
           f"AED {best['direct_cost']:,.0f}, exposure AED {best['exposure_aed']:,.0f}.")
    if len(ranked) > 1:
        ru = ranked[1]
        why += f" Runner-up: {ru['option']} (wait {ru['wait_h']:.0f} h, exposure AED {ru['exposure_aed']:,.0f})."
    checks = HUMAN_CHECKS["common"] + HUMAN_CHECKS[_CHECK_GROUP[best["key"]]]
    if best["key"] == "lateral":
        checks = checks + HUMAN_CHECKS["lateral"]
    return {"recommended": best["key"], "recommended_label": best["option"], "source": best.get("source"),
            "estimate": best["estimate"], "why": why, "checks": checks, "robbery_note": rob_note,
            "robbery_checks": HUMAN_CHECKS["robbery"]}


# ---------------------------------------------------------------------------------------------
def _isna(x) -> bool:
    try:
        return x is None or bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def build_snapshot(view: HistoryView, req) -> Snapshot:
    """Snapshot for a material_requests row, using only information available at need_h."""
    rid, pn, st, t = int(req.request_id), str(req.pn), str(req.station), int(req.need_h)
    cutoff = view.request_cutoff(rid, t)
    part = view.parts.loc[pn]
    pl_cfg = view.acfg["protection_level"]
    prot, d0 = {}, {}
    for s in view.net.stations:
        n, rate = view.d0_demand_rate(pn, s, t, int(pl_cfg["lookback_weeks"]))
        d0[s] = n
        prot[s] = poisson_protection(rate, view.net.routine_h, float(pl_cfg["service_level"]))
    ros = [{"ro_id": int(r.ro_id), "shop": r.shop, "quoted_due_h": int(r.quoted_due_h), "serial": r.serial,
            "started": bool(not _isna(r.start_h) and int(r.start_h) <= t)}
           for r in view.open_ros(pn, t).itertuples()]
    pos = [{"po_id": int(p.po_id), "qty": int(p.qty), "due_h": int(p.due_h), "reason": p.reason}
           for p in view.open_pos(pn, t).itertuples()]
    mr = view.t["material_requests"]
    ahead = mr[(mr.pn == pn) & (mr.need_h < t) & (mr.request_id != rid)]
    ahead = ahead[ahead.filled_h.isna() | (ahead.filled_h > t)]
    tr = view.t["transfers"]
    covered = set(tr[(tr.pn == pn) & (tr.ship_h <= t) & tr.request_id.notna()].request_id.astype(int))
    if "aog_route_h" in ahead:      # needs already on an AOG route (borrow/exchange/robbery) do not claim inbound
        on_route = ahead.aog_route_result.isin(["robbery", "exchange_loan", "local_borrow", "local_buy", "planned_loan"]) \
            & ahead.aog_route_h.notna() & (ahead.aog_route_h <= t)
        ahead = ahead[~on_route]
    ahead = ahead[~ahead.request_id.astype(int).isin(covered)]
    intr = tr[(tr.pn == pn) & (tr.to_station == st) & (tr.ship_h < t) & (tr.arrive_h >= t) & tr.request_id.isna()
              & (tr.kind != "loan_return")]
    inbound = [{"transfer_id": int(x.transfer_id), "from": x.from_station, "qty": int(x.qty),
                "eta_h": int(x.ship_h + (view.net.routine_h if x.kind == "routine" else view.net.hours(x.from_station, st)))}
               for x in intr.itertuples()]
    tail = None if _isna(req["tail"]) else str(req["tail"])
    arch = view.arch.get(tail, "narrowbody")
    app = view.t["part_applicability"]
    fits = set(app[(app.pn == pn) & (app.qty_per_aircraft > 0)].archetype)
    busy = view.busy_donors(pn, t)
    donors = [x for x, a in view.arch.items() if a == arch and a in fits and x != tail and x not in busy]
    return Snapshot(pn=pn, part_class=str(part.part_class), unit_cost=float(part.unit_cost_aed), station=st, need_h=t,
                    qty=int(req.qty), deadline_class=str(req.deadline_class), archetype=arch,
                    on_hand=view.stock_at(pn, t, cutoff),
                    repair_cost=0.0 if _isna(part.repair_cost_aed) else float(part.repair_cost_aed),
                    quoted_tat_d=0.0 if _isna(part.repair_tat_mean_d) else float(part.repair_tat_mean_d),
                    repair_shop=None if _isna(part.repair_shop) else str(part.repair_shop),
                    committed={s: view.kit_commitments(pn, s, t) for s in view.net.stations},
                    protection=prot, d0_counts=d0, open_ros=ros, open_pos=pos, inbound_transfers=inbound,
                    backorders_ahead=int(ahead.qty.sum()), station_backorders_ahead=int(ahead[ahead.station == st].qty.sum()),
                    donor_candidates=len(donors), request_id=rid, tail=tail)


def snapshot_dict(snap: Snapshot) -> dict:
    return asdict(snap)
