/**
 * 08 · Planner Action Centre — placeholder by design-system (screen agent will extend).
 * Data: actions.json
 * Deep links: #/actions?severity=urgent&id=EX-1040
 * Shows: severity tabs, exception inbox, evidence drawer.
 */
import { h, pageHead, card, provChip, pill, tabs, drawer, icon, stubNote } from '../ui.js';

export const data = ['actions'];
const SEV = ['urgent', 'review', 'info'];

export async function render(el, ctx) {
  const { actions: A } = ctx.data;
  let sev = SEV.includes(ctx.params.severity) ? ctx.params.severity : 'all';
  el.append(pageHead({ num: '08', eyebrow: 'Planner Action Centre', title: 'This week’s exceptions, ranked', lede: 'Each exception carries its evidence and a recommended action with an owner and a due week. Recommendations support a planner; they do not replace engineering or airworthiness judgement.', meta: [provChip('DERIVED')] }));
  const count = (s) => A.actions.filter((a) => s === 'all' || a.severity === s).length;
  const list = h('div');
  const t = tabs({ label: 'Severity', value: sev, tabs: [{ id: 'all', label: 'All', count: count('all') }, ...SEV.map((s) => ({ id: s, label: s[0].toUpperCase() + s.slice(1), count: count(s) }))], onChange: (v) => { sev = v; ctx.setParams({ severity: v === 'all' ? '' : v }); draw(); } });
  el.append(card({ body: [t, list], prov: 'DERIVED' }));

  function open(a) {
    ctx.setParams({ id: a.exception_id });
    drawer({ kicker: a.exception_id, title: a.summary, onClose: () => ctx.setParams({ id: '' }), body: h('div', { class: 'stack-3' }, h('div', { class: 'row-wrap' }, pill(a.severity), h('span', { class: 'chip chip-mono' }, a.type)), h('dl', { class: 'meta-list' }, ...[['Part', a.pn], ['Station', a.station], ['Owner', a.owner], ['Due', `W${a.due_week}`], ['Action', a.recommended_action]].flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)])), h('div', {}, h('div', { class: 'card-kicker' }, 'Evidence'), h('pre', { class: 'mono t-12 muted', style: { whiteSpace: 'pre-wrap', margin: 0 } }, JSON.stringify(a.evidence, null, 2)))) }).open();
  }
  function draw() {
    const rows = A.actions.filter((a) => sev === 'all' || a.severity === sev);
    list.replaceChildren(...rows.map((a) => h('div', { class: 'inbox-item', role: 'button', tabindex: '0', style: { cursor: 'pointer' }, onclick: () => open(a), onkeydown: (e) => { if (e.key === 'Enter') open(a); } }, pill(a.severity), h('div', {}, h('div', { class: 'inbox-title' }, a.summary), h('div', { class: 'inbox-meta' }, `${a.exception_id} · ${a.pn} · ${a.station} · ${a.recommended_action}`)), h('span', { class: 'row faint t-12 mono' }, `W${a.due_week}`, icon('chevron-right')))));
  }
  draw();
  const deep = A.actions.find((a) => a.exception_id === ctx.params.id);
  if (deep) open(deep);
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: bulk triage, export and evidence charts arrive with the Planner Action Centre screen agent.')));
}
