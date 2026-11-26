// Components gallery: renders every component, chart primitive and illustration of the design system.
// Served at docs/design/gallery.html. Uses fixture data purely for layout.
import { h, icon, ensureSprite, provChip, pill, fixtureChip, kbd, pageHead, card, kpiTile, dataTable, tabs, segmented, slider, drawer, modal, tooltip, inlineSVG, blueprintAircraft, fillExploded, fillLifecycle, storyMode, disclaimer, stubNote, stateBlock, sectionTitle } from '../js/ui.js';
import { chartFrame, lineChart, dotWhiskerChart, barList, sparkline, plot, theme, fmtAED, fmtPct, fmtPts, fmtHours, fmtInt, fmtByUnit, fmtWeek } from '../js/charts/theme.js';
import { renderNetworkMap } from '../js/charts/map.js';
import { loadMany, onFixture } from '../js/data.js';

const root = document.getElementById('gallery');
const section = (num, title, ...kids) => h('section', { class: 'gallery-section' }, h('h2', { class: 't-28' }, h('span', { class: 'mono' }, num), title), ...kids);

async function main() {
  await ensureSprite();
  const D = await loadMany(['kpis', 'parts', 'policies', 'network', 'forecast', 'rotables', 'demand_history', 'actions']);
  const fixtureSlot = h('span');
  onFixture(() => { if (!fixtureSlot.childElementCount) fixtureSlot.append(fixtureChip()); });

  root.append(pageHead({ eyebrow: 'Design system · Aerospace Titanium × Blueprint', title: 'Components gallery', lede: 'Every token, component, chart primitive and original illustration used by GROUNDED NO MORE. Screen agents compose these; see docs/design/DESIGN_SYSTEM.md for the rules.', meta: [fixtureSlot] }));

  // ------------------------------------------------------------------ 01 colour
  const sw = (name, varName, hex, note) => h('div', { class: 'swatch span-2 sm-span-6' }, h('div', { class: 'swatch-chip', style: { background: `var(${varName})` } }), h('div', { class: 'swatch-meta' }, h('b', {}, name), h('span', {}, hex), note ? h('div', { class: 'faint' }, note) : null));
  root.append(section('01', 'Colour', h('div', { class: 'grid-12' },
    sw('Midnight', '--c-midnight', '#09131F', 'bg'), sw('Deep steel', '--c-deep-steel', '#132638', 'panel'), sw('Card', '--c-card', '#0F1E2E', 'surface'), sw('Ice', '--c-ice', '#F2F6FA', 'text'), sw('Titanium', '--c-titanium', '#B9C8D6', 'muted · DERIVED'), sw('Text faint', '--c-text-faint', '#8A9BAD', 'derived, AA'),
    sw('Aero teal', '--c-aero-teal', '#22C7B8', 'primary · OK · REAL'), sw('Copper', '--c-copper', '#C47F52', 'capital · SIMULATED'), sw('Amber', '--c-amber', '#F5B942', 'review · ASSUMED'), sw('Red', '--c-red', '#E76B64', 'urgent'), sw('Slate', '--c-slate', '#6B7C8F', 'unknown (non-text)'), sw('Teal hi', '--c-teal-hi', '#7FF3E6', 'glow only')
  )));

  // ------------------------------------------------------------------ 02 type
  const typeRows = [['64 / display', 't-64', 'Grounded no more'], ['40 / h1', 't-40', 'Spares readiness across the network'], ['28 / h2', 't-28', 'Capital versus groundings'], ['20 / h3', 't-20', 'Where part risk concentrates'], ['16 / body', 't-16', 'Body copy in Inter, 16 px, for explanations and ledes.'], ['14 / ui', 't-14', 'Dense UI text, table cells and controls.'], ['12 / meta', 't-12 mono', 'GN-32-R014 · W104 · AED 4.8M · 98.7% · 124 h']];
  root.append(section('02', 'Typography', card({ body: [h('div', {}, typeRows.map(([k, c, t]) => h('div', { class: 'type-row' }, h('span', { class: 'mono faint t-12' }, k), h('span', { class: c }, t)))), h('p', { class: 'mt-3 faint t-12' }, 'Space Grotesk (display) · Inter (UI) · IBM Plex Mono (part numbers, serials, codes, axis ticks). Numerals are tabular everywhere numbers align.')] })));

  // ------------------------------------------------------------------ 03 space + icons
  root.append(section('03', 'Spacing & icons', h('div', { class: 'grid-12' },
    card({ cls: 'span-4', title: '8-px spacing scale', body: h('div', { class: 'stack-1' }, [8, 16, 24, 32, 40, 48, 64, 80].map((v) => h('div', { class: 'row' }, h('span', { class: 'mono faint t-12', style: { width: '40px' } }, `${v}`), h('div', { class: 'space-bar', style: { width: `${v * 2}px` } })))) }),
    card({ cls: 'span-8', title: 'Line-icon sprite · 24 px grid · 1.5 px stroke', body: h('div', { class: 'grid-12', style: { gap: '8px' } }, ['aircraft', 'part', 'rotable', 'warehouse', 'route', 'clock', 'alert', 'check', 'info', 'capital', 'wrench', 'filter', 'download', 'play', 'map-pin', 'chart', 'flask', 'inbox', 'shield', 'book', 'layers', 'target', 'keyboard', 'sort'].map((n) => h('div', { class: 'icon-cell span-2 sm-span-6' }, icon(n), n))) })
  )));

  // ------------------------------------------------------------------ 04 chips, pills, buttons
  root.append(section('04', 'Chips, pills & buttons', card({ body: h('div', { class: 'stack-3' },
    h('div', { class: 'row-wrap' }, h('span', { class: 'kpi-label', style: { width: '140px' } }, 'Provenance'), provChip('REAL'), provChip('DERIVED'), provChip('ASSUMED'), provChip('SIMULATED')),
    h('div', { class: 'row-wrap' }, h('span', { class: 'kpi-label', style: { width: '140px' } }, 'Status'), pill('ok'), pill('review'), pill('urgent'), pill('unknown'), pill('info')),
    h('div', { class: 'row-wrap' }, h('span', { class: 'kpi-label', style: { width: '140px' } }, 'Warning'), fixtureChip(), h('span', { class: 'chip chip-ata mono' }, 'ATA 32'), h('span', { class: 'chip' }, 'SIM · W104–155')),
    h('div', { class: 'row-wrap' }, h('span', { class: 'kpi-label', style: { width: '140px' } }, 'Buttons'), h('button', { class: 'btn btn--primary', type: 'button' }, icon('play'), 'Primary'), h('button', { class: 'btn', type: 'button' }, 'Secondary'), h('button', { class: 'btn btn--ghost', type: 'button' }, 'Ghost'), h('button', { class: 'btn btn--sm', type: 'button', 'aria-pressed': 'true' }, 'Pressed'), h('button', { class: 'btn btn--icon', type: 'button', 'aria-label': 'Download' }, icon('download')), h('button', { class: 'btn', type: 'button', disabled: true }, 'Disabled')),
    h('div', { class: 'row-wrap' }, h('span', { class: 'kpi-label', style: { width: '140px' } }, 'Keys'), kbd('1'), kbd('8'), kbd('?'), kbd('Esc'))
  ) })));

  // ------------------------------------------------------------------ 05 KPI tiles
  const K = D.kpis.kpis;
  const fmtFor = (k) => (k.id === 'open_exceptions' ? fmtInt : fmtByUnit(k.unit));
  root.append(section('05', 'KPI instrument tiles', h('div', { class: 'grid-12' }, K.slice(0, 4).map((k, i) => h('div', { class: 'span-3' }, kpiTile(k, { format: fmtFor(k), deltaFormat: k.unit === '%' ? fmtPts : fmtFor(k), sparkline, scale: i === 0 ? { min: 0.9, max: 1 } : undefined }))))));

  // ------------------------------------------------------------------ 06 cards + controls
  const tabsHost = h('div', { class: 'mt-2 t-14 muted' }, 'Selected: overview');
  const segOut = h('span', { class: 'mono t-12 faint' }, 'lumpy');
  root.append(section('06', 'Cards & controls', h('div', { class: 'grid-12' },
    card({ cls: 'span-4', bp: true, kicker: 'Card · blueprint corners', title: 'Hero card with registration marks', prov: 'DERIVED', body: h('p', { class: 't-14 muted' }, 'Radius 12, 1 px hairline, card surface. Use the corner marks sparingly — one hero card per screen.'), foot: [h('span', {}, 'Footer meta'), h('a', { class: 'card-link', href: '#' }, 'Action', icon('chevron-right'))] }),
    card({ cls: 'span-4', kicker: 'Tabs + segmented', title: 'Navigation inside a card', body: [tabs({ label: 'Demo tabs', value: 'overview', tabs: [{ id: 'overview', label: 'Overview' }, { id: 'drivers', label: 'Risk drivers', count: 4 }, { id: 'history', label: 'History' }], onChange: (v) => (tabsHost.textContent = `Selected: ${v}`) }), tabsHost, h('div', { class: 'row mt-3' }, segmented({ label: 'Demand class', value: 'lumpy', options: ['smooth', 'erratic', 'lumpy'].map((v) => ({ value: v, label: v })), onChange: (v) => (segOut.textContent = v) }), segOut)] }),
    card({ cls: 'span-4', kicker: 'Slider · drawer · tooltip · story', title: 'Interactive primitives', body: h('div', { class: 'stack-3' },
      slider({ label: 'Capital budget', min: 38e6, max: 54e6, step: 5e5, value: 44.5e6, format: (v) => fmtAED(v) }),
      h('div', { class: 'row-wrap' },
        h('button', { class: 'btn btn--sm', type: 'button', onclick: () => drawer({ kicker: 'Part number', title: 'GN-32-R014', body: h('p', { class: 'muted' }, 'Drawer content: evidence, charts and actions for one entity. Esc or the scrim closes it.') }).open() }, 'Open drawer'),
        h('button', { class: 'btn btn--sm', type: 'button', onclick: () => modal({ title: 'Modal dialog', body: h('p', { class: 'muted' }, 'Centred dialog for short confirmations and help.') }).open() }, 'Open modal'),
        h('button', { class: 'btn btn--sm', type: 'button', onpointerenter: (e) => tooltip.show(e, { title: 'GN-32-R014', rows: [['Risk', '91 / 100'], ['Stock', '2 @ AUH']] }), onpointermove: (e) => tooltip.move(e), onpointerleave: () => tooltip.hide() }, 'Hover tooltip'),
        h('button', { class: 'btn btn--sm', type: 'button', onclick: () => storyMode({ steps: [{ selector: '#kpi-demo', title: 'Story-mode step', body: 'A spotlight frames the element; the step card explains it.' }, { selector: '#table-demo', title: 'Second step', body: 'Arrow keys move between steps; Esc exits.' }], navigate: async () => {} }).start() }, 'Story overlay')
      )) })
  )));
  root.querySelector('.gallery-section:last-child .grid-12 > .card:nth-child(1)').id = 'kpi-demo';

  // ------------------------------------------------------------------ 07 table
  const P = D.parts.parts.filter((p) => p.cls === 'R').slice(0, 12);
  const tbl = dataTable({ caption: 'Demo parts table', columns: [{ key: 'pn', label: 'Part number', mono: true }, { key: 'desc', label: 'Description' }, { key: 'ata', label: 'ATA' }, { key: 'deadline', label: 'Deadline' }, { key: 'stock_total', label: 'Stock', num: true, format: fmtInt }, { key: 'unit_cost', label: 'Unit cost', num: true, format: (v) => fmtAED(v) }, { key: 'risk_score', label: 'Risk', num: true, render: (r) => pill(r.risk_level, String(Math.round(r.risk_score * 100))) }], rows: P, sort: { key: 'risk_score', dir: 'desc' }, maxHeight: 360 });
  tbl.id = 'table-demo';
  root.append(section('07', 'Dense data table', tbl));

  // ------------------------------------------------------------------ 08 charts
  const pols = D.policies.policies;
  const chartsGrid = h('div', { class: 'grid-12' });
  root.append(section('08', 'Charts (theme.js)', chartsGrid));
  const c1 = h('section', { class: 'card span-7' }), c2 = h('section', { class: 'card span-5' }), c3 = h('section', { class: 'card span-6' }), c4 = h('section', { class: 'card span-6' });
  chartsGrid.append(c1, c2, c3, c4);
  // pick the busiest consumable so the demo line has shape
  const pn = Object.entries(D.demand_history.series).filter(([k]) => k.includes('-C')).sort((a, b) => b[1].reduce((s, v) => s + v, 0) - a[1].reduce((s, v) => s + v, 0))[0][0];
  const series = (D.demand_history.series[pn] || []).map((y, x) => ({ x, y }));
  const roll = series.map((d, i) => { const w = series.slice(Math.max(0, i - 7), i + 1).map((v) => v.y); const m = w.reduce((s, v) => s + v, 0) / w.length; const sd = Math.sqrt(w.reduce((s, v) => s + (v - m) ** 2, 0) / w.length); return { x: d.x, y: +m.toFixed(2), lo: Math.max(0, m - sd), hi: m + sd }; });
  const f1 = chartFrame(c1, { headline: `${pn} demand is steady with a seasonal swing — the 8-week mean tracks it closely`, subtitle: 'Units per week · weeks 0–103 · 8-week mean ± 1 rolling s.d. · simulated calendar', provenance: 'SIMULATED', source: 'demand_history.json', table: { columns: [{ key: 'x', label: 'Week', format: fmtWeek }, { key: 'y', label: 'Qty', num: true }], rows: series } });
  const peak = series.reduce((a, b) => (b.y > a.y ? b : a), series[0]);
  lineChart(f1.body, { series: [{ id: 'weekly', label: 'Weekly', values: series, color: 'rgba(185,200,214,0.4)', primary: false, width: 1, curve: window.d3.curveLinear }, { id: 'mean', label: '8-wk mean', values: roll.map(({ x, y }) => ({ x, y })), color: theme.color.accent, primary: true }], bandColor: theme.color.accent, band: roll.map(({ x, lo, hi }) => ({ x, lo, hi })), x: { format: fmtWeek }, y: { format: fmtInt }, annotation: { x: peak.x, y: peak.y, title: `Peak W${peak.x}`, sub: `${peak.y} units` } });
  const f2 = chartFrame(c2, { headline: 'P2 halves AOG hours versus legacy rules', subtitle: 'AOG hours / year · mean and 95% CI · 20 paired holdout seeds', provenance: 'SIMULATED', source: 'policies.json' });
  dotWhiskerChart(f2.body, { rows: pols.map((p) => ({ key: p.policy_id, label: `${p.policy_id} · ${p.label}`, value: p.kpi.aog_hours.mean, lo: p.kpi.aog_hours.ci_lo, hi: p.kpi.aog_hours.ci_hi, highlight: p.policy_id === 'P2' })), format: fmtHours, domain: [0, 500] });
  const f3 = chartFrame(c3, { headline: 'BOM carries the highest exposure of any outstation', subtitle: 'Risk score · 0–1 · per station', provenance: 'SIMULATED', source: 'network.json' });
  barList(f3.body, { rows: D.network.stations.slice().sort((a, b) => b.risk - a.risk).map((s) => ({ label: `${s.station} · ${s.name.split(',')[0]}`, value: s.risk, highlight: s.station === 'BOM' })), format: (v) => fmtPct(v, 0), max: 1 });
  const f4 = chartFrame(c4, { headline: 'Observable Plot, styled by the theme', subtitle: `Weekly demand · ${pn} · Plot.rectY + ruleY`, provenance: 'SIMULATED', source: 'demand_history.json' });
  const drawPlot = () => { f4.body.replaceChildren(plot({ width: f4.body.clientWidth, height: 220, y: { grid: false, label: null }, x: { label: 'week →' }, marks: [window.Plot.rectY(series, { x1: (d) => d.x, x2: (d) => d.x + 0.8, y: 'y', fill: theme.color.accent, fillOpacity: 0.8 }), window.Plot.ruleY([0], { stroke: theme.color.lineStrong })] })); };
  drawPlot();

  // ------------------------------------------------------------------ 09 map
  const mapHost = h('div');
  const replay = h('button', { class: 'btn btn--sm', type: 'button' }, icon('play'), 'Animate AUH → BOM');
  root.append(section('09', 'Network map (map.js)', card({ bp: true, kicker: 'd3-geo · Natural Earth 110m · REAL coordinates', title: 'Hub-and-spoke network', actions: replay, body: mapHost, prov: 'REAL' })));
  const map = await renderNetworkMap(mapHost, { stations: D.network.stations, arcs: D.network.arcs, selected: 'BOM', labelSub: (s) => (s.role === 'hub' ? 'HUB' : `${s.serviceable_units} u`) });
  replay.onclick = () => map.animateTransfer('AUH', 'BOM', { kind: 'emergency' });

  // ------------------------------------------------------------------ 10 illustrations
  const topHost = h('div', { class: 'bp-figure bp-figure--grid' });
  const compactHost = h('div', { style: { maxWidth: '420px' } });
  const sideHost = h('div', { class: 'bp-figure bp-figure--grid' });
  const frontHost = h('div', { class: 'bp-figure bp-figure--grid' });
  root.append(section('10', 'Original illustrations', h('div', { class: 'stack-3' },
    card({ bp: true, kicker: 'blueprint-aircraft-top.svg · full sheet (≥ 1000 px)', title: 'Plan view with ATA hotspots — click a callout', body: topHost }),
    h('div', { class: 'grid-12' },
      card({ cls: 'span-4', kicker: 'compact mode (< 1000 px)', title: 'Badges on the airframe', body: compactHost }),
      h('div', { class: 'span-8 stack-3' }, card({ kicker: 'blueprint-aircraft-side.svg', body: sideHost }), card({ kicker: 'blueprint-aircraft-front.svg', body: frontHost }))
    )
  )));
  await blueprintAircraft(topHost, { active: '32', compactBelow: 900 });
  await blueprintAircraft(compactHost, { active: '27' });
  sideHost.append(await inlineSVG('blueprint-aircraft-side.svg'));
  frontHost.append(await inlineSVG('blueprint-aircraft-front.svg'));

  const exGrid = h('div', { class: 'grid-12' });
  root.append(section('11', 'Exploded diagrams (label slots filled from parts.json)', exGrid));
  for (const ata of ['21', '24', '27', '29', '32', '34', '36', '49']) {
    const host = h('div', { class: 'bp-figure' });
    exGrid.append(card({ cls: 'span-6', kicker: `exploded-${ata}.svg`, body: host }));
    const svg = await inlineSVG(`exploded-${ata}.svg`);
    const ps = D.parts.parts.filter((p) => p.ata === ata).sort((a, b) => b.risk_score - a.risk_score);
    fillExploded(svg, [1, 2, 3, 4, 5].map((slot, i) => ({ slot, pn: ps[i]?.pn })));
    host.append(svg);
  }
  const lcHost = h('div', { class: 'bp-figure' });
  const lcV = h('div', { class: 'bp-figure', style: { maxWidth: '360px' } });
  root.append(section('12', 'Rotable lifecycle', h('div', { class: 'grid-12' }, card({ cls: 'span-8', kicker: 'rotable-lifecycle.svg', body: lcHost }), card({ cls: 'span-4', kicker: 'rotable-lifecycle-vertical.svg (narrow)', body: lcV }))));
  for (const [host, name] of [[lcHost, 'rotable-lifecycle.svg'], [lcV, 'rotable-lifecycle-vertical.svg']]) { const svg = await inlineSVG(name); fillLifecycle(svg, D.rotables.lifecycle); host.append(svg); }

  // ------------------------------------------------------------------ 13 states + footer
  root.append(section('13', 'States, notes & footer', h('div', { class: 'grid-12' }, card({ cls: 'span-4', title: 'Loading', body: stateBlock('loading') }), card({ cls: 'span-4', title: 'Empty', body: stateBlock('empty', 'No exceptions match this filter.') }), card({ cls: 'span-4', title: 'Error', body: stateBlock('error', 'This export could not be loaded.') })), h('div', { class: 'mt-3' }, stubNote('Stub note: marks a placeholder area a screen agent will replace.'))));
  root.append(h('div', { class: 'mt-8' }, disclaimer({ meta: 'Falcon Hub Airways is fictional' })));
  document.documentElement.dataset.ready = 'true';
}

main().catch((e) => { console.error(e); root.append(stateBlock('error', e.message)); document.documentElement.dataset.ready = 'true'; });
