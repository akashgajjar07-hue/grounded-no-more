/**
 * Parts Intelligence · v2.1 flags shared with Rotable & Repair.
 *  - A7 escalationBlock(part): the escalation text for a part flagged in parts.json (`parts[].escalation`, the hero part).
 *  - A9 allocationFlagNote(flags): the frozen plan's outstation brake units, kept in the numbers and flagged with
 *    `invalid_allocation_text` ("invalid recommendation — brakes are not changed outside the hub in this model").
 * Every string comes from parts.json; nothing is typed here except labels.
 */
import { h, icon } from '../../ui.js';
import { byMode, isSimple } from '../../lib/mode.js';
import { nameTag, displayName } from '../../lib/names.js';

/** Flags for one plan at one station. */
export const flagsAt = (flags, policy, station) => (flags || []).filter((f) => f.policy === policy && f.station === station);

/**
 * The A7 escalation callout. opts.compact: smaller (side panel); opts.onOpen: adds an "Open the part" button.
 * → section.pi-escalation[data-role=escalation] with p[data-role=escalation-text] holding the exported text verbatim.
 */
export function escalationBlock(part, { compact = false, onOpen } = {}) {
  const e = part?.escalation;
  if (!e?.text) return null;
  const basis = [
    e.estimated_ratio != null ? `History estimate ${Number(e.estimated_ratio).toFixed(1)}× (${e.quoted_multiple_basis || 'quoted / history-based MTBUR'})` : null,
    e.threshold != null ? `rule: escalate at ≥ ${e.threshold}×` : null,
    e.true_multiple_evaluation_only != null ? `planted multiple ${e.true_multiple_evaluation_only}× (evaluation only)` : null,
  ].filter(Boolean).join(' · ');
  return h('section', { class: `pi-escalation${compact ? ' is-compact' : ''}`, role: 'note', 'aria-label': `Escalate first: ${part.pn}`, dataset: { role: 'escalation', pn: part.pn } },
    icon('alert'),
    h('div', { class: 'pi-escalation-main' },
      h('div', { class: 'pi-escalation-k' }, h('span', {}, byMode('Escalate first', 'Escalation · reliability and warranty')), h('span', { class: 'mono' }, part.pn), part.desc ? h('span', { class: 'pi-escalation-desc' }, part.desc) : null),
      h('p', { class: 'pi-escalation-text', dataset: { role: 'escalation-text' } }, e.text),
      basis ? h('p', { class: 'pi-escalation-basis expert-only' }, basis) : null,
      onOpen ? h('button', { type: 'button', class: 'btn btn--sm pi-escalation-open', onclick: onOpen }, byMode('Open the part', 'Open the drill-down'), icon('chevron-right')) : null));
}

/**
 * The A9 note listing flagged allocations, grouped by plan then part: "Network Plan: GN-32-R013 at BOM, CAI, JED".
 * → div.pi-alloc-flags[data-role=invalid-allocations]
 */
export function allocationFlagNote(flags, { text, compact = false } = {}) {
  const list = (flags || []).filter((f) => f && f.flag === 'invalid_recommendation');
  if (!list.length) return null;
  const msg = text || list[0].text;
  const byPolicy = new Map();
  list.forEach((f) => {
    if (!byPolicy.has(f.policy)) byPolicy.set(f.policy, new Map());
    const m = byPolicy.get(f.policy);
    if (!m.has(f.pn)) m.set(f.pn, []);
    m.get(f.pn).push(`${f.station}${f.units > 1 ? ` (${f.units})` : ''}`);
  });
  return h('div', { class: `pi-alloc-flags${compact ? ' is-compact' : ''}`, role: 'note', dataset: { role: 'invalid-allocations' } },
    icon('alert'),
    h('div', {},
      h('p', { class: 'pi-alloc-flags-t' }, h('strong', {}, 'Flagged: '), h('span', { dataset: { role: 'invalid-text' } }, msg), '.'),
      h('ul', { class: 'list-reset pi-alloc-flags-list' }, [...byPolicy].map(([pol, m]) => h('li', {}, isSimple() ? h('strong', { class: 'name-tag', dataset: { code: pol } }, displayName(pol)) : nameTag(pol), ': ',
        [...m].map(([pn, st], i) => [i ? ' · ' : '', h('span', { class: 'mono' }, pn), ` at ${st.join(', ')}`])))),
      h('p', { class: 'pi-alloc-flags-s' }, byMode('These spares stay in the frozen results. They are flagged, not removed.', 'Units kept in the frozen results (not re-run); flagged, not deleted.'))));
}
