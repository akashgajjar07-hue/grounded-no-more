"""Policy-agnostic continuous-time event engine (docs/data_contract.md §4).

One code path runs every :class:`~gnm.contracts.PolicySpec` against a
:class:`~gnm.contracts.Scenario`. The engine never imports ``gnm.sim.truth``: true
condemnation outcomes, repair durations and lead times arrive pre-sampled in the Scenario.

Time is integer hours on an event heap. Same-hour ordering: weekly snapshot, arrivals and
receipts, shop events, shelf-life expiry, kit reservations, requests, deadline checks.

Initial state (approximate steady state): stations at target (C/E on-hand spread in (s, S] via the
Scenario's ``initial`` CRN), installed serials on every aircraft, and each rotable's repair pipeline
seeded with round(quoted removal rate x quoted pipeline days) units (``pipeline`` CRN; quoted public
figures only, see gnm.sim.quoted).

Stock logic (per PN p, station j):
* serviceable ``on_hand`` (rotables: a FIFO list of serials), ``reserved`` (kit claims from
  ``known_h``), ``routine_in`` (stock-transfer orders in transit), ``sto`` (outstation stock
  transfer orders not yet shipped by AUH), ``bo_unc`` (backordered qty not yet covered by an
  earmarked shipment), ``po`` (AUH purchase orders on order).
* Inventory position: outstation ``IP = on_hand + routine_in + sto - bo_unc - reserved``;
  AUH ``IP = on_hand + routine_in + po - bo_unc - reserved - sum(outstation sto)``.
* C/E: when IP <= s order up to S (outstations raise an STO on AUH, AUH raises a PO).
  R: outstations keep ``base_stock`` one-for-one (STO on AUH); AUH is fed by repairs, condemnation
  replacement POs and expedite POs.
* AUH allocation of every unit that becomes available there: AUH backorders -> outstation
  backorders (earmarked, emergency) -> pending STOs (routine). Backorders are served most-urgent
  first (earliest AOG start = need_h + deadline hours), ties by request order.
"""
from __future__ import annotations

import heapq
import math
import os
from bisect import insort
from collections import deque
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.special import ndtri

from gnm import schemas
from gnm.config import HOURS_PER_WEEK
from gnm.contracts import PolicySpec, RunResult, Scenario, World

# event types
EV_SNAP, EV_ARRIVE, EV_PO, EV_RET, EV_SHOP_IN, EV_BENCH, EV_WORKDONE, EV_CONDEMN, EV_EXPIRE, EV_KIT, EV_REQ, EV_DEADLINE, EV_AOG = range(13)
PRIO = {EV_SNAP: 0, EV_ARRIVE: 1, EV_PO: 1, EV_RET: 1, EV_SHOP_IN: 2, EV_BENCH: 2, EV_WORKDONE: 2, EV_CONDEMN: 2,
        EV_EXPIRE: 3, EV_KIT: 4, EV_REQ: 5, EV_DEADLINE: 6, EV_AOG: 6}
DL_HOURS = schemas.DEADLINE_HOURS
SRC_KIT, SRC_REM, SRC_USE = 0, 1, 2

SNAP_COLS = ["week", "pn", "station", "on_hand", "reserved", "in_transit_in", "backorders", "pipeline", "on_order"]


def merge_intervals(iv: pd.DataFrame) -> pd.DataFrame:
    """Merge overlapping or adjacent AOG intervals per tail.

    ``iv`` columns: tail, start_h, end_h, station, pn, request_id, trigger. Returns aog_events rows
    (without aog_id provenance ordering guarantees beyond (start_h, tail))."""
    cols = schemas.TABLES["aog_events"].colnames
    if iv is None or len(iv) == 0:
        return pd.DataFrame({c: pd.Series(dtype="int64" if c.endswith("_h") or c == "aog_id" else
                                          ("float64" if c == "hours" else "object")) for c in cols})
    iv = iv.sort_values(["tail", "start_h", "end_h"], kind="mergesort")
    out = []
    for tail, g in iv.groupby("tail", sort=True):
        cur = None
        for r in g.itertuples(index=False):
            if cur is not None and r.start_h <= cur["end_h"]:
                cur["end_h"] = max(cur["end_h"], int(r.end_h))
                if r.pn not in cur["pns"]:
                    cur["pns"].append(r.pn)
                cur["rids"].append(str(r.request_id))
            else:
                if cur is not None:
                    out.append(cur)
                cur = {"tail": tail, "station": r.station, "start_h": int(r.start_h), "end_h": int(r.end_h),
                       "pns": [r.pn], "rids": [str(r.request_id)], "trigger": r.trigger}
        out.append(cur)
    df = pd.DataFrame(out).sort_values(["start_h", "tail"], kind="mergesort").reset_index(drop=True)
    df["aog_id"] = np.arange(len(df), dtype=np.int64)
    df["hours"] = (df.end_h - df.start_h).astype(float)
    df["pns"] = df.pns.map(";".join)
    df["request_ids"] = df.rids.map(";".join)
    return df[cols].astype({"start_h": np.int64, "end_h": np.int64})


class _Engine:
    def __init__(self, world: World, sc: Scenario, pol: PolicySpec, kpi_from_week: int, kpi_to_week: int):
        if pol.pool_exchange:
            raise NotImplementedError("pool exchange (P3) hook is not implemented in engine v1")
        cfg = world.cfg
        self.world, self.sc, self.pol = world, sc, pol
        parts = world.parts.reset_index(drop=True)
        self.pns = parts.pn.tolist()
        self.P = P = len(self.pns)
        self.pidx = {p: i for i, p in enumerate(self.pns)}
        self.stations = world.stations.station.tolist()
        self.J = J = len(self.stations)
        self.sidx = {s: i for i, s in enumerate(self.stations)}
        self.H = self.sidx[cfg["network"]["hub"]]
        self.outs = [j for j in range(J) if j != self.H]
        self.cls = parts.part_class.tolist()
        self.is_rot = [c == "R" for c in self.cls]
        self.cost = parts.unit_cost_aed.astype(float).tolist()
        self.lt_quoted = parts.lead_time_mean_d.astype(float).tolist()
        self.shelf_h = [(None if (isinstance(x, float) and math.isnan(x)) or x is None else int(round(x * 30.4375 * 24)))
                        for x in parts.shelf_life_months.tolist()]
        self.rc = parts.repair_cost_aed.fillna(0).astype(float).tolist()
        self.qtat = parts.repair_tat_mean_d.fillna(0).astype(float).tolist()
        shops = world.repair_shops
        self.shop_ids = list(shops.keys())
        self.shop_of = [(self.shop_ids.index(s) if isinstance(s, str) else -1) for s in parts.repair_shop.tolist()]
        self.shop_cap = [shops[s]["capacity_slots"] for s in self.shop_ids]
        self.shop_transit_h = [int(round(shops[s]["transit_days"] * 24)) for s in self.shop_ids]
        self.shop_loc = [shops[s]["location"] for s in self.shop_ids]
        ec = cfg["engine"]
        self.bench_share = float(ec["shop_bench_time_share"])
        self.inspect_h = int(round(ec["condemn_inspection_days"] * 24))
        self.exp_factor = float(ec["expedite_lead_time_factor"])
        self.exp_margin = int(ec.get("expedite_margin_h", 24))
        caps = ec.get("expedite_max_days") or {}
        self.exp_cap = [(float(caps[c]) if caps.get(c) is not None else float("inf")) for c in self.cls]
        net = cfg["network"]
        rt = net["routine_transport_days"]
        cr = net["removed_unit_return_days"]
        mind = float(ec["routine_transport_min_days"])
        jit = sc.transport_jitter or {}
        def _stream(key, m, s):
            u = np.asarray(jit.get(key, np.full(1, 0.5)), float)
            return np.maximum(mind, m + s * ndtri(np.clip(u, 1e-9, 1 - 1e-9))) * 24.0
        self.rt_h = np.rint(_stream("routine", rt["mean"], rt["sd"])).astype(int).tolist()
        self.cr_h = np.rint(_stream("core_return", cr["mean"], cr["sd"])).astype(int).tolist()
        self.rt_i = self.cr_i = 0
        slack = ec.get("earmark_routine_if_slack_sd")
        self.routine_ok_h = (rt["mean"] + slack * rt["sd"]) * 24 if slack is not None else float("inf")
        aog = world.aog_hours.loc[self.stations, self.stations].to_numpy(float)
        self.aog_h = np.rint(aog).astype(int).tolist()
        nz = aog[aog > 0]
        lo, hi = cfg["economics"]["emergency_logistics_aed"]
        self.em_cost = [[0.0 if a == 0 else lo + (hi - lo) * (a - nz.min()) / max(1e-9, nz.max() - nz.min()) for a in row]
                        for row in aog.tolist()]
        eco = cfg["economics"]
        self.line_cost = float(eco["routine_shipment_aed_per_line"])
        self.premium = float(eco["expedite_purchase_premium_pct"])
        self.accel_cost = float(eco["repair_acceleration_cost_aed_per_day_per_unit"])
        self.carry = float(eco["carrying_cost_pct_per_year"])
        arch = dict(zip(world.aircraft["tail"], world.aircraft.archetype))
        self.pen = {t: float(eco["aog_penalty_aed_per_hour"][a]) for t, a in arch.items()}

        # policy parameters
        self.s = [[-1] * J for _ in range(P)]
        self.S = [[0] * J for _ in range(P)]
        self.bs = [[0] * J for _ in range(P)]
        sp = pol.stock_params
        for r in sp.itertuples(index=False):
            if r.pn in self.pidx and r.station in self.sidx:
                i, j = self.pidx[r.pn], self.sidx[r.station]
                self.s[i][j], self.S[i][j], self.bs[i][j] = int(r.s), int(r.S), int(r.base_stock)
        self.em_src = {self.sidx[k]: [self.sidx[x] for x in v if x in self.sidx]
                       for k, v in (pol.emergency_sources or {}).items() if k in self.sidx}
        self.lateral = bool(pol.lateral_transfers)
        self.expedite = bool(pol.expedite_purchase_on_aog)
        self.mult = [float((pol.repair_tat_multiplier or {}).get(p, 1.0)) for p in self.pns]
        # lateral order: other outstations by AOG hours
        self.lat_order = {j: sorted([k for k in self.outs if k != j], key=lambda k: self.aog_h[k][j]) for j in range(J)}

        # time window
        self.t0 = sc.week_from * HOURS_PER_WEEK
        self.end_h = (sc.week_to + 1) * HOURS_PER_WEEK
        self.k0 = kpi_from_week * HOURS_PER_WEEK
        self.k1 = (kpi_to_week + 1) * HOURS_PER_WEEK
        self.kweeks = kpi_to_week - kpi_from_week + 1

        # lead-time streams
        self.lt = {}
        for p, i in self.pidx.items():
            reg = (sc.lead_time_regimes or {}).get(p)
            if reg:
                self.lt[i] = [(int(h), np.asarray(a, float).tolist()) for h, a in reg]
            else:
                a = sc.lead_time_days.get(p)
                self.lt[i] = [(0, np.asarray(a if a is not None else [self.lt_quoted[i]], float).tolist())]
        self.lt_ix = {i: [0] * len(v) for i, v in self.lt.items()}

    # ------------------------------------------------------------------ helpers
    def _push(self, t, et, a=None, b=None):
        self.seq += 1
        heapq.heappush(self.heap, (t, PRIO[et], self.seq, et, a, b))

    def _cap(self, t, delta):
        """Integrate owned-spares value over the KPI window, then apply delta."""
        lo, hi = max(self.cap_t, self.k0), min(t, self.k1)
        if hi > lo:
            self.cap_area += self.cap_val * (hi - lo)
        self.cap_t = t
        self.cap_val += delta

    def _inwin(self, t):
        return self.k0 <= t < self.k1

    def _sstate(self, s, state, loc, t):
        li = self.ser_last[s]
        recs = self.ser_recs
        if li >= 0 and recs[li][3] == t:
            recs[li][1] = state
            recs[li][2] = loc
        else:
            recs.append([s, state, loc, t])
            self.ser_last[s] = len(recs) - 1

    def _new_serial(self, p, state, loc, t):
        n = self.ser_count[p] = self.ser_count[p] + 1
        s = len(self.ser_name)
        self.ser_name.append(f"{self.pns[p]}-S{n:04d}")
        self.ser_pn.append(p)
        self.ser_last.append(-1)
        self._sstate(s, state, loc, t)
        return s

    def _txn(self, t, p, j, typ, q, ref=None, serial=None):
        self.txns.append((t, p, j, typ, q, ref, serial))

    def _lead_days(self, p, t):
        regs = self.lt[p]
        k = 0
        for n, (h, _) in enumerate(regs):
            if h <= t:
                k = n
        arr = regs[k][1]
        ix = self.lt_ix[p][k]
        self.lt_ix[p][k] = ix + 1
        return arr[ix % len(arr)]

    def _ip(self, p, j):
        ip = self.on_hand[p][j] + self.routine_in[p][j] - self.bo_unc[p][j] - self.reserved[p][j]
        if j == self.H:
            return ip + self.po[p] - self.sto_tot[p]
        return ip + self.sto[p][j]

    # ------------------------------------------------------------------ stock moves
    def _take_units(self, p, j, q):
        """Remove q serviceable units from (p, j); returns (serials, batches)."""
        self.on_hand[p][j] -= q
        sers, bats = None, None
        if self.is_rot[p]:
            dq = self.svc[p][j]
            sers = [dq.popleft() for _ in range(q)]
        elif self.shelf_h[p] is not None:
            bl = self.batches[p][j]
            bats, need = [], q
            while need > 0 and bl:
                e = bl[0]
                x = min(need, e[1])
                bats.append([e[0], x])
                e[1] -= x
                need -= x
                if e[1] == 0:
                    bl.pop(0)
        return sers, bats

    def _put_units(self, p, j, q, sers, bats, t):
        self.on_hand[p][j] += q
        if sers:
            loc = self.stations[j]
            for s in sers:
                self._sstate(s, "SERVICEABLE", loc, t)
                self.svc[p][j].append(s)
        if bats:
            bl = self.batches[p][j]
            for e in bats:
                insort(bl, [e[0], e[1]])

    def _issue(self, p, j, q, r, t, src):
        sers, _ = self._take_units(p, j, q)
        self._cap(t, -self.cost[p] * q)
        rid = self.r_reqid[r]
        if sers:
            tail = self.r_tail[r]
            key = (tail, p)
            inst = self.installed.setdefault(key, [])
            for s in sers:
                self._sstate(s, "INSTALLED", tail, t)
                inst.append(s)
                self._txn(t, p, j, "ISSUE", -1, rid, s)
        else:
            self._txn(t, p, j, "ISSUE", -q, rid, None)
        self.r_unf[r] -= q
        self.open_unf[p][j] -= q
        need = self.r_need[r]
        if t > need:
            lo, hi = max(need, self.k0), min(t, self.k1)
            if hi > lo:
                self.bo_area += q * (hi - lo)
        if self.r_unf[r] == 0:
            self.r_filled[r] = t
            self.r_fsrc[r] = src

    def _ship(self, p, k, j, q, t, kind, r=None, src="transfer"):
        sers, bats = self._take_units(p, k, q)
        tid = len(self.trf)
        if sers:
            loc = f"{self.stations[k]}>{self.stations[j]}"
            for s in sers:
                self._sstate(s, "IN_TRANSIT", loc, t)
                self._txn(t, p, k, "TRANSFER_OUT", -1, f"T{tid}", s)
        else:
            self._txn(t, p, k, "TRANSFER_OUT", -q, f"T{tid}", None)
        if kind in ("emergency", "lateral"):
            dur = self.aog_h[k][j]
            cost = self.em_cost[k][j]
            if self._inwin(t):
                self.c_exp += cost
        else:
            dur = self.rt_h[self.rt_i % len(self.rt_h)]
            self.rt_i += 1
            cost = self.line_cost
            if self._inwin(t):
                self.c_log += cost
        arr = t + max(1, dur)
        self.trf.append([tid, p, k, j, q, t, arr, kind, cost, (self.r_reqid[r] if r is not None else None)])
        if r is not None:
            self.earmark_in[p][j] += q
            self.r_unc[r] -= q
        else:
            self.routine_in[p][j] += q
        self._push(arr, EV_ARRIVE, (tid, r, sers, bats, src))

    def _place_po(self, p, q, t, reason):
        lead = self._lead_days(p, t)
        quoted = self.lt_quoted[p]
        val = q * self.cost[p]
        if reason == "expedite":
            lead = min(lead * self.exp_factor, self.exp_cap[p])
            quoted = min(quoted * self.exp_factor, self.exp_cap[p])
            if self._inwin(t):
                self.c_exp += self.premium * val
        rec = t + max(1, int(round(lead * 24)))
        pid = len(self.pos)
        self.pos.append([pid, p, self.H, q, t, t + int(round(quoted * 24)), None, reason, val])
        self.po[p] += q
        if self._inwin(t):
            self.c_buy += val
        self._push(rec, EV_PO, pid)

    # ------------------------------------------------------------------ policy logic
    def _expedite(self, p, u, t):
        """AOG-desk purchase, netted against supply already coming soon: open expedite POs and
        repair returns whose work has started and that are due back within the expedite time."""
        cap = self.exp_cap[p]
        horizon = t + (int(cap * 24) if cap != float("inf") else int(self.lt_quoted[p] * self.exp_factor * 24))
        soon = 0
        for x in self.ret_due[p]:
            if x > horizon:
                break
            soon += 1
        backlog = sum(self.bo_unc[p])
        q = min(u, backlog - soon - self.exp_open[p])
        if q > 0:
            self.exp_open[p] += q
            self._place_po(p, q, t, "expedite")

    def _check(self, p, j, t):
        if self.is_rot[p]:
            if j == self.H:
                return
            bs = self.bs[p][j]
            ip = self._ip(p, j)
            if ip < bs:
                q = bs - ip
                self.sto[p][j] += q
                self.sto_tot[p] += q
                self.sto_q[p].append([j, q])
                self._alloc_auh(p, t, "transfer")
            return
        s = self.s[p][j]
        if s < 0:
            return
        ip = self._ip(p, j)
        if ip <= s:
            q = self.S[p][j] - ip
            if q <= 0:
                return
            if j == self.H:
                self._place_po(p, q, t, "reorder")
            else:
                self.sto[p][j] += q
                self.sto_tot[p] += q
                self.sto_q[p].append([j, q])
                self._alloc_auh(p, t, "transfer")

    def _earmark_kind(self, r):
        return "routine" if self.r_dlh[r] >= self.routine_ok_h else "emergency"

    def _cancel_sto(self, p, j, q):
        q = min(q, self.sto[p][j])
        if q <= 0:
            return
        self.sto[p][j] -= q
        self.sto_tot[p] -= q
        for e in self.sto_q[p]:
            if q == 0:
                break
            if e[0] == j and e[1] > 0:
                x = min(q, e[1])
                e[1] -= x
                q -= x
        while self.sto_q[p] and self.sto_q[p][0][1] == 0:
            self.sto_q[p].popleft()

    def _alloc_auh(self, p, t, src):
        """Allocate AUH serviceable stock. Kit reservations protect stock except against needs that
        are already AOG (need_h + deadline <= t): those may break a reservation (kit robbing)."""
        H = self.H
        oh, rs = self.on_hand[p], self.reserved[p]
        shipped = False
        while oh[H] > 0:
            dq = self.bo_q[p][H]
            best, bkey = None, None
            if dq:
                bkey, best = dq[0]
            for j in self.outs:
                d = self.bo_q[p][j]
                if d and (best is None or d[0] < (bkey, best)):
                    bkey, best = d[0]
            if best is not None:
                avail = oh[H] - (0 if bkey <= t else rs[H])
                if avail > 0:
                    j = self.r_st[best]
                    x = min(avail, self.r_unc[best])
                    self.r_unc[best] -= x
                    self.bo_unc[p][j] -= x
                    if j == H:
                        self._issue(p, H, x, best, t, src)
                    else:
                        self.r_unc[best] += x          # _ship reduces r_unc itself
                        self._ship(p, H, j, x, t, self._earmark_kind(best), r=best, src=src)
                        self._cancel_sto(p, j, x)
                        shipped = True
                    if self.r_unc[best] == 0:
                        heapq.heappop(self.bo_q[p][j])
                    continue
            avail = oh[H] - rs[H]
            if avail <= 0:
                break
            sq = self.sto_q[p]
            while sq and sq[0][1] == 0:
                sq.popleft()
            if sq:
                e = sq[0]
                x = min(avail, e[1])
                e[1] -= x
                self.sto[p][e[0]] -= x
                self.sto_tot[p] -= x
                self._ship(p, H, e[0], x, t, "routine")
                if e[1] == 0:
                    sq.popleft()
                shipped = True
                continue
            break
        if shipped:
            self._check(p, H, t)

    def _serve_local(self, p, j, t, src):
        dq = self.bo_q[p][j]
        while dq:
            key, r = dq[0]
            avail = self.on_hand[p][j] - (0 if key <= t else self.reserved[p][j])
            if avail <= 0:
                break
            x = min(avail, self.r_unc[r])
            self.r_unc[r] -= x
            self.bo_unc[p][j] -= x
            self._issue(p, j, x, r, t, src)
            if self.r_unc[r] == 0:
                heapq.heappop(dq)

    def _core_removal(self, r, p, t):
        tail = self.r_tail[r]
        inst = self.installed.get((tail, p))
        if not inst:
            self.n_phantom += 1
            return
        s = inst.pop(0)
        j = self.r_st[r]
        self._sstate(s, "REMOVED", self.stations[j], t)
        self._cap(t, self.cost[p])
        self.pipe[p] += 1
        self._txn(t, p, j, "UNSERVICEABLE_IN", 0, self.r_reqid[r], s)
        delay = 0
        if j != self.H:
            delay += self.cr_h[self.cr_i % len(self.cr_h)]
            self.cr_i += 1
            if self._inwin(t):
                self.c_log += self.line_cost
        sh = self.shop_of[p]
        if self.shop_transit_h[sh] > 0:
            delay += self.shop_transit_h[sh]
            if self._inwin(t):
                self.c_log += self.line_cost
        self._push(t + delay, EV_SHOP_IN, (s, p, self.r_rid[r], t))

    def _request(self, r, t):
        p, j, q = self.r_pn[r], self.r_st[r], self.r_qty[r]
        if self.r_resv[r]:
            self.reserved[p][j] -= q
            self.r_resv[r] = 0
        if self.r_src[r] == SRC_REM and self.is_rot[p]:
            self._core_removal(r, p, t)
        self.open_unf[p][j] += q
        avail = self.on_hand[p][j] - (0 if self.r_dlh[r] == 0 else self.reserved[p][j])
        take = min(max(avail, 0), q)
        self.r_unc[r] = q
        if take:
            self.r_unc[r] -= take
            self._issue(p, j, take, r, t, "local")
        self.r_imm[r] = take
        rem = q - take
        touched = []
        if rem:
            for k in self.em_src.get(j, []):
                if rem == 0:
                    break
                a = self.on_hand[p][k] - self.reserved[p][k]
                x = min(max(a, 0), rem)
                if x:
                    self._ship(p, k, j, x, t, self._earmark_kind(r), r=r, src="transfer")
                    rem -= x
                    touched.append(k)
            if rem and self.lateral:
                srcs = self.em_src.get(j, [])
                for k in self.lat_order[j]:
                    if rem == 0:
                        break
                    if k in srcs:
                        continue
                    a = self.on_hand[p][k] - self.reserved[p][k]
                    x = min(max(a, 0), rem)
                    if x:
                        self._ship(p, k, j, x, t, "lateral", r=r, src="lateral")
                        rem -= x
                        touched.append(k)
            if rem:
                self.bo_unc[p][j] += rem
                heapq.heappush(self.bo_q[p][j], (self.r_need[r] + self.r_dlh[r], r))
                if self.expedite:
                    if self.r_dlh[r] == 0:
                        self._expedite(p, rem, t)
                        self.r_expd[r] = 1
                    else:   # just-in-time expedite check: deadline - expedite time - margin
                        cap = self.exp_cap[p]
                        exp_h = int(cap * 24) if cap != float("inf") else int(self.lt_quoted[p] * self.exp_factor * 24)
                        self._push(max(t, self.r_need[r] + self.r_dlh[r] - exp_h - self.exp_margin), EV_DEADLINE, r)
                if self.r_dlh[r] > 0:
                    self._push(self.r_need[r] + self.r_dlh[r], EV_AOG, r)   # may then break kit reservations
        self._check(p, j, t)
        for k in touched:
            self._check(p, k, t)

    # ------------------------------------------------------------------ run
    def run(self, detail=True):
        sc, P, J = self.sc, self.P, self.J
        self.heap, self.seq = [], 0
        self.on_hand = [[0] * J for _ in range(P)]
        self.reserved = [[0] * J for _ in range(P)]
        self.routine_in = [[0] * J for _ in range(P)]
        self.earmark_in = [[0] * J for _ in range(P)]
        self.sto = [[0] * J for _ in range(P)]
        self.sto_tot = [0] * P
        self.sto_q = [deque() for _ in range(P)]
        self.po = [0] * P
        self.bo_unc = [[0] * J for _ in range(P)]
        self.bo_q = [[[] for _ in range(J)] for _ in range(P)]   # heaps of (AOG-start time, request) -> most urgent first
        self.open_unf = [[0] * J for _ in range(P)]
        self.svc = [[deque() for _ in range(J)] for _ in range(P)]
        self.batches = [[[] for _ in range(J)] for _ in range(P)]
        self.pipe = [0] * P
        self.exp_open = [0] * P          # expedite qty on order
        self.ret_due = [[] for _ in range(P)]   # expected repair-return times (known once work starts)
        self.installed = {}
        self.ser_name, self.ser_pn, self.ser_last, self.ser_recs = [], [], [], []
        self.ser_count = [0] * P
        self.txns, self.trf, self.pos, self.ros = [], [], [], []
        self.shop_busy = [0] * len(self.shop_ids)
        self.shop_q = [deque() for _ in self.shop_ids]
        self.cap_val = self.cap_area = 0.0
        self.cap_t = self.t0
        self.bo_area = 0.0
        self.c_log = self.c_exp = self.c_rep = self.c_buy = 0.0
        self.n_phantom = 0
        t0 = self.t0

        # ---- requests
        rq = sc.requests
        self.r_reqid = rq.request_id.astype(np.int64).tolist()
        self.r_pn = rq.pn.map(self.pidx).astype(int).tolist()
        self.r_st = rq.station.map(self.sidx).astype(int).tolist()
        self.r_tail = rq["tail"].astype(str).tolist()
        self.r_need = rq.need_h.astype(np.int64).tolist()
        known = rq.known_h.astype(np.int64).tolist()
        self.r_qty = rq.qty.astype(np.int64).tolist()
        self.r_dlh = rq.deadline_class.map(DL_HOURS).astype(int).tolist()
        srcmap = {"scheduled_kit": SRC_KIT, "unscheduled_removal": SRC_REM, "line_usage": SRC_USE}
        self.r_src = rq.source.map(srcmap).astype(int).tolist()
        self.r_rid = rq.removal_id.fillna(-1).astype(np.int64).tolist()
        R = len(rq)
        self.r_unf = list(self.r_qty)
        self.r_unc = list(self.r_qty)
        self.r_filled = [None] * R
        self.r_fsrc = [None] * R
        self.r_imm = [0] * R
        self.r_resv = [0] * R
        self.r_expd = [0] * R

        # ---- initial state: stations at target, installed serials, empty pipeline
        tails = self.world.aircraft["tail"].tolist()
        arch = self.world.aircraft.archetype.tolist()
        for a in self.world.applicability.itertuples(index=False):
            p = self.pidx.get(a.pn)
            if p is None or not self.is_rot[p]:
                continue
            for tail, ar in zip(tails, arch):
                if ar == a.archetype:
                    for _ in range(int(a.qty_per_aircraft)):
                        s = self._new_serial(p, "INSTALLED", tail, t0)
                        self.installed.setdefault((tail, p), []).append(s)
        jit = sc.transport_jitter or {}
        u_init = np.asarray(jit.get("initial", [0.999]), float).tolist()
        ui = 0
        for p in range(P):
            for j in range(J):
                if self.is_rot[p]:
                    q = self.bs[p][j]
                else:   # approximate steady state: on-hand spread between s+1 and S (paired CRN stream)
                    q = max(0, self.S[p][j])
                    s_ = self.s[p][j]
                    if s_ >= 0 and q > s_ + 1:
                        u = u_init[ui % len(u_init)]
                        ui += 1
                        q = s_ + 1 + min(q - s_ - 1, int(u * (q - s_)))
                if q <= 0:
                    continue
                self.on_hand[p][j] = q
                self._cap(t0, self.cost[p] * q)
                if self.is_rot[p]:
                    for _ in range(q):
                        s = self._new_serial(p, "SERVICEABLE", self.stations[j], t0)
                        self.svc[p][j].append(s)
                        self._txn(t0, p, j, "INITIAL", 1, None, s)
                else:
                    self._txn(t0, p, j, "INITIAL", q, None, None)
                    sh = self.shelf_h[p]
                    if sh is not None:          # initial stock: ages spread over 8 batches
                        nb = min(8, q)
                        for k in range(nb):
                            e = t0 + max(1, int(sh * (k + 1) / (nb + 1)))
                            insort(self.batches[p][j], [e, q // nb + (1 if k < q % nb else 0)])
                            self._push(e, EV_EXPIRE, p)
        self._seed_pipeline(t0)
        # ---- schedule events
        for r in range(R):
            self._push(self.r_need[r], EV_REQ, r)
            if self.r_src[r] == SRC_KIT and known[r] < self.r_need[r]:
                self._push(max(known[r], t0), EV_KIT, r)
        nweeks = sc.week_to - sc.week_from + 1
        for w in range(nweeks):
            self._push(t0 + (w + 1) * HOURS_PER_WEEK, EV_SNAP, sc.week_from + w)
        self.snaps = []

        heap, end_h = self.heap, self.end_h
        pop = heapq.heappop
        while heap:
            t, _, _, et, a, b = pop(heap)
            if t >= end_h and et != EV_SNAP:
                break
            if et == EV_REQ:
                self._request(a, t)
            elif et == EV_ARRIVE:
                self._arrive(a, t)
            elif et == EV_PO:
                self._po_receipt(a, t)
            elif et == EV_SHOP_IN:
                self._shop_in(a, t)
            elif et == EV_BENCH:
                self._bench_done(a, t)
            elif et == EV_WORKDONE:
                self._work_done(a, t)
            elif et == EV_RET:
                self._repair_return(a, t)
            elif et == EV_CONDEMN:
                self._condemn(a, t)
            elif et == EV_KIT:
                r = a
                p, j = self.r_pn[r], self.r_st[r]
                self.reserved[p][j] += self.r_qty[r]
                self.r_resv[r] = 1
                self._check(p, j, t)
            elif et == EV_DEADLINE:
                r = a
                if self.r_unf[r] > 0 and self.r_unc[r] > 0 and self.expedite and not self.r_expd[r]:
                    self._expedite(self.r_pn[r], self.r_unc[r], t)
                    self.r_expd[r] = 1
            elif et == EV_AOG:
                if self.r_unc[a] > 0:
                    p, j = self.r_pn[a], self.r_st[a]
                    self._serve_local(p, j, t, "local")
                    if j == self.H or self.r_unc[a] > 0:
                        self._alloc_auh(p, t, "transfer")
            elif et == EV_EXPIRE:
                self._expire(a, t)
            elif et == EV_SNAP:
                self._snapshot(a, t)
        self._cap(end_h, 0.0)
        return self._results(detail)

    def _seed_pipeline(self, t0):
        """Steady-state rotable pipeline from PUBLIC quoted figures: round(quoted removal rate x quoted
        pipeline days) units per PN, remaining times uniform over the pipeline (Scenario 'pipeline' CRN)."""
        from gnm.sim.quoted import pipeline_days, quoted_weekly_demand
        dem = quoted_weekly_demand(self.world).groupby("pn").weekly_demand.sum().to_dict()
        u = np.asarray((self.sc.transport_jitter or {}).get("pipeline", [0.5]), float).tolist()
        k = 0
        H = self.H
        for p in range(self.P):
            if not self.is_rot[p]:
                continue
            pn = self.pns[p]
            days = pipeline_days(self.world, pn)
            n = int(round(dem.get(pn, 0.0) / 7.0 * days))
            sh = self.shop_of[p]
            shop_h = int(round(self.qtat[p] * 24)) + self.shop_transit_h[sh]   # time from shop-in to return
            for _ in range(n):
                R = max(1, int(u[k % len(u)] * days * 24))
                k += 1
                self._cap(t0, self.cost[p])
                self.pipe[p] += 1
                if R > shop_h:     # core still on its way to the shop
                    s = self._new_serial(p, "REMOVED", self.stations[H], t0)
                    self._push(t0 + R - shop_h, EV_SHOP_IN, (s, p, -1, t0))
                else:              # in work at the shop (past its bench time)
                    s = self._new_serial(p, "IN_REPAIR", self.shop_ids[sh], t0)
                    ro = len(self.ros)
                    self.ros.append([ro, s, p, sh, t0, t0, t0, t0 + R, None, False, 0.0, -1])
                    back = self.shop_transit_h[sh]
                    self._push(t0 + max(1, R - back), EV_WORKDONE, (ro, self.qtat[p]))
                    insort(self.ret_due[p], t0 + max(1, R - back) + back)
        self.n_seeded = k

    # ------------------------------------------------------------------ event handlers
    def _arrive(self, a, t):
        tid, r, sers, bats, src = a
        tr = self.trf[tid]
        p, j, q, kind = tr[1], tr[3], tr[4], tr[7]
        self._put_units(p, j, q, sers, bats, t)
        if sers:
            for s in sers:
                self._txn(t, p, j, "TRANSFER_IN", 1, f"T{tid}", s)
        else:
            self._txn(t, p, j, "TRANSFER_IN", q, f"T{tid}", None)
        if bats:
            self._purge(p, j, t)
        if r is not None:
            self.earmark_in[p][j] -= q
            x = min(q, self.r_unf[r], self.on_hand[p][j])
            if x > 0:
                self._issue(p, j, x, r, t, "lateral" if kind == "lateral" else src)
        else:
            self.routine_in[p][j] -= q
        self._serve_local(p, j, t, "transfer")
        if j == self.H:
            self._alloc_auh(p, t, "transfer")
        self._check(p, j, t)

    def _po_receipt(self, pid, t):
        po = self.pos[pid]
        p, q = po[1], po[3]
        H = self.H
        po[6] = t
        self.po[p] -= q
        if po[7] == "expedite":
            self.exp_open[p] -= q
        sers, bats = None, None
        if self.is_rot[p]:
            sers = [self._new_serial(p, "SERVICEABLE", self.stations[H], t) for _ in range(q)]
            for s in sers:
                self.svc[p][H].append(s)
                self._txn(t, p, H, "RECEIPT_PO", 1, f"PO{pid}", s)
            self.on_hand[p][H] += q
        else:
            sh = self.shelf_h[p]
            if sh is not None:
                bats = [[t + sh, q]]
                self._push(t + sh, EV_EXPIRE, p)
            self._put_units(p, H, q, None, bats, t)
            self._txn(t, p, H, "RECEIPT_PO", q, f"PO{pid}", None)
        self._cap(t, self.cost[p] * q)
        self._alloc_auh(p, t, "purchase")
        self._check(p, H, t)

    def _shop_in(self, a, t):
        s, p, rid, removed_t = a
        sh = self.shop_of[p]
        ro = len(self.ros)
        self._sstate(s, "IN_REPAIR", self.shop_ids[sh], t)
        due = t + int(round(self.qtat[p] * 24)) + self.shop_transit_h[sh]
        self.ros.append([ro, s, p, sh, removed_t, t, None, due, None, False, 0.0, rid])
        if self.shop_busy[sh] < self.shop_cap[sh]:
            self._start(ro, t)
        else:
            self.shop_q[sh].append(ro)

    def _start(self, ro, t):
        rec = self.ros[ro]
        rec[6] = t
        sh, p, rid = rec[3], rec[2], rec[11]
        self.shop_busy[sh] += 1
        days = float(self.sc.repair_days.get(rid, self.qtat[p] or 30.0))
        work_h = max(1, int(round(days * self.mult[p] * 24)))
        if self.sc.condemn_flag.get(rid, False):
            self._push(t + min(work_h, self.inspect_h), EV_CONDEMN, ro)
        else:
            self._push(t + max(1, min(work_h, int(round(work_h * self.bench_share)))), EV_BENCH, sh)
            self._push(t + work_h, EV_WORKDONE, (ro, days))
            insort(self.ret_due[p], t + work_h + self.shop_transit_h[sh])

    def _bench_done(self, sh, t):
        self.shop_busy[sh] -= 1
        if self.shop_q[sh]:
            self._start(self.shop_q[sh].popleft(), t)

    def _work_done(self, a, t):
        ro, days = a
        rec = self.ros[ro]
        p, sh = rec[2], rec[3]
        cost = self.rc[p]
        if self.mult[p] < 1.0:
            cost += (1.0 - self.mult[p]) * days * self.accel_cost
        rec[10] = cost
        if self._inwin(t):
            self.c_rep += cost
        if self.shop_transit_h[sh] > 0:
            self._sstate(rec[1], "IN_TRANSIT", f"{self.shop_ids[sh]}>{self.stations[self.H]}", t)
            self._push(t + self.shop_transit_h[sh], EV_RET, ro)
        else:
            self._repair_return(ro, t)

    def _repair_return(self, ro, t):
        rec = self.ros[ro]
        s, p = rec[1], rec[2]
        H = self.H
        rec[8] = t
        self.pipe[p] -= 1
        rd = self.ret_due[p]
        if rd:
            rd.pop(0)
        self._sstate(s, "SERVICEABLE", self.stations[H], t)
        self.svc[p][H].append(s)
        self.on_hand[p][H] += 1
        self._txn(t, p, H, "RECEIPT_REPAIR", 1, f"RO{ro}", s)
        self._alloc_auh(p, t, "repair")

    def _condemn(self, ro, t):
        rec = self.ros[ro]
        s, p, sh = rec[1], rec[2], rec[3]
        rec[9] = True
        self.shop_busy[sh] -= 1
        if self.shop_q[sh]:
            self._start(self.shop_q[sh].popleft(), t)
        self.pipe[p] -= 1
        self._sstate(s, "CONDEMNED", self.shop_ids[sh], t)
        self._cap(t, -self.cost[p])
        loc = self.shop_loc[sh]
        self._txn(t, p, self.sidx.get(loc, self.H), "CONDEMN", 0, f"RO{ro}", s)
        self._place_po(p, 1, t, "condemn_replacement")

    def _purge(self, p, j, t):
        bl = self.batches[p][j]
        x = 0
        while bl and bl[0][0] <= t:
            x += bl.pop(0)[1]
        if x:
            self.on_hand[p][j] -= x
            self._txn(t, p, j, "EXPIRE", -x, None, None)
            self._cap(t, -self.cost[p] * x)
        return x

    def _expire(self, p, t):
        for j in range(self.J):
            if self._purge(p, j, t):
                self._check(p, j, t)

    def _snapshot(self, week, t):
        J = self.J
        if self.pol.rebalance:
            for p in range(self.P):
                for j in self.outs:
                    tgt = self.bs[p][j] if self.is_rot[p] else max(0, self.S[p][j])
                    ex = self.on_hand[p][j] - self.reserved[p][j] - tgt
                    if ex > 0 and not self.bo_q[p][j]:
                        self._ship(p, j, self.H, ex, t, "rebalance")
        oh = np.array(self.on_hand, dtype=np.int64)
        tr = np.array(self.routine_in, dtype=np.int64) + np.array(self.earmark_in, dtype=np.int64)
        pipe = np.zeros((self.P, J), np.int64)
        pipe[:, self.H] = self.pipe
        oo = np.zeros((self.P, J), np.int64)
        oo[:, self.H] = self.po
        self.snaps.append((week, oh, np.array(self.reserved, dtype=np.int64), tr,
                           np.array(self.open_unf, dtype=np.int64), pipe, oo))

    # ------------------------------------------------------------------ outputs
    def _results(self, detail):
        sc = self.sc
        k0, k1 = self.k0, self.k1
        ann = 52.0 / self.kweeks
        need = np.array(self.r_need, dtype=np.int64)
        qty = np.array(self.r_qty, dtype=np.int64)
        imm = np.array(self.r_imm, dtype=np.int64)
        win = (need >= k0) & (need < k1)
        filled = np.array([-1 if x is None else x for x in self.r_filled], dtype=np.int64)
        # open requests at end contribute backorder hours up to end
        bo_area = self.bo_area
        unf = np.array(self.r_unf, dtype=np.int64)
        lo = np.maximum(need, k0)
        hi = np.minimum(self.end_h, k1)
        bo_area += float((unf * np.clip(hi - lo, 0, None))[unf > 0].sum())
        # AOG intervals
        dlh = np.array(self.r_dlh, dtype=np.int64)
        start = need + dlh
        end = np.where(filled >= 0, filled, self.end_h)
        aog = end > start
        idx = np.where(aog)[0]
        iv = pd.DataFrame({"tail": [self.r_tail[i] for i in idx], "start_h": start[idx], "end_h": end[idx],
                           "station": [self.stations[self.r_st[i]] for i in idx],
                           "pn": [self.pns[self.r_pn[i]] for i in idx],
                           "request_id": [self.r_reqid[i] for i in idx],
                           "trigger": ["D0_no_stock" if dlh[i] == 0 else "deadline_expired" for i in idx]})
        aog_ev = merge_intervals(iv)
        if len(aog_ev):
            ov = (np.minimum(aog_ev.end_h.to_numpy(), k1) - np.maximum(aog_ev.start_h.to_numpy(), k0)).clip(0)
            pen = aog_ev["tail"].map(self.pen).to_numpy()
            aog_hours = float(ov.sum())
            aog_pen = float((ov * pen).sum())
            n_aog = int(((aog_ev.start_h >= k0) & (aog_ev.start_h < k1)).sum())
        else:
            aog_hours = aog_pen = 0.0
            n_aog = 0
        cap = self.cap_area / max(1, (min(self.end_h, k1) - max(self.t0, k0)))
        tq = int(qty[win].sum())
        kpis = {
            "immediate_fill_rate": float(imm[win].sum() / tq) if tq else float("nan"),
            "aog_hours": aog_hours * ann,
            "aog_events": n_aog,
            "backorder_unit_hours": bo_area * ann,
            "spare_capital_aed": cap,
            "holding_cost_aed": self.carry * cap,
            "repair_cost_aed": self.c_rep * ann,
            "logistics_cost_aed": self.c_log * ann,
            "expedite_cost_aed": self.c_exp * ann,
            "aog_penalty_aed": aog_pen * ann,
            "purchase_spend_aed": self.c_buy * ann,
        }
        self.kpis = kpis
        E = pd.DataFrame()
        if not detail:
            return RunResult(policy_id=self.pol.policy_id, seed=sc.seed, kpis=kpis, requests=E, aog_events=aog_ev,
                             inventory_transactions=E, repair_orders=E, purchase_orders=E, transfers=E,
                             serial_history=E, stock_snapshots=E)
        pns, sts = np.array(self.pns, dtype=object), np.array(self.stations, dtype=object)
        req = sc.requests.copy()
        req["filled_h"] = pd.array([None if x < 0 else int(x) for x in filled], dtype="Int64")
        req["fill_source"] = pd.array(self.r_fsrc, dtype="string")
        req["immediate_fill"] = pd.array((imm == qty).tolist(), dtype="boolean")

        tx = pd.DataFrame(self.txns, columns=["t_h", "p", "j", "txn_type", "qty_delta", "ref_id", "s"])
        txns = pd.DataFrame({
            "txn_id": np.arange(len(tx), dtype=np.int64), "t_h": tx.t_h.astype(np.int64),
            "pn": pns[tx.p.to_numpy(int)] if len(tx) else [], "station": sts[tx.j.to_numpy(int)] if len(tx) else [],
            "txn_type": tx.txn_type, "qty_delta": tx.qty_delta.astype(np.int64),
            "ref_id": pd.array([None if v is None else str(v) for v in tx.ref_id], dtype="string"),
            "serial": pd.array([None if (v is None or (isinstance(v, float) and math.isnan(v))) else self.ser_name[int(v)]
                                for v in tx.s], dtype="string")})

        sr = pd.DataFrame(self.ser_recs, columns=["s", "state", "location", "since_h"])
        sr = sr.sort_values(["s", "since_h"], kind="mergesort").reset_index(drop=True)
        nxt = sr.groupby("s").since_h.shift(-1)
        serial = pd.DataFrame({"serial": np.array(self.ser_name, dtype=object)[sr.s.to_numpy(int)] if len(sr) else [],
                               "pn": pns[np.array(self.ser_pn, dtype=int)[sr.s.to_numpy(int)]] if len(sr) else [],
                               "state": sr.state, "location": sr.location.astype(str),
                               "since_h": sr.since_h.astype(np.int64), "until_h": nxt.astype("Int64")})

        ro = pd.DataFrame(self.ros, columns=["ro_id", "s", "p", "sh", "removed_h", "shop_in_h", "start_h", "quoted_due_h",
                                             "return_h", "condemned", "repair_cost_aed", "rid"])
        ros = pd.DataFrame({"ro_id": ro.ro_id.astype(np.int64),
                            "serial": [self.ser_name[int(s)] for s in ro.s], "pn": [self.pns[int(p)] for p in ro.p],
                            "shop": [self.shop_ids[int(s)] for s in ro.sh], "removed_h": ro.removed_h.astype(np.int64),
                            "shop_in_h": ro.shop_in_h.astype(np.int64), "start_h": ro.start_h.astype("Int64"),
                            "quoted_due_h": ro.quoted_due_h.astype(np.int64), "return_h": ro.return_h.astype("Int64"),
                            "condemned": ro.condemned.astype(bool), "repair_cost_aed": ro.repair_cost_aed.astype(float),
                            "removal_id": ro.rid.where(ro.rid >= 0).astype("Int64")})

        po = pd.DataFrame(self.pos, columns=["po_id", "p", "j", "qty", "order_h", "due_h", "receipt_h", "reason", "value_aed"])
        pos = pd.DataFrame({"po_id": po.po_id.astype(np.int64), "pn": [self.pns[int(p)] for p in po.p],
                            "station": [self.stations[int(j)] for j in po.j], "qty": po.qty.astype(np.int64),
                            "order_h": po.order_h.astype(np.int64), "due_h": po.due_h.astype(np.int64),
                            "receipt_h": po.receipt_h.astype("Int64"), "reason": po.reason.astype(str),
                            "value_aed": po.value_aed.astype(float)})

        tf = pd.DataFrame(self.trf, columns=["transfer_id", "p", "k", "j", "qty", "ship_h", "arrive_h", "kind", "cost_aed",
                                             "request_id"])
        trfs = pd.DataFrame({"transfer_id": tf.transfer_id.astype(np.int64), "pn": [self.pns[int(p)] for p in tf.p],
                             "from_station": [self.stations[int(k)] for k in tf.k],
                             "to_station": [self.stations[int(j)] for j in tf.j], "qty": tf.qty.astype(np.int64),
                             "ship_h": tf.ship_h.astype(np.int64), "arrive_h": tf.arrive_h.astype(np.int64),
                             "kind": tf.kind.astype(str), "cost_aed": tf.cost_aed.astype(float),
                             "request_id": tf.request_id.astype("Int64")})
        P, J = self.P, self.J
        if self.snaps:
            nw = len(self.snaps)
            snap = pd.DataFrame({
                "week": np.repeat([s[0] for s in self.snaps], P * J).astype(np.int64),
                "pn": np.tile(np.repeat(pns, J), nw), "station": np.tile(np.tile(sts, P), nw),
                "on_hand": np.concatenate([s[1].ravel() for s in self.snaps]),
                "reserved": np.concatenate([s[2].ravel() for s in self.snaps]),
                "in_transit_in": np.concatenate([s[3].ravel() for s in self.snaps]),
                "backorders": np.concatenate([s[4].ravel() for s in self.snaps]),
                "pipeline": np.concatenate([s[5].ravel() for s in self.snaps]),
                "on_order": np.concatenate([s[6].ravel() for s in self.snaps])})
        else:
            snap = pd.DataFrame(columns=SNAP_COLS)
        return RunResult(policy_id=self.pol.policy_id, seed=sc.seed, kpis=kpis, requests=req, aog_events=aog_ev,
                         inventory_transactions=txns, repair_orders=ros, purchase_orders=pos, transfers=trfs,
                         serial_history=serial, stock_snapshots=snap)


def run_policy(world: World, scenario: Scenario, policy: PolicySpec, kpi_from_week: int, kpi_to_week: int,
               detail: bool = True) -> RunResult:
    """Run one PolicySpec on one Scenario. ``detail=False`` skips building the event tables (KPIs + AOG only)."""
    eng = _Engine(world, scenario, policy, kpi_from_week, kpi_to_week)
    res = eng.run(detail=detail)
    res.kpis_extra = {"phantom_removals": eng.n_phantom}
    return res


# ---------------------------------------------------------------------------------------------
# parallel helper
# ---------------------------------------------------------------------------------------------
_W = {}


def _init_worker(world):
    _W["world"] = world


def _job(args):
    sc, pol, kf, kt, detail = args
    if not isinstance(sc, Scenario):
        from gnm.sim.api import load_or_generate_scenario
        sc = load_or_generate_scenario(*sc)
    return run_policy(_W["world"], sc, pol, kf, kt, detail=detail)


def run_many(world: World, scenarios, policies, kpi_from_week: int, kpi_to_week: int, processes: int | None = None,
             detail: bool = False) -> list[RunResult]:
    """Run every policy on every scenario (paired: each policy sees the same Scenario).

    ``scenarios``: Scenario objects or ``(seed, week_from, week_to)`` tuples (generated/cached in the
    worker via ``gnm.sim.api``). Returns RunResults in scenario-major, policy-minor order."""
    jobs = [(sc, pol, kpi_from_week, kpi_to_week, detail) for sc in scenarios for pol in policies]
    processes = processes or min(len(jobs), max(1, (os.cpu_count() or 2) - 1))
    if processes <= 1:
        _init_worker(world)
        return [_job(j) for j in jobs]
    import multiprocessing as mp
    with ProcessPoolExecutor(max_workers=processes, mp_context=mp.get_context("spawn"),
                             initializer=_init_worker, initargs=(world,)) as ex:
        return list(ex.map(_job, jobs, chunksize=1))
