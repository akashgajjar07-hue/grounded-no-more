# v1 world: archived

Git tag: `v1-archive` (commit 06a6280). Archived on 2026-11-26 after the fresh aviation domain review (`reports/review_aviation.md`), which found 4 critical and 11 major domain-realism problems in the v1 simulator. v1 is kept for transparency, not deleted. Every v1 artefact can be recovered with `git checkout v1-archive`.

## What v1 ran
- Calibration (P0 only) locked at commit 8b7a631, before any P1/P2 code existed.
- Freeze at 95dfce5, then a single holdout at ccf6f2b on seeds 1000–1019. One block was force-rerun after it crashed before producing output (D010).

## v1 holdout headline (central world, seeds 1000–1019)
| Policy | Material AOG h/yr [95% CI] | Spare capital |
|---|---|---|
| P0 legacy (stock to pipeline mean) | 2,871 [2,459–3,282] | AED 36.8M |
| P1 local optimised | 1,626 [1,243–2,008] | AED 64.6M |
| P2 network | 533 [419–646] | AED 37.0M |
| I125 recommended | 223 [174–272] | AED 41.9M |

## Why it was superseded
- Parts were shared across the A320- and 787-family archetypes (AV-01).
- Cheap consumables were rated D0 and drove 29% of AOG (AV-02).
- An always-available 5-day outright rotable buy grew the float (AV-03).
- A straw-man P0 stocked to the pipeline mean (AV-04).
- Deadline classes contradicted MEL practice (AV-05).
- An engine artefact in deferred-item sourcing (AV-07).
- No robbery at the hub (AV-08).
- Over-allocation of cheap rotables (AV-09).
- AOG accounting (AV-10).
- A wear-driven brake was used as the hero part (AV-11).
- No local borrow at outstations (AV-15).

These problems mostly overstate P0's AOG and the size of the improvement, so the v1 numbers above should not be quoted as findings. v2 fixes these as domain corrections chosen *before* any v2 results existed. It recalibrates P0 only, locks before any P1/P2 run, and runs its holdout on fresh seeds 2000–2019, because 1000–1019 results have been seen.
