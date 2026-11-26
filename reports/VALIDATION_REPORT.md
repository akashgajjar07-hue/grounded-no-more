# Validation report

What was checked, how, and what came out. Rendered by `scripts/render_docs.py` from `reports/junit.xml`, `outputs/`, `docs/data/` and `git log`; template `docs/templates/VALIDATION_REPORT.md.tmpl`. Everything here concerns a **simulated** airline (Falcon Hub Airways, fictional). The section "Phase 5 reviewer findings and fixes" at the end is written by hand and is preserved when the report is re-rendered.

---

## 1. Tests

467 tests, 0 failures, 0 errors, 0 skipped, 305 s, run at 2026-11-26T10:26:05.316039+05:30 (`reports/junit.xml`; summary in `reports/test_results.txt`).

| Area | Test modules | Tests | Failed |
|---|---|---|---|
| Data contracts, leakage, simulator, calibration | `test_contracts`, `test_leakage`, `test_sim_engine`, `test_sim_generator`, `test_calibration`, `test_calibration_lock` | 42 | 0 |
| Forecasting (incl. Monash benchmark) | `test_forecasting_classify`, `test_forecasting_evaluate`, `test_forecasting_methods`, `test_forecasting_metrics`, `test_forecasting_monash` | 47 | 0 |
| Inventory policy and Palm/EBO maths | `test_analytic`, `test_floatcalc_mirror`, `test_policy_economics`, `test_policy_forecast`, `test_policy_slow`, `test_policy_specs` | 75 | 0 |
| Optimiser / Readiness Frontier | `test_optim_frontier`, `test_optim_greedy`, `test_optim_levers` | 28 | 0 |
| AOG Response Lab and Planner Action Centre | `test_aog_actions`, `test_aog_incidents`, `test_aog_options` | 31 | 0 |
| Freeze and holdout discipline | `test_freeze` | 3 | 0 |
| Site data export and reconciliation | `test_reconciliation`, `test_site_data` | 18 | 0 |
| Web app screens (browser) | `test_site_actions`, `test_site_aog`, `test_site_forecast`, `test_site_method`, `test_site_mission`, `test_site_network`, `test_site_optimiser`, `test_site_overlays`, `test_site_parts`, `test_site_rotables`, `test_site_shared_apis`, `test_site_wave3_shared` | 161 | 0 |
| Other | test_docs_rendered, test_leakage_runtime, test_notebooks, test_sql, test_workbook | 62 | 0 |
| **Total** | 43 modules | **467** | **0** |

Doc rendering is checked by `tests/test_docs_rendered.py`: no result placeholder survives in the rendered docs, and the headline KPI numbers in the README match `docs/data/kpis.json`.

## 2. Calibration (P0 only, locked before any P1/P2 run)

The generator was calibrated against ASSUMED bands using the legacy policy P0 only, then locked (`outputs/freeze/calibration_lock.json`, enforced by `tests/test_calibration_lock.py`) before any data-driven policy was built.

| Metric (P0, central history, weeks 0–103) | Target band (ASSUMED) | Achieved | In band |
|---|---|---|---|
| immediate fill rate | 0.930–0.970 | 0.958 | yes |
| rotable immediate fill rate | 0.800–0.880 | 0.832 | yes |
| aog hours per year | 1,500–3,500 | 2,754 | yes |
| aog events per year | 60–250 | 90 | yes |

## 3. Freeze and holdout chain

Frozen at 2026-11-26 02:25:21 UTC: 19 artefacts (forecast champions, P0/P1/P2 parameter tables for all variants, frontier candidates, configs), verified (`gnm.freeze.verify()` passed at export). Manifest SHA-256 `fdd5bc8d5057c1307511ebb46367f7875790b0a21ca8b99304bfb045087fc77d`.

Commit chain (`git log --oneline`, oldest first; the freeze commit precedes the holdout-results commit):

- `2fa3607` Phase 2 (part): forecasting module + Monash Car Parts benchmark, docs scaffold, analytic float maths, freeze tooling
- `8b7a631` Phase 2: simulator + event engine, P0 legacy baseline, calibration (P0 only) locked before any P1/P2 run
- `69c2acb` Phase 2: design system — tokens, components, chart theme, map, original blueprint SVG illustrations, app shell with fixtures
- `edfd23f` Phase 3: AOG Response Lab (incident timelines, sourcing options, counterfactual) + Planner Action Centre exceptions
- `fda0a15` Phase 3: forecasting champions (frozen candidates), P1 local + P2 network policies, paired selection-seed evaluation across calibration variants
- `e3dd9fc` Holdout runner (dry-run verified on selection data), freeze script, truth-recovery evaluation
- `4a03e4d` Phase 3: Readiness Frontier on champion forecasts with P2 base; P0/P1/P2 + 20 candidates in candidates.json
- `95dfce5` FREEZE: champions, P0/P1/P2 tables (all variants), frontier candidate set, configs hashed before holdout
- `ccf6f2b` HOLDOUT: policy (3 variants), frontier candidates, forecast champions on history continuation, truth recovery — run once after freeze (one logged forced rerun of a block that crashed before output; see D010)
- `7763a58` Phase 4: site data exporter (12 JSON files from pipeline outputs, holdout headline) + reconciliation tests
- `dfc5c26` Release prep: remove layout fixtures, full test suite 345/345 (fast+slow+browser), refreshed validation export
- `b950c5a` Live deploy verified: Playwright smoke on GitHub Pages, all routes x 2 viewports

Holdout runs logged in `outputs/freeze/holdout_log.json`, all after the freeze:

| # | Run | Logged at (UTC) | Forced |
|---|---|---|---|
| 1 | `policy_holdout` | 2026-11-26 02:25:31 | no |
| 2 | `policy_holdout` | 2026-11-26 02:26:19 | yes |
| 3 | `frontier_holdout` | 2026-11-26 02:26:53 | no |
| 4 | `forecast_holdout` | 2026-11-26 02:27:04 | no |

### Holdout incident (D010)

The first `policy_holdout` attempt crashed *before producing any output*. Parallel workers generated the same uncached holdout scenario at the same moment and one read a truncated pickle cache file; the dry run hadn't hit this because the selection scenarios were already cached. Fix: `run_holdout.py` now warms the scenario cache sequentially before multiprocessing. That block was re-run once with `force=True`, which is logged in `outputs/freeze/holdout_log.json`. No holdout results existed or were seen before the rerun, and no frozen artefact changed (`gnm.freeze.verify()` passed).

### Reporting note (D011)

Holdout results are reported as-is, including that the frozen MASE champion for intermittent rotables (`naive`) ranked 9/9 on the holdout. The policies size rotables on the reliability-exposure rate (POL decision), so the policy results don't depend on that champion. The B250 frontier point shows one unstable seed (very wide CI); it is reported, not removed.

## 4. Selection versus holdout

Selection seeds 100–119 were used for every choice; holdout seeds 1000–1019 were run once. Central variant, KPIs over weeks 104–155, annualised.

| KPI | Plan | Selection (seeds 100–119) | Holdout (seeds 1000–1019) [95% CI] | Selection inside holdout CI |
|---|---|---|---|---|
| Immediate fill rate | P0 | 95.6% | 95.4% [95.2–95.6] | yes |
| | I125 | 98.1% | 98.1% [97.9–98.3] | yes |
| Material AOG hours / year | P0 | 2,938 h | 2,871 h [2,459–3,282] | yes |
| | I125 | 118 h | 223 h [174–272] | no |
| Spare capital | P0 | AED 36.2M | AED 36.8M [36.2–37.4] | yes |
| | I125 | AED 41.6M | AED 41.9M [41.4–42.3] | yes |
| Total annual cost | P0 | AED 86.9M | AED 86.0M [77.5–94.5] | yes |
| | I125 | AED 29.4M | AED 31.4M [30.4–32.5] | no |
| Expedite spend / year | P0 | AED 995,316 | AED 1.0M [0.9–1.1] | yes |
| | I125 | AED 1.1M | AED 1.1M [1.0–1.2] | yes |
| AOG events / year | P0 | 87.4 | 86.2 [79.5–93.0] | yes |
| | I125 | 6.2 | 8.8 [6.5–11.1] | no |
| Material AOG hours / year | P1 | 1,677 h | 1,626 h [1,243–2,008] | yes |
| Material AOG hours / year | P2 | 428 h | 533 h [419–646] | yes |

Reading: the legacy baseline replicated closely. The recommended plan I125 was optimistic on selection: 118 h on selection against 223 h [174–272] on holdout (+89%), while P2 moved +24%. The paired improvement of I125 over P2 replicated: −310 h [−383 to −238] on selection, −310 h [−408 to −212] on holdout.

Forecasting: frozen champions re-scored on the holdout (12 origins, weeks 104–148):

| Demand class | Part class | Parts | Frozen champion | Holdout MASE | Rank of 9 | Best in hindsight |
|---|---|---|---|---|---|---|
| erratic | C | 6 | TSB | 0.724 | 6 | reliability-exposure (0.711) |
| insufficient_data | E | 2 | TSB | 1.031 | 2 | naive (0.576) |
| intermittent | C | 4 | IMAPA | 1.054 | 6 | reliability-exposure (1.008) |
| intermittent | E | 30 | TSB | 0.879 | 1 | TSB (0.879) |
| intermittent | R | 38 | naive | 1.072 | 9 | TSB (0.932) |
| smooth | C | 35 | SBA | 0.723 | 1 | SBA (0.723) |
| smooth | E | 3 | SBA | 0.674 | 2 | reliability-exposure (0.650) |
| smooth | R | 2 | SBA | 0.814 | 2 | reliability-exposure (0.807) |

The intermittent-rotable champion (naive) ranked last. The policies size rotables on the reliability-exposure rate, not on the MASE champion, so policy results do not depend on it. Reliability vs best Croston-family method on removal-driven parts (holdout): +0.013 [−0.010 to 0.037]; the reliability model does not beat the best Croston-family method on MASE; the difference is not significant, so it is a tie on point accuracy (75 parts, 95% bootstrap CI over parts).

## 5. Truth recovery (evaluation only)

`gnm.eval.truth_recovery` is the only code that reads the hidden truth. Metric: median absolute log error |ln(estimate / truth)|.

| Parameter | Parts | Median abs log error, vendor quote | Median abs log error, estimate | Estimate closer |
|---|---|---|---|---|
| MTBUR, rotables + expendables | 75 | 0.369 | 0.109 | 79% |
| MTBUR, rotables | 40 | 0.416 | 0.126 | 80% |
| MTBUR, expendables | 35 | 0.282 | 0.096 | 77% |
| Purchase lead time, all parts | 120 | 0.066 | 0.064 | — |

PS4 GN-30-E025: true lead time 165.2 d, planner estimate 156.5 d, quoted 65.2 d.

## 6. Analytic models versus the simulator

Palm vs simulation for rotable floats (P1, central, selection seeds; `outputs/policies/palm_vs_sim.csv`):

| Group | Rows with demand | Simulated requests | Palm availability (mean) | Simulated fill (mean) | Mean abs gap | ΣEBO / Σ simulated backorders |
|---|---|---|---|---|---|---|
| AUH | 40 | 15,493 | 0.928 | 0.929 | 0.046 | 1.83 / 0.89 |
| Outstations | 167 | 2,196 | 0.982 | 0.999 | 0.019 | 0.20 / 0.00 |

Optimiser proxy vs simulation: for P2 the model predicts 321 h a year against 533 h simulated on the holdout; for I125 26 h against 223 h; for P0 3,017 h against 2,871 h. The proxy is a ranking heuristic, not a forecast of AOG hours, and it ranks well: correlation r = 0.95 across the 23 frontier points (r = 0.96 on selection seeds).

Greedy optimality: on a small separable, convex toy case the greedy allocation equals the brute-force optimum at every greedy breakpoint (unit test `tests/test_optim_greedy.py::test_greedy_equals_brute_force_at_breakpoints`, passing); no exact comparison exists for the full, non-separable network problem.

AOG reconstruction: 5,507 of 5,507 history AOG hours reconstructed request by request across 180 incidents (reconciles).

## 7. Known limitations that bear on validity

- The world, the methods and the evaluation were designed by the same author; the reliability model has a structural home advantage (removals are generated from exposure ÷ MTBUR).
- Every policy depends on the AOG-desk emergency purchase: with it switched off (selection seeds) material AOG rises from 428 h to 14,400 h a year under P2, from 118 h to 11,230 h under I125, and from 2,938 h to 268,500 h under P0.
- In the low-stress variant I125 is not worth its extra capital over P2: on the selection seeds it saved 3.5 AOG h/yr [−3.9 to 10.8] versus P2 at a net annual cost of AED 0.95M [0.73–1.17], and the rule picks P2 there (the frontier holdout ran the central variant only).
- Confidence intervals reflect seed-to-seed noise in one simulated world, not parameter uncertainty.
- The rolling-origin forecast scoring gives the reliability model the realised flying programme of the forecast weeks.
- Full list: [LIMITATIONS.md](../LIMITATIONS.md).

---

## Phase 5 reviewer findings and fixes

*To be completed by the lead.*
