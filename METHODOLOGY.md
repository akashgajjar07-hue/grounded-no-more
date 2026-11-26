# Methodology

How GROUNDED NO MORE turns a simulated airline into planning decisions, and how those decisions are tested. The contract every module builds against is in [`docs/data_contract.md`](docs/data_contract.md); every parameter is in [`config/assumptions.yaml`](config/assumptions.yaml) and the [assumption register](docs/assumption_register.md).

Parameter values quoted below come from the config and are **ASSUMED** unless marked otherwise. Result values are shown as `{{RESULT:…}}` placeholders until the pipeline fills them.

**Contents**

1. [Design principles](#1-design-principles)
2. [The synthetic world (generator)](#2-the-synthetic-world-generator)
3. [Exposure](#3-exposure)
4. [Demand types](#4-demand-types)
5. [Event engine semantics](#5-event-engine-semantics)
6. [Forecasting and its evaluation](#6-forecasting-and-its-evaluation)
7. [Inventory and rotable policy maths](#7-inventory-and-rotable-policy-maths)
8. [Network positioning](#8-network-positioning)
9. [Greedy marginal allocation and the Readiness Frontier](#9-greedy-marginal-allocation-and-the-readiness-frontier)
10. [Paired-seed evaluation](#10-paired-seed-evaluation)
11. [Holdout freeze discipline](#11-holdout-freeze-discipline)
12. [Economics](#12-economics)

---

## 1. Design principles

| Principle | How it is enforced |
|---|---|
| Planning models never see the truth | True rates live in `data/ground_truth/`. `tests/test_leakage.py` scans the source of `gnm.forecasting`, `gnm.policy`, `gnm.optim`, `gnm.aog` and `gnm.export` for any import of the truth or the generator internals. |
| One set of mechanics for every policy | A policy is a parameter table (`PolicySpec`). One event engine runs them all ([D002](docs/DECISIONS.md)). |
| Same world for every policy | Exogenous demand and the random draws for repair time, condemnation and lead time are pre-sampled into a `Scenario` (common random numbers, [D003](docs/DECISIONS.md)). |
| Test once, on data nobody tuned against | Parameters are hashed before the holdout runs ([section 11](#11-holdout-freeze-discipline)). |
| Every number traceable | Each table and JSON object carries a provenance tag. `tests/test_reconciliation.py` recomputes the KPIs shown in the app from `outputs/`. |

---

## 2. The synthetic world (generator)

`gnm.sim.generator` builds the world from `world_seed = 2023`.

**Fleet.** 24 narrowbody (A320-family archetype) and 16 widebody (787-family archetype) aircraft with fictional registrations (`A6-FH?`, `A6-FW?`). Daily utilisation is drawn per aircraft: narrowbody about 10.5 FH and 4.2 FC per day, widebody about 14.0 FH and 1.6 FC per day (ASSUMED). Weekly, monthly and holiday seasonality factors scale utilisation.

**Network.** Hub AUH and six outstations (LHR, FRA, CAI, JED, BOM, SIN). Station coordinates are REAL (OurAirports). Narrowbodies fly to CAI, JED and BOM; widebodies to LHR, FRA, BOM and SIN, in the shares given by `network.route_mix` (ASSUMED). BOM is the only outstation both fleets serve.

**Parts.** 120 fictional part numbers in the format `GN-<ATA>-<C|E|R><nnn>`: 45 consumables, 35 expendables and 40 rotables across 13 ATA chapters. Each part draws, within ASSUMED ranges:

| Attribute | Consumable | Expendable | Rotable |
|---|---|---|---|
| Unit cost (AED, log-uniform) | 20–500 | 500–15,000 | 15,000–500,000 |
| Purchase lead time mean (days) | 7–45 | 14–90 | 30–180 |
| Demand driver | Line usage per 1,000 FC, plus kits | Removals (FH or FC) | Removals (FH or FC) |
| Repair | No | No | Shop TAT 15–90 days, cost 8–25% of unit cost, condemnation 1–8% |

**Reliability.** Removal-driven parts have a true MTBUR (3,000–40,000 FH, or 2,000–25,000 FC for the 35% that are cycle-driven). The part master publishes a **vendor-quoted** MTBUR, which is the truth times lognormal noise (σ_log = 0.35) and 25% optimistic on average ([D005](docs/DECISIONS.md)). About 30% of parts have overdispersed, clustered demand (negative binomial, shape k in 0.6–3.0). All of this is ASSUMED and SIMULATED. None of it is measured reliability.

**Planted situations.** Four documented demo situations (PS1–PS4) are built in so the planner screens have something real to find: an understocked D0 rotable at BOM, an overdue repair order at the EU vendor, a declining consumable creating excess, and a lead-time jump on one expendable around week 70.

**Scenarios.** `generate_scenario(world, truth, seed, week_from, week_to)` returns the exogenous events for one seed: flights, the maintenance schedule, removals and material requests, plus pre-sampled repair durations, condemnation flags and PO lead-time streams. Downstream code receives only this `Scenario`, never the truth.

---

## 3. Exposure

Removals happen because aircraft fly. Exposure is the flying that drives them:

- **FH-driven parts** accumulate flight hours.
- **FC-driven parts** (landing gear, brakes, doors, APU starts) accumulate flight cycles.
- **Consumables** are used per 1,000 FC of line maintenance, plus scheduled kits.

For a removal-driven part with installed quantity *q* per aircraft, the expected removal rate over a period is

$$
\lambda = \frac{q \times \text{exposure in the period}}{\text{MTBUR}}
$$

summed over the aircraft that carry the part. A part fitted twice per aircraft on a fleet flying 1,000 FH a day with an MTBUR of 10,000 FH would see about 0.2 removals a day. (Illustrative numbers.)

**No exposure feedback.** A grounded aircraft still accrues scheduled exposure. The assumption is that protection flying (a spare aircraft or a sub-charter) covers the schedule, and the cost of lost flying sits in the AOG penalty. This keeps demand identical across policies, which the paired comparison needs ([D004](docs/DECISIONS.md), [LIMITATIONS](LIMITATIONS.md)).

---

## 4. Demand types

| Source | Parts | Known in advance? | Notes |
|---|---|---|---|
| `unscheduled_removal` | Rotables, expendables | No: `known_h = need_h` | One removal = one unit. Carries the part's deadline class. |
| `scheduled_kit` | Consumables (about half of PNs) | Yes: 21 days' notice before the A-check | A-checks every 750 FH (narrowbody) or 1,000 FH (widebody) at AUH, 6–14 kit lines each. Kits reserve stock from `known_h`. |
| `line_usage` | Consumables | No | Poisson or negative binomial on cycles flown. |

Requests record **unconstrained** demand ([D006](docs/DECISIONS.md)): a removal happens whether or not a spare exists. Forecasting therefore sees true demand, not sales censored by stockouts. That is how removal-driven demand works in aviation, and it is a simplification for consumables, where real issue history can be censored.

**Deadline classes** are hypothetical requirement deadlines, not MEL categories ([D009](docs/DECISIONS.md)):

| Class | Window | Meaning in the engine |
|---|---|---|
| D0 | 0 h | Needed before next departure. The aircraft is AOG from need time until the part is fitted. |
| D3 | 72 h | AOG only if not fitted within 72 h, from that point until fitted. |
| D10 | 240 h | AOG only if not fitted within 240 h, from that point until fitted. |

---

## 5. Event engine semantics

`gnm.sim.engine` is a continuous-time discrete-event simulation at hour resolution. For a given (Scenario, PolicySpec) it is deterministic.

**Request lifecycle.** At need time the engine tries local serviceable stock. If there is none it sources, in order, by the policy's rules:

1. Emergency transfer from the station's allowed sources, AUH first for P0 and P1. Arrives after the AOG transport time (for example AUH→BOM 9 h, AUH→LHR 16 h; ASSUMED, including next flight out, handling and customs).
2. Lateral transfer from another outstation, if the policy allows it.
3. Pool exchange, if the policy has a pool contract (P3, stretch).
4. Otherwise a backorder, filled by the next receipt (repair return or PO). An expedite PO is raised if the policy says so.

**AOG accounting.** Grounding intervals are merged per aircraft: two missing parts on one aircraft at the same time count once. `aog_events.hours` is the merged duration.

**Rotables are serialised.** Every serial is in exactly one state and location:

```
SERVICEABLE@station → INSTALLED@tail → REMOVED → IN_REPAIR@shop → SERVICEABLE@AUH
                                                              ↘ CONDEMNED
```

A removed unit (the core) travels to AUH (about 5 days), then to its shop (0 days for the AUH in-house shop, 4 days for the EU vendor). Shops have finite parallel capacity (6 and 8 slots), so work queues. Work time is the pre-sampled repair duration times any TAT multiplier the policy pays for. A condemned unit triggers a replacement PO. Repair returns land at AUH. When a station issues a unit, AUH sends a routine replacement (about 4 days) if it has stock, keeping each station at its base stock.

**Consumables and expendables** use continuous review on inventory position (on hand + on order + in transit in − backorders − reservations). When it falls to the reorder point *s*, the station orders up to *S*. Outstations replenish from AUH; AUH replenishes by PO. Shelf-life items expire first-in, first-out.

**Conservation invariants** are tested: each serial has one current state; per PN, opening serials + purchased − condemned = closing serials; for counted stock, opening + receipts − issues − expiries ± transfers = closing; every transfer debits its origin; repairs never create units.

---

## 6. Forecasting and its evaluation

### 6.1 Split calendar

| Block | Weeks | Use |
|---|---|---|
| Train | 0–77 | Fit models and estimate removal rates |
| Selection | 78–103 | Rolling-origin selection: origins every 4 weeks, horizon 4 weeks |
| Holdout | 104–155 | Run once, after the freeze |

### 6.2 Demand classification

Each PN's weekly series is classified with the Syntetos–Boylan scheme on the training window:

- **ADI** (average demand interval) = number of periods ÷ number of periods with non-zero demand.
- **CV²** = squared coefficient of variation of the non-zero demand sizes.

| | CV² < 0.49 | CV² ≥ 0.49 |
|---|---|---|
| **ADI < 1.32** | smooth | erratic |
| **ADI ≥ 1.32** | intermittent | lumpy |

Series with too few non-zero periods to estimate CV² are labelled `insufficient_data`.

### 6.3 Methods

| Method | Idea | Best suited to |
|---|---|---|
| Naive / moving average | Benchmarks | Scaling (MASE) and sanity |
| Simple exponential smoothing | Smoothed level | Smooth demand |
| **Croston** | Smooth demand size and interval separately; forecast = size ÷ interval | Intermittent |
| **SBA** (Syntetos–Boylan approximation) | Croston × (1 − α/2) to remove Croston's known upward bias | Intermittent, lumpy |
| **TSB** (Teunter–Syntetos–Babai) | Smooth the probability of demand each period instead of the interval, so the forecast decays when demand stops | Obsolescence risk, declining parts |
| **Bootstrap** (Willemain-style) | Resample observed history, with a Markov model for zero/non-zero runs and jittered sizes, to build a full lead-time demand distribution | Lumpy demand, quantiles for stock setting |
| **Reliability-exposure model** | Removal rate = installed quantity × projected exposure ÷ estimated MTBUR. MTBUR is estimated from observed removals and cumulative exposure, starting from the vendor-quoted figure and moving towards the evidence as removals accumulate | Removal-driven rotables and expendables |

Croston-family methods use the `statsforecast` implementations where available. The reliability model is the project's hypothesis: because it uses the exposure that drives removals, it should beat time-series methods that only see the demand history, especially when utilisation changes. The selection window tests that hypothesis rather than assuming it.

### 6.4 Metrics

- **MASE** (mean absolute scaled error): forecast MAE ÷ in-sample MAE of the one-step naive forecast on the training window. Scale-free, so it can be averaged across parts. Below 1 means better than naive.
- **Bias**: mean forecast error. Persistent positive bias means overstocking.
- **PIS** (periods in stock): the cumulative forecast error summed over the horizon. It measures how many unit-periods of stock (positive) or shortage (negative) a forecast would have produced. It catches bias that MAE-type measures miss, which matters for intermittent demand where a zero forecast can score a deceptively good MAE.
- **Coverage**: share of actuals that fall inside the forecast's prediction interval, for methods that produce a distribution.
- **Stock-based evaluation**: the forecast's lead-time demand distribution is turned into a reorder point, and the resulting fill rate and stock are compared. A forecast is only as good as the stock decision it supports.
- **Truth recovery** (evaluation only): how close each method's implied rate gets to the hidden true rate. Only `gnm.eval.truth_recovery` reads the truth.

### 6.5 Selection

A champion is picked per demand class and part class by mean MASE across rolling origins in the selection window, with bias and PIS as tie-breakers. Confidence intervals on MASE differences are bootstrapped over parts. Results: `{{RESULT:forecast.leaderboard_table}}`.

---

## 7. Inventory and rotable policy maths

### 7.1 Palm's theorem and the repair pipeline

For a rotable, the question is not "how many will we use" but "how many will be away being repaired at any moment".

Let removals arrive as a Poisson process with rate λ, and let each removed unit spend a turnaround time *T* in the pipeline (core return + transit + shop queue + shop work + return), with any distribution and mean E[T]. **Palm's theorem** says the number of units in the pipeline at a random moment, *X*, is Poisson with mean

$$
X \sim \text{Poisson}(\lambda \cdot E[T])
$$

regardless of the shape of the TAT distribution, provided the repair times are independent and repair capacity is unlimited. Shops here have finite capacity, so queueing adds to *T*. The policy uses an estimate of E[T] that includes average queue time, and the simulation is the referee.

### 7.2 Base stock, backorders and availability

With a base stock (float) of *S* units, a demand is filled immediately if fewer than *S* units are in the pipeline. The key quantities:

$$
\text{EBO}(S) = E[\max(X - S, 0)] = \sum_{x > S} (x - S)\,P(X = x)
$$

$$
\text{Probability a demand finds stock} = P(X < S) = P(X \le S - 1)
$$

EBO (expected backorders) is the time-average number of unfilled demands. With D0 parts each backorder is, to a first approximation, one aircraft on the ground, so EBO × hours per year approximates AOG aircraft-hours per year before interval merging.

Two facts drive the optimiser:

- **Marginal value of one more unit:** EBO(S) − EBO(S+1) = P(X > S).
- **Convexity:** P(X > S) falls as S rises, so EBO is decreasing and convex in S. Each extra unit is worth less than the one before.

A worked numeric example (λ = 2 per 30 days, TAT 30 days) is in the [study guide](STUDY_GUIDE.md#poisson-float-and-ebo-worked-example).

When demand is overdispersed (negative binomial), the Poisson pipeline understates variance. The policy then uses a negative binomial with the estimated dispersion for the pipeline distribution. This is a pragmatic extension, not part of Palm's theorem.

### 7.3 Consumables and expendables: (s, S)

For counted stock, lead-time demand (LTD) is built from the champion forecast over the purchase lead time (or the transfer time for outstations). The reorder point *s* is the LTD quantile that meets the service target for the part's deadline class: 0.97 for D0, 0.92 for D3, 0.85 for D10 (ASSUMED). The order-up-to level *S* = *s* + an order quantity sized from average demand. Lead-time uncertainty enters through the quoted lead-time CV.

### 7.4 Policies compared

| Policy | Description |
|---|---|
| **P0 Legacy** | Static rules. Consumables: min = 6 weeks of average demand, max = 2 × min. Rotables: float = ceil(5% of installed fleet quantity), all at AUH; an outstation holds 1 unit only for D0 parts with fleet quantity ≥ 40. |
| **P1 Data-driven, hub float** | Forecast-based (s, S) and Palm-based floats, with the float held at AUH. |
| **P2 Data-driven, positioned** | As P1, but rotable float allocated across hub and outstations by the network model and the frontier. |
| **P3 Pool exchange** *(stretch)* | P2 plus a pool contract: 24 h response, fee 8% of unit cost per exchange, 10-day core return, AED 250,000 annual access fee, capacity 6 exchanges a month (all ASSUMED). |

---

## 8. Network positioning

The positioning model is **METRIC-inspired, not full METRIC**. It borrows Sherbrooke's two-echelon logic but simplifies it.

- **Station pipeline.** An outstation that issues a unit is resupplied from AUH. Its pipeline is the resupply time: routine transport (about 4 days) plus the expected delay if AUH is itself out of stock.
- **Hub delay.** The AUH delay is approximated from the hub's own EBO: expected delay ≈ EBO_hub ÷ network demand rate (Little's law).
- **Station demand.** Each station's removal rate comes from the flying its routes generate: route mix × fleet exposure × installed quantity ÷ estimated MTBUR.
- **Emergency cover.** A station without stock is covered by an emergency transfer with a known AOG transport time. For D0 parts the cost of a station stockout is roughly that transport time in AOG hours; for D3/D10 parts it is often zero, because the transfer arrives inside the window.

Simplifications versus full METRIC: no variance correction for the station pipeline (VARI-METRIC), no explicit lateral pooling in the analytic model (laterals appear only in the simulation where a policy allows them), and repairs happen only at the hub's shops. The event engine runs the real mechanics, so any error in the approximation shows up in the evaluation rather than being hidden by it.

---

## 9. Greedy marginal allocation and the Readiness Frontier

**Objective.** Minimise expected AOG risk, weighted by archetype penalty and deadline class, for a given spares capital.

**Algorithm.** Start from the minimum allocation (zero, or a floor). Repeatedly add the single unit — one (PN, station) pair — with the largest reduction in expected AOG risk per AED of capital. Record the (capital, risk) point after each step. The sequence of points is the frontier.

**When greedy is optimal, and when it is not.** If the objective is a sum of separate terms, one per (PN, station), and each term is decreasing and convex in its stock level (as EBO is), marginal analysis yields allocations on the lower convex hull of the exact frontier. At those budgets it is optimal; between them, an integer knapsack could do slightly better. Two things in this project break separability: hub and station stock interact (the hub delay term), and AOG intervals merge per aircraft. So **greedy is a heuristic here**, chosen for speed, transparency and because each step has a clear "why this unit next" explanation a planner can check.

**Picking candidates and the recommendation.** A set of frontier points is chosen on the selection seeds (100–119) and frozen. Each candidate is then run through the event engine on the holdout seeds (1000–1019) to get simulated AOG hours with confidence intervals. The recommended point is `{{RESULT:frontier.recommendation_rule}}` (the rule is fixed before the holdout, for example the knee of the frontier or the cheapest point whose AOG hours beat a target).

Recommended: capital `{{RESULT:frontier.recommended.capital_aed}}` AED, AOG hours `{{RESULT:frontier.recommended.aog_hours}}` per year (95% CI `{{RESULT:frontier.recommended.aog_hours_ci}}`).

**Levers beyond buying stock.** The frontier also prices alternatives: paying the vendor to cut TAT (AED 400 per unit per day, ASSUMED), repositioning existing units, and pool access. A sensitivity (tornado) view varies the starred config parameters: AOG penalty (×0.5, ×1, ×2), carrying cost (15–25%), repair TAT and unit cost.

---

## 10. Paired-seed evaluation

Every policy and frontier candidate runs on the same scenarios. For a KPI *K* and seed *s*, the paired difference is

$$
d_s = K_{\text{policy},s} - K_{\text{P0},s}
$$

Because both policies faced identical removals, repair times and lead times, the seed-to-seed noise in the world cancels, and the interval on the mean of *d_s* is much narrower than comparing two independent averages.

- 20 holdout seeds (1000–1019), 52-week window (weeks 104–155) after an 8-week warm-up from week 96.
- 95% interval: mean(d) ± t₀.₉₇₅,₁₉ × sd(d) ÷ √20, with t₀.₉₇₅,₁₉ ≈ 2.093. A percentile bootstrap is reported alongside when the differences are skewed.
- KPIs are annualised to 52 weeks.

---

## 11. Holdout freeze discipline

1. Forecast champions, every PolicySpec parameter table, the frontier candidate set and the config are fixed using only training, selection and selection seeds.
2. `scripts/freeze.py` writes `outputs/freeze/manifest.json` with SHA-256 hashes of all of them.
3. The holdout runner refuses to start if any hash differs. `tests/test_freeze.py` checks this.
4. Git history shows the freeze commit before the holdout-results commit.
5. The holdout is run once. If a bug is found afterwards, the fix, the re-freeze and the re-run are all logged in [DECISIONS.md](docs/DECISIONS.md).

Freeze commit: `{{RESULT:freeze.commit_sha}}`. Manifest hash: `{{RESULT:freeze.manifest_sha256}}`.

---

## 12. Economics

All money is in AED.

| Quantity | Definition | Type |
|---|---|---|
| **Spares capital** | Time-average value, at unit cost, of owned spares: serviceable anywhere, in transit, and rotables in the unserviceable and repair pipeline | Stock (a balance) |
| Holding cost | Carrying rate × spares capital. Rate 20%/yr, range 15–25% (ASSUMED) | Annual |
| Repair cost | Shop visit costs | Annual |
| Logistics cost | Routine shipments (AED 150 per line, ASSUMED) | Annual |
| Expedite cost | Emergency shipments (AED 2,000–15,000 each, scaled by distance) plus expedite purchase premium (15%) | Annual |
| AOG penalty | AOG hours × AED 15,000/h (narrowbody) or 30,000/h (widebody). A **scenario value**, sensitivity-tested at ×0.5, ×1, ×2 | Annual |

**Total annual cost = holding + repair + logistics + expedite + AOG penalty.**

**No double counting.** Capital is a balance, not a flow, so it is never added to annual cost; its annual effect is the holding cost. Purchase spend for consumption replenishment (`purchase_spend_aed`) is reported but not added to total cost: demand is the same across policies, so consumption spend is largely common to all of them, and the stock it builds is already counted in capital. The AOG penalty is shown on its own line so a reader can drop it and compare operating costs alone.
