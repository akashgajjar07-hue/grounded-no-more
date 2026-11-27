# How this transfers to an MRO

This project looks at spares from an airline's side: an aircraft waits for a part. A maintenance, repair and overhaul (MRO) shop faces the same problem from the other side. The same ideas carry over, with a few changes.

## Work-order shortages

At an MRO, the "grounded aircraft" is often an open work order that cannot close because one part is missing. The question stays the same: which missing parts hold up the most work, and how long for? The downtime measure becomes hours a work order or check is held for a part, not hours an aircraft sits waiting.

<!-- expert -->
Measures an MRO would track in place of aircraft downtime:

- **Work-order hold hours**: hours from the moment a task is stopped for a part until the part is issued, summed per work order or check.
- **Parts-driven share of late check release**: how much of a late release is due to parts, versus labour, tooling or findings.
- **Shortages per 100 task cards**: how often a planned task waits for a part at all.

In this project the matching measure is hours an aircraft waits for a part. Hold hours would replace it one-for-one in the scoring, with the same paired-seed comparison of plans.
<!-- /expert -->


## Kit readiness

Planned checks use kits: the parts for a task, picked in advance. Kit demand is known ahead, so the useful number is the share of kits complete on the day the work starts. The forecasting and stocking logic here applies to the parts that are *not* known ahead, such as findings during a check.

<!-- expert -->
- **Kit-completeness % at work start**: kits with every line issued ÷ kits due that day. It is all-or-nothing: one missing line makes the kit incomplete.
- **Line fill rate** (lines issued ÷ lines requested) flatters the picture, because the one missing line is often the one that holds the task.
- Routine demand is fixed once the check package is frozen. The uncertain part is non-routine findings, which behave like the intermittent demand modelled here (Croston, SBA and TSB family).
<!-- /expert -->


## Repair induction and repair time

An MRO controls the repair loop that an airline only sees from outside. Induction (when a removed unit enters the shop), queue time and shop repair time set how many units are away at any moment. That is the removal rate × repair time idea used here. Cutting repair time can beat buying spares, and the MRO owns that lever directly.

<!-- expert -->
**Turnaround time (TAT), broken down.** Total repair TAT = induction wait + queue + shop (bench) time + test + return transport. An airline sees only the total; an MRO can measure and act on each step.

**Pipeline arithmetic (illustrative, not a model output).** Expected units in repair = removal rate × repair TAT. Example: 24 removals a year × 60-day repair TAT ÷ 365 ≈ 3.9 units in repair at any time. Palm's theorem says the number in repair follows a Poisson distribution with that mean, so the spares level is read from the Poisson tail for a target availability, not from the mean alone. Cutting TAT to 45 days lowers the mean to about 3.0 units, which can remove about one spare at the same availability target.

Queue time rises steeply as shop load nears capacity, so with several customers sharing a shop, TAT is not a fixed input: it depends on load. This model takes repair time as a given input per part and does not model shop capacity.
<!-- /expert -->


## Customer-owned vs company-owned stock

An MRO holds two kinds of stock:

- **Customer-owned stock**: the customer's parts held on their behalf. The MRO must not use them for another customer without permission.
- **Company-owned stock**: the MRO's own pool, used for exchanges and to cover shortages across customers.

Pooling only works on company-owned stock. A transfer of this model would need ownership on every unit, and rules for when, if ever, customer stock can be borrowed.

<!-- expert -->
Pooling and ownership rules a transfer would need:

- Every serial number carries an owner (customer or company) and a condition (serviceable, unserviceable, in repair, quarantined).
- Pooled demand draws only on company-owned stock, or on customer stock covered by a written pooling or exchange agreement.
- **Exchange**: the customer receives a serviceable unit from the pool, and the removed unit joins the pool after repair. The exchange fee and any extra repair cost are settled under the contract.
- **Borrowing customer stock**, where allowed, needs consent, a return-by date and full traceability. The model would treat it as a separate, slower recovery route with its own cost.
- Pool size then follows the same removal rate × TAT logic, applied to the combined removal rate of all pool members.
<!-- /expert -->


## What would need to change

- Demand comes from work orders and customer contracts, not one airline's flying.
- Cost of a shortage comes from contract terms (turn-time commitments, penalties), not an assumed hourly rate.
- Several customers share capacity, so shop queues matter more than in this model.

See also: [What real data would make this useful](real_data.md) · [Next experiments](next_experiments.md)
