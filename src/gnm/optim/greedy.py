"""Greedy marginal allocation (Sherbrooke-style marginal analysis) for the Readiness Frontier.

Each step adds the unit (pn, station) with the largest reduction in expected annual material-delay
cost per AED of capital; the downward sweep removes the unit with the smallest cost increase per AED.

Optimality. If the objective is separable over items, f(x) = sum_i f_i(x_i), each f_i is convex
and non-increasing in its integer stock x_i (EBO(S) is convex in S for Poisson pipelines), and
capital is linear, then every greedy breakpoint x^k minimises the Lagrangian f(x) + lambda_k c.x with
lambda_k the ratio of the last increment taken, so x^k is optimal for its own capital c.x^k
(Fox 1966; Sherbrooke, *Optimal Inventory Modeling of Systems*, 2004, ch. 2). tests/test_optim_greedy.py
checks this against brute force on a toy problem.

Here the objective is NOT fully separable: a hub unit shortens every outstation's resupply (METRIC
coupling) and the expedite cap / deadline transform makes f_i only approximately convex. The greedy
path is therefore a HEURISTIC; the event simulation judges every candidate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from gnm.optim.model import ItemModel


# ---------------------------------------------------------------------------------- generic (toy)
def greedy_separable(cost_fns, unit_costs, max_units, budget: float):
    """Generic greedy on a separable problem. cost_fns[i](x) -> objective of item i at x units.

    Returns a list of breakpoints (capital, objective, allocation tuple), starting at x = 0."""
    n = len(cost_fns)
    x = [0] * n
    cap = 0.0
    obj = float(sum(f(0) for f in cost_fns))
    path = [(cap, obj, tuple(x))]
    while True:
        best = None
        for i in range(n):
            if x[i] >= max_units[i] or cap + unit_costs[i] > budget + 1e-9:
                continue
            gain = cost_fns[i](x[i]) - cost_fns[i](x[i] + 1)
            r = gain / unit_costs[i]
            if r > 1e-15 and (best is None or r > best[0] + 1e-15):
                best = (r, i, gain)
        if best is None:
            return path
        _, i, gain = best
        x[i] += 1
        cap += unit_costs[i]
        obj -= gain
        path.append((cap, obj, tuple(x)))


# ---------------------------------------------------------------------------------- frontier greedy
@dataclass
class Step:
    pn: str
    station: str
    delta: int                 # +1 add, -1 remove
    capital: float             # allocation capital after the step (AED)
    aog_hours: float           # modelled total AOG h/yr after the step
    cost: float                # modelled delay cost AED/yr after the step
    d_aog_hours: float         # change in modelled AOG h/yr caused by this step
    ratio: float               # delay-cost change per AED of capital


@dataclass
class GreedyPath:
    start: dict                # pn -> np.ndarray levels at the start
    start_capital: float
    start_aog_hours: float
    start_cost: float
    up: list = field(default_factory=list)     # steps adding units (from start upward)
    down: list = field(default_factory=list)   # steps removing units (from start downward)
    items: dict = field(default_factory=dict)
    capital_offset: float = 0.0                # constant capital (C/E (s,S) cycle stock at base)

    def allocation_at(self, budget: float) -> tuple[dict, float]:
        """Allocation with the largest capital <= budget along the path, and its capital."""
        lv = {k: v.copy() for k, v in self.start.items()}
        if budget >= self.start_capital - 1e-6:
            cap = self.start_capital
            for st in self.up:
                if st.capital > budget + 1e-6:
                    break
                lv[st.pn][self.items[st.pn].stations.index(st.station)] += 1
                cap = st.capital
            return lv, cap
        cap = self.start_capital
        for st in self.down:
            lv[st.pn][self.items[st.pn].stations.index(st.station)] -= 1
            cap = st.capital
            if cap <= budget + 1e-6:
                break
        return lv, cap

    def breakpoints(self) -> list[tuple[float, float]]:
        pts = [(s.capital, s.aog_hours) for s in reversed(self.down)]
        pts.append((self.start_capital, self.start_aog_hours))
        pts += [(s.capital, s.aog_hours) for s in self.up]
        return pts


def unit_capital(it: ItemModel) -> float:
    return it.unit_cost


def allocation_capital(items: dict[str, ItemModel], levels: dict[str, np.ndarray]) -> float:
    """Capital of an allocation in model terms: rotable float units x cost; C/E average target stock
    (s+S+1)/2 x cost per station (so each +1 increment adds exactly one unit cost)."""
    tot = 0.0
    for pn, it in items.items():
        lv = levels[pn]
        if it.is_rotable:
            tot += float(lv.sum()) * it.unit_cost
        else:
            tot += float(np.maximum(lv - (it.q - 1) / 2.0, 0.0).sum()) * it.unit_cost
    return tot


def guardrail_caps(it: ItemModel, guard: dict) -> tuple[np.ndarray, list[str]]:
    """AV-09 planner guardrails for one rotable PN, in engine base_stock units per station.

    G1 (stocking-point cap): Palm total at each stocking point <= the 99.5 % fill quantile of its own
       pipeline, i.e. the smallest S with P(Poisson(mu) <= S-1) >= q. Hub: total = base_stock + loop units,
       mu = network pipeline mean; outstation j: mu = lambda_j x routine resupply days.
    G2 (low-rate outstation cap): an outstation whose annual rate <= `low_rate_per_year` holds <= 1 unit.
    Overrides: guard["overrides"]["PN@STATION"] = {"max_units": n, "reason": "..."} (a reason is required).
    Returns (caps, reasons-per-station)."""
    from gnm.optim.model import poisson_fill_quantile
    J = len(it.stations)
    q = float(guard.get("fill_quantile", 0.995))
    lam = it.rates.sum(axis=1)
    caps = np.zeros(J, dtype=int)
    why = [""] * J
    mu0 = it.hub_mu()
    caps[0] = max(0, poisson_fill_quantile(mu0, q) - int(it.loop_units))
    why[0] = f"G1: total {caps[0] + it.loop_units} = Q{q:.3f}(mu {mu0:.2f})"
    for j in range(1, J):
        if lam[j] <= 0:
            caps[j], why[j] = 0, "no demand"
            continue
        caps[j] = poisson_fill_quantile(lam[j] * it.route_days, q)
        why[j] = f"G1: Q{q:.3f}(mu {lam[j] * it.route_days:.3f})"
        if lam[j] * 365.0 <= float(guard.get("low_rate_per_year", 6.0)):
            lim = int(guard.get("low_rate_max_units", 1))
            if caps[j] > lim:
                caps[j], why[j] = lim, f"G2: station rate {lam[j] * 365:.1f}/yr <= {guard.get('low_rate_per_year', 6.0)}"
    for key, ov in (guard.get("overrides") or {}).items():
        pn, st = key.split("@")
        if pn == it.pn and st in it.stations:
            if not str(ov.get("reason", "")).strip():
                raise ValueError(f"guardrail override {key} needs a written reason")
            j = it.stations.index(st)
            caps[j], why[j] = int(ov["max_units"]), f"override: {ov['reason']}"
    return caps, why


def default_bounds(items: dict[str, ItemModel], base: dict[str, np.ndarray], start: dict[str, np.ndarray],
                   max_out: int = 4, hub_sd: float = 6.0, ce_sd: float = 3.0, min_hub_ready: float = 0.0,
                   guard: dict | None = None):
    """(floor, ceiling) per PN. Rotable floor 0 (hub: `min_hub_ready` ready-rate floor if > 0), C/E floor =
    base (C/E are only ever increased).
    Ceilings: rotable hub ceil(mu + k sd) + 2, outstations `max_out` where there is demand; C/E base +
    ceil(k sqrt(mu)) + 2. Without `guard`, ceilings never cut below the base or start level; with `guard`
    the rotable AV-09 caps (guardrail_caps) bind strictly."""
    floors, ceils = {}, {}
    for pn, it in items.items():
        J = len(it.stations)
        lam = it.rates.sum(axis=1)
        fl = np.zeros(J, dtype=int) if it.is_rotable else base[pn].copy()
        ce = np.zeros(J, dtype=int)
        mu0 = it.hub_mu()
        if it.is_rotable and min_hub_ready > 0 and mu0 > 0:
            # the floor is on Palm's TOTAL hub level; the engine's base_stock sits on top of the seeded loop
            fl[0] = max(0, rotable_hub_floor(mu0, min_hub_ready) - int(it.loop_units))
        if it.is_rotable:
            ce[0] = int(math.ceil(mu0 + hub_sd * math.sqrt(max(mu0, 0.0)))) + 2
            for j in range(1, J):
                ce[j] = max_out if lam[j] > 0 else 0
        else:
            for j in range(J):
                mu = lam[j] * (it.resupply_days if j == 0 else it.route_days)
                ce[j] = base[pn][j] + (int(math.ceil(ce_sd * math.sqrt(mu))) + 2 if lam[j] > 0 else 0)
        if it.is_rotable and guard:
            # AV-09 guardrails bind strictly (even below the base policy); never below the floor
            ce = np.maximum(np.minimum(ce, guardrail_caps(it, guard)[0]), fl)
        else:
            ce = np.maximum(ce, np.maximum(base[pn], start[pn]))
        floors[pn], ceils[pn] = fl, ce
    return floors, ceils


def rotable_hub_floor(mu0: float, ready: float) -> int:
    """Smallest hub float S with ready rate P(X < S) >= ready (planner floor: the float covers the
    pipeline at least `ready` of the time; emergency buying is for exceptions, not routine supply)."""
    from gnm.optim.model import avail_vec
    S = 0
    while avail_vec(np.array([S]), mu0)[0] < ready:
        S += 1
    return S


def _best_move(it: ItemModel, lv: np.ndarray, cur: float, bound: np.ndarray, direction: int):
    """Best single-unit move for one PN: direction +1 -> max cost reduction per AED; -1 -> min increase."""
    best = None
    for j in range(len(lv)):
        if direction > 0 and lv[j] >= bound[j]:
            continue
        if direction < 0 and lv[j] <= bound[j]:
            continue
        lv[j] += direction
        new = it.cost(lv)
        lv[j] -= direction
        r = (cur - new) / it.unit_cost if direction > 0 else (new - cur) / it.unit_cost
        if best is None or (r > best[0] + 1e-12 if direction > 0 else r < best[0] - 1e-12):
            best = (r, j, new)
    return best


def greedy_path(items: dict[str, ItemModel], start: dict[str, np.ndarray], floors: dict, ceils: dict,
                budget_max: float, budget_min: float = 0.0, capital_fn=allocation_capital) -> GreedyPath:
    """Sweep from `start` upward (adding) until budget_max and downward (removing) until budget_min."""
    lv0 = {k: v.copy() for k, v in start.items()}
    cap0 = capital_fn(items, lv0)
    costs = {pn: it.cost(lv0[pn]) for pn, it in items.items()}
    hours = {pn: it.aog_hours(lv0[pn]) for pn, it in items.items()}
    path = GreedyPath(start={k: v.copy() for k, v in lv0.items()}, start_capital=cap0,
                      start_aog_hours=sum(hours.values()), start_cost=sum(costs.values()), items=items)
    order = sorted(items)
    for direction in (+1, -1):
        lv = {k: v.copy() for k, v in lv0.items()}
        c = dict(costs)
        h = dict(hours)
        cap = cap0
        bound = ceils if direction > 0 else floors
        cand = {pn: _best_move(items[pn], lv[pn], c[pn], bound[pn], direction) for pn in order}
        while True:
            pick = None
            for pn in order:
                b = cand[pn]
                if b is None:
                    continue
                if direction > 0 and cap + items[pn].unit_cost > budget_max + 1e-6:
                    continue
                if direction > 0 and b[0] <= 1e-12:
                    continue
                if pick is None or (b[0] > pick[1][0] + 1e-12 if direction > 0 else b[0] < pick[1][0] - 1e-12):
                    pick = (pn, b)
            if pick is None or (direction < 0 and cap <= budget_min + 1e-6):
                break
            pn, (r, j, new) = pick
            it = items[pn]
            lv[pn][j] += direction
            cap += direction * it.unit_cost
            newh = it.aog_hours(lv[pn])
            dh = newh - h[pn]
            h[pn], c[pn] = newh, new
            step = Step(pn=pn, station=it.stations[j], delta=direction, capital=cap, aog_hours=sum(h.values()),
                        cost=sum(c.values()), d_aog_hours=dh, ratio=r)
            (path.up if direction > 0 else path.down).append(step)
            cand[pn] = _best_move(it, lv[pn], c[pn], bound[pn], direction)
    return path


def reposition_only(items: dict[str, ItemModel], levels: dict[str, np.ndarray],
                    ceils: dict | None = None) -> tuple[dict, list]:
    """Zero-capital lever: move existing rotable units hub -> outstation while the model says it
    reduces delay cost (best move first, per PN). Returns new levels and the list of moves."""
    out = {k: v.copy() for k, v in levels.items()}
    moves = []
    for pn in sorted(items):
        it = items[pn]
        if not it.is_rotable:
            continue
        lv = out[pn]
        while lv[0] > 0:
            cur = it.cost(lv)
            cur_h = it.aog_hours(lv)
            best = None
            for j in range(1, len(lv)):
                if it.rates[j].sum() <= 0 or (ceils is not None and lv[j] >= ceils[pn][j]):
                    continue
                lv[0] -= 1
                lv[j] += 1
                new = it.cost(lv)
                lv[0] += 1
                lv[j] -= 1
                if new < cur - 1e-6 and (best is None or new < best[1]):
                    best = (j, new)
            if best is None:
                break
            j, new = best
            lv[0] -= 1
            lv[j] += 1
            moves.append({"pn": pn, "from": it.stations[0], "to": it.stations[j],
                          "d_aog_hours": it.aog_hours(lv) - cur_h})
    return out, moves
