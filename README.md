# GROUNDED NO MORE

**The right spare, at the right station, before an aircraft needs it.**

An aviation materials-planning simulation exploring how spare-parts forecasting, repair time, stock positioning and capital affect how long aircraft sit grounded waiting for parts.

[![CI](https://github.com/akashgajjar07-hue/grounded-no-more/actions/workflows/ci.yml/badge.svg)](https://github.com/akashgajjar07-hue/grounded-no-more/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-22C7B8)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-B9C8D6)](LICENSE)

**Web app (GitHub Pages):** <https://akashgajjar07-hue.github.io/grounded-no-more/>

![GROUNDED NO MORE: Mission Control view](docs/assets/readme/hero.png)

**40 aircraft · 120 part numbers · 7 stations · 20 fresh test runs**

*Independent educational simulation · Fictional airline · No operational airline data.*

---

## What this is

An airline keeps a shelf of spare parts so that when something comes off an aircraft, a working one can go straight back on. If the right spare is not on the shelf at the right airport, the aircraft sits on the ground and waits. This project builds a fictional airline, **Falcon Hub Airways (fictional)**, with a hub and six other airports, and simulates two years of parts coming off its aircraft. It then tests four ways of deciding how many spares to hold and where to keep them:

| Plan | In one line |
|---|---|
| **Simple Rulebook (naive reference)** `P0` | Holds spares by the supplier's quoted numbers, almost all at the hub. A deliberately simple starting point, not a model of a competent airline. |
| **Each Airport for Itself (simplified local comparator)** `P1` | Each airport sizes its own shelf from its own history and ignores the rest of the network. A deliberately simple comparator. |
| **Network Plan** `P2` | Learns from the history, pools most repairable parts at the hub and places a spare at an outstation only where a no-go part is worth it. |
| **Network Plan + Extra Spares** `I125` | The Network Plan plus extra repairable spares picked one at a time for the most downtime removed per dirham. |

Each plan is tested on 20 fresh test runs the model never saw, with every plan facing identical events, so the differences come from the plans and not from luck.

## Why it matters

Spare parts are one of the largest capital lines in an airline's engineering budget, and most of that money sits in a small number of expensive repairable parts that are needed rarely and unpredictably. Too little stock in the wrong place grounds aircraft; too much ties up money for years. The trade-off is a planning problem, not a purchasing one, and it is easy to get wrong in both directions.

## What I found

Hours aircraft spent waiting for a part, per year, in the simulation: about 1,690 h under the Simple Rulebook (naive reference) `P0` and 210 h under the Network Plan `P2`. The Each Airport for Itself (simplified local comparator) `P1` sits between them at 566 h, and the Network Plan + Extra Spares `I125` goes lower, to 76 h, for extra capital.

| Plan | Downtime waiting for parts, h / yr [likely range] | Average spare inventory |
|---|---|---|
| Simple Rulebook (naive reference) `P0` | 1,690 h [1,555–1,826] | AED 48.4M |
| Each Airport for Itself (simplified local comparator) `P1` | 566 h [452–680] | AED 71.9M |
| Network Plan `P2` | 210 h [146–274] | AED 49.0M |
| Network Plan + Extra Spares `I125` | 76 h [50–102] | AED 56.7M |

*across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part*

> How to read these numbers: simulated downtime of the aircraft waiting for the part, across 120 modelled part numbers. Downtime of aircraft that donated a part (cannibalisation) is shown separately, not included. The Simple Rulebook is a deliberately simplified starting point, not a model of a competent airline. Part costs, reliability and sourcing are assumed. These are not forecasts of achievable airline savings.

**It is not a free move of existing stock.** Going from the Simple Rulebook to the Network Plan buys some parts and removes others:

| Capital change, Simple Rulebook (naive reference) `P0` → Network Plan `P2` | Amount |
|---|---|
| New rotables bought | +68 units ≈ AED 8.4M assumed value |
| Rotables removed | −20 units ≈ AED 3.1M |
| Net change in average simulated spare inventory | +AED 0.6M |

*Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a discount.* Units and values: target units × assumed unit cost from the policy tables; the net is the paired holdout change in time-averaged simulated spare inventory, so it differs slightly from bought minus removed.

**How wide the test was.** The three simulated worlds differ only in how reliable the parts are: reliability scaled ×0.96 / ×1.00 / ×1.08 — a narrow range. Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.

**The most useful insight.** Faster repair can beat buying spares: with 25% shorter repair time, the extra-investment option loses its clear cost advantage. The levers to compare are: faster repair · pool access · better reliability · more spares.

**Donor downtime.** Hours that donor aircraft (aircraft that gave up a part to another) spend waiting for a replacement are not reconstructible from current logs for the frozen test runs, so no per-plan figure is given. What the logs do allow (post-plan, exploratory): parts borrowed from another of our aircraft per year in the test runs, Simple Rulebook (naive reference) `P0` 33.2 [28.5–37.9]; Each Airport for Itself (simplified local comparator) `P1` 31.3 [27.1–35.4]; Network Plan `P2` 22.5 [18.4–26.6]; for the Network Plan + Extra Spares `I125` this is not reconstructible either. For scale only, in the historical record of the Simple Rulebook (naive reference) `P0` (history weeks 0–103, one simulated history, not the test runs), donor aircraft were held about 5,285 h a year, beside 1,282 h a year of counted waiting-for-part downtime in that same history. Gross donor hours are an upper bound: a donor may already be in maintenance or not scheduled to fly.

**Findings that do not flatter the method**, kept visible on purpose:

- **The chosen forecasting methods rarely won on the fresh test runs.** The method chosen in advance was best in only 3 of 9 groups of parts. For rarely-needed repairable parts the chosen method (SBA) ranked 6th of 9.
- **History beats the supplier's quote on reliability.** Estimating how often a part comes off the aircraft from the airline's own history was about 7% off the hidden truth; the supplier quotes were about 14% off.
- **The chance of finding the part on the shelf is slightly lower under the Network Plan**, about 1.25 points lower than the Simple Rulebook, because it keeps leaner stocks of cheap consumables. Those shortages rarely ground an aircraft here.
- **Every plan depends on the emergency routes.** Borrowing a part from another of our aircraft, borrowing from other airlines and short-notice exchange or loan all carry weight. Switch them off and downtime rises sharply for every plan, the Simple Rulebook included.

## How to read it

- **Downtime** means the hours an aircraft waits for a part (in the specialist sections: material AOG hours). The downtime clock starts when the part is removed (for no-go items; for deferrable items, when the rectification window runs out), not at the next scheduled departure, and overnight and other non-flying hours count in full. Fitting and release-to-service time is included. A departure-based count would be lower for every plan.
- **Scope.** Every headline number is across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part. It is not every part on the fleet, and it is not fleet downtime.
- **Likely ranges** in square brackets are 95% intervals over the 20 test runs. Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.
- **Plan codes** (`P0`, `P1`, `P2`, `I125`) appear in small code type after each name, so you can match them to the specialist tables and the web app.
- **Money** is in AED (UAE dirhams). Capital (stock held) is never added to annual running cost.
- Every value carries a provenance tag: REAL, DERIVED, ASSUMED or SIMULATED (see the table under "For specialists").

## Limits

- **The data is simulated.** The airline, its aircraft, part numbers, failures and repair times are all generated from assumed values.
- **The starting point was chosen, not measured.** The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the model, not benchmarked against real airline KPIs. A line-kit variant (≈1,052 h) was measured but not adopted because it fell outside that range. All results are conditional on this choice.
- **The Simple Rulebook is deliberately weak.** Much of the gap to the Network Plan comes from stocking no-go parts at outstations, which a competent operator would already do.
- **Donor downtime is not in the headline.** When a part is borrowed from another of our aircraft, that aircraft's waiting time is not counted.
- **Some plan lines are flagged, not removed.** Outstation brake allocations in the frozen plans are flagged as an **invalid recommendation — brakes are not changed outside the hub in this model**: 5 in the Network Plan `P2` (GN-32-R013 at BOM, GN-32-R013 at CAI, GN-32-R013 at JED, GN-32-R036 at LHR, GN-32-R036 at SIN), 7 in the Network Plan + Extra Spares `I125` and 6 in the Simple Rulebook (naive reference) `P0`. They stay in the frozen results so the numbers are unchanged, but no planner should act on them.
- **Results depend on the emergency routes, the assumed costs and the downtime clock described above.**

The full list, including every finding from the domain review and its status, is in [LIMITATIONS.md](LIMITATIONS.md).

---

## For specialists

Technical detail: holdout statistics, the worked story, method notes and the reproduction steps. The project uses aviation terms from here on (material AOG, rotable, float, TAT, MTBUR, holdout, CI).

### Headline

Holdout results: 20 paired seeds (2000–2019), 52 weeks (weeks 104–155), central world, run once after the freeze. "Material AOG" means expected material-related downtime hours: the hours an aircraft waits for a part that was not available in time. The downtime clock starts when the part is removed (for no-go items; for deferrable items, when the rectification window runs out), not at the next scheduled departure, and overnight and other non-flying hours count in full. Fitting and release-to-service time is included. A departure-based count would be lower for every plan. The scope is the modelled catalogue of 120 AOG-critical part numbers, not every part on the fleet.

**Network Plan `P2` vs Simple Rulebook (naive reference) `P0`: −1,480 h a year [−1,629 to −1,332]** of material AOG (paired over the 20 holdout seeds 2000–2019, 95% t-interval), from 1,690 h to 210 h. The Network Plan holds 44 rotables at the six outstations instead of 8, pools the rest at the hub. The lead over the Simple Rulebook (naive reference) holds in all three stress worlds and across the ×0.5–×2 range of the hourly AOG cost.

*across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part*

The Network Plan is not a free repositioning of the Simple Rulebook (naive reference)'s float. It buys rotables for no-go (D0) items and sheds high-value deferrable ones, so procurement would see a purchase request plus disposals:

| Capital change, Simple Rulebook (naive reference) `P0` → Network Plan `P2` | Amount |
|---|---|
| New rotables bought | +68 units ≈ AED 8.4M assumed value |
| Rotables removed | −20 units ≈ AED 3.1M |
| Net change in average simulated spare inventory | +AED 0.6M |

*Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a discount.* Units and values: target units × assumed unit cost from the policy tables; the net is the paired holdout change in time-averaged simulated spare inventory, so it differs slightly from bought minus removed.

**Frontier option: if you invest an additional AED 7.6M**, the frontier point I125 (P2 plus greedy rotable additions) cuts a further 134 h a year [87–181] vs P2 (76 h vs 210 h) and lowers total annual cost by AED 3.3M [1.8–4.8] (holdout, paired). Sensitivity, on the selection seeds and one factor at a time: its cost lead over P2 is not significant if repair is 25% faster (+AED 0.36M [−0.75 to 1.46] a year), and the pre-stated rule moves to I110 at ×0.5 and B150 at ×2 the hourly rate. Post-plan check (D015, added after the main holdout, no re-selection): low stress −85 h [−125 to −45] a year and total annual cost −AED 1.7M [−2.9 to −0.4] for +AED 7.7M capital (I125 62 h vs central-built P2 147 h); high stress −184 h [−239 to −128] a year and total annual cost −AED 5.0M [−6.8 to −3.1] for +AED 7.5M capital (I125 76 h vs central-built P2 260 h).

Faster repair can beat buying spares: with 25% shorter repair time, the extra-investment option loses its clear cost advantage. Levers: faster repair · pool access · better reliability · more spares. Stress worlds: reliability scaled ×0.96 / ×1.00 / ×1.08 — a narrow range. Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.

**Findings that do not flatter the method**, kept visible on purpose:

- **Forecasting champions rarely won on the holdout.** The frozen champion was best in only 3 of 9 demand-class × part-class cells. For intermittent rotables the frozen SBA champion ranked 6th of 9 (TSB was best in hindsight). The policies size rotables on the reliability-exposure rate instead, so they do not depend on that cell's champion.
- **History beats the vendor quote on reliability.** The history-based MTBUR estimate is about 7% off the hidden truth against about 14% for vendor quotes (median absolute log error, 75 removal-driven parts).
- **Immediate fill is slightly lower under the network plans.** Against `P0`, `P2` changes the share of requests filled from the shelf by −1.25 pts [−1.42 to −1.09] and P1 by −1.26 pts [−1.43 to −1.10]. The cause is lean consumable and expendable reorder points, not rotables (consumables P0 1.000 vs P2 0.983; expendables P0 0.949 vs P2 0.918; rotables P0 0.803 vs P2 0.898).
- **Everything depends on the AOG recovery routes.** Every policy, P0 included, leans on robbery at the hub (used automatically as the first AUH route after local stock, with engineering/quality approval flagged), local borrow at outstations, exchange/loan and local buy: with the routes switched off (selection seeds, a structural stress) material AOG rises from 1,727 h to 42,070 h a year under P0, from 235 h to 18,320 h under P2 and from 92 h to 11,080 h under I125. See [LIMITATIONS](LIMITATIONS.md#economics-and-decisions).
- **Two model limits a domain reviewer flagged, disclosed rather than fixed.** Robbed donor aircraft are assumed grounded until reinstated, but those hours are not counted, so absolute downtime is understated for every policy (about 5,285 a year in the `P0` history, not the holdout). And 6 of the Simple Rulebook (naive reference)'s 8 outstation rotables are brakes that are only changed at AUH, so the `P2`-vs-`P0` gap largely measures stocking no-go items at line stations. See the [review status table](LIMITATIONS.md#v2-domain-review-findings-and-status).
- **Hero part.** Removing 2.3× faster than quoted → escalate to reliability engineering and warranty review first. Extra spares are interim cover, compared against faster repair or pool access.
- **Selection carried over to the holdout:** for P2 the selection-seed value of 6 of 6 headline KPIs lies inside the holdout 95% CI (material AOG 235 h on selection, 210 h [146–274] on holdout); I125 scored 92 h on selection and 76 h [50–102] on holdout (inside the CI).
- **The stress worlds sit at different ends of the calibration band:** the low-stress world reaches the AOG end of the band (pooled history and selection 1,174 h/yr; band end 1,200) at 0.841 rotable fill, and the high-stress world reaches the fill end (0.781; band end 0.78) at about 1,595 h/yr, well short of the 2,700 h end, because fill binds first.

A v1 world was archived after a domain review; see [archive/v1](archive/v1/README.md). Its numbers are not findings.

---

### The story

It is 17:30 local (12:00 UTC) at Mumbai. A narrowbody (fictional tail A6-FHW) about to fly back to Abu Dhabi has its **GN-32-R014** Nose wheel steering actuator (NB) removed unserviceable. It is needed before the next departure (rectification window D0, hypothetical).

BOM holds no serviceable spare. The Simple Rulebook (naive reference) (`P0`) holds 0 units of this part at BOM and 0 at all six outstations together, because it puts a line-station unit only where a D0 part has at least 4 quoted removals a year at that station, and BOM's quoted rate for this part is below that. AUH has 3 on the shelf. The AOG desk ships one on the next flight out: 9 h in transit, then 5 h of fitting and release to service. In the simulated history this exact incident is AOG-0001: 14 h of material-related downtime. The Network Plan (`P2`) holds 2 units at BOM and 6 across the outstations.

**This part carries a planted reliability problem (test case PS1).** The model was built so that it is removed faster than the supplier quotes; the planning screens found that from the history alone, without being told. Finding it is a check that the method works, not a discovery about a real part.

Nothing went "wrong" here. The removal rate, the repair turnaround and the positioning rule together made this grounding likely. That is the question this project answers at fleet scale: which parts, at which stations, carry the material shortage exposure, and what is the cheapest way to take it off the table.

---

### Six questions this answers

**1. Which parts drive material shortage exposure?**
Of 120 part numbers, 11 are flagged urgent (at least 25 hours a year of exposure: material AOG in the Simple Rulebook history plus modelled residual downtime under the frontier option). Together they account for 95% of the Simple Rulebook (P0) history's material AOG hours. The top part is GN-32-R014, Nose wheel steering actuator (NB), at 398 hours a year of exposure (386 h/yr of waiting in the two-year Simple Rulebook history plus 12 h/yr of modelled residual downtime). The largest share of its two-year history downtime was at BOM (35% of its history AOG hours); in the last 52 history weeks it caused 464 h of waiting for the part across the network (25 events), most of it at CAI (177 h). It is the planted test case PS1 (see The story).

**2. Which forecasting method wins, by demand class? Does the reliability model beat the Croston family?**
Champions were frozen per demand class × part class on the selection window and re-scored once on the holdout: best in 3 of 9 cells. For removal-driven parts (holdout) the exposure-based reliability model scores mean MASE 0.918 against 0.907 for the best Croston-family method (TSB), a paired difference of +0.010 (95% CI [−0.014 to 0.036]). Verdict: the reliability model does not beat the best Croston-family method on MASE; the difference is not significant, so it is a tie on point accuracy (75 parts, 95% bootstrap CI over parts). Where it does win is the upper quantile that stocking depends on: it has the lowest q90 pinball loss of all methods for both expendables and rotables on the holdout (expendables 0.286 vs next best 0.290; rotables 0.228 vs next best 0.243).

**3. What float does each plan hold?**
Total rotable spares (serviceable stock plus the 118 units seeded in the repair loop, common to all plans): **Simple Rulebook (naive reference)** `P0` 260, **Each Airport for Itself (simplified local comparator)** `P1` 441, **Network Plan** `P2` 308, **Network Plan + Extra Spares** `I125` 352.

**4. Hub or outstation?**
Both, in proportion. Under P0, 70% of material AOG is at the outstations (1,181 h a year), because P0 holds only 8 rotables there. P1 sizes every station on its own demand and puts 193 rotables forward; P2 pools the float at AUH and positions 44, only where a D0 miss costs more than the unit's carrying cost. Paired against P1, P2 changes material AOG by −356 h [−458 to −254] a year with AED 22.8M less capital: starving the hub to stock outstations moves the shortage to AUH rather than removing it.

**5. What does the Readiness Frontier show?** (how much readiness each extra dirham buys)
P2 is already near the frontier: at P2's capital the best re-optimised allocation is −3 h [−49 to 43] vs P2 (not significant). The gain beyond P2 comes from more capital. The pre-stated break-even rule picks the Network Plan + Extra Spares (`I125`) on the selection seeds; on the holdout it costs AED 7.6M more than P2 for 134 h [87–181] less material AOG a year. That makes it a frontier option for a planner with the budget, not a free lunch.

**6. What should the planner do this week?**
At week 103 the Planner Action Centre raises 63 actions, 25 urgent. The first three in the inbox: A6-FHE (fictional) robbed of GN-32-R014 10 days ago for A6-FHO; not reinstated (urgent: reinstate the donor from the next serviceable AUH unit; keep the engineering/quality approval record open until then); GN-33-E033 recent PO lead time 78 d vs quoted 25 d (×3.1) (urgent: update the planning lead time to ~78 d and recompute the reorder point; ask the supplier for a recovery date); GN-27-R006 at BOM: 0 serviceable (+0 inbound) vs target 1 (demand-implied protection level); 2 D0 requests and 24 material-related downtime h in 52 weeks (urgent: position 1 unit at BOM (station target 0 -> 1) from AUH stock).

---

### Results

Holdout: 52 weeks (weeks 104–155), 20 paired seeds (2000–2019), central world, run once after the freeze. Means with 95% confidence intervals (t-interval over seeds). Capital is shown separately and is never added to annual cost. `P2` is the core finding; `I125` is the frontier option for additional capital.

| KPI | Simple Rulebook (naive reference) `P0` | Each Airport for Itself (simplified local comparator) `P1` | Network Plan `P2` | Network Plan + Extra Spares `I125` |
|---|---|---|---|---|
| Immediate fill rate | 98.9% [98.9–99.0] | 97.7% [97.5–97.8] | 97.7% [97.5–97.8] | 97.9% [97.8–98.1] |
| Material AOG hours / yr | 1,690 h [1,555–1,826] | 566 h [452–680] | 210 h [146–274] | 76 h [50–102] |
| AOG events / yr | 78.0 [73.9–82.0] | 17.3 [14.6–20.0] | 8.6 [6.7–10.5] | 3.9 [3.0–4.8] |
| Spares capital | AED 48.4M [48.3–48.6] | AED 71.9M [71.8–72.0] | AED 49.0M [48.9–49.2] | AED 56.7M [56.5–56.8] |
| Outstation rotable units | 8 | 193 | 44 | — |
| Annual operating cost excl. AOG cost | AED 29.1M | AED 33.0M | AED 29.2M | AED 30.3M |
| Annual AOG cost, scenario (hourly rate + cost per event) | AED 40.5M | AED 14.7M | AED 6.6M | AED 2.2M |
| Total annual cost | AED 69.7M [65.7–73.7] | AED 47.7M [44.3–51.0] | AED 35.8M [33.4–38.1] | AED 32.4M [31.4–33.5] |
| Paired difference in material AOG vs P0 | — | −1,125 h [−1,254 to −995] | −1,480 h [−1,629 to −1,332] | n/a ¹ |
| Paired difference in material AOG vs P2 | +1,480 h [1,332–1,629] | +356 h [254–458] | — | −134 h [−181 to −87] |

¹ The frontier holdout run recorded paired differences against the base policy P2 only, so no paired I125 − P0 interval exists. Money is AED; CIs on money are in AED millions.

*across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part*

> How to read these numbers: simulated downtime of the aircraft waiting for the part, across 120 modelled part numbers. Downtime of aircraft that donated a part (cannibalisation) is shown separately, not included. The Simple Rulebook is a deliberately simplified starting point, not a model of a competent airline. Part costs, reliability and sourcing are assumed. These are not forecasts of achievable airline savings.

All four plans rely on emergency sourcing (borrowing from another aircraft, loans, local purchase). With those routes switched off, every plan's downtime rises sharply — e.g. Network Plan from ≈235 h to ≈18,320 h a year (selection runs). See [Limitations](LIMITATIONS.md#economics-and-decisions).

Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.

**P2 across worlds and penalty settings (holdout).** P1 and P2 are re-planned from each world's own history:

| World | P0 h/yr | P1 h/yr | P2 h/yr | P2 − P0 h/yr [95% CI] | P2 − P0 capital | P2 − P0 total annual cost |
|---|---|---|---|---|---|---|
| low stress | 1,480 | 629 | 217 | −1,263 h [−1,443 to −1,084] | −AED 1.0M | −AED 28.3M [−33.0 to −23.7] |
| central | 1,690 | 566 | 210 | −1,480 h [−1,629 to −1,332] | +AED 0.6M | −AED 33.9M [−37.9 to −29.9] |
| high stress | 1,825 | 641 | 206 | −1,619 h [−1,800 to −1,438] | +AED 3.0M | −AED 37.5M [−41.9 to −33.0] |

P2 − P0 total annual cost at the hourly AOG rate ×0.5 / ×1 / ×2 (the fixed cost per event kept at ×1): ×0.5 −AED 19.0M [−21.1 to −16.8]; ×1 −AED 33.9M [−37.9 to −29.9]; ×2 −AED 63.8M [−71.5 to −56.2].

These are results on simulated data from assumed parameters. They show how the method behaves and how large the effects can be under those assumptions. They are not a forecast of any real airline's performance.

---

### Signature features

| Feature | What it does |
|---|---|
| **Readiness Frontier** | Capital vs expected material-related downtime for every budget, within stated stocking guardrails. Each point is an allocation you can open line by line, with paired-seed confidence intervals. |
| **AOG Response Lab** | Replays the simulated history's groundings. For each one it compares AUH transfer, lateral, local borrow, robbery (shown and flagged for engineering/quality approval; the engine uses it automatically as the first AUH route after local stock, but the lab never ranks it), exchange/loan, local buy and awaiting inbound supply on wait, cost and material shortage exposure. |
| **Planner Action Centre** | A weekly inbox of exceptions (outstation depletion, overdue repair, robbed donor not reinstated, lead-time drift, excess stock) with evidence, owner and a recommended action. |
| **Forecast Lab** | Demand classification (ADI, CV²), method leaderboard by class, and how well each method recovers the hidden true rates. |
| **Rotable & Repair** | Serial lifecycle flows, the simulated repair pipeline (including no-fault-found), TAT and float sizing from Palm's theorem. |
| **Network Positioning** | Hub and six outstations, stock and downtime by station, and the policy comparison. |

---

### How it works

![Pipeline: assumptions to generator to history to models to paired evaluation to web app](docs/assets/readme/pipeline.svg)

1. **Simulate a world.** A seeded generator builds a fictional 40-aircraft fleet (narrowbody and widebody archetypes, type-exclusive parts), its flights, and the removals, kit demands and line usage those flights cause. True failure rates stay hidden in `data/ground_truth/`.
2. **Record a history.** One event engine runs the airline for 104 weeks under the Simple Rulebook (naive reference) (`P0`). Its output looks like what a materials planner would pull from an MRO system: requests, repair orders, POs, transfers, loans, robberies and AOG events.
3. **Calibrate `P0` only, then lock.** The world was calibrated using `P0` alone and locked before any `P1`, `P2` or optimiser run. The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the model, not benchmarked against real airline KPIs. A line-kit variant (≈1,052 h) was measured but not adopted because it fell outside that range. All results are conditional on this choice.
4. **Plan from the history only.** Forecasting, float sizing, positioning and the frontier optimiser see only the history and the part master, never the truth. A static scan of the source and a runtime audit test check this.
5. **Evaluate fairly.** Every policy runs through the same engine on the same paired seeds. Parameters are frozen and hashed before the 52-week holdout runs once.
6. **Ship.** Results export to JSON and a static app on GitHub Pages. Every number on screen is read from the exported JSON, and `tests/test_reconciliation.py` recomputes the headline from `outputs/`.

Method details: [METHODOLOGY.md](METHODOLOGY.md). Model scope: [MODEL_CARD.md](MODEL_CARD.md). Verification: [reports/VALIDATION_REPORT.md](reports/VALIDATION_REPORT.md).

**Also run on a public intermittent-demand benchmark (car parts, not aviation).** The forecasting code was also run on a real public dataset. Dataset: Monash Car Parts (without missing values), 2,674 monthly series, licence CC BY 4.0, data provenance REAL (metrics DERIVED). Best eligible method IMAPA with mean MASE 1.056 [1.011–1.109]; the all-zero forecast scores 0.777, which is why zero is never allowed to be a champion. Attribution: Car Parts dataset, Monash Time Series Forecasting Archive (Godahewa, Bergmeir, Webb, Hyndman & Montero-Manso, 2021), Zenodo record 4656021, licensed CC BY 4.0; original data from Hyndman (2015), R package expsmooth.

**Tests:** 398/398 passing, 0 failing, 0 skipped (fast and slow suites, `GNM_RELEASE=1`; the Playwright browser suite runs separately; `reports/junit.xml`, run at 2026-11-27 16:37).

---

### Data provenance

| Tag | Meaning | Examples here |
|---|---|---|
| **REAL** | From a public, cited dataset | Station names and coordinates (OurAirports), the Monash Car Parts benchmark |
| **DERIVED** | Computed in this repo from other data | Demand classes, forecasts, float levels, planner exceptions |
| **ASSUMED** | A planning assumption chosen by the author, with rationale | Utilisation, MTBUR ranges, repair TAT ranges, AOG route availability, AOG cost per hour and per event, carrying cost 20%/yr |
| **SIMULATED** | Produced by the synthetic generator | Fleet, flights, removals, requests, repair orders, AOG events |

Every table and every exported JSON object carries its tag. The full list of parameters is in the [assumption register](docs/assumption_register.md); every column is in the [data dictionary](data/data_dictionary.md).

---

### Limitations

The short version: the data is synthetic; the rectification windows D3/D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions; grounded aircraft keep accruing flying exposure; the repair shop queue is light by construction; brake cost-per-landing contracts are not modelled; the AOG cost is a scenario value; the optimiser is a greedy heuristic; and every policy, the Simple Rulebook (naive reference) included, depends on the AOG recovery routes: with the routes switched off (selection seeds, a structural stress) material AOG rises from 1,727 h to 42,070 h a year under P0, from 235 h to 18,320 h under P2 and from 92 h to 11,080 h under I125. The full, specific list is in [LIMITATIONS.md](LIMITATIONS.md).

---

### Reproduce

Requires Python 3.11 or later.

```bash
git clone https://github.com/akashgajjar07-hue/grounded-no-more.git
cd grounded-no-more
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python scripts/run_all.py          # history -> forecasting -> policies -> frontier -> AOG lab -> export -> docs
python scripts/run_all.py --check  # same, then verify every frozen artefact re-derives byte-identically
pytest -m "not slow and not browser"
```

`run_all.py` reproduces the selection stage and re-exports from the committed holdout outputs. The holdout itself ran once, after `python scripts/freeze_all.py` hashed every frozen artefact into `outputs/freeze/manifest.json`; `python scripts/run_holdout.py` refuses to run if a hash differs and logs every run. `python scripts/render_docs.py` fills the numbers in these docs from `outputs/`. Seeds are fixed in `config/assumptions.yaml`, so a clean run reproduces every number.

---

### Project structure

```
config/assumptions.yaml     every parameter, with provenance and rationale (locked by the calibration)
config/part_catalogue.csv   the hand-curated 120-part catalogue (type applicability, windows, QPA)
src/gnm/
  schemas.py, contracts.py  data contract (tables, enums, in-memory objects)
  sim/                      generator (owns hidden truth) + policy-agnostic event engine
  forecasting/              demand classification, Croston family, bootstrap, reliability model
  policy/                   P0/P1/P2 parameter tables, Palm/EBO maths, paired evaluation
  optim/                    greedy marginal allocation, guardrails and the Readiness Frontier
  aog/                      AOG Response Lab options and the Planner Action Centre
  eval/                     truth recovery (the only reader of ground truth)
  export/                   JSON exports for the web app
scripts/                    build_history, run_forecasting, evaluate_policies, run_frontier, run_aog_lab,
                            freeze_all, run_holdout, export_site, render_docs, ...
data/                       processed/ (Parquet + DuckDB), ground_truth/ (hidden)
outputs/                    pipeline outputs, calibration diagnostics, freeze manifest
archive/v1/                 the archived v1 world (headline and reasons)
docs/                       static web app (GitHub Pages), method docs, templates/ for these docs
tests/                      contracts, leakage, conservation, freeze, reconciliation, site, rendered docs
reports/                    junit results, VALIDATION_REPORT.md, reviews
```

---

## Author

**Akash Gajjar**
MSc Supply Chain Management, University of Liverpool (2025).

- GitHub: [akashgajjar07-hue](https://github.com/akashgajjar07-hue)

---

## Licence

Code is released under the [MIT licence](LICENSE). Third-party components and their licences are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

This is an independent educational project. It is not an approved maintenance, airworthiness or dispatch tool.
