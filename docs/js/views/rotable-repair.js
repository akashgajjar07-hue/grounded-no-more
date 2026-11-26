/**
 * 04 · Rotable & Repair Control
 * Data: rotables.json (+ method.json for the assumption register).
 * Deep links: #/rotables?pn=GN-32-R014&shop=EU_VENDOR
 *
 * Sections
 *  1. Status strip (units in the loop, open / overdue ROs, quoted-vs-actual TAT)
 *  2. Serial lifecycle flow (rotable-lifecycle.svg with injected counts)
 *  3. Repair-queue Gantt (open + recent ROs by shop, quoted due vs actual, overdue alerts)
 *  4. TAT: actual vs quoted by PN and shop
 *  5. Float calculator (METRIC-inspired, Palm's theorem) — maths from lib/floatcalc.js only
 *  6. Palm vs simulation
 * Every number comes from the JSON or from floatcalc.js applied to user inputs.
 */
import { h, icon, pageHead, card, provChip, pill, dataTable, bindValueText } from '../ui.js';
import { chartFrame, responsive, svgIn, axisBottom, axisLeft, gridY, directLabel, annotate, withTooltip, truncate, theme, chipLabel, refLine, fmtAED, fmtPct, fmtDays, fmtInt, fmtNum, fmtWeek, fmtEnum, fmtCount, plural } from '../charts/theme.js';
import { floatCalc, compareLevers, pmfSeries } from '../lib/floatcalc.js';

export const data = ['rotables', 'method', 'network'];

const d3 = () => window.d3;
/** directLabel whose colour wins over the .gnm-label CSS fill. */
const dl = (g, o) => directLabel(g, o).style('fill', o.color || null);
const HPD = 24, HPW = 168;
const C = theme.color;
const SR = theme.series;

let cssLoaded = false;
function loadCSS() {
  if (cssLoaded || document.querySelector('link[data-view-css="rotable-repair"]')) { cssLoaded = true; return; }
  const l = document.createElement('link');
  l.rel = 'stylesheet';
  l.href = new URL('../../css/views/rotable-repair.css', import.meta.url).href;
  l.dataset.viewCss = 'rotable-repair';
  document.head.append(l);
  cssLoaded = true;
}

// ----------------------------------------------------------------------------- data helpers
const num = (v) => (v == null || v === '' || Number.isNaN(+v) ? null : +v);
const pick = (o, ...keys) => { for (const k of keys) { const v = o?.[k]; if (v != null && v !== '') return v; } return null; };
const shopLabel = (s) => (s ? fmtEnum(s) : '—');
/** An overdue RO is critical (urgent red + alert icon) only when it is more than this many days past quoted due. */
const CRITICAL_LATE_D = 28;
const isCritical = (o) => !!(o.open && o.overdue && (o.late_d ?? 0) > CRITICAL_LATE_D);
const prov = (obj, fallback = 'SIMULATED') => obj?.provenance || fallback;
const median = (a) => { const s = a.filter((x) => x != null).sort((x, y) => x - y); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

function asOfHour(r) {
  const direct = num(pick(r, 'as_of_h', 'now_h')) ?? num(pick(r.meta || {}, 'as_of_h'));
  if (direct != null) return direct;
  const q = r.repair_queue || [];
  const ts = q.flatMap((o) => [o.shop_in_h, o.start_h, o.return_h]).filter((x) => x != null);
  return ts.length ? Math.max(...ts) : null;
}

/** Normalise one RO: quoted TAT, actual (or elapsed) TAT, lateness, state. */
function normRO(o, now) {
  const start = num(o.start_h) ?? num(o.shop_in_h);
  const inH = num(o.shop_in_h) ?? start;
  const due = num(o.due_h);
  const ret = num(o.return_h);
  const open = o.status ? o.status === 'open' : ret == null;
  const end = open ? now : ret;
  const overdue = o.overdue != null ? !!o.overdue : open && due != null && now != null && now > due;
  const lateD = due != null && end != null ? (end - due) / HPD : null;
  return {
    ...o, start, inH, due, ret, open, end, overdue,
    quoted_tat_d: num(o.quoted_tat_d) ?? (due != null && start != null ? (due - start) / HPD : null),
    actual_tat_d: num(o.actual_tat_d) ?? (!open && start != null ? (ret - start) / HPD : null),
    elapsed_d: start != null && end != null ? (end - start) / HPD : null,
    late_d: lateD,
    planted: o.planted || o.ps || null,
  };
}

// ----------------------------------------------------------------------------- view
export async function render(el, ctx) {
  loadCSS();
  const { rotables: r, method } = ctx.data;
  const cleanups = [];
  const now = asOfHour(r);
  const ros = (r.repair_queue || []).map((o) => normRO(o, now));
  const openROs = ros.filter((o) => o.open);
  const overdueROs = ros.filter((o) => o.open && o.overdue);
  const counts = r.lifecycle?.counts || {};
  const flows = r.lifecycle?.flows || [];
  const fixture = !!r.meta?.fixture;

  el.append(pageHead({
    num: '04', eyebrow: 'Rotable & Repair Control',
    title: 'Every serial, every repair order, every day of float',
    lede: 'Serialised rotables of Falcon Hub Airways (fictional) cycle through fit, removal, shop and return. This workspace tracks the loop, flags overdue repair orders and sizes the float with a METRIC-inspired (Palm’s theorem) calculator.',
    meta: [provChip(prov(r.meta)), provChip('DERIVED'), now != null ? h('span', { class: 'chip chip-mono' }, `As of ${fmtWeek(Math.floor(now / HPW))}`) : null].filter(Boolean),
  }));

  // ---------------------------------------------------------------- 1. status strip
  const loop = (num(counts.REMOVED) ?? 0) + (num(counts.IN_REPAIR) ?? 0);
  const fleet = Object.entries(counts).filter(([k]) => k !== 'CONDEMNED').reduce((s, [, v]) => s + (num(v) ?? 0), 0);
  const tatRows = (r.tat || []).filter((t) => num(t.quoted_d) && num(t.actual_mean_d) != null);
  const tatRatio = median(tatRows.map((t) => t.actual_mean_d / t.quoted_d));
  const lateShare = tatRows.length ? tatRows.filter((t) => t.actual_mean_d > t.quoted_d).length / tatRows.length : null;
  const stat = ({ label, value, unit, sub, chip, alert, story }) => h('div', { class: `rr-stat ${alert ? 'is-alert' : ''}`, dataset: story ? { story } : undefined },
    h('div', { class: 'rr-stat-top' }, h('div', { class: 'rr-stat-label' }, label), provChip(chip)),
    h('div', { class: 'rr-stat-value' }, value, unit ? h('small', {}, unit) : null),
    h('div', { class: 'rr-stat-sub' }, sub));
  el.append(h('div', { class: 'rr-stats mt-3', dataset: { story: 'rotable-stats' } },
    stat({ label: 'Units in repair loop', value: fmtInt(loop), unit: 'serials', sub: fleet ? `${fmtPct(loop / fleet)} of ${fmtInt(fleet)} active serials are removed (U/S) or in a shop` : 'Lifecycle counts not exported', chip: prov(r.lifecycle, prov(r.meta)) }),
    stat({ label: 'Open repair orders', value: fmtInt(r.repair_summary?.open ?? openROs.length), unit: 'ROs', sub: `${fmtInt(new Set(openROs.map((o) => o.shop)).size)} shops · ${fmtInt(r.repair_summary?.returned_last_8w ?? ros.length - openROs.length)} returned in the last 8 weeks`, chip: prov(r.meta) }),
    stat({ label: 'Overdue vs quoted due', value: fmtInt(r.repair_summary?.overdue ?? overdueROs.length), unit: 'ROs', sub: overdueROs.length ? h('span', { class: 'rr-stat-crit' }, overdueROs.some(isCritical) ? icon('alert') : null, `${plural(overdueROs.filter(isCritical).length, 'RO')} more than ${Math.round(CRITICAL_LATE_D / 7)} weeks late`) : 'None overdue', chip: prov(r.meta) }),
    stat({ label: 'Actual / quoted TAT', value: tatRatio != null ? `${fmtNum(tatRatio, 2)}×` : 'not run', sub: lateShare != null ? `Median over ${fmtInt(tatRows.length)} PN–shop pairs · ${fmtPct(lateShare, 0)} run late` : 'TAT table not exported', chip: prov(r.tat?.[0], prov(r.meta)) }),
  ));

  // ---------------------------------------------------------------- 2. lifecycle
  const lcCard = card({ bp: true, cls: 'mt-3', story: 'rotable-lifecycle', body: [] });
  el.append(lcCard);
  const sumF = (pred) => flows.filter(pred).reduce((t, f) => t + (num(f.count) ?? 0), 0);
  const removals = sumF((f) => f.from === 'INSTALLED' && f.to !== 'INSTALLED');
  const shopOut = sumF((f) => f.from === 'IN_REPAIR' && f.to !== 'IN_REPAIR');
  const condemned = sumF((f) => f.from === 'IN_REPAIR' && f.to === 'CONDEMNED');
  const flowWindow = r.lifecycle?.window_label || (r.lifecycle?.window_weeks ? `weeks ${r.lifecycle.window_weeks.join('–')}` : now != null ? `weeks 0–${Math.floor(now / HPW) - 1}` : null);
  const lcHead = flows.length && shopOut
    ? `${fmtInt(removals)} removals fed the repair loop; ${fmtPct(condemned / shopOut)} of shop exits were condemned (BER)`
    : `${fmtInt(loop)} serials are removed (U/S) or in repair right now`;
  const lcF = chartFrame(lcCard, {
    headline: lcHead,
    subtitle: `Box = serials in each state at ${now != null ? fmtWeek(Math.floor(now / HPW)) : 'end of window'} (${fmtInt(r.lifecycle?.n_serials ?? fleet)} serials) · one row per transition, dot = from, arrow = to, width = count${flowWindow ? ` over ${flowWindow}` : ''}`,
    provenance: prov(r.lifecycle, prov(r.meta)), source: 'rotables.json → lifecycle',
    table: { columns: [{ key: 'item', label: 'State / transition' }, { key: 'count', label: 'Serials', num: true, format: fmtInt }], rows: [...Object.entries(counts).map(([k, v]) => ({ item: stateName(k), count: v })), ...flows.map((f) => ({ item: `${stateName(f.from)} → ${stateName(f.to)}`, count: f.count }))] },
  });
  const lcHost = h('div', { class: 'rr-flow' });
  lcF.body.append(lcHost, h('p', { class: 'rr-lc-note' }, 'Each serial is in exactly one state. Outstation removals travel to AUH as unserviceable cores before induction; hub removals go straight to the shop. BER units are condemned and replaced by purchase order.'));
  cleanups.push(responsive(lcHost, (w) => drawFlow(lcHost, r.lifecycle?.states || Object.keys(counts), counts, flows, w)));
  // ---------------------------------------------------------------- 3. repair queue gantt + 4. TAT
  const grid = h('div', { class: 'grid-12 mt-3' });
  el.append(grid);
  const ganttCard = h('section', { class: 'card span-7', dataset: { story: 'repair-queue' } });
  const tatCard = h('section', { class: 'card span-5', dataset: { story: 'rotable-tat' } });
  grid.append(ganttCard, tatCard);
  cleanups.push(renderGantt(ganttCard, ros, now, r, ctx));
  cleanups.push(renderTatDist(tatCard, r));
  cleanups.push(renderTat(tatCard, r));

  // ---------------------------------------------------------------- 5. float calculator
  const fcCard = h('section', { class: 'card mt-3', dataset: { story: 'rotable-float-calc' }, id: 'float-calculator' });
  el.append(fcCard);
  cleanups.push(renderFloatCalc(fcCard, r, method, ctx));

  // ---------------------------------------------------------------- 6. Palm vs sim
  const pvGrid = h('div', { class: 'grid-12 mt-3' });
  el.append(pvGrid);
  const pvCard = h('section', { class: 'card span-7', dataset: { story: 'palm-vs-sim' } });
  const whyCard = card({ cls: 'span-5', kicker: 'Why analytic and simulated differ', title: 'Palm assumes an infinite, stationary repair loop. The simulated network does not.', prov: 'DERIVED', body: whyList(r) });
  pvGrid.append(pvCard, whyCard);
  cleanups.push(renderPalmVsSim(pvCard, r, ctx.data.network?.hub || ctx.data.network?.stations?.find((s) => s.role === 'hub')?.station));

  // ---------------------------------------------------------------- open ROs table
  const tableRows = ros.filter((o) => o.open).sort((a, b) => (b.overdue - a.overdue) || ((b.late_d ?? -1e9) - (a.late_d ?? -1e9)));
  el.append(h('div', { class: 'mt-3' }, card({
    kicker: 'Repair orders', title: `${fmtInt(tableRows.length)} open repair orders, most days past due first`, prov: prov(r.meta),
    body: dataTable({
      caption: 'Open repair orders', maxHeight: 360, dense: true,
      mobileColumns: ['serial', 'late_d', 'shop', 'ro_id', 'overdue'], stickyFirst: true,
      columns: [
        { key: 'ro_id', label: 'RO', mono: true },
        { key: 'serial', label: 'Serial', mono: true },
        { key: 'shop', label: 'Shop', format: shopLabel },
        { key: 'inH', label: 'Inducted', num: true, format: (v) => (v == null ? '—' : fmtWeek(Math.floor(v / HPW))) },
        { key: 'due', label: 'Quoted due', num: true, format: (v) => (v == null ? '—' : fmtWeek(Math.floor(v / HPW))) },
        { key: 'late_d', label: 'vs due', short: 'vs due', num: true, format: (v) => (v == null ? '—' : v > 0 ? `+${fmtDays(v)}` : `−${fmtDays(-v)}`) },
        { key: 'overdue', label: 'Status', render: (o) => (isCritical(o) ? pill('urgent', o.planted ? `Critical · ${o.planted}` : 'Critical') : o.overdue ? h('span', { class: 'pill pill--unknown rr-pill-late' }, o.planted ? `Overdue · ${o.planted}` : 'Overdue') : h('span', { class: 'pill pill--unknown rr-pill-quote' }, 'In quote')) },
      ],
      rows: tableRows, sort: { key: 'late_d', dir: 'desc' }, // F7 (wave 4): the mobile Sort control names the real order
    }),
  })));

  if (fixture) console.info('rotable-repair: running on fixtures');
  return () => cleanups.forEach((fn) => { try { fn?.(); } catch { /* ignore */ } });
}

// ============================================================================= lifecycle state ladder
const STATE_META = {
  SERVICEABLE: { label: 'SERVICEABLE', short: 'Serviceable', sub: 'In stores' },
  INSTALLED: { label: 'INSTALLED', short: 'Installed', sub: 'On aircraft' },
  REMOVED: { label: 'REMOVED (U/S)', short: 'Removed', sub: 'Core to AUH' },
  IN_REPAIR: { label: 'IN REPAIR', short: 'In repair', sub: 'Queue + shop' },
  IN_TRANSIT: { label: 'IN TRANSIT', short: 'In transit', sub: 'Return · position' },
  CONDEMNED: { label: 'CONDEMNED', short: 'Condemned', sub: 'BER · PO' },
};
const stateName = (s) => STATE_META[s]?.short || shopLabel(s);
/**
 * State ladder. Boxes sit left → right in lifecycle order. Under them, every transition gets its OWN row:
 * a straight connector from the source column to the target column, with its count in a chip at the row's
 * midpoint. One connector per row means no two strokes cross and no chip can sit on another flow.
 * Forward flows (teal, the primary series) come first, then returns (titanium), then condemnation
 * (dashed titanium: BER is a cost, not an AOG risk). Phones get the same ladder as a list.
 */
function drawFlow(el, states, counts, flows, w) {
  const order = ['SERVICEABLE', 'INSTALLED', 'REMOVED', 'IN_REPAIR', 'IN_TRANSIT', 'CONDEMNED'].filter((s) => states.includes(s) || counts[s] != null);
  states.forEach((s) => { if (!order.includes(s)) order.push(s); });
  const n = order.length;
  const idx = (s) => order.indexOf(s);
  const kindOf = (f) => (f.to === 'CONDEMNED' ? 'bad' : idx(f.to) > idx(f.from) ? 'fwd' : 'back');
  const RANK = { fwd: 0, back: 1, bad: 2 };
  const fl = flows.filter((f) => f.from !== f.to && order.includes(f.from) && order.includes(f.to) && num(f.count))
    .slice().sort((a, b) => RANK[kindOf(a)] - RANK[kindOf(b)] || idx(a.from) - idx(b.from) || idx(a.to) - idx(b.to));
  const maxC = d3().max(fl, (f) => f.count) || 1;
  const KIND = {
    fwd: { color: SR.recommended, op: 0.55, label: 'FORWARD · fit → removal → shop → transit' },
    back: { color: SR.neutral, op: 0.5, label: 'RETURNS · back to stock or onto aircraft' },
    bad: { color: SR.context, op: 0.9, dash: '5 4', label: 'CONDEMNED · beyond economic repair' },
  };
  const tip = (f) => ({ title: `${STATE_META[f.from]?.label || f.from} → ${STATE_META[f.to]?.label || f.to}`, rows: [['Transitions', fmtInt(f.count)], ['Share of largest flow', fmtPct(f.count / maxC, 0)]] });
  if (w < 640) return drawFlowList(el, order, counts, fl, w, { kindOf, KIND, maxC, tip });

  const boxW = Math.min(176, (w - (n - 1) * 16) / n);
  const gap = (w - n * boxW) / (n - 1);
  const boxH = 84, rowH = 28, headH = 24, top = 2;
  const cx = (s) => idx(s) * (boxW + gap) + boxW / 2;
  // layout rows: a group header before each kind, then one row per flow
  let y = top + boxH + 14;
  const rows = [];
  let prevKind = null;
  fl.forEach((f) => {
    const k = kindOf(f);
    if (k !== prevKind) { rows.push({ header: k, y: y + 14 }); y += headH; prevKind = k; }
    rows.push({ f, k, y: y + rowH / 2 }); y += rowH;
  });
  const hgt = Math.round(y + 6);
  const svg = svgIn(el, w, hgt, `Rotable lifecycle: ${order.map((s) => `${stateName(s)} ${counts[s] ?? 0}`).join(', ')}`);
  const defs = svg.append('defs');
  Object.entries(KIND).forEach(([k, o]) => defs.append('marker').attr('id', `rr-arr-${k}`).attr('viewBox', '0 0 10 10').attr('refX', 9).attr('refY', 5).attr('markerWidth', 8).attr('markerHeight', 8).attr('orient', 'auto').attr('markerUnits', 'userSpaceOnUse')
    .append('path').attr('d', 'M0,1L10,5L0,9L2.5,5Z').attr('fill', o.color));
  // column guides: hairlines from each box down through the ladder
  svg.append('g').selectAll('line').data(order).join('line').attr('class', 'rr-guide')
    .attr('x1', (s) => cx(s)).attr('x2', (s) => cx(s)).attr('y1', top + boxH).attr('y2', hgt - 4);
  const sw = d3().scaleSqrt().domain([0, maxC]).range([2, 10]);
  const rowG = svg.append('g').attr('class', 'rr-arcs');
  rows.forEach((r) => {
    if (r.header) { dl(rowG, { x: 0, y: r.y, text: KIND[r.header].label, color: KIND[r.header].color, mono: true }); return; }
    const { f, k } = r;
    const o = KIND[k];
    const x1 = cx(f.from), x2 = cx(f.to);
    const dir = x2 > x1 ? 1 : -1;
    const g = rowG.append('g').attr('class', `rr-arc rr-arc--${k}`).attr('tabindex', 0).attr('role', 'img')
      .attr('aria-label', `${stateName(f.from)} to ${stateName(f.to)}: ${fmtInt(f.count)} transitions`);
    g.append('rect').attr('x', Math.min(x1, x2) - 8).attr('y', r.y - rowH / 2).attr('width', Math.abs(x2 - x1) + 16).attr('height', rowH).attr('fill', 'transparent');
    g.append('circle').attr('cx', x1).attr('cy', r.y).attr('r', 3.5).attr('fill', o.color);
    g.append('line').attr('x1', x1).attr('x2', x2 - dir * 10).attr('y1', r.y).attr('y2', r.y)
      .attr('stroke', o.color).attr('stroke-opacity', o.op).attr('stroke-width', sw(f.count)).attr('stroke-dasharray', o.dash || null);
    g.append('line').attr('x1', x1).attr('x2', x2).attr('y1', r.y).attr('y2', r.y).attr('stroke', o.color).attr('stroke-width', 1).attr('marker-end', `url(#rr-arr-${k})`);
    chipLabel(g, { x: (x1 + x2) / 2, y: r.y, text: fmtInt(f.count), color: C.text, cls: 'rr-flow-chip' });
    // wave 4: every desktop lane names its own transition ("Serviceable → Installed"), as the phone ladder does
    const name = `${stateName(f.from)} → ${stateName(f.to)}`;
    const tw = name.length * 6.6;
    const lo = Math.min(x1, x2), hi = Math.max(x1, x2);
    const right = hi + 12 + tw <= w, left = lo - 12 - tw >= 0;
    if (right || left) g.append('text').attr('class', 'gnm-label rr-lane-name').attr('x', right ? hi + 12 : lo - 12).attr('y', r.y).attr('dy', '0.32em').attr('text-anchor', right ? 'start' : 'end').text(name);
    withTooltip(g, () => tip(f));
  });
  const nodes = svg.append('g').selectAll('g').data(order).join('g').attr('class', 'rr-node-g').attr('transform', (s) => `translate(${idx(s) * (boxW + gap)},${top})`);
  nodes.append('rect').attr('width', boxW).attr('height', boxH).attr('rx', 10).attr('class', (s) => `rr-node ${s === 'CONDEMNED' ? 'is-bad' : ''} ${s === 'IN_REPAIR' ? 'is-active' : ''}`);
  nodes.append('text').attr('x', 12).attr('y', 22).attr('class', 'rr-node-state').text((s) => truncate(STATE_META[s]?.label || s, boxW - 20, 7));
  nodes.append('text').attr('x', 12).attr('y', 56).attr('class', 'rr-node-count').text((s) => fmtInt(counts[s] ?? 0));
  nodes.append('text').attr('x', 12).attr('y', 74).attr('class', 'rr-node-sub').text((s) => truncate(STATE_META[s]?.sub || '', boxW - 20, 6.2));
}

/** Phone ladder: state tiles in a 3-column grid, then one row per transition (name, count, bar). */
function drawFlowList(el, order, counts, fl, w, { kindOf, KIND, maxC, tip }) {
  const cols = 3, tileGap = 8;
  const tileW = (w - (cols - 1) * tileGap) / cols, tileH = 56;
  const tilesH = Math.ceil(order.length / cols) * (tileH + tileGap);
  const rowH = 34, headH = 22;
  let y = tilesH + 8;
  const rows = [];
  let prevKind = null;
  fl.forEach((f) => {
    const k = kindOf(f);
    if (k !== prevKind) { rows.push({ header: k, y: y + 14 }); y += headH; prevKind = k; }
    rows.push({ f, k, y }); y += rowH;
  });
  const svg = svgIn(el, w, Math.round(y + 4), `Rotable lifecycle: ${order.map((s) => `${stateName(s)} ${counts[s] ?? 0}`).join(', ')}`);
  const tiles = svg.append('g').selectAll('g').data(order).join('g').attr('class', 'rr-node-g')
    .attr('transform', (s, i) => `translate(${(i % cols) * (tileW + tileGap)},${Math.floor(i / cols) * (tileH + tileGap)})`);
  tiles.append('rect').attr('width', tileW).attr('height', tileH).attr('rx', 8).attr('class', (s) => `rr-node ${s === 'CONDEMNED' ? 'is-bad' : ''} ${s === 'IN_REPAIR' ? 'is-active' : ''}`);
  tiles.append('text').attr('x', 8).attr('y', 17).attr('class', 'rr-node-state').text((s) => truncate(stateName(s).toUpperCase(), tileW - 12, 6.8));
  tiles.append('text').attr('x', 8).attr('y', 44).attr('class', 'rr-node-count rr-node-count--sm').text((s) => fmtInt(counts[s] ?? 0));
  const valW = 44;
  const barX = 0, barW = w - valW - 8;
  rows.forEach((r) => {
    if (r.header) { dl(svg, { x: 0, y: r.y, text: r.header === 'fwd' ? 'FORWARD' : r.header === 'back' ? 'RETURNS' : 'CONDEMNED (BER)', color: KIND[r.header].color, mono: true }); return; }
    const { f, k } = r; const o = KIND[k];
    const g = svg.append('g').attr('class', `rr-arc rr-arc--${k}`).attr('transform', `translate(0,${r.y})`).attr('tabindex', 0).attr('role', 'img')
      .attr('aria-label', `${stateName(f.from)} to ${stateName(f.to)}: ${fmtInt(f.count)} transitions`);
    g.append('rect').attr('width', w).attr('height', rowH).attr('fill', 'transparent');
    g.append('text').attr('class', 'rr-ladder-name').attr('x', 0).attr('y', 12).text(`${stateName(f.from)} → ${stateName(f.to)}`);
    g.append('rect').attr('x', barX).attr('y', 20).attr('height', 6).attr('rx', 2).attr('width', barW).attr('fill', C.line);
    g.append('rect').attr('x', barX).attr('y', 20).attr('height', 6).attr('rx', 2).attr('width', Math.max(2, (barW * f.count) / maxC))
      .attr('fill', o.color).attr('fill-opacity', k === 'fwd' ? 0.75 : 0.6).attr('stroke', k === 'bad' ? o.color : null).attr('stroke-dasharray', o.dash || null);
    chipLabel(g, { x: w, y: 18, text: fmtInt(f.count), anchor: 'end', color: C.text, cls: 'rr-flow-chip' });
    withTooltip(g, () => tip(f));
  });
}

// ============================================================================= Gantt
function renderGantt(host, ros, now, r, ctx) {
  const shops = [...new Set(ros.map((o) => o.shop))].filter(Boolean).sort();
  let shopSel = shops.includes(ctx.params.shop) ? ctx.params.shop : 'ALL';
  let statusSel = ros.some((o) => o.open && o.overdue) ? 'overdue' : 'all';
  const ps2 = ros.find((o) => o.open && o.overdue && o.planted);
  const overdue = ros.filter((o) => o.open && o.overdue);
  const worst = ps2 || overdue.slice().sort((a, b) => (b.late_d ?? 0) - (a.late_d ?? 0))[0];
  // the serial lives in the chase list below; a hyphenated serial wraps badly inside a headline
  const head = !overdue.length ? 'Every open repair order is still inside its quoted due date'
    : `${fmtInt(overdue.length)} repair orders are past quoted due${worst ? `; the worst is ${fmtDays(worst.late_d)} late at ${shopLabel(worst.shop)}` : ''}`;
  const f = chartFrame(host, {
    headline: head,
    subtitle: `Bar = induction → return (or now) · tick = quoted due · hatched = days past due, red only beyond ${fmtInt(CRITICAL_LATE_D)} d · shops by worst delay${now != null ? ` · now ${fmtWeek(Math.floor(now / HPW))}` : ''}`,
    provenance: prov(r.meta), source: 'rotables.json → repair_queue',
    table: { columns: [{ key: 'ro_id', label: 'RO' }, { key: 'serial', label: 'Serial' }, { key: 'shop', label: 'Shop', format: shopLabel }, { key: 'quoted_tat_d', label: 'Quoted TAT', num: true, format: fmtDays }, { key: 'elapsed_d', label: 'Elapsed / actual', num: true, format: fmtDays }, { key: 'late_d', label: 'Days vs due', num: true, format: (v) => (v == null ? '—' : fmtNum(v, 0)) }, { key: 'open', label: 'Open', format: (v) => (v ? 'yes' : 'no') }], rows: ros },
  });
  const shopSeg = segmentedLite([{ value: 'ALL', label: 'All shops' }, ...shops.map((s) => ({ value: s, label: shopLabel(s) }))], shopSel, (v) => { shopSel = v; ctx.setParams({ shop: v === 'ALL' ? undefined : v }); redraw(); }, 'Filter by shop');
  const statSeg = segmentedLite([{ value: 'all', label: 'Open + recent' }, { value: 'open', label: 'Open' }, { value: 'overdue', label: 'Overdue' }], statusSel, (v) => { statusSel = v; redraw(); }, 'Filter by status');
  f.body.before(h('div', { class: 'rr-filters' }, shopSeg, statSeg));
  const scroll = h('div', { class: 'rr-gantt-scroll', tabindex: '0', role: 'region', 'aria-label': 'Repair order timeline' });
  const chart = h('div', { class: 'rr-gantt' });
  scroll.append(chart);
  f.body.append(scroll, h('div', { class: 'rr-key', 'aria-hidden': 'true' },
    h('span', {}, h('i', { style: { background: 'rgba(34,199,184,0.45)' } }), 'Open, inside quote'),
    h('span', {}, h('i', { style: { background: 'rgba(185,200,214,0.22)' } }), 'Returned'),
    h('span', {}, h('i', { class: 'rr-key-late' }), 'Past quoted due'),
    h('span', {}, h('i', { style: { background: C.urgent } }), `Critical: > ${fmtInt(CRITICAL_LATE_D)} d past due`),
    h('span', {}, h('i', { style: { background: C.text, width: '2px', height: '12px' } }), 'Quoted due date')));
  const topOverdue = overdue.slice().sort((a, b) => ((b.late_d ?? 0) - (a.late_d ?? 0)) || (!!b.planted - !!a.planted)).slice(0, 3);
  if (topOverdue.length) {
    const chase = h('div', { class: 'rr-chase', role: 'list', 'aria-label': 'Overdue repair orders to chase first' },
      h('div', { class: 'rr-chase-head' }, h('span', {}, 'Chase first'), h('span', { class: 'rr-chase-rule' }, '· most days past quoted due'), overdue.length > topOverdue.length ? h('span', { class: 'rr-chase-more' }, `+ ${fmtInt(overdue.length - topOverdue.length)} more overdue in the table below`) : null),
      ...topOverdue.map((o) => h('div', { class: `rr-alert ${isCritical(o) ? 'is-crit' : ''}`, role: 'listitem' },
        h('span', { class: 'rr-alert-late' }, isCritical(o) ? icon('alert', { label: 'critical' }) : null, `+${fmtDays(o.late_d)}`),
        h('span', { class: 'rr-alert-id mono' }, o.serial),
        h('span', { class: 'rr-alert-shop' }, `${shopLabel(o.shop)} · ${o.ro_id} · due ${o.due != null ? fmtWeek(Math.floor(o.due / HPW)) : '—'}`),
        o.planted ? h('span', { class: 'chip chip-mono rr-alert-ps' }, o.planted) : h('span'))));
    f.body.append(chase);
  }

  let stop = null;
  function rows() {
    let a = ros.filter((o) => shopSel === 'ALL' || o.shop === shopSel);
    if (statusSel === 'open') a = a.filter((o) => o.open);
    if (statusSel === 'overdue') a = a.filter((o) => o.open && o.overdue);
    // shops with the worst delay first, so the most urgent rows are visible without scrolling
    const worstBy = new Map();
    a.forEach((o) => worstBy.set(o.shop, Math.max(worstBy.get(o.shop) ?? -1e9, o.open && o.overdue ? (o.late_d ?? 0) : -1e6)));
    return a.sort((x, y) => (worstBy.get(y.shop) - worstBy.get(x.shop)) || String(x.shop).localeCompare(String(y.shop)) || (x.inH ?? 0) - (y.inH ?? 0));
  }
  function redraw() {
    stop?.();
    stop = responsive(chart, (w) => drawGantt(chart, rows(), now, w));
  }
  redraw();
  return () => stop?.();
}

function segmentedLite(options, value, onChange, label) {
  const g = h('div', { class: 'seg', role: 'radiogroup', 'aria-label': label });
  const set = (v) => { [...g.children].forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === String(v)))); onChange(v); };
  options.forEach((o) => g.append(h('button', { type: 'button', role: 'radio', dataset: { value: o.value }, 'aria-checked': String(o.value === value), onclick: () => set(o.value) }, o.label)));
  return g;
}

function drawGantt(el, rows, now, w) {
  if (!rows.length) { el.replaceChildren(h('div', { class: 'state' }, 'No repair orders match this filter.')); return; }
  const narrow = w < 560;
  const rowH = 20, shopH = 26;
  const labelW = narrow ? 76 : 150;
  const hasPlanted = rows.some((o) => o.planted && o.open && o.overdue);
  const m = { top: 8, right: narrow ? 52 : hasPlanted ? 96 : 64, bottom: 28, left: labelW };
  const shops = [...new Set(rows.map((o) => o.shop))];
  const hgt = m.top + m.bottom + rows.length * rowH + shops.length * shopH;
  const iw = Math.max(60, w - m.left - m.right);
  const svg = svgIn(el, w, hgt, 'Repair order Gantt chart');
  svg.append('defs').append('pattern').attr('id', 'rr-hatch').attr('width', 5).attr('height', 5).attr('patternUnits', 'userSpaceOnUse').attr('patternTransform', 'rotate(45)')
    .call((pt) => { pt.append('rect').attr('width', 5).attr('height', 5).attr('fill', 'rgba(185,200,214,0.18)'); pt.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 5).attr('stroke', 'rgba(185,200,214,0.75)').attr('stroke-width', 2); });
  const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
  const lo = d3().min(rows, (o) => o.inH ?? o.start);
  const hi = d3().max(rows, (o) => Math.max(o.end ?? 0, o.due ?? 0, now ?? 0));
  const x = d3().scaleLinear().domain([lo, hi + (hi - lo) * 0.02]).range([0, iw]);
  // layout
  let yCur = 0;
  const pos = new Map();
  const bands = [];
  shops.forEach((s) => {
    const rs = rows.filter((o) => o.shop === s);
    bands.push({ shop: s, y: yCur, h: shopH + rs.length * rowH, n: rs.length });
    yCur += shopH;
    rs.forEach((o) => { pos.set(o, yCur); yCur += rowH; });
  });
  const ih = yCur;
  g.append('g').selectAll('rect').data(bands).join('rect').attr('class', 'rr-shop-band').attr('x', -labelW + 4).attr('width', iw + labelW - 4).attr('y', (b) => b.y).attr('height', (b) => b.h).attr('rx', 6);
  g.append('g').selectAll('text').data(bands).join('text').attr('class', 'rr-shop-label').attr('x', -labelW + 12).attr('y', (b) => b.y + 17)
    .text((b) => { const od = rows.filter((o) => o.shop === b.shop && o.open && o.overdue).length; return `${shopLabel(b.shop)} · ${b.n} RO${b.n === 1 ? '' : 's'}${od && od < b.n ? ` · ${od} overdue` : ''}`; });
  axisBottom(g.append('g'), x, { ticks: narrow ? 3 : 6, format: (v) => fmtWeek(Math.floor(v / HPW)), height: ih });
  if (now != null) {
    g.append('line').attr('class', 'rr-now').attr('x1', x(now)).attr('x2', x(now)).attr('y1', 0).attr('y2', ih);
    dl(g, { x: x(now) - 4, y: 10, text: 'NOW', anchor: 'end', color: C.accentHi });
  }
  const rowG = g.append('g').selectAll('g').data(rows).join('g').attr('class', 'rr-row').attr('transform', (o) => `translate(0,${pos.get(o)})`)
    .attr('tabindex', 0).attr('role', 'listitem')
    .attr('aria-label', (o) => `${o.ro_id}, serial ${o.serial}, ${shopLabel(o.shop)}, ${o.open ? 'open' : 'returned'}, ${o.overdue ? `overdue ${fmtDays(o.late_d)}` : 'within quote'}`);
  rowG.filter((o) => !!o.planted).append('rect').attr('class', 'rr-row-hl').attr('x', -labelW + 6).attr('y', 1).attr('width', iw + labelW - 8).attr('height', rowH - 2).attr('rx', 4);
  rowG.append('rect').attr('class', 'rr-focus').attr('x', -labelW + 6).attr('y', 1).attr('width', iw + labelW - 8).attr('height', rowH - 2).attr('rx', 4).attr('fill', 'none');
  rowG.append('text').attr('class', (o) => (o.planted ? 'gnm-label gnm-label--strong' : 'gnm-label')).attr('font-family', theme.font.mono).attr('x', -8).attr('y', rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'end').style('font-size', '11px')
    .text((o) => truncate(narrow ? o.ro_id : `${o.serial}`, labelW - 20, 6.6));
  const bx = (o) => x(o.inH ?? o.start);
  const ex = (o) => x(o.end ?? o.inH);
  rowG.append('rect').attr('class', (o) => `rr-bar ${o.open ? 'is-open' : ''}`).attr('x', bx).attr('y', 5).attr('height', rowH - 10).attr('rx', 2)
    .attr('width', (o) => Math.max(2, (o.overdue && o.due != null ? x(Math.max(o.due, o.inH ?? o.due)) : ex(o)) - bx(o)));
  rowG.filter((o) => o.due != null && o.end != null && o.end > o.due).append('rect').attr('class', (o) => `rr-bar-late ${isCritical(o) ? 'is-crit' : ''}`).attr('x', (o) => x(Math.max(o.due, o.inH ?? o.due))).attr('y', 5).attr('height', rowH - 10).attr('rx', 2)
    .attr('width', (o) => Math.max(1.5, ex(o) - x(Math.max(o.due, o.inH ?? o.due))));
  rowG.filter((o) => o.due != null).append('line').attr('class', 'rr-due').attr('x1', (o) => x(o.due)).attr('x2', (o) => x(o.due)).attr('y1', 2).attr('y2', rowH - 2);
  const late = rowG.filter((o) => o.open && o.overdue);
  late.filter(isCritical).append('use').attr('href', '#i-alert').attr('x', (o) => Math.min(iw + 4, ex(o) + 4)).attr('y', 3).attr('width', 13).attr('height', 13).attr('color', C.urgent).style('color', C.urgent);
  late.append('text').attr('class', (o) => `rr-late-label ${isCritical(o) ? 'is-crit' : ''}`).attr('x', (o) => Math.min(iw + 4, ex(o) + 4) + (isCritical(o) ? 16 : 2)).attr('y', rowH / 2).attr('dy', '0.32em').text((o) => `+${Math.round(o.late_d)}d`)
    .append('tspan').attr('class', 'rr-late-ps').text((o) => (o.planted && !narrow ? ` · ${o.planted}` : ''));
  withTooltip(rowG, (o) => ({
    title: `${o.ro_id} · ${o.serial}`,
    rows: [['Shop', shopLabel(o.shop)], ['Inducted', o.inH != null ? fmtWeek(Math.floor(o.inH / HPW)) : '—'], ['Quoted TAT', fmtDays(o.quoted_tat_d)], [o.open ? 'Elapsed' : 'Actual TAT', fmtDays(o.open ? o.elapsed_d : o.actual_tat_d)], ['vs quoted due', o.late_d == null ? '—' : o.late_d > 0 ? `+${fmtDays(o.late_d)} late` : `${fmtDays(-o.late_d)} early`]],
    note: `${o.planted ? `Planted situation ${o.planted} · ` : ''}${o.open ? (isCritical(o) ? `Critical: more than ${fmtInt(CRITICAL_LATE_D)} d past due, chase the vendor` : o.overdue ? 'Overdue, chase the vendor' : 'Open, inside quote') : 'Returned'}`,
  }));
}

// ============================================================================= TAT distribution
function renderTatDist(host, r) {
  const dists = (r.tat_distribution || []).filter((d) => Array.isArray(d.counts) && d.counts.length);
  if (!dists.length) return null;
  const slow = dists.slice().sort((a, b) => (b.mean_d / b.quoted_mean_d) - (a.mean_d / a.quoted_mean_d))[0];
  const f = chartFrame(host, {
    headline: `${shopLabel(slow.shop)} averages ${fmtDays(slow.mean_d)} against ${fmtDays(slow.quoted_mean_d)} quoted; one in ten takes over ${fmtDays(slow.p90_d)}`,
    subtitle: `Share of completed ROs by shop TAT · ${slow.bin_width_d}-day bins · solid = actual mean, dashed = quoted · ${dists.map((d) => `${shopLabel(d.shop)} n=${fmtInt(d.n)}`).join(' · ')}`,
    provenance: prov(dists[0], prov(r.meta)), source: 'rotables.json → tat_distribution',
    table: { columns: [{ key: 'shop', label: 'Shop', format: shopLabel }, { key: 'n', label: 'ROs', num: true, format: fmtInt }, { key: 'quoted_mean_d', label: 'Quoted mean', num: true, format: fmtDays }, { key: 'mean_d', label: 'Actual mean', num: true, format: fmtDays }, { key: 'median_d', label: 'Median', num: true, format: fmtDays }, { key: 'p90_d', label: 'p90', num: true, format: fmtDays }], rows: dists },
  });
  f.root.classList.add('mb-3');
  return responsive(f.body, (w) => {
    const panelH = 96, gapH = 18, m = { top: 8, right: 12, bottom: 28, left: 12 };
    const hgt = m.top + m.bottom + dists.length * panelH + (dists.length - 1) * gapH;
    const iw = w - m.left - m.right;
    const svg = svgIn(f.body, w, hgt, 'Repair turnaround distribution by shop');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    // trim the empty tail common to all shops
    const lastNZ = d3().max(dists, (d) => { let k = d.counts.length - 1; while (k > 0 && !d.counts[k]) k--; return k; });
    const bw = dists[0].bin_width_d;
    const xmax = (lastNZ + 1) * bw;
    const x = d3().scaleLinear().domain([0, xmax]).range([0, iw]);
    dists.forEach((d, i) => {
      const gy = i * (panelH + gapH);
      const pg = g.append('g').attr('transform', `translate(0,${gy})`);
      const share = d.counts.slice(0, lastNZ + 1).map((c, k) => ({ x0: d.bins_d[k], c, p: c / d.n }));
      const y = d3().scaleLinear().domain([0, d3().max(dists, (dd) => d3().max(dd.counts) / dd.n)]).range([panelH, 18]);
      // shops are categories, not a recommendation: the slowest shop is solid titanium, the others slate
      const color = d === slow ? SR.neutral : SR.context;
      const bars = pg.selectAll('rect').data(share).join('rect').attr('x', (b) => x(b.x0) + 0.5).attr('width', Math.max(1, x(bw) - x(0) - 1.5)).attr('y', (b) => y(b.p)).attr('height', (b) => panelH - y(b.p)).attr('fill', color).attr('fill-opacity', d === slow ? 0.55 : 0.5);
      withTooltip(bars, (b) => ({ title: `${shopLabel(d.shop)} · ${b.x0}–${b.x0 + bw} d`, rows: [['ROs', fmtInt(b.c)], ['Share', fmtPct(b.p)]] }));
      pg.append('line').attr('x1', 0).attr('x2', iw).attr('y1', panelH).attr('y2', panelH).attr('stroke', C.lineStrong);
      refLine(pg, { x1: x(d.quoted_mean_d), x2: x(d.quoted_mean_d), y1: 14, y2: panelH });
      pg.append('line').attr('x1', x(d.mean_d)).attr('x2', x(d.mean_d)).attr('y1', 14).attr('y2', panelH).attr('stroke', C.text).attr('stroke-width', 1.25);
      dl(pg, { x: 0, y: 6, text: `${shopLabel(d.shop)} · mean ${fmtDays(d.mean_d)} vs quoted ${fmtDays(d.quoted_mean_d)}`, color: d === slow ? C.text : C.muted, strong: d === slow });
      if (d === slow && w >= 360) annotate(pg, { x: x(d.p90_d), y: panelH - 4, dx: x(d.p90_d) > iw * 0.6 ? -24 : 24, dy: -34, title: `p90 ${fmtDays(d.p90_d)}`, sub: 'long tail' });
    });
    axisBottom(g.append('g'), x, { ticks: w < 480 ? 4 : 6, format: (v) => `${v} d`, height: hgt - m.top - m.bottom });
  });
}

// ============================================================================= TAT scatter
function renderTat(host, r) {
  const rows = (r.tat || []).filter((t) => num(t.quoted_d) != null && num(t.actual_mean_d) != null);
  const shops = [...new Set(rows.map((t) => t.shop))].filter(Boolean).sort();
  const late = rows.filter((t) => t.actual_mean_d > t.quoted_d);
  const worst = rows.slice().sort((a, b) => (b.actual_mean_d - b.quoted_d) - (a.actual_mean_d - a.quoted_d))[0];
  const byShop = shops.map((s) => { const rs = rows.filter((t) => t.shop === s); return { shop: s, n: rs.length, ratio: median(rs.map((t) => t.actual_mean_d / t.quoted_d)) }; });
  const headline = rows.length
    ? `${fmtInt(late.length)} of ${fmtInt(rows.length)} PN–shop pairs run slower than quoted${worst ? `; ${worst.pn} is ${fmtDays(worst.actual_mean_d - worst.quoted_d)} over` : ''}`
    : 'TAT comparison not run';
  const f = chartFrame(host, {
    headline,
    subtitle: `Quoted vs actual mean TAT (whisker to p90), one dot per PN × shop · ${byShop.map((b) => `${shopLabel(b.shop)} median ${fmtNum(b.ratio, 2)}×`).join(' · ')}`,
    provenance: prov(r.tat?.[0], prov(r.meta)), source: 'rotables.json → tat',
    table: { columns: [{ key: 'pn', label: 'PN' }, { key: 'shop', label: 'Shop', format: shopLabel }, { key: 'quoted_d', label: 'Quoted', num: true, format: fmtDays }, { key: 'actual_mean_d', label: 'Actual mean', num: true, format: fmtDays }, { key: 'p90_d', label: 'p90', num: true, format: fmtDays }, { key: 'n', label: 'ROs', num: true, format: fmtInt }], rows },
  });
  if (!rows.length) { f.body.append(h('div', { class: 'state' }, 'not run')); return null; }
  // shops are categories (no accent): the slowest shop (highest median ratio) is solid titanium, others hollow slate
  const slowShop = byShop.slice().sort((a, b) => (b.ratio ?? 0) - (a.ratio ?? 0))[0]?.shop;
  const colorOf = (s) => (s === slowShop ? SR.neutral : SR.context);
  return responsive(f.body, (w) => {
    const hgt = Math.max(300, Math.min(420, Math.round(w * 0.82)));
    const m = { top: 16, right: 20, bottom: 40, left: 48 };
    const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
    const svg = svgIn(f.body, w, hgt, 'Actual versus quoted turnaround time');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const maxV = d3().max(rows, (t) => Math.max(t.quoted_d, t.p90_d ?? t.actual_mean_d, t.actual_mean_d)) * 1.05;
    const x = d3().scaleLinear().domain([0, d3().max(rows, (t) => t.quoted_d) * 1.1]).nice().range([0, iw]);
    const y = d3().scaleLinear().domain([0, maxV]).nice().range([ih, 0]);
    gridY(g.append('g'), y, iw, 4);
    axisLeft(g.append('g'), y, { ticks: 4, format: (v) => `${v} d` });
    axisBottom(g.append('g'), x, { ticks: w < 480 ? 3 : 5, format: (v) => `${v} d`, height: ih });
    dl(g, { x: iw, y: ih + 30, text: 'QUOTED TAT →', anchor: 'end', color: C.faint });
    // y = x reference
    const dmax = Math.min(x.domain()[1], y.domain()[1]);
    refLine(g, { x1: x(0), y1: y(0), x2: x(dmax), y2: y(dmax), label: 'on quote', dx: -4, dy: 14, anchor: 'end' });
    dl(g, { x: 6, y: 6, text: 'SLOWER THAN QUOTED ↑', color: C.faint });
    const r0 = d3().scaleSqrt().domain([0, d3().max(rows, (t) => t.n || 1)]).range([2.5, 7]);
    const pts = g.append('g').selectAll('g').data(rows).join('g').attr('transform', (t) => `translate(${x(t.quoted_d)},0)`);
    pts.filter((t) => t.p90_d != null).append('line').attr('y1', (t) => y(t.actual_mean_d)).attr('y2', (t) => y(t.p90_d)).attr('stroke', (t) => colorOf(t.shop)).attr('stroke-opacity', 0.45);
    pts.append('circle').attr('cy', (t) => y(t.actual_mean_d)).attr('r', (t) => r0(t.n || 1)).attr('fill', (t) => (t.shop === slowShop ? SR.neutral : C.bg)).attr('fill-opacity', (t) => (t.shop === slowShop ? 0.7 : 1)).attr('stroke', (t) => colorOf(t.shop)).attr('stroke-width', 1.5);
    withTooltip(pts, (t) => ({ title: `${t.pn} · ${shopLabel(t.shop)}`, rows: [['Quoted', fmtDays(t.quoted_d)], ['Actual mean', fmtDays(t.actual_mean_d)], ['p90', fmtDays(t.p90_d)], ['ROs', fmtInt(t.n)]] }));
    // direct shop labels (legend-free): top-right stack
    const legendShops = [slowShop, ...shops.filter((s) => s !== slowShop)].slice(0, 3);
    legendShops.forEach((s, i) => dl(g, { x: iw, y: ih - 12 - i * 16, text: `${s === slowShop ? '●' : '○'} ${shopLabel(s)}`, anchor: 'end', color: s === slowShop ? C.text : C.muted }));
    if (worst) {
      // annotate into the empty lower-left / upper-left space, away from the point cloud
      const wx = x(worst.quoted_d), wy = y(worst.actual_mean_d);
      const cx = d3().mean(rows, (t) => x(t.quoted_d));
      annotate(g, { x: wx, y: wy, dx: wx > cx ? -Math.min(wx - 8, 64) : 40, dy: wy < 60 ? 40 : -30, title: worst.pn, sub: `+${fmtDays(worst.actual_mean_d - worst.quoted_d)} vs quote` });
    }
  });
}

// ============================================================================= Float calculator
function accelAssumption(r, method) {
  const fromR = num(pick(r, 'repair_acceleration_cost_aed_per_day_per_unit', 'accel_cost_aed_per_day_per_unit')) ?? num(pick(r.assumptions || {}, 'repair_acceleration_cost_aed_per_day_per_unit', 'accel_cost_aed_per_day_per_unit'));
  if (fromR != null) return { value: fromR, provenance: r.assumptions?.provenance || 'ASSUMED', source: 'rotables.json (config/assumptions.yaml)' };
  const a = (method?.assumptions || []).find((x) => /repair_acceleration/.test(x.key || ''));
  if (a && num(a.value) != null) return { value: num(a.value), provenance: a.provenance || 'ASSUMED', source: `method.json → assumptions (${a.key})` };
  return null;
}

function exampleInputs(ex, r) {
  const tatRow = (r.tat || []).find((t) => t.pn === ex.pn);
  return {
    pn: ex.pn, station: ex.station || null,
    rate: num(pick(ex, 'rate_per_30d', 'removal_rate_per_30d', 'removals_per_30d')),
    tat: num(pick(ex, 'tat_days', 'tat_d', 'pipeline_days')) ?? num(tatRow?.actual_mean_d),
    spares: num(pick(ex, 'spares', 'total_spares')) ?? (num(ex.current) != null ? num(ex.current) + (num(ex.loop_units) ?? 0) : null),
    loop: num(ex.loop_units) ?? 0,
    // S = shelf + units already in the repair loop (exporter spares_total when present, else derived)
    presets: [['P0', ex.p0_units, 'P0'], ['P1', ex.p1_units, 'P1'], ['P2', ex.p2_units, 'P2'], ['Recommended', ex.rec_units ?? ex.recommended, 'recommended']].filter(([, v]) => num(v) != null)
      .map(([k, v, sk]) => [k, num(ex.spares_total?.[sk]) ?? num(v) + (num(ex.loop_units) ?? 0)]),
    desc: ex.desc || '', deadline: ex.deadline || '', planted: ex.planted || null,
    cost: num(pick(ex, 'unit_cost_aed', 'unit_cost')),
    recommended: num(ex.recommended),
    reason: ex.reason || '',
    stationView: ex.station_view || null,
    provenance: ex.provenance || prov(r.meta),
  };
}

let ctxRec = null;
/** Availability that never prints a misleading "100.0%" for a Poisson tail: > 99.9%. */
const fmtAvail = (v) => (v == null ? '—' : v > 0.9995 ? '> 99.9%' : fmtPct(v, 1));
const fmtEbo = (v) => (v == null ? '—' : v < 0.01 ? '< 0.01' : fmtNum(v, 2));
/** Expected wait: hours under two days ("< 1 h", "5 h"), days above ("3.2 d"). */
const fmtWait = (d) => (d == null ? '—' : d * 24 < 1 ? '< 1 h' : d < 2 ? `${fmtInt(d * 24)} h` : `${fmtNum(d, 1)} d`);
function renderFloatCalc(host, r, method, ctx) {
  ctxRec = r.recommended_id || null;
  const examples = (r.float_examples || []).map((ex) => exampleInputs(ex, r));
  const accel = accelAssumption(r, method);
  const want = ctx.params.pn;
  let cur = examples.find((e) => e.pn === want) || examples.find((e) => e.planted === 'PS1') || examples[0] || { pn: null, rate: null, tat: null, spares: null, cost: null };

  host.append(h('div', { class: 'card-head' },
    h('div', {}, h('div', { class: 'card-kicker' }, 'Float calculator · METRIC-inspired (Palm’s theorem), not full METRIC'), h('h3', { class: 'card-title' }, 'How many spares does a rotable need to cover its repair pipeline?')),
    h('div', { class: 'row' }, ...[...new Set(['DERIVED', cur.provenance || 'SIMULATED'])].map((x) => provChip(x)))));

  const VT = { rate: (v) => `${fmtNum(v, 2)} removals per 30 days`, tat: (v) => `${fmtNum(v, 1)} days`, spares: (v) => `${fmtInt(v)} spares`, cost: (v) => fmtAED(v), extra: (v) => `${fmtInt(v)} more spares`, cut: (v) => `${fmtInt(v)} days shorter TAT` };
  const mkNum = (key, label, { min = 0, step = 1, hint, grouped = false } = {}) => {
    const id = `fc-${key}`;
    // grouped inputs show thousands separators ("47,977"), so they are text inputs parsed by num(stripCommas)
    const input = grouped ? h('input', { class: 'input', type: 'text', id, inputmode: 'numeric', autocomplete: 'off', dataset: { input: key, grouped: '1' } })
      : h('input', { class: 'input', type: 'number', id, min, step, inputmode: 'decimal', dataset: { input: key } });
    const range = h('input', { class: 'slider', type: 'range', min, step, 'aria-label': `${label} slider`, dataset: { range: key } });
    const vt = bindValueText(range, VT[key] || String);
    return { key, input, range, vt, el: h('div', { class: 'fc-field' }, h('label', { for: id }, label), input, range, hint ? h('div', { class: 'fc-hint' }, hint) : null) };
  };
  const sel = h('select', { class: 'select', id: 'fc-pn', 'aria-label': 'Prefill from rotable' },
    examples.map((e) => h('option', { value: e.pn }, `${e.pn}${e.desc ? ` · ${e.desc}` : ''}${e.planted ? ` · ${e.planted}` : ''}`)));
  if (cur.pn) sel.value = cur.pn;
  const fRate = mkNum('rate', 'Removals per 30 d', { step: 0.01, hint: 'Unscheduled removals (U/S) at this stocking point' });
  const fTat = mkNum('tat', 'Pipeline TAT, days', { step: 0.1, hint: 'Removal → serviceable again (transport + shop + return)' });
  const fSp = mkNum('spares', 'Spares (S)', { step: 1, hint: 'Total spares: shelf + pipeline' });
  const fCost = mkNum('cost', 'Unit cost, AED', { step: 1000, hint: 'Exchange / purchase price per serial', grouped: true });
  const fields = [fRate, fTat, fSp, fCost];
  const reason = h('div', { class: 'fc-hint fc-wide' });
  const presetBox = h('div', { class: 'fc-presets fc-wide', role: 'group', 'aria-label': 'Set spares to a policy level' });
  const inputs = h('div', { class: 'fc-inputs' },
    h('div', { class: 'fc-field fc-wide' }, h('label', { for: 'fc-pn' }, 'Prefill from a rotable'), sel), reason, ...fields.map((f) => f.el), h('div', { class: 'fc-field fc-wide' }, h('span', { class: 'fc-label' }, 'Set S to a policy level · shelf + in loop = S'), presetBox));

  // outputs
  const out = (key, label, isKey) => { const v = h('div', { class: 'fc-out-value', dataset: { out: key } }, '—'); return { v, el: h('div', { class: `fc-out ${isKey ? 'is-key' : ''}` }, h('div', { class: 'fc-out-label' }, label), v) }; };
  const oMu = out('pipeline_mean', 'Pipeline mean λT');
  const oA = out('availability', 'Availability P(X<S)', true);
  const oE = out('ebo', 'Expected backorders');
  const oW = out('expected_wait_days', 'Expected wait');
  const oCap = out('capital_aed', 'Float capital');
  const outs = h('div', { class: 'fc-outs', role: 'status', 'aria-live': 'polite' }, oA.el, oMu.el, oE.el, oW.el, oCap.el);
  // C9 (wave 4): the pooled network figure next to one outstation's own float, with a one-line explanation
  const stationBox = h('div', { class: 'fc-station', dataset: { out: 'station' } });
  const results = h('div', { class: 'fc-results' }, outs, stationBox);
  const chartHost = h('div');

  // levers
  const lN = mkNum('extra', 'Buy N more spares', { min: 0, step: 1 });
  const lD = mkNum('cut', 'Cut TAT by d days', { min: 0, step: 1 });
  const leverBox = h('div', { class: 'fc-levers', role: 'region', 'aria-label': 'Lever comparison' });
  const verdict = h('p', { class: 'fc-verdict', dataset: { out: 'verdict' } });
  const assume = h('div', { class: 'fc-assume' },
    accel ? [provChip(accel.provenance), h('span', {}, `Repair acceleration fee ${fmtAED(accel.value)} per day per unit (${accel.provenance === 'ASSUMED' ? 'ASSUMED' : accel.provenance}; ${accel.source})`)]
      : [provChip('ASSUMED'), h('span', {}, 'Repair acceleration fee: not exported — TAT-cut cost not run')]);

  // grid areas: inputs left / outputs + chart right at desktop; outputs first on narrow screens
  inputs.classList.add('fc-area-in'); results.classList.add('fc-area-out'); chartHost.classList.add('fc-area-chart');
  host.append(h('div', { class: 'fc-grid' }, inputs, results, chartHost));
  host.append(h('div', { class: 'section-title mt-3' }, h('h2', { class: 't-16' }, 'Lever comparison: buy spares vs cut TAT'), h('span', { class: 'rule' })));
  host.append(h('div', { class: 'fc-lever-controls' }, lN.el, lD.el), leverBox, verdict, assume);
  host.append(h('p', { class: 'rr-method-note mt-2' }, 'Palm’s theorem: with Poisson removals at rate λ and any repair-time distribution of mean T, the number of units in the pipeline is Poisson(λT). Availability = P(X < S); EBO = E[max(X − S, 0)]; expected wait = EBO / λ. Single site, infinite repair capacity, no condemnation — hence “METRIC-inspired”, not a full multi-echelon METRIC.'));

  const frame = chartFrame(chartHost, { headline: 'Float calculator', subtitle: 'Units in the repair pipeline', provenance: 'DERIVED', source: 'lib/floatcalc.js (mirrors src/gnm/policy/analytic.py)' });
  frame.root.dataset.story = 'float-pipeline';

  const state = { rate: null, tat: null, spares: null, cost: null, extra: 1, cut: 10 };
  const setRanges = () => {
    const rmax = Math.max(1, Math.ceil((state.rate ?? 1) * 3 * 10) / 10);
    fRate.range.max = rmax; fTat.range.max = Math.max(30, Math.ceil((state.tat ?? 30) * 2));
    fSp.range.max = Math.max(10, (state.spares ?? 5) * 2 + 4); fCost.range.max = Math.max(100000, Math.ceil(((state.cost ?? 50000) * 3) / 1000) * 1000);
    lN.range.max = 10; lD.range.max = Math.max(10, Math.floor(state.tat ?? 10));
  };
  const sync = (key) => {
    const all = { rate: fRate, tat: fTat, spares: fSp, cost: fCost, extra: lN, cut: lD };
    Object.entries(all).forEach(([k, f]) => { if (k === key) return; f.input.value = f.input.dataset.grouped ? (state[k] == null ? '' : fmtCount(state[k])) : state[k] ?? ''; f.range.value = state[k] ?? 0; f.vt?.(); });
  };
  const round = (v, d) => (v == null ? null : Math.round(v * 10 ** d) / 10 ** d);
  const load = (ex) => {
    cur = ex;
    // C9 (wave 4): open on the Recommended preset (not P0's S); removals to 1 decimal, TAT to whole days
    const recS = (ex.presets || []).find(([k]) => k === 'Recommended')?.[1];
    Object.assign(state, { rate: round(ex.rate, 1), tat: round(ex.tat, 0), spares: recS ?? ex.spares, cost: ex.cost });
    lD.range.max = Math.max(10, Math.floor(ex.tat ?? 10));
    if (state.tat != null && state.cut > state.tat) state.cut = Math.floor(state.tat / 2);
    reason.replaceChildren(`${ex.deadline ? `${ex.deadline} (hypothetical deadline class) · ` : ''}${ex.station && ex.station !== 'network' ? `${ex.station} · ` : 'network float · '}spares include ${fmtInt(ex.loop ?? 0)} units already in the repair loop. `, ex.reason ? h('details', { class: 'fc-why' }, h('summary', {}, `Why the model recommends ${ex.recommended != null ? fmtInt(ex.recommended) : 'this'} base-stock units`), h('p', {}, ex.reason)) : '');
    presetBox.replaceChildren(...(ex.presets || []).map(([k, v]) => h('button', { type: 'button', class: 'btn btn--sm', 'aria-pressed': 'false', dataset: { preset: k, value: v }, onclick: () => { state.spares = v; sync(null); compute(); } }, (ex.loop ? `${k} · ${fmtInt(v - ex.loop)} + ${fmtInt(ex.loop)} = ${fmtInt(v)}` : `${k} · S = ${fmtInt(v)}`))));
    setRanges(); sync(null); compute();
  };
  [...fields, lN, lD].forEach((f) => {
    const onIn = (src) => () => {
      const v = num(String(src.value).replace(/[,\s]/g, ''));
      state[f.key] = v;
      if (src === f.input) { f.range.value = v ?? 0; f.vt?.(); } else f.input.value = f.input.dataset.grouped ? (v == null ? '' : fmtCount(v)) : v ?? '';
      compute();
    };
    f.input.addEventListener('input', onIn(f.input));
    f.range.addEventListener('input', onIn(f.range));
    if (f.input.dataset.grouped) f.input.addEventListener('change', () => { if (state[f.key] != null) f.input.value = fmtCount(state[f.key]); });
  });
  sel.addEventListener('change', () => { const ex = examples.find((e) => e.pn === sel.value); if (ex) { ctx.setParams({ pn: ex.pn }); load(ex); } });

  /** Station view: one outstation's own float (no pooling), with the pooled-vs-station callout. */
  function renderStation(res) {
    const sv = cur.stationView;
    if (!sv || !sv.units) { stationBox.replaceChildren(); stationBox.hidden = true; return; }
    stationBox.hidden = false;
    const rec = ctxRec || 'Recommended';
    const rows = [['P0', 'P0'], ['P2', 'P2'], ['recommended', rec]].filter(([k]) => sv.units[k] != null);
    const recU = sv.units.recommended, recA = sv.availability?.recommended;
    stationBox.replaceChildren(
      h('div', { class: 'fc-station-head' }, h('span', { class: 'fc-out-label' }, `Station view · ${sv.station}`), h('span', { class: 'fc-hint' }, `${fmtNum(sv.rate_per_30d, 1)} removals / 30 d · ${fmtInt(sv.loop_days)}-day loop · own units only`)),
      h('div', { class: 'fc-station-rows' }, rows.map(([k, label]) => h('div', { class: `fc-station-row ${k === 'recommended' ? 'is-rec' : ''}`, dataset: { station: k } },
        h('span', { class: 'fc-station-k' }, label), h('span', { class: 'fc-station-u' }, `${fmtInt(sv.units[k])} unit${sv.units[k] === 1 ? '' : 's'}`), h('span', { class: 'fc-station-a' }, fmtPct(sv.availability?.[k], 0))))),
      h('p', { class: 'fc-station-note' }, icon('info'), h('span', {}, `Pooled vs station: the ${fmtAvail(res.availability)} above pools every spare as if any unit reached any station at once. An aircraft at ${sv.station} waits for one of the ${fmtInt(recU)} unit${recU === 1 ? '' : 's'} there: ${fmtPct(recA, 0)} available, which is where the AOG hours come from.`)));
  }
  let stopChart = null;
  function compute() {
    const { rate, tat, spares, cost, extra, cut } = state;
    const ok = [rate, tat, spares, cost].every((v) => v != null && v >= 0);
    if (!ok) {
      [oMu, oA, oE, oW, oCap].forEach((o) => (o.v.textContent = 'not run'));
      frame.root.querySelector('.chart-headline').textContent = 'Enter removal rate, TAT, spares and unit cost to size the float';
      frame.root.querySelector('.chart-subtitle').textContent = 'Units in the repair pipeline · Poisson(λT)';
      stopChart?.(); frame.body.replaceChildren(h('div', { class: 'state' }, 'not run'));
      leverBox.replaceChildren(); verdict.textContent = '';
      return;
    }
    const S = Math.round(spares);
    const res = floatCalc(rate, tat, S, cost);
    oMu.v.textContent = `${fmtNum(res.pipeline_mean, 1)} units`;
    oA.v.textContent = fmtAvail(res.availability);
    oE.v.textContent = fmtEbo(res.ebo);
    oW.v.textContent = fmtWait(res.expected_wait_days);
    // exact values ride along in data-value (the text is rounded for reading; tests compare the exact maths)
    Object.assign(oMu.v.dataset, { value: res.pipeline_mean }); Object.assign(oA.v.dataset, { value: res.availability });
    Object.assign(oE.v.dataset, { value: res.ebo }); Object.assign(oW.v.dataset, { value: res.expected_wait_days });
    presetBox.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.value === S)));
    renderStation(res);
    oCap.v.textContent = fmtAED(res.capital_aed);
    frame.root.querySelector('.chart-headline').textContent = `${fmtInt(S)} pooled spare${S === 1 ? '' : 's'} cover ${fmtAvail(res.availability)} of removals against a mean pipeline of ${fmtNum(res.pipeline_mean, 1)} units`;
    frame.root.querySelector('.chart-subtitle').textContent = `P(k units in the repair pipeline), X ~ Poisson(λT = ${fmtNum(rate, 1)}/30 d × ${fmtInt(tat)} d)${cur.pn ? ` for ${cur.pn}` : ''} · bars at k ≥ S are shortages`;
    stopChart?.();
    stopChart = drawPmf(frame, res.pipeline_mean, S, res);
    // levers
    const N = Math.max(0, Math.round(extra ?? 0)), D = Math.max(0, cut ?? 0);
    const cl = compareLevers(rate, tat, S, cost, D, N, accel ? accel.value : 0);
    const gainA = cl.extra_spares.availability - cl.base.availability;
    const gainB = cl.tat_cut.availability - cl.base.availability;
    // C6 (wave 4): highlight the CHEAPER lever per availability point (annual AED / pt), as the Capital lever panel does;
    // "more availability" stays a neutral note in the verdict
    const annA = carryingValue(cl.extra_spares.incremental_capital_aed, method);
    const annB = accel ? cl.tat_cut.incremental_annual_aed : null;
    const perPt = (ann, gain) => (ann != null && gain > 1e-9 ? ann / (gain * 100) : null);
    const cA = perPt(annA, gainA), cB = perPt(annB, gainB);
    const betterA = cA != null && (cB == null || cA < cB - 1e-6), betterB = cB != null && (cA == null || cB < cA - 1e-6);
    const cell = (v, out, better) => h('td', { class: better ? 'is-better' : '', dataset: out ? { out } : undefined }, v);
    const rowC = (label, a, b, outA, outB) => h('tr', {}, h('th', { scope: 'row' }, label), cell(a, outA, betterA), cell(b, outB, betterB));
    const gainTxt = (o, gain) => [fmtAvail(o.availability), h('span', { class: 'fc-gain' }, ` ${gain >= 0 ? '+' : '−'}${fmtNum(Math.abs(gain) * 100, 1)} pts`)];
    const thLever = (title, key, better) => h('th', { scope: 'col', class: better ? 'is-better' : '', dataset: { lever: key } }, h('span', { class: 'fc-lever-title' }, title), better ? h('span', { class: 'fc-win' }, icon('check'), 'Cheaper per point') : null);
    leverBox.replaceChildren(h('table', { class: 'fc-cmp' },
      h('caption', { class: 'sr-only' }, 'Lever comparison: buy spares versus cut TAT'),
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, h('span', { class: 'sr-only' }, 'Metric')),
        thLever(`Buy ${fmtInt(N)} more spare${N === 1 ? '' : 's'}`, 'extra_spares', betterA),
        thLever(`Cut TAT by ${fmtInt(D)} day${D === 1 ? '' : 's'}`, 'tat_cut', betterB))),
      h('tbody', {},
        rowC('Availability', gainTxt(cl.extra_spares, gainA), gainTxt(cl.tat_cut, gainB), 'extra_spares_availability', 'tat_cut_availability'),
        rowC('Expected backorders', fmtEbo(cl.extra_spares.ebo), fmtEbo(cl.tat_cut.ebo), 'extra_spares_ebo', 'tat_cut_ebo'),
        rowC('Expected wait', fmtWait(cl.extra_spares.expected_wait_days), fmtWait(cl.tat_cut.expected_wait_days)),
        rowC('One-off capital', fmtAED(cl.extra_spares.incremental_capital_aed), fmtAED(0), 'extra_spares_capital'),
        rowC('Annual cost', h('span', {}, carrying(cl.extra_spares.incremental_capital_aed, method), h('span', { class: 'fc-gain' }, ' carrying')), h('span', {}, accel ? fmtAED(cl.tat_cut.incremental_annual_aed) : 'not run', h('span', { class: 'fc-gain' }, ' fees')), null, 'tat_cut_annual'),
        rowC('Annual cost per pt', cA != null ? fmtAED(cA) : '—', cB != null ? fmtAED(cB) : '—', 'extra_spares_per_pt', 'tat_cut_per_pt'))));
    [['extra_spares_availability', cl.extra_spares.availability], ['tat_cut_availability', cl.tat_cut.availability], ['extra_spares_ebo', cl.extra_spares.ebo], ['tat_cut_ebo', cl.tat_cut.ebo]]
      .forEach(([k, v]) => { const c = leverBox.querySelector(`[data-out="${k}"]`); if (c) c.dataset.value = v; });
    const ann = carryingValue(cl.extra_spares.incremental_capital_aed, method);
    const saturated = Math.max(gainA, gainB) < 0.0005;
    const p0S = (cur.presets || []).find(([k]) => k === 'P0')?.[1];
    const cheaper = betterA ? `Buying ${fmtInt(N)} spare${N === 1 ? '' : 's'} is the cheaper lever per availability point` : betterB ? `Cutting TAT by ${fmtInt(D)} d is the cheaper lever per availability point` : null;
    const more = gainA > gainB + 1e-9 ? `the spares add more availability` : gainB > gainA + 1e-9 ? `the TAT cut adds more availability` : 'both add the same availability';
    const annualTxt = accel && ann != null ? `On an annual basis the spares cost ${fmtAED(ann)}/yr to carry versus ${fmtAED(cl.tat_cut.incremental_annual_aed)}/yr in acceleration fees for ${fmtNum((rate * 365) / 30, 1)} removals a year.` : 'Annual cost comparison needs the carrying rate and acceleration fee from the assumption register.';
    if (saturated) {
      // the pooled float is already saturated (e.g. the Recommended S): say so, and offer the level where the levers bite
      verdict.replaceChildren(h('strong', {}, `At S = ${fmtInt(S)} the pooled float is saturated: neither lever moves availability. `),
        p0S != null && p0S !== S ? h('button', { type: 'button', class: 'btn btn--sm btn--ghost fc-try-p0', onclick: () => { state.spares = p0S; sync(null); compute(); } }, `Compare the levers at P0 (S = ${fmtInt(p0S)})`) : null, ' ', annualTxt);
      return;
    }
    verdict.replaceChildren(
      h('strong', {}, cheaper || (gainA > gainB + 1e-9 ? `Buying ${fmtInt(N)} spare${N === 1 ? '' : 's'} lifts availability more` : gainB > gainA + 1e-9 ? `Cutting TAT by ${fmtInt(D)} d lifts availability more` : 'Both levers give the same availability')),
      cheaper ? `; ${more} (${fmtPts(gainA)} vs ${fmtPts(gainB)}). ` : ` (${fmtPts(gainA)} vs ${fmtPts(gainB)}). `, annualTxt);
  }
  setRanges();
  if (cur.pn) load(cur); else compute();
  if (!examples.length) reason.textContent = 'No float examples exported — enter values to explore.';
  return () => stopChart?.();
}
const fmtPts = (v) => `${v >= 0 ? '+' : '−'}${fmtNum(Math.abs(v) * 100, 1)} pts`;
function carryingValue(capital, method) {
  const a = (method?.assumptions || []).find((x) => /carrying_cost/.test(x.key || ''));
  const rate = num(a?.value);
  return rate != null ? capital * rate : null;
}
function carrying(capital, method) { const v = carryingValue(capital, method); return v == null ? 'not run' : fmtAED(v); }

function drawPmf(frame, mu, S, res) {
  const sd = Math.sqrt(Math.max(mu, 0.01));
  const kMax = Math.max(S + 3, Math.ceil(mu + 4 * sd), 6);
  const series = pmfSeries(mu, kMax);
  frame.setTable([{ key: 'k', label: 'Units in pipeline (k)', num: true }, { key: 'p', label: 'P(X = k)', num: true, format: (v) => fmtPct(v, 2) }, { key: 'zone', label: 'Zone' }], series.map((d) => ({ ...d, zone: d.k < S ? 'covered by spares' : 'shortage (backorder)' })));
  return responsive(frame.body, (w) => {
    const hgt = 240;
    const m = { top: 28, right: 16, bottom: 36, left: 44 };
    const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
    const svg = svgIn(frame.body, w, hgt, `Poisson pipeline distribution, mean ${fmtNum(mu, 2)}, spares ${S}`);
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const x = d3().scaleBand().domain(series.map((d) => d.k)).range([0, iw]).padding(0.18);
    const y = d3().scaleLinear().domain([0, d3().max(series, (d) => d.p) * 1.15]).nice().range([ih, 0]);
    gridY(g.append('g'), y, iw, 4);
    axisLeft(g.append('g'), y, { ticks: 4, format: (v) => fmtPct(v, 0) });
    const every = Math.ceil(series.length / (w < 480 ? 8 : 16));
    const ax = g.append('g').attr('transform', `translate(0,${ih})`).call(d3().axisBottom(x).tickSize(4).tickValues(series.map((d) => d.k).filter((k) => k % every === 0)));
    ax.attr('class', 'gnm-axis').selectAll('text').attr('font-family', theme.font.mono);
    ax.selectAll('.tick line').attr('stroke', C.lineStrong);
    dl(g, { x: iw, y: ih + 30, text: 'UNITS IN PIPELINE (k) →', anchor: 'end', color: C.faint });
    const bars = g.append('g').selectAll('rect').data(series).join('rect').attr('x', (d) => x(d.k)).attr('width', x.bandwidth()).attr('y', (d) => y(d.p)).attr('height', (d) => ih - y(d.p)).attr('rx', 1.5)
      .attr('fill', (d) => (d.k < S ? SR.recommended : SR.urgent)).attr('fill-opacity', (d) => (d.k < S ? 0.75 : 0.8));
    withTooltip(bars, (d) => ({ title: `${d.k} unit${d.k === 1 ? '' : 's'} in the pipeline`, rows: [['P(X = k)', fmtPct(d.p, 2)], ['Zone', d.k < S ? 'Covered by spares' : 'Shortage']] }));
    const sx = S <= kMax ? (x(S) ?? iw) - (x.step() * x.padding()) / 2 : iw;
    g.append('line').attr('x1', sx).attr('x2', sx).attr('y1', -14).attr('y2', ih).attr('stroke', C.text).attr('stroke-width', 1.25).attr('stroke-dasharray', '3 3');
    dl(g, { x: sx + (sx > iw * 0.7 ? -6 : 6), y: -18, text: `S = ${S}`, anchor: sx > iw * 0.7 ? 'end' : 'start', color: C.text, strong: true, dy: '0.7em' });
    if (w >= 420) {
      dl(g, { x: Math.max(4, sx - 8), y: 6, text: '◀ covered', anchor: 'end', color: C.accent });
      dl(g, { x: sx + 8, y: 6, text: 'shortage ▶', color: SR.urgent });
    }
    // mean λT and EBO are already in the output tiles: no in-chart annotation competing with the bars
  });
}

// ============================================================================= Palm vs sim
function pvsRows(r, hubId) {
  const src = r.palm_vs_sim?.rows || r.palm_vs_sim || [];
  if (!Array.isArray(src)) return [];
  return src.map((d) => ({
    pn: d.pn, station: d.station,
    palm: num(pick(d, 'palm_availability', 'palm', 'analytic_availability')),
    sim: num(pick(d, 'sim_immediate_fill', 'sim_fill', 'simulated_fill')),
    n: num(pick(d, 'sim_requests', 'requests', 'n')) ?? 1,
    hub: d.role ? d.role === 'hub' : d.station === hubId,
  })).filter((d) => d.palm != null && d.sim != null);
}

function renderPalmVsSim(host, r, hubId) {
  const rows = pvsRows(r, hubId);
  const meta = r.palm_vs_sim && !Array.isArray(r.palm_vs_sim) ? r.palm_vs_sim : {};
  if (!rows.length) {
    chartFrame(host, { headline: 'Palm vs simulation not run', subtitle: 'Analytic availability vs simulated immediate fill per rotable × station', provenance: 'SIMULATED', source: 'rotables.json → palm_vs_sim' }).body.append(h('div', { class: 'state' }, 'not run — no Palm-vs-simulation rows in this export'));
    return null;
  }
  const wavg = (a, k) => { const n = d3().sum(a, (d) => d.n); return n ? d3().sum(a, (d) => d[k] * d.n) / n : null; };
  const hub = rows.filter((d) => d.hub), out = rows.filter((d) => !d.hub);
  const gap = rows.slice().sort((a, b) => (a.sim - a.palm) - (b.sim - b.palm))[0];
  const pol = meta.policy || r.palm_vs_sim_policy;
  const hp = wavg(hub, 'palm'), hs = wavg(hub, 'sim');
  const headline = hub.length
    ? `Palm predicts ${fmtPct(hp)} fill at the hub; the simulation delivers ${fmtPct(hs)}`
    : `Palm predicts ${fmtPct(wavg(rows, 'palm'))} fill; the simulation delivers ${fmtPct(wavg(rows, 'sim'))}`;
  const f = chartFrame(host, {
    headline,
    subtitle: `Request-weighted${pol ? `, ${pol} floats` : ''}${out.length && hub.length ? ` · outstations ${fmtPct(wavg(out, 'palm'))} Palm vs ${fmtPct(wavg(out, 'sim'))} sim` : ''} · one dot per rotable × station, size = requests · ${meta.split || r.palm_vs_sim_split || 'selection'} seeds${meta.n_seeds ? ` (${meta.n_seeds})` : ''}`,
    provenance: 'SIMULATED', source: 'rotables.json → palm_vs_sim',
    table: { columns: [{ key: 'pn', label: 'PN' }, { key: 'station', label: 'Station' }, { key: 'palm', label: 'Palm A', num: true, format: (v) => fmtPct(v) }, { key: 'sim', label: 'Sim fill', num: true, format: (v) => fmtPct(v) }, { key: 'n', label: 'Requests', num: true, format: fmtInt }], rows },
  });
  return responsive(f.body, (w) => {
    const hgt = Math.max(300, Math.min(400, Math.round(w * 0.6)));
    const m = { top: 16, right: 20, bottom: 40, left: 52 };
    const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
    const svg = svgIn(f.body, w, hgt, 'Palm availability versus simulated fill');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const lo = Math.max(0, Math.floor(Math.min(d3().min(rows, (d) => d.palm), d3().min(rows, (d) => d.sim)) * 10) / 10);
    const x = d3().scaleLinear().domain([lo, 1]).range([0, iw]);
    const y = d3().scaleLinear().domain([lo, 1]).range([ih, 0]);
    gridY(g.append('g'), y, iw, 4);
    axisLeft(g.append('g'), y, { ticks: 4, format: (v) => fmtPct(v, 0) });
    axisBottom(g.append('g'), x, { ticks: w < 480 ? 3 : 5, format: (v) => fmtPct(v, 0), height: ih });
    dl(g, { x: iw, y: ih + 30, text: 'PALM AVAILABILITY →', anchor: 'end', color: C.faint });
    dl(g, { x: 6, y: 6, text: 'SIMULATED FILL ↑', color: C.faint });
    refLine(g, { x1: 0, y1: ih, x2: iw, y2: 0 });
    dl(g, { x: iw * 0.18 + 8, y: ih - ih * 0.18 + 6, text: 'sim = Palm', color: C.faint, mono: true });
    const rr = d3().scaleSqrt().domain([0, d3().max(rows, (d) => d.n)]).range([2, 8]);
    const pts = g.append('g').selectAll('circle').data(rows.slice().sort((a, b) => a.hub - b.hub)).join('circle').attr('cx', (d) => x(d.palm)).attr('cy', (d) => y(d.sim)).attr('r', (d) => rr(d.n))
      .attr('fill', (d) => (d.hub ? SR.neutral : 'none')).attr('fill-opacity', (d) => (d.hub ? 0.6 : 0)).attr('stroke', (d) => (d.hub ? SR.neutral : SR.context)).attr('stroke-width', 1.25);
    withTooltip(pts, (d) => ({ title: `${d.pn} @ ${d.station}`, rows: [['Palm A', fmtPct(d.palm)], ['Sim fill', fmtPct(d.sim)], ['Gap', `${fmtNum((d.sim - d.palm) * 100, 1)} pts`], ['Requests', fmtInt(d.n)]] }));
    dl(g, { x: iw, y: ih - 28, text: '● Hub', anchor: 'end', color: C.text });
    dl(g, { x: iw, y: ih - 12, text: '○ Outstations', anchor: 'end', color: C.muted });
    if (gap) annotate(g, { x: x(gap.palm), y: y(gap.sim), dx: x(gap.palm) > iw * 0.5 ? -34 : 34, dy: y(gap.sim) > ih * 0.6 ? -30 : 30, title: `${gap.pn} @ ${gap.station}`, sub: `Palm ${fmtPct(gap.palm, 0)} → sim ${fmtPct(gap.sim, 0)}` });
  });
}

function whyList(r) {
  const reasons = (r.palm_vs_sim && !Array.isArray(r.palm_vs_sim) && Array.isArray(r.palm_vs_sim.reasons)) ? r.palm_vs_sim.reasons : null;
  const items = reasons ? reasons.map((x) => [x.title || '', x.body || x]) : [
    ['Finite shop capacity.', 'Palm assumes ample repair servers. Real benches queue work; the simulator models bench capacity, so a busy shop stretches the pipeline beyond λT.'],
    ['Condemnation.', 'Beyond-economic-repair units leave the loop and are replaced by purchase orders with their own lead time, so the effective pipeline time is longer than the shop TAT.'],
    ['Transport and multi-echelon competition.', 'Cores travel to AUH before induction, and hub returns also refill outstation floats. An outstation resupplied from the hub in days sees far more than its own Palm figure.'],
    ['Non-stationary demand.', 'Removals cluster (frailty on over-dispersed PNs) and TAT drifts; Palm’s steady-state Poisson pipeline smooths this out.'],
  ];
  return h('ul', { class: 'rr-reasons' }, items.map(([t, b]) => h('li', {}, icon('info'), h('div', {}, h('strong', {}, `${t} `), b))));
}
