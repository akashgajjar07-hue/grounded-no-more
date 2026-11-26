#!/usr/bin/env python
"""Why do deferred (D3/D10) needs still expire? Classify every deadline-expiry AOG hour (raw P0, history +
5 selection seeds) by the engine's own route trace (aog_route_result / aog_route_h) and fill source.
Diagnostic only. Writes outputs/calibration/v2_deadline_expiry.json."""
import json

import numpy as np
import pandas as pd

from gnm.config import OUTPUTS, load_config
from gnm.sim.api import load_or_generate_scenario, load_world
from gnm.sim.baseline import build_p0
from gnm.sim.calibration import _request_aog
from gnm.sim.engine import run_policy

OUT = OUTPUTS / "calibration" / "v2_deadline_expiry.json"


def classify(r, cfg):
    dl = {"D3": 72, "D10": 240}[r.deadline_class]
    route = r.aog_route_result if isinstance(r.aog_route_result, str) else None
    src = r.fill_source if isinstance(r.fill_source, str) else "unfilled"
    if route in ("exchange_loan", "robbery", "local_borrow", "local_buy"):
        if getattr(r, "aog_route_attempts", 1) > 1:
            return f"route {route} succeeded only on a retry (earlier draw unavailable), after the deadline"
        if pd.notna(r.aog_route_h) and r.aog_route_h <= r.need_h:
            return f"route {route} succeeded but its response time exceeds the window (triggered at need)"
        return f"route {route} succeeded but arrived after the deadline"
    if route == "none":
        tail = {"repair": "repair return", "purchase": "PO receipt", "transfer": "own-stock transfer",
                "lateral": "lateral", "local": "local stock"}.get(src, src)
        what = "local buy unavailable (5% draw)" if r.part_class != "R" else (
            "robbery/exchange unavailable on draw (AUH)" if r.station == "AUH" else "local borrow + exchange unavailable on draw")
        return f"{what} -> waited for {tail}"
    if route is None:
        if src in ("transfer", "lateral"):
            return "own-stock transfer arrived after deadline (no AOG route needed/triggered)"
        return f"no route attempted ({src})"
    return f"other ({route}/{src})"


def main():
    cfg = load_config()
    w = load_world()
    p0 = build_p0(w)
    runs = [(7, 0, 103, 0, 103)] + [(s, 78, 155, 104, 155) for s in range(100, 105)]
    rows = []
    for seed, s0, s1, k0, k1 in runs:
        res = run_policy(w, load_or_generate_scenario(seed, s0, s1), p0, k0, k1)
        rq = _request_aog(w, res, (s1 + 1) * 168)
        rq = rq[(rq.aog_h > 0) & rq.deadline_class.isin(["D3", "D10"]) & (rq.need_h >= k0 * 168)]
        rq = rq.assign(seed=seed, years=(k1 - k0 + 1) / 52)
        rows.append(rq)
    a = pd.concat(rows, ignore_index=True)
    a["reason"] = [classify(r, cfg) for r in a.itertuples()]
    yrs = sum((k1 - k0 + 1) / 52 for _, _, _, k0, k1 in runs)
    by_reason = (a.groupby("reason").aog_h.agg(["size", "sum"]).assign(h_per_yr=lambda d: d["sum"] / yrs)
                 .sort_values("sum", ascending=False))
    by_pn = (a.groupby(["pn", "description", "part_class", "deadline_class"]).aog_h.agg(["size", "sum"])
             .assign(h_per_yr=lambda d: d["sum"] / yrs).sort_values("sum", ascending=False).head(15))
    pn_reason = (a.groupby(["pn", "reason"]).aog_h.sum() / yrs).round(1)
    out = {"years_pooled": yrs, "total_h_per_yr": round(float(a.aog_h.sum() / yrs), 1),
           "by_reason": {k: {"requests": int(v["size"]), "h_per_yr": round(float(v.h_per_yr), 1)} for k, v in by_reason.iterrows()},
           "by_pn": [{"pn": k[0], "description": k[1], "class": k[2], "deadline": k[3], "requests": int(v["size"]),
                      "h_per_yr": round(float(v.h_per_yr), 1),
                      "reasons": {rr: float(h) for (pp, rr), h in pn_reason.items() if pp == k[0]}} for k, v in by_pn.iterrows()]}
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
