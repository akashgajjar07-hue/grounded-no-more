# Methodology

How GROUNDED NO MORE turns a simulated airline into planning decisions, and how those decisions are tested. The contract every module builds against is in [`docs/data_contract.md`](docs/data_contract.md); every parameter is in [`config/assumptions.yaml`](config/assumptions.yaml), the part catalogue in [`config/part_catalogue.csv`](config/part_catalogue.csv), and both are listed in the [assumption register](docs/assumption_register.md).

Parameter values quoted below come from the config and are **ASSUMED** unless marked otherwise. Result values are computed from `outputs/` and `docs/data/` by `scripts/render_docs.py`, which renders this file from `docs/templates/METHODOLOGY.md.tmpl`. Headline results are from the v2 holdout (seeds 2000–2019, central world) unless labelled "selection" (seeds 100–119). A v1 world was archived after a domain review; see [archive/v1](archive/v1/README.md).

Plan names used throughout: **Simple Rulebook (naive reference)** `P0`, **Each Airport for Itself (simplified local comparator)** `P1`, **Network Plan** `P2`, **Network Plan + Extra Spares** `I125`, and **Network Plan held to guardrails** `P2_GUARD`; other frontier points are "Frontier point B150" and so on. Every headline number is across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part.

**Contents**

1. [Design principles](#1-design-principles)
2. [The synthetic world (generator)](#2-the-synthetic-world-generator)
3. [Exposure](#3-exposure)
4. [Demand types and rectification windows](#4-demand-types-and-rectification-windows)
5. [Event engine semantics](#5-event-engine-semantics)
6. [Calibration (P0 only) and the lock](#6-calibration-p0-only-and-the-lock)
7. [Forecasting and its evaluation](#7-forecasting-and-its-evaluation)
8. [Inventory and rotable policy maths](#8-inventory-and-rotable-policy-maths)
9. [Network positioning](#9-network-positioning)
10. [Greedy marginal allocation and the Readiness Frontier](#10-greedy-marginal-allocation-and-the-readiness-frontier)
11. [Paired-seed evaluation](#11-paired-seed-evaluation)
12. [Holdout freeze discipline](#12-holdout-freeze-discipline)
13. [Economics](#13-economics)
14. [Engine and data fixes made before the freeze](#14-engine-and-data-fixes-made-before-the-freeze)

---

## 1. Design principles

| Principle | How it is enforced |
|---|---|
| Planning models never see the truth | True rates live in `data/ground_truth/`. `tests/test_leakage.py` statically scans `gnm.forecasting`, `gnm.policy`, `gnm.optim`, `gnm.aog` and `gnm.export` for imports of the truth or the generator internals, and a runtime test makes reads of the hidden-truth folder raise while the planning pipeline runs. These are checks, not a proof. |
| One set of mechanics for every policy | A policy is a parameter table (`PolicySpec`). One event engine runs them all ([D002](docs/DECISIONS.md)). |
| Same world for every policy | Exogenous demand and the random draws for repair time, condemnation, no-fault-found, lead time and AOG route availability are pre-sampled or counter-based (common random numbers, [D003](docs/DECISIONS.md), V2-SIM-5). |
| Calibrate the baseline only, then lock | P0 alone was calibrated, and the world was locked before any P1, P2 or optimiser run ([section 6](#6-calibration-p0-only-and-the-lock)). The target range itself was an exploratory assumption chosen after diagnosing the model. |
| Test once, on data nobody tuned against | Parameters are hashed before the holdout runs ([section 12](#12-holdout-freeze-discipline)). |
| Every number traceable | Each table and JSON object carries a provenance tag. `tests/test_reconciliation.py` recomputes the headline shown in the app from `outputs/`. |

---

## 2. The synthetic world (generator)

`gnm.sim.generator` builds the world from `world_seed = 2023`.

**Fleet.** 24 narrowbody and 16 widebody aircraft (generic narrowbody and widebody archetypes) with fictional registrations (`A6-FH?`, `A6-FW?`). Daily utilisation is drawn per aircraft: narrowbody about 10.5 FH and 4.2 FC per day, widebody about 14.0 FH and 2.4 FC per day (ASSUMED). Weekly, monthly and holiday seasonality factors scale utilisation.

**Network.** Hub AUH and six outstations (LHR, FRA, CAI, JED, BOM, SIN). Station coordinates are REAL (OurAirports). Narrowbodies fly to CAI, JED and BOM; widebodies to LHR, FRA, BOM and SIN. BOM is the only outstation both fleets serve.

**Parts: a curated, type-exclusive catalogue** (V2-SIM-1). The 120 fictional part numbers (`GN-<ATA>-<C|E|R><nnn>`: 45 consumables, 35 expendables, 40 rotables) come from a hand-curated catalogue that fixes, per row, the ATA chapter, description, family, type applicability, quantity per aircraft, rectification window, removal mode and driver. Applicability is type-exclusive: only 12 common items (masks, lamps, battery packs, hardware, fluids and similar) fit both archetypes. The widebody archetype has no ATA 36 bleed parts and gets electrical analogues instead. Unit cost is drawn log-uniform by family, and MTBUR, repair TAT and lead time are still drawn from the world seed within ASSUMED ranges.

**Reliability.** Removal-driven parts have a true MTBUR (4,000–40,000 FH or 2,500–25,000 FC by default, with family-specific ranges in the config). The part master publishes a **vendor-quoted** MTBUR: truth × lognormal noise (σ_log 0.20) and 10% optimistic on average; quoted shop TAT is 5% optimistic (σ_log 0.10) ([D005](docs/DECISIONS.md), calibrated in V2-SIM-CAL). About 30% of parts have overdispersed, clustered demand. All of this is ASSUMED and SIMULATED. None of it is measured reliability.

**No-fault-found** (V2-SIM-4). A removal is NFF with probability = family share 10–40% (0 for brakes and wheels), 2–5 shop days at 15% of the repair cost, never condemned. NFF shortens the repair pipeline, which matters for avionics.

**Wheels and brakes** (V2-SIM-3, V2-SIM-15). Wheel-and-tyre assemblies are rebuilt in the AUH wheel and tyre shop in 2–7 days at 15–35% of unit cost. Brakes are type-specific and wear-planned: their removals are known 5–10 days ahead and rectified at AUH (section 4).

**Planted situations.** Four documented demo situations (PS1–PS4) give the planner screens something real to find: PS1 GN-32-R014 (Nose wheel steering actuator (NB)), an unscheduled D0 rotable that the Simple Rulebook does not stock at BOM; an overdue repair order at the EU vendor; a declining consumable creating excess; and a lead-time jump on one expendable around week 70.

**Scenarios.** `generate_scenario(world, truth, seed, week_from, week_to)` returns the exogenous events for one seed: flights, the maintenance schedule, removals and material requests, plus pre-sampled repair durations, condemnation and NFF flags, PO lead-time streams and the per-request uniforms the AOG routes use. Downstream code receives only this `Scenario`, never the truth.

---

## 3. Exposure

Removals happen because aircraft fly. Exposure is the flying that drives them:

- **FH-driven parts** accumulate flight hours.
- **FC-driven parts** (landing gear, wheels, brakes, doors, APU starts) accumulate flight cycles.
- **Consumables** are used per 1,000 FC of line maintenance, plus scheduled kits.

For a removal-driven part with installed quantity *q* per aircraft, the expected removal rate over a period is

$$
\lambda = \frac{q \times \text{exposure in the period}}{\text{MTBUR}}
$$

summed over the aircraft of the type that carries the part.

**No exposure feedback.** A grounded aircraft still accrues scheduled exposure. The assumption is that protection flying (a spare aircraft or a sub-charter) covers the schedule, and the cost of lost flying sits in the AOG cost. This keeps demand identical across policies, which the paired comparison needs ([D004](docs/DECISIONS.md), [LIMITATIONS](LIMITATIONS.md)).

---

## 4. Demand types and rectification windows

| Source | Parts | Known in advance? | Notes |
|---|---|---|---|
| `unscheduled_removal` | Rotables, expendables | No | One removal = one unit. Carries the part's rectification window. |
| `planned_removal` | Brakes (wear-planned) | Yes: 5–10 days | Rectified at AUH on the next hub arrival and reserved like a kit. Supply is triggered at notice if the hub will be short (V2-SIM-13). |
| `scheduled_kit` | Consumables | Yes: 21 days before the A-check | Kits reserve stock from the notice time. |
| `line_usage` | Consumables | No | Poisson or negative binomial on cycles flown. |

Requests record **unconstrained** demand ([D006](docs/DECISIONS.md)): a removal happens whether or not a spare exists.

**Rectification windows (hypothetical)** (V2-SIM-2). D3/D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions. They are applied generically per PN (elapsed hours, not calendar days excluding the day of discovery) and do not represent an approved MEL; the real go/no-go depends on the MEL item and the redundancy remaining.

| Class | Window | Meaning in the engine |
|---|---|---|
| D0 | 0 h | Needed before the next departure; only where no plausible MEL relief exists. No consumable is D0. |
| D3 | 72 h | Material-related downtime only if the part is not fitted within 72 h. |
| D10 | 240 h | Material-related downtime only if the part is not fitted within 240 h. |
| NONE | — | Servicing fluids: line usage only, never a downtime driver. |

Deferrable (D3/D10) removals found at an outstation are rectified at AUH on the tail's next hub arrival with probability 92% (SIM-11).

---

## 5. Event engine semantics

`gnm.sim.engine` is a continuous-time discrete-event simulation at hour resolution. For a given (Scenario, PolicySpec) it is deterministic.

**Request lifecycle.** At need time the engine tries local serviceable stock, then an emergency transfer from AUH (or a lateral where the policy allows it). A deferred (D3/D10) need is sourced at deferral time: a shipment from stock goes routine only if its drawn routine ETA is at least 24 h before the window closes, otherwise emergency (V2-SIM-6). If no owned unit can arrive in time, the **AOG desk routes** take over (V2-SIM-5):

| Route | Where | Parts | Availability per attempt | Response | Cost |
|---|---|---|---|---|---|
| Robbery from a same-type donor | AUH only | Rotables | 0.60 | 6–8 h | double fitting labour; flagged "engineering/quality approval required" |
| Local borrow | outstations | Rotables | NB 0.30–0.60, WB 0.10–0.35 by station | 4–8 h | AED 2,500 + 0.4% of list per day |
| Exchange / loan | any station | Rotables | NB 0.85, WB 0.50 | NB 24–48 h, WB 48–120 h | 20% (NB) / 30% (WB) of list + 0.3% per day |
| Local buy / borrow | every station | Consumables, expendables | 0.95 | 4–12 h | +50% |

Rotables try local borrow (outstations) or robbery (AUH) first, then exchange/loan in the same attempt; consumables and expendables use local buy. A failed attempt is retried every 72 h for rotables and 24 h for consumables and expendables with fresh paired draws (V2-SIM-14). There is **no outright AOG purchase and no pool growth**: a borrowed unit is a serial with `owned = False`, never serviceable stock and never capital; the first own serviceable unit at AUH replaces it and the loan is returned. A robbed donor is reinstated from the next AUH unit, and the donor is assumed not to fly until then. Outright POs are only reorders (C/E) and condemnation replacements. AUH allocates each new serviceable unit in the order: backorders, donors, loan hand-backs, stock transfers.

**Material-related downtime** (V2-SIM-7). Material AOG hour = clock hours from need (or end of the rectification window) to release to service, including fitting/RTS time, counted only when the part was not available in time. The interval is [need + window, fill + fitting/RTS], with fitting/RTS 2–6 h for rotables and 1 h for consumables and expendables. Intervals are merged per aircraft: two missing parts on one aircraft at the same time count once. In plain terms: The downtime clock starts when the part is removed (for no-go items; for deferrable items, when the rectification window runs out), not at the next scheduled departure, and overnight and other non-flying hours count in full. Fitting and release-to-service time is included. A departure-based count would be lower for every plan.

**Rotables are serialised.** Every serial is in exactly one state and location:

```
SERVICEABLE@station → INSTALLED@tail → REMOVED → IN_REPAIR@shop → SERVICEABLE@AUH
                                                              ↘ CONDEMNED
LOAN serial (not owned) → INSTALLED@tail → RETURNED_TO_LENDER
```

A removed core travels to AUH, then to its shop (the AUH in-house shop, the wheel and tyre shop or the EU vendor). Shops have parallel bench slots; a unit holds a slot for only 5% of its work time (SIM-4), so queues are light by construction. A condemned unit triggers a replacement PO.

**Consumables and expendables** use continuous review on inventory position. When it falls to the reorder point *s*, the station orders up to *S*. Outstations replenish from AUH; AUH replenishes by PO. Shelf-life items expire first-in, first-out; a need whose earmarked shelf-life units expire on arrival is re-opened and re-routed (V2-SIM-17).

**Conservation invariants** are tested: owned serials are conserved with loans and donors; borrowed units are never owned and always returned; per PN, opening serials + purchased − condemned = closing serials; counted stock balances; repairs never create units.

---

## 6. Calibration (P0 only) and the lock

> The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the model, not benchmarked against real airline KPIs. A line-kit variant (≈1,052 h) was measured but not adopted because it fell outside that range. All results are conditional on this choice.

**Band (V2-SIM-16): an ASSUMED target range set by the author after the P0 gap diagnosis and before any policy comparison; author judgement, not an external benchmark:** P0 network rotable immediate fill 0.78–0.85, material AOG 1,200–2,700 h/yr, AOG events 60–100/yr. It describes a simple OEM-quote operation with no line-station units for low-volume D0 parts; the v1 band (rotable fill 0.80–0.88, AOG 1,500–3,500 h/yr, events 60–250/yr) is kept in the config for reference only.

**History of the P0 numbers.** Each step below is a domain or engine correction made before calibration, then the calibration itself. None was chosen by looking at P1, P2 or the optimiser, which did not exist yet:

| Step (central world, P0, history weeks 0–103) | What changed | Rotable fill | Material AOG h/yr | Events/yr | In band |
|---|---|---|---|---|---|
| 1. Raw v2 P0 | domain rebuild (V2-SIM-1..9), uncalibrated | 0.588 | 6,700 | 152 | no |
| 2. Gap diagnosis fixes | V2-SIM-10..12: P0 fill definition, pipeline weighting, reservation bug | 0.672 | 4,708 | 136 | no |
| 3. Realism corrections A | V2-SIM-13..15: planned brake supply, AOG route retries, hub wheel shop | 0.678 | 1,712 | 97 | no |
| 4. Calibration V1 (locked) | quote accuracy only (V2-SIM-CAL) | 0.815 | 1,282 | 74 | yes |

**The diagnosis** (`outputs/calibration/v2_p0_gap_diagnosis.md`): with P0's own assumptions true the engine reproduces Poisson availability (simulated rotable fill 0.943 against a demand-weighted analytic 0.948; it was 0.872 on paper before the V2-SIM-10 fix). What remains is intended realism. Switching one factor off at a time from the as-built fill of 0.669: quoted-vs-true removal rates +0.18, quoted-vs-true TAT +0.07, unstocked outstation demand under the starting-point line-station rule +0.10, and NFF works the other way (−0.09 if removed). Reaching the band therefore needed either more accurate quotes, a change to the starting-point rule, or a looser band.

**The choice.** The raw P0 and four variants were measured in memory with nothing applied (`outputs/calibration/v2_p0_variants.json`):

| Variant (measured in memory, nothing applied) | Rotable fill, history / selection | Material AOG h/yr, history / selection | Events/yr, history / selection | All in band |
|---|---|---|---|---|
| V0 raw P0 (after A) | 0.678 / 0.673 | 1,712 / 1,907 | 97 / 90 | no |
| V1 quote accuracy (chosen) | 0.815 / 0.809 | 1,282 / 1,435 | 74 / 72 | yes |
| V2 line-station kit | 0.711 / 0.705 | 1,246 / 1,445 | 68 / 63 | no |
| V3 = V1 + V2 | 0.832 / 0.830 | 1,052 / 1,142 | 59 / 54 | no |
| V4 = V3 + AOG market (reference) | 0.831 / 0.830 | 912 / 976 | 57 / 52 | no |

Only V1 quote accuracy lands inside the band, and it is also the fewest-changes option (the rule chosen before calibration), so it was applied: `quoted_mtbur_optimism` 1.10, `quoted_mtbur_noise_sd_log` 0.20, `quoted_tat_optimism` 0.95, `quoted_tat_noise_sd_log` 0.10. The AOG-market settings and the line-station kit were not applied, and the P0 rule is unchanged.

**Stress worlds.** Only the true MTBUR is scaled: ×1.08 (low stress) and ×0.96 (high stress), aiming each at one end of the band. Read together that is reliability ×1.08 (easier) / ×1.00 / ×0.96 (tougher) — a narrow range. Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.

| World (true-MTBUR scale) | Target | Rotable fill, history / selection | Material AOG h/yr, history / selection | Events/yr, history / selection | In the central band |
|---|---|---|---|---|---|
| central (×1.00) | central band | 0.815 / 0.809 | 1,282 / 1,435 | 74 / 72 | yes |
| low stress (×1.08) | AOG 1,200, fill 0.85 | 0.846 / 0.836 | 1,123 / 1,226 | 66 / 63 | no |
| high stress (×0.96) | AOG 2,700, fill 0.78 | 0.780 / 0.781 | 1,632 / 1,558 | 84 / 76 | yes |

In short, the low-stress world reaches the AOG end of the band (pooled history and selection 1,174 h/yr; band end 1,200) at 0.841 rotable fill, and the high-stress world reaches the fill end (0.781; band end 0.78) at about 1,595 h/yr, well short of the 2,700 h end, because fill binds first. Both are disclosed as they came out (D013).

**Lock.** `outputs/freeze/calibration_lock.json` hashes 12 files (the config, the catalogue, `src/gnm/sim/*.py` and the P0 summary) and `tests/test_calibration_lock.py` enforces it. Locked at commit `42c02d8`, before any v2 P1/P2/optimiser run; re-locked only after the documented non-calibration fixes V2-SIM-17/18 at `4a564c6`, with policy results unchanged.

---

## 7. Forecasting and its evaluation

### 7.1 Split calendar

| Block | Weeks | Use |
|---|---|---|
| Train | 0–77 | Fit models and estimate removal rates |
| Selection | 78–103 | Rolling-origin selection: origins 78, 82, …, 98, horizon 4 weeks |
| Holdout | 104–155 | Run once, after the freeze (12 origins, weeks 104–148) |

### 7.2 Demand classification

Each PN's weekly series is classified with the Syntetos–Boylan scheme on the training window: **ADI** (average interval between non-zero weeks) and **CV²** (squared coefficient of variation of non-zero sizes). ADI < 1.32 and CV² < 0.49 is smooth; ADI < 1.32 and CV² ≥ 0.49 erratic; ADI ≥ 1.32 and CV² < 0.49 intermittent; otherwise lumpy. Series with fewer than 3 non-zero weeks are `insufficient_data`. Parts per class (smooth / erratic / intermittent / lumpy / insufficient data): 32 / 3 / 82 / 2 / 1.

### 7.3 Methods

| Method | Idea | Best suited to |
|---|---|---|
| Zero | Forecast 0 every week. Benchmark only, never eligible as champion | Shows how MAE-type metrics flatter a zero forecast on sparse series |
| Naive | Last week's demand | Benchmark; also the MASE scale |
| Moving average | Mean of the last *k* weeks, *k* chosen by in-sample one-step MSE | Smooth demand |
| **ADIDA**, **IMAPA** | Temporal aggregation (one level, or several averaged), then smoothing and disaggregation | Intermittent |
| **Croston**, **SBA**, **TSB** | Smooth size and interval separately; SBA removes Croston's bias; TSB smooths the probability of demand so the forecast decays when demand stops | Intermittent, lumpy, obsolescence risk |
| **Bootstrap** (Willemain-style) | Resample history with a Markov model for zero/non-zero runs and jittered sizes | Lead-time demand quantiles |
| **Reliability-exposure model** | Removal rate per unit of exposure from a gamma–Poisson posterior: a prior worth 2 pseudo-removals at the vendor-quoted MTBUR, updated with observed removals and cumulative exposure. Lead-time demand is negative binomial | Removal-driven rotables and expendables |

Croston, SBA, TSB, ADIDA and IMAPA are implemented in numpy and cross-checked against `statsforecast`.

### 7.4 Metrics

- **MASE**: forecast MAE ÷ in-sample MAE of the one-step naive forecast. Below 1 means better than naive.
- **Bias** and **PIS** (periods in stock): persistent over- or under-forecasting, and the cumulative stock or shortage it would produce.
- **Coverage and q90 pinball loss** of each method's lead-time demand distribution: the metrics closest to setting a reorder point.
- **Truth recovery** (evaluation only): how close the planner's estimates get to the hidden truth. Only `gnm.eval.truth_recovery` reads the truth.

### 7.5 Selection and holdout

A champion is picked per demand class × part class by mean MASE over the six selection origins (ties within 0.001 broken by the smallest absolute bias, then the simpler method; cells with fewer than 5 parts fall back to the pooled class). The rules were kept unchanged from v1 (V2-POL-1). The champions were frozen, and the holdout re-scored every method:

| Demand class | Part class | Parts | Champion (frozen) | Selection MASE | Holdout MASE | Holdout rank | Best on holdout |
|---|---|---|---|---|---|---|---|
| erratic | C | 3 | reliability-exposure | 0.908 | 0.595 | 6 of 9 | ADIDA |
| insufficient_data | R | 1 | reliability-exposure | 0.908 | 1.095 | 3 of 9 | SBA |
| intermittent | C | 13 | reliability-exposure | 0.927 | 0.783 | 3 of 9 | SBA |
| intermittent | E | 32 | TSB | 0.942 | 0.955 | 1 of 9 | TSB |
| intermittent | R | 37 | SBA | 0.989 | 0.917 | 6 of 9 | TSB |
| lumpy | C | 2 | reliability-exposure | 0.908 | 0.788 | 6 of 9 | IMAPA |
| smooth | C | 27 | SBA | 0.727 | 0.690 | 1 of 9 | SBA |
| smooth | E | 3 | reliability-exposure | 0.747 | 0.726 | 2 of 9 | SBA |
| smooth | R | 2 | reliability-exposure | 0.747 | 0.611 | 1 of 9 | reliability-exposure |

The frozen champion was best in only 3 of 9 cells, and the intermittent-rotable champion (SBA) ranked 6th of 9. Rotable policies use the reliability-exposure rate (POL-3), so they do not depend on that champion. Holdout leaderboard, demand classes pooled within each part class (mean MASE [95% bootstrap CI over parts], q90 pinball loss; best eligible in bold):

| Method | Consumables MASE [CI] | Consumables q90 pinball | Expendables MASE [CI] | Expendables q90 pinball | Rotables MASE [CI] | Rotables q90 pinball |
|---|---|---|---|---|---|---|
| Zero (benchmark, not eligible) | 1.644 [1.356–1.939] | 28.240 | 0.755 [0.652–0.859] | 1.946 | 0.662 [0.573–0.758] | 1.504 |
| naive | 0.884 [0.837–0.929] | 4.124 | 0.998 [0.860–1.160] | 1.039 | 1.014 [0.866–1.168] | 0.930 |
| moving average | 0.720 [0.692–0.753] | 1.749 | 0.970 [0.855–1.092] | 0.328 | 0.887 [0.796–0.981] | 0.250 |
| Croston | 0.719 [0.689–0.749] | 1.579 | 0.997 [0.905–1.088] | 0.290 | 0.940 [0.875–1.012] | 0.243 |
| SBA | **0.711 [0.683–0.743]** | 1.688 | 0.968 [0.881–1.054] | 0.304 | 0.907 [0.841–0.982] | 0.245 |
| TSB | 0.721 [0.692–0.753] | 1.601 | **0.936 [0.842–1.024]** | 0.324 | **0.882 [0.793–0.978]** | 0.254 |
| ADIDA | 0.722 [0.692–0.753] | 1.668 | 0.955 [0.875–1.037] | 0.315 | 0.901 [0.822–0.978] | 0.255 |
| IMAPA | 0.721 [0.693–0.749] | 1.664 | 0.952 [0.865–1.044] | 0.311 | 0.896 [0.805–0.981] | 0.246 |
| bootstrap | 0.756 [0.714–0.800] | 1.567 | 1.048 [0.972–1.129] | 0.321 | 1.005 [0.938–1.086] | 0.275 |
| reliability-exposure | 0.728 [0.693–0.769] | **1.518** | 0.942 [0.867–1.020] | **0.286** | 0.897 [0.831–0.968] | **0.228** |

Full tables: `outputs/holdout/forecast_leaderboard.csv` (by demand class × part class) and `outputs/forecasting/leaderboard.csv` (selection window).

---

## 8. Inventory and rotable policy maths

### 8.1 Palm's theorem and the repair pipeline

Let removals arrive as a Poisson process with rate λ, and let each removed unit spend a turnaround time *T* in the pipeline (core return + transit + shop queue + shop work + return), with mean E[T]. **Palm's theorem** says the number of units in the pipeline at a random moment, *X*, is Poisson with mean λ · E[T], whatever the shape of the TAT distribution, provided repair times are independent and repair capacity is unlimited:

$$
X \sim \text{Poisson}(\lambda \cdot E[T])
$$

### 8.2 Base stock, backorders and fill

With total spares *S*, a demand is filled immediately if fewer than *S* units are in the pipeline:

$$
\text{EBO}(S) = \sum_{x > S} (x - S)\,P(X = x), \qquad \text{fill} = P(X \le S - 1)
$$

The protection level of every policy is defined on this fill, the quantity the engine measures as immediate fill (V2-SIM-10). EBO(S) − EBO(S+1) = P(X > S) falls as S rises, so each extra unit is worth less than the one before. The planner workbook ([`excel/grounded_no_more_planner_workbook.xlsx`](excel/grounded_no_more_planner_workbook.xlsx)) works this through with live formulas. Rotable floats always use the Poisson pipeline; clustered removals make that optimistic, and the event engine (which simulates the clustering) is the referee.

### 8.3 Consumables and expendables: (s, S)

Lead-time demand (LTD) comes from the champion forecast over the planner's estimated lead time (recency-weighted history receipts with a supplier-change rule; this is what catches PS4), negative binomial when variance/mean ≥ 1.05, else Poisson. The reorder point *s* is the LTD quantile at the deadline-class target (D0 0.97, D3 0.92, D10 0.85, NONE 0.85; ASSUMED); *S* = *s* + EOQ, capped at 52 weeks of cover and half the shelf life.

### 8.4 Policies compared

| Policy | Description |
|---|---|
| **Simple Rulebook (naive reference)** `P0` (V2-SIM-8) | A deliberately simplified static starting point on quoted data only, not a model of a competent airline. Rotables: total spares S = smallest S with P(Poisson(quoted annual removals × quoted pipeline days ÷ 365) ≤ S − 1) ≥ 95% for D0 and 90% for D3/D10, held at AUH, plus 1 line-station unit only for a D0 part with at least 4 quoted removals a year at that station. Consumables and expendables: min = 26 weeks (C) / 13 weeks (E) of quoted demand, max = 2 × min, at every station that sees quoted demand. It holds 8 rotables at the outstations. |
| **Each Airport for Itself (simplified local comparator)** `P1` | Every stocking point sized on its own forecast demand (single-echelon): (s, S) for C/E, and a Palm float at each station for rotables. It holds 193 outstation rotables. A deliberate "every station for itself" comparator. |
| **Network Plan** `P2` | Hub float sized on the network pipeline; outstation *j* gets its *k*-th rotable unit only while the expected annual cost of a local miss avoided per AED of unit cost is at least the 20% carrying rate. The miss cost uses the v2 AOG routes (hub transfer with the hub's fill probability, otherwise local borrow then exchange/loan, or local buy), the hourly rate and the fixed cost per event (V2-POL-4). Laterals and rebalancing on. It holds 44 outstation rotables. |
| **Network Plan + Extra Spares** `I125` (frontier option) | P2 within the stocking guardrails, plus greedy additions up to 1.25 × P2's allocation capital ([section 10](#10-greedy-marginal-allocation-and-the-readiness-frontier)). |

All policies keep the AOG desk routes on. P0, P1 and P2 share one definition of total spares: the engine seeds each repair loop with units from P0's own plan (118 in total), and P1/P2 hand the engine Palm's S minus those loop units at the hub (V2-POL-3), so capital is comparable. Total rotable spares: P0 260, P1 441, P2 308, I125 352.

Route usage per year by policy (holdout, central):

| Policy | Robbery / yr | Exchange/loan / yr | Local borrow / yr | Local buy / yr |
|---|---|---|---|---|
| P0 | 33.2 | 23.4 | 4.2 | 36.8 |
| P1 | 31.2 | 15.4 | 0.1 | 111.1 |
| P2 | 22.4 | 11.2 | 0.7 | 27.0 |

Robbery stays a reported outcome: the simulation engine uses robbery automatically as the first AUH route (after local stock), with engineering/quality approval flagged on every case; the AOG Lab never ranks it, and the optimiser never optimises its frequency.

---

## 9. Network positioning

The positioning model is **METRIC-inspired, not full METRIC**. An outstation that issues a unit is resupplied from AUH: its pipeline is routine transport plus the expected hub delay, approximated from the hub's own EBO (expected delay ≈ EBO_hub ÷ network demand rate, Little's law). Station demand is the network removal rate split by shares learned from observed station counts, shrunk towards an exposure-based prior; this learns that most deferred D3/D10 removals end up rectified at AUH. A station without stock is covered by an emergency transfer or, when the hub is also short, by the AOG routes in section 5.

Material AOG by station (holdout, central, mean per year):

| Station | P0 h/yr | P1 h/yr | P2 h/yr |
|---|---|---|---|
| AUH | 509 | 557 | 180 |
| BOM | 242 | 0 | 6 |
| CAI | 284 | 2 | 2 |
| FRA | 136 | 2 | 3 |
| JED | 228 | 2 | 3 |
| LHR | 161 | 2 | 8 |
| SIN | 131 | 1 | 8 |

Under P0, 70% of material AOG is at the outstations. P1 removes outstation downtime but leaves the hub short, because it sizes the hub on hub-local demand while the hub also refills the outstation floats. P2 cuts both, with AED 22.8M less capital than P1.

---

## 10. Greedy marginal allocation and the Readiness Frontier

**Objective.** Minimise expected material-related downtime, weighted by the archetype's AOG cost and the rectification window, for a given spares capital.

**Algorithm.** The analytic model (`gnm.optim.model`) gives expected downtime per part from a hub + outstation (METRIC-lite) model. When AUH is out of stock, a need waits for own supply or the v2 AOG route, whichever comes first; downtime counts only when late and includes fitting/RTS; cost = hours × hourly rate + events × fixed cost + route fees (V2-OPT-1). Starting from P2 within guardrails, the greedy repeatedly adds the (PN, station) unit with the largest reduction in weighted downtime per AED of capital. Greedy gives the best allocation only for separable, convex objectives at its breakpoints; hub-station coupling and per-aircraft merging break separability, so it is a heuristic here. Check: on a small separable, convex toy case the greedy allocation equals the brute-force optimum at every greedy breakpoint (unit test `tests/test_optim_greedy.py::test_greedy_equals_brute_force_at_breakpoints`, passing); no exact comparison exists for the full, non-separable network problem.

**Guardrails, stated before computing** (V2-OPT-2). G1: at each stocking point the total spares may not exceed the 99.5% fill quantile of that point's own pipeline. G2: a station with at most 6 requests a year for the part holds at most 1 unit. Above those levels the tail is cheaper to cover with the AOG routes than with idle stock. They cost +17 h [10–24] of material AOG a year at P2's capital (selection seeds).

**Candidates and the rule.** 25 candidates were frozen (candidates.json a8a22af8…): P0, P1 and P2; 16 re-optimised budget points; P2 within guardrails; two "P2 + greedy additions" points (I110, I125); a reposition-only point; a TAT-cut lever and a budget + TAT combination. All were run on the selection seeds, and the recommendation rule was applied there, before the holdout:

> Stated before computing. Among the capital-only candidates (baseline/reference policies, budget points, base+additions, reposition), take the non-dominated set on the selection-seed means (minimise simulated capital and material AOG h/yr) and its lower convex hull, sorted by capital. Walking up the hull, each segment's marginal value is the AOG-hour reduction per extra AED 1M of capital. The break-even value implied by the AOG penalty is h* = carrying % x AED 1M / (baseline AED per AOG hour), i.e. the AOG hours whose penalty equals the extra annual holding cost of AED 1M. The recommended 'balanced' point is the last hull vertex before the first segment whose marginal value falls below h* (equivalently the hull point that minimises carrying % x capital + AED/h x AOG hours). If no segment falls below h*, the highest-capital vertex is recommended and flagged 'frontier not saturated'.

With P2's realised AED 31,151 per downtime hour (the fixed cost per event spread over its hours, V2-OPT-3), h* = 6.4 hours per AED 1M at 20% carrying cost. The rule picked **I125** on the selection seeds: 92 h [55–129] against 235 h [153–317] for P2, paired −143 h [−195 to −91], net +AED 3.8M [2.0–5.6] a year. The pick is unchanged at carrying cost 15% and 25%, but moves to I110 at ×0.5 and B150 at ×2 the hourly rate.

**Holdout.** I125 costs AED 7.6M more than P2 for 134 h [87–181] less material AOG a year and AED 3.3M [1.8–4.8] lower total annual cost. At P2's own capital the best re-optimised allocation (B100) is −3 h [−49 to 43] vs P2: P2 is already near the frontier. Model vs simulation: the analytic model predicts 2,507 h a year for P0 against 1,690 h simulated on the holdout, 130 h against 210 h for P2 and 39 h against 76 h for I125. It overstates P0 and understates the network plans, so it is a ranking heuristic, not a forecast of AOG hours; it ranks well (r = 0.97 across the 25 frontier points on the holdout, r = 0.97 on selection seeds).

**Tornado (one at a time, selection seeds, I125 paired against P2):**

| Factor (one at a time, selection seeds) | Setting | I125 − P2 net annual benefit [95% CI] | Material AOG h saved vs P2 |
|---|---|---|---|
| base case | — | +AED 3.8M [2.0–5.6] | 143 h |
| aog penalty | x0.5 | +AED 1.7M [0.7–2.7] | 143 h |
| aog penalty | x2.0 | +AED 8.0M [4.6–11.5] | 143 h |
| carrying cost | 0.15 | +AED 4.2M [2.4–6.0] | 143 h |
| carrying cost | 0.25 | +AED 3.4M [1.6–5.3] | 143 h |
| repair tat | x0.75 | +AED 0.36M [−0.75 to 1.46] | 45 h |
| repair tat | x1.25 | +AED 12.0M [8.7–15.3] | 385 h |
| lead time | x0.75 | +AED 3.4M [1.7–5.0] | 132 h |
| lead time | x1.25 | +AED 3.8M [2.0–5.6] | 144 h |

The AOG penalty and carrying cost re-cost the simulated KPIs; repair TAT and lead time re-simulate. A separate structural stress switches the AOG routes off: with the routes switched off (selection seeds, a structural stress) material AOG rises from 1,727 h to 42,070 h a year under P0, from 235 h to 18,320 h under P2 and from 92 h to 11,080 h under I125. Same-plan stress worlds (selection): low stress −63 h [−92 to −34], net +AED 0.95M [0.00–1.90]; central −143 h [−195 to −91], net +AED 3.8M [2.0–5.6]; high stress −186 h [−245 to −127], net +AED 5.3M [3.4–7.3]. Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.

**Insight.** Faster repair can beat buying spares: with 25% shorter repair time, the extra-investment option loses its clear cost advantage. Levers compared: faster repair · pool access · better reliability · more spares. The capital behind the core finding is never shown as a net figure alone:

| Capital change, Simple Rulebook (naive reference) `P0` → Network Plan `P2` | Amount |
|---|---|
| New rotables bought | +68 units ≈ AED 8.4M assumed value |
| Rotables removed | −20 units ≈ AED 3.1M |
| Net change in average simulated spare inventory | +AED 0.6M |

*Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a discount.* Units and values: target units × assumed unit cost from the policy tables; the net is the paired holdout change in time-averaged simulated spare inventory. Average stock value rises by only about AED 0.6M, not bought minus removed, because many bought units sit in the repair loop rather than on the shelf.

---

## 11. Paired-seed evaluation

Every policy and frontier candidate runs on the same scenarios. For a KPI *K* and seed *s*, the paired difference is

$$
d_s = K_{\text{policy},s} - K_{\text{reference},s}
$$

Because both plans faced identical removals, repair times, lead times and route draws, world noise cancels, and the interval on the mean of *d_s* is much narrower than comparing two independent averages.

- 20 selection seeds (100–119) for every choice, then 20 fresh holdout seeds (2000–2019). Each run covers weeks 78–155: a 26-week warm-up from a steady-state start, then KPIs over weeks 104–155, annualised.
- 95% interval: mean(d) ± t₀.₉₇₅,₁₉ × sd(d) ÷ √20. A percentile bootstrap over seeds agreed on the selection results.
- In the stress worlds, P1 and P2 are re-planned from that world's own history; P0 follows its fixed rule.

---

## 12. Holdout freeze discipline

1. Forecast champions, every PolicySpec parameter table (all worlds), the frontier candidate set and the configs are fixed using only training data and selection seeds.
2. `scripts/freeze_all.py` writes `outputs/freeze/manifest.json` with SHA-256 hashes of 19 artefacts.
3. The holdout runner refuses to start if any hash differs, and `evaluate()` refuses the holdout seeds during selection. `tests/test_freeze.py` checks this.
4. Git history shows the freeze commit before the holdout-results commit: v1 archived at `f02f4eb`, calibration locked at `42c02d8`, freeze at `e57a265`, holdout results at `64e6511`.
5. The holdout is run once. Every run is appended to `outputs/freeze/holdout_log.json`: 3 main v2 runs and 1 post-plan run, 0 forced.

Manifest hash (SHA-256 of `outputs/freeze/manifest.json`): `407689699aefd27f9969c34d752245353b45269b730937f2801783ffc7fe7205`.

**Fresh seeds.** The v1 holdout seeds (retired v1 holdout (archived)) had been seen, so v2 uses 2000–2019 (D013). The v1 holdout had one disclosed forced rerun of a block that crashed before producing output (D010); its root cause, a non-atomic scenario cache, was fixed in V2-SIM-18 before the v2 freeze.

**Post-plan check (D015).** After the main v2 holdout, the author asked how the frozen central-built I125 does in the stress worlds. P0, P2 and I125 were run once on the holdout seeds in the low- and high-stress worlds, paired against P2, with no re-selection, and logged at `37467a6`: low stress −85 h [−125 to −45] a year and total annual cost −AED 1.7M [−2.9 to −0.4] for +AED 7.7M capital (I125 62 h vs central-built P2 147 h); high stress −184 h [−239 to −128] a year and total annual cost −AED 5.0M [−6.8 to −3.1] for +AED 7.5M capital (I125 76 h vs central-built P2 260 h). It is labelled post-plan because it was not in the frozen run plan.

---

## 13. Economics

All money is in AED.

| Quantity | Definition | Type |
|---|---|---|
| **Spares capital** | Time-average value, at unit cost, of owned spares: serviceable anywhere, in transit, and rotables in the repair pipeline. Borrowed units are never capital | Stock (a balance) |
| Holding cost | Carrying rate × spares capital. Rate 20%/yr, range 15–25% (ASSUMED) | Annual |
| Repair cost | Shop visits, including NFF tests | Annual |
| Logistics cost | Routine shipments | Annual |
| Expedite and route fees | Emergency shipments, exchange/loan and borrow fees, robbery labour, local-buy premiums | Annual |
| AOG cost | AED 15,000/h (narrowbody) or 30,000/h (widebody), plus a fixed AED 40,000 (NB) / 100,000 (WB) per merged event. A **scenario value**; the sensitivity scales the hourly part ×0.5 and ×2 with the per-event cost kept at ×1 (V2-POL-5) | Annual |

**Total annual cost = holding + repair + logistics + expedite and route fees + AOG cost.** Capital is a balance, not a flow, so it is never added to annual cost. Purchase spend for consumption is reported but not added: demand is the same across policies. **Brakes:** cost-per-landing contracts are not modelled; brake units are owned and repaired like other rotables.

---

## 14. Engine and data fixes made before the freeze

Each item is a documented non-calibration correction, decided before any result it could flatter (details in [DECISIONS.md](docs/DECISIONS.md)):

| ID | Kind | What changed |
|---|---|---|
| V2-SIM-10 | Design mismatch | P0's protection level now applies to fill P(X ≤ S − 1), the quantity the engine measures; before, P0 missed its own target even on paper. |
| V2-SIM-11 | Design mismatch | P0's quoted pipeline weights core-return transport by the share of removals rectified at an outstation, matching the engine. |
| V2-SIM-12 | Bug | A scheduled need is no longer blocked by reservations for later scheduled needs (priority inversion). |
| V2-SIM-13 | Engine | A wear-planned brake change triggers supply at notice when the hub will be short: a transfer, else a pre-arranged exchange/loan. |
| V2-SIM-14 | Engine | A failed AOG route is retried with fresh paired draws while the need is open, instead of waiting weeks for a PO. |
| V2-SIM-15 | Data | Wheel-and-tyre assemblies are rebuilt in a hub shop in days, not at the EU vendor in months. |
| V2-SIM-16 | Decision | Calibration band recorded (ASSUMED plausibility band, author decision); the starting-point line-station rule kept. |
| V2-SIM-17 | Bug | A need whose earmarked shelf-life units expire on arrival is re-opened and re-routed. |
| V2-SIM-18 | Bug | Atomic scenario-cache writes, so parallel workers cannot read a truncated file (the D010 root cause). |
