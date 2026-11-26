# Donor-hours recount (v2.1, workstream B)

**Post-plan exploratory recount. Gross donor hours are an upper bound — a donor may already be in maintenance or not scheduled to fly.**

Post-processing of existing outputs only. No policy, simulation or optimiser was re-run. Decision V21-B.

## Holdout robbery counts per year (seeds 2000–2019, central, 95% CI over 20 seeds)

| Policy | Robberies / yr | 95% CI |
|---|---|---|
| P0 | 33.2 | 28.5–37.9 |
| P1 | 31.2 | 27.1–35.4 |
| P2 | 22.4 | 18.4–26.5 |
| I125 | not reconstructible from current logs | |

| Paired difference | Mean | 95% paired-t CI |
|---|---|---|
| P2-P0 | -10.8 | -15.1 to -6.4 |
| P1-P0 | -1.9 | -6.1 to 2.2 |
| I125-P2 | not reconstructible from current logs | |

Requests in the 52-week KPI window whose AOG route was a robbery at AUH (a count per year). Robbery is used only for AUH needs in the engine.

## Holdout donor hours

Gross donor-grounded hours, combined hours and their paired differences: **not reconstructible from current logs**. The holdout runs stored aggregate KPIs only; donor robbed / reinstated times were not logged. Recomputing them needs a new simulation, which v2.1 does not run.

Recipient hours (= the frozen material AOG hours, unchanged): P0 1,690 h, P1 566 h, P2 210 h, I125 76 h.

## HISTORICAL P0 (history weeks 0–103; not holdout, never mixed with it)

* Robberies: 56 on 29 donor tails (28.0 a year); 1 still open at the end of history.
* Average donor held 8.0 days (max 29.7); 82% of robberies were for D3/D10 items.
* Gross donor hours: **5,285 h/yr** (sum of (reinstated_h - robbed_h) over the reinstated robberies / 2 years (LIMITATIONS 29)).
* Per-tail union (overlaps counted once): 5,094 h/yr.
* Counted material AOG (historical P0): **1,282 h/yr**.

_Post-plan exploratory recount. Gross donor hours are an upper bound — a donor may already be in maintenance or not scheduled to fly._
