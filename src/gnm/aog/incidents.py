"""AOG incidents from the v2 history: reconstructed timelines, the route actually taken, options at
request time and the counterfactual (actual vs best feasible option).

An incident is one row of ``aog_events`` (material-related downtime merged per aircraft). Each
driving request is traced through removal_events, material_requests (fill_source, AOG route trace,
fitting time), inventory_transactions, transfers, purchase_orders, repair_orders, aog_loans and
aog_robberies.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .data import HistoryView, deadline_hours, sim_datetime
from .options import best_option, build_snapshot, evaluate_options, human_panel

ROUTE_LABELS = {
    "local": "Local stock (issued from the shelf)",
    "hub_transfer": "Transfer from AUH stock",
    "lateral": "Lateral transfer from an outstation",
    "inbound_transfer": "Shipment already in transit to the station",
    "inbound_po": "Purchase order received (normal supply)",
    "inbound_repair": "Repair return from the shop (normal supply)",
    "inbound_hub_stock": "Transfer from AUH once AUH stock was replenished",
    "robbery": "Robbery from an aircraft at AUH (approval flagged)",
    "exchange_loan": "AOG exchange / loan",
    "planned_loan": "Pre-arranged exchange / loan for a planned change",
    "local_borrow": "Local borrow / third-party loan",
    "local_buy": "Local AOG buy / borrow",
    "unfilled": "Still unfilled at end of history",
}
ROUTE_TO_OPTION = {"local": "local", "hub_transfer": "hub_transfer", "lateral": "lateral", "inbound_transfer": "inbound",
                   "inbound_po": "inbound", "inbound_repair": "inbound", "inbound_hub_stock": "inbound",
                   "robbery": "robbery", "exchange_loan": "exchange_loan", "planned_loan": "exchange_loan",
                   "local_borrow": "local_borrow", "local_buy": "local_buy", "unfilled": None}


def _isna(x) -> bool:
    try:
        return x is None or bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def _step(step, abs_h, need_h, station, event, evidence):
    return {"step": step, "abs_h": int(abs_h), "t_h": int(abs_h) - int(need_h), "datetime": sim_datetime(abs_h),
            "station": station, "event": event, "evidence": evidence}


def _loan_row(view, rid):
    ln = view.t.get("aog_loans")
    if ln is None:
        return None
    r = ln[ln.request_id == rid]
    return None if r.empty else r.iloc[0]


def _rob_row(view, rid):
    rb = view.t.get("aog_robberies")
    if rb is None:
        return None
    r = rb[rb.request_id == rid]
    return None if r.empty else r.iloc[0]


def trace_fill(view: HistoryView, req) -> dict:
    """The route that filled the request, with its supporting records."""
    rid = int(req.request_id)
    need = int(req.need_h)
    fs = None if _isna(req.fill_source) else str(req.fill_source)
    out = {"fill_h": None if _isna(req.filled_h) else int(req.filled_h), "fill_source": fs,
           "route_result": None if _isna(req.aog_route_result) else str(req.aog_route_result),
           "route_h": None if _isna(req.aog_route_h) else int(req.aog_route_h),
           "route_attempts": int(req.aog_route_attempts), "transfer": None, "receipt": None, "loan": None, "robbery": None}
    if fs is None:
        out["route"] = "unfilled"
        return out
    if fs in ("exchange_loan", "local_borrow"):
        ln = _loan_row(view, rid)
        if ln is not None:
            out["loan"] = {"loan_id": int(ln.loan_id), "serial": ln.serial, "kind": ln.kind, "start_h": int(ln.start_h),
                           "returned_h": None if _isna(ln.returned_h) else int(ln.returned_h), "station": ln.station}
        out["route"] = "planned_loan" if out["route_result"] == "planned_loan" else fs
        return out
    if fs == "robbery":
        rb = _rob_row(view, rid)
        if rb is not None:
            out["robbery"] = {"robbery_id": int(rb.robbery_id), "donor_tail": rb.donor_tail, "robbed_h": int(rb.robbed_h),
                              "reinstated_h": None if _isna(rb.reinstated_h) else int(rb.reinstated_h)}
        out["route"] = "robbery"
        return out
    if fs == "local_buy":
        out["route"] = "local_buy"
        return out
    # owned stock: follow the issue back to its supply
    tx = view.t["inventory_transactions"]
    iss = tx[(tx.ref_id.astype("string") == str(rid)) & (tx.txn_type == "ISSUE")].sort_values("txn_id")
    if iss.empty:
        out["route"] = "local" if fs == "local" else "unfilled"
        return out
    last = iss.iloc[-1]
    pn, st, th = last.pn, last.station, int(last.t_h)
    serial = None if _isna(last.serial) else last.serial
    out["serial"] = serial
    out["issue_txn"] = int(last.txn_id)

    def preceding(station, t_h, before_id):
        c = tx[(tx.pn == pn) & (tx.station == station) & (tx.t_h == t_h) & (tx.txn_id < before_id)
               & tx.txn_type.isin(["TRANSFER_IN", "RECEIPT_PO", "RECEIPT_REPAIR"])]
        if serial is not None:
            c = c[c.serial.astype("string") == serial]
        return None if c.empty else c.sort_values("txn_id").iloc[-1]

    prev = preceding(st, th, int(last.txn_id))
    receipt = None
    if prev is not None and prev.txn_type == "TRANSFER_IN":
        tid = int(str(prev.ref_id)[1:])
        trow = view.t["transfers"].set_index("transfer_id").loc[tid]
        out["transfer"] = {"transfer_id": tid, "from": trow.from_station, "to": trow.to_station, "ship_h": int(trow.ship_h),
                           "arrive_h": int(trow.arrive_h), "kind": trow.kind, "cost_aed": float(trow.cost_aed)}
        o = tx[(tx.ref_id.astype("string") == f"T{tid}") & (tx.txn_type == "TRANSFER_OUT")]
        if len(o):
            receipt = preceding(trow.from_station, int(trow.ship_h), int(o.iloc[0].txn_id))
            if receipt is not None and receipt.txn_type == "TRANSFER_IN":
                receipt = None
    elif prev is not None:
        receipt = prev
    if receipt is not None:
        ref = str(receipt.ref_id)
        if ref.startswith("PO"):
            po = view.t["purchase_orders"].set_index("po_id").loc[int(ref[2:])]
            out["receipt"] = {"kind": "PO", "po_id": int(ref[2:]), "reason": po.reason, "order_h": int(po.order_h),
                              "due_h": int(po.due_h), "receipt_h": int(po.receipt_h), "station": receipt.station}
        else:
            ro = view.t["repair_orders"].set_index("ro_id").loc[int(ref[2:])]
            out["receipt"] = {"kind": "RO", "ro_id": int(ref[2:]), "serial": ro.serial, "shop": ro.shop,
                              "shop_in_h": int(ro.shop_in_h), "quoted_due_h": int(ro.quoted_due_h),
                              "return_h": int(ro.return_h), "station": receipt.station, "nff": bool(ro.nff)}
    t, r = out["transfer"], out["receipt"]
    if t is not None and t["ship_h"] < need:
        out["route"] = "inbound_transfer"
    elif r is not None:
        out["route"] = "inbound_repair" if r["kind"] == "RO" else "inbound_po"
    elif t is not None:
        if t["from"] != view.net.hub:
            out["route"] = "lateral"
        elif t["ship_h"] <= need or (fs == "transfer" and t["ship_h"] <= (out["route_h"] or need)):
            out["route"] = "hub_transfer"
        else:
            out["route"] = "inbound_hub_stock"
    else:
        out["route"] = "local"
    return out


def actual_cost(view: HistoryView, req, fill: dict) -> dict:
    """Direct cost attributable to the request, using the engine's accounting rules."""
    cfg = view.cfg
    rid = int(req.request_id)
    pn = str(req.pn)
    unit = float(view.parts.loc[pn].unit_cost_aed)
    arch = view.arch.get(str(req["tail"]), "narrowbody")
    ags = cfg["aog_sourcing"]
    tr = view.t["transfers"]
    ship = float(tr[(tr.request_id == rid)].cost_aed.sum())
    fee = labour = prem = 0.0
    ln = fill.get("loan")
    if ln:
        src = ags["exchange_loan"] if ln["kind"] == "exchange_loan" else ags["local_borrow"]
        fixed = (float(src["fee_pct_of_list"][arch]) * unit if ln["kind"] == "exchange_loan" else float(src["fee_aed_fixed"]))
        end = ln["returned_h"] if ln["returned_h"] is not None else view.end_h
        fee = fixed + float(src["loan_fee_pct_of_list_per_day"]) * unit * max(0, end - ln["start_h"]) / 24.0
    if fill["route"] == "robbery":
        labour = float(cfg["economics"]["fitting_labour_aed_per_hour"]) * float(req.fitting_h) * float(ags["robbery"]["labour_multiplier"])
    if fill["route"] == "local_buy":
        prem = float(ags["local_buy"]["premium_pct"]) * unit * int(req.qty)
    tot = ship + fee + labour + prem
    return {"logistics_aed": round(ship, 2), "loan_fees_aed": round(fee, 2), "robbery_labour_aed": round(labour, 2),
            "local_buy_premium_aed": round(prem, 2), "total_aed": round(tot, 2)}


def realised_outcome(view: HistoryView, opt: dict, options: list[dict], need_h: int) -> tuple[float, float, str]:
    """Ex-post (wait_h, direct cost, basis) of an option where the history records the outcome.

    Transfers use the fixed transport matrix (estimate = outcome). 'inbound' uses the awaited unit's
    actual arrival; if it was not in by its quoted date the desk re-plans to the best probabilistic
    AOG route at that moment (config counterfactual.replan_at_quoted_due). Probabilistic routes and the
    queue-jump were not observed for this request, so their expected values are kept.
    """
    if opt["key"] in ("local", "hub_transfer", "lateral"):
        return float(opt["wait_h"]), float(opt["direct_cost"]), "transport_matrix"
    if opt["key"] == "inbound":
        ev = opt["evidence"]
        ref = ev["inbound_ref"]
        if ref.startswith("T"):
            arr = view.t["transfers"].set_index("transfer_id").loc[int(ref[1:])].arrive_h
        elif ref.startswith("PO"):
            arr = view.t["purchase_orders"].set_index("po_id").loc[int(ref[2:])].receipt_h
        else:
            arr = view.t["repair_orders"].set_index("ro_id").loc[int(ref[2:])].return_h
        arr = view.end_h if _isna(arr) else int(arr)
        w = float(max(0, arr - need_h) + ev["leg_h"])
        if view.acfg["counterfactual"]["replan_at_quoted_due"]:
            alts = [o for o in options if o["key"] in ("local_borrow", "exchange_loan", "local_buy") and o["feasible"]]
            if alts:
                a = min(alts, key=lambda o: o["wait_h"])
                fb = float(ev["remaining_h"]) + float(a["wait_h"])
                if fb < w:
                    return fb, float(a["direct_cost"]), f"replan_{a['key']}_at_quoted_due"
        return w, float(opt["direct_cost"]), "actual_arrival"
    return float(opt["wait_h"]), float(opt["direct_cost"]), "expected_value_not_observed"


def request_timeline(view: HistoryView, req, snap, fill: dict, aog: dict) -> list[dict]:
    rid, need = int(req.request_id), int(req.need_h)
    st, pn = str(req.station), str(req.pn)
    win = deadline_hours(str(req.deadline_class))
    steps, order = [], [0]

    def add(*a, context=False):
        s = _step(*a)
        if context:
            s["evidence"] = dict(s["evidence"], context=True)
        s["_o"] = order[0]
        order[0] += 1
        steps.append(s)

    if req.source == "planned_removal":
        add("requirement", int(req.known_h), need, st, f"Planned {pn} change known (wear-planned, notice)",
            {"source": req.source, "known_h": int(req.known_h), "supply_at_notice": fill["route_result"]})
    if req.source in ("unscheduled_removal", "planned_removal") and not _isna(req.removal_id):
        rem = view.t["removal_events"].set_index("removal_id").loc[int(req.removal_id)]
        add("removal", int(rem.removal_h), need, rem.station, f"{pn} removed unserviceable from {req['tail']} (fictional)",
            {"removal_id": int(req.removal_id), "deadline_class": rem.deadline_class})
    elif req.source != "planned_removal":
        add("requirement", int(req.known_h), need, st, f"Requirement known ({str(req.source).replace('_', ' ')})",
            {"source": req.source})
    add("request", need, need, st, f"Material request raised: {int(req.qty)} x {pn}, window {req.deadline_class}",
        {"request_id": rid, "deadline_class": req.deadline_class, "window_h": win, "qty": int(req.qty)})
    add("local_check", need, need, st,
        f"Stock check {st}: {snap.on_hand.get(st, 0)} serviceable on hand"
        + (f", {snap.committed.get(st, 0)} reserved" if snap.committed.get(st, 0) else ""),
        {"on_hand": snap.on_hand.get(st, 0), "reserved": snap.committed.get(st, 0)})
    others = {s: v for s, v in snap.on_hand.items() if s != st}
    add("network_check", need, need, view.net.hub, "Network check: " + ", ".join(f"{s} {v}" for s, v in others.items()),
        {"on_hand_by_station": others, "open_ros": len(snap.open_ros), "open_pos": len(snap.open_pos)})
    if win == 0 and aog.get("hours", 0) > 0:
        add("aog_start", need, need, st, f"Material-related downtime starts: D0 requirement, no serviceable unit at {st}",
            {"aog_id": aog.get("aog_id")})
    route = fill["route"]
    t, r = fill.get("transfer"), fill.get("receipt")
    if route == "inbound_transfer":
        add("shipped", t["ship_h"], need, t["from"], f"(before request) {t['kind'].title()} shipment {t['from']} -> {t['to']} (T{t['transfer_id']})",
            {"transfer_id": t["transfer_id"], "kind": t["kind"]}, context=True)
        add("sourcing", need, need, st, f"Await shipment T{t['transfer_id']} already in transit to {st}",
            {"transfer_id": t["transfer_id"]})
        add("arrived", t["arrive_h"], need, t["to"], f"Arrived {t['to']}", {"transfer_id": t["transfer_id"]})
        t = r = None
    if fill.get("route_h") is not None and route in ("robbery", "exchange_loan", "local_borrow", "local_buy", "inbound_repair",
                                                      "inbound_po", "inbound_hub_stock", "unfilled", "hub_transfer"):
        rh = fill["route_h"]
        if rh >= need and fill["route_result"] not in ("planned_covered", "planned_transfer"):
            add("aog_route", rh, need, st,
                f"AOG desk tries recovery routes: {fill['route_attempts']} attempt(s), result {fill['route_result']}",
                {"attempts": fill["route_attempts"], "result": fill["route_result"]})
    if route in ("robbery", "exchange_loan", "local_borrow", "local_buy", "planned_loan"):
        label = {"robbery": "Robbery committed (engineering/quality approval required)",
                 "exchange_loan": "Exchange/loan unit delivered", "planned_loan": "Pre-arranged exchange/loan unit fitted",
                 "local_borrow": "Locally borrowed unit delivered", "local_buy": "Local AOG buy delivered"}[route]
        ev = {"fill_source": fill["fill_source"]}
        if fill.get("loan"):
            ev.update(fill["loan"])
        if fill.get("robbery"):
            ev.update(fill["robbery"])
        add("sourced", fill["fill_h"], need, st, label, ev)
    if r is not None and r["kind"] == "PO":
        add("sourcing", max(need, r["order_h"]) if r["order_h"] >= need else need, need, view.net.hub,
            f"Awaiting {r['reason'].replace('_', ' ')} PO {r['po_id']} (raised h{r['order_h']}, quoted due h{r['due_h']})",
            {k: r[k] for k in ("po_id", "reason", "order_h", "due_h")})
        add("received", r["receipt_h"], need, r["station"], f"PO {r['po_id']} received serviceable at {r['station']}",
            {"po_id": r["po_id"], "vs_quoted_h": r["receipt_h"] - r["due_h"]})
    elif r is not None and r["kind"] == "RO":
        add("sourcing", need, need, view.net.hub,
            f"Awaiting repair return: RO {r['ro_id']} ({r['serial']}) at {r['shop']}, quoted due h{r['quoted_due_h']}",
            {k: r[k] for k in ("ro_id", "serial", "shop", "shop_in_h", "quoted_due_h")})
        add("received", r["return_h"], need, r["station"], f"RO {r['ro_id']} returned serviceable to {r['station']}",
            {"ro_id": r["ro_id"], "vs_quoted_h": r["return_h"] - r["quoted_due_h"], "nff": r["nff"]})
    if t is not None:
        if r is None:
            add("sourcing", t["ship_h"], need, t["from"], f"{t['kind'].title()} transfer {t['from']} -> {t['to']} decided",
                {"transfer_id": t["transfer_id"], "kind": t["kind"]})
        add("shipped", t["ship_h"], need, t["from"], f"Shipped {t['from']} -> {t['to']} ({t['kind']}, T{t['transfer_id']})",
            {"transfer_id": t["transfer_id"], "cost_aed": t["cost_aed"]})
        add("arrived", t["arrive_h"], need, t["to"], f"Arrived {t['to']}", {"transfer_id": t["transfer_id"]})
    fill_h = fill.get("fill_h")
    if win and aog.get("hours", 0) > 0 and need + win <= (fill_h if fill_h is not None else view.end_h):
        add("aog_start", need + win, need, st, f"Window {req.deadline_class} expired: material-related downtime starts",
            {"deadline_h": need + win, "aog_id": aog.get("aog_id")})
    if route == "unfilled":
        add("open", view.end_h, need, st, "Still unfilled at end of history (week 103)", {})
    else:
        fit = int(req.fitting_h)
        add("fitted", fill_h, need, st, "Part available at the aircraft; fitting / release-to-service starts",
            {"route": route, "fitting_h": fit, "serial": fill.get("serial")})
        add("released", fill_h + fit, need, st, f"Fitted and released to service (+{fit} h fitting/RTS)",
            {"fitting_h": fit})
    ln, rb = fill.get("loan"), fill.get("robbery")
    if ln and ln.get("returned_h") is not None:
        add("loan_returned", ln["returned_h"], need, ln["station"], "Own unit fitted in place of the borrowed unit; loan returned",
            {"loan_id": ln["loan_id"]})
    if rb and rb.get("reinstated_h") is not None:
        add("donor_reinstated", rb["reinstated_h"], need, view.net.hub, f"Donor {rb['donor_tail']} (fictional) reinstated from AUH stock",
            {"robbery_id": rb["robbery_id"]})
    steps.sort(key=lambda s: (s["abs_h"], s["_o"]))
    for s in steps:
        s.pop("_o")
    return steps


def request_record(view: HistoryView, req, aog: dict) -> dict:
    rid = int(req.request_id)
    snap = build_snapshot(view, req)
    opts = evaluate_options(snap, view.net, view.cfg, view.acfg)
    fill = trace_fill(view, req)
    cost = actual_cost(view, req, fill)
    need = int(req.need_h)
    win = deadline_hours(str(req.deadline_class))
    fill_h = fill["fill_h"] if fill["fill_h"] is not None else view.end_h
    fit = int(req.fitting_h) if fill["fill_h"] is not None else 0
    start = need + win
    late = fill_h > start
    end = fill_h + fit if fill["fill_h"] is not None else view.end_h
    aog_h = float(max(0, end - start)) if late else 0.0
    eco = view.cfg["economics"]
    rate = float(eco["aog_penalty_aed_per_hour"][snap.archetype])
    evc = float(eco["aog_event_cost_aed"][snap.archetype])
    actual_exp = aog_h * rate + (evc if aog_h > 0 else 0.0) + cost["total_aed"]
    best = best_option(opts)
    act_opt = ROUTE_TO_OPTION[fill["route"]]
    lbo = next(o for o in opts if o["key"] == "local_borrow")
    if act_opt in ("exchange_loan", "local_borrow") and lbo["feasible"] and fill["route"] != "planned_loan":
        act_opt = "local_borrow"     # at an outstation the engine always tries local borrow first, then exchange/loan
    cf = {"actual_route": fill["route"], "actual_route_label": ROUTE_LABELS[fill["route"]],
          "actual_option": act_opt, "actual_wait_h": fill_h - need, "actual_fitting_h": fit,
          "actual_aog_h": aog_h, "actual_direct_cost_aed": cost["total_aed"], "actual_cost_detail": cost,
          "actual_exposure_aed": round(actual_exp, 2),
          "best_option": best["key"] if best else None, "best_option_label": best["option"] if best else None,
          "best_wait_h": best["wait_h"] if best else None, "best_aog_h": best["aog_h"] if best else None,
          "best_direct_cost_aed": best["direct_cost"] if best else None,
          "best_exposure_aed": best["exposure_aed"] if best else None}
    if best:
        if best["key"] == act_opt:           # the history took this option: its outcome is observed
            rw, rc, basis = float(fill_h - need), cost["total_aed"], "observed_in_history"
        else:
            rw, rc, basis = realised_outcome(view, best, opts, need)
        late_b = rw > win
        fit_r = fit if fill["fill_h"] is not None else best["fitting_h"]   # fitting time is route-independent
        r_aog = (rw + fit_r - win) if late_b else 0.0
        r_exp = r_aog * rate + (evc if late_b else 0.0) + rc
        cf.update({"best_realised_wait_h": round(rw, 1), "best_realised_aog_h": round(r_aog, 1),
                   "best_realised_direct_cost_aed": round(rc, 2), "best_realised_exposure_aed": round(r_exp, 2),
                   "realised_basis": basis, "aog_h_saving": round(aog_h - r_aog, 1),
                   "exposure_saving_aed": round(actual_exp - r_exp, 2)})
    return {
        "request_id": rid, "pn": req.pn, "station": req.station, "tail": req["tail"], "need_h": need,
        "deadline": req.deadline_class, "qty": int(req.qty), "source": req.source,
        "approval_flag": None if _isna(req.approval_flag) else str(req.approval_flag),
        "timeline": request_timeline(view, req, snap, fill, aog),
        "options": opts, "decision": human_panel(snap, opts), "counterfactual": cf,
        "snapshot": {"on_hand": snap.on_hand, "reserved": {k: v for k, v in snap.committed.items() if v},
                     "protection": {k: v for k, v in snap.protection.items() if v},
                     "open_ros": snap.open_ros[:5], "open_pos": snap.open_pos[:5],
                     "inbound_transfers": snap.inbound_transfers, "backorders_ahead": snap.backorders_ahead,
                     "donor_candidates": snap.donor_candidates},
        "_aog_interval": (start, end if late else start),
    }


def merged_hours(intervals) -> float:
    iv = sorted((a, b) for a, b in intervals if b > a)
    tot, cur = 0, None
    for a, b in iv:
        if cur is None or a > cur[1]:
            if cur:
                tot += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        tot += cur[1] - cur[0]
    return float(tot)


def build_incident(view: HistoryView, ev) -> dict:
    mr = view.t["material_requests"].set_index("request_id", drop=False)
    rids = [int(x) for x in str(ev.request_ids).split(";")]
    aog = {"aog_id": int(ev.aog_id), "hours": float(ev.hours)}
    recs = [request_record(view, mr.loc[r], aog) for r in rids]
    for rec in recs:
        a, b = rec["_aog_interval"]
        rec["aog_h_own"] = float(max(0, b - a))
    prim = max(recs, key=lambda r: (r["aog_h_own"], -r["request_id"]))
    part = view.parts.loc[prim["pn"]]
    hours_rec = merged_hours(rec.pop("_aog_interval") for rec in recs)
    arch = view.arch.get(ev.tail)
    eco = view.cfg["economics"]
    return {
        "id": f"AOG-{int(ev.aog_id):04d}", "aog_id": int(ev.aog_id), "tail": ev.tail, "tail_fictional": True,
        "archetype": arch, "station": ev.station, "pn": prim["pn"], "desc": part.description, "ata": part.ata,
        "part_class": part.part_class, "family": part.get("family"), "removal_mode": part.get("removal_mode"),
        "planted": None if _isna(part.planted) else part.planted,
        "deadline": prim["deadline"], "need_h": prim["need_h"], "need_datetime": sim_datetime(prim["need_h"]),
        "trigger": ev.trigger, "start_h": int(ev.start_h), "end_h": int(ev.end_h), "aog_hours": float(ev.hours),
        "aog_hours_reconstructed": hours_rec,
        "material_shortage_exposure_aed": round(float(ev.hours) * float(eco["aog_penalty_aed_per_hour"][arch])
                                                + float(eco["aog_event_cost_aed"][arch]), 2),
        "rate_aed_per_h": float(eco["aog_penalty_aed_per_hour"][arch]),
        "event_cost_aed": float(eco["aog_event_cost_aed"][arch]),
        "request_ids": rids, "request_id": prim["request_id"], "request_station": prim["station"],
        "source": prim["source"], "approval_flag": prim["approval_flag"], "n_requests": len(recs),
        "timeline": prim["timeline"], "options": prim["options"], "decision": prim["decision"],
        "counterfactual": prim["counterfactual"], "snapshot": prim["snapshot"],
        "requests": [r for r in recs if r is not prim], "provenance": "SIMULATED",
    }


def build_all_incidents(view: HistoryView) -> list[dict]:
    ae = view.t["aog_events"].sort_values("aog_id")
    return [build_incident(view, ev) for ev in ae.itertuples()]


def _all_requests(inc):
    yield inc
    yield from inc["requests"]


def ps1_station(view: HistoryView, pn: str) -> str | None:
    """The outstation where the planted PS1 PN accumulated the most material-related downtime (data-driven)."""
    ae = view.t["aog_events"]
    g = ae[ae.pns.str.contains(pn, regex=False) & (ae.station != view.net.hub)].groupby("station").hours.sum()
    return None if g.empty else str(g.sort_values(ascending=False).index[0])


def select_showcase(incidents: list[dict], n: int = 12, view: HistoryView | None = None) -> list[str]:
    """Deterministic: forced cases, then greedy coverage of station, window, class, route, duration, PN."""
    single = [i for i in incidents if i["n_requests"] == 1]
    chosen = []

    def take(cands, key=lambda i: (i["aog_id"],)):
        cands = [i for i in cands if i["id"] not in {c["id"] for c in chosen}]
        if cands:
            used = {c["pn"] for c in chosen}
            chosen.append(sorted(cands, key=lambda i: (i["pn"] in used, *key(i)))[0])

    ps1 = [i for i in incidents if i.get("planted") == "PS1"]
    if ps1:
        st1 = ps1_station(view, ps1[0]["pn"]) if view is not None else None
        take([i for i in ps1 if i["station"] == st1 and i["n_requests"] == 1] or ps1)
    longest = lambda i: (-i["aog_hours"], i["aog_id"])
    take(single, longest)
    take([i for i in incidents if i["trigger"] == "deadline_expired"], longest)
    for route in ("robbery", "exchange_loan", "local_borrow", "local_buy", "inbound_repair", "lateral", "planned_loan"):
        take([i for i in single if i["counterfactual"]["actual_route"] == route], longest)
    take([i for i in single if i["source"] == "planned_removal"], longest)
    take([i for i in single if (i["counterfactual"].get("exposure_saving_aed") or 0) > 0],
         lambda i: (-i["counterfactual"]["exposure_saving_aed"], i["aog_id"]))
    take([i for i in incidents if i["n_requests"] > 1])

    def feats(i):
        h = i["aog_hours"]
        return {("st", i["station"]), ("dl", i["deadline"]), ("cls", i["part_class"]),
                ("route", i["counterfactual"]["actual_route"]), ("dur", "short" if h < 12 else "medium" if h < 24 else "long"),
                ("best", i["counterfactual"]["best_option"]), ("pn", i["pn"]), ("arch", i["archetype"])}

    while len(chosen) < n:
        have = set().union(*[feats(c) for c in chosen]) if chosen else set()
        cands = [i for i in single if i["id"] not in {c["id"] for c in chosen}]
        if not cands:
            break
        chosen.append(max(cands, key=lambda i: (len(feats(i) - have), i["aog_hours"], -i["aog_id"])))
    return [c["id"] for c in chosen[:max(n, 0)]]


def summarise(view: HistoryView, incidents: list[dict]) -> dict:
    ae = view.t["aog_events"]
    rows = []
    for inc in incidents:
        for r in _all_requests(inc):
            cf = r["counterfactual"]
            rows.append({"aog_id": inc["aog_id"], "request_id": r["request_id"],
                         "station": r.get("request_station", r["station"]), "pn": r["pn"], "deadline": r["deadline"],
                         "part_class": view.parts.loc[r["pn"]].part_class,
                         **{k: cf.get(k) for k in ("actual_route", "actual_option", "actual_aog_h", "actual_direct_cost_aed",
                                                   "actual_exposure_aed", "best_option", "best_aog_h", "best_exposure_aed",
                                                   "best_realised_aog_h", "best_realised_exposure_aed", "realised_basis",
                                                   "aog_h_saving", "exposure_saving_aed")}})
    df = pd.DataFrame(rows)
    inc_df = pd.DataFrame([{"aog_id": i["aog_id"], "station": i["station"], "deadline": i["deadline"],
                            "part_class": i["part_class"], "trigger": i["trigger"], "archetype": i["archetype"],
                            "hours": i["aog_hours"], "recon": i["aog_hours_reconstructed"],
                            "exposure": i["material_shortage_exposure_aed"]} for i in incidents])

    def grp(col):
        g = inc_df.groupby(col).agg(events=("hours", "size"), aog_hours=("hours", "sum"), mean_h=("hours", "mean"),
                                    median_h=("hours", "median"), exposure=("exposure", "sum")).reset_index()
        return [{col: k, "events": int(e), "aog_hours": float(s), "mean_h": round(float(m), 1), "median_h": float(md),
                 "material_shortage_exposure_aed": round(float(x), 0)} for k, e, s, m, md, x in g.itertuples(index=False)]

    cmp_ = df[df.actual_option.notna() & df.best_option.notna()]
    pos = df[df.exposure_saving_aed > 0]
    neg = df[df.exposure_saving_aed < 0]
    return {
        "n_incidents": int(len(incidents)), "n_requests": int(len(df)),
        "aog_hours_total": float(ae.hours.sum()), "aog_hours_reconstructed": float(inc_df.recon.sum()),
        "reconciles": bool(np.isclose(ae.hours.sum(), inc_df.recon.sum())),
        "material_shortage_exposure_aed": round(float(inc_df.exposure.sum()), 0),
        "hours_stats": {"mean": round(float(ae.hours.mean()), 1), "median": float(ae.hours.median()),
                        "p90": float(ae.hours.quantile(0.9)), "max": float(ae.hours.max())},
        "by_station": grp("station"), "by_trigger": grp("trigger"), "by_deadline": grp("deadline"),
        "by_part_class": grp("part_class"), "by_archetype": grp("archetype"),
        "actual_routes": {k: int(v) for k, v in df.actual_route.value_counts().items()},
        "best_options": {str(k): int(v) for k, v in df.best_option.value_counts(dropna=False).items()},
        "counterfactual": {
            "requests_compared": int(len(cmp_)),
            "history_took_best_option": int((cmp_.actual_option == cmp_.best_option).sum()),
            "history_used_robbery": int((df.actual_route == "robbery").sum()),
            "requests_with_lower_exposure_option": int(len(pos)),
            "requests_where_history_beat_estimate": int(len(neg)),
            "actual_request_aog_h": float(df.actual_aog_h.sum()),
            "best_option_request_aog_h_ex_ante": float(df.best_aog_h.fillna(0).sum()),
            "best_option_request_aog_h": float(df.best_realised_aog_h.fillna(0).sum()),
            "actual_exposure_aed": round(float(df.actual_exposure_aed.sum()), 0),
            "best_option_exposure_aed_ex_ante": round(float(df.best_exposure_aed.fillna(0).sum()), 0),
            "best_option_exposure_aed": round(float(df.best_realised_exposure_aed.fillna(0).sum()), 0),
            "net_exposure_saving_aed": round(float(df.exposure_saving_aed.fillna(0).sum()), 0),
            "excluding_history_robbery": {
                "requests": int((df.actual_route != "robbery").sum()),
                "actual_request_aog_h": float(df[df.actual_route != "robbery"].actual_aog_h.sum()),
                "best_option_request_aog_h": float(df[df.actual_route != "robbery"].best_realised_aog_h.fillna(0).sum()),
                "net_exposure_saving_aed": round(float(df[df.actual_route != "robbery"].exposure_saving_aed.fillna(0).sum()), 0),
            },
            "realised_basis_counts": {str(k): int(v) for k, v in df.realised_basis.value_counts().items()},
            "by_best_option_where_lower": {str(k): {"requests": int(len(g)), "aog_h_saving": float(g.aog_h_saving.sum()),
                                                    "exposure_saving_aed": round(float(g.exposure_saving_aed.sum()), 0)}
                                           for k, g in pos.groupby("best_option")},
            "caveats": [
                "Request-level hours and exposure (each late request carries the fixed event cost); incident totals merge overlapping requests per aircraft.",
                "The best option is chosen ex ante from quoted dates and published route odds; the history's own route outcomes are single draws from the same odds.",
                "Probabilistic routes and the repair queue-jump keep their expected value ex post (not observed for that request); transfers are deterministic; 'await inbound' uses the actual arrival, re-planned at the quoted date.",
                "Robbery is never ranked as a recommendation, so requests history covered by robbery compare against the best non-robbery option.",
            ],
        },
        "requests": df.to_dict("records"),
    }
