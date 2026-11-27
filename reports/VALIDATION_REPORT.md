# Validation report

What was checked, how, and what came out. Rendered by `scripts/render_docs.py` from `reports/junit.xml`, `outputs/`, `docs/data/` and `git log`; template `docs/templates/VALIDATION_REPORT.md.tmpl`. Everything here concerns a **simulated** airline (Falcon Hub Airways, fictional). Headline results are the v2 holdout (seeds 2000–2019, central world), across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part. Plan names: **Simple Rulebook (naive reference)** `P0`, **Each Airport for Itself (simplified local comparator)** `P1`, **Network Plan** `P2`, **Network Plan + Extra Spares** `I125`. The subsection "v2 reviews" at the end is written by hand and is preserved when the report is re-rendered. The reviews it refers to (`reports/review_*.md`, `reports/cutaway_critique_*.md`) are **AI-generated reviews used during development, not reviews by human aviation professionals.**

---

## 1. Tests

398 tests, 0 failures, 0 errors, 0 skipped, 45 s, run at 2026-11-27T16:37:18.685541+05:30 (`reports/junit.xml`, from `GNM_RELEASE=1 pytest -m "not browser" -p no:cacheprovider -q --junitxml=reports/junit.xml`, fast and slow suites; the Playwright browser suite (`-m browser`) runs separately and is not counted in this file).

| Area | Test modules | Tests | Failed | Skipped |
|---|---|---|---|---|
| Data contracts, leakage, simulator, calibration lock | `test_contracts`, `test_leakage`, `test_leakage_runtime`, `test_sim_engine`, `test_sim_generator`, `test_calibration`, `test_calibration_lock` | 56 | 0 | 0 |
| Forecasting (incl. Monash benchmark) | `test_forecasting_classify`, `test_forecasting_evaluate`, `test_forecasting_methods`, `test_forecasting_metrics`, `test_forecasting_monash` | 47 | 0 | 0 |
| Inventory policy and Palm/EBO maths | `test_analytic`, `test_floatcalc_mirror`, `test_policy_economics`, `test_policy_forecast`, `test_policy_slow`, `test_policy_specs` | 83 | 0 | 0 |
| Optimiser / Readiness Frontier (guardrails, levers) | `test_optim_frontier`, `test_optim_greedy`, `test_optim_levers` | 32 | 0 | 0 |
| AOG Response Lab and Planner Action Centre | `test_aog_actions`, `test_aog_incidents`, `test_aog_options` | 34 | 0 | 0 |
| Freeze and holdout discipline | `test_freeze` | 3 | 0 | 0 |
| Site data export, reconciliation, rendered docs | `test_reconciliation`, `test_site_data`, `test_docs_rendered` | 75 | 0 | 0 |
| SQL, workbook, notebooks | `test_sql`, `test_workbook`, `test_notebooks` | 64 | 0 | 0 |
| Public-surface word gate and privacy | `test_public_scan` | 4 | 0 | 0 |
| Web app screens (browser) | not in this file (run separately) | — | — | — |
| **Total** | 32 modules | **398** | **0** | **0** |

No test failed.

Doc rendering is verified by `tests/test_docs_rendered.py`: every result key is filled, the README results table and headline match `docs/data/kpis.json`, the outstation sentence (8 vs 44 outstation rotables) is present, the scope line sits beside the headline numbers, the capital table shows the gross lines, the README opening makes no percentage or paired-difference claim, the calibration wording is present here and in METHODOLOGY, the rendered docs contain no forbidden wording or manufacturer names, and the README never claims a result "at every tested setting".

## 2. Calibration (P0 only, locked before any P1/P2/optimiser run)

> The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the model, not benchmarked against real airline KPIs. A line-kit variant (≈1,052 h) was measured but not adopted because it fell outside that range. All results are conditional on this choice.

Band (ASSUMED, chosen by the user after the P0 gap diagnosis and before any policy result): P0 network rotable immediate fill 0.78–0.85, material AOG 1,200–2,700 h/yr, AOG events 60–100/yr.

How P0 got there, central world, history weeks 0–103:

| Step (central world, P0, history weeks 0–103) | What changed | Rotable fill | Material AOG h/yr | Events/yr | In band |
|---|---|---|---|---|---|
| 1. Raw v2 P0 | domain rebuild (V2-SIM-1..9), uncalibrated | 0.588 | 6,700 | 152 | no |
| 2. Gap diagnosis fixes | V2-SIM-10..12: P0 fill definition, pipeline weighting, reservation bug | 0.672 | 4,708 | 136 | no |
| 3. Realism corrections A | V2-SIM-13..15: planned brake supply, AOG route retries, hub wheel shop | 0.678 | 1,712 | 97 | no |
| 4. Calibration V1 (locked) | quote accuracy only (V2-SIM-CAL) | 0.815 | 1,282 | 74 | yes |

Diagnosis: with P0's own assumptions true the engine reproduces Poisson availability (simulated rotable fill 0.943 against a demand-weighted analytic 0.948; it was 0.872 on paper before the V2-SIM-10 fix). What remains is intended realism. Switching one factor off at a time from the as-built fill of 0.669: quoted-vs-true removal rates +0.18, quoted-vs-true TAT +0.07, unstocked outstation demand under the starting-point line-station rule +0.10, and NFF works the other way (−0.09 if removed). Variants measured in memory before anything was applied:

| Variant (measured in memory, nothing applied) | Rotable fill, history / selection | Material AOG h/yr, history / selection | Events/yr, history / selection | All in band |
|---|---|---|---|---|
| V0 raw P0 (after A) | 0.678 / 0.673 | 1,712 / 1,907 | 97 / 90 | no |
| V1 quote accuracy (chosen) | 0.815 / 0.809 | 1,282 / 1,435 | 74 / 72 | yes |
| V2 line-station kit | 0.711 / 0.705 | 1,246 / 1,445 | 68 / 63 | no |
| V3 = V1 + V2 | 0.832 / 0.830 | 1,052 / 1,142 | 59 / 54 | no |
| V4 = V3 + AOG market (reference) | 0.831 / 0.830 | 912 / 976 | 57 / 52 | no |

Applied (V1, fewest changes): `quoted_mtbur_optimism` 1.10, `quoted_mtbur_noise_sd_log` 0.20, `quoted_tat_optimism` 0.95, `quoted_tat_noise_sd_log` 0.10. Not applied: the AOG-market settings and the line-station kit. Targets vs achieved per world (history / 5-seed selection mean):

| World (true-MTBUR scale) | Target | Rotable fill, history / selection | Material AOG h/yr, history / selection | Events/yr, history / selection | In the central band |
|---|---|---|---|---|---|
| central (×1.00) | central band | 0.815 / 0.809 | 1,282 / 1,435 | 74 / 72 | yes |
| low stress (×1.08) | AOG 1,200, fill 0.85 | 0.846 / 0.836 | 1,123 / 1,226 | 66 / 63 | no |
| high stress (×0.96) | AOG 2,700, fill 0.78 | 0.780 / 0.781 | 1,632 / 1,558 | 84 / 76 | yes |

Stress worlds: reliability scaled ×0.96 / ×1.00 / ×1.08 — a narrow range. Band ends: the low-stress world reaches the AOG end of the band (pooled history and selection 1,174 h/yr; band end 1,200) at 0.841 rotable fill, and the high-stress world reaches the fill end (0.781; band end 0.78) at about 1,595 h/yr, well short of the 2,700 h end, because fill binds first. The lock (`outputs/freeze/calibration_lock.json`, 12 hashed files, enforced by `tests/test_calibration_lock.py`) was written at `c2ef333` and re-written only after the non-calibration fixes V2-SIM-17/18 at `52410a4`.

## 3. Freeze and holdout chain

Frozen at 2026-11-26 08:43:36 UTC: 19 artefacts (forecast champions, P0/P1/P2 parameter tables for all worlds, frontier candidates a8a22af8…, configs), verified (`gnm.freeze.verify()` passed at export). Manifest SHA-256 `407689699aefd27f9969c34d752245353b45269b730937f2801783ffc7fe7205`.

v2 commit chain (`git log --oneline`, oldest first). The calibration lock precedes every P1/P2/optimiser commit, the freeze precedes the holdout-results commit, and the post-plan check comes after both:

- `e6c943f` Archive v1 (tag v1-archive); start v2 rebuild — D012
- `e55c9d3` v2 simulator (UNCALIBRATED, not locked): type-exclusive catalogue, curated deadlines/QPA/prices, NFF, exchange/loan + local borrow + robbery + local buy (no pool growth), deferred-item sourcing fix, AOG fitting time + per-event cost, OEM Poisson P0; P0 diagnostics only — no P1/P2 run
- `f65935d` v2 P0 gap diagnosis: fix P0 ready-rate vs fill-rate mismatch (V2-SIM-10), P0 pipeline transport weighting (V2-SIM-11), reservation blocking bug (V2-SIM-12); raw P0 rerun — still uncalibrated, not locked
- `905988b` v2 realism corrections before calibration: wheel/tyre hub shop (2-7 d TAT), brake notice-time supply (V2-SIM-13), AOG route retries (V2-SIM-14), band recorded (V2-SIM-16); raw P0 rerun — not tuned, not locked
- `6467e5c` v2 calibration variants V1–V4 measured in memory (nothing applied): V1 quote-accuracy is the only in-band candidate
- `c2ef333` v2 CALIBRATION LOCK: V1 quote-accuracy settings (user-approved), stress worlds at band ends, holdout seeds 2000–2019 — locked BEFORE any v2 P1/P2/optimiser run
- `67cd748` v2: AOG Response Lab + Planner Action Centre rebuilt on v2 history (v2 routes, robbery never ranked, AV-21 queue-jump, no fake quarantine data)
- `2cea63d` v2: forecasting champions + P1/P2 paired selection evaluation (3 worlds), selection seeds only
- `52410a4` v2 bug fixes before freeze: re-open needs whose earmarked shelf-life units expire on arrival (V2-SIM-17); atomic scenario cache (V2-SIM-18); re-lock; policy results reproduce unchanged
- `c3330e1` v2: Readiness Frontier with AV-09 guardrails (selection only); recommended I125; candidates.json a8a22af8
- `2a45af9` v2 FREEZE: champions, P0/P1/P2 tables, frontier candidates, configs hashed before the v2 holdout (seeds 2000–2019); v1 holdout archived
- `ecad6d8` v2 HOLDOUT: seeds 2000–2019, run once after freeze 2a45af9 (no forced reruns)
- `c0e43c7` Post-plan robustness check: frozen I125/P2/P0 on holdout seeds in low/high stress worlds (D015)
- `ced9d6a` v2 site export: P2-led headline framing (vs starting-point OEM-quote P0 with 8 outstation rotables), I125 as frontier option, honest findings, brake disclosure; reconciliation recomputes v2 headline

Holdout runs logged in `outputs/freeze/holdout_log.json` (the archived v1 entries are kept):

| # | Run | World | Logged at (UTC) | After the v2 freeze | Forced |
|---|---|---|---|---|---|
| 1 | `policy_holdout` | v1 (archived) | 2026-11-26 02:25:31 | — | no |
| 2 | `policy_holdout` | v1 (archived) | 2026-11-26 02:26:19 | — | yes |
| 3 | `frontier_holdout` | v1 (archived) | 2026-11-26 02:26:53 | — | no |
| 4 | `forecast_holdout` | v1 (archived) | 2026-11-26 02:27:04 | — | no |
| 5 | `v2_policy_holdout` | v2 | 2026-11-26 08:43:46 | yes | no |
| 6 | `v2_frontier_holdout` | v2 | 2026-11-26 08:44:32 | yes | no |
| 7 | `v2_forecast_holdout` | v2 | 2026-11-26 08:44:47 | yes | no |
| 8 | `v2_postplan_i125_stress_holdout` | v2 | 2026-11-26 09:36:15 | yes | no |

### Post-plan check (D015)

Added after the main v2 holdout at the user's request: the frozen central-built P0, P2 and I125 on the holdout seeds in the low- and high-stress worlds, paired against P2, no re-selection, logged once. P2 here is the central-built allocation, not the world-re-planned P2 of the policy holdout.

| World | Plan | Material AOG h/yr [95% CI] | Δ vs central-built P2 [95% CI] | Δ total annual cost vs P2 | Δ capital vs P2 |
|---|---|---|---|---|---|
| low stress | P0 | 1,480 h [1,329–1,632] | +1,334 h [1,175–1,492] | +AED 30.4M [26.7–34.1] | −AED 0.7M |
| low stress | P2 | 147 h [102–192] | — | — | — |
| low stress | I125 | 62 h [43–81] | −85 h [−125 to −45] | −AED 1.7M [−2.9 to −0.4] | +AED 7.7M |
| high stress | P0 | 1,825 h [1,651–1,999] | +1,566 h [1,382–1,749] | +AED 36.2M [31.8–40.5] | −AED 0.5M |
| high stress | P2 | 260 h [197–322] | — | — | — |
| high stress | I125 | 76 h [52–100] | −184 h [−239 to −128] | −AED 5.0M [−6.8 to −3.1] | +AED 7.5M |

## 4. The v1 archive and why

v1 is archived, not a finding. Tag `v1-archive` (06a6280); see [archive/v1/README.md](../archive/v1/README.md). The archive gives these 11 reasons, all from the aviation domain review (`reports/review_aviation.md`):

- Parts were shared across the narrowbody and widebody archetypes (AV-01).
- Cheap consumables were rated D0 and drove 29% of AOG (AV-02).
- An always-available 5-day outright rotable buy grew the float (AV-03).
- A straw-man P0 stocked to the pipeline mean (AV-04).
- Deadline classes contradicted MEL practice (AV-05).
- An engine artefact in deferred-item sourcing (AV-07).
- No robbery at the hub (AV-08).
- Over-allocation of cheap rotables (AV-09).
- AOG accounting (AV-10).
- A wear-driven brake was used as the hero part (AV-11).
- No local borrow at outstations (AV-15).

Most of them overstated P0's downtime and the size of the improvement. For transparency only, the v1 holdout (seeds retired v1 holdout (archived)) read:

| Policy (v1, archived) | Material AOG h/yr [95% CI] | Spare capital |
|---|---|---|
| P0 Simple Rulebook (stock to pipeline mean) | 2,871 [2,459–3,282] | AED 36.8M |
| P1 local optimised | 1,626 [1,243–2,008] | AED 64.6M |
| P2 network | 533 [419–646] | AED 37.0M |
| I125 v1 frontier pick | 223 [174–272] | AED 41.9M |

v1 commit chain:

- `b35d833` Phase 2: simulator + event engine, P0 Simple Rulebook baseline, calibration (P0 only) locked before any P1/P2 run
- `3cbc96c` Holdout runner (dry-run verified on selection data), freeze script, truth-recovery evaluation
- `5a1cdda` FREEZE: champions, P0/P1/P2 tables (all variants), frontier candidate set, configs hashed before holdout
- `94d8796` HOLDOUT: policy (3 variants), frontier candidates, forecast champions on history continuation, truth recovery — run once after freeze (one logged forced rerun of a block that crashed before output; see D010)

v2 fixed the problems as domain corrections chosen before any v2 result, recalibrated P0 only, locked, and ran on fresh holdout seeds (2000–2019), because the v1 seeds had been seen.

### v1 holdout incident (D010)

The first `policy_holdout` attempt crashed *before producing any output*. Parallel workers generated the same uncached holdout scenario at the same moment and one read a truncated pickle cache file; the dry run hadn't hit this because the selection scenarios were already cached. Fix: `run_holdout.py` now warms the scenario cache sequentially before multiprocessing. That block was re-run once with `force=True`, which is logged in `outputs/freeze/holdout_log.json`. No holdout results existed or were seen before the rerun, and no frozen artefact changed (`gnm.freeze.verify()` passed). The root cause (a non-atomic scenario-cache write) was fixed in V2-SIM-18 before the v2 freeze; the v2 holdout had 0 forced reruns.

## 5. Selection versus holdout

Selection seeds 100–119 were used for every choice; holdout seeds 2000–2019 were run once. Central world, KPIs over weeks 104–155, annualised.

| KPI | Plan | Selection (seeds 100–119) | Holdout (seeds 2000–2019) [95% CI] | Selection inside holdout CI |
|---|---|---|---|---|
| Immediate fill rate | P0 | 98.9% | 98.9% [98.9–99.0] | yes |
| | P2 | 97.7% | 97.7% [97.5–97.8] | yes |
| Material AOG hours / year | P0 | 1,727 h | 1,690 h [1,555–1,826] | yes |
| | P2 | 235 h | 210 h [146–274] | yes |
| Spare capital | P0 | AED 48.5M | AED 48.4M [48.3–48.6] | yes |
| | P2 | AED 49.1M | AED 49.0M [48.9–49.2] | yes |
| Total annual cost | P0 | AED 72.3M | AED 69.7M [65.7–73.7] | yes |
| | P2 | AED 36.8M | AED 35.8M [33.4–38.1] | yes |
| Expedite spend / year | P0 | AED 1.8M | AED 1.7M [1.5–1.9] | yes |
| | P2 | AED 1.7M | AED 1.6M [1.4–1.8] | yes |
| AOG events / year | P0 | 77.5 | 78.0 [73.9–82.0] | yes |
| | P2 | 9.6 | 8.6 [6.7–10.5] | yes |
| Material AOG hours / year | P1 | 545 h | 566 h [452–680] | yes |
| Material AOG hours / year | I125 (frontier) | 92 h | 76 h [50–102] | yes |
| Material AOG hours / year | I110 (frontier) | 148 h | 144 h [86–202] | yes |
| Material AOG hours / year | B150 (frontier) | 64 h | 41 h [30–52] | no |
| I125 − P2 material AOG (paired) | I125 | −143 h | −134 h [−181 to −87] | yes |

Reading: for P2 the selection-seed value of 6 of 6 headline KPIs lies inside the holdout 95% CI (material AOG 235 h on selection, 210 h [146–274] on holdout); I125 scored 92 h on selection and 76 h [50–102] on holdout (inside the CI).

Forecasting: frozen champions re-scored on the holdout (12 origins, weeks 104–148):

| Demand class | Part class | Parts | Frozen champion | Holdout MASE | Rank | Best in hindsight |
|---|---|---|---|---|---|---|
| erratic | C | 3 | reliability-exposure | 0.595 | 6 of 9 | ADIDA (0.582) |
| insufficient_data | R | 1 | reliability-exposure | 1.095 | 3 of 9 | SBA (1.073) |
| intermittent | C | 13 | reliability-exposure | 0.783 | 3 of 9 | SBA (0.776) |
| intermittent | E | 32 | TSB | 0.954 | 1 of 9 | TSB (0.954) |
| intermittent | R | 37 | SBA | 0.917 | 6 of 9 | TSB (0.886) |
| lumpy | C | 2 | reliability-exposure | 0.788 | 6 of 9 | IMAPA (0.772) |
| smooth | C | 27 | SBA | 0.690 | 1 of 9 | SBA (0.690) |
| smooth | E | 3 | reliability-exposure | 0.726 | 2 of 9 | SBA (0.722) |
| smooth | R | 2 | reliability-exposure | 0.611 | 1 of 9 | reliability-exposure (0.611) |

The frozen champion was best in 3 of 9 cells. Rotable policies size floats on the reliability-exposure rate, not on the MASE champion. Reliability vs the best Croston-family method on removal-driven parts (holdout): +0.010 [−0.014 to 0.036]; the reliability model does not beat the best Croston-family method on MASE; the difference is not significant, so it is a tie on point accuracy (75 parts, 95% bootstrap CI over parts).

## 6. Truth recovery (evaluation only)

`gnm.eval.truth_recovery` is the only code that reads the hidden truth. Metric: median absolute log error |ln(estimate / truth)|.

| Parameter | Parts | Median abs log error, vendor quote | Median abs log error, history estimate | Estimate closer |
|---|---|---|---|---|
| MTBUR, rotables + expendables | 75 | 0.139 | 0.071 | 64% |
| MTBUR, rotables | 40 | 0.165 | 0.069 | 65% |
| MTBUR, expendables | 35 | 0.128 | 0.072 | 63% |
| Purchase lead time, all parts | 120 | 0.061 | 0.062 | — |

PS4 GN-33-E033: true lead time 73.2 d after the planted change, planner estimate 69.9 d, quoted 24.8 d.

## 7. Analytic models versus the simulator

Palm vs simulation for rotable floats (P1, central, selection seeds; `outputs/policies/palm_vs_sim.csv`):

| Group | Rows with demand | Simulated requests | Palm fill (mean) | Simulated fill (mean) | Mean abs gap | ΣEBO / Σ simulated backorders |
|---|---|---|---|---|---|---|
| AUH | 40 | 15,458 | 0.951 | 0.901 | 0.063 | 1.17 / 0.62 |
| Outstations | 106 | 1,884 | 0.985 | 0.997 | 0.016 | 0.08 / 0.00 |

at AUH mean Palm fill 0.951 vs simulated immediate fill 0.901 over 40 rotables (mean absolute gap 0.063): the simulated hub is below Palm because the next serviceable unit first reinstates robbed donors and hands back loans; at outstations 0.985 vs 0.997, because Palm with a local repair loop ignores resupply from AUH.

Optimiser proxy vs simulation: the analytic model predicts 2,507 h a year for P0 against 1,690 h simulated on the holdout, 130 h against 210 h for P2 and 39 h against 76 h for I125. It overstates P0 and understates the network plans, so it is a ranking heuristic, not a forecast of AOG hours; it ranks well (r = 0.97 across the 25 frontier points on the holdout, r = 0.97 on selection seeds).

Greedy check: on a small separable, convex toy case the greedy allocation equals the brute-force optimum at every greedy breakpoint (unit test `tests/test_optim_greedy.py::test_greedy_equals_brute_force_at_breakpoints`, passing); no exact comparison exists for the full, non-separable network problem.

AOG reconstruction: 2,564 of 2,564 history material AOG hours reconstructed request by request across 148 incidents (reconciles). Counterfactual: history took the rank-1 option in 117 of 148 requests; excluding the 12 robbery cases (never ranked), the actual route gave 2,353 h against 2,367 h for the ranked option, so the starting-point AOG desk already takes about the best per-incident route and the lever is positioning.

## 8. Known limitations that bear on validity

- The world, the methods and the evaluation were designed by the same author; the reliability model has a structural home advantage.
- Every policy depends on the AOG recovery routes: with the routes switched off (selection seeds, a structural stress) material AOG rises from 1,727 h to 42,070 h a year under P0, from 235 h to 18,320 h under P2 and from 92 h to 11,080 h under I125.
- The P0 calibration lever was quote accuracy, and the starting-point line-station rule is a deliberate weakness of P0.
- Confidence intervals reflect seed-to-seed noise in one simulated world, not parameter uncertainty. Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.
- The downtime clock starts when the part is removed (for no-go items; for deferrable items, when the rectification window runs out), not at the next scheduled departure, and overnight and other non-flying hours count in full. Fitting and release-to-service time is included. A departure-based count would be lower for every plan.
- Full list: [LIMITATIONS.md](../LIMITATIONS.md).

**Donor downtime.** Hours that donor aircraft (aircraft that gave up a part to another) spend waiting for a replacement are not reconstructible from current logs for the frozen test runs, so no per-plan figure is given. What the logs do allow (post-plan, exploratory): parts borrowed from another of our aircraft per year in the test runs, Simple Rulebook (naive reference) `P0` 33.2 [28.5–37.9]; Each Airport for Itself (simplified local comparator) `P1` 31.3 [27.1–35.4]; Network Plan `P2` 22.5 [18.4–26.6]; for the Network Plan + Extra Spares `I125` this is not reconstructible either. For scale only, in the historical record of the Simple Rulebook (naive reference) `P0` (history weeks 0–103, one simulated history, not the test runs), donor aircraft were held about 5,285 h a year, beside 1,282 h a year of counted waiting-for-part downtime in that same history. Gross donor hours are an upper bound: a donor may already be in maintenance or not scheduled to fly.

---

## Phase 5 reviewer findings and fixes

### v1-era reviews (archived world)

These reviews were run on the v1 world before it was archived. The aviation review is the reason v1 was archived; the correctness and design findings were fixed in v1 and the fixes carried into v2 where the code survived.

- [`reports/review_aviation.md`](review_aviation.md): > **AI-generated review used during development — not a review by a human aviation professional.**; 4 critical, 11 major, 13 minor.
- [`reports/review_aviation_v2.md`](review_aviation_v2.md): > **AI-generated review used during development — not a review by a human aviation professional.**; see file.
- [`reports/review_correctness.md`](review_correctness.md): > **AI-generated review used during development — not a review by a human aviation professional.**; 0 critical, 5 major, 16 minor.
- [`reports/review_design.md`](review_design.md): > **AI-generated review used during development — not a review by a human aviation professional.**; overall 3.61 / 5.
- [`reports/review_design_2.md`](review_design_2.md): > **AI-generated review used during development — not a review by a human aviation professional.**; overall 4.23 / 5.
- [`reports/review_design_3.md`](review_design_3.md): > **AI-generated review used during development — not a review by a human aviation professional.**; overall 4.22 / 5.
- [`reports/review_design_4.md`](review_design_4.md): > **AI-generated review used during development — not a review by a human aviation professional.**; overall 4.33 / 5.
- [`reports/review_design_5.md`](review_design_5.md): > **AI-generated review used during development — not a review by a human aviation professional.**; overall 4.20 / 5.

### v2 reviews

**Aviation domain review (fresh, v2): `reports/review_aviation_v2.md`.** 3 critical, 11 major, 11 minor.
- **Fixed (wording/UI, design wave C, db8890c):** AV2-03 (P2 re-mixes the float: buys 68 rotables ≈ AED 8.4M and sheds 20 ≈ AED 3.1M, net ≈ +AED 0.6M; "positioning the existing float" removed); AV2-10 (v1 leftovers removed); AV2-11 (band wording: "an ASSUMED plausibility band chosen before any policy comparison"); robbery wording (used automatically first at AUH with approval flagged; never ranked by the AOG Lab); AV2-14 (outstation float view uses the resupply time from AUH); consistent MEL-analogue wording; the 120-part scope stated.
- **Disclosed, not fixed (author decision; LIMITATIONS 29–39):** AV2-01 robbed-donor downtime not counted; AV2-02 P0's outstation stock mostly unusable brakes, no line kit, no re-provisioning; AV2-04 wheels as rare unscheduled removals; AV2-05 phantom brake positioning; AV2-06 hero-part rate and no warranty escalation; AV2-07 robbery as the automatic first route; AV2-08 no cost of deferral; AV2-09 AOG from removal, not departure; AV2-12 exchange/loan merged, no pool contract; AV2-13 unit costs per family; and the minor items. Each is described with its likely direction of bias.

**Design critic (fresh, v2): `reports/review_design_5.md`.** 4.20/5, story mode 4.43. Every functional bug (F1–F9) and top issue (1–12) was fixed in design wave C (db8890c). A further fresh design re-score follows.
