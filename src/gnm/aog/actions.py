"""Planner Action Centre (v2): weekly exception inbox for the latest history week (103).

Reads only the v2 history tables (weeks 0-103) and config, and raises only exception types the v2
simulation actually produces. Each exception follows ``schemas.planner_exceptions`` (evidence = JSON
string in the table; parsed dict in actions.json) plus the action fields the simulation supports:
trigger, quantity, source -> destination, required-by week, expected availability, constraints,
expected benefit (where computable) and owner. Nothing the engine does not model is invented
(no documentation / certificate data exists, so there is no quarantine exception).

Exception types
---------------
KIT_SHORTAGE                    Projected scheduled-check kits (next 3 weeks) not covered by AUH stock
OVERDUE_REPAIR                  Repair order past its quoted due date and still open
CONDEMNED_AWAITING_REPLACEMENT  Core condemned; replacement PO still open
OUTSTATION_DEPLETION            D0 part at an outstation below max(P0 target, demand-implied protection level)
EXCESS_DECLINING_DEMAND         Demand falling and network cover far above need
EXPIRY_RISK                     Shelf-life part whose cover exceeds a share of its shelf life
LEAD_TIME_DRIFT                 Recent PO lead times well above quoted
OPEN_LOAN                       Borrowed / exchange-loan unit still fitted (fee accruing, hand-back pending)
DONOR_NOT_REINSTATED            Aircraft robbed at AUH still waiting for its replacement unit
OPEN_REQUIREMENT                Requirement still unfilled at the end of the week
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from gnm.config import HOURS_PER_WEEK

from .data import HistoryView, poisson_protection

SEVERITY_ICON = {"urgent": "alert", "review": "clock", "info": "info"}
TYPE_ICON = {
    "KIT_SHORTAGE": "layers", "OVERDUE_REPAIR": "wrench", "CONDEMNED_AWAITING_REPLACEMENT": "rotable",
    "OUTSTATION_DEPLETION": "map-pin", "EXCESS_DECLINING_DEMAND": "warehouse", "EXPIRY_RISK": "clock",
    "LEAD_TIME_DRIFT": "chart", "OPEN_LOAN": "route", "DONOR_NOT_REINSTATED": "aircraft", "OPEN_REQUIREMENT": "inbox",
}
OWNER = {
    "KIT_SHORTAGE": "Materials planning", "OVERDUE_REPAIR": "Repair control",
    "CONDEMNED_AWAITING_REPLACEMENT": "Procurement", "OUTSTATION_DEPLETION": "Materials planning",
    "EXCESS_DECLINING_DEMAND": "Materials planning", "EXPIRY_RISK": "Materials planning",
    "LEAD_TIME_DRIFT": "Procurement", "OPEN_LOAN": "AOG desk", "DONOR_NOT_REINSTATED": "AOG desk",
    "OPEN_REQUIREMENT": "AOG desk",
}
OWNERS = sorted(set(OWNER.values()))
SEV_ORDER = {"urgent": 0, "review": 1, "info": 2}
DUE_OFFSET = {"urgent": 1, "review": 2, "info": 4}
ACTION_FIELDS = ["trigger", "quantity", "source", "destination", "required_by_week", "expected_availability",
                 "constraints", "expected_benefit"]


# ---------------------------------------------------------------------------------------------
# severity rules (pure functions, tested on fixtures)
def severity_kit(weeks_to_due: int, urgent_within: int = 1) -> str:
    return "urgent" if weeks_to_due <= urgent_within else "review"


def severity_overdue(weeks_overdue: float, network_serviceable: int, deadline_class: str, urgent_weeks: float = 4) -> str:
    if weeks_overdue > urgent_weeks or network_serviceable == 0 or (deadline_class == "D0" and network_serviceable <= 1):
        return "urgent"
    return "review"


def severity_condemn(network_serviceable: int, po_overdue: bool) -> str:
    if network_serviceable == 0:
        return "urgent"
    return "review" if po_overdue else "info"


def severity_depletion(on_hand_plus_inbound: int, aog_hours_lookback: float) -> str:
    return "urgent" if on_hand_plus_inbound == 0 and aog_hours_lookback > 0 else "review"


def severity_lead_drift(ratio: float, review: float = 1.5, urgent: float = 2.0) -> str | None:
    if ratio >= urgent:
        return "urgent"
    if ratio >= review:
        return "review"
    return None


def severity_excess(ratio: float, cover_weeks: float, decline_ratio: float = 0.75, cover_limit: float = 26) -> str | None:
    if ratio < decline_ratio and cover_weeks > cover_limit:
        return "review"
    return None


def severity_open_loan(days_fitted: float, urgent_days: float = 14) -> str:
    return "urgent" if days_fitted > urgent_days else "review"


def severity_donor(days_waiting: float, urgent_days: float = 7) -> str:
    return "urgent" if days_waiting > urgent_days else "review"


def severity_open_requirement(deadline_class: str, overdue_h: float) -> str:
    return "urgent" if deadline_class == "D0" or overdue_h > 0 else "review"


# ---------------------------------------------------------------------------------------------
class _Inbox:
    def __init__(self, week):
        self.week = week
        self.rows = []

    def add(self, typ, severity, pn, station, summary, evidence, action, *, trigger, quantity=None, source=None,
            destination=None, required_by_week=None, expected_availability=None, constraints=None,
            expected_benefit=None, due_week=None):
        due = due_week if due_week is not None else self.week + DUE_OFFSET[severity]
        self.rows.append({"week": self.week, "type": typ, "severity": severity, "pn": pn, "station": station,
                          "summary": summary, "evidence": evidence, "recommended_action": action,
                          "owner": OWNER[typ], "due_week": int(max(self.week + 1, due)),
                          "trigger": trigger, "quantity": quantity, "source": source, "destination": destination,
                          "required_by_week": required_by_week, "expected_availability": expected_availability,
                          "constraints": constraints or [], "expected_benefit": expected_benefit,
                          "severity_icon": SEVERITY_ICON[severity], "type_icon": TYPE_ICON[typ]})


def project_kits(view: HistoryView, T: int, horizon_weeks: int) -> pd.DataFrame:
    """Projected A-check kit lines due in [T, T + horizon) from history patterns only (the history
    schedule ends at week 103): next check = last check + the tail's median interval; kit content =
    the archetype's average kit quantity per check and PN."""
    ms = view.t["maintenance_schedule"]
    ms = ms[ms.notice_h < T]
    tasks = ms.drop_duplicates("task_id")[["task_id", "tail", "due_h"]].sort_values(["tail", "due_h"])
    tasks = tasks.assign(gap=tasks.groupby("tail").due_h.diff())
    arch = view.arch
    ms_a = ms.assign(archetype=ms["tail"].map(arch))
    n_chk = ms_a.drop_duplicates("task_id").groupby("archetype").size()
    tot = ms_a.groupby(["archetype", "pn"]).qty.sum()
    per_chk = tot / n_chk.reindex(tot.index.get_level_values(0)).to_numpy()
    rows = []
    end = T + horizon_weeks * HOURS_PER_WEEK
    for tail, g in tasks.groupby("tail"):
        gap = g.gap.median()
        if not gap == gap:
            continue
        nxt = int(g.due_h.max() + gap)
        while nxt < end:
            if nxt >= T:
                a = arch.get(tail)
                if a in per_chk.index.get_level_values(0):
                    for pn, q in per_chk.loc[a].items():
                        rows.append({"tail": tail, "archetype": a, "due_h": nxt, "pn": pn, "exp_qty": float(q)})
            nxt += int(gap)
    return pd.DataFrame(rows, columns=["tail", "archetype", "due_h", "pn", "exp_qty"])


def _network_serviceable(view, pn, t):
    return int(sum(view.stock_at(pn, t).values()))


def _first_own_unit(view, pn, T):
    """Earliest quoted own-unit arrival at AUH (open RO or PO) after the week: (h, ref) or (None, None)."""
    c = []
    for r in view.open_ros(pn, T).itertuples():
        c.append((int(r.quoted_due_h), f"RO{int(r.ro_id)}"))
    for p in view.open_pos(pn, T).itertuples():
        c.append((int(p.due_h), f"PO{int(p.po_id)}"))
    return min(c) if c else (None, None)


def _avail(h, basis, T):
    if h is None:
        return {"h": None, "week": None, "basis": basis}
    return {"h": int(h), "week": int(h // HOURS_PER_WEEK), "basis": basis, "past_quote": bool(h < T)}


def generate_actions(view: HistoryView, week: int | None = None) -> pd.DataFrame:
    a = view.acfg["actions"]
    week = int(week if week is not None else a["as_of_week"])
    T = (week + 1) * HOURS_PER_WEEK          # end of the as-of week
    W = HOURS_PER_WEEK
    t = view.t
    parts = view.parts
    hub = view.net.hub
    inbox = _Inbox(week)
    mr = t["material_requests"]
    mr = mr[mr.need_h < T]
    eco = view.cfg["economics"]

    # ---- kit shortage (projected) -----------------------------------------------------------
    hz = int(a["kit_horizon_weeks"])
    for pn, g in project_kits(view, T, hz).groupby("pn", sort=True):
        oh = view.ledger.on_hand(pn, hub, T)
        use = mr[(mr.pn == pn) & (mr.station == hub) & ~mr.source.isin(["scheduled_kit", "planned_removal"])
                 & (mr.need_h >= T - 13 * W)]
        rate_h = float(use.qty.sum()) / (13 * W)
        pos = view.open_pos(pn, T)
        cum = 0.0
        for line in g.sort_values("due_h").itertuples():
            cum += float(line.exp_qty)
            other = rate_h * (line.due_h - T)
            inbound = int(pos[pos.due_h <= line.due_h].qty.sum())
            proj = oh - cum - other + inbound
            if proj < 0:
                wk = int(line.due_h // W)
                short = int(math.ceil(-proj))
                inbox.add("KIT_SHORTAGE", severity_kit(wk - week, int(a["kit_urgent_within_weeks"])), pn, hub,
                          f"{pn}: projected A-check kit demand to W{wk} leaves AUH short by ~{short}",
                          {"projected_check_week": wk, "checks_in_horizon": int(g[["tail", "due_h"]].drop_duplicates().shape[0]),
                           "on_hand_auh": oh, "expected_kit_qty_cumulative": round(cum, 1),
                           "expected_line_usage_to_due": round(other, 1), "open_po_qty_due_before": inbound,
                           "projected_balance": round(proj, 1)},
                          f"Secure ~{short} before W{wk}: pull an open PO forward or reorder; confirm the work package at kit notice",
                          trigger="projected kit balance < 0 within the kit horizon", quantity=short, destination=hub,
                          required_by_week=wk, constraints=["projection: history schedule ends at week 103"],
                          due_week=max(week + 1, wk - 1))
                break

    # ---- overdue repair ---------------------------------------------------------------------
    ro = t["repair_orders"]
    open_ro = ro[(ro.shop_in_h < T) & (ro.return_h.isna() | (ro.return_h >= T))]
    open_ro = open_ro[open_ro.ro_id.map(lambda i: view.condemn_h.get(int(i), math.inf)) >= T]
    for r in open_ro[open_ro.quoted_due_h < T].sort_values("quoted_due_h").itertuples():
        wo = (T - int(r.quoted_due_h)) / W
        ns = _network_serviceable(view, r.pn, T)
        dc = parts.loc[r.pn].deadline_class
        inbox.add("OVERDUE_REPAIR", severity_overdue(wo, ns, dc, float(a["overdue_urgent_weeks"])), r.pn, hub,
                  f"RO {int(r.ro_id)} ({r.serial}) at {r.shop} is {wo:.1f} weeks past quoted due (W{int(r.quoted_due_h // W)})",
                  {"ro_id": int(r.ro_id), "serial": r.serial, "shop": r.shop, "removed_week": int(r.removed_h // W),
                   "shop_in_week": int(r.shop_in_h // W), "work_started": bool(pd.notna(r.start_h) and r.start_h < T),
                   "quoted_due_week": int(r.quoted_due_h // W), "weeks_overdue": round(wo, 1),
                   "quoted_tat_d": float(parts.loc[r.pn].repair_tat_mean_d), "network_serviceable": ns,
                   "deadline_class": dc},
                  "Chase the shop for a committed release date; escalate; consider an AOG exchange if network cover is thin",
                  trigger="open RO past its quoted due date", quantity=1, source=r.shop, destination=hub,
                  required_by_week=int(r.quoted_due_h // W),
                  expected_availability=_avail(None, "past quoted date; shop has not re-quoted (not in the data)", T),
                  constraints=["shop work content is not shortened by priority (AV-21)"])

    # ---- condemned core awaiting replacement -------------------------------------------------
    po = t["purchase_orders"]
    rep = po[(po.reason == "condemn_replacement") & (po.order_h < T) & (po.receipt_h.isna() | (po.receipt_h >= T))]
    for p in rep.sort_values("order_h").itertuples():
        ns = _network_serviceable(view, p.pn, T)
        late = bool(p.due_h < T)
        cond = [k for k, h in view.condemn_h.items() if h == int(p.order_h)]
        cro = ro[ro.ro_id.isin(cond) & (ro.pn == p.pn)]
        inbox.add("CONDEMNED_AWAITING_REPLACEMENT", severity_condemn(ns, late), p.pn, hub,
                  f"{p.pn} core condemned W{int(p.order_h // W)}; replacement PO {int(p.po_id)} "
                  + ("overdue" if late else f"due W{int(p.due_h // W)}"),
                  {"po_id": int(p.po_id), "ro_id": int(cro.ro_id.iloc[0]) if len(cro) else None,
                   "serial": cro.serial.iloc[0] if len(cro) else None, "order_week": int(p.order_h // W),
                   "quoted_due_week": int(p.due_h // W), "po_overdue": late, "network_serviceable": ns,
                   "value_aed": float(p.value_aed)},
                  "Confirm the supplier delivery date; if network cover is thin, line up an exchange/loan for the next AOG",
                  trigger="condemnation replacement PO open", quantity=int(p.qty), source="supplier", destination=hub,
                  required_by_week=int(p.due_h // W),
                  expected_availability=_avail(int(p.due_h), "supplier quoted due date", T),
                  constraints=["normal lead time; the v2 engine has no outright AOG purchase"])

    # ---- outstation depletion (D0 parts) ------------------------------------------------------
    sp = t["policy_p0_stock_params"].set_index(["pn", "station"])
    plan = t.get("policy_p0_rotable_plan")
    tr = t["transfers"]
    ae = t["aog_events"]
    lb = int(a["depletion_lookback_weeks"])
    for pn in sorted(parts[parts.deadline_class == "D0"].index):
        cls = parts.loc[pn].part_class
        unit = float(parts.loc[pn].unit_cost_aed)
        for st in view.net.stations:
            if st == hub:
                continue
            oh = view.ledger.on_hand(pn, st, T)
            inbound = int(tr[(tr.pn == pn) & (tr.to_station == st) & (tr.ship_h < T) & (tr.arrive_h >= T)
                             & (tr.kind != "loan_return")].qty.sum())
            p0 = 0
            if (pn, st) in sp.index:
                row = sp.loc[(pn, st)]
                p0 = int(row.base_stock) if cls == "R" else int(max(0, row.reorder_point_s))
            n, rate = view.d0_demand_rate(pn, st, T, lb)
            pl = poisson_protection(rate, view.net.routine_h, float(a["depletion_service_level"]))
            target = max(p0, pl)
            if target == 0 or oh + inbound >= target:
                continue
            ev_ = ae[(ae.station == st) & (ae.start_h >= T - lb * W) & (ae.start_h < T) & ae.pns.str.contains(pn, regex=False)]
            aog_h = float(ev_.hours.sum())
            auh = view.ledger.on_hand(pn, hub, T)
            need = target - oh - inbound
            basis = "demand-implied protection level" if pl > p0 else "P0 target"
            arch_ = sorted({view.arch.get(x) for x in mr[(mr.pn == pn) & (mr.station == st)]["tail"].dropna()} - {None})
            rate_h = [float(eco["aog_penalty_aed_per_hour"][x]) for x in arch_] or [float(eco["aog_penalty_aed_per_hour"]["narrowbody"])]
            inbox.add("OUTSTATION_DEPLETION", severity_depletion(oh + inbound, aog_h), pn, st,
                      f"{pn} at {st}: {oh} serviceable (+{inbound} inbound) vs target {target} ({basis}); "
                      f"{n} D0 requests and {aog_h:.0f} material-related downtime h in {lb} weeks",
                      {"on_hand": oh, "inbound": inbound, "p0_target": p0, "demand_implied_protection": pl,
                       "target": target, "target_basis": basis, "d0_requests_lookback": n, "lookback_weeks": lb,
                       "aog_events_lookback": int(len(ev_)), "aog_hours_lookback": aog_h, "auh_on_hand": auh,
                       "aog_transport_h_from_auh": view.net.hours(hub, st), "part_class": cls},
                      f"Position {need} unit(s) at {st} (station target {p0} -> {target})"
                      + (" from AUH stock" if auh > 0 else "; AUH has none serviceable — source via repair/exchange"),
                      trigger=f"D0 PN below {basis} at an outstation", quantity=need, source=hub, destination=st,
                      required_by_week=week + 1,
                      expected_availability=_avail(T + view.net.routine_h if auh > 0 else None,
                                                   "routine shipment from AUH (planned transit)" if auh > 0
                                                   else "no serviceable AUH unit at week end", T),
                      constraints=["capital: + AED {:,.0f} per unit held".format(unit),
                                   "station target is a P0 parameter; changing it is a policy decision"],
                      expected_benefit={"observed_downtime_h_lookback": aog_h,
                                        "observed_exposure_rate_aed_per_h": max(rate_h),
                                        "note": "observed at this station for this PN in the lookback; an upper bound, not a forecast"})

    # ---- excess / declining demand / expiry ---------------------------------------------------
    win = int(a["decline_window_weeks"])
    tx = t["inventory_transactions"]
    for pn in sorted(parts.index):
        cls = parts.loc[pn].part_class
        if cls == "R":
            continue
        u = mr[mr.pn == pn]
        recent = float(u[u.need_h >= T - win * W].qty.sum())      # year over year (decline_window_weeks)
        prior = float(u[(u.need_h >= T - 2 * win * W) & (u.need_h < T - win * W)].qty.sum())
        net_oh = _network_serviceable(view, pn, T)
        rate_w = recent / win
        cover = math.inf if rate_w == 0 else net_oh / rate_w
        ratio = (recent / prior) if prior > 0 else math.inf
        sev = severity_excess(ratio, cover, float(a["decline_ratio"]), float(a["excess_cover_weeks"]))
        q = u.assign(qtr=(u.need_h // (13 * W)).astype(int)).groupby("qtr").qty.sum()
        qlist = [int(x) for x in q.reindex(range(int((T - 1) // (13 * W)) + 1), fill_value=0).tolist()]
        unit = float(parts.loc[pn].unit_cost_aed)
        excess_units = None if cover == math.inf else max(0.0, net_oh - rate_w * float(a["excess_cover_weeks"]))
        ev = {"usage_recent": recent, "usage_prior": prior, "window_weeks": win,
              "ratio": round(ratio, 3) if ratio != math.inf else None, "network_on_hand": net_oh,
              "cover_weeks_at_recent_rate": None if cover == math.inf else round(cover, 1), "quarterly_usage": qlist,
              "unit_cost_aed": unit,
              "excess_value_aed": None if excess_units is None else round(excess_units * unit, 0)}
        if sev:
            inbox.add("EXCESS_DECLINING_DEMAND", sev, pn, None,
                      (f"{pn} demand down to {ratio:.0%} of the previous {win} weeks; network holds {net_oh} "
                       f"(~{cover:.0f} weeks of cover)") if cover != math.inf else
                      f"{pn}: no demand in the last {win} weeks (previous {win} weeks: {prior:.0f}); network holds {net_oh}",
                      ev, "Cut min/max to recent demand, stop open reorders, redistribute surplus",
                      trigger=f"usage ratio < {a['decline_ratio']} and cover > {a['excess_cover_weeks']} weeks",
                      quantity=None if excess_units is None else int(excess_units), source="network",
                      expected_benefit=None if excess_units is None else {
                          "capital_above_26w_cover_aed": round(excess_units * unit, 0),
                          "annual_carrying_cost_aed": round(excess_units * unit * float(eco["carrying_cost_pct_per_year"]), 0)})
        shelf = parts.loc[pn].shelf_life_months
        if shelf == shelf and shelf is not None and cover != math.inf:
            shelf_w = float(shelf) * 52 / 12
            if cover > float(a["expiry_cover_share_of_shelf_life"]) * shelf_w:
                exp_n = int(-tx[(tx.pn == pn) & (tx.txn_type == "EXPIRE") & (tx.t_h < T)].qty_delta.sum())
                inbox.add("EXPIRY_RISK", "review" if (sev or exp_n) else "info", pn, None,
                          f"{pn} cover ~{cover:.0f} weeks against a {shelf_w:.0f}-week shelf life ({exp_n} expired in history)",
                          dict(ev, shelf_life_weeks=round(shelf_w, 1), expired_units_history=exp_n),
                          "Reduce reorder quantity; move stock to where it is used before it expires",
                          trigger="cover > {:.0%} of shelf life".format(float(a["expiry_cover_share_of_shelf_life"])),
                          source="network", constraints=["the engine issues oldest batches first (FIFO)"],
                          expected_benefit={"units_expired_in_history": exp_n,
                                            "value_expired_in_history_aed": round(exp_n * unit, 0)})

    # ---- lead-time drift ---------------------------------------------------------------------
    lbw = int(a["lead_drift_lookback_weeks"])
    base = po[po.order_h < T].copy()
    rec_ = base[base.receipt_h.notna() & (base.receipt_h < T) & (base.receipt_h >= T - lbw * W)].copy()
    rec_["lead_d"] = (rec_.receipt_h - rec_.order_h) / 24
    opn = base[(base.receipt_h.isna() | (base.receipt_h >= T)) & (base.due_h < T)].copy()
    opn["lead_d"] = (T - opn.order_h) / 24                 # censored: at least this long, already past due
    cand = pd.concat([rec_.assign(open=False), opn.assign(open=True)])
    cand["quoted_d"] = (cand.due_h - cand.order_h) / 24
    for pn, g in cand.groupby("pn", sort=True):
        if len(g) < int(a["lead_drift_min_pos"]):
            continue
        ratio = float((g.lead_d / g.quoted_d).mean())
        sev = severity_lead_drift(ratio, float(a["lead_drift_review_ratio"]), float(a["lead_drift_urgent_ratio"]))
        if not sev:
            continue
        older = base[base.receipt_h.notna() & (base.receipt_h < T - lbw * W) & (base.pn == pn)]
        old_mean = float(((older.receipt_h - older.order_h) / 24).mean()) if len(older) else None
        new_lt = float(g.lead_d.mean())
        inbox.add("LEAD_TIME_DRIFT", sev, pn, hub,
                  f"{pn} recent PO lead time {new_lt:.0f} d vs quoted {g.quoted_d.mean():.0f} d ({ratio:.1f}x)",
                  {"pos": [int(x) for x in g.po_id], "n_pos": int(len(g)), "n_open_past_due": int(g.open.sum()),
                   "mean_lead_d": round(new_lt, 1), "mean_quoted_d": round(float(g.quoted_d.mean()), 1),
                   "ratio": round(ratio, 2), "master_quoted_lead_d": float(parts.loc[pn].lead_time_mean_d),
                   "earlier_mean_lead_d": None if old_mean is None or math.isnan(old_mean) else round(old_mean, 1),
                   "earlier_n": int(len(older)), "lookback_weeks": lbw},
                  f"Update the planning lead time to ~{new_lt:.0f} d and recompute the reorder point; ask the supplier for a recovery date",
                  trigger=f"mean realised/quoted lead >= {a['lead_drift_review_ratio']}", source="supplier",
                  destination=hub, constraints=["includes open POs already past due (censored lead times)"])

    # ---- open loans (borrowed units still fitted) -----------------------------------------------
    ln = t.get("aog_loans")
    ags = view.cfg["aog_sourcing"]
    if ln is not None and len(ln):
        op = ln[(ln.start_h < T) & (ln.returned_h.isna() | (ln.returned_h >= T))]
        for l in op.sort_values("start_h").itertuples():
            days = (T - int(l.start_h)) / 24
            unit = float(parts.loc[l.pn].unit_cost_aed)
            src = ags["exchange_loan"] if l.kind == "exchange_loan" else ags["local_borrow"]
            daily = float(src["loan_fee_pct_of_list_per_day"]) * unit
            h_own, ref = _first_own_unit(view, l.pn, T)
            inbox.add("OPEN_LOAN", severity_open_loan(days, float(a["loan_urgent_days"])), l.pn, l.station,
                      f"Borrowed {l.pn} ({l.kind.replace('_', ' ')}) fitted to {l.tail} (fictional) for {days:.0f} days; fee accruing",
                      {"loan_id": int(l.loan_id), "serial": l.serial, "kind": l.kind, "tail": l.tail,
                       "start_week": int(l.start_h // W), "days_fitted": round(days, 1), "daily_fee_aed": round(daily, 2),
                       "fees_to_date_aed": round(daily * days, 0), "network_serviceable": _network_serviceable(view, l.pn, T)},
                      "Hand the borrowed unit back as soon as an own serviceable unit is available (AUH allocation: backorders, then donors, then loan hand-backs)",
                      trigger="borrowed unit still fitted at week end", quantity=1, source=hub, destination=l.station,
                      expected_availability=_avail(h_own, f"earliest own unit inbound ({ref}, quoted)" if ref
                                                   else "no own unit inbound", T),
                      constraints=["the own unit must be serviceable and certified before the swap",
                                   "AUH serves open backorders and robbed donors before loan hand-backs"],
                      expected_benefit={"loan_fee_avoided_aed_per_day": round(daily, 2)})

    # ---- robbed donors not yet reinstated --------------------------------------------------------
    rb = t.get("aog_robberies")
    if rb is not None and len(rb):
        op = rb[(rb.robbed_h < T) & (rb.reinstated_h.isna() | (rb.reinstated_h >= T))]
        for r in op.sort_values("robbed_h").itertuples():
            days = (T - int(r.robbed_h)) / 24
            h_own, ref = _first_own_unit(view, r.pn, T)
            inbox.add("DONOR_NOT_REINSTATED", severity_donor(days, float(a["donor_urgent_days"])), r.pn, hub,
                      f"{r.donor_tail} (fictional) robbed of {r.pn} {days:.0f} days ago for {r.aog_tail}; not reinstated",
                      {"robbery_id": int(r.robbery_id), "donor_tail": r.donor_tail, "aog_tail": r.aog_tail,
                       "robbed_week": int(r.robbed_h // W), "days_waiting": round(days, 1),
                       "auh_on_hand": view.ledger.on_hand(r.pn, hub, T)},
                      "Reinstate the donor from the next serviceable AUH unit; keep the engineering/quality approval record open until then",
                      trigger="robbery donor without its unit at week end", quantity=1, source=hub, destination=r.donor_tail,
                      expected_availability=_avail(h_own, f"earliest own unit inbound ({ref}, quoted)" if ref
                                                   else "no own unit inbound", T),
                      constraints=["engineering/quality approval required — human decision",
                                   "simulation assumes the donor does not fly until reinstated"])

    # ---- requirements still unfilled at week end -----------------------------------------------
    allmr = t["material_requests"]
    un = allmr[(allmr.need_h < T) & (allmr.filled_h.isna() | (allmr.filled_h >= T)) & (allmr.deadline_class != "NONE")]
    un = un[~un.request_id.isin(ln.request_id if ln is not None else [])]
    for r in un.sort_values("need_h").itertuples():
        from gnm.schemas import DEADLINE_HOURS
        win_h = DEADLINE_HOURS[r.deadline_class]
        over = T - (int(r.need_h) + win_h)
        h_own, ref = _first_own_unit(view, r.pn, T)
        inbox.add("OPEN_REQUIREMENT", severity_open_requirement(r.deadline_class, over), r.pn, r.station,
                  f"{r.qty} x {r.pn} for {r.tail} (fictional) at {r.station} unfilled since W{int(r.need_h // W)} "
                  f"(window {r.deadline_class}{', expired' if over > 0 else ''})",
                  {"request_id": int(r.request_id), "need_week": int(r.need_h // W), "deadline_class": r.deadline_class,
                   "hours_past_window": max(0, over), "aog_route_result": None if pd.isna(r.aog_route_result) else r.aog_route_result,
                   "aog_route_attempts": int(r.aog_route_attempts)},
                  "AOG desk: keep the recovery routes open (local borrow / exchange-loan / local buy) and expedite the inbound unit",
                  trigger="requirement open at week end", quantity=int(r.qty), destination=r.station,
                  required_by_week=int((int(r.need_h) + win_h) // W),
                  expected_availability=_avail(h_own, f"earliest own unit inbound ({ref}, quoted)" if ref
                                               else "no own unit inbound", T),
                  constraints=["route availability is uncertain (market odds by fleet type)"])

    df = pd.DataFrame(inbox.rows)
    df["_s"] = df.severity.map(SEV_ORDER)
    df = df.sort_values(["_s", "type", "pn", "station"], na_position="last", kind="mergesort").drop(columns="_s")
    df.insert(0, "exception_id", [f"EX-{week}-{i:03d}" for i in range(1, len(df) + 1)])
    return df.reset_index(drop=True)


def to_table(df: pd.DataFrame) -> pd.DataFrame:
    """schemas.planner_exceptions layout (evidence and structured fields as JSON strings), extras appended."""
    from gnm.schemas import TABLES
    out = df.copy()
    for c in ["evidence", "expected_availability", "constraints", "expected_benefit"]:
        out[c] = out[c].map(lambda e: None if e is None else json.dumps(e, default=_json_default, sort_keys=True))
    cols = TABLES["planner_exceptions"].colnames
    for c in ("pn", "station"):
        out[c] = out[c].astype("object").where(out[c].notna(), None)
    return out[cols + [c for c in out.columns if c not in cols]]


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)
