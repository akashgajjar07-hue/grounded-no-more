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
import { h, icon, pageHead, card, provChip, pill, dataTable } from '../ui.js';
import { renderNetworkMap } from '../charts/map.js';
import { chartFrame, responsive, svgIn, axisBottom, directLabel, annotate, withTooltip, truncate, theme, fmtAED, fmtInt, fmtPct, fmtHours, fmtNum, fmtWeek, reducedMotion } from '../charts/theme.js';

export const data = ['network', 'policies'];

const d3 = () => window.d3;
/** directLabel whose colour wins over the .gnm-label CSS fill. */
const dl = (g, o) => directLabel(g, o).style('fill', o.color || null);
const C = theme.color;
const HPW = 168;
const POLS = ['P0', 'P1', 'P2'];
const SR = theme.series;
// P0 = baseline (copper), P1 = other comparison (slate), P2 = the network policy (bright titanium, filled).
// Not teal: teal is the recommended I125 plan site-wide, and I125 has no per-station holdout breakdown (wave 4, C5).
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
const prov = (o, f = 'SIMULATED') => o?.provenance || f;

/**
 * Outstation risk is rated against the riskiest OUTSTATION (exporter: outstation_risk_level / risk_vs_outstations),
 * not against the hub, so the riskiest outstation never wears a LOW pill while it has urgent shortfalls.
 * Fallback when the exporter field is missing: derive the same ratio from `risk`.
 */
let OUT_MAX = null;
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
    if (['urgent', 'high'].includes(lv)) return 'urgent';
    // below the top band, outstations are compared in neutral (no amber/teal status: the map already carries teal + red)
    if (['review', 'medium', 'elevated', 'watch'].includes(lv)) return 'watch';
    if (['ok', 'low'].includes(lv)) return 'low';
    const rv = riskVsOut(s);
    if (rv != null) return rv >= 0.8 ? 'urgent' : rv >= 0.5 ? 'watch' : 'low';
  }
  const lvl = String(s.risk_level || '').toLowerCase();
  if (['urgent', 'high'].includes(lvl)) return 'urgent';
  if (['review', 'medium', 'elevated'].includes(lvl)) return 'review';
  if (['ok', 'low'].includes(lvl)) return 'ok';
  const r = num(s.risk);
  if (r == null) return 'unknown';
  return r > 0.66 ? 'urgent' : r > 0.33 ? 'review' : 'ok';
}
const RISK = {
  urgent: { word: 'HIGH', glyph: '▲', color: C.urgent, pill: 'urgent' },
  review: { word: 'WATCH', glyph: '◆', color: C.review, pill: 'review' },
  ok: { word: 'LOW', glyph: '●', color: C.ok, pill: 'ok' },
  watch: { word: 'ELEVATED', glyph: '◆', color: SR.neutral, pill: 'unknown' }, // not WATCH: WATCH is amber review site-wide (wave 4, C4)
  low: { word: 'LOWER', glyph: '●', color: SR.context, pill: 'unknown' },
  unknown: { word: 'N/A', glyph: '○', color: C.unknown, pill: 'unknown' },
};

/** Risk pill text: outstations relative to the riskiest outstation, the hub on its own scale. */
function riskText(s, stations) {
  const b = RISK[riskBand(s)];
  if (s.role === 'hub') return `${b.word} · hub`;
  const rv = riskVsOut(s);
  if (rv != null && rv >= 0.999) return `${b.word} · top outstation`;
  const top = stations.filter((x) => x.role !== 'hub').sort((a, c) => (c.risk ?? 0) - (a.risk ?? 0))[0];
  return rv != null ? `${b.word} · ${fmtPct(rv, 0)} of ${top?.station || 'top'}` : b.word;
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
  { key: 'aog_hours', label: 'AOG h / yr', short: 'AOG h', fmt: fmtHours, better: 'lower' },
  { key: 'fill_rate', label: 'Immediate fill', short: 'Fill', fmt: (v) => fmtPct(v), better: 'higher' },
  { key: 'rotable_fill_rate', label: 'Rotable fill', short: 'Rot. fill', fmt: (v) => fmtPct(v), better: 'higher' },
];

function splitLabel(n, p) {
  const split = n.policy_compare_meta?.split || p?.split || n.meta?.split;
  const seeds = n.policy_compare_meta?.seeds || p?.seeds;
  const ns = n.policy_compare_meta?.n_seeds || p?.n_seeds;
  const range = Array.isArray(seeds) && seeds.length ? ` ${Math.min(...seeds)}–${Math.max(...seeds)}` : '';
  return split ? `${split[0].toUpperCase()}${split.slice(1)} seeds${range}${ns ? ` (${ns})` : ''}` : 'Simulated seeds';
}

// ----------------------------------------------------------------------------- view
export async function render(el, ctx) {
  loadCSS();
  const { network: n, policies: p } = ctx.data;
  const stations = n.stations || [];
  setOutstationScale(stations);
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
    title: 'Where the stock sits, and how fast it can move',
    lede: `${hub ? hub.station : 'The hub'} supports ${fmtInt(stations.length - 1)} outstations for Falcon Hub Airways (fictional). Node size is serviceable stock, ring colour is projected risk (with icon and text), arc weight is simulated transfer volume. Station coordinates are real (OurAirports); the network activity is simulated.`,
    meta: [provChip('REAL'), provChip(prov(n.meta))],
  }));

  // ---------------------------------------------------------------- 1. hero map + drill-down
  const maxUnits = Math.max(1, ...stations.map((s) => num(s.serviceable_units) ?? 0));
  const mapHost = h('div', { style: { minHeight: '260px' } });
  // keyboard selector for the map: visually hidden until it receives focus (the map nodes and the table select with the pointer)
  const picker = h('div', { class: 'np-picker', role: 'group', 'aria-label': 'Select a station' });
  stations.forEach((s) => {
    const rb = RISK[riskBand(s)];
    picker.append(h('button', { type: 'button', 'aria-pressed': String(s.station === selected), dataset: { station: s.station }, onclick: () => choose(s.station, true) },
      h('span', { class: 'np-dot', style: { background: rb.color }, 'aria-hidden': 'true' }), `${s.station} · ${rb.word}`));
  });
  const mapCard = h('section', { class: 'card card--bp', dataset: { story: 'map' } });
  const totalTransfers = arcs.reduce((a, b) => a + (num(b.transfers) ?? 0), 0);
  const totalEmerg = arcs.reduce((a, b) => a + (num(b.emergency) ?? 0), 0);
  const busiest = arcs.slice().sort((a, b) => (b.transfers ?? 0) - (a.transfers ?? 0))[0];
  const topRisk = stations.filter((s) => s.role !== 'hub').sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))[0];
  const topAll = stations.slice().sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))[0];
  const mapF = chartFrame(mapCard, {
    headline: topAll && topRisk
      ? (topAll.role === 'hub'
        ? `The ${topAll.station} hub carries the most projected AOG risk; ${topRisk.station} leads outstations at ${fmtPct(topRisk.risk, 0)} of it`
        : `${topAll.station} carries the highest projected risk (${fmtPct(topAll.risk, 0)}); ${fmtInt(totalEmerg)} of ${fmtInt(totalTransfers)} transfers were emergencies`)
      : 'Hub-and-spoke network',
    subtitle: `Node size = serviceable units (recommended plan) · ring = projected risk (hub on its own; outstations vs the riskiest outstation) · line width = ${fmtInt(totalTransfers)} history transfers`,
    provenance: prov(n.meta), source: 'network.json → stations, arcs',
    table: { columns: [{ key: 'from', label: 'From' }, { key: 'to', label: 'To' }, { key: 'transfers', label: 'Transfers', num: true, format: fmtInt }, { key: 'emergency', label: 'Emergency', num: true, format: fmtInt }, { key: 'aog_transport_h', label: 'AOG transport', num: true, format: fmtHours }], rows: arcs },
  });
  // one legend row, two groups: ring = risk (only the bands present), line = transfer kind
  const bandsPresent = ['low', 'watch', 'ok', 'review', 'urgent'].filter((b) => stations.some((s) => riskBand(s) === b));
  mapF.body.append(mapHost, h('div', { class: 'np-map-foot' }, picker,
    h('div', { class: 'np-legend', 'aria-hidden': 'true' },
      h('span', { class: 'np-legend-k' }, 'Risk ring'),
      ...bandsPresent.map((b) => h('span', { style: { color: RISK[b].color } }, h('i', { class: 'np-ring' }), RISK[b].word.toLowerCase())),
      h('span', { class: 'np-legend-k' }, 'Transfers'),
      h('span', { style: { color: SR.neutral } }, h('i', { class: 'np-line' }), 'routine'),
      totalEmerg ? h('span', { style: { color: SR.urgent } }, h('i', { class: 'np-line' }), 'emergency (replay)') : null)));
  const drill = h('section', { class: 'card', dataset: { story: 'station-drill' }, 'aria-live': 'polite' });
  // wave 4: the hub-vs-outstation finding sits under the map, so the left column matches the tall station panel (no dead space)
  const shareCard = h('section', { class: 'card', dataset: { story: 'network-hub-finding' } });
  el.append(h('div', { class: 'np-hero mt-3' }, h('div', { class: 'np-left' }, mapCard, shareCard), drill));

  const map = await renderNetworkMap(mapHost, {
    stations, arcs, selected,
    onSelect: (id) => choose(id, false),
    // sub-label sits directly under the IATA code: units, plus the risk word only when it is not low (no glyph, so it never reads as another airport)
    labelSub: (s) => { const b = riskBand(s); const risk = b === 'ok' || b === 'low' ? '' : ` · ${RISK[b].word}`; return `${fmtInt(s.serviceable_units)} u${risk}`; },
    nodeRadius: (s) => 4 + 10 * Math.sqrt((num(s.serviceable_units) ?? 0) / maxUnits),
    nodeColor: (s) => RISK[riskBand(s)].color,
    nodeAria: (s) => `${s.station} ${s.name || ''}: ${fmtInt(s.serviceable_units)} serviceable units, projected risk ${RISK[riskBand(s)].word}`,
    tooltipRows: (s) => [['Role', s.role], ['Serviceable units', fmtInt(s.serviceable_units)], ['Stock value', fmtAED(s.stock_value)], ['Requests', fmtInt(s.requests)], ['Projected risk', `${RISK[riskBand(s)].glyph} ${riskText(s, stations)}`], ...(s.role !== 'hub' ? [['Risk vs hub', fmtPct(s.risk, 0)]] : [])],
    label: 'Network map of Falcon Hub Airways (fictional) stations',
    // the hub's arcs leave to the west and east; its label block sits above-right, clear of them and of the Gulf outstations
    labelOffsets: hub ? { [hub.station]: [12, -30, 'start'] } : {},
  });
  cleanups.push(() => map.destroy());
  if (!alive) return () => {};

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
      drill.append(h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, 'Station drill-down'), h('h3', { class: 'card-title' }, 'Select a station on the map or below')), provChip(prov(n.meta))),
        h('p', { class: 'muted t-14' }, 'Each station shows its serviceable units, request volume, projected risk, transfer traffic and how P0, P1 and P2 perform there.'),
        h('div', { class: 'np-sub' }, 'Highest projected risk first'),
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
    drill.append(
      h('div', { class: 'np-drill-head' },
        h('div', {}, h('div', { class: 'card-kicker' }, s.role === 'hub' ? 'Hub station' : 'Outstation'), h('div', { class: 'np-drill-code' }, s.station), h('div', { class: 'np-drill-name' }, s.name || '')),
        h('div', { class: 'row', style: { flexWrap: 'wrap' } }, pill(rb.pill, `${riskText(s, stations)}`), provChip(prov(n.meta)))),
      h('div', { class: 'np-facts' },
        fact('Serviceable units', fmtInt(s.serviceable_units)),
        fact('Stock value', fmtAED(s.stock_value)),
        fact('Requests (history)', `${fmtInt(s.requests)}${s.requests_d0 != null ? ` · ${fmtInt(s.requests_d0)} D0` : ''}`),
        s.role === 'hub' ? fact('Transfers out', fmtInt(tOut)) : fact('Transfers in', `${fmtInt(tIn)}${eIn ? ` (${fmtInt(eIn)} AOG)` : ''}`),
        ...(aogT != null ? [fact('AOG transport from hub', fmtHours(aogT))] : []),
        ...(s.aog_hours_hist != null ? [fact('AOG h (history, P0)', `${fmtHours(s.aog_hours_hist)}${s.aog_events_hist != null ? ` · ${fmtInt(s.aog_events_hist)} ev` : ''}`)] : []),
        ...(s.role === 'hub' ? [fact('Outstations served', fmtInt(outbound.length))] : [])),
      s.by_policy ? h('div', { class: 'np-sub' }, 'Rotable units positioned here, by plan') : null,
      s.by_policy ? h('div', { class: 'np-units' }, Object.entries(s.by_policy).map(([k, v]) => h('div', { class: `np-unit ${k === n.recommended_id ? 'is-rec' : ''}` }, h('span', { class: 'np-unit-k' }, k === n.recommended_id ? `${k} · rec.` : k), h('span', { class: 'np-unit-v' }, fmtInt(v.rotable_units)), h('span', { class: 'np-unit-s' }, fmtAED(v.stock_value_aed))))) : null,
      h('div', { class: 'np-sub' }, `P0 / P1 / P2 at ${s.station} · ${splitLabel(n, p)} · mean, 95% CI`),
      polRows.some((r) => r.aog || r.fill)
        ? h('table', { class: 'np-pol' },
          h('caption', { class: 'sr-only' }, `Policy comparison at ${s.station}`),
          h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Policy'), h('th', { scope: 'col' }, 'AOG h/yr'), h('th', { scope: 'col' }, 'Fill'), hasR ? h('th', { scope: 'col' }, 'Rot. fill') : null)),
          h('tbody', {}, polRows.map((r) => h('tr', { class: bestAog && r.pol === bestAog.pol ? 'is-best' : '' },
            h('td', {}, r.pol, bestAog && r.pol === bestAog.pol ? h('span', { class: 'np-best' }, ' · lowest AOG') : null),
            h('td', {}, r.aog ? fmtHours(r.aog.mean) : 'not run', ci(r.aog, fmtHours)),
            h('td', {}, r.fill ? fmtPct(r.fill.mean) : 'not run', ci(r.fill, (v) => fmtPct(v))),
            hasR ? h('td', {}, r.rfill ? fmtPct(r.rfill.mean) : '—', ci(r.rfill, (v) => fmtPct(v))) : null))))
        : h('div', { class: 'state' }, 'Policy comparison not run'),
      ...(polRows.some((r) => r.aog?.clamped || r.fill?.clamped || r.rfill?.clamped) ? [h('p', { class: 'np-note' }, 'CI lower ends below 0 are shown as 0 (t-interval on a near-zero mean).')] : []),
      h('div', { class: 'np-link' }, h('a', { class: 'card-link', href: ctx.buildHash('parts', { station: s.station }) }, 'Parts at this station', icon('chevron-right'))),
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
    kicker: 'Stations', title: 'Stock and exposure by station, highest projected risk first', prov: prov(n.meta),
    body: dataTable({
      caption: 'Stations', dense: true,
      columns: [
        { key: 'station', label: 'Station', mono: true },
        { key: 'role', label: 'Role' },
        { key: 'serviceable_units', label: 'Serviceable', short: 'Units', num: true, format: fmtInt },
        { key: 'stock_value', label: 'Stock value', short: 'Stock', num: true, format: (v) => fmtAED(v) },
        { key: 'requests', label: 'Requests', num: true, format: fmtInt },
        { key: 'risk', label: 'Projected risk', short: 'Risk', render: (s) => pill(RISK[riskBand(s)].pill, riskText(s, stations)) },
      ],
      rows: stations, sort: { key: 'risk', dir: 'desc' }, onRowClick: (s) => choose(s.station, true),
      mobileColumns: ['station', 'risk', 'stock_value', 'serviceable_units'], stickyFirst: true,
    }),
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
    note: e.focus && fo ? `${fo.desc || ''} for ${fo.tail || 'a tail'} · AOG ${fmtHours(fo.aog_hours)}` : null,
  }));
  const featured = events.find((e) => e.focus) || events.find((e) => e.planted) || events.find((e) => e.kind === 'emergency') || events[0];
  let cur = featured;
  const nEm = events.filter((e) => e.kind === 'emergency').length;
  const win = tr.window_h || [];
  const f = chartFrame(host, {
    headline: featured
      ? `${featured.planted ? `${featured.planted}: ` : ''}${featured.from}→${featured.to} ${featured.kind === 'emergency' ? 'emergency' : 'routine'} transfer${featured.aog_transport_h != null ? ` took ${fmtHours(featured.aog_transport_h)}` : ''}; ${fmtInt(nEm)} of ${fmtInt(events.length)} replayed transfers were emergencies`
      : 'No transfers exported for replay',
    subtitle: `Simulated history transfers${win.length === 2 ? ` ${fmtWeek(Math.floor(win[0] / HPW))}–${fmtWeek(Math.floor(win[1] / HPW))} (sim h ${fmtInt(win[0])}–${fmtInt(win[1])})` : ''}${featured?.pn ? ` · featured part ${featured.pn}` : ''} · one dot per transfer, row = destination · red = emergency${reducedMotion() ? ' · reduced motion: arcs flash' : ''}`,
    provenance: prov(tr, prov(n.meta)), source: 'network.json → transfer_replay',
    table: { columns: [{ key: 't_h', label: 'Week', format: (v) => fmtWeek(Math.floor(v / HPW)) }, { key: 'pn', label: 'PN' }, { key: 'from', label: 'From' }, { key: 'to', label: 'To' }, { key: 'kind', label: 'Kind' }, { key: 'planted', label: 'Planted', format: (v) => v || '' }], rows: events },
  });
  if (!events.length) { f.body.append(h('div', { class: 'state' }, 'not run')); return null; }
  const sel = h('select', { class: 'select', 'aria-label': 'Choose a transfer to replay' }, events.map((e) => h('option', { value: String(e.i) }, `${fmtWeek(Math.floor(e.t_h / HPW))} · ${e.pn} · ${e.from}→${e.to} · ${e.kind}${e.planted ? ` · ${e.planted}` : ''}`)));
  sel.value = String(cur.i);
  const playBtn = h('button', { class: 'btn btn--primary btn--sm', type: 'button' }, icon('play'), 'Replay transfer');
  const allBtn = h('button', { class: 'btn btn--sm', type: 'button' }, icon('route'), 'Replay all');
  const info = h('div', { class: 'np-event', role: 'status', 'aria-live': 'polite' });
  f.body.before(h('div', { class: 'np-replay-bar' }, sel, playBtn, allBtn));
  const strip = h('div', { class: 'np-strip' });
  f.body.append(strip, info);
  if (fo?.timeline?.length) {
    f.body.append(h('div', { class: 'np-sub' }, `${fo.planted ? `${fo.planted} · ` : ''}${fo.incident_id || 'Incident'} timeline · ${fo.pn} at ${fo.station} · hours from removal`),
      h('ol', { class: 'np-timeline' }, fo.timeline.map((t) => h('li', { class: `is-${t.step || 'event'}` }, h('span', { class: 'np-tl-t mono' }, `T+${fmtNum(t.t_h, 0)} h`), h('span', { class: 'np-tl-st mono' }, t.station || ''), h('span', { class: 'np-tl-ev' }, t.event)))));
  }
  const setInfo = (e) => {
    info.className = `np-event ${e.kind === 'emergency' ? 'is-emergency' : ''}`;
    info.replaceChildren(...[
      e.kind === 'emergency' ? pill('urgent', 'Emergency (AOG)') : pill('ok', 'Routine'),
      h('span', { class: 'mono' }, `${fmtWeek(Math.floor(e.t_h / HPW))} · ${e.pn}`),
      h('span', {}, `${e.from} → ${e.to}`),
      e.aog_transport_h != null ? h('span', { class: 'faint' }, `${fmtHours(e.aog_transport_h)} transport`) : null,
      e.qty != null ? h('span', { class: 'faint' }, `${fmtInt(e.qty)} unit${e.qty === 1 ? '' : 's'}`) : null,
      e.planted ? h('span', { class: 'chip chip-mono' }, `Planted ${e.planted}`) : null,
      e.note ? h('span', { class: 'faint' }, e.note) : null].filter(Boolean));
  };
  let busy = false;
  const play = async (list) => {
    if (busy) return;
    busy = true; playBtn.disabled = true; allBtn.disabled = true;
    for (const e of list) {
      if (!isAlive()) break;
      cur = e; sel.value = String(e.i); setInfo(e); markSel();
      map.select(e.to);
      await map.animateTransfer(e.from, e.to, { kind: e.kind, duration: list.length > 1 ? 700 : 1400 });
    }
    busy = false; if (isAlive()) { playBtn.disabled = false; allBtn.disabled = false; }
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
    const ev = g.append('g').selectAll('g').data(events).join('g').attr('class', 'np-ev').attr('transform', (e) => `translate(${x(e.t_h)},${y(e.to) + y.bandwidth() / 2})`)
      .attr('tabindex', 0).attr('role', 'button').attr('aria-label', (e) => `Replay ${e.kind} transfer of ${e.pn} from ${e.from} to ${e.to} in ${fmtWeek(Math.floor(e.t_h / HPW))}`);
    ev.append('circle').attr('r', 12).attr('fill', 'transparent');
    ev.append('circle').attr('class', 'np-ev-ring').attr('r', 8).attr('fill', 'none').attr('stroke', 'transparent');
    ev.append('circle').attr('r', (e) => (e.kind === 'emergency' ? 5 : 4)).attr('fill', (e) => (e.kind === 'emergency' ? SR.urgent : C.bg)).attr('stroke', (e) => (e.kind === 'emergency' ? SR.urgent : SR.neutral)).attr('stroke-width', 1.5);
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
  if (!mk) { chartFrame(host, { headline: 'Policy comparison by station: not run', subtitle: 'P0 / P1 / P2', provenance: 'SIMULATED', source: 'network.json → policy_compare' }).body.append(h('div', { class: 'state' }, 'not run')); return null; }
  const order = stations.slice().sort((a, b) => (a.role === 'hub' ? -1 : b.role === 'hub' ? 1 : 0) || a.station.localeCompare(b.station));
  const f = chartFrame(host, { headline: 'Policy comparison by station', subtitle: 'P0 / P1 / P2', provenance: prov(n.meta), source: 'network.json → policy_compare' });
  const seg = h('div', { class: 'seg', role: 'radiogroup', 'aria-label': 'Metric' }, avail.map((m) => h('button', { type: 'button', role: 'radio', 'aria-checked': String(m === mk), dataset: { value: m.key }, onclick: () => { mk = m; ctx.setParams({ metric: m.key }); seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === m.key))); draw(); } }, m.label)));
  f.body.before(h('div', { class: 'np-metric-bar' }, seg));
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
        ? `P2 cuts ${hubSt} AOG from ${fmtHours(g0.mean)} to ${fmtHours(g2.mean)} a year${u1 && u2 ? ` with ${fmtInt(u2)} outstation rotables, not ${fmtInt(u1)}` : ''}`
        : 'AOG hours by station and policy';
      subExtra = outs.length ? `Outstations ${fmtHours(o2)} under P2 vs ${fmtHours(o1)} under P1` : '';
    } else {
      const lows = outs.map((s) => ({ s, v: metric(pcBy('P2', s), mk.key)?.mean })).filter((d) => d.v != null);
      const avgP2 = lows.length ? d3().mean(lows, (d) => d.v) : null;
      const avgP1 = outs.map((s) => metric(pcBy('P1', s), mk.key)?.mean).filter((v) => v != null);
      head = avgP2 != null && avgP1.length ? `Outstation ${mk.label.toLowerCase()} averages ${fmtPct(avgP2)} under P2 vs ${fmtPct(d3().mean(avgP1))} under P1` : `${mk.label} by station and policy`;
    }
    f.root.querySelector('.chart-headline').textContent = head;
    const sub = f.root.querySelector('.chart-subtitle') || (() => { const d = h('div', { class: 'chart-subtitle' }); f.root.querySelector('.chart-headline').after(d); return d; })();
    const clamped = rows.some((r) => r.m.clamped);
    sub.textContent = [subExtra, `${splitLabel(n, p)} · mean and 95% CI${mk.key === 'aog_hours' ? ' · square-root scale' : ''}`, 'P0 legacy, P1 local, P2 network', clamped ? 'CI ends below 0 drawn at 0' : ''].filter(Boolean).join(' · ');
    sub.title = sub.textContent;
    f.setTable([{ key: 'station', label: 'Station' }, { key: 'pol', label: 'Policy' }, { key: 'mean', label: 'Mean', num: true, format: mk.fmt }, { key: 'lo', label: 'CI lo', num: true, format: mk.fmt }, { key: 'hi', label: 'CI hi', num: true, format: mk.fmt }], rows.map((r) => ({ station: r.station, pol: r.pol, mean: r.m.mean, lo: r.m.lo, hi: r.m.hi })));
    stop?.();
    stop = responsive(f.body, (w) => drawCompare(f.body, rows, order, mk, w));
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
  axisBottom(axG, x, { ticks: narrow ? 3 : 5, format: mk.fmt, height: sts.length * rowH });
  // a square-root scale bunches the top ticks: drop any tick label (and its grid line) that would sit within 56 px of the previous one
  if (mk.key === 'aog_hours') {
    let last = -1e9;
    const keep = new Set();
    axG.selectAll('.tick').each(function (t) { const px = x(t); if (px - last < 64 && t !== 0) d3().select(this).remove(); else { last = px; keep.add(t); } });
    g.selectAll('line.gnm-grid').filter((t) => !keep.has(t)).remove();
  }
  g.append('g').selectAll('text').data(sts).join('text').attr('class', 'gnm-label gnm-label--strong').attr('font-family', theme.font.mono).attr('x', -10).attr('y', (s) => y(s) + y.bandwidth() / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((s) => s);
  const pts = g.append('g').selectAll('g').data(rows).join('g').attr('transform', (r) => `translate(0,${y(r.station) + y.bandwidth() / 2 + off[r.pol]})`);
  pts.filter((r) => r.m.lo != null && r.m.hi != null).append('line').attr('x1', (r) => x(Math.max(x.domain()[0], r.m.lo))).attr('x2', (r) => x(r.m.hi)).attr('stroke', (r) => POL_COLOR[r.pol]).attr('stroke-width', 1.5).attr('stroke-opacity', 0.7);
  pts.append('circle').attr('cx', (r) => x(r.m.mean)).attr('r', 4).attr('fill', (r) => (r.pol === 'P2' ? SR.neutral : C.bg)).attr('stroke', (r) => POL_COLOR[r.pol]).attr('stroke-width', 1.75);
  withTooltip(pts, (r) => ({ title: `${r.pol} at ${r.station}`, rows: [['Mean', mk.fmt(r.m.mean)], ['95% CI', r.m.lo != null ? `${mk.fmt(r.m.lo)} – ${mk.fmt(r.m.hi)}` : '—']] }));
  // direct labels: policy names on the first row, values on the right for the hub row (wide only)
  const first = sts[0];
  POLS.forEach((pol) => {
    const r = rows.find((d) => d.station === first && d.pol === pol);
    if (!r) return;
    if (!narrow) dl(g, { x: iw + 10, y: y(first) + y.bandwidth() / 2 + off[pol], text: `${pol} ${mk.fmt(r.m.mean)}`, color: pol === 'P1' ? C.muted : POL_COLOR[pol], strong: pol === 'P2' });
  });
  if (narrow) POLS.forEach((pol, i) => dl(g, { x: i * 52 - m.left + 8, y: -14, text: `● ${pol}`, color: pol === 'P1' ? C.muted : POL_COLOR[pol], strong: pol === 'P2' }));
  else dl(g, { x: iw + 10, y: -12, text: first, color: C.faint });
  if (mk.key === 'aog_hours') {
    const r0 = rows.find((d) => d.station === first && d.pol === 'P0');
    const r2 = rows.find((d) => d.station === first && d.pol === 'P2');
    if (r0 && r2 && sts.length > 1) {
      if (narrow) {
        // no room for a leader inside the row at 390: state the delta in the legend line instead
        dl(g, { x: iw, y: -14, text: `${first} P2 −${fmtHours(r0.m.mean - r2.m.mean)} vs P0`, anchor: 'end', color: C.text, strong: true });
      } else {
        const xa = x(r2.m.mean), ya = y(first) + y.bandwidth() / 2 + off.P2;
        annotate(g, { x: xa, y: ya, dx: -48, dy: -6, title: `${first} −${fmtHours(r0.m.mean - r2.m.mean)}`, sub: 'P2 vs P0' });
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
  const f = chartFrame(host, {
    headline: share0 != null ? `${fmtPct(share0, 0)} of P0’s AOG hours are at the ${hub.station} hub, not the outstations` : 'Hub vs outstation AOG: not run',
    subtitle: `AOG h / yr · hub vs sum of outstations · ${splitLabel(n, p)} · means`,
    provenance: prov(n.meta), source: 'network.json → policy_compare',
    table: { columns: [{ key: 'pol', label: 'Policy' }, { key: 'hub', label: 'Hub AOG h', num: true, format: fmtHours }, { key: 'out', label: 'Outstations AOG h', num: true, format: fmtHours }], rows },
  });
  if (!rows.length) { f.body.append(h('div', { class: 'state' }, 'not run')); return null; }
  const stop = responsive(f.body, (w) => {
    const rowH = 44, m = { top: 8, right: 8, bottom: 8, left: 32 };
    const hgt = m.top + m.bottom + rows.length * rowH;
    const iw = w - m.left - m.right;
    const svg = svgIn(f.body, w, hgt, 'AOG hours, hub versus outstations, by policy');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const x = d3().scaleLinear().domain([0, d3().max(rows, (r) => r.hub + r.out)]).range([0, iw]);
    rows.forEach((r, i) => {
      const yy = i * rowH;
      dl(g, { x: -8, y: yy + 22, text: r.pol, anchor: 'end', color: r.pol === 'P2' ? C.text : C.muted, strong: r.pol === 'P2' });
      g.append('rect').attr('x', 0).attr('y', yy + 14).attr('width', Math.max(1, x(r.hub))).attr('height', 16).attr('rx', 2).attr('fill', SR.neutral).attr('fill-opacity', r.pol === 'P2' ? 0.85 : 0.6);
      g.append('rect').attr('x', x(r.hub) + 1).attr('y', yy + 14).attr('width', Math.max(1, x(r.out))).attr('height', 16).attr('rx', 2).attr('fill', SR.context).attr('fill-opacity', 0.55);
      const txt = `hub ${fmtHours(r.hub)} · out ${fmtHours(r.out)}`;
      const tx = x(r.hub + r.out) + 6;
      if (tx + txt.length * 6.4 < iw) dl(g, { x: tx, y: yy + 22, text: txt, color: C.muted });
      else dl(g, { x: 0, y: yy + 6, text: truncate(txt, iw, 6.4), color: C.muted });
    });
  });
  const items = [];
  if (r0 && r2) items.push([`Pooling at the hub pays most.`, ` P2 cuts hub AOG by ${fmtHours(r0.hub - r2.hub)} a year versus P0, with ${fmtHours(r2.out)} left across all outstations.`]);
  if (r1 && r2) items.push([`Local floats miss the hub.`, ` P1 stocks every outstation, yet leaves ${fmtHours(r1.hub)} of AOG at ${hub.station}${r0 ? ` (P0: ${fmtHours(r0.hub)})` : ''}.`]);
  items.push(['Selective positioning.', ' Outstation units go where D0 exposure and transport time justify them; D3/D10 demand is covered from the hub within the deadline.']);
  f.body.after(h('ul', { class: 'np-findings' }, items.map(([a, b]) => h('li', {}, icon('target'), h('div', {}, h('strong', {}, a), b)))));
  return stop;
}
