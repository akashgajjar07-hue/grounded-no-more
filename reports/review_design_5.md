> **AI-generated review used during development — not a review by a human aviation professional.**

> Edited for publication (v2.2): wording about the intended audience was replaced with neutral terms such as "reviewer". The findings are unchanged.

# GROUNDED NO MORE: fifth independent design critique

Reviewer stance: principal product designer at a data-visualisation studio, seeing the build cold.
Build: local `docs/` served with `python -m http.server 8851 -d docs`, Playwright Chromium, a **fresh browser context per
view**, `reduced_motion=reduce`, DPR 1, 2026-11-26.

**Health checks.** All 11 routes at all 4 viewports loaded with:
- no console errors, page errors or failed requests;
- no visible NaN, undefined, null or Infinity;
- no horizontal page scroll.

**Evidence** (all in `docs/design-review/`):
- `critic5-<view>-<1440|1024|768|390>.png` (full page) and `…-fold.png` (first screen). Views: mission, parts,
  parts-pn (`?ata=32&pn=GN-32-R014`), forecast, rotables, network (`?station=BOM`), capital, aog
  (`?incident=AOG-0001`), actions, method, about.
- `critic5-story-<1..6>-<1440|390>.png`: every story step at both viewports.
- `critic5-int-*.png`: interaction states.
  - Parts: Widebody, Narrowbody, ATA 21.
  - Part drawer.
  - Capital slider at min and after three ArrowLeft presses.
  - AOG-0086.
  - Actions: filtered, zero-result and drawer states (1440 and 390).
  - Story step 1 at 390 with the grab handle collapsed.

---

## 1. Verdict

The bones are excellent. The blueprint aircraft, the KPI instruments with P0 → P2 rulers and the readiness frontier would
all sit comfortably in a studio portfolio. So would the AOG swimlane, the Monday walkthrough and the action inbox. Every
chart carries a conclusion title and a "So what" line, and provenance is handled with real restraint.

It does **not** reach 4.5. The v2 data export left visible seams:
- **One glaring visual regression.** Every AOG option card overprints its title with a snake_case route id.
- **A functional filter bug.** The NB/WB filter does not update the systems list or the hotspot badges.
- **Contradictory numbers and labels across screens:**
  - AOG 9 h against 14 h for the same incident.
  - Method says the champion was "naive ranked 9/9"; Forecast says SBA ranked 6/9.
  - It is unclear whether P2 or I125 is "recommended".
  - Station shares are given "% of hub" on one screen and "% of CAI" on another.
- **Small chart defects.** Duplicate axis ticks, an off-scale label collision and a missing key.
- **Masonry voids.** The same layout gap (300–450 px of empty card) recurs on six screens.

**Overall average: 4.20 / 5** (round 4: 4.33). It fell because v2 introduced new regressions, mainly on AOG.
**Story mode: 4.43.**

## 2. Per-view scores (1–5)

H = hierarchy · A = alignment & spacing · T = typography · C = chart clarity · Col = colour discipline ·
DS = design-system consistency · P = polish/delight · M = responsive legibility

| View | H | A | T | C | Col | DS | P | M | **Avg** |
|---|---|---|---|---|---|---|---|---|---|
| 01 Mission Control `#/mission` | 4.5 | 4 | 4.5 | 4.5 | 4 | 4.5 | 4 | 4 | **4.25** |
| 02 Parts `#/parts` | 4.5 | 4 | 4.5 | 4 | 4.5 | 4 | 3.5 | 4 | **4.13** |
| 02 Parts deep link `?ata=32&pn=GN-32-R014` | 4.5 | 4 | 4.5 | 4 | 4.5 | 4 | 4.5 | 4.5 | **4.31** |
| 03 Forecast Lab `#/forecast` | 4.5 | 4.5 | 4.5 | 3.5 | 4.5 | 4 | 4 | 4 | **4.19** |
| 04 Rotable & Repair `#/rotables` | 4.5 | 4 | 4.5 | 4.5 | 4 | 4.5 | 4.5 | 4 | **4.31** |
| 05 Network `#/network?station=BOM` | 4.5 | 4 | 4.5 | 4 | 4 | 4 | 4.5 | 4.5 | **4.25** |
| 06 Capital Optimiser `#/capital` | 4.5 | 4 | 4.5 | 4.5 | 4.5 | 4 | 4 | 3.5 | **4.19** |
| 07 AOG Response Lab `#/aog?incident=AOG-0001` | 4.5 | 3 | 3.5 | 4 | 4.5 | 3.5 | 3 | 3.5 | **3.69** |
| 08 Planner Action Centre `#/actions` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | **4.44** |
| Data & Method `#/method` | 4.5 | 4 | 4 | 4.5 | 4.5 | 4 | 3.5 | 4 | **4.13** |
| About `#/about` | 4.5 | 4.5 | 4.5 | – | 4.5 | 4 | 3.5 | 4.5 | **4.29** |
| **Criterion average** | 4.50 | 4.05 | 4.36 | 4.20 | 4.36 | 4.09 | 3.91 | 4.09 | **4.20** |

**Story mode: 4.43.** Hierarchy 4.5, spacing 4.5, type 4.5, colour 4.5, DS 4.5, polish 4, mobile 4.5.

### What earns and costs points, per view

**Mission (4.25).**
- Earns: the hero is confident, with the exact tagline, the tour CTA and an aircraft with the urgent-part callout. The
  four KPI instruments with P0/I125/P2 rulers and 95% CIs are the best component on the site. The policy bars use
  copper P0 and teal P2 correctly.
- Costs, at 1440:
  - The right column ends ~450 px above the left. The "Aircraft systems" card is stretched with a large empty body.
  - The fill delta "−1.3 pts" is red. Red is reserved for urgent/AOG; this is a trade-off, not an alarm.
  - "2 systems rate urgent; 1 more hold an urgent part" should read "holds".
  - An amber "Watch" pill appears where the DS says amber = "Review".
- Costs, at 1024: the urgent-part callout sits on top of the aircraft's left wing and badge 36, and the tagline leaves the
  widow "it.".
- Costs, at 390: ~200 px of empty hero under the drawing, and the priorities footer wraps into a 5-line, 120 px column
  beside the link.

**Parts (4.13).**
- **Functional bug.** Switching Narrowbody/Widebody updates the headline, the side panel and the part master. It does not
  update the "Systems · list view" counts and pills, or the hotspot badges. With WB selected, the headline says "2 urgent
  of 9 PNs" while the list still says "Landing gear · 20 PNs · 6 urgent PNs" and badge 32 still shows "6".
- Drawing labels collide with linework at every width:
  - "▲_URGENT" for ATA 32 is white (ATA 27's is red) and has the leader line running along its baseline.
  - "indicative zone" is struck through by the wing trailing-edge line.
  - "34 ● OK" sits inside the teal-tinted nose-gear part of the selected zone.
  - Badge 29 overlaps the bottom of zone 32.
- "of the all fleet total" should be "of the all-fleet total".
- The header says 84 of 120 PNs, the scatter says "84 of 119" with no explanation of the missing PN.
- The left card has ~430 px of dead space under its legend.

**Parts deep link (4.31).**
- Earns: the drawer opens, takes focus, traps Tab and locks scroll. Esc closes it and returns focus to the row. Number
  keys close it and navigate (3 → Forecast).
- Costs:
  - "Peak W25" annotates only the first of two equal 3-unit peaks (W25 and ~W45).
  - The drawer button says "See in Rotable Control" while the nav says "Rotable & Repair".
  - The tags ROTABLE / INTERMITTENT / ABC A are uppercase pills. The DS says pills are sentence case.
  - Browser Back to `#/parts?ata=32` does not restore the drawer (acceptable, but noted).

**Forecast (4.19).**
- Earns: the small multiples, the leaderboard with its frozen-champion marker, the champion-check dot plot and the
  service-level histogram are clear, with good conclusion titles.
- Costs:
  - The **MTBUR chart's x-axis reads "0.0 · 0.1 · 0.1 · 0.1 · 0.1 · 0.2"**. The tick formatter rounds 0.05 steps to one
    decimal.
  - In the fill-vs-capital chart the last tick "AED 22.5M" collides with "off-scale" ("AED 22·5Moff-scale").
  - "Insufficient Data · 1 PNs" has a plural bug and Title Case where the other headings use sentence case.
  - The intermittent column uses lollipops while the other columns use bars, without a key.

**Rotables (4.31).**
- Earns: the lifecycle flow, the overdue Gantt with its chase-first list, the TAT histograms, the float calculator with
  pooled vs station view, and the lever comparison are all strong. The sliders now fill to the thumb.
- Costs:
  - In the station view, I125 is painted teal ("61%") while P2 holds the identical 2 units and 61%. Teal implies I125 is
    the recommended plan here, which contradicts Mission (see Issue 3).
  - The Gantt card has ~230 px of empty space below it.
  - The legend "Hub / Outstations" sits on the GN-27-R031 annotation in the Palm-vs-sim scatter.
  - The KPI says 121 open ROs and the lifecycle "In repair" box says 116, with no reconciling note.

**Network (4.25).**
- Earns: the map, the PS1 replay with its event timeline, and the station card with the policy table are all good.
- Costs:
  - The 1440 dumbbell chart (P0/P1/P2 by station) has **no key**. It appears only at 390. P1 (hollow) and P2 (pale
    filled) are hard to tell apart.
  - The "AUH −329 h" annotation's leader line strikes through "P2 vs P0".
  - The FRA label is crossed by the dashed teal positioning line.
  - "High" exposure rings and pills are red (red = urgent/AOG only), and the band pills are uppercase.
  - P0 is neutral grey in the hub/outstation bars, but copper everywhere else.
  - The same station metric appears as "% of hub" on Mission (CAI 56%, BOM 47%) and as "% of CAI" here (BOM 85%).
  - The right column ends ~350 px early.

**Capital (4.19).**
- Earns: the frontier with its log axis, CI band, P0 copper square and I125 callout is the signature chart. The slider has
  an excellent `aria-valuetext`: "Budget AED 56.7M: plan I125, AED 56.7M capital, 76 h AOG a year".
- Costs:
  - **At the slider minimum, budget AED 28.2M picks B015 at AED 28.4M capital.** The plan exceeds the budget the copy
    promises it "fits".
  - The raw id `P2_GUARD` appears in the paired-differences table.
  - At 390 the stacked paired-difference rows clip their metric pill at the card edge ("−134 [−181 to −…" is cut off).
  - The tornado headline cites "−AED 748k", which the AED 0–15M axis barely shows.
  - Robustness "Rule picks —" for Low and High is unexplained.
  - Two masonry gaps: under the cost card, and ~400 px under Robustness.

**AOG (3.69).**
- **Visual regression.** All 10 option cards render `.aog-key` (a badge sized for one letter, A–H) containing the full
  v2 route key (`hub_transfer`, `local_borrow`, `exchange_loan`, `repair_queue_jump`, `robbery`…). It overprints the card
  title at every viewport.
- The kicker still says "Options a–h" (lowercase) over 10 options.
- The route chart and counterfactual print snake_case ids ("hub_transfer · Transfer from AUH").
- **Numbers disagree on one incident.** The timeline title says "Released 9 h after the request" and the red bar says
  "AOG 9 h". The same timeline shows "released" at T+14 h, the header says AOG (history) 14 h, the story says "It waited
  14 h", and the recommendation says "expected material-related downtime 13 h". Exposure is AED 238k in the ranking and
  AED 253k in the counterfactual for the same route, with no ex-ante/ex-post label next to the numbers.
- An invalid `?incident=AOG-9999` silently shows AOG-0001 with no notice.
- The incident picker, arrow keys and URL sync all work well.

**Actions (4.44).** Best screen.
- Earns:
  - The queue bars filter on click.
  - Owners, severity segments and selects all filter, and the state is kept in the URL.
  - Clear works, and the drawer deep-links (`?id=EX-103-015`) at both widths.
  - CSV `planner-exceptions-W103.csv` has 63 rows and readable labels.
  - The walkthrough steps through 01→05 and disables Next at the end.
- Costs:
  - "Showing 63 of 63" while only ~16 rows render until "Show all 63 exceptions" is pressed.
  - That button touches the footnote below it (0 px gap).
  - The drawer's "capital: + AED 104,446" uses a different sign style from the site-wide "+AED".

**Method (4.13).**
- **Stale contradiction.** The freeze log says "the frozen MASE champion for intermittent rotables (naive) ranked 9/9 on
  the holdout". Forecast Lab (and `forecast.json`) say SBA, holdout rank 6/9.
- The evaluation chain truncates mid-word ("quoted_mtbur_op…", "low str…") with no expand control.
- It exposes process language ("chosen by the user's fewest-changes rule", "user request").
- Register keys break mid-word ("calendar.evaluation_week / s", "calendar.forecast_horizo / n_weeks").
- A rationale line leaks below the clipped table viewport.
- "target 60.0–100" mixes decimal styles.

**About (4.29).**
- Earns: clean and honest.
- Costs:
  - The six "Why I made these planning decisions" cards are empty dashed boxes. To a reviewer that reads as
    unfinished.
  - The eyebrow renders as "— · ABOUT".

## 3. Story mode (4.43)

Overall:
- 0 px² overlap between card and target at both viewports on all six steps.
- The spotlight frames sit below the top bar.
- At 390 the bottom sheet works and the grab handle toggles peek.
- Back is disabled on step 1, and the last step shows "Finish".
- Esc and Skip both close the tour and return focus to the tour button.
- ArrowRight and ArrowLeft both work.

Defects:
1. **Space does not play or pause in practice.** Focus lands on **Next** after every step, and the handler ignores Space
   when the target is a button. So Space activates Next: step 1 → 2 → 3, with `aria-pressed` staying `false`. The Play
   button itself works.
2. Step 1 narrates "It waited 14 h" over a timeline titled "Released 9 h after the request" with an "AOG 9 h" bar.
3. Step 6 at 390: the "I125 · frontier option" label covers the "P2" label.
4. Step 4 calls I125 "the network plan" built on P2. The spotlit card labels it "I125 · rec.", an abbreviation that
   appears nowhere else.

## 4. Functional bugs

| # | Severity | Where | Bug | Repro |
|---|---|---|---|---|
| F1 | High | AOG options | Route key overprints the option title in all 10 cards (`.aog-key` sized for one letter, now holds `hub_transfer` etc.) | `#/aog?incident=AOG-0001`, any width |
| F2 | High | Parts | Fleet filter does not update the Systems list (PN counts, urgent pills, "N urgent PNs") or the hotspot count badges | `#/parts` → Widebody |
| F3 | Medium | Story | Space advances the step instead of toggling Play, because focus sits on Next | `S` → Space |
| F4 | Medium | Capital | The slider minimum (AED 28.2M) selects B015 at AED 28.4M capital, above the budget | Focus slider → Home |
| F5 | Medium | Forecast | MTBUR x-axis ticks duplicate ("0.1" ×4) | `#/forecast`, "Fitting MTBUR" card |
| F6 | Low | Forecast | "AED 22.5M" tick overlaps "off-scale" | Fill-vs-capital chart |
| F7 | Low | Actions | "Showing 63 of 63" while the list is truncated to ~16 rows | `#/actions` initial |
| F8 | Low | Capital 390 | Stacked paired-difference metric pill clipped at the card edge | `#/capital` at 390 |
| F9 | Low | AOG | Unknown `?incident=` falls back silently, and the URL keeps the bad id | `#/aog?incident=AOG-9999` |

## 5. Cross-screen consistency

| Item | Screen A | Screen B | Fix |
|---|---|---|---|
| AOG-0001 duration | Timeline "Released 9 h" / "AOG 9 h" | Header "AOG (history) 14 h", story "waited 14 h", timeline "released T+14 h", recommendation "13 h" | Title: "Part at aircraft 9 h after request; released at 14 h". Red bar from T+0 to T+14 labelled "AOG 14 h". Say "13 h expected (ex-ante)" explicitly |
| Intermittent-rotable champion | Method: "naive ranked 9/9" | Forecast: SBA, holdout rank 6/9 | Regenerate the `method.json` freeze-log note from `forecast.json` |
| What is "recommended" | Mission: "Network positioning (P2) is the core result; I125 is an option" | Network "I125 · rec." / "I125 recommended"; Rotables teal I125; Method "Recommended frontier point is I125"; v1 table "I125 recommended"; Parts "I125 target" | Pick one vocabulary site-wide: "P2 = recommended core plan" and "I125 = frontier option (if you invest +AED 7.6M)". Teal goes on P2 only |
| Station exposure share | Mission bars "% of hub AUH" (CAI 56%, BOM 47%) | Network pills "% of CAI" (BOM 85%) | Use one denominator (share of network total) on both screens |
| Exposure for the same AOG route | Route ranking AED 238k | Counterfactual AED 253k | Label "ex-ante 238k" / "scored ex post 253k" next to the figures |
| Workspace name | Nav "Rotable & Repair" | Drawer "See in Rotable Control"; eyebrow "Rotable & Repair Control" | "Open in Rotable & Repair" |
| Option count | Kicker "Options a–h" | 10 option cards | "10 sourcing routes · 4 feasible" |
| PN universe | Header "84 of 120" | Scatter "84 of 119" | Add "(1 PN has insufficient history)" to the scatter subtitle |

## 6. Top remaining issues, ranked, with precise fixes

1. **AOG option card header overlap (F1).** Either map `o.key` back to a letter (A–J in rank order) for `.aog-key`, or
   move the key out of the header:
   - Render it as a muted mono caption under the title (`.aog-opt-code`, `--fs-12`, `--text-faint`, no box).
   - Give `.aog-opt-head` `display:grid; grid-template-columns:auto 1fr auto; gap:8px; align-items:start`.
   - Set `min-width:0` on the title.

   Also change the kicker to "10 sourcing routes · 4 feasible". Drop the `snake_id ·` prefix in the route chart and
   counterfactual (use `optLabel(o)` only).
2. **Parts fleet filter (F2).** Feed the filtered PN set into the systems list and the hotspot badges. Recompute per
   chapter: PN count, urgent-PN count, top risk, system band (share ≥ 15% / 7% of the *filtered* total) and badge number.
   Hide or dim chapters with 0 applicable PNs, and change the list kicker to "Widebody · 57 PNs". If ATA 32 is no longer
   the top system for the fleet, re-default the selection to the fleet's top system.
3. **One "recommended" vocabulary (cross-screen).**
   - Replace every "I125 recommended", "I125 · rec." and "Recommended frontier point" with "I125 · frontier option".
   - Badge P2 as "Recommended (core)" wherever plans are compared: the Network station card, the Rotables station view
     and the Method v1 table.
   - Move the teal highlight in the Rotables station view and the Network plan tiles to P2.
   - Update story step 4's copy to match.
4. **AOG-0001 duration story (cross-screen).**
   - Retitle the timeline "Part at the aircraft 9 h after the request; released to service at 14 h".
   - Draw the red AOG bar from T+0 to the "released" node and label it "AOG 14 h · grounded from removal (D0)".
   - In the recommendation, write "expected 13 h (ex-ante estimate)".
5. **Masonry voids (6 screens).** Where a 2-column row ends with a 300–450 px height difference, either:
   - set `align-items:start` on that `grid-12` row and let the shorter card end naturally, or
   - move the next short card into the gap (`grid-auto-flow: dense`, or a CSS-columns wrapper for the paired cards).

   Specific rows: Mission (map + systems), Parts (explorer + list), Rotables (Gantt + TAT), Network (map + station),
   Capital (cost + robustness), AOG (recommendation + counterfactual).
6. **Method stale/truncated text.**
   - Regenerate the freeze-log paragraph from current champions (SBA 6/9).
   - Give the evaluation-chain items a `<details>` "Full entry" toggle instead of hard truncation.
   - Replace "the user's fewest-changes rule" and "user request" with "the author's".
   - Set `overflow-wrap:anywhere` → `word-break: normal; overflow-wrap: break-word` on register keys, and break keys only
     at `.` and `_` (insert `<wbr>` after each).
   - Size the register viewport so a row is never cut mid-cell (or add a bottom fade).
7. **Chart micro-defects.**
   - MTBUR axis: format ticks with `d3.format('.2f')`, or set `ticks(4)` on a 0–0.2 domain.
   - Fill-vs-capital: drop the last tick when it is within 40 px of the "off-scale" label.
   - Network dumbbell: show the P0/P1/P2 key at every width, and make P2 a solid titanium dot (`neutral`) and P1 a hollow
     ring. Move the "AUH −329 h" annotation above the row so its leader does not cross the text.
   - Drawer demand chart: label "Peaks W25 and W45 · 3 units", or annotate the max in the selection window.
   - Parts drawing: give "URGENT" for the selected zone the red token, end leader lines at the label box edge, give zone
     labels a 3 px surface halo, and nudge "34 OK" above the zone.
8. **Colour discipline.**
   - The fill delta on Mission ("−1.3 pts vs P0") should use the neutral trade-off tone (`deltaTone:'neutral'`), as
     capital does, not red.
   - Network "high" exposure bands should use amber "review" or a neutral ring with a ▲ icon. Keep red for stations with
     an open urgent/AOG exception.
   - Hub/outstation bars: paint the P0 baseline copper, as everywhere else.
9. **Story Space key (F3).** In the story `keydown` handler, treat Space as Play/Pause even when focus is on Next/Back
   (`e.target.closest('.story-card')`). Or move initial focus to the step title (`tabindex=-1`) instead of Next.
10. **Capital slider minimum (F4).** Clamp the minimum to the cheapest plan's capital (28.4M), or select only plans with
    `capital ≤ budget` and show "No plan fits" below that. Also: replace `P2_GUARD` with "P2 guard (−1 unit)", and let
    the 390 stacked row wrap the CI below the value rather than clipping it.
11. **About empty decision cards.** Fill each with 2–3 sentences, plus a deep link to the screen that shows the evidence
    (e.g. "How TAT drives float" → `#/rotables`). If they must stay empty for now, remove the section; an empty grid looks
    unfinished. Fix the eyebrow ("ABOUT", no "— ·").
12. **Copy and DS nits.**
    - "1 more hold" → "holds"; "of the all fleet total" → "of the all-fleet total"; "1 PNs" → "1 PN"; "Insufficient Data"
      → "Insufficient data".
    - Sentence-case the band pills ("High · 85% of …") and the drawer tags.
    - Status pill label "Watch" → "Review" (or document "Watch" in the DS).
    - Add a gap above the Actions footnote after "Show all 63 exceptions" (`margin-bottom: var(--s-2)`).
    - Make the counter read "Showing 16 of 63 (expand for all)".

## 7. What would get this to ≥ 4.5

Issues 1–6 are the gate. They are the only things a reviewer would notice in a five-minute skim:
- the overprinted AOG cards;
- a filter that half-works;
- 9 h vs 14 h on the first story step;
- P2 vs I125 "recommended" changing between screens;
- empty half-cards.

Fixing those and the chart micro-defects (7) would lift AOG to ~4.4, Parts to ~4.5 and Method to ~4.4, plus about 0.25
on alignment everywhere. That puts the site average at roughly 4.45–4.5. Issues 8–12 then take it over the line.
