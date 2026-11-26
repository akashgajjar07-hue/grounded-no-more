"""Planner Action Centre: weekly exception inbox for the latest history week (103).

Reads only the history tables (weeks 0-103) and config. Each exception follows
``schemas.planner_exceptions`` (evidence = JSON string in the table; parsed dict in actions.json).

Exception types
---------------
KIT_SHORTAGE              Scheduled-check kits due in the next 3 weeks not covered by projected AUH stock
OVERDUE_REPAIR            Repair order past its quoted due date and still open
CONDEMNED_AWAITING_REPLACEMENT  Core condemned (beyond economic repair); replacement PO still open
OUTSTATION_DEPLETION      D0 part at an outstation below max(P0 target, demand-implied protection level)
EXCESS_DECLINING_DEMAND   Demand falling and network cover far above need
EXPIRY_RISK               Shelf-life part whose cover exceeds a share of its shelf life
LEAD_TIME_DRIFT           Recent PO lead times well above the quoted lead time
QUARANTINE_DOCS           SIMULATED: receipt awaiting certificate review (seeded RNG; no document data exists)
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
    "LEAD_TIME_DRIFT": "chart", "QUARANTINE_DOCS": "shield",
}
OWNER = {
    "KIT_SHORTAGE": "Materials planner", "OVERDUE_REPAIR": "Repair & warranty administrator",
    "CONDEMNED_AWAITING_REPLACEMENT": "Materials planner", "OUTSTATION_DEPLETION": "Materials planner",
    "EXCESS_DECLINING_DEMAND": "Materials planner", "EXPIRY_RISK": "Stores / quality",
    "LEAD_TIME_DRIFT": "Materials planner", "QUARANTINE_DOCS": "Stores / quality",
}
SEV_ORDER = {"urgent": 0, "review": 1, "info": 2}
DUE_OFFSET = {"urgent": 1, "review": 2, "info": 4}


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


# ---------------------------------------------------------------------------------------------
class _Inbox:
    def __init__(self, week):
        self.week = week
        self.rows = []

    def add(self, typ, severity, pn, station, summary, evidence, action, due_week=None):
        due = due_week if due_week is not None else self.week + DUE_OFFSET[severity]
        self.rows.append({"week": self.week, "type": typ, "severity": severity, "pn": pn, "station": station,
                          "summary": summary, "evidence": evidence, "recommended_action": action,
                          "owner": OWNER[typ], "due_week": int(max(self.week + 1, due)),
                          "severity_icon": SEVERITY_ICON[severity], "type_icon": TYPE_ICON[typ]})


def project_kits(view: HistoryView, T: int, horizon_weeks: int) -> pd.DataFrame:
    """Projected A-check kit lines due in [T, T + horizon) from history patterns only."""
    ms = view.t["maintenance_schedule"]
    ms = ms[ms.notice_h < T]
    tasks = ms.drop_duplicates("task_id")[["task_id", "tail", "due_h"]].sort_values(["tail", "due_h"])
    tasks = tasks.assign(gap=tasks.groupby("tail").due_h.diff())
    arch = view.arch
    ms_a = ms.assign(archetype=ms["tail"].map(arch))
    n_chk = ms_a.drop_duplicates("task_id").groupby("archetype").size()
    per_chk = (ms_a.groupby(["archetype", "pn"]).qty.sum() / n_chk.reindex(
        ms_a.groupby(["archetype", "pn"]).qty.sum().index.get_level_values(0)).to_numpy())
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
                for pn, q in per_chk.loc[a].items():
                    rows.append({"tail": tail, "archetype": a, "due_h": nxt, "pn": pn, "exp_qty": float(q)})
            nxt += int(gap)
    return pd.DataFrame(rows, columns=["tail", "archetype", "due_h", "pn", "exp_qty"])


def _network_serviceable(view, pn, t):
    return int(sum(view.stock_at(pn, t).values()))


def generate_actions(view: HistoryView, week: int | None = None) -> pd.DataFrame:
    a = view.acfg["actions"]
    week = int(week if week is not None else a["as_of_week"])
    T = (week + 1) * HOURS_PER_WEEK          # end of the as-of week
    W = HOURS_PER_WEEK
    t = view.t
    parts = view.parts
    inbox = _Inbox(week)
    mr = t["material_requests"]
    mr = mr[mr.need_h < T]

    # ---- 1. kit shortage (projected) ---------------------------------------------------------
    # The history ends at week 103, so checks due in weeks 104+ are projected: each tail's next
    # A-check = its last check + its median observed check interval; kit content = the archetype's
    # average kit quantity per check and PN in the history (no future work package is read).
    hz = int(a["kit_horizon_weeks"])
    proj_kits = project_kits(view, T, hz)
    for pn, g in proj_kits.groupby("pn", sort=True):
        st = view.net.hub
        oh = view.ledger.on_hand(pn, st, T)
        use = mr[(mr.pn == pn) & (mr.station == st) & (mr.source != "scheduled_kit") & (mr.need_h >= T - 13 * W)]
        rate_h = float(use.qty.sum()) / (13 * W)
        pos = view.open_pos(pn, T - 1)
        cum = 0.0
        for line in g.sort_values("due_h").itertuples():
            cum += float(line.exp_qty)
            other = rate_h * (line.due_h - T)
            inbound = int(pos[pos.due_h <= line.due_h].qty.sum())
            proj = oh - cum - other + inbound
            if proj < 0:
                wk = int(line.due_h // W)
                sev = severity_kit(wk - week, int(a["kit_urgent_within_weeks"]))
                short = int(math.ceil(-proj))
                inbox.add("KIT_SHORTAGE", sev, pn, st,
                          f"{pn}: projected A-check kit demand to W{wk} leaves AUH short by ~{short}",
                          {"first_short_check_tail": line.tail, "projected_check_due_h": int(line.due_h),
                           "projected_check_week": wk, "checks_in_horizon": int(len(g)), "on_hand_auh": oh,
                           "expected_kit_qty_cumulative": round(cum, 1), "expected_line_usage_to_due": round(other, 1),
                           "open_po_qty_due_before": inbound, "projected_balance": round(proj, 1),
                           "basis": "projected checks (median interval) x average kit qty per check (history)"},
                          f"Secure ~{short} unit(s) before W{wk}: expedite an open PO or raise one; pull outstation surplus; "
                          f"confirm the work package when the kit notice arrives",
                          due_week=max(week + 1, wk - 1))
                break

    # ---- 2. overdue repair -----------------------------------------------------------------
    ro = t["repair_orders"]
    open_ro = ro[(ro.shop_in_h < T) & (ro.return_h.isna() | (ro.return_h >= T))]
    open_ro = open_ro[open_ro.ro_id.map(lambda i: view.condemn_h.get(int(i), math.inf)) >= T]
    over = open_ro[open_ro.quoted_due_h < T].sort_values("quoted_due_h")
    for r in over.itertuples():
        wo = (T - int(r.quoted_due_h)) / W
        ns = _network_serviceable(view, r.pn, T)
        dc = parts.loc[r.pn].deadline_class
        sev = severity_overdue(wo, ns, dc, float(a["overdue_urgent_weeks"]))
        inbox.add("OVERDUE_REPAIR", sev, r.pn, view.net.hub,
                  f"RO {int(r.ro_id)} ({r.serial}) at {r.shop} is {wo:.1f} weeks past quoted due (W{int(r.quoted_due_h // W)})",
                  {"ro_id": int(r.ro_id), "serial": r.serial, "shop": r.shop, "removed_week": int(r.removed_h // W),
                   "shop_in_week": int(r.shop_in_h // W), "quoted_due_week": int(r.quoted_due_h // W),
                   "weeks_overdue": round(wo, 1), "quoted_tat_d": float(parts.loc[r.pn].repair_tat_mean_d),
                   "network_serviceable": ns, "deadline_class": dc},
                  "Chase the shop for a committed release date; escalate, consider paid acceleration or an exchange unit")

    # ---- 3. condemned core awaiting replacement ---------------------------------------------
    po = t["purchase_orders"]
    rep = po[(po.reason == "condemn_replacement") & (po.order_h < T) & (po.receipt_h.isna() | (po.receipt_h >= T))]
    for p in rep.sort_values("order_h").itertuples():
        ns = _network_serviceable(view, p.pn, T)
        late = bool(p.due_h < T)
        sev = severity_condemn(ns, late)
        cond = [k for k, h in view.condemn_h.items() if h == int(p.order_h)]
        cro = ro[ro.ro_id.isin(cond) & (ro.pn == p.pn)]
        inbox.add("CONDEMNED_AWAITING_REPLACEMENT", sev, p.pn, view.net.hub,
                  f"{p.pn} core condemned W{int(p.order_h // W)}; replacement PO {int(p.po_id)} "
                  + ("overdue" if late else f"due W{int(p.due_h // W)}"),
                  {"po_id": int(p.po_id), "ro_id": (int(cro.ro_id.iloc[0]) if len(cro) else None),
                   "serial": (cro.serial.iloc[0] if len(cro) else None), "order_week": int(p.order_h // W),
                   "quoted_due_week": int(p.due_h // W), "po_overdue": late, "network_serviceable": ns,
                   "value_aed": float(p.value_aed)},
                  "Confirm supplier delivery date; if network cover is thin, expedite or source a serviceable used unit")

    # ---- 4. outstation depletion (D0 parts) --------------------------------------------------
    sp = t["policy_p0_stock_params"].set_index(["pn", "station"])
    tr = t["transfers"]
    ae = t["aog_events"]
    lb = int(a["depletion_lookback_weeks"])
    d0_pns = parts[parts.deadline_class == "D0"].index
    for pn in sorted(d0_pns):
        cls = parts.loc[pn].part_class
        for st in view.net.stations:
            if st == view.net.hub:
                continue
            oh = view.ledger.on_hand(pn, st, T)
            inbound = int(tr[(tr.pn == pn) & (tr.to_station == st) & (tr.ship_h < T) & (tr.arrive_h >= T)].qty.sum())
            p0 = 0
            if (pn, st) in sp.index:
                row = sp.loc[(pn, st)]
                p0 = int(row.base_stock) if cls == "R" else int(max(0, row.reorder_point_s))
            n, rate = view.d0_demand_rate(pn, st, T, lb)
            pl = poisson_protection(rate, view.net.routine_h, float(a["depletion_service_level"]))
            target = max(p0, pl)
            if oh + inbound >= target or target == 0:
                continue
            ev_ = ae[(ae.station == st) & (ae.start_h >= T - lb * W) & (ae.start_h < T)
                     & ae.pns.str.contains(pn, regex=False)]
            aog_h = float(ev_.hours.sum())
            sev = severity_depletion(oh + inbound, aog_h)
            basis = "demand-implied protection level" if pl > p0 else "P0 target"
            inbox.add("OUTSTATION_DEPLETION", sev, pn, st,
                      f"{pn} at {st}: {oh} serviceable (+{inbound} inbound) vs target {target} ({basis}); "
                      f"{n} D0 requests and {aog_h:.0f} AOG h in {lb} weeks",
                      {"on_hand": oh, "inbound": inbound, "p0_target": p0, "demand_implied_protection": pl,
                       "target": target, "target_basis": basis, "d0_requests_lookback": n, "lookback_weeks": lb,
                       "aog_events_lookback": int(len(ev_)), "aog_hours_lookback": aog_h,
                       "auh_on_hand": view.ledger.on_hand(pn, view.net.hub, T),
                       "aog_transport_h_from_auh": view.net.hours(view.net.hub, st), "part_class": cls},
                      f"Position {target - oh - inbound} unit(s) at {st} (raise the station target from {p0} to {target}); "
                      f"send from AUH stock")

    # ---- 5. excess / declining demand / expiry ----------------------------------------------
    win = int(a["decline_window_weeks"])
    for pn in sorted(parts.index):
        cls = parts.loc[pn].part_class
        if cls == "R":
            continue
        u = mr[mr.pn == pn]
        recent = float(u[u.need_h >= T - win * W].qty.sum())
        prior = float(u[(u.need_h >= T - 2 * win * W) & (u.need_h < T - win * W)].qty.sum())
        net_oh = _network_serviceable(view, pn, T)
        rate_w = recent / win
        cover = math.inf if rate_w == 0 else net_oh / rate_w
        ratio = (recent / prior) if prior > 0 else math.inf
        sev = severity_excess(ratio, cover, float(a["decline_ratio"]), float(a["excess_cover_weeks"]))
        q = u.assign(qtr=(u.need_h // (13 * W)).astype(int)).groupby("qtr").qty.sum()
        qlist = [int(x) for x in q.reindex(range(int((T - 1) // (13 * W)) + 1), fill_value=0).tolist()]
        ev = {"usage_recent_26w": recent, "usage_prior_26w": prior, "ratio": round(ratio, 3) if ratio != math.inf else None,
              "network_on_hand": net_oh, "cover_weeks_at_recent_rate": (None if cover == math.inf else round(cover, 1)),
              "quarterly_usage": qlist, "unit_cost_aed": float(parts.loc[pn].unit_cost_aed),
              "excess_value_aed": (None if cover == math.inf else round(max(0.0, net_oh - rate_w * float(a["excess_cover_weeks"]))
                                                                        * float(parts.loc[pn].unit_cost_aed), 0))}
        if sev:
            inbox.add("EXCESS_DECLINING_DEMAND", sev, pn, None,
                      (f"{pn} demand down to {ratio:.0%} of the previous {win} weeks; network holds {net_oh} "
                       f"(~{cover:.0f} weeks of cover)") if cover != math.inf else
                      (f"{pn}: no demand in the last {win} weeks (previous {win} weeks: {prior:.0f}); "
                       f"network holds {net_oh}"),
                      ev, "Cut min/max to recent demand, stop open reorders, redistribute or return surplus")
        shelf = parts.loc[pn].shelf_life_months
        if shelf == shelf and shelf is not None and cover != math.inf:
            shelf_w = float(shelf) * 52 / 12
            if cover > float(a["expiry_cover_share_of_shelf_life"]) * shelf_w:
                ev2 = dict(ev, shelf_life_weeks=round(shelf_w, 1),
                           expired_units_history=int(view.t["inventory_transactions"].pipe(
                               lambda x: -x[(x.pn == pn) & (x.txn_type == "EXPIRE") & (x.t_h < T)].qty_delta.sum())))
                inbox.add("EXPIRY_RISK", "review" if sev else "info", pn, None,
                          f"{pn} cover ~{cover:.0f} weeks against a {shelf_w:.0f}-week shelf life",
                          ev2, "Issue oldest batches first (FIFO), check expiry dates in stores, reduce reorder quantity")

    # ---- 6. lead-time drift ------------------------------------------------------------------
    lbw = int(a["lead_drift_lookback_weeks"])
    base = po[po.reason.isin(["reorder", "condemn_replacement"]) & (po.order_h < T)].copy()
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
        q_master = float(parts.loc[pn].lead_time_mean_d)
        inbox.add("LEAD_TIME_DRIFT", sev, pn, view.net.hub,
                  f"{pn} recent PO lead time {g.lead_d.mean():.0f} d vs quoted {g.quoted_d.mean():.0f} d ({ratio:.1f}x)",
                  {"pos": [int(x) for x in g.po_id], "n_pos": int(len(g)), "n_open_past_due": int(g.open.sum()),
                   "mean_lead_d": round(float(g.lead_d.mean()), 1), "mean_quoted_d": round(float(g.quoted_d.mean()), 1),
                   "ratio": round(ratio, 2), "master_quoted_lead_d": q_master,
                   "earlier_mean_lead_d": (None if old_mean is None or math.isnan(old_mean) else round(old_mean, 1)),
                   "earlier_n": int(len(older)), "lookback_weeks": lbw},
                  f"Update planning lead time to ~{g.lead_d.mean():.0f} d and recompute the reorder point; ask the supplier for a recovery date")

    # ---- 7. quarantine / missing documents (SIMULATED) -----------------------------------------
    tx = t["inventory_transactions"]
    qw = int(a["quarantine_window_weeks"])
    rc = tx[tx.txn_type.isin(["RECEIPT_PO", "RECEIPT_REPAIR"]) & (tx.t_h >= T - qw * W) & (tx.t_h < T)].sort_values("txn_id")
    if len(rc):
        rng = np.random.default_rng(int(a["quarantine_seed"]))
        k = max(1, int(round(float(a["quarantine_share"]) * len(rc))))
        pick = rc.iloc[np.sort(rng.choice(len(rc), size=k, replace=False))]
        for r in pick.itertuples():
            inbox.add("QUARANTINE_DOCS", "review", r.pn, r.station,
                      f"SIMULATED: {r.pn} receipt {r.ref_id} at {r.station} awaiting certificate review",
                      {"simulated": True, "provenance": "SIMULATED", "txn_id": int(r.txn_id), "ref": str(r.ref_id),
                       "serial": (None if pd.isna(r.serial) else str(r.serial)), "received_h": int(r.t_h),
                       "received_week": int(r.t_h // W), "receipts_in_window": int(len(rc)),
                       "rule": f"seeded RNG {a['quarantine_seed']} flags {a['quarantine_share']:.0%} of receipts in the last {qw} weeks"},
                      "Hold in quarantine; verify the release certificate and traceability before booking to serviceable stock")

    df = pd.DataFrame(inbox.rows)
    df["_s"] = df.severity.map(SEV_ORDER)
    df = df.sort_values(["_s", "type", "pn", "station"], na_position="last", kind="mergesort").drop(columns="_s")
    df.insert(0, "exception_id", [f"EX-{week}-{i:03d}" for i in range(1, len(df) + 1)])
    return df.reset_index(drop=True)


def to_table(df: pd.DataFrame) -> pd.DataFrame:
    """schemas.planner_exceptions layout (evidence as JSON string), extra icon columns at the end."""
    from gnm.schemas import TABLES
    out = df.copy()
    out["evidence"] = out.evidence.map(lambda e: json.dumps(e, default=_json_default, sort_keys=True))
    cols = TABLES["planner_exceptions"].colnames
    for c in ("pn", "station"):
        out[c] = out[c].astype("object").where(out[c].notna(), None)
    return out[cols + [c for c in out.columns if c not in cols]]


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)
