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
| KPI instrument | `kpiTile(kpi, {format, deltaFormat, sparkline, scale})` | Big numeral + unit, delta with arrow icon and text ("improvement"/"worse" for screen readers), sparkline slot, provenance chip, CI + baseline footer, optional ruler with value marker and amber target notch. |
| Provenance chip | `provChip('REAL'|'DERIVED'|'ASSUMED'|'SIMULATED')` | Plex Mono small caps. Shape plus colour: ● REAL, ◆ DERIVED, ○ ASSUMED, ▲ SIMULATED. |
| Status pill | `pill('ok'|'review'|'urgent'|'unknown'|'info', text?)` | Always an icon plus text, never colour alone. |
| Fixture chip | `fixtureChip()` | Amber hatched "FIXTURE DATA". The shell shows it automatically when any loaded file has `meta.fixture`. |
| Data table | `dataTable({columns, rows, sort, onRowClick, rowKey, selected, maxHeight, dense, caption, bare})` | Sticky header, sortable buttons with `aria-sort`, `mono: true` for PNs/serials, `num: true` right-aligns tabular numbers, `render(row)` for cells holding nodes. `.update(rows)` re-renders. |
| Tabs | `tabs({tabs:[{id,label,count}], value, onChange})` | ARIA tablist with arrow-key support. |
| Segmented | `segmented({options:[{value,label}], value, onChange, label})` | Radio group. |
| Slider | `slider({label, min, max, step, value, format, onInput})` | Labelled range with live `<output>` and min/max scale. |
| Drawer | `drawer({title, kicker, body, foot, onClose}).open()` | Right panel. Esc, the scrim and the close button all close it; focus is trapped and then restored. |
| Modal | `modal({title, body}).open()` | Used by the shortcuts help. |
| Tooltip | `tooltip.show(evt, {title, rows:[[k,v]], note})`, `.move`, `.hide` | Card-style singleton, also used by charts. |
| Story mode | `storyMode({steps, navigate}).start()` | Spotlight plus step card. Steps come from `story.json` (`{route, selector, title, body}`); mark targets with `data-story="…"`. |
| Footer | `disclaimer({meta})` | Holds the **exact** required disclaimer text (`DISCLAIMER` constant). Do not edit it. |
| States | `stateBlock('loading'|'empty'|'error', msg)`, `stubNote(text)` | |
| Illustrations | `inlineSVG(name)`, `blueprintAircraft(host, {active, onSelect, compactBelow})`, `fillExploded(svg, [{slot,pn,desc}])`, `fillLifecycle(svg, {counts, flows})` | See §4. |

---

## 3. Charts (`docs/js/charts/theme.js`)

### Rules (every chart)
1. Wrap it in `chartFrame()`, which gives a **takeaway headline** (a sentence that states the finding, not
   "AOG hours by policy"), a **subtitle** with units · grain · window/as-of, a **provenance chip**, a **source**
   line and a `<details>` **View data** table (the accessible fallback).
2. Use **direct labels** over legends (`directLabel`, end-of-line labels; `dodge()` resolves collisions).
3. Add **one annotation** for the key point (`annotate`).
4. **Show uncertainty** whenever an interval exists: `band()` for series, `dotWhisker()` for estimates.
5. Use **at most 2 accents**: teal (`theme.color.accent`) for the primary or recommended series, copper
   (`accent2`) for capital, baseline or comparison, and neutrals (titanium/slate) for context.
6. Keep axes as hairlines with mono tabular ticks and no heavy gridlines (`gridY` draws faint dashed guides).
   **No pies, no 3-D, no rainbow scales, no default library styling.**
7. Make it responsive: draw inside `responsive(el, draw)`. At < 480 px charts drop end labels to a compact
   key, shorten row labels (`truncate`) and reduce ticks. Every chart must work at 390 px.

### API
```js
import { chartFrame, lineChart, dotWhiskerChart, barList, plot, responsive, svgIn,
         axisBottom, axisLeft, gridY, line, band, dotWhisker, directLabel, annotate, dodge,
         withTooltip, sparkline, theme, fmtAED, fmtPct, fmtPts, fmtHours, fmtDays, fmtInt,
         fmtNum, fmtWeek, fmtByUnit } from '../charts/theme.js';

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
Formatters: `fmtAED(4.8e6)` → `AED 4.8M`, `fmtAED(820000)` → `AED 820k`, `fmtPct(0.987)` → `98.7%`
(fractions in), `fmtPts(0.034)` → `3.4 pts`, `fmtHours(124)` → `124 h`, `fmtInt(12345)` → `12,345`,
`fmtWeek(104)` → `W104` (simulated calendar).

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
world locator inset (≥ 520 px). Coordinates come from the data (`network.json` → `config/assumptions.yaml`, REAL).

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
  overlays. The shell ignores keys while focus is in an input.

## 6. Do / don't

| Do | Don't |
|---|---|
| Write headlines that state the finding ("P2 halves AOG hours") | Write headlines that name the chart ("AOG hours by policy") |
| Use teal for the recommendation, copper for capital or baseline, neutrals for everything else | Use more than 2 accent colours, rainbow scales, pies or 3-D |
| Pair status with icon and text (`pill`) | Encode status by colour alone |
| Show CIs and bands, and say "simulated" | Show point estimates as certainties |
| Put PNs, serials and codes in Plex Mono, numbers in tabular figures | Use proportional digits in tables |
| Label "Falcon Hub Airways (fictional)" and fictional tails | Use real airline names, logos, liveries or OEM drawings |
| Call deadline classes D0/D3/D10 hypothetical | Call them MEL categories |
| Keep the exact footer disclaimer | Paraphrase or remove it |
| Respect reduced motion and keep focus visible | Animate for decoration or remove outlines |
