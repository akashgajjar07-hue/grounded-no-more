/**
 * 06 · Capital Optimiser — placeholder by design-system (screen agent will extend).
 * Data: frontier.json
 * Deep links: #/capital?point=F12
 * Shows: capital vs AOG-hours frontier (D3, styled by the theme) with CI whiskers, baseline and
 * recommended annotations, a budget lever slider, the allocation table and a sensitivity bar list.
 */
import { h, pageHead, card, provChip, slider, dataTable, stubNote } from '../ui.js';
import { chartFrame, responsive, svgIn, axisBottom, axisLeft, gridY, annotate, directLabel, withTooltip, theme, fmtAED, fmtHours, barList } from '../charts/theme.js';

export const data = ['frontier'];

export async function render(el, ctx) {
  const { frontier: F } = ctx.data;
  const d3 = window.d3;
  const pts = F.points;
  const front = pts.filter((p) => !p.dominated).sort((a, b) => a.capital_aed - b.capital_aed);
  const base = pts.find((p) => p.id === F.baseline);
  const rec = pts.find((p) => p.id === F.recommended);
  let sel = pts.find((p) => p.id === ctx.params.point) || rec;

  el.append(pageHead({ num: '06', eyebrow: 'Capital Optimiser', title: 'Capital versus groundings: the efficient frontier', lede: 'Each dot is a stocking plan evaluated on paired seeds. The frontier is the lowest AOG hours reachable at each capital level. Capital is reported separately from annual operating cost.', meta: [provChip('SIMULATED')] }));

  const chartCard = h('section', { class: 'card span-8', dataset: { story: 'frontier' } });
  const side = h('div', { class: 'span-4 stack-3' });
  el.append(h('div', { class: 'grid-12' }, chartCard, side));
  const frame = chartFrame(chartCard, {
    headline: `The recommended plan holds ${fmtAED(base.capital_aed - rec.capital_aed)} less capital than today and cuts AOG hours by ${Math.round((1 - rec.aog_hours / base.aog_hours) * 100)}%`,
    subtitle: 'Spare capital (AED) vs AOG hours per year · 95% CI whiskers · paired holdout seeds',
    provenance: 'SIMULATED', source: 'frontier.json',
    table: { columns: [{ key: 'id', label: 'Plan', mono: true }, { key: 'kind', label: 'Kind' }, { key: 'capital_aed', label: 'Capital', num: true, format: (v) => fmtAED(v) }, { key: 'aog_hours', label: 'AOG h', num: true, format: fmtHours }], rows: pts },
  });

  let redraw = () => {};
  const stop = responsive(frame.body, (w) => {
    redraw = () => {
      const hgt = w < 480 ? 300 : 380;
      const m = { top: 24, right: w < 480 ? 16 : 32, bottom: 40, left: 56 };
      const iw = Math.max(40, w - m.left - m.right), ih = hgt - m.top - m.bottom;
      const svg = svgIn(frame.body, w, hgt, 'Capital vs AOG hours frontier');
      const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
      const x = d3.scaleLinear().domain(d3.extent(pts, (p) => p.capital_aed)).nice().range([0, iw]);
      const y = d3.scaleLinear().domain([0, d3.max(pts, (p) => p.aog_ci[1])]).nice().range([ih, 0]);
      gridY(g.append('g'), y, iw);
      axisLeft(g.append('g'), y, { format: (v) => `${v} h` });
      axisBottom(g.append('g'), x, { height: ih, ticks: w < 480 ? 3 : 6, format: (v) => fmtAED(v, { digits: 0 }) });
      // dominated candidates (neutral)
      g.selectAll('circle.dom').data(pts.filter((p) => p.dominated && p.kind === 'candidate')).join('circle').attr('class', 'dom').attr('cx', (p) => x(p.capital_aed)).attr('cy', (p) => y(p.aog_hours)).attr('r', 3).attr('fill', theme.color.neutral).attr('fill-opacity', 0.55);
      // frontier band of CIs + line
      g.append('path').datum(front).attr('fill', theme.color.accent).attr('fill-opacity', 0.1).attr('d', d3.area().x((p) => x(p.capital_aed)).y0((p) => y(p.aog_ci[0])).y1((p) => y(p.aog_ci[1])).curve(d3.curveMonotoneX));
      g.append('path').datum(front).attr('fill', 'none').attr('stroke', theme.color.accent).attr('stroke-width', 2).attr('d', d3.line().x((p) => x(p.capital_aed)).y((p) => y(p.aog_hours)).curve(d3.curveMonotoneX));
      const fp = g.selectAll('circle.fr').data(front).join('circle').attr('class', 'fr').attr('cx', (p) => x(p.capital_aed)).attr('cy', (p) => y(p.aog_hours)).attr('r', (p) => (p.id === sel.id ? 6 : 3.5)).attr('fill', (p) => (p.id === sel.id ? theme.color.accent : theme.color.bg)).attr('stroke', theme.color.accent).attr('stroke-width', 1.5).style('cursor', 'pointer');
      withTooltip(fp, (p) => ({ title: p.id, rows: [['Capital', fmtAED(p.capital_aed)], ['AOG hours', fmtHours(p.aog_hours)], ['95% CI', `${fmtHours(p.aog_ci[0])} – ${fmtHours(p.aog_ci[1])}`]] }));
      fp.on('click', (e, p) => select(p));
      // baseline (accent 2 = comparison)
      g.append('line').attr('x1', x(base.capital_aed)).attr('x2', x(base.capital_aed)).attr('y1', y(base.aog_ci[0])).attr('y2', y(base.aog_ci[1])).attr('stroke', theme.color.accent2).attr('stroke-width', 1.5);
      g.append('rect').attr('x', x(base.capital_aed) - 5).attr('y', y(base.aog_hours) - 5).attr('width', 10).attr('height', 10).attr('fill', theme.color.bg).attr('stroke', theme.color.accent2).attr('stroke-width', 2);
      directLabel(g, w < 480 ? { x: x(base.capital_aed), y: y(base.aog_ci[1]) - 10, text: 'Today (P0)', color: theme.color.accent2, anchor: 'middle', strong: true } : { x: x(base.capital_aed) - 10, y: y(base.aog_hours), text: 'Today (P0)', color: theme.color.accent2, anchor: 'end', strong: true });
      annotate(g, { x: x(rec.capital_aed), y: y(rec.aog_hours), dx: w < 480 ? 28 : -56, dy: w < 480 ? 56 : 72, title: 'Recommended', sub: `${fmtAED(rec.capital_aed)} · ${fmtHours(rec.aog_hours)}` });
      if (w >= 480) directLabel(g, { x: iw, y: ih - 8, text: 'Capital →', anchor: 'end', color: theme.color.faint });
    };
    redraw();
  });

  const readout = h('dl', { class: 'meta-list' });
  const showSel = () => readout.replaceChildren(...[['Plan', sel.id], ['Capital', fmtAED(sel.capital_aed)], ['AOG hours', fmtHours(sel.aog_hours)], ['95% CI', `${fmtHours(sel.aog_ci[0])} – ${fmtHours(sel.aog_ci[1])}`]].flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
  function select(p) { sel = p; showSel(); redraw(); ctx.setParams({ point: p.id }); }
  showSel();
  const lever = F.levers.find((l) => l.id === 'budget');
  side.append(
    card({ kicker: 'Lever', title: 'Capital budget', prov: 'ASSUMED', body: h('div', { class: 'stack-3' }, slider({ label: 'Budget', min: lever.min, max: lever.max, step: lever.step, value: sel.budget_aed, format: (v) => fmtAED(v), onInput: (v) => { const p = front.reduce((a, b) => (Math.abs(b.budget_aed - v) < Math.abs(a.budget_aed - v) ? b : a)); if (p !== sel) select(p); } }), readout) })
  );
  const tor = h('div');
  side.append(card({ kicker: 'Sensitivity', title: 'What moves the answer', prov: 'ASSUMED', body: tor }));
  barList(tor, { rows: F.tornado.map((t, i) => ({ label: t.param, value: t.high - t.low, highlight: i === 0 })), format: (v) => fmtAED(v) });

  const alloc = F.allocations[rec.id] || [];
  el.append(h('div', { class: 'mt-3' }, card({ kicker: `Allocation · ${rec.id}`, title: 'What changes in the recommended plan', prov: 'SIMULATED', body: dataTable({ caption: 'Allocation', columns: [{ key: 'pn', label: 'PN', mono: true }, { key: 'station', label: 'Station', mono: true }, { key: 'current', label: 'Now', num: true }, { key: 'proposed', label: 'Plan', num: true }, { key: 'delta_capital', label: 'Δ Capital', num: true, format: (v) => fmtAED(v, { sign: true }) }, { key: 'risk_reduction', label: 'Risk ↓ (h)', num: true }, { key: 'alt_action', label: 'Alternative' }], rows: alloc, sort: { key: 'risk_reduction', dir: 'desc' } }) })));
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: lever interplay, penalty sensitivity and plan comparison arrive with the Capital Optimiser screen agent.')));
  return stop;
}
