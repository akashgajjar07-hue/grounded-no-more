/**
 * 08 · Planner Action Centre — screen agent D.
 * Data: actions.json (schemas.planner_exceptions + parsed evidence, DERIVED; QUARANTINE_DOCS rows SIMULATED)
 * Deep links: #/actions?id=EX-103-002  ·  filters: &severity=urgent&type=OVERDUE_REPAIR&station=BOM&owner=…
 * Shows: the weekly exception inbox with filters and counts, a "where the work is" chart, an evidence
 * drawer per exception (numbers behind it, a small chart where it helps, recommended action, owner, due
 * week) and a client-side CSV export of the current filtered list.
 */
import { h, pageHead, card, provChip, pill, drawer, icon, segmented } from '../ui.js';
import { chartFrame, responsive, svgIn, theme, fmtAED, fmtInt, fmtNum, fmtWeek, withTooltip, fmtEnum, plural } from '../charts/theme.js';

export const data = ['actions', 'parts'];

const SEV = ['urgent', 'review', 'info'];
const SEV_LABEL = { urgent: 'Urgent', review: 'Review', info: 'Info' };
const SEV_RANK = { urgent: 0, review: 1, info: 2 };
const TYPE_LABEL = {
  OVERDUE_REPAIR: 'Overdue repair',
  OUTSTATION_DEPLETION: 'Outstation depletion',
  EXCESS_DECLINING_DEMAND: 'Excess · declining demand',
  CONDEMNED_AWAITING_REPLACEMENT: 'Condemned · awaiting replacement',
  QUARANTINE_DOCS: 'Quarantine · documents',
  LEAD_TIME_DRIFT: 'Lead-time drift',
  EXPIRY_RISK: 'Shelf-life expiry risk',
  KIT_SHORTAGE: 'Kit shortage',
};
const TYPE_ICON = { OVERDUE_REPAIR: 'wrench', OUTSTATION_DEPLETION: 'map-pin', EXCESS_DECLINING_DEMAND: 'warehouse', CONDEMNED_AWAITING_REPLACEMENT: 'rotable', QUARANTINE_DOCS: 'shield', LEAD_TIME_DRIFT: 'chart', EXPIRY_RISK: 'clock', KIT_SHORTAGE: 'layers' };
const typeLabel = (t) => TYPE_LABEL[t] || String(t || '').toLowerCase().replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
const sevPill = (s) => pill(s === 'info' ? 'info' : s, SEV_LABEL[s] || s);
const NETWORK = 'Network';
const nOr = (v) => (v === null || v === undefined || Number.isNaN(+v) ? null : +v);
const wk1 = (v) => fmtNum(v, Number.isInteger(+v) ? 0 : 1);
/** Raw enum tokens inside exported prose → readable labels: "at EU_VENDOR" → "at EU vendor". */
export const tidyEnums = (t) => String(t ?? '').replace(/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g, (m) => fmtEnum(m))
  .replace(/(\d[\d,.]*)\s+([a-z]+)\(s\)/gi, (m, n, w) => `${n} ${+String(n).replace(/,/g, '') === 1 ? w : `${w}s`}`);
/**
 * Row text for the action column: the whole first sentence (never cut mid-sentence); the rest lives in the drawer.
 * Splits on ". " / "; " so "Chase the shop…; escalate, consider…" shows "Chase the shop for a committed release date".
 */
export function firstSentence(t) {
  const s = tidyEnums(t).trim();
  const m = s.match(/^(.+?)(?:[.;!?](?=\s|$))/);
  const head = m ? m[1].trim() : s;
  return { head, more: head.length < s.replace(/[.;!?]\s*$/, '').trim().length };
}

/** The scannable numbers of an exception (all optional; only depletion rows carry a target). */
export function rowMetrics(a) {
  const e = a.evidence || {};
  const onHand = nOr(e.on_hand), target = nOr(e.target);
  return {
    stock: onHand != null && target != null ? { have: onHand + (nOr(e.inbound) || 0), target } : null,
    aogH: nOr(e.aog_hours_lookback), d0: nOr(e.d0_requests_lookback), lookback: nOr(e.lookback_weeks),
  };
}
/** One short phrase for the "Issue" column: the type's key number, not the whole rationale. */
export function issueText(a) {
  const e = a.evidence || {};
  switch (a.type) {
    case 'OUTSTATION_DEPLETION': return 'Below station target';
    case 'OVERDUE_REPAIR': return e.weeks_overdue != null ? `${wk1(e.weeks_overdue)} wk overdue at shop` : 'Repair overdue';
    case 'LEAD_TIME_DRIFT': return e.ratio != null ? `Lead time ${fmtNum(e.ratio, 1)}× quote` : 'Lead-time drift';
    case 'EXCESS_DECLINING_DEMAND': return e.cover_weeks_at_recent_rate != null ? `${fmtInt(e.cover_weeks_at_recent_rate)} wk cover, demand falling` : 'Excess stock';
    case 'EXPIRY_RISK': return e.cover_weeks_at_recent_rate != null && e.shelf_life_weeks != null ? `${fmtInt(e.cover_weeks_at_recent_rate)} wk cover vs ${fmtInt(e.shelf_life_weeks)} wk life` : 'Shelf-life risk';
    case 'QUARANTINE_DOCS': return 'Certificate review';
    case 'CONDEMNED_AWAITING_REPLACEMENT': return e.quoted_due_week != null ? `Replacement due ${fmtWeek(e.quoted_due_week)}` : 'Awaiting replacement';
    default: return typeLabel(a.type);
  }
}
/** Short title for the drawer: "{pn} · {station}: 0 of 2 on hand". The long rationale stays in the drawer body. */
export function shortTitle(a) {
  const e = a.evidence || {};
  const stn = a.station || NETWORK;
  const m = rowMetrics(a);
  if (a.type === 'OUTSTATION_DEPLETION' && m.stock) return `${a.pn} · ${stn}: ${fmtInt(m.stock.have)} of ${fmtInt(m.stock.target)} on hand`;
  if (a.type === 'OVERDUE_REPAIR' && e.weeks_overdue != null) return `${a.pn} · repair ${wk1(e.weeks_overdue)} wk past quoted due`;
  return a.pn ? `${a.pn} · ${issueText(a)}` : a.summary;
}

function ensureCSS() {
  if (document.querySelector('link[data-view-css="planner-action-centre"]')) return;
  document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/planner-action-centre.css', import.meta.url).href, dataset: { viewCss: 'planner-action-centre' } }));
}

// ----------------------------------------------------------------------------- evidence formatting
const EV_LABEL = {
  on_hand: 'On hand (serviceable)', inbound: 'Inbound', p0_target: 'P0 station target', demand_implied_protection: 'Demand-implied protection level',
  target: 'Target used', target_basis: 'Target basis', d0_requests_lookback: 'D0 requests in lookback', lookback_weeks: 'Lookback', aog_events_lookback: 'AOG events in lookback',
  aog_hours_lookback: 'AOG hours in lookback', auh_on_hand: 'AUH on hand', aog_transport_h_from_auh: 'AOG transport from AUH', part_class: 'Part class',
  ro_id: 'Repair order', serial: 'Serial', shop: 'Shop', removed_week: 'Removed', shop_in_week: 'At shop', quoted_due_week: 'Quoted due', weeks_overdue: 'Weeks overdue',
  quoted_tat_d: 'Quoted TAT', network_serviceable: 'Network serviceable', deadline_class: 'Deadline class (hypothetical)',
  pos: 'Purchase orders', n_pos: 'POs in window', n_open_past_due: 'Open and past due', mean_lead_d: 'Mean realised lead time', mean_quoted_d: 'Mean quoted lead time', ratio: 'Ratio',
  master_quoted_lead_d: 'Master-data quoted lead', earlier_mean_lead_d: 'Earlier mean lead time', earlier_n: 'Earlier POs',
  usage_recent_26w: 'Usage, last 26 weeks', usage_prior_26w: 'Usage, previous 26 weeks', network_on_hand: 'Network on hand', cover_weeks_at_recent_rate: 'Cover at recent rate',
  quarterly_usage: 'Quarterly usage', unit_cost_aed: 'Unit cost', excess_value_aed: 'Excess value', shelf_life_weeks: 'Shelf life', expired_units_history: 'Units expired in history',
  po_id: 'Replacement PO', order_week: 'Ordered', po_overdue: 'PO overdue', value_aed: 'Unit value',
  txn_id: 'Receipt transaction', ref: 'Receipt reference', received_h: 'Received (sim hour)', received_week: 'Received', receipts_in_window: 'Receipts in window', rule: 'Rule', simulated: 'Simulated flag', provenance: 'Provenance',
  risk_score: 'Risk score', deadline: 'Deadline class (hypothetical)', stock_total: 'Stock total',
};
function fmtEv(k, v) {
  if (v === null || v === undefined || v === '') return 'not recorded';
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'number' ? fmtInt(x) : String(x))).join(' · ');
  if (typeof v === 'boolean') return v ? 'Yes' : 'No';
  if (typeof v === 'object') return Object.entries(v).map(([a, b]) => `${a} ${b}`).join(' · ');
  if (typeof v !== 'number') return /^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$/.test(String(v)) ? fmtEnum(v) : tidyEnums(v);
  if (/_aed$/.test(k)) return fmtAED(v);
  if (/(^|_)week$|_week$/.test(k)) return fmtWeek(v);
  if (/_weeks$|^weeks_/.test(k) || k === 'cover_weeks_at_recent_rate' || k === 'shelf_life_weeks' || k === 'lookback_weeks') return `${fmtNum(v, Number.isInteger(v) ? 0 : 1)} wk`;
  if (/_d$/.test(k)) return `${fmtNum(v, Number.isInteger(v) ? 0 : 1)} d`;
  if (/_h$|hours/.test(k)) return `${fmtNum(v, Number.isInteger(v) ? 0 : 1)} h`;
  if (k === 'ratio') return `${fmtNum(v, 2)}×`;
  if (k === 'risk_score') return fmtNum(v, 2);
  if (/_id$|^txn|^ro_id|^po_id/.test(k)) return String(v);
  return Number.isInteger(v) ? fmtInt(v) : fmtNum(v, 1);
}
const evLabel = (k) => EV_LABEL[k] || k.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

/** A small chart for the evidence, where one helps. Returns a node or null. */
function evidenceChart(a) {
  const e = a.evidence || {};
  const d3 = window.d3;
  const host = h('div', { class: 'pac-evchart' });
  if (Array.isArray(e.quarterly_usage) && e.quarterly_usage.length > 1) {
    const vals = e.quarterly_usage;
    const fr = chartFrame(host, {
      headline: `Usage fell from ${fmtInt(vals[0])} to ${fmtInt(vals.at(-1))} a quarter`,
      subtitle: 'Units issued per 13-week quarter · network · oldest → latest',
      provenance: 'DERIVED', source: 'actions.json',
      table: { columns: [{ key: 'q', label: 'Quarter' }, { key: 'v', label: 'Units', num: true, format: fmtInt }], rows: vals.map((v, i) => ({ q: `Q${i + 1}`, v })) },
    });
    responsive(fr.body, (w) => {
      const H = 120, m = { t: 18, r: 8, b: 20, l: 8 };
      const svg = svgIn(fr.body, w, H, 'Quarterly usage bars');
      const x = d3.scaleBand().domain(vals.map((_, i) => i)).range([m.l, w - m.r]).padding(0.28);
      const y = d3.scaleLinear().domain([0, d3.max(vals)]).range([H - m.b, m.t]);
      svg.selectAll('rect').data(vals).join('rect').attr('x', (_, i) => x(i)).attr('width', x.bandwidth()).attr('y', (v) => y(v)).attr('height', (v) => y(0) - y(v)).attr('rx', 2)
        .attr('fill', (_, i) => (i === vals.length - 1 ? theme.color.accent : theme.color.neutral));
      svg.selectAll('text.v').data(vals).join('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('text-anchor', 'middle').attr('x', (_, i) => x(i) + x.bandwidth() / 2).attr('y', (v) => y(v) - 5).text((v) => fmtInt(v));
      svg.selectAll('text.q').data(vals).join('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('text-anchor', 'middle').attr('x', (_, i) => x(i) + x.bandwidth() / 2).attr('y', H - 4).text((_, i) => `Q${i + 1}`);
    });
    return host;
  }
  if (e.mean_lead_d != null && e.mean_quoted_d != null) {
    const rows = [
      { k: 'Quoted (master data)', v: e.mean_quoted_d },
      e.earlier_mean_lead_d != null ? { k: `Earlier POs (${fmtInt(e.earlier_n)})`, v: e.earlier_mean_lead_d } : null,
      { k: `Recent POs (${fmtInt(e.n_pos)})`, v: e.mean_lead_d, hi: true },
    ].filter(Boolean);
    const fr = chartFrame(host, {
      headline: `Recent lead time is ${fmtNum(e.ratio, 2)}× the quoted ${fmtNum(e.mean_quoted_d, 0)} d`,
      subtitle: `Days from order to receipt · non-expedite POs · last ${fmtInt(e.lookback_weeks)} weeks`,
      provenance: 'DERIVED', source: 'actions.json',
      table: { columns: [{ key: 'k', label: 'Basis' }, { key: 'v', label: 'Days', num: true, format: (v) => `${fmtNum(v, 1)} d` }], rows },
    });
    hbars(fr.body, rows, (v) => `${fmtNum(v, 0)} d`);
    return host;
  }
  if (e.target != null && e.on_hand != null) {
    const rows = [{ k: 'On hand + inbound', v: (e.on_hand || 0) + (e.inbound || 0) }, { k: 'P0 station target', v: e.p0_target ?? 0 }, { k: 'Target used', v: e.target, hi: true }];
    const fr = chartFrame(host, {
      headline: `${a.station} holds ${fmtInt(rows[0].v)} against a target of ${fmtInt(e.target)}`,
      subtitle: `Serviceable units · ${a.pn} · target basis: ${e.target_basis || 'not recorded'}`,
      provenance: 'DERIVED', source: 'actions.json',
      table: { columns: [{ key: 'k', label: 'Measure' }, { key: 'v', label: 'Units', num: true, format: fmtInt }], rows },
    });
    hbars(fr.body, rows, fmtInt, Math.max(2, e.target));
    return host;
  }
  if (e.quoted_due_week != null && e.removed_week != null && e.weeks_overdue != null) {
    const asOf = a.week;
    const steps = [{ k: 'Removed', w: e.removed_week }, e.shop_in_week != null ? { k: 'At shop', w: e.shop_in_week } : null, { k: 'Quoted due', w: e.quoted_due_week }, { k: 'This week', w: asOf, hi: true }].filter(Boolean);
    const fr = chartFrame(host, {
      headline: `${fmtNum(e.weeks_overdue, 1)} weeks past the quoted due date`,
      subtitle: `Simulated weeks · ${e.ro_id != null ? `RO ${e.ro_id}` : e.po_id != null ? `PO ${e.po_id}` : 'order'} · ${e.shop ? fmtEnum(e.shop) : 'supplier'}`,
      provenance: 'DERIVED', source: 'actions.json',
      table: { columns: [{ key: 'k', label: 'Milestone' }, { key: 'w', label: 'Week', num: true, format: fmtWeek }], rows: steps },
    });
    responsive(fr.body, (w) => {
      const H = 76, m = { l: 12, r: 12 };
      const svg = svgIn(fr.body, w, H, 'Repair order timeline');
      const x = d3.scaleLinear().domain([d3.min(steps, (s) => s.w), d3.max(steps, (s) => s.w)]).range([m.l + 30, w - m.r - 30]);
      const yy = 34;
      svg.append('line').attr('x1', x(e.quoted_due_week)).attr('x2', x(asOf)).attr('y1', yy).attr('y2', yy).attr('stroke', theme.color.urgent).attr('stroke-width', 4).attr('stroke-opacity', 0.55);
      svg.append('line').attr('x1', x(steps[0].w)).attr('x2', x(e.quoted_due_week)).attr('y1', yy).attr('y2', yy).attr('stroke', theme.color.lineStrong).attr('stroke-width', 2);
      steps.forEach((s, i) => {
        svg.append('circle').attr('cx', x(s.w)).attr('cy', yy).attr('r', 4.5).attr('fill', theme.color.bg).attr('stroke', s.hi ? theme.color.text : theme.color.muted).attr('stroke-width', 1.5);
        svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('text-anchor', 'middle').attr('x', x(s.w)).attr('y', i % 2 ? yy + 26 : yy - 14).text(`${s.k} ${fmtWeek(s.w)}`);
      });
    });
    return host;
  }
  return null;
}
function hbars(el, rows, fmt, maxV) {
  const d3 = window.d3;
  responsive(el, (w) => {
    const rowH = 30, H = rows.length * rowH + 4, lw = Math.min(170, w * 0.42);
    const svg = svgIn(el, w, H, 'Comparison bars');
    const x = d3.scaleLinear().domain([0, Math.max(maxV || 0, d3.max(rows, (r) => r.v)) * 1.05]).range([0, Math.max(30, w - lw - 56)]);
    rows.forEach((r, i) => {
      const y = i * rowH + 6;
      svg.append('text').attr('class', r.hi ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', y + 10).text(r.k);
      svg.append('rect').attr('x', lw).attr('y', y + 2).attr('width', Math.max(1, x(r.v))).attr('height', 12).attr('rx', 2).attr('fill', r.hi ? theme.color.accent : theme.color.neutral);
      svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', lw + Math.max(1, x(r.v)) + 8).attr('y', y + 12).text(fmt(r.v));
    });
  });
}

// ----------------------------------------------------------------------------- CSV
const CSV_COLS = ['exception_id', 'week', 'type', 'severity', 'pn', 'station', 'summary', 'recommended_action', 'owner', 'due_week', 'evidence'];
function csvCell(v) {
  if (v === null || v === undefined) return '';
  const s = typeof v === 'object' ? JSON.stringify(v) : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
export function toCSV(rows) {
  return [CSV_COLS.join(','), ...rows.map((r) => CSV_COLS.map((c) => csvCell(r[c])).join(','))].join('\r\n') + '\r\n';
}

// ----------------------------------------------------------------------------- view
export async function render(el, ctx) {
  ensureCSS();
  const { actions: A, parts: PT } = ctx.data;
  // one AOG-hour metric per PN across screens: the exporter's worst-station 52-week total, with its label (as on Mission)
  const partBy = Object.fromEntries((PT?.parts || []).map((p) => [p.pn, p]));
  const aogMeta = PT?.aog_metric_labels?.aog_h_52w_max_station;
  const aogShort = (typeof aogMeta === 'object' && aogMeta?.short) || 'max AOG h at one station';
  const aogLabel = (typeof aogMeta === 'string' ? aogMeta : aogMeta?.label) || 'AOG h · last 52 wk · worst station';
  const all = (A.actions || []).slice().sort((a, b) => (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9) || (a.due_week ?? 0) - (b.due_week ?? 0) || String(a.exception_id).localeCompare(String(b.exception_id)));
  const asOf = A.as_of_week ?? (all.length ? Math.max(...all.map((a) => a.week ?? 0)) : null);
  const metaProv = A.meta?.provenance || A.provenance || 'DERIVED';
  const count = (pred) => all.filter(pred).length;
  const nSev = Object.fromEntries(SEV.map((s) => [s, count((a) => a.severity === s)]));
  const types = [...new Set(all.map((a) => a.type))].sort((a, b) => count((x) => x.type === b) - count((x) => x.type === a));
  const stationOf = (a) => a.station || NETWORK;
  const stations = [...new Set(all.map(stationOf))].sort((a, b) => (a === 'AUH' ? -1 : b === 'AUH' ? 1 : a === NETWORK ? 1 : b === NETWORK ? -1 : a.localeCompare(b)));
  const owners = [...new Set(all.map((a) => a.owner).filter(Boolean))].sort();

  const f = {
    severity: SEV.includes(ctx.params.severity) ? ctx.params.severity : 'all',
    type: types.includes(ctx.params.type) ? ctx.params.type : '',
    station: stations.includes(ctx.params.station) ? ctx.params.station : '',
    owner: owners.includes(ctx.params.owner) ? ctx.params.owner : '',
  };

  const topType = types[0];
  el.append(pageHead({
    num: '08', eyebrow: 'Planner Action Centre',
    title: asOf != null ? `${fmtWeek(asOf)}: ${fmtInt(all.length)} exceptions, ${fmtInt(nSev.urgent)} urgent` : `${fmtInt(all.length)} exceptions this week`,
    lede: 'The weekly exception inbox for Falcon Hub Airways (fictional). Each exception carries the numbers behind it, a recommended action, an owner and a due week. Recommendations support a planner; they do not replace engineering, quality or airworthiness judgement.',
    meta: [provChip(metaProv), h('span', { class: 'chip chip-mono' }, asOf != null ? `As of ${fmtWeek(asOf)}` : 'As-of week not exported')],
  }));

  // ---- summary row: severity counts + where-the-work-is chart
  // Ownership: who carries the work, as small stacked bars that also filter (no repeat of the severity counts).
  const ownerCounts = owners.map((o) => ({ o, n: count((a) => a.owner === o), ...Object.fromEntries(SEV.map((sv) => [sv, count((a) => a.owner === o && a.severity === sv)])) })).sort((a, b) => b.urgent - a.urgent || b.n - a.n);
  const maxOwner = Math.max(1, ...ownerCounts.map((r) => r.n));
  const ownerList = h('ul', { class: 'pac-ownlist list-reset' }, ownerCounts.map((r) => h('li', {}, h('button', {
    type: 'button', class: 'pac-own', dataset: { owner: r.o }, 'aria-pressed': 'false', 'aria-label': `${r.o}: ${r.n} open, ${r.urgent} urgent. Filter the inbox`,
    onclick: () => { f.owner = f.owner === r.o ? '' : r.o; sync(); },
  },
  h('span', { class: 'pac-own-name' }, r.o),
  h('span', { class: 'pac-own-n mono' }, `${fmtInt(r.n)}${r.urgent ? ` · ${fmtInt(r.urgent)} urgent` : ''}`),
  h('span', { class: 'pac-own-bar', 'aria-hidden': 'true' }, SEV.filter((sv) => r[sv]).map((sv) => h('i', { class: `pac-own-seg pac-own-seg--${sv}`, style: { width: `${(r[sv] / maxOwner) * 100}%` } })))))));
  const summaryCard = card({
    cls: 'span-4', kicker: 'This week', title: 'Who owns the work', prov: metaProv,
    body: h('div', { class: 'stack-3' }, ownerList,
      h('p', { class: 't-12 faint m-0' }, 'Click an owner to filter the inbox. Rules live in config/aog_lab.yaml; quarantine (documents) rows are a simulated workflow illustration, not document data.')),
  });
  const chartCard = h('section', { class: 'card span-8', dataset: { story: 'action-types' } });
  const byType = types.map((t) => ({ t, label: typeLabel(t), ...Object.fromEntries(SEV.map((s) => [s, count((a) => a.type === t && a.severity === s)])), n: count((a) => a.type === t) }));
  const top = byType[0];
  const frame = chartFrame(chartCard, {
    headline: top ? `${typeLabel(topType)} is the biggest queue: ${fmtInt(top.n)} of ${fmtInt(all.length)} exceptions, ${fmtInt(top.urgent)} urgent` : 'No exceptions this week',
    subtitle: `Open exceptions by type and severity · ${asOf != null ? fmtWeek(asOf) : 'week not exported'} · click a bar to filter`,
    provenance: metaProv, source: 'actions.json',
    table: { columns: [{ key: 'label', label: 'Type' }, ...SEV.map((s) => ({ key: s, label: SEV_LABEL[s], num: true })), { key: 'n', label: 'Total', num: true }], rows: byType },
  });
  frame.body.before(h('div', { class: 'pac-legend t-12', 'aria-hidden': 'true' }, SEV.filter((sv) => nSev[sv]).map((sv) => h('span', {}, h('i', { class: `pac-key pac-key--${sv}` }), `${SEV_LABEL[sv]} ${fmtInt(nSev[sv])}`))));
  const stopChart = responsive(frame.body, (w) => drawTypes(frame.body, w));
  function drawTypes(body, w) {
    const d3 = window.d3;
    const narrow = w < 520;
    const rowH = 30, lw = narrow ? 0 : Math.min(230, w * 0.34), top0 = narrow ? 0 : 4;
    const H = byType.length * (narrow ? rowH + 16 : rowH) + 8;
    const svg = svgIn(body, w, H, 'Exceptions by type and severity');
    const bw = Math.max(40, w - lw - 120);
    const x = d3.scaleLinear().domain([0, d3.max(byType, (r) => r.n) || 1]).range([0, bw]);
    const fill = { urgent: theme.series.urgent, review: theme.series.review, info: theme.color.neutral };
    byType.forEach((r, i) => {
      const y = top0 + i * (narrow ? rowH + 16 : rowH);
      const g = svg.append('g').attr('transform', `translate(0,${y})`).style('cursor', 'pointer').attr('tabindex', 0).attr('role', 'button').attr('aria-label', `${r.label}: ${r.n} exceptions; filter`)
        .on('click', () => { f.type = f.type === r.t ? '' : r.t; sync(); })
        .on('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); f.type = f.type === r.t ? '' : r.t; sync(); } });
      const by = narrow ? 18 : 6;
      g.append('text').attr('class', f.type === r.t ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', narrow ? 10 : by + 9).text(r.label);
      let x0 = lw;
      SEV.forEach((s) => {
        if (!r[s]) return;
        const seg = g.append('rect').attr('x', x0).attr('y', by).attr('width', Math.max(1, x(r[s]) - 1)).attr('height', 12).attr('rx', 2).attr('fill', fill[s]).attr('fill-opacity', f.type && f.type !== r.t ? 0.35 : 0.9);
        withTooltip(seg, () => ({ title: r.label, rows: [[SEV_LABEL[s], fmtInt(r[s])], ['Total', fmtInt(r.n)]] }));
        x0 += x(r[s]);
      });
      g.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', x0 + 8).attr('y', by + 10).text(`${fmtInt(r.n)}${r.urgent ? ` · ${fmtInt(r.urgent)} urgent` : ''}`);
    });
  }
  el.append(h('div', { class: 'grid-12' }, chartCard, summaryCard));

  // ---- filters
  const sel = (label, key, options, fmt = (v) => v) => {
    const id = `pac-${key}`;
    const s = h('select', { class: 'input pac-select', id, onchange: (e) => { f[key] = e.target.value; sync(); } }, h('option', { value: '' }, `All ${label.toLowerCase()}s`), options.map((o) => h('option', { value: o }, fmt(o))));
    return h('label', { class: 'pac-filter', for: id }, h('span', { class: 'field-label' }, label), s);
  };
  const sevSeg = h('div', { class: 'pac-filter' }, h('span', { class: 'field-label' }, 'Severity'), h('div', { class: 'pac-sevseg' }));
  const typeSel = sel('Type', 'type', types, typeLabel);
  const stationSel = sel('Station', 'station', stations);
  const ownerSel = sel('Owner', 'owner', owners);
  const shown = h('span', { class: 'pac-shown mono t-12', 'aria-live': 'polite' });
  const resetBtn = h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: () => { Object.assign(f, { severity: 'all', type: '', station: '', owner: '' }); sync(); } }, icon('close'), 'Clear filters');
  const csvBtn = h('button', { type: 'button', class: 'btn btn--sm', dataset: { action: 'export-csv' }, onclick: () => exportCSV() }, icon('download'), 'Export CSV');
  const list = h('ul', { class: 'pac-list list-reset', role: 'list', 'aria-label': 'Exceptions, grouped by part number' });
  const gridHead = h('div', { class: 'pac-grid pac-grid-head', 'aria-hidden': 'true' },
    h('span', {}, 'Severity'), h('span', {}, 'Part · station'), h('span', {}, 'Issue'), h('span', { class: 'is-num', title: 'Serviceable + inbound vs station target' }, 'On hand'), h('span', { class: 'is-num', title: 'AOG hours in the last 52 weeks' }, 'AOG h'), h('span', { class: 'is-num', title: 'D0 requests in the last 52 weeks' }, 'D0 req'), h('span', {}, 'Recommended action'), h('span', { class: 'is-num' }, 'Due'));
  const PAGE = 12;
  const GROUP_PEEK = 3;
  const openGroups = new Set();
  let expanded = false;
  const moreBtn = h('button', { type: 'button', class: 'btn btn--sm pac-more', dataset: { action: 'show-all' }, onclick: () => { expanded = !expanded; sync(); } });
  const inbox = card({
    cls: 'mt-3', kicker: 'Exception inbox', title: 'Ranked by severity, then due week · grouped by part', prov: metaProv, story: 'action-inbox',
    actions: csvBtn,
    body: h('div', { class: 'stack-3' }, h('div', { class: 'pac-filters' }, sevSeg, typeSel, stationSel, ownerSel), h('div', { class: 'row-between pac-shownrow' }, shown, resetBtn), h('div', { class: 'pac-table' }, gridHead, list), moreBtn,
      h('p', { class: 't-12 faint m-0' }, 'On hand = serviceable + inbound vs the station target. AOG h and D0 requests count the last 52 weeks (depletion rules only; — = not applicable). Open a row for the full rationale and evidence.')),
  });
  inbox.dataset.story = 'action-inbox';
  el.append(inbox);

  const current = () => all.filter((a) => (f.severity === 'all' || a.severity === f.severity) && (!f.type || a.type === f.type) && (!f.station || stationOf(a) === f.station) && (!f.owner || a.owner === f.owner));

  function exportCSV() {
    const rows = current();
    const blob = new Blob([toCSV(rows)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const parts = [asOf != null ? `W${asOf}` : 'week', f.severity !== 'all' ? f.severity : '', f.type ? f.type.toLowerCase() : '', f.station ? f.station.toLowerCase() : ''].filter(Boolean);
    const a = h('a', { href: url, download: `planner-exceptions-${parts.join('-')}.csv`, style: { display: 'none' } });
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
  }

  const num = (v, fmt = fmtInt) => (v == null ? h('span', { class: 'pac-na', title: 'Not applicable to this exception type' }, '—') : fmt(v));
  function row(a, { inGroup = false } = {}) {
    const prov = a.evidence?.provenance === 'SIMULATED' || a.evidence?.simulated ? 'SIMULATED' : null;
    const m = rowMetrics(a);
    const stn = stationOf(a);
    return h('li', { class: 'pac-li' },
      h('button', { type: 'button', class: `pac-row pac-grid pac-row--${a.severity}${inGroup ? ' is-grouped' : ''}`, dataset: { id: a.exception_id, sev: a.severity }, 'aria-label': `${SEV_LABEL[a.severity] || a.severity}: ${shortTitle(a)}. ${tidyEnums(a.recommended_action || '')}. Due ${a.due_week != null ? fmtWeek(a.due_week) : 'not set'}. Open evidence.`, onclick: () => open(a) },
        h('span', { class: 'pac-c-sev' }, sevPill(a.severity)),
        h('span', { class: 'pac-c-part mono' }, inGroup ? h('span', { class: 'pac-stn' }, h('span', { class: 'faint' }, '↳ '), stn) : h('span', {}, h('b', {}, a.pn || '—'), h('span', { class: 'faint' }, ' · '), stn)),
        h('span', { class: 'pac-c-issue', title: typeLabel(a.type) }, icon(a.type_icon || TYPE_ICON[a.type] || 'info'), h('span', { class: 'pac-c-issue-t' }, issueText(a)), prov ? provChip(prov) : null),
        h('span', { class: 'pac-c-stock is-num mono', dataset: { k: 'On hand' } }, m.stock ? h('span', { class: m.stock.have < m.stock.target ? 'pac-short' : '' }, `${fmtInt(m.stock.have)} / ${fmtInt(m.stock.target)}`) : num(null)),
        h('span', { class: 'pac-c-aog is-num mono', dataset: { k: 'AOG h' } }, num(m.aogH)),
        h('span', { class: 'pac-c-d0 is-num mono', dataset: { k: 'D0' } }, num(m.d0)),
        (() => { const fs = firstSentence(a.recommended_action || ''); return h('span', { class: 'pac-c-action', title: tidyEnums(a.recommended_action || '') }, a.recommended_action ? `${fs.head}${fs.more ? '\u00a0…' : ''}` : 'No action recorded'); })(),
        h('span', { class: 'pac-c-due is-num mono' }, a.due_week != null ? fmtWeek(a.due_week) : '—', icon('chevron-right'))));
  }
  /** Same-PN exceptions collapse under one header ("GN-… · 6 stations · 63 AOG h max"); singletons stay plain rows. */
  function groupsOf(rows) {
    const map = new Map();
    rows.forEach((a) => { const k = a.pn || a.exception_id; if (!map.has(k)) map.set(k, []); map.get(k).push(a); });
    const gs = [...map.entries()].map(([pn, rs]) => { const pv = nOr(partBy[pn]?.aog_h_52w_max_station); return { pn, rows: rs, sev: Math.min(...rs.map((a) => SEV_RANK[a.severity] ?? 9)), aog: pv ?? Math.max(0, ...rs.map((a) => rowMetrics(a).aogH || 0)), first: rows.indexOf(rs[0]) }; });
    return gs.sort((a, b) => a.sev - b.sev || a.first - b.first);
  }
  const peek = (g) => (openGroups.has(g.pn) ? g.rows.length : Math.min(g.rows.length, GROUP_PEEK));
  function groupBlock(g) {
    if (g.rows.length === 1) return row(g.rows[0]);
    const isOpen = openGroups.has(g.pn);
    const nU = g.rows.filter((a) => a.severity === 'urgent').length;
    const stations = new Set(g.rows.map(stationOf));
    const sevKey = SEV[g.sev] || 'info';
    const toggle = h('button', { type: 'button', class: 'pac-gtoggle btn btn--ghost btn--sm', 'aria-expanded': String(isOpen), dataset: { action: 'group-toggle', pn: g.pn }, onclick: () => { if (isOpen) openGroups.delete(g.pn); else openGroups.add(g.pn); sync(); } },
      icon(isOpen ? 'arrow-up' : 'arrow-down'), isOpen ? 'Show fewer' : `Show ${fmtInt(g.rows.length - GROUP_PEEK)} more`);
    return h('li', { class: `pac-group pac-group--${sevKey}`, dataset: { pn: g.pn } },
      h('div', { class: 'pac-ghead' },
        h('span', { class: 'pac-ghead-pn mono' }, g.pn),
        h('span', { class: 'pac-ghead-meta' }, `${fmtInt(g.rows.length)} exceptions · ${fmtInt(stations.size)} ${stations.size === 1 ? 'station' : 'stations'}${nU ? ` · ${fmtInt(nU)} urgent` : ''}`, g.aog ? h('span', { class: 'pac-nw', title: `${aogLabel} (${aogShort})` }, ` · max ${fmtInt(g.aog)} AOG h at one station`) : null),
        g.rows.length > GROUP_PEEK ? toggle : null),
      h('ul', { class: 'list-reset pac-grows' }, g.rows.map((a, i) => { const li = row(a, { inGroup: true }); if (i >= GROUP_PEEK && !isOpen) li.hidden = true; return li; })));
  }

  let activeDrawer = null;
  let alive = true;
  function open(a) {
    ctx.setParams({ id: a.exception_id });
    const e = a.evidence || {};
    const prov = e.provenance === 'SIMULATED' || e.simulated ? 'SIMULATED' : metaProv;
    const evRows = Object.entries(e).filter(([k]) => !['provenance', 'simulated'].includes(k));
    const chart = evidenceChart(a);
    activeDrawer?.close();
    activeDrawer = drawer({
      kicker: `${a.exception_id} · ${typeLabel(a.type)}`, title: shortTitle(a),
      onClose: () => { if (alive) ctx.setParams({ id: '' }); activeDrawer = null; },
      body: h('div', { class: 'stack-3 pac-drawer' },
        h('div', { class: 'row-wrap' }, sevPill(a.severity), h('span', { class: 'chip chip-mono' }, typeLabel(a.type)), provChip(prov)),
        h('div', { class: 'pac-why' }, h('div', { class: 'card-kicker mb-1' }, 'Why it was raised'), h('p', { class: 'm-0' }, tidyEnums(a.summary))),
        h('div', { class: 'pac-action' }, h('div', { class: 'card-kicker' }, 'Recommended action'), h('p', { class: 'm-0' }, a.recommended_action ? tidyEnums(a.recommended_action) : 'No action recorded'),
          h('dl', { class: 'meta-list mt-2' }, ...[['Owner', a.owner || 'not set'], ['Due', a.due_week != null ? fmtWeek(a.due_week) : 'not set'], ['Raised', a.week != null ? fmtWeek(a.week) : 'not recorded'], ['Part', a.pn || '—'], ['Station', stationOf(a)]].flatMap(([k, v]) => [h('dt', {}, k), h('dd', { class: k === 'Part' || k === 'Station' ? 'mono' : '' }, v)]))),
        chart,
        h('div', {}, h('div', { class: 'card-kicker mb-1' }, 'Evidence · the numbers behind it'),
          h('table', { class: 'data-table data-table--dense pac-evtable' }, h('caption', { class: 'sr-only' }, 'Evidence'), h('tbody', {}, evRows.map(([k, v]) => h('tr', {}, h('th', { scope: 'row' }, evLabel(k)), h('td', { class: 'is-num mono' }, fmtEv(k, v))))))),
        prov === 'SIMULATED' ? h('p', { class: 't-12 faint m-0' }, 'This exception comes from a seeded random flag, not from document data. It illustrates the quarantine workflow only.') : null,
        h('p', { class: 't-12 faint m-0' }, 'Deadline classes D0/D3/D10 are hypothetical simulation classes, not MEL categories. A planner confirms before acting.')),
      foot: h('a', { class: 'btn btn--sm btn--ghost', href: ctx.buildHash('actions', { id: a.exception_id }) }, icon('chevron-right'), 'Deep link'),
    }).open();
  }

  function sync() {
    const rows = current();
    sevSeg.querySelector('.pac-sevseg').replaceChildren(segmented({
      label: 'Severity', value: f.severity,
      options: [{ value: 'all', label: `All ${fmtInt(all.length)}` }, ...SEV.map((s) => ({ value: s, label: `${SEV_LABEL[s]} ${fmtInt(nSev[s])}` }))],
      onChange: (v) => { f.severity = v; sync(); },
    }));
    typeSel.querySelector('select').value = f.type;
    stationSel.querySelector('select').value = f.station;
    ownerSel.querySelector('select').value = f.owner;
    ownerList.querySelectorAll('.pac-own').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.owner === f.owner)));
    const nU = rows.filter((a) => a.severity === 'urgent').length;
    shown.replaceChildren(h('span', { class: 'pac-nw' }, `Showing ${fmtInt(rows.length)} of ${fmtInt(all.length)}`), ' · ', h('span', { class: 'pac-nw' }, `${fmtInt(nU)} urgent`));
    resetBtn.disabled = f.severity === 'all' && !f.type && !f.station && !f.owner;
    // Page by whole groups: show groups until about PAGE visible rows, then "Show all".
    const gs = groupsOf(rows);
    let collapsedN = 0, vis = 0;
    for (const g of gs) { if (vis >= PAGE) break; vis += peek(g); collapsedN++; }
    const shownN = expanded ? gs.length : collapsedN;
    const hiddenRows = gs.slice(collapsedN).reduce((n, g) => n + g.rows.length, 0);
    list.replaceChildren(...(rows.length ? gs.slice(0, shownN).map(groupBlock) : [h('li', { class: 'state' }, icon('info'), h('p', {}, 'No exceptions match these filters.'))]));
    gridHead.hidden = !rows.length;
    moreBtn.hidden = hiddenRows === 0;
    moreBtn.replaceChildren(icon(expanded ? 'arrow-up' : 'arrow-down'), expanded ? 'Show the top of the list only' : `Show all ${fmtInt(rows.length)} exceptions (${fmtInt(hiddenRows)} more across ${fmtInt(gs.length - collapsedN)} parts)`);
    ctx.setParams({ severity: f.severity === 'all' ? '' : f.severity, type: f.type, station: f.station, owner: f.owner });
    drawTypes(frame.body, Math.floor(frame.body.clientWidth) || 600);
  }
  sync();

  const deep = all.find((a) => a.exception_id === ctx.params.id);
  if (deep) {
    if (deep.pn) openGroups.add(deep.pn);
    sync();
    if (!list.querySelector(`.pac-row[data-id="${deep.exception_id}"]`)) { expanded = true; sync(); }
    open(deep);
  }
  return () => { alive = false; stopChart(); activeDrawer?.close(); };
}
