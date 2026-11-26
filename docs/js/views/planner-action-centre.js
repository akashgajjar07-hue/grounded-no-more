/**
 * 08 · Planner Action Centre — screen agent D.
 * Data: actions.json (schemas.planner_exceptions + parsed evidence, DERIVED; QUARANTINE_DOCS rows SIMULATED)
 * Deep links: #/actions?id=EX-103-002  ·  filters: &severity=urgent&type=OVERDUE_REPAIR&station=BOM&owner=…
 * Shows: the weekly exception inbox with filters and counts, a "where the work is" chart, an evidence
 * drawer per exception (numbers behind it, a small chart where it helps, recommended action, owner, due
 * week) and a client-side CSV export of the current filtered list.
 */
import { h, pageHead, card, provChip, pill, drawer, icon, segmented, intro3, scopeLine } from '../ui.js';
import { chartFrame, responsive, svgIn, theme, fmtAED, fmtHours, fmtInt, fmtNum, fmtWeek, withTooltip, fmtEnum, plural } from '../charts/theme.js';
import { isSimple, byMode } from '../lib/mode.js';
import { tx as txSel } from '../lib/motion.js';
import { displayName, replaceCodes } from '../lib/names.js';
import { term, termText } from '../lib/glossary.js';

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

// ----------------------------------------------------------------------------- v2.1 Simple mode (plain English)
/** Plain-English names for the exception types (Simple mode). The CSV keeps the expert labels. */
export const SIMPLE_TYPE = {
  OUTSTATION_DEPLETION: 'Station short of a spare',
  OVERDUE_REPAIR: 'Repair is late',
  CONDEMNED_AWAITING_REPLACEMENT: 'Scrapped part, new one not here yet',
  EXCESS_DECLINING_DEMAND: 'Too much stock, use falling',
  EXPIRY_RISK: 'Stock may expire before it is used',
  DONOR_NOT_REINSTATED: 'Borrowed part not yet given back',
  LEAD_TIME_DRIFT: 'Supplier slower than promised',
  OPEN_REQUIREMENT: 'A plane is still waiting for a part',
  QUARANTINE_DOCS: 'Paperwork check needed',
  KIT_SHORTAGE: 'Kit is missing parts',
};
/** Why each type is raised, in one or two short sentences. */
const SIMPLE_WHY = {
  OUTSTATION_DEPLETION: 'This station holds fewer spares than its demand needs.',
  OVERDUE_REPAIR: 'The repair shop has kept this part past the promised date.',
  CONDEMNED_AWAITING_REPLACEMENT: 'A broken part could not be fixed and was scrapped. The order for a new one is still open.',
  EXCESS_DECLINING_DEMAND: 'Use has dropped, but we still hold a lot of stock.',
  EXPIRY_RISK: 'At today’s use, the stock will last longer than its shelf life.',
  DONOR_NOT_REINSTATED: 'We took this part from another of our planes. That plane is still without it.',
  LEAD_TIME_DRIFT: 'Recent orders took much longer to arrive than the supplier said.',
  OPEN_REQUIREMENT: 'A plane asked for this part and is still waiting.',
  QUARANTINE_DOCS: 'A part arrived and its papers need a check before use.',
  KIT_SHORTAGE: 'A kit of parts is not complete.',
};
export const labelFor = (t) => (isSimple() ? SIMPLE_TYPE[t] || typeLabel(t) : typeLabel(t));
const plur = (n, w) => `${fmtInt(n)} ${+n === 1 ? w : `${w}s`}`;
/** What to do, in plain words (Simple mode). Built from the exception's own fields; falls back to the expert text. */
export function simpleAction(a) {
  const e = a.evidence || {};
  switch (a.type) {
    case 'OUTSTATION_DEPLETION': return a.quantity != null && a.destination ? `Send ${plur(a.quantity, 'spare')} from ${a.source || 'the hub'} to ${a.destination}.` : 'Send a spare to this station.';
    case 'OVERDUE_REPAIR': return 'Ask the shop for a firm return date. If spares run low, borrow or swap a unit.';
    case 'CONDEMNED_AWAITING_REPLACEMENT': return 'Confirm the delivery date with the supplier. Line up a loan in case a plane needs one.';
    case 'EXCESS_DECLINING_DEMAND': return 'Lower the reorder levels, stop open orders and move spare stock to where it is used.';
    case 'EXPIRY_RISK': return 'Order smaller amounts. Move stock to where it is used before it expires.';
    case 'DONOR_NOT_REINSTATED': return 'Give the part back from the next good unit at the hub. Keep the approval record open.';
    case 'LEAD_TIME_DRIFT': return e.mean_lead_d != null && e.mean_quoted_d != null ? `Plan for about ${fmtInt(e.mean_lead_d)} days, not ${fmtInt(e.mean_quoted_d)}. Ask the supplier when it will recover.` : 'Plan for the longer delivery time. Ask the supplier when it will recover.';
    case 'OPEN_REQUIREMENT': return 'Keep every way to get the part open: borrow, swap or buy locally. Speed up the unit on its way.';
    case 'QUARANTINE_DOCS': return 'Check the papers before the part is used.';
    default: return tidyEnums(a.recommended_action || 'No action recorded');
  }
}
/** The key numbers, in plain words (Simple mode). */
export function simpleEvidence(a) {
  const e = a.evidence || {};
  const m = rowMetrics(a);
  const stn = a.station || 'The network';
  switch (a.type) {
    case 'OUTSTATION_DEPLETION': {
      const have = m.stock ? `${stn} has ${fmtInt(m.stock.have)} of the ${fmtInt(m.stock.target)} it needs.` : `${stn} is below its target.`;
      return m.aogH ? `${have} Planes there waited ${fmtInt(m.aogH)} hours for this part in the last ${fmtInt(m.lookback || 52)} weeks.` : have;
    }
    case 'OVERDUE_REPAIR': return e.weeks_overdue != null ? `The part is ${wk1(e.weeks_overdue)} weeks past the date the shop promised.` : 'The repair is past its promised date.';
    case 'CONDEMNED_AWAITING_REPLACEMENT': return e.quoted_due_week != null ? `The new part was due in ${fmtWeek(e.quoted_due_week)}.${e.network_serviceable != null ? ` The network has ${plur(e.network_serviceable, 'good spare')}.` : ''}` : 'The new part has not arrived.';
    case 'EXCESS_DECLINING_DEMAND': return e.cover_weeks_at_recent_rate != null ? `Use is down. We hold about ${fmtInt(e.cover_weeks_at_recent_rate)} weeks of stock.` : 'Use is down and stock is high.';
    case 'EXPIRY_RISK': return e.cover_weeks_at_recent_rate != null && e.shelf_life_weeks != null ? `We hold about ${fmtInt(e.cover_weeks_at_recent_rate)} weeks of stock. It expires after ${fmtInt(e.shelf_life_weeks)} weeks.` : 'Stock may expire before it is used.';
    case 'LEAD_TIME_DRIFT': return e.mean_lead_d != null && e.mean_quoted_d != null ? `Recent orders took ${fmtInt(e.mean_lead_d)} days. The supplier quoted ${fmtInt(e.mean_quoted_d)} days.` : 'Recent orders arrived late.';
    case 'DONOR_NOT_REINSTATED': return e.days_waiting != null ? `The other plane has waited ${fmtNum(e.days_waiting, 0)} days for the part to come back.` : 'The other plane is still waiting.';
    case 'OPEN_REQUIREMENT': return 'The request is still open at the end of the week.';
    default: return tidyEnums(a.summary || '');
  }
}
/** Short issue phrase for the row (Simple mode). */
function simpleIssue(a) {
  const e = a.evidence || {};
  switch (a.type) {
    case 'OUTSTATION_DEPLETION': return 'Short of spares';
    case 'OVERDUE_REPAIR': return e.weeks_overdue != null ? `${wk1(e.weeks_overdue)} wk late at the shop` : 'Repair is late';
    case 'LEAD_TIME_DRIFT': return e.ratio != null ? `Supplier ${fmtNum(e.ratio, 1)}× slower` : 'Supplier is slow';
    case 'EXCESS_DECLINING_DEMAND': return e.cover_weeks_at_recent_rate != null ? `${fmtInt(e.cover_weeks_at_recent_rate)} wk of stock, use falling` : 'Too much stock';
    case 'EXPIRY_RISK': return e.cover_weeks_at_recent_rate != null && e.shelf_life_weeks != null ? `${fmtInt(e.cover_weeks_at_recent_rate)} wk stock vs ${fmtInt(e.shelf_life_weeks)} wk life` : 'May expire';
    case 'CONDEMNED_AWAITING_REPLACEMENT': return e.quoted_due_week != null ? `New part due ${fmtWeek(e.quoted_due_week)}` : 'Waiting for a new part';
    case 'DONOR_NOT_REINSTATED': return 'Borrowed part not back';
    case 'OPEN_REQUIREMENT': return 'Plane still waiting';
    default: return SIMPLE_TYPE[a.type] || typeLabel(a.type);
  }
}
const whyText = (a) => (isSimple() ? SIMPLE_WHY[a.type] || tidyEnums(a.summary || '') : tidyEnums(a.trigger || a.summary || ''));
const actionText = (a) => (isSimple() ? simpleAction(a) : a.recommended_action ? tidyEnums(a.recommended_action) : 'No action recorded');
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
  if (isSimple()) return simpleIssue(a);
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
  if (a.type === 'OVERDUE_REPAIR' && e.weeks_overdue != null) return `${a.pn} · repair ${wk1(e.weeks_overdue)} ${byMode('weeks past the promised date', 'wk past quoted due')}`;
  return a.pn ? `${a.pn} · ${issueText(a)}` : a.summary;
}

/** The v2 action fields that exist on this exception, in planner order: [label, value, mono]. */
export function actionFields(a) {
  const out = [];
  const ea = a.expected_availability, eb = a.expected_benefit;
  if (a.trigger) out.push([byMode('What set it off', 'Exception trigger'), isSimple() ? SIMPLE_WHY[a.type] || tidyEnums(a.trigger) : tidyEnums(a.trigger)]);
  if (a.quantity != null) out.push([byMode('How many', 'Quantity'), fmtInt(a.quantity)]);
  if (a.source || a.destination) out.push([byMode('From → to', 'Source → destination'), `${a.source ? tidyEnums(a.source) : '—'} → ${a.destination ? tidyEnums(a.destination) : '—'}`, true]);
  if (a.required_by_week != null) out.push([byMode('Needed by', 'Required by'), fmtWeek(a.required_by_week), true]);
  if (ea && (ea.week != null || ea.basis)) out.push([byMode('When it should be ready', 'Expected availability'), `${ea.week != null ? fmtWeek(ea.week) : 'not known'}${ea.basis ? ` · ${ea.basis}` : ''}${ea.past_quote ? ' · already past quote' : ''}`]);
  if (Array.isArray(a.constraints) && a.constraints.length) out.push([byMode('Limits to keep in mind', 'Constraints'), h('ul', { class: 'pac-list-inline' }, a.constraints.map((c) => h('li', {}, replaceCodes(tidyEnums(c)))))]);
  if (eb && typeof eb === 'object') {
    const bits = [];
    if (eb.observed_downtime_h_lookback != null) bits.push(`${fmtInt(eb.observed_downtime_h_lookback)} h downtime observed here in the lookback`);
    if (eb.observed_exposure_rate_aed_per_h != null) bits.push(`at ${fmtAED(eb.observed_exposure_rate_aed_per_h)}/h`);
    if (eb.capital_above_26w_cover_aed != null) bits.push(`${fmtAED(eb.capital_above_26w_cover_aed)} capital above 26 weeks of cover`);
    if (eb.annual_carrying_cost_aed != null) bits.push(`${fmtAED(eb.annual_carrying_cost_aed)}/yr carrying cost`);
    if (eb.units_expired_in_history != null) bits.push(`${fmtInt(eb.units_expired_in_history)} units expired in history (${fmtAED(eb.value_expired_in_history_aed)})`);
    if (bits.length) out.push([byMode('What it saves', 'Expected benefit'), `${bits.join(', ')}${eb.note ? ` (${eb.note})` : ''}`]);
  }
  if (a.owner) out.push([byMode('Who owns it', 'Owner'), a.owner]);
  if (a.due_week != null) out.push([byMode('Due by', 'Due'), fmtWeek(a.due_week), true]);
  if (a.pn) out.push(['Part', a.pn, true]);
  return out;
}

function ensureCSS() {
  if (document.querySelector('link[data-view-css="planner-action-centre"]')) return;
  document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/planner-action-centre.css', import.meta.url).href, dataset: { viewCss: 'planner-action-centre' } }));
}

// ----------------------------------------------------------------------------- evidence formatting
const EV_LABEL = {
  on_hand: 'On hand (serviceable)', inbound: 'Inbound', p0_target: `${displayName('P0', { mode: 'short' })} station target`, demand_implied_protection: 'Demand-implied protection level',
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
  risk_score: 'Material shortage exposure (score)', deadline: 'Deadline class (hypothetical)', stock_total: 'Stock total',
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
  if (/_h$|_h_|hours/.test(k)) return `${fmtNum(v, Number.isInteger(v) ? 0 : 1)} h`;
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
      implication: 'Falling usage means stock to run down: cut the reorder level before buying more.',
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
      implication: 'A late supplier invalidates the reorder point: update the planning lead time now.',
      headline: `Recent lead time is ${fmtNum(e.ratio, 2)}× the quoted ${fmtNum(e.mean_quoted_d, 0)} d`,
      subtitle: `Days from order to receipt · non-expedite POs · last ${fmtInt(e.lookback_weeks)} weeks`,
      provenance: 'DERIVED', source: 'actions.json',
      table: { columns: [{ key: 'k', label: 'Basis' }, { key: 'v', label: 'Days', num: true, format: (v) => `${fmtNum(v, 1)} d` }], rows },
    });
    hbars(fr.body, rows, (v) => `${fmtNum(v, 0)} d`);
    return host;
  }
  if (e.target != null && e.on_hand != null) {
    const rows = [{ k: byMode('On hand + on the way', 'On hand + inbound'), v: (e.on_hand || 0) + (e.inbound || 0) }, { k: byMode(`${displayName('P0', { mode: 'short' })} target`, `${displayName('P0', { mode: 'short' })} station target (P0)`), v: e.p0_target ?? 0 }, { k: 'Target used', v: e.target, hi: true }];
    const fr = chartFrame(host, {
      implication: byMode('The station has fewer spares than it needs. The next urgent request there could ground a plane.', 'The station is below the level its demand needs: the next D0 request there could ground an aircraft.'),
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
      implication: 'An overdue repair is float the network does not have: chase the shop for a release date.',
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
// F6 (wave 4): human-readable type/severity labels and the key evidence flattened into columns; the raw JSON stays last
const CSV_EV = [['on_hand', 'on_hand'], ['target', 'target'], ['aog_h_52w', 'aog_hours_lookback'], ['d0_req_52w', 'd0_requests_lookback'], ['lead_time_ratio', 'ratio'], ['weeks_overdue', 'weeks_overdue']];
const CSV_COLS = ['exception_id', 'week', 'type_label', 'severity_label', 'pn', 'station', 'summary', 'recommended_action', 'owner', 'due_week', ...CSV_EV.map(([c]) => c), 'type', 'severity', 'evidence_json'];
function csvRow(r) {
  const e = r.evidence || {};
  return {
    ...r, type_label: r.type_label || typeLabel(r.type), severity_label: r.severity_label || SEV_LABEL[r.severity] || r.severity,
    week: r.week != null ? fmtWeek(r.week) : '', due_week: r.due_week != null ? fmtWeek(r.due_week) : '',
    summary: tidyEnums(r.summary || ''), recommended_action: tidyEnums(r.recommended_action || ''),
    ...Object.fromEntries(CSV_EV.map(([c, k]) => [c, e[k] ?? ''])), evidence_json: e,
  };
}
function csvCell(v) {
  if (v === null || v === undefined) return '';
  const s = typeof v === 'object' ? JSON.stringify(v) : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
export function toCSV(rows) {
  return [CSV_COLS.join(','), ...rows.map(csvRow).map((r) => CSV_COLS.map((c) => csvCell(r[c])).join(','))].join('\r\n') + '\r\n';
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
    title: byMode(asOf != null ? `${fmtWeek(asOf)}: ${fmtInt(all.length)} issues to check, ${fmtInt(nSev.urgent)} urgent` : `${fmtInt(all.length)} issues to check this week`,
      asOf != null ? `${fmtWeek(asOf)}: ${fmtInt(all.length)} exceptions, ${fmtInt(nSev.urgent)} urgent` : `${fmtInt(all.length)} exceptions this week`),
    lede: byMode('The weekly to-do list for Falcon Hub Airways (fictional). Each item shows the numbers behind it, what to do, who owns it and when it is due. It supports a planner. It does not replace engineering, quality or safety judgement.',
      'The weekly exception inbox for Falcon Hub Airways (fictional). Each exception carries the numbers behind it, a recommended action, an owner and a due week. Recommendations support a planner; they do not replace engineering, quality or airworthiness judgement.'),
    meta: [provChip(metaProv), h('span', { class: 'chip chip-mono' }, asOf != null ? `As of ${fmtWeek(asOf)}` : 'As-of week not exported')],
  }));

  // v2.1 (C2): the three intro lines
  el.append(intro3({
    what: byMode(`This week’s list of parts problems that need a planner, ranked by urgency.`, 'The weekly exception inbox: rule-based flags on stock, repairs, suppliers and open requirements, ranked by severity and due week.'),
    why: ['Each item is a part that could ground a plane, tie up money or go to waste. ', isSimple() ? 'Acting early keeps ' : 'Acting early cuts ', term('aog_hours'), isSimple() ? ' low.' : '.'],
    action: byMode('Start with the urgent items. Open one to see the numbers, then do the action and close it by its due week.', 'Work the urgent queue first, open the evidence drawer, confirm the action and clear it by the due week; export the filtered list as CSV.'),
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
      h('p', { class: 't-12 faint m-0' }, byMode('Click a team to show only its items. Only problems the simulation can produce are raised.', 'Click an owner to filter the inbox. Rules live in config/aog_lab.yaml; only exception types the v2 simulation produces are raised (no document data exists).'))),
  });
  const chartCard = h('section', { class: 'card span-8', dataset: { story: 'action-types' } });
  const byType = types.map((t) => ({ t, label: labelFor(t), ...Object.fromEntries(SEV.map((s) => [s, count((a) => a.type === t && a.severity === s)])), n: count((a) => a.type === t) }));
  const top = byType[0];
  const frame = chartFrame(chartCard, {
    implication: byMode('Most of the work is moving spares and chasing repairs. Put planners on those first.', 'Most planner work is repair follow-up and stock positioning: staff the desk for those queues.'),
    headline: top ? byMode(`Biggest pile: ${labelFor(topType).toLowerCase()} (${fmtInt(top.n)} of ${fmtInt(all.length)}, ${fmtInt(top.urgent)} urgent)`, `${typeLabel(topType)} is the biggest queue: ${fmtInt(top.n)} of ${fmtInt(all.length)} exceptions, ${fmtInt(top.urgent)} urgent`) : 'No exceptions this week',
    subtitle: `${byMode('Open items by type and urgency', 'Open exceptions by type and severity')} · ${asOf != null ? fmtWeek(asOf) : 'week not exported'} · click a bar to filter`,
    provenance: metaProv, source: 'actions.json',
    table: { columns: [{ key: 'label', label: 'Type' }, ...SEV.map((s) => ({ key: s, label: SEV_LABEL[s], num: true })), { key: 'n', label: 'Total', num: true }], rows: byType },
  });
  frame.body.before(h('div', { class: 'pac-legend t-12', 'aria-hidden': 'true' }, SEV.filter((sv) => nSev[sv]).map((sv) => h('span', {}, h('i', { class: `pac-key pac-key--${sv}` }), `${SEV_LABEL[sv]} ${fmtInt(nSev[sv])}`))));
  const stopChart = responsive(frame.body, (w) => drawTypes(frame.body, w));
  /**
   * v2.1 addendum (motion): one persistent SVG per width with keyed joins (row per type, segment per severity).
   * First draw: bars grow in over the slow token. Filter changes: opacity and label weight transition; nothing
   * redraws from zero. A width change rebuilds (no animation needed for a resize).
   */
  function drawTypes(body, w) {
    // a late rAF after the route changed: d3 cannot inherit a transition on a detached node ("transition N not found")
    if (!body.isConnected) return;
    const d3 = window.d3;
    const narrow = w < 520;
    const rowH = 30, lw = narrow ? 0 : Math.min(230, w * 0.34), top0 = narrow ? 0 : 4;
    const step = narrow ? rowH + 16 : rowH;
    const H = byType.length * step + 8;
    let svg = d3.select(body).select('svg');
    const fresh = svg.empty() || +svg.attr('width') !== w;
    if (fresh) svg = svgIn(body, w, H, 'Exceptions by type and severity');
    const bw = Math.max(40, w - lw - 120);
    const x = d3.scaleLinear().domain([0, d3.max(byType, (r) => r.n) || 1]).range([0, bw]);
    const fill = { urgent: theme.series.urgent, review: theme.series.review, info: theme.color.neutral };
    const by = narrow ? 18 : 6;
    const toggle = (r) => { f.type = f.type === r.t ? '' : r.t; sync(); };
    const rows = svg.selectAll('g.pac-trow').data(byType, (r) => r.t).join((enter) => {
      const g = enter.append('g').attr('class', 'pac-trow').style('cursor', 'pointer').attr('tabindex', 0).attr('role', 'button')
        .attr('transform', (r, i) => `translate(0,${top0 + i * step})`)
        .attr('aria-label', (r) => `${r.label}: ${r.n} exceptions; filter`)
        .on('click', (e, r) => toggle(r))
        .on('keydown', (e, r) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(r); } });
      // a full-row transparent hit target: the click area does not depend on bar length or the draw-in animation
      g.append('rect').attr('class', 'pac-thit').attr('x', 0).attr('y', 0).attr('width', w).attr('height', step - 2).attr('fill', 'transparent');
      g.append('text').attr('class', 'pac-tlabel gnm-label').attr('x', 0).attr('y', narrow ? 10 : by + 9).text((r) => r.label);
      g.append('text').attr('class', 'pac-tval gnm-label').attr('font-family', theme.font.mono).attr('y', by + 10).text((r) => `${fmtInt(r.n)}${r.urgent ? ` · ${fmtInt(r.urgent)} urgent` : ''}`);
      return g;
    });
    rows.select('text.pac-tlabel').attr('class', (r) => (f.type === r.t ? 'pac-tlabel gnm-label gnm-label--strong' : 'pac-tlabel gnm-label'));
    rows.each(function (r) {
      let x0 = lw;
      const segs = SEV.filter((sv) => r[sv]).map((sv) => { const d = { sv, x: x0, w: Math.max(1, x(r[sv]) - 1), n: r[sv], r }; x0 += x(r[sv]); return d; });
      const g = d3.select(this);
      const rect = g.selectAll('rect.pac-tseg').data(segs, (d) => d.sv).join((enter) => {
        const e = enter.append('rect').attr('class', 'pac-tseg').attr('y', by).attr('height', 12).attr('rx', 2).attr('fill', (d) => fill[d.sv])
          .attr('x', (d) => d.x).attr('width', (d) => d.w).style('transform-box', 'fill-box').style('transform-origin', 'left center');
        withTooltip(e, (d) => ({ title: d.r.label, rows: [[SEV_LABEL[d.sv], fmtInt(d.n)], ['Total', fmtInt(d.r.n)]] }));
        return e;
      });
      const op = f.type && f.type !== r.t ? 0.35 : 0.9;
      if (fresh) {
        // draw-in: scale each bar from its left edge (transform + opacity only)
        rect.attr('fill-opacity', op).style('transform', 'scaleX(0)'); txSel(rect, { duration: 'slow', ease: 'enter', name: 'draw-in' }).style('transform', 'scaleX(1)');
        txSel(g.select('text.pac-tval').attr('x', x0 + 8).style('opacity', 0), { duration: 'slow', ease: 'enter', name: 'draw-in' }).style('opacity', 1);
      } else {
        txSel(rect, { name: 'filter' }).attr('fill-opacity', op);
      }
    });
  }
  el.append(h('div', { class: 'grid-12' }, chartCard, summaryCard));

  // ---- wave B: a guided "Monday morning" walkthrough of five typical exceptions from the v2 queue (one per owner/type)
  const TYPE_ORDER = ['OUTSTATION_DEPLETION', 'DONOR_NOT_REINSTATED', 'OPEN_REQUIREMENT', 'OVERDUE_REPAIR', 'CONDEMNED_AWAITING_REPLACEMENT', 'LEAD_TIME_DRIFT', 'EXCESS_DECLINING_DEMAND', 'EXPIRY_RISK'];
  const walk = [];
  TYPE_ORDER.forEach((t) => { if (walk.length < 5) { const a = all.find((x) => x.type === t); if (a) walk.push(a); } });
  if (walk.length) {
    let wi = 0;
    const wBody = h('div', { class: 'pac-walk-body', 'aria-live': 'polite' });
    const wBack = h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: () => showWalk(wi - 1) }, 'Back');
    const wNext = h('button', { type: 'button', class: 'btn btn--primary btn--sm', onclick: () => showWalk(wi + 1) }, 'Next');
    const dots = h('div', { class: 'pac-walk-dots', 'aria-hidden': 'true' }, walk.map(() => h('span')));
    function showWalk(n) {
      wi = Math.max(0, Math.min(walk.length - 1, n));
      const a = walk[wi];
      wBody.replaceChildren(
        h('div', { class: 'pac-walk-step' }, `${String(wi + 1).padStart(2, '0')} / ${String(walk.length).padStart(2, '0')} · ${a.owner || 'Owner not set'}`),
        h('h4', { class: 'pac-walk-title' }, sevPill(a.severity), h('span', {}, `${isSimple() ? labelFor(a.type) : a.type_label || typeLabel(a.type)} · `), h('span', { class: 'mono' }, a.pn || ''), a.station ? h('span', { class: 'mono faint' }, ` · ${a.station}`) : null),
        h('dl', { class: 'pac-walk-dl' },
          h('dt', {}, byMode('Why it came up', 'What triggered it')), h('dd', {}, whyText(a)),
          h('dt', {}, byMode('What we know', 'The evidence')), h('dd', {}, isSimple() ? simpleEvidence(a) : tidyEnums(a.summary || '')),
          h('dt', {}, 'What to do'), h('dd', {}, actionText(a))),
        h('button', { type: 'button', class: 'btn btn--sm', onclick: () => open(a) }, icon('chevron-right'), byMode('Open the full item', 'Open the full exception')));
      [...dots.children].forEach((d, j) => d.classList.toggle('is-on', j <= wi));
      wBack.disabled = wi === 0; wNext.disabled = wi === walk.length - 1;
    }
    el.append(h('div', { class: 'grid-12 mt-3' }, card({
      cls: 'span-12 pac-walk', kicker: 'Guided walkthrough', story: 'action-walkthrough', prov: metaProv,
      title: byMode(`Monday morning: ${fmtInt(walk.length)} typical items from the ${asOf != null ? fmtWeek(asOf) : ''} list, in the order a planner works them`, `Monday morning: ${fmtInt(walk.length)} typical exceptions from the ${asOf != null ? fmtWeek(asOf) : ''} queue, in the order a planner works them`),
      body: h('div', {}, wBody, h('div', { class: 'pac-walk-nav' }, dots, h('div', { class: 'row' }, wBack, wNext))),
    })));
    showWalk(0);
  }

  // ---- filters
  const sel = (label, key, options, fmt = (v) => v) => {
    const id = `pac-${key}`;
    const s = h('select', { class: 'input pac-select', id, onchange: (e) => { f[key] = e.target.value; sync(); } }, h('option', { value: '' }, `All ${label.toLowerCase()}s`), options.map((o) => h('option', { value: o }, fmt(o))));
    return h('label', { class: 'pac-filter', for: id }, h('span', { class: 'field-label' }, label), s);
  };
  const sevSeg = h('div', { class: 'pac-filter' }, h('span', { class: 'field-label' }, 'Severity'), h('div', { class: 'pac-sevseg' }));
  const typeSel = sel('Type', 'type', types, labelFor);
  const stationSel = sel('Station', 'station', stations);
  const ownerSel = sel('Owner', 'owner', owners);
  const shown = h('span', { class: 'pac-shown mono t-12', 'aria-live': 'polite' });
  const resetBtn = h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: () => { Object.assign(f, { severity: 'all', type: '', station: '', owner: '' }); sync(); } }, icon('close'), 'Clear filters');
  const csvBtn = h('button', { type: 'button', class: 'btn btn--sm', dataset: { action: 'export-csv' }, onclick: () => exportCSV() }, icon('download'), 'Export CSV');
  const list = h('ul', { class: 'pac-list list-reset', role: 'list', 'aria-label': 'Exceptions, grouped by part number' });
  const gridHead = h('div', { class: 'pac-grid pac-grid-head', 'aria-hidden': 'true' },
    h('span', {}, byMode('Urgency', 'Severity')), h('span', {}, 'Part · station'), h('span', {}, 'Issue'), h('span', { class: 'is-num', title: 'Serviceable + inbound vs station target' }, 'On hand'), h('span', { class: 'is-num', title: 'AOG hours in the last 52 weeks' }, byMode('Hours grounded', 'AOG h · 52 wk')), h('span', { class: 'is-num', title: 'D0 requests in the last 52 weeks' }, byMode('Urgent asks', 'D0 req')), h('span', {}, byMode('What to do', 'Recommended action')), h('span', { class: 'is-num' }, 'Due'));
  const PAGE = 12;
  const GROUP_PEEK = 3;
  const openGroups = new Set();
  let expanded = false;
  const moreBtn = h('button', { type: 'button', class: 'btn btn--sm pac-more', dataset: { action: 'show-all' }, onclick: () => { if (moreBtn.dataset.clear === 'true') { Object.assign(f, { severity: 'all', type: '', station: '', owner: '' }); expanded = true; } else expanded = !expanded; sync(); } });
  const inbox = card({
    cls: 'mt-3', kicker: 'Exception inbox', title: byMode('Most urgent first, then by due week · grouped by part', 'Ranked by severity, then due week · grouped by part'), prov: metaProv, story: 'action-inbox',
    actions: csvBtn,
    body: h('div', { class: 'stack-3' }, h('div', { class: 'pac-filters' }, sevSeg, typeSel, stationSel, ownerSel), h('div', { class: 'row-between pac-shownrow' }, shown, resetBtn), h('div', { class: 'pac-table' }, gridHead, list), moreBtn,
      h('p', { class: 't-12 faint m-0' }, byMode('On hand means good spares there or on the way, against the target. Hours grounded and urgent asks count the last 52 weeks. A dash means it does not apply. Open a row to see the full story.',
        'On hand = serviceable + inbound vs the station target. AOG h and D0 requests count the last 52 weeks (depletion rules only; — = not applicable). Open a row for the full rationale and evidence.')),
      scopeLine()),
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
      h('button', { type: 'button', class: `pac-row pac-grid pac-row--${a.severity}${inGroup ? ' is-grouped' : ''}`, dataset: { id: a.exception_id, sev: a.severity }, 'aria-label': `${SEV_LABEL[a.severity] || a.severity}: ${shortTitle(a)}. ${actionText(a)} Due ${a.due_week != null ? fmtWeek(a.due_week) : 'not set'}. Open evidence.`, onclick: () => open(a) },
        h('span', { class: 'pac-c-sev' }, sevPill(a.severity)),
        h('span', { class: 'pac-c-part mono' }, inGroup ? h('span', { class: 'pac-stn' }, h('span', { class: 'faint' }, '↳ '), stn) : h('span', {}, h('b', {}, a.pn || '—'), h('span', { class: 'faint' }, ' · '), stn)),
        h('span', { class: 'pac-c-issue', title: labelFor(a.type) }, icon(a.type_icon || TYPE_ICON[a.type] || 'info'), h('span', { class: 'pac-c-issue-t' }, issueText(a)), prov ? provChip(prov) : null),
        h('span', { class: 'pac-c-stock is-num mono', dataset: { k: 'On hand' } }, m.stock ? h('span', { class: m.stock.have < m.stock.target ? 'pac-short' : '' }, `${fmtInt(m.stock.have)} / ${fmtInt(m.stock.target)}`) : num(null)),
        h('span', { class: 'pac-c-aog is-num mono', dataset: { k: byMode('Hours grounded', 'AOG h') } }, num(m.aogH)),
        h('span', { class: 'pac-c-d0 is-num mono', dataset: { k: byMode('Urgent asks', 'D0') } }, num(m.d0)),
        // wave 5: the whole action, clamped to two lines by CSS (the browser's own ellipsis), full text in the title
        h('span', { class: 'pac-c-action', title: tidyEnums(a.recommended_action || '') }, actionText(a)),
        h('span', { class: 'pac-c-due is-num mono' }, a.due_week != null ? fmtWeek(a.due_week) : '—', icon('chevron-right'))));
  }
  /** Same-PN exceptions collapse under one header ("GN-… · 6 stations · 63 AOG h max"); singletons stay plain rows. */
  function groupsOf(rows) {
    const map = new Map();
    rows.forEach((a) => { const k = a.pn || a.exception_id; if (!map.has(k)) map.set(k, []); map.get(k).push(a); });
    const gs = [...map.entries()].map(([pn, rs]) => { const pv = nOr(partBy[pn]?.aog_h_52w_max_station); const aog = pv ?? Math.max(0, ...rs.map((a) => rowMetrics(a).aogH || 0)); return { pn, rows: rs, sev: Math.min(...rs.map((a) => SEV_RANK[a.severity] ?? 9)), aog, aogSt: pv != null ? partBy[pn]?.aog_h_52w_max_station_id || null : rs.find((a) => rowMetrics(a).aogH === aog)?.station || null, first: rows.indexOf(rs[0]) }; });
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
        h('span', { class: 'pac-ghead-meta' }, `${fmtInt(g.rows.length)} ${byMode('items', 'exceptions')} · ${fmtInt(stations.size)} ${stations.size === 1 ? 'station' : 'stations'}${nU ? ` · ${fmtInt(nU)} urgent` : ''}`, g.aog ? h('span', { class: 'pac-nw', title: `${aogLabel} (${aogShort})` }, ` · worst station ${g.aogSt ? `${g.aogSt} ` : ''}${fmtHours(g.aog)}${g.aogSt && !g.rows.some((a) => a.station === g.aogSt) ? ' (no exception there)' : ''}`) : null),
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
      kicker: `${a.exception_id} · ${labelFor(a.type)}`, title: shortTitle(a),
      onClose: () => { if (alive) ctx.setParams({ id: '' }); activeDrawer = null; },
      body: h('div', { class: 'stack-3 pac-drawer' },
        h('div', { class: 'row-wrap' }, sevPill(a.severity), h('span', { class: 'chip chip-mono' }, labelFor(a.type)), provChip(prov)),
        h('div', { class: 'pac-why' }, h('div', { class: 'card-kicker mb-1' }, 'Why it was raised'),
          isSimple() ? h('p', { class: 'm-0' }, `${SIMPLE_WHY[a.type] || ''} ${simpleEvidence(a)}`.trim()) : null,
          h('p', { class: isSimple() ? 'm-0 mt-1 t-12 faint pac-record' : 'm-0' }, isSimple() ? `Record: ${replaceCodes(tidyEnums(a.summary))}` : tidyEnums(a.summary))),
        h('div', { class: 'pac-action' }, h('div', { class: 'card-kicker' }, byMode('What to do', 'Recommended action')), h('p', { class: 'm-0' }, actionText(a)),
          isSimple() && a.recommended_action ? h('p', { class: 'm-0 mt-1 t-12 faint pac-record' }, `Planner’s exact instruction: ${replaceCodes(tidyEnums(a.recommended_action))}`) : null,
          // wave B: only the fields the v2 actions.json produces; a field the rule does not fill is left out
          h('dl', { class: 'meta-list mt-2', dataset: { role: 'action-fields' } }, ...actionFields(a).flatMap(([k, v, mono]) => [h('dt', {}, k), h('dd', { class: mono ? 'mono' : '' }, v)]))),
        chart,
        h('div', {}, h('div', { class: 'card-kicker mb-1' }, 'Evidence · the numbers behind it'),
          h('table', { class: 'data-table data-table--dense pac-evtable' }, h('caption', { class: 'sr-only' }, 'Evidence'), h('tbody', {}, evRows.map(([k, v]) => h('tr', {}, h('th', { scope: 'row' }, evLabel(k)), h('td', { class: 'is-num mono' }, fmtEv(k, v))))))),
        prov === 'SIMULATED' ? h('p', { class: 't-12 faint m-0' }, 'This exception comes from a seeded random flag, not from document data. It illustrates the quarantine workflow only.') : null,
        h('p', { class: 't-12 faint m-0' }, byMode('Urgency classes in this model are made up for teaching. They are not real airline safety rules. A planner checks before acting.', 'D0/D3/D10 are hypothetical rectification windows; D3 and D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions. A planner confirms before acting.'))),
      foot: [
        a.pn ? h('a', { class: 'btn btn--sm', href: ctx.buildHash('parts', { ata: a.pn.split('-')[1], pn: a.pn }) }, icon('layers'), 'Open part') : null,
        a.station && a.station !== NETWORK ? h('a', { class: 'btn btn--sm', href: ctx.buildHash('network', { station: a.station }) }, icon('map-pin'), 'Open station') : null,
        h('a', { class: 'btn btn--sm btn--ghost', href: ctx.buildHash('actions', { id: a.exception_id }) }, icon('chevron-right'), 'Deep link'),
      ].filter(Boolean),
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
    resetBtn.disabled = f.severity === 'all' && !f.type && !f.station && !f.owner;
    // Page by whole groups: show groups until about PAGE visible rows, then "Show all".
    const gs = groupsOf(rows);
    let collapsedN = 0, vis = 0;
    for (const g of gs) { if (vis >= PAGE) break; vis += peek(g); collapsedN++; }
    const shownN = expanded ? gs.length : collapsedN;
    const hiddenRows = gs.slice(collapsedN).reduce((n, g) => n + g.rows.length, 0);
    list.replaceChildren(...(rows.length ? gs.slice(0, shownN).map(groupBlock) : [h('li', { class: 'state' }, icon('info'), h('p', {}, 'No exceptions match these filters.'))]));
    gridHead.hidden = !rows.length;
    // wave C (F7): the counter reports the rows actually on screen, and says when the list is truncated
    const visN = [...list.querySelectorAll('.pac-row')].filter((r) => !r.closest('[hidden]') && r.offsetParent !== null).length || list.querySelectorAll('.pac-row').length;
    shown.replaceChildren(...[h('span', { class: 'pac-nw', dataset: { role: 'shown-count' } }, `Showing ${fmtInt(Math.min(visN, rows.length))} of ${fmtInt(rows.length)}`),
      rows.length < all.length ? h('span', { class: 'pac-nw' }, ` matching (${fmtInt(all.length)} in all)`) : null,
      visN < rows.length ? h('span', { class: 'pac-nw' }, ' (expand for all)') : null, ' · ', h('span', { class: 'pac-nw' }, `${fmtInt(nU)} urgent`)].filter((x) => x != null));
    // every filtered state keeps a working button: with nothing left to expand, it clears the filters and shows everything
    const filtered = f.severity !== 'all' || !!f.type || !!f.station || !!f.owner;
    const clearMode = hiddenRows === 0 && filtered;
    moreBtn.hidden = hiddenRows === 0 && !filtered;
    moreBtn.dataset.clear = String(clearMode);
    const word = byMode('items', 'exceptions');
    moreBtn.replaceChildren(icon(expanded && !clearMode ? 'arrow-up' : 'arrow-down'), clearMode ? `Clear filters and show all ${fmtInt(all.length)} ${word}`
      : expanded ? 'Show the top of the list only' : `Show all ${fmtInt(rows.length)} ${word} (${fmtInt(hiddenRows)} more across ${fmtInt(gs.length - collapsedN)} parts)`);
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
