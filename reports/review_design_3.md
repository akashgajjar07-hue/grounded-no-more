> **AI-generated review used during development — not a review by a human aviation professional.**

> Edited for publication (v2.2): wording about the intended audience was replaced with neutral terms such as "reviewer". The findings are unchanged.

# GROUNDED NO MORE: third independent design critique

Reviewer stance: principal product designer at a data-visualisation studio, seeing the build for the first time.
Build: local `docs/` served with `python -m http.server 8793 -d docs`, Playwright Chromium, a **fresh browser context
for every view**, `reduced_motion=reduce`, DPR 1, 2026-11-26. No view logged a console error or page error. No view
showed NaN, undefined or null, and none scrolls horizontally at 390 px.

**Evidence** (all in `docs/design-review/`):
- **Views.** `critic3-<view>-<1440|390>.png` is the full page and `critic3-<view>-<1440|390>-fold.png` is the first screen. Views covered: mission, parts, parts-pn (`?ata=32&pn=GN-32-R014`), forecast, rotables, network (`?station=BOM`), capital, aog (`?incident=AOG-0001`), actions and method.
- **Story mode.** `critic3-story-<1..8>-<1440|390>.png` covers every step at both viewports.
- **Interactions.** The `critic3-int-*.png` files record the interaction tests:
  - part drawer: closed, closed by key 3, and navigating to Forecast
  - capital slider at its minimum and maximum
  - AOG-0177 at both viewports
  - action filters, including a zero-result combination
  - action drawer at both viewports
  - help modal and focus ring

---

## 1. Verdict

This is a confident, coherent product, and the narrative is now readable end to end:
- The hero, KPI instruments, the AOG swimlane, the frontier and the action centre are portfolio-grade.
- The headline-first chart frames are used consistently on almost every chart.
- Provenance chips are everywhere.
- Keyboard behaviour is now correct across the board.

Since round 2, colour discipline has improved most. Copper vendor quotes, the teal Willemain and EU-vendor categories, and the red condemned node are all gone.

It **still does not reach 4.5**. Three kinds of problem hold it back:

1. **A visible mobile defect on Network.** In the stacked stations table at 390 px, "RISK" is set one letter per line. The risk pills are also clipped to "HIGH · TOP OUTS" and "WATCH · 71% OF", with no tooltip. This one card drags Network to 3.6.
2. **Semantic contradictions between screens.** None of these is a typo; each is a case of the same word or colour meaning two different things:
   - "Baseline" means P0 on Mission but P2 on Capital.
   - "WATCH" is an amber clock pill on Parts but a neutral info pill on Network.
   - Network paints P2 teal while I125 is the recommendation everywhere else.
   - The Rotables lever table gives its teal ✓ to a lever that costs 17× more, while Capital says buying a spare is the cheaper lever.
   - GN-36-R007 is paired with FRA beside a 120 h "worst station" figure that actually belongs to AUH.
3. **The float calculator opens on a misleading default.** It opens on P0 (S = 10) and shows **99.0 % availability**. A reviewer reads that as "the starting-point plan was already fine", which contradicts the 2,871 AOG h/yr headline.

**Overall average: 4.22 / 5** (target ≥ 4.5; round 2 scored 4.23 and round 1 scored 3.61). The colour and copy gains were offset
by the new mobile defect and by the cross-screen contradictions. **Story mode: 4.36** (round 2: 4.14).

## 2. Per-view scores (1–5)

Column key:

| Code | Criterion |
|---|---|
| H | Visual hierarchy |
| A | Alignment and 8-px spacing |
| T | Typography |
| C | Chart clarity (headline, direct labels, units, annotation, uncertainty) |
| Col | Colour discipline |
| DS | Design-system consistency |
| P | Polish and delight |
| M | Mobile legibility |

| View | H | A | T | C | Col | DS | P | M | **Avg** |
|---|---|---|---|---|---|---|---|---|---|
| 01 Mission Control `#/mission` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | **4.44** |
| 02 Parts `#/parts` | 4.5 | 4 | 4.5 | 4 | 4 | 4.5 | 4 | 4 | **4.19** |
| 02 Parts deep link `?ata=32&pn=GN-32-R014` | 4.5 | 4 | 4.5 | 4.5 | 4 | 4.5 | 4 | 4 | **4.25** |
| 03 Forecast Lab `#/forecast` | 4.5 | 4.5 | 4.5 | 4 | 4 | 4.5 | 4 | 4.5 | **4.31** |
| 04 Rotable & Repair `#/rotables` | 4 | 4 | 4.5 | 3.5 | 4 | 4 | 3.5 | 4.5 | **4.00** |
| 05 Network `#/network?station=BOM` | 4 | 3.5 | 4 | 4 | 3.5 | 3.5 | 3.5 | 3 | **3.63** |
| 06 Capital Optimiser `#/capital` | 4.5 | 4 | 4.5 | 4.5 | 4.5 | 4 | 4 | 4.5 | **4.31** |
| 07 AOG Response Lab `#/aog?incident=AOG-0001` | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | 4 | 4 | **4.31** |
| 08 Planner Action Centre `#/actions` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | **4.44** |
| Data & Method `#/method` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 3.5 | **4.31** |
| **Criterion average** | 4.40 | 4.20 | 4.45 | 4.25 | 4.15 | 4.35 | **3.95** | 4.05 | **4.22** |

**Story mode scores 4.36:** hierarchy 4.5, spacing 4.5, type 4.5, colour 4.5, DS 4.5, polish 4, mobile 4. There is no chart criterion because the step cards carry no charts.

### What earns and what costs points, per view

#### Mission (4.44)
The hero is excellent: an outlined aircraft with a pinned urgent callout, a lede with bolded numbers, and two CTAs.

What costs points:
- **KPI rulers read in two directions.** On the AOG ruler, P0 (2,871 h) sits left and I125 (223 h) right, so it reads "better → right". On the capital ruler, P0 (AED 36.8M) sits left and I125 (AED 41.9M) right, so it reads numerically. The "P2 98.0 %" label also has no tick.
- **Planner Priorities mispairs a station.** It shows "GN-36-R007 · FRA +5 stations … 120" (see C1).
- **The KPI grid is cramped at 390.** The two-column grid wraps labels onto 3 lines, puts "· 39 review" on its own line, and splits "+AED 5M / more capital".
- **The footer link wraps onto 3 lines** ("Open / Planner / Action Centre").

#### Parts (4.19)
The aircraft explorer and the systems list agree with each other.

What costs points:
- **Teal used as a category.**
  - The ABC×demand heatmap is a teal ramp.
  - The "ATA 34 parts" scatter dots are teal.
  - Risk-0 rows show a teal ✓ pill, eight times.
- **Labels collide in the explorer.** The badge labels "21 WATCH", "29 URGENT" and "36 URGENT" overlap the wing panel lines.
- **Dead space.** About 100 px is empty at the bottom of the scatter card and of the systems card.
- **Mobile stacked rows wrap badly.** They hang the description indent ("Description Connector backshell kit – / variant B").

#### Parts deep link (4.25)
The drawer is rich: a demand stem chart with the train/selection split, an annotated peak, and a by-station allocation.

What costs points:
- **The explorer card ignores the selection.** Its headline still says "ATA 34 navigation carries the most risk" while ATA 32 is selected.
- **The PN banner floats away from its hotspot.** The "GN-32-R014 · risk 89" banner renders near the tail, about 50 px below the main-gear hotspot it belongs to.
- **Drawer copy and chips.**
  - "GROUNDING RISK 248.8 AOG h / yr" is unformatted; it should read `249 h/yr`.
  - The "ROTABLE" chip is teal.
  - "STOCK (ALL STATIONS) 18 units" is really the I125 target (see C7).
- **Focus is lost on close.** Esc closes the drawer, but focus goes to `<body>`.
- **The drawer's key/value list squeezes at 390.** It stays in two columns ("32 · Landing / gear").

#### Forecast (4.31)
The leaderboard is the best chart on the site: naive scale line, starred champion, zero benchmark shown as dashed. The MTBUR recovery dumbbell is also very good.

What costs points:
- **The stock-eval scatter's headline names an unlabelled point.** "Reliability adds 2.0 pts of fill over IMAPA" is the headline, but IMAPA is not labelled in the chart.
- **The champion check uses teal as a category.** It paints "1/9 · held" teal, for two different methods.
- **Champion card precision does not match the chart.** The card says 0.848; the chart says 0.85.
- **"Needs 3 units at BOM" is never reconciled** with the 2 units the plans place there (C8).
- **The "Best eligible" label touches the IMAPA whisker.**

#### Rotables (4.00)
On mobile the lifecycle becomes labelled bars, which read better than the desktop version. The gantt is clear, and the past-due hatch is correctly neutral.

What costs points:
- **The desktop lifecycle lanes have no "from → to" labels.** The reader has to map lane starts to the six boxes; mobile has these labels.
- **The calculator default is misleading** (C9).
- **The lever table marks the costlier lever** (C6).
- **Noisy precision.** "0.000", "0.00 d", "3.492" and "35.39".
- **"Palm vs sim" uses P1 floats.** The subtitle says P1 when every other screen talks about P2 or I125.
- **The mobile repair-order Sort control reads "RO"** while the list is sorted by days past due.

#### Network (3.63)
What costs points:
- **The mobile stations table is broken** (F1).
- **The BOM policy table wraps CI ranges onto 3 lines** ("159 h–423 / h", "98.6%– / 98.9%") at 1440 as well as at 390.
- **About 360 px of empty space** sits under the map card, beside the tall BOM panel.
- **P2 is teal** (C5).
- **"WATCH" means two things across screens** (C4).
- **The routine transfer arcs are teal,** which makes teal a category on the one page where it already means two things.
- **The policy chart lacks direct labels.** Only the AUH row has them. Its "AUH −1,350 h" leader line crosses the P1 whisker.

#### Capital (4.31)
The frontier with its CI band, annotated I125, flagged B250 and copper P0 is exemplary, and capital deltas are neutral. Neutral bars with a capital column alongside, never added to cost, are also correct.

What costs points:
- **"Baseline" means P2 here** (C2).
- **Two different capital deltas** on the same page (C3).
- **Dead space.**
  - The Recommendation-rule card leaves the right column empty for about 300 px.
  - The lower-left column runs about 250 px longer than the right.
- **Rule card spacing breaks the 8-px grid.** The "Selection-seed hull …" footnote sits directly against the paragraph.
- **The cost chart uses a legend** rather than direct labels.
- **The robustness table shows a raw code.** "B125" appears with no gloss.

#### AOG (4.31)
The incident picker is a proper radio group. The swimlane timeline, the exposure bars and the counterfactual are clear.

What costs points:
- **Red "MISSED" pills on every feasible option** (4 of them) turn a structural fact into alarm noise. With 0 h of D0 slack, every option misses.
- **Teal check icons** on the "what a human must check" list are decoration.
- **Jargon.** The Scoring-basis copy reads "112 transport matrix · 49 estimate not realisable …".
- **The page is 8,000 px on mobile.** The five "Not available" cards are fully expanded.

#### Actions (4.44)
Filters, the owner bars and the bar-click filter all work and all deep-link. The empty state reads well: "No exceptions match these filters".

What costs points:
- **Pluralisation.** "1 D0 requests" (F5).
- **The CSV is raw** (F6).
- **A bare "AOG H" column header** on desktop, which the design system forbids.
- **The drawer has no cross-links.** Its only footer action is "Deep link"; it should also offer "Open part" and "Open station".
- **GN-36-R007's group header** cites a 120 h worst station that has no row in the group (C1).

#### Method (4.31)
The provenance pipeline, calibration bands, the honest "3 of 6 inside CI" chart and the disclosed forced rerun build strong credibility.

What costs points:
- **The mobile consistency chart truncates and overlaps.** KPI labels are cut ("Material AOG hours …", "Expedite spend / ye…") and value text overlaps the diamonds.
- **The page is 11,900 px on mobile.**
- **The register count omits a category.** The header says "274 entries · 242 ASSUMED, 28 REAL" and leaves out the 4 SIMULATED entries.
- **The P0 calibration dots are teal.** By §3, P0 is copper.

---

## 3. Functional bugs

| # | Severity | Where | Bug | Fix |
|---|---|---|---|---|
| F1 | **P0** | Network, Stations table at ≤ 480 px | The stacked-row metric pill is too narrow. Its `RISK` label wraps one letter per line, and the status pill inside is clipped ("HIGH · TOP OUTS", "WATCH · 71% OF") with no `title`. The audit misses it because the clip is visual (pill inside pill). | In `dataTable` stacked mode, give the metric slot `flex: 0 1 auto; max-width: 60%; white-space: nowrap`, and render a `pill` cell *without* the extra metric capsule. Or set `short: 'Risk'`, put the pill on its own line 2, and add `title` to any truncated pill. Add an audit rule that fails when any element's `getClientRects().length` exceeds 2 for a ≤ 6-character label. |
| F2 | P1 | Story step 8 at 1440 | The step card (x 16–396) overlaps the spotlit inbox (x 280+) by 116 × 282 px. It covers the "Exception inbox" title, "All 75" and "Showing …". The spotlight also covers the whole inbox, not the BOM row the copy talks about. | Use the `mobile_selector` (`[data-id="EX-103-003"]`) on desktop too, or add a `desktop_selector`. Then place the card below or right of the row. In `storyCardPosition`, reject rail positions whenever `rect.left < cardRight`. |
| F3 | P2 | Parts drawer opened from the deep link | After Esc, focus goes to `<body>` (there was no prior focus to restore). | When there is no opener, restore focus to the selected table row or the ATA hotspot. |
| F4 | P2 | Capital slider | `aria-valuetext` is excellent: "Budget AED 41.9M: plan I125, AED 41.9M capital, 223 h AOG a year". But the accessible name is "Capital budgetAED 41.9M", because the visible output sits inside `<label>`. | Move the `<output>` out of the `<label>`, or label with `aria-labelledby` pointing at the title span only. |
| F5 | P2 | Actions summary, drawer and CSV | "1 D0 requests and 14 AOG h". The CSV `recommended_action` says "Position 1 unit(s)" while the UI says "unit". | Use `plural()` in the exporter (`export_site.py`) and in the summary template. Also put a unit on "AOG transport from AUH 14" (it should read `14 h`). |
| F6 | P2 | Export CSV | The CSV has raw enums (`OUTSTATION_DEPLETION`, `LEAD_TIME_DRIFT`), lowercase severity, and a JSON blob in `evidence` that is unusable in Excel. | Add `type_label` and `severity_label` columns, flatten the key evidence into columns (`on_hand`, `target`, `aog_h_52w`, `d0_req_52w`, `ratio`, `days_late`), and keep the JSON blob as the last column. |
| F7 | P3 | Rotables repair orders at 390 | The Sort select shows "RO", but rows are ordered by days past due. | Initialise the stacked sort control from the table's actual `sort` state. |
| F8 | P3 | Parts deep link | The explorer headline does not follow `ata=`, and the PN banner is anchored about 50 px from its hotspot. | Template the headline from the selected system ("ATA 32 landing gear: 11 % of fleet risk-hours, 3 urgent of 15 PNs"). Anchor the banner with `labelAround(hotspot)`. |

**Interactions that pass:**
- **Part drawer.** Esc closes it. Keys 1–8 and 0 close it and navigate (`#/parts?…` → key 3 → `#/forecast`, no drawer, no scrim, scroll unlocked). "See in Forecast Lab" closes it and deep-links with `pn=`.
- **Help modal.** `?` opens it, Esc closes it, and `?` then `4` closes it and navigates.
- **Story mode.** S starts the tour and Esc exits.
- **Digit keys in the slider** are ignored, as they should be.
- **AOG picker.** It is a `role=radio` group, click updates `?incident=` and every headline, and it works at 390 (scroll strip).
- **Action filters.** Severity, type, station, owner, bar-click and owner-click all filter and deep-link. Zero results show a good empty state. "Clear filters" resets.
- **CSV.** It exports the filtered set with a filter-aware filename (`planner-exceptions-W103-urgent.csv`, 28 rows).
- **Focus ring.** It is a visible teal outline.

---

## 4. Cross-screen consistency audit

**Verified consistent:**
- GN-32-R014 at BOM shows 0 of 2 on hand, 7 D0 requests and 63 AOG h in the last 52 weeks. This matches on Mission, Actions, the drawer and story step 8.
- AOG-0001 is 9 h on Network, AOG and story step 7.
- BOM sits at 17 % of the hub, and the other stations at "x % of BOM". The two normalisations agree (LHR 12/17 = 71 %).
- BOM AOG falls from 291 h to 40 h under P2 (Network and story).
- ATA 32 is REVIEW with 3 urgent PNs on Mission, Parts and story.
- I125 is AED 41.9M and 223 h on Mission, Capital and story.

**Contradictions:**

| # | Item | Where it conflicts | Fix |
|---|---|---|---|
| C1 | GN-36-R007 worst-station AOG | `parts.json` gives `aog_h_52w_max_station = 120` with `_id = AUH`. Mission prints "FRA +5 stations … 120", where FRA is 56 h. The Actions group header says "max 120 AOG h at one station", but there is no AUH row. | Print the station id next to the number ("120 h · AUH"). On Mission, show the station of the *worst* row, or label the column "worst stn (any)". |
| C2 | "Baseline" | Mission: the "Baseline P0" chip and the copper P0 markers. Capital KPI footers: "Baseline AED 37M" and "Baseline AED 36.8M", which are P2's capital and P2's annual cost. | Rename the Capital footers to "P2 base AED 37M" and "P2 AED 36.8M". Reserve "baseline" for P0 site-wide. |
| C3 | I125 extra capital vs P2 | KPI and headline: "+AED 4.8M". The allocation card on the same page: "+101 units, AED 5.5M more capital". | Explain the gap in the allocation subtitle ("at unit cost; simulated capital nets out AOG-desk buys = +AED 4.8M"), or show the same basis in both places. |
| C4 | "WATCH" | Parts uses an amber clock pill: an OK system holding an urgent part. Network uses a neutral info pill: a relative station risk. | Rename one. On Network use "LOWER · 71 % of BOM" or "OUTSTATION · 71 % of BOM". Keep WATCH = amber everywhere. |
| C5 | What teal means on Network | P2 is teal in the policy dot chart and in the "60 % of P0's AOG" bars, and the I125 card is also teal. Everywhere else, teal is I125. | Make P2 neutral (titanium) and add I125 as the teal series. If I125 is not in `policy_compare`, export it, because the page's own BOM card already shows I125 = 7 units. |
| C6 | Which lever wins for GN-32-R014 | The Rotables lever table puts teal and "✓ MORE AVAILABILITY" on "Cut TAT 10 d" (+0.9 pts, AED 170k/yr), not "Buy 1 spare" (+0.6 pts, AED 10k/yr). Capital: "A spare is the cheaper lever on 28 of 32 PNs". | Highlight the lever with the lower AED per availability point (or per AOG hour) and keep "more availability" as a neutral note. |
| C7 | GN-32-R014 "Stock 18" | Parts table and drawer: "18 units". Actions: "0 of 2 on hand" at BOM. Rotables: "Recommended · 18 + 5 = 23". | Rename the Parts column and drawer field "I125 target (shelf)", and put the stock-basis note in the column tooltip. |
| C8 | BOM units for GN-32-R014 | Forecast: "needs 3 units to cover 97 % of lead times at BOM". P2 and I125 place 2 at BOM; story step 4 gives "79 % availability for the 2 units". | Add one line to the Forecast card: "Policies place 2 at BOM: the third unit's D0 penalty does not pay for its holding cost (see Capital)". |
| C9 | P0 availability | The Rotables calculator opens at S = 10 (P0) and shows **99.0 %**. Mission: P0 suffers 2,871 AOG h/yr. | Open at the I125 value, or add a callout: "Network-pooled Palm assumes any spare reaches any station instantly; the real loss is at outstations (BOM 79 % with 2 units)". Show the station-level availability beside the network figure. |
| C10 | GN-30-E025 | Parts PS4 shows a risk 0 teal ✓ pill. Mission and Actions rank it #1 URGENT (lead time 2.0×). | Add a type chip on Mission's row ("lead-time drift") and a note in the PS4 drawer: "urgent for planning data, not grounding risk". |
| C11 | Story step 2 title | "One urgent part in a review system", but ATA 32 has 3 urgent PNs. | Retitle it "An urgent part inside a review-rated system". |

---

## 5. Top remaining issues, ranked (with precise fixes)

### 1. Fix the Network mobile stations table (F1)
**Gain:** about +0.6 on Network mobile and +0.3 on polish. This is the only defect a reviewer will see within 10 seconds on a phone.

**Fix:**
- Stacked-row metric slot: `white-space: nowrap`, `max-width: 60%`.
- Do not wrap a `pill()` inside the metric capsule; render the pill alone, on line 1 or line 2.
- Give it a short label ("Risk"), and add `title` to any truncated pill.
- Add the regression audit rule described in F1.

### 2. Make each word and colour mean one thing site-wide (C2, C4, C5, C6)
**Gain:** colour discipline 4.15 → about 4.5, and DS consistency on Network and Capital +0.5.

**Fix:**
- **"Baseline" = P0 only.** Rename the Capital footers to "P2 base AED 37M" and "P2 AED 36.8M".
- **WATCH = amber review only.** Rename the Network station pills to neutral "OUTSTATION · 71 % of BOM".
- **Teal = I125 only.** On Network:
  - Recolour P2 neutral in the dot chart and the hub/out bars.
  - Add I125 as the teal row (export it in `network.json → policy_compare`).
  - Make the routine arcs titanium and let the I125 allocation carry the teal.
- **The lever table** highlights the cheaper lever per AOG hour avoided (C6).
- **Remaining teal-as-category sites:**
  - ROTABLE chip → neutral.
  - Champion-check "held" dots → neutral with a ★.
  - Parts scatter "ATA 34 parts" → ice outline, with teal kept only for the selected PN.
  - Heatmap ramp → titanium.
  - AOG checklist icons → titanium.
  - Method P0 calibration dots → copper.
- **Extend `lintTeal`** to flag teal *chips* and *icons* outside charts.

### 3. Repair the float-calculator story (C8, C9) and the story step-4 framing
**Gain:** Rotables chart clarity 3.5 → 4.5, plus story polish.

**Fix:**
- **Default.** Prefill with Recommended (18 + 5 = 23).
- **Station-level line.** Add "BOM · 2 units · 40-d loop → 79 %" so the 79 % quoted in story step 4 is actually on screen.
- **Explain the gap with one callout:** network pooling vs station reality.
- **Story step 4.**
  - Spotlight `.fc-inputs` *and* the result strip, or move the card below.
  - At 1440, the card currently covers the 99.0 % result and the top of the distribution.
  - At 390, it overlaps the "Recommended 18 + 5 = 23" chip by about 3,200 px².
- **Forecast.** Add the one-line reconciliation of 3 needed vs 2 placed.

### 4. Fix the number-to-place pairings (C1, C3, C7, C10)
**Gain:** Mission, Actions and Parts DS consistency.

**Fix:**
- **Always print the station id with "worst station" numbers.** Mission: "GN-36-R007 · worst AUH 120 h", or show the station of the row whose number is printed.
- **Capital.** Reconcile AED 4.8M vs AED 5.5M in the allocation subtitle.
- **Parts.** Rename "Stock" to "I125 target".
- **GN-30-E025.** Add a "lead-time drift" chip on Mission so a risk-0 part ranked URGENT is not puzzling.

### 5. Fix story step 8 at 1440 (F2) and the step 1 mobile peek
**Gain:** story 4.36 → about 4.6.

**Fix:**
- **Step 8 target.** Use `[data-id="EX-103-003"]` on desktop.
- **Step 8 card.** Place it right of or below the row, never over the rail when the target starts at x < 396.
- **Step 1 at 390.** The peek strip truncates the key number ("2,871 to 22…"). Lead the body with the result ("223 h a year, down from 2,871"), or raise the peek clamp to 3 lines.

### 6. Reclaim dead space and fix wrapping
**Gain:** alignment 4.20 → about 4.5.

**Fix:**
- **Network.**
  - Stack the map card and the PS1 replay in the left column so they fill the height of the BOM panel, or make the BOM panel `position: sticky`.
  - BOM policy table: put the CI on its own line in Plex Mono 12 with `white-space: nowrap` ("159–423 h", "98.6–98.9 %").
- **Capital.**
  - Move the Recommendation-rule card into the right column under "Explore the frontier".
  - Put 8 px (`--s-1`) between the rule paragraph and its footnote.
- **Parts and Forecast.** Use `align-items: start` on the paired cards, or end each card with its source line instead of padding.

### 7. Label the desktop lifecycle lanes and tame the precision
**Gain:** Rotables chart clarity and polish.

**Fix:**
- **Lifecycle lanes.** Put the mobile "Serviceable → Installed" label on each desktop lane, left-aligned at the lane start in `--c-text-faint` 12 px.
- **Lever and calculator precision.**
  - Backorders to 2 significant figures ("< 0.01").
  - Wait in hours ("< 1 h").
  - Removals to 1 decimal (3.5), TAT to whole days (35 d).
- **Drawer.** "248.8 AOG h/yr" → `fmtHours` → "249 h/yr".

### 8. Fix the parts deep link details (F3, F8)
**Gain:** about +0.25 on Parts deep link.

**Fix:**
- Template the explorer headline from the selected ATA.
- Anchor the PN banner next to its hotspot.
- Restore focus to the selected row after the drawer closes.
- Stack the drawer's key/value list at ≤ 480 px.

### 9. Tune AOG alarms and length
**Gain:** AOG colour and mobile.

**Fix:**
- **MISSED pills.** When *every* option misses (D0, 0 h slack), show one red banner ("No option can meet D0: the aircraft is AOG from removal") and render the per-card deadline cell as neutral "−9 h vs D0".
- **Mobile length.** Collapse the "Not available (5)" group into a `<details>` at ≤ 480 px.
- **Scoring basis.** Rewrite it in plain words ("112 scored on transport times · 49 not realisable · …").

### 10. Method mobile and copy nits
**Gain:** Method mobile 3.5 → 4.5.

**Fix:**
- **Consistency chart at < 480 px.** Move the value text onto its own line under each KPI label, and use full label names (`truncate` with `title` is not enough; there is room for 2 lines).
- **Register header.** "274 entries · 242 assumed · 28 real · 4 simulated".
- **Desktop Actions header.** "AOG h · 52 wk".
- **Actions drawer.** Add "Open part" and "Open station" footer buttons.
- **CSV.** Apply the F6 fixes.

**Expected outcome.**
- Issues 1–3 are about a day of focused work and should add roughly +0.6 to Network, +0.5 to Rotables and +0.15 elsewhere. That moves the average to about 4.45.
- Issues 4–6 should close the remaining gap to **≥ 4.5**.
