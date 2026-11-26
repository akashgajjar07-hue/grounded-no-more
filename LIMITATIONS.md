# Limitations

What this project does not do, and where its numbers would mislead if read too literally. Each item says what was simplified, why, and which way it is likely to bias the results. Numbers are computed by `scripts/render_docs.py` from `outputs/` and `docs/data/`; headline numbers are the v2 holdout (seeds 2000–2019, central world) unless labelled "selection".

---

## Data

**1. The data is synthetic.** The airline, fleet, part numbers, removals, repair orders and AOG events are generated. Only station coordinates are REAL. Every parameter is ASSUMED, chosen to be order-of-magnitude plausible, and listed in the [assumption register](docs/assumption_register.md). Results show how the methods behave under those assumptions; they are not a measurement of any airline. A v1 world was archived after a domain review; see [archive/v1](archive/v1/README.md).

**2. Simulated rates are not reliability data.** MTBUR, NFF shares, condemnation rates and repair TATs are drawn from configured ranges. They must never be quoted as measured component reliability.

**3. The models are tested on a world the author designed.** The generator draws removals from exposure ÷ MTBUR, which is exactly the structure the reliability-exposure forecast assumes. That gives it a home advantage. NFF is generated, but maintenance-induced removals and fleet campaigns are not.

**4. The vendor-quote error is assumed, and was set by the calibration.** The quoted MTBUR is truth × lognormal noise (σ_log 0.20) and 10% optimistic on average; quoted shop TAT is 5% optimistic (σ_log 0.10). These settings were the calibration lever (V2-SIM-CAL), so P0's performance, and the size of P2's improvement, depend on them.

**5. Demand is unconstrained and uncensored.** Every requirement is recorded whether or not stock existed. Real consumable issue histories are often censored by stockouts.

**6. Two years of history.** Parts with very few removals cannot be forecast from their own history; they rely on the quoted MTBUR.

## Operations

**7. No exposure feedback from groundings.** A grounded aircraft keeps accruing its scheduled flying (protection by spare aircraft or sub-charter is assumed). In reality a grounded aircraft does not fly, so removals on that tail pause. This keeps demand identical across policies for a fair paired comparison, and the lost flying is costed through the AOG cost instead.

**8. Rectification windows are simplified, not MEL.** D3 and D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions. They are elapsed-hour windows applied generically per part number. Real relief depends on the operator's approved MEL, the specific item, the redundancy remaining, and operational restrictions that this model does not cost.

**9. The legacy line-station rule is a deliberate weakness of P0.** P0 puts a rotable at an outstation only where a D0 part has at least 4 quoted removals a year at that station, so low-volume D0 rotables (the nose wheel steering actuator, wheel-and-tyre assemblies) are not held where they fail. The D0 parts below account for 54% of P0's history downtime:

| D0 part | Material AOG h/yr (P0 history, weeks 0–103) | Share at outstations | P0 outstation units | P2 outstation units |
|---|---|---|---|---|
| GN-35-E032 Crew quick-donning oxygen mask | 57 | 0% | 17 reorder-point units (min) | 13 |
| GN-32-R014 Nose wheel steering actuator (NB) | 386 | 79% | 0 units | 6 |
| GN-32-R015 Main wheel and tyre assembly (NB) | 97 | 82% | 2 units | 7 |
| GN-32-R016 Nose wheel and tyre assembly (NB) | 86 | 100% | 0 units | 5 |
| GN-32-R037 Main wheel and tyre assembly (WB) | 71 | 100% | 0 units | 6 |

Crew oxygen masks are expendables, so the line-station rule does not apply to them: P0's min/max rule holds them at every station that sees quoted demand, and 0% of the mask's history downtime was at outstations. The rule was kept on purpose (V2-SIM-16) because it is how a legacy OEM-quote operation provisions, and P2 is the remedy. A more careful legacy operator would narrow the P2 − P0 gap: the in-memory variant V3 (the calibrated quote settings plus a legacy line-station kit of 150 units; [METHODOLOGY section 6](METHODOLOGY.md#6-calibration-p0-only-and-the-lock)) gave P0 1,052 h/yr of history downtime instead of 1,282 h, at 59 events/yr (outside the band), and was not applied.

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

**20. The optimiser is a greedy heuristic on an analytic proxy.** Marginal analysis is optimal only for separable, convex objectives at its breakpoints. Check: on a small separable, convex toy case the greedy allocation equals the brute-force optimum at every greedy breakpoint (unit test `tests/test_optim_greedy.py::test_greedy_equals_brute_force_at_breakpoints`, passing); no exact comparison exists for the full, non-separable network problem. The proxy ranks candidates but is not a forecast: the analytic model predicts 2,507 h a year for P0 against 1,690 h simulated on the holdout, 130 h against 210 h for P2 and 39 h against 76 h for I125. It overstates P0 and understates the network plans, so it is a ranking heuristic, not a forecast of AOG hours; it ranks well (r = 0.97 across the 25 frontier points on the holdout, r = 0.97 on selection seeds). The guardrails are planner policy, not optimisation results; they cost +17 h [10–24] of material AOG a year at P2's capital (selection seeds).

**21. The I125 frontier option is sensitive.** Its cost lead over P2 is not significant if repair is 25% faster (+AED 0.36M [−0.75 to 1.46] a year, selection seeds). Its post-plan stress check (D015) was added after the main holdout: low stress −85 h [−125 to −45] a year and total annual cost −AED 1.7M [−2.9 to −0.4] for +AED 7.7M capital (I125 62 h vs central-built P2 147 h); high stress −184 h [−239 to −128] a year and total annual cost −AED 5.0M [−6.8 to −3.1] for +AED 7.5M capital (I125 76 h vs central-built P2 260 h).

**22. Pool exchange (P3) is not implemented.** The AOG Response Lab shows a pool option only as "not contracted".

## Evaluation

**23. Paired seeds narrow intervals within this world only.** Confidence intervals reflect simulation noise across 20 seeds, not uncertainty in the assumed parameters. Parameter uncertainty is explored only through the one-at-a-time tornado, the stress worlds and the routes-off stress. Selection to holdout: for P2 the selection-seed value of 6 of 6 headline KPIs lies inside the holdout 95% CI (material AOG 235 h on selection, 210 h [146–274] on holdout); I125 scored 92 h on selection and 76 h [50–102] on holdout (inside the CI).

**24. The stress worlds do not span the whole band.** In short, the low-stress world reaches the AOG end of the band (pooled history and selection 1,174 h/yr; band end 1,200) at 0.841 rotable fill, and the high-stress world reaches the fill end (0.781; band end 0.78) at about 1,595 h/yr, well short of the 2,700 h end, because fill binds first. A world at 2,700 h with in-band fill was not reachable by scaling true MTBUR alone.

**25. Lower immediate fill is a real cost of the lean plans.** P2 changes immediate fill by −1.25 pts [−1.42 to −1.09] against P0 (consumables P0 1.000 vs P2 0.983; expendables P0 0.949 vs P2 0.918; rotables P0 0.803 vs P2 0.898). Consumable and expendable shortages rarely cause downtime here, but they mean more chasing on the shop floor.

**26. One fleet, one network.** Results are for a 40-aircraft, seven-station network. They are not evidence about other fleet sizes or network shapes.

## Scope

**27. Not an approved maintenance, airworthiness or dispatch tool.** It does not replace an approved MEL, an MRO/ERP system, an AOG desk, or certification paperwork (such as an authorised release certificate).

**28. Independent project.** Not affiliated with any airline, OEM, vendor or MRO organisation, and uses none of their data or systems.
