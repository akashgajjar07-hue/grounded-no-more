# Next experiments

These are proposed, not run. Anything built from them would be labelled **post-plan, exploratory** and kept separate from the frozen v2 results, which do not change.

## 1. P0-R: a revised reference policy

The Simple Rulebook (`P0`) is a deliberately simplified starting point. Six of its eight outstation spares are brakes, which this model only changes at the hub, and it never re-provisions over two years. A fairer reference, P0-R, would:

- hold **fleet-specific station kits**: the no-go parts each station's fleet actually needs;
- **re-provision periodically**, as a planning team would after reviewing its own removals;
- run on the **same selection seeds** as the original plans;
- involve **no re-tuning** of the Network Plan or any other policy.

The question it answers: how much of the Network Plan's lead survives against a competent reference?

## 2. Incremental donor unavailability

When a part is borrowed from another of our aircraft (cannibalisation), the donor sits waiting until it is reinstated. Those hours are disclosed but not counted in the headline. This experiment would count the *extra* donor downtime each plan causes, so the comparison includes both aircraft.

## 3. Combined disruption scenarios

The current stress worlds change one thing at a time, over a narrow range (reliability scaled ×0.96 / ×1.00 / ×1.08). Real disruptions arrive together. Combine:

- slower repair and a supplier delay;
- a reliability problem on a top part and reduced loan or exchange availability;
- higher utilisation in the peak season.

## 4. An MRO-side model

Model the same ideas from the repair shop's side. That means work orders held for parts, kit readiness, repair induction and shop queues. It also means customer-owned versus company-owned stock. See [How this transfers to an MRO](mro.md).

Back: [What real data would make this useful](real_data.md)
