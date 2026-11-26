/**
 * Data & Method — placeholder by design-system (docs agent will extend).
 * Data: method.json
 * Shows: provenance legend, source manifest, assumption register excerpt, validation, licences.
 */
import { h, pageHead, card, provChip, pill, dataTable, stubNote, sectionTitle } from '../ui.js';

export const data = ['method'];

export async function render(el, ctx) {
  const { method: M } = ctx.data;
  el.append(pageHead({ eyebrow: 'Reference · Data & Method', title: 'Where every number comes from', lede: 'Every value shown carries a provenance tag. Models run offline in Python; this site only loads their exported results. Falcon Hub Airways and its fleet are fictional.' }));
  const legend = [['REAL', 'Sourced from a public, cited dataset (e.g. airport coordinates).'], ['DERIVED', 'Computed in this repo from REAL or SIMULATED data.'], ['ASSUMED', 'A planning assumption chosen by the author, with a rationale.'], ['SIMULATED', 'Produced by the synthetic world generator.']];
  el.append(h('div', { class: 'grid-12' }, ...legend.map(([p, d]) => card({ cls: 'span-3', body: h('div', { class: 'stack' }, provChip(p), h('p', { class: 't-14 muted' }, d)) }))));
  el.append(sectionTitle('Sources'));
  el.append(card({ body: dataTable({ caption: 'Source manifest', columns: [{ key: 'name', label: 'Source' }, { key: 'licence', label: 'Licence' }, { key: 'used_for', label: 'Used for' }, { key: 'provenance', label: 'Provenance', render: (r) => provChip(r.provenance) }], rows: M.source_manifest, bare: true }) }));
  el.append(sectionTitle('Assumptions (excerpt)'));
  el.append(card({ body: dataTable({ caption: 'Assumptions', columns: [{ key: 'key', label: 'Key', mono: true }, { key: 'value', label: 'Value', mono: true }, { key: 'provenance', label: 'Tag', render: (r) => provChip(r.provenance) }, { key: 'rationale', label: 'Rationale' }], rows: M.assumptions, bare: true }) }));
  el.append(sectionTitle('Validation and licences'));
  el.append(h('div', { class: 'grid-12' },
    card({ cls: 'span-6', title: `${M.validation.tests_passed} / ${M.validation.tests_total} tests passed`, body: h('div', { class: 'stack-1' }, M.validation.checks.map((c) => h('div', { class: 'row' }, pill(c.status === 'pass' ? 'ok' : c.status === 'fail' ? 'urgent' : 'unknown', c.status), h('span', { class: 't-14' }, c.name)))) }),
    card({ cls: 'span-6', title: 'Third-party licences', body: dataTable({ caption: 'Licences', columns: [{ key: 'name', label: 'Package' }, { key: 'version', label: 'Version', mono: true }, { key: 'licence', label: 'Licence' }], rows: M.licences, bare: true, dense: true }) })
  ));
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: full methodology, limitations and the assumption register arrive with the docs agent.')));
}
