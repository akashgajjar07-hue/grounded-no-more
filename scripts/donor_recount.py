"""Post-plan exploratory donor-hours recount (v2.1 workstream B, AV2-01). Post-processing ONLY.

Reads the EXISTING frozen holdout outputs (outputs/holdout/*, seeds 2000-2019, central) and the P0 history
(data/processed/history/aog_robberies.parquet). It never re-runs a policy, a simulation or the optimiser and it
never writes to a frozen folder. Output: outputs/postplan/donor_recount.json and .md.

What the holdout outputs contain (checked, see `inventory` in the JSON):
* robbery COUNTS per seed and policy: `route_robbery` in policy_class_kpis / policy_station_kpis.parquet, for P0, P1
  and P2 only (requests in the 52-week KPI window whose AOG route was a robbery, so a count per year). The frontier
  holdout run (frontier_points.csv) stores only aggregates for I125, with no route columns.
* donor robbed / reinstated times: NOT stored for any holdout run (only aggregate KPIs were kept), so holdout donor
  hours cannot be recomputed without a new simulation, which v2.1 forbids.
* recipient hours = the frozen material AOG hours (policy_results.parquet aog_hours, frontier_points.csv for I125).

Usage:  python scripts/donor_recount.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
HOLD = ROOT / "outputs" / "holdout"
HIST = ROOT / "data" / "processed" / "history"
OUT = ROOT / "outputs" / "postplan"

LABEL = ("Post-plan exploratory recount. Gross donor hours are an upper bound — a donor may already be in maintenance "
         "or not scheduled to fly.")
NOT_RECON = "not reconstructible from current logs"
POLICIES = ["P0", "P1", "P2", "I125"]
HISTORY_WEEKS = 104
HOURS_PER_WEEK = 168


def mean_ci(x, level: float = 0.95) -> dict:
    x = np.asarray(x, float)
    n = x.size
    m = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else float("nan")
    hw = float(stats.t.ppf(0.5 + level / 2, n - 1)) * sd / math.sqrt(n) if n > 1 else float("nan")
    return {"mean": m, "ci_lo": m - hw, "ci_hi": m + hw, "sd": sd, "n": int(n)}


def paired(a: pd.Series, b: pd.Series) -> dict:
    """a - b over common seeds, 95% paired t."""
    d = (a - b).dropna()
    r = mean_ci(d.to_numpy())
    r["share_seeds_lower"] = float((d < 0).mean())
    r["seeds"] = [int(s) for s in d.index]
    return r


def union_hours(df: pd.DataFrame, start: str, end: str) -> float:
    """Sum of per-tail interval unions (overlapping robberies of the same donor counted once)."""
    tot = 0.0
    for _, g in df.sort_values(start).groupby("donor_tail"):
        cs = ce = None
        for s, e in zip(g[start], g[end]):
            if cs is None:
                cs, ce = s, e
            elif s <= ce:
                ce = max(ce, e)
            else:
                tot += ce - cs
                cs, ce = s, e
        if cs is not None:
            tot += ce - cs
    return float(tot)


def holdout_block() -> dict:
    cls = pd.read_parquet(HOLD / "policy_class_kpis.parquet")
    stn = pd.read_parquet(HOLD / "policy_station_kpis.parquet")
    res = pd.read_parquet(HOLD / "policy_results.parquet")
    fp = pd.read_csv(HOLD / "frontier_points.csv").set_index("id")
    cls, stn, res = (d[d.variant == "central"] for d in (cls, stn, res))
    rob = cls.groupby(["policy_id", "seed"]).route_robbery.sum().unstack(0)
    rob_st = stn.groupby(["policy_id", "seed"]).route_robbery.sum().unstack(0)
    if not rob.equals(rob_st):
        raise RuntimeError("route_robbery differs between the class and the station tables")
    by_station = stn.groupby(["policy_id", "station"]).route_robbery.mean().unstack(0)
    seeds = sorted(int(s) for s in res.seed.unique())
    aog = res.pivot(index="seed", columns="policy_id", values="aog_hours")
    robbery = {}
    for p in POLICIES:
        if p in rob.columns:
            robbery[p] = {**mean_ci(rob[p].to_numpy()), "per_seed": {int(s): int(v) for s, v in rob[p].items()},
                          "at_auh_mean": float(by_station.at["AUH", p]),
                          "elsewhere_mean": float(by_station[p].drop("AUH").sum())}
        else:
            robbery[p] = {"status": NOT_RECON,
                          "why": "the frozen frontier holdout run kept only aggregate KPIs for I125 (frontier_points.csv); "
                                 "no route counts were stored"}
    paired_rob = {"P2-P0": paired(rob["P2"], rob["P0"]),
                  "P1-P0": paired(rob["P1"], rob["P0"]),
                  "I125-P2": {"status": NOT_RECON, "why": "no per-seed I125 robbery counts"}}
    recipient = {p: {**mean_ci(aog[p].to_numpy()), "source": "outputs/holdout/policy_results.parquet aog_hours (frozen)"}
                 for p in ["P0", "P1", "P2"]}
    r = fp.loc["I125"]
    recipient["I125"] = {"mean": float(r.aog_hours_mean), "ci_lo": float(r.aog_hours_lo), "ci_hi": float(r.aog_hours_hi),
                         "n": int(r.n_seeds), "source": "outputs/holdout/frontier_points.csv aog_hours (frozen)"}
    for p in POLICIES:   # the frozen numbers must be what the site shows
        if p in fp.index and abs(recipient[p]["mean"] - float(fp.at[p, "aog_hours_mean"])) > 1e-9:
            raise RuntimeError(f"{p}: policy_results and frontier_points AOG means differ")
    gross = {p: {"status": NOT_RECON} for p in POLICIES}
    return {
        "split": "holdout", "variant": "central", "seeds": seeds, "kpi_weeks": [104, 155],
        "robbery_count_per_year": robbery,
        "robbery_count_paired": paired_rob,
        "robbery_count_note": ("Requests in the 52-week KPI window whose AOG route was a robbery at AUH (a count per year). "
                               "Robbery is used only for AUH needs in the engine."),
        "recipient_hours_per_year": recipient,
        "recipient_hours_note": "Recipient hours = the frozen material AOG hours (the downtime of the aircraft waiting for the part).",
        "gross_donor_hours_per_year": gross,
        "combined_hours_per_year": {p: {"status": NOT_RECON} for p in POLICIES},
        "donor_hours_paired": {"P2-P0": {"status": NOT_RECON}, "I125-P2": {"status": NOT_RECON}},
        "donor_hours_status": NOT_RECON,
        "donor_hours_why": ("The holdout runs stored aggregate KPIs only; donor robbed / reinstated times were not logged. "
                            "Recomputing them needs a new simulation, which v2.1 does not run."),
    }


def history_block() -> dict:
    r = pd.read_parquet(HIST / "aog_robberies.parquet")
    ae = pd.read_parquet(HIST / "aog_events.parquet")
    years = HISTORY_WEEKS / 52.0
    end_h = HISTORY_WEEKS * HOURS_PER_WEEK
    done = r[r.reinstated_h.notna()].copy()
    done["reinstated_h"] = done.reinstated_h.astype(float)
    done["held_h"] = done.reinstated_h - done.robbed_h
    open_ = r[r.reinstated_h.isna()].copy()
    allr = r.copy()
    allr["end_h"] = allr.reinstated_h.astype("Float64").fillna(end_h).astype(float).clip(upper=end_h)
    gross = float(done.held_h.sum()) / years
    union = union_hours(done, "robbed_h", "reinstated_h") / years
    counted = float(ae.hours.sum()) / years
    req = pd.read_parquet(HIST / "material_requests.parquet", columns=["request_id", "deadline_class"])
    dl = r.merge(req, on="request_id", how="left").deadline_class
    return {
        "label": "HISTORICAL P0 (history weeks 0-103, one P0 world). Not holdout; never mix with the holdout numbers.",
        "split": "history", "policy": "P0", "weeks": [0, HISTORY_WEEKS - 1],
        "robberies": int(len(r)), "robberies_per_year": len(r) / years, "donor_tails": int(r.donor_tail.nunique()),
        "reinstated": int(len(done)), "open_at_end_of_history": int(len(open_)),
        "mean_days_held": float(done.held_h.mean()) / 24.0, "max_days_held": float(done.held_h.max()) / 24.0,
        "share_d3_d10": float(dl.isin(["D3", "D10"]).mean()),
        "gross_donor_hours_per_year": gross,
        "gross_donor_hours_basis": "sum of (reinstated_h - robbed_h) over the reinstated robberies / 2 years (LIMITATIONS 29)",
        "donor_hours_per_tail_union_per_year": union,
        "donor_hours_per_tail_union_basis": "same robberies, overlapping intervals of one donor tail counted once",
        "gross_donor_hours_incl_open_per_year": float((allr.end_h - allr.robbed_h).sum()) / years,
        "counted_material_aog_hours_per_year": counted,
        "counted_basis": "data/processed/history/aog_events.parquet hours / 2 years (the calibrated P0 history figure)",
        "ratio_gross_donor_to_counted": gross / counted,
        "source": ["data/processed/history/aog_robberies.parquet", "data/processed/history/aog_events.parquet",
                   "data/processed/history/material_requests.parquet"],
    }


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        x = float(o)
        return None if not math.isfinite(x) else round(x, 4)
    return o


def build() -> dict:
    h = holdout_block()
    hist = history_block()
    return clean({
        "label": LABEL, "status": "post-plan, exploratory",
        "decision": "V21-B",
        "outcome": {
            "robbery_counts": "computed for P0, P1, P2 (holdout, paired); " + NOT_RECON + " for I125",
            "donor_hours_holdout": NOT_RECON,
            "historical_p0": "reported separately (history, not holdout)",
        },
        "inventory": {
            "outputs/holdout/policy_class_kpis.parquet": "route_robbery per seed x policy x class (P0, P1, P2; 3 worlds)",
            "outputs/holdout/policy_station_kpis.parquet": "route_robbery per seed x policy x station (same counts; all at AUH)",
            "outputs/holdout/policy_results.parquet": "aggregate KPIs per seed (aog_hours = recipient hours); no route or donor columns",
            "outputs/holdout/frontier_points.csv": "aggregate means/CIs per candidate incl. I125; no per-seed rows, no route columns",
            "outputs/holdout/postplan_i125_*": "aggregate I125/P0/P2 stress-world rows; no route columns",
            "donor robbed / reinstated times": "not stored by any holdout run",
        },
        "holdout": h,
        "historical_p0": hist,
        "not_reconstructible_text": NOT_RECON,
        "provenance": "SIMULATED",
        "sources": ["outputs/holdout/policy_class_kpis.parquet", "outputs/holdout/policy_station_kpis.parquet",
                    "outputs/holdout/policy_results.parquet", "outputs/holdout/frontier_points.csv",
                    *hist["source"]],
    })


def fmt(x, d=0):
    return "n/a" if x is None else f"{x:,.{d}f}"


def to_md(j: dict) -> str:
    h, hi = j["holdout"], j["historical_p0"]
    rc = h["robbery_count_per_year"]
    L = ["# Donor-hours recount (v2.1, workstream B)", "", f"**{j['label']}**", "",
         "Post-processing of existing outputs only. No policy, simulation or optimiser was re-run. Decision V21-B.", "",
         "## Holdout robbery counts per year (seeds 2000–2019, central, 95% CI over 20 seeds)", "",
         "| Policy | Robberies / yr | 95% CI |", "|---|---|---|"]
    for p in POLICIES:
        r = rc[p]
        L.append(f"| {p} | {fmt(r['mean'], 1)} | {fmt(r['ci_lo'], 1)}–{fmt(r['ci_hi'], 1)} |" if "mean" in r
                 else f"| {p} | {r['status']} | |")
    L += ["", "| Paired difference | Mean | 95% paired-t CI |", "|---|---|---|"]
    for k, r in h["robbery_count_paired"].items():
        L.append(f"| {k} | {fmt(r['mean'], 1)} | {fmt(r['ci_lo'], 1)} to {fmt(r['ci_hi'], 1)} |" if "mean" in r
                 else f"| {k} | {r['status']} | |")
    L += ["", h["robbery_count_note"], "",
          "## Holdout donor hours", "",
          f"Gross donor-grounded hours, combined hours and their paired differences: **{NOT_RECON}**. {h['donor_hours_why']}", "",
          "Recipient hours (= the frozen material AOG hours, unchanged): "
          + ", ".join(f"{p} {fmt(h['recipient_hours_per_year'][p]['mean'])} h" for p in POLICIES) + ".", "",
          "## HISTORICAL P0 (history weeks 0–103; not holdout, never mixed with it)", "",
          f"* Robberies: {hi['robberies']} on {hi['donor_tails']} donor tails ({fmt(hi['robberies_per_year'], 1)} a year); "
          f"{hi['open_at_end_of_history']} still open at the end of history.",
          f"* Average donor held {fmt(hi['mean_days_held'], 1)} days (max {fmt(hi['max_days_held'], 1)}); "
          f"{fmt(100 * hi['share_d3_d10'])}% of robberies were for D3/D10 items.",
          f"* Gross donor hours: **{fmt(hi['gross_donor_hours_per_year'])} h/yr** ({hi['gross_donor_hours_basis']}).",
          f"* Per-tail union (overlaps counted once): {fmt(hi['donor_hours_per_tail_union_per_year'])} h/yr.",
          f"* Counted material AOG (historical P0): **{fmt(hi['counted_material_aog_hours_per_year'])} h/yr**.",
          "", f"_{j['label']}_", ""]
    return "\n".join(L)


def main() -> None:
    j = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "donor_recount.json").write_text(json.dumps(j, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    (OUT / "donor_recount.md").write_text(to_md(j))
    print(to_md(j))


if __name__ == "__main__":
    main()
