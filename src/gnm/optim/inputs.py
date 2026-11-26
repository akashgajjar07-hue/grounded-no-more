"""Demand inputs for the optimiser (swappable source).

The optimiser consumes one long table, one row per (pn, station, deadline_class):

    pn, station, deadline_class, rate_per_day, pipeline_days, work_days, lead_time_days,
    unit_cost, part_class

* ``rate_per_day``   – unit demand rate at that station for that deadline class.
* ``pipeline_days``  – rotables: removal -> serviceable at AUH (core return + transit + queue + shop work);
  10%-trimmed mean of COMPLETED repair orders (open/overdue ROs excluded; OPT-8).
* ``work_days``      – rotables: the shop work part of the pipeline (what ``repair_tat_multiplier`` scales).
* ``lead_time_days`` – consumables/expendables: hub purchase lead time.

Default source = the airline HISTORY (data/processed/history, weeks 0–103 only). The lead can swap
in the champion forecasts by passing a DataFrame / CSV / Parquet with at least
``pn, station, rate_per_day`` (+ optional deadline_class, pipeline_days, work_days, lead_time_days,
unit_cost); missing columns are filled from the history estimates / part master.
Never reads ground truth.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import trim_mean

from gnm.config import HOURS_PER_WEEK, PROCESSED, ROOT

OPT_CONFIG = ROOT / "config" / "optimiser.yaml"
HISTORY = PROCESSED / "history"
CLASSES = ("D0", "D3", "D10")
PIPELINE_TRIM = 0.10   # OPT-8: per-PN 10%-trimmed mean (10% cut from each tail) of completed RO cycle times
COLUMNS = ["pn", "station", "deadline_class", "rate_per_day", "pipeline_days", "work_days", "lead_time_days",
           "unit_cost", "part_class"]


@lru_cache(maxsize=1)
def load_opt_config() -> dict:
    with open(OPT_CONFIG) as f:
        return yaml.safe_load(f)


def _read(name: str, history_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(Path(history_dir) / f"{name}.parquet")


def history_demand_inputs(history_dir: Path | str = HISTORY, weeks: tuple[int, int] | None = None,
                          ro_before_week: int | None = None, lt_from_week: int | None = None) -> pd.DataFrame:
    """Demand inputs estimated from the history tables only (weeks 0–103)."""
    oc = load_opt_config()["demand_inputs"]
    w0, w1 = weeks or tuple(oc["history_weeks"])
    if w1 >= 104:
        raise ValueError("history rate window must end before week 104 (evaluation horizon)")
    ro_before = int(ro_before_week if ro_before_week is not None else oc["pipeline_ro_removed_before_week"])
    lt_from = int(lt_from_week if lt_from_week is not None else oc["lead_time_recent_from_week"])
    hd = Path(history_dir)
    pm = _read("part_master", hd).set_index("pn")
    days = (w1 - w0 + 1) * 7.0
    end_h = (w1 + 1) * HOURS_PER_WEEK

    mr = _read("material_requests", hd)
    mr = mr[(mr.week >= w0) & (mr.week <= w1)]
    mr = mr.assign(part_class=mr.pn.map(pm.part_class))
    # rotables: one unit per removal (unscheduled_removal requests); C/E: all unit demand
    rot = mr[(mr.part_class == "R") & (mr.source == "unscheduled_removal")]
    ce = mr[mr.part_class != "R"]
    dem = pd.concat([rot, ce]).groupby(["pn", "station", "deadline_class"], as_index=False).qty.sum()
    dem["rate_per_day"] = dem.qty / days

    ro = _read("repair_orders", hd)
    # OPT-8: COMPLETED ROs only (open/overdue ROs are excluded), removed before ro_before so short
    # late ROs do not dominate; per-PN 10%-trimmed mean so one stuck repair cannot inflate the pipeline
    ro = ro[ro.removal_id.notna() & ~ro.condemned.astype(bool) & ro.return_h.notna()
            & (ro.removed_h < ro_before * HOURS_PER_WEEK)]
    ret = ro.return_h.astype(float)
    start = ro.start_h.astype("Float64").fillna(ro.return_h).astype(float)
    back = ro.shop.map({"EU_VENDOR": 4.0}).fillna(0.0)
    try:   # shop return transit from the public config if available
        from gnm.config import load_config
        tr = load_config()["repair_shops"]["vendor_transit_days_from_auh"]
        back = ro.shop.map(tr).fillna(0.0).astype(float)
    except Exception:  # pragma: no cover
        pass
    ro = ro.assign(pipe=(ret - ro.removed_h) / 24.0, work=((ret - start) / 24.0 - back).clip(lower=1.0))
    pipe = ro.groupby("pn")[["pipe", "work"]].agg(lambda x: float(trim_mean(x.to_numpy(float), PIPELINE_TRIM)))

    po = _read("purchase_orders", hd)
    po = po[(po.reason == "reorder") & po.receipt_h.notna() & (po.order_h >= lt_from * HOURS_PER_WEEK)]
    po = po.assign(lt=(po.receipt_h.astype(float) - po.order_h) / 24.0)
    lt = po.groupby("pn").lt.agg(["mean", "size"])
    lt = lt[lt["size"] >= 2]["mean"]

    out = dem.merge(pm[["part_class", "unit_cost_aed", "repair_tat_mean_d", "lead_time_mean_d"]],
                    left_on="pn", right_index=True, how="left")
    out["pipeline_days"] = out.pn.map(pipe["pipe"])
    out["work_days"] = out.pn.map(pipe["work"])
    miss = out.part_class.eq("R") & out.pipeline_days.isna()
    out.loc[miss, "pipeline_days"] = out.loc[miss, "repair_tat_mean_d"]           # quoted fallback
    out.loc[miss, "work_days"] = out.loc[miss, "repair_tat_mean_d"]
    out["lead_time_days"] = out.pn.map(lt).fillna(out.lead_time_mean_d)
    out.loc[out.part_class == "R", "lead_time_days"] = out.loc[out.part_class == "R", "lead_time_mean_d"]
    out["unit_cost"] = out.unit_cost_aed.astype(float)
    out = out[COLUMNS].sort_values(["pn", "station", "deadline_class"]).reset_index(drop=True)
    return out


def load_demand_inputs(source=None, history_dir: Path | str = HISTORY) -> pd.DataFrame:
    """Swappable entry point. ``source``: None (config) | 'history' | 'forecasts' | DataFrame | path."""
    source = source if source is not None else load_opt_config()["demand_inputs"]["source"]
    if isinstance(source, str) and source == "forecasts":
        return forecast_demand_inputs(history_dir=history_dir)
    hist = history_demand_inputs(history_dir)
    if isinstance(source, str) and source == "history":
        return hist
    df = source if isinstance(source, pd.DataFrame) else (
        pd.read_parquet(source) if str(source).endswith(".parquet") else pd.read_csv(source))
    df = df.copy()
    pm = _read("part_master", history_dir).set_index("pn")
    if "deadline_class" not in df:
        # split each (pn, station) rate by the history deadline mix (PN default class if no history)
        mix = hist.groupby(["pn", "station", "deadline_class"]).rate_per_day.sum()
        mix = (mix / mix.groupby(level=[0, 1]).transform("sum")).rename("share").reset_index()
        df = df.merge(mix, on=["pn", "station"], how="left")
        df["deadline_class"] = df.deadline_class.fillna(df.pn.map(pm.deadline_class))
        df["rate_per_day"] = df.rate_per_day * df.share.fillna(1.0)
        df = df.drop(columns="share")
    per_pn = hist.groupby("pn")[["pipeline_days", "work_days", "lead_time_days"]].first()
    for c in ["pipeline_days", "work_days", "lead_time_days"]:
        if c not in df:
            df[c] = df.pn.map(per_pn[c])
        df[c] = df[c].fillna(df.pn.map(per_pn[c]))
    if "unit_cost" not in df:
        df["unit_cost"] = df.pn.map(pm.unit_cost_aed).astype(float)
    if "part_class" not in df:
        df["part_class"] = df.pn.map(pm.part_class)
    return df[COLUMNS].sort_values(["pn", "station", "deadline_class"]).reset_index(drop=True)


def penalty_per_hour_by_pn(world) -> dict[str, float]:
    """AED per AOG hour for each PN: the archetype penalties weighted by the PN's applicability exposure
    (aircraft count x qty per aircraft x planned utilisation of its driver)."""
    pen = world.cfg["economics"]["aog_penalty_aed_per_hour"]
    ac = world.aircraft
    util = {a: {"n": int((ac.archetype == a).sum()), "FH": float(ac.loc[ac.archetype == a, "fh_per_day_mean"].mean()),
                "FC": float(ac.loc[ac.archetype == a, "fc_per_day_mean"].mean())} for a in ac.archetype.unique()}
    drv = world.parts.set_index("pn").driver
    out = {}
    for pn, g in world.applicability.groupby("pn"):
        d = drv.get(pn, "FH")
        key = "FH" if d == "FH" else "FC"
        w = np.array([util[a]["n"] * q * util[a][key] for a, q in zip(g.archetype, g.qty_per_aircraft)])
        p = np.array([float(pen[a]) for a in g.archetype])
        out[pn] = float((w * p).sum() / w.sum()) if w.sum() > 0 else float(np.mean(list(pen.values())))
    return out


FORECASTS = ROOT / "outputs" / "forecasting" / "final_forecasts.parquet"


def forecast_demand_inputs(path: Path | str = FORECASTS, history_dir: Path | str = HISTORY) -> pd.DataFrame:
    """Demand inputs from the frozen champion-forecast table (outputs/forecasting/final_forecasts.parquet).

    * Rotables: the reliability-exposure removal rate per station (``removal_rate_day``), as P1/P2 use (POL-3).
    * C/E: the champion's weekly rate per station / 7 (hub row = hub-local demand; network demand at the hub
      is rebuilt by the model as the sum over stations).
    * Deadline split per row: D0 = p_d0, D10 = p_d10, D3 = the rest.
    * Rotable pipeline / work days: the OPT-8 robust history estimate (10%-trimmed mean of COMPLETED ROs);
      PNs without completed ROs fall back to the forecast table's t_eff (rotable_pipeline.csv).
    * C/E lead time: the hub row's planner lead-time estimate (catches PS4).
    """
    ff = pd.read_parquet(path)
    hist = history_demand_inputs(history_dir)
    per_pn = hist.groupby("pn")[["pipeline_days", "work_days"]].first()
    hub = load_config_hub()
    lt_hub = ff[ff.station == hub].set_index("pn").lead_time_d
    teff = ff[ff.station == hub].set_index("pn").get("t_eff_hub_d")
    pm = _read("part_master", history_dir).set_index("pn")
    rows = []
    for r in ff.itertuples(index=False):
        pc = r.part_class
        rate = float(r.removal_rate_day) if pc == "R" else float(r.weekly_rate) / 7.0
        if not np.isfinite(rate) or rate <= 0:
            continue
        p0 = float(np.nan_to_num(r.p_d0))
        p10 = float(np.nan_to_num(r.p_d10))
        split = {"D0": p0, "D10": p10, "D3": max(0.0, 1.0 - p0 - p10)}
        pipe = per_pn.pipeline_days.get(r.pn, np.nan)
        work = per_pn.work_days.get(r.pn, np.nan)
        if pc == "R" and (pipe is None or not np.isfinite(pipe)):
            pipe = float(teff.get(r.pn)) if teff is not None else float(pm.loc[r.pn, "repair_tat_mean_d"])
            work = float(pm.loc[r.pn, "repair_tat_mean_d"])
        for dc, sh in split.items():
            if sh <= 0:
                continue
            rows.append({"pn": r.pn, "station": r.station, "deadline_class": dc, "rate_per_day": rate * sh,
                         "pipeline_days": pipe if pc == "R" else np.nan, "work_days": work if pc == "R" else np.nan,
                         "lead_time_days": float(lt_hub.get(r.pn, pm.loc[r.pn, "lead_time_mean_d"])),
                         "unit_cost": float(pm.loc[r.pn, "unit_cost_aed"]), "part_class": pc})
    return pd.DataFrame(rows)[COLUMNS].sort_values(["pn", "station", "deadline_class"]).reset_index(drop=True)


def load_config_hub() -> str:
    from gnm.config import load_config
    return load_config()["network"]["hub"]
