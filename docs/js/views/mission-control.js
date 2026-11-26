/**
 * 01 · Mission Control — landing workspace (placeholder by design-system; screen agent will extend).
 * Data: kpis.json, parts.json (ata_systems), policies.json, actions.json
 * Shows: KPI instrument tiles, the plan-view blueprint with ATA hotspots, a policy comparison
 * (dot-and-whisker) and the top of the planner inbox.
 */
import { h, pageHead, card, kpiTile, provChip, pill, icon, blueprintAircraft, stubNote, sectionTitle } from '../ui.js';
import { chartFrame, dotWhiskerChart, sparkline, fmtByUnit, fmtPct, fmtPts, fmtHours, fmtAED, fmtInt } from '../charts/theme.js';

export const data = ['kpis', 'parts', 'policies', 'actions'];

const KPI_SCALE = { immediate_fill_rate: { min: 0.9, max: 1 } };
const fmtFor = (k) => (k.id === 'open_exceptions' ? fmtInt : fmtByUnit(k.unit));
const deltaFmtFor = (k) => (k.unit === '%' ? fmtPts : fmtFor(k));

export async function render(el, ctx) {
  const { kpis, parts, policies, actions } = ctx.data;
  const byId = Object.fromEntries(kpis.kpis.map((k) => [k.id, k]));
  const tile = (id, opts = {}) => { const k = byId[id]; return k ? kpiTile(k, { format: fmtFor(k), deltaFormat: deltaFmtFor(k), sparkline, scale: KPI_SCALE[id], ...opts }) : null; };

  el.append(
    pageHead({
      num: '01', eyebrow: 'Mission Control', title: 'Spares readiness across the network',
      lede: 'How often the right part is on the shelf, how many hours aircraft wait for parts, and the capital it takes — legacy rules versus the recommended policy, Falcon Hub Airways (fictional), 52-week holdout.',
      meta: [provChip('SIMULATED'), h('span', { class: 'chip' }, `${kpis.split || 'holdout'} · 20 seeds`)],
    })
  );

  // ---------------------------------------------------------------- hero: aircraft + instruments
  const ataSys = Object.fromEntries((parts.ata_systems || []).map((a) => [a.ata, a]));
  const selected = h('div', { class: 'row-between', style: { flexWrap: 'wrap', gap: '16px' } });
  const fig = h('div', { class: 'bp-figure', style: { margin: '0 -8px' } });
  const legend = h('div', { class: 'ata-legend mt-2', role: 'group', 'aria-label': 'ATA systems' });
  const hotspotAtas = ['21', '24', '27', '29', '32', '34', '36', '49'];

  const showAta = (ata) => {
    const a = ataSys[ata] || { ata, name: '', n_parts: 0, risk: 0, n_urgent: 0 };
    const top = parts.parts.filter((p) => p.ata === ata).sort((x, y) => y.risk_score - x.risk_score)[0];
    const level = a.risk > 0.66 ? 'urgent' : a.risk > 0.33 ? 'review' : 'ok';
    selected.replaceChildren(
      h('div', { class: 'row', style: { gap: '16px' } }, h('span', { class: 'chip chip-ata mono' }, `ATA ${ata}`), h('div', {}, h('div', { class: 't-16' }, a.name), h('div', { class: 'faint t-12 mono' }, `${a.n_parts} part numbers · ${a.n_urgent ?? 0} urgent · top: ${top?.pn ?? '—'}`))),
      h('div', { class: 'row' }, pill(level, `Max risk ${fmtPct(a.risk, 0)}`), h('a', { class: 'btn btn--sm', href: ctx.buildHash('parts', { ata, pn: top?.pn }) }, 'Open parts', icon('chevron-right')))
    );
    legend.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.ata === ata)));
    ctx.setParams({ ata });
  };
  hotspotAtas.forEach((ata) => legend.append(h('button', { type: 'button', dataset: { ata }, 'aria-pressed': 'false', onclick: () => { craft?.setActive(ata); showAta(ata); } }, h('span', { class: 'ata-num' }, ata), h('span', {}, ataSys[ata]?.name || ''))));

  const hero = h(
    'div', { class: 'grid-12' },
    card({
      cls: 'span-8', bp: true, story: 'aircraft', kicker: 'Fleet schematic · plan view', title: 'Where part risk concentrates, by aircraft system', prov: 'DERIVED',
      body: [fig, h('hr', { class: 'divider', style: { margin: '8px 0 16px' } }), selected, legend],
    }),
    h('div', { class: 'span-4 stack-3', dataset: { story: 'kpis' } }, tile('immediate_fill_rate'), tile('aog_hours'), tile('open_exceptions'))
  );
  el.append(hero);
  let craft = null;
  const initial = hotspotAtas.includes(ctx.params.ata) ? ctx.params.ata : '32';
  blueprintAircraft(fig, { active: initial, onSelect: showAta }).then((c) => { craft = c; });
  showAta(initial);
  // the legend carries the system names whenever the drawing is in compact (badge) mode
  const ro = new ResizeObserver(() => (legend.hidden = fig.clientWidth >= 1000));
  ro.observe(fig);

  // ---------------------------------------------------------------- money row
  el.append(sectionTitle('Capital and cost', provChip('SIMULATED')));
  el.append(h('div', { class: 'grid-12' }, ...['spare_capital_aed', 'total_annual_cost_aed', 'expedite_cost_aed'].map((id) => h('div', { class: 'span-4' }, tile(id)))));

  // ---------------------------------------------------------------- policy comparison + inbox
  const polCard = h('section', { class: 'card span-7' });
  const P = policies.policies;
  const best = P.reduce((a, b) => (a.kpi.aog_hours.mean < b.kpi.aog_hours.mean ? a : b));
  const p0 = P.find((p) => p.policy_id === 'P0') || P[0];
  const frame = chartFrame(polCard, {
    headline: `${best.policy_id} cuts AOG hours by ${Math.round((1 - best.kpi.aog_hours.mean / p0.kpi.aog_hours.mean) * 100)}% versus legacy rules, and the intervals do not overlap`,
    subtitle: 'AOG hours per year · mean and 95% CI over paired holdout seeds · weeks 104–155',
    provenance: 'SIMULATED', source: 'policies.json',
    table: { columns: [{ key: 'policy_id', label: 'Policy' }, { key: 'label', label: 'Description' }, { key: 'mean', label: 'Mean', num: true, format: fmtHours }, { key: 'lo', label: 'CI low', num: true, format: fmtHours }, { key: 'hi', label: 'CI high', num: true, format: fmtHours }], rows: P.map((p) => ({ policy_id: p.policy_id, label: p.label, mean: p.kpi.aog_hours.mean, lo: p.kpi.aog_hours.ci_lo, hi: p.kpi.aog_hours.ci_hi })) },
  });
  dotWhiskerChart(frame.body, { rows: P.map((p) => ({ key: p.policy_id, label: `${p.policy_id} · ${p.label}`, value: p.kpi.aog_hours.mean, lo: p.kpi.aog_hours.ci_lo, hi: p.kpi.aog_hours.ci_hi, highlight: p.policy_id === best.policy_id })), format: fmtHours, domain: [0, Math.ceil(Math.max(...P.map((p) => p.kpi.aog_hours.ci_hi)) / 100) * 100] });

  const top = actions.actions.slice().sort((a, b) => ['urgent', 'review', 'info'].indexOf(a.severity) - ['urgent', 'review', 'info'].indexOf(b.severity)).slice(0, 5);
  const inbox = card({
    cls: 'span-5', kicker: 'Planner inbox', title: `${actions.actions.length} open exceptions this week`, prov: 'DERIVED',
    body: h('div', {}, top.map((a) => h('div', { class: 'inbox-item' }, pill(a.severity === 'info' ? 'info' : a.severity), h('div', {}, h('div', { class: 'inbox-title' }, a.summary), h('div', { class: 'inbox-meta' }, `${a.exception_id} · ${a.pn} · ${a.station} · due W${a.due_week}`)), h('span', { class: 'faint t-12 mono' }, a.owner.split(' ')[0])))),
    foot: [h('span', {}, 'Sorted by severity'), h('a', { class: 'card-link', href: '#/actions' }, 'Open action centre', icon('chevron-right'))],
  });
  el.append(h('div', { class: 'grid-12 mt-3' }, polCard, inbox));
  el.append(h('div', { class: 'mt-4' }, stubNote('Design-system placeholder: the Mission Control screen agent replaces this composition with the final story.')));

  return () => { ro.disconnect(); craft?.destroy(); };
}
