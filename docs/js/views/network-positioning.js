/**
 * 05 · Network Positioning
 * Data: network.json (+ policies.json for split / seed labels).
 * Deep links: #/network?station=BOM&metric=aog_hours
 *
 * Sections
 *  1. Hero: Europe–Middle East–Asia map (geodesic arcs from AUH, nodes sized by stock, coloured by
 *     risk with icon + text) + station drill-down panel
 *  2. Scenario replay of simulated transfers (animated arc; reduced motion respected by map.js)
 *  3. P0 / P1 / P2 by station (holdout, CIs) + the hub-vs-outstation finding built from data
 *  4. Station table
 * Coordinates are REAL (OurAirports); everything else is SIMULATED. Numbers come from the JSON only.
 */
import { h, icon, pageHead, card, provChip, pill, dataTable, drawer, intro3, scopeLine, slidingThumb } from '../ui.js';
import { morphStore, morph, morphAxis, drawIn, liveDraw } from './forecast-lab/morph.js';
import { MOTION } from '../lib/motion.js';
import { term, termText } from '../lib/glossary.js';
import { isSimple, byMode } from '../lib/mode.js';
import { nameTag, displayName } from '../lib/names.js';
import { renderNetworkMap } from '../charts/map.js';
import { chartFrame, responsive, svgIn, axisBottom, directLabel, annotate, withTooltip, truncate, theme, fmtAED, fmtInt, fmtPct, fmtHours, fmtNum, fmtWeek, reducedMotion } from '../charts/theme.js';

export const data = ['network', 'policies', 'frontier'];

const d3 = () => window.d3;
let MS = morphStore(); // v2.1 motion: previous mark positions per chart (reset each render)
/** directLabel whose colour wins over the .gnm-label CSS fill. */
const dl = (g, o) => directLabel(g, o).style('fill', o.color || null);
const C = theme.color;
const HPW = 168;
const POLS = ['P0', 'P1', 'P2'];
const SR = theme.series;
// P0 = baseline (copper), P1 = other comparison (slate), P2 = the network policy (bright titanium, filled).
// Not teal: teal is the P2 core plan site-wide, and I125 has no per-station holdout breakdown (wave 4, C5).
const POL_COLOR = { P0: SR.baseline, P1: SR.context, P2: SR.neutral };

let cssLoaded = false;
function loadCSS() {
  if (cssLoaded || document.querySelector('link[data-view-css="network-positioning"]')) { cssLoaded = true; return; }
  const l = document.createElement('link');
  l.rel = 'stylesheet';
  l.href = new URL('../../css/views/network-positioning.css', import.meta.url).href;
  l.dataset.viewCss = 'network-positioning';
  document.head.append(l);
  cssLoaded = true;
}

// ----------------------------------------------------------------------------- helpers
const num = (v) => (v == null || v === '' || Number.isNaN(+v) ? null : +v);
/** A3 display names: short in charts; Expert mode adds the code in plain-text contexts (SVG, headlines). */
const pn = (code) => (isSimple() ? displayName(code, { mode: 'short' }) : `${displayName(code, { mode: 'short' })} (${code})`);
const pnS = (code) => displayName(code, { mode: 'short' });
/** "outstation" in plain English: "other airports (outstations)" on first use in Simple mode. */
function outTerm({ first = false, plural = true, cap = false } = {}) {
  if (!isSimple()) return term('outstation', { label: `${cap ? 'O' : 'o'}utstation${plural ? 's' : ''}`, first: false });
  const el = term('outstation', { label: `${cap ? 'O' : 'o'}ther airport${plural ? 's' : ''}`, first: false });
  if (first) el.append(' ', h('small', { class: 'term-expert' }, plural ? '(outstations)' : '(outstation)'));
  return el;
}
const OUT = () => byMode('other airports', 'outstations');
const EXPO = () => byMode('share of grounded time', 'material shortage exposure');
const HRS = () => byMode('hours grounded', 'AOG h');
/**
 * ONE denominator site-wide for a station's share: its hours planes waited for parts under the Simple Rulebook (P0,
 * 20 fresh test runs, per year) divided by the SAME hours summed over all stations (hub + outstations).
 * risk = P0 AOG / worst station, so risk / Σrisk is the same ratio when the per-policy hours are missing.
 */
let SHARE_TOT = null;
function setShareBase(stations) {
  const hrs = stations.map((s) => num(s.aog_hours_by_policy?.P0?.mean));
  SHARE_TOT = hrs.every((v) => v != null) ? { kind: 'h', tot: hrs.reduce((a, b) => a + b, 0) } : { kind: 'r', tot: stations.reduce((a, s) => a + (num(s.risk) ?? 0), 0) };
}
function shareOf(s) {
  if (!SHARE_TOT?.tot) return null;
  const v = SHARE_TOT.kind === 'h' ? num(s.aog_hours_by_policy?.P0?.mean) : num(s.risk);
  return v == null ? null : v / SHARE_TOT.tot;
}
const SHARE_NOTE = () => byMode(
  'Share = this airport\'s part of all hours planes waited for parts under the Simple Rulebook, across all 7 airports. It comes from the 20 fresh test runs.',
  'Share = the station\'s P0 holdout material AOG h/yr ÷ the sum over all 7 stations (hub + outstations), seeds 2000–2019, central. Every share on this page uses this denominator.');
/** The Network Plan's (P2) units and stock value at a station; serviceable_units in network.json is the I125 option. */
const p2Units = (s) => num(s.by_policy?.P2?.rotable_units) ?? num(s.serviceable_units);
const p2Value = (s) => num(s.by_policy?.P2?.stock_value_aed) ?? num(s.stock_value);
const prov = (o, f = 'SIMULATED') => o?.provenance || f;

/**
 * Outstation risk is rated against the riskiest OUTSTATION (exporter: outstation_risk_level / risk_vs_outstations),
 * not against the hub, so the riskiest outstation never wears a LOW pill while it has urgent shortfalls.
 * Fallback when the exporter field is missing: derive the same ratio from `risk`.
 */
let OUT_MAX = null;
let REC = { id: 'I125', pt: null }; // the recommended plan's network holdout result, for the module-level chart helpers
function setOutstationScale(stations) { OUT_MAX = Math.max(0, ...stations.filter((s) => s.role !== 'hub').map((s) => num(s.risk) ?? 0)) || null; }
function riskVsOut(s) {
  if (s.role === 'hub') return null;
  const v = num(s.risk_vs_outstations);
  if (v != null) return v;
  return OUT_MAX && num(s.risk) != null ? num(s.risk) / OUT_MAX : null;
}
function riskBand(s) {
  if (s.role !== 'hub') {
    const lv = String(s.outstation_risk_level || '').toLowerCase();
    if (['urgent', 'high'].includes(lv)) return 'high';
    // below the top band, outstations are compared in neutral (no amber/teal status: the map already carries teal + red)
    if (['review', 'medium', 'elevated', 'watch'].includes(lv)) return 'watch';
    if (['ok', 'low'].includes(lv)) return 'low';
    const rv = riskVsOut(s);
    if (rv != null) return rv >= 0.8 ? 'high' : rv >= 0.5 ? 'watch' : 'low';
  }
  const lvl = String(s.risk_level || '').toLowerCase();
  if (['urgent', 'high'].includes(lvl)) return 'high';
  if (['review', 'medium', 'elevated'].includes(lvl)) return 'review';
  if (['ok', 'low'].includes(lvl)) return 'ok';
  const r = num(s.risk);
  if (r == null) return 'unknown';
  return r > 0.66 ? 'high' : r > 0.33 ? 'review' : 'ok';
}
const RISK = {
  urgent: { word: 'HIGH', glyph: '▲', color: C.urgent, pill: 'urgent' }, // legacy key; stations use 'high' (wave C)
  // wave C: station exposure is a scale, not an exception: amber ring + ▲; red stays for urgent exceptions (pills, actions)
  high: { word: 'HIGH', glyph: '▲', color: C.review, pill: 'review' },
  review: { word: 'WATCH', glyph: '◆', color: C.review, pill: 'review' },
  ok: { word: 'LOW', glyph: '●', color: C.ok, pill: 'ok' },
  watch: { word: 'ELEVATED', glyph: '◆', color: SR.neutral, pill: 'unknown' }, // not WATCH: WATCH is amber review site-wide (wave 4, C4)
  low: { word: 'LOWER', glyph: '●', color: SR.context, pill: 'unknown' },
  unknown: { word: 'N/A', glyph: '○', color: C.unknown, pill: 'unknown' },
};

/** Risk pill text: outstations relative to the riskiest outstation, the hub on its own scale. */
function riskText(s, stations) {
  const b = RISK[riskBand(s)];
  // v2.1: one stated denominator (SHARE_NOTE): share of all stations' Simple Rulebook grounded hours
  const v = shareOf(s);
  const sh = v != null ? ` · ${fmtPct(v, 0)} of all` : '';
  const word = b.word.charAt(0) + b.word.slice(1).toLowerCase();
  return `${word}${s.role === 'hub' ? ' · hub' : ''}${sh}`;
}

/** {mean, lo, hi} for a metric on a policy_compare row, tolerant of several export shapes. */
function metric(row, key) {
  if (!row) return null;
  const v = row[key];
  if (v && typeof v === 'object' && !Array.isArray(v)) { const lo0 = num(v.ci_lo ?? v.lo); return { mean: num(v.mean), lo: lo0 == null ? null : Math.max(0, lo0), hi: num(v.ci_hi ?? v.hi), clamped: lo0 != null && lo0 < 0 }; }
  const mean = num(v);
  if (mean == null) return null;
  const short = key.replace('_hours', '').replace('_rate', '');
  const arr = row[`${key}_ci`] || row[`${short}_ci`] || null;
  const loRaw = num(arr?.[0] ?? row[`${key}_ci_lo`] ?? row[`${key}_lo`]);
  const lo = loRaw == null ? null : Math.max(0, loRaw); // t-CI can dip below 0 for near-zero means; quantities are non-negative
  const hi = num(arr?.[1] ?? row[`${key}_ci_hi`] ?? row[`${key}_hi`]);
  return { mean, lo, hi, clamped: loRaw != null && loRaw < 0 };
}

const METRICS = [
  { key: 'aog_hours', get label() { return byMode('Hours grounded / yr', 'AOG h / yr'); }, short: 'AOG h', fmt: fmtHours, better: 'lower' },
  { key: 'fill_rate', get label() { return byMode('On the shelf', 'Immediate fill'); }, short: 'Fill', fmt: (v) => fmtPct(v), better: 'higher' },
  { key: 'rotable_fill_rate', get label() { return byMode('Repairable on the shelf', 'Rotable fill'); }, short: 'Rot. fill', fmt: (v) => fmtPct(v), better: 'higher' },
];

function splitLabel(n, p) {
  const split = n.policy_compare_meta?.split || p?.split || n.meta?.split;
  const seeds = n.policy_compare_meta?.seeds || p?.seeds;
  const ns = n.policy_compare_meta?.n_seeds || p?.n_seeds;
  const range = Array.isArray(seeds) && seeds.length ? ` ${Math.min(...seeds)}–${Math.max(...seeds)}` : '';
  if (isSimple()) return split === 'holdout' || ns === 20 ? '20 fresh test runs' : 'simulated test runs';
  return split ? `${split[0].toUpperCase()}${split.slice(1)} seeds${range}${ns ? ` (${ns})` : ''}` : 'Simulated seeds';
}

// ----------------------------------------------------------------------------- view
export async function render(el, ctx) {
  loadCSS();
  // wait for the view stylesheet before building the DOM: an unstyled first paint shifts the layout (CLS)
  await new Promise((res) => { const l = document.querySelector('link[data-view-css="network-positioning"]'); if (!l || l.sheet) return res(); l.addEventListener('load', res, { once: true }); l.addEventListener('error', res, { once: true }); setTimeout(res, 3000); });
  MS = morphStore();
  const { network: n, policies: p, frontier: F } = ctx.data;
  const stations = n.stations || [];
  // the recommended plan's network-level holdout result (frontier.json); per-station holdout exists only for P0/P1/P2
  const recId = n.recommended_id || F?.recommended || 'I125';
  const fpt = (id) => { const q = (F?.points || []).find((x) => x.id === id); return q ? { aog: num(q.aog_hours ?? q.aog_hours_mean), cap: num(q.capital_aed) } : null; };
  const recPt = fpt(recId), p2Pt = fpt('P2');
  REC = { id: recId, pt: recPt, extra: recPt && p2Pt ? fmtAED(recPt.cap - p2Pt.cap) : null };
  setOutstationScale(stations);
  setShareBase(stations);
  const S = isSimple();
  const hub = stations.find((s) => s.role === 'hub') || stations[0];
  const byId = Object.fromEntries(stations.map((s) => [s.station, s]));
  const arcs = n.arcs || [];
  const pc = n.policy_compare || [];
  const pcBy = (pol, st) => pc.find((r) => r.policy_id === pol && r.station === st);
  let alive = true;
  let selected = byId[ctx.params.station] ? ctx.params.station : null;
  const cleanups = [];

  el.append(pageHead({
    num: '05', eyebrow: 'Network Positioning',
    title: byMode('Where the spares sit, and how fast they can move', 'Where the stock sits, and how fast it can move'),
    lede: S
      ? h('span', {}, `The ${hub ? hub.station : 'home'} base serves ${fmtInt(stations.length - 1)} `, outTerm({ first: true }), ` for Falcon Hub Airways (fictional). Bigger circles mean more time grounded there. Airport locations are real; the activity is simulated.`)
      : `${hub ? hub.station : 'The hub'} supports ${fmtInt(stations.length - 1)} outstations for Falcon Hub Airways (fictional). Node size is material shortage exposure, ring colour is its band (with icon and text), solid line weight is simulated transfer volume and dashed teal lines are proposed positioning. Station coordinates are real (OurAirports); the network activity is simulated.`,
    meta: [provChip('REAL'), provChip(prov(n.meta))],
  }));
  el.append(intro3({
    what: S
      ? `Which airports hold spares under the ${displayName('P2')}, our core plan, and where planes wait longest for parts.`
      : ['Station-level stock under the ', nameTag('P2'), ' (the core plan) versus the two comparators, with holdout ', term('aog_hours'), ' by station.'],
    why: S
      ? ['A spare in the wrong place is no help. A plane can sit grounded while the part travels from the ', term('hub'), '.']
      : 'Positioning decides how much transport time sits inside each AOG; the hub-vs-outstation split shows where stock pays.',
    action: S
      ? 'Keep the most urgent parts at the busiest other airports. Serve the rest from the home base.'
      : 'Hold D0 no-go stock at outstations where exposure and transport time justify it; cover D3/D10 from the hub.',
  }));

  // ---------------------------------------------------------------- 1. hero map + drill-down
  const maxUnits = Math.max(1, ...stations.map((s) => num(s.serviceable_units) ?? 0));
  const mapHost = h('div', { style: { minHeight: '260px' } });
  // keyboard selector for the map: visually hidden until it receives focus (the map nodes and the table select with the pointer)
  const picker = h('div', { class: 'np-picker', role: 'group', 'aria-label': 'Select a station' }, h('span', { class: 'np-picker-k', 'aria-hidden': 'true' }, byMode('Airports', 'Stations')));
  stations.forEach((s) => {
    const rb = RISK[riskBand(s)];
    picker.append(h('button', { type: 'button', 'aria-pressed': String(s.station === selected), dataset: { station: s.station }, onclick: () => choose(s.station, true) },
      h('span', { class: 'np-dot', style: { background: rb.color }, 'aria-hidden': 'true' }), `${s.station} · ${rb.word}`));
  });
  const mapCard = h('section', { class: 'card card--bp', dataset: { story: 'map' } });
  const totalTransfers = arcs.reduce((a, b) => a + (num(b.transfers) ?? 0), 0);
  const totalEmerg = arcs.reduce((a, b) => a + (num(b.emergency) ?? 0), 0);
  // wave A: proposed movements = where the recommended plan positions more rotables than P2 (its base), from AUH
  // wave C: proposed movements = where P2 (the core recommendation) holds more rotables than the P0 legacy policy
  const proposed = hub ? stations.filter((x) => x.role !== 'hub' && x.by_policy?.P2 && x.by_policy?.P0 && x.by_policy.P2.rotable_units > x.by_policy.P0.rotable_units)
    .map((x) => { const d = x.by_policy.P2.rotable_units - x.by_policy.P0.rotable_units; return { from: hub.station, to: x.station, label: S ? `+${fmtInt(d)} repairable spare${d === 1 ? '' : 's'} held here (Network Plan vs Simple Rulebook)` : `+${fmtInt(d)} rotable${d === 1 ? '' : 's'} held here (P2 vs P0)`, basis: S ? 'Network Plan placement (proposed, not a past transfer)' : 'P2 allocation (proposed, not a history transfer)' }; }) : [];
  const busiest = arcs.slice().sort((a, b) => (b.transfers ?? 0) - (a.transfers ?? 0))[0];
  const topRisk = stations.filter((s) => s.role !== 'hub').sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))[0];
  const topAll = stations.slice().sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))[0];
  const mapF = chartFrame(mapCard, {
    implication: byMode('Spares belong where a plane would wait longest for them, not spread evenly.', 'Stock belongs where an aircraft would wait longest for it, not evenly across stations.'),
    // wave 5 / v2.1: the headline speaks the Network Plan (P2, the core plan); node size stays the Simple Rulebook holdout share
    headline: topAll && topRisk && hub?.by_policy?.P2 && stations.every((x) => x.by_policy?.P2 && x.by_policy?.P0)
      ? (() => {
        const outs = stations.filter((x) => x.role !== 'hub');
        const o2 = outs.reduce((a, x) => a + x.by_policy.P2.rotable_units, 0), o0 = outs.reduce((a, x) => a + x.by_policy.P0.rotable_units, 0);
        if (S) {
          const a1 = `The Network Plan keeps ${fmtInt(o2)} repairable spares at other airports; the Simple Rulebook keeps ${fmtInt(o0)}`;
          return a1.length <= 90 ? a1 : `The Network Plan keeps ${fmtInt(o2)} spares at other airports, not ${fmtInt(o0)}`;
        }
        const a1 = `Network Plan (P2) holds ${fmtInt(o2)} outstation rotables, not ${fmtInt(o0)}; ${topRisk.station} is the riskiest outstation`;
        return a1.length <= 90 ? a1 : `Network Plan (P2) holds ${fmtInt(o2)} outstation rotables, not P0's ${fmtInt(o0)}`;
      })()
      : topAll && topRisk
        ? `${topAll.station} has the largest share of grounded time (${fmtPct(shareOf(topAll), 0)} of all stations)`
        : 'Hub-and-spoke network',
    subtitle: S
      ? `Circle size = share of grounded time under the Simple Rulebook. Ring = band. Solid lines = ${fmtInt(totalTransfers)} past transfers. Dashed teal = spares the Network Plan adds at other airports. Labels = Network Plan spares.`
      : `Node size = material shortage exposure (P0 holdout AOG h, share of all stations) · ring = exposure band · solid lines = ${fmtInt(totalTransfers)} history transfers (width = volume) · dashed teal = outstation rotables P2 adds over P0 · labels: P2 rotable units`,
    provenance: prov(n.meta), source: 'network.json → stations, arcs',
    table: { columns: [{ key: 'from', label: 'From' }, { key: 'to', label: 'To' }, { key: 'transfers', label: 'Transfers', num: true, format: fmtInt }, { key: 'emergency', label: 'Emergency', num: true, format: fmtInt }, { key: 'aog_transport_h', label: S ? 'Transport while grounded' : 'AOG transport', num: true, format: fmtHours }], rows: arcs },
  });
  // one legend row, two groups: ring = risk (only the bands present), line = transfer kind
  const bandsPresent = ['low', 'watch', 'ok', 'review', 'high', 'urgent'].filter((b) => stations.some((s) => riskBand(s) === b));
  mapF.body.append(mapHost, h('div', { class: 'np-map-foot' }, picker,
    h('div', { class: 'np-legend', 'aria-hidden': 'true' },
      h('span', { class: 'np-legend-k' }, byMode('Grounded-time ring', 'Exposure ring')),
      ...bandsPresent.map((b) => h('span', { style: { color: RISK[b].color } }, h('i', { class: 'np-ring' }), RISK[b].word.toLowerCase())),
      h('span', { class: 'np-legend-k' }, 'Movements'),
      h('span', { style: { color: SR.neutral } }, h('i', { class: 'np-line' }), byMode('past transfers', 'history transfers')),
      proposed.length ? h('span', { style: { color: theme.series.recommended } }, h('i', { class: 'np-line np-line--dash' }), byMode('Network Plan adds', 'P2 adds over P0')) : null,
      totalEmerg ? h('span', { style: { color: SR.urgent } }, h('i', { class: 'np-line' }), 'emergency (replay)') : null)),
    h('p', { class: 'np-note np-share-note', dataset: { role: 'share-note' } }, SHARE_NOTE()),
    scopeLine());
  const drill = h('section', { class: 'card', dataset: { story: 'station-drill' }, 'aria-live': 'polite' });
  // wave 4: the hub-vs-outstation finding sits under the map, so the left column matches the tall station panel (no dead space)
  const shareCard = h('section', { class: 'card', dataset: { story: 'network-hub-finding' } });
  el.append(h('div', { class: 'np-hero mt-3' }, h('div', { class: 'np-left' }, mapCard, shareCard), drill));

  const map = await renderNetworkMap(mapHost, {
    stations, arcs, selected, proposed,
    onSelect: (id) => { choose(id, false); openStation(id); },
    // sub-label sits directly under the IATA code: units, plus the risk word only when it is not low (no glyph, so it never reads as another airport)
    labelSub: (s) => { const b = riskBand(s); const risk = b === 'ok' || b === 'low' ? '' : ` · ${RISK[b].word}`; return `${fmtInt(p2Units(s))} u${risk}`; },
    // wave A: node size = material shortage exposure (P0 holdout AOG h vs the worst station); units are in the label
    nodeRadius: (s) => 4.5 + 11 * Math.sqrt(Math.max(0, num(s.risk) ?? 0)),
    nodeColor: (s) => RISK[riskBand(s)].color,
    nodeAria: (s) => `${s.station} ${s.name || ''}: ${fmtInt(p2Units(s))} Network Plan repairable units, material shortage exposure ${RISK[riskBand(s)].word}, ${fmtPct(shareOf(s), 0)} of all stations`,
    tooltipRows: (s) => [['Role', S ? (s.role === 'hub' ? 'home base' : 'other airport') : s.role], [S ? 'Network Plan spares' : 'P2 rotable units', fmtInt(p2Units(s))], [S ? 'Value of those spares' : 'P2 stock value', fmtAED(p2Value(s))], ['Requests', fmtInt(s.requests)], [S ? 'Share of grounded time' : 'Material shortage exposure', `${RISK[riskBand(s)].glyph} ${riskText(s, stations)}`]],
    label: 'Network map of Falcon Hub Airways (fictional) stations',
    // the hub's arcs leave to the west and east; its label block sits above-right, clear of them and of the Gulf outstations
    labelOffsets: hub ? { [hub.station]: [12, -30, 'start'] } : {},
    // v2.1 addendum: each node gets an invisible, pointer-transparent frame centred on the node and enclosing its label
    // and the hub's radar pulse. The node's box is then centred on the node (a click at its centre lands on the node,
    // not on the land between node and label) and constant while the pulse animates. One getBBox per node per draw.
    onDraw: ({ svg }) => {
      svg.selectAll('g[data-station]').each(function () {
        const g = d3().select(this);
        g.select('rect.np-node-frame').remove();
        const b = this.getBBox();
        const hw = Math.max(30, Math.abs(b.x), Math.abs(b.x + b.width)), hh = Math.max(30, Math.abs(b.y), Math.abs(b.y + b.height));
        g.insert('rect', ':first-child').attr('class', 'np-node-frame').attr('x', -hw).attr('y', -hh).attr('width', 2 * hw).attr('height', 2 * hh).attr('fill', 'none').attr('pointer-events', 'none');
      });
    },
  });
  cleanups.push(() => map.destroy());
  if (!alive) return () => {};

  /** Station details drawer (every map station is clickable); the full panel stays on the page. */
  let stDrawer = null;
  function openStation(id) {
    const s = byId[id];
    if (!s) return;
    stDrawer?.close?.();
    const rb = RISK[riskBand(s)];
    const row = (k, v) => [h('dt', {}, k), h('dd', {}, v)];
    const u = s.by_policy || {};
    stDrawer = drawer({
      kicker: s.role === 'hub' ? byMode('Home base (hub)', 'Hub station') : byMode('Other airport', 'Outstation'), title: `${s.station} · ${s.name || ''}`, persistOnParams: true,
      body: h('div', { class: 'stack-3' },
        h('div', { class: 'row-wrap' }, pill(rb.pill, riskText(s, stations)), provChip(prov(n.meta))),
        h('dl', { class: 'meta-list' },
          ...row(S ? 'Network Plan spares (core plan)' : 'Network Plan (P2) rotable units (core plan)', fmtInt(p2Units(s))),
          ...row(S ? 'Value of those spares' : 'P2 stock value', fmtAED(p2Value(s))),
          ...row(S ? 'Share of grounded time' : 'Material shortage exposure', `${fmtPct(shareOf(s), 0)} of all 7 stations`),
          ...row(S ? 'Requests (2 years of history)' : 'Requests (2-yr history)', fmtInt(s.requests)),
          ...(s.aog_hours_hist != null ? row(S ? 'Hours grounded · 2 years of history (Simple Rulebook)' : 'AOG h · W0–W103 history (2 yr, P0)', fmtHours(s.aog_hours_hist)) : []),
          ...(u.P2 ? row(S ? 'Spares by plan' : 'Units by plan', ['P0', 'P1', 'P2', recId].filter((k) => u[k]).map((k) => `${pnS(k)} ${fmtInt(u[k].rotable_units)}`).join(' · ')) : [])),
        h('p', { class: 't-12 faint m-0' }, SHARE_NOTE()),
        h('p', { class: 't-12 faint m-0' }, byMode('Simulated planning snapshot. The station panel on this page compares the plans, with likely ranges.', 'Simulated planning snapshot. The station panel on this page has the policy comparison with intervals.'))),
      foot: [h('a', { class: 'btn btn--sm', href: ctx.buildHash('parts', { station: s.station }) }, byMode('Parts at this airport', 'Parts at this station'), icon('chevron-right'))],
    }).open();
  }
  function choose(id, fromPicker) {
    selected = id;
    if (fromPicker) map.select(id);
    picker.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.station === id)));
    ctx.setParams({ station: id });
    renderDrill();
  }

  function renderDrill() {
    const s = byId[selected] || null;
    drill.replaceChildren();
    drill.dataset.story = s ? `network-${s.station.toLowerCase()}` : 'station-drill';
    if (!s) {
      const ranked = stations.slice().sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0));
      drill.append(h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, byMode('Airport details', 'Station drill-down')), h('h3', { class: 'card-title' }, byMode('Pick an airport on the map or below', 'Select a station on the map or below'))), provChip(prov(n.meta))),
        h('p', { class: 'muted t-14' }, S
          ? 'Each airport shows its spares, requests, share of grounded time, transfers and how the three plans do there.'
          : ['Each station shows its P2 units, request volume, material shortage exposure, transfer traffic and how ', nameTag('P0'), ', ', nameTag('P1'), ' and ', nameTag('P2'), ' perform there.']),
        h('div', { class: 'np-sub' }, byMode('Largest share of grounded time first', 'Highest material shortage exposure first')),
        h('div', { class: 'np-rank' }, ranked.map((x) => h('button', { type: 'button', class: 'np-rank-item', onclick: () => choose(x.station, true) },
          h('span', { class: 'np-rank-name' }, h('span', { class: 'mono' }, x.station), h('span', { class: 'faint t-12' }, x.name || '')), pill(RISK[riskBand(x)].pill, riskText(x, stations))))));
      return;
    }
    const rb = RISK[riskBand(s)];
    const inbound = arcs.filter((a) => a.to === s.station), outbound = arcs.filter((a) => a.from === s.station);
    const tIn = inbound.reduce((a, b) => a + (num(b.transfers) ?? 0), 0), tOut = outbound.reduce((a, b) => a + (num(b.transfers) ?? 0), 0);
    const eIn = inbound.reduce((a, b) => a + (num(b.emergency) ?? 0), 0);
    const aogT = inbound.find((a) => a.from === hub?.station)?.aog_transport_h;
    const fact = (label, value) => h('div', { class: 'np-fact' }, h('div', { class: 'np-fact-label' }, label), h('div', { class: 'np-fact-value' }, value));
    const polRows = POLS.map((pol) => ({ pol, aog: metric(pcBy(pol, s.station), 'aog_hours'), fill: metric(pcBy(pol, s.station), 'fill_rate'), rfill: metric(pcBy(pol, s.station), 'rotable_fill_rate') }));
    const bestAog = polRows.filter((r) => r.aog?.mean != null).sort((a, b) => a.aog.mean - b.aog.mean)[0];
    // CI on its own line, one unit ("159–423 h", "98.6–98.9%"), never wrapping (wave 4)
    const ci = (m, fmt) => {
      if (m?.lo == null || m?.hi == null) return null;
      const a = fmt(m.lo), b = fmt(m.hi), sa = a.match(/[^\d.,]+$/)?.[0], sb = b.match(/[^\d.,]+$/)?.[0];
      return h('span', { class: 'ci' }, sa && sa === sb ? `${a.slice(0, -sa.length).trim()}–${b}` : `${a}–${b}`);
    };
    const hasR = polRows.some((r) => r.rfill?.mean != null);
    function recRow(st) {
      const u = st.by_policy?.[recId]?.rotable_units, u2 = st.by_policy?.P2?.rotable_units;
      if (u == null) return null;
      const d = u2 != null ? u - u2 : null;
      return h('tr', { class: 'is-opt', dataset: { pol: recId } },
        h('td', {}, nameTag(recId), h('span', { class: 'np-best' }, byMode(' extra option', ' frontier option'))),
        h('td', { colspan: hasR ? 3 : 2, class: 'np-rec-note' }, S
          ? `${fmtInt(u)} spares here${d != null ? ` (${d === 0 ? 'same as the Network Plan' : `${d > 0 ? '+' : '−'}${fmtInt(Math.abs(d))} vs the Network Plan`})` : ''}. Not tested airport by airport${recPt ? `. Whole network: ${fmtHours(recPt.aog)} a year, vs ${fmtHours(p2Pt?.aog)} for the Network Plan` : ''}.`
          : `${fmtInt(u)} rotables here${d != null ? ` (${d === 0 ? 'same as P2' : `${d > 0 ? '+' : '−'}${fmtInt(Math.abs(d))} vs P2`})` : ''}. Per-station holdout not run${recPt ? `; network ${fmtHours(recPt.aog)}/yr vs P2 ${fmtHours(p2Pt?.aog)}` : ''}.`));
    }
    drill.append(
      h('div', { class: 'np-drill-head' },
        h('div', {}, h('div', { class: 'card-kicker' }, s.role === 'hub' ? byMode('Home base (hub)', 'Hub station') : byMode('Other airport (outstation)', 'Outstation')), h('div', { class: 'np-drill-code' }, s.station), h('div', { class: 'np-drill-name' }, s.name || '')),
        h('div', { class: 'row', style: { flexWrap: 'wrap' } }, pill(rb.pill, `${riskText(s, stations)}`), provChip(prov(n.meta)))),
      h('div', { class: 'np-facts' },
        fact(byMode('Network Plan spares', 'P2 rotable units'), fmtInt(p2Units(s))),
        fact(byMode('Value of those spares', 'P2 stock value'), fmtAED(p2Value(s))),
        fact(byMode('Share of grounded time', 'Exposure share'), `${fmtPct(shareOf(s), 0)} of all`),
        fact(byMode('Requests (history)', 'Requests (history)'), `${fmtInt(s.requests)}${s.requests_d0 != null && !S ? ` · ${fmtInt(s.requests_d0)} D0` : ''}`),
        s.role === 'hub' ? fact('Transfers out', fmtInt(tOut)) : fact('Transfers in', `${fmtInt(tIn)}${eIn ? (S ? ` (${fmtInt(eIn)} urgent)` : ` (${fmtInt(eIn)} AOG)`) : ''}`),
        ...(aogT != null ? [fact(byMode('Transport time from the home base', 'AOG transport from hub'), fmtHours(aogT))] : []),
        // wave 5: a two-year history TOTAL, labelled so it is never read as the holdout's per-year figure
        ...(s.aog_hours_hist != null ? [fact(byMode('Hours grounded · 2 years of history', 'AOG h · W0–W103 history (2 yr, P0)'), `${fmtHours(s.aog_hours_hist)}${s.aog_events_hist != null ? (S ? ` · ${fmtInt(s.aog_events_hist)} times` : ` · ${fmtInt(s.aog_events_hist)} ev`) : ''}`)] : []),
        ...(s.role === 'hub' ? [fact(byMode('Other airports served', 'Outstations served'), fmtInt(outbound.length))] : [])),
      s.by_policy ? h('div', { class: 'np-sub' }, byMode('Repairable spares kept here, by plan', 'Rotable units positioned here, by plan')) : null,
      s.by_policy ? h('div', { class: 'np-units' }, Object.entries(s.by_policy).map(([k, v]) => h('div', { class: `np-unit ${k === 'P2' ? 'is-rec' : ''}` }, h('span', { class: 'np-unit-k', title: displayName(k) }, k === 'P2' ? `${pnS(k)} · core` : k === n.recommended_id ? `${pnS(k)} · option` : pnS(k)), h('span', { class: 'np-unit-v' }, fmtInt(v.rotable_units)), h('span', { class: 'np-unit-s' }, fmtAED(v.stock_value_aed))))) : null,
      h('div', { class: 'np-sub' }, S ? `The plans at ${s.station} · ${splitLabel(n, p)} · average and likely range` : `P0 / P1 / P2 / ${recId} at ${s.station} · ${splitLabel(n, p)} · mean, 95% CI`),
      polRows.some((r) => r.aog || r.fill)
        ? h('table', { class: 'np-pol' },
          h('caption', { class: 'sr-only' }, `Policy comparison at ${s.station}`),
          h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, byMode('Plan', 'Policy')), h('th', { scope: 'col' }, byMode('Hours grounded / yr', 'AOG h/yr')), h('th', { scope: 'col' }, byMode('On shelf', 'Fill')), hasR ? h('th', { scope: 'col' }, byMode('Repairable on shelf', 'Rot. fill')) : null)),
          h('tbody', {}, polRows.map((r) => h('tr', { class: [bestAog && r.pol === bestAog.pol ? 'is-best' : '', r.pol === 'P2' ? 'is-rec' : ''].filter(Boolean).join(' ') },
            h('td', {}, nameTag(r.pol, { mode: 'short' }), r.pol === 'P2' ? h('span', { class: 'np-best' }, ' core plan') : bestAog && r.pol === bestAog.pol ? h('span', { class: 'np-best' }, byMode(' fewest hours', ' lowest AOG')) : null),
            h('td', {}, r.aog ? fmtHours(r.aog.mean) : 'not run', ci(r.aog, fmtHours)),
            h('td', {}, r.fill ? fmtPct(r.fill.mean) : 'not run', ci(r.fill, (v) => fmtPct(v))),
            hasR ? h('td', {}, r.rfill ? fmtPct(r.rfill.mean) : '—', ci(r.rfill, (v) => fmtPct(v))) : null)),
            // wave 5: the recommended plan's row, with the data that exists. I125 was simulated on the holdout for network
            // totals only, so its per-station AOG is not invented: units here vs P2, and the network result.
            recRow(s)))
        : h('div', { class: 'state' }, 'Policy comparison not run'),
      polRows.some((r) => r.aog) ? scopeLine() : null,
      ...(polRows.some((r) => r.aog?.clamped || r.fill?.clamped || r.rfill?.clamped) ? [h('p', { class: 'np-note' }, byMode('Ranges that dip below 0 are shown from 0.', 'CI lower ends below 0 are shown as 0 (t-interval on a near-zero mean).'))] : []),
      h('div', { class: 'np-link' }, h('a', { class: 'card-link', href: ctx.buildHash('parts', { station: s.station }) }, byMode('Parts at this airport', 'Parts at this station'), icon('chevron-right'))),
    );
  }
  renderDrill();

  // ---------------------------------------------------------------- 2. replay
  const replayCard = h('section', { class: 'card mt-3', dataset: { story: 'network-replay' } });
  el.append(replayCard);
  cleanups.push(renderReplay(replayCard, n, map, byId, () => alive));

  // ---------------------------------------------------------------- 3. P0/P1/P2 by station
  const cmpGrid = h('div', { class: 'grid-12 mt-3' });
  el.append(cmpGrid);
  const cmpCard = h('section', { class: 'card span-12', dataset: { story: 'network-policy' } });
  cmpGrid.append(cmpCard);
  cleanups.push(renderCompare(cmpCard, n, p, stations, pcBy, ctx));
  cleanups.push(renderShare(shareCard, n, p, stations, pcBy, hub));

  // ---------------------------------------------------------------- 4. station table
  el.append(h('div', { class: 'mt-3' }, card({
    kicker: byMode('Airports', 'Stations'), title: byMode('Network Plan spares and share of grounded time, by airport', 'Network Plan (P2) stock and material shortage exposure by station'), prov: prov(n.meta),
    body: h('div', {}, dataTable({
      caption: 'Stations', dense: true,
      columns: [
        { key: 'station', label: byMode('Airport', 'Station'), mono: true },
        { key: 'role_t', label: 'Role' },
        { key: 'p2_units', label: byMode('Spares (Network Plan)', 'P2 units'), short: 'Units', num: true, format: fmtInt },
        { key: 'p2_value', label: byMode('Value (Network Plan)', 'P2 stock value'), short: 'Stock', num: true, format: (v) => fmtAED(v) },
        { key: 'requests', label: 'Requests', num: true, format: fmtInt },
        { key: 'risk', label: byMode('Share of grounded time', 'Shortage exposure'), short: 'Exposure', render: (s) => pill(RISK[riskBand(s)].pill, riskText(s, stations)) },
      ],
      rows: stations.map((s) => ({ ...s, role_t: S ? (s.role === 'hub' ? 'home base' : 'other airport') : s.role, p2_units: p2Units(s), p2_value: p2Value(s) })), sort: { key: 'risk', dir: 'desc' }, onRowClick: (s) => choose(s.station, true),
      mobileColumns: ['station', 'risk', 'p2_value', 'p2_units'], stickyFirst: true,
    }), h('p', { class: 'np-note' }, SHARE_NOTE()), scopeLine()),
  })));

  return () => { alive = false; cleanups.forEach((fn) => { try { fn?.(); } catch { /* ignore */ } }); };
}

// ============================================================================= replay
function renderReplay(host, n, map, byId, isAlive) {
  const tr = n.transfer_replay || {};
  const fo = tr.focus || null;
  const events = (tr.events || []).filter((e) => byId[e.from] && byId[e.to]).map((e, i) => ({
    ...e, i,
    planted: e.planted || (e.focus && fo?.planted) || null,
    aog_transport_h: e.aog_transport_h ?? (e.arrive_h != null ? e.arrive_h - e.t_h : null),
    note: e.focus && fo ? `${fo.desc || ''} for ${fo.tail || 'a tail'} · ${byMode('grounded', 'AOG')} ${fmtHours(fo.aog_hours)}` : null,
  }));
  const featured = events.find((e) => e.focus) || events.find((e) => e.planted) || events.find((e) => e.kind === 'emergency') || events[0];
  let cur = featured;
  const nEm = events.filter((e) => e.kind === 'emergency').length;
  const win = tr.window_h || [];
  const f = chartFrame(host, {
      implication: byMode('Each emergency transfer is a part that was in the wrong place, with a plane waiting.', 'Each emergency transfer is the cost of an unpositioned part: an aircraft waiting on the ground.'),
    headline: featured && isSimple()
      ? `${featured.from}→${featured.to} ${featured.kind === 'emergency' ? 'emergency' : 'routine'} transfer${featured.aog_transport_h != null ? ` took ${fmtHours(featured.aog_transport_h)}` : ''}; ${fmtInt(nEm)} of ${fmtInt(events.length)} replayed transfers were emergencies`
      : featured
      ? `${featured.planted ? `${featured.planted}: ` : ''}${featured.from}→${featured.to} ${featured.kind === 'emergency' ? 'emergency' : 'routine'} transfer${featured.aog_transport_h != null ? ` took ${fmtHours(featured.aog_transport_h)}` : ''}; ${fmtInt(nEm)} of ${fmtInt(events.length)} replayed transfers were emergencies`
      : 'No transfers exported for replay',
    subtitle: isSimple()
      ? `Simulated past transfers${featured?.pn ? ` around part ${featured.pn}` : ''}. One dot per transfer; each row is the airport it went to. Red = emergency.${reducedMotion() ? ' Reduced motion: arcs flash.' : ''}`
      : `Simulated history transfers${win.length === 2 ? ` ${fmtWeek(Math.floor(win[0] / HPW))}–${fmtWeek(Math.floor(win[1] / HPW))} (sim h ${fmtInt(win[0])}–${fmtInt(win[1])})` : ''}${featured?.pn ? ` · featured part ${featured.pn}` : ''} · one dot per transfer, row = destination · red = emergency${reducedMotion() ? ' · reduced motion: arcs flash' : ''}`,
    provenance: prov(tr, prov(n.meta)), source: 'network.json → transfer_replay',
    table: { columns: [{ key: 't_h', label: 'Week', format: (v) => fmtWeek(Math.floor(v / HPW)) }, { key: 'pn', label: 'PN' }, { key: 'from', label: 'From' }, { key: 'to', label: 'To' }, { key: 'kind', label: 'Kind' }, { key: 'planted', label: 'Planted', format: (v) => v || '' }], rows: events },
  });
  if (!events.length) { f.body.append(h('div', { class: 'state' }, 'not run')); return null; }
  const sel = h('select', { class: 'select', 'aria-label': 'Choose a transfer to replay' }, events.map((e) => h('option', { value: String(e.i) }, `${fmtWeek(Math.floor(e.t_h / HPW))} · ${e.pn} · ${e.from}→${e.to} · ${e.kind}${e.planted ? ` · ${e.planted}` : ''}`)));
  sel.value = String(cur.i);
  const playBtn = h('button', { class: 'btn btn--primary btn--sm', type: 'button' }, icon('play'), 'Replay transfer');
  const allBtn = h('button', { class: 'btn btn--sm', type: 'button', 'aria-pressed': 'false' }, icon('route'), 'Replay all');
  const info = h('div', { class: 'np-event', role: 'status', 'aria-live': 'polite' });
  f.body.before(h('div', { class: 'np-replay-bar' }, sel, playBtn, allBtn));
  const strip = h('div', { class: 'np-strip' });
  f.body.append(strip, info);
  if (fo?.timeline?.length) {
    f.body.append(h('div', { class: 'np-sub' }, isSimple() ? `What happened, hour by hour · ${fo.pn} at ${fo.station}` : `${fo.planted ? `${fo.planted} · ` : ''}${fo.incident_id || 'Incident'} timeline · ${fo.pn} at ${fo.station} · hours from removal`),
      h('ol', { class: 'np-timeline' }, fo.timeline.map((t) => h('li', { class: `is-${t.step || 'event'}` }, h('span', { class: 'np-tl-t mono' }, `T+${fmtNum(t.t_h, 0)} h`), h('span', { class: 'np-tl-st mono' }, t.station || ''), h('span', { class: 'np-tl-ev' }, t.event)))));
  }
  const setInfo = (e) => {
    info.className = `np-event ${e.kind === 'emergency' ? 'is-emergency' : ''}`;
    info.replaceChildren(...[
      e.kind === 'emergency' ? pill('urgent', byMode('Emergency (plane grounded)', 'Emergency (AOG)')) : pill('ok', 'Routine'),
      h('span', { class: 'mono' }, `${fmtWeek(Math.floor(e.t_h / HPW))} · ${e.pn}`),
      h('span', {}, `${e.from} → ${e.to}`),
      e.aog_transport_h != null ? h('span', { class: 'faint' }, `${fmtHours(e.aog_transport_h)} transport`) : null,
      e.qty != null ? h('span', { class: 'faint' }, `${fmtInt(e.qty)} unit${e.qty === 1 ? '' : 's'}`) : null,
      e.planted && !isSimple() ? h('span', { class: 'chip chip-mono' }, `Planted ${e.planted}`) : null,
      e.note ? h('span', { class: 'faint' }, e.note) : null].filter(Boolean));
  };
  // v2.1 addendum: controls stay live while a replay runs; a new request supersedes the running one (no disabled
  // buttons that swallow clicks). The playing state shows on the buttons (aria-pressed) and the event panel.
  let run = 0;
  const play = async (list) => {
    const me = ++run;
    host.classList.add('is-playing');
    allBtn.setAttribute('aria-pressed', String(list.length > 1));
    for (const e of list) {
      if (!isAlive() || me !== run) break;
      cur = e; sel.value = String(e.i); setInfo(e); markSel();
      map.select(e.to);
      await map.animateTransfer(e.from, e.to, { kind: e.kind, duration: list.length > 1 ? MOTION.slow + MOTION.base : MOTION.hero });
    }
    if (me === run && isAlive()) { host.classList.remove('is-playing'); allBtn.setAttribute('aria-pressed', 'false'); }
  };
  playBtn.addEventListener('click', () => play([cur]));
  allBtn.addEventListener('click', () => play(events.slice().sort((a, b) => a.t_h - b.t_h)));
  sel.addEventListener('change', () => { cur = events.find((e) => String(e.i) === sel.value) || cur; setInfo(cur); markSel(); });
  setInfo(cur);

  let markSel = () => {};
  const stop = responsive(strip, (w) => {
    const dests = [...new Set(events.map((e) => e.to))].sort();
    const rowH = 26, m = { top: 8, right: 16, bottom: 28, left: 44 };
    const hgt = m.top + m.bottom + dests.length * rowH;
    const iw = w - m.left - m.right;
    const svg = svgIn(strip, w, hgt, 'Transfer timeline');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const t0 = win[0] ?? d3().min(events, (e) => e.t_h), t1 = win[1] ?? d3().max(events, (e) => e.t_h);
    const x = d3().scaleLinear().domain([t0, t1 === t0 ? t0 + 1 : t1]).range([0, iw]);
    const y = d3().scaleBand().domain(dests).range([0, dests.length * rowH]).padding(0.2);
    g.append('g').selectAll('line').data(dests).join('line').attr('x1', 0).attr('x2', iw).attr('y1', (d) => y(d) + y.bandwidth() / 2).attr('y2', (d) => y(d) + y.bandwidth() / 2).attr('stroke', C.line);
    g.append('g').selectAll('text').data(dests).join('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', -10).attr('y', (d) => y(d) + y.bandwidth() / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((d) => d);
    axisBottom(g.append('g'), x, { ticks: w < 480 ? 3 : 6, format: (v) => (t1 - t0 < 4 * HPW ? fmtHours(v) : fmtWeek(Math.floor(v / HPW))), height: dests.length * rowH });
    // v2.1 addendum: transfers closer than one dot apart on the same row are nudged up / down, so every dot stays
    // clickable on its own (they overlapped at 390 and one swallowed the other's clicks)
    const nudge = new Map();
    d3().groups(events, (e) => e.to).forEach(([, list]) => {
      let lastX = -1e9, k = 0;
      list.slice().sort((a, b) => a.t_h - b.t_h).forEach((e) => { const px = x(e.t_h); k = px - lastX < 14 ? k + 1 : 0; lastX = px; nudge.set(e, k ? (k % 2 ? -1 : 1) * Math.min(y.bandwidth() / 2, 9) : 0); });
    });
    const ev = g.append('g').selectAll('g').data(events).join('g').attr('class', 'np-ev').attr('transform', (e) => `translate(${x(e.t_h)},${y(e.to) + y.bandwidth() / 2 + nudge.get(e)})`)
      .attr('tabindex', 0).attr('role', 'button').attr('aria-label', (e) => `Replay ${e.kind} transfer of ${e.pn} from ${e.from} to ${e.to} in ${fmtWeek(Math.floor(e.t_h / HPW))}`);
    ev.append('circle').attr('r', w < 520 ? 7 : 12).attr('fill', 'transparent');
    ev.append('circle').attr('class', 'np-ev-ring').attr('r', 8).attr('fill', 'none').attr('stroke', 'transparent').attr('pointer-events', 'none');
    ev.append('circle').attr('r', (e) => (e.kind === 'emergency' ? 5 : 4)).attr('fill', (e) => (e.kind === 'emergency' ? SR.urgent : C.bg)).attr('stroke', (e) => (e.kind === 'emergency' ? SR.urgent : SR.neutral)).attr('stroke-width', 1.5);
    drawIn(MS, 'replay', w, ev);
    ev.on('click', (evt, e) => play([e])).on('keydown', (evt, e) => { if (evt.key === 'Enter' || evt.key === ' ') { evt.preventDefault(); play([e]); } });
    withTooltip(ev, (e) => ({ title: `${e.pn} · ${e.from} → ${e.to}`, rows: [['When', fmtWeek(Math.floor(e.t_h / HPW))], ['Kind', e.kind], ...(e.aog_transport_h != null ? [['Transport', fmtHours(e.aog_transport_h)]] : [])], note: e.planted ? `Planted situation ${e.planted}` : 'Click to replay' }));
    markSel = () => ev.classed('is-sel', (e) => e === cur);
    markSel();
    if (featured && w >= 520) {
      const fx = x(featured.t_h), fy = y(featured.to) + y.bandwidth() / 2;
      annotate(g, { x: fx, y: fy, dx: fx > iw * 0.6 ? -28 : 28, dy: fy > 40 ? -18 : 18, title: featured.planted || `${featured.from}→${featured.to}`, sub: featured.pn });
    }
  });
  return () => stop();
}

// ============================================================================= policy compare
function renderCompare(host, n, p, stations, pcBy, ctx) {
  const avail = METRICS.filter((m) => stations.some((s) => metric(pcBy('P0', s.station), m.key)));
  let mk = avail.find((m) => m.key === ctx.params.metric) || avail[0];
  if (!mk) { chartFrame(host, { headline: byMode('The three plans by airport: not run', 'Policy comparison by station: not run'), subtitle: byMode('the three plans', 'P0 / P1 / P2'), provenance: 'SIMULATED', source: 'network.json → policy_compare' }).body.append(h('div', { class: 'state' }, 'not run')); return null; }
  const order = stations.slice().sort((a, b) => (a.role === 'hub' ? -1 : b.role === 'hub' ? 1 : 0) || a.station.localeCompare(b.station));
  const f = chartFrame(host, { implication: byMode('The Network Plan cuts grounded time at the home base and other airports, without stocking every airport.', 'Network positioning cuts downtime at the hub and the outstations without stocking every station.'), headline: byMode('The three plans by airport', 'Policy comparison by station'), subtitle: byMode('the three plans', 'P0 / P1 / P2'), provenance: prov(n.meta), source: 'network.json → policy_compare' });
  const seg = h('div', { class: 'seg', role: 'radiogroup', 'aria-label': 'Metric' }, avail.map((m) => h('button', { type: 'button', role: 'radio', 'aria-checked': String(m === mk), dataset: { value: m.key }, onclick: () => { mk = m; ctx.setParams({ metric: m.key }); seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === m.key))); draw(); } }, m.label)));
  slidingThumb(seg);
  f.body.before(h('div', { class: 'np-metric-bar' }, seg),
    h('div', { class: 'np-key', 'aria-hidden': 'true' }, POLS.map((pol) => h('span', { class: `np-key-i is-${pol.toLowerCase()}` }, h('i', { style: { borderColor: POL_COLOR[pol], background: pol === 'P2' ? POL_COLOR[pol] : 'transparent' } }), pnS(pol), isSimple() ? null : h('span', { class: 'mono-tag' }, pol)))));
  f.body.after(scopeLine());
  let stop = null;
  function draw() {
    const rows = order.flatMap((s) => POLS.map((pol) => ({ station: s.station, hub: s.role === 'hub', pol, m: metric(pcBy(pol, s.station), mk.key) }))).filter((r) => r.m?.mean != null);
    // headline from data
    const hubSt = order.find((s) => s.role === 'hub')?.station;
    const outs = order.filter((s) => s.role !== 'hub').map((s) => s.station);
    let head, subExtra = '';
    if (mk.key === 'aog_hours') {
      const g0 = metric(pcBy('P0', hubSt), 'aog_hours'), g2 = metric(pcBy('P2', hubSt), 'aog_hours');
      const o1 = outs.reduce((a, s) => a + (metric(pcBy('P1', s), 'aog_hours')?.mean ?? 0), 0), o2 = outs.reduce((a, s) => a + (metric(pcBy('P2', s), 'aog_hours')?.mean ?? 0), 0);
      const u = (pol) => order.filter((s) => s.role !== 'hub').reduce((a, s) => a + (num(s.by_policy?.[pol]?.rotable_units) ?? 0), 0);
      const u1 = u('P1'), u2 = u('P2');
      head = g0 && g2
        ? (isSimple()
          ? `The Network Plan cuts ${hubSt} grounded time from ${fmtHours(g0.mean)} to ${fmtHours(g2.mean)} a year`
          : `Network Plan (P2) cuts ${hubSt} AOG from ${fmtHours(g0.mean)} to ${fmtHours(g2.mean)}/yr${u1 && u2 ? ` with ${fmtInt(u2)} outstation rotables, not ${fmtInt(u1)}` : ''}`)
        : byMode('Hours grounded by airport and plan', 'AOG hours by station and policy');
      subExtra = outs.length ? (isSimple() ? `Other airports: ${fmtHours(o2)} under the Network Plan vs ${fmtHours(o1)} under Each Airport for Itself, which keeps ${fmtInt(u1)} spares there, not ${fmtInt(u2)}` : `Outstations ${fmtHours(o2)} under P2 vs ${fmtHours(o1)} under P1`) : '';
    } else {
      const lows = outs.map((s) => ({ s, v: metric(pcBy('P2', s), mk.key)?.mean })).filter((d) => d.v != null);
      const avgP2 = lows.length ? d3().mean(lows, (d) => d.v) : null;
      const avgP1 = outs.map((s) => metric(pcBy('P1', s), mk.key)?.mean).filter((v) => v != null);
      head = avgP2 != null && avgP1.length ? (isSimple() ? `At other airports, ${mk.label.toLowerCase()}: ${fmtPct(avgP2)} under the Network Plan vs ${fmtPct(d3().mean(avgP1))}` : `Outstation ${mk.label.toLowerCase()} averages ${fmtPct(avgP2)} under P2 vs ${fmtPct(d3().mean(avgP1))} under P1`) : `${mk.label} by ${byMode('airport and plan', 'station and policy')}`;
    }
    f.root.querySelector('.chart-headline').textContent = head;
    const sub = f.root.querySelector('.chart-subtitle') || (() => { const d = h('div', { class: 'chart-subtitle' }); f.root.querySelector('.chart-headline').after(d); return d; })();
    const clamped = rows.some((r) => r.m.clamped);
    sub.textContent = isSimple()
      ? [subExtra ? `${subExtra}.` : '', `${splitLabel(n, p).replace(/^./, (c) => c.toUpperCase())}: average and likely range${mk.key === 'aog_hours' ? ', on a stretched scale so small values show' : ''}.`, REC.pt ? `${displayName(REC.id)}${REC.extra ? ` (another ${REC.extra})` : ''} was tested for the whole network only: ${fmtHours(REC.pt.aog)} a year.` : '', clamped ? 'Ranges below 0 drawn at 0.' : ''].filter(Boolean).join(' ')
      : [subExtra, `${splitLabel(n, p)} · mean and 95% CI${mk.key === 'aog_hours' ? ' · square-root scale' : ''}`, 'P0 Simple Rulebook, P1 Each Airport for Itself, P2 Network Plan', REC.pt ? `${REC.id} (${displayName(REC.id)}: P2 + targeted units${REC.extra ? `, if you invest an additional ${REC.extra}` : ''}) was simulated for network totals only: ${fmtHours(REC.pt.aog)}/yr` : '', clamped ? 'CI ends below 0 drawn at 0' : ''].filter(Boolean).join(' · ');
    sub.title = sub.textContent;
    f.setTable([{ key: 'station', label: byMode('Airport', 'Station') }, { key: 'pol', label: byMode('Plan', 'Policy'), format: (c) => pn(c) }, { key: 'mean', label: 'Mean', num: true, format: mk.fmt }, { key: 'lo', label: 'CI lo', num: true, format: mk.fmt }, { key: 'hi', label: 'CI hi', num: true, format: mk.fmt }], rows.map((r) => ({ station: r.station, pol: r.pol, mean: r.m.mean, lo: r.m.lo, hi: r.m.hi })));
    stop?.();
    stop = liveDraw(f.body, (w) => drawCompare(f.body, rows, order, mk, w));
  }
  draw();
  return () => stop?.();
}

function drawCompare(el, rows, order, mk, w) {
  const narrow = w < 520;
  const sts = order.map((s) => s.station).filter((s) => rows.some((r) => r.station === s));
  const rowH = 60, m = { top: 24, right: narrow ? 16 : 96, bottom: 32, left: narrow ? 44 : 64 };
  const hgt = m.top + m.bottom + sts.length * rowH;
  const iw = Math.max(80, w - m.left - m.right);
  const svg = svgIn(el, w, hgt, `${mk.label} by station and policy`);
  const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
  const vals = rows.flatMap((r) => [r.m.mean, r.m.lo, r.m.hi]).filter((v) => v != null);
  const x = mk.key === 'aog_hours'
    ? d3().scaleSqrt().domain([0, d3().max(vals) * 1.05]).nice().range([0, iw])
    : d3().scaleLinear().domain([Math.max(0, Math.floor(d3().min(vals) * 20) / 20), Math.min(1, Math.ceil(d3().max(vals) * 50) / 50)]).range([0, iw]);
  const y = d3().scaleBand().domain(sts).range([0, sts.length * rowH]).padding(0.12);
  const off = { P0: -14, P1: 0, P2: 14 };
  g.append('g').selectAll('rect').data(sts).join('rect').attr('x', -m.left + 4).attr('width', iw + m.left - 4).attr('y', (s) => y(s)).attr('height', y.bandwidth()).attr('rx', 6).attr('fill', (s, i) => (i % 2 ? 'transparent' : 'rgba(185,200,214,0.035)'));
  const ticks = mk.key === 'aog_hours' ? x.ticks(narrow ? 3 : 5) : x.ticks(narrow ? 3 : 5);
  g.append('g').selectAll('line').data(ticks).join('line').attr('class', 'gnm-grid').attr('x1', (t) => x(t)).attr('x2', (t) => x(t)).attr('y1', 0).attr('y2', sts.length * rowH).attr('stroke', C.line).attr('stroke-dasharray', '2 4');
  const axG = g.append('g');
  // v2.1 motion: the axis transitions between metrics; a sqrt ↔ linear switch snaps (different scale types)
  const sameKind = MS.get('cmp-x')?.kind === mk.key;
  if (!sameKind) MS.delete('cmp-x');
  morphAxis(MS, 'cmp-x', w, axG, x, (ga, sc) => axisBottom(ga, sc, { ticks: narrow ? 3 : 5, format: mk.fmt, height: sts.length * rowH }));
  MS.get('cmp-x').kind = mk.key;
  // a square-root scale bunches the top ticks: drop any tick label (and its grid line) that would sit within 56 px of the previous one
  if (mk.key === 'aog_hours') {
    let last = -1e9;
    const keep = new Set();
    axG.selectAll('.tick').each(function (t) { const px = x(t); if (px - last < 64 && t !== 0) d3().select(this).remove(); else { last = px; keep.add(t); } });
    g.selectAll('line.gnm-grid').filter((t) => !keep.has(t)).remove();
  }
  g.append('g').selectAll('text').data(sts).join('text').attr('class', 'gnm-label gnm-label--strong').attr('font-family', theme.font.mono).attr('x', -10).attr('y', (s) => y(s) + y.bandwidth() / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((s) => s);
  const pts = g.append('g').selectAll('g').data(rows).join('g').attr('class', 'np-cmp-pt').attr('transform', (r) => `translate(0,${y(r.station) + y.bandwidth() / 2 + off[r.pol]})`);
  const ciL = pts.filter((r) => r.m.lo != null && r.m.hi != null).append('line').attr('stroke', (r) => POL_COLOR[r.pol]).attr('stroke-width', 1.5).attr('stroke-opacity', 0.7);
  const dots = pts.append('circle').attr('r', 4).attr('fill', (r) => (r.pol === 'P2' ? SR.neutral : C.bg)).attr('stroke', (r) => POL_COLOR[r.pol]).attr('stroke-width', 1.75);
  // v2.1 motion: keyed by station × plan, values slide to the new metric (sqrt ↔ linear included), never from zero
  const kf = (r) => `${r.station}:${r.pol}`;
  morph(MS, 'cmp', w, ciL, kf, { x1: (r) => x(Math.max(x.domain()[0], r.m.lo)), x2: (r) => x(r.m.hi) });
  morph(MS, 'cmp', w, dots, kf, { cx: (r) => x(r.m.mean) });
  withTooltip(pts, (r) => ({ title: `${pn(r.pol)} at ${r.station}`, rows: [[byMode('Average', 'Mean'), mk.fmt(r.m.mean)], [termText('ci', { cap: true }), r.m.lo != null ? `${mk.fmt(r.m.lo)} – ${mk.fmt(r.m.hi)}` : '—']] }));
  // direct labels: policy names on the first row, values on the right for the hub row (wide only)
  const first = sts[0];
  POLS.forEach((pol) => {
    const r = rows.find((d) => d.station === first && d.pol === pol);
    if (!r) return;
    // v2.1: values only (the HTML key above the chart names the plans; no bare codes in Simple mode)
    if (!narrow) dl(g, { x: iw + 10, y: y(first) + y.bandwidth() / 2 + off[pol], text: mk.fmt(r.m.mean), color: pol === 'P1' ? C.muted : POL_COLOR[pol], strong: pol === 'P2' });
  });
  if (!narrow) dl(g, { x: iw + 10, y: -12, text: first, color: C.faint });
  if (mk.key === 'aog_hours') {
    const r0 = rows.find((d) => d.station === first && d.pol === 'P0');
    const r2 = rows.find((d) => d.station === first && d.pol === 'P2');
    if (r0 && r2 && sts.length > 1) {
      if (narrow) {
        // no room for a leader inside the row at 390: state the delta in the legend line instead
        dl(g, { x: iw, y: -14, text: `${first}: −${fmtHours(r0.m.mean - r2.m.mean)} ${byMode('with the Network Plan', 'P2 vs P0')}`, anchor: 'end', color: C.text, strong: true });
      } else {
        const xa = x(r2.m.mean), ya = y(first) + y.bandwidth() / 2 + off.P2;
        // above the row (wave C): the leader no longer crosses the P0/P1 labels
        annotate(g, { x: xa, y: ya, dx: 36, dy: -(off.P2 + y.bandwidth() / 2) + 4, title: `${first} −${fmtHours(r0.m.mean - r2.m.mean)}`, sub: byMode('Network Plan vs Simple Rulebook', 'P2 vs P0') });
      }
    }
  }
}

// ============================================================================= hub vs outstation share
function renderShare(host, n, p, stations, pcBy, hub) {
  const outs = stations.filter((s) => s.role !== 'hub').map((s) => s.station);
  const rows = POLS.map((pol) => {
    const hb = metric(pcBy(pol, hub?.station), 'aog_hours')?.mean;
    const os = outs.map((s) => metric(pcBy(pol, s), 'aog_hours')?.mean).filter((v) => v != null);
    return { pol, hub: hb, out: os.length ? d3().sum(os) : null };
  }).filter((r) => r.hub != null && r.out != null);
  const r0 = rows.find((r) => r.pol === 'P0'), r1 = rows.find((r) => r.pol === 'P1'), r2 = rows.find((r) => r.pol === 'P2');
  const share0 = r0 ? r0.hub / (r0.hub + r0.out) : null;
  const S = isSimple();
  const f = chartFrame(host, {
    implication: share0 != null && share0 < 0.5
      ? byMode('Most grounded time under the Simple Rulebook is at other airports. Keep urgent spares there, fed from the home base.', 'Most legacy downtime is at outstations holding no no-go stock: position units there, fed from the hub.')
      : byMode('Shortages at the home base cause most grounded time, so pool and restock there first.', 'Hub shortages drive most legacy downtime, so hub pooling and replenishment come first.'),
    headline: share0 != null
      ? (S
        ? (share0 < 0.5 ? `${fmtPct(1 - share0, 0)} of the Simple Rulebook's grounded time is at other airports` : `${fmtPct(share0, 0)} of the Simple Rulebook's grounded time is at the ${hub.station} home base`)
        : share0 < 0.5 ? `${fmtPct(1 - share0, 0)} of P0’s AOG hours are at the outstations; ${fmtPct(share0, 0)} at the ${hub.station} hub` : `${fmtPct(share0, 0)} of P0’s AOG hours are at the ${hub.station} hub, not the outstations`)
      : byMode('Home base vs other airports: not run', 'Hub vs outstation AOG: not run'),
    // the denominator is stated: hub + every outstation, i.e. the same all-station total as the station shares
    subtitle: S
      ? `Hours grounded a year: home base vs all other airports added up. Share = part of the total across all ${fmtInt(stations.length)} airports. ${splitLabel(n, p).replace(/^./, (c) => c.toUpperCase())}, averages.`
      : `AOG h / yr · hub vs sum of outstations · share of the all-station total (hub + ${fmtInt(outs.length)} outstations) · ${splitLabel(n, p)} · means`,
    provenance: prov(n.meta), source: 'network.json → policy_compare',
    table: { columns: [{ key: 'pol', label: byMode('Plan', 'Policy'), format: (c) => pn(c) }, { key: 'hub', label: byMode('Home base hours', 'Hub AOG h'), num: true, format: fmtHours }, { key: 'out', label: byMode('Other airports hours', 'Outstations AOG h'), num: true, format: fmtHours }, { key: 'share', label: byMode('Home base share', 'Hub share'), num: true, format: (v) => fmtPct(v, 0) }], rows: rows.map((r) => ({ ...r, share: r.hub / (r.hub + r.out) })) },
  });
  if (!rows.length) { f.body.append(h('div', { class: 'state' }, 'not run')); return null; }
  const stop = responsive(f.body, (w) => {
    const rowH = 50, m = { top: 6, right: 8, bottom: 6, left: 8 };
    const hgt = m.top + m.bottom + rows.length * rowH;
    const iw = w - m.left - m.right;
    const svg = svgIn(f.body, w, hgt, byMode('Hours grounded, home base versus other airports, by plan', 'AOG hours, hub versus outstations, by policy'));
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const x = d3().scaleLinear().domain([0, d3().max(rows, (r) => r.hub + r.out)]).range([0, iw]);
    drawIn(MS, 'share', w, g);
    rows.forEach((r, i) => {
      const yy = i * rowH;
      // the plan name and its numbers sit on one line above the bar (no codes in Simple mode)
      const txt = `${pnS(r.pol)} · ${byMode('home', 'hub')} ${fmtHours(r.hub)} · ${byMode('others', 'out')} ${fmtHours(r.out)}`;
      dl(g, { x: 0, y: yy + 10, text: truncate(txt, iw, 6.6), color: r.pol === 'P2' ? C.text : C.muted, strong: r.pol === 'P2' });
      g.append('rect').attr('x', 0).attr('y', yy + 20).attr('width', Math.max(1, x(r.hub))).attr('height', 16).attr('rx', 2).attr('fill', r.pol === 'P0' ? SR.baseline : SR.neutral).attr('fill-opacity', r.pol === 'P2' ? 0.85 : 0.6);
      g.append('rect').attr('x', x(r.hub) + 1).attr('y', yy + 20).attr('width', Math.max(1, x(r.out))).attr('height', 16).attr('rx', 2).attr('fill', r.pol === 'P0' ? SR.baseline : SR.context).attr('fill-opacity', r.pol === 'P0' ? 0.35 : 0.55);
    });
  });
  const items = [];
  if (r0 && r2) {
    const dHub = r0.hub - r2.hub, dOut = r0.out - r2.out;
    items.push(S
      ? (dOut >= dHub
        ? ['Spares at other airports pay most.', ` Against the Simple Rulebook, the Network Plan cuts ${fmtHours(dOut)} a year at other airports and ${fmtHours(dHub)} at the home base.`]
        : ['Pooling at the home base pays most.', ` Against the Simple Rulebook, the Network Plan cuts ${fmtHours(dHub)} a year at the home base. ${fmtHours(r2.out)} is left across all other airports.`])
      : dOut >= dHub
        ? ['Outstation stock pays most.', ` Network Plan (P2) cuts outstation AOG by ${fmtHours(dOut)} a year versus P0 and hub AOG by ${fmtHours(dHub)}.`]
        : ['Pooling at the hub pays most.', ` Network Plan (P2) cuts hub AOG by ${fmtHours(dHub)} a year versus P0, with ${fmtHours(r2.out)} left across all outstations.`]);
  }
  if (r1 && r2) items.push(S
    ? ['Stocking every airport misses the home base.', ` Each Airport for Itself still leaves ${fmtHours(r1.hub)} a year at ${hub.station}${r0 ? ` (Simple Rulebook: ${fmtHours(r0.hub)})` : ''}.`]
    : ['Local floats miss the hub.', ` P1 stocks every outstation, yet leaves ${fmtHours(r1.hub)} of AOG at ${hub.station}${r0 ? ` (P0: ${fmtHours(r0.hub)})` : ''}.`]);
  items.push(S
    ? ['Spares go where they are needed.', ' Other airports get spares only where urgent demand and transport time justify them. Parts that can wait a few days come from the home base.']
    : ['Selective positioning.', ' Outstation units go where D0 exposure and transport time justify them; D3/D10 demand is covered from the hub within the deadline.']);
  f.body.after(h('ul', { class: 'np-findings' }, items.map(([a, b]) => h('li', {}, icon('target'), h('div', {}, h('strong', {}, a), b)))), scopeLine());
  return stop;
}
