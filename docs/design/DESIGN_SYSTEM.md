# GROUNDED NO MORE design system: Aerospace Titanium × Blueprint

A dark technical blueprint with precise linework and restrained metallic accents. It should read
like a premium aerospace engineering workspace. It is not a neon game and not a generic admin
dashboard. Everything is self-hosted and needs no build step.

- **Live gallery:** `docs/design/gallery.html` renders every component, chart primitive and
  illustration on this page.
- **Tokens:** `docs/design/tokens.json` is the binding source, mirrored in `docs/css/tokens.css`.
- **Airline:** Falcon Hub Airways (fictional). Never use a real airline's name, logo, colours or
  livery, and never use OEM drawings or copyrighted images.

---

## v2.1 additions (override anything below that disagrees)

- **Simple / Expert mode.** The top-bar toggle (`lib/mode.js`) defaults to Simple, sets `body.mode-simple` / `body.mode-expert` and re-renders the view on `gnm:mode`. `.simple-only` / `.expert-only` hide content per mode. Simple mode hides formulas, codes and method names.
- **Plain English.** Write domain words with `term(key)` from `lib/glossary.js`. In Simple mode the first use adds the expert term in small grey brackets, and every term has a definition tooltip. Use `termText()` in SVG and attributes.
- **Names.** Policies use `displayName()` / `nameTag()` from `lib/names.js`: Simple Rulebook (naive reference), Each Airport for Itself (simplified local comparator), Network Plan, Network Plan + Extra Spares. The code is a small `.mono-tag`, shown in Expert mode only.
- **Every workspace starts with `intro3()`.** Every headline KPI carries the scope line (`kpiTile` adds it, and `scopeLine()` provides it elsewhere). Results numbers carry `readingNote()`. Capital uses `capitalTable()`, never the net alone. Anything added after the freeze gets `postPlanBadge()`.
- **Footer.** Every page shows the disclaimer plus the credit line (`CREDIT_LINE`).
- **Navigation.** PROJECT now lists the 60-second tour, Data & Method, About, Glossary and The Planner Behind the Project.
- Full API with examples: `docs/agent_notes/v21_shell.md`.

## 0. Wave A rules (override anything below that disagrees)

**Typography.**

| Role | Font · size / weight | Token |
|---|---|---|
| Hero title | Space Grotesk 44–48 / 700 | `--fs-hero` (46 px; Mission uses 44 px) |
| Workspace heading (h1) | Space Grotesk 28–32 / 600 | `--fs-workspace` 30 px (28 px on phones) |
| KPI value | Space Grotesk 34–40 / 600 | `--fs-kpi` 38 px |
| Chart heading | **Inter** 18–20 / 600 | `--fs-chart` 19 px |
| Card heading | Inter 16 / 600 | `--fs-card` |
| Body | Inter 14–15 | `--fs-15` (body), `--fs-14` |
| Table and decision text | Inter, **≥ 13 px** | `--fs-13` minimum (cells, stacked rows, pills) |

- **IBM Plex Mono** is used *only* for PNs, serials, timestamps, codes (station codes, ATA, plan ids) and numeric values.
- **Uppercase letter-spaced** text is used *only* for small section labels (kickers, field labels, table headers, nav
  group labels), set in Inter 600, never Plex Mono. Status pills are sentence case (`pill()` sentence-cases all-caps data
  text but keeps codes such as BOM, AOG, PS1 and D0).

**Colour.**
- `--c-muted-titanium #8FA5B7` is the secondary-text colour (`--text-faint`; 7.0:1 on midnight).
- **No opacity or rgba on meaningful text.** Copper and red text are always full strength. `tests/_sitefx.py` audits it.
- Red and amber are used *only* for operational exceptions (urgent / review).
- **Provenance.** SIMULATED is the default state of the whole site, so the shell shows **one** neutral "Simulation"
  indicator (top bar, with a tooltip that explains provenance). A SIMULATED `provChip()` renders visually quiet: it
  keeps screen-reader text, a title and the `.chip-prov` element, so every chart, KPI and table still carries its
  provenance in the DOM, the chart "View data" table and the source line. REAL / DERIVED / ASSUMED chips stay visible,
  because they mark what is *not* simulated. `provChip(p, {force: true})` shows the SIMULATED badge where provenance is
  the subject: the Data & Method legend and the assumption register.

**Blueprint grid.** 3–5% opacity (`--c-grid` 3%, `--c-grid-major` 5%). Cards are opaque, so the grid never runs
behind dense tables or charts. It stays around aircraft illustrations (the drawings' own `bp-gridfill`) and section
headers.

**Navigation.** Four labelled groups: OPERATIONS (Mission Control, Planner Action Centre, AOG Response Lab) ·
MATERIAL INTELLIGENCE (Parts Intelligence, Forecast Lab, Rotable & Repair) · STRATEGIC PLANNING (Network Positioning,
Capital Optimiser) · PROJECT (60-second tour, Data & Method, About). Route ids, deep links and the shortcut keys
(1–8 = original workspace numbers, 0 = Data & Method, S = tour) are unchanged, and the help modal lists them by name.

**Aircraft drawings.** `aircraft-narrowbody.svg` and `aircraft-widebody.svg` are generated from parameters by
`docs/assets/svg/src/aircraft-plan.mjs`. They are original orthographic plan views with no tracing.

| Line type | Stroke |
|---|---|
| Silhouette | 1.8 px `#B9C8D6` |
| Major structure (control-surface boundaries, section lines) | 1.1 px `#71899C` |
| Secondary (slats, spoilers, fairings, windscreen) | 0.7 px `#51697D` |
| Gear bays / spars | dashed `#51697D` |
| Construction (centreline, nacelle and reference lines) | 0.5 px dashed `#334C61` |
| Unselected zone | 0.9 px muted titanium |
| Selected zone | 2.25 px teal |
| Urgent marker | 1.75 px red |

ATA areas are soft **indicative zones**: rounded shapes, an "indicative zone" tag on the selected zone and a sheet
note. They are never component locations. The hotspot API (`#ata-XX.ata-hotspot[data-ata]`, `.hs-shapes`,
`.hs-badge`, `.bp-callout`, `data-compact-viewbox`) is unchanged. The widebody archetype has no bleed-system callout.

**Wording.**

| Prefer | Never |
|---|---|
| material shortage exposure | aircraft risk score |
| expected material-related downtime hours | aircraft ready |
| material requirement covered | approved to fly |
| simulated planning snapshot | live data |

JSON field names stay as they are.

## 1. Tokens

| Group | Values |
|---|---|
| Colour | midnight `#09131F` (bg) · deep steel `#132638` (panel) · card `#0F1E2E` (surface) · ice `#F2F6FA` (text) · titanium `#B9C8D6` (muted) · aero teal `#22C7B8` (primary / OK / REAL) · copper `#C47F52` (capital / SIMULATED) · amber `#F5B942` (review / ASSUMED) · red `#E76B64` (urgent) · slate `#6B7C8F` (unknown, **non-text only**) · hairline `rgba(185,200,214,.14)` · grid `rgba(34,199,184,.07)` |
| Derived (CSS only) | `--c-text-faint #8A9BAD` (tertiary text, passes AA) · `--c-teal-hi #7FF3E6` (glow/active only) · teal/amber/red alpha tints for chips and selection |
| Type | Space Grotesk (display) · Inter (UI) · IBM Plex Mono (PNs, serials, codes, ticks, chips). Scale **12 / 14 / 16 / 20 / 28 / 40 / 64** (`.t-12` … `.t-64`). Tabular numerals (`.num`) wherever numbers align. |
| Space | 8-px base: `--s-1` 8 · `--s-2` 16 · `--s-3` 24 · `--s-4` 32 · `--s-6` 48 · `--s-8` 64. Utilities `.mt-*`, `.mb-*`, `.gap-*`, `.stack-*`. |
| Layout | 12-column `.grid-12`, gutter 24 (16 on mobile), max width 1440, rail 264. `.span-N` collapses to 6/12 at < 1200 px and 12 at < 768 px. |
| Shape | card radius 12 · control 8 · chip 999 · 1 px hairlines · icon stroke 1.5 |
| Motion | 200 / 300 / 400 ms, `cubic-bezier(0.16, 1, 0.3, 1)`. All motion collapses to 0 under `prefers-reduced-motion`, and the radar pulse is removed. |

### Contrast (WCAG 2.1 AA, verified by `scripts/screenshot.py --contrast` → `docs/design/contrast.json`)

| Foreground | on midnight | on card | on deep steel |
|---|---|---|---|
| ice | 17.2 | 15.53 | 14.2 |
| titanium | 10.93 | 9.87 | 9.03 |
| text-faint (derived) | 6.56 | 5.92 | 5.41 |
| aero teal | 8.83 | 7.97 | 7.29 |
| amber | 10.58 | 9.56 | 8.74 |
| red | 5.94 | 5.37 | 4.91 |
| copper | 5.78 | 5.22 | 4.78 |
| slate (non-text, ≥ 3:1) | 4.36 | 3.94 | 3.6 |

Chips (text on its own 10% tint over card): REAL 6.64, DERIVED 7.99, ASSUMED 7.85, SIMULATED 4.6.
Pills (12% tint): urgent 4.66, review 7.51. Primary button (midnight on teal): 8.83. All pass.

---

## 2. Components (`docs/js/ui.js` + `docs/css/components.css`)

Every helper returns a real DOM element. Compose them and don't restyle them per view.

| Component | API | Notes |
|---|---|---|
| Element builder | `h(tag, attrs, ...children)` | Strings become safe text nodes; `on*` attrs bind listeners; `dataset`, `style` objects. |
| Icon | `icon(name, {label?})` | `<use href="#i-name">` from the inlined sprite (`ensureSprite()` runs at boot). Names: aircraft, part, rotable, warehouse, route, clock, alert, check, info, capital, wrench, filter, download, play, map-pin, chart, flask, inbox, shield, book, arrow-up/down, chevron-right, close, menu, sort, keyboard, minus, layers, target. |
| Page header | `pageHead({num, eyebrow, title, lede, meta})` | Eyebrow "02 · PARTS INTELLIGENCE", H1 40 px, lede ≤ 72ch, meta chips right. |
| Card | `card({title, kicker, prov, actions, body, foot, cls, story, bp, flush})` | `bp: true` adds the blueprint corner registration marks. Use it on at most one hero card per screen. |
| KPI instrument | `kpiTile(kpi, {format, deltaFormat, sparkline, scale, capital, deltaTone})` | Big numeral + unit, delta with arrow icon and text ("improvement"/"worse" for screen readers), sparkline slot, provenance chip, CI + baseline footer, optional ruler with value marker and amber target notch. **Capital deltas are neutral** (titanium, arrow, "more/less capital"), never red/green: automatic when the KPI id/label mentions "capital" (`isCapitalKpi`), or force with `capital: true` / `deltaTone: 'neutral'`. |
| Provenance chip | `provChip('REAL'|'DERIVED'|'ASSUMED'|'SIMULATED')` | Plex Mono small caps. Shape plus colour: ● REAL, ◆ DERIVED, ○ ASSUMED, ▲ SIMULATED. |
| Status pill | `pill('ok'|'review'|'urgent'|'unknown'|'info', text?)` | Always an icon plus text, never colour alone. |
| Fixture chip | `fixtureChip()` | Amber hatched "FIXTURE DATA". The shell shows it automatically when any loaded file has `meta.fixture`. |
| Data table | `dataTable({columns, rows, sort, onRowClick, rowKey, selected, maxHeight, dense, caption, bare, mobileColumns, stack, stickyFirst})` | Sticky header, sortable buttons with `aria-sort`, `mono: true` for PNs/serials, `num: true` right-aligns tabular numbers, `render(row)` for cells holding nodes. `.update(rows)` re-renders, `.setSelected(key)`. **Mobile:** `mobileColumns: ['pn','risk_score','stock']` is a priority list: < 768 px shows only those columns; ≤ 480 px renders two-line stacked rows (key 1 on line 1, key 2 in a right-aligned metric pill, the rest as faint "Label value" pairs on line 2) with a compact sort control (`stack: false` opts out; `short` gives a column a short label). `stickyFirst: true` pins the first column with a hairline shadow. Every table whose decision column would scroll off at 390 px must set `mobileColumns`. |
| Tabs | `tabs({tabs:[{id,label,count}], value, onChange})` | ARIA tablist with arrow-key support. |
| Segmented | `segmented({options:[{value,label}], value, onChange, label})` | Radio group. |
| Slider | `slider({label, min, max, step, value, format, valueText, onInput})` | Labelled range with live `<output>` and min/max scale. **Always sets `aria-valuetext`** (from `valueText(v)`, else `format(v)`), so screen readers hear "AED 41.9M", not "41850000". Returns the field with `.input` and `.setValue(v)`. For a hand-built `<input type=range>` call `bindValueText(input, fmt)` (returns `update()` for programmatic changes). |
| Drawer | `drawer({title, kicker, body, foot, onClose, persistOnParams}).open()` | Right panel. Esc, the scrim and the close button all close it; focus is trapped and then restored; page scroll is locked while open. Registered with the overlay registry: **the router closes it on every route change** (`onClose({reason:'route'})`). `close()` is idempotent. |
| Modal | `modal({title, body}).open()` | Used by the shortcuts help. Registered like the drawer. |
| Overlay registry | `closeAllOverlays({reason})`, `registerOverlay({close, el, persistOnParams})`, `openOverlayCount()` | The router calls `closeAllOverlays()` before rendering any view (links, `ctx.navigate`, `location.hash`, Back/Forward, query changes that re-render). Register any custom overlay so it is closed too. Story mode is exempt. |
| Tooltip | `tooltip.show(evt, {title, rows:[[k,v]], note})`, `.move`, `.hide` | Card-style singleton, also used by charts. |
| Story mode | `storyMode({steps, navigate}).start()` | Spotlight plus step card. Steps come from `story.json` (`{route, selector, mobile_selector?, title, body}`); mark targets with `data-story="…"`. Targets are framed with their top at **top-bar height + 16 px** (never under the sticky bar; re-framed while charts above them finish rendering); a target taller than the free space is top-aligned under the bar and the card goes in the remaining space. The card goes right / left / below / above the visible part of the target (then the corners), choosing the least overlap (`storyCardPosition(rect, {cw, ch, vw, vh, top})`, `top` = the smallest card top). **≤ 480 px:** a bottom sheet (≤ 40vh) with a grab-handle button; it drops to a **peek** strip (~25% of the viewport, body clamped to 2 lines) automatically when it would cover the target, and the handle toggles it. `mobile_selector` names a narrower child to spotlight on phones (falls back to `selector`). |
| Native select | `<select>` (any class) | Styled globally: no OS chrome, 8 px radius, hairline border, DS chevron. Views may change size/font; the chevron always wins. |
| Footer | `disclaimer({meta})` | Holds the **exact** required disclaimer text (`DISCLAIMER` constant). Do not edit it. |
| States | `stateBlock('loading'|'empty'|'error', msg)`, `stubNote(text)` | |
| Illustrations | `inlineSVG(name)`, `blueprintAircraft(host, {active, onSelect, compactBelow})`, `fillExploded(svg, [{slot,pn,desc}])`, `fillLifecycle(svg, {counts, flows})` | See §4. |

---

## 3. Charts (`docs/js/charts/theme.js`)

### Rules (every chart)
1. Wrap it in `chartFrame()`, which gives a **takeaway headline** (one finding, **≤ 90 characters**, a sentence that
   states the finding, not "AOG hours by policy"; dev builds `console.warn` above 90), a **subtitle** with units · grain
   · window/as-of (Inter 12, **clamped to 2 lines**, full text in `title` + a "More" toggle), a **provenance chip**, a
   **source** line and a `<details>` **View data** table (the accessible fallback). Qualifications go in the subtitle or
   the footnote, not the headline.
2. Use **direct labels** over legends (`directLabel`, end-of-line labels). Every label must clear other labels **and
   marks**: run them through `dodge(labels, {gap, obstacles, bounds})` with `markerRect()` / `elementRect()` obstacles,
   or place single labels with `labelAround(point, {r, centroid, obstacles, placed})` (offset r + 6 px, away from the
   data centroid). All chart labels have a surface-colour **halo** by default (`.gnm-label`, paint-order stroke).
   Values on arcs, flows and lifecycle edges use `chipLabel()` (a filled pill), placed at the arc apex.
3. Add **one annotation** for the key point (`annotate`).
4. **Show uncertainty** whenever an interval exists: `band()` for series, `dotWhisker()` for estimates.
5. **Colour semantics are fixed** (table below). Use **at most 2 accents** per chart; everything else is neutral.
   Pick colours from `theme.series.*`, never raw hex.
6. Keep axes as hairlines with mono tabular ticks and no heavy gridlines (`gridY` draws faint dashed guides).
   **No pies, no 3-D, no rainbow scales, no default library styling.**
7. Make it responsive: draw inside `responsive(el, draw)`. At < 480 px charts drop end labels to a compact
   key, shorten row labels (`truncate`) and reduce ticks. Every chart must work at 390 px.
8. Weeks are always `fmtWeek(n)` → `W103` (simulated calendar; ranges `fmtWeekRange(104, 155)` → `W104–W155`).
   Never show real dates or "Week 103".

### Accent → meaning (rule 5, enforced via `theme.series`)

| Accent | Token | Means | Never use it for |
|---|---|---|---|
| Teal `#22C7B8` | `theme.series.recommended` (`theme.color.accent`) | The recommended plan; the primary data series; OK / REAL | Baselines, reference lines, decoration |
| Copper `#C47F52` | `theme.series.baseline` (`theme.color.accent2`) | Capital, and the P0 baseline only; SIMULATED chip | Return flows, vendors, emergencies, AOG-penalty bars, calibration targets, seeds, any second series |
| Red `#E76B64` | `theme.series.urgent` | Urgent status / AOG risk (pills, at-risk marks, emergency AOG replays) | Capital increases, cost deltas, a "worse" series that is not an AOG risk |
| Amber `#F5B942` | `theme.series.review` | Review status; ASSUMED chip; KPI target notch | Reference lines, thresholds, targets in charts |
| Faded titanium (50%) | `theme.series.reference` + `refLine()` | Reference lines and thresholds (4 4 dash, label in `--c-text-faint`) | Data series |
| Titanium / slate | `theme.series.neutral`, `neutralSoft`, `context` | Every other comparison or context series (P1, P2, other methods, return flows at 40% opacity) | Status |

- **Capital deltas are neutral text** (titanium, arrow and "more capital"/"less capital", `fmtCapitalDelta()`), never red or
  green: spending more capital is a choice, not an alarm. `kpiTile` does this automatically for capital KPIs.
- Calibration target bands: hatch or outline in titanium, not a copper fill.
- `lintAccents(el)` lists the accents painted in a chart; `chartFrame` warns in dev builds when there are more than 2.
- **The one-line rule: teal = the recommended / primary result only; neutral (titanium/slate) for every other category;
  red = urgent / AOG; amber = review status; copper = capital or the P0 baseline.** Teal is never a category colour
  ("EU vendor", "hub", "Willemain", a "best" marker on a non-recommended row, a "high" tornado bar).
- `lintTeal(el)` lists the distinct **series** painted teal (marks tagged with `data-series` via `markSeries(sel, id)` /
  `pickSeries(role, id)`, plus teal non-numeric direct labels). `chartFrame` warns in dev builds when more than one series
  is teal. `lineChart`, `dotWhiskerChart` and `barList` tag their marks automatically; tag bespoke marks with
  `markSeries(selection, d => d.key)` and pick colours with `pickSeries('recommended', id)` (it also warns when two
  different series ask for teal in the same chart).

### API
```js
import { chartFrame, lineChart, dotWhiskerChart, barList, plot, responsive, svgIn,
         axisBottom, axisLeft, gridY, line, band, dotWhisker, directLabel, annotate, dodge,
         labelAround, labelBox, markerRect, elementRect, chipLabel, refLine, lintAccents, lintTeal,
         markSeries, pickSeries, withTooltip, sparkline, theme, fmtAED, fmtMoney, fmtPct, fmtPts, fmtHours,
         fmtDays, fmtInt, fmtCount, fmtNum, fmtMult, TIMES, fmtEnum, plural, fmtSimTime, fmtStamp, SIM_EPOCH,
         fmtWeek, fmtWeekRange, fmtCapitalDelta, fmtByUnit } from '../charts/theme.js';

const f = chartFrame(card, {
  headline: 'P2 cuts AOG hours by 45% versus legacy rules',
  subtitle: 'AOG hours / year · mean and 95% CI · 20 paired holdout seeds · weeks 104–155',
  provenance: 'SIMULATED', source: 'policies.json',
  table: { columns: [{ key: 'policy', label: 'Policy' }, { key: 'mean', label: 'Mean', num: true, format: fmtHours }], rows },
});
dotWhiskerChart(f.body, { rows: [{ key: 'P2', label: 'P2 · Multi-echelon', value: 228, lo: 196, hi: 263, highlight: true }, …], format: fmtHours });
lineChart(f.body, { series: [{ id: 'mean', label: '8-wk mean', values, primary: true }], band, x: { format: fmtWeek },
                    annotation: { x: 13, y: 15, title: 'Peak W13', sub: '15 units' } });
```
Formatters: `fmtAED(4.8e6)` → `AED 4.8M`, `fmtAED(820000)` → `AED 820k` (`fmtMoney` is the same compact format: use it for
**every** money value, prose included, never `AED 137,650`), `fmtCount(47977)` → `47,977`, `fmtMult(2)` → `×2.0` (always
the `×` sign, `TIMES`), `fmtEnum('EU_VENDOR')` → `EU vendor` (never print raw enums), `plural(3, 'option')` → `3 options`
(never "option(s)"), `fmtSimTime('2023-01-18T01:00Z' | simHours)` → `W2 · d3 01:00` (simulated calendar, epoch
`SIM_EPOCH` = `aog_lab.json` `sim_calendar.epoch`), `fmtStamp('2026-11-26T02:25:21Z')` → `26 Nov 02:25 UTC` (real build
timestamps only), `fmtPct(0.987)` → `98.7%`
(fractions in), `fmtPts(0.034)` → `3.4 pts`, `fmtHours(124)` → `124 h`, `fmtInt(12345)` → `12,345`,
`fmtWeek(104)` → `W104` (simulated calendar; also accepts `'W104'`, rounds, `null` → `—`), `fmtWeekRange(104, 155)` →
`W104–W155`, `fmtCapitalDelta(5.04e6)` → `+AED 5M more capital`.

Label collision, chips and reference lines (see `docs/agent_notes/design-fix-shared.md` for full examples):
```js
const obstacles = dots.map((d) => markerRect(x(d.x), y(d.y), 5));          // marker boxes
dodge(labels, { gap: 14, obstacles, bounds: { x: 0, y: 0, width: iw, height: ih } }).forEach((l) => directLabel(g, l));
const p = labelAround({ x: cx, y: cy }, { r: 5, text: 'Reliability-exposure', centroid, obstacles });
directLabel(g, { ...p, text: 'Reliability-exposure' });
chipLabel(g, { x: apex.x, y: apex.y, text: fmtInt(39) });                    // value on an arc / flow
refLine(g, { x1: x(1), x2: x(1), y1: 0, y2: ih, label: 'naive = 1.0' });     // faded titanium dashes
line(g, p0, { x, y, color: theme.series.baseline });                         // P0 baseline in copper
```

For bespoke D3 charts, start from `svgIn(el, w, h)`, then use `axisBottom`/`axisLeft`/`gridY`/`line`/`band`/
`dotWhisker`/`annotate` and `withTooltip(selection, d => ({title, rows}))`. `capital-optimiser.js` is the
reference example (a frontier with CI band, baseline in copper, one annotation). For Observable
Plot, call `plot({...})`: it applies the theme (transparent background, mono ticks, hairline axes, no
grid).

### Map (`docs/js/charts/map.js`)
```js
const map = await renderNetworkMap(host, { stations, arcs, selected: 'BOM', onSelect, labelSub: s => `${s.serviceable_units} u` });
await map.animateTransfer('AUH', 'BOM', { kind: 'emergency', duration: 900 });
map.select('LHR'); map.destroy();
```
It draws Natural Earth land in low-contrast steel with a faint graticule, geodesic arcs from the hub with a
teal gradient (stroke width follows `transfers`), ring nodes with Plex Mono IATA labels, and an AUH radar pulse
(none under reduced motion). It uses a conic projection over Europe, the Middle East and Asia, plus a
world locator inset (only when the map is ≥ 900 px wide; `insetMinWidth`). Station labels (IATA + `labelSub` as one
block directly under/beside the node) are placed automatically clear of every node ring, arc chip and other label
(`labelOffsets[station]` is tried first; `autoLabels: false` restores fixed offsets). `arcLabel: (arc) => string` draws a
`chipLabel()` value at each arc midpoint. Emergency replays are red (`theme.series.urgent`), not copper. Coordinates come from the data (`network.json` → `config/assumptions.yaml`, REAL).

---

## 4. Illustrations (`docs/assets/svg/`, generated by `node docs/assets/svg/src/build.mjs`)

| File | What | Script hooks |
|---|---|---|
| `blueprint-aircraft-top.svg` | Plan view of a generic twin-engine airliner: centreline, SPAN/LENGTH dimensions, panel lines, hidden (dashed) equipment, nacelles, gear bays, 8 ATA callouts, title block | `<g id="ata-XX" class="ata-hotspot" data-ata="XX">`; add `.is-active` for the glow. `data-compact-viewbox` + `.bp-compact` switch to badge mode. |
| `blueprint-aircraft-side.svg`, `-front.svg` | Elevations in the same style | — |
| `exploded-{21,24,27,29,32,34,36,49}.svg` | Exploded isometric views of 5 fictional components each | `.bp-part[data-slot][data-role]`, `.bp-label[data-slot] [data-field="pn"|"desc"]` → `fillExploded()` |
| `rotable-lifecycle.svg` (+ `-vertical.svg`) | SERVICEABLE → INSTALLED → REMOVED (U/S) → IN REPAIR → SERVICEABLE / CONDEMNED | `[data-count="STATE"]`, `[data-flow="FROM>TO"]` → `fillLifecycle()`; `[data-state]` + `.is-active` |
| `icons.svg` | 30-symbol line sprite (24 px, 1.5 px stroke) | `#i-<name>` |
| `../favicon.svg`, `og-card.svg` → `../og-image.png` | Mark and social card | — |

Inline illustrations with `inlineSVG()` (never `<img>`) whenever you need hotspots or labels. It makes `bp-*`
ids unique per instance. The shell already draws the grid, so `.bp-figure` hides the SVG's own grid;
add `.bp-figure--grid` to show it on its own.

---

## 5. How a screen agent writes a view

```js
// docs/js/views/parts-intelligence.js
import { h, pageHead, card, provChip, dataTable } from '../ui.js';
import { chartFrame, lineChart, fmtAED } from '../charts/theme.js';

export const data = ['parts', 'demand_history'];     // the router loads these first (real or fixture)

export async function render(el, ctx) {
  // ctx = {route, params, data, navigate(hash), setParams(obj), load(name), buildHash(id, params)}
  const { parts } = ctx.data;
  el.append(pageHead({ num: '02', eyebrow: 'Parts Intelligence', title: '…', lede: '…', meta: [provChip('SIMULATED')] }));
  // … compose cards, tables, charts …
  ctx.setParams({ ata: '32' });                         // deep-link state without re-rendering
  return () => { /* cleanup: observers, timers, maps */ };
}
```
- Deep links: read `ctx.params` (e.g. `#/parts?ata=32&pn=GN-32-R014`) and write with `ctx.setParams`.
  `ctx.navigate('#/network?station=BOM')` moves between workspaces.
- Every number on screen must come from the exported JSON. Show its provenance chip.
- Mark story targets with `data-story="name"`. Use one `bp` hero card at most.
- Test at 1440 × 900 and 390 × 844 with `scripts/screenshot.py --only <route>`.
- Keyboard: 1–8 switch workspaces, 0 opens Data & Method, ? shows help, S starts the story, Esc closes
  overlays. 1–8 / 0 / S also work **while a drawer or modal is open** (the shell closes every overlay, then acts);
  Esc closes the overlay first. The shell ignores keys while focus is in an input, and the tour owns → ← Esc.
- Overlays: never leave one behind. The router closes all drawers/modals/tooltips before any view renders, and a stale
  view's `ctx.setParams` is ignored. To keep a drawer open across same-route query changes, export
  `onParams(params, ctx)` from the view (return `false` to fall back to a full re-render) and open the drawer with
  `persistOnParams: true`.

### Cross-screen numbers (exported once, shown the same everywhere)
- Per-PN AOG hours: `parts.json` `aog_h_2y`, `aog_h_52w`, `aog_h_52w_max_station` (+ `_id`), printed with the labels in
  `parts.json` `aog_metric_labels` (e.g. "AOG h · last 52 wk · all stations"). Never show an unlabelled "AOG h".
- ATA system pills: print `ata_systems[].status_label` with `pill(status)`; `system_level` (relative rating) and
  `has_urgent_part` are separate fields. A system never reads a bare OK next to urgent parts ("WATCH · 2 urgent PNs").
- Outstation risk: `network.json` `stations[].outstation_risk_level` / `risk_vs_outstations` / `outstation_rank`
  (relative to the riskiest outstation); the hub-normalised `risk` is for the hub-vs-network comparison only.
- Float S: the calculator's S = shelf + units in the loop (`rotables.json` `float_examples[].spares_total`).

### Automated QA (tests/_sitefx.py `audit()`)
Fails on: console errors, failed requests, visible NaN/undefined/null, horizontal page scroll, text clipped inside a card
(`scrollWidth > clientWidth`; a deliberate **single-line ellipsis is allowed when the full text is in a `title`**
on the element or an ancestor), **text past the right edge of its card, its `<svg>` or the viewport** (`EDGE_JS`: SVG
`text` boxes and HTML glyph boxes; scroll containers exempt), and chart frames without headline + subtitle + chip.

## 6. Do / don't

| Do | Don't |
|---|---|
| Write headlines that state the finding ("P2 halves AOG hours") | Write headlines that name the chart ("AOG hours by policy") |
| Use teal for the recommendation, copper for capital or baseline, neutrals for everything else | Use more than 2 accent colours, rainbow scales, pies or 3-D |
| Draw reference lines with `refLine()` (faded titanium dashes) | Draw reference lines in amber or copper |
| Show capital changes in neutral text ("+AED 5M more capital") | Colour a capital increase red |
| Keep teal for the recommended / primary result only | Paint a category, a vendor, the hub or a "best" row teal |
| Format money compactly (`fmtMoney` → "AED 138k"), multipliers with `×`, enums as words | Print "AED 137,650", "x2.0", `EU_VENDOR` or "option(s)" |
| Keep headlines ≤ 90 characters and subtitles ≤ 2 lines | Pack three clauses and six numbers into a headline |
| Pair status with icon and text (`pill`) | Encode status by colour alone |
| Show CIs and bands, and say "simulated" | Show point estimates as certainties |
| Put PNs, serials and codes in Plex Mono, numbers in tabular figures | Use proportional digits in tables |
| Label "Falcon Hub Airways (fictional)" and fictional tails | Use real airline names, logos, liveries or OEM drawings |
| Call deadline classes D0/D3/D10 hypothetical | Call them MEL categories |
| Keep the exact footer disclaimer | Paraphrase or remove it |
| Respect reduced motion and keep focus visible | Animate for decoration or remove outlines |
- Status word WATCH (wave C note): an OK-band system or station that holds an urgent part; amber review tone, documented in the Parts legend.
