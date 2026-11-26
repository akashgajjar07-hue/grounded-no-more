"""AOG incidents from the history: reconstructed timelines, the route actually taken, options at
request time and the counterfactual (actual vs best feasible option).

An incident is one row of ``aog_events`` (groundings merged per aircraft). Each driving request is
traced through removal_events, material_requests, inventory_transactions, transfers,
purchase_orders and repair_orders.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from gnm.schemas import DEADLINE_HOURS

from .data import HistoryView, sim_datetime
from .options import best_option, build_snapshot, evaluate_options, human_panel

ROUTE_LABELS = {
    "a_local": "Local stock (issued later from shelf)",
    "b_hub_transfer": "Emergency transfer from AUH stock",
    "b_hub_transfer_delayed": "Transfer from AUH once AUH stock was replenished",
    "c_lateral": "Lateral transfer from an outstation",
    "f_expedite_po": "Expedited purchase (AOG-desk buy)",
    "h_open_po": "Open purchase order received",
    "h_repair_return": "Repair return from shop",
    "h_inbound_transfer": "Replenishment already in transit to the station",
    "unfilled": "Still unfilled at end of history",
}
ROUTE_TO_OPTION = {"a_local": "a", "b_hub_transfer": "b", "b_hub_transfer_delayed": "b", "c_lateral": "c",
                   "f_expedite_po": "f", "h_open_po": "h", "h_repair_return": "h", "h_inbound_transfer": "h", "unfilled": None}


def _isna(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NA or str(x) in ("<NA>", "nan")


def _step(step, abs_h, need_h, station, event, evidence):
    return {"step": step, "abs_h": int(abs_h), "t_h": int(abs_h) - int(need_h), "datetime": sim_datetime(abs_h),
            "station": station, "event": event, "evidence": evidence}


def trace_fill(view: HistoryView, rid: int) -> dict:
    """Follow the issue that filled request ``rid`` back to its supply (transfer, PO receipt, RO return)."""
    tx = view.t["inventory_transactions"]
    iss = tx[(tx.ref_id.astype("string") == str(rid)) & (tx.txn_type == "ISSUE")].sort_values("txn_id")
    if iss.empty:
        return {"route": "unfilled"}
    last = iss.iloc[-1]
    pn, st, th = last.pn, last.station, int(last.t_h)
    out = {"issue_txn": int(last.txn_id), "fill_h": th, "fill_station": st, "serial": None if _isna(last.serial) else last.serial}

    def preceding(station, t_h, before_id, serial):
        c = tx[(tx.pn == pn) & (tx.station == station) & (tx.t_h == t_h) & (tx.txn_id < before_id)
               & tx.txn_type.isin(["TRANSFER_IN", "RECEIPT_PO", "RECEIPT_REPAIR"])]
        if serial is not None:
            c = c[c.serial.astype("string") == serial]
        return None if c.empty else c.sort_values("txn_id").iloc[-1]

    prev = preceding(st, th, int(last.txn_id), out["serial"])
    receipt, transfer = None, None
    if prev is not None and prev.txn_type == "TRANSFER_IN":
        tid = int(str(prev.ref_id)[1:])
        trow = view.t["transfers"].set_index("transfer_id").loc[tid]
        transfer = {"transfer_id": tid, "from": trow.from_station, "to": trow.to_station, "ship_h": int(trow.ship_h),
                    "arrive_h": int(trow.arrive_h), "kind": trow.kind, "cost_aed": float(trow.cost_aed),
                    "request_id": None if _isna(trow.request_id) else int(trow.request_id)}
        out_tx = tx[(tx.ref_id.astype("string") == f"T{tid}") & (tx.txn_type == "TRANSFER_OUT")]
        if len(out_tx):
            o = out_tx.iloc[0]
            receipt = preceding(trow.from_station, int(trow.ship_h), int(o.txn_id), out["serial"])
            if receipt is not None and receipt.txn_type == "TRANSFER_IN":
                receipt = None
    elif prev is not None:
        receipt = prev
    if receipt is not None:
        ref = str(receipt.ref_id)
        if ref.startswith("PO"):
            po = view.t["purchase_orders"].set_index("po_id").loc[int(ref[2:])]
            out["receipt"] = {"kind": "PO", "po_id": int(ref[2:]), "reason": po.reason, "order_h": int(po.order_h),
                              "due_h": int(po.due_h), "receipt_h": int(po.receipt_h), "qty": int(po.qty),
                              "value_aed": float(po.value_aed), "station": receipt.station}
        else:
            ro = view.t["repair_orders"].set_index("ro_id").loc[int(ref[2:])]
            out["receipt"] = {"kind": "RO", "ro_id": int(ref[2:]), "serial": ro.serial, "shop": ro.shop,
                              "shop_in_h": int(ro.shop_in_h), "quoted_due_h": int(ro.quoted_due_h),
                              "return_h": int(ro.return_h), "station": receipt.station}
    out["transfer"] = transfer
    r = out.get("receipt")
    need_h = int(view.t["material_requests"].set_index("request_id").loc[rid].need_h)
    if transfer is not None and transfer["ship_h"] < need_h:
        out["route"] = "h_inbound_transfer"
    elif r is not None:
        out["route"] = "h_repair_return" if r["kind"] == "RO" else ("f_expedite_po" if r["reason"] == "expedite" else "h_open_po")
    elif transfer is not None:
        if transfer["from"] != view.net.hub:
            out["route"] = "c_lateral"
        elif transfer["ship_h"] <= need_h:
            out["route"] = "b_hub_transfer"
        else:
            out["route"] = "b_hub_transfer_delayed"
    else:
        out["route"] = "a_local"
    return out


def actual_cost(view: HistoryView, rid: int, fill: dict) -> dict:
    """Direct cost attributable to the request: its emergency/lateral shipments + expedite premium."""
    tr = view.t["transfers"]
    ship = float(tr[tr.request_id == rid].cost_aed.sum())
    prem = 0.0
    r = fill.get("receipt")
    if r and r.get("kind") == "PO" and r["reason"] == "expedite":
        unit = r["value_aed"] / max(1, r["qty"])
        prem = float(view.cfg["economics"]["expedite_purchase_premium_pct"]) * unit
    return {"logistics_aed": round(ship, 2), "expedite_premium_aed": round(prem, 2), "total_aed": round(ship + prem, 2)}


def realised_outcome(view: HistoryView, opt: dict, options: list[dict], need_h: int) -> tuple[float, float, str]:
    """Ex-post (wait_h, direct cost, basis) of an option where the history records the outcome.

    Transfers (a/b/c) use the fixed transport matrix, so the estimate is the outcome. For (h) the
    awaited order's actual arrival replaces its quoted date; if it is not in by its quoted date
    (+ the assumed remaining time when already overdue) the desk re-plans to an expedited purchase
    at that moment (config/aog_lab.yaml counterfactual.replan_at_quoted_due). (d/e/f) were not taken,
    so no realisation exists and the estimate is kept. Ex-post use only; never fed to the ranking.
    """
    if opt["key"] in "abc":
        return float(opt["wait_h"]), float(opt["direct_cost"]), "transport_matrix"
    if opt["key"] == "h":
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
            f = next(o for o in options if o["key"] == "f")
            fb = float(ev["remaining_h"]) + float(f["wait_h"])
            if fb < w:
                return fb, float(f["direct_cost"]), "replan_expedite_at_quoted_due"
        return w, float(opt["direct_cost"]), "actual_order_arrival"
    return float(opt["wait_h"]), float(opt["direct_cost"]), "estimate_not_realisable"


def request_timeline(view: HistoryView, req, snap, fill: dict, aog: dict) -> list[dict]:
    rid, need = int(req.request_id), int(req.need_h)
    st, pn = str(req.station), str(req.pn)
    slack = DEADLINE_HOURS[str(req.deadline_class)]
    steps = []
    order = 0

    def add(*a):
        nonlocal order
        s = _step(*a)
        s["_o"] = order
        order += 1
        steps.append(s)

    if req.source == "unscheduled_removal" and not _isna(req.removal_id):
        rem = view.t["removal_events"].set_index("removal_id").loc[int(req.removal_id)]
        add("removal", int(rem.removal_h), need, rem.station, f"{pn} removed unserviceable from {req['tail']} (fictional)",
            {"removal_id": int(req.removal_id), "deadline_class": rem.deadline_class})
    else:
        add("requirement", int(req.known_h), need, st,
            f"Requirement known ({str(req.source).replace('_', ' ')})", {"source": req.source})
    add("request", need, need, st, f"Material request raised: {int(req.qty)} x {pn}, deadline {req.deadline_class}",
        {"request_id": rid, "deadline_class": req.deadline_class, "slack_h": slack, "qty": int(req.qty)})
    add("local_check", need, need, st,
        f"Stock check {st}: {snap.on_hand.get(st, 0)} serviceable on hand"
        + (f", {snap.committed.get(st, 0)} committed to kits" if snap.committed.get(st, 0) else ""),
        {"on_hand": snap.on_hand.get(st, 0), "kit_committed": snap.committed.get(st, 0)})
    others = {s: v for s, v in snap.on_hand.items() if s != st}
    add("network_check", need, need, view.net.hub,
        "Network check: " + ", ".join(f"{s} {v}" for s, v in others.items()),
        {"on_hand_by_station": others, "open_ros": len(snap.open_ros), "open_pos": len(snap.open_pos)})
    if slack == 0 and aog.get("hours", 0) > 0:
        add("aog_start", need, need, st, f"Aircraft AOG: D0 requirement, no serviceable unit at {st}",
            {"aog_id": aog.get("aog_id")})
    route = fill["route"]
    r, t = fill.get("receipt"), fill.get("transfer")
    if route == "h_inbound_transfer":
        # supply already moving before the request: shown as context, then the decision to wait for it
        if r is not None:
            ref = f"PO {r['po_id']}" if r["kind"] == "PO" else f"RO {r['ro_id']}"
            add("received", r.get("receipt_h", r.get("return_h")), need, r["station"],
                f"(before request) {ref} received serviceable at {r['station']}", {"context": True, **{
                    k: r[k] for k in ("po_id", "ro_id", "receipt_h", "return_h") if k in r}})
        add("shipped", t["ship_h"], need, t["from"],
            f"(before request) Routine replenishment {t['from']} -> {t['to']} shipped (T{t['transfer_id']})",
            {"context": True, "transfer_id": t["transfer_id"], "kind": t["kind"]})
        add("sourcing", need, need, st, f"Await replenishment T{t['transfer_id']} already in transit to {st}",
            {"transfer_id": t["transfer_id"], "ship_h": t["ship_h"]})
        add("arrived", t["arrive_h"], need, t["to"], f"Arrived {t['to']}", {"transfer_id": t["transfer_id"]})
        r = t = None
    if r is not None and r["kind"] == "PO":
        if r["order_h"] >= need:
            add("sourcing", r["order_h"], need, view.net.hub,
                f"{'Expedite' if r['reason'] == 'expedite' else r['reason'].replace('_', ' ').title()} PO {r['po_id']} raised (quoted due h{r['due_h']})",
                {k: r[k] for k in ("po_id", "reason", "order_h", "due_h", "value_aed")})
        else:
            add("sourcing", need, need, view.net.hub,
                f"Awaiting open {r['reason'].replace('_', ' ')} PO {r['po_id']} (raised h{r['order_h']}, quoted due h{r['due_h']})",
                {k: r[k] for k in ("po_id", "reason", "order_h", "due_h", "value_aed")})
        add("received", r["receipt_h"], need, r["station"], f"PO {r['po_id']} received serviceable at {r['station']}",
            {"po_id": r["po_id"], "receipt_h": r["receipt_h"], "lead_vs_quoted_h": r["receipt_h"] - r["due_h"]})
    elif r is not None and r["kind"] == "RO":
        add("sourcing", need, need, view.net.hub,
            f"Awaiting repair return: RO {r['ro_id']} ({r['serial']}) at {r['shop']}, quoted due h{r['quoted_due_h']}",
            {k: r[k] for k in ("ro_id", "serial", "shop", "shop_in_h", "quoted_due_h")})
        add("received", r["return_h"], need, r["station"], f"RO {r['ro_id']} returned serviceable to {r['station']}",
            {"ro_id": r["ro_id"], "return_h": r["return_h"], "vs_quoted_h": r["return_h"] - r["quoted_due_h"]})
    if t is not None:
        if r is None:
            add("sourcing", t["ship_h"], need, t["from"],
                f"{'Emergency' if t['kind'] == 'emergency' else t['kind'].title()} transfer {t['from']} -> {t['to']} decided",
                {"transfer_id": t["transfer_id"], "kind": t["kind"]})
        add("shipped", t["ship_h"], need, t["from"], f"Shipped {t['from']} -> {t['to']} ({t['kind']}, T{t['transfer_id']})",
            {"transfer_id": t["transfer_id"], "cost_aed": t["cost_aed"]})
        add("arrived", t["arrive_h"], need, t["to"], f"Arrived {t['to']}", {"transfer_id": t["transfer_id"]})
    if slack > 0 and aog.get("hours", 0) > 0 and need + slack <= (fill.get("fill_h") or view.end_h):
        add("aog_start", need + slack, need, st, f"Deadline {req.deadline_class} expired: aircraft AOG",
            {"deadline_h": need + slack, "aog_id": aog.get("aog_id")})
    if route == "unfilled":
        add("open", view.end_h, need, st, "Still unfilled at end of history (week 103)", {})
    else:
        add("fitted", fill["fill_h"], need, st,
            f"Part issued and fitted; aircraft released" if aog.get("hours", 0) else "Part issued and fitted",
            {"issue_txn": fill["issue_txn"], "serial": fill["serial"], "route": route})
    steps.sort(key=lambda s: (s["abs_h"], s["_o"]))
    for s in steps:
        s.pop("_o")
    return steps


def request_record(view: HistoryView, req, aog: dict) -> dict:
    rid = int(req.request_id)
    snap = build_snapshot(view, req)
    opts = evaluate_options(snap, view.net, view.cfg, view.acfg)
    fill = trace_fill(view, rid)
    cost = actual_cost(view, rid, fill)
    need = int(req.need_h)
    slack = DEADLINE_HOURS[str(req.deadline_class)]
    fill_h = fill.get("fill_h", view.end_h)
    wait = fill_h - need
    aog_h = max(0, wait - slack)
    actual_exp = aog_h * snap.penalty_per_h + cost["total_aed"]
    best = best_option(opts)
    cf = {
        "actual_route": fill["route"], "actual_route_label": ROUTE_LABELS[fill["route"]],
        "actual_option": ROUTE_TO_OPTION[fill["route"]], "actual_wait_h": wait, "actual_aog_h": aog_h,
        "actual_direct_cost_aed": cost["total_aed"], "actual_cost_detail": cost,
        "actual_exposure_aed": round(actual_exp, 2),
        "best_option": best["key"] if best else None, "best_option_label": best["option"] if best else None,
        "best_wait_h": best["wait_h"] if best else None, "best_aog_h": best["aog_h"] if best else None,
        "best_direct_cost_aed": best["direct_cost"] if best else None,
        "best_exposure_aed": best["exposure_aed"] if best else None,
    }
    if best:
        rw, rc, basis = realised_outcome(view, best, opts, need)
        r_aog = max(0.0, rw - slack)
        r_exp = r_aog * snap.penalty_per_h + rc
        cf.update({"best_realised_wait_h": round(rw, 1), "best_realised_aog_h": round(r_aog, 1),
                   "best_realised_direct_cost_aed": round(rc, 2),
                   "best_realised_exposure_aed": round(r_exp, 2), "realised_basis": basis,
                   "aog_h_saving_ex_ante": round(aog_h - best["aog_h"], 1),
                   "aog_h_saving": round(aog_h - r_aog, 1),
                   "exposure_saving_aed": round(actual_exp - r_exp, 2)})
    return {
        "request_id": rid, "pn": req.pn, "station": req.station, "tail": req["tail"], "need_h": need,
        "deadline": req.deadline_class, "qty": int(req.qty), "source": req.source,
        "timeline": request_timeline(view, req, snap, fill, aog),
        "options": opts, "decision": human_panel(snap, opts), "counterfactual": cf,
        "snapshot": {"on_hand": snap.on_hand, "committed": {k: v for k, v in snap.committed.items() if v},
                     "protection": {k: v for k, v in snap.protection.items() if v},
                     "open_ros": snap.open_ros[:5], "open_pos": snap.open_pos[:5],
                     "backorders_ahead": snap.backorders_ahead},
        "_aog_interval": (need + slack, fill_h),
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
    inc = {
        "id": f"AOG-{int(ev.aog_id):04d}", "aog_id": int(ev.aog_id), "tail": ev.tail, "tail_fictional": True,
        "archetype": view.arch.get(ev.tail), "station": ev.station, "pn": prim["pn"], "desc": part.description,
        "ata": part.ata, "part_class": part.part_class, "deadline": prim["deadline"], "need_h": prim["need_h"],
        "need_datetime": sim_datetime(prim["need_h"]), "trigger": ev.trigger,
        "start_h": int(ev.start_h), "end_h": int(ev.end_h), "aog_hours": float(ev.hours),
        "aog_hours_reconstructed": hours_rec, "penalty_aed_per_h": view.penalty(ev.tail),
        "request_ids": rids, "request_id": prim["request_id"], "request_station": prim["station"],
        "n_requests": len(recs),
        "timeline": prim["timeline"], "options": prim["options"], "decision": prim["decision"],
        "counterfactual": prim["counterfactual"], "snapshot": prim["snapshot"],
        "requests": [r for r in recs if r is not prim],
        "provenance": "SIMULATED",
    }
    return inc


def build_all_incidents(view: HistoryView) -> list[dict]:
    ae = view.t["aog_events"].sort_values("aog_id")
    return [build_incident(view, ev) for ev in ae.itertuples()]


def _all_requests(inc):
    yield inc
    yield from inc["requests"]


def select_showcase(incidents: list[dict], n: int = 12, ps1_pn="GN-32-R014", ps1_station="BOM") -> list[str]:
    """Deterministic greedy pick maximising coverage of station, deadline, part class, route, duration."""
    single = [i for i in incidents if i["n_requests"] == 1]
    chosen = []

    def take(i):
        if i and i["id"] not in [c["id"] for c in chosen]:
            chosen.append(i)

    ps1 = sorted([i for i in single if i["pn"] == ps1_pn and i["station"] == ps1_station],
                 key=lambda i: (-i["aog_hours"], i["aog_id"]))
    take(ps1[0] if ps1 else None)
    take(sorted(single, key=lambda i: (-i["aog_hours"], i["aog_id"]))[0])
    d3 = sorted([i for i in single if i["deadline"] == "D3" and i["trigger"] == "deadline_expired"],
                key=lambda i: (-i["aog_hours"], i["aog_id"]))
    take(d3[0] if d3 else None)
    big_cf = sorted([i for i in single if (i["counterfactual"].get("aog_h_saving") or 0) > 0],
                    key=lambda i: (-(i["counterfactual"]["exposure_saving_aed"]), i["aog_id"]))
    take(big_cf[0] if big_cf else None)
    multi = [i for i in incidents if i["n_requests"] > 1]
    take(multi[0] if multi else None)

    def feats(i):
        h = i["aog_hours"]
        dur = "short" if h < 12 else ("medium" if h < 48 else "long")
        return {("st", i["station"]), ("dl", i["deadline"]), ("cls", i["part_class"]),
                ("route", i["counterfactual"]["actual_route"]), ("dur", dur), ("trig", i["trigger"]),
                ("best", i["counterfactual"]["best_option"]), ("pn", i["pn"])}

    while len(chosen) < n:
        have = set().union(*[feats(c) for c in chosen]) if chosen else set()
        cands = [i for i in single if i["id"] not in {c["id"] for c in chosen}]
        if not cands:
            break
        best = max(cands, key=lambda i: (len(feats(i) - have), i["aog_hours"], -i["aog_id"]))
        take(best)
    return [c["id"] for c in chosen]


def summarise(view: HistoryView, incidents: list[dict]) -> dict:
    ae = view.t["aog_events"]
    rows = []
    for inc in incidents:
        for r in _all_requests(inc):
            cf = r["counterfactual"]
            rows.append({"aog_id": inc["aog_id"], "request_id": r["request_id"],
                         "station": r.get("request_station", r["station"]), "pn": r["pn"], "deadline": r["deadline"],
                         "part_class": view.parts.loc[r["pn"]].part_class, **{k: cf[k] for k in (
                             "actual_route", "actual_option", "actual_aog_h", "actual_direct_cost_aed",
                             "actual_exposure_aed", "best_option", "best_aog_h", "best_exposure_aed",
                             "best_realised_aog_h", "best_realised_exposure_aed", "realised_basis")},
                         "aog_h_saving": cf.get("aog_h_saving"), "exposure_saving_aed": cf.get("exposure_saving_aed")})
    df = pd.DataFrame(rows)
    inc_df = pd.DataFrame([{"aog_id": i["aog_id"], "station": i["station"], "deadline": i["deadline"],
                            "part_class": i["part_class"], "trigger": i["trigger"], "hours": i["aog_hours"],
                            "recon": i["aog_hours_reconstructed"]} for i in incidents])

    def grp(col):
        g = inc_df.groupby(col).hours.agg(["count", "sum", "mean", "median"]).reset_index()
        return [{col: k, "events": int(c), "aog_hours": float(s), "mean_h": round(float(m), 1), "median_h": float(md)}
                for k, c, s, m, md in g.itertuples(index=False)]

    agree = df[df.actual_option.notna()]
    same = int((agree.actual_option == agree.best_option).sum())
    pos = df[df.exposure_saving_aed > 0]
    neg = df[df.exposure_saving_aed < 0]
    return {
        "n_incidents": int(len(incidents)), "n_requests": int(len(df)),
        "aog_hours_total": float(ae.hours.sum()), "aog_hours_reconstructed": float(inc_df.recon.sum()),
        "reconciles": bool(np.isclose(ae.hours.sum(), inc_df.recon.sum())),
        "hours_stats": {"mean": round(float(ae.hours.mean()), 1), "median": float(ae.hours.median()),
                        "p90": float(ae.hours.quantile(0.9)), "max": float(ae.hours.max())},
        "by_station": grp("station"), "by_trigger": grp("trigger"), "by_deadline": grp("deadline"),
        "by_part_class": grp("part_class"),
        "actual_routes": {k: int(v) for k, v in df.actual_route.value_counts().items()},
        "best_options": {str(k): int(v) for k, v in df.best_option.value_counts(dropna=False).items()},
        "counterfactual": {
            "requests_compared": int(len(agree)),
            "history_took_best_option": same,
            "requests_with_cheaper_option": int(len(pos)),
            "requests_where_history_beat_estimate": int(len(neg)),
            "actual_request_aog_h": float(df.actual_aog_h.sum()),
            "best_option_request_aog_h_ex_ante": float(df.best_aog_h.fillna(0).sum()),
            "best_option_request_aog_h": float(df.best_realised_aog_h.fillna(0).sum()),
            "actual_exposure_aed": round(float(df.actual_exposure_aed.sum()), 0),
            "best_option_exposure_aed_ex_ante": round(float(df.best_exposure_aed.fillna(0).sum()), 0),
            "best_option_exposure_aed": round(float(df.best_realised_exposure_aed.fillna(0).sum()), 0),
            "realised_basis_counts": {str(k): int(v) for k, v in df.realised_basis.value_counts().items()},
            "net_exposure_saving_aed": round(float(df.exposure_saving_aed.fillna(0).sum()), 0),
            "gross_saving_where_better_aed": round(float(pos.exposure_saving_aed.sum()), 0),
            "by_best_option_where_better": {str(k): {"requests": int(len(g)), "aog_h_saving": float(g.aog_h_saving.sum()),
                                                     "exposure_saving_aed": round(float(g.exposure_saving_aed.sum()), 0)}
                                            for k, g in pos.groupby("best_option")},
            "note": ("Request-level AOG hours (before merging overlapping groundings per aircraft). Best option = "
                     "lowest exposure among feasible options at request time (ex ante, quoted figures). Savings use "
                     "the best option's ex-post outcome where history records it (transfers: fixed transport times; "
                     "awaiting an open order: its actual arrival, re-planned to an expedited purchase if it was not in "
                     "by its quoted date); accelerated repair, expedite and pool were not "
                     "taken, so their estimate is kept. History can beat the estimate."),
        },
        "requests": df.to_dict("records"),
    }
