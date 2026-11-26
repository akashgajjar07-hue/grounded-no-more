# v2 P0 diagnostics (diagnostic only: no band, nothing tuned or locked)

Policy: P0 (OEM-recommended provisioning on quoted data). History = weeks 0–103, seed 7. Selection = seeds [100, 101, 102, 103, 104], weeks [104, 155] (start week 78).

| Metric | History | Year 1 | Year 2 | Selection mean |
|---|---|---|---|---|
| Immediate fill (all) | 0.980 | 0.982 | 0.977 | 0.978 |
| Rotable fill | 0.588 | 0.591 | 0.584 | 0.585 |
| Expendable fill | 0.928 | 0.973 | 0.887 | 0.895 |
| Consumable fill | 1.000 | 1.000 | 1.000 | 1.000 |
| Material AOG h/yr (fleet) | 6,700.500 | 6,367.000 | 7,034.000 | 7,554.600 |
| AOG events/yr | 152.000 | 156.000 | 148.000 | 147.800 |

AOG h per aircraft-year: 167.5. P0 spare capital: AED 40,625,357 (selection mean AED 41,046,037). Consumable share of AOG hours: 0.0%.

**AOG by trigger** (per-request hours/yr, share): D0_no_stock 3,842 h (57%); deadline_expired 2,900 h (43%)

**AOG by class** (per-request hours/yr, share): R 5,748 h (85%); E 994 h (15%)

**AOG by station** (per-request hours/yr, share): AUH 4,986 h (74%); BOM 380 h (6%); JED 377 h (6%); CAI 367 h (5%); SIN 242 h (4%); FRA 230 h (3%); LHR 160 h (2%)

**AOG by archetype** (per-request hours/yr, share): widebody 3,639 h (54%); narrowbody 3,104 h (46%)

| Top AOG PN | Description | Class | Deadline | Unit cost AED | AOG h/yr |
|---|---|---|---|---|---|
| GN-32-R015 | Main wheel and tyre assembly (NB) | R | D0 | 15,574 | 958 |
| GN-32-R036 | Carbon brake assembly (WB) | R | D0 | 270,041 | 734 |
| GN-29-R034 | Electric motor pump (WB) | R | D3 | 92,085 | 568 |
| GN-32-R013 | Carbon brake assembly (NB) | R | D0 | 149,600 | 546 |
| GN-29-R035 | Engine-driven hydraulic pump (WB) | R | D3 | 126,967 | 538 |
| GN-33-E033 | Emergency light battery pack | E | D10 | 4,919 | 412 |
| GN-24-R029 | Auto-transformer rectifier unit (WB) | R | D10 | 74,569 | 405 |
| GN-27-R032 | Aileron power control unit (WB) | R | D0 | 169,624 | 403 |
| GN-32-R014 | Nose wheel steering actuator (NB) | R | D0 | 104,446 | 380 |
| GN-36-E013 | Bleed temperature sensor (NB) | E | D10 | 1,200 | 244 |

| Sourcing route | Requests | Mean wait h | Median wait h |
|---|---|---|---|
| local stock | 35,331 | 0.0 | 0.0 |
| robbery (AUH) | 233 | 43.9 | 7.0 |
| AOG exchange/loan | 167 | 74.2 | 41.0 |
| backorder -> repair return | 158 | 109.2 | 83.5 |
| AUH/network transfer | 135 | 18.9 | 11.0 |
| AOG local buy | 101 | 135.3 | 209.0 |
| backorder -> PO receipt | 41 | 137.0 | 78.0 |
| local borrow | 16 | 26.6 | 5.0 |
| unfilled at end | 2 | None | None |

Rotable fill implied by the 90–95% Poisson rule on quoted data: 0.458 (quoted station split) / 0.779 (simulated station split); simulated: 0.588. analytic = P0's own expectation from quoted MTBUR/TAT (Poisson pipeline at AUH, line-station unit at outstations); simulated reflects true rates (quotes are optimistic), queueing and variability.

