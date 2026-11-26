/**
 * 07 · AOG Response Lab — screen agent D.
 * Data: aog_lab.json (gnm.aog: incidents, options a–h, decision panel, counterfactual; SIMULATED)
 * Deep links: #/aog?incident=AOG-0001
 * Shows: the 12 showcase incidents, a precise response timeline (removal → request → stock checks →
 * sourcing → shipped → fitted), the options with feasibility, reason codes, wait, direct cost, exposure
 * and deadline, a "Human decision required" panel, and the history-vs-best-option counterfactual.
 * The recommended option is the one ranked 1 by the lab (decision.recommended): exposure_aed already
 * includes direct cost, so the two are never added.
 */
import { h, pageHead, card, provChip, pill, icon, intro3, scopeLine, tooltip } from '../ui.js';
import { isSimple } from '../lib/mode.js';
import { dur } from '../lib/motion.js';

/** Enter transition (opacity + 8 px rise, transform/opacity only) with a motion token; reduced motion → instant. */
function enter(el, d = 'base') {
  const ms = dur(d);
  if (!el || !ms) return;
  el.style.setProperty('--aog-enter-ms', `${ms}ms`);
  el.classList.remove('aog-enter');
  void el.offsetWidth; // restart the CSS animation (one read, outside any loop)
  el.classList.add('aog-enter');
  el.addEventListener('animationend', () => el.classList.remove('aog-enter'), { once: true });
}
import { term, termText } from '../lib/glossary.js';
import { displayName } from '../lib/names.js';
import { chartFrame, responsive, svgIn, theme, fmtAED, fmtHours, fmtInt, fmtPct, fmtWeek, withTooltip, truncate, refLine, chipLabel, HEADLINE_MAX, fmtMoney, fmtEnum, plural } from '../charts/theme.js';

export const data = ['aog_lab'];

const STEP_LABEL = { sourced: 'Part sourced', aog_route: 'AOG-desk route', requirement: 'Requirement', donor_reinstated: 'Donor reinstated', loan_returned: 'Loan returned', removal: 'Removal', request: 'Request', local_check: 'Local stock check', network_check: 'Network stock check', aog_start: 'AOG starts', sourcing: 'Sourcing decided', ordered: 'Ordered', shipped: 'Shipped', arrived: 'Arrived', received: 'Received', fitted: 'Part at the aircraft', released: 'Fitted and released to service', unfilled: 'Unfilled', context: 'Context' };
const BASIS = {
  transport_matrix: 'Transfers keep their estimate: transport times in this world are fixed.',
  actual_order_arrival: 'Scored on the order’s actual arrival.',
  replan_expedite_at_quoted_due: 'The order missed its quoted date, so the best option is re-planned to an expedite at that date.',
  estimate_not_realisable: 'Not taken in history, so it keeps the ex-ante estimate (cannot be realised from the record).',
};
/** Plain words for the scoring-basis counts ("112 scored on transport times"). */
const BASIS_SHORT = { transport_matrix: 'scored on fixed transport times', actual_order_arrival: 'scored on the order’s actual arrival', replan_expedite_at_quoted_due: 're-planned to an expedite at the quoted date', estimate_not_realisable: 'kept the estimate (not taken in history)' };
/** Plain step names for Simple mode (v2.1 C). */
const STEP_PLAIN = { removal: 'Part removed', request: 'Part requested', requirement: 'Need recorded', local_check: 'Shelf checked here', network_check: 'Other airports checked', aog_start: 'Grounded clock starts', sourcing: 'Route chosen', aog_route: 'Urgent-parts team tries a route', sourced: 'Part found', ordered: 'Ordered', shipped: 'Shipped', arrived: 'Arrived', received: 'Received', fitted: 'Part at the aircraft', released: 'Fitted and released', loan_returned: 'Loan handed back', donor_reinstated: 'Donor aircraft gets a part back', unfilled: 'Still waiting', context: 'Context' };
const stepLabel = (s) => (isSimple() && STEP_PLAIN[s]) || STEP_LABEL[s] || String(s || 'step').replace(/_/g, ' ');
/** Short step names for the swimlane (the full sentence lives in the event log). */
const STEP_SHORT = { removal: 'Removal', requirement: 'Requirement', request: 'Request', local_check: 'Local check', network_check: 'Network check', aog_start: 'AOG starts', sourcing: 'Sourcing', aog_route: 'AOG route', sourced: 'Sourced', ordered: 'Ordered', shipped: 'Shipped', arrived: 'Arrived', received: 'Received', fitted: 'Part at aircraft', released: 'Released', loan_returned: 'Loan back', donor_reinstated: 'Donor back', unfilled: 'Unfilled', context: 'Context' };
const STEP_SHORT_PLAIN = { removal: 'Removed', requirement: 'Need', request: 'Request', local_check: 'Shelf here', network_check: 'Other airports', aog_start: 'Clock starts', sourcing: 'Route chosen', aog_route: 'Route tried', sourced: 'Part found', ordered: 'Ordered', shipped: 'Shipped', arrived: 'Arrived', received: 'Received', fitted: 'Part at aircraft', released: 'Released', loan_returned: 'Loan back', donor_reinstated: 'Donor back', unfilled: 'Waiting', context: 'Context' };
const stepShort = (s) => (isSimple() ? STEP_SHORT_PLAIN[s] : STEP_SHORT[s]) || stepLabel(s);
/** Swimlanes: desk decisions vs physical movement of the part. Unknown steps go to the desk lane. */
const MOVE_STEPS = new Set(['shipped', 'arrived', 'received', 'fitted', 'released', 'unfilled', 'issued']);
/** The step that ends material downtime: release to service when exported (v2: fit/RTS counted), else the fitted step. */
const endStepOf = (tl) => (tl || []).find((s) => s.step === 'released') || (tl || []).find((s) => s.step === 'fitted');
const laneOf = (s) => (MOVE_STEPS.has(s.step) ? 1 : 0);
/** Plain-language reason labels; the raw code stays in a title attribute. Unknown codes are sentence-cased. */
const REASON = {
  LOCAL_STOCK: 'Stock on the shelf here', NO_STOCK: 'No serviceable stock', COMMITTED_TO_KIT: 'Committed to a check kit', ROBS_KIT_RESERVATION: 'Breaks a kit reservation',
  NOT_APPLICABLE_AT_HUB: 'Request is at the hub', STOCK_AT_HUB: 'Stock at the hub', NEXT_FLIGHT_OUT: 'Next flight out', ROUTINE_SHIPMENT: 'Routine shipment covers it',
  BELOW_PROTECTION_LEVEL: 'Donors at protection level', LATERAL_OK: 'Donor keeps its cover', NOT_CONTRACTED: 'No pool contract', NOT_POOLED_PART_CLASS: 'Part class not pooled', POOL_OK: 'Pool contracted',
  NOT_REPAIRABLE: 'Not a repairable part', NO_OPEN_RO: 'No unit at a repair shop', RO_OVERDUE: 'Repair already overdue', NO_TIME_SAVED: 'Acceleration saves no time',
  DOES_NOT_BEAT_ALTERNATIVES: 'Slower than another option', ACCELERATION_OK: 'Acceleration is fastest', EXPEDITE_MARKET_BUY: 'AOG-desk market purchase', OPEN_PO_EXISTS: 'Order already open',
  NO_OPEN_SUPPLY: 'No open order or repair', OPEN_PO_INBOUND: 'Open purchase order inbound', INBOUND_TRANSFER: 'Transfer already in transit', RO_RETURN_INBOUND: 'Repair return inbound',
  QUEUED_BEHIND_BACKORDERS: 'Queued behind earlier requests', SUPPLY_OVERDUE: 'Inbound order overdue', EXCEEDS_DEADLINE: 'Wait exceeds deadline slack',
  HUMAN_DECISION_REQUIRED: 'Engineering approval needed', NO_DONOR_AIRCRAFT: 'No donor aircraft',
};
/** Simple mode: [short label, one plain sentence] per reason code; unknown codes fall back to the exported text. */
const REASON_PLAIN = {
  LOCAL_STOCK: ['Spare on the shelf here', 'A ready spare is on the shelf at this airport.'],
  NO_STOCK: ['No ready spare', 'No ready-to-fit spare at the source.'],
  COMMITTED_TO_KIT: ['Saved for planned work', 'The spares here are saved for planned work.'],
  ROBS_KIT_RESERVATION: ['Takes a spare saved for planned work', 'Allowed only when the plane must be fixed before its next flight.'],
  NOT_APPLICABLE_AT_HUB: ['Request is at AUH', 'The request is already at the AUH home base.'],
  STOCK_AT_HUB: ['Spare at AUH', 'A ready spare is at the AUH home base.'],
  NEXT_FLIGHT_OUT: ['Next flight out', 'It ships on the next flight or by hand-carry.'],
  ROUTINE_SHIPMENT: ['Normal shipment is fast enough', 'A normal shipment arrives in time, at normal cost.'],
  BELOW_PROTECTION_LEVEL: ['Other airports need their spares', 'Other airports hold only the spares they need themselves.'],
  LATERAL_OK: ['Another airport can spare one', 'The other airport keeps enough cover after sending it.'],
  ROTABLES_ONLY: ['Repairable parts only', 'This route only works for repairable parts.'],
  CONSUMABLES_EXPENDABLES_ONLY: ['Throw-away parts only', 'This route only works for cheap throw-away parts.'],
  OUTSTATION_ONLY: ['Away airports only', 'Local borrowing exists only away from the home base.'],
  HUB_ONLY: ['AUH only', 'Borrowing from our own aircraft is modelled only at AUH.'],
  NO_LOCAL_MARKET: ['Nobody to borrow from here', 'No one at this airport lends this part for this aircraft type.'],
  AVAILABILITY_UNCERTAIN: ['May not work first time', 'This route works only some of the time. Failed tries are repeated.'],
  NO_DONOR_AIRCRAFT: ['No aircraft to borrow from', 'No other aircraft of this type has a part we could borrow.'],
  HUMAN_DECISION_REQUIRED: ['Engineering approval needed', 'Engineering and quality staff must approve it. The lab never ranks it.'],
  LOAN_FEE_ACCRUES: ['Daily fee', 'A daily fee runs until our own part replaces the borrowed one.'],
  NOT_CONTRACTED: ['No pool contract', 'There is no parts-pool contract under the Simple Rulebook. Terms are shown for reference.'],
  NOT_POOLED_PART_CLASS: ['Not a pooled part', 'The pool covers repairable parts only.'],
  POOL_OK: ['Pool contracted', 'A parts-pool contract is in place.'],
  NO_OPEN_RO: ['Nothing at the repair shop', 'None of this part is at a repair shop.'],
  NO_QUEUE_TO_JUMP: ['Nothing to rush', 'Every unit at the shop is already being worked on.'],
  DOES_NOT_BEAT_ALTERNATIVES: ['Slower than another route', 'Rushing the repair is not faster than another route.'],
  QUEUE_JUMP_OK: ['Rushing is fastest', 'Rushing the repair beats the other routes.'],
  ESTIMATE: ['Rough estimate', 'It uses the quoted repair time and a flat fee, not a shop quote.'],
  NO_OPEN_SUPPLY: ['Nothing on its way', 'No part of this kind is on its way.'],
  OPEN_PO_INBOUND: ['Order on its way', 'The first usable part is an order already placed.'],
  INBOUND_TRANSFER: ['Shipment on its way', 'A shipment to this airport is already in transit.'],
  RO_RETURN_INBOUND: ['Repair coming back', 'The first usable part is one coming back from repair.'],
  QUEUED_BEHIND_BACKORDERS: ['Others are waiting first', 'Earlier requests get the first parts that arrive.'],
  SUPPLY_OVERDUE: ['Order is late', 'The order is past its quoted date.'],
  EXCEEDS_DEADLINE: ['Too slow for the deadline', 'The part arrives after the deadline, so the plane stays grounded until it is fitted.'],
};
export const reasonLabel = (c) => (isSimple() && REASON_PLAIN[c]?.[0]) || REASON[c] || String(c || '').toLowerCase().replace(/_/g, ' ').replace(/^./, (x) => x.toUpperCase());
const reasonText = (c, codes) => (isSimple() && REASON_PLAIN[c]?.[1]) || (codes[c] ? tidyProse(codes[c]).replace(/never auto-recommended/g, 'never ranked by the lab') : null);

/** Plain route names (v2.1 C): robbery is "borrowing a part from another of our aircraft". Keyed by option key. */
const OPT_PLAIN = {
  local: 'Spare on the shelf here', hub_transfer: 'Send a spare from AUH', lateral: 'Send a spare from another airport',
  local_borrow: 'Borrow a spare at this airport', robbery: 'Borrow the part from another of our aircraft at AUH',
  exchange_loan: 'Exchange or loan part from an outside supplier', local_buy: 'Buy or borrow the part locally',
  inbound: 'Wait for a part already on its way', repair_queue_jump: 'Pay the repair shop to rush ours (estimate)', pool: 'Swap from a parts pool',
};
/** Plain names for the route history actually took (aog_lab.route_labels keys). */
const ROUTE_PLAIN = {
  local: 'Spare taken from the shelf here', hub_transfer: 'Spare sent from AUH', lateral: 'Spare sent from another airport',
  inbound_transfer: 'Shipment already on its way', inbound_po: 'Normal order arrived', inbound_repair: 'Our part came back from repair',
  inbound_hub_stock: 'Sent from AUH once it was restocked', robbery: 'Borrowed from another of our aircraft at AUH',
  exchange_loan: 'Exchange or loan part from an outside supplier', planned_loan: 'Pre-arranged exchange or loan',
  local_borrow: 'Borrowed a spare at this airport', local_buy: 'Bought or borrowed locally', unfilled: 'Still waiting at the end of the history',
};
const TRIGGER_PLAIN = { D0_no_stock: 'Must fix now, no spare here', deadline_expired: 'Time allowed ran out' };
const DEADLINE_TERM = { D0: 'd0', D3: 'd3', D10: 'd10' };
/** Timeline event sentences in plain words (Simple mode). Expert keeps the exported record. */
export function plainEvent(t) {
  if (!isSimple()) return t;
  return String(t || '')
    .replace(/Robbery committed \(engineering\/quality approval required\)/i, 'Part borrowed from another of our aircraft (approval needed)')
    .replace(/AOG desk tries recovery routes: (\d+) attempt\(s\), result (\w+)/, (m, n, r) => `Urgent-parts team makes ${n} ${+n === 1 ? 'try' : 'tries'}: ${(OPT_PLAIN[r] || ROUTE_PLAIN[r] || r).toLowerCase()}`)
    .replace(/Material-related downtime starts/i, 'Grounded clock starts')
    .replace(/Exchange\/loan unit delivered/i, 'Exchange or loan part delivered')
    .replace(/Locally borrowed unit delivered/i, 'Borrowed part delivered')
    .replace(/Own unit fitted in place of the borrowed unit; loan returned/i, 'Our own part replaces the borrowed one; loan handed back')
    .replace(/fitting \/ release-to-service starts/i, 'fitting and release start')
    .replace(/fitting\/RTS/g, 'fitting and release')
    .replace(/removed unserviceable/i, 'removed, broken')
    .replace(/\bserviceable\b/g, 'ready')
    .replace(/requirement/gi, 'need')
    .replace(/\(s\)/g, 's');
}
/** Plain versions of the exported desk checklists (Simple mode); unknown items keep the exported text. */
const CHECK_PLAIN = [
  [/rectification window/i, 'Confirm how long the aircraft may wait before it must be fixed. The D0, D3 and D10 deadlines here are made up for the model.'],
  [/applicability/i, 'Check the part fits this exact aircraft, including its modification status.'],
  [/lender's release certificate/i, "Check the lender's paperwork, the part's history and its modification status."],
  [/release certificate/i, "Make sure the part's release paperwork and history travel with it."],
  [/next-flight-out|hand-carry/i, 'Book the next flight out or a hand-carry, and clear customs ahead.'],
  [/commercial terms/i, 'Agree the fees, the daily charge and when our own part must go back.'],
  [/donor station/i, 'Agree with the airport that sends the part, and refill its own spares.'],
  [/inbound unit's status/i, 'Confirm the part on its way is real and set it aside for this aircraft.'],
  [/hand-back/i, 'Plan the hand-back: our own part replaces the borrowed one once it is repaired.'],
  [/engineering and quality approval/i, 'Engineering and quality staff must approve it first. The owner must approve too if the donor aircraft is leased.'],
  [/records must be updated/i, 'Update both aircraft records. The donor aircraft stays short until the next spare reaches AUH.'],
];
const plainCheck = (c) => (isSimple() && CHECK_PLAIN.find(([re]) => re.test(c))?.[1]) || c;
const fitHeadline = (...cands) => { const c = cands.filter(Boolean); return c.find((t) => t.length <= (HEADLINE_MAX || 90)) || c.at(-1); };
const simWeek = (absH) => (absH == null ? null : fmtWeek(Math.floor(absH / 168)));
const tLabel = (t) => `T${t >= 0 ? '+' : '−'}${fmtHours(Math.abs(t))}`;
const fmtAEDfull = (v) => (v == null ? '—' : `AED ${Math.round(v).toLocaleString('en-GB')}`);
/** Compact money with one decimal under AED 10k ("AED 1.8k"), else fmtMoney ("AED 138k"). */
const fmtMoneyFine = (v) => (v != null && Math.abs(v) >= 1000 && Math.abs(v) < 10000 ? `AED ${(v / 1000).toFixed(1).replace(/\.0$/, '')}k` : fmtMoney(v));
/** Exported prose → house style: "3 feasible option(s)" → "3 feasible options", "AED 137,650" → "AED 138k". */
export const tidyProse = (t) => String(t || '')
  .replace(/(\d[\d,]*)\s+((?:[a-z-]+\s+)?)([a-z]+)\(s\)/gi, (m, n, mid, w) => `${n} ${mid}${+n.replace(/,/g, '') === 1 ? w : `${w}s`}`)
  .replace(/\b([a-z]+)\(s\)/gi, '$1s')
  .replace(/AED\s?(-?\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?/g, (m, n) => fmtMoneyFine(+n.replace(/,/g, '')));
/** Recommendation title without a repeated source: "Emergency transfer from AUH (AUH)" → "Emergency transfer from AUH". */
export const recTitle = (label, source) => (source && !new RegExp(`\\b${String(source).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).test(label) ? `${label} (${source})` : label);

function ensureCSS() {
  if (document.querySelector('link[data-view-css="aog-response-lab"]')) return;
  document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/aog-response-lab.css', import.meta.url).href, dataset: { viewCss: 'aog-response-lab' } }));
}

/** The lab's recommendation: decision.recommended, else the rank-1 option. Never direct_cost + exposure. */
export function recommendedOption(inc) {
  const opts = inc.options || [];
  const key = inc.decision?.recommended ?? inc.recommended_option;
  return (key && opts.find((o) => o.key === key)) || opts.find((o) => o.rank === 1) || null;
}

function optState(o, rec) {
  const S = isSimple();
  if (o.human_decision) return { cls: 'human', pill: pill('review', S ? 'A person decides' : 'Human decision'), order: 5, group: 'na' };
  if (rec && o === rec) return { cls: 'rec', pill: pill('ok', 'Recommended · rank 1'), order: 0, group: 'ok' };
  if (o.indicative || (o.reason_codes || []).includes('NOT_CONTRACTED')) return { cls: 'greyed', pill: pill('unknown', 'Not contracted'), order: 3, group: 'na' };
  if (o.feasible) return { cls: 'feasible', pill: pill('info', o.rank ? `${S ? 'Could work' : 'Feasible'} · rank ${o.rank}` : (S ? 'Could work' : 'Feasible')), order: 1, group: 'ok' };
  return { cls: 'infeasible', pill: pill('unknown', S ? 'Not possible' : 'Infeasible'), order: 4, group: 'na' };
}

/** Why the recommended option misses its deadline, in one plain sentence (null when it meets it). */
export function missedNote(inc, rec, slack) {
  if (!rec || rec.deadline_met || rec.wait_h == null) return null;
  const feas = (inc.options || []).filter((o) => o.feasible && !o.human_decision);
  const anyMeets = feas.some((o) => o.deadline_met);
  if (isSimple()) {
    if (anyMeets) return `Misses the deadline, but has the lowest total cost of the ${fmtInt(feas.length)} routes that could work.`;
    if (!slack) return 'No route meets the deadline: the plane is grounded from removal. Ranked by total cost.';
    return `No route arrives within the ${fmtHours(slack)} allowed, so some grounded time is unavoidable. Ranked by total cost.`;
  }
  if (anyMeets) return `Misses the deadline, but has the lowest exposure of the ${fmtInt(feas.length)} feasible options.`;
  if (!slack) return `No option meets a ${inc.deadline || 'D0'} deadline: the aircraft is AOG from removal; ranked by exposure.`;
  return `No feasible option arrives within the ${fmtHours(slack)} slack: some AOG is unavoidable; ranked by exposure.`;
}

export async function render(el, ctx) {
  ensureCSS();
  // wait for the view stylesheet before building the DOM: an unstyled first paint shifts the layout (CLS)
  await new Promise((res) => { const l = document.querySelector('link[data-view-css="aog-response-lab"]'); if (!l || l.sheet) return res(); l.addEventListener('load', res, { once: true }); l.addEventListener('error', res, { once: true }); setTimeout(res, 3000); });
  const { aog_lab: A } = ctx.data;
  const codes = A.reason_codes || {};
  const labels = A.option_labels || {};
  const prov = A.meta?.provenance || A.provenance || 'SIMULATED';
  const showIds = Array.isArray(A.showcase_ids) && A.showcase_ids.length ? A.showcase_ids : (A.incidents || []).map((i) => i.id);
  const incidents = showIds.map((id) => A.incidents.find((i) => i.id === id)).filter(Boolean);
  let inc = incidents.find((i) => i.id === ctx.params.incident) || incidents[0];
  const S = isSimple();
  // v2.1 C: route names are plain in Simple mode (robbery → borrowing a part from another of our aircraft)
  const optLabel = (o) => (S && OPT_PLAIN[o.key]) || o.option || labels[o.key] || o.key;

  el.append(pageHead({
    num: '07', eyebrow: 'AOG Response Lab',
    title: 'An aircraft is on the ground. What are the options?',
    lede: S
      ? `${fmtInt(incidents.length)} example groundings from the model's history of a fictional airline. Each one is replayed at the moment the part was requested. Only what the parts desk knew then is used.`
      : `${fmtInt(incidents.length)} showcase groundings from the simulated history of Falcon Hub Airways (fictional). Each is replayed at the moment of the request, using only what the AOG desk knew then: stock before the request, open orders at their quoted dates. D0/D3/D10 are hypothetical rectification windows; D3 and D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions.`,
    meta: [provChip(prov), h('span', { class: 'chip chip-mono' }, S ? `History W0–W103 · ${displayName('P0', { mode: 'short' })}` : 'History W0–W103 · policy P0')],
  }));
  el.append(intro3({
    what: `${fmtInt(incidents.length)} example groundings, replayed step by step, with every route the parts desk could have used to find the part.`,
    why: ['Each of the ', term('aog_hours'), ' costs money and upsets the schedule. The fastest route is not always the cheapest.'],
    action: ['Pick the route with the lowest total cost and check the paperwork. Get engineering approval before ', term('robbery'), '.'],
  }));
  // A11: the AOG clock, said once where downtime is shown (starts at removal; overnight hours count; fitting included)
  el.append(h('aside', { class: 'aog-clock mt-3', dataset: { role: 'aog-clock' } }, icon('clock'),
    h('div', {},
      h('p', { class: 'm-0' }, h('b', {}, 'How the grounded clock runs. '), S
        ? 'The clock starts when the part is removed. For a part that can wait, it starts when the time allowed runs out. Overnight and other non-flying hours count in full. Fitting and release time is included.'
        : 'The downtime clock starts when the part is removed (for no-go items; for deferrable items, when the rectification window runs out), not at the next scheduled departure, and overnight and other non-flying hours count in full. Fitting and release-to-service time is included. A departure-based count would be lower for every plan.'),
      S ? h('p', { class: 'm-0 t-12 faint' }, 'The deadlines are made up for the model: D0 means fix before the next flight; D3 and D10 allow 3 or 10 days.') : null)));

  // ---- incident picker
  const picker = h('div', { class: 'aog-picker', role: 'radiogroup', 'aria-label': 'Showcase incident' });
  const tiles = incidents.map((i) => h('button', {
    type: 'button', role: 'radio', class: 'aog-tile', dataset: { id: i.id }, 'aria-checked': String(i === inc),
    onclick: () => select(i),
  },
  h('span', { class: 'aog-tile-top' }, h('span', { class: 'mono' }, i.id), h('span', { class: `aog-dl aog-dl--${String(i.deadline).toLowerCase()}` }, i.deadline)),
  h('span', { class: 'aog-tile-pn mono' }, i.pn),
  h('span', { class: 'aog-tile-desc' }, i.desc || ''),
  h('span', { class: 'aog-tile-foot mono' }, h('span', {}, i.station), h('span', {}, i.aog_hours != null ? `${fmtHours(i.aog_hours)}${S ? ' down' : ''}` : 'AOG h not run'))));
  picker.append(...tiles);
  picker.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;
    e.preventDefault();
    const k = incidents.indexOf(inc) + (e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1);
    select(incidents[(k + incidents.length) % incidents.length], true);
  });
  el.append(card({ cls: 'mt-3', kicker: S ? 'Example groundings' : 'Showcase incidents', title: 'Pick a grounding to replay', prov, story: 'aog-picker', body: picker }));
  const badId = ctx.params.incident && !incidents.some((i) => i.id === ctx.params.incident) ? ctx.params.incident : null;
  if (badId && inc) {
    el.append(h('p', { class: 'aog-badid t-12 muted mt-2', role: 'status', dataset: { role: 'bad-incident' } }, icon('info'), ` ${badId} is not one of the showcase incidents; showing ${inc.id}.`));
    ctx.setParams({ incident: inc.id });
  }

  const host = h('div', { class: 'mt-3' });
  el.append(host);
  const summaryHost = h('div', { class: 'mt-3' });
  el.append(summaryHost);
  let stops = [];
  let drawnOnce = false;

  function select(i, focus) {
    inc = i;
    tiles.forEach((t) => { const on = t.dataset.id === i.id; t.setAttribute('aria-checked', String(on)); t.tabIndex = on ? 0 : -1; if (on && focus) t.focus(); });
    ctx.setParams({ incident: i.id });
    draw();
  }
  tiles.forEach((t) => (t.tabIndex = t.dataset.id === inc?.id ? 0 : -1));

  function draw() {
    stops.forEach((s) => s()); stops = [];
    if (!inc) { host.replaceChildren(h('div', { class: 'state' }, icon('info'), h('p', {}, 'No incidents exported.'))); return; }
    const rec = recommendedOption(inc);
    const cf = inc.counterfactual || {};
    const req = (inc.timeline || []).find((s) => s.step === 'request');
    const slack = req?.evidence?.slack_h ?? (inc.deadline === 'D0' ? 0 : null);

    // incident header
    const CLASS = S ? { R: termText('rotable'), C: termText('consumable'), E: termText('expendable') } : { R: 'Rotable', C: 'Consumable', E: 'Expendable' };
    const rate = inc.penalty_aed_per_h ?? inc.rate_aed_per_h;
    const facts = S ? [
      ['Aircraft', `${inc.tail} (fictional)`], ['Airport', inc.station], ['Part', `${inc.pn}`], ['Part type', CLASS[inc.part_class] || '—'],
      ['How urgent', DEADLINE_TERM[inc.deadline] ? [term(DEADLINE_TERM[inc.deadline], { cap: true }), slack ? ` · ${fmtHours(slack)} allowed` : ''] : inc.deadline], ['What happened', TRIGGER_PLAIN[inc.trigger] || (inc.trigger ? fmtEnum(inc.trigger) : '—')],
      ['Hours grounded (history)', inc.aog_hours != null ? fmtHours(inc.aog_hours) : 'not run'], ['Assumed cost per grounded hour', rate != null ? `${fmtMoneyFine(rate)}${inc.archetype ? ` · ${inc.archetype}` : ''}` : 'not run'],
    ] : [
      ['Tail', `${inc.tail} (fictional)`], ['Station', inc.station], ['Part', `${inc.pn}`], ['ATA · class', [inc.ata ? `ATA ${inc.ata}` : null, inc.part_class ? CLASS[inc.part_class] || inc.part_class : null].filter(Boolean).join(' · ') || '—'],
      ['Deadline', `${inc.deadline}${slack != null ? ` · ${fmtHours(slack)} slack` : ''} (hypothetical)`], ['Trigger', inc.trigger ? fmtEnum(inc.trigger) : '—'],
      ['AOG (history)', inc.aog_hours != null ? fmtHours(inc.aog_hours) : 'not run'], ['AOG penalty', rate != null ? `${fmtMoneyFine(rate)} / h${inc.archetype ? ` · ${inc.archetype}` : ''}` : 'not run'],
    ];
    const head = card({
      cls: 'aog-head', kicker: `${inc.id}${inc.need_h != null ? (S ? ` · ${simWeek(inc.need_h)}` : ` · ${simWeek(inc.need_h)} · simulated hour ${fmtInt(inc.need_h)}`) : ''}`,
      title: `${inc.pn} · ${inc.desc || ''}`, prov,
      body: h('dl', { class: 'aog-facts' }, facts.map(([k, v]) => h('div', {}, h('dt', {}, k), h('dd', { class: k === 'Part' || k === 'Station' || k === 'Airport' ? 'mono' : '' }, v)))),
    });

    // timeline
    const tlCard = h('section', { class: 'card span-12', dataset: { story: 'aog-timeline' } });
    const incWrap = h('div', { class: 'span-12 aog-incident', dataset: { story: inc.id === A.ps1_incident_id ? 'aog-incident-ps1' : 'aog-incident', incident: inc.id } });
    const atAc = (inc.timeline || []).find((s) => s.step === 'fitted');
    const fitted = endStepOf(inc.timeline);
    const twoStage = atAc && fitted && fitted !== atAc;
    const histRouteTxt = (S && ROUTE_PLAIN[cf.actual_route]) || cf.actual_route_label || 'route not recorded';
    const tf = chartFrame(tlCard, {
      implication: S ? 'Most of the wait is finding the part, not flying it in. Where the spare already sits decides how long the plane stays down.' : 'The wait sits in sourcing, not transport: where the stock already is decides how long the aircraft stays down.',
      headline: S && fitted
        ? (twoStage
          ? fitHeadline(`Part at the aircraft after ${fmtHours(atAc.t_h)}; fitted and released at ${fmtHours(fitted.t_h)}`, `Part at aircraft after ${fmtHours(atAc.t_h)}; released at ${fmtHours(fitted.t_h)}`)
          : fitHeadline(`Fitted and released ${fmtHours(fitted.t_h)} after the request: ${histRouteTxt.toLowerCase()}`, `Released ${fmtHours(fitted.t_h)} after the request`))
        : fitted
        ? (twoStage
          ? fitHeadline(`Part at the aircraft ${fmtHours(atAc.t_h)} after the request; released to service at ${fmtHours(fitted.t_h)}`, `Part at aircraft at ${fmtHours(atAc.t_h)}; released at ${fmtHours(fitted.t_h)}`)
          : fitHeadline(`Released ${fmtHours(fitted.t_h)} after the request: ${cf.actual_route_label || 'route not recorded'}`, `Released ${fmtHours(fitted.t_h)} after the request`))
        : fitHeadline(`Not released within the history window: ${histRouteTxt}`, 'Not released within the history window'),
      subtitle: S
        ? `${twoStage ? `${fmtHours(atAc.t_h)} to get the part + ${fmtHours(fitted.t_h - atAc.t_h)} to fit it = ${fmtHours(fitted.t_h)} from the request. ` : ''}Desk decisions are on top; the part moving is below. Gaps show hours passed (not to scale).`
        : `${twoStage ? `Realised: ${fmtHours(atAc.t_h)} sourcing + ${fmtHours(fitted.t_h - atAc.t_h)} fitting = ${fmtHours(fitted.t_h)} material AOG · ` : ''}Each step in order, split into desk decisions and physical movement · same-hour steps share a bracket · gaps show elapsed hours (not to scale)`,
      provenance: prov, source: 'aog_lab.json',
      table: { columns: [{ key: 'wk', label: 'Sim week', mono: true }, { key: 't_h', label: 'T+ h', num: true }, { key: 'station', label: 'Station', mono: true }, { key: 'step', label: 'Step', format: stepLabel }, { key: 'event', label: 'Event', format: plainEvent }], rows: (inc.timeline || []).map((s) => ({ ...s, wk: simWeek(s.abs_h) ?? '—' })) },
    });
    stops.push(responsive(tf.body, (w) => drawTimeline(tf.body, w, inc, slack)));
    // The full event sentences: collapsed by default so the chart, not a repeat of it, carries the story.
    const tlList = h('ol', { class: 'aog-tl list-reset' }, (inc.timeline || []).map((s, i) => h('li', { class: `aog-tl-row ${s.evidence?.context ? 'is-context' : ''} ${s === fitted ? 'is-fitted' : ''}` },
      h('span', { class: 'aog-tl-n mono' }, String(i + 1).padStart(2, '0')),
      h('span', { class: 'aog-tl-time mono' }, h('span', {}, tLabel(s.t_h)), s.abs_h != null ? h('span', { class: 'faint' }, simWeek(s.abs_h)) : null),
      h('span', { class: 'aog-tl-stn mono' }, s.station || ''),
      h('span', { class: 'aog-tl-ev' }, h('b', {}, stepLabel(s.step)), ' ', plainEvent(s.event)))));
    tf.body.after(scopeLine(), h('details', { class: 'aog-tl-details' }, h('summary', {}, icon('chevron-right'), S ? `Event log · ${fmtInt((inc.timeline || []).length)} steps, each with its record` : `Event log · ${fmtInt((inc.timeline || []).length)} steps with the record behind each`), tlList));

    // options
    const opts = (inc.options || []).slice().sort((a, b) => optState(a, rec).order - optState(b, rec).order || (a.rank ?? 99) - (b.rank ?? 99) || String(a.key).localeCompare(String(b.key)));
    const mNote = missedNote(inc, rec, slack);
    // wave 4: when EVERY feasible option misses (e.g. D0 with 0 h slack) that is one structural fact: one banner, and the
    // per-card deadline cells turn neutral ("+9 h past D0") instead of four red MISSED pills
    const feasAll = opts.filter((o) => o.feasible && !o.human_decision && o.wait_h != null);
    const noneMeets = feasAll.length > 0 && feasAll.every((o) => !o.deadline_met);
    const optCards = opts.map((o) => optionCard(o, rec, inc, codes, optLabel, slack, o === rec && !noneMeets ? mNote : null, noneMeets));
    const okCards = optCards.filter((c, i) => optState(opts[i], rec).group === 'ok');
    const naCards = optCards.filter((c, i) => optState(opts[i], rec).group === 'na');
    const feas = opts.filter((o) => o.feasible && o.exposure_aed != null && !o.human_decision);
    const runner = feas.filter((o) => o !== rec).sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))[0];
    const exCard = h('section', { class: 'card span-12' });
    const allMeet = rec && runner && rec.deadline_met && feas.filter((o) => o !== rec).every((o) => o.deadline_met) && slack > 0;
    const lc = (t) => (S ? t.charAt(0).toLowerCase() + t.slice(1) : t.toLowerCase());
    const ef = chartFrame(exCard, {
      implication: S ? 'Rank the routes by total cost, including the grounded hours, not by freight cost alone.' : 'Rank sourcing routes by total shortage exposure, not by freight cost alone.',
      headline: S ? (allMeet
        ? fitHeadline(`Every route that could work arrives in time; ${lc(optLabel(rec))} costs ${fmtMoneyFine(runner.exposure_aed - rec.exposure_aed)} less`, 'Every route arrives in time; the cheapest wins')
        : rec
          ? fitHeadline(`${optLabel(rec)} has the lowest total cost: ${fmtMoneyFine(rec.exposure_aed)}${runner ? ` against ${fmtMoneyFine(runner.exposure_aed)} next best` : ''}`, `${optLabel(rec)}: lowest total cost, ${fmtMoneyFine(rec.exposure_aed)}`, `Lowest total cost: ${fmtMoneyFine(rec.exposure_aed)}`)
          : 'No route could work at the time of the request')
      : allMeet
        // every feasible option lands inside the slack, so none is AOG: exposure (= direct cost) is the tie-breaker
        ? fitHeadline(`${feas.length === 2 ? 'Both' : `All ${fmtInt(feas.length)}`} feasible options land inside the ${fmtHours(slack)} ${inc.deadline} slack; ${optLabel(rec).toLowerCase()} costs ${fmtMoneyFine(runner.exposure_aed - rec.exposure_aed)} less`,
          `${feas.length === 2 ? 'Both' : `All ${fmtInt(feas.length)}`} feasible options beat the ${fmtHours(slack)} ${inc.deadline} slack; ${optLabel(rec).toLowerCase()} is ${fmtMoneyFine(runner.exposure_aed - rec.exposure_aed)} cheaper`,
          `All feasible options beat the ${fmtHours(slack)} slack; the cheapest wins`)
        : rec
        ? fitHeadline(`${optLabel(rec)} has the lowest exposure: ${fmtMoneyFine(rec.exposure_aed)}${runner ? ` against ${fmtMoneyFine(runner.exposure_aed)} for ${optLabel(runner).toLowerCase()}` : ''}`,
          runner ? `${optLabel(rec)} has the lowest exposure: ${fmtMoneyFine(rec.exposure_aed)} vs ${fmtMoneyFine(runner.exposure_aed)} next best` : null,
          `${optLabel(rec)} has the lowest exposure: ${fmtMoneyFine(rec.exposure_aed)}`)
        : 'No feasible option at the time of the request',
      subtitle: S ? `Total cost = hours grounded past the deadline × assumed hourly cost + the route's own cost (AED) · estimated at the time of the request · dashed = not available` : `${allMeet ? 'No feasible option is AOG, so exposure is the direct cost alone · ' : ''}Exposure = hours beyond the ${slack != null ? `${fmtHours(slack)} ` : ''}deadline slack × AOG penalty + direct cost (AED) · ex-ante estimate at request time · dashed = not available`,
      provenance: prov, source: 'aog_lab.json',
      table: { columns: [{ key: 'option', label: 'Option' }, { key: 'feasible', label: 'Feasible', format: (v) => (v ? 'yes' : 'no') }, { key: 'wait_h', label: 'Wait', num: true, format: fmtHours }, { key: 'direct_cost', label: 'Direct cost', num: true, format: (v) => fmtAEDfull(v) }, { key: 'exposure_aed', label: S ? 'Total cost' : 'Exposure', num: true, format: (v) => fmtAEDfull(v) }, { key: 'rank', label: 'Rank', num: true, format: (v) => (v == null ? '—' : v) }], rows: opts.map((o) => ({ ...o, option: optLabel(o) })) },
    });
    stops.push(responsive(ef.body, (w) => drawExposure(ef.body, w, opts, rec, optLabel, S)));

    // human decision panel
    const d = inc.decision || {};
    const robbery = opts.find((o) => o.human_decision);
    const nFeas = feas.length;
    const plainWhy = rec ? [
      `${optLabel(rec)} has the lowest total cost of the ${fmtInt(nFeas)} ${nFeas === 1 ? 'route' : 'routes'} that could work.`,
      rec.wait_h != null ? ` The part would arrive in about ${fmtHours(rec.wait_h)}${rec.aog_h != null ? `, and the plane would be grounded for about ${fmtHours(rec.aog_h)}` : ''}.` : '',
      rec.exposure_aed != null ? ` Total cost: about ${fmtMoneyFine(rec.exposure_aed)}.` : '',
      runner ? ` Next best: ${lc(optLabel(runner))} (${runner.wait_h != null ? `${fmtHours(runner.wait_h)}, ` : ''}${fmtMoneyFine(runner.exposure_aed)}).` : '',
    ].join('') : null;
    const recName = rec ? (S ? optLabel(rec) : recTitle(d.recommended_label || optLabel(rec), d.source || rec.source)) : null;
    const human = card({
      cls: 'span-7 aog-human', bp: true, kicker: S ? 'A person decides' : 'Human decision required', title: rec ? `Recommend: ${recName}` : 'No feasible option to recommend', prov, story: 'aog-decision',
      body: h('div', { class: 'stack-3' },
        S ? h('p', { class: 'aog-why m-0' }, plainWhy || 'No route could work at the time.')
          : h('p', { class: 'aog-why m-0' }, d.why ? tidyProse(d.why).replace(/expected material-related downtime ([\d.,]+ h)/, 'expected $1 of material AOG (ex-ante estimate)').replace(/exposure (AED [\d.,]+k?M?)/, 'ex-ante exposure $1') : 'No reasoning exported.'),
        h('div', {}, h('div', { class: 'card-kicker mb-1' }, S ? 'What a person must check first' : 'What a human must check before acting'),
          h('ul', { class: 'aog-checks list-reset' }, (d.checks || []).map((c) => h('li', {}, icon('check'), h('span', {}, plainCheck(c)))))),
        h('p', { class: 't-12 faint m-0' }, S ? 'The lab helps the parts desk. It is not an approved maintenance or safety tool.' : 'The lab supports the AOG desk. It is not an approved maintenance, airworthiness or dispatch tool.')),
    });
    const optsWrap = card({
      cls: 'span-12', kicker: S ? `${fmtInt(opts.length)} routes · ${fmtInt(okCards.length)} could work` : `${fmtInt(opts.length)} sourcing routes · ${fmtInt(okCards.length)} feasible`, title: S ? 'Every route the parts desk could have taken' : 'Every sourcing route the desk could have taken', prov, story: 'aog-options',
      body: h('div', { class: 'stack-3' },
        noneMeets ? h('div', { class: 'aog-nomeet', role: 'note', dataset: { role: 'none-meets' } }, icon('alert'), h('span', {}, h('b', {}, S ? 'No route can meet the deadline. ' : `No option can meet ${inc.deadline || 'the deadline'}. `),
          S ? (!slack ? 'The plane is grounded from the moment the part comes off, so every route is late. They are ranked by total cost.' : `No route arrives within the ${fmtHours(slack)} allowed, so some grounded time is unavoidable. They are ranked by total cost.`)
            : !slack ? 'The aircraft is AOG from removal (0 h slack), so every route misses; the options are ranked by exposure.' : `No route arrives within the ${fmtHours(slack)} slack, so some AOG is unavoidable; the options are ranked by exposure.`)) : null,
        h('div', { class: 'aog-optgroup', dataset: { group: 'feasible' } },
          h('div', { class: 'aog-optgroup-head' }, h('h4', {}, `${S ? 'Could work' : 'Feasible'} (${fmtInt(okCards.length)})`), h('span', { class: 't-12 faint' }, okCards.length ? (S ? 'Ranked by total cost: grounded hours past the deadline, plus the route cost.' : 'Ranked by exposure: hours beyond the deadline slack × AOG penalty + direct cost.') : (S ? 'No route could supply a part at the time.' : 'No route could supply a unit at the time of the request.'))),
          okCards.length ? h('div', { class: 'aog-opts' }, okCards) : null),
        // phones: the unavailable routes collapse behind a summary (the page was 8,000 px tall)
        naCards.length ? h('details', { class: 'aog-optgroup aog-optgroup--na', dataset: { group: 'unavailable' }, open: innerWidth > 480 ? true : null },
          h('summary', { class: 'aog-optgroup-head' }, h('h4', {}, `Not available (${fmtInt(naCards.length)})`), h('span', { class: 't-12 faint' }, S ? 'No contract, not possible at the time, or a choice only a person can make.' : 'Not contracted, infeasible at the time, or a human decision the lab never ranks.')),
          h('div', { class: 'aog-opts' }, naCards)) : null),
    });

    // counterfactual for this incident
    const cfCard = counterfactualCard(inc, cf, prov, optLabel, S);
    // the robbery note sits under the counterfactual, so the two columns end together (no half-card void)
    const rn = String(d.robbery_note || '').match(/p = ([\d.]+), expected wait ([\d.]+) h, exposure AED ([\d,]+)/);
    const robCard = card({ cls: 'mt-3', kicker: S ? 'Borrowing from another of our aircraft' : 'Robbery / cannibalisation', title: 'Shown, never ranked', prov, body: h('div', { class: 'aog-robbery stack-2' },
      S ? h('p', { class: 'm-0' }, 'When nothing else is on hand at AUH, the model may use ', term('robbery', { first: true }), '. Every case needs engineering approval. The lab never ranks or recommends it, so a person must decide.')
        : h('p', { class: 'm-0' }, 'The simulation engine uses robbery automatically as the first AUH route after local stock, with engineering/quality approval flagged on every case. The AOG Lab never ranks or recommends it: here it is a human decision.'),
      d.robbery_note ? (S ? (rn ? h('p', { class: 'm-0 faint' }, `Here it would work about ${fmtPct(+rn[1], 0)} of the time, take about ${fmtHours(+rn[2])} and cost about ${fmtMoneyFine(+rn[3].replace(/,/g, ''))} in total.`) : null)
        : h('p', { class: 'm-0 faint' }, d.robbery_note)) : null,
      robbery?.evidence?.donors?.length ? h('p', { class: 'm-0 mono t-12' }, `${S ? 'Aircraft we could borrow from' : 'Donor aircraft'}: ${robbery.evidence.donors.map((x) => (typeof x === 'string' ? x : `${x.tail || x.aircraft || ''} ${x.status || ''}`.trim())).join(', ')}`) : null,
      h('ul', { class: 'aog-checks list-reset' }, (d.robbery_checks || []).map((c) => h('li', {}, icon('shield'), h('span', {}, plainCheck(c)))))) });

    head.classList.add('mb-3');
    incWrap.append(head, tlCard);
    host.replaceChildren(
      h('div', { class: 'grid-12' }, incWrap, exCard),
      h('div', { class: 'grid-12 mt-3' }, optsWrap),
      h('div', { class: 'grid-12 mt-3' }, human, h('div', { class: 'span-5 aog-side' }, cfCard, robCard)),
    );
    // first load: the incident charts draw in (slow); switching incidents cross-fades the new one in (base)
    enter(host, drawnOnce ? 'base' : 'slow');
    drawnOnce = true;
  }

  // ---- network-wide counterfactual summary (all requests)
  function drawSummary() {
    const S = A.summary || A.counterfactual_summary || null;
    const C = S?.counterfactual || S;
    if (!C || C.actual_request_aog_h == null) {
      summaryHost.replaceChildren(card({ kicker: S ? 'What if · all requests' : 'Counterfactual · all requests', title: 'History versus the best feasible option', prov, body: h('p', { class: 'muted m-0' }, 'The network-wide counterfactual summary is not in this export (not run).') }));
      return;
    }
    const sc = h('section', { class: 'card span-7' });
    const rows = [
      { key: 'actual', label: S ? 'History (route taken)' : 'History (route taken)', value: C.actual_request_aog_h, ex: C.actual_exposure_aed },
      { key: 'post', label: S ? 'Best route, checked afterwards' : 'Best option, scored ex post', value: C.best_option_request_aog_h, ex: C.best_option_exposure_aed, hi: true },
      { key: 'ante', label: S ? 'Best route, estimated at the time' : 'Best option, ex-ante estimate', value: C.best_option_request_aog_h_ex_ante, ex: C.best_option_exposure_aed_ex_ante },
    ].filter((r) => r.value != null);
    const saved = C.actual_request_aog_h - C.best_option_request_aog_h;
    const fr = chartFrame(sc, {
      implication: S ? 'The desk already picks close to the best route. The bigger lever is putting spares in the right place before they are needed.' : 'Per-incident response is already close to the best route; the remaining lever is positioning stock before the need.',
      headline: S ? (saved > 0
        ? fitHeadline(`The best route each time would have cut grounded hours from ${fmtHours(C.actual_request_aog_h)} to ${fmtHours(C.best_option_request_aog_h)}`, `Best route: ${fmtHours(C.actual_request_aog_h)} → ${fmtHours(C.best_option_request_aog_h)} grounded`)
        : fitHeadline(`History matched or beat the best route: ${fmtHours(C.actual_request_aog_h)} grounded in total`, 'History matched the best route'))
      : saved > 0
        ? fitHeadline(`Taking the best feasible option at request time would have cut request-level AOG from ${fmtHours(C.actual_request_aog_h)} to ${fmtHours(C.best_option_request_aog_h)}${C.net_exposure_saving_aed != null ? `, ${fmtAED(C.net_exposure_saving_aed)} less exposure` : ''}`,
          `The best feasible option would have cut request-level AOG from ${fmtHours(C.actual_request_aog_h)} to ${fmtHours(C.best_option_request_aog_h)}`,
          `Best option: request-level AOG ${fmtHours(C.actual_request_aog_h)} → ${fmtHours(C.best_option_request_aog_h)}`)
        : fitHeadline(`History matched or beat the best feasible option: ${fmtHours(C.actual_request_aog_h)} of request-level AOG`, 'History matched the best feasible option'),
      subtitle: S ? `${fmtInt(C.requests_compared)} requests · history weeks 0–103 under the ${displayName('P0', { mode: 'short' })} · grounded hours per request · total cost in AED` : `${fmtInt(C.requests_compared)} requests · history weeks 0–103 under P0 · AOG hours before merging per incident · exposure in AED`,
      provenance: prov, source: 'aog_lab.json',
      table: { columns: [{ key: 'label', label: 'Basis' }, { key: 'value', label: S ? 'Hours grounded' : 'AOG h', num: true, format: fmtHours }, { key: 'ex', label: S ? 'Total cost' : 'Exposure', num: true, format: (v) => fmtAED(v) }], rows },
    });
    stops2.push(responsive(fr.body, (w) => {
      const d3 = window.d3;
      const narrow = w < 520, lw = narrow ? 0 : 210, rowH = narrow ? 46 : 38, H = rows.length * rowH + 8;
      const svg = svgIn(fr.body, w, H, 'Counterfactual AOG hours');
      const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.value) * 1.05]).range([0, Math.max(40, w - lw - 150)]);
      rows.forEach((r, i) => {
        const y = i * rowH + (narrow ? 16 : 8);
        svg.append('text').attr('class', r.hi ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', narrow ? y - 4 : y + 11).text(r.label);
        svg.append('rect').attr('x', lw).attr('y', y + (narrow ? 2 : 2)).attr('height', 14).attr('rx', 2).attr('width', Math.max(1, x(r.value))).attr('fill', r.hi ? theme.color.accent : theme.color.neutral).attr('fill-opacity', r.key === 'ante' ? 0.6 : 0.95);
        svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', lw + x(r.value) + 8).attr('y', y + 13).text(`${fmtHours(r.value)} · ${fmtMoney(r.ex)}`);
      });
    }));
    // the footnote is HTML under the chart (it wraps at 390 px instead of running off the SVG)
    fr.body.after(...[saved > 0 ? h('p', { class: 'aog-cf-foot t-12 m-0' }, S ? `${fmtHours(saved)} fewer grounded hours over two simulated years, checked afterwards.` : `${fmtHours(saved)} fewer AOG hours over two simulated years, scored ex post.`) : null, scopeLine()].filter(Boolean));
    const n = C.requests_compared;
    const cav = card({
      cls: 'span-5', kicker: 'Honest caveats', title: S ? 'How to read this what-if' : 'How to read this counterfactual', prov,
      body: h('div', { class: 'stack-3' },
        h('dl', { class: 'meta-list' },
          h('dt', {}, S ? 'Best route taken' : 'Best option taken'), h('dd', {}, C.history_took_best_option != null ? `${fmtInt(C.history_took_best_option)} of ${fmtInt(n)} requests (${fmtPct(C.history_took_best_option / n, 0)})` : 'not run'),
          h('dt', {}, 'History did better'), h('dd', {}, C.requests_where_history_beat_estimate != null ? `${fmtInt(C.requests_where_history_beat_estimate)} requests` : 'not run'),
          S ? null : h('dt', {}, 'Scoring basis'), S ? null : h('dd', {}, C.realised_basis_counts ? Object.entries(C.realised_basis_counts).map(([k, v]) => `${fmtInt(v)} ${BASIS_SHORT[k] || fmtEnum(k).toLowerCase()}`).join(' · ') : 'not run')),
        S ? h('ul', { class: 'aog-caveats' },
          h('li', {}, 'The routes are estimates made at the time, from quoted figures. Quoted repair and order dates are often wrong in this model.'),
          h('li', {}, 'Some routes were never used in history, such as rushed repair and the parts pool. They keep their estimate.'),
          h('li', {}, '“Wait for a part on its way” queues behind earlier requests. The model may have handed out parts differently.'),
          h('li', {}, 'Grounded hours include fitting and release, after the part reaches the aircraft. The route waits on the cards cover finding and shipping the part only.'),
          h('li', {}, 'The parts pool is shown for reference only. There was no pool contract under the Simple Rulebook.'))
        : h('ul', { class: 'aog-caveats' },
          h('li', {}, 'Options are ex-ante estimates built on quoted figures. Quoted repair and purchase dates are unreliable in this world, and expedite lead times are a cap, not a supplier quote.'),
          h('li', {}, 'Accelerated repair, expedite and pool were not taken in history, so they keep their estimate; they cannot be realised from the record.'),
          h('li', {}, '“Await inbound” queues behind earlier unfilled requests network-wide; the engine may have allocated units differently.'),
          h('li', {}, 'Material AOG runs from removal (or the end of the rectification window) to release to service, overnight hours included, so it includes the fitting / release-to-service hours after the part reaches the aircraft (V2-SIM-7). Route waits in the options are sourcing and transport only. Pool exchange is shown for reference only: no contract existed under P0.'))),
    });
    summaryHost.replaceChildren(h('div', { class: 'grid-12' }, sc, cav));
    enter(summaryHost, 'slow');
  }
  let stops2 = [];
  draw();
  drawSummary();
  return () => { stops.forEach((s) => s()); stops2.forEach((s) => s()); };
}

// ----------------------------------------------------------------------------- pieces
function optionCard(o, rec, inc, codes, optLabel, slack, note, noneMeets = false) {
  const st = optState(o, rec);
  const S = isSimple();
  const metric = (k, v, extra) => h('div', { class: 'aog-m' }, h('dt', {}, k), h('dd', { class: 'num' }, v, extra || null));
  const late = o.wait_h != null ? o.wait_h - (slack || 0) : null;
  const met = o.human_decision ? h('span', { class: 'faint' }, 'n/a') : o.wait_h == null ? h('span', { class: 'faint' }, '—') : o.deadline_met ? pill('ok', 'Met')
    : noneMeets ? h('span', { class: 'aog-late mono', title: 'Every option misses this deadline (see the note above)' }, `+${fmtHours(Math.max(0, late))} late`) : pill('urgent', 'Missed');
  // wave 5: when every option misses, "wait exceeds the deadline slack" is said once (banner + the top card), not per card
  const rc = (o.reason_codes || []).filter((c) => !(noneMeets && c === 'EXCEEDS_DEADLINE' && o !== rec && o.feasible)).map((c) => { const t = reasonText(c, codes); return h('li', { title: c, dataset: { code: c } }, h('span', { class: 'aog-code' }, reasonLabel(c)), t ? h('span', { class: 'aog-code-txt' }, t) : null); });
  return h('article', { class: `aog-opt aog-opt--${st.cls}`, dataset: { key: o.key, state: st.cls }, 'aria-label': `Option: ${optLabel(o)}` },
    h('div', { class: 'aog-opt-head' }, h('h4', { class: 'aog-opt-title' }, optLabel(o)), st.pill),
    o.human_decision ? h('p', { class: 'aog-human-note m-0' }, icon('alert'), h('span', {}, S ? 'Needs engineering/quality approval — a person decides' : 'Requires engineering/quality approval — human decision')) : null,
    st.cls === 'greyed' ? h('p', { class: 'aog-human-note aog-human-note--grey m-0' }, icon('info'), h('span', {}, S ? 'No contract: example terms shown for reference' : 'Not contracted: indicative P3 terms shown for reference')) : null,
    h('dl', { class: 'aog-metrics' },
      metric(S ? 'Part arrives in' : 'Wait', o.wait_h == null ? '—' : fmtHours(o.wait_h)),
      metric(S ? 'Route cost' : 'Cost', o.human_decision && !o.feasible ? '—' : fmtMoneyFine(o.direct_cost)),
      metric(S ? 'Total cost' : 'Exposure', o.exposure_aed == null ? '—' : fmtMoneyFine(o.exposure_aed)),
      h('div', { class: 'aog-m' }, h('dt', {}, 'Deadline'), h('dd', {}, met))),
    note ? h('p', { class: 'aog-missed-note m-0', dataset: { role: 'missed-note' } }, icon('info'), h('span', {}, note)) : null,
    o.source ? h('div', { class: 'aog-src mono t-12 faint' }, `${S ? 'From' : 'Source'}: ${o.source}${o.mode ? ` · ${fmtEnum(o.mode).toLowerCase()}` : ''}`) : null,
    rc.length ? h('ul', { class: 'aog-codes list-reset' }, rc) : null);
}

function counterfactualCard(inc, cf, prov, optLabel, S = isSimple()) {
  if (!cf || cf.actual_aog_h == null) return card({ kicker: S ? 'This grounding · what if' : 'This incident · counterfactual', title: 'History versus best option', prov, body: h('p', { class: 'muted m-0' }, 'Counterfactual not run for this incident.') });
  const better = (cf.aog_h_saving ?? 0) > 0;
  const worse = (cf.aog_h_saving ?? 0) < 0;
  // wave 5: the route is prose, so it gets a full-width left-aligned line above the numeric rows
  const histRoute = (S && ROUTE_PLAIN[cf.actual_route]) || cf.actual_route_label || cf.actual_route || '—';
  const bestRoute = (S && OPT_PLAIN[cf.best_option]) || cf.best_option_label || '—';
  const sameRoute = cf.best_option && (cf.best_option === cf.actual_option || cf.best_option === cf.actual_route || (cf.best_option === 'inbound' && /^inbound/.test(cf.actual_route || '')));
  const rows = [
    ['', 'History', S ? 'Best route' : 'Best (ex post)'],
    [S ? 'Hours grounded' : 'AOG hours', fmtHours(cf.actual_aog_h), fmtHours(cf.best_realised_aog_h ?? cf.best_aog_h)],
    [S ? 'Route cost' : 'Direct cost', fmtMoneyFine(cf.actual_direct_cost_aed), fmtMoneyFine(cf.best_realised_direct_cost_aed ?? cf.best_direct_cost_aed)],
    [S ? 'Total cost' : 'Exposure', fmtMoneyFine(cf.actual_exposure_aed), fmtMoneyFine(cf.best_realised_exposure_aed ?? cf.best_exposure_aed)],
  ];
  const verdict = S ? (better ? `The best route would have saved ${fmtHours(cf.aog_h_saving)} grounded and ${fmtAED(cf.exposure_saving_aed)} in total cost.`
    : worse ? `History did better than the estimate here, by ${fmtHours(-cf.aog_h_saving)}.`
      : 'History already took the best route; nothing to save.')
    : better ? `The best option would have saved ${fmtHours(cf.aog_h_saving)} AOG and ${fmtAED(cf.exposure_saving_aed)} of exposure.`
    : worse ? `History did better than the estimate here, by ${fmtHours(-cf.aog_h_saving)}.`
      : 'History already took the best-ranked route; nothing to save.';
  return card({
    kicker: S ? 'This grounding · what if' : 'This incident · counterfactual', title: better ? 'A better route existed' : worse ? 'History beat the estimate' : (S ? 'History matched the best route' : 'History matched the best option'), prov,
    body: h('div', { class: 'stack-3' },
      h('dl', { class: 'aog-cf-route' }, h('dt', {}, 'Route'), h('dd', {}, sameRoute ? [bestRoute, h('span', { class: 'faint' }, ' · same route in history')] : [h('span', {}, `History: ${histRoute}`), h('br'), h('span', {}, `${S ? 'Best route' : 'Best option'}: ${bestRoute}`)])),
      h('table', { class: 'data-table data-table--dense aog-cf' }, h('caption', { class: 'sr-only' }, 'History versus best option'),
        h('thead', {}, h('tr', {}, rows[0].map((c, i) => h('th', { scope: 'col', class: i ? 'is-num' : '' }, c)))),
        h('tbody', {}, rows.slice(1).map((r) => h('tr', {}, h('th', { scope: 'row' }, r[0]), h('td', { class: 'is-num' }, r[1]), h('td', { class: 'is-num' }, r[2]))))),
      cf.best_exposure_aed != null ? h('p', { class: 't-12 faint m-0', dataset: { role: 'cf-exante' } }, S ? `Estimated at the time: ${fmtHours(cf.best_aog_h)} grounded, ${fmtMoneyFine(cf.best_exposure_aed)} total cost. Checked against the record: ${fmtHours(cf.best_realised_aog_h ?? cf.best_aog_h)}, ${fmtMoneyFine(cf.best_realised_exposure_aed ?? cf.best_exposure_aed)}.` : `Ex-ante estimate at the request: ${fmtHours(cf.best_aog_h)} expected, exposure ${fmtMoneyFine(cf.best_exposure_aed)}. Scored ex post on the record: ${fmtHours(cf.best_realised_aog_h ?? cf.best_aog_h)}, ${fmtMoneyFine(cf.best_realised_exposure_aed ?? cf.best_exposure_aed)}.`) : null,
      h('p', { class: 'm-0' }, verdict),
      S ? null : h('p', { class: 't-12 faint m-0' }, `Scoring basis: ${BASIS[cf.realised_basis] || (cf.realised_basis ? fmtEnum(cf.realised_basis) : 'not recorded')}`)),
  });
}

/**
 * Two-lane swimlane on a broken (ordinal) time axis: every step gets its own slot, steps in the same hour
 * share a "T+0 h" bracket, and the gaps between brackets carry the elapsed hours. This separates the 7-steps-at-T+0
 * cluster that a linear hour axis collapses into one point. Horizontal ≥ 560 px, vertical below.
 */
function drawTimeline(body, w, inc, slack) {
  const d3 = window.d3;
  const steps = (inc.timeline || []).map((s, i) => ({ ...s, n: i + 1, lane: laneOf(s) }));
  if (!steps.length) { body.replaceChildren(h('p', { class: 'muted' }, 'No timeline exported.')); return; }
  const narrow = w < 560;
  // ordinal positions: slot = 1 unit, gap between time groups = GAP units
  const GAP = 1.2;
  const groups = [];
  steps.forEach((s) => { const g = groups.at(-1); if (g && g.t === s.t_h) g.steps.push(s); else groups.push({ t: s.t_h, steps: [s] }); });
  let pos = 0;
  groups.forEach((g, gi) => { if (gi) { g.gapFrom = pos; pos += GAP; g.gapTo = pos; } g.from = pos; g.steps.forEach((s) => { s.p = pos + 0.5; pos += 1; }); g.to = pos; });
  const total = pos;
  const aog = steps.find((s) => s.step === 'aog_start');
  const endRaw = endStepOf(inc.timeline);
  const fit = steps.find((s) => endRaw && s.step === endRaw.step);
  const aogH = aog && fit ? fit.t_h - aog.t_h : null;
  const deadlineGroup = slack != null && slack > 0 ? groups.find((g) => g.t >= slack) : null;
  const LANES = isSimple() ? ['Desk decisions', 'Part moving'] : ['Desk decisions', 'Physical movement'];
  const urgent = theme.series.urgent;
  const stepNode = (gg, s, cx, cy) => {
    const isFit = s === fit;
    const c = gg.append('g').attr('transform', `translate(${cx},${cy})`).attr('class', 'aog-sl-step').attr('tabindex', 0).attr('role', 'img')
      .attr('aria-label', `${String(s.n).padStart(2, '0')} ${stepLabel(s.step)} at ${tLabel(s.t_h)}${s.station ? `, ${s.station}` : ''}`);
    c.append('circle').attr('r', 10).attr('fill', isFit ? theme.color.accent : theme.color.panel)
      .attr('stroke', isFit ? theme.color.accent : s.evidence?.context ? theme.color.neutral : theme.series.neutral).attr('stroke-dasharray', s.evidence?.context ? '2 2' : null).attr('stroke-width', 1.25);
    c.append('text').attr('text-anchor', 'middle').attr('dy', '0.35em').attr('font-family', theme.font.mono).attr('font-size', 9).style('fill', isFit ? theme.color.bg : theme.color.text).text(String(s.n).padStart(2, '0'));
    const tipOf = () => ({ title: `${String(s.n).padStart(2, '0')} · ${stepLabel(s.step)}`, rows: [['T+', fmtHours(s.t_h)], [isSimple() ? 'Airport' : 'Station', s.station || '—']], note: plainEvent(s.event) });
    withTooltip(c, tipOf);
    // keyboard: focusing a step shows its tooltip (visible effect); blur hides it
    c.on('focus', function () { const r = this.getBoundingClientRect(); tooltip.show({ clientX: r.right, clientY: r.bottom }, tipOf()); }).on('blur', () => tooltip.hide());
    return c;
  };

  if (!narrow) {
    const m = { t: 34, r: 16, b: 40, l: 128 };
    const laneH = 64;
    const H = m.t + laneH * 2 + m.b;
    const svg = svgIn(body, w, H, `Timeline of ${inc.id}: ${steps.length} steps in two lanes`);
    const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);
    const iw = Math.max(120, w - m.l - m.r);
    const x = d3.scaleLinear().domain([0, total]).range([0, iw]);
    const laneY = (l) => l * laneH + laneH / 2 - 6;
    // lanes
    LANES.forEach((name, l) => {
      g.append('rect').attr('x', -m.l + 8).attr('y', l * laneH).attr('width', iw + m.l - 8).attr('height', laneH - 4).attr('rx', 6).attr('fill', l ? 'rgba(185,200,214,0.035)' : 'rgba(185,200,214,0.06)');
      svg.append('text').attr('class', 'gnm-label').attr('x', 18).attr('y', m.t + laneY(l)).attr('dy', '0.32em').style('fill', theme.color.muted).text(name);
    });
    // brackets (same-hour groups) + gap labels (elapsed hours)
    groups.forEach((gr, gi) => {
      const x0 = x(gr.from) + 4, x1 = x(gr.to) - 4;
      g.append('path').attr('d', `M${x0},-6V-12H${x1}V-6`).attr('fill', 'none').attr('stroke', theme.color.lineStrong);
      g.append('text').attr('class', 'gnm-label gnm-label--mono').attr('x', (x0 + x1) / 2).attr('y', -18).attr('text-anchor', 'middle').style('fill', theme.color.text)
        .text(`${tLabel(gr.t)}${gr.steps.length > 1 && x1 - x0 > 120 ? ` · ${gr.steps.length} steps` : ''}`);
      if (gi) {
        const gx = (x(gr.gapFrom) + x(gr.gapTo)) / 2, dt = gr.t - groups[gi - 1].t;
        g.append('line').attr('x1', gx).attr('x2', gx).attr('y1', -4).attr('y2', laneH * 2 - 4).attr('stroke', theme.color.lineStrong).attr('stroke-dasharray', '2 4');
        chipLabel(g, { x: gx, y: laneH - 2, text: `+${fmtHours(dt)}`, color: theme.color.muted });
      }
    });
    // deadline (D3/D10): a reference line at the start of the first group at or after the slack
    if (deadlineGroup) {
      const dx = deadlineGroup.gapFrom != null ? (x(deadlineGroup.gapFrom) + x(deadlineGroup.gapTo)) / 2 + (deadlineGroup.t === slack ? x(GAP) / 2 : 0) : x(deadlineGroup.from);
      refLine(g, { x1: dx, x2: dx, y1: -2, y2: laneH * 2 + 14 }); // labelled in the AOG caption below, which always sits beside it
    }
    // sequence path through the steps
    g.append('path').attr('d', d3.line().x((s) => x(s.p)).y((s) => laneY(s.lane)).curve(d3.curveMonotoneX)(steps)).attr('fill', 'none').attr('stroke', theme.color.lineStrong).attr('stroke-width', 1);
    // AOG interval
    if (aog && fit && fit.p >= aog.p) {
      const yb = laneH * 2 + 22;
      g.append('rect').attr('x', x(aog.p)).attr('y', yb - 4).attr('width', Math.max(4, x(fit.p) - x(aog.p))).attr('height', 6).attr('rx', 3).attr('fill', urgent).attr('fill-opacity', 0.85);
      g.append('text').attr('class', 'gnm-label gnm-label--strong').attr('x', x(aog.p) - 6).attr('y', yb).attr('dy', '0.1em').attr('text-anchor', 'end').style('fill', urgent)
        .text(isSimple() ? `Grounded ${fmtHours(aogH)}${slack === 0 ? ' · from removal, fitting included' : deadlineGroup ? ' · from the deadline (dashed), fitting included' : ''}` : `AOG ${fmtHours(aogH)}${slack === 0 ? ' · grounded from removal (D0)' : deadlineGroup ? ` · from the ${tLabel(slack)} deadline (dashed)` : ''}`);
    }
    // steps + labels (alternate above/below inside the lane when slots are tight)
    const slotW = x(1) - x(0);
    steps.forEach((s, i) => {
      const cx = x(s.p), cy = laneY(s.lane);
      stepNode(g, s, cx, cy);
      const below = slotW >= 84 || i % 2 === 0;
      g.append('text').attr('class', 'gnm-label').attr('x', cx).attr('y', below ? cy + 24 : cy - 16).attr('text-anchor', 'middle').attr('font-size', 11)
        .style('fill', s === fit ? theme.color.accent : theme.color.muted).text(truncate(stepShort(s.step), Math.max(48, slotW * (slotW < 84 ? 1.9 : 0.98))));
    });
    return;
  }

  // ---- vertical (phones): rows = steps, two lane columns, time on the left, gaps between same-hour groups
  const rowH = 30, gapH = 26, m = { t: 26, l: 50, r: 16, b: 10 };
  const ys = new Map(); let yy = 0;
  groups.forEach((gr, gi) => { if (gi) yy += gapH; gr.y0 = yy; gr.steps.forEach((s) => { ys.set(s, yy + rowH / 2); yy += rowH; }); gr.y1 = yy; });
  const H = m.t + yy + m.b;
  const svg = svgIn(body, w, H, `Timeline of ${inc.id}: ${steps.length} steps in two lanes`);
  const g = svg.append('g').attr('transform', `translate(0,${m.t})`);
  const span = w - m.l - m.r;
  const colWs = [span * 0.56, span * 0.44];
  const laneX = (l) => m.l + (l ? colWs[0] : 0);
  const colW = colWs[1];
  LANES.forEach((name, l) => {
    g.append('rect').attr('x', laneX(l) + 2).attr('y', -4).attr('width', colWs[l] - 4).attr('height', yy + 8).attr('rx', 6).attr('fill', l ? 'rgba(185,200,214,0.035)' : 'rgba(185,200,214,0.06)');
    svg.append('text').attr('class', 'gnm-label').attr('x', laneX(l) + 10).attr('y', 12).style('fill', theme.color.muted).attr('font-size', 11).text(l ? 'Movement' : 'Desk');
  });
  groups.forEach((gr, gi) => {
    g.append('path').attr('d', `M${m.l - 6},${gr.y0 + 4}H${m.l - 10}V${gr.y1 - 4}H${m.l - 6}`).attr('fill', 'none').attr('stroke', theme.color.lineStrong);
    g.append('text').attr('class', 'gnm-label gnm-label--mono').attr('x', m.l - 14).attr('y', (gr.y0 + gr.y1) / 2).attr('dy', '0.32em').attr('text-anchor', 'end').style('fill', theme.color.text).text(tLabel(gr.t).replace(' h', 'h'));
    if (gi) g.append('text').attr('class', 'gnm-label gnm-label--mono').attr('x', laneX(1)).attr('y', gr.y0 - gapH / 2).attr('dy', '0.32em').attr('text-anchor', 'middle').attr('font-size', 10).style('fill', theme.color.faint).text(`⋯ +${fmtHours(gr.t - groups[gi - 1].t)} ⋯`);
  });
  g.append('path').attr('d', d3.line().x((s) => laneX(s.lane) + 18).y((s) => ys.get(s)).curve(d3.curveMonotoneY)(steps)).attr('fill', 'none').attr('stroke', theme.color.lineStrong);
  steps.forEach((s) => {
    const cx = laneX(s.lane) + 18, cy = ys.get(s);
    stepNode(g, s, cx, cy);
    g.append('text').attr('class', 'gnm-label').attr('x', cx + 16).attr('y', cy).attr('dy', '0.32em').attr('font-size', 11).style('fill', s === fit ? theme.color.accent : theme.color.muted).text(truncate(stepShort(s.step), colWs[s.lane] - 40));
  });
  if (aog && fit && ys.get(fit) >= ys.get(aog)) {
    const xb = w - 6;
    g.append('rect').attr('x', xb - 3).attr('y', ys.get(aog) - 8).attr('width', 6).attr('height', Math.max(8, ys.get(fit) - ys.get(aog) + 16)).attr('rx', 3).attr('fill', urgent).attr('fill-opacity', 0.85);
    // label beside the start of the bar (the AOG-start row's movement cell is empty when the step is a desk step)
    g.append('text').attr('class', 'gnm-label gnm-label--strong').attr('x', xb - 8).attr('y', ys.get(aog)).attr('dy', '0.32em').attr('text-anchor', 'end').style('fill', urgent).attr('font-size', 11).text(`${isSimple() ? 'Grounded' : 'AOG'} ${fmtHours(aogH)}`);
  }
  if (deadlineGroup) {
    const dy = deadlineGroup.t === slack ? deadlineGroup.y0 - 2 : deadlineGroup.y0 - gapH / 2 + 8;
    refLine(g, { x1: m.l, x2: w - m.r, y1: dy, y2: dy, label: 'deadline', labelAt: 'start', dx: -14, dy: -4, anchor: 'end' });
  }
}

function drawExposure(body, w, opts, rec, optLabel, S = isSimple()) {
  const d3 = window.d3;
  const rows = opts.filter((o) => !o.human_decision);
  const narrow = w < 560;
  // label column sized to the longest label (cap 360 px at >= 900 px); labels longer than the cap wrap to two lines
  const CW = 6.9;
  const labOf = (o) => optLabel(o);
  const longest = d3.max(rows, (o) => labOf(o).length) * CW + 16;
  const cap = w >= 900 ? 360 : Math.min(300, w * 0.4);
  const lw = narrow ? 0 : Math.min(cap, longest);
  const wrapAt = Math.floor((lw - 16) / CW);
  const split = (t) => { if (narrow || t.length <= wrapAt) return [t]; const cut = t.lastIndexOf(' ', wrapAt); const k = cut > 8 ? cut : wrapAt; return [t.slice(0, k), truncate(t.slice(k).trim(), lw - 24, CW)]; };
  const twoLine = !narrow && rows.some((o) => split(labOf(o)).length > 1);
  const rowH = narrow ? 44 : twoLine ? 40 : 32;
  const H = rows.length * rowH + 8;
  const svg = svgIn(body, w, H, 'Exposure by option');
  const vals = rows.map((o) => o.exposure_aed).filter((v) => v != null);
  const x = d3.scaleLinear().domain([0, (d3.max(vals) || 1) * 1.02]).range([0, Math.max(40, w - lw - (narrow ? 150 : 200))]);
  rows.forEach((o, i) => {
    const y = i * rowH + (narrow ? 16 : 6);
    const isRec = o === rec, grey = o.indicative || o.greyed;
    const lab = labOf(o);
    const parts = narrow ? [truncate(lab, w, CW)] : split(lab);
    const tx = svg.append('text').attr('class', isRec ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', narrow ? y - 4 : y + 11 - (parts.length > 1 ? 7 : 0)).style('fill', o.feasible || grey ? null : theme.color.faint);
    parts.forEach((t, k) => tx.append('tspan').attr('x', 0).attr('dy', k ? '1.2em' : 0).text(t));
    if (o.exposure_aed == null) {
      svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).style('fill', theme.color.faint).attr('x', lw).attr('y', y + 12).text(`Not available · ${reasonLabel((o.reason_codes || [])[0])}`);
      return;
    }
    const bar = svg.append('rect').attr('x', lw).attr('y', y + 2).attr('height', 14).attr('rx', 2).attr('width', Math.max(2, x(o.exposure_aed)))
      .attr('fill', isRec ? theme.color.accent : o.feasible ? theme.color.neutral : 'transparent')
      .attr('stroke', o.feasible || isRec ? null : theme.color.neutral).attr('stroke-dasharray', o.feasible ? null : '3 2');
    withTooltip(bar, () => ({ title: optLabel(o), rows: [[S ? 'Part arrives in' : 'Wait', o.wait_h == null ? '—' : fmtHours(o.wait_h)], [S ? 'Route cost' : 'Direct cost', fmtAEDfull(o.direct_cost)], [S ? 'Total cost' : 'Exposure', fmtAEDfull(o.exposure_aed)]], note: o.feasible ? (isRec ? 'Recommended (rank 1)' : `Rank ${o.rank ?? '—'}`) : grey ? 'Not contracted (indicative)' : (S ? 'Not possible: estimate shown with its reason' : 'Infeasible: estimate shown with its reason') }));
    svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', lw + Math.max(2, x(o.exposure_aed)) + 8).attr('y', y + 13)
      .text(`${fmtMoneyFine(o.exposure_aed)} · ${o.wait_h == null ? '—' : fmtHours(o.wait_h)}${o.feasible ? '' : grey ? ' · not contracted' : S ? ' · not possible' : ' · infeasible'}`); // same words at every width (wave 5)
  });
}
