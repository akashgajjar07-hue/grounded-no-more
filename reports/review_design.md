# GROUNDED NO MORE: independent design critique

Reviewer stance: principal product designer, data-visualisation studio. Fresh eyes, no prior context.
Build reviewed: local `docs/` served on :8765 (same build as GitHub Pages), Chromium via Playwright,
`reduced_motion=reduce`, DPR 1. Date 2026-11-26.

Evidence (all in `docs/design-review/`):
`critic-<view>-1440.png` / `critic-<view>-390.png` for mission, parts, parts-pn, forecast, rotables,
network, capital, aog, actions and method; `critic-mission-fold-1440.png` / `-390.png` (above the fold);
`critic-story-{1,2,3}-1440.png` / `-390.png` (story mode); `critic-bug-drawer-persists-1440.png`
(state-leak bug, issue 1).

Each view was shot in a fresh tab. Shooting them in one tab exposed the drawer bug in issue 1: the
parts drawer stayed open over Forecast and Rotables.

---

## 1. Verdict

This is a serious, well-engineered piece of work with a real point of view. The hero, the provenance
system and the headline-first chart frames are better than most commercial analytics products. It
does **not** reach the 4.5 bar yet. Three themes hold it back:

1. **Overlapping annotations and labels in the charts.** Labels sit on top of their own markers in
   at least six charts, and some values are clamped to the axis edge with no marker.
2. **The colour semantics leak.** Copper, red and amber are each used for two or three different
   meanings.
3. **Prose replaces structure on the operational screens.** The action inbox, the planner priorities
   and the AOG option cards make the reader parse sentences where they should scan columns.

Mobile is the weakest dimension (3.25). Tables hide the decision column behind a horizontal scroll.

**Overall average: 3.61 / 5** (target ≥ 4.5).

## 2. Per-screen scores (1–5)

| Screen | Hierarchy | Align/8-px | Type | Chart clarity | Colour discipline | DS consistency | Polish | Mobile | **Avg** |
|---|---|---|---|---|---|---|---|---|---|
| 01 Mission Control `#/mission` | 4.5 | 4 | 4 | 4 | 3.5 | 4 | 4 | 4 | **4.00** |
| 02 Parts `#/parts` | 4 | 3.5 | 3.5 | 3.5 | 4 | 4 | 4 | 3 | **3.69** |
| 02 Parts deep link `?ata=32&pn=GN-32-R014` | 4 | 3.5 | 3.5 | 3.5 | 4 | 3.5 | 3.5 | 3 | **3.56** |
| 03 Forecast Lab `#/forecast` | 3.5 | 4 | 3.5 | 3.5 | 3.5 | 4 | 3.5 | 3.5 | **3.62** |
| 04 Rotable & Repair `#/rotables` | 3 | 3.5 | 3.5 | 3.5 | 3 | 3.5 | 4 | 3 | **3.38** |
| 05 Network `#/network?station=BOM` | 3.5 | 3.5 | 4 | 3 | 3.5 | 4 | 3.5 | 3 | **3.50** |
| 06 Capital Optimiser `#/capital` | 4 | 3.5 | 4 | 4 | 3.5 | 4 | 4 | 3 | **3.75** |
| 07 AOG Response Lab `#/aog?incident=AOG-0001` | 3.5 | 4 | 3.5 | 3 | 3.5 | 3.5 | 3.5 | 3.5 | **3.50** |
| 08 Planner Action Centre `#/actions` | 3 | 4 | 3.5 | 4 | 3.5 | 4 | 3 | 3.5 | **3.56** |
| Data & Method `#/method` | 3.5 | 3.5 | 3.5 | 3.5 | 3.5 | 4 | 3.5 | 3 | **3.50** |
| **Criterion average** | 3.65 | 3.70 | 3.65 | 3.55 | 3.55 | 3.85 | 3.65 | **3.25** | **3.61** |

Story mode is scored separately because it has no charts: hierarchy 4, spacing 3.5, type 4,
colour 4, DS consistency 4, polish 3, mobile 3, giving **3.64**.

## 3. Cross-cutting judgements

**First 10 seconds (Mission, 1440 fold).** This is strong, at 4.5. The "GROUNDED / NO MORE" lockup,
the teal plan-view aircraft with a single red ATA 32 hotspot and an URGENT callout, a lede that states
the result with numbers, and four KPI instruments all land above the fold. Three things weaken it:
- The rail brand block repeats the H1 word for word, at 4 type sizes in a 70 px stack.
- The red "+AED 5M vs P0" in the Spare Capital KPI reads as an alarm.
- The URGENT callout butts against the aircraft nose: its right edge sits about 16 px from the
  ATA 34 bubble.

**Blueprint illustrations.** The plan view is credible and original. Its centreline, dashed hidden
equipment, nacelles and numbered ATA balloons read as an engineering drawing, not clip art. The
exploded schematics are weaker:
- Each one is the same three generic isometric boxes plus a disc, whatever the system.
- The callout text renders at about 6–7 px, illegible at 1440 and worse at 390.
- The hottest part (for example GN-34-R012, risk 85) gets no visual emphasis in the drawing.

**Density vs clarity.** Desktop density is appropriate for the expert audience. Text density is not:
- Chart subtitles routinely run to 3–5 lines of mono text ("Node = serviceable units (recommended
  plan) · ring = projected risk = P0 holdout AOG h/yr ÷ worst station (no per-station holdout
  breakdown exists…").
- Headlines run to 3–4 lines in narrow columns (Rotables "EU VENDOR turns units in 67 d…",
  Network "P2 takes AUH AOG from 1,721 h…").
- A headline should be one finding in ≤ 90 characters. Qualifications belong in the subtitle or the
  footnote.

**Consistency across screens.** This is the best-scoring criterion (3.85). Page heads, eyebrow
numbering, card chrome, provenance chips and the "Source / View data" footer are consistent. The
deviations:
- **Section dividers.** Some screens use stand-alone H2 dividers with a rule and a chip ("Method
  leaderboard", "From forecast to stock", "Validation"); others put every block inside cards.
- **Chip placement.** At 1440 the provenance chip sits top-right of each card. At 390 it drops to its
  own line under the subtitle, adding 32 px per card.
- **KPI tiles.** Mission's "Open planner actions" tile has no ruler or CI, so its footer does not line
  up with its three siblings.
- **Week labels.** The header says "SIM · W104–155", Actions says "Week 103", and the AOG timeline
  uses real dates (2023-01-11 11:00).

**Story mode.** The concept is excellent and the copy is good. The execution:
- Step 2 spotlights a tall narrow slice of the aircraft that cuts through both wings. The highlighted
  ATA 32 balloon is amber "REVIEW", while the narration and the Mission hero call this part URGENT.
- Step 3's card covers the Intermittent and Insufficient Data columns, which are the point of the
  step.
- At 390, step 1's card covers the aircraft, and step 3's card covers about 45% of the viewport.

---

## 4. Top 10 issues (ranked by impact)

### 1. A deep-linked drawer survives route changes, freezing the next screen (all screens; P0 bug)
- **Where:** the drawer opened by `#/parts?ata=32&pn=GN-32-R014`, then any hash change: browser
  Back/Forward, `location.hash`, or an in-app `ctx.navigate` that bypasses the drawer.
- **What's wrong:** the `.drawer.is-open` and `.scrim.is-open` elements stay mounted. They covered
  Forecast and Rotables in my first pass and blocked the "Start the story" click on Mission (Playwright:
  "scrim intercepts pointer events"). Reproduced: open the deep link, set `location.hash='#/forecast'`,
  and `.scrim.is-open` count is still 1. Number-key shortcuts are swallowed while it is open.
- **Why it matters:** a hiring manager who uses Back lands on a dimmed, unclickable page. It is the
  single most damaging thing a reviewer can hit.
- **Fix:** in the router's `render` path, call `closeAllOverlays()` (drawer, modal, tooltip.hide) before
  the outgoing view's cleanup. Have `drawer()` register itself in a module-level `Set` that the router
  clears. Also have each view's cleanup return close its own drawer. Add a Playwright test: open the
  deep link, navigate to `#/forecast`, and assert `document.querySelectorAll('.scrim.is-open').length === 0`.

### 2. Chart labels collide with their own markers and data (Parts, Forecast, Network, Rotables, Capital)
- **Where:**
  - Parts ADI×CV² scatter: the "top risk in ATA 34" annotation is struck through by a point, and
    "SMOOTH 40" and "INTERMITTENT 72" overlap data.
  - Forecast stock-eval: "Reliability-exposure" is drawn on top of its own dot, and "Moving average"
    overlaps a ring.
  - Forecast LTD bars at 390: "1.1% chance of a shortfall" overlaps the bars.
  - Network map: "LOW · 7 u" for BOM and SIN sits on the arcs, and AUH collides with its sub-label
    at 390.
  - Network policy-compare at 390: the "AUH" row label overlaps the "AUH −1,350 h" annotation.
  - Rotables lifecycle: the flow values "39" and "174" sit on crossing copper arcs.
  - Capital cost components at 390: "AED 86M" overlaps the bar end.
- **Why it matters:** this breaks the "direct labels, one annotation" rule and is the clearest
  signal of an unfinished viz.
- **Fix:** run every direct label through `dodge()` against both other labels **and** marker bboxes.
  Offset labels by `r + 6px` from the mark centre on the side away from the data centroid. Give
  quadrant labels (SMOOTH/INTERMITTENT/ERRATIC/LUMPY) `paint-order: stroke; stroke: var(--c-card);
  stroke-width: 4px` and pin them to the plot corners, inset by 8 px. On the lifecycle, put the arc
  value chips at the arc apex with a `--c-card` filled `rect` behind them (padding 2×6).

### 3. Colour semantics are overloaded: copper, red and amber each carry 2–3 meanings (system-wide)
- **Where:**
  - **Copper** marks capital/SIMULATED (chip), but also the baseline P0, "returns" flows on the
    Rotables lifecycle, the EU VENDOR series, the AOG-penalty bar (Capital), the AOG 9 h bar (AOG
    timeline), "Emergency" arcs (Network), the calibration target bands (Method) and the
    selection-seed diamonds (Method).
  - **Red** marks urgent, but also a capital *increase* in the KPIs ("+AED 4.8M", "+AED 5M").
  - **Amber** marks review/ASSUMED, but also every reference line ("naive scale = 1.0", CV² 0.49,
    ADI 1.32, "sim = Palm", "on quote").
- **Why it matters:** a chart with teal series, a copper baseline, an amber reference line and red
  status has four accents, against a rule of two. Red capital deltas read as a warning on the
  recommended plan.
- **Fix:**
  - Reserve copper for *capital and baseline*.
  - Draw reference lines in `--c-titanium` at 50% opacity with a 4 4 dash, labelled in `--c-text-faint`.
  - Draw the Rotables "returns" arcs in titanium/slate at 40% opacity.
  - Show KPI capital deltas in neutral titanium with an arrow and the word "more capital", with no red.
  - Use a hatch or an outline for the calibration target bands, not a copper fill.
  - Document the mapping in DESIGN_SYSTEM §3 rule 5 as a table: accent → meaning → never.

### 4. Mobile tables hide the decision column (Parts, Network, Capital, Method at 390)
- **Where:** at 390 the Part master shows only PART NUMBER and a truncated DESCRIPTION, so RISK,
  the sort key, is off-screen. The Network stations table hides STOCK VALUE and PROJECTED RISK. The
  Capital allocation table shows PN / STATION / CLASS, with CHANGE, Δ CAPITAL and AOG AVOIDED hidden.
- **Why it matters:** mobile legibility is the lowest criterion (3.25). On a phone the tables show
  identifiers and no insight.
- **Fix:** add `mobileColumns: ['pn','risk','stock']` (a per-table priority list) to `dataTable`. At
  < 480 px render rows as two-line stacked cells: PN in mono on line 1, the key metric right-aligned in
  a pill, and secondary fields on line 2 in `t-12` faint. Make PN `position: sticky; left: 0` with a
  `--c-card` background and a right hairline shadow.

### 5. The Action Centre and Planner Priorities are walls of near-identical sentences (Actions, Mission)
- **Where:** each inbox row is a 2-line sentence: "GN-32-R014 at BOM: 0 serviceable (+0 inbound) vs
  target 2 (demand-implied protection level); 7 D0 requests and 63 AOG h in 52 weeks". 12 red URGENT
  rows in a row, and 6 of them are the same PN at different stations. The Mission priorities card
  repeats the pattern at 140 px per row.
- **Why it matters:** an inbox is for scanning. The numbers that decide priority (gap, AOG h, D0
  requests) are buried mid-sentence, and the uniform red left border plus pill becomes noise.
- **Fix:**
  - Restructure each row as a grid:
    `grid-template-columns: 96px minmax(180px,1.2fr) repeat(3, 88px) minmax(220px,1.5fr) 72px`.
    The columns are severity pill · PN + station (mono) · On hand / Target · AOG h/52w · D0 req ·
    recommended action (one line, ellipsis) · Due.
  - Group rows with the same PN under a collapsible PN header ("GN-32-R014 · 6 stations · 63 AOG h max").
  - Keep the red left border only on the group header.
  - Use a short title template, "{station}: 0 of {target} on hand", and move the long rationale into
    the drawer.

### 6. The AOG timeline chart is degenerate and the option cards expose machine codes (AOG)
- **Where:**
  - "Released 9 h after the request": the 1,100 px axis puts 7 of 9 events in a "01–07" cluster chip
    at +0 h, then empty space to +9 h. The table below repeats it verbatim.
  - The option cards print raw enum codes as UI copy (`STOCK_AT_HUB`, `EXCEEDS_DEADLINE`,
    `DOES_NOT_BEAT_ALTERNATIVES`, `HUMAN_DECISION_REQUIRED`).
  - The cards are ordered b, f, h, d, a, c, e, g.
  - The RECOMMENDED card shows a red "MISSED" deadline pill with no explanation next to it.
- **Why it matters:** the AOG Lab is the most narratively powerful screen, and here it reads like a
  debug dump.
- **Fix:**
  - Replace the axis with a two-lane swimlane, "Desk decisions (T+0)" and "Physical movement
    (T+0 → T+9 h)". Or drop the chart and keep the table, adding a 4 px progress rail in the left
    gutter of each row scaled to T+.
  - Map the enum codes to sentence-case labels ("Stock at hub", "Exceeds deadline slack") and keep
    the code in a `title` attribute.
  - Sort cards as feasible by rank, then not contracted, infeasible and human decision. Group them
    under sub-headers "Feasible (3)" and "Not available (5)".
  - Next to MISSED on the recommended card, add "9 h AOG unavoidable: no option meets D0" in `t-12`.

### 7. Validation charts clamp out-of-range values to the axis edge without saying so (Method)
- **Where:** in "3 of 6 selection-seed results fall inside the holdout 95% CI", the copper diamonds
  for Material AOG, Total annual cost and AOG events all sit at the far-left end of their rows. "Each
  row on its own scale" is clamping values that fall outside the CI-padded domain.
- **Why it matters:** clamped values with no indicator undermine the screen whose job is credibility.
- **Fix:** make each row's domain `[min(lo, sel) , max(hi, sel)]` padded by 10%. If clamping stays,
  draw a left-pointing chevron `‹` with the true value ("118 h ‹") in `--c-text-faint`. Add a shared
  "within CI ✓ / outside ✕" column header so ✓/✕ is not the only signal.

### 8. Headlines and subtitles are too long, and narrow cards wrap them to 4–5 lines (Rotables, Network, Forecast, Parts)
- **Where:**
  - Network policy-compare headline: 3 clauses and 6 numbers.
  - Rotables TAT card headline: 4 lines.
  - Parts scatter headline: "72 of 118 classified PNs average at least 1.32 weeks between demands:
    intermittent or lumpy".
  - Network map subtitle: 5 mono lines.
- **Why it matters:** the headline is meant to be the takeaway at a glance. Mono subtitles at 14 px
  in 5 lines push the chart below the fold of the card and slow reading.
- **Fix:**
  - Cap headlines at 90 characters and one finding, for example "Most PNs demand rarely: 72 of 118
    are intermittent or lumpy". Move secondary numbers into an annotation.
  - Cap subtitles at 2 lines with `display:-webkit-box; -webkit-line-clamp:2` and an "i" disclosure
    for the rest.
  - Set subtitles in Inter `t-12`, not Plex Mono. Mono is for codes and ticks, per the DS.
  - Add a lint to `chartFrame()` that `console.warn`s when `headline.length > 90`.

### 9. Network map nodes vs labels: detached "LOW · 8 u" tags read as extra stations (Network)
- **Where:** each station has its IATA ring plus a separate grey dot and a "LOW · 8 u" label about
  40–90 px away (LHR, FRA, CAI, JED). The ring encodes risk with a teal/amber/red outline, a second
  chip row under the map repeats the same data, and the legend combines four encodings in one line.
- **Why it matters:** the grey bullets look like more airports. The map is the flagship geographic
  view and currently needs a legend to decode.
- **Fix:**
  - Drop the detached bullets. Render the sub-label directly under the IATA code (`dy: 14`, `t-12`
    faint, no dot), and run it through `dodge()`.
  - Size the ring by serviceable units and use outline style plus icon for risk, as already specified.
  - Remove the chip row (the station table below already serves selection), or turn it into the map's
    keyboard-accessible selector, visually hidden until focus.
  - Hide the inset locator at < 900 px card width, because it currently collides with SIN.

### 10. Story mode spotlight and card placement occlude the content being narrated (Story, both viewports)
- **Where:**
  - Step 2 crops a narrow rectangle through the aircraft. The highlighted ATA 32 shows amber
    "REVIEW" while the text says "risk score 89/100", and the hero says URGENT.
  - Step 3's card covers the Intermittent and Insufficient columns of the spotlit chart.
  - At 390, step 1's card covers the aircraft, and step 3's card covers about 45% of the viewport.
- **Why it matters:** story mode is the hiring-manager path. A spotlight that hides its subject, or
  contradicts the status shown, costs trust in the first minute.
- **Fix:**
  - Place the card with a collision solver: try right, left, below, then above the target rect, and
    pick the first that does not intersect it with 16 px clearance. On mobile, pin the card to the
    bottom as a sheet (`max-height: 40vh`) and `scrollIntoView({block:'start'})` the target with a
    `56px + 16px` top offset.
  - For step 2, spotlight the whole aircraft card, and add a part-level badge "GN-32-R014 · risk 89 ·
    URGENT" next to the ATA 32 balloon so the status matches the narration.
  - Reconcile "16 D0 requests at BOM" (story, 2-year history) with "7 D0 requests in 52 weeks"
    (inbox) by stating the window in both places.

---

## 5. Smaller issues

- **Capital:** the allocation table's scroll container clips a half row ("GN-31-R038") and its
  footnote touches the table border with 0 px gap. Add `margin-top: var(--s-2)` and a bottom fade
  mask. The KPI row shows "223 h" twice ("vs P2", "vs P0"). Merge them into one tile with two deltas.
- **Mission:** the "Recommended · I125 / P2 + greedy additions (I…" row label is truncated at 1440,
  where there is room. Allow 2 lines or widen the label column to 220 px.
- **Mission rail:** the brand lockup is in 4 sizes and fonts. Use one mono line "Falcon Hub Airways
  (fictional)" under the mark.
- **Parts exploded view:** set label text to a minimum of 11 px on screen. Scale via
  `vector-effect`/`font-size` in CSS, not the SVG viewBox. Outline the highest-risk part in red with a
  risk callout.
- **Parts heatmap at 390:** the column headers collide ("ERRATICINTERMITT INSUFF."). Use abbreviations
  S/E/I/ID with a key, or rotate the headers 45°.
- **Capital at 390:** the four KPI tiles stack into about 940 px of mostly empty card. Use a 2×2 grid
  with `min-height: auto`.
- **Method:** the assumption register repeats an identical 6-line rationale on consecutive rows. Group
  rows by shared rationale (rowspan, or "same as above ↑").
- **Method:** the flow node "Exports → this si…" is truncated. Allow wrapping.
- **Actions:** the native `<select>` controls (Type, Station, Owner) use OS chrome. Style them with
  `appearance:none`, an 8 px radius, the DS chevron icon and a `--c-hairline` border.
- **Actions:** the stacked severity bars have no legend for amber or slate. Add direct labels ("12
  urgent · 21 review").
- **Ghost link alignment:** "Open action centre" sits 15 px right of the primary button's left edge
  when stacked at 390. Remove the ghost button's left padding when it wraps.

## 6. Path to ≥ 4.5

Issues 1–4 alone would lift the average by about 0.4:
1. Fix the overlay bug.
2. Run a label-collision pass.
3. Apply the colour-semantics table.
4. Implement mobile priority columns.

Issues 5–6 and 8 restructure the operational screens and add about another 0.3. Issues 7, 9 and 10,
plus the smaller list, are the polish needed to clear 4.5.
