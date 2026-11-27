> **AI-generated review used during development — not a review by a human aviation professional.**

> Edited for publication (v2.2): wording about the intended audience was replaced with neutral terms such as "reviewer". The findings are unchanged.

# GROUNDED NO MORE: second independent design critique

Reviewer stance: principal product designer at a data-visualisation studio, seeing the build for the first time.
Build: local `docs/` served with `python -m http.server 8792 -d docs`, Chromium via Playwright, a **fresh browser
context for every view**, `reduced_motion=reduce`, DPR 1. Date 2026-11-26. No console errors or page errors appeared on
any view, and no view scrolls horizontally at 390 px.

**Evidence** (all in `docs/design-review/`):
- `critic2-<view>-<1440|390>.png` is the full page and `critic2-<view>-<1440|390>-fold.png` is the first screen, for mission, parts,
  parts-pn (`?ata=32&pn=GN-32-R014`), forecast, rotables, network (`?station=BOM`), capital, aog
  (`?incident=AOG-0001`), actions and method.
- `critic2-story-<1..8>-<1440|390>.png` covers every story step.
- `critic2-int-*.png` records the interaction tests: drawer then navigation, capital slider (min, max, chart), AOG-0177, action filters and
  drawer (both viewports), help modal, focus ring and the parts drawer at 390.

---

## 1. Verdict

The previous round fixed the big problems: label collisions, the drawer leaking across routes, prose inboxes and
tables hiding their decision column on mobile. This is now a confident, coherent product. The hero, the provenance chips,
the headline-first chart frames, the AOG swimlane and the action centre are portfolio-grade. It **still falls short of
4.5**. What remains is no longer layout. It is **semantic and editorial discipline**:

1. **Accent meanings still leak, roughly 10 times across 6 screens.** Teal is used as a category or "best" marker,
   copper for vendor quotes, red for condemned or merely late, and amber for a deadline class.
2. **Numbers and labels contradict each other across screens.** The same part shows 230 h on one screen and 63 h on
   another. One rotable shows S = 10/21/23 in one place and 5/16/18 in another. ATA 32 is URGENT on the hero but REVIEW on
   Parts. A chapter shows an OK pill next to "2 urgent".
3. **Copy and templating defects** an expert reader will notice: "(AUH)" printed twice, "option(s)", raw enums,
   `h 200` axis ticks, the placeholder social link, and a footnote clipped at 390 px.
4. **Story mode frames its own subject badly.** At 1440, headlines slide under the sticky bar. At 390, the bottom
   sheet covers the inputs or table the step is talking about.

**Overall average: 4.23 / 5** (target ≥ 4.5; previous review 3.61). **Story mode: 4.14.**

## 2. Per-view scores (1–5)

H = visual hierarchy · A = alignment & 8-px spacing · T = typography · C = chart clarity · Col = colour discipline ·
DS = design-system consistency · P = polish/delight · M = mobile legibility.

| View | H | A | T | C | Col | DS | P | M | **Avg** |
|---|---|---|---|---|---|---|---|---|---|
| 01 Mission Control `#/mission` | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | 4.5 | 4 | **4.38** |
| 02 Parts `#/parts` | 4.5 | 4 | 4.5 | 4 | 4 | 4.5 | 4 | 3.5 | **4.12** |
| 02 Parts deep link `?ata=32&pn=GN-32-R014` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | **4.44** |
| 03 Forecast Lab `#/forecast` | 4 | 4.5 | 4 | 4.5 | 3.5 | 4 | 4 | 4.5 | **4.12** |
| 04 Rotable & Repair `#/rotables` | 4 | 4 | 4.5 | 3.5 | 3.5 | 4 | 4 | 4 | **3.94** |
| 05 Network `#/network?station=BOM` | 4.5 | 4 | 4 | 4 | 4 | 4.5 | 4 | 4 | **4.12** |
| 06 Capital Optimiser `#/capital` | 4.5 | 4 | 4.5 | 4.5 | 4 | 4.5 | 4.5 | 4.5 | **4.38** |
| 07 AOG Response Lab `#/aog?incident=AOG-0001` | 4.5 | 4.5 | 4 | 4.5 | 4 | 4.5 | 3.5 | 4 | **4.19** |
| 08 Planner Action Centre `#/actions` | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4.5 | 4 | 4.5 | **4.44** |
| Data & Method `#/method` | 4.5 | 4 | 4.5 | 4.5 | 4.5 | 4.5 | 3.5 | 3.5 | **4.19** |
| **Criterion average** | 4.40 | 4.25 | 4.35 | 4.30 | **4.05** | 4.40 | **4.00** | 4.10 | **4.23** |

**Story mode** scores 4.14: hierarchy 4.5, spacing 4, type 4.5, colour 4.5, DS 4.5, polish 3.5, mobile 3.5. There is no chart
criterion because the step cards carry no charts.

The weakest criteria are colour discipline (4.05) and polish (4.00). Fixing issues 1, 3 and 4 below lifts five views by 0.25
to 0.5 and gets the average to about 4.5.

## 3. Per-view notes

**Mission (4.38).** The 1440 fold is excellent: the lockup, the plan-view aircraft with one red hotspot, a lede that
states the result with numbers, and four KPI instruments.
- The network mini-chart paints the **AUH hub bar teal at 100%**, but AUH is the HIGH-risk node (red ring, "HIGH · 100%" pill on Network). Teal means OK.
- KPI rulers flip direction. Fill runs P0→I125 left to right, while AOG runs I125→P0.
- "Planner priorities → AOG h 52W" shows **230** for GN-32-R014, while Actions shows "63 AOG h max". One is a sum across stations and the other a maximum, and neither is labelled as such.
- At 390, "P0 · Legacy rules (baselin…" and "P2 · Network (multi-echelo…" truncate, and the ATA badges on the small aircraft are about 8 px.
- At 1440, the right column ends about 280 px above the left.

**Parts (4.12).**
- System pills contradict their own counts: ATA 21 and 24 read **OK** next to "1 urgent" and "2 urgent", with red count pips on teal badges.
- The exploded schematic for ATA 34 draws 5 of 14 PNs but **omits GN-34-C023**, the risk-100 part the aircraft callout points at.
- The demand-class scatter fills the Croston zone with a teal tint. That is decorative teal.
- At 390, the aircraft callout "GN-34-C023 · 100" sits on the ATA 24 badge and its "OK" label, and "34 URGENT" overlaps the fuselage.
- The hero says "URGENT · ATA 32" while this screen rates ATA 32 REVIEW. The story explains the difference, but the hero does not.

**Parts deep link (4.44).**
- The drawer is clean, with a planted-situation callout, a stem chart with takeaway, selection shading and footer actions.
- The background correctly selects ATA 32, but the card headline still reads "ATA 34 navigation carries the most risk". That is fine on its own, but jarring under story step 2.

**Forecast (4.12).**
- **Copper is used for "vendor-quoted"** in the MTBUR dumbbell, which DS §3 forbids ("vendors… any second series").
- The stock-evaluation scatter paints **Willemain bootstrap teal** as well as Reliability-exposure, so the recommendation colour is shared.
- The leaderboard highlights the frozen champion *Naive* in teal while the same page calls it "a MASE artefact" ranked 9/9.
- "Frozen champion" sits on the left end of its own whisker.
- Three headlines wrap to 3 lines in half-width cards.

**Rotables (3.94).**
- The lifecycle diagram is spaghetti. Seven forward arcs nest and cross, and value chips (208 / 1,074 / 1,450) sit on overlapping strokes, so you cannot trace which flow a number belongs to.
- **CONDEMNED is red.** BER is not an AOG risk.
- The overdue gantt has 33 red bars plus 33 warning icons, so red loses its signal.
- The TAT histogram and the scatter use **teal as the "EU VENDOR" category colour**.
- "Chase first" lists +72, +58 and **+30 d** while the gantt shows +64 and +61 d items. The PS2 priority rule is not explained.
- The float calculator offers presets "P0 S = 10 · P2 21 · Recommended 23" while its own note and the story say "P0 5, P2 16, recommended 18". Both are right (S includes 5 units in the loop), but it reads as a contradiction.
- Unit cost shows as `47977` with no thousands separator.
- "IN TRANSIT · SHOP RETURN · POSITIO…" truncates.

**Network (4.12).**
- The transfer-replay axis ticks read **`h 160 … h 320`**, with the unit before the number. Every other chart uses `500 h`.
- The BOM policy table marks **P1 ✓ in teal**. Teal means the recommended plan, which is I125.
- The hub-vs-outstation bars use teal as the "hub" category.
- Outstation risk is normalised to AUH, so BOM (the "riskiest outstation", the subject of the story) wears a teal **LOW · 17%** OK pill while the action centre lists BOM urgent shortfalls.
- The dot-whisker square-root axis crowds "1,000 h / 1,500 h / 2,000 h" at the right.

**Capital (4.38).** The KPI tiles, frontier and robustness table are strong.
- At about AED 69M there is an **unexplained full-height grey whisker**: the unstable B250 seed is disclosed only on Method.
- The tornado uses **teal for the high-multiplier bar**, which is "high value", not "recommended". Notation is inconsistent: `x0.5`, `x2.0`, then a bare `0.15 / 0.25`, never `×`.
- The frontier card has about 260 px of dead space under "View data" because the side column is taller.

**AOG (4.19).** The swimlane timeline is the best chart in the product.
- Copy defects: "Recommend: Emergency transfer from AUH **(AUH)**", "of 3 feasible **option(s)**", and "exposure **AED 137,650** … **AED 1,944,847**", where every chart uses `AED 138k`.
- The exposure chart truncates "c · Lateral transfer from another outstati…" and "e · Accelerated repair (earliest unit at s…" at 1440, with about 600 px free.
- Deadline chips use red for D0 and **amber for D3**, but amber means review.
- **At 390, the counterfactual footnote "1,890 h fewer AOG hours … ex post" is clipped:** its right edge is at 409 px on a 390 px viewport.
- The counterfactual table's label column wraps to "AOG / hours" and "Direct / cost".
- AOG-0177 headline: "Expedite has the lowest exposure: AED 154 vs AED 2k". The 144 h option beats an 8 h lateral transfer, which needs the "both inside the 240 h slack" explanation.

**Actions (4.44).** The best operational screen. Filters, URL sync, Clear, bar-click and owner-click filters all work, and the drawer returns focus to its row.
- The recommended-action text is clamped mid-sentence ("…paid acceleration or an…") even at 1440.
- The drawer shows raw enums: `OVERDUE_REPAIR` chip, "at **EU_VENDOR**", "RO 1564 · EU_VENDOR".
- At 390, "Showing 75 of 75 · 28 / urgent" orphans a word, and the Owner select sits alone at half width.

**Method (4.19).**
- The author card ships a **placeholder social-link chip**.
- The pytest card stretches to match the right column, leaving about 1,000 px of empty card.
- Timestamps are raw ISO (`2026-11-26T02:25:21Z`).
- At 390, the register's stacked rows truncate keys to "**m…**" and "calendar.…", and source names truncate to "Car Parts Datas…" and "Synthetic …". The key is the primary datum and must not truncate.

**Footer (every view).** The disclaimer and "Falcon Hub Airways is fictional" are top-aligned on different baselines at 1440. On mobile the second line is indented about 28 px from the text above it.

## 4. Story mode (8 steps × 2 viewports)

Navigation works: Next/Back, → and Esc, the 8-segment progress bar, and Finish on step 8. Routes and deep links are correct. Framing problems:
- **1440, steps 5, 6 and 7:** the target is scrolled so its top sits at y = 4, *under the sticky top bar*. The bar is spotlit inside the frame, and steps 6 and 7 lose their own chart headline ("I125 holds…", "Released 9 h…").
- **1440, step 4:** the target is cut at the viewport bottom (the "Spares (S)" row is cut off).
- **1440, step 8:** the card sits top-left and covers 116 px of the spotlit inbox, including the severity pills.
- **390, step 1:** the sheet covers the bottom 43 px of the KPI target.
- **390, step 4:** the sheet covers 176 px of the float-calculator target, which is the sliders the body describes.
- **390, step 5:** the sheet hides the P0/P1/P2 table that holds the numbers the step quotes (291 → 40 h).
- **Content.** Step 4's "P0 5, P2 16, recommended 18" sits beside presets "10 / 21 / 23". Step 5 praises P2 while the spotlit table ticks P1. Step 8 ends on a clumsy "(step 2 counted two years)".

## 5. Functional bugs

| # | Bug | Repro | Severity |
|---|---|---|---|
| F1 | Workspace shortcuts 1–8/0 do nothing while a drawer is open. The drawer neither closes nor navigates. | `#/parts`, open a row, press `3`; or `#/parts?ata=32&pn=GN-32-R014`, press `4`; or `#/actions`, open a row, press `1`. The hash and drawer stay unchanged. | Medium (the shortcut contract in the DS and the help modal is silently broken) |
| F2 | AOG counterfactual footnote clipped at 390 px (right edge 409 px). | `#/aog?incident=AOG-0001` at 390 | Medium |
| F3 | Replay axis ticks render as `h 200` instead of `200 h`. | `#/network?station=BOM`, PS1 replay strip | Low |
| F4 | Template and copy leaks: "(AUH)" printed twice, "option(s)", unformatted AED, raw enums `OVERDUE_REPAIR`/`EU_VENDOR`, `47977`, raw ISO timestamps, the placeholder social link. | AOG recommendation card, actions drawer, float calc, method | Low (but very visible to experts) |
| F5 | The capital slider has no `aria-valuetext`, so screen readers announce "41850000". | `#/capital`, slider | Low (accessibility) |

Verified as working:
- Opening the part drawer and then navigating closes it: by drawer link (to Forecast), by `location.hash`, and by Back. Esc closes it and returns focus to the row. A scrim click closes it without navigating, which is correct.
- The capital slider steps through the non-dominated plans (I125 → I110 → B200), keeps the URL in sync (`?point=`) and moves the ring marker on the frontier.
- The AOG picker works by click and by arrow keys and keeps the URL in sync.
- The action filters, Clear, the chart and owner shortcuts, the group "Show n more" and the drawer all work, and the URL stays in sync.
- Keys 1–8 and 0 route correctly, `?` opens help, Esc closes it, and `S` starts the story. Typing in an input does not trigger shortcuts.
- The skip link comes first in tab order, and every focus ring is a visible 2 px teal outline.

## 6. Top 10 remaining issues, ranked, with fixes

1. **Accent semantics leak (colour discipline 4.05).** Fix each site with `theme.series`:
   - Forecast MTBUR "vendor-quoted": copper → `theme.series.neutral`, with estimated staying teal.
   - Stock-eval "Willemain · highest fill" dot: teal → `neutralSoft`, with a label only.
   - Leaderboard frozen-champion highlight: teal → `neutral` strong plus the ★ glyph. Keep teal for the method the policies use (Reliability-exposure).
   - Rotables CONDEMNED node and arc: red → slate dashed outline. The gantt's past-due red should be the urgent colour only for ROs flagged PS/urgent; use a hatched titanium for the others.
   - TAT histogram and scatter "EU VENDOR": teal → titanium solid vs slate hollow.
   - Network "P1 ✓" and hub bars: neutral. Put the teal emphasis on the I125 card and row.
   - Capital tornado high-side bars: neutral, with the base marker in teal.
   - AOG deadline chips: all neutral mono, with D0 in bold.
   - Mission hub risk bar: red (urgent) or neutral, never teal.
   - Extend `lintAccents()` into a test that fails when teal is painted on more than one series in a chart.
2. **Cross-screen contradictions.**
   - Rename Mission's column to "Σ AOG h · 52 wk · all stations" and the Actions group header to "max 63 AOG h at one station".
   - Float-calc presets: "P2 · 16 + 5 in loop = 21".
   - Hero callout: "URGENT PART · ATA 32 (system review)".
   - System pill: if a chapter has urgent PNs, show "WATCH · 2 urgent PNs" (or review), never a bare OK.
   - Network outstation pill: show "17% of hub" in neutral, not a teal LOW, when a station has open urgent actions.
3. **Copy and templating pass (polish 4.00).**
   - AOG recommendation: drop the "(station)" suffix when it equals the source, use `plural()`, and format money with `fmtAED`.
   - Map enum → label for exception type and shop in the drawer (`OVERDUE_REPAIR` → "Overdue repair", `EU_VENDOR` → "EU vendor").
   - Format the unit-cost input with `fmtInt`.
   - Show timestamps as `26 Nov 02:25 UTC`.
   - Use `×` for every multiplier in the tornado.
   - Hide the social-link chip until there is a URL.
   - Fix the replay tick formatter to `fmtHours`.
4. **Story framing.**
   - In `storyMode`, scroll so `target.top = topbarHeight + 16` and never 4. Pass the top bar as an obstacle to `storyCardPosition`.
   - At ≤ 480 px, if the target is taller than `vh − sheetHeight − topbar`, spotlight a narrower child: step 4 `.fc-inputs .fc-sliders`, step 5 the policy table, step 1 the first KPI row.
   - On step 8, prefer placing the card over the rail (x < 264) only when the spotlight starts right of it. Otherwise use the bottom-right corner.
   - Rewrite step 4 to "S = 21 under P2 (16 serviceable + 5 in loop)" and the step 8 tail.
5. **Truncation where space exists.**
   - AOG exposure chart: size the label column to the longest label (max 320 px at ≥ 900 px) or wrap to 2 lines.
   - Action column: clamp at 3 lines on desktop, or drop the "Issue" column width to fit content.
   - Method register at 390: put the key on its own full-width line, with the value pill on line 2.
   - Source manifest: two-line names, not ellipses.
   - Mission policy rows at 390: use short labels (`P0 · Legacy`, `P2 · Network`).
   - Rotables node subtitle: use "SHOP RETURN · POS." or two lines.
6. **AOG footnote overflow at 390 (F2).** Render the note as an HTML caption under the SVG, or split it at < 480 px. Add a check in `scripts/screenshot.py` that flags any `text` element whose bounding box exceeds the viewport.
7. **Keyboard shortcuts while overlays are open (F1).** In the drawer's `onKey`, let `[0-8]` through to the shell handler, which already calls `closeAllOverlays()` before routing. Alternatively, state "Esc first" in the help modal. Add `aria-valuetext` (formatted AED) to `slider()`.
8. **Rotables lifecycle legibility.**
   - Sort forward arcs by span into fixed lane heights so no two cross.
   - Fade any flow under 5% of the maximum to 40% and drop its chip into the View-data table.
   - Put chips at each arc apex only after `dodge()` against the other arcs' paths.
   - Add hover-to-isolate.
   - Add a one-line "Chase-first = PS-flagged ROs first, then days late" caption, or sort the list strictly by days late.
9. **Dead space and column balance.**
   - Apply `align-items: start` on the capital, method and mission grids. Better still, move the "Recommendation rule" card under the frontier chart, and collapse the pytest card list into two columns at ≥ 1200 px.
   - Align the footer as a single baseline row on desktop and flush-left on mobile.
10. **In-chart annotation gaps.**
    - Frontier: annotate the B250 whisker ("B250 · 1 unstable seed, see Method") or clip it at the axis with an arrow.
    - Exploded schematic: always include the chapter's top-risk PN among the 5 drawn.
    - AOG-0177 headline: "Both feasible options land inside the 240 h D10 slack; expedite costs AED 1.8k less".
    - Forecast "Frozen champion" label: `labelAround` its own whisker.

---

The highest-leverage work is issues 1 to 4: about a day of focused edits with no new components. That moves colour discipline
and polish to about 4.5 and lifts Rotables, Forecast, Network, AOG and Method by 0.25 to 0.5 each, which gets the average
to about 4.5.
