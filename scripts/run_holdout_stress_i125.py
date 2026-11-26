"""POST-PLAN robustness check (user request, added AFTER the main v2 holdout; see DECISIONS D015).

Evaluates the FROZEN frontier candidates P0, P2 and I125 (central-built allocations, exactly as frozen in
outputs/frontier/candidates.json) on the v2 holdout seeds 2000–2019 in the low_stress and high_stress worlds.
Nothing is re-selected; the candidate file must still match the freeze manifest. Runs once (logged as
`v2_postplan_i125_stress_holdout`). Results are reported as they come out.
"""
import json

from gnm.config import OUTPUTS, ROOT, load_config, seeds as cfg_seeds
from gnm.freeze import require_frozen, sha256_file, verify
from gnm.optim.frontier import evaluate, load_candidates, summarise
from gnm.sim.api import load_or_generate_scenario, load_world

CAND = ROOT / "outputs/frontier/candidates.json"
IDS = ["P0", "P2", "I125"]

if __name__ == "__main__":
    m = verify()
    rel = str(CAND.relative_to(ROOT))
    assert m["artefacts"].get(rel) == sha256_file(CAND), "candidates.json changed since freeze"
    require_frozen("v2_postplan_i125_stress_holdout")
    cal = load_config()["calendar"]
    w0, w1 = cal["evaluation_weeks"][0] - cal["warmup_weeks"], cal["evaluation_weeks"][1]
    hold = cfg_seeds()["holdout"]
    cands = [(meta, pol) for meta, pol in load_candidates(CAND) if pol.policy_id in IDS]
    assert sorted(p.policy_id for _, p in cands) == sorted(IDS)
    out = {"note": "Post-plan robustness check added after the main v2 holdout (D015); frozen central-built "
                   "candidates; paired vs P2; no re-selection.", "seeds": hold, "worlds": {}}
    for v in ["low_stress", "high_stress"]:
        for s in hold:   # sequential cache warm-up (V2-SIM-18 makes writes atomic anyway)
            load_or_generate_scenario(int(s), w0, w1, variant=v)
        long = evaluate(load_world(v), [p for _, p in cands], hold, v, weeks=(w0, w1),
                        kpi=tuple(cal["evaluation_weeks"]), allow_holdout=True)
        summ = summarise(long, "P2")
        summ.to_csv(OUTPUTS / "holdout" / f"postplan_i125_{v}.csv", index=False)
        out["worlds"][v] = summ.to_dict("records")
        print(v)
        cols = [c for c in summ.columns if c in ("id", "capital_mean", "aog_hours_mean", "aog_hours_lo", "aog_hours_hi",
                                                  "d_aog_hours_vs_base_mean", "d_aog_hours_vs_base_lo", "d_aog_hours_vs_base_hi",
                                                  "d_total_cost_vs_base_mean", "d_total_cost_vs_base_lo",
                                                  "d_total_cost_vs_base_hi", "d_capital_vs_base_mean")]
        print(summ[cols].to_string(index=False))
    (OUTPUTS / "holdout" / "postplan_i125_stress.json").write_text(json.dumps(out, indent=2, default=float))
