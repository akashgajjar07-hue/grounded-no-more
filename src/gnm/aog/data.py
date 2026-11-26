"""History access for the AOG lab: tables, config and as-of (point-in-time) views.

Only the realised history (``data/processed/history``, weeks 0-103) is read. Every as-of helper
takes a time ``t`` and returns what a materials controller could have known at that moment:
transactions before ``t``, orders already placed, quoted (never actual) due dates of open orders.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from gnm.config import HOURS_PER_WEEK, PROCESSED, ROOT, load_config
from gnm.schemas import DEADLINE_HOURS

HISTORY_DIR = PROCESSED / "history"
AOG_CONFIG_PATH = ROOT / "config" / "aog_lab.yaml"

TABLE_NAMES = (
    "aircraft_master", "part_master", "part_applicability", "maintenance_schedule", "removal_events",
    "material_requests", "inventory_transactions", "repair_orders", "purchase_orders", "transfers",
    "aog_events", "stock_snapshots", "policy_p0_stock_params", "serialised_components", "aog_loans", "aog_robberies",
)


@lru_cache(maxsize=1)
def load_aog_config() -> dict:
    with open(AOG_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_history(path: Path | str = HISTORY_DIR, names=TABLE_NAMES) -> dict[str, pd.DataFrame]:
    path = Path(path)
    return {n: pd.read_parquet(path / f"{n}.parquet") for n in names if (path / f"{n}.parquet").exists()}


def sim_datetime(h) -> str:
    epoch = datetime.fromisoformat(load_config()["calendar"]["epoch"].replace("Z", "+00:00"))
    return (epoch + timedelta(hours=int(h))).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


# ---------------------------------------------------------------------------------------------
# network parameters (public config)
@dataclass(frozen=True)
class Network:
    stations: tuple
    hub: str
    aog_h: dict          # (from, to) -> next-flight-out hours (symmetric)
    em_cost: dict        # (from, to) -> AED per AOG shipment
    routine_h: float     # mean routine transport hours
    routine_ok_h: float  # slack at/above which a transfer ships routine (planned ETA + margin, AV-07)
    line_cost: float
    shop_transit_h: dict  # shop -> hours shop -> AUH

    def hours(self, a, b) -> int:
        return int(self.aog_h[(a, b)])


def network_from_config(cfg: dict | None = None, acfg: dict | None = None) -> Network:
    cfg = cfg or load_config()
    acfg = acfg or load_aog_config()
    net = cfg["network"]
    m = net["aog_transport_hours"]
    st = [net["hub"]] + list(net["outstations"])
    aog = {}
    for a in st:
        for b in st:
            v = m.get(a, {}).get(b, m.get(b, {}).get(a))
            aog[(a, b)] = float(v)
    nz = [v for v in aog.values() if v > 0]
    lo, hi = cfg["economics"]["emergency_logistics_aed"]
    # same linear distance scaling the engine uses for emergency/lateral shipments
    em = {k: (0.0 if v == 0 else lo + (hi - lo) * (v - min(nz)) / max(1e-9, max(nz) - min(nz))) for k, v in aog.items()}
    rt = net["routine_transport_days"]
    slack_sd = float(acfg["routine_option"]["slack_sd"])
    shops = cfg["repair_shops"]
    transit = {s: float(shops["vendor_transit_days_from_auh"].get(s, 0)) * 24 for s in shops if isinstance(shops[s], dict)}
    margin = float(cfg["engine"].get("deferred_margin_h", 24))
    return Network(tuple(st), net["hub"], aog, em, rt["mean"] * 24, (rt["mean"] + slack_sd * rt["sd"]) * 24 + margin,
                   float(cfg["economics"]["routine_shipment_aed_per_line"]), transit)


# ---------------------------------------------------------------------------------------------
# point-in-time stock ledger
class Ledger:
    """Serviceable on-hand per (pn, station) reconstructed from inventory_transactions.

    SIM-9: ``qty_delta`` tracks serviceable on-hand only, so the running sum is on-hand.
    """

    def __init__(self, tx: pd.DataFrame):
        tx = tx.sort_values(["t_h", "txn_id"], kind="mergesort")
        self._by = {}
        for (pn, st), g in tx.groupby(["pn", "station"], sort=False):
            self._by[(pn, st)] = (g.t_h.to_numpy(np.int64), g.txn_id.to_numpy(np.int64),
                                  np.cumsum(g.qty_delta.to_numpy(np.int64)))

    def on_hand(self, pn: str, station: str, t: int, before_txn: int | None = None) -> int:
        """On-hand from all transactions with t_h < t (plus, if given, same-hour txns with id < before_txn)."""
        rec = self._by.get((pn, station))
        if rec is None:
            return 0
        th, ids, cum = rec
        i = int(np.searchsorted(th, t, side="left"))
        if before_txn is not None:
            j = int(np.searchsorted(th, t, side="right"))
            i += int(np.sum(ids[i:j] < before_txn))
        return int(cum[i - 1]) if i > 0 else 0


@dataclass
class HistoryView:
    """Tables + derived indexes, built once."""
    t: dict
    net: Network
    cfg: dict
    acfg: dict
    ledger: Ledger = field(init=False)
    parts: pd.DataFrame = field(init=False)
    arch: dict = field(init=False)

    def __post_init__(self):
        self.ledger = Ledger(self.t["inventory_transactions"])
        self.parts = self.t["part_master"].set_index("pn")
        self.arch = dict(zip(self.t["aircraft_master"]["tail"], self.t["aircraft_master"].archetype))
        tx = self.t["inventory_transactions"]
        cond = tx[tx.txn_type == "CONDEMN"]
        self.condemn_h = {int(r[2:]): int(h) for r, h in zip(cond.ref_id.astype(str), cond.t_h)}
        tr = self.t["transfers"]
        self.tid_req = {int(a): (None if pd.isna(b) else int(b)) for a, b in zip(tr.transfer_id, tr.request_id)}

    @property
    def end_h(self) -> int:
        return (int(self.acfg["history"]["weeks"][1]) + 1) * HOURS_PER_WEEK

    def penalty(self, tail) -> float:
        a = self.arch.get(tail, "narrowbody")
        return float(self.cfg["economics"]["aog_penalty_aed_per_hour"][a])

    # -- as-of views ------------------------------------------------------------------------
    def request_cutoff(self, rid: int, need_h: int) -> int | None:
        """txn_id of the first same-hour transaction caused by this request (its own U/S booking,
        local issue or emergency shipment). Stock is read *before* it."""
        tx = self.t["inventory_transactions"]
        same = tx[tx.t_h == need_h]
        own = [int(i) for i, r in zip(same.txn_id, same.ref_id) if not pd.isna(r) and (
            str(r) == str(rid) or (str(r).startswith("T") and str(r)[1:].isdigit()
                                   and self.tid_req.get(int(str(r)[1:])) == rid))]
        return min(own) if own else None

    def stock_at(self, pn, t, before_txn=None) -> dict:
        return {s: self.ledger.on_hand(pn, s, t, before_txn) for s in self.net.stations}

    def kit_commitments(self, pn, station, t, horizon_h=None) -> int:
        """Scheduled quantity already known at t and not yet due: kit lines (notice_h <= t < due_h) and
        wear-planned removals (known_h <= t < need_h)."""
        ms = self.t["maintenance_schedule"]
        m = ms[(ms.pn == pn) & (ms.station == station) & (ms.notice_h <= t) & (ms.due_h > t)]
        if horizon_h is not None:
            m = m[m.due_h <= t + horizon_h]
        mr = self.t["material_requests"]
        pl = mr[(mr.source == "planned_removal") & (mr.pn == pn) & (mr.station == station)
                & (mr.known_h <= t) & (mr.need_h > t)]       # (v2) wear-planned changes are reserved like kits
        if horizon_h is not None:
            pl = pl[pl.need_h <= t + horizon_h]
        return int(m.qty.sum()) + int(pl.qty.sum())

    def open_ros(self, pn, t) -> pd.DataFrame:
        """Repair orders at a shop at t, not returned and not yet known to be condemned."""
        ro = self.t["repair_orders"]
        r = ro[(ro.pn == pn) & (ro.shop_in_h < t)].copy()
        r = r[r.return_h.isna() | (r.return_h > t)]
        ch = r.ro_id.map(lambda i: self.condemn_h.get(int(i), math.inf))
        r = r[ch > t]
        return r.sort_values(["quoted_due_h", "ro_id"])

    def open_pos(self, pn, t) -> pd.DataFrame:
        po = self.t["purchase_orders"]
        p = po[(po.pn == pn) & (po.order_h < t)]
        p = p[p.receipt_h.isna() | (p.receipt_h > t)]
        return p.sort_values(["due_h", "po_id"])

    def busy_donors(self, pn, t) -> set:
        """Tails robbed of this PN before t and not yet reinstated (status known at t)."""
        rb = self.t.get("aog_robberies")
        if rb is None or rb.empty:
            return set()
        r = rb[(rb.pn == pn) & (rb.robbed_h < t)]
        r = r[r.reinstated_h.isna() | (r.reinstated_h >= t)]
        return set(r.donor_tail)

    def d0_demand_rate(self, pn, station, t, lookback_weeks) -> tuple[int, float]:
        """D0 requests for pn at station in the lookback window before t -> (count, per hour)."""
        mr = self.t["material_requests"]
        w = lookback_weeks * HOURS_PER_WEEK
        lo = max(0, t - w)
        n = int(((mr.pn == pn) & (mr.station == station) & (mr.deadline_class == "D0")
                 & (mr.need_h >= lo) & (mr.need_h < t)).sum())
        span = max(1, t - lo)
        return n, n / span


def poisson_protection(rate_per_h: float, hours: float, service_level: float) -> int:
    """Smallest n with P(Poisson(rate*hours) <= n-1) >= service_level (0 if there is no demand)."""
    mu = rate_per_h * hours
    if mu <= 0:
        return 0
    cdf, pmf = 0.0, math.exp(-mu)
    for n in range(1, 1000):
        cdf += pmf                 # P(X <= n-1)
        if cdf >= service_level:
            return n
        pmf *= mu / n
    return 1000


def deadline_hours(dc: str):
    """Rectification window in hours; None for NONE (servicing fluids never drive AOG)."""
    v = DEADLINE_HOURS[dc]
    return None if v is None else int(v)


def fitting_mid_h(cfg: dict, part_class: str) -> float:
    """Midpoint of engine.fitting_hours for the class (fitting / ops check / release to service)."""
    v = cfg["engine"]["fitting_hours"][part_class]
    return float(sum(v) / 2) if isinstance(v, list) else float(v)


@lru_cache(maxsize=1)
def default_view() -> HistoryView:
    return HistoryView(load_history(), network_from_config(), load_config(), load_aog_config())
