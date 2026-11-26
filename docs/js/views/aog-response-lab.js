/**
 * 07 · AOG Response Lab — placeholder by design-system (screen agent will extend).
 * Data: aog_lab.json
 * Deep links: #/aog?incident=AOG-0193
 * Shows: incident picker, response timeline, sourcing options with feasibility and exposure.
 */
import { h, pageHead, card, provChip, pill, segmented, dataTable, stubNote } from '../ui.js';
import { fmtAED, fmtHours } from '../charts/theme.js';

export const data = ['aog_lab'];

export async function render(el, ctx) {
  const { aog_lab: A } = ctx.data;
  let inc = A.incidents.find((i) => i.id === ctx.params.incident) || A.incidents[0];
  el.append(pageHead({ num: '07', eyebrow: 'AOG Response Lab', title: 'An aircraft is waiting. What are the options?', lede: 'Sourcing options for a grounding, with wait time, direct cost and AOG exposure. Deadline classes are hypothetical simulation categories, not MEL categories.', meta: [provChip('SIMULATED')] }));
  const host = h('div');
  el.append(h('div', { class: 'mb-3' }, segmented({ label: 'Incident', value: inc.id, options: A.incidents.map((i) => ({ value: i.id, label: `${i.id} · ${i.station}` })), onChange: (v) => { inc = A.incidents.find((i) => i.id === v); ctx.setParams({ incident: v }); draw(); } })), host);

  function draw() {
    const best = inc.options.filter((o) => o.feasible).sort((a, b) => a.direct_cost + a.exposure_aed - (b.direct_cost + b.exposure_aed))[0];
    const timeline = h('ol', { class: 'list-reset stack-1' }, inc.timeline.map((t) => h('li', { class: 'row', style: { gap: '16px' } }, h('span', { class: 'mono faint', style: { width: '56px' } }, `T+${t.t_h}h`), h('span', { style: { width: '8px', height: '8px', borderRadius: '50%', border: '1.5px solid var(--primary)' } }), h('span', { class: 't-14' }, t.event))));
    host.replaceChildren(
      h('div', { class: 'grid-12' },
        card({ cls: 'span-4', bp: true, kicker: `${inc.tail} (fictional) · ${inc.station}`, title: `${inc.pn} · ${inc.desc}`, prov: 'SIMULATED', body: h('div', { class: 'stack-3' }, h('div', { class: 'row-wrap' }, pill(inc.deadline === 'D0' ? 'urgent' : 'review', `Deadline ${inc.deadline}`), h('span', { class: 'chip' }, inc.archetype)), timeline) }),
        card({ cls: 'span-8', kicker: 'Options', title: best ? `Best feasible option: ${best.option}` : 'No feasible option', prov: 'SIMULATED', body: dataTable({ caption: 'Sourcing options', columns: [{ key: 'option', label: 'Option' }, { key: 'feasible', label: 'Feasible', render: (o) => (o.feasible ? pill('ok', 'Yes') : pill('urgent', 'No')) }, { key: 'wait_h', label: 'Wait', num: true, format: fmtHours }, { key: 'direct_cost', label: 'Direct cost', num: true, format: (v) => fmtAED(v) }, { key: 'exposure_aed', label: 'AOG exposure', num: true, format: (v) => fmtAED(v) }, { key: 'deadline_met', label: 'Deadline', render: (o) => (o.deadline_met ? pill('ok', 'Met') : pill('review', 'Missed')) }, { key: 'reason_codes', label: 'Reasons', render: (o) => h('span', { class: 'mono faint t-12' }, o.reason_codes.join(', ')) }], rows: inc.options }) })
      )
    );
  }
  draw();
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: interactive what-if, cost waterfall and policy replay arrive with the AOG Response Lab screen agent.')));
}
