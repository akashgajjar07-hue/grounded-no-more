# v2 P0 diagnostics (diagnostic only: no band, nothing tuned or locked)

Policy: P0 (OEM-recommended provisioning on quoted data). History = weeks 0–103, seed 7. Selection = seeds [100, 101, 102, 103, 104], weeks [104, 155] (start week 78).

| Metric | History | Year 1 | Year 2 | Selection mean |
|---|---|---|---|---|
| Immediate fill (all) | 0.983 | 0.986 | 0.980 | 0.981 |
| Rotable fill | 0.672 | 0.690 | 0.654 | 0.668 |
| Expendable fill | 0.928 | 0.973 | 0.887 | 0.895 |
| Consumable fill | 1.000 | 1.000 | 1.000 | 1.000 |
| Material AOG h/yr (fleet) | 4,708.500 | 4,443.000 | 4,974.000 | 5,681.800 |
| AOG events/yr | 136.000 | 138.000 | 134.000 | 132.200 |

AOG h per aircraft-year: 117.7. P0 spare capital: AED 45,644,535 (selection mean AED 45,954,291). Consumable share of AOG hours: 0.0%.

**AOG by trigger** (per-request hours/yr, share): D0_no_stock 3,022 h (64%); deadline_expired 1,718 h (36%)

**AOG by class** (per-request hours/yr, share): R 3,747 h (79%); E 994 h (21%)

**AOG by station** (per-request hours/yr, share): AUH 3,270 h (69%); CAI 370 h (8%); JED 339 h (7%); BOM 322 h (7%); FRA 230 h (5%); LHR 116 h (2%); SIN 94 h (2%)

**AOG by archetype** (per-request hours/yr, share): narrowbody 2,485 h (52%); widebody 2,256 h (48%)

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

| Sourcing route | Requests | Mean wait h | Median wait h |
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

Rotable fill implied by the 90–95% Poisson rule on quoted data: 0.497 (quoted station split) / 0.852 (simulated station split); simulated: 0.672. analytic = P0's own expectation from quoted MTBUR/TAT (Poisson pipeline at AUH, line-station unit at outstations); simulated reflects true rates (quotes are optimistic), queueing and variability.

