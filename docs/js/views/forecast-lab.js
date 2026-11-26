/**
 * 03 · Forecast Lab — placeholder by design-system (screen agent will extend).
 * Data: forecast.json, demand_history.json
 * Deep links: #/forecast?class=lumpy&part=R
 * Shows: MASE dot-and-whisker by method for one demand class, leaderboard table, champions,
 * truth-recovery tiles and the Monash benchmark status.
 */
import { h, pageHead, card, provChip, segmented, dataTable, pill, stubNote, sectionTitle } from '../ui.js';
import { chartFrame, dotWhiskerChart, fmtNum, fmtPct } from '../charts/theme.js';

export const data = ['forecast'];
const CLASSES = ['smooth', 'erratic', 'intermittent', 'lumpy'];

export async function render(el, ctx) {
  const { forecast: f } = ctx.data;
  let dc = CLASSES.includes(ctx.params.class) ? ctx.params.class : 'lumpy';
  let pc = ['C', 'E', 'R'].includes(ctx.params.part) ? ctx.params.part : 'R';

  el.append(pageHead({ num: '03', eyebrow: 'Forecast Lab', title: 'Which forecasting method wins, for which kind of demand', lede: 'Rolling-origin evaluation on weeks 78–103 (origins every 4 weeks, 4-week horizon). Lower MASE is better; below 1.0 beats the naive benchmark.', meta: [provChip('DERIVED')] }));

  const controls = h('div', { class: 'row-wrap gap-2 mb-3' },
    segmented({ label: 'Demand class', value: dc, options: CLASSES.map((c) => ({ value: c, label: c })), onChange: (v) => { dc = v; ctx.setParams({ class: v }); draw(); } }),
    segmented({ label: 'Part class', value: pc, options: [{ value: 'R', label: 'Rotable' }, { value: 'E', label: 'Expendable' }, { value: 'C', label: 'Consumable' }], onChange: (v) => { pc = v; ctx.setParams({ part: v }); draw(); } })
  );
  el.append(controls);

  const chartCard = h('section', { class: 'card span-7' });
  const tableHost = h('div');
  el.append(h('div', { class: 'grid-12' }, chartCard, card({ cls: 'span-5', kicker: 'Leaderboard', title: 'All methods, this segment', body: tableHost, prov: 'DERIVED' })));

  function draw() {
    const rows = f.leaderboard.filter((r) => r.demand_class === dc && r.part_class === pc).sort((a, b) => a.mase - b.mase);
    const champ = rows[0];
    chartCard.replaceChildren();
    const frame = chartFrame(chartCard, {
      headline: `${champ.method} is the champion for ${dc} ${pc === 'R' ? 'rotables' : pc === 'E' ? 'expendables' : 'consumables'} (MASE ${fmtNum(champ.mase)})`,
      subtitle: 'MASE · mean and 95% CI across rolling origins · lower is better · dashed line = naive benchmark (1.0)',
      provenance: 'DERIVED', source: 'forecast.json',
      table: { columns: [{ key: 'method', label: 'Method' }, { key: 'mase', label: 'MASE', num: true, format: (v) => fmtNum(v) }, { key: 'bias', label: 'Bias', num: true, format: (v) => fmtNum(v) }, { key: 'coverage', label: '80% PI coverage', num: true, format: (v) => fmtPct(v, 0) }], rows },
    });
    dotWhiskerChart(frame.body, { rows: rows.map((r) => ({ key: r.method.split(' ')[0], label: r.method, value: r.mase, lo: r.mase_ci[0], hi: r.mase_ci[1], highlight: r === champ })), format: (v) => fmtNum(v), refValue: 1, refLabel: 'naive = 1.0' });
    tableHost.replaceChildren(dataTable({ columns: [{ key: 'method', label: 'Method' }, { key: 'mase', label: 'MASE', num: true, format: (v) => fmtNum(v) }, { key: 'coverage', label: 'Cover', num: true, format: (v) => fmtPct(v, 0) }, { key: 'n', label: 'n', num: true }], rows, sort: { key: 'mase', dir: 'asc' }, dense: true, bare: true, caption: 'Leaderboard' }));
  }
  draw();

  el.append(sectionTitle('Truth recovery', provChip('DERIVED')));
  el.append(h('div', { class: 'grid-12' }, ...f.truth_recovery.map((t) => card({ cls: 'span-4', kicker: t.metric, title: t.param, body: h('div', { class: 'row-between mt-2' }, h('div', {}, h('div', { class: 'kpi-label' }, 'Estimated'), h('div', { class: 't-28 num' }, fmtPct(t.estimated, 0))), h('div', { style: { textAlign: 'right' } }, h('div', { class: 'kpi-label' }, 'Vendor-quoted'), h('div', { class: 't-28 num muted' }, t.vendor_quoted == null ? '—' : fmtPct(t.vendor_quoted, 0)))) }))));
  el.append(h('div', { class: 'row mt-3' }, pill(f.monash?.status === 'not run' ? 'unknown' : 'ok', `Monash benchmark: ${f.monash?.status || 'n/a'}`), h('span', { class: 'faint t-12' }, f.monash?.reason || '')));
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: forecast fan charts, lead-time-demand distributions and champion stock impact arrive with the Forecast Lab screen agent.')));
}
