# Limitations

What this project does not do, and where its numbers would mislead if read too literally. Each item says what was simplified, why, and which way it is likely to bias the results. Numbers are computed by `scripts/render_docs.py` from `outputs/` and `docs/data/`; headline numbers are the v2 holdout (seeds 2000–2019, central world) unless labelled "selection". Plan names: **Simple Rulebook (naive reference)** `P0`, **Each Airport for Itself (simplified local comparator)** `P1`, **Network Plan** `P2` and **Network Plan + Extra Spares** `I125`.

Every headline number is across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part. Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts.

---

## Data

**1. The data is synthetic.** The airline, fleet, part numbers, removals, repair orders and AOG events are generated. Only station coordinates are REAL. Every parameter is ASSUMED, chosen to be order-of-magnitude plausible, and listed in the [assumption register](docs/assumption_register.md). Results show how the methods behave under those assumptions; they are not a measurement of any airline. A v1 world was archived after a domain review; see [archive/v1](archive/v1/README.md).

**2. Simulated rates are not reliability data.** MTBUR, NFF shares, condemnation rates and repair TATs are drawn from configured ranges. They must never be quoted as measured component reliability.

**3. The models are tested on a world the author designed.** The generator draws removals from exposure ÷ MTBUR, which is exactly the structure the reliability-exposure forecast assumes. That gives it a home advantage. NFF is generated, but maintenance-induced removals and fleet campaigns are not.

**4. The vendor-quote error is assumed, and was set by the calibration.** The quoted MTBUR is truth × lognormal noise (σ_log 0.20) and 10% optimistic on average; quoted shop TAT is 5% optimistic (σ_log 0.10). These settings were the calibration lever (V2-SIM-CAL), so P0's performance, and the size of P2's improvement, depend on them. The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the model, not benchmarked against real airline KPIs. A line-kit variant (≈1,052 h) was measured but not adopted because it fell outside that range. All results are conditional on this choice.

**5. Demand is unconstrained and uncensored.** Every requirement is recorded whether or not stock existed. Real consumable issue histories are often censored by stockouts.

**6. Two years of history.** Parts with very few removals cannot be forecast from their own history; they rely on the quoted MTBUR.

## Operations

**7. No exposure feedback from groundings.** A grounded aircraft keeps accruing its scheduled flying (protection by spare aircraft or sub-charter is assumed). In reality a grounded aircraft does not fly, so removals on that tail pause. This keeps demand identical across policies for a fair paired comparison, and the lost flying is costed through the AOG cost instead.

**8. Rectification windows are simplified, not MEL.** D3 and D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions. They are elapsed-hour windows applied generically per part number. Real relief depends on the operator's approved MEL, the specific item, the redundancy remaining, and operational restrictions that this model does not cost.

**9. The starting-point line-station rule is a deliberate weakness of P0.** P0 puts a rotable at an outstation only where a D0 part has at least 4 quoted removals a year at that station, so low-volume D0 rotables (the nose wheel steering actuator, wheel-and-tyre assemblies) are not held where they fail. The D0 parts below account for 54% of P0's history downtime:

| D0 part | Material AOG h/yr (P0 history, weeks 0–103) | Share at outstations | P0 outstation units | P2 outstation units |
|---|---|---|---|---|
| GN-35-E032 Crew quick-donning oxygen mask | 57 | 0% | 17 reorder-point units (min) | 13 |
| GN-32-R014 Nose wheel steering actuator (NB) | 386 | 79% | 0 units | 6 |
| GN-32-R015 Main wheel and tyre assembly (NB) | 97 | 82% | 2 units | 7 |
| GN-32-R016 Nose wheel and tyre assembly (NB) | 86 | 100% | 0 units | 5 |
| GN-32-R037 Main wheel and tyre assembly (WB) | 71 | 100% | 0 units | 6 |

Crew oxygen masks are expendables, so the line-station rule does not apply to them: P0's min/max rule holds them at every station that sees quoted demand, and 0% of the mask's history downtime was at outstations. The rule was kept on purpose (V2-SIM-16) because it is how a simple OEM-quote operation provisions, and P2 is the remedy. A more careful operator would narrow the P2 − P0 gap: the in-memory variant V3 (the calibrated quote settings plus a line-station kit of 150 units; [METHODOLOGY section 6](METHODOLOGY.md#6-calibration-p0-only-and-the-lock)) gave P0 1,052 h/yr of history downtime instead of 1,282 h, at 59 events/yr (outside the band), and was not applied.

**10. Brakes: cost-per-landing contracts are not modelled.** Brakes are owned, type-specific, wear-planned rotables. Brake changes are planned at notice (5–10 days ahead); residual brake downtime only occurs when AUH is short and the exchange fails. Many operators buy brakes on a cost-per-landing contract with the supplier holding the pool, which would remove brakes from the airline's capital and from this trade-off. History downtime on the brake part numbers under P0: GN-32-R013 Carbon brake assembly (NB) 42 h/yr, GN-32-R036 Carbon brake assembly (WB) 38 h/yr.

**11. The shop queue is light by construction.** A unit occupies a bench slot for only 5% of its work time (SIM-4), so shops almost never queue. The AOG Response Lab's repair queue-jump option was infeasible for lack of a queue in 11 of the 11 rotable showcase incidents. Real shops queue, prioritise AOG cores and send beyond-economic-repair quotes; none of that is modelled, so TAT variability is understated.

**12. Close to single-echelon.** Repairs happen only through the hub. Outstations are resupplied only from AUH (laterals only where a policy allows them). There is no regional warehouse, consignment stock or supplier-held pool. The analytic positioning model is METRIC-inspired, not full METRIC.

**13. Transport times are fixed planning values.** AOG transport hours per station pair are ASSUMED constants. Real next-flight-out times vary with schedule, customs, dangerous-goods rules and weight limits.

**14. Simplified scheduled maintenance.** Only A-checks at AUH generate kits. No C-checks, no modification programmes, no airworthiness directives creating sudden fleet-wide demand.

**15. Parts are independent.** No interchangeability, no alternate part numbers, no next-higher-assembly logic, no common-cause failures.

**16. Swaps and donors are simplified.** A borrowed or robbed unit is fitted at the requirement's station, and a robbed donor is assumed not to fly until it is reinstated from the next AUH unit.

## Economics and decisions

**17. Results depend heavily on the AOG recovery routes.** Every policy, P0 included, relies on robbery at AUH (which needs engineering/quality approval), local borrow at outstations, exchange/loan by fleet type (failed attempts retried every 72 h for rotables and 24 h for consumables and expendables) and local buy for consumables and expendables. In practice this means access to an AOG exchange/loan market and to borrow agreements at the assumed availability and response times. Borrowed units never join the owned pool. Switching them off shows the dependence: with the routes switched off (selection seeds, a structural stress) material AOG rises from 1,727 h to 42,070 h a year under P0, from 235 h to 18,320 h under P2 and from 92 h to 11,080 h under I125. The frontier and the P2 − P0 gap are conditional on those markets existing.

**18. The AOG cost is a scenario.** AED 15,000/h (narrowbody) or 30,000/h (widebody), plus a fixed AED 40,000 (NB) / 100,000 (WB) per merged event are planning values. Real AOG cost depends on route, time of day, passenger load, crew legality and recovery options. P2's lead over P0 holds across ×0.5–×2 the hourly rate, but the frontier pick moves: on the selection seeds I125's net annual benefit over P2 is +AED 1.7M [0.7–2.7] at hourly penalty ×0.5 and +AED 8.0M [4.6–11.5] at ×2, against +AED 3.8M at ×1, and the rule's pick moves to I110 at ×0.5 and B150 at ×2 the hourly rate.

**19. Carrying cost is a single rate.** 20% per year (range 15–25%) covers capital cost, storage, insurance and obsolescence together.

**20. The optimiser is a greedy heuristic on an analytic proxy.** Marginal analysis gives the best allocation only for separable, convex objectives at its breakpoints. Check: on a small separable, convex toy case the greedy allocation equals the brute-force optimum at every greedy breakpoint (unit test `tests/test_optim_greedy.py::test_greedy_equals_brute_force_at_breakpoints`, passing); no exact comparison exists for the full, non-separable network problem. The proxy ranks candidates but is not a forecast: the analytic model predicts 2,507 h a year for P0 against 1,690 h simulated on the holdout, 130 h against 210 h for P2 and 39 h against 76 h for I125. It overstates P0 and understates the network plans, so it is a ranking heuristic, not a forecast of AOG hours; it ranks well (r = 0.97 across the 25 frontier points on the holdout, r = 0.97 on selection seeds). The guardrails are planner policy, not optimisation results; they cost +17 h [10–24] of material AOG a year at P2's capital (selection seeds).

**21. The I125 frontier option is sensitive.** Its cost lead over P2 is not significant if repair is 25% faster (+AED 0.36M [−0.75 to 1.46] a year, selection seeds). Its post-plan stress check (D015) was added after the main holdout: low stress −85 h [−125 to −45] a year and total annual cost −AED 1.7M [−2.9 to −0.4] for +AED 7.7M capital (I125 62 h vs central-built P2 147 h); high stress −184 h [−239 to −128] a year and total annual cost −AED 5.0M [−6.8 to −3.1] for +AED 7.5M capital (I125 76 h vs central-built P2 260 h).

**22. Pool exchange (P3) is not implemented.** The AOG Response Lab shows a pool option only as "not contracted".

## Evaluation

**23. Paired seeds narrow intervals within this world only.** Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or contracts. Confidence intervals reflect simulation noise across 20 seeds, not uncertainty in the assumed parameters. Parameter uncertainty is explored only through the one-at-a-time tornado, the stress worlds and the routes-off stress. Selection to holdout: for P2 the selection-seed value of 6 of 6 headline KPIs lies inside the holdout 95% CI (material AOG 235 h on selection, 210 h [146–274] on holdout); I125 scored 92 h on selection and 76 h [50–102] on holdout (inside the CI).

**24. The stress worlds are narrow and do not span the whole band.** They use reliability scaled ×0.96 / ×1.00 / ×1.08 — a narrow range. In short, the low-stress world reaches the AOG end of the band (pooled history and selection 1,174 h/yr; band end 1,200) at 0.841 rotable fill, and the high-stress world reaches the fill end (0.781; band end 0.78) at about 1,595 h/yr, well short of the 2,700 h end, because fill binds first. A world at 2,700 h with in-band fill was not reachable by scaling true MTBUR alone.

**25. Lower immediate fill is a real cost of the lean plans.** P2 changes immediate fill by −1.25 pts [−1.42 to −1.09] against P0 (consumables P0 1.000 vs P2 0.983; expendables P0 0.949 vs P2 0.918; rotables P0 0.803 vs P2 0.898). Consumable and expendable shortages rarely cause downtime here, but they mean more chasing on the shop floor.

**26. One fleet, one network.** Results are for a 40-aircraft, seven-station network. They are not evidence about other fleet sizes or network shapes.

## Scope

**27. Not an approved maintenance, airworthiness or dispatch tool.** It does not replace an approved MEL, an MRO/ERP system, an AOG desk, or certification paperwork (such as an authorised release certificate).

**28. Independent project.** Not affiliated with any airline, OEM, vendor or MRO organisation, and uses none of their data or systems.

## Known model limitations from the v2 domain review (disclosed, not fixed)

A fresh aviation domain review of v2 (`reports/review_aviation_v2.md`) found the model-level issues below. By the author's decision they are disclosed rather than fixed, because each fix would need another rebuild, recalibration and holdout. The wording and UI issues from the same review were fixed.

**29. Robbed-donor downtime is not counted (AV2-01).** A robbed donor aircraft is assumed not to fly until it is reinstated, but those hours are not counted as material AOG. In the P0 history there are about 28 robberies a year, donors are held for 8 days on average, and the donor hours come to about 5,285 a year, against 1,282 counted material AOG hours. 82% of robberies are for D3/D10 items. Absolute downtime is therefore understated for every policy. P0 robs more often than P2, so the P2-vs-P0 gap is probably understated too, but the absolute levels should not be quoted as fleet downtime.

**30. P0's outstation stock is mostly unusable (AV2-02).** 6 of P0's 8 outstation rotables are wear-planned brakes, and every brake change is done at AUH, so only the rest can ever be used at a line station. P0 holds no nose-wheel or widebody wheel assemblies at outstations and never re-provisions over the two years. Most of P0's downtime comes from no-go actuators and wheels at line stations, so the P2-vs-P0 headline largely measures "stock no-go items at line stations". A P0 with a standard line kit was measured during calibration but not adopted (only the fewest-changes variant met the band); it would narrow the gap.

**31. Wheels and tyres are modelled as rare unscheduled removals (AV2-04).** In reality they are the highest-volume rotable, and most changes are wear-planned.

**32. Some brake positioning comes from a station-share prior (AV2-05).** P2 and I125 place a few brakes at outstations where no brake change ever happens, which is dead stock. Outstation brake allocations in the frozen plans are flagged as an **invalid recommendation — brakes are not changed outside the hub in this model**: 5 in the Network Plan `P2` (GN-32-R013 at BOM, GN-32-R013 at CAI, GN-32-R013 at JED, GN-32-R036 at LHR, GN-32-R036 at SIN), 7 in the Network Plan + Extra Spares `I125` and 6 in the Simple Rulebook (naive reference) `P0`. They stay in the frozen results so the numbers are unchanged, but no planner should act on them.

**33. The hero part's removal rate is high, and there is no warranty or reliability escalation (AV2-06).** A real planner would escalate a part removed this often to reliability and warranty before buying more spares. The product now says so: "Removing 2.3× faster than quoted → escalate to reliability engineering and warranty review first. Extra spares are interim cover, compared against faster repair or pool access."

**34. Robbery is the engine's automatic first route at AUH, at a flat availability (AV2-07).** In practice robbery is a case-by-case engineering decision and would often follow an exchange or loan. The AOG Response Lab never ranks robbery, but the simulated policies use it.

**35. Deferral has no cost of its own (AV2-08).** Flying with a D3/D10 item deferred costs nothing until the window expires, so the optimiser can cut expensive deferrable floats more readily than an operator would.

**36. AOG hours run from removal, not from the next scheduled departure (AV2-09).** The downtime clock starts when the part is removed (for no-go items; for deferrable items, when the rectification window runs out), not at the next scheduled departure, and overnight and other non-flying hours count in full. Fitting and release-to-service time is included. A departure-based count would be lower for every plan.

**37. Exchange and loan are one route, and there is no pool or component-support contract (AV2-12).** A widebody operator would usually have a pool or support agreement that changes the widebody sourcing picture.

**38. Unit costs are drawn per part family, not per aircraft type (AV2-13).** Several are well off typical list prices, so absolute capital figures, including I125's extra investment, are illustrative. Comparisons within the model are consistent, but the AED amounts are not price estimates.

**39. Other simplifications the reviewer noted.** Some removal rates are high, local buy of windshields is very fast, IDG/VFSG repair is in-house, outstations are assumed to have fitting capability, robbery at AUH is not used to supply outstations, and P1 is a deliberately simple comparator. See the review for details.

**40. Outstation wheels (A9).** Wheel-and-tyre assemblies are modelled as rare, unscheduled no-go removals (AV2-04), so the frozen plans hold 2 wheel assemblies at outstations under the Simple Rulebook (naive reference) `P0` (none on the nose wheel or the widebody), 18 under the Network Plan `P2` and 12 under the Network Plan + Extra Spares `I125`. A real operator holds wheels at every station and changes most of them on planned tread wear, so these counts follow from the modelling assumption and are not a wheel-sizing recommendation. Most of the gap between the Simple Rulebook (naive reference) and the Network Plan at outstations comes from no-go actuators and wheels.

**41. Donor downtime is kept out of the headline.** Hours that donor aircraft (aircraft that gave up a part to another) spend waiting for a replacement are not reconstructible from current logs for the frozen test runs, so no per-plan figure is given. What the logs do allow (post-plan, exploratory): parts borrowed from another of our aircraft per year in the test runs, Simple Rulebook (naive reference) `P0` 33.2 [28.5–37.9]; Each Airport for Itself (simplified local comparator) `P1` 31.3 [27.1–35.4]; Network Plan `P2` 22.5 [18.4–26.6]; for the Network Plan + Extra Spares `I125` this is not reconstructible either. For scale only, in the historical record of the Simple Rulebook (naive reference) `P0` (history weeks 0–103, one simulated history, not the test runs), donor aircraft were held about 5,285 h a year, beside 1,282 h a year of counted waiting-for-part downtime in that same history. Gross donor hours are an upper bound: a donor may already be in maintenance or not scheduled to fly.

## v2 domain review findings and status

Every finding in [`reports/review_aviation_v2.md`](reports/review_aviation_v2.md), with its status for the v2.1 release. **Fixed** means the wording, labels or screens were corrected; no frozen number changed. **Disclosed** means the model keeps the simplification and this document says so. **Next experiment** means it needs a new, separately labelled run (see below); the frozen holdout is not re-run.

| ID | Severity | Finding, in short | Status | Where it is handled |
|---|---|---|---|---|
| AV2-01 | critical | Robbed donor aircraft downtime is not counted | Disclosed; next experiment | Item 29, item 41, README "What I found"; incremental donor unavailability below |
| AV2-02 | critical | The Simple Rulebook (naive reference) fails where no real line-station list would (brakes at outstations, no re-provisioning) | Disclosed; next experiment | Display name "Simple Rulebook (naive reference)", item 30; P0-R below |
| AV2-03 | critical | "Positioning the existing float" and the net capital alone misstate what the Network Plan does | Fixed | Capital table (bought, removed, net) on Results, Frontier and README |
| AV2-04 | major | Wheels and tyres modelled as rare unscheduled removals | Disclosed | Items 31 and 40 |
| AV2-05 | major | Outstation brakes in the Network Plan and Extra Spares plans | Disclosed (flagged invalid) | Item 32: lines flagged "invalid recommendation", kept in the frozen results |
| AV2-06 | major | Hero part removal rate implausible; no reliability or warranty escalation | Fixed (wording); disclosed (rate) | Item 33; escalation wording on the hero-part screens |
| AV2-07 | major | Robbery is the automatic first route at the hub at a flat availability | Disclosed; next experiment | Item 34; combined disruption scenarios below |
| AV2-08 | major | Deferral has no cost of its own | Disclosed | Item 35 |
| AV2-09 | major | AOG clock starts at removal and counts overnight hours and fitting | Disclosed | Item 36; the clock is stated wherever downtime is defined |
| AV2-10 | major | Stale v1 text in the v2 app | Fixed | Site copy |
| AV2-11 | major | Calibration range has no external anchor and was chosen after the diagnosis | Fixed (wording) | Item 4, METHODOLOGY section 6, VALIDATION_REPORT section 2 |
| AV2-12 | major | Exchange and loan modelled as one route; no pool or support contract | Disclosed | Items 22 and 37 |
| AV2-13 | major | Unit costs drawn per family, not per aircraft type | Disclosed | Item 38 |
| AV2-14 | major | Station view sized an outstation on the repair loop instead of hub resupply | Fixed | Rotable & Repair screen |
| AV2-15 | minor | Several removal rates high for mature parts | Disclosed | Items 2 and 39 |
| AV2-16 | minor | High-value expendables can be bought locally, fast | Disclosed | Item 39 |
| AV2-17 | minor | Some component repairs in-house; light shop queue; long brake TAT | Disclosed; next experiment | Items 11 and 39; MRO-side model below |
| AV2-18 | minor | Outstations assumed able to fit any part | Disclosed | Item 39 |
| AV2-19 | minor | Hub robbery never supplies an outstation | Disclosed | Item 39 |
| AV2-20 | minor | A few common part numbers implausible across both archetypes; one wheel missing | Disclosed | Item 39 |
| AV2-21 | minor | Mixed wording on rectification windows vs MEL | Fixed | One sentence used everywhere (item 8) |
| AV2-22 | minor | Contradictory one-line summaries on the network screens | Fixed | Site copy |
| AV2-23 | minor | Headline scope read as fleet-wide | Fixed | Scope line beside every headline number |
| AV2-24 | minor | P1 sizes the hub on hub-local demand | Fixed (label); disclosed | Display name "Each Airport for Itself (simplified local comparator)", item 39 |
| AV2-25 | minor | Low hub floor at low-budget frontier points | Disclosed | Stated here: low-budget frontier points below a sign-off floor are illustrative only |

## Next experiments

None of these changes the frozen v2 results. Each would be a new run, labelled "post-plan, exploratory", reported beside the frozen holdout and never mixed with it.

1. **P0-R, a revised reference.** Fleet-specific station kits (no brakes outside the hub, nose and main wheels at every station that sees the fleet), periodic re-provisioning from observed removals, the same selection seeds, and no re-tuning of anything else. This measures how much of the gap to the Network Plan survives a competent starting point.
2. **Incremental donor unavailability.** Count the hours a robbed donor aircraft actually waits for its reinstatement part, per plan, so the headline can show waiting-for-part downtime with and without donors.
3. **Combined disruption scenarios.** Routes partly unavailable, slower repair and lower reliability at the same time, instead of one factor at a time.
4. **An MRO-side model.** Shop capacity, queues, AOG-priority induction, vendor repair routes and beyond-economic-repair quotes, so repair time becomes a lever that can be bought rather than a fixed input.
