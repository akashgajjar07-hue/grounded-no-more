"""Truth-recovery evaluation — the ONLY module outside gnm.sim that may read data/ground_truth.

Question: how close do the planner's estimates (built from history only) get to the
generator's hidden truth, compared with the vendor-quoted figures the legacy rules use?
Reported separately from forecast accuracy (which is scored against realised demand).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from gnm.config import GROUND_TRUTH, OUTPUTS


def _mdale(est: pd.Series, true: pd.Series) -> float:
    """Median absolute log error (|log(est/true)|): 0.10 ~ 10% off, symmetric."""
    m = est.notna() & true.notna() & (est > 0) & (true > 0)
    return float(np.median(np.abs(np.log(est[m] / true[m])))) if m.any() else float("nan")


def run(final_forecasts: pd.DataFrame, lead_times: pd.DataFrame | None = None, out_dir=None) -> dict:
    truth = pd.read_parquet(GROUND_TRUTH / "gt_part_truth.parquet")
    planted = json.loads((GROUND_TRUTH / "planted.json").read_text()) if (GROUND_TRUTH / "planted.json").exists() else {}
    ff = final_forecasts.drop_duplicates("pn").set_index("pn")
    t = truth.set_index("pn")
    rows = []
    for pn, r in ff.iterrows():
        if pn not in t.index or pd.isna(t.loc[pn, "mtbur_true"]):
            continue
        rows.append({"pn": pn, "part_class": r["part_class"], "mtbur_true": t.loc[pn, "mtbur_true"],
                     "mtbur_quoted": r.get("mtbur_quoted"), "mtbur_estimated": r.get("mtbur_post")})
    rel = pd.DataFrame(rows)
    out = {"provenance": "DERIVED", "note": "Estimates use history weeks 0-103 only; truth read here for evaluation only.",
           "metric": "median absolute log error |ln(est/true)|; 0.10 ~ 10% off", "reliability": {}}
    for cls, g in [("all", rel)] + list(rel.groupby("part_class")):
        out["reliability"][cls] = {
            "n_parts": int(len(g)),
            "quoted_mdale": _mdale(g.mtbur_quoted, g.mtbur_true),
            "estimated_mdale": _mdale(g.mtbur_estimated, g.mtbur_true),
            "share_estimate_closer": float(np.mean(np.abs(np.log(g.mtbur_estimated / g.mtbur_true))
                                                   < np.abs(np.log(g.mtbur_quoted / g.mtbur_true)))),
        }
    if lead_times is not None and "lt_est_d" in lead_times.columns:
        lt = lead_times.drop_duplicates("pn").set_index("pn")
        ltrows = []
        for pn in lt.index.intersection(t.index):
            tr = t.loc[pn]
            true_now = tr["lead_time_after_d"] if pd.notna(tr.get("lead_time_change_week")) else tr["lead_time_mean_true_d"]
            ltrows.append({"pn": pn, "true": true_now, "est": lt.loc[pn, "lt_est_d"],
                           "quoted": lt.loc[pn].get("lt_quoted_d", np.nan),
                           "changed": bool(pd.notna(tr.get("lead_time_change_week")))})
        L = pd.DataFrame(ltrows)
        out["lead_time"] = {"n_parts": int(len(L)), "quoted_mdale": _mdale(L.quoted, L.true),
                            "estimated_mdale": _mdale(L.est, L.true),
                            "changed_parts": L[L.changed].to_dict("records")}
    out["planted"] = planted
    out_dir = out_dir or (OUTPUTS / "holdout")
    out_dir.mkdir(parents=True, exist_ok=True)
    rel.to_csv(out_dir / "truth_recovery_reliability.csv", index=False)
    return out
