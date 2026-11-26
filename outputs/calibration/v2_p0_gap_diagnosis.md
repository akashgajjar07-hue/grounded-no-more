# v2 P0 gap diagnosis: analytic Poisson availability vs simulated rotable fill

Diagnostic only. No generator parameter was tuned and nothing is locked. The counterfactual runs switch one factor at a time in memory (`scripts/v2_p0_gap_diagnosis.py`). Pooled over the history (seed 7, weeks 0–103) and 5 selection seeds (100–104, weeks 78–155, KPIs from week 104). Fill is rotable immediate fill.

**Analytic availability** = P0's own expectation from its own inputs: P(Poisson(quoted pipeline mean) ≤ S − 1) at AUH, using P0's quoted rate and its quoted pipeline.

## 1. The 10 worst gaps (as diagnosed, before the fixes)

Pre = before the fixes; post = after. The decomposition columns give the change in fill when ONE factor is switched off, from the pre-fix world:

* **rate**: true MTBUR = quoted
* **TAT**: true TAT mean = quoted
* **outst.**: all rotable demand at AUH
* **NFF**: no-fault-found off (negative: NFF helps P0)
* **NB**: Poisson instead of NB frailty
* **routes**: AOG routes and robbery off

| PN | Description | Deadline | S pre / post | Quoted pipeline mean | Analytic pre | Sim fill pre | Sim fill post | Outstation demand share | True/quoted rate | True / quoted TAT (d) | rate | TAT | outst. | NFF | NB | routes | Ideal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GN-27-R008 | Spoiler servo control (NB) | D10 | 8 / 9 | 4.98 | 0.869 | 0.127 | 0.214 | 0.03 | 2.09 | 78 / 72 | +0.61 | +0.04 | +0.01 | -0.05 | -0.01 | +0.01 | 0.88 |
| GN-32-R015 | Main wheel and tyre assembly (NB) | D0 | 6 / 7 | 3.03 | 0.913 | 0.211 | 0.302 | 0.49 | 1.83 | 52 / 54 | +0.26 | +0.00 | +0.25 | +0.00 | +0.01 | +0.00 | 0.94 |
| GN-32-R014 | Nose wheel steering actuator (NB) | D0 | 6 / 7 | 2.64 | 0.948 | 0.298 | 0.345 | 0.52 | 2.50 | 68 / 76 | +0.21 | -0.04 | +0.36 | -0.02 | +0.03 | -0.01 | 0.98 |
| GN-27-R007 | Aileron servo control (NB) | D0 | 3 / 4 | 0.92 | 0.934 | 0.309 | 0.382 | 0.60 | 1.64 | 81 / 57 | +0.12 | +0.04 | +0.45 | -0.02 | +0.14 | +0.00 | 0.97 |
| GN-34-R019 | Air data inertial reference unit (NB) | D3 | 5 / 6 | 2.73 | 0.859 | 0.315 | 0.599 | 0.06 | 2.10 | 63 / 48 | +0.57 | +0.28 | +0.10 | -0.20 | +0.02 | +0.06 | 0.92 |
| GN-34-R021 | Pitot probe (NB) | D3 | 5 / 6 | 2.93 | 0.827 | 0.298 | 0.509 | 0.04 | 2.04 | 38 / 33 | +0.51 | +0.10 | +0.10 | -0.12 | +0.09 | +0.09 | 0.80 |
| GN-27-R031 | Elevator power control unit (WB) | D0 | 5 / 6 | 1.98 | 0.949 | 0.424 | 0.457 | 0.53 | 1.54 | 60 / 62 | +0.11 | +0.00 | +0.47 | +0.00 | +0.07 | +0.00 | 0.97 |
| GN-32-R016 | Nose wheel and tyre assembly (NB) | D0 | 5 / 6 | 1.97 | 0.950 | 0.453 | 0.480 | 0.52 | 1.31 | 79 / 73 | +0.03 | +0.01 | +0.44 | +0.00 | +0.01 | +0.00 | 0.95 |
| GN-34-R018 | Air data module (NB) | D10 | 19 / 20 | 14.21 | 0.870 | 0.376 | 0.450 | 0.03 | 1.38 | 88 / 60 | +0.47 | +0.48 | +0.04 | -0.26 | +0.04 | +0.02 | 0.88 |
| GN-21-R001 | Pack flow control valve (NB) | D10 | 1 / 2 | 0.14 | 0.866 | 0.373 | 0.806 | 0.06 | 2.11 | 16 / 11 | +0.28 | +0.18 | +0.25 | -0.01 | +0.19 | +0.21 | 0.79 |

Per-PN effects interact, so the columns do not add up exactly. Each PN has 14–700 requests across the 6 runs. All 40 rotables are listed in the json.

## 2. Pooled factor sizes (rotable fill, 6-run pooled; AOG h/yr, 6-run mean)

| Counterfactual | Fill pre-fix | Hub fill pre-fix | AOG h/yr pre-fix | Fill post-fix | Hub fill post-fix | AOG h/yr post-fix |
|---|---|---|---|---|---|---|
| full (as built) | 0.586 | 0.653 | 7,412 | 0.669 | 0.747 | 5,520 |
| rates = quoted | 0.782 | 0.869 | 3,415 | 0.848 | 0.942 | 2,347 |
| TAT mean = quoted | 0.666 | 0.744 | 7,225 | 0.740 | 0.827 | 5,378 |
| deterministic TAT | 0.587 | 0.655 | 7,391 | 0.670 | 0.748 | 5,338 |
| Poisson (no NB frailty) | 0.593 | 0.659 | 7,477 | 0.679 | 0.755 | 5,536 |
| no condemnation | 0.588 | 0.655 | 7,313 | 0.671 | 0.749 | 5,535 |
| no NFF | 0.498 | 0.555 | 8,556 | 0.575 | 0.641 | 6,320 |
| no transport | 0.590 | 0.659 | 6,748 | 0.682 | 0.761 | 5,085 |
| no shop queue | 0.587 | 0.654 | 7,378 | 0.670 | 0.749 | 5,486 |
| all rotable demand at AUH | 0.681 | 0.681 | 6,063 | 0.770 | 0.770 | 4,273 |
| AOG routes + robbery off | 0.552 | 0.617 | 136,996 | 0.637 | 0.712 | 110,380 |
| ideal (P0 assumptions hold) | 0.880 | 0.880 | 3,004 | 0.943 | 0.943 | 2,081 |
| 104-week warm-up (selection seeds) | n/a | n/a | n/a | 0.662 | 0.738 | 6,182 |

Demand-weighted analytic availability with all demand at AUH: pre-fix 0.872 (P0 was **not** reaching its own 90–95% target even on paper); post-fix 0.948.

Quote vs truth, by design: the mean true/quoted removal-rate ratio = optimism 1.25 × E[lognormal(0, 0.35)] = 1.329. Realised over the 40 rotables: mean 1.347, median 1.287, range 0.639–2.5 (PS1 is planted at 2.5). The true/quoted TAT ratio by design is 1.124; realised mean 1.115, range 0.816–1.544 (PS2 is planted at 88/60).

## 3. Cause classification

| # | Cause | Class | Measured size | Action |
|---|---|---|---|---|
| 1 | P0 sized the protection level on the ready rate P(N ≤ S), but the engine's immediate fill is P(N ≤ S − 1): a demand is filled only if a spare is on the shelf. So P0 under-provisioned against its own 90–95% target (analytic 0.872 on paper). | DESIGN MISMATCH | Rotable fill +0.083 (0.586 → 0.669), AOG 7,412 → 5,520 h/yr (6-run mean), capital +AED 5.0 M (40.6 → 45.6 M). Ideal world: 0.880 → 0.943. Measured together with #2. | Fixed: V2-SIM-10. S = smallest S with P(N ≤ S − 1) ≥ p. |
| 2 | P0's quoted pipeline weighted core return at 50% for every PN. The engine's demand puts D3/D10 removals mostly at the hub (92% deferral) and wear-planned brakes always at the hub. | DESIGN MISMATCH (minor, conservative) | Pipeline overstated by ~2.3 d (D3/D10) and 2.5 d (brakes) on 15–90 d. Reduces S slightly; included in #1's net figure. | Fixed: V2-SIM-11. Same public definition for P0 and for engine loop seeding. |
| 3 | A scheduled need (kit / planned removal) at its need time was blocked by reservations for LATER scheduled needs (priority inversion). | BUG | ≈0 on measured fill: brakes are D0 and already exempt; consumable fill was already 1.000. | Fixed: V2-SIM-12. |
| 4 | Loop units vs base stock (the POL-6 question) | Checked: no double counting | P0 hands AUH S − seeded loop units; the engine seeds round(quoted rate × pipeline). The ideal world reproduces the analytic value (post-fix 0.943 vs 0.948). | none |
| 5 | Robbery and loan semantics | Checked: neutral or helpful | A borrowed unit is replaced by the first own unit, and a donor is reinstated from the next own unit. Both are equivalent to a backorder: no extra serviceable stock is consumed. Switching the routes off LOWERS fill (−0.032 post-fix). | none |
| 6 | What immediate fill counts | Checked | Deferred outstation removals rectified at the hub are generated with station = AUH and counted at AUH (not as outstation misses). Only D0 removals stay at the outstation. | none |
| 7 | True vs quoted removal rate (vendor optimism 1.25 + lognormal noise 0.35) | INTENDED REALISM | +0.178 fill, −3,173 AOG h/yr if removed | Keep in principle; this is what history-based planning exploits. Its magnitude is a calibration choice (see §5). |
| 8 | True vs quoted shop TAT (optimism 0.90 + noise 0.15) | INTENDED REALISM | +0.071 fill | Keep; magnitude is a calibration choice. |
| 9 | D0 demand at outstations with no line-station unit (P0's ≥ 4 quoted removals/yr rule); 10.5% of rotable demand fills ≈0 | INTENDED (legacy rule) | +0.101 fill, −1,247 AOG h/yr if all demand were at the hub. Emergency transfers alone ≈ 800 AOG h/yr (9–16 h + fitting each). | Keep: this is the P0 rule. |
| 10 | No-fault-found shortens the pipeline (P0 assumes full TAT) | INTENDED REALISM (favours P0) | -0.094 fill if NFF removed | Keep. |
| 11 | NB weekly frailty (overdispersion) | INTENDED | +0.010 | Keep. |
| 12 | Condemnation + replacement lead time; shop queue; TAT variability; transport beyond P0's assumption | INTENDED | +0.002 / +0.001 / +0.001 / +0.013 | Keep. |
| 13 | Warm-up / initial state | No effect | 104-week warm-up -0.007; history year 1 vs year 2 fill 0.690 / 0.654 | none |
| 14 | Wear-planned brakes | INTENDED, with a scope limit | NB/WB brakes are 2 of the top 3 AOG drivers. The 5–10-day notice is used for reservation only; there is no pre-need exchange or loan (out of v2 scope). Brakes' fill is close to their analytic value in the ideal run. | Keep; flag for scope. |

## 4. Raw P0 after the fixes (history + 5 selection seeds)

| Metric | History pre-fix | History post-fix | Year 1 / Year 2 post | Selection mean post |
|---|---|---|---|---|
| Immediate fill (all) | 0.980 | 0.983 | 0.986 / 0.980 | 0.981 |
| Rotable fill | 0.588 | 0.672 | 0.690 / 0.654 | 0.668 |
| Expendable fill | 0.928 | 0.928 | 0.973 / 0.887 | 0.895 |
| Consumable fill | 1.000 | 1.000 | 1.000 / 1.000 | 1.000 |
| Material AOG h/yr (fleet) | 6,700.500 | 4,708.500 | 4,443.000 / 4,974.000 | 5,681.800 |
| AOG events/yr | 152.000 | 136.000 | 138.000 / 134.000 | 132.200 |

* **Scale:** AOG h per aircraft-year 167.5 → 117.7. P0 capital AED 40.6 M → 45.6 M (selection mean 46.0 M). Consumable share of AOG: 0.0%.
* **By trigger:** D0_no_stock 3,022 h (64%); deadline_expired 1,718 h (36%)
* **By class:** R 3,747 h (79%); E 994 h (21%)
* **By station:** AUH 3,270 h (69%); CAI 370 h (8%); JED 339 h (7%); BOM 322 h (7%); FRA 230 h (5%); LHR 116 h (2%); SIN 94 h (2%)
* **By archetype:** narrowbody 2,485 h (52%); widebody 2,256 h (48%)

| Top AOG PN | Description | Class | Deadline | Unit cost AED | AOG h/yr |
|---|---|---|---|---|---|
| GN-32-R015 | Main wheel and tyre assembly (NB) | R | D0 | 15,574 | 731 |
| GN-32-R036 | Carbon brake assembly (WB) | R | D0 | 270,041 | 616 |
| GN-32-R013 | Carbon brake assembly (NB) | R | D0 | 149,600 | 516 |
| GN-33-E033 | Emergency light battery pack | E | D10 | 4,919 | 412 |
| GN-24-R029 | Auto-transformer rectifier unit (WB) | R | D10 | 74,569 | 405 |
| GN-32-R014 | Nose wheel steering actuator (NB) | R | D0 | 104,446 | 327 |
| GN-36-E013 | Bleed temperature sensor (NB) | E | D10 | 1,200 | 244 |
| GN-35-E032 | Crew quick-donning oxygen mask | E | D0 | 11,307 | 238 |
| GN-29-R034 | Electric motor pump (WB) | R | D3 | 92,085 | 191 |
| GN-34-R021 | Pitot probe (NB) | R | D3 | 31,055 | 138 |

| Route | Requests | Mean wait h | Median wait h |
|---|---|---|---|
| local stock | 35,477 | 0.0 | 0.0 |
| robbery (AUH) | 153 | 41.1 | 7.0 |
| AUH/network transfer | 152 | 19.3 | 11.0 |
| AOG exchange/loan | 128 | 69.7 | 40.0 |
| backorder -> repair return | 119 | 92.2 | 77.0 |
| AOG local buy | 101 | 135.3 | 209.0 |
| backorder -> PO receipt | 41 | 136.1 | 78.0 |
| local borrow | 12 | 33.7 | 5.5 |
| unfilled at end | 1 | None | None |

Analytic vs sim rotable fill (post-fix): 0.497 with the quoted 50/50 station split; 0.852 with the simulated station split; simulated 0.672.

## 5. Draft for the lead: remaining gap and settings to reach a plausible band (NOT applied)

**What remains after the fixes is intended realism.** Rotable fill is 0.669 (6-run). Switching off each intended factor alone gives:

* quoted-vs-true reliability: +0.18
* quoted-vs-true TAT: +0.07
* the unstocked outstation D0 demand left by the legacy line-station rule: +0.10
* everything else: ±0.01 each
* NFF works the other way: removing it costs 0.09

Estimates below are in-memory runs (6-run mean, P0 rebuilt on the modified public data each time). None was written to config.

| Setting | Documented range (now) | Current | Proposed | Why |
|---|---|---|---|---|
| `parts.quoted_mtbur_optimism` | 1.0–1.3 (ASSUMED) | 1.25 | 1.10 | Vendor optimism still present but smaller. P0 then sees closer-to-true rates; history-based planning keeps an edge. |
| `parts.quoted_mtbur_noise_sd_log` | 0.15–0.40 | 0.35 | 0.20 | ±0.35 log noise makes some PNs 2× under-quoted, which drives the worst-10. |
| `generator.quoted_tat_optimism` | 0.85–1.0 | 0.90 | 0.95 | Vendor TAT quotes are usually contractual, so a small bias. |
| `generator.quoted_tat_noise_sd_log` | 0.05–0.20 | 0.15 | 0.10 | Same reasoning as above. |
| `parts.mtbur_fh` / `mtbur_fc` lower bounds and family MTBUR overrides | FH 4,000–40,000; FC 2,500–25,000 | — | ×1.5 (FH 6,000–60,000; FC 3,750–37,500; brakes 2,700–4,500 FC; wheels 4,500–12,000 FC; servo 22,500–90,000 FH) | Fewer removals per PN: the 120 PNs are an AOG-critical sample, not the whole catalogue. |
| `aog_sourcing.robbery.availability` (assumption, not generator) | 0.4–0.9 | 0.60 | 0.75 | A hub with check and parked aircraft usually has a donor. |
| `aog_sourcing.exchange_loan` availability NB / WB | NB 0.7–0.95, WB 0.4–0.8 | 0.85 / 0.50 | 0.90 / 0.65 | Pool and OEM programmes improve WB access. |
| `aog_sourcing.exchange_loan.response_hours` NB / WB | NB 12–48, WB 24–120 | [24, 48] / [48, 120] | [18, 36] / [36, 96] | Common A320 LRUs ship next flight out. |
| `aog_sourcing.local_buy.availability` | 0.9–0.99 | 0.95 | 0.99 | A failed local buy leaves a C/E need waiting for a PO (378 h per event in history; PS4). |

**Indicative effects (rotable fill / AOG h/yr / events per year):**

| Settings applied | Rotable fill | AOG h/yr | Events/yr | Capital (AED) |
|---|---|---|---|---|
| Current (post-fix) | 0.669 | 5,520 | 133 | 45.9 M |
| Quotes (first four rows) | 0.793 | 3,703 | 96 | 49.0 M |
| + AOG market (robbery, exchange) | 0.794 | 3,317 | 96 | |
| + MTBUR ×1.5 | 0.769 | 2,656 | 73 | 38.8 M |
| + generous AOG market (robbery 0.85, exchange 0.95/0.75, local borrow +0.25, local buy 0.99) | 0.769 | 1,608 | 71 | |
| + unbiased quotes (optimism 1.0, noise 0.15) | 0.805 | 1,273 | 66 | 41.4 M |

**Conclusion for the band.** With P0's legacy line-station rule (≥ 4 quoted removals/yr), 300–900 material AOG h/yr and 0.85–0.93 rotable fill cannot be reached with generator and assumption settings inside their documented ranges:

* About 10% of rotable demand is outstation D0 with no line-station unit. That caps rotable fill at about 0.9 × hub fill and adds about 800 AOG h/yr of 9–16 h emergency transfers on its own.

To hit that band, one of these is needed:

* (a) relax the band to roughly 0.78–0.85 rotable fill and 1,200–2,700 AOG h/yr (30–90 h per aircraft-year), events 60–100/yr;
* (b) change the P0 line-station rule, for example ≥ 2 quoted removals/yr (a policy change, not generator);
* (c) reduce D0 outstation exposure in the catalogue (fewer D0 LRUs on high-frequency outstation routes).

Events per year (66–133) are already within 30–120 once the quotes are tightened.


## 6. User decisions A–C (data/realism corrections, band recorded; raw P0 rerun)

### A. Changes (old → new). Nothing is tuned to the band and nothing is locked.

| Item | Old | New | Type |
|---|---|---|---|
| `generator.families.wheel_tyre.repair_shop` | EU_VENDOR (ATA 32 mapping, 4 d transit each way) | AUH_INHOUSE (hub wheel & tyre shop) | data correction (A.a) |
| `wheel_tyre.repair_tat_days` | 15–90 d (generic rotable range) | 2–7 d (realised quoted 4.6 / 5.8 / 5.6 d) | data correction (A.a) |
| `wheel_tyre.repair_tat_cv` | 0.20–0.50 | 0.20–0.40 | data correction (A.a) |
| `wheel_tyre.repair_cost_pct_of_unit` | 0.08–0.25 | 0.15–0.35 (new or retreaded tyre + inspection per rebuild) | data correction (A.a) |
| `wheel_tyre.condemnation_prob` | 0.01–0.08 | 0.01–0.03 (wheel-half scrap; tyre scrap is inside the rebuild cost) | data correction (A.a) |
| `wheel_tyre` cost / QPA / MTBUR | AED 15–45k; NB main 4, NB nose 2, WB main 8; 3,000–8,000 FC | unchanged | — |
| Engine: wear-planned brake supply (V2-SIM-13) | 5–10 d notice used only for a reservation | At notice, if the hub will be short by the due date: transfer from another station (routine if it arrives by due − 24 h, else emergency), else a pre-arranged exchange/loan (same fleet-type availability and response draws), fitted at the planned change | non-calibration engine fix (A.b) |
| Engine: AOG route retries (V2-SIM-14); new `aog_sourcing.retry_hours` | a failed route was never retried | retried with fresh paired draws while the need is open: C/E every 24 h, R every 72 h | non-calibration engine fix (A.c) |
| `calibration_targets` | PENDING | rotable fill 0.78–0.85, AOG 1,200–2,700 h/yr, 60–100 events/yr; stress worlds at the band ends (scalars not set); P0 line-station rule unchanged | band recorded (B) |

### A.c Why deferred (D3/D10) needs expired

Before the retry fix (but after A.a and A.b): deadline expiry was 1,802 AOG h/yr (pooled history + 5 selection seeds).

| Reason | h/yr | Verdict |
|---|---|---|
| Expendable: local buy unavailable on its single 5% draw → waited for the PO (PS4 battery pack alone 930 h/yr, at a 73-day post-change lead time) | 1,281 | ENGINE GAP (no retry) → fixed (V2-SIM-14) |
| Rotable at AUH: robbery and exchange unavailable on their single draws → waited for the repair return | 446 | ENGINE GAP (no retry) → fixed |
| Rotable at an outstation: local borrow and exchange unavailable → waited for the repair return | 36 | ENGINE GAP → fixed |
| Exchange succeeded, but its response time (WB 48–120 h) exceeds a 72 h window triggered at need | 31 | realistic |
| Robbery/exchange unavailable → waited for a PO | 9 | ENGINE GAP → fixed |

After the fix: 123.3 h/yr in total.

| Reason (after the fix) | Requests | h/yr | Verdict |
|---|---|---|---|
| route exchange_loan succeeded only on a retry (earlier draw unavailable), after the deadline | 9 | 63.9 | realistic |
| route exchange_loan succeeded but its response time exceeds the window (triggered at need) | 9 | 31.3 | realistic |
| route robbery succeeded only on a retry (earlier draw unavailable), after the deadline | 10 | 16.3 | realistic |
| route local_buy succeeded only on a retry (earlier draw unavailable), after the deadline | 2 | 6.1 | realistic |
| robbery/exchange unavailable on draw (AUH) -> waited for repair return | 2 | 3.9 | realistic |
| route local_borrow succeeded only on a retry (earlier draw unavailable), after the deadline | 1 | 1.9 | realistic |

Every residual case is realistic:

* the first market check found nothing, and the retry 72 h later landed after the window; or
* the response time is longer than the window (WB exchange 48–120 h against D3's 72 h).

The largest residual parts are all WB or avionics D3 LRUs: WB electric motor pump 26 h/yr, WB EDP 17, WB fuel boost pump 16, NB ADIRU 16, NB spoiler servo 15.

### C. Raw P0 after A (history + 5 selection seeds)

| Metric | History before A | History after A | Year 1 / Year 2 after A | Selection mean after A | Band |
|---|---|---|---|---|---|
| Immediate fill (all) | 0.983 | 0.984 | 0.986 / 0.981 | 0.981 |  |
| Rotable fill (network) | 0.672 | 0.678 | 0.690 / 0.667 | 0.673 | 0.78–0.85 |
| Rotable fill (hub pool) | None | 0.760 | 0.772 / 0.748 | 0.750 |  |
| Expendable fill | 0.928 | 0.928 | 0.973 / 0.887 | 0.896 |  |
| Consumable fill | 1.0 | 1.000 | 1.000 / 1.000 | 1.000 |  |
| Material AOG h/yr | 4708.5 | 1,712.000 | 1,699.000 / 1,725.000 | 1,907.200 | 1,200–2,700 |
| AOG events/yr | 136.0 | 97.000 | 90.000 / 104.000 | 90.400 | 60–100 |

* **Scale:** AOG h per aircraft-year 42.8. Capital AED 44.9 M (selection mean 45.2 M).
* **By trigger:** D0_no_stock 1,621 h (95%); deadline_expired 91 h (5%)
* **By station:** AUH 542 h (32%); BOM 306 h (18%); JED 292 h (17%); CAI 283 h (17%); LHR 116 h (7%); SIN 94 h (5%); FRA 80 h (5%)
* **By class:** R 1,625 h (95%); E 87 h (5%)
* **By archetype:** narrowbody 1,132 h (66%); widebody 580 h (34%)

| Top AOG PN | Description | Class | Deadline | Removal mode | Unit cost AED | AOG h/yr |
|---|---|---|---|---|---|---|
| GN-32-R015 | Main wheel and tyre assembly (NB) | R | D0 | unscheduled | 15,574 | 381 |
| GN-32-R014 | Nose wheel steering actuator (NB) | R | D0 | unscheduled | 104,446 | 327 |
| GN-32-R036 | Carbon brake assembly (WB) | R | D0 | wear_planned | 270,041 | 184 |
| GN-27-R032 | Aileron power control unit (WB) | R | D0 | unscheduled | 169,624 | 121 |
| GN-27-R007 | Aileron servo control (NB) | R | D0 | unscheduled | 196,170 | 115 |
| GN-27-R006 | Elevator servo control (NB) | R | D0 | unscheduled | 138,105 | 102 |
| GN-27-R031 | Elevator power control unit (WB) | R | D0 | unscheduled | 231,228 | 100 |
| GN-35-E032 | Crew quick-donning oxygen mask | E | D0 | unscheduled | 11,307 | 87 |
| GN-32-R016 | Nose wheel and tyre assembly (NB) | R | D0 | unscheduled | 21,664 | 86 |
| GN-32-R037 | Main wheel and tyre assembly (WB) | R | D0 | unscheduled | 20,357 | 71 |

| Route | Requests | Mean wait h | Median wait h |
|---|---|---|---|
| local stock | 35,488 | 0.0 | 0.0 |
| AUH/network transfer | 162 | 17.9 | 11.0 |
| AOG exchange/loan | 154 | 50.3 | 29.0 |
| robbery (AUH) | 118 | 55.4 | 7.5 |
| backorder -> repair return | 110 | 71.8 | 69.5 |
| AOG local buy | 107 | 135.9 | 209.0 |
| backorder -> PO receipt | 35 | 76.9 | 63.0 |
| local borrow | 9 | 43.1 | 6.0 |
| unfilled at end | 1 | None | None |

* **Analytic vs sim rotable fill:** 0.497 (quoted split) / 0.852 (simulated split) vs simulated 0.678.

**Against the band:** AOG hours and events are already inside it. Network rotable fill (0.678 / 0.673) is below 0.78–0.85.

### A.d Plausibility flags on the new top 10 (explained, not fixed)

| Driver | Flag | Explanation |
|---|---|---|
| NB main wheel & tyre (AED 15.6k, 381 h/yr); NB nose wheel (86); WB main wheel (71) | Implausible to a materials manager under P0 | Cheap, high-volume assemblies. About half the NB main-wheel demand is D0 at outstations, where P0 holds none: the legacy line-station rule needs ≥ 4 quoted removals/yr per station, and the quoted BOM/JED/CAI rates are about 3.5/yr. Every outstation removal waits for an emergency transfer of 9–16 h + fitting. A real airline keeps a wheel or two at every daily outstation. This is the P0 rule weakness that P2 should fix, not a data error. Also: tyre-wear changes (every few hundred landings, planned) are not modelled; wheels here are unscheduled damage removals only (a scope limit). |
| PS1 NWS actuator (327 h/yr) | Planted | Designed: optimistic quote (2.5×) and no BOM unit. |
| WB carbon brake (wear-planned, 184 h/yr) | Questionable | Residual after notice-time sourcing: the hub is short and the pre-arranged WB exchange is unavailable (WB availability 0.50), so the planned change waits. Brakes are also often on OEM cost-per-landing contracts with an OEM-held float (not modelled). |
| Flight-control servo controls / PCUs (D0, AED 138–231k, 100–121 h/yr each) | Plausible | Expensive D0 LRUs with outstation exposure and no line-station unit under P0. |
| Crew quick-donning oxygen mask (E, D0, AED 11k, 87 h/yr) | Mildly implausible | An outstation stock-out of a cheap expendable, filled by local buy (4–12 h) + fitting. D0 is defensible for a required crew mask, but airlines stock these at every outstation. P0's C/E min/max does hold them at stations with quoted demand, so the AOG comes from local stock-outs between replenishments. |
| PS4 emergency light battery pack | Resolved | It was a top driver only because a failed local buy was never retried (V2-SIM-14). The planted lead-time jump stays visible in POs (reorders 23 → 76 d) but no longer drives AOG. |

### In-memory estimate (NOT applied, not in config): raw P0 after A + quote and AOG-market settings

Settings, exactly as applied in memory:

| Setting | Old → new |
|---|---|
| `parts.quoted_mtbur_optimism` | 1.25 -> 1.10 |
| `parts.quoted_mtbur_noise_sd_log` | 0.35 -> 0.20 |
| `generator.quoted_tat_optimism` | 0.90 -> 0.95 |
| `generator.quoted_tat_noise_sd_log` | 0.15 -> 0.10 |
| `aog_sourcing.robbery.availability` | 0.60 -> 0.75 |
| `aog_sourcing.exchange_loan.availability` | NB 0.85 -> 0.90, WB 0.50 -> 0.65 |
| `aog_sourcing.exchange_loan.response_hours` | NB [24,48] -> [18,36], WB [48,120] -> [36,96] |
| `aog_sourcing.local_buy.availability` | 0.95 -> 0.99 |

Not applied in this estimate: the MTBUR ×1.5 range change and the local-borrow changes.

| Metric | History | Selection mean | Band |
|---|---|---|---|
| Rotable fill (network) | 0.814 | 0.808 | 0.78–0.85 |
| Rotable fill (hub pool) | 0.895 | 0.889 |  |
| Overall fill | 0.990 | 0.990 |  |
| Expendable fill | 0.957 | 0.953 |  |
| Material AOG h/yr | 1,137.500 | 1,264.600 | 1,200–2,700 |
| AOG events/yr | 72.000 | 70.600 | 60–100 |

Capital AED 48.3 M. Top drivers: Nose wheel steering actuator (NB) 340; Aileron power control unit (WB) 121; Elevator servo control (NB) 102; Aileron servo control (NB) 102; Elevator power control unit (WB) 100.

With these settings the estimate lands inside the band on rotable fill and events. AOG hours sit at the lower edge (1,138 history / 1,265 selection against 1,200–2,700).

