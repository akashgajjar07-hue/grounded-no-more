/**
 * 04 · Rotable & Repair — placeholder by design-system (screen agent will extend).
 * Data: rotables.json
 * Shows: lifecycle state flow (SVG with injected counts; vertical variant on narrow screens),
 * repair-order queue with overdue status, quoted vs actual TAT.
 */
import { h, pageHead, card, provChip, pill, dataTable, inlineSVG, fillLifecycle, stubNote } from '../ui.js';
import { chartFrame, dotWhiskerChart, fmtDays, fmtInt } from '../charts/theme.js';

export const data = ['rotables'];

export async function render(el, ctx) {
  const { rotables: r } = ctx.data;
  el.append(pageHead({ num: '04', eyebrow: 'Rotable & Repair', title: 'Serialised units through the repair loop', lede: 'Every serial is in exactly one state. Removed cores travel to AUH, then to the shop; repaired units return to stock, a few are condemned.', meta: [provChip('SIMULATED')] }));

  const lcHost = h('div', { class: 'bp-figure' });
  el.append(card({ bp: true, kicker: 'Lifecycle', title: 'Where the rotable fleet is right now', body: lcHost, prov: 'SIMULATED' }));
  let variant = null;
  const drawLc = async () => {
    const want = lcHost.clientWidth < 640 ? 'rotable-lifecycle-vertical.svg' : 'rotable-lifecycle.svg';
    if (want === variant) return;
    variant = want;
    const svg = await inlineSVG(want);
    fillLifecycle(svg, { counts: r.lifecycle.counts, flows: r.lifecycle.flows });
    if (lcHost.clientWidth < 640) svg.style.maxWidth = '420px';
    lcHost.replaceChildren(svg);
  };
  const ro = new ResizeObserver(drawLc);
  ro.observe(lcHost);

  const queue = dataTable({
    caption: 'Repair queue',
    columns: [
      { key: 'ro_id', label: 'RO', mono: true },
      { key: 'serial', label: 'Serial', mono: true },
      { key: 'shop', label: 'Shop', format: (v) => v.replace('_', ' ') },
      { key: 'due_h', label: 'Due', num: true, format: (v) => `W${Math.floor(v / 168)}` },
      { key: 'overdue', label: 'Status', render: (row) => (row.overdue ? pill('urgent', 'Overdue') : pill('ok', 'On time')) },
    ],
    rows: r.repair_queue, sort: { key: 'overdue', dir: 'desc' }, maxHeight: 420,
  });
  const tatCard = h('section', { class: 'card span-5' });
  el.append(h('div', { class: 'grid-12 mt-3' }, card({ cls: 'span-7', kicker: 'Repair orders', title: `${r.repair_queue.length} units in the shop pipeline`, body: queue, prov: 'SIMULATED' }), tatCard));
  const rows = r.tat.slice(0, 8).map((t) => ({ key: t.pn, label: t.pn, value: t.actual_mean_d, lo: t.quoted_d, hi: t.p90_d, highlight: t.actual_mean_d > t.quoted_d * 1.3 }));
  const f = chartFrame(tatCard, { headline: 'Actual shop turnaround runs above the vendor-quoted figure for most units', subtitle: 'Days · dot = actual mean · whisker from quoted TAT to p90 · per PN', provenance: 'SIMULATED', source: 'rotables.json', table: { columns: [{ key: 'pn', label: 'PN' }, { key: 'quoted_d', label: 'Quoted', num: true, format: fmtDays }, { key: 'actual_mean_d', label: 'Actual', num: true, format: fmtDays }, { key: 'p90_d', label: 'p90', num: true, format: fmtDays }, { key: 'n', label: 'n', num: true, format: fmtInt }], rows: r.tat } });
  dotWhiskerChart(f.body, { rows, format: fmtDays, domain: [0, Math.max(...rows.map((d) => d.hi)) + 10] });
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: float sizing, TAT distributions and the serial timeline arrive with the Rotable & Repair screen agent.')));
  return () => ro.disconnect();
}
