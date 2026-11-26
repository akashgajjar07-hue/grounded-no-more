# GROUNDED NO MORE: fourth independent design critique

Reviewer stance: principal product designer at a data-visualisation studio, seeing the build cold.
Build: local `docs/` served with `python -m http.server 8814 -d docs`, Playwright Chromium, a **fresh browser context per
view**, `reduced_motion=reduce`, DPR 1, 2026-11-26. No console errors, page errors, failed requests, visible
NaN/undefined/null, or horizontal page scroll on any view at either viewport.

**Evidence** (all in `docs/design-review/`):
- `critic4-<view>-<1440|390>.png` (full page) and `critic4-<view>-<1440|390>-fold.png` (first screen) for mission, parts,
  parts-pn (`?ata=32&pn=GN-32-R014`), forecast, rotables, network (`?station=BOM`), capital, aog (`?incident=AOG-0001`),
  actions, method.
- `critic4-story-<1..8>-<1440|390>.png`: every story step at both viewports.
- `critic4-int-*.png`: part drawer, capital slider min/max, AOG-0177 (both viewports), action filters (zero-result state),
  action drawer (both viewports), shortcuts modal.

---

## 1. Verdict

This is now a genuinely premium build. The blueprint aircraft, KPI instruments with P0 → I125 rulers, the AOG
swimlane, the readiness frontier and the action centre would all hold up in a studio portfolio. Round-3 defects are
mostly closed:
- the Network stacked table and risk pills at 390 px;
- the "No option can meet D0" banner;
- the templated parts headline;
- the float calculator now opens on Recommended (18 + 5 = 23);
- story step 8 targets the BOM row;
- "AOG h · 52 wk" headers, the register header, and the Open part / Open station drawer buttons.

It **still misses 4.5**. Three things hold it back:
1. **One real functional bug on Rotables.** All six hand-built sliders have `--pct` stuck at `50%`, so the teal fill
   never matches the thumb.
2. **Colour-discipline slips in bespoke charts.** Teal is used as a category in three places: the forward lifecycle
   flows, the "Open, inside quote" repair bars, and the tornado base line.
3. **A cluster of small polish and mobile defects.** One is a visible text-over-pill overlap on Mission at 390 px.

**Overall average: 4.33 / 5** (round 3: 4.22, round 2: 4.23, round 1: 3.61). **Story mode: 4.43** (round 3: 4.36).

## 2. Per-view scores (1–5)

H = hierarchy · A = alignment & 8-px spacing · T = typography · C = chart clarity · Col = colour discipline ·
DS = design-system consistency · P = polish/delight · M = mobile legibility

| View | H | A | T | C | Col | DS | P | M | **Avg** |
|---|---|---|---|---|---|---|---|---|---|
| 01 Mission Control `#/mission` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | **4.44** |
| 02 Parts `#/parts` | 4.5 | 4 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4 | **4.31** |
| 02 Parts deep link `?ata=32&pn=GN-32-R014` | 4.5 | 4 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | **4.38** |
| 03 Forecast Lab `#/forecast` | 4.5 | 4.5 | 4.5 | 4 | 4 | 4.5 | 4 | 4.5 | **4.31** |
| 04 Rotable & Repair `#/rotables` | 4 | 4 | 4.5 | 4 | 3.5 | 3.5 | 3.5 | 4 | **3.88** |
| 05 Network `#/network?station=BOM` | 4.5 | 4 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | 4.5 | **4.38** |
| 06 Capital Optimiser `#/capital` | 4.5 | 4 | 4.5 | 4.5 | 4 | 4.5 | 4.5 | 4.5 | **4.38** |
| 07 AOG Response Lab `#/aog?incident=AOG-0001` | 4.5 | 4 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | **4.38** |
| 08 Planner Action Centre `#/actions` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | **4.44** |
| Data & Method `#/method` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | **4.44** |
| **Criterion average** | 4.45 | 4.20 | 4.50 | 4.40 | 4.30 | 4.35 | 4.25 | 4.20 | **4.33** |

**Story mode: 4.43.** Hierarchy 4.5, spacing 4.5, type 4.5, colour 4.5, DS 4.5, polish 4.5, mobile 4.

### What earns and costs points, per view

**Mission (4.44).**
- *Earns:* the hero is excellent. The KPI rulers (P0 copper, P2 tick, I125 teal) are the best instrument idea on the site. The policy dot-whisker chart puts the I125 row in a teal band, and the copper P0 is correct.
- *Costs:*
  - **At 390 px, in the GN-49-R038 Planner-priorities row, "Outstation depletion" prints on top of the URGENT pill** (`critic4-mission-390.png`, about y 2,600).
  - GN-36-R007 still reads "FRA +5 stations … 120 h · AUH" with no qualifier. Actions adds "(no exception there)"; Mission doesn't.
  - "3 systems rate urgent; 7 more hold an urgent part" lists four rows, and the fourth (32, REVIEW) is one of the "7 more", but nothing says so.

**Parts (4.31) / deep link (4.38).**
- *Earns:*
  - the explorer headline is now templated ("ATA 32 landing gear: 11% of fleet risk-hours, 3 urgent of 15 PNs");
  - the PN banner sits on the aircraft;
  - Esc closes the drawer and restores focus to the row;
  - the drawer's own demand chart and per-station I125 allocation (7/2/1/2/2/2/2 = 18) reconcile with Rotables (18 + 5 = 23) and Actions (BOM target 2).
- *Costs:*
  - **At 1440 px the part-master table scrolls horizontally inside its card and clips the risk column, the decision column** (a "⚠ 5" pill is cut at the card edge).
  - At 390 px the scatter legend's zone swatch "[ ]" is orphaned at the end of one line, with its label wrapping to the next.

**Forecast (4.31).**
- *Earns:* the leaderboard with frozen champion, naive = 1.0 reference line and bootstrap CIs. The holdout-rank strip ("Only 2 of 8 frozen champions stayed best") is honest and readable.
- *Costs:*
  - The headline "Reliability adds 2.0 pts of fill over IMAPA for 1% more capital" names IMAPA, but **IMAPA is not labelled in the chart**: it's an anonymous open circle beside the teal point.
  - That scatter uses about 15% of its plot area: x runs to AED 24M while the points sit at 13–15M.
  - In the leaderboard, the champion (naive, white star) and the teal "Reliability-exposure · used by rotable policies" compete for "the answer". It's semantically defensible, but it needs a one-line key.

**Rotables (3.88), now the weakest view.**
- *Functional bug:* the slider track fill is decoupled from the value (§3, F1). Removals 3.5/10.5 shows 50% fill instead of 33%; "Buy N more spares" shows 50% fill with the thumb at 10%.
- *Colour:*
  - the lifecycle "Forward" flows are all teal and "Returns" are titanium, which makes teal a category;
  - in the repair-queue gantt, "Open, inside quote" bars are teal, which makes teal a status.
  - Neither is the recommended result.
- *Default state is dead:* with S = 23 the lever comparison shows "> 99.9% +0.0 pts" in both columns. The page then explains that the float is saturated, so the first thing a reader sees in the lever tool is "nothing happens".
- *Copy and values:*
  - the slider value text says "1 more spares";
  - the unit-cost slider holds 48,000 while the field shows 47,977.
- *Earns:* the new lifecycle diagram (rows labelled at lane end, count chips) is a big step up from round 3, and the station-view tiles (P0 0% / P2 79% / I125 79%) are excellent.

**Network (4.38).**
- *Earns:*
  - the 390 px table is fixed;
  - pills are now consistent (HIGH red, ELEVATED neutral info, "71% OF BOM");
  - P2 is no longer teal in the dot-whisker chart.
- *Costs:*
  - The page is still a **P0/P1/P2 story while the product recommends I125.** The BOM policy table has no I125 row, yet the tile row above it highlights "I125 rec. 7". Story step 5 also narrates P2 ("291 → 40 under P2").
  - "AOG H (HISTORY, P0) 294 h · 26 ev" sits next to the holdout "P0 291 h/yr". Two near-identical numbers mean different things (a two-year history total vs a simulated annual mean), and the first has no "/2 yr".
  - The headline "…with 42 outstation rotables, not 259" is cryptic: 259 is P1's count, and that is never said.

**Capital (4.38).**
- *Earns:* KPI capital deltas are neutral; the frontier is strong (annotation, CI band, unstable-B250 callout); the robustness table and the amber low-stress callout are exemplary honesty; mobile is clean.
- *Costs:*
  - **Tornado "base AED 5.6M" is a teal reference line**, which breaks DS rule 5.
  - The tornado headline "I125 beats P2 at every tested setting" sits next to the robustness card, which shows I125 losing AED 951k a year in the low-stress world. The two cards contradict each other unless the tornado says "every one-at-a-time setting".
  - Sign style drifts: "+AED 4.8M" in the KPIs, "AED +4.8M" in the frontier annotation and side panel, "AED +501k" in the allocation table.
  - About 140 px of dead space sits under the frontier card, because the recommendation-rule card in the right column is taller.

**AOG (4.38).**
- *Earns:* the swimlane, the red "No option can meet D0" banner with neutral "+9 h late" cells, the amber robbery card, and the roving-tabindex radiogroup picker.
- *Costs:*
  - The counterfactual table's Route row wraps both cells over 2–3 right-aligned lines, which looks broken.
  - There is dead space under the counterfactual card and in the aggregate-chart card.
  - At 390 px the exposure list prints "n/a" where desktop says "not contracted" and "infeasible", so the meaning is lost.
  - All three feasible cards repeat "Wait exceeds deadline slack".

**Actions (4.44).**
- *Earns:* functionally excellent.
  - Filters write to the URL, the zero-result state is handled, Clear works.
  - The CSV has 75 rows with human labels.
  - The drawer has Open part / Open station / Deep link, and Esc restores focus to the row.
- *Costs:*
  - Every recommended action is truncated with a literal " ..." (space + three dots), often mid-parenthesis: "(raise the station target from 0 to 1) ...".
  - The CSV summary prints "2.0x", not "×2.0".
  - At 390 px "Showing 75 of 75 · 28 urgent" wraps awkwardly against "Clear filters".

**Method (4.44).**
- *Earns:* the copper P0 dots on titanium hatched calibration bands follow the colour rules exactly; the consistency chart is fixed at 390 px; the freeze log is excellent.
- *Costs:*
  - The assumption register opens on five rows whose rationale is "—" (`meta.*`).
  - At 390 px the licence list shows bare "Version" labels with no value for five packages.

## 3. Functional bugs

| # | Severity | Where | Bug | Repro |
|---|---|---|---|---|
| F1 | **High** | `#/rotables` all 6 sliders | Track fill is fixed at 50%; it does not reflect the value. `--pct` is never set (computed `--pct: 50%` for values whose expected fill is 33.3 / 50 / 46 / 33.3 / 10 / 28.6%). The capital slider, built with `slider()`, is correct (39.4%). | Load `#/rotables`, compare thumb vs teal fill on "Buy N more spares" |
| F2 | Medium | `#/mission` @ 390 | In the GN-49-R038 Planner-priorities row the type label overlaps the URGENT pill | `critic4-mission-390.png` |
| F3 | Medium | `#/parts` @ 1440 | The part-master table overflows its card; the risk column is clipped behind an internal scroll | `critic4-parts-1440.png` |
| F4 | Low | `#/rotables` | aria-valuetext "1 more spares" (no pluralisation); unit-cost slider holds 48000 while the input shows 47,977 | read `aria-valuetext` |
| F5 | Low | `#/method` @ 390 | Empty "Version" label in stacked licence rows | `critic4-method-390.png` |
| F6 | Low | Actions CSV | Free-text `summary` contains "2.0x" (DS: ×) | `planner-exceptions-W103.csv` row 1 |
| F7 | Low | `#/capital` | Switching seed set to Selection leaves the side panel's "AOG / YR" on holdout values. The panel is always holdout, but the toggle reads as if it should change. | click Selection |

Passed:
- **Deep link and part drawer.** `#/parts?ata=32&pn=GN-32-R014` opens the drawer with focus on Close. Esc closes it, removes `pn` from the URL and returns focus to the row.
- **Row clicks.** A row click opens the drawer and updates `pn`.
- **Number keys with a drawer open.** Pressing 3 closes the drawer and goes to `#/forecast`, and Back returns.
- **Drawer button.** "See in Forecast Lab" deep-links with `class`, `part` and `pn`.
- **Capital slider.**
  - Home, End and ← all work.
  - aria-valuetext reads "Budget AED 41.9M: plan I125, AED 41.9M capital, 223 h AOG a year".
  - The accessible name is "Capital budget".
  - The side panel and chart marker update (B015 / B200).
- **AOG picker.** It is a radiogroup with roving tabindex, and AOG-0177 updates the URL and every headline.
- **Action filters and drawer.**
  - Severity, type and station combine, and the URL syncs (`?severity=urgent`).
  - A zero-result combination shows "No exceptions match these filters".
  - Clear resets everything.
  - The drawer opens by `?id=` and Esc restores focus.
- **Keyboard.**
  - 1–8 and 0 route correctly.
  - ? opens the help modal, Esc closes it, and 4 with the modal open closes it and navigates.
  - S starts the tour and → advances it.
  - Number keys are ignored inside the tour, and Esc exits it.
  - Typing "3s" in the Method search box triggers nothing.
- **Focus ring.** It is visible: a 2 px teal outline.

## 4. Cross-screen consistency

These reconcile across screens:
- **Headline results.** I125 is 223 h, AED 41.9M and 98.1% on Mission, Capital and story step 6.
- **Inbox counts.** 75 / 28 urgent on Mission, Actions and story step 8.
- **GN-32-R014 at BOM.**
  - The worst station is 63 h on Mission, the Parts drawer, Actions and story step 8.
  - The I125 target is 18 units, with 2 at BOM, on the Parts drawer, Rotables and Actions ("0 of 2").
- **BOM risk.** 17% of hub on Mission and Network.
- **Emergency hop.** 9 h on Network, AOG and the story.

Remaining inconsistencies:
1. **Recommended plan vs Network narrative.** I125 is the recommendation everywhere, but Network's headlines, BOM table and story step 5 talk only about P2.
2. **GN-36-R007.** Actions qualifies FRA/AUH 120 h with "(no exception there)"; Mission doesn't.
3. **294 vs 291.** At BOM, P0 history is 294 h with no "/2 yr", while the P0 holdout is 291 h/yr. Readers will assume one is a typo.
4. **Story step 2 says "16 AOG events (144 h)".** The number 144 h appears on no screen. The Parts drawer shows 52-week figures (230 h all stations, 63 h BOM).
5. **Capital delta sign style.** "+AED 4.8M" vs "AED +4.8M" vs "AED +501k".
6. **Not-available labels.** AOG options say "not contracted / infeasible" on desktop but "n/a" on mobile.

## 5. Story mode (4.43)

- **Desktop.** All 8 steps frame correctly under the top bar. The cards sit right, left, below or above without covering the subject. Step 8 now spotlights the GN-32-R014 · BOM row.
- **Step 2 at 390 px.** The spotlight covers the aircraft only. The "GN-32-R014 · risk 89 · URGENT" banner, which is the subject of the step, sits dimmed below it. Fix: `mobile_selector: '[data-story="aircraft"]'` wrapping the plan view plus the banner, or move the banner inside the spotlit node on mobile.
- **Step 1 at 390 px.** The peek strip still truncates: "…across 20 holdout…".
- **Step 5 copy.** It narrates P2, not the recommended I125 (see §4.1).

## 6. Top remaining issues, ranked, with precise fixes

**1. Fix the Rotables sliders (F1).** About +0.3 on Rotables P/DS.

In `rotable-repair.js`, build the six sliders with `slider()` from `ui.js`. Or, after every programmatic and `input` change, call:

```js
input.style.setProperty('--pct', ((v - min) / (max - min)) * 100 + '%')
```

Also:
- pluralise the value text (`plural(n, 'more spare')`);
- set the unit-cost slider `step` so it can hold 47,977, or snap the field to the slider.

**2. Remove teal-as-category from bespoke charts.** About +0.5 on Rotables Col, +0.5 on Capital Col.
- **Lifecycle "Forward" flows.** Use `theme.series.neutral` (titanium) for all flows, and keep teal only on the flow into the highlighted state. Or keep everything neutral and differentiate forward/return by solid vs 40% opacity.
- **Repair gantt.** Make "Open, inside quote" titanium/slate, "Past quoted due" hatched titanium, "Critical > 28 d" red.
- **Capital tornado.** The `base AED 5.6M` line must be `refLine()`: faded titanium, 4 4 dash, label in `--c-text-faint`.

**3. Give Rotables a live default for the lever tool.** About +0.3 on Rotables H/P.
- Default the lever comparison to the **station view** (BOM, 2 units), where Buy 1 spare moves 79% to roughly 95%.
- Or default S to the P0 level (10), where the levers bite.
- Keep the "saturated" sentence only when both deltas are 0.

**4. Fix the Mission 390 px overlap and the Parts table clipping (F2, F3).** About +0.25 on Mission M and Parts A/M.
- **Mission.** In the stacked priorities row, put the type label on its own line (`grid-template-areas: "pn pill" "type type"`), or truncate it with `min-width: 0; overflow: hidden; text-overflow: ellipsis` before the pill column.
- **Parts.** Set `stickyFirst: true` and move Risk to the second column, or drop "Unit cost" / "ABC" below 1500 px with `mobileColumns`-style priority, so the decision column never scrolls off at 1440.

**5. Make Network speak the recommendation.** About +0.5 on Network DS, plus story consistency.
- **BOM policy table.** Add an I125 row (teal band, "recommended") below P2. Move the P1 "lowest AOG" tag to faint text.
- **Headline.** Template it on I125 vs P0 ("I125 cuts BOM AOG from 291 h to N h a year").
- **Story step 5.** Rewrite it the same way.
- **The 259.** Rename it "…not P1's 259".
- **Station KPI.** Relabel "AOG H (HISTORY, P0)" as "AOG h · W0–W103 history (2 yr)", or show it per year ("147 h/yr"), so it can't be confused with the 291 h/yr holdout.

**6. Label what the headline names (Forecast).** About +0.5 on Forecast C.
- **Fill vs capital scatter.**
  - Direct-label IMAPA ("IMAPA · 88%").
  - Clamp the x domain to the data (`d3.extent` ± 5%).
  - Raise the plot height so the cluster isn't squeezed.
- **Leaderboard.** Add a 1-line key under the subtitle: "★ frozen champion (MASE) · teal = rate the policies use".

**7. Resolve the Capital headline contradiction and sign style.** About +0.25 on Capital C/DS.
- Tornado headline: "I125 beats P2 at every one-at-a-time setting: AED 2.4M–12.1M a year net".
- Use `fmtCapitalDelta`-style "+AED 4.8M" everywhere (annotation, side panel, allocation Δ capital).

**8. Polish the AOG detail cards.** About +0.25 on AOG A/M.
- **Counterfactual table.** Put the route in a full-width row above the numeric rows ("Route · b Emergency transfer from AUH — same in history"), left-aligned. Keep the numeric rows right-aligned.
- **Mobile exposure list.** Print the same reason as desktop ("not contracted", "infeasible").
- **Feasible cards.** Show the "Wait exceeds deadline slack" reason once, in the D0 banner, not in every card.

**9. Fix the action-text truncation.** About +0.25 on Actions P.
- Use CSS `-webkit-line-clamp: 2` on the full recommended-action string (with the full text in `title`) instead of a server-side " ..." cut. If you keep the JS cut, cut at a word boundary outside parentheses and use "…" with no leading space.
- CSV: use `fmtMult` (×2.0) in `summary`.

**10. Close the small consistency and mobile nits.** About +0.1 overall.
- **Mission.** Append "(no exception there)" to the GN-36-R007 worst-station cell. Change the Aircraft-systems header to "3 systems rate urgent; 7 more hold an urgent part (1 shown)".
- **Story.**
  - Step 2: cite a number the drawer shows (63 h at BOM in the last 52 wk), or add the 2-year BOM figure to the drawer.
  - Step 2 at 390 px: frame the PN banner.
  - Step 1: raise the peek clamp to 3 lines.
- **Method.**
  - Hide empty "Version" labels at 390 px, or print "—".
  - Sort `meta.*` rows below the rationale-bearing groups, or give them a group rationale ("site metadata").
- **Parts.** At 390 px, keep the scatter legend's zone swatch on the same line as its label (`white-space: nowrap` on each legend item).

**Expected outcome.**
- Issues 1–4 are mechanical, about half a day. They lift Rotables to about 4.35, and Mission and Parts by about 0.1 each. The average moves to about 4.42.
- Issues 5–7 close the narrative gap and should bring Network, Forecast and Capital to about 4.5. That moves the average to **about 4.5**.
- Issues 8–10 give the margin.
