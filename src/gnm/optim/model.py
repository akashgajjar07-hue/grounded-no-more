"""Analytic material-delay model used by the greedy optimiser (METRIC-lite, hub + outstations).

For one PN with stations j = 0 (hub, AUH) .. J-1 and Poisson unit demand rates lambda_{j,c} per day by
deadline class c in {D0, D3, D10}:

Hub (resupply time T days; rotables: repair pipeline, C/E: purchase lead time)
    X0 ~ Poisson(mu0 = lambda_net * T)        (Palm; for C/E the lead-time demand)
    EBO0 = E[(X0 - y)^+],  A0 = P(X0 < y)     averaged over y in {s0+1..S0} (rotables: y = S0)
    W0   = EBO0 / lambda_net                  mean wait per hub demand (Little's law), days
Outstation j (routine resupply from AUH, t_route days, delayed by the hub wait — METRIC)
    Xj ~ Poisson(lambda_j * (t_route + W0)),  Aj = P(Xj < y_j)
Delay seen by aircraft
    * outstation miss, hub has stock  -> emergency transfer, delay = aog_transport_hours(AUH->j)
    * hub stock-out (aircraft-facing demand: hub demand + outstation misses) -> backorder wait W.
      W is modelled as exponential with the EBO-implied conditional mean m = W0 / (1 - A0) and is
      truncated at the expedite cap (engine: expedited PO in min(0.5 x lead, cap by class) days).
AOG hours by deadline class (the D3/D10 approximation): a requirement with deadline d only grounds
the aircraft for the part of the wait beyond d, so per stock-out
    G_c = E[(min(W, cap) - d_c)^+] = m (exp(-d_c/m) - exp(-cap/m))   for d_c < cap, else 0
D0 (d = 0) counts the whole (capped) wait; D3/D10 count only the probability-weighted excess beyond
72/240 h. Transport delay counts only where it exceeds the deadline (in practice D0 only).

Expedite self-healing (rotables): see ItemModel.evaluate — uncovered backorders buy units that stay in
the float, so the hub level drifts up during a run; the model integrates that drift.

Expected AOG hours/yr (static, at fixed levels) = 365 * [ sum_c lambda_{0,c} (1-A0) G_c
                               + sum_j sum_c lambda_{j,c} (1-Aj) ( (1-A0) (G_c + [c=D0] h_j) + A0 (h_j - d_c)^+ ) ]
Delay cost = AOG hours x the PN's AOG penalty (archetype mix of its applicability).

Approximations (documented in docs/agent_notes/optimiser.md): infinite-server repair (no queueing
beyond what the history pipeline already contains), unit demand, no lateral transfers, exponential
residual wait, kits treated as ordinary demand. The event simulation is the judge.
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
    """P(X < y)."""
    y = np.asarray(y, dtype=float)
    if mu <= 0:
        return (y > 0).astype(float)
    return stats.poisson.cdf(y - 1, mu)


def sS_ebo_avail(s: int, S: int, mu: float) -> tuple[float, float]:
    """Time-average EBO and ready rate under (s, S): inventory position ~ uniform on {s+1..S}."""
    lo = max(s + 1, 0)
    hi = max(S, lo)
    y = np.arange(lo, hi + 1)
    return float(ebo_vec(y, mu).mean()), float(avail_vec(y, mu).mean())


def g_wait(d_h: np.ndarray, m_h: float, cap_h: float) -> np.ndarray:
    """E[(min(W, cap) - d)^+] for W ~ Exp(mean m)."""
    d_h = np.asarray(d_h, dtype=float)
    if m_h <= 0 or cap_h <= 0:
        return np.zeros_like(d_h)
    out = m_h * (np.exp(-d_h / m_h) - math.exp(-cap_h / m_h))
    return np.where(d_h < cap_h, np.maximum(out, 0.0), 0.0)


@dataclass
class ItemModel:
    pn: str
    part_class: str                  # R / E / C
    stations: tuple                  # hub first
    rates: np.ndarray                # (J, 3) units/day by deadline class
    resupply_days: float             # R: pipeline days; C/E: hub lead time
    work_days: float                 # R: shop work days inside the pipeline
    route_days: float                # AUH -> outstation routine transport
    transport_h: np.ndarray          # (J,) AOG transport hours AUH -> j (hub 0)
    cap_days_class: float            # expedite cap for the class
    lead_time_days: float            # purchase lead time (expedite = min(0.5 x lead, cap))
    expedite_factor: float
    unit_cost: float
    penalty_per_h: float
    q: np.ndarray = field(default=None)   # (J,) order quantity S - s (rotables: 1)
    heal: bool = True                # model expedite self-healing of the rotable float
    warmup_weeks: float = 26.0
    kpi_weeks: float = 52.0
    heal_dt_weeks: float = 2.0
    loop_units: int = 0              # POL-6/OPT-9: rotable units the engine seeds in the repair loop at t0, on top
                                     # of base_stock; Palm's total hub level = base_stock + loop_units

    def __post_init__(self):
        self.rates = np.asarray(self.rates, float)
        self.transport_h = np.asarray(self.transport_h, float)
        if self.q is None:
            self.q = np.ones(len(self.stations), dtype=int)
        self.q = np.maximum(np.asarray(self.q, dtype=int), 1)
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

    def cap_h(self, lead_mult: float = 1.0) -> float:
        return 24.0 * min(self.expedite_factor * self.lead_time_days * lead_mult, self.cap_days_class)

    def _rates(self, S: np.ndarray, tat_mult: float, lead_mult: float) -> tuple[float, float]:
        """(expected AOG hours / yr, expected expedite purchases / yr) at integer levels S (static)."""
        key = ("r", S.tobytes(), tat_mult, lead_mult)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        lam_net = self.lam_net
        if lam_net <= 0:
            return 0.0, 0.0
        lam = self.rates.sum(axis=1)
        mu0 = self.hub_mu(tat_mult, lead_mult)
        y0 = int(S[0]) + (int(self.loop_units) if self.is_rotable else 0)
        ebo0, a0 = sS_ebo_avail(y0 - int(self.q[0]), y0, mu0)
        W0 = ebo0 / lam_net
        pso = 1.0 - a0
        m_h = 24.0 * W0 / pso if pso > 1e-12 else 0.0
        cap = self.cap_h(lead_mult)
        G = g_wait(DEADLINE_H, m_h, cap)
        # expedite fires when a backordered aircraft need is not covered within the expedite time:
        # D0/D3 at once (P(W > cap)), D10 just in time at deadline - cap - 24 h (P(W > deadline - 24 h))
        t_buy = np.maximum(cap, DEADLINE_H - 24.0)
        B = np.exp(-t_buy / m_h) if m_h > 0 else np.zeros(3)
        air = self.rates[0].copy()
        total = pso * float(self.rates[0] @ G)
        for j in range(1, len(self.stations)):
            if lam[j] <= 0:
                continue
            _, aj = sS_ebo_avail(int(S[j] - self.q[j]), int(S[j]), lam[j] * (self.route_days + W0))
            miss = self.rates[j] * (1.0 - aj)
            air += miss
            h = self.transport_h[j]
            total += pso * float(miss @ G) + pso * miss[0] * h + a0 * float(miss @ np.maximum(h - DEADLINE_H, 0.0))
        out = (365.0 * total, 365.0 * pso * float(air @ B))
        if len(self._cache) < 50000:
            self._cache[key] = out
        return out

    def aog_hours(self, S: np.ndarray, tat_mult: float = 1.0, lead_mult: float = 1.0) -> float:
        """Expected material AOG hours per year (KPI window) at station levels S (order-up-to; s = S - q)."""
        return self.evaluate(S, tat_mult, lead_mult)[0]

    def evaluate(self, S: np.ndarray, tat_mult: float = 1.0, lead_mult: float = 1.0) -> tuple[float, float]:
        """(AOG h/yr, mean extra rotable units bought by the AOG desk during the KPI window).

        Expedite self-healing (rotables): every uncovered aircraft backorder triggers an expedited
        purchase, and the unit stays in the float after the repaired core returns (base-stock never
        sells surplus). The hub level therefore drifts up from the base stock during a run. The model
        integrates that drift over the run (weeks 0..warm-up+KPI of the run, step `heal_dt_weeks`) and
        averages AOG over the KPI window. C/E have no drift (their (s,S) position absorbs expedites)."""
        S = np.asarray(S, dtype=int)
        key = ("e", S.tobytes(), tat_mult, lead_mult)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        if not (self.is_rotable and self.heal):
            out = (self._rates(S, tat_mult, lead_mult)[0], 0.0)
        else:
            dt = self.heal_dt_weeks / 52.0
            n_warm = int(round(self.warmup_weeks / self.heal_dt_weeks))
            n_kpi = int(round(self.kpi_weeks / self.heal_dt_weeks))
            y = float(S[0])
            Sl = S.copy()
            aog = extra = 0.0
            for k in range(n_warm + n_kpi):
                lo = int(math.floor(y))
                f = y - lo
                Sl[0] = lo
                a_lo, b_lo = self._rates(Sl, tat_mult, lead_mult)
                if f > 1e-9:
                    Sl[0] = lo + 1
                    a_hi, b_hi = self._rates(Sl, tat_mult, lead_mult)
                else:
                    a_hi, b_hi = a_lo, b_lo
                a, b = (1 - f) * a_lo + f * a_hi, (1 - f) * b_lo + f * b_hi
                if k >= n_warm:
                    aog += a * dt
                    extra += (y - S[0]) * dt
                y += b * dt
            T = n_kpi * dt
            out = (aog / T, extra / T)
        if len(self._cache) < 50000:
            self._cache[key] = out
        return out

    def cost(self, S: np.ndarray, **kw) -> float:
        """Expected annual material-delay cost (AED/yr)."""
        return self.penalty_per_h * self.aog_hours(S, **kw)


def build_items(demand: "pd.DataFrame", world, base_policy, penalty: dict[str, float],
                include_count_parts: bool = True, value_classes=("D0", "D3"), heal: bool = True,
                warmup_weeks: float = 26.0, kpi_weeks: float = 52.0,
                loop_units: dict | None = None) -> dict[str, ItemModel]:
    """ItemModels for every rotable PN (and C/E PNs with D0/D3 demand) from the demand-input table."""
    cfg = world.cfg
    hub = cfg["network"]["hub"]
    stations = [hub] + [s for s in world.stations.station.tolist() if s != hub]
    sidx = {s: i for i, s in enumerate(stations)}
    route = float(cfg["network"]["routine_transport_days"]["mean"])
    trans = world.aog_hours.loc[hub, stations].to_numpy(float)
    caps = cfg["engine"]["expedite_max_days"]
    efac = float(cfg["engine"]["expedite_lead_time_factor"])
    parts = world.parts.set_index("pn")
    sp = base_policy.stock_params.set_index(["pn", "station"])
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
        q = np.ones(len(stations), dtype=int)
        if pc != "R":
            for st, j in sidx.items():
                if (pn, st) in sp.index:
                    row = sp.loc[(pn, st)]
                    q[j] = max(1, int(row["S"]) - int(row["s"]))
        first = g.iloc[0]
        items[pn] = ItemModel(
            pn=pn, part_class=pc, stations=tuple(stations), rates=rates,
            resupply_days=float(first.pipeline_days if pc == "R" else first.lead_time_days),
            work_days=float(first.work_days) if pc == "R" and not np.isnan(first.work_days) else 0.0,
            route_days=route, transport_h=trans, cap_days_class=float(caps[pc]),
            lead_time_days=float(first.lead_time_days), expedite_factor=efac,
            unit_cost=float(first.unit_cost), penalty_per_h=float(penalty.get(pn, 20000.0)), q=q,
            heal=heal, warmup_weeks=warmup_weeks, kpi_weeks=kpi_weeks,
            loop_units=int((loop_units or {}).get(pn, 0)) if pc == "R" else 0)
    return items


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
