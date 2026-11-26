# IN-MEMORY ESTIMATE (not applied): raw P0 after A + quote/AOG-market settings

Policy: P0 (OEM-recommended provisioning on quoted data). History = weeks 0–103, seed 7. Selection = seeds [100, 101, 102, 103, 104], weeks [104, 155] (start week 78).

| Metric | History | Year 1 | Year 2 | Selection mean |
|---|---|---|---|---|
| Immediate fill (all) | 0.990 | 0.992 | 0.989 | 0.990 |
| Rotable fill (network) | 0.814 | 0.822 | 0.806 | 0.808 |
| Rotable fill (hub pool, AUH demand) | 0.895 | 0.903 | 0.888 | 0.889 |
| Expendable fill | 0.957 | 0.980 | 0.936 | 0.953 |
| Consumable fill | 1.000 | 1.000 | 1.000 | 1.000 |
| Material AOG h/yr (fleet) | 1,137.500 | 1,019.000 | 1,256.000 | 1,264.600 |
| AOG events/yr | 72.000 | 61.000 | 83.000 | 70.600 |

AOG h per aircraft-year: 28.4. P0 spare capital: AED 48,282,781 (selection mean AED 48,469,176). Consumable share of AOG hours: 0.0%.

**AOG by trigger** (per-request hours/yr, share): D0_no_stock 1,106 h (97%); deadline_expired 32 h (3%)

**AOG by class** (per-request hours/yr, share): R 1,080 h (95%); E 57 h (5%)

**AOG by station** (per-request hours/yr, share): CAI 264 h (23%); AUH 222 h (20%); JED 194 h (17%); BOM 192 h (17%); LHR 116 h (10%); SIN 94 h (8%); FRA 57 h (5%)

**AOG by archetype** (per-request hours/yr, share): narrowbody 762 h (67%); widebody 375 h (33%)

| Top AOG PN | Description | Class | Deadline | Removal mode | Unit cost AED | AOG h/yr |
|---|---|---|---|---|---|---|
| GN-32-R014 | Nose wheel steering actuator (NB) | R | D0 | unscheduled | 104,446 | 340 |
| GN-27-R032 | Aileron power control unit (WB) | R | D0 | unscheduled | 169,624 | 121 |
| GN-27-R006 | Elevator servo control (NB) | R | D0 | unscheduled | 138,105 | 102 |
| GN-27-R007 | Aileron servo control (NB) | R | D0 | unscheduled | 196,170 | 102 |
| GN-27-R031 | Elevator power control unit (WB) | R | D0 | unscheduled | 231,228 | 100 |
| GN-32-R015 | Main wheel and tyre assembly (NB) | R | D0 | unscheduled | 15,574 | 90 |
| GN-32-R016 | Nose wheel and tyre assembly (NB) | R | D0 | unscheduled | 21,664 | 86 |
| GN-32-R037 | Main wheel and tyre assembly (WB) | R | D0 | unscheduled | 20,357 | 71 |
| GN-35-E032 | Crew quick-donning oxygen mask | E | D0 | unscheduled | 11,307 | 57 |
| GN-32-R036 | Carbon brake assembly (WB) | R | D0 | wear_planned | 270,041 | 38 |

| Sourcing route | Requests | Mean wait h | Median wait h |
|---|---|---|---|
| local stock | 35,779 | 0.0 | 0.0 |
| AUH/network transfer | 141 | 22.0 | 11.0 |
| AOG local buy | 69 | 131.6 | 209.0 |
| robbery (AUH) | 62 | 57.4 | 19.0 |
| AOG exchange/loan | 55 | 54.7 | 25.0 |
| backorder -> repair return | 55 | 68.5 | 69.0 |
| backorder -> PO receipt | 15 | 62.8 | 60.0 |
| local borrow | 7 | 33.0 | 6.0 |
| unfilled at end | 1 | None | None |

Rotable fill implied by the 90–95% Poisson rule on quoted data: 0.524 (quoted station split) / 0.860 (simulated station split); simulated: 0.814. analytic = P0's own expectation from quoted MTBUR/TAT (Poisson pipeline at AUH, line-station unit at outstations); simulated reflects true rates (quotes are optimistic), queueing and variability.

