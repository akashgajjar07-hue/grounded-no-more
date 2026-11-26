"""Alternative actions per rotable PN on one annual basis.

Levers, each evaluated against the base allocation:
  * buy n more spares (at the best station)  annual cost = n x unit cost x carrying %   (capital is
    reported separately; the annualised holding cost is what is compared)
  * cut repair TAT by d days                  annual cost = annual removals x d x repair_acceleration_cost
                                              (implemented in the engine as repair_tat_multiplier = 1 - d / work days)
  * reposition one existing unit hub -> best outstation   annual cost 0, capital 0

Benefit = modelled AOG-hour reduction per year (gnm.optim.model) x the PN's AOG penalty.
The Palm/EBO view of the same levers comes from gnm.policy.analytic.compare_levers (network
float vs pipeline) and is reported alongside (columns palm_*).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gnm.optim.model import ItemModel
from gnm.policy.analytic import compare_levers


def tat_multiplier(it: ItemModel, cut_days: float, max_share: float = 0.5) -> tuple[float, float]:
    """(multiplier on shop work days, effective cut in days) for a d-day TAT cut."""
    if it.work_days <= 0:
        return 1.0, 0.0
    d = min(cut_days, max_share * it.work_days)
    return 1.0 - d / it.work_days, d


def lever_table(items: dict[str, ItemModel], levels: dict[str, np.ndarray], carry: float,
                accel_cost_per_day: float, tat_cut_days: float = 10.0, extra_spares=(1, 2),
                max_cut_share: float = 0.5) -> pd.DataFrame:
    rows = []
    for pn in sorted(items):
        it = items[pn]
        if not it.is_rotable or it.lam_net <= 0:
            continue
        lv = levels[pn].astype(int)
        base_h = it.aog_hours(lv)
        pen = it.penalty_per_h
        annual_removals = it.lam_net * 365.0
        net_units = int(lv.sum())
        palm = compare_levers(rate_per_30d=it.lam_net * 30.0, tat_days=it.resupply_days,
                              spares=net_units + int(it.loop_units),   # Palm total = base_stock + seeded loop
                              unit_cost_aed=it.unit_cost, tat_cut_days=tat_multiplier(it, tat_cut_days, max_cut_share)[1],
                              extra_spares=max(extra_spares), accel_cost_per_day_per_unit=accel_cost_per_day)
        common = {"pn": pn, "unit_cost_aed": it.unit_cost, "annual_removals": annual_removals,
                  "pipeline_days": it.resupply_days, "work_days": it.work_days, "current_units": net_units,
                  "base_aog_hours": base_h, "penalty_aed_per_h": pen,
                  "palm_ebo_base": palm["base"]["ebo"], "palm_ebo_extra": palm["extra_spares"]["ebo"],
                  "palm_ebo_tat_cut": palm["tat_cut"]["ebo"]}
        # buy n spares: greedy placement of n units (best station each time)
        for n in extra_spares:
            cur = lv.copy()
            where = []
            for _ in range(n):
                best = None
                for j in range(len(cur)):
                    if j > 0 and it.rates[j].sum() <= 0:
                        continue
                    cur[j] += 1
                    h = it.aog_hours(cur)
                    cur[j] -= 1
                    if best is None or h < best[1] - 1e-9:
                        best = (j, h)
                cur[best[0]] += 1
                where.append(it.stations[best[0]])
            dh = base_h - it.aog_hours(cur)
            rows.append({**common, "lever": f"buy_{n}", "detail": "+1 @ " + ", +1 @ ".join(where),
                         "incremental_capital_aed": n * it.unit_cost, "annual_cost_aed": n * it.unit_cost * carry,
                         "aog_hours_reduction": dh})
        # TAT cut
        m, d = tat_multiplier(it, tat_cut_days, max_cut_share)
        if d > 0:
            dh = base_h - it.aog_hours(lv, tat_mult=m)
            rows.append({**common, "lever": f"tat_cut_{int(round(tat_cut_days))}d",
                         "detail": f"repair_tat_multiplier {m:.3f} ({d:.1f} of {it.work_days:.1f} work days)",
                         "incremental_capital_aed": 0.0,
                         "annual_cost_aed": palm["tat_cut"]["incremental_annual_aed"],
                         "aog_hours_reduction": dh, "tat_multiplier": m})
        # reposition: one hub unit to the best outstation
        if lv[0] > 0:
            best = None
            for j in range(1, len(lv)):
                if it.rates[j].sum() <= 0:
                    continue
                cur = lv.copy()
                cur[0] -= 1
                cur[j] += 1
                h = it.aog_hours(cur)
                if best is None or h < best[1] - 1e-9:
                    best = (j, h)
            if best is not None:
                rows.append({**common, "lever": "reposition_1", "detail": f"AUH -> {it.stations[best[0]]}",
                             "incremental_capital_aed": 0.0, "annual_cost_aed": 0.0,
                             "aog_hours_reduction": base_h - best[1]})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["penalty_saved_aed"] = df.aog_hours_reduction * df.penalty_aed_per_h
    df["net_annual_benefit_aed"] = df.penalty_saved_aed - df.annual_cost_aed
    df["annual_cost_per_aog_hour_aed"] = np.where(df.aog_hours_reduction > 1e-9,
                                                  df.annual_cost_aed / df.aog_hours_reduction.clip(lower=1e-9), np.nan)
    df["tat_multiplier"] = df.get("tat_multiplier", pd.Series(np.nan, index=df.index))
    return df


def best_actions(levers: pd.DataFrame) -> pd.DataFrame:
    """Per PN: the lever with the largest net annual benefit (or 'hold' if none is positive)."""
    if levers.empty:
        return pd.DataFrame(columns=["pn", "best_action", "best_net_benefit_aed"])
    out = []
    for pn, g in levers.groupby("pn", sort=True):
        g = g.sort_values(["net_annual_benefit_aed", "lever"], ascending=[False, True])
        top = g.iloc[0]
        act = top.lever if top.net_annual_benefit_aed > 0 else "hold"
        out.append({"pn": pn, "best_action": act, "best_detail": top.detail if act != "hold" else "",
                    "best_net_benefit_aed": float(top.net_annual_benefit_aed)})
    return pd.DataFrame(out)


def lever_findings(levers: pd.DataFrame, tat_label: str, compare: str = "buy_2", top: int = 8) -> list[str]:
    """Plain-language findings: PNs where cutting TAT gives more AOG-hour reduction than buying
    spares at a lower annual cost (and the reverse)."""
    if levers.empty:
        return []
    p = levers.pivot_table(index="pn", columns="lever", values=["aog_hours_reduction", "annual_cost_aed"])
    out = []
    if (("aog_hours_reduction", tat_label) not in p.columns) or (("aog_hours_reduction", compare) not in p.columns):
        return out
    t_h, b_h = p[("aog_hours_reduction", tat_label)], p[("aog_hours_reduction", compare)]
    t_c, b_c = p[("annual_cost_aed", tat_label)], p[("annual_cost_aed", compare)]
    win = p[(t_h >= b_h) & (t_c <= b_c) & (t_h > 1.0)].index
    for pn in sorted(win, key=lambda x: -float(t_h[x]))[:top]:
        out.append(f"{pn}: cutting TAT ({tat_label}) avoids {t_h[pn]:.0f} AOG h/yr for AED {t_c[pn]:,.0f}/yr, "
                   f"vs {b_h[pn]:.0f} h/yr for AED {b_c[pn]:,.0f}/yr holding cost by buying {compare[4:]} spares.")
    lose = p[(b_h > t_h) & (b_c < t_c) & (b_h > 1.0)].index
    for pn in sorted(lose, key=lambda x: -float(b_h[x]))[:top]:
        out.append(f"{pn}: buying {compare[4:]} spares avoids {b_h[pn]:.0f} AOG h/yr for AED {b_c[pn]:,.0f}/yr, "
                   f"vs {t_h[pn]:.0f} h/yr for AED {t_c[pn]:,.0f}/yr by cutting TAT ({tat_label}).")
    return out
