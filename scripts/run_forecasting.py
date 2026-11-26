"""Forecasting integration run (inventory-policy agent).

Rolling-origin evaluation on the selection origins (weeks 78-101 forecast; history only),
leaderboard with bootstrap CIs, champion freeze, stock-based evaluation, and final per-PN /
per-station forecasts fitted on weeks 0-103.

Outputs (outputs/forecasting/): errors.parquet, leaderboard.csv, leaderboard_by_class.csv,
champions.{csv,json,sha256}, stock_eval.parquet, stock_eval_summary.csv,
reliability_vs_croston.csv, final_forecasts.parquet, lead_times.csv, rotable_pipeline.csv,
forecasting_summary.json.

    python scripts/run_forecasting.py
"""
from __future__ import annotations

import json
import time

import pandas as pd

from gnm.policy import forecast_pipeline as fp
from gnm.sim.api import load_world


def main() -> dict:
    t0 = time.time()
    out = fp.FC_OUT
    out.mkdir(parents=True, exist_ok=True)
    world = load_world()
    hist = fp.load_history()
    inputs = fp.build_inputs(hist, origin=104)
    ev = fp.run_forecast_evaluation(inputs)
    ev["errors"].to_parquet(out / "errors.parquet", index=False)
    ev["leaderboard"].to_csv(out / "leaderboard.csv", index=False, float_format="%.6f")
    ev["leaderboard_by_class"].to_csv(out / "leaderboard_by_class.csv", index=False, float_format="%.6f")
    frz = fp.freeze_champions(ev["champions"], out / "champions")
    rvc = fp.reliability_vs_croston(ev["leaderboard_by_class"])
    rvc.to_csv(out / "reliability_vs_croston.csv", index=False)
    t1 = time.time()
    se = fp.run_stock_eval(hist)
    se.to_parquet(out / "stock_eval.parquet", index=False)
    ses = fp.summarise_stock_eval(se)
    ses.to_csv(out / "stock_eval_summary.csv", index=False, float_format="%.6f")
    t2 = time.time()
    champs = pd.read_csv(out / "champions.csv")
    ff = fp.final_forecasts(hist, world, champs, origin=104)
    ff.to_parquet(out / "final_forecasts.parquet", index=False)
    pt = fp.pipeline_tables(hist, world, 104)
    pt["lead_times"].to_csv(out / "lead_times.csv", float_format="%.4f")
    pt["rotable_pipeline"].to_csv(out / "rotable_pipeline.csv", float_format="%.4f")
    summary = {
        "provenance": "DERIVED",
        "source": "data/processed/history (weeks 0-103, history_seed, P0); selection origins 78-98",
        "n_parts": int(len(inputs["pns"])), "origins": sorted(ev["errors"].origin.unique().tolist()),
        "methods": sorted(ev["errors"].method.unique().tolist()),
        "champions_sha256": frz["sha256"],
        "champion_counts_parts": ff.drop_duplicates("pn").champion.value_counts().to_dict(),
        "reliability_vs_croston": json.loads(rvc.to_json(orient="records")),
        "lead_time_regime_shifts": pt["lead_times"].index[pt["lead_times"].regime_shift].tolist(),
        "timings_s": {"evaluation": round(t1 - t0, 1), "stock_eval": round(t2 - t1, 1),
                      "final": round(time.time() - t2, 1)},
    }
    (out / "forecasting_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
