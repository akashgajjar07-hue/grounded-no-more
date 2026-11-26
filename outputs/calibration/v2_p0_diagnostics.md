# v2 P0 diagnostics (diagnostic only: no band, nothing tuned or locked)

Policy: P0 (OEM-recommended provisioning on quoted data). History = weeks 0–103, seed 7. Selection = seeds [100, 101, 102, 103, 104], weeks [104, 155] (start week 78).

| Metric | History | Year 1 | Year 2 | Selection mean |
|---|---|---|---|---|
| Immediate fill (all) | 0.984 | 0.986 | 0.981 | 0.981 |
| Rotable fill (network) | 0.678 | 0.690 | 0.667 | 0.673 |
| Rotable fill (hub pool, AUH demand) | 0.760 | 0.772 | 0.748 | 0.750 |
| Expendable fill | 0.928 | 0.973 | 0.887 | 0.896 |
| Consumable fill | 1.000 | 1.000 | 1.000 | 1.000 |
| Material AOG h/yr (fleet) | 1,712.000 | 1,699.000 | 1,725.000 | 1,907.200 |
| AOG events/yr | 97.000 | 90.000 | 104.000 | 90.400 |

AOG h per aircraft-year: 42.8. P0 spare capital: AED 44,918,087 (selection mean AED 45,234,597). Consumable share of AOG hours: 0.0%.

**AOG by trigger** (per-request hours/yr, share): D0_no_stock 1,621 h (95%); deadline_expired 91 h (5%)

**AOG by class** (per-request hours/yr, share): R 1,625 h (95%); E 87 h (5%)

**AOG by station** (per-request hours/yr, share): AUH 542 h (32%); BOM 306 h (18%); JED 292 h (17%); CAI 283 h (17%); LHR 116 h (7%); SIN 94 h (5%); FRA 80 h (5%)

**AOG by archetype** (per-request hours/yr, share): narrowbody 1,132 h (66%); widebody 580 h (34%)

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

| Sourcing route | Requests | Mean wait h | Median wait h |
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

Rotable fill implied by the 90–95% Poisson rule on quoted data: 0.497 (quoted station split) / 0.852 (simulated station split); simulated: 0.678. analytic = P0's own expectation from quoted MTBUR/TAT (Poisson pipeline at AUH, line-station unit at outstations); simulated reflects true rates (quotes are optimistic), queueing and variability.

