"""Analytic material-delay model used by the greedy optimiser (v2: METRIC-lite + the v2 AOG routes).

For one PN with stations j = 0 (hub, AUH) .. J-1 and Poisson unit demand rates lambda_{j,c} per day by
rectification window c in {D0, D3, D10} (class NONE carries no downtime value and is dropped upstream):

Hub (resupply time T days; rotables: network repair pipeline sum_j lambda_j T_j / lambda_net, C/E: lead time)
    X0 ~ Poisson(lambda_net * T)                 (Palm; C/E: lead-time demand under (s,S))
    Palm's TOTAL hub level y0 = base_stock + loop units seeded by the engine (POL-6 / V2-POL-3)
    A0 = P(X0 <= y0 - 1)  (immediate fill, V2-SIM-10),  EBO0 = E[(X0 - y0)^+],  W0 = EBO0 / lambda_net
Outstation j: routine resupply from AUH in t_route + W0 days (METRIC), Aj = P(Xj <= y_j - 1)

What an aircraft need sees (v2 engine semantics, V2-SIM-5/6/7/14):
    * outstation miss while AUH has stock -> emergency transfer, delay = aog_transport_hours(AUH->j)
    * AUH out of stock -> the need waits for own supply W (exponential, EBO-implied mean
      m = W0 / (1 - A0)) OR an AOG route, whichever comes first. Routes (public `aog_sourcing`, via
      gnm.policy.policies.route_expectation): hub = robbery -> exchange/loan; outstation = local borrow
      -> exchange/loan; C/E = local buy; retried every retry_hours. The route's expected wait R caps W.
    * downtime counts only if the part is late: the interval is [need + window, fill + fitting/RTS]
Per stock-out of a need with window d (exponential W, route wait R treated as deterministic):
    late hours  E[(min(W, R) - d)^+] = m (exp(-d/m) - exp(-R/m))   if d < R, else 0
    P(late)     = exp(-d/m)                                          if d < R, else 0
    downtime    = late hours + P(late) x fitting hours;  events = P(late)
    route used  = P(W > max(0, d - R - 24 h))   (deferred needs trigger the route at window - R - 24 h)
Cost (AED/yr) = downtime h x hourly rate + events x fixed cost per event + routes x route fee, with the
PN's own (single-archetype, or fleet-mix) rate and event cost.

Approximations (internal development notes (kept privately)): infinite-server repair, unit demand, no laterals or
rebalancing (P2 has both, so the model is conservative there), exponential own-supply wait, a
deterministic route wait, merged events approximated per need. v2 has no outright AOG buy, so the v1
"expedite self-healing" drift is OFF by default (`heal=False`). The event simulation is the judge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

CLASSES = ("D0", "D3", "D10")
DEADLINE_H = np.array([0.0, 72.0, 240.0])


def ebo_vec(y: np.ndarray, mu: float) -> np.ndarray:
    """E[(X - y)^+] for X ~ Poisson(mu), vectorised over integer y >= 0.

    Identity: E[(X-y)^+] = mu P(X >= y) - y P(X >= y+1)."""
    y = np.asarray(y, dtype=float)
    if mu <= 0:
        return np.zeros_like(y)
    return mu * stats.poisson.sf(y - 1, mu) - y * stats.poisson.sf(y, mu)


def avail_vec(y: np.ndarray, mu: float) -> np.ndarray:
    """P(X < y) = P(X <= y - 1): immediate fill under base stock y (V2-SIM-10)."""
    y = np.asarray(y, dtype=float)
    if mu <= 0:
        return (y > 0).astype(float)
    return stats.poisson.cdf(y - 1, mu)


def poisson_fill_quantile(mu: float, p: float, s_max: int = 500) -> int:
    """Smallest S with P(Poisson(mu) <= S - 1) >= p (fill definition)."""
    if mu <= 0:
        return 0
    S = 0
    while S < s_max and avail_vec(np.array([S]), mu)[0] < p:
        S += 1
    return S


def sS_ebo_avail(s: int, S: int, mu: float) -> tuple[float, float]:
    """Time-average EBO and fill under (s, S): inventory position ~ uniform on {s+1..S}."""
    lo = max(s + 1, 0)
    hi = max(S, lo)
    y = np.arange(lo, hi + 1)
    return float(ebo_vec(y, mu).mean()), float(avail_vec(y, mu).mean())


def late_terms(d_h: np.ndarray, m_h: float, cap_h: float):
    """(E[(min(W,cap) - d)^+], P(min(W,cap) > d)) for W ~ Exp(mean m), deterministic cap."""
    d_h = np.asarray(d_h, dtype=float)
    if m_h <= 0 or cap_h <= 0:
        return np.zeros_like(d_h), np.zeros_like(d_h)
    hrs = m_h * (np.exp(-d_h / m_h) - math.exp(-cap_h / m_h))
    ok = d_h < cap_h
    return np.where(ok, np.maximum(hrs, 0.0), 0.0), np.where(ok, np.exp(-d_h / m_h), 0.0)


def g_wait(d_h: np.ndarray, m_h: float, cap_h: float) -> np.ndarray:
    """E[(min(W, cap) - d)^+] for W ~ Exp(mean m) (kept for the v1 tests / API)."""
    return late_terms(d_h, m_h, cap_h)[0]


@dataclass
class ItemModel:
    pn: str
    part_class: str                  # R / E / C
    stations: tuple                  # hub first
    rates: np.ndarray                # (J, 3) units/day by window class
    resupply_days: float             # R: network pipeline days; C/E: hub lead time
    work_days: float                 # R: shop work days inside the pipeline (TAT lever)
    route_days: float                # AUH -> outstation routine transport
    transport_h: np.ndarray          # (J,) AOG transport hours AUH -> j (hub 0)
    cap_days_class: float = 5.0      # v1 only (expedite cap); unused in v2
    lead_time_days: float = 60.0
    expedite_factor: float = 0.5
    unit_cost: float = 0.0
    penalty_per_h: float = 20000.0   # hourly downtime rate (AED/h)
    q: np.ndarray = field(default=None)   # (J,) order quantity S - s (rotables: 1)
    heal: bool = False               # v1 expedite self-healing drift (v2: no outright AOG buy -> off)
    warmup_weeks: float = 26.0
    kpi_weeks: float = 52.0
    heal_dt_weeks: float = 2.0
    loop_units: int = 0              # rotable units seeded in the repair loop at t0, on top of base_stock
    event_cost: float = 0.0          # fixed cost per downtime event (AED)
    fitting_h: float = 0.0           # fitting / release-to-service hours added to every late need
    route_wait_h: np.ndarray = field(default=None)   # (J,) expected AOG-route wait when AUH is out (h)
    route_fee: np.ndarray = field(default=None)      # (J,) expected AOG-route fee per use (AED)

    def __post_init__(self):
        J = len(self.stations)
        self.rates = np.asarray(self.rates, float)
        self.transport_h = np.asarray(self.transport_h, float)
        if self.q is None:
            self.q = np.ones(J, dtype=int)
        self.q = np.maximum(np.asarray(self.q, dtype=int), 1)
        if self.route_wait_h is None:     # v1 behaviour: the expedite cap acts as the "route"
            self.route_wait_h = np.full(J, 24.0 * min(self.expedite_factor * self.lead_time_days,
                                                      self.cap_days_class))
        if self.route_fee is None:
            self.route_fee = np.zeros(J)
        self.route_wait_h = np.asarray(self.route_wait_h, float)
        self.route_fee = np.asarray(self.route_fee, float)
        self._cache = {}

    @property
    def is_rotable(self) -> bool:
        return self.part_class == "R"

    @property
    def lam_net(self) -> float:
        return float(self.rates.sum())

    def hub_mu(self, tat_mult: float = 1.0, lead_mult: float = 1.0) -> float:
        if self.is_rotable:
            T = self.resupply_days - self.work_days + self.work_days * tat_mult
        else:
            T = self.resupply_days * lead_mult
        return self.lam_net * max(T, 0.0)

    def _rates(self, S: np.ndarray, tat_mult: float, lead_mult: float) -> tuple:
        """(downtime h/yr, events/yr, route uses/yr, route fees AED/yr) at integer levels S (static)."""
        key = ("r", S.tobytes(), tat_mult, lead_mult)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        lam_net = self.lam_net
        if lam_net <= 0:
            return 0.0, 0.0, 0.0, 0.0
        lam = self.rates.sum(axis=1)
        mu0 = self.hub_mu(tat_mult, lead_mult)
        y0 = int(S[0]) + (int(self.loop_units) if self.is_rotable else 0)
        ebo0, a0 = sS_ebo_avail(y0 - int(self.q[0]), y0, mu0)
        W0 = ebo0 / lam_net
        pso = 1.0 - a0
        m_h = 24.0 * W0 / pso if pso > 1e-12 else 0.0
        hours = events = routes = fees = 0.0

        def stockout(rate_vec, j):
            """Aircraft needs (per class, per day) that meet an AUH stock-out and wait W vs route j."""
            R = float(self.route_wait_h[j])
            lh, pl = late_terms(DEADLINE_H, m_h, R)
            trig = np.maximum(DEADLINE_H - R - 24.0, 0.0)
            pr = np.exp(-trig / m_h) if m_h > 0 else np.zeros(3)
            return (float(rate_vec @ (lh + pl * self.fitting_h)), float(rate_vec @ pl), float(rate_vec @ pr))

        h, e, r = stockout(self.rates[0] * pso, 0)
        hours, events, routes, fees = h, e, r, r * self.route_fee[0]
        for j in range(1, len(self.stations)):
            if lam[j] <= 0:
                continue
            _, aj = sS_ebo_avail(int(S[j] - self.q[j]), int(S[j]), lam[j] * (self.route_days + W0))
            miss = self.rates[j] * (1.0 - aj)
            h, e, r = stockout(miss * pso, j)
            hours += h
            events += e
            routes += r
            fees += r * self.route_fee[j]
            tr = self.transport_h[j]                      # AUH has stock: emergency transfer
            late = (tr > DEADLINE_H).astype(float)
            hours += a0 * float(miss @ (np.maximum(tr - DEADLINE_H, 0.0) + late * self.fitting_h))
            events += a0 * float(miss @ late)
        out = (365.0 * hours, 365.0 * events, 365.0 * routes, 365.0 * fees)
        if len(self._cache) < 50000:
            self._cache[key] = out
        return out

    def aog_hours(self, S: np.ndarray, tat_mult: float = 1.0, lead_mult: float = 1.0) -> float:
        """Expected material-related downtime hours per year at station levels S."""
        return self.evaluate(S, tat_mult, lead_mult)[0]

    def evaluate(self, S: np.ndarray, tat_mult: float = 1.0, lead_mult: float = 1.0) -> tuple[float, float]:
        """(downtime h/yr, mean extra rotable units from the v1 self-healing drift; 0 when heal is off)."""
        S = np.asarray(S, dtype=int)
        if not (self.is_rotable and self.heal):
            return self._rates(S, tat_mult, lead_mult)[0], 0.0
        key = ("e", S.tobytes(), tat_mult, lead_mult)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        dt = self.heal_dt_weeks / 52.0
        n_warm = int(round(self.warmup_weeks / self.heal_dt_weeks))
        n_kpi = int(round(self.kpi_weeks / self.heal_dt_weeks))
        y, Sl, aog, extra = float(S[0]), S.copy(), 0.0, 0.0
        for k in range(n_warm + n_kpi):
            lo = int(math.floor(y))
            f = y - lo
            Sl[0] = lo
            a_lo, _, b_lo, _ = self._rates(Sl, tat_mult, lead_mult)
            Sl[0] = lo + 1
            a_hi, _, b_hi, _ = self._rates(Sl, tat_mult, lead_mult) if f > 1e-9 else (a_lo, 0, b_lo, 0)
            a, b = (1 - f) * a_lo + f * a_hi, (1 - f) * b_lo + f * b_hi
            if k >= n_warm:
                aog += a * dt
                extra += (y - S[0]) * dt
            y += b * dt
        out = (aog / (n_kpi * dt), extra / (n_kpi * dt))
        if len(self._cache) < 50000:
            self._cache[key] = out
        return out

    def cost(self, S: np.ndarray, tat_mult: float = 1.0, lead_mult: float = 1.0) -> float:
        """Expected annual material shortage cost (AED/yr): downtime h x rate + events x fixed cost + route fees."""
        S = np.asarray(S, dtype=int)
        if self.is_rotable and self.heal:
            return self.penalty_per_h * self.aog_hours(S, tat_mult, lead_mult)
        h, e, _, fee = self._rates(S, tat_mult, lead_mult)
        return self.penalty_per_h * h + self.event_cost * e + fee


def build_items(demand: "pd.DataFrame", world, base_policy, penalty: dict[str, float],
                include_count_parts: bool = True, value_classes=("D0", "D3"), heal: bool = False,
                warmup_weeks: float = 26.0, kpi_weeks: float = 52.0,
                loop_units: dict | None = None, v2_routes: bool = True) -> dict[str, ItemModel]:
    """ItemModels for every rotable PN (and C/E PNs with D0/D3 demand) from the demand-input table.

    Optional demand columns used when present: aog_penalty_aed_h, aog_event_cost_aed, nb_share (rate-weighted
    per PN; from the forecast table). Otherwise the penalty dict and the applicability archetype mix are used."""
    import pandas as pd  # noqa: F401
    cfg = world.cfg
    hub = cfg["network"]["hub"]
    stations = [hub] + [s for s in world.stations.station.tolist() if s != hub]
    sidx = {s: i for i, s in enumerate(stations)}
    route = float(cfg["network"]["routine_transport_days"]["mean"])
    trans = world.aog_hours.loc[hub, stations].to_numpy(float)
    caps = cfg["engine"].get("expedite_max_days", {"C": 2, "E": 3, "R": 5})
    efac = float(cfg["engine"].get("expedite_lead_time_factor", 0.5))
    fit_cfg = cfg["engine"].get("fitting_hours", {})
    ev_cfg = cfg["economics"].get("aog_event_cost_aed") or {}
    parts = world.parts.set_index("pn")
    sp = base_policy.stock_params.set_index(["pn", "station"])
    nb_share_w = _nb_share_from_applicability(world)
    items = {}
    for pn, g in demand.groupby("pn", sort=True):
        pc = parts.loc[pn, "part_class"]
        if pc != "R":
            if not include_count_parts:
                continue
            if g[g.deadline_class.isin(value_classes)].rate_per_day.sum() <= 0:
                continue
        rates = np.zeros((len(stations), 3))
        for r in g.itertuples(index=False):
            if r.station in sidx and r.deadline_class in CLASSES:
                rates[sidx[r.station], CLASSES.index(r.deadline_class)] += float(r.rate_per_day)
        if rates.sum() <= 0:
            continue
        q = np.ones(len(stations), dtype=int)
        if pc != "R":
            for st, j in sidx.items():
                if (pn, st) in sp.index:
                    row = sp.loc[(pn, st)]
                    q[j] = max(1, int(row["S"]) - int(row["s"]))
        w = g.rate_per_day.to_numpy(float)
        wsum = w.sum() if w.sum() > 0 else 1.0
        wavg = lambda col, dflt: float((g[col].to_numpy(float) * w).sum() / wsum) if col in g else dflt  # noqa: E731
        nb = wavg("nb_share", nb_share_w.get(pn, 0.5))
        pen = wavg("aog_penalty_aed_h", float(penalty.get(pn, 20000.0)))
        evc = wavg("aog_event_cost_aed", nb * float(ev_cfg.get("narrowbody", 0.0))
                   + (1 - nb) * float(ev_cfg.get("widebody", 0.0)))
        if pc == "R":   # network pipeline mean = sum_j lambda_j T_j / lambda_net
            T = float((g.pipeline_days.to_numpy(float) * w).sum() / wsum)
        else:
            T = float(g.lead_time_days.iloc[0])
        fit = fit_cfg.get(pc, 0.0)
        fit_h = float(np.mean(fit)) if isinstance(fit, (list, tuple)) else float(fit or 0.0)
        uc = float(g.unit_cost.iloc[0])
        rw = rf = None
        if v2_routes and "aog_sourcing" in cfg:
            from gnm.policy.policies import route_expectation
            rw, rf = np.zeros(len(stations)), np.zeros(len(stations))
            for st, j in sidx.items():
                re_ = route_expectation(world, pc, st, nb, uc)
                rw[j], rf[j] = re_["wait_h"], re_["fee_aed"]
        first = g.iloc[0]
        items[pn] = ItemModel(
            pn=pn, part_class=pc, stations=tuple(stations), rates=rates, resupply_days=T,
            work_days=float(first.work_days) if pc == "R" and np.isfinite(first.work_days) else 0.0,
            route_days=route, transport_h=trans, cap_days_class=float(caps.get(pc, 5)),
            lead_time_days=float(first.lead_time_days), expedite_factor=efac, unit_cost=uc,
            penalty_per_h=pen, q=q, heal=heal, warmup_weeks=warmup_weeks, kpi_weeks=kpi_weeks,
            loop_units=int((loop_units or {}).get(pn, 0)) if pc == "R" else 0,
            event_cost=evc if v2_routes else 0.0, fitting_h=fit_h if v2_routes else 0.0,
            route_wait_h=rw, route_fee=rf)
    return items


def _nb_share_from_applicability(world) -> dict:
    ac = world.aircraft
    n = ac.archetype.value_counts().to_dict()
    out = {}
    for pn, g in world.applicability.groupby("pn"):
        w = {a: n.get(a, 0) * q for a, q in zip(g.archetype, g.qty_per_aircraft)}
        tot = sum(w.values())
        out[pn] = w.get("narrowbody", 0.0) / tot if tot else 0.5
    return out


def base_levels(items: dict[str, ItemModel], base_policy) -> dict[str, np.ndarray]:
    """Station levels of the base policy in model terms: rotables base_stock, C/E order-up-to S."""
    sp = base_policy.stock_params.set_index(["pn", "station"])
    out = {}
    for pn, it in items.items():
        lv = np.zeros(len(it.stations), dtype=int)
        for j, st in enumerate(it.stations):
            if (pn, st) in sp.index:
                row = sp.loc[(pn, st)]
                lv[j] = int(row["base_stock"]) if it.is_rotable else max(int(row["S"]), 0)
        out[pn] = lv
    return out
