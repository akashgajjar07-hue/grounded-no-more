# The Planner Behind the Project

I'm Akash Gajjar. I hold an MSc in Supply Chain Management from the University of Liverpool (2025). My working background is retail inventory at Primark and Uniqlo. There I learned to care about availability, about replenishing before a gap opens, and about what an empty shelf really costs.

## Why aviation

In a shop, an empty shelf means a lost sale. In aviation, a missing part can mean an aircraft that cannot fly. I could not think of a place where one missing item has a bigger operational consequence. So I built this project to learn the problem properly.

## Decisions I made

- When a domain critique found errors in the first version, I archived v1 and its headline (a 92% cut in downtime). I rebuilt the model instead of polishing it.
- I kept the unfavourable results visible. The forecasting champions were best in only 3 of 9 groups, and the method chosen in advance ranked 6th of 9 in its own group.
- When a later review found weaknesses, I chose to disclose them instead of re-tuning the model until they went away.
- I removed the savings number from the landing page. It now sits on the results page, next to its limits.

## A mistake I made

I accepted a starting-point policy and a downtime metric before checking them with domain logic. The starting point turned out to be simpler than a competent airline would run. So the headline gap is bigger than it would be against a careful real operator. Next time I would agree the baseline and the KPI with a practitioner before building anything.

## What I learned

Repairable spares are sized by removal rate × repair time. That product tells you how many units are away being repaired at any moment, and the spares have to cover it. I also learned that buying spares isn't always the answer. Faster repair, access to a pool, or fixing an unreliable part can do more for the same money.

## How I used AI

Claude Code and other AI tools did most of the implementation. I defined the problem, directed the work, reviewed the outputs and approved the key decisions. I'm accountable for every claim in this project.

## What real data I would need

To make this useful for a real airline, I would need:

- the part master and which aircraft each part fits
- aircraft utilisation
- removal history
- stock by station
- repair orders and repair times
- supplier performance
- AOG records
- pool, loan and exchange agreements
- cannibalisation records
- stock valuations

With those, I would start with an offline back-test against real history. Then I would run it in shadow mode, next to the planners, before anyone relied on it.

Written with AI assistance from my own decisions; reviewed and edited by me.
