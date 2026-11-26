/**
 * 02 · Parts Intelligence — placeholder by design-system (screen agent will extend).
 * Data: parts.json, demand_history.json
 * Deep links: #/parts?ata=32&pn=GN-32-R014&cls=R
 * Shows: exploded ATA diagram with injected fictional PN labels, sortable parts table,
 * part drawer with a weekly demand chart.
 */
import { h, pageHead, card, provChip, pill, segmented, dataTable, drawer, inlineSVG, fillExploded, stubNote } from '../ui.js';
import { chartFrame, lineChart, fmtAED, fmtInt, fmtWeek, fmtNum } from '../charts/theme.js';

export const data = ['parts', 'demand_history'];
const ATAS = ['21', '24', '27', '29', '32', '34', '36', '49'];

export async function render(el, ctx) {
  const { parts, demand_history: dh } = ctx.data;
  let ata = ATAS.includes(ctx.params.ata) ? ctx.params.ata : '32';
  let cls = ['C', 'E', 'R'].includes(ctx.params.cls) ? ctx.params.cls : 'all';
  const sysName = (a) => parts.ata_systems.find((s) => s.ata === a)?.name || '';

  el.append(pageHead({ num: '02', eyebrow: 'Parts Intelligence', title: 'Every part number, its demand and its risk', lede: 'Demand class (Syntetos–Boylan), stock by station and a grounding-risk score for each fictional part number. Select a system on the diagram or a row in the table.', meta: [provChip('SIMULATED'), h('span', { class: 'chip' }, `${parts.parts.length} PNs`)] }));

  // ---- exploded diagram (8 cols) + system summary (4 cols)
  const figHost = h('div', { class: 'bp-figure' });
  const slotKey = h('ol', { class: 'list-reset stack-1 mt-2 slot-key' });
  const summary = h('div', { class: 'stack-3' });
  async function drawFigure() {
    const svg = await inlineSVG(`exploded-${ata}.svg`);
    const ps = parts.parts.filter((p) => p.ata === ata).sort((a, b) => b.risk_score - a.risk_score);
    const labels = [1, 2, 3, 4, 5].map((slot, i) => ({ slot, pn: ps[i]?.pn, desc: svg.querySelector(`.bp-label[data-slot="${slot}"] [data-field="desc"]`)?.textContent }));
    fillExploded(svg, labels);
    figHost.replaceChildren(svg);
    slotKey.replaceChildren(...labels.map((l) => h('li', { class: 'row t-12' }, h('span', { class: 'chip chip-mono' }, String(l.slot)), h('span', { class: 'mono' }, l.pn || '—'), h('span', { class: 'faint' }, l.desc))));
    const s = parts.ata_systems.find((x) => x.ata === ata) || {};
    summary.replaceChildren(
      h('div', {}, h('div', { class: 'card-kicker' }, `ATA ${ata}`), h('h3', { class: 't-20' }, sysName(ata))),
      h('dl', { class: 'meta-list' }, ...[['Part numbers', fmtInt(s.n_parts)], ['Urgent', fmtInt(s.n_urgent)], ['Max risk', `${Math.round((s.risk || 0) * 100)} / 100`], ['Highest-risk PN', ps[0]?.pn || '—']].flatMap(([k, v]) => [h('dt', {}, k), h('dd', { class: 'mono' }, v)])),
      ataSeg
    );
  }
  const ataSeg = h('div', { class: 'row-wrap', role: 'group', 'aria-label': 'ATA system' }, ATAS.map((a) => h('button', { class: 'btn btn--sm', type: 'button', 'aria-pressed': String(a === ata), dataset: { ata: a }, onclick: () => setAta(a) }, a)));
  const figCard = card({ cls: 'span-8', bp: true, kicker: 'Exploded schematic · fictional components · top-risk PNs injected', body: [figHost, slotKey], prov: 'SIMULATED' });
  const sumCard = card({ cls: 'span-4', kicker: 'System', body: summary, prov: 'DERIVED' });
  const mq = matchMedia('(min-width: 900px)');
  const syncKey = () => (slotKey.hidden = mq.matches);
  syncKey();
  mq.addEventListener('change', syncKey);

  // ---- table
  const risk = (p) => pill(p.risk_level, `${Math.round(p.risk_score * 100)}`);
  const columns = [
    { key: 'pn', label: 'Part number', mono: true },
    { key: 'desc', label: 'Description' },
    { key: 'cls', label: 'Class' },
    { key: 'deadline', label: 'Deadline' },
    { key: 'demand_class', label: 'Demand', format: (v) => v.replace('_', ' ') },
    { key: 'stock_total', label: 'Stock', num: true, format: fmtInt },
    { key: 'unit_cost', label: 'Unit cost', num: true, format: (v) => fmtAED(v) },
    { key: 'risk_score', label: 'Risk', num: true, render: risk },
  ];
  const rowsFor = () => parts.parts.filter((p) => p.ata === ata && (cls === 'all' || p.cls === cls));
  const table = dataTable({ columns, rows: rowsFor(), sort: { key: 'risk_score', dir: 'desc' }, onRowClick: (r) => openPart(r.pn), caption: 'Parts for the selected ATA system', maxHeight: 560 });
  const clsSeg = segmented({ label: 'Part class', value: cls, options: [{ value: 'all', label: 'All' }, { value: 'R', label: 'Rotable' }, { value: 'E', label: 'Expendable' }, { value: 'C', label: 'Consumable' }], onChange: (v) => { cls = v; table.update(rowsFor()); ctx.setParams({ cls: v === 'all' ? '' : v }); } });
  const tableCard = card({ cls: 'span-12', story: 'parts-table', kicker: 'Part master + risk', title: 'Parts in this system', actions: clsSeg, body: table, prov: 'SIMULATED' });

  el.append(h('div', { class: 'grid-12' }, figCard, sumCard));
  el.append(h('div', { class: 'grid-12 mt-3' }, tableCard));
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: filters, risk drivers and the PN deep dive arrive with the Parts Intelligence screen agent.')));

  function setAta(a) {
    ata = a;
    ataSeg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.ata === a)));
    table.update(rowsFor());
    drawFigure();
    ctx.setParams({ ata: a, pn: '' });
  }

  function openPart(pn) {
    const p = parts.parts.find((x) => x.pn === pn);
    if (!p) return;
    ctx.setParams({ pn });
    const body = h('div', { class: 'stack-3' });
    const series = (dh.series[pn] || []).map((y, x) => ({ x, y }));
    const total = series.reduce((m, d) => m + d.y, 0);
    body.append(
      h('dl', { class: 'meta-list' }, ...[['Description', p.desc], ['ATA', `${p.ata} · ${sysName(p.ata)}`], ['Class · deadline', `${p.cls} · ${p.deadline}`], ['Demand', `${p.demand_class.replace('_', ' ')} (ADI ${fmtNum(p.adi)}, CV² ${fmtNum(p.cv2)})`], ['Unit cost', fmtAED(p.unit_cost)], ['Stock', Object.entries(p.stock_by_station).filter(([, q]) => q).map(([s, q]) => `${s} ${q}`).join(' · ') || 'none']].flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]))
    );
    const chartHost = h('div');
    body.append(chartHost);
    const d = drawer({ kicker: 'Part number', title: pn, body, onClose: () => ctx.setParams({ pn: '' }) }).open();
    requestAnimationFrame(() => {
      const f = chartFrame(chartHost, { headline: `${fmtInt(total)} unit${total === 1 ? '' : 's'} demanded over 104 weeks`, subtitle: 'Units per week · weeks 0–103 (train + selection) · simulated calendar', provenance: 'SIMULATED', source: 'demand_history.json', table: { columns: [{ key: 'x', label: 'Week', format: fmtWeek }, { key: 'y', label: 'Qty', num: true }], rows: series } });
      lineChart(f.body, { series: [{ id: pn, label: 'Demand', values: series }], x: { format: fmtWeek }, y: { format: fmtInt }, height: 200 });
    });
    return d;
  }

  await drawFigure();
  if (ctx.params.pn) openPart(ctx.params.pn);
  return () => mq.removeEventListener('change', syncKey);
}
