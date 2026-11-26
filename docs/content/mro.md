# How this transfers to an MRO

This project looks at spares from an airline's side: an aircraft waits for a part. A maintenance, repair and overhaul (MRO) shop faces the same problem from the other side. The same ideas carry over, with a few changes.

## Work-order shortages

At an MRO, the "grounded aircraft" is often an open work order that cannot close because one part is missing. The question stays the same: which missing parts hold up the most work, and how long for? The downtime measure becomes hours a work order or check is held for a part, not hours an aircraft sits waiting.

## Kit readiness

Planned checks use kits: the parts for a task, picked in advance. Kit demand is known ahead, so the useful number is the share of kits complete on the day the work starts. The forecasting and stocking logic here applies to the parts that are *not* known ahead, such as findings during a check.

## Repair induction and repair time

An MRO controls the repair loop that an airline only sees from outside. Induction (when a removed unit enters the shop), queue time and shop repair time set how many units are away at any moment. That is the removal rate × repair time idea used here. Cutting repair time can beat buying spares, and the MRO owns that lever directly.

## Customer-owned vs company-owned stock

An MRO holds two kinds of stock:

- **Customer-owned stock**: the customer's parts held on their behalf. The MRO must not use them for another customer without permission.
- **Company-owned stock**: the MRO's own pool, used for exchanges and to cover shortages across customers.

Pooling only works on company-owned stock. A transfer of this model would need ownership on every unit, and rules for when, if ever, customer stock can be borrowed.

## What would need to change

- Demand comes from work orders and customer contracts, not one airline's flying.
- Cost of a shortage comes from contract terms (turn-time commitments, penalties), not an assumed hourly rate.
- Several customers share capacity, so shop queues matter more than in this model.

See also: [What real data would make this useful](real_data.md) · [Next experiments](next_experiments.md)
