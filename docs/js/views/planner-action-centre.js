/**
 * 08 · Planner Action Centre — screen agent D.
 * Data: actions.json (schemas.planner_exceptions + parsed evidence, DERIVED; QUARANTINE_DOCS rows SIMULATED)
 * Deep links: #/actions?id=EX-103-002  ·  filters: &severity=urgent&type=OVERDUE_REPAIR&station=BOM&owner=…
 * Shows: the weekly exception inbox with filters and counts, a "where the work is" chart, an evidence
 * drawer per exception (numbers behind it, a small chart where it helps, recommended action, owner, due
 * week) and a client-side CSV export of the current filtered list.
 */
import { h, pageHead, card, provChip, pill, drawer, icon, segmented } from '../ui.js';
import { chartFrame, responsive, svgIn, theme, fmtAED, fmtInt, fmtNum, fmtWeek, withTooltip } from '../charts/theme.js';

export const data = ['actions'];

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
  if (typeof v !== 'number') return String(v);
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
      subtitle: `Simulated weeks · RO ${e.ro_id ?? e.po_id ?? ''} · ${e.shop || 'supplier'}`,
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
  const { actions: A } = ctx.data;
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
    title: asOf != null ? `Week ${asOf}: ${fmtInt(all.length)} exceptions, ${fmtInt(nSev.urgent)} urgent` : `${fmtInt(all.length)} exceptions this week`,
    lede: 'The weekly exception inbox for Falcon Hub Airways (fictional). Each exception carries the numbers behind it, a recommended action, an owner and a due week. Recommendations support a planner; they do not replace engineering, quality or airworthiness judgement.',
    meta: [provChip(metaProv), h('span', { class: 'chip chip-mono' }, asOf != null ? `As of ${fmtWeek(asOf)}` : 'As-of week not exported')],
  }));

  // ---- summary row: severity counts + where-the-work-is chart
  const sevTiles = h('div', { class: 'pac-sevtiles' }, SEV.map((s) => h('button', {
    type: 'button', class: 'pac-sevtile', dataset: { sev: s }, 'aria-label': `Show ${SEV_LABEL[s].toLowerCase()} exceptions (${nSev[s]})`,
    onclick: () => { f.severity = f.severity === s ? 'all' : s; sync(); },
  }, h('span', { class: 'pac-sevtile-n num' }, fmtInt(nSev[s])), sevPill(s))));
  const ownerCounts = owners.map((o) => ({ o, n: count((a) => a.owner === o), u: count((a) => a.owner === o && a.severity === 'urgent') })).sort((a, b) => b.n - a.n);
  const summaryCard = card({
    cls: 'span-4', kicker: 'This week', title: 'Severity and ownership', prov: metaProv,
    body: h('div', { class: 'stack-3' }, sevTiles,
      h('dl', { class: 'meta-list pac-owners' }, ownerCounts.flatMap((r) => [h('dt', {}, r.o), h('dd', { class: 'num' }, `${fmtInt(r.n)} open · ${fmtInt(r.u)} urgent`)])),
      h('p', { class: 't-12 faint' }, 'Severity is shown as icon + text. Rules live in config/aog_lab.yaml; QUARANTINE_DOCS rows are a SIMULATED workflow illustration, not document data.')),
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
  const stopChart = responsive(frame.body, (w) => drawTypes(frame.body, w));
  function drawTypes(body, w) {
    const d3 = window.d3;
    const narrow = w < 520;
    const rowH = 30, lw = narrow ? 0 : Math.min(230, w * 0.34), top0 = narrow ? 0 : 4;
    const H = byType.length * (narrow ? rowH + 16 : rowH) + 8;
    const svg = svgIn(body, w, H, 'Exceptions by type and severity');
    const bw = Math.max(40, w - lw - 120);
    const x = d3.scaleLinear().domain([0, d3.max(byType, (r) => r.n) || 1]).range([0, bw]);
    const fill = { urgent: theme.color.urgent, review: theme.color.review, info: theme.color.neutral };
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
  const list = h('ul', { class: 'pac-list list-reset', role: 'list', 'aria-label': 'Exceptions' });
  const PAGE = 12;
  let expanded = false;
  const moreBtn = h('button', { type: 'button', class: 'btn btn--sm pac-more', dataset: { action: 'show-all' }, onclick: () => { expanded = !expanded; sync(); } });
  const inbox = card({
    cls: 'mt-3', kicker: 'Exception inbox', title: 'Ranked by severity, then due week', prov: metaProv, story: 'action-inbox',
    actions: csvBtn,
    body: h('div', { class: 'stack-3' }, h('div', { class: 'pac-filters' }, sevSeg, typeSel, stationSel, ownerSel), h('div', { class: 'row-between pac-shownrow' }, shown, resetBtn), list, moreBtn),
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

  function row(a) {
    const prov = a.evidence?.provenance === 'SIMULATED' || a.evidence?.simulated ? 'SIMULATED' : null;
    return h('li', {},
      h('button', { type: 'button', class: `pac-row pac-row--${a.severity}`, dataset: { id: a.exception_id }, 'aria-label': `${SEV_LABEL[a.severity] || a.severity}: ${a.summary}. Open evidence.`, onclick: () => open(a) },
        h('span', { class: 'pac-row-sev' }, sevPill(a.severity)),
        h('span', { class: 'pac-row-type', title: typeLabel(a.type) }, icon(a.type_icon || TYPE_ICON[a.type] || 'info')),
        h('span', { class: 'pac-row-main' },
          h('span', { class: 'pac-row-title' }, a.summary),
          h('span', { class: 'pac-row-meta' }, h('span', { class: 'mono' }, a.exception_id), h('span', {}, typeLabel(a.type)), a.pn ? h('span', { class: 'mono' }, a.pn) : null, h('span', { class: 'mono' }, stationOf(a)), h('span', {}, a.owner || 'Owner not set'), prov ? provChip(prov) : null)),
        h('span', { class: 'pac-row-due mono' }, h('span', { class: 'faint' }, 'Due '), a.due_week != null ? fmtWeek(a.due_week) : '—', icon('chevron-right'))));
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
      kicker: `${a.exception_id} · ${typeLabel(a.type)}`, title: a.summary,
      onClose: () => { if (alive) ctx.setParams({ id: '' }); activeDrawer = null; },
      body: h('div', { class: 'stack-3 pac-drawer' },
        h('div', { class: 'row-wrap' }, sevPill(a.severity), h('span', { class: 'chip chip-mono' }, a.type), provChip(prov)),
        h('div', { class: 'pac-action' }, h('div', { class: 'card-kicker' }, 'Recommended action'), h('p', { class: 'm-0' }, a.recommended_action || 'No action recorded'),
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
    sevTiles.querySelectorAll('.pac-sevtile').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.sev === f.severity)));
    const nU = rows.filter((a) => a.severity === 'urgent').length;
    shown.textContent = `Showing ${fmtInt(rows.length)} of ${fmtInt(all.length)} · ${fmtInt(nU)} urgent`;
    resetBtn.disabled = f.severity === 'all' && !f.type && !f.station && !f.owner;
    const lim = expanded ? rows.length : PAGE;
    list.replaceChildren(...(rows.length ? rows.slice(0, lim).map(row) : [h('li', { class: 'state' }, icon('info'), h('p', {}, 'No exceptions match these filters.'))]));
    moreBtn.hidden = rows.length <= PAGE;
    moreBtn.replaceChildren(icon(expanded ? 'arrow-up' : 'arrow-down'), expanded ? `Show the first ${PAGE} only` : `Show all ${fmtInt(rows.length)} exceptions (${fmtInt(rows.length - PAGE)} more)`);
    ctx.setParams({ severity: f.severity === 'all' ? '' : f.severity, type: f.type, station: f.station, owner: f.owner });
    drawTypes(frame.body, Math.floor(frame.body.clientWidth) || 600);
  }
  sync();

  const deep = all.find((a) => a.exception_id === ctx.params.id);
  if (deep) { if (current().indexOf(deep) >= PAGE) { expanded = true; sync(); } open(deep); }
  return () => { alive = false; stopChart(); activeDrawer?.close(); };
}
