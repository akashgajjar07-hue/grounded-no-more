# What real data would make this useful

Everything in this project is simulated for a fictional airline. The method transfers; the numbers do not. To use it for real, every assumed value would need to be replaced with an operator's own records.

| Data item | Why it matters | First use |
|---|---|---|
| Part master and applicability | Which parts exist, which aircraft they fit, how many per aircraft | Set the part list and fleet coverage for the back-test |
| Aircraft utilisation (flight hours and cycles) | Removals follow flying, not the calendar | Turn removal history into removal rates per flight hour or cycle |
| Removal history | The real demand signal for repairable parts | Compare the airline's own removal rates with the vendor quotes |
| Stock by station | What is actually on the shelf, and where | Set the starting position for the back-test |
| Repair orders and repair times | Repair time × removal rate sets how many spares are needed | Measure real repair times, including transport and queues |
| Supplier performance (lead times, on-time delivery) | Late supply widens every gap | Replace quoted lead times with observed ones |
| AOG records | The outcome the project tries to reduce | Score the back-test: would the plan have prevented these? |
| Pool, loan and exchange agreements | Recovery routes the airline can really use, and their cost | Replace the assumed availability of each recovery route |
| Cannibalisation records | Borrowing a part from another of our aircraft moves downtime to the donor | Count donor downtime alongside the waiting aircraft |
| Stock valuations | Capital figures depend on real unit values | Replace the assumed part costs in the capital table |

<!-- expert -->
Data-quality checks before the back-test:

- Split removal history into confirmed failures and no-fault-found (NFF) removals. NFF removals still use a spare and shop capacity, but they say less about reliability.
- Normalise removal rates per 1,000 flight hours or per 1,000 cycles, whichever drives the part, so fleets of different sizes compare.
- Measure repair TAT from removal to serviceable on the shelf, not the shop's quoted bench time. The gap is usually transport, paperwork and queue.
- Reconcile stock records with a physical count and with condition codes (serviceable, unserviceable, quarantined).
- For slow movers with few events, pool rates across similar parts and say so, rather than fitting a rate to two or three removals.
<!-- /expert -->

## How it would be introduced

1. **Offline back-test.** Run the method on past data and compare its plan with what actually happened. No decisions depend on it.
2. **Shadow mode.** Run it alongside the planners for a few months. Planners keep deciding; the model's suggestions are logged and reviewed.
3. Only then consider using it to support real decisions, with a practitioner agreeing the baseline and the KPI first.

Next: [Next experiments](next_experiments.md)
