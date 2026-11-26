/**
 * 06 · Capital Optimiser — screen agent D.
 * Data: frontier.json (+ policies.json for reference-policy cost components when a point lacks them)
 * Deep links: #/capital?point=I125&view=holdout|selection|overlay
 * Shows: the Readiness Frontier (capital vs expected material AOG h/yr, holdout means with 95% CI
 * whiskers, the non-dominated set connected, dominated points muted, P0/P1/P2 labelled, the recommended
 * point annotated), a selection-vs-holdout toggle/overlay, a budget slider that walks the frontier and
 * drives the allocation table, the annual cost breakdown (capital shown separately, never summed), the
 * sensitivity tornado, the lever panel, the stress-variant table and the method limitations.
 */
import { h, pageHead, card, provChip, slider, dataTable, segmented, kpiTile, icon } from '../ui.js';
import { chartFrame, responsive, svgIn, axisBottom, withTooltip, theme, fmtAED, fmtHours, fmtInt, fmtNum, reducedMotion, truncate } from '../charts/theme.js';

export const data = ['frontier', 'policies'];

const CAPITAL_KINDS = new Set(['policy', 'baseline', 'budget', 'incremental', 'reposition', 'frontier', 'recommended', 'candidate']);
const KIND_LABEL = { policy: 'Reference policy', baseline: 'Reference policy', budget: 'Re-optimised budget point', incremental: 'Base + greedy additions', lever: 'Lever (annual spend, not capital)', combo: 'Budget point + lever', reposition: 'Reposition only', frontier: 'Frontier point', recommended: 'Recommended', candidate: 'Candidate' };
const LEVER_LABEL = { buy_1: 'Buy 1 spare', buy_2: 'Buy 2 spares', tat_cut_10d: 'Cut repair TAT 10 d', reposition_1: 'Reposition 1 unit' };
const COMP = [
  { key: 'aog_penalty', label: 'AOG penalty' },
  { key: 'holding_cost', label: 'Holding' },
  { key: 'repair_cost', label: 'Repair' },
  { key: 'expedite_cost', label: 'Expedite' },
  { key: 'logistics_cost', label: 'Logistics' },
];
const FACTOR_LABEL = { aog_penalty: 'AOG penalty', carrying_cost: 'Carrying cost', repair_tat: 'Repair TAT', lead_time: 'Lead time', aog_desk_expedite: 'AOG-desk expedite' };
const num = (v) => (v === null || v === undefined || v === '' || Number.isNaN(+v) ? null : +v);
const ciTxt = (lo, hi, f) => (lo == null || hi == null ? '' : ` [${f(lo)}, ${f(hi)}]`);
const signH = (v) => (v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtHours(Math.abs(v))}`);
const signAED = (v) => fmtAED(v, { sign: true });

function ensureCSS() {
  if (document.querySelector('link[data-view-css="capital-optimiser"]')) return;
  document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/capital-optimiser.css', import.meta.url).href, dataset: { viewCss: 'capital-optimiser' } }));
}

// ----------------------------------------------------------------------------- normalise
function triple(o, ...names) {
  for (const n of names) {
    const v = o?.[n];
    if (Array.isArray(v) && v.length >= 1) return [num(v[0]), num(v[1]), num(v[2])];
    if (v && typeof v === 'object' && 'mean' in v) return [num(v.mean), num(v.lo ?? v.ci_lo), num(v.hi ?? v.ci_hi)];
  }
  return null;
}
function normPoint(p, selCI) {
  const cap = num(p.capital_aed ?? p.capital_mean);
  const ci = Array.isArray(p.aog_ci) ? p.aog_ci.map(num) : [num(p.aog_hours_lo), num(p.aog_hours_hi)];
  const s = p.selection || p.sel || null;
  const sel = s ? { cap: num(s.capital_aed ?? s.capital_mean), aog: num(s.aog_hours ?? s.aog_hours_mean), ci: Array.isArray(s.aog_ci) ? s.aog_ci.map(num) : [num(s.aog_hours_lo), num(s.aog_hours_hi)] }
    : p.selection_aog_hours != null ? { cap: num(p.selection_capital_aed ?? cap), aog: num(p.selection_aog_hours), ci: Array.isArray(p.selection_aog_ci) ? p.selection_aog_ci.map(num) : Array.isArray(selCI?.aog_ci) ? selCI.aog_ci.map(num) : [null, null] } : null;
  const comps = p.cost_components || p.costs || p.annual_cost || null;
  const compObj = {};
  COMP.forEach((c) => { const v = comps ? num(comps[c.key] ?? comps[`${c.key}_aed`] ?? comps[c.key.replace('_cost', '')]) : num(p[`${c.key}_mean`] ?? p[`${c.key}_aed`]); if (v != null) compObj[c.key] = v; });
  const dBaseAog = (p.d_aog_vs_P2 != null ? [num(p.d_aog_vs_P2), num(p.d_aog_vs_P2_ci?.[0]), num(p.d_aog_vs_P2_ci?.[1])] : null) || triple(p.d_vs_base, 'aog', 'aog_hours') || triple(p, 'd_aog_vs_base', 'd_aog_hours_vs_base') || (p.d_aog_hours_vs_base_mean != null ? [num(p.d_aog_hours_vs_base_mean), num(p.d_aog_hours_vs_base_lo), num(p.d_aog_hours_vs_base_hi)] : null);
  const dBaseCap = (p.d_capital_vs_P2_aed != null ? [num(p.d_capital_vs_P2_aed), null, null] : null) || triple(p.d_vs_base, 'capital', 'capital_aed') || triple(p, 'd_capital_vs_base') || (p.d_capital_vs_base_mean != null ? [num(p.d_capital_vs_base_mean), num(p.d_capital_vs_base_lo), num(p.d_capital_vs_base_hi)] : null);
  const dP0Aog = triple(p.d_vs_p0 || p.d_vs_P0, 'aog', 'aog_hours') || (p.d_aog_hours_vs_P0_mean != null ? [num(p.d_aog_hours_vs_P0_mean), num(p.d_aog_hours_vs_P0_lo), num(p.d_aog_hours_vs_P0_hi)] : null);
  const dP0Cap = triple(p.d_vs_p0 || p.d_vs_P0, 'capital', 'capital_aed') || (p.d_capital_vs_P0_mean != null ? [num(p.d_capital_vs_P0_mean), num(p.d_capital_vs_P0_lo), num(p.d_capital_vs_P0_hi)] : null);
  return {
    raw: p, id: p.id, kind: p.subkind || p.kind || 'candidate', label: p.label || KIND_LABEL[p.kind] || p.kind,
    cap, capCI: Array.isArray(p.capital_ci) ? p.capital_ci.map(num) : [num(p.capital_lo), num(p.capital_hi)],
    aog: num(p.aog_hours ?? p.aog_hours_mean), ci, dominated: !!p.dominated, hull: p.on_hull ?? p.hull ?? null,
    budget: num(p.budget_aed), total: num(p.total_cost_aed ?? p.total_cost_mean ?? p.total_annual_cost_aed), totalCI: Array.isArray(p.total_cost_ci) ? p.total_cost_ci.map(num) : null, comps: compObj,
    sel, dBaseAog, dBaseCap, dP0Aog, dP0Cap, fill: num(p.fill_rate ?? p.fill_rate_mean), events: num(p.aog_events ?? p.aog_events_mean),
  };
}
const isPolicy = (p) => p.kind === 'policy' || p.kind === 'baseline' || /^P\d$/.test(p.id);
const isCapital = (p) => CAPITAL_KINDS.has(p.kind) || isPolicy(p);

/** Non-dominated set (minimise capital and AOG) on the given accessor, sorted by capital. */
function frontierOf(pts, get) {
  const ok = pts.filter((p) => get(p) && get(p).cap != null && get(p).aog != null);
  return ok.filter((p) => !ok.some((q) => q !== p && get(q).cap <= get(p).cap && get(q).aog <= get(p).aog && (get(q).cap < get(p).cap || get(q).aog < get(p).aog))).sort((a, b) => get(a).cap - get(b).cap);
}

// ----------------------------------------------------------------------------- view
export async function render(el, ctx) {
  ensureCSS();
  const d3 = window.d3;
  const { frontier: F, policies: POL } = ctx.data;
  const prov = F.meta?.provenance || F.provenance || 'SIMULATED';
  const stops = [];
  const selById = new Map((F.selection_points || []).map((q) => [q.id, q]));
  const pts = (F.points || []).map((p) => normPoint(p, selById.get(p.id))).filter((p) => p.cap != null && p.aog != null);
  const byId = new Map(pts.map((p) => [p.id, p]));
  const baseId = F.base_policy || F.base_policy_id || (byId.has('P2') ? 'P2' : F.baseline);
  const P0 = byId.get('P0') || byId.get(F.baseline);
  const P2 = byId.get(baseId);
  const P1 = byId.get('P1');
  const rec = byId.get(F.recommended) || pts.find((p) => p.kind === 'recommended') || pts[0];
  const split = F.split || F.meta?.split || 'holdout';
  const seedsTxt = F.seeds_label || (split === 'holdout' ? 'holdout seeds 1000–1019' : 'selection seeds 100–119');
  const hasSel = pts.some((p) => p.sel && p.sel.aog != null);
  const H = (p) => ({ cap: p.cap, aog: p.aog, ci: p.ci });
  const S = (p) => (p.sel && p.sel.aog != null ? { cap: p.sel.cap ?? p.cap, aog: p.sel.aog, ci: p.sel.ci } : null);
  const capPts = pts.filter(isCapital);
  const front = (() => {
    const flagged = capPts.filter((p) => !p.dominated).sort((a, b) => a.cap - b.cap);
    return flagged.length >= 2 ? frontierOf(flagged, H) : frontierOf(capPts, H);
  })();
  const frontSel = hasSel ? frontierOf(capPts, S) : [];
  const policyByName = (id) => (POL?.policies || []).find((q) => q.policy_id === id);

  let mode = ['holdout', 'selection', 'overlay'].includes(ctx.params.view) && (hasSel || ctx.params.view === 'holdout') ? ctx.params.view : 'holdout';
  let sel = byId.get(ctx.params.point) && front.includes(byId.get(ctx.params.point)) ? byId.get(ctx.params.point) : front.includes(rec) ? rec : front[0];

  // ---- header
  const dAogP2 = rec && P2 ? rec.dBaseAog || [rec.aog - P2.aog, null, null] : null;
  el.append(pageHead({
    num: '06', eyebrow: 'Capital Optimiser', title: 'The Readiness Frontier',
    lede: 'Every dot is a complete stocking plan for Falcon Hub Airways (fictional), simulated on paired seeds. The frontier is the least expected material AOG reachable at each level of spare capital. Capital is a balance-sheet stock, so it is shown apart from annual operating cost and never added to it.',
    meta: [provChip(prov), h('span', { class: 'chip chip-mono' }, split === 'holdout' ? 'Holdout · central' : `${split} · central`)],
  }));

  // ---- KPI strip (constructed from frontier points; baseline = base policy P2)
  if (rec && P2) {
    const tiles = [
      kpiTile({ label: `${rec.id} capital · vs ${baseId}`, value: rec.cap, baseline: P2.cap, delta: rec.cap - P2.cap, better: 'lower', provenance: prov, ci: rec.capCI[0] != null ? rec.capCI : null }, { format: fmtAED, deltaFormat: (v) => fmtAED(v) }),
      kpiTile({ label: `${rec.id} AOG / yr · vs ${baseId}`, value: rec.aog, baseline: P2.aog, delta: rec.aog - P2.aog, better: 'lower', provenance: prov, ci: rec.ci }, { format: fmtHours }),
      P0 ? kpiTile({ label: `${rec.id} AOG / yr · vs P0`, value: rec.aog, baseline: P0.aog, delta: rec.aog - P0.aog, better: 'lower', provenance: prov, ci: rec.ci }, { format: fmtHours }) : null,
      rec.total != null && P2.total != null ? kpiTile({ label: `${rec.id} annual cost · vs ${baseId}`, value: rec.total, baseline: P2.total, delta: rec.total - P2.total, better: 'lower', provenance: prov, ci: rec.totalCI }, { format: fmtAED }) : null,
    ].filter(Boolean);
    tiles.forEach((t) => t.classList.add('span-3'));
    el.append(h('div', { class: 'grid-12 co-kpis', dataset: { story: 'capital-kpis' } }, tiles));
  }

  // ---- hero: frontier chart + control panel
  const chartCard = h('section', { class: 'card card--bp span-8 co-hero', dataset: { story: 'frontier-chart' } });
  const side = h('div', { class: 'span-4 co-side' });
  el.append(h('div', { class: 'grid-12 mt-3' }, chartCard, side));
  const recVsP2 = rec?.dBaseAog;
  const headline = rec && P2 && P0
    ? `${rec.id} holds material AOG to ${fmtHours(rec.aog)} a year, ${fmtHours(P2.aog - rec.aog)} below P2 for ${fmtAED(rec.cap - P2.cap)} more capital`
    : 'Frontier: capital versus material AOG hours';
  const tableRows = pts.slice().sort((a, b) => a.cap - b.cap).map((p) => ({ id: p.id, kind: KIND_LABEL[p.kind] || p.kind, cap: p.cap, aog: p.aog, lo: p.ci[0], hi: p.ci[1], sel: p.sel?.aog ?? null, front: front.includes(p) ? 'yes' : 'no' }));
  const frame = chartFrame(chartCard, {
    headline,
    subtitle: `Spare capital (AED, simulated) vs expected material AOG h/yr (log scale) · ${seedsTxt} · central variant · mean and 95% CI`,
    provenance: prov, source: 'frontier.json',
    table: { columns: [{ key: 'id', label: 'Plan', mono: true }, { key: 'kind', label: 'Kind' }, { key: 'cap', label: 'Capital', num: true, format: (v) => fmtAED(v) }, { key: 'aog', label: 'AOG h/yr', num: true, format: fmtHours }, { key: 'lo', label: 'CI lo', num: true, format: fmtHours }, { key: 'hi', label: 'CI hi', num: true, format: fmtHours }, { key: 'sel', label: 'Selection AOG h', num: true, format: (v) => (v == null ? 'not exported' : fmtHours(v)) }, { key: 'front', label: 'Non-dominated' }], rows: tableRows },
  });
  const legend = h('div', { class: 'co-legend t-12' },
    h('span', {}, h('i', { class: 'co-key co-key--front' }), 'Non-dominated plans (connected)'),
    h('span', {}, h('i', { class: 'co-key co-key--dom' }), 'Dominated'),
    h('span', {}, h('i', { class: 'co-key co-key--pol' }), 'Reference policies P0 / P1 / P2'),
    h('span', {}, h('i', { class: 'co-key co-key--lev' }), 'Levers (annual spend)'),
    h('span', { class: 'co-legend-sel', hidden: mode !== 'overlay' }, h('i', { class: 'co-key co-key--sel' }), 'Selection-seed position'));
  frame.body.before(legend);
  const annoteHTML = h('p', { class: 'co-annote', hidden: true });
  frame.body.after(annoteHTML);

  let chart = null;
  const stopChart = responsive(frame.body, (w) => { chart = drawFrontier(frame.body, w); });

  function drawFrontier(body, w) {
    const narrow = w < 560;
    const hgt = narrow ? 340 : 440;
    const m = { top: 28, right: narrow ? 20 : 36, bottom: 44, left: narrow ? 44 : 56 };
    const iw = Math.max(60, w - m.left - m.right), ih = hgt - m.top - m.bottom;
    const svg = svgIn(body, w, hgt, 'Readiness frontier: spare capital versus material AOG hours');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const allCap = pts.flatMap((p) => [p.cap, p.sel?.cap]).filter((v) => v != null);
    const allAog = pts.flatMap((p) => [p.aog, p.ci[1], p.sel?.aog, p.sel?.ci?.[1]]).filter((v) => v != null && v > 0);
    const yMin = Math.max(1, d3.min(pts.flatMap((p) => [p.aog, p.sel?.aog]).filter((v) => v > 0)) * 0.55);
    const x = d3.scaleLinear().domain(d3.extent(allCap)).nice().range([0, iw]);
    const y = d3.scaleLog().domain([yMin, d3.max(allAog) * 1.08]).range([ih, 0]).clamp(true);
    const yTicks = [50, 100, 200, 500, 1000, 2000, 5000, 10000].filter((t) => t >= y.domain()[0] && t <= y.domain()[1]);
    g.append('g').attr('class', 'gnm-grid').selectAll('line').data(yTicks).join('line').attr('x1', 0).attr('x2', iw).attr('y1', (t) => y(t)).attr('y2', (t) => y(t));
    const ay = g.append('g').call(d3.axisLeft(y).tickValues(yTicks).tickSize(0).tickPadding(8).tickFormat((v) => fmtInt(v)));
    ay.attr('class', 'gnm-axis').select('.domain').remove();
    ay.selectAll('text').attr('font-family', theme.font.mono);
    axisBottom(g.append('g'), x, { height: ih, ticks: narrow ? 3 : 6, format: (v) => fmtAED(v, { digits: 0 }) });
    g.append('text').attr('class', 'gnm-label').attr('x', -m.left + 4).attr('y', -14).style('fill', theme.color.faint).text('AOG h / yr');
    if (!narrow) g.append('text').attr('class', 'gnm-label').attr('x', iw).attr('y', ih + 36).attr('text-anchor', 'end').style('fill', theme.color.faint).text('Spare capital →');

    const gBand = g.append('g'), gWhisk = g.append('g'), gLine = g.append('g'), gLinks = g.append('g'), gGhost = g.append('g'), gPts = g.append('g'), gLab = g.append('g'), gAnn = g.append('g'), gSel = g.append('g');
    const dur = reducedMotion() ? 0 : theme.motion.ms + 150;
    const ease = d3.easeCubicOut;

    const posOf = (p, md) => (md === 'selection' ? S(p) || H(p) : H(p));
    const lineGen = d3.line().x((d) => x(d.cap)).y((d) => y(d.aog)).curve(d3.curveMonotoneX);
    const areaGen = d3.area().x((d) => x(d.cap)).y0((d) => y(Math.max(yMin, d.ci[0] ?? d.aog))).y1((d) => y(d.ci[1] ?? d.aog)).curve(d3.curveMonotoneX);

    function update(animate = true) {
      const md = mode === 'selection' ? 'selection' : 'holdout';
      const fr = md === 'selection' ? frontSel : front;
      const T = (s) => (animate && dur ? s.transition().duration(dur).ease(ease) : s);
      const frPos = fr.map((p) => posOf(p, md));
      T(gBand.selectAll('path').data([frPos]).join('path').attr('fill', theme.color.accent).attr('fill-opacity', 0.09)).attr('d', areaGen);
      T(gLine.selectAll('path').data([frPos]).join('path').attr('fill', 'none').attr('stroke', theme.color.accent).attr('stroke-width', 2)).attr('d', lineGen);
      // whiskers
      const wh = gWhisk.selectAll('line').data(pts, (p) => p.id).join('line').attr('stroke-linecap', 'round');
      T(wh).attr('x1', (p) => x(posOf(p, md).cap)).attr('x2', (p) => x(posOf(p, md).cap))
        .attr('y1', (p) => y(Math.max(yMin, posOf(p, md).ci?.[0] ?? posOf(p, md).aog))).attr('y2', (p) => y(posOf(p, md).ci?.[1] ?? posOf(p, md).aog))
        .attr('stroke', (p) => (isPolicy(p) ? theme.color.accent2 : fr.includes(p) ? theme.color.accent : theme.color.neutral)).attr('stroke-opacity', (p) => (fr.includes(p) || isPolicy(p) ? 0.55 : 0.3)).attr('stroke-width', 1.25);
      // points
      const shape = (p) => (isPolicy(p) ? d3.symbolSquare : p.kind === 'lever' || p.kind === 'combo' ? d3.symbolDiamond : d3.symbolCircle);
      const size = (p) => (p === rec ? 150 : isPolicy(p) ? 90 : fr.includes(p) ? 52 : 30);
      const pp = gPts.selectAll('path.co-pt').data(pts, (p) => p.id).join((en) => en.append('path').attr('class', 'co-pt').attr('transform', (p) => `translate(${x(posOf(p, md).cap)},${y(posOf(p, md).aog)})`));
      pp.attr('d', (p) => d3.symbol(shape(p), size(p))())
        .attr('fill', (p) => (p === rec ? theme.color.accent : isPolicy(p) ? theme.color.bg : fr.includes(p) ? theme.color.bg : theme.color.neutral))
        .attr('fill-opacity', (p) => (fr.includes(p) || isPolicy(p) || p === rec ? 1 : 0.55))
        .attr('stroke', (p) => (isPolicy(p) ? theme.color.accent2 : fr.includes(p) || p === rec ? theme.color.accent : p.kind === 'lever' || p.kind === 'combo' ? theme.color.muted : 'none'))
        .attr('stroke-width', (p) => (isPolicy(p) ? 2 : 1.5)).style('cursor', 'pointer')
        .attr('tabindex', (p) => (front.includes(p) ? 0 : null)).attr('role', (p) => (front.includes(p) ? 'button' : null))
        .attr('aria-label', (p) => `${p.id}: ${fmtAED(p.cap)}, ${fmtHours(p.aog)} per year`);
      T(pp).attr('transform', (p) => `translate(${x(posOf(p, md).cap)},${y(posOf(p, md).aog)})`);
      withTooltip(pp, (p) => ({
        title: `${p.id} · ${KIND_LABEL[p.kind] || p.kind}`,
        rows: [['Capital', fmtAED(p.cap)], ['AOG h/yr (holdout)', `${fmtHours(p.aog)}${ciTxt(p.ci[0], p.ci[1], fmtInt)}`], p.sel?.aog != null ? ['AOG h/yr (selection)', fmtHours(p.sel.aog)] : null, p.dBaseAog ? [`Δ vs ${baseId} (paired)`, `${signH(p.dBaseAog[0])}${ciTxt(p.dBaseAog[1], p.dBaseAog[2], (v) => fmtInt(v))}`] : null].filter(Boolean),
        note: front.includes(p) ? 'On the frontier · click to inspect its allocation' : p.kind === 'lever' || p.kind === 'combo' ? 'Adds annual spend, not capital: reported beside the rule' : p.dominated ? 'Dominated: another plan is cheaper and no worse' : '',
      }));
      pp.on('click', (e, p) => { if (front.includes(p)) choose(p, true); })
        .on('keydown', (e, p) => { if ((e.key === 'Enter' || e.key === ' ') && front.includes(p)) { e.preventDefault(); choose(p, true); } });
      // overlay ghosts + links
      const ov = mode === 'overlay' ? pts.filter((p) => S(p)) : [];
      gLinks.selectAll('line').data(ov, (p) => p.id).join('line').attr('stroke', theme.color.muted).attr('stroke-opacity', 0.35).attr('stroke-dasharray', '2 3')
        .attr('x1', (p) => x(p.cap)).attr('y1', (p) => y(p.aog)).attr('x2', (p) => x(S(p).cap)).attr('y2', (p) => y(S(p).aog));
      gGhost.selectAll('circle').data(ov, (p) => p.id).join('circle').attr('r', 3).attr('fill', 'none').attr('stroke', theme.color.muted).attr('stroke-opacity', 0.8)
        .attr('cx', (p) => x(S(p).cap)).attr('cy', (p) => y(S(p).aog));
      legend.querySelector('.co-legend-sel').hidden = mode !== 'overlay';
      // policy labels
      const pols = [P0, P1, P2].filter(Boolean);
      const labs = gLab.selectAll('text').data(pols, (p) => p.id).join('text').attr('class', 'gnm-label gnm-label--strong').attr('fill', theme.color.accent2).attr('font-family', theme.font.mono);
      T(labs).attr('x', (p) => x(posOf(p, md).cap) + (p === P2 ? -10 : 10)).attr('y', (p) => y(posOf(p, md).aog) + (p === P2 ? 20 : 0)).attr('dy', '0.32em').attr('text-anchor', (p) => (p === P2 ? 'end' : 'start'))
        .text((p) => (p.id === baseId && !narrow ? `${p.id} · base policy` : p.id));
      // annotation on recommended
      gAnn.selectAll('*').remove();
      if (rec) {
        const rp = posOf(rec, md);
        const ax = x(rp.cap), ayy = y(rp.aog);
        const lines = [
          [`Recommended · ${rec.id}${md === 'selection' ? ' (selection seeds)' : ''}`, 'gnm-annot-text'],
          [`${fmtAED(rp.cap)} · ${fmtHours(rp.aog)}/yr${ciTxt(rp.ci?.[0], rp.ci?.[1], fmtInt)}`, 'gnm-annot-sub'],
        ];
        if (md !== 'selection' && P2 && rec.dBaseAog) lines.push([`vs ${baseId}: ${signH(rec.dBaseAog[0])}${ciTxt(rec.dBaseAog[1], rec.dBaseAog[2], (v) => fmtInt(v))} h · ${signAED(rec.cap - P2.cap)}`, 'gnm-annot-sub']);
        if (md !== 'selection' && P0) lines.push([`vs P0: ${signH(rec.aog - P0.aog)}${rec.dP0Aog ? ciTxt(rec.dP0Aog[1], rec.dP0Aog[2], (v) => fmtInt(v)) : ''} · ${signAED(rec.cap - P0.cap)}`, 'gnm-annot-sub']);
        if (narrow) {
          gAnn.append('text').attr('class', 'gnm-annot-text').attr('x', ax + 14).attr('y', ayy + 24).text(`${rec.id} · recommended`);
          annoteHTML.replaceChildren(...lines.map(([t], i) => h(i ? 'span' : 'b', {}, t)));
          annoteHTML.hidden = false;
        } else {
          annoteHTML.hidden = true;
          const dx = ax > iw * 0.55 ? -40 : 40, dy = -Math.min(150, ayy - lines.length * 15 - 4);
          const tx = ax + dx, anchor = dx < 0 ? 'end' : 'start';
          gAnn.append('path').attr('class', 'gnm-annot-line').attr('d', `M${ax},${ayy - 10}L${ax},${ayy + dy + 6}L${tx},${ayy + dy + 6}`);
          lines.forEach(([t, c], i) => gAnn.append('text').attr('class', c).attr('x', tx + (dx < 0 ? -6 : 6)).attr('y', ayy + dy - 4 - (lines.length - 1 - i) * 15).attr('text-anchor', anchor).text(t));
        }
      }
      // selected ring
      const sp = posOf(sel, md);
      const ring = gSel.selectAll('circle').data([sel]).join('circle').attr('r', 11).attr('fill', 'none').attr('stroke', theme.color.text).attr('stroke-width', 1.5).attr('stroke-dasharray', '3 2');
      T(ring).attr('cx', x(sp.cap)).attr('cy', y(sp.aog));
      const rl = gSel.selectAll('text').data([sel]).join('text').attr('class', 'gnm-label gnm-label--strong').attr('font-family', theme.font.mono).attr('text-anchor', 'middle');
      T(rl).attr('x', x(sp.cap)).attr('y', y(sp.aog) + 26).text(sel === rec ? '' : sel.id);
    }
    update(false);
    return { update };
  }

  // ---- side panel: view toggle, budget slider, readout, rule
  const readout = h('dl', { class: 'meta-list co-readout' });
  const minB = front[0]?.cap ?? 0, maxB = front.at(-1)?.cap ?? 1;
  const step = Math.max(50000, Math.round((maxB - minB) / 200 / 50000) * 50000);
  const sl = slider({ label: 'Capital budget', min: Math.floor(minB / step) * step, max: Math.ceil(maxB / step) * step, step, value: Math.round(sel.cap / step) * step, format: (v) => fmtAED(v), onInput: (v) => { const p = front.filter((q) => q.cap <= v + step / 2).at(-1) || front[0]; if (p !== sel) choose(p, false); } });
  const slInput = sl.querySelector('input');
  slInput.dataset.role = 'budget-slider';
  const modeSeg = segmented({ label: 'Seed set', value: mode, options: [{ value: 'holdout', label: 'Holdout' }, { value: 'selection', label: 'Selection' }, { value: 'overlay', label: 'Overlay' }], onChange: (v) => { mode = v; ctx.setParams({ view: v === 'holdout' ? '' : v }); chart?.update(true); } });
  if (!hasSel) modeSeg.querySelectorAll('button').forEach((b) => { if (b.dataset.value !== 'holdout') { b.disabled = true; b.title = 'Selection-seed values not exported'; } });
  function showSel() {
    const p = sel;
    const rows = [
      ['Plan', h('span', {}, h('b', { class: 'mono' }, p.id), ' ', h('span', { class: 'faint' }, KIND_LABEL[p.kind] || p.kind))],
      ['Capital', `${fmtAED(p.cap)}${p.capCI[0] != null ? ciTxt(p.capCI[0], p.capCI[1], (v) => fmtAED(v).replace('AED ', '')) : ''}`],
      ['AOG / yr', `${fmtHours(p.aog)}${ciTxt(p.ci[0], p.ci[1], fmtInt)}`],
      P2 && p !== P2 ? [`vs ${baseId}`, p.dBaseAog ? `${signH(p.dBaseAog[0])}${ciTxt(p.dBaseAog[1], p.dBaseAog[2], (v) => fmtInt(v))} · ${signAED(p.cap - P2.cap)}` : `${signH(p.aog - P2.aog)} · ${signAED(p.cap - P2.cap)}`] : null,
      P0 && p !== P0 ? ['vs P0', `${signH(p.aog - P0.aog)} · ${signAED(p.cap - P0.cap)}`] : null,
      p.total != null ? ['Annual cost', fmtAED(p.total)] : null,
      p.sel?.aog != null ? ['Selection', `${fmtHours(p.sel.aog)}${ciTxt(p.sel.ci?.[0], p.sel.ci?.[1], fmtInt)}`] : null,
    ].filter(Boolean);
    readout.replaceChildren(...rows.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
  }
  const R = F.recommendation || {};
  const rule = card({
    kicker: 'Recommendation rule · pre-stated', title: R.h_star_per_aed_1m != null ? `Stop when an extra AED 1M buys fewer than ${fmtNum(R.h_star_per_aed_1m, 1)} AOG h` : 'Balanced point rule', prov: 'ASSUMED',
    body: h('div', { class: 'stack-1 t-14 muted' },
      h('p', { class: 'm-0' }, R.aed_per_aog_hour != null ? `Walk the lower hull of the capital-only plans. Each segment buys AOG hours per extra AED 1M. Break-even h* = carrying ${fmtNum((R.carrying_pct ?? 0) * 100, 0)}% × AED 1M ÷ ${fmtAED(R.aed_per_aog_hour)} per AOG hour. The recommendation is the last vertex before the first segment below h*.` : 'Walk the lower hull of the capital-only plans and stop at the first segment worth less than its holding cost.'),
      R.segments ? h('p', { class: 'm-0 t-12 faint' }, `Selection-seed hull. Segment into ${R.recommended || rec.id}: ${fmtNum(R.segments.find((s) => s.to === (R.recommended || rec.id))?.h_per_aed_1m, 1)} h per AED 1M; next segment: ${fmtNum(R.segments.find((s) => s.from === (R.recommended || rec.id))?.h_per_aed_1m, 1)} h.`) : null),
  });
  side.append(
    card({
      cls: 'co-controls', kicker: 'Explore the frontier', title: 'Budget and seed set', prov,
      body: h('div', { class: 'stack-3' },
        h('div', { class: 'field' }, h('span', { class: 'field-label' }, 'Seed set'), modeSeg, h('span', { class: 't-12 faint' }, hasSel ? 'Selection seeds 100–119 chose the plan; holdout seeds 1000–1019 judge it.' : 'Selection-seed values are not in this export.')),
        sl,
        h('p', { class: 't-12 faint m-0' }, 'The slider walks the non-dominated plans: it picks the lowest-AOG plan whose capital fits the budget (holdout means).'),
        readout),
    }),
    rule,
  );
  showSel();

  // ---- allocation table
  const allocCard = h('section', { class: 'card mt-3', dataset: { story: 'allocation-table' } });
  el.append(allocCard);
  const allocHead = h('div', { class: 'card-head' });
  const allocBody = h('div');
  allocCard.append(allocHead, allocBody);
  const allocRows = (id) => (F.allocations?.[id] || []).map((r) => {
    const cur = num(r.current), prop = num(r.proposed);
    return { pn: r.pn, station: r.station, cls: r.part_class || (String(r.pn).match(/-([CER])\d/)?.[1] ?? ''), current: cur, proposed: prop, change: num(r.delta_units) ?? (cur != null && prop != null ? prop - cur : null), dcap: num(r.delta_capital ?? r.incremental_capital_aed), risk: num(r.risk_reduction ?? r.modelled_aog_hour_reduction), alt: r.alt_action ?? r.best_alternative_action ?? '' };
  });
  const altTxt = (a) => LEVER_LABEL[a] || (a === 'hold' ? 'Hold (no better lever)' : a ? String(a).replace(/_/g, ' ') : '—');
  const allocTable = dataTable({
    caption: 'Allocation changes', maxHeight: 440, dense: true, sort: { key: 'risk', dir: 'desc' }, rowKey: 'pn',
    columns: [
      { key: 'pn', label: 'PN', mono: true }, { key: 'station', label: 'Station', mono: true }, { key: 'cls', label: 'Class', mono: true },
      { key: 'current', label: `Float (${baseId})`, num: true, format: (v) => (v == null ? '—' : fmtInt(v)) },
      { key: 'change', label: 'Change', num: true, render: (r) => h('span', { class: `co-chg ${r.change > 0 ? 'is-up' : r.change < 0 ? 'is-down' : ''}` }, r.change == null ? '—' : `${r.change > 0 ? '+' : r.change < 0 ? '−' : ''}${fmtInt(Math.abs(r.change))}`) },
      { key: 'proposed', label: 'Proposed', num: true, format: (v) => (v == null ? '—' : fmtInt(v)) },
      { key: 'dcap', label: 'Δ capital', num: true, format: (v) => (v == null ? '—' : signAED(v)) },
      { key: 'risk', label: 'AOG h/yr avoided*', num: true, format: (v) => (v == null ? '—' : fmtNum(v, 1)) },
      { key: 'alt', label: 'Alternative', format: altTxt },
    ],
    rows: [],
  });
  const allocNote = h('p', { class: 't-12 muted mt-2 m-0' });
  allocBody.append(allocTable, allocNote, h('p', { class: 't-12 faint mt-2 m-0' }, `Rows are the changes against the base policy ${baseId} only. * AOG h/yr avoided is a leave-one-out estimate on the analytic model (a ranking heuristic), not a simulated result. Alternative action is the cheapest modelled lever for that PN.`));
  function showAlloc() {
    const rows = allocRows(sel.id);
    const tot = F.allocation_totals?.[sel.id];
    const sumCap = num(tot?.delta_capital_aed) ?? rows.reduce((s, r) => s + (r.dcap || 0), 0);
    const units = num(tot?.delta_units) ?? rows.reduce((s, r) => s + (r.change || 0), 0);
    const nAll = num(tot?.n_rows) ?? rows.length;
    allocHead.replaceChildren(
      h('div', {}, h('div', { class: 'card-kicker' }, `Allocation · ${sel.id}`), h('h3', { class: 'card-title co-alloc-title', 'aria-live': 'polite' }, rows.length ? `${sel.id} changes ${fmtInt(nAll)} PN-station levels vs ${baseId}: ${units >= 0 ? '+' : '−'}${fmtInt(Math.abs(units))} units, ${signAED(sumCap)} allocation capital` : sel === P2 ? `${baseId} is the base policy: no changes` : `No allocation rows exported for ${sel.id}`)),
      h('div', { class: 'row' }, provChip(prov)));
    allocTable.update(rows);
    allocNote.textContent = tot && num(tot.n_rows_shown) < num(tot.n_rows) ? `Showing the ${fmtInt(tot.n_rows_shown)} changes with the largest modelled effect of ${fmtInt(tot.n_rows)}; totals cover all rows.` : '';
    allocCard.dataset.point = sel.id;
  }
  showAlloc();

  function choose(p, fromChart) {
    sel = p;
    showSel(); showAlloc(); chart?.update(true);
    if (fromChart) { slInput.value = String(Math.round(p.cap / step) * step); slInput.dispatchEvent(new Event('input')); }
    ctx.setParams({ point: p.id });
  }

  // ---- cost breakdown + tornado
  const costCard = h('section', { class: 'card span-6' });
  const torCard = h('section', { class: 'card span-6', dataset: { story: 'tornado' } });
  el.append(h('div', { class: 'grid-12 mt-3' }, costCard, torCard));
  drawCost(costCard);
  drawTornado(torCard);

  function compsFor(p) {
    if (!p) return null;
    const q = policyByName(p.id);
    if (!q) return Object.keys(p.comps).length >= 2 ? p.comps : null;
    const o = {};
    COMP.forEach((c) => { const v = q.kpi?.[`${c.key}_aed`]?.mean ?? q.kpi?.[c.key]?.mean; if (v != null) o[c.key] = v; });
    return Object.keys(o).length ? o : null;
  }
  function drawCost(host) {
    const rows = [P0, P2, rec].filter(Boolean).filter((p, i, a) => a.indexOf(p) === i).map((p) => {
      const c = compsFor(p);
      const q = policyByName(p.id);
      const official = num(q?.kpi?.total_annual_cost_aed?.mean) ?? p.total;
      return { p, c, official };
    }).filter((r) => r.c);
    if (!rows.length) { host.append(card({ title: 'Annual cost breakdown', prov, body: h('p', { class: 'muted' }, 'Cost components not run.') })); return; }
    const keys = COMP.filter((c) => rows.every((r) => r.c[c.key] != null));
    const shownSum = (r) => keys.reduce((s, c) => s + (r.c[c.key] || 0), 0);
    rows.forEach((r) => { r.other = r.official != null ? Math.max(0, r.official - shownSum(r)) : 0; r.total = r.official ?? shownSum(r); });
    const anyOther = rows.some((r) => r.other > 0.005 * r.total);
    const segs = [...keys, ...(anyOther ? [{ key: 'other', label: 'Other (logistics, rounding)' }] : [])];
    const val = (r, k) => (k === 'other' ? r.other : r.c[k] || 0);
    const r0 = rows[0], rl = rows.at(-1);
    const fr = chartFrame(host, {
      headline: r0.c.aog_penalty != null && rl.c.aog_penalty != null ? `The AOG penalty is ${fmtNum((r0.c.aog_penalty / r0.total) * 100, 0)}% of ${r0.p.id}'s annual cost; ${rl.p.id} cuts it from ${fmtAED(r0.c.aog_penalty)} to ${fmtAED(rl.c.aog_penalty)} a year` : `Annual cost: ${r0.p.id} ${fmtAED(r0.total)} vs ${rl.p.id} ${fmtAED(rl.total)}`,
      subtitle: `Annual cost components (AED/yr) · ${seedsTxt} · means · capital is a stock: shown on the right, never added`,
      provenance: prov, source: 'policies.json · frontier.json',
      table: { columns: [{ key: 'id', label: 'Plan', mono: true }, ...segs.map((c) => ({ key: c.key, label: c.label, num: true, format: (v) => fmtAED(v) })), { key: 'total', label: 'Annual total', num: true, format: (v) => fmtAED(v) }, { key: 'cap', label: 'Capital (separate)', num: true, format: (v) => fmtAED(v) }], rows: rows.map((r) => ({ id: r.p.id, ...Object.fromEntries(segs.map((c) => [c.key, val(r, c.key)])), total: r.total, cap: r.p.cap })) },
    });
    const shade = { aog_penalty: theme.color.accent2, holding_cost: 'rgba(185,200,214,0.62)', repair_cost: 'rgba(185,200,214,0.40)', expedite_cost: 'rgba(185,200,214,0.25)', logistics_cost: 'rgba(185,200,214,0.15)', other: 'rgba(185,200,214,0.10)' };
    stops.push(responsive(fr.body, (w) => {
      const narrow = w < 520;
      const lw = 52, capW = narrow ? 84 : 124, rowH = narrow ? 56 : 58;
      const Hh = rows.length * rowH + 24;
      const svg = svgIn(fr.body, w, Hh, 'Annual cost breakdown');
      const bw = Math.max(60, w - lw - capW - (narrow ? 12 : 84));
      const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.total)]).range([0, bw]);
      svg.append('text').attr('class', 'gnm-label').attr('x', lw).attr('y', 10).style('fill', theme.color.faint).text('Annual cost / yr');
      svg.append('text').attr('class', 'gnm-label').attr('x', w - capW + 12).attr('y', 10).style('fill', theme.color.faint).text('Capital (stock)');
      svg.append('line').attr('x1', w - capW).attr('x2', w - capW).attr('y1', 0).attr('y2', Hh).attr('stroke', theme.color.lineStrong).attr('stroke-dasharray', '2 3');
      rows.forEach((r, i) => {
        const y0 = 26 + i * rowH;
        svg.append('text').attr('class', r.p === rec ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('font-family', theme.font.mono).attr('x', 0).attr('y', y0 + 13).text(r.p.id);
        let x0 = lw;
        segs.forEach((c) => {
          const v = val(r, c.key);
          const seg = svg.append('rect').attr('x', x0).attr('y', y0).attr('height', 18).attr('width', Math.max(0, x(v) - 1)).attr('fill', shade[c.key]);
          withTooltip(seg, () => ({ title: `${r.p.id} · ${c.label}`, rows: [['AED / yr', fmtAED(v)], ['Share', `${fmtNum((v / r.total) * 100, 0)}%`]] }));
          x0 += x(v);
        });
        if (!narrow && r.c.aog_penalty != null && x(r.c.aog_penalty) > 90) svg.append('text').attr('class', 'gnm-label').attr('x', lw + 4).attr('y', y0 + 33).style('fill', theme.color.accent2).text(`AOG penalty ${fmtAED(r.c.aog_penalty)}`);
        const tx = x0 + 6, fits = tx + 72 < w - capW;
        svg.append('text').attr('class', 'gnm-label gnm-label--strong').attr('font-family', theme.font.mono).attr('x', fits ? tx : Math.min(x0, w - capW - 8)).attr('text-anchor', fits ? 'start' : 'end').attr('y', fits ? y0 + 13 : y0 - 4).text(fmtAED(r.total));
        svg.append('rect').attr('x', w - capW + 12).attr('y', y0 + 4).attr('width', 10).attr('height', 10).attr('fill', 'none').attr('stroke', theme.color.muted);
        svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', w - capW + 28).attr('y', y0 + 13).text(fmtAED(r.p.cap));
      });
    }));
    fr.body.after(h('div', { class: 'co-legend t-12' }, segs.map((c) => h('span', {}, h('i', { class: `co-sw co-sw--${c.key}` }), c.label))));
  }

  function drawTornado(host) {
    const T = (F.tornado || []).filter((t) => t.factor !== 'aog_desk_expedite' && t.factor !== 'base case');
    const rows = T.map((t) => {
      const base = num(t.base);
      const lo = { setting: t.low_setting, v: num(t.low_value) ?? (base != null && num(t.low) != null ? base + num(t.low) : null), ci: t.low_ci, saved: num(t.low_aog_saved) };
      const hi = { setting: t.high_setting, v: num(t.high_value) ?? (base != null && num(t.high) != null ? base + num(t.high) : null), ci: t.high_ci, saved: num(t.high_aog_saved) };
      return { f: t.factor, label: FACTOR_LABEL[t.factor] || t.param, base, settings: [lo, hi].filter((x) => x.v != null), swing: Math.abs(num(t.high) - num(t.low)) };
    }).filter((r) => r.base != null && r.settings.length).sort((a, b) => b.swing - a.swing);
    if (!rows.length) {
      const fr = chartFrame(host, { headline: 'Sensitivity of the recommendation', subtitle: 'Net annual benefit vs the base policy (AED)', provenance: prov, source: 'frontier.json', table: { columns: [{ key: 'param', label: 'Factor' }, { key: 'low', label: 'Low', num: true, format: (v) => fmtAED(v) }, { key: 'high', label: 'High', num: true, format: (v) => fmtAED(v) }], rows: F.tornado || [] } });
      fr.body.append(h('p', { class: 'muted' }, 'Tornado not run.'));
      return;
    }
    const base = rows[0].base;
    const all = rows.flatMap((r) => r.settings);
    const minLo = d3.min(all, (s) => num(s.ci?.[0]) ?? s.v), vMin = d3.min(all, (s) => s.v), vMax = d3.max(all, (s) => s.v);
    const fr = chartFrame(host, {
      headline: minLo > 0 ? `${rec.id} beats ${baseId} at every tested setting: net benefit stays between ${fmtAED(vMin)} and ${fmtAED(vMax)} a year` : `${rec.id}'s advantage over ${baseId} is not robust everywhere: the lowest bound reaches ${fmtAED(minLo)} a year`,
      subtitle: `Net annual benefit of ${rec.id} vs ${baseId} (AED/yr) · paired · selection seeds 100–119 · base case ${fmtAED(base)} · 95% CI whiskers`,
      provenance: prov, source: 'frontier.json',
      table: { columns: [{ key: 'label', label: 'Factor' }, { key: 'setting', label: 'Setting' }, { key: 'v', label: 'Net benefit', num: true, format: (v) => fmtAED(v) }, { key: 'lo', label: 'CI lo', num: true, format: (v) => fmtAED(v) }, { key: 'hi', label: 'CI hi', num: true, format: (v) => fmtAED(v) }, { key: 'saved', label: 'AOG h saved', num: true, format: fmtHours }],
        rows: rows.flatMap((r) => r.settings.map((s) => ({ label: r.label, setting: s.setting, v: s.v, lo: num(s.ci?.[0]), hi: num(s.ci?.[1]), saved: s.saved }))) },
    });
    stops.push(responsive(fr.body, (w) => {
      const narrow = w < 520;
      const lw = narrow ? 84 : 128, rowH = 48, Hh = rows.length * rowH + 44;
      const svg = svgIn(fr.body, w, Hh, 'Sensitivity tornado');
      const vals = all.flatMap((s) => [s.v, num(s.ci?.[0]), num(s.ci?.[1])]).filter((v) => v != null).concat([0, base]);
      const x = d3.scaleLinear().domain(d3.extent(vals)).nice().range([lw, w - (narrow ? 36 : 44)]);
      axisBottom(svg.append('g'), x, { height: Hh - 22, ticks: narrow ? 3 : 5, format: (v) => fmtAED(v, { digits: 0 }) });
      svg.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 14).attr('y2', Hh - 22).attr('stroke', theme.color.lineStrong);
      svg.append('line').attr('x1', x(base)).attr('x2', x(base)).attr('y1', 14).attr('y2', Hh - 22).attr('stroke', theme.color.text).attr('stroke-dasharray', '3 3');
      svg.append('text').attr('class', 'gnm-label').attr('x', x(base)).attr('y', 9).attr('text-anchor', 'middle').text(`base ${fmtAED(base)}`);
      rows.forEach((r, i) => {
        const yc = 34 + i * rowH;
        svg.append('text').attr('class', 'gnm-label gnm-label--strong').attr('x', 0).attr('y', yc + 4).text(r.label);
        r.settings.forEach((s, j) => {
          const yy = yc - 10 + j * 13;
          const bar = svg.append('rect').attr('x', Math.min(x(base), x(s.v))).attr('width', Math.max(1.5, Math.abs(x(s.v) - x(base)))).attr('y', yy).attr('height', 10).attr('rx', 2).attr('fill', s.v >= base ? theme.color.accent : theme.color.neutral);
          const lo = num(s.ci?.[0]), hi = num(s.ci?.[1]);
          if (lo != null && hi != null) svg.append('line').attr('x1', x(lo)).attr('x2', x(hi)).attr('y1', yy + 5).attr('y2', yy + 5).attr('stroke', theme.color.muted).attr('stroke-width', 1);
          withTooltip(bar, () => ({ title: `${r.label} · ${s.setting}`, rows: [['Net benefit / yr', `${fmtAED(s.v)}${ciTxt(lo, hi, (q) => fmtAED(q))}`], ['AOG h saved / yr', fmtHours(s.saved)]] }));
          const right = s.v >= base;
          const lx = right ? x(Math.max(s.v, hi ?? s.v)) + 4 : x(Math.min(s.v, lo ?? s.v)) - 4;
          svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', 10).attr('x', lx).attr('y', yy + 9).attr('text-anchor', right ? 'start' : 'end').text(s.setting);
        });
      });
    }));
    const desk = F.aog_desk_dependence;
    if (desk && typeof desk === 'object' && desk.base_aog_hours != null) fr.body.after(h('p', { class: 't-12 faint m-0' }, `Not drawn (off-scale): with the AOG-desk expedite switched off, ${baseId} rises from ${fmtHours(num(desk.central_base_aog_hours))} to ${fmtHours(num(desk.base_aog_hours))} a year and ${rec.id} from ${fmtHours(num(desk.central_rec_aog_hours))} to ${fmtHours(num(desk.rec_aog_hours))} (selection seeds). See the limitations below.`));
  }

  // ---- levers + variants
  const levCard = h('section', { class: 'card span-6', dataset: { story: 'levers' } });
  const varCard = h('div', { class: 'span-6' });
  el.append(h('div', { class: 'grid-12 mt-3' }, levCard, varCard));
  drawLevers(levCard);
  drawVariants(varCard);

  function drawLevers(host) {
    const L = (F.lever_table || F.levers_table || (Array.isArray(F.levers) && F.levers.some((l) => l.lever) ? F.levers : [])).map((r) => ({ ...r, cph: num(r.annual_cost_per_aog_hour_aed), red: num(r.aog_hours_reduction), cost: num(r.annual_cost_aed), net: num(r.net_annual_benefit_aed) }));
    if (!L.length) { host.append(card({ title: '“Buy another spare” vs “cut repair TAT” vs “reposition stock”', prov, body: h('p', { class: 'muted m-0' }, 'Lever table not run.') })); return; }
    const byPn = d3.group(L, (r) => r.pn);
    let buyWins = 0, tatWins = 0, both = 0, reposHelps = 0;
    const cmp = [];
    byPn.forEach((rs, pn) => {
      const b = rs.find((r) => r.lever === 'buy_1'), t = rs.find((r) => r.lever === 'tat_cut_10d'), rp = rs.find((r) => r.lever === 'reposition_1');
      if (rp && rp.red > 0) reposHelps++;
      if (b && t && b.red > 0 && t.red > 0 && b.cph != null && t.cph != null) { both++; if (b.cph <= t.cph) buyWins++; else tatWins++; cmp.push({ pn, b, t, rp, unit: num(b.unit_cost_aed), red: Math.max(b.red, t.red) }); }
    });
    const top = cmp.sort((a, b) => b.red - a.red).slice(0, 8);
    const levPt = pts.find((p) => p.kind === 'lever');
    const fr = chartFrame(host, {
      headline: `Buying a spare is the cheaper way to avoid an AOG hour on ${fmtInt(buyWins)} of ${fmtInt(both)} rotable PNs; cutting repair TAT wins on ${fmtInt(tatWins)}`,
      subtitle: 'AED per AOG hour avoided per year (log scale) · modelled at the base allocation · top PNs by AOG hours avoided · lower is better',
      provenance: prov, source: 'frontier.json (levers)',
      table: { columns: [{ key: 'pn', label: 'PN', mono: true }, { key: 'unit', label: 'Unit cost', num: true, format: (v) => fmtAED(v) }, { key: 'b', label: 'Buy 1: AED/h', num: true, format: (v) => fmtAED(v) }, { key: 'bh', label: 'Buy 1: h avoided', num: true, format: (v) => fmtNum(v, 1) }, { key: 't', label: 'TAT −10 d: AED/h', num: true, format: (v) => fmtAED(v) }, { key: 'th', label: 'TAT −10 d: h avoided', num: true, format: (v) => fmtNum(v, 1) }],
        rows: cmp.map((c) => ({ pn: c.pn, unit: c.unit, b: c.b.cph, bh: c.b.red, t: c.t.cph, th: c.t.red })) },
    });
    stops.push(responsive(fr.body, (w) => {
      const narrow = w < 520;
      const lw = narrow ? 92 : 108, rowH = 26, Hh = top.length * rowH + 52;
      const svg = svgIn(fr.body, w, Hh, 'Lever cost per AOG hour');
      const vals = top.flatMap((c) => [c.b.cph, c.t.cph]).filter((v) => v > 0);
      const x = d3.scaleLog().domain([d3.min(vals) * 0.7, d3.max(vals) * 1.4]).range([lw, w - 12]);
      axisBottom(svg.append('g'), x, { height: Hh - 22, ticks: narrow ? 3 : 4, format: (v) => (String(v).match(narrow ? /^1/ : /^[125]/) ? fmtAED(v, { digits: 0 }) : '') });
      svg.append('text').attr('class', 'gnm-label').attr('x', lw).attr('y', 10).style('fill', theme.color.accent).text('● Buy 1 spare');
      svg.append('text').attr('class', 'gnm-label').attr('x', lw + 110).attr('y', 10).style('fill', theme.color.accent2).text('◆ Cut TAT 10 d');
      top.forEach((c, i) => {
        const yc = 32 + i * rowH;
        svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', 0).attr('y', yc + 4).text(c.pn);
        svg.append('line').attr('x1', x(c.b.cph)).attr('x2', x(c.t.cph)).attr('y1', yc).attr('y2', yc).attr('stroke', theme.color.lineStrong);
        const cb = svg.append('circle').attr('cx', x(c.b.cph)).attr('cy', yc).attr('r', 5).attr('fill', theme.color.accent);
        const ct = svg.append('path').attr('d', d3.symbol(d3.symbolDiamond, 60)()).attr('transform', `translate(${x(c.t.cph)},${yc})`).attr('fill', theme.color.accent2);
        withTooltip(cb, () => ({ title: `${c.pn} · buy 1 spare`, rows: [['AED / AOG h', fmtAED(c.b.cph)], ['AOG h/yr avoided', fmtNum(c.b.red, 1)], ['Annual holding', fmtAED(c.b.cost)], ['Unit cost', fmtAED(c.unit)]] }));
        withTooltip(ct, () => ({ title: `${c.pn} · cut TAT 10 d`, rows: [['AED / AOG h', fmtAED(c.t.cph)], ['AOG h/yr avoided', fmtNum(c.t.red, 1)], ['Annual fee', fmtAED(c.t.cost)]] }));
      });
    }));
    const med = (arr) => (arr.length ? d3.median(arr) : null);
    const bMed = med(L.filter((r) => r.lever === 'buy_1' && r.red > 0 && r.cph != null).map((r) => r.cph));
    const tMed = med(L.filter((r) => r.lever === 'tat_cut_10d' && r.red > 0 && r.cph != null).map((r) => r.cph));
    const nPn = byPn.size;
    fr.body.after(h('div', { class: 'co-levers' },
      h('div', { class: 'co-lever' }, h('div', { class: 'co-lever-k' }, icon('rotable'), 'Buy another spare'), h('div', { class: 'co-lever-v num' }, bMed != null ? fmtAED(bMed) : 'not run'), h('div', { class: 't-12 faint' }, 'median AED per AOG hour avoided · holding cost only')),
      h('div', { class: 'co-lever' }, h('div', { class: 'co-lever-k' }, icon('wrench'), 'Cut repair TAT 10 d'), h('div', { class: 'co-lever-v num' }, tMed != null ? fmtAED(tMed) : 'not run'), h('div', { class: 't-12 faint' }, levPt?.dBaseAog ? `simulated on top 8 PNs: ${signH(levPt.dBaseAog[0])}${ciTxt(levPt.dBaseAog[1], levPt.dBaseAog[2], (v) => fmtInt(v))} vs ${baseId}` : 'median AED per AOG hour avoided · acceleration fee')),
      h('div', { class: 'co-lever' }, h('div', { class: 'co-lever-k' }, icon('route'), 'Reposition stock'), h('div', { class: 'co-lever-v num' }, `${fmtInt(reposHelps)} of ${fmtInt(nPn)}`), h('div', { class: 't-12 faint' }, `PNs where moving one unit lowers modelled AOG at the ${baseId} allocation`))));
  }

  function drawVariants(host) {
    const VR = Array.isArray(F.variant_robustness) ? F.variant_robustness : [];
    const LBL = { low_stress: 'Low', central: 'Central', high_stress: 'High' };
    const rows = ['low_stress', 'central', 'high_stress'].map((k) => VR.find((v) => v.variant === k)).filter(Boolean).map((v) => {
      const d = v.rec_vs_P2 || {};
      return { k: v.variant, label: LBL[v.variant] || v.variant, p2: num(v[baseId]?.aog_hours), rec: num(v[rec.id]?.aog_hours), recCap: num(v[rec.id]?.capital_aed), p2Cap: num(v[baseId]?.capital_aed), dA: num(d.aog_reduction), dAlo: num(d.aog_reduction_ci?.[0]), dAhi: num(d.aog_reduction_ci?.[1]), nb: num(d.net_benefit_aed), nblo: num(d.net_benefit_ci?.[0]), nbhi: num(d.net_benefit_ci?.[1]), pick: v.rule_recommends || '—' };
    });
    if (!rows.length) { host.append(card({ title: 'Stress variants', prov, body: h('p', { class: 'muted m-0' }, 'Variant robustness not run.') })); return; }
    const low = rows.find((r) => r.k === 'low_stress');
    const tbl = dataTable({
      caption: 'Stress-variant robustness', dense: true, bare: true,
      columns: [
        { key: 'label', label: 'Stress' }, { key: 'p2', label: baseId, num: true, format: fmtHours }, { key: 'rec', label: rec.id, num: true, format: fmtHours },
        { key: 'dA', label: 'Saved', num: true, render: (r) => h('span', { class: 'co-two' }, fmtHours(r.dA), h('small', {}, ciTxt(r.dAlo, r.dAhi, (v) => fmtNum(v, Math.abs(v) < 20 ? 1 : 0)).trim())) },
        { key: 'nb', label: 'Net / yr', num: true, render: (r) => h('span', { class: `co-two ${r.nbhi < 0 ? 'co-neg' : ''}` }, h('span', {}, r.nbhi < 0 ? icon('alert') : null, fmtAED(r.nb)), h('small', {}, ciTxt(r.nblo, r.nbhi, (v) => fmtAED(v).replace('AED ', '')).trim())) },
        { key: 'pick', label: 'Rule', mono: true },
      ],
      rows,
    });
    tbl.classList.add('co-var');
    host.append(card({
      kicker: 'Robustness · selection seeds 100–119', title: `Does ${rec.id} survive a different reliability world?`, prov,
      body: h('div', { class: 'stack-3' }, tbl,
        low && low.nb < 0 ? h('p', { class: 'co-honest m-0' }, icon('alert'), h('span', {}, `In the low-stress world ${rec.id} is not worth its extra capital over ${baseId}: it saves ${fmtHours(low.dA)}${ciTxt(low.dAlo, low.dAhi, (v) => fmtNum(v, 1))}${low.dAlo != null && low.dAlo < 0 ? ' (not significant)' : ''} for ${low.recCap != null && low.p2Cap != null ? `${fmtAED(low.recCap - low.p2Cap)} more capital, and` : ''} costs ${fmtAED(-low.nb)} a year net. The rule would pick ${low.pick} there. The extra capital is insurance against a harsher world.`)) : null,
        h('p', { class: 't-12 faint m-0' }, `Allocations were planned on central inputs and re-simulated in each world. Net benefit = avoided AOG penalty − extra holding cost, paired against ${baseId}.`)),
    }));
  }

  // ---- method & limitations
  const deskO = typeof F.aog_desk_dependence === 'object' ? F.aog_desk_dependence : null;
  const desk = deskO && deskO.base_aog_hours != null ? { p0_base_aog_hours: deskO.p0_aog_hours, base_aog_hours: deskO.base_aog_hours, rec_aog_hours: deskO.rec_aog_hours } : (F.tornado || []).find((t) => t.factor === 'aog_desk_expedite');
  el.append(card({
    cls: 'mt-3', kicker: 'Method and limitations', title: 'What this frontier can and cannot tell you', prov: 'ASSUMED',
    body: h('div', { class: 'co-limits' },
      h('div', {}, h('h4', {}, icon('chart'), 'Greedy marginal allocation is a heuristic'), h('p', {}, 'Budget points come from a greedy walk that adds the unit with the largest modelled delay-cost reduction per AED. Greedy is optimal only for separable convex problems; with hub/outstation coupling, the expedite drift and the wait cap it is a heuristic. The analytic model only ranks candidates; the simulator judges every plan.')),
      h('div', {}, h('h4', {}, icon('alert'), 'Conditional on an AOG-desk market'), h('p', {}, (typeof F.aog_desk_dependence === 'object' ? F.aog_desk_dependence?.text : F.aog_desk_dependence) || 'Every policy leans on the simulated AOG-desk emergency purchase.'),
        desk ? h('p', { class: 'mono t-12' }, `Expedite off (selection seeds): P0 ${fmtHours(num(desk.p0_base_aog_hours))} · ${baseId} ${fmtHours(num(desk.base_aog_hours))} · ${rec.id} ${fmtHours(num(desk.rec_aog_hours))} a year`) : null),
      h('div', {}, h('h4', {}, icon('capital'), 'Capital is partly endogenous'), h('p', {}, 'Simulated capital includes units the AOG desk buys during the run, so a plan’s capital is its starting allocation plus what the run had to buy. CIs are over 20 seeds of one world; the stress variants show the knee moves with true reliability.'))),
  }));

  return () => { stopChart(); stops.forEach((s) => s()); };
}
