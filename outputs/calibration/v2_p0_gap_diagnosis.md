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

