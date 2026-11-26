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
import { h, icon, pageHead, card, provChip, pill, dataTable, bindValueText, fillPct, intro3, slidingThumb } from '../ui.js';
import { chartFrame, responsive, svgIn, axisBottom, axisLeft, gridY, styleAxis, directLabel, annotate, withTooltip, truncate, theme, chipLabel, refLine, fmtAED, fmtPct, fmtDays, fmtInt, fmtNum, fmtWeek, fmtEnum, fmtCount, plural } from '../charts/theme.js';
import { floatCalc, compareLevers, pmfSeries } from '../lib/floatcalc.js';
import { isSimple, byMode } from '../lib/mode.js';
import { term, termText } from '../lib/glossary.js';
import { displayName } from '../lib/names.js';
import { escalationBlock, allocationFlagNote } from './parts-intelligence/flags.js';
import { drawIn, focusTip } from './parts-intelligence/motion-helpers.js';
import { chartTransition, throttleRAF, countUpOnce, tx as txSel } from '../lib/motion.js';

export const data = ['rotables', 'method', 'network', 'parts'];

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

/** responsive() + a one-time chart draw-in (slow token) of the svg the draw callback renders. */
const respIn = (host, draw) => responsive(host, (w) => { draw(w); drawIn(host, host.querySelector('svg')); });

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
  // wait for the view stylesheet before building the DOM: an unstyled first paint shifts the layout (CLS)
  await new Promise((res) => { const l = document.querySelector('link[data-view-css="rotable-repair"]'); if (!l || l.sheet) return res(); l.addEventListener('load', res, { once: true }); l.addEventListener('error', res, { once: true }); setTimeout(res, 3000); });
  const { rotables: r, method } = ctx.data;
  const cleanups = [];
  const now = asOfHour(r);
  const ros = (r.repair_queue || []).map((o) => normRO(o, now));
  const openROs = ros.filter((o) => o.open);
  const overdueROs = ros.filter((o) => o.open && o.overdue);
  const counts = r.lifecycle?.counts || {};
  const flows = r.lifecycle?.flows || [];
  const fixture = !!r.meta?.fixture;

  const S = isSimple();
  el.append(pageHead({
    num: '04', eyebrow: 'Rotable & Repair',
    title: byMode('Repairable parts: the repair loop and the spares that cover it', 'Every serial, every repair order, every day of float'),
    lede: S
      ? h('span', {}, 'Each ', term('rotable'), ' of a fictional airline goes round a loop: fitted, removed, repaired and returned. This page tracks the loop, flags late repairs and sizes the ', term('float'), '.')
      : 'Serialised rotables of Falcon Hub Airways (fictional) cycle through fit, removal, shop and return. This workspace tracks the loop, flags overdue repair orders and sizes the float with a METRIC-inspired (Palm’s theorem) calculator.',
    meta: [provChip(prov(r.meta)), provChip('DERIVED'), now != null ? h('span', { class: 'chip chip-mono' }, `As of ${fmtWeek(Math.floor(now / HPW))}`) : null].filter(Boolean),
  }));

  el.append(intro3({
    what: 'How repairable parts move through repair, which repairs are late, and how many spares cover the gap.',
    why: ['When ', term('tat'), ' runs long and the spares pool is small, planes wait on the ground for a part.'],
    action: 'Chase the latest repairs first. Then use the calculator to compare buying spares with faster repair.',
  }));

  // ---------------------------------------------------------------- 1. status strip
  const loop = (num(counts.REMOVED) ?? 0) + (num(counts.IN_REPAIR) ?? 0);
  const fleet = Object.entries(counts).filter(([k]) => k !== 'CONDEMNED').reduce((s, [, v]) => s + (num(v) ?? 0), 0);
  const tatRows = (r.tat || []).filter((t) => num(t.quoted_d) && num(t.actual_mean_d) != null);
  const tatRatio = median(tatRows.map((t) => t.actual_mean_d / t.quoted_d));
  const lateShare = tatRows.length ? tatRows.filter((t) => t.actual_mean_d > t.quoted_d).length / tatRows.length : null;
  // addendum: KPI values count up ONCE per session (countUpOnce, 600 ms); re-renders print the final value
  const countEl = (v, fmt, key) => { const e = h('span', { class: 'rr-count' }); if (v == null || !Number.isFinite(+v)) e.textContent = fmt(v); else countUpOnce(e, +v, fmt, { key: `rotables-${key}` }); return e; };
  const stat = ({ label, value, unit, sub, chip, alert, story }) => h('div', { class: `rr-stat ${alert ? 'is-alert' : ''}`, dataset: story ? { story } : undefined },
    h('div', { class: 'rr-stat-top' }, h('div', { class: 'rr-stat-label' }, label), provChip(chip)),
    h('div', { class: 'rr-stat-value' }, value, unit ? h('small', {}, unit) : null),
    h('div', { class: 'rr-stat-sub' }, sub));
  el.append(h('div', { class: 'rr-stats mt-3', dataset: { story: 'rotable-stats' } },
    stat({ label: byMode('Parts away for repair', 'Units in repair loop'), value: countEl(loop, fmtInt, 'loop'), unit: byMode('parts', 'serials'), sub: fleet ? (S ? `${fmtPct(loop / fleet)} of ${fmtInt(fleet)} parts are broken or in a shop` : `${fmtPct(loop / fleet)} of ${fmtInt(fleet)} active serials are removed (U/S) or in a shop`) : 'Lifecycle counts not exported', chip: prov(r.lifecycle, prov(r.meta)) }),
    stat({ label: byMode('Open repair jobs', 'Open repair orders'), value: countEl(r.repair_summary?.open ?? openROs.length, fmtInt, 'open'), unit: byMode('jobs', 'ROs'), sub: `${fmtInt(new Set(openROs.map((o) => o.shop)).size)} shops · ${fmtInt(r.repair_summary?.returned_last_8w ?? ros.length - openROs.length)} returned in the last 8 weeks`, chip: prov(r.meta) }),
    stat({ label: byMode('Repair jobs past due', 'Overdue vs quoted due'), value: countEl(r.repair_summary?.overdue ?? overdueROs.length, fmtInt, 'overdue'), unit: byMode('jobs', 'ROs'), sub: overdueROs.length ? h('span', { class: 'rr-stat-crit' }, overdueROs.some(isCritical) ? icon('alert') : null, `${plural(overdueROs.filter(isCritical).length, byMode('job', 'RO'))} more than ${Math.round(CRITICAL_LATE_D / 7)} weeks late`) : 'None overdue', chip: prov(r.meta) }),
    stat({ label: byMode('Actual vs promised repair time', 'Actual / quoted TAT'), value: tatRatio != null ? countEl(tatRatio, (v) => `${fmtNum(v, 2)}×`, 'tat-ratio') : 'not run', sub: lateShare != null ? (S ? `Middle value over ${fmtInt(tatRows.length)} part and shop pairs · ${fmtPct(lateShare, 0)} run late` : `Median over ${fmtInt(tatRows.length)} PN–shop pairs · ${fmtPct(lateShare, 0)} run late`) : 'TAT table not exported', chip: prov(r.tat?.[0], prov(r.meta)) }),
  ));

  // ---------------------------------------------------------------- 2. lifecycle
  const lcCard = card({ bp: true, cls: 'mt-3', story: 'rotable-lifecycle', body: [] });
  el.append(lcCard);
  const sumF = (pred) => flows.filter(pred).reduce((t, f) => t + (num(f.count) ?? 0), 0);
  const removals = sumF((f) => f.from === 'INSTALLED' && f.to !== 'INSTALLED');
  const shopOut = sumF((f) => f.from === 'IN_REPAIR' && f.to !== 'IN_REPAIR');
  const condemned = sumF((f) => f.from === 'IN_REPAIR' && f.to === 'CONDEMNED');
  const flowWindow = r.lifecycle?.window_label || (r.lifecycle?.window_weeks ? `weeks ${r.lifecycle.window_weeks.join('–')}` : now != null ? `weeks 0–${Math.floor(now / HPW) - 1}` : null);
  const lcHead = S
    ? (flows.length && shopOut ? `${fmtInt(removals)} removals fed the repair loop; ${fmtPct(condemned / shopOut)} of parts leaving the shop were scrapped` : `${fmtInt(loop)} parts are broken or in repair right now`)
    : flows.length && shopOut
      ? `${fmtInt(removals)} removals fed the repair loop; ${fmtPct(condemned / shopOut)} of shop exits were condemned (BER)`
      : `${fmtInt(loop)} serials are removed (U/S) or in repair right now`;
  const lcF = chartFrame(lcCard, {
    implication: byMode('Most repairable parts sit on aircraft. The repair loop is where the spares pool is won or lost.', 'Most rotables sit on aircraft; the repair loop is where float is gained or lost.'),
    headline: lcHead,
    subtitle: S ? `Boxes show how many parts are in each state${now != null ? ` at ${fmtWeek(Math.floor(now / HPW))}` : ''}. Each row below is one kind of move. Thicker lines mean more moves${flowWindow ? ` over ${flowWindow}` : ''}.` : `Box = serials in each state at ${now != null ? fmtWeek(Math.floor(now / HPW)) : 'end of window'} (${fmtInt(r.lifecycle?.n_serials ?? fleet)} serials) · one row per transition, dot = from, arrow = to, width = count${flowWindow ? ` over ${flowWindow}` : ''}`,
    provenance: prov(r.lifecycle, prov(r.meta)), source: 'rotables.json → lifecycle',
    table: { columns: [{ key: 'item', label: 'State / transition' }, { key: 'count', label: 'Serials', num: true, format: fmtInt }], rows: [...Object.entries(counts).map(([k, v]) => ({ item: stateName(k), count: v })), ...flows.map((f) => ({ item: `${stateName(f.from)} → ${stateName(f.to)}`, count: f.count }))] },
  });
  const lcHost = h('div', { class: 'rr-flow' });
  lcF.body.append(lcHost, h('p', { class: 'rr-lc-note' }, byMode('Each part is in one state at a time. Broken parts at other airports fly to AUH before repair. Hub removals go straight to the shop. Parts not worth fixing are scrapped and bought new.', 'Each serial is in exactly one state. Outstation removals travel to AUH as unserviceable cores before induction; hub removals go straight to the shop. BER units are condemned and replaced by purchase order.')));
  cleanups.push(respIn(lcHost, (w) => drawFlow(lcHost, r.lifecycle?.states || Object.keys(counts), counts, flows, w)));
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
  const whyCard = card({ cls: 'span-5', kicker: byMode('Why the formula and the simulation differ', 'Why analytic and simulated differ'), title: byMode('The simple formula assumes an endless, steady repair loop. The simulated network does not.', 'Palm assumes an infinite, stationary repair loop. The simulated network does not.'), prov: 'DERIVED', body: whyList(r) });
  pvGrid.append(pvCard, whyCard);
  cleanups.push(renderPalmVsSim(pvCard, r, ctx.data.network?.hub || ctx.data.network?.stations?.find((s) => s.role === 'hub')?.station));

  // ---------------------------------------------------------------- open ROs table
  const tableRows = ros.filter((o) => o.open).sort((a, b) => (b.overdue - a.overdue) || ((b.late_d ?? -1e9) - (a.late_d ?? -1e9)));
  el.append(h('div', { class: 'mt-3' }, card({
    kicker: byMode('Repair jobs', 'Repair orders'), title: S ? `${fmtInt(tableRows.length)} open repair jobs, latest first` : `${fmtInt(tableRows.length)} open repair orders, most days past due first`, prov: prov(r.meta),
    body: dataTable({
      caption: 'Open repair orders', maxHeight: 360, dense: true,
      mobileColumns: ['serial', 'late_d', 'shop', 'ro_id', 'overdue'], stickyFirst: true,
      columns: [
        { key: 'ro_id', label: byMode('Job', 'RO'), mono: true },
        { key: 'serial', label: byMode('Part serial', 'Serial'), mono: true },
        { key: 'shop', label: 'Shop', format: shopLabel },
        { key: 'inH', label: byMode('Went in', 'Inducted'), num: true, format: (v) => (v == null ? '—' : fmtWeek(Math.floor(v / HPW))) },
        { key: 'due', label: byMode('Promised', 'Quoted due'), num: true, format: (v) => (v == null ? '—' : fmtWeek(Math.floor(v / HPW))) },
        { key: 'late_d', label: 'vs due', short: 'vs due', num: true, format: (v) => (v == null ? '—' : v > 0 ? `+${fmtDays(v)}` : `−${fmtDays(-v)}`) },
        { key: 'overdue', label: 'Status', render: (o) => (isCritical(o) ? pill('urgent', o.planted ? `Critical · ${o.planted}` : 'Critical') : o.overdue ? h('span', { class: 'pill pill--unknown rr-pill-late' }, o.planted ? `Overdue · ${o.planted}` : 'Overdue') : h('span', { class: 'pill pill--unknown rr-pill-quote' }, byMode('On time', 'In quote'))) },
      ],
      rows: tableRows, sort: { key: 'late_d', dir: 'desc' }, // F7 (wave 4): the mobile Sort control names the real order
    }),
  })));

  if (fixture) console.info('rotable-repair: running on fixtures');
  return () => cleanups.forEach((fn) => { try { fn?.(); } catch { /* ignore */ } });
}

// ============================================================================= lifecycle state ladder
const STATE_SIMPLE = {
  SERVICEABLE: { label: 'READY TO FIT', short: 'Ready to fit', sub: 'In stores' },
  INSTALLED: { label: 'ON AIRCRAFT', short: 'On aircraft', sub: 'Fitted' },
  REMOVED: { label: 'BROKEN', short: 'Broken', sub: 'Sent to AUH' },
  IN_REPAIR: { label: 'IN REPAIR', short: 'In repair', sub: 'Queue + shop' },
  IN_TRANSIT: { label: 'IN TRANSIT', short: 'In transit', sub: 'On the way back' },
  CONDEMNED: { label: 'SCRAPPED', short: 'Scrapped', sub: 'Not worth fixing' },
};
/** v2.1: state names follow the reading mode (Simple: plain words). */
const STATE_META = new Proxy({}, { get: (_, k) => (isSimple() ? STATE_SIMPLE : STATE_EXPERT)[k] });
const STATE_EXPERT = {
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
 * Forward flows (solid titanium) come first, then returns (40% titanium), then condemnation
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
    // wave 5: no teal category here (teal = the recommended plan only); forward solid titanium, returns 40% titanium
    fwd: { color: SR.neutral, op: 0.75, label: 'FORWARD · fit → removal → shop → transit' },
    back: { color: SR.neutral, op: 0.35, label: 'RETURNS · back to stock or onto aircraft' },
    bad: { color: SR.context, op: 0.9, dash: '5 4', label: byMode('SCRAPPED · not worth fixing', 'CONDEMNED · beyond economic repair') },
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
    withTooltip(g, () => tip(f)); focusTip(g, () => tip(f));
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
    if (r.header) { dl(svg, { x: 0, y: r.y, text: r.header === 'fwd' ? 'FORWARD' : r.header === 'back' ? 'RETURNS' : byMode('SCRAPPED', 'CONDEMNED (BER)'), color: KIND[r.header].color, mono: true }); return; }
    const { f, k } = r; const o = KIND[k];
    const g = svg.append('g').attr('class', `rr-arc rr-arc--${k}`).attr('transform', `translate(0,${r.y})`).attr('tabindex', 0).attr('role', 'img')
      .attr('aria-label', `${stateName(f.from)} to ${stateName(f.to)}: ${fmtInt(f.count)} transitions`);
    g.append('rect').attr('width', w).attr('height', rowH).attr('fill', 'transparent');
    g.append('text').attr('class', 'rr-ladder-name').attr('x', 0).attr('y', 12).text(`${stateName(f.from)} → ${stateName(f.to)}`);
    g.append('rect').attr('x', barX).attr('y', 20).attr('height', 6).attr('rx', 2).attr('width', barW).attr('fill', C.line);
    g.append('rect').attr('x', barX).attr('y', 20).attr('height', 6).attr('rx', 2).attr('width', Math.max(2, (barW * f.count) / maxC))
      .attr('fill', o.color).attr('fill-opacity', k === 'fwd' ? 0.75 : 0.6).attr('stroke', k === 'bad' ? o.color : null).attr('stroke-dasharray', o.dash || null);
    chipLabel(g, { x: w, y: 18, text: fmtInt(f.count), anchor: 'end', color: C.text, cls: 'rr-flow-chip' });
    withTooltip(g, () => tip(f)); focusTip(g, () => tip(f));
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
  const S = isSimple();
  const head = S
    ? (!overdue.length ? 'Every open repair job is still inside its promised date' : `${fmtInt(overdue.length)} repair jobs are past their promised date${worst ? `; the worst is ${fmtDays(worst.late_d)} late at ${shopLabel(worst.shop)}` : ''}`)
    : !overdue.length ? 'Every open repair order is still inside its quoted due date'
      : `${fmtInt(overdue.length)} repair orders are past quoted due${worst ? `; the worst is ${fmtDays(worst.late_d)} late at ${shopLabel(worst.shop)}` : ''}`;
  const f = chartFrame(host, {
    implication: byMode('Late repairs drain the spares pool. Chase the shops that are furthest past their promise first.', 'Overdue repairs eat float: chase the shops furthest past quote first.'),
    headline: head,
    subtitle: S ? `Each bar runs from the day a part went in to its return, or to now. The tick is the promised date. Hatching shows days late, red only beyond ${fmtInt(CRITICAL_LATE_D)} days.` : `Bar = induction → return (or now) · tick = quoted due · hatched = days past due, red only beyond ${fmtInt(CRITICAL_LATE_D)} d · shops by worst delay${now != null ? ` · now ${fmtWeek(Math.floor(now / HPW))}` : ''}`,
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
    h('span', {}, h('i', { style: { background: 'rgba(185,200,214,0.55)' } }), byMode('Open, on time', 'Open, inside quote')),
    h('span', {}, h('i', { style: { background: 'rgba(185,200,214,0.22)' } }), 'Returned'),
    h('span', {}, h('i', { class: 'rr-key-late' }), byMode('Past the promised date', 'Past quoted due')),
    h('span', {}, h('i', { style: { background: C.urgent } }), `Critical: > ${fmtInt(CRITICAL_LATE_D)} d past due`),
    h('span', {}, h('i', { style: { background: C.text, width: '2px', height: '12px' } }), byMode('Promised date', 'Quoted due date'))));
  const topOverdue = overdue.slice().sort((a, b) => ((b.late_d ?? 0) - (a.late_d ?? 0)) || (!!b.planted - !!a.planted)).slice(0, 3);
  if (topOverdue.length) {
    const chase = h('div', { class: 'rr-chase', role: 'list', 'aria-label': 'Overdue repair orders to chase first' },
      h('div', { class: 'rr-chase-head' }, h('span', {}, 'Chase first'), h('span', { class: 'rr-chase-rule' }, byMode('· most days past the promised date', '· most days past quoted due')), overdue.length > topOverdue.length ? h('span', { class: 'rr-chase-more' }, `+ ${fmtInt(overdue.length - topOverdue.length)} more ${byMode('late', 'overdue')} in the table below`) : null),
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
  let lastW = 0;
  function redraw() {
    // filter change: re-join in place (animated); the observer only redraws on a width change
    if (stop && lastW) { drawGantt(chart, rows(), now, lastW, true); return; }
    stop = responsive(chart, (w) => { lastW = w; drawGantt(chart, rows(), now, w); });
  }
  redraw();
  return () => stop?.();
}

function segmentedLite(options, value, onChange, label) {
  const g = h('div', { class: 'seg', role: 'radiogroup', 'aria-label': label });
  const set = (v) => { g.querySelectorAll(':scope > button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === String(v)))); onChange(v); };
  options.forEach((o) => g.append(h('button', { type: 'button', role: 'radio', dataset: { value: o.value }, 'aria-checked': String(o.value === value), onclick: () => set(o.value) }, o.label)));
  slidingThumb(g);
  return g;
}

/**
 * Repair-order Gantt. Filter changes (shop / status) re-join the rows keyed on the RO id: rows slide to their new
 * place (transform), bars re-scale (base token), new rows fade in and removed rows fade out. A width change redraws.
 */
function drawGantt(el, rows, now, w, animate = false) {
  if (!rows.length) { el.replaceChildren(h('div', { class: 'state' }, 'No repair orders match this filter.')); el.__gantt = null; return; }
  const narrow = w < 560;
  const rowH = 20, shopH = 26;
  const labelW = narrow ? 76 : 150;
  const hasPlanted = rows.some((o) => o.planted && o.open && o.overdue);
  const m = { top: 8, right: narrow ? 52 : hasPlanted ? 96 : 64, bottom: 28, left: labelW };
  const shops = [...new Set(rows.map((o) => o.shop))];
  const hgt = m.top + m.bottom + rows.length * rowH + shops.length * shopH;
  const iw = Math.max(60, w - m.left - m.right);
  let G = el.__gantt;
  if (!G || G.w !== w || G.right !== m.right || !G.svg.node().isConnected) {
    const svg = svgIn(el, w, hgt, 'Repair order Gantt chart');
    svg.append('defs').append('pattern').attr('id', 'rr-hatch').attr('width', 5).attr('height', 5).attr('patternUnits', 'userSpaceOnUse').attr('patternTransform', 'rotate(45)')
      .call((pt) => { pt.append('rect').attr('width', 5).attr('height', 5).attr('fill', 'rgba(185,200,214,0.18)'); pt.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 5).attr('stroke', 'rgba(185,200,214,0.75)').attr('stroke-width', 2); });
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    G = el.__gantt = { w, right: m.right, svg, g, bands: g.append('g'), labels: g.append('g'), axis: g.append('g'), nowG: g.append('g'), rowsG: g.append('g') };
    animate = false;
  }
  const T = (sel, o = {}) => (animate ? txSel(sel, o) : sel);
  G.svg.attr('height', hgt).attr('viewBox', `0 0 ${w} ${hgt}`);
  const lo = d3().min(rows, (o) => o.inH ?? o.start);
  const hi = d3().max(rows, (o) => Math.max(o.end ?? 0, o.due ?? 0, now ?? 0));
  const x = d3().scaleLinear().domain([lo, hi + (hi - lo) * 0.02]).range([0, iw]);
  // layout
  let yCur = 0;
  const pos = new Map();
  const bands = [];
  shops.forEach((sh) => {
    const rs = rows.filter((o) => o.shop === sh);
    bands.push({ shop: sh, y: yCur, h: shopH + rs.length * rowH, n: rs.length });
    yCur += shopH;
    rs.forEach((o) => { pos.set(o.ro_id, yCur); yCur += rowH; });
  });
  const ih = yCur;
  const bandSel = G.bands.selectAll('rect').data(bands, (b) => b.shop).join((en) => en.append('rect').attr('class', 'rr-shop-band').attr('rx', 6).attr('y', (b) => b.y).attr('height', (b) => b.h).style('opacity', 0));
  bandSel.attr('x', -labelW + 4).attr('width', iw + labelW - 4);
  T(bandSel).attr('y', (b) => b.y).attr('height', (b) => b.h).style('opacity', 1);
  const shopTxt = (b) => { const od = rows.filter((o) => o.shop === b.shop && o.open && o.overdue).length; return `${shopLabel(b.shop)} · ${b.n} ${isSimple() ? 'job' : 'RO'}${b.n === 1 ? '' : 's'}${od && od < b.n ? ` · ${od} ${isSimple() ? 'late' : 'overdue'}` : ''}`; };
  const lblSel = G.labels.selectAll('text').data(bands, (b) => b.shop).join((en) => en.append('text').attr('class', 'rr-shop-label').attr('transform', (b) => `translate(0,${b.y + 17})`));
  lblSel.attr('x', -labelW + 12).text(shopTxt);
  T(lblSel).attr('transform', (b) => `translate(0,${b.y + 17})`);
  G.axis.attr('transform', `translate(0,${ih})`);
  T(G.axis).call(d3().axisBottom(x).ticks(narrow ? 3 : 6).tickSizeOuter(0).tickSize(4).tickPadding(6).tickFormat((v) => fmtWeek(Math.floor(v / HPW))));
  styleAxis(G.axis);
  G.nowG.selectAll('*').remove();
  if (now != null) {
    G.nowG.append('line').attr('class', 'rr-now').attr('x1', x(now)).attr('x2', x(now)).attr('y1', 0).attr('y2', ih);
    dl(G.nowG, { x: x(now) - 4, y: 10, text: 'NOW', anchor: 'end', color: C.text });
  }
  const bx = (o) => x(o.inH ?? o.start);
  const ex = (o) => x(o.end ?? o.inH);
  const lateX = (o) => x(Math.max(o.due, o.inH ?? o.due));
  const rowG = G.rowsG.selectAll('g.rr-row').data(rows, (o) => o.ro_id).join(
    (en) => {
      const rg = en.append('g').attr('class', 'rr-row').attr('transform', (o) => `translate(0,${pos.get(o.ro_id)})`).style('opacity', 0)
        .attr('tabindex', 0).attr('role', 'listitem')
        .attr('aria-label', (o) => `${o.ro_id}, serial ${o.serial}, ${shopLabel(o.shop)}, ${o.open ? 'open' : 'returned'}, ${o.overdue ? `overdue ${fmtDays(o.late_d)}` : 'within quote'}`);
      rg.filter((o) => !!o.planted).append('rect').attr('class', 'rr-row-hl').attr('y', 1).attr('height', rowH - 2).attr('rx', 4);
      rg.append('rect').attr('class', 'rr-focus').attr('y', 1).attr('height', rowH - 2).attr('rx', 4).attr('fill', 'none');
      rg.append('text').attr('class', (o) => (o.planted ? 'gnm-label gnm-label--strong rr-row-t' : 'gnm-label rr-row-t')).attr('font-family', theme.font.mono).attr('x', -8).attr('y', rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'end').style('font-size', '11px')
        .text((o) => truncate(narrow ? o.ro_id : `${o.serial}`, labelW - 20, 6.6));
      rg.append('rect').attr('class', (o) => `rr-bar ${o.open ? 'is-open' : ''}`).attr('y', 5).attr('height', rowH - 10).attr('rx', 2);
      rg.filter((o) => o.due != null && o.end != null && o.end > o.due).append('rect').attr('class', (o) => `rr-bar-late ${isCritical(o) ? 'is-crit' : ''}`).attr('y', 5).attr('height', rowH - 10).attr('rx', 2);
      rg.filter((o) => o.due != null).append('line').attr('class', 'rr-due').attr('y1', 2).attr('y2', rowH - 2);
      const late = rg.filter((o) => o.open && o.overdue);
      late.filter(isCritical).append('use').attr('class', 'rr-late-icon').attr('href', '#i-alert').attr('y', 3).attr('width', 13).attr('height', 13).attr('color', C.urgent).style('color', C.urgent);
      late.append('text').attr('class', (o) => `rr-late-label ${isCritical(o) ? 'is-crit' : ''}`).attr('y', rowH / 2).attr('dy', '0.32em').text((o) => `+${Math.round(o.late_d)}d`)
        .append('tspan').attr('class', 'rr-late-ps').text((o) => (o.planted && !narrow ? ` · ${o.planted}` : ''));
      // new rows are placed at their final geometry, then fade in
      placeRow(rg, (sel) => sel);
      return rg;
    },
    (up) => up,
    (exit) => (animate ? txSel(exit, { ease: 'exit' }).style('opacity', 0).remove() : exit.remove()));
  function placeRow(sel, Tr) {
    sel.selectAll('.rr-row-hl, .rr-focus').attr('x', -labelW + 6).attr('width', iw + labelW - 8);
    Tr(sel.select('.rr-bar')).attr('x', bx).attr('width', (o) => Math.max(2, (o.overdue && o.due != null ? lateX(o) : ex(o)) - bx(o)));
    Tr(sel.select('.rr-bar-late')).attr('x', lateX).attr('width', (o) => Math.max(1.5, ex(o) - lateX(o)));
    Tr(sel.select('.rr-due')).attr('x1', (o) => x(o.due)).attr('x2', (o) => x(o.due));
    Tr(sel.select('.rr-late-icon')).attr('x', (o) => Math.min(iw + 4, ex(o) + 4));
    Tr(sel.select('.rr-late-label')).attr('x', (o) => Math.min(iw + 4, ex(o) + 4) + (isCritical(o) ? 16 : 2));
  }
  placeRow(rowG, (sel) => T(sel));
  T(rowG).attr('transform', (o) => `translate(0,${pos.get(o.ro_id)})`).style('opacity', 1);
  const rowTip = (o) => ({
    title: `${o.ro_id} · ${o.serial}`,
    rows: [['Shop', shopLabel(o.shop)], ['Inducted', o.inH != null ? fmtWeek(Math.floor(o.inH / HPW)) : '—'], ['Quoted TAT', fmtDays(o.quoted_tat_d)], [o.open ? 'Elapsed' : 'Actual TAT', fmtDays(o.open ? o.elapsed_d : o.actual_tat_d)], ['vs quoted due', o.late_d == null ? '—' : o.late_d > 0 ? `+${fmtDays(o.late_d)} late` : `${fmtDays(-o.late_d)} early`]],
    note: `${o.planted ? `Planted situation ${o.planted} · ` : ''}${o.open ? (isCritical(o) ? `Critical: more than ${fmtInt(CRITICAL_LATE_D)} d past due, chase the vendor` : o.overdue ? 'Overdue, chase the vendor' : 'Open, inside quote') : 'Returned'}`,
  });
  withTooltip(rowG, rowTip); focusTip(rowG, rowTip);
  drawIn(el, G.svg);
}

// ============================================================================= TAT distribution
function renderTatDist(host, r) {
  const dists = (r.tat_distribution || []).filter((d) => Array.isArray(d.counts) && d.counts.length);
  if (!dists.length) return null;
  const slow = dists.slice().sort((a, b) => (b.mean_d / b.quoted_mean_d) - (a.mean_d / a.quoted_mean_d))[0];
  const S = isSimple();
  const f = chartFrame(host, {
    implication: byMode('Shops take longer than they promise, so a spares pool sized on promises comes up short.', 'Shop turnaround runs longer than quoted, so float sized on quotes comes up short.'),
    headline: S ? `${shopLabel(slow.shop)} takes ${fmtDays(slow.mean_d)} on average against ${fmtDays(slow.quoted_mean_d)} promised; one in ten takes over ${fmtDays(slow.p90_d)}` : `${shopLabel(slow.shop)} averages ${fmtDays(slow.mean_d)} against ${fmtDays(slow.quoted_mean_d)} quoted; one in ten takes over ${fmtDays(slow.p90_d)}`,
    subtitle: S ? `Share of finished repairs by ${termText('tat')}, in ${slow.bin_width_d}-day steps. Solid line = actual average, dashed = promised. ${dists.map((d) => `${shopLabel(d.shop)}: ${fmtInt(d.n)} jobs`).join(' · ')}` : `Share of completed ROs by shop TAT · ${slow.bin_width_d}-day bins · solid = actual mean, dashed = quoted · ${dists.map((d) => `${shopLabel(d.shop)} n=${fmtInt(d.n)}`).join(' · ')}`,
    provenance: prov(dists[0], prov(r.meta)), source: 'rotables.json → tat_distribution',
    table: { columns: [{ key: 'shop', label: 'Shop', format: shopLabel }, { key: 'n', label: 'ROs', num: true, format: fmtInt }, { key: 'quoted_mean_d', label: 'Quoted mean', num: true, format: fmtDays }, { key: 'mean_d', label: 'Actual mean', num: true, format: fmtDays }, { key: 'median_d', label: 'Median', num: true, format: fmtDays }, { key: 'p90_d', label: 'p90', num: true, format: fmtDays }], rows: dists },
  });
  f.root.classList.add('mb-3');
  return respIn(f.body, (w) => {
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
  const S = isSimple();
  const headline = !rows.length ? 'TAT comparison not run' : S
    ? `${fmtInt(late.length)} of ${fmtInt(rows.length)} part and shop pairs take longer than promised${worst ? `; ${worst.pn} is ${fmtDays(worst.actual_mean_d - worst.quoted_d)} over` : ''}`
    : `${fmtInt(late.length)} of ${fmtInt(rows.length)} PN–shop pairs run slower than quoted${worst ? `; ${worst.pn} is ${fmtDays(worst.actual_mean_d - worst.quoted_d)} over` : ''}`;
  const f = chartFrame(host, {
    implication: byMode('For shops that run late, plan on the measured repair time, not the promise.', 'Plan on measured turnaround, not the quote, for the shops that run late.'),
    headline,
    subtitle: S ? 'Promised against actual repair time, one dot per part and shop. The whisker reaches the slowest one in ten. Dots above the line run late.' : `Quoted vs actual mean TAT (whisker to p90), one dot per PN × shop · ${byShop.map((b) => `${shopLabel(b.shop)} median ${fmtNum(b.ratio, 2)}×`).join(' · ')}`,
    provenance: prov(r.tat?.[0], prov(r.meta)), source: 'rotables.json → tat',
    table: { columns: [{ key: 'pn', label: 'PN' }, { key: 'shop', label: 'Shop', format: shopLabel }, { key: 'quoted_d', label: 'Quoted', num: true, format: fmtDays }, { key: 'actual_mean_d', label: 'Actual mean', num: true, format: fmtDays }, { key: 'p90_d', label: 'p90', num: true, format: fmtDays }, { key: 'n', label: 'ROs', num: true, format: fmtInt }], rows },
  });
  if (!rows.length) { f.body.append(h('div', { class: 'state' }, 'not run')); return null; }
  // shops are categories (no accent): the slowest shop (highest median ratio) is solid titanium, others hollow slate
  const slowShop = byShop.slice().sort((a, b) => (b.ratio ?? 0) - (a.ratio ?? 0))[0]?.shop;
  const colorOf = (s) => (s === slowShop ? SR.neutral : SR.context);
  return respIn(f.body, (w) => {
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
    dl(g, { x: iw, y: ih + 30, text: byMode('PROMISED REPAIR TIME →', 'QUOTED TAT →'), anchor: 'end', color: C.faint });
    // y = x reference
    const dmax = Math.min(x.domain()[1], y.domain()[1]);
    refLine(g, { x1: x(0), y1: y(0), x2: x(dmax), y2: y(dmax), label: byMode('on time', 'on quote'), dx: -4, dy: 14, anchor: 'end' });
    dl(g, { x: 6, y: 6, text: byMode('SLOWER THAN PROMISED ↑', 'SLOWER THAN QUOTED ↑'), color: C.faint });
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
      annotate(g, { x: wx, y: wy, dx: wx > cx ? -Math.min(wx - 8, 64) : 40, dy: wy < 60 ? 40 : -30, title: worst.pn, sub: `+${fmtDays(worst.actual_mean_d - worst.quoted_d)} ${byMode('late', 'vs quote')}` });
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
  const rec = r.recommended_id || 'I125';
  return {
    pn: ex.pn, station: ex.station || null,
    rate: num(pick(ex, 'rate_per_30d', 'removal_rate_per_30d', 'removals_per_30d')),
    tat: num(pick(ex, 'tat_days', 'tat_d', 'pipeline_days')) ?? num(tatRow?.actual_mean_d),
    spares: num(pick(ex, 'spares', 'total_spares')) ?? (num(ex.current) != null ? num(ex.current) + (num(ex.loop_units) ?? 0) : null),
    loop: num(ex.loop_units) ?? 0,
    // S = shelf + units already in the repair loop (exporter spares_total when present, else derived)
    presets: [['P0', ex.p0_units, 'P0'], ['P1', ex.p1_units, 'P1'], ['P2', ex.p2_units, 'P2'], [rec, ex.rec_units ?? ex.recommended, 'recommended']].filter(([, v]) => num(v) != null)
      .map(([code, v, sk]) => ({ code, value: num(ex.spares_total?.[sk]) ?? num(v) + (num(ex.loop_units) ?? 0), shelf: num(v) })),
    desc: ex.desc || '', deadline: ex.deadline || '', planted: ex.planted || null,
    cost: num(pick(ex, 'unit_cost_aed', 'unit_cost')),
    recommended: num(ex.recommended),
    reason: ex.reason || '',
    // A10: per-outstation inputs (rate at the station, resupply time from AUH, the plans' units there)
    stationViews: Array.isArray(ex.station_views) ? ex.station_views : [],
    provenance: ex.provenance || prov(r.meta),
  };
}

let ctxRec = null;
/** Availability that never prints a misleading "100.0%" for a Poisson tail: > 99.9%. */
const fmtAvail = (v) => (v == null ? '—' : v > 0.9995 ? '> 99.9%' : fmtPct(v, 1));
const fmtEbo = (v) => (v == null ? '—' : v < 0.01 ? '< 0.01' : fmtNum(v, 2));
/** Expected wait: hours under two days ("< 1 h", "5 h"), days above ("3.2 d"). */
const fmtWait = (d) => (d == null ? '—' : d * 24 < 1 ? '< 1 h' : d < 2 ? `${fmtInt(d * 24)} h` : `${fmtNum(d, 1)} d`);
const cap1 = (s) => String(s).replace(/^./, (c) => c.toUpperCase());
/** A station view is usable only when every outstation input is present. */
const svOk = (sv) => !!sv && num(sv.rate_per_30d) != null && num(sv.resupply_days) != null && !!sv.units && num(sv.units.P2) != null && sv.station;

function renderFloatCalc(host, r, method, ctx) {
  const S = isSimple();
  ctxRec = r.recommended_id || null;
  const rec = ctxRec || 'I125';
  const P = ctx.data.parts || {};
  const partsByPn = new Map((P.parts || []).map((p) => [p.pn, p]));
  const modes = r.calculator_modes || {};
  const examples = (r.float_examples || []).map((ex) => exampleInputs(ex, r));
  const accel = accelAssumption(r, method);
  const want = ctx.params.pn;
  let cur = examples.find((e) => e.pn === want) || examples.find((e) => e.planted === 'PS1') || examples[0] || { pn: null, rate: null, tat: null, spares: null, cost: null, presets: [], stationViews: [] };
  // A10: two clearly labelled views. hub = pooled float over the network repair-loop time; outstation = one station's
  // own shelf over the resupply time from AUH (rotables.json station_views). Deep link: ?view=outstation&station=BOM
  let calcMode = ctx.params.view === 'outstation' ? 'outstation' : 'hub';
  let station = ctx.params.station || null;
  /** Why the outstation view is off for this part (null = available). */
  const outstationIssue = (ex) => {
    if (r.outstation_mode !== 'enabled') return byMode('The outstation view is off: this export does not include airport resupply inputs.', `Outstation view disabled: outstation_mode is "${r.outstation_mode ?? 'missing'}" in rotables.json.`);
    if (!ex?.stationViews?.length) return byMode('The outstation view is off for this part: no airport resupply inputs were exported.', 'Outstation view disabled for this PN: no station_views exported.');
    if (ex.stationViews.some((sv) => !svOk(sv))) return byMode('The outstation view is off for this part: some airport resupply inputs are missing.', 'Outstation view disabled for this PN: a station view is missing its rate, resupply time or units.');
    return null;
  };
  const curView = () => (calcMode === 'outstation' ? cur.stationViews.find((sv) => sv.station === station) || null : null);

  host.append(h('div', { class: 'card-head' },
    h('div', {}, h('div', { class: 'card-kicker' }, byMode('Spares calculator · a simple formula, not the full simulation', 'Float calculator · METRIC-inspired (Palm’s theorem), not full METRIC')), h('h3', { class: 'card-title' }, byMode('How many spares does a repairable part need to cover the wait?', 'How many spares does a rotable need to cover its repair pipeline?'))),
    h('div', { class: 'row' }, ...[...new Set(['DERIVED', cur.provenance || 'SIMULATED'])].map((x) => provChip(x)))));

  // ---- view switch (hub pooled / one outstation)
  const modeSeg = h('div', { class: 'seg fc-mode-seg', role: 'radiogroup', 'aria-label': 'Calculator view', dataset: { role: 'calc-mode' } });
  const stationSel = h('select', { class: 'select fc-station-sel', id: 'fc-station', 'aria-label': 'Outstation' });
  const stationField = h('label', { class: 'fc-station-pick', for: 'fc-station' }, h('span', { class: 'fc-label' }, 'Airport'), stationSel);
  const modeLabel = h('p', { class: 'fc-mode-label', dataset: { role: 'calc-mode-label' }, 'aria-live': 'polite' });
  const modeNote = h('p', { class: 'fc-mode-note', dataset: { role: 'outstation-disabled' }, role: 'note', hidden: true });
  const modeRow = h('div', { class: 'fc-mode' }, h('div', { class: 'fc-mode-row' }, h('span', { class: 'fc-label' }, 'View'), modeSeg, stationField), modeLabel, modeNote);
  const escHost = h('div', { class: 'fc-esc' });
  host.append(modeRow, escHost);

  const VT = { rate: (v) => `${fmtNum(v, 2)} removals per 30 days`, tat: (v) => `${fmtNum(v, 1)} days`, spares: (v) => `${fmtInt(v)} spares`, cost: (v) => fmtAED(v), extra: (v) => `${fmtInt(v)} more spare${v === 1 ? '' : 's'}`, cut: (v) => `${fmtInt(v)} day${v === 1 ? '' : 's'} shorter` };
  const mkNum = (key, label, { min = 0, step = 1, hint, grouped = false } = {}) => {
    const id = `fc-${key}`;
    // grouped inputs show thousands separators ("47,977"), so they are text inputs parsed by num(stripCommas)
    const input = grouped ? h('input', { class: 'input', type: 'text', id, inputmode: 'numeric', autocomplete: 'off', dataset: { input: key, grouped: '1' } })
      : h('input', { class: 'input', type: 'number', id, min, step, inputmode: 'decimal', dataset: { input: key } });
    const range = h('input', { class: 'slider', type: 'range', min, step, 'aria-label': `${label} slider`, dataset: { range: key } });
    const vt = bindValueText(range, VT[key] || String);
    const lab = h('label', { for: id }, label);
    const hintEl = h('div', { class: 'fc-hint' }, hint || '');
    return { key, input, range, vt, lab, hintEl, el: h('div', { class: 'fc-field' }, lab, input, range, hintEl) };
  };
  const sel = h('select', { class: 'select', id: 'fc-pn', 'aria-label': 'Prefill from rotable' },
    examples.map((e) => h('option', { value: e.pn }, `${e.pn}${e.desc ? ` · ${e.desc}` : ''}${e.planted && !S ? ` · ${e.planted}` : ''}`)));
  if (cur.pn) sel.value = cur.pn;
  const fRate = mkNum('rate', 'Removals per 30 d', { step: 0.01 });
  const fTat = mkNum('tat', 'Pipeline TAT, days', { step: 0.1 });
  const fSp = mkNum('spares', 'Spares (S)', { step: 1 });
  const fCost = mkNum('cost', byMode('Price of one part, AED', 'Unit cost, AED'), { step: 1, hint: byMode('Price to buy or swap one part', 'Exchange / purchase price per serial'), grouped: true }); // step 1: the slider holds the field's exact value (47,977)
  const fields = [fRate, fTat, fSp, fCost];
  /** Field labels and hints name what the current view feeds in. */
  const FIELD_TEXT = {
    hub: {
      rate: [byMode('Removals per 30 days', 'Removals per 30 d'), byMode('Broken parts taken off across the network', 'Unscheduled removals (U/S), network')],
      tat: [byMode('Repair time, days', 'Pipeline TAT, days'), byMode('From removal to ready again, with shipping', `Removal → serviceable again (transport + shop + return) · ${modes.hub?.basis || 'network repair-loop time'}`)],
      spares: [byMode('Spares in the pool', 'Spares (S)'), byMode('Spares on shelves plus parts already in repair', 'Total spares: shelf + pipeline')],
    },
    outstation: {
      rate: [byMode('Removals per 30 days at this airport', 'Station removals per 30 d'), byMode('Broken parts taken off at this airport only', 'Unscheduled removals at this station')],
      tat: [byMode('Resupply time from AUH, days', 'Resupply time from AUH, days'), byMode('Time to send a good part from the home base, with the wait there', `Transit from AUH + expected hub wait · ${modes.outstation?.basis || 'resupply time from AUH'}`)],
      spares: [byMode('Spares on this airport’s shelf', 'Station units (S)'), byMode('Only this airport’s own spares count', 'Own units only (no pooling)')],
    },
  };
  const reason = h('div', { class: 'fc-hint fc-wide' });
  const presetBox = h('div', { class: 'fc-presets fc-wide', role: 'group', 'aria-label': 'Set spares to a policy level' });
  const presetLabel = h('span', { class: 'fc-label' });
  const inputs = h('div', { class: 'fc-inputs' },
    h('div', { class: 'fc-field fc-wide' }, h('label', { for: 'fc-pn' }, byMode('Fill in from a repairable part', 'Prefill from a rotable')), sel), reason, ...fields.map((f) => f.el), h('div', { class: 'fc-field fc-wide' }, presetLabel, presetBox));

  // outputs
  const out = (key, label, isKey) => { const v = h('div', { class: 'fc-out-value', dataset: { out: key } }, '—'); const l = h('div', { class: 'fc-out-label' }, label); return { v, l, el: h('div', { class: `fc-out ${isKey ? 'is-key' : ''}` }, l, v) }; };
  const oMu = out('pipeline_mean', 'Pipeline mean λT');
  const oA = out('availability', S ? cap1(termText('fill_rate')) : 'Availability P(X<S)', true);
  const oE = out('ebo', S ? cap1(termText('ebo')) : 'Expected backorders');
  const oW = out('expected_wait_days', byMode('Average wait per removal', 'Expected wait'));
  const oCap = out('capital_aed', byMode('Money tied up in these spares', 'Float capital'));
  const outs = h('div', { class: 'fc-outs', role: 'status', 'aria-live': 'polite' }, oA.el, oMu.el, oE.el, oW.el, oCap.el);
  const stationBox = h('div', { class: 'fc-station', dataset: { out: 'station' } });
  const results = h('div', { class: 'fc-results' }, outs, stationBox);
  const chartHost = h('div');

  // levers
  const lN = mkNum('extra', byMode('Buy this many more spares', 'Buy N more spares'), { min: 0, step: 1 });
  const lD = mkNum('cut', 'Cut TAT by d days', { min: 0, step: 1 });
  const leverBox = h('div', { class: 'fc-levers', role: 'region', 'aria-label': 'Lever comparison' });
  const verdict = h('p', { class: 'fc-verdict', dataset: { out: 'verdict' } });
  const assume = h('div', { class: 'fc-assume' });

  // grid areas: inputs left / outputs + chart right at desktop; outputs first on narrow screens
  inputs.classList.add('fc-area-in'); results.classList.add('fc-area-out'); chartHost.classList.add('fc-area-chart');
  host.append(h('div', { class: 'fc-grid' }, inputs, results, chartHost));
  const leverTitle = h('h2', { class: 't-16' });
  host.append(h('div', { class: 'section-title mt-3' }, leverTitle, h('span', { class: 'rule' })));
  // the levers act on the calculator inputs of the current view (hub pooled or one outstation)
  const basisSeg = h('div', { class: 'seg fc-basis', role: 'radiogroup', 'aria-label': 'Compare the levers at' });
  host.append(h('div', { class: 'fc-basis-row' }, h('span', { class: 'fc-label' }, 'Compare at'), basisSeg), h('div', { class: 'fc-lever-controls' }, lN.el, lD.el), leverBox, verdict, assume);
  host.append(S
    ? h('p', { class: 'rr-method-note mt-2' }, 'The calculator uses a standard formula for repairable spares. It assumes one stocking point, no limit on shop space and no scrapped parts. Expert mode shows the maths.')
    : h('p', { class: 'rr-method-note mt-2' }, 'Palm’s theorem: with Poisson removals at rate λ and any repair-time distribution of mean T, the number of units in the pipeline is Poisson(λT). Availability = P(X < S); EBO = E[max(X − S, 0)]; expected wait = EBO / λ. Single site, infinite repair capacity, no condemnation — hence “METRIC-inspired”, not a full multi-echelon METRIC. Hub view: T = network repair-loop time; outstation view: T = resupply time from AUH.'));

  const frame = chartFrame(chartHost, { implication: byMode('A pooled figure can flatter: at an outstation only the spares on that shelf decide whether a plane waits.', 'Pooled availability flatters: the station\'s own units decide whether an aircraft waits.'), headline: 'Float calculator', subtitle: 'Units in the repair pipeline', provenance: 'DERIVED', source: 'lib/floatcalc.js (mirrors src/gnm/policy/analytic.py)' });
  frame.root.dataset.story = 'float-pipeline';

  const state = { rate: null, tat: null, spares: null, cost: null, extra: 1, cut: 10 };
  const setRanges = () => {
    const rmax = Math.max(1, Math.ceil((state.rate ?? 1) * 3 * 10) / 10);
    fRate.range.max = rmax; fTat.range.max = Math.max(30, Math.ceil((state.tat ?? 30) * 2));
    fSp.range.max = Math.max(10, (state.spares ?? 5) * 2 + 4); fCost.range.max = Math.max(100000, Math.ceil(((state.cost ?? 50000) * 3) / 1000) * 1000);
    lN.range.max = 10; lD.range.max = Math.max(10, Math.floor(state.tat ?? 10));
    [fRate, fTat, fSp, fCost, lN, lD].forEach((f) => fillPct(f.range)); // a new max moves the fill too
  };
  const sync = (key) => {
    const all = { rate: fRate, tat: fTat, spares: fSp, cost: fCost, extra: lN, cut: lD };
    Object.entries(all).forEach(([k, f]) => { if (k === key) return; f.input.value = f.input.dataset.grouped ? (state[k] == null ? '' : fmtCount(state[k])) : state[k] ?? ''; f.range.value = state[k] ?? 0; f.vt?.(); });
  };
  const round = (v, d) => (v == null ? null : Math.round(v * 10 ** d) / 10 ** d);
  const presetText = (code, value, shelf, loop) => {
    const nm = S ? displayName(code, { mode: 'short' }) : code;
    if (S) return `${nm}: ${fmtInt(value)}`;
    return loop ? `${nm} · ${fmtInt(shelf ?? value - loop)} + ${fmtInt(loop)} = ${fmtInt(value)}` : `${nm} · S = ${fmtInt(value)}`;
  };

  /** View switch + labels for the current mode and part. */
  function renderMode() {
    const issue = outstationIssue(cur);
    if (issue && calcMode === 'outstation') calcMode = 'hub';
    const views = issue ? [] : cur.stationViews;
    if (calcMode === 'outstation' && !views.some((sv) => sv.station === station)) {
      // default station: the exporter's highlighted station view when present, else the busiest outstation
      const hi = (r.float_examples || []).find((e) => e.pn === cur.pn)?.station_view?.station;
      station = views.find((sv) => sv.station === hi)?.station || views.slice().sort((a, b) => b.rate_per_30d - a.rate_per_30d)[0]?.station || null;
    }
    const optLabel = { hub: byMode('Hub pool', modes.hub?.label || 'Hub pooled view'), outstation: byMode('One outstation', modes.outstation?.label || 'Outstation view') };
    // buttons are built once and updated in place, so the sliding thumb glides between them
    if (!modeSeg.querySelector('button')) {
      modeSeg.append(...['hub', 'outstation'].map((m) => h('button', { type: 'button', role: 'radio', dataset: { mode: m }, onclick: () => setMode(m) }, optLabel[m])));
      slidingThumb(modeSeg);
    }
    modeSeg.querySelectorAll('button').forEach((b) => {
      const m = b.dataset.mode;
      b.setAttribute('aria-checked', String(calcMode === m));
      b.disabled = m === 'outstation' && !!issue;
      b.title = m === 'outstation' && issue ? issue : '';
    });
    stationSel.replaceChildren(...views.map((sv) => h('option', { value: sv.station }, `${sv.station}${sv.invalid_recommendation ? ' · flagged' : ''}`)));
    if (station) stationSel.value = station;
    stationField.hidden = calcMode !== 'outstation';
    modeNote.hidden = !issue;
    modeNote.replaceChildren(...(issue ? [icon('info'), h('span', {}, issue)] : []));
    const basis = calcMode === 'outstation' ? (modes.outstation?.basis || 'resupply time from AUH') : (modes.hub?.basis || 'network repair-loop time');
    modeLabel.dataset.mode = calcMode;
    modeLabel.replaceChildren(
      h('strong', {}, calcMode === 'outstation' ? `${optLabel.outstation} · ${station}` : optLabel.hub), ' · uses the ', h('span', { dataset: { role: 'calc-basis' } }, basis), '. ',
      calcMode === 'outstation'
        ? byMode(`Only the spares on ${station}’s own shelf count. AUH refills that shelf.`, cap1(modes.outstation?.note || ''))
        : byMode('All spares are pooled. They cover parts that are away for repair.', cap1(modes.hub?.note || '')));
    const ft = FIELD_TEXT[calcMode];
    [['rate', fRate], ['tat', fTat], ['spares', fSp]].forEach(([k, f]) => { f.lab.textContent = ft[k][0]; f.hintEl.textContent = ft[k][1]; f.range.setAttribute('aria-label', `${ft[k][0]} slider`); });
    oMu.l.textContent = S ? (calcMode === 'outstation' ? 'Parts on the way from AUH (average)' : 'Parts away for repair (average)') : calcMode === 'outstation' ? 'Resupply pipeline mean λT' : 'Pipeline mean λT';
    const cutWhat = calcMode === 'outstation' ? byMode('resupply time', 'resupply') : byMode('repair time', 'TAT');
    lD.lab.textContent = S ? `Cut ${cutWhat} by this many days` : `Cut ${cutWhat} by d days`;
    lD.range.setAttribute('aria-label', `${lD.lab.textContent} slider`);
    leverTitle.textContent = S ? `Compare two fixes: buy spares or cut the ${cutWhat}` : `Lever comparison: buy spares vs cut ${cutWhat}`;
    presetLabel.textContent = calcMode === 'outstation' ? byMode(`Set the spares to a plan’s level at ${station}`, `Set S to a policy’s units at ${station}`) : byMode('Set the spares to a plan’s level', 'Set S to a policy level · shelf + in loop = S');
    // A7: the hero part's escalation text, from parts.json
    escHost.replaceChildren(...[escalationBlock(partsByPn.get(cur.pn), { compact: true })].filter(Boolean));
    assume.replaceChildren(...(calcMode === 'outstation'
      ? []
      : accel ? [provChip(accel.provenance), h('span', {}, S ? `Assumed fee to speed up a repair: ${fmtAED(accel.value)} per day per part.` : `Repair acceleration fee ${fmtAED(accel.value)} per day per unit (${accel.provenance === 'ASSUMED' ? 'ASSUMED' : accel.provenance}; ${accel.source})`)]
        : [provChip('ASSUMED'), h('span', {}, 'Repair acceleration fee: not exported — TAT-cut cost not run')]));
  }
  function setMode(m) {
    calcMode = m;
    load(cur);
    ctx.setParams({ view: calcMode === 'outstation' ? 'outstation' : '', station: calcMode === 'outstation' ? station || '' : '' });
  }
  stationSel.addEventListener('change', () => { station = stationSel.value; ctx.setParams({ station }); load(cur); });

  const load = (ex) => {
    cur = ex;
    renderMode();
    const sv = curView();
    let presets;
    if (sv) {
      // outstation: the station's own removals over the resupply time from AUH; S = that station's units
      presets = [['P0', sv.units.P0], ['P1', sv.units.P1], ['P2', sv.units.P2], [rec, sv.units.recommended]].filter(([, v]) => num(v) != null).map(([code, v]) => ({ code, value: num(v), shelf: num(v) }));
      Object.assign(state, { rate: round(num(sv.rate_per_30d), 6), tat: round(num(sv.resupply_days), 6), spares: num(sv.units.P2), cost: ex.cost });
    } else {
      // wave C: open on P2's S (the core plan); removals to 1 decimal, TAT to whole days
      presets = ex.presets || [];
      const recS = presets.find((p) => p.code === 'P2')?.value;
      Object.assign(state, { rate: round(ex.rate, 1), tat: round(ex.tat, 0), spares: recS ?? ex.spares, cost: ex.cost });
    }
    lD.range.max = Math.max(10, Math.floor(state.tat ?? 10));
    if (state.tat != null && state.cut > state.tat) state.cut = Math.floor(state.tat / 2);
    const loop = sv ? 0 : ex.loop ?? 0;
    reason.replaceChildren(...(sv
      ? [S ? `${sv.station}: only the spares on this airport’s shelf count.` : `${ex.deadline ? `${ex.deadline} (hypothetical deadline class) · ` : ''}${sv.station} · station units only, resupplied from AUH.`]
      : [S ? `Hub pool: the spares include ${fmtInt(loop)} part${loop === 1 ? '' : 's'} already in the repair loop.` : `${ex.deadline ? `${ex.deadline} (hypothetical deadline class) · ` : ''}network float · spares include ${fmtInt(loop)} units already in the repair loop. `,
        !S && ex.reason ? h('details', { class: 'fc-why' }, h('summary', {}, `Why the frontier option ${rec} holds ${ex.recommended != null ? fmtInt(ex.recommended) : 'these'} base-stock units`), h('p', {}, ex.reason)) : '']));
    presetBox.replaceChildren(...presets.map((p) => h('button', { type: 'button', class: 'btn btn--sm', 'aria-pressed': 'false', title: displayName(p.code), dataset: { preset: p.code, value: p.value }, onclick: () => { state.spares = p.value; sync(null); compute(); } }, presetText(p.code, p.value, p.shelf, loop))));
    cur.livePresets = presets;
    setRanges(); sync(null); compute();
  };
  [...fields, lN, lD].forEach((f) => {
    const onIn = (src) => () => {
      const v = num(String(src.value).replace(/[,\s]/g, ''));
      state[f.key] = v;
      if (src === f.input) { f.range.value = v ?? 0; f.vt?.(); } else f.input.value = f.input.dataset.grouped ? (v == null ? '' : fmtCount(v)) : v ?? '';
      fillPct(f.range);
      computeRAF(); // addendum: slider / typing updates coalesce to one recompute per animation frame
    };
    f.input.addEventListener('input', onIn(f.input));
    f.range.addEventListener('input', onIn(f.range));
    if (f.input.dataset.grouped) f.input.addEventListener('change', () => { if (state[f.key] != null) f.input.value = fmtCount(state[f.key]); });
  });
  sel.addEventListener('change', () => { const ex = examples.find((e) => e.pn === sel.value); if (ex) { ctx.setParams({ pn: ex.pn }); load(ex); } });

  /** Station box: in the outstation view, every plan's units at this station (exported, Palm) + the A9 flag. */
  function renderStation() {
    const sv = curView();
    const pnFlags = (P.invalid_allocations || []).filter((f) => f.pn === cur.pn);
    if (!sv) {
      const n = outstationIssue(cur) ? 0 : cur.stationViews.length;
      const kids = [];
      if (n) kids.push(h('p', { class: 'fc-station-note' }, icon('info'), h('span', {}, byMode(`This is the hub pool. Switch to “One outstation” to see one of ${fmtInt(n)} airports and its own shelf.`, `Hub pooled view. The outstation view sizes one of ${fmtInt(n)} stations on its resupply time from AUH.`))));
      if (pnFlags.length) kids.push(allocationFlagNote(pnFlags, { text: P.invalid_allocation_text, compact: true }));
      stationBox.replaceChildren(...kids);
      stationBox.hidden = !kids.length;
      return;
    }
    stationBox.hidden = false;
    const fmtA = (v) => (v == null ? '—' : v > 0.9995 ? '> 99.9%' : v > 0.99 ? fmtPct(v, 1) : fmtPct(v, 0));
    const rows = [['P0', ''], ['P1', ''], ['P2', 'is-rec'], ['recommended', 'is-opt']].filter(([k]) => sv.units[k] != null);
    const code = (k) => (k === 'recommended' ? rec : k);
    const flagsHere = pnFlags.filter((f) => f.station === sv.station);
    stationBox.replaceChildren(...[
      h('div', { class: 'fc-station-head' }, h('span', { class: 'fc-out-label' }, byMode(`Each plan at ${sv.station}`, `Station view · ${sv.station} · exported`)), h('span', { class: 'fc-hint' }, S ? `${fmtNum(sv.rate_per_30d, 2)} removals a month · ${fmtNum(sv.resupply_days, 1)} days to resupply from AUH · own spares only` : `${fmtNum(sv.rate_per_30d, 3)} removals / 30 d · ${fmtNum(sv.resupply_days, 2)}-day resupply from AUH (transit + expected hub wait), as P2 sizes it · own units only`)),
      h('div', { class: 'fc-station-rows' }, rows.map(([k, cls]) => h('div', { class: `fc-station-row ${cls}`, dataset: { station: k } },
        h('span', { class: 'fc-station-k' }, S ? displayName(code(k), { mode: 'short' }) : `${code(k)}${k === 'P2' ? ' · core' : k === 'recommended' ? ' · option' : ''}`),
        h('span', { class: 'fc-station-u' }, `${fmtInt(sv.units[k])} unit${sv.units[k] === 1 ? '' : 's'}`), h('span', { class: 'fc-station-a' }, fmtA(sv.availability?.[k]))))),
      sv.invalid_recommendation || flagsHere.length
        ? (flagsHere.length ? allocationFlagNote(flagsHere, { text: P.invalid_allocation_text, compact: true })
          : h('div', { class: 'pi-alloc-flags is-compact', role: 'note', dataset: { role: 'invalid-allocations' } }, icon('alert'), h('p', {}, h('strong', {}, 'Flagged: '), P.invalid_allocation_text || 'invalid recommendation', '.')))
        : null].filter(Boolean));
  }
  const pmf = makePmf(frame);
  const computeRAF = throttleRAF(() => compute());
  function compute() {
    [fRate, fTat, fSp, fCost, lN, lD].forEach((f) => fillPct(f.range));
    const { rate, tat, spares, cost, extra, cut } = state;
    const sv = curView();
    const ok = [rate, tat, spares, cost].every((v) => v != null && v >= 0);
    if (!ok) {
      [oMu, oA, oE, oW, oCap].forEach((o) => (o.v.textContent = 'not run'));
      frame.root.querySelector('.chart-headline').textContent = byMode('Enter the removals, time, spares and price to size the pool', 'Enter removal rate, TAT, spares and unit cost to size the float');
      frame.root.querySelector('.chart-subtitle').textContent = byMode('Parts away at once', 'Units in the repair pipeline · Poisson(λT)');
      frame.body.replaceChildren(h('div', { class: 'state' }, 'not run'));
      leverBox.replaceChildren(); verdict.textContent = '';
      return;
    }
    const Sn = Math.round(spares);
    const res = floatCalc(rate, tat, Sn, cost);
    oMu.v.textContent = `${fmtNum(res.pipeline_mean, sv ? 2 : 1)} units`;
    oA.v.textContent = fmtAvail(res.availability);
    oE.v.textContent = fmtEbo(res.ebo);
    oW.v.textContent = fmtWait(res.expected_wait_days);
    // exact values ride along in data-value (the text is rounded for reading; tests compare the exact maths)
    Object.assign(oMu.v.dataset, { value: res.pipeline_mean }); Object.assign(oA.v.dataset, { value: res.availability });
    Object.assign(oE.v.dataset, { value: res.ebo }); Object.assign(oW.v.dataset, { value: res.expected_wait_days });
    presetBox.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.value === Sn)));
    renderStation();
    oCap.v.textContent = fmtAED(res.capital_aed);
    const sp = `spare${Sn === 1 ? '' : 's'}`;
    frame.root.querySelector('.chart-headline').textContent = sv
      ? (S ? `${fmtInt(Sn)} ${sp} at ${sv.station} give${Sn === 1 ? 's' : ''} a ${fmtAvail(res.availability)} chance the part is on the shelf` : `${fmtInt(Sn)} station unit${Sn === 1 ? '' : 's'} at ${sv.station} cover${Sn === 1 ? 's' : ''} ${fmtAvail(res.availability)} of removals; resupply pipeline ${fmtNum(res.pipeline_mean, 2)}`)
      : (S ? `${fmtInt(Sn)} pooled ${sp} give${Sn === 1 ? 's' : ''} a ${fmtAvail(res.availability)} chance the part is on the shelf` : `${fmtInt(Sn)} pooled spare${Sn === 1 ? '' : 's'} cover ${fmtAvail(res.availability)} of removals against a mean pipeline of ${fmtNum(res.pipeline_mean, 1)} units`);
    frame.root.querySelector('.chart-subtitle').textContent = S
      ? `How likely it is that a given number of parts are ${sv ? 'on the way from AUH' : 'away for repair'} at once. Red bars mean more are away than there are spares.`
      : sv ? `P(k units in the resupply pipeline), X ~ Poisson(λT = ${fmtNum(rate, 3)}/30 d × ${fmtNum(tat, 2)} d) for ${cur.pn} at ${sv.station} · bars at k ≥ S are shortages`
        : `P(k units in the repair pipeline), X ~ Poisson(λT = ${fmtNum(rate, 1)}/30 d × ${fmtInt(tat)} d)${cur.pn ? ` for ${cur.pn}` : ''} · bars at k ≥ S are shortages`;
    pmf.update(res.pipeline_mean, Sn);
    // levers act on the current view's inputs
    const viewName = sv ? byMode(`${sv.station} shelf`, `Outstation view · ${sv.station}`) : byMode('Hub pool', 'Network (pooled) view');
    basisSeg.replaceChildren(h('button', { type: 'button', role: 'radio', 'aria-checked': 'true', dataset: { basis: 'inputs' }, onclick: () => compute() }, `${viewName} · ${S ? `${fmtInt(Sn)} ${sp}` : `S = ${fmtInt(Sn)}`}`));
    const L = { rate, tat, S: Sn };
    const fee = sv ? null : accel ? accel.value : null;
    const N = Math.max(0, Math.round(extra ?? 0)), D = Math.min(Math.max(0, cut ?? 0), L.tat);
    const cl = compareLevers(L.rate, L.tat, L.S, cost, D, N, fee ?? 0);
    const gainA = cl.extra_spares.availability - cl.base.availability;
    const gainB = cl.tat_cut.availability - cl.base.availability;
    // C6 (wave 4): highlight the CHEAPER lever per availability point (annual AED / pt)
    const annA = carryingValue(cl.extra_spares.incremental_capital_aed, method);
    const annB = fee != null ? cl.tat_cut.incremental_annual_aed : null;
    const perPt = (ann, gain) => (ann != null && gain > 1e-9 ? ann / (gain * 100) : null);
    const cA = perPt(annA, gainA), cB = perPt(annB, gainB);
    const betterA = cA != null && (cB == null || cA < cB - 1e-6), betterB = cB != null && (cA == null || cB < cA - 1e-6);
    const cell = (v, o, better) => h('td', { class: better ? 'is-better' : '', dataset: o ? { out: o } : undefined }, v);
    const rowC = (label, a, b, outA, outB) => h('tr', {}, h('th', { scope: 'row' }, label), cell(a, outA, betterA), cell(b, outB, betterB));
    const gainTxt = (o, gain) => [fmtAvail(o.availability), h('span', { class: 'fc-gain' }, ` ${gain >= 0 ? '+' : '−'}${fmtNum(Math.abs(gain) * 100, 1)} pts`)];
    const thLever = (title, key, better) => h('th', { scope: 'col', class: better ? 'is-better' : '', dataset: { lever: key } }, h('span', { class: 'fc-lever-title' }, title), better ? h('span', { class: 'fc-win' }, icon('check'), 'Cheaper per point') : null);
    const cutWhat = sv ? byMode('resupply time', 'resupply') : byMode('repair time', 'TAT');
    const buyT = `Buy ${fmtInt(N)} more spare${N === 1 ? '' : 's'}`, cutT = `Cut ${cutWhat} by ${fmtInt(D)} day${D === 1 ? '' : 's'}`;
    leverBox.replaceChildren(h('table', { class: 'fc-cmp' },
      h('caption', { class: 'sr-only' }, `Lever comparison: buy spares versus cut ${cutWhat}`),
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, h('span', { class: 'sr-only' }, 'Metric')), thLever(buyT, 'extra_spares', betterA), thLever(cutT, 'tat_cut', betterB))),
      h('tbody', {},
        rowC(byMode('Chance on the shelf', 'Availability'), gainTxt(cl.extra_spares, gainA), gainTxt(cl.tat_cut, gainB), 'extra_spares_availability', 'tat_cut_availability'),
        rowC(byMode('Expected waits for a part', 'Expected backorders'), fmtEbo(cl.extra_spares.ebo), fmtEbo(cl.tat_cut.ebo), 'extra_spares_ebo', 'tat_cut_ebo'),
        rowC(byMode('Average wait', 'Expected wait'), fmtWait(cl.extra_spares.expected_wait_days), fmtWait(cl.tat_cut.expected_wait_days)),
        rowC(byMode('One-off cost', 'One-off capital'), fmtAED(cl.extra_spares.incremental_capital_aed), fmtAED(0), 'extra_spares_capital'),
        rowC(byMode('Yearly cost', 'Annual cost'), h('span', {}, carrying(cl.extra_spares.incremental_capital_aed, method), h('span', { class: 'fc-gain' }, byMode(' to keep', ' carrying'))), h('span', {}, fee != null ? fmtAED(cl.tat_cut.incremental_annual_aed) : 'not run', h('span', { class: 'fc-gain' }, ' fees')), null, 'tat_cut_annual'),
        rowC(byMode('Yearly cost per point', 'Annual cost per pt'), cA != null ? fmtAED(cA) : '—', cB != null ? fmtAED(cB) : '—', 'extra_spares_per_pt', 'tat_cut_per_pt'))));
    [['extra_spares_availability', cl.extra_spares.availability], ['tat_cut_availability', cl.tat_cut.availability], ['extra_spares_ebo', cl.extra_spares.ebo], ['tat_cut_ebo', cl.tat_cut.ebo]]
      .forEach(([k, v]) => { const c = leverBox.querySelector(`[data-out="${k}"]`); if (c) c.dataset.value = v; });
    const ann = annA;
    const saturated = Math.max(gainA, gainB) < 0.0005;
    const p0S = (cur.livePresets || []).find((p) => p.code === 'P0')?.value;
    const nYr = fmtNum((L.rate * 365) / 30, 1);
    const annualTxt = fee != null && ann != null
      ? (S ? `Each year the spares cost ${fmtAED(ann)} to keep, against ${fmtAED(cl.tat_cut.incremental_annual_aed)} in fees to speed up ${nYr} repairs.` : `On an annual basis the spares cost ${fmtAED(ann)}/yr to carry versus ${fmtAED(cl.tat_cut.incremental_annual_aed)}/yr in acceleration fees for ${nYr} removals a year.`)
      : sv ? byMode('Faster resupply has no cost in the data, so only the spares’ cost is shown.', 'No resupply-acceleration cost is exported: only the spares’ carrying cost is compared.')
        : 'Annual cost comparison needs the carrying rate and acceleration fee from the assumption register.';
    if (saturated) {
      // already saturated (e.g. the Recommended S): say so, and offer the level where the levers bite
      verdict.replaceChildren(h('strong', {}, S ? `With ${fmtInt(L.S)} ${sp} the chance is already as high as it gets: neither fix changes it. ` : `At S = ${fmtInt(L.S)} the float is saturated: neither lever moves availability. `),
        p0S != null && p0S !== Sn ? h('button', { type: 'button', class: 'btn btn--sm btn--ghost fc-try-p0', onclick: () => { state.spares = p0S; sync(null); compute(); } }, S ? `Compare at the Simple Rulebook level (${fmtInt(p0S)} spares)` : `Compare the levers at P0 (S = ${fmtInt(p0S)})`) : null, ' ', annualTxt);
      return;
    }
    const cheaper = betterA ? (S ? `Buying ${fmtInt(N)} more spare${N === 1 ? '' : 's'} is the cheaper way to raise the chance` : `Buying ${fmtInt(N)} spare${N === 1 ? '' : 's'} is the cheaper lever per availability point`)
      : betterB ? (S ? `Cutting the ${cutWhat} by ${fmtInt(D)} days is the cheaper way to raise the chance` : `Cutting ${cutWhat} by ${fmtInt(D)} d is the cheaper lever per availability point`) : null;
    const more = gainA > gainB + 1e-9 ? byMode('the spares add more', 'the spares add more availability') : gainB > gainA + 1e-9 ? byMode(`the shorter ${cutWhat} adds more`, `the ${cutWhat} cut adds more availability`) : byMode('both add the same', 'both add the same availability');
    verdict.replaceChildren(
      h('strong', {}, cheaper || (gainA > gainB + 1e-9 ? `${buyT} lifts the chance more` : gainB > gainA + 1e-9 ? `${cutT} lifts the chance more` : 'Both fixes give the same result')),
      cheaper ? `; ${more} (${fmtPts(gainA)} vs ${fmtPts(gainB)}). ` : ` (${fmtPts(gainA)} vs ${fmtPts(gainB)}). `, annualTxt);
  }
  setRanges();
  if (cur.pn) load(cur); else { renderMode(); compute(); }
  if (!examples.length) reason.textContent = 'No float examples exported — enter values to explore.';
  return () => { computeRAF.cancel(); pmf.stop(); };
}
const fmtPts = (v) => `${v >= 0 ? '+' : '−'}${fmtNum(Math.abs(v) * 100, 1)} pts`;
function carryingValue(capital, method) {
  const a = (method?.assumptions || []).find((x) => /carrying_cost/.test(x.key || ''));
  const rate = num(a?.value);
  return rate != null ? capital * rate : null;
}
function carrying(capital, method) { const v = carryingValue(capital, method); return v == null ? 'not run' : fmtAED(v); }

/**
 * Pipeline distribution, built once and updated in place: bars are keyed on k and drawn as unit rects scaled by
 * transform, so slider changes interpolate heights and positions (base token); the axes and the S marker transition.
 */
function makePmf(frame) {
  let W = 0, L = null, cur = null;
  function render(w, animate) {
    if (!cur) return;
    const { mu, S } = cur;
    const sd = Math.sqrt(Math.max(mu, 0.01));
    const kMax = Math.max(S + 3, Math.ceil(mu + 4 * sd), 6);
    const series = pmfSeries(mu, kMax);
    frame.setTable([{ key: 'k', label: 'Units in pipeline (k)', num: true }, { key: 'p', label: 'P(X = k)', num: true, format: (v) => fmtPct(v, 2) }, { key: 'zone', label: 'Zone' }], series.map((d) => ({ ...d, zone: d.k < S ? 'covered by spares' : 'shortage (backorder)' })));
    const hgt = 240;
    const m = { top: 28, right: 16, bottom: 36, left: 44 };
    const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
    if (w !== W || !L || !L.svg.node().isConnected) {
      const svg = svgIn(frame.body, w, hgt, 'Poisson pipeline distribution');
      const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
      L = { svg, g, grid: g.append('g'), ya: g.append('g'), xa: g.append('g').attr('transform', `translate(0,${ih})`) };
      dl(g, { x: iw, y: ih + 30, text: byMode('PARTS AWAY AT ONCE (k) →', 'UNITS IN PIPELINE (k) →'), anchor: 'end', color: C.faint });
      L.bars = g.append('g');
      L.mark = g.append('g').attr('class', 'rr-pmf-s');
      L.mark.append('line').attr('x1', 0).attr('x2', 0).attr('y1', -14).attr('y2', ih).attr('stroke', C.text).attr('stroke-width', 1.25).attr('stroke-dasharray', '3 3');
      L.sLab = dl(L.mark, { x: 6, y: -18, text: '', color: C.text, strong: true, dy: '0.7em' });
      if (w >= 420) {
        L.cov = dl(L.mark, { x: -8, y: 6, text: '◀ covered', anchor: 'end', color: C.accent });
        L.sho = dl(L.mark, { x: 8, y: 6, text: 'shortage ▶', color: SR.urgent });
      }
      W = w; animate = false;
    }
    const T = (sel) => (animate ? txSel(sel) : sel);
    L.svg.attr('aria-label', `Poisson pipeline distribution, mean ${fmtNum(mu, 2)}, spares ${S}`);
    const x = d3().scaleBand().domain(series.map((d) => d.k)).range([0, iw]).padding(0.18);
    const y = d3().scaleLinear().domain([0, d3().max(series, (d) => d.p) * 1.15]).nice().range([ih, 0]);
    gridY(L.grid, y, iw, 4);
    T(L.ya).call(d3().axisLeft(y).ticks(4).tickSizeOuter(0).tickSize(0).tickPadding(8).tickFormat((v) => fmtPct(v, 0)));
    styleAxis(L.ya, { domain: false });
    const every = Math.ceil(series.length / (w < 480 ? 8 : 16));
    T(L.xa).call(d3().axisBottom(x).tickSize(4).tickValues(series.map((d) => d.k).filter((k) => k % every === 0)));
    L.xa.attr('class', 'gnm-axis').selectAll('text').attr('font-family', theme.font.mono);
    L.xa.selectAll('.tick line').attr('stroke', C.lineStrong);
    const tf = (d) => `translate(${x(d.k)},${ih}) scale(1,${-Math.max(0, ih - y(d.p))})`;
    const bars = L.bars.selectAll('rect').data(series, (d) => d.k).join(
      (en) => en.append('rect').attr('y', 0).attr('height', 1).attr('width', x.bandwidth()).attr('transform', (d) => `translate(${x(d.k)},${ih}) scale(1,0)`),
      (up) => up,
      (ex) => (animate ? txSel(ex, { ease: 'exit' }).style('opacity', 0).remove() : ex.remove()));
    bars.attr('fill', (d) => (d.k < S ? SR.recommended : SR.urgent)).attr('fill-opacity', (d) => (d.k < S ? 0.75 : 0.8));
    T(bars).attr('width', x.bandwidth()).attr('transform', tf).style('opacity', 1);
    withTooltip(bars, (d) => ({ title: `${d.k} unit${d.k === 1 ? '' : 's'} in the pipeline`, rows: [['P(X = k)', fmtPct(d.p, 2)], ['Zone', d.k < S ? 'Covered by spares' : 'Shortage']] }));
    const sx = (x(S) ?? iw) - (x.step() * x.padding()) / 2;
    const right = sx > iw * 0.7;
    L.sLab.text(`S = ${S}`).attr('x', right ? -6 : 6).attr('text-anchor', right ? 'end' : 'start');
    if (L.cov) L.cov.attr('x', -Math.min(8, sx - 4));
    T(L.mark).attr('transform', `translate(${sx},0)`);
    drawIn(frame.body, L.svg);
  }
  const stop = responsive(frame.body, (w) => render(w, false));
  return { stop, update(mu, S) { cur = { mu, S }; if (W) render(W, true); } };
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
  const S = isSimple();
  const headline = S
    ? (hub.length ? `At the hub the formula expects ${fmtPct(hp)} on the shelf; the simulation gives ${fmtPct(hs)}` : `The formula expects ${fmtPct(wavg(rows, 'palm'))} on the shelf; the simulation gives ${fmtPct(wavg(rows, 'sim'))}`)
    : hub.length
      ? `Palm predicts ${fmtPct(hp)} fill at the hub; the simulation delivers ${fmtPct(hs)}`
      : `Palm predicts ${fmtPct(wavg(rows, 'palm'))} fill; the simulation delivers ${fmtPct(wavg(rows, 'sim'))}`;
  const f = chartFrame(host, {
    implication: byMode('The simple formula is a good first guess. The simulation shows where pooling and shipping matter.', 'The simple formula is a good first estimate; the simulation shows where pooling and transport bite.'),
    headline,
    subtitle: S ? `One dot per part and airport; bigger dots had more requests.${pol ? ` Spares follow the plan “${displayName(pol, { mode: 'short' })}”.` : ''}${out.length && hub.length ? ` Outstations: formula ${fmtPct(wavg(out, 'palm'))}, simulation ${fmtPct(wavg(out, 'sim'))}.` : ''}` : `Request-weighted${pol ? `, ${pol} floats` : ''}${out.length && hub.length ? ` · outstations ${fmtPct(wavg(out, 'palm'))} Palm vs ${fmtPct(wavg(out, 'sim'))} sim` : ''} · one dot per rotable × station, size = requests · ${meta.split || r.palm_vs_sim_split || 'selection'} seeds${meta.n_seeds ? ` (${meta.n_seeds})` : ''}`,
    provenance: 'SIMULATED', source: 'rotables.json → palm_vs_sim',
    table: { columns: [{ key: 'pn', label: 'PN' }, { key: 'station', label: 'Station' }, { key: 'palm', label: 'Palm A', num: true, format: (v) => fmtPct(v) }, { key: 'sim', label: 'Sim fill', num: true, format: (v) => fmtPct(v) }, { key: 'n', label: 'Requests', num: true, format: fmtInt }], rows },
  });
  return respIn(f.body, (w) => {
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
    dl(g, { x: iw, y: ih + 30, text: byMode('FORMULA ESTIMATE →', 'PALM AVAILABILITY →'), anchor: 'end', color: C.faint });
    dl(g, { x: 6, y: 6, text: byMode('SIMULATION ↑', 'SIMULATED FILL ↑'), color: C.faint });
    refLine(g, { x1: 0, y1: ih, x2: iw, y2: 0 });
    dl(g, { x: iw * 0.18 + 8, y: ih - ih * 0.18 + 6, text: byMode('same', 'sim = Palm'), color: C.faint, mono: true });
    const rr = d3().scaleSqrt().domain([0, d3().max(rows, (d) => d.n)]).range([2, 8]);
    const pts = g.append('g').selectAll('circle').data(rows.slice().sort((a, b) => a.hub - b.hub)).join('circle').attr('cx', (d) => x(d.palm)).attr('cy', (d) => y(d.sim)).attr('r', (d) => rr(d.n))
      .attr('fill', (d) => (d.hub ? SR.neutral : 'none')).attr('fill-opacity', (d) => (d.hub ? 0.6 : 0)).attr('stroke', (d) => (d.hub ? SR.neutral : SR.context)).attr('stroke-width', 1.25);
    withTooltip(pts, (d) => ({ title: `${d.pn} @ ${d.station}`, rows: [['Palm A', fmtPct(d.palm)], ['Sim fill', fmtPct(d.sim)], ['Gap', `${fmtNum((d.sim - d.palm) * 100, 1)} pts`], ['Requests', fmtInt(d.n)]] }));
    dl(g, { x: iw, y: ih - 28, text: '● Hub', anchor: 'end', color: C.text });
    dl(g, { x: iw, y: ih - 12, text: '○ Outstations', anchor: 'end', color: C.muted });
    if (gap) annotate(g, { x: x(gap.palm), y: y(gap.sim), dx: x(gap.palm) > iw * 0.5 ? -34 : 34, dy: y(gap.sim) > ih * 0.6 ? -30 : 30, title: `${gap.pn} @ ${gap.station}`, sub: S ? `formula ${fmtPct(gap.palm, 0)} → sim ${fmtPct(gap.sim, 0)}` : `Palm ${fmtPct(gap.palm, 0)} → sim ${fmtPct(gap.sim, 0)}` });
  });
}

function whyList(r) {
  const reasons = (r.palm_vs_sim && !Array.isArray(r.palm_vs_sim) && Array.isArray(r.palm_vs_sim.reasons)) ? r.palm_vs_sim.reasons : null;
  const items = reasons ? reasons.map((x) => [x.title || '', x.body || x]) : isSimple() ? [
    ['Shops have limited space.', 'The formula assumes a shop can fix any number of parts at once. Real shops queue work, so a busy shop stretches the wait.'],
    ['Some parts are scrapped.', 'Parts not worth fixing leave the loop. Buying new ones takes extra time, so the real wait is longer than the shop time.'],
    ['Parts travel between airports.', 'Broken parts fly to AUH before repair, and good parts fly back out. An outstation refilled from the hub does better than its own formula says.'],
    ['Demand comes in bursts.', 'Removals bunch up and repair times drift. The formula smooths all of this out.'],
  ] : [
    ['Finite shop capacity.', 'Palm assumes ample repair servers. Real benches queue work; the simulator models bench capacity, so a busy shop stretches the pipeline beyond λT.'],
    ['Condemnation.', 'Beyond-economic-repair units leave the loop and are replaced by purchase orders with their own lead time, so the effective pipeline time is longer than the shop TAT.'],
    ['Transport and multi-echelon competition.', 'Cores travel to AUH before induction, and hub returns also refill outstation floats. An outstation resupplied from the hub in days sees far more than its own Palm figure.'],
    ['Non-stationary demand.', 'Removals cluster (frailty on over-dispersed PNs) and TAT drifts; Palm’s steady-state Poisson pipeline smooths this out.'],
  ];
  return h('ul', { class: 'rr-reasons' }, items.map(([t, b]) => h('li', {}, icon('info'), h('div', {}, h('strong', {}, `${t} `), b))));
}
