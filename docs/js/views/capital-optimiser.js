/**
 * 06 · Capital Optimiser.
 * Data: frontier.json (+ policies.json for reference-policy cost components when a point lacks them)
 * Deep links: #/capital?point=I125&view=holdout|selection|overlay
 * Shows: the Readiness Frontier (capital vs expected material AOG h/yr, holdout means with 95% CI
 * whiskers, the non-dominated set connected, dominated points muted, P0/P1/P2 labelled, the recommended
 * point annotated), a selection-vs-holdout toggle/overlay, a budget slider that walks the frontier and
 * drives the allocation table, the annual cost breakdown (capital shown separately, never summed), the
 * sensitivity tornado, the lever panel, the stress-variant table and the method limitations.
 */
import { h, pageHead, card, provChip, slider, dataTable, segmented, kpiTile, icon, intro3, scopeLine, capitalTable, tooltip } from '../ui.js';
import { isSimple } from '../lib/mode.js';
import { throttleRAF, countUpOnce, dur, EASE } from '../lib/motion.js';
/**
 * A transition created ON the selection itself with the motion tokens (same timing as chartTransition()). It never
 * inherits from a document-level transition, so a newer transition elsewhere on the site can never cancel its parent
 * and throw "transition N not found" (seen when a shortcut navigates away mid-animation).
 */
const tx = (sel, { duration = 'base', ease = 'standard', name } = {}) => sel.transition(name).duration(dur(duration)).ease(EASE[ease] || EASE.standard);
import { term, termText, FRONTIER_SUBTITLE } from '../lib/glossary.js';
import { displayName, nameTag, relabelArchetype } from '../lib/names.js';
const relabelArchetypeSafe = (t) => (typeof relabelArchetype === 'function' ? relabelArchetype(String(t)) : String(t));
import { chartFrame, responsive, svgIn, axisBottom, withTooltip, theme, fmtAED, fmtHours, fmtInt, fmtNum, reducedMotion, truncate, HEADLINE_MAX, markerRect, labelAround, fmtMult, refLine, stripRefs, stressWorldsText } from '../charts/theme.js';

export const data = ['frontier', 'policies', 'parts'];

const CAPITAL_KINDS = new Set(['policy', 'baseline', 'budget', 'incremental', 'reposition', 'frontier', 'recommended', 'candidate']);
/** A3 display names (names.js): full name in prose, short name in tight chart labels; the code is an expert-only tag. */
const planName = (id) => displayName(id);
const sn = (id) => displayName(id, { mode: 'short' });
/** v2.1 wording rule: the frontier option is the "best evaluated allocation under the stated scenario". */
const BEST_EVAL = 'best evaluated allocation under the stated scenario';
const KIND_LABEL_X = { policy: 'Reference policy', baseline: 'Reference policy', greedy: 'Budget point', budget: 'Re-optimised budget point', incremental: 'Base + greedy additions', lever: 'Lever (annual spend, not capital)', combo: 'Budget point + lever', reposition: 'Reposition only', frontier: 'Frontier point', recommended: 'Recommended', candidate: 'Candidate' };
const KIND_LABEL_S = { policy: 'Reference plan', baseline: 'Reference plan', greedy: 'Budget plan', budget: 'Budget plan', incremental: 'Network Plan plus extra spares', lever: 'Faster repair (yearly spend, not spares)', combo: 'Budget plan + faster repair', reposition: 'Move existing spares only', frontier: 'Frontier plan', recommended: 'Frontier option', candidate: 'Candidate' };
const KIND_LABEL = new Proxy({}, { get: (_, k) => (isSimple() ? KIND_LABEL_S : KIND_LABEL_X)[k] });
const LEVER_LABEL_X = { buy_1: 'Buy 1 spare', buy_2: 'Buy 2 spares', tat_cut_10d: 'Cut repair TAT 10 d', reposition_1: 'Reposition 1 unit' };
const LEVER_LABEL_S = { buy_1: 'Buy 1 spare', buy_2: 'Buy 2 spares', tat_cut_10d: 'Repair 10 days faster', reposition_1: 'Move 1 spare' };
const LEVER_LABEL = new Proxy({}, { get: (_, k) => (isSimple() ? LEVER_LABEL_S : LEVER_LABEL_X)[k] });
const COMP = [
  { key: 'aog_penalty', label: 'AOG penalty', simple: 'Cost of grounded hours' },
  { key: 'holding_cost', label: 'Holding', simple: 'Holding spares' },
  { key: 'repair_cost', label: 'Repair', simple: 'Repair' },
  { key: 'expedite_cost', label: 'Expedite', simple: 'Rush orders' },
  { key: 'logistics_cost', label: 'Logistics', simple: 'Shipping' },
].map((c) => ({ ...c, get label() { return isSimple() ? c.simple : c.label; } }));
const FACTOR_LABEL_X = { aog_penalty: 'AOG penalty', carrying_cost: 'Carrying cost', repair_tat: 'Repair TAT', lead_time: 'Lead time', aog_desk_expedite: 'AOG-desk routes' };
const FACTOR_LABEL_S = { aog_penalty: 'Cost per grounded hour', carrying_cost: 'Holding cost', repair_tat: 'Repair time', lead_time: 'Supplier time', aog_desk_expedite: 'Urgent-parts routes' };
const FACTOR_LABEL = new Proxy({}, { get: (_, k) => (isSimple() ? FACTOR_LABEL_S : FACTOR_LABEL_X)[k] });
const num = (v) => (v === null || v === undefined || v === '' || Number.isNaN(+v) ? null : +v);
/** v2.2: both CI bounds in the same unit ("[0.0M, 1.9M]", never "[695, 1.9M]"). */
const sameUnitM = (v, lo, hi) => (Math.max(Math.abs(lo ?? 0), Math.abs(hi ?? 0)) >= 1e6 ? `${v < 0 ? '−' : ''}${(Math.abs(v) / 1e6).toFixed(1)}M` : fmtAED(v).replace('AED ', ''));
const ciTxt = (lo, hi, f) => (lo == null || hi == null ? '' : ` [${f(lo)}, ${f(hi)}]`);
const signH = (v) => (v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtHours(Math.abs(v))}`);
const signAED = (v) => fmtAED(v, { sign: true });
/** v2.2: one rounding source for capital differences: the difference of the two values AS DISPLAYED (0.1M / 1k), so
 *  "AED 56.7M − AED 48.4M" always reads "+AED 8.3M" wherever it appears. */
const rCap = (v) => (Math.abs(v) >= 1e6 ? Math.round(v / 1e5) * 1e5 : Math.round(v / 1e3) * 1e3);
const dCap = (a, b) => rCap(a) - rCap(b);
/** Capital vs the Network Plan: the PAIRED frontier value d_capital_vs_P2_aed when exported (CEO review row 13). */
const capVsP2 = (p, P2) => (p?.dBaseCap?.[0] != null ? p.dBaseCap[0] : dCap(p.cap, P2.cap));
/** Tornado setting: "x0.5" → "×0.5"; a bare rate "0.15" → "15%"; anything else as exported. */
const settingTxt = (st) => { const t = String(st ?? '').trim(); const m = t.match(/^[x×]\s*([\d.]+)$/i); if (m) return fmtMult(+m[1], m[1].includes('.') ? (m[1].split('.')[1].length) : 1); if (/^0?\.\d+$/.test(t)) return `${Math.round(+t * 100)}%`; return t; };
/** First candidate headline that fits the 90-character rule (data-driven copy can vary in length). */
export const fitHeadline = (...cands) => { const c = cands.filter(Boolean); return c.find((t) => t.length <= (HEADLINE_MAX || 90)) || c.at(-1); };
const SER = theme.series;
/** "AED 4.8M more capital" (no sign: reads well after "for"). Capital deltas are neutral copy, never red. */
const capWords = (v) => (v == null ? '—' : v === 0 ? 'no extra capital' : `${fmtAED(Math.abs(v))} ${v > 0 ? 'more' : 'less'} capital`);

/** Charts draw in once (slow token) on first render; later redraws (resize) and reduced motion are instant. */
function drawIn(svgSel, host) {
  if (!svgSel || host.__drawn) return;
  host.__drawn = true;
  if (!dur('slow')) return;
  tx(svgSel.style('opacity', 0), { duration: 'slow', ease: 'enter' }).style('opacity', 1);
}

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
  // wait for the view stylesheet before building the DOM: an unstyled first paint shifts the layout (CLS)
  await new Promise((res) => { const l = document.querySelector('link[data-view-css="capital-optimiser"]'); if (!l || l.sheet) return res(); l.addEventListener('load', res, { once: true }); l.addEventListener('error', res, { once: true }); setTimeout(res, 3000); });
  const d3 = window.d3;
  const { frontier: F, policies: POL } = ctx.data;
  const prov = F.meta?.provenance || F.provenance || 'SIMULATED';
  const stops = [];
  let dead = false;
  const selById = new Map((F.selection_points || []).map((q) => [q.id, q]));
  const pts = (F.points || []).map((p) => normPoint(p, selById.get(p.id))).filter((p) => p.cap != null && p.aog != null);
  const byId = new Map(pts.map((p) => [p.id, p]));
  const baseId = F.base_policy || F.base_policy_id || (byId.has('P2') ? 'P2' : F.baseline);
  const P0 = byId.get('P0') || byId.get(F.baseline);
  const P2 = byId.get(baseId);
  const P1 = byId.get('P1');
  const rec = byId.get(F.recommended) || pts.find((p) => p.kind === 'recommended') || pts[0];
  const split = F.split || F.meta?.split || 'holdout';
  const seedsTxt = F.seeds_label || (split === 'holdout' ? 'holdout seeds' : 'selection seeds 100–119');
  const holdRange = (F.seeds_label || '').replace(/^holdout seeds\s*/, '');
  const hasSel = pts.some((p) => p.sel && p.sel.aog != null);
  const H = (p) => ({ cap: p.cap, aog: p.aog, ci: p.ci });
  const SEL = (p) => (p.sel && p.sel.aog != null ? { cap: p.sel.cap ?? p.cap, aog: p.sel.aog, ci: p.sel.ci } : null);
  const capPts = pts.filter(isCapital);
  const front = (() => {
    const flagged = capPts.filter((p) => !p.dominated).sort((a, b) => a.cap - b.cap);
    return flagged.length >= 2 ? frontierOf(flagged, H) : frontierOf(capPts, H);
  })();
  const frontSel = hasSel ? frontierOf(capPts, SEL) : [];
  const policyByName = (id) => (POL?.policies || []).find((q) => q.policy_id === id);

  let mode = ['holdout', 'selection', 'overlay'].includes(ctx.params.view) && (hasSel || ctx.params.view === 'holdout') ? ctx.params.view : 'holdout';
  let sel = byId.get(ctx.params.point) && front.includes(byId.get(ctx.params.point)) ? byId.get(ctx.params.point) : front.includes(rec) ? rec : front[0];

  // ---- header
  const S = isSimple();
  const recN = rec ? sn(rec.id) : '', baseN = sn(baseId), p0N = P0 ? sn(P0.id) : 'Simple Rulebook';
  el.append(pageHead({
    num: '06', eyebrow: 'Capital Optimiser', title: 'The Readiness Frontier',
    lede: S
      ? `Every dot is a full stocking plan for a fictional airline, tested in the model. The curve shows the best plans found for each budget (a step-by-step search, then tested in the model). That money is shown apart from yearly running costs and never added to them.`
      : `Every dot is a complete stocking plan for Falcon Hub Airways (fictional), simulated on paired seeds. The frontier shows the best plans found for each budget (greedy search, then simulated), not a proven best. Capital is a balance-sheet stock, so it is shown apart from annual operating cost and never added to it.`,
    meta: [provChip(prov), h('span', { class: 'chip chip-mono' }, split === 'holdout' ? (S ? '20 fresh test runs · central world' : 'Holdout · central') : `${split} · central`)],
  }));
  el.querySelector('.page-head h1')?.after(h('p', { class: 'co-subtitle', dataset: { role: 'frontier-subtitle' } }, F.subtitle || FRONTIER_SUBTITLE));
  el.append(intro3({
    what: ['Each dot is a stocking plan. It shows the money tied up in spares against the ', term('aog_hours'), ' it leaves.'],
    why: ['Spares cost money to hold. Past a point, each extra dirham buys less readiness, and other levers can do better.'],
    action: [`Start from the ${baseN}. Add spares only while each step still pays for its holding cost, and compare with faster repair first.`],
  }));

  // ---- KPI strip (constructed from frontier points; compared with the base policy P2 — 'baseline' is P0 only)
  if (rec && P2) {
    const capTile = kpiTile({ label: S ? `${recN}: money in spares` : `${recN} simulated capital`, value: rec.cap, baseline: P2.cap, baseline_label: baseN, delta: capVsP2(rec, P2), better: 'lower', provenance: prov, ci: rec.capCI[0] != null ? rec.capCI : null }, { format: fmtAED, deltaFormat: (v) => fmtAED(v), capital: true });
    // One AOG tile with both comparisons (vs the base policy and vs P0), instead of the same value twice.
    const aogTile = kpiTile({ label: S ? `${recN}: hours grounded a year` : `${recN} AOG / yr`, value: rec.aog, baseline: P2.aog, baseline_label: baseN, delta: rec.aog - P2.aog, better: 'lower', provenance: prov, ci: rec.ci }, { format: fmtHours });

    if (P0) {
      const d0 = rec.aog - P0.aog;
      const second = h('span', { class: `kpi-delta co-delta2 is-${d0 < 0 ? 'good' : d0 > 0 ? 'bad' : 'flat'}` }, icon(d0 < 0 ? 'arrow-down' : d0 > 0 ? 'arrow-up' : 'minus'), `${d0 > 0 ? '+' : d0 < 0 ? '−' : ''}${fmtHours(Math.abs(d0))}`, h('span', { class: 'kpi-delta-ref' }, ` vs ${p0N}`));
      aogTile.querySelector('.kpi-delta')?.after(second);
      const foot = aogTile.querySelector('.kpi-foot span:last-child');
      if (foot) foot.textContent = `${baseN} ${fmtHours(P2.aog)} · ${p0N} ${fmtHours(P0.aog)}`;
      aogTile.setAttribute('aria-label', `${recN} hours grounded per year: ${fmtHours(rec.aog)}; ${fmtHours(Math.abs(rec.aog - P2.aog))} ${rec.aog < P2.aog ? 'below' : 'above'} ${baseN}, ${fmtHours(Math.abs(d0))} ${d0 < 0 ? 'below' : 'above'} ${p0N}`);
    }
    const costTile = rec.total != null && P2.total != null ? kpiTile({ label: S ? `${recN}: yearly cost` : `${recN} annual cost`, value: rec.total, baseline: P2.total, baseline_label: baseN, delta: rec.total - P2.total, better: 'lower', provenance: prov, ci: rec.totalCI }, { format: fmtAED }) : null;
    const tiles = [capTile, aogTile, costTile].filter(Boolean);
    tiles.forEach((t) => {
      const r = t.querySelector('.kpi-delta-ref'); if (r) r.textContent = ` vs ${baseN}`; t.querySelector('.kpi-spark')?.remove();
      const ci = t.querySelector('.kpi-foot span:first-child');
      if (S && ci) ci.textContent = ci.textContent.replace(/^95% CI/, 'Likely range');
      const w = t.querySelector('.kpi-delta-word'); if (S && w) w.textContent = w.textContent.replace('capital', 'in spares');
    });
    tiles.forEach((t) => t.classList.add(tiles.length === 3 ? 'span-4' : 'span-6'));
    // KPI numbers count up ONCE per session (stable keys); re-renders and mode toggles print the final value
    [[capTile, rec.cap, (v) => fmtAED(v).replace(/^AED\s/, '')], [aogTile, rec.aog, (v) => fmtHours(v).replace(/\s?h$/, '')], [costTile, rec.total, (v) => fmtAED(v).replace(/^AED\s/, '')]].forEach(([t, v, f], i) => {
      const val = t?.querySelector('.kpi-value');
      const tn = val && [...val.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
      if (!tn || v == null || tn.textContent.trim() !== f(v)) return;
      const span = h('span', { class: 'kpi-num' }, tn.textContent);
      tn.replaceWith(span);
      countUpOnce(span, v, f, { key: `capital-kpi-${i}-${rec.id}` });
    });
    el.append(h('div', { class: `grid-12 co-kpis co-kpis--${tiles.length}`, dataset: { story: 'capital-kpis' } }, tiles));
  }

  // ---- hero: frontier chart + control panel
  const chartCard = h('section', { class: 'card card--bp co-hero', dataset: { story: 'frontier-chart' } });
  const side = h('div', { class: 'span-4 co-side' });
  // the rule card sits under the frontier (left column), so the chart card never stretches to the side column's height
  const mainCol = h('div', { class: 'span-8 co-main' }, chartCard);
  el.append(h('div', { class: 'grid-12 mt-3 co-hero-grid' }, mainCol, side));
  const recVsP2 = rec?.dBaseAog;
  const headline = rec && P2 && P0
    // v2 framing: P2 is the core result; the rule's pick is a frontier option for additional capital
    ? (S ? fitHeadline(`${fmtAED(capVsP2(rec, P2))} more in spares than the ${baseN} cuts a further ${fmtHours(Math.abs(P2.aog - rec.aog))} grounded a year`,
      `${fmtAED(capVsP2(rec, P2))} more in spares buys ${fmtHours(Math.abs(P2.aog - rec.aog))} less grounded time a year`)
      : fitHeadline(`If you invest ${fmtAED(capVsP2(rec, P2))} more than the ${baseN}, ${recN} removes a further ${fmtHours(Math.abs(P2.aog - rec.aog))} of AOG a year`,
        `${fmtAED(capVsP2(rec, P2))} more than ${baseN} buys ${recN}: ${fmtHours(Math.abs(P2.aog - rec.aog))} less AOG a year`))
    : 'Frontier: capital versus material AOG hours';
  const tableRows = pts.slice().sort((a, b) => a.cap - b.cap).map((p) => ({ id: planName(p.id), kind: KIND_LABEL[p.kind] || p.kind, cap: p.cap, aog: p.aog, lo: p.ci[0], hi: p.ci[1], sel: p.sel?.aog ?? null, front: front.includes(p) ? 'yes' : 'no' }));
  const frame = chartFrame(chartCard, {
      implication: S ? `The ${baseN} is the efficient base. Each extra dirham buys a smaller cut in grounded time, so a stopping rule decides how far to go.` : `The ${baseN} is the efficient base; extra capital buys smaller downtime cuts, so a stopping rule decides how far to go.`,
    headline,
    subtitle: S ? 'Money in spares (AED) against hours grounded a year (log scale) · 20 fresh test runs · average and likely range' : `Spare capital (AED, simulated) vs expected material AOG h/yr (log scale) · ${seedsTxt} · central variant · mean and 95% CI`,
    provenance: prov, source: 'frontier.json',
    table: { columns: [{ key: 'id', label: 'Plan' }, { key: 'kind', label: 'Kind' }, { key: 'cap', label: 'Capital', num: true, format: (v) => fmtAED(v) }, { key: 'aog', label: S ? 'Grounded h/yr' : 'AOG h/yr', num: true, format: fmtHours }, { key: 'lo', label: S ? 'Range low' : 'CI lo', num: true, format: fmtHours }, { key: 'hi', label: S ? 'Range high' : 'CI hi', num: true, format: fmtHours }, { key: 'sel', label: S ? 'Tuning runs h' : 'Selection AOG h', num: true, format: (v) => (v == null ? 'not exported' : fmtHours(v)) }, { key: 'front', label: S ? 'On the curve' : 'Non-dominated' }], rows: tableRows },
  });
  const legend = h('div', { class: 'co-legend t-12' },
    h('span', {}, h('i', { class: 'co-key co-key--front' }), S ? 'Best plans for their cost (connected)' : 'Non-dominated plans (connected)'),
    h('span', {}, h('i', { class: 'co-key co-key--dom' }), S ? 'Beaten by a cheaper plan' : 'Dominated'),
    P0 ? h('span', {}, h('i', { class: 'co-key co-key--p0' }), `${p0N} (starting point)`) : null,
    h('span', {}, h('i', { class: 'co-key co-key--pol' }), `${P1 ? `${sn('P1')} / ` : ''}${baseN}`),
    h('span', {}, h('i', { class: 'co-key co-key--lev' }), S ? 'Faster repair (yearly spend)' : 'Levers (annual spend)'),
    h('span', { class: 'co-legend-sel', hidden: mode !== 'overlay' }, h('i', { class: 'co-key co-key--sel' }), S ? 'Position in the tuning runs' : 'Selection-seed position'));
  frame.body.before(legend);
  const annoteHTML = h('div', { class: 'co-annote', hidden: true });
  // A6 under the frontier: the stress-world range and what the likely ranges do (and do not) cover; then the scope line
  const SW = F.stress_worlds || {};
  frame.body.after(annoteHTML,
    h('p', { class: 'co-a6 t-12 m-0', dataset: { role: 'stress-ranges' } }, h('span', { dataset: { readability: 'skip' } }, `Stress worlds: ${stressWorldsText(SW) || 'not exported'}.`), ' ', SW.ranges_note || ''),
    scopeLine());

  let chart = null;
  const stopChart = responsive(frame.body, (w) => { chart = drawFrontier(frame.body, w); });

  function drawFrontier(body, w) {
    const narrow = w < 560;
    const hgt = narrow ? 340 : w >= 640 ? 680 : 440; // tall enough to match the controls + rule column (no dead space)
    const m = { top: 28, right: narrow ? 30 : 36, bottom: 44, left: narrow ? 44 : 56 };
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
    g.append('text').attr('class', 'gnm-label').attr('x', -m.left + 4).attr('y', -14).style('fill', theme.color.faint).text(S ? 'Grounded h / yr' : 'AOG h / yr');
    if (!narrow) g.append('text').attr('class', 'gnm-label').attr('x', iw).attr('y', ih + 36).attr('text-anchor', 'end').style('fill', theme.color.faint).text(S ? 'Money in spares →' : 'Spare capital →');

    const gBand = g.append('g'), gWhisk = g.append('g'), gLine = g.append('g'), gLinks = g.append('g'), gGhost = g.append('g'), gPts = g.append('g'), gLab = g.append('g'), gAnn = g.append('g'), gSel = g.append('g');
    // overlays never take the pointer, so every clickable frontier dot stays reachable
    [gBand, gWhisk, gLine, gLinks, gGhost, gLab, gAnn, gSel].forEach((q) => q.style('pointer-events', 'none'));
    const firstDraw = !body.__drawn;

    const posOf = (p, md) => (md === 'selection' ? SEL(p) || H(p) : H(p));
    const lineGen = d3.line().x((d) => x(d.cap)).y((d) => y(d.aog)).curve(d3.curveMonotoneX);
    const areaGen = d3.area().x((d) => x(d.cap)).y0((d) => y(Math.max(yMin, d.ci[0] ?? d.aog))).y1((d) => y(d.ci[1] ?? d.aog)).curve(d3.curveMonotoneX);

    function update(animate = true) {
      const md = mode === 'selection' ? 'selection' : 'holdout';
      const fr = md === 'selection' ? frontSel : front;
      // one transition per selection (a shared transition throws "transition N not found" once it has ended)
      const T = (s) => (animate && !dead ? tx(s) : s);
      const frPos = fr.map((p) => posOf(p, md));
      T(gBand.selectAll('path').data([frPos]).join('path').attr('fill', theme.color.accent).attr('fill-opacity', 0.09)).attr('d', areaGen);
      T(gLine.selectAll('path').data([frPos]).join('path').attr('fill', 'none').attr('stroke', theme.color.accent).attr('stroke-width', 2)).attr('d', lineGen);
      // whiskers
      const wh = gWhisk.selectAll('line').data(pts, (p) => p.id).join('line').attr('stroke-linecap', 'round');
      T(wh).attr('x1', (p) => x(posOf(p, md).cap)).attr('x2', (p) => x(posOf(p, md).cap))
        .attr('y1', (p) => y(Math.max(yMin, posOf(p, md).ci?.[0] ?? posOf(p, md).aog))).attr('y2', (p) => y(posOf(p, md).ci?.[1] ?? posOf(p, md).aog))
        .attr('stroke', (p) => (p === P0 ? SER.baseline : isPolicy(p) ? SER.neutral : fr.includes(p) ? theme.color.accent : theme.color.neutral)).attr('stroke-opacity', (p) => (fr.includes(p) || isPolicy(p) ? 0.55 : 0.3)).attr('stroke-width', 1.25);
      // points
      const sizeOf = (p) => (p === rec ? 150 : isPolicy(p) ? 90 : fr.includes(p) ? 52 : 30);
      const px = (p) => [x(posOf(p, md).cap), y(posOf(p, md).aog)];
      // draw order among frontier dots: data order, the frontier option last. A dot whose centre lies under a dot drawn
      // after it cannot be clicked, so it leaves the tab order / pointer path (the budget slider still reaches it)
      const ord = (p) => (p === rec ? Infinity : pts.indexOf(p));
      const rad = (q) => Math.sqrt(sizeOf(q) / Math.PI) + 1.5;
      const covered = new Set(front.filter((p) => p !== rec && front.some((q) => q !== p && ord(q) > ord(p) && Math.hypot(px(q)[0] - px(p)[0], px(q)[1] - px(p)[1]) < rad(q))));
      const live = (p) => front.includes(p) && !covered.has(p);
      const shape = (p) => (isPolicy(p) ? d3.symbolSquare : p.kind === 'lever' || p.kind === 'combo' ? d3.symbolDiamond : d3.symbolCircle);
      const size = (p) => (p === rec ? 150 : isPolicy(p) ? 90 : fr.includes(p) ? 52 : 30);
      const pp = gPts.selectAll('path.co-pt').data(pts, (p) => p.id).join((en) => en.append('path').attr('class', 'co-pt').attr('transform', (p) => `translate(${x(posOf(p, md).cap)},${y(posOf(p, md).aog)})`));
      pp.attr('d', (p) => d3.symbol(shape(p), size(p))())
        // wave C: teal marks P2 (the core plan); the frontier option I125 is a neutral, secondary marker
        .attr('fill', (p) => (p === P2 ? theme.color.accent : p === rec ? SER.neutral : isPolicy(p) ? theme.color.bg : fr.includes(p) ? theme.color.bg : theme.color.neutral))
        .attr('fill-opacity', (p) => (fr.includes(p) || isPolicy(p) || p === rec ? 1 : 0.55))
        .attr('stroke', (p) => (p === P0 ? SER.baseline : p === P2 ? theme.color.accent : p === rec ? SER.neutral : isPolicy(p) ? SER.neutral : fr.includes(p) ? theme.color.accent : p.kind === 'lever' || p.kind === 'combo' ? theme.color.muted : 'none'))
        .attr('stroke-width', (p) => (isPolicy(p) ? 2 : 1.5)).style('cursor', 'pointer')
        .attr('tabindex', (p) => (live(p) ? 0 : null)).attr('role', (p) => (live(p) ? 'button' : null))
        .style('pointer-events', (p) => (front.includes(p) && !live(p) ? 'none' : null))
        .attr('aria-label', (p) => `${displayName(p.id, { mode: 'code' })}: ${fmtAED(p.cap)}, ${fmtHours(p.aog)} per year`);
      T(pp).attr('transform', (p) => `translate(${x(posOf(p, md).cap)},${y(posOf(p, md).aog)})`);
      const tipOf = (p) => ({
        title: `${S ? sn(p.id) : displayName(p.id, { mode: 'code' })} · ${KIND_LABEL[p.kind] || p.kind}`,
        rows: S ? [['Money in spares', fmtAED(p.cap)], ['Grounded h/yr (test runs)', `${fmtHours(p.aog)}${ciTxt(p.ci[0], p.ci[1], fmtInt)}`], p.sel?.aog != null ? ['Grounded h/yr (tuning runs)', fmtHours(p.sel.aog)] : null, p.dBaseAog ? [`Change vs ${baseN}`, `${signH(p.dBaseAog[0])}${ciTxt(p.dBaseAog[1], p.dBaseAog[2], (v) => fmtInt(v))}`] : null].filter(Boolean)
          : [['Capital', fmtAED(p.cap)], ['AOG h/yr (holdout)', `${fmtHours(p.aog)}${ciTxt(p.ci[0], p.ci[1], fmtInt)}`], p.sel?.aog != null ? ['AOG h/yr (selection)', fmtHours(p.sel.aog)] : null, p.dBaseAog ? [`Δ vs ${baseN} (paired)`, `${signH(p.dBaseAog[0])}${ciTxt(p.dBaseAog[1], p.dBaseAog[2], (v) => fmtInt(v))}`] : null].filter(Boolean),
        note: front.includes(p) ? (S ? 'On the curve · click to see where its spares go' : 'On the frontier · click to inspect its allocation') : p.kind === 'lever' || p.kind === 'combo' ? (S ? 'Adds yearly spend, not spares' : 'Adds annual spend, not capital: reported beside the rule') : p.dominated ? (S ? 'Another plan is cheaper and no worse' : 'Dominated: another plan is cheaper and no worse') : '',
      });
      withTooltip(pp, tipOf);
      // keyboard: focusing a dot shows the same tooltip (a visible effect), blur hides it
      pp.on('focus', function (e, p) { const r = this.getBoundingClientRect(); tooltip.show({ clientX: r.right, clientY: r.bottom }, tipOf(p)); }).on('blur', () => tooltip.hide());
      // frontier dots sit above the rest; a frontier dot hidden under a bigger one (same spot) is reached by the slider
      pp.filter((p) => front.includes(p)).sort((a, b) => ord(a) - ord(b)).raise();
      pp.filter((p) => p === rec).raise();
      pp.on('click', (e, p) => { if (live(p)) choose(p, true); })
        .on('keydown', (e, p) => { if ((e.key === 'Enter' || e.key === ' ') && live(p)) { e.preventDefault(); choose(p, true); } });
      // overlay ghosts + links
      const ov = mode === 'overlay' ? pts.filter((p) => SEL(p)) : [];
      gLinks.selectAll('line').data(ov, (p) => p.id).join('line').attr('stroke', theme.color.muted).attr('stroke-opacity', 0.35).attr('stroke-dasharray', '2 3')
        .attr('x1', (p) => x(p.cap)).attr('y1', (p) => y(p.aog)).attr('x2', (p) => x(SEL(p).cap)).attr('y2', (p) => y(SEL(p).aog));
      gGhost.selectAll('circle').data(ov, (p) => p.id).join('circle').attr('r', 3).attr('fill', 'none').attr('stroke', theme.color.muted).attr('stroke-opacity', 0.8)
        .attr('cx', (p) => x(SEL(p).cap)).attr('cy', (p) => y(SEL(p).aog));
      legend.querySelector('.co-legend-sel').hidden = mode !== 'overlay';
      // policy labels
      const pols = [P0, P1, P2].filter(Boolean);
      const labs = gLab.selectAll('text').data(pols, (p) => p.id).join('text').attr('class', 'gnm-label gnm-label--strong').style('fill', (p) => (p === P0 ? SER.baseline : SER.neutral)).attr('font-family', theme.font.mono);
      // a label that would run past the plot's right edge flips to the left of its marker (long display names at 390)
      const flip = (p) => p === P2 || (p !== P2 && x(posOf(p, md).cap) + 10 + sn(p.id).length * 6.6 > iw + m.right - 4);
      T(labs).attr('x', (p) => x(posOf(p, md).cap) + (flip(p) ? -10 : 10)).attr('y', (p) => y(posOf(p, md).aog) + (p === P2 ? 20 : 0)).attr('dy', '0.32em').attr('text-anchor', (p) => (flip(p) ? 'end' : 'start'))
        .text((p) => (p.id === baseId && !narrow ? `${sn(p.id)} · core plan` : sn(p.id)));
      // annotation on recommended
      gAnn.selectAll('*').remove();
      if (rec) {
        const rp = posOf(rec, md);
        const ax = x(rp.cap), ayy = y(rp.aog);
        const lines = [
          [`Frontier option · ${recN}${md === 'selection' ? (S ? ' (tuning runs)' : ' (selection seeds)') : ''}`, 'gnm-annot-text'],
          [`${fmtAED(rp.cap)} · ${fmtHours(rp.aog)}/yr${ciTxt(rp.ci?.[0], rp.ci?.[1], fmtInt)}`, 'gnm-annot-sub'],
        ];
        if (md !== 'selection' && P2 && rec.dBaseAog) lines.push([`vs ${baseN}: ${signH(rec.dBaseAog[0])}${ciTxt(rec.dBaseAog[1], rec.dBaseAog[2], (v) => fmtInt(v))} h · ${signAED(capVsP2(rec, P2))}`, 'gnm-annot-sub']);
        if (md !== 'selection' && P0) lines.push([`vs ${p0N}: ${signH(rec.aog - P0.aog)}${rec.dP0Aog ? ciTxt(rec.dP0Aog[1], rec.dP0Aog[2], (v) => fmtInt(v)) : ''} · ${signAED(dCap(rec.cap, P0.cap))}`, 'gnm-annot-sub']);
        // long display names: when the call-out would not fit beside the point, it moves under the chart (HTML), as on phones
        const lineW = d3.max(lines, ([t, c]) => t.length * (c === 'gnm-annot-text' ? 7.2 : 6.6)) + 12;
        const fitsR = ax + 46 + lineW <= iw + m.right - 4, fitsL = ax - 46 - lineW >= -m.left + 4;
        if (narrow || (!fitsR && !(ax > iw * 0.55 && fitsL))) {
          const txt = 'Frontier option';
          const obstacles = pts.map((p) => markerRect(x(posOf(p, md).cap), y(posOf(p, md).aog), p === rec ? 8 : 4));
          // wave C: the policy labels (P0 / P1 / P2) are obstacles too, so the option label never covers "P2" at 390
          pols.forEach((p) => { const t = sn(p.id), w = t.length * 7 + 4, lx = x(posOf(p, md).cap) + (flip(p) ? -10 - w : 10), ly = y(posOf(p, md).aog) + (p === P2 ? 20 : 0); obstacles.push({ x: lx - 2, y: ly - 9, width: w + 4, height: 18 }); });
          const centroid = { x: d3.mean(fr, (p) => x(posOf(p, md).cap)), y: d3.mean(fr, (p) => y(posOf(p, md).aog)) };
          const lp = labelAround({ x: ax, y: ayy }, { r: 12, text: txt, centroid, obstacles, bounds: { x: 0, y: 0, width: iw, height: ih } });
          gAnn.append('text').attr('class', 'gnm-annot-text').attr('x', lp.x).attr('y', lp.y).attr('dy', '0.32em').attr('text-anchor', lp.anchor).text(txt);
          annoteHTML.replaceChildren(...lines.map(([t], i) => h('div', { class: i ? 'co-annote-sub' : 'co-annote-head', dataset: i ? { readability: 'skip' } : {} }, t)));
          annoteHTML.hidden = false;
        } else {
          annoteHTML.hidden = true;
          const dx = ax > iw * 0.55 && fitsL ? -40 : 40, dy = -Math.min(105, ayy - lines.length * 15 - 4);
          const tx = ax + dx, anchor = dx < 0 ? 'end' : 'start';
          gAnn.append('path').attr('class', 'gnm-annot-line').attr('d', `M${ax},${ayy - 10}L${ax},${ayy + dy + 6}L${tx},${ayy + dy + 6}`);
          lines.forEach(([t, c], i) => gAnn.append('text').attr('class', c).attr('x', tx + (dx < 0 ? -6 : 6)).attr('y', ayy + dy - 4 - (lines.length - 1 - i) * 15).attr('text-anchor', anchor).text(t));
        }
      }
      // selected ring
      const sp = posOf(sel, md);
      // the selected-plan marker is ONE keyed group that glides along the frontier (transform only) as the budget changes
      const mk = gSel.selectAll('g.co-sel').data(['selected'], (k) => k).join((en) => {
        const g0 = en.append('g').attr('class', 'co-sel').attr('transform', `translate(${x(sp.cap)},${y(sp.aog)})`);
        g0.append('circle').attr('r', 11).attr('fill', 'none').attr('stroke', theme.color.text).attr('stroke-width', 1.5).attr('stroke-dasharray', '3 2');
        g0.append('text').attr('class', 'gnm-label gnm-label--strong').attr('font-family', theme.font.mono).attr('text-anchor', 'middle').attr('y', 26);
        return g0;
      });
      mk.attr('data-point', sel.id);
      mk.select('text').text(sel === rec || isPolicy(sel) ? '' : sn(sel.id).replace(/^Frontier point /, ''));
      (animate && !dead ? tx(mk.interrupt('sel'), { name: 'sel' }) : mk).attr('transform', `translate(${x(sp.cap)},${y(sp.aog)})`);
      // unstable plans: a CI that crosses zero on a log axis draws a full-height whisker. Say why, from the data.
      gAnn.selectAll('.co-unstable').remove();
      if (md !== 'selection') {
        pts.filter((p) => p.ci[0] != null && p.ci[0] <= 0 && !isPolicy(p)).forEach((p) => {
          const px = x(p.cap), py = y(p.aog);
          const right = px < iw * 0.7;
          // phones: the empty lower-right corner under the frontier tail; desktop: beside the point
          const lx = px + (right ? 10 : -10), ly = narrow ? ih - 26 : Math.max(12, py - 14);
          const t = gAnn.append('text').attr('class', 'co-unstable').attr('x', lx).attr('y', ly).attr('text-anchor', right ? 'start' : 'end');
          const pid = sn(p.id).replace(/^Frontier point /, '');
          t.append('tspan').attr('x', lx).text(narrow ? `${pid} · unstable (${S ? 'range' : 'CI'} crosses 0)` : `${pid} · unstable: ${S ? 'range' : 'CI'} ${fmtInt(p.ci[0]).replace('-', '−')} to ${fmtInt(p.ci[1])} h`);
          t.append('tspan').attr('x', lx).attr('dy', '1.25em').text(p.sel?.aog != null ? `${S ? 'tuning runs' : 'selection seeds'} ${fmtHours(p.sel.aog)} · see Method` : 'outlier run · see Method');
        });
      }
    }
    update(false);
    if (firstDraw) drawIn(g, body); else body.__drawn = true;
    return { update };
  }

  // ---- side panel: view toggle, budget slider, readout, rule
  const readout = h('dl', { class: 'meta-list co-readout' });
  const minB = front[0]?.cap ?? 0, maxB = front.at(-1)?.cap ?? 1;
  const step = Math.max(50000, Math.round((maxB - minB) / 200 / 50000) * 50000);
  const onBudget = throttleRAF((v) => { if (dead) return; const p = planFor(v); if (p !== sel) choose(p, false); });
  const planFor = (v) => front.filter((q) => q.cap <= v + 1).at(-1) || front[0]; // never a plan above the budget
  const sl = slider({
    id: 'co-budget', // stable id: the control keeps its identity across re-renders (mode switch, deep links)
    label: S ? 'Budget for spares' : 'Capital budget', min: Math.ceil(minB / step) * step, /* wave C (F4): the minimum always maps to a plan that fits */ max: Math.ceil(maxB / step) * step, step, value: Math.ceil(sel.cap / step) * step, format: (v) => fmtAED(v),
    // screen readers hear the budget and the plan it selects, not "41850000" (F5)
    valueText: (v) => { const p = planFor(v); return `Budget ${fmtAED(v)}: plan ${displayName(p.id, { mode: 'code' })}, ${fmtAED(p.cap)} ${S ? 'in spares' : 'capital'}, ${fmtHours(p.aog)} ${S ? 'grounded' : 'AOG'} a year`; },
    onInput: onBudget,
  });
  const slInput = sl.input || sl.querySelector('input');
  slInput.dataset.role = 'budget-slider';
  const modeSeg = segmented({ label: S ? 'Which runs' : 'Seed set', value: mode, options: S ? [{ value: 'holdout', label: 'Test' }, { value: 'selection', label: 'Tuning' }, { value: 'overlay', label: 'Both' }] : [{ value: 'holdout', label: 'Holdout' }, { value: 'selection', label: 'Selection' }, { value: 'overlay', label: 'Overlay' }], onChange: (v) => { mode = v; ctx.setParams({ view: v === 'holdout' ? '' : v }); chart?.update(true); showSel(); } });
  if (!hasSel) modeSeg.querySelectorAll('button').forEach((b) => { if (b.dataset.value !== 'holdout') { b.disabled = true; b.title = 'Selection-seed values not exported'; } });
  // F7 (wave 5): the readout follows the seed-set toggle (selection values when Selection is chosen; holdout otherwise)
  function showSel() {
    const p = sel;
    const selMode = mode === 'selection' && p.sel?.aog != null;
    const rows = [
      ['Plan', h('span', {}, h('b', {}, nameTag(p.id)), ' ', h('span', { class: 'faint' }, KIND_LABEL[p.kind] || p.kind))],
      [S ? 'Runs' : 'Seeds', selMode ? (S ? 'tuning runs' : 'selection 100–119') : (S ? '20 fresh test runs' : `holdout ${holdRange}`.trim())],
      [S ? 'In spares' : 'Capital', `${fmtAED(p.cap)}${p.capCI[0] != null ? ciTxt(p.capCI[0], p.capCI[1], (v) => fmtAED(v).replace('AED ', '')) : ''}`],
      [S ? 'Grounded / yr' : 'AOG / yr', selMode ? `${fmtHours(p.sel.aog)}${ciTxt(p.sel.ci?.[0], p.sel.ci?.[1], fmtInt)}` : `${fmtHours(p.aog)}${ciTxt(p.ci[0], p.ci[1], fmtInt)}`],
      selMode && P2?.sel?.aog != null && p !== P2 ? [`vs ${baseN}`, `${signH(p.sel.aog - P2.sel.aog)} · ${signAED(capVsP2(p, P2))}`] : null,
      !selMode && P2 && p !== P2 ? [`vs ${baseN}`, p.dBaseAog ? `${signH(p.dBaseAog[0])}${ciTxt(p.dBaseAog[1], p.dBaseAog[2], (v) => fmtInt(v))} · ${signAED(capVsP2(p, P2))}` : `${signH(p.aog - P2.aog)} · ${signAED(capVsP2(p, P2))}`] : null,
      !selMode && P0 && p !== P0 ? [`vs ${p0N}`, `${signH(p.aog - P0.aog)} · ${signAED(dCap(p.cap, P0.cap))}`] : null,
      p.total != null ? [S ? 'Yearly cost' : 'Annual cost', `${fmtAED(p.total)}${selMode ? (S ? ' (test runs)' : ' (holdout)') : ''}`] : null,
      selMode ? [S ? 'Test runs' : 'Holdout AOG', `${fmtHours(p.aog)}${ciTxt(p.ci[0], p.ci[1], fmtInt)}`] : p.sel?.aog != null ? [S ? 'Tuning runs' : 'Selection', `${fmtHours(p.sel.aog)}${ciTxt(p.sel.ci?.[0], p.sel.ci?.[1], fmtInt)}`] : null,
    ].filter(Boolean);
    readout.replaceChildren(...rows.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
  }
  const R = F.recommendation || {};
  const rule = card({
    kicker: S ? 'Stopping rule · set in advance' : 'Recommendation rule · pre-stated', title: R.h_star_per_aed_1m != null ? `Stop when an extra AED 1M buys fewer than ${fmtNum(R.h_star_per_aed_1m, 1)} ${S ? 'grounded hours' : 'AOG h'}` : 'Balanced point rule', prov: 'ASSUMED',
    body: h('div', { class: 't-14 muted co-rule-body' },
      S ? h('p', { class: 'm-0' }, `Walk up the curve one step at a time. Stop at the first step where an extra AED 1M saves less grounded time than its yearly holding cost is worth. The plan before that step is the frontier option: the ${BEST_EVAL}, not a guaranteed best.`) : null,
      S ? null : h('p', { class: 'm-0' }, R.aed_per_aog_hour != null ? `Walk the lower hull of the capital-only plans. Each segment buys AOG hours per extra AED 1M. Break-even h* = carrying ${fmtNum((R.carrying_pct ?? 0) * 100, 0)}% × AED 1M ÷ ${fmtAED(R.aed_per_aog_hour)} per AOG hour. The frontier option is the last vertex before the first segment below h*.` : 'Walk the lower hull of the capital-only plans and stop at the first segment worth less than its holding cost.'),
      S ? null : h('p', { class: 'm-0 t-12 faint' }, `The frontier option is the ${BEST_EVAL}.`),
      R.segments && !S ? h('p', { class: 'm-0 t-12 faint' }, `Selection-seed hull. Segment into ${displayName(R.recommended || rec.id, { mode: 'code' })}: ${fmtNum(R.segments.find((s) => s.to === (R.recommended || rec.id))?.h_per_aed_1m, 1)} h per AED 1M; next segment: ${fmtNum(R.segments.find((s) => s.from === (R.recommended || rec.id))?.h_per_aed_1m, 1)} h.`) : null),
  });
  side.append(
    card({
      cls: 'co-controls', kicker: 'Explore the frontier', title: S ? 'Budget and test runs' : 'Budget and seed set', prov,
      body: h('div', { class: 'stack-3' },
        h('div', { class: 'field' }, h('span', { class: 'field-label' }, S ? 'Which runs' : 'Seed set'), modeSeg, h('span', { class: 't-12 faint' }, hasSel ? (S ? 'Tuning runs chose the plan; the 20 fresh test runs judge it.' : `Selection seeds 100–119 chose the plan; ${seedsTxt} judge it.`) : 'Selection-seed values are not in this export.')),
        sl,
        h('p', { class: 't-12 faint m-0' }, S ? 'The slider walks along the curve. It picks the best plan found that fits the budget.' : 'The slider walks the non-dominated plans: it picks the lowest-AOG plan whose capital fits the budget (holdout means).'),
        readout),
    }),
  );
  // wave 4: the rule card lives under the controls (right column), so neither column leaves ~300 px of dead space
  side.append(rule);
  showSel();

  // ---- v2.1 A4 + A8: the capital change Network Plan vs Simple Rulebook (gross buys, gross removals, THEN the net) and
  // the frontier insight card (verbatim) with the four levers
  {
    const CT = F.capital_table || {};
    const capCard = card({
      cls: 'span-6 md-span-12 co-capital', kicker: S ? 'What the Network Plan changes in spares' : 'Capital change · A4', story: 'capital-table', prov,
      title: [nameTag(CT.to || baseId), ' vs ', nameTag(CT.from || 'P0')],
      body: h('div', { class: 'stack-2' },
        h('p', { class: 'm-0 t-14 muted' }, S ? `Moving from the ${sn(CT.from || 'P0')} to the ${sn(CT.to || baseId)} buys some repairable parts and removes others. Read the buys and removals before the net.` : `Moving from ${displayName(CT.from || 'P0', { mode: 'code' })} to ${displayName(CT.to || baseId, { mode: 'code' })}: gross rotables bought and removed, then the net change in average simulated inventory.`),
        capitalTable({ buy_units: CT.bought_units, buy_aed: CT.bought_aed, shed_units: CT.removed_units, shed_aed: CT.removed_aed }, { net: CT.net_inventory_change_aed, caption: `Capital change: ${sn(CT.to || baseId)} vs ${sn(CT.from || 'P0')}` })),
    });
    const INS = F.insight || {};
    const levers = INS.levers || [];
    const insCard = card({
      cls: 'span-6 md-span-12 co-insight', kicker: S ? 'More spares is not the only lever' : 'Frontier insight · A8', story: 'frontier-insight', prov: INS.provenance || prov,
      title: S ? 'With 25% faster repair, the extra spares no longer clearly pay' : 'With repair TAT ×0.75, the extra spares no longer clearly pay',
      body: h('div', { class: 'stack-2' },
        h('p', { class: 'co-insight-text m-0', dataset: { role: 'insight-text' } }, INS.text || 'Insight not exported.'),
        levers.length ? h('ul', { class: 'co-levers-row list-reset', 'aria-label': 'Levers', dataset: { role: 'levers' } }, levers.map((l, i) => h('li', { class: `co-lever-chip ${i === levers.length - 1 ? 'is-spares' : ''}` }, l))) : null,
        INS.evidence?.net_benefit_vs_P2_aed ? h('p', { class: 't-12 faint m-0' }, S
          ? `With repair 25% faster, the extra spares save ${fmtAED(INS.evidence.net_benefit_vs_P2_aed.mean)} a year net. The likely range runs from ${fmtAED(INS.evidence.net_benefit_vs_P2_aed.ci[0])} to ${fmtAED(INS.evidence.net_benefit_vs_P2_aed.ci[1])}, so the gain is not clear.`
          : `Evidence: repair TAT ${settingTxt(INS.evidence.setting)}, net benefit of ${recN} vs ${baseN} ${fmtAED(INS.evidence.net_benefit_vs_P2_aed.mean)} [${fmtAED(INS.evidence.net_benefit_vs_P2_aed.ci[0])}, ${fmtAED(INS.evidence.net_benefit_vs_P2_aed.ci[1])}]${INS.evidence.net_benefit_significant === false ? ', not significant' : ''} (selection seeds, one at a time).`) : null),
    });
    el.append(h('div', { class: 'grid-12 mt-3 co-a4a8' }, capCard, insCard));
  }

  // ---- wave B: marginal value of the last investment increment + paired differences vs P2 (holdout) — Expert depth only
  // (rendered in both modes but hidden in Simple, so the page keeps one DOM structure across a mode switch)
  {
    const R2 = F.recommendation || {};
    const segs = R2.segments || [];
    const into = segs.find((x) => x.to === rec?.id), after = segs.find((x) => x.from === rec?.id);
    const hstar = R2.h_star_per_aed_1m;
    // the hull points from P2's capital upward (where extra capital is spent), plus P2 within guardrails
    const hull = new Set(R2.hull || []);
    const pairRows = (F.points || []).filter((q) => q.id !== baseId && Array.isArray(q.d_aog_vs_P2_ci) && (q.d_capital_vs_P2_aed ?? -1) >= -1e6 && (hull.has(q.id) || q.id === 'P2_GUARD' || q.id === rec?.id))
      .map((q) => ({ id: q.id, kind: KIND_LABEL[q.kind] || q.kind, dcap: q.d_capital_vs_P2_aed, daog: q.d_aog_vs_P2, ci: q.d_aog_vs_P2_ci, dcost: q.d_total_cost_vs_P2_aed, cci: q.d_total_cost_vs_P2_ci || [null, null], rec: q.id === rec?.id }))
      .sort((x, y) => x.dcap - y.dcap);
    const sigTxt = (ci) => (ci[0] != null && ci[1] != null ? (ci[1] < 0 ? 'lower' : ci[0] > 0 ? 'higher' : 'not significant') : '—');
    const pr = (v, ci, f) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${f(Math.abs(v))} [${f(ci[0])} to ${f(ci[1])}]`;
    const mvCard = card({
      cls: `mt-3 co-marginal${S ? ' expert-only' : ''}`, kicker: 'Marginal value and paired differences', prov, story: 'capital-paired',
      title: into && hstar != null ? `The last increment into ${recN} buys ${fmtNum(into.h_per_aed_1m, 1)} h per AED 1M; the next one only ${after ? fmtNum(after.h_per_aed_1m, 1) : '—'}, under the ${fmtNum(hstar, 1)} h break-even` : 'Marginal value of extra capital',
      body: h('div', { class: 'stack' },
        h('p', { class: 'chart-implication' }, h('span', { class: 'chart-implication-k' }, 'So what'), h('span', { class: 'chart-implication-t' }, `Each extra AED 1M buys less downtime; stop where the next step is worth less than its holding cost. Differences vs ${baseN} below are paired (same seeds); a CI crossing 0 is not significant.`)),
        dataTable({ caption: `Paired differences vs ${baseN}, holdout`, bare: true, dense: true, rows: pairRows, rowKey: 'id', mobileColumns: ['id', 'daog', 'dcap'],
          columns: [{ key: 'id', label: 'Plan', render: (r) => h('span', { class: r.rec ? 'co-rec-id' : '' }, nameTag(r.id), r.rec ? h('span', { class: 'faint t-12' }, ' frontier option') : null) },
            { key: 'kind', label: 'Kind' },
            { key: 'dcap', label: `Δ capital vs ${baseN}`, num: true, format: (v) => signAED(v) },
            { key: 'daog', label: 'Δ AOG h/yr [95% CI]', num: true, render: (r) => pr(r.daog, r.ci, (x) => fmtInt(x)) },
            { key: 'sig', label: `AOG vs ${baseN}`, render: (r) => sigTxt(r.ci) },
            { key: 'dcost', label: 'Δ total cost/yr [95% CI]', num: true, render: (r) => (r.dcost == null ? '—' : `${signAED(r.dcost)} [${fmtAED(r.cci[0])} to ${fmtAED(r.cci[1])}]`) }] }),
        h('p', { class: 't-12 faint m-0' }, `CIs are 95% paired-t over the ${seedsTxt} and are conditional on the simulation assumptions (one world per variant, the assumed AOG routes and penalty rates); they are not uncertainty about the real airline. Marginal values come from the pre-stated rule's hull on the selection seeds.`)),
    });
    el.append(mvCard);
  }

  // ---- allocation table
  const allocCard = h('section', { class: 'card mt-3 co-alloc', dataset: { story: 'allocation-table' } });
  el.append(allocCard);
  const allocHead = h('div', { class: 'card-head' });
  const allocBody = h('div');
  allocCard.append(allocHead, allocBody);
  const allocRows = (id) => (F.allocations?.[id] || []).map((r) => {
    const cur = num(r.current), prop = num(r.proposed);
    return { key: `${r.pn}@${r.station}`, pn: r.pn, station: r.station, cls: r.part_class || (String(r.pn).match(/-([CER])\d/)?.[1] ?? ''), current: cur, proposed: prop, change: num(r.delta_units) ?? (cur != null && prop != null ? prop - cur : null), dcap: num(r.delta_capital ?? r.incremental_capital_aed), risk: num(r.risk_reduction ?? r.modelled_aog_hour_reduction), alt: r.alt_action ?? r.best_alternative_action ?? '', invalid: !!r.invalid_recommendation, flag: r.flag_text || F.invalid_allocation_text || '' };
  });
  // A9: outstation brake allocations are flagged, never deleted (frozen results unchanged)
  const INVALID_TXT = F.invalid_allocation_text || ctx.data.parts?.invalid_allocation_text || 'invalid recommendation — brakes are not changed outside the hub in this model';
  const frozenInvalid = (id) => (ctx.data.parts?.invalid_allocations || []).filter((r) => r.policy === id);
  const flagBadge = (txt) => h('span', { class: 'co-flag', title: txt, dataset: { role: 'invalid-flag' } }, icon('alert'), h('span', {}, 'invalid'));
  const altTxt = (a) => LEVER_LABEL[a] || (a === 'hold' ? 'Hold (no better lever)' : a ? String(a).replace(/_/g, ' ') : '—');
  const allocTable = dataTable({
    caption: 'Allocation changes', dense: true, sort: { key: 'risk', dir: 'desc' }, rowKey: 'key', stickyFirst: true,
    // ≤ 767 px keeps the decision columns; ≤ 480 px stacks rows: PN · AOG-avoided pill · change, Δ capital, station
    mobileColumns: ['pn', 'risk', 'change', 'dcap', 'station'],
    columns: [
      { key: 'pn', label: S ? 'Part' : 'PN', render: (r) => h('span', { class: 'co-pn' }, h('span', { class: 'mono' }, r.pn), r.invalid ? flagBadge(r.flag || INVALID_TXT) : null) },
      { key: 'station', label: S ? 'Airport' : 'Station', short: S ? 'Airport' : 'Stn', mono: true }, { key: 'cls', label: S ? 'Type' : 'Class', mono: true },
      { key: 'current', label: S ? `Spares now (${baseN})` : `Float (${baseN})`, num: true, format: (v) => (v == null ? '—' : fmtInt(v)) },
      { key: 'change', label: 'Change', short: 'Units', num: true, render: (r) => h('span', { class: `co-chg ${r.change > 0 ? 'is-up' : r.change < 0 ? 'is-down' : ''}` }, r.change == null ? '—' : `${r.change > 0 ? '+' : r.change < 0 ? '−' : ''}${fmtInt(Math.abs(r.change))}`) },
      { key: 'proposed', label: S ? 'New level' : 'Proposed', num: true, format: (v) => (v == null ? '—' : fmtInt(v)) },
      { key: 'dcap', label: S ? 'Change in spares money' : 'Δ capital', short: S ? 'Spares AED' : 'Δ cap', num: true, format: (v) => (v == null ? '—' : signAED(v)) },
      { key: 'risk', label: S ? 'Grounded h/yr avoided*' : 'AOG h/yr avoided*', short: S ? 'Grounded h avoided' : 'AOG h avoided', num: true, format: (v) => (v == null ? '—' : fmtNum(v, 1)) },
      { key: 'alt', label: S ? 'Cheapest alternative lever' : 'Cheapest alternative lever', short: 'Alternative', render: (r) => h('span', {}, /^buy_/.test(r.alt || '') && r.change > 0 ? (S ? 'Same lever (buying)' : 'Same lever (buy)') : altTxt(r.alt)) },
    ],
    rows: [],
  });
  const allocNote = h('p', { class: 't-12 muted m-0' });
  const allocFlags = h('div', { class: 'co-flags', dataset: { role: 'invalid-allocations' } });
  const allocMore = h('button', { type: 'button', class: 'btn btn--sm co-alloc-more', dataset: { action: 'alloc-more' }, onclick: () => { const on = allocCard.classList.toggle('is-expanded'); allocMore.textContent = on ? 'Show fewer rows' : allocMore.dataset.label; } });
  allocBody.append(allocFlags, allocTable, allocMore, h('div', { class: 'co-alloc-notes stack-1' }, allocNote, h('p', { class: 't-12 faint m-0' }, S ? `Rows are the changes against the ${baseN} only. * Grounded hours avoided is a quick ranking estimate (a heuristic), not a test-run result. The cheapest alternative lever is the cheapest modelled option for that part; “same lever” means buying is already that option.` : `Rows are the changes against the base policy ${baseN} only. * AOG h/yr avoided is a leave-one-out estimate on the analytic model (a ranking heuristic), not a simulated result. Cheapest alternative lever = the cheapest modelled lever for that PN; “same lever” when that is the buy already in the row.`)));
  function showAlloc() {
    const rows = allocRows(sel.id);
    const tot = F.allocation_totals?.[sel.id];
    const sumCap = num(tot?.delta_capital_aed) ?? rows.reduce((s, r) => s + (r.dcap || 0), 0);
    const units = num(tot?.delta_units) ?? rows.reduce((s, r) => s + (r.change || 0), 0);
    const nAll = num(tot?.n_rows) ?? rows.length;
    allocHead.replaceChildren(
      h('div', {}, h('div', { class: 'card-kicker' }, [S ? 'Where the spares go · ' : 'Allocation · ', nameTag(sel.id)]), h('h3', { class: 'card-title co-alloc-title', 'aria-live': 'polite' }, rows.length
        ? (S ? `${sn(sel.id)} changes ${fmtInt(nAll)} part-and-airport levels vs the ${baseN}: ${fmtInt(Math.abs(units))} ${units >= 0 ? 'more' : 'fewer'} units, ${fmtAED(Math.abs(sumCap))} ${sumCap >= 0 ? 'more' : 'less'} at target units × price (a different basis)` : `${sn(sel.id)} changes ${fmtInt(nAll)} PN-station levels vs ${baseN}: ${fmtInt(Math.abs(units))} ${units >= 0 ? 'more' : 'fewer'} units on top of ${baseN}, ${fmtAED(Math.abs(sumCap))} ${sumCap >= 0 ? 'more' : 'less'} allocation capital (target units × unit cost, a different basis)`)
        : sel === P2 ? `The ${baseN} is the base plan: no changes` : `No allocation rows exported for ${sn(sel.id)}`)),
      h('div', { class: 'row' }, provChip(prov)));
    // keyed, flash-free update: hold the table's height across the swap, then fade in only the rows that are new
    const before = new Set([...allocTable.querySelectorAll('[data-key]')].map((e) => e.dataset.key));
    const hgt = allocTable.offsetHeight;
    if (hgt) allocTable.style.minHeight = `${hgt}px`;
    allocTable.update(rows);
    if (before.size && dur('fast')) allocTable.querySelectorAll('[data-key]').forEach((e) => { if (!before.has(e.dataset.key)) e.classList.add('co-row-in'); });
    requestAnimationFrame(() => { allocTable.style.minHeight = ''; });
    allocMore.dataset.label = `Show all ${fmtInt(rows.length)} changes`;
    allocMore.textContent = allocCard.classList.contains('is-expanded') ? 'Show fewer rows' : allocMore.dataset.label;
    allocCard.classList.toggle('has-more', rows.length > 8);
    // C3 (wave 4): two capital bases on one page, each named. Allocation capital = target units × unit cost (this table);
    // simulated capital = the time-average stock value over the run (the KPI and the frontier).
    const simD = sel !== P2 && num(sel.cap) != null && num(P2?.cap) != null ? capVsP2(sel, P2) : null;
    const basis = rows.length && simD != null ? (S ? `This table counts target units × unit price. The tiles and the curve use the average value of spares held over the run. That leaves out parts away for repair: ${fmtAED(Math.abs(simD))} ${simD >= 0 ? 'more' : 'less'} than the ${baseN}.` : `Allocation capital is target units × unit cost. The KPI and frontier show simulated capital (the time-average stock value over the run, which nets out units away in repair): ${fmtAED(Math.abs(simD))} ${simD >= 0 ? 'more' : 'less'} than ${baseN}.`) : '';
    const shown = tot && num(tot.n_rows_shown) < num(tot.n_rows) ? (S ? `Showing the ${fmtInt(tot.n_rows_shown)} changes with the biggest effect, out of ${fmtInt(tot.n_rows)}. Totals cover all rows. ` : `Showing the ${fmtInt(tot.n_rows_shown)} changes with the largest modelled effect of ${fmtInt(tot.n_rows)}; totals cover all rows. `) : '';
    allocNote.textContent = `${shown}${basis}`;
    // A9: flagged outstation brake units — in this plan's change rows, or (for the frozen Network Plan itself) from parts.json
    const flagged = rows.filter((r) => r.invalid).map((r) => ({ pn: r.pn, station: r.station, units: r.change }));
    const frozen = sel === P2 || sel.id === 'P2' ? frozenInvalid('P2').map((r) => ({ pn: r.pn, station: r.station, units: r.units })) : [];
    const list = flagged.length ? flagged : frozen;
    allocFlags.replaceChildren(...(list.length ? [h('div', { class: 'co-flag-note', role: 'note' }, icon('alert'), h('div', {},
      h('p', { class: 'm-0' }, h('b', {}, `${fmtInt(list.length)} brake ${list.length === 1 ? 'allocation' : 'allocations'} outside the hub: `), h('span', { dataset: { role: 'invalid-text' } }, INVALID_TXT), '.'),
      h('ul', { class: 'co-flag-list list-reset t-12 mono' }, list.map((r) => h('li', {}, `${r.pn} at ${r.station}${r.units != null ? ` (${r.units > 0 ? '+' : ''}${fmtInt(r.units)})` : ''}`))),
      ctx.data.parts?.invalid_allocation_summary?.text ? h('p', { class: 'm-0 t-12', dataset: { role: 'invalid-size' } }, ctx.data.parts.invalid_allocation_summary.text) : null,
      h('p', { class: 'm-0 t-12 faint' }, S ? 'They stay in the frozen results and are not deleted. Treat them as errors, not advice.' : 'Kept in the frozen results (not deleted); flagged here and in the parts tables.')))] : []));
    allocCard.dataset.point = sel.id;
  }
  showAlloc();

  function choose(p, fromChart) {
    if (dead) return;
    sel = p;
    showSel(); showAlloc(); chart?.update(true);
    if (fromChart) { slInput.value = String(Math.ceil(p.cap / step) * step); slInput.dispatchEvent(new Event('input')); }
    ctx.setParams({ point: p.id });
  }

  // ---- cost breakdown + tornado
  const costCard = h('section', { class: 'card' });
  const torCard = h('section', { class: 'card', dataset: { story: 'tornado' } });
  // wave C: two stacked columns (cost + levers | tornado + robustness), so no card is stretched beside a taller one
  const colL = h('div', { class: 'span-6 md-span-12 co-col' }, costCard), colR = h('div', { class: 'span-6 md-span-12 co-col' }, torCard);
  el.append(h('div', { class: 'grid-12 mt-3 co-cols' }, colL, colR));
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
    const segs = [...keys, ...(anyOther ? [{ key: 'other', label: S ? 'Other (shipping, rounding)' : 'Other (logistics, rounding)' }] : [])];
    const val = (r, k) => (k === 'other' ? r.other : r.c[k] || 0);
    const r0 = rows[0], rl = rows.at(-1);
    const fr = chartFrame(host, {
      implication: S ? 'Grounded hours drive most of the starting cost. Holding cost is the price of keeping spares in place.' : 'Downtime penalties dominate the starting-point policy’s cost; holding cost is the price of positioning stock.',
      headline: r0.c.aog_penalty != null && rl.c.aog_penalty != null
        ? (S ? fitHeadline(`Grounded hours are ${fmtNum((r0.c.aog_penalty / r0.total) * 100, 0)}% of the ${sn(r0.p.id)}'s yearly cost`, 'Grounded hours drive the starting yearly cost')
          : fitHeadline(`The AOG penalty is ${fmtNum((r0.c.aog_penalty / r0.total) * 100, 0)}% of the ${sn(r0.p.id)}'s annual cost; ${sn(rl.p.id)} cuts it to ${fmtAED(rl.c.aog_penalty)}`,
            `${sn(rl.p.id)} cuts the annual AOG penalty from ${fmtAED(r0.c.aog_penalty)} to ${fmtAED(rl.c.aog_penalty)}`))
        : `Annual cost: ${sn(r0.p.id)} ${fmtAED(r0.total)} vs ${sn(rl.p.id)} ${fmtAED(rl.total)}`,
      subtitle: S ? 'Yearly cost by part (AED a year) · 20 fresh test runs · averages · money in spares is shown on the right, never added' : `Annual cost components (AED/yr) · ${seedsTxt} · means · capital is a stock: shown on the right, never added`,
      provenance: prov, source: 'policies.json · frontier.json',
      table: { columns: [{ key: 'id', label: 'Plan' }, ...segs.map((c) => ({ key: c.key, label: c.label, num: true, format: (v) => fmtAED(v) })), { key: 'total', label: S ? 'Yearly total' : 'Annual total', num: true, format: (v) => fmtAED(v) }, { key: 'cap', label: S ? 'Money in spares (separate)' : 'Capital (separate)', num: true, format: (v) => fmtAED(v) }], rows: rows.map((r) => ({ id: planName(r.p.id), ...Object.fromEntries(segs.map((c) => [c.key, val(r, c.key)])), total: r.total, cap: r.p.cap })) },
    });
    // Neutral ramp: the AOG penalty is the strongest titanium, never copper (copper = capital / P0 only).
    const shade = { aog_penalty: SER.neutral, holding_cost: 'rgba(185,200,214,0.55)', repair_cost: 'rgba(185,200,214,0.36)', expedite_cost: 'rgba(185,200,214,0.22)', logistics_cost: 'rgba(185,200,214,0.14)', other: 'rgba(185,200,214,0.09)' };
    stops.push(responsive(fr.body, (w) => {
      const narrow = w < 520;
      const lw = 0, capW = narrow ? 100 : 140, rowH = narrow ? 64 : 70;
      const Hh = rows.length * rowH + 30;
      const svg = svgIn(fr.body, w, Hh, 'Annual cost breakdown'); drawIn(svg, fr.body);
      // Reserve room for the longest total label so it always sits clear of its bar end.
      const labW = d3.max(rows, (r) => fmtAED(r.total).length) * 7 + 14;
      const bw = Math.max(60, w - lw - capW - labW - 8);
      const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.total)]).range([0, bw]);
      svg.append('text').attr('class', 'gnm-label').attr('x', lw).attr('y', 10).style('fill', theme.color.faint).text(S ? 'Yearly cost' : 'Annual cost / yr');
      svg.append('text').attr('class', 'gnm-label').attr('x', w - capW + 12).attr('y', 10).style('fill', theme.color.faint).text(S ? 'In spares' : 'Capital (stock)');
      svg.append('line').attr('x1', w - capW).attr('x2', w - capW).attr('y1', 0).attr('y2', Hh).attr('stroke', theme.color.lineStrong).attr('stroke-dasharray', '2 3');
      rows.forEach((r, i) => {
        const y0 = 40 + i * rowH;
        // the plan name sits on its own line above its bar (display names are too long for a side column)
        svg.append('text').attr('class', r.p === rec ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', y0 - 6).text(sn(r.p.id));
        let x0 = lw;
        segs.forEach((c) => {
          const v = val(r, c.key);
          const seg = svg.append('rect').attr('x', x0).attr('y', y0).attr('height', 18).attr('width', Math.max(0, x(v) - 1)).attr('fill', shade[c.key]);
          withTooltip(seg, () => ({ title: `${sn(r.p.id)} · ${c.label}`, rows: [['AED / yr', fmtAED(v)], ['Share', `${fmtNum((v / r.total) * 100, 0)}%`]] }));
          x0 += x(v);
        });
        if (r.c.aog_penalty != null) svg.append('text').attr('class', 'gnm-label').attr('x', lw).attr('y', y0 + 32).style('fill', theme.color.faint).text(`${S ? 'Grounded hours' : 'AOG penalty'} ${fmtAED(r.c.aog_penalty)}`);
        svg.append('text').attr('class', 'gnm-label gnm-label--strong').attr('font-family', theme.font.mono).attr('x', x0 + 8).attr('text-anchor', 'start').attr('y', y0 + 13).text(fmtAED(r.total));
        svg.append('rect').attr('x', w - capW + 12).attr('y', y0 + 4).attr('width', 10).attr('height', 10).attr('rx', 2).attr('fill', SER.baseline).attr('fill-opacity', 0.25).attr('stroke', SER.baseline);
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
      const fr = chartFrame(host, { headline: S ? 'What changes the answer' : 'Sensitivity of the recommendation', subtitle: 'Net annual benefit vs the base policy (AED)', provenance: prov, source: 'frontier.json', table: { columns: [{ key: 'param', label: 'Factor' }, { key: 'low', label: 'Low', num: true, format: (v) => fmtAED(v) }, { key: 'high', label: 'High', num: true, format: (v) => fmtAED(v) }], rows: F.tornado || [] } });
      fr.body.append(h('p', { class: 'muted' }, 'Tornado not run.'));
      return;
    }
    const base = rows[0].base;
    const all = rows.flatMap((r) => r.settings);
    const minLo = d3.min(all, (s) => num(s.ci?.[0]) ?? s.v), vMin = d3.min(all, (s) => s.v), vMax = d3.max(all, (s) => s.v);
    const fr = chartFrame(host, {
      implication: S ? 'Whether extra spares pay depends on the cost of grounded time and on repair speed. Treat the case as conditional.' : 'The case for extra capital depends on the downtime rate and repair speed: treat it as conditional, not universal.',
      headline: S ? (minLo > 0
        ? fitHeadline(`The extra spares pay at every setting tried: ${fmtAED(vMin)} to ${fmtAED(vMax)} a year net`, 'The extra spares pay at every setting tried')
        : fitHeadline(`The gain from extra spares is not clear everywhere: the low end reaches ${fmtAED(minLo)} a year`, 'The gain from extra spares is not clear everywhere'))
        : minLo > 0
          ? fitHeadline(`${recN} beats ${baseN} at every one-at-a-time setting: ${fmtAED(vMin)} to ${fmtAED(vMax)} a year net`, `${recN} beats ${baseN} at every one-at-a-time setting`)
          : fitHeadline(`${recN}'s edge over ${baseN} is not clear everywhere: the lowest bound reaches ${fmtAED(minLo)} a year`, `${recN}'s edge over ${baseN} is not clear everywhere`),
      subtitle: S ? `Yearly net gain of the extra spares (AED). One input changed at a time · net gain on tuning runs: ${fmtAED(base)}${rec?.total != null && P2?.total != null && P2.total > rec.total ? ` (test runs: ${fmtAED(P2.total - rec.total)} lower yearly cost)` : ''} · lines show the likely range` : `Net annual benefit of ${displayName(rec.id, { mode: 'code' })} vs ${displayName(baseId, { mode: 'code' })} (AED/yr) · one factor varied at a time (whole alternative worlds: see Robustness) · paired · selection seeds 100–119 · base case ${fmtAED(base)} · 95% CI whiskers`,
      provenance: prov, source: 'frontier.json',
      table: { columns: [{ key: 'label', label: S ? 'Input' : 'Factor' }, { key: 'setting', label: 'Setting', format: settingTxt }, { key: 'v', label: S ? 'Net gain' : 'Net benefit', num: true, format: (v) => fmtAED(v) }, { key: 'lo', label: S ? 'Range low' : 'CI lo', num: true, format: (v) => fmtAED(v) }, { key: 'hi', label: S ? 'Range high' : 'CI hi', num: true, format: (v) => fmtAED(v) }, { key: 'saved', label: S ? 'Grounded h saved' : 'AOG h saved', num: true, format: fmtHours }],
        rows: rows.flatMap((r) => r.settings.map((s) => ({ label: r.label, setting: s.setting, v: s.v, lo: num(s.ci?.[0]), hi: num(s.ci?.[1]), saved: s.saved }))) },
    });
    stops.push(responsive(fr.body, (w) => {
      const narrow = w < 520;
      // Narrow: factor names sit on their own line above the bars, so setting labels never meet them.
      const lw = narrow ? 0 : 128, rowH = narrow ? 60 : 48, Hh = rows.length * rowH + 44;
      const svg = svgIn(fr.body, w, Hh, 'Sensitivity tornado'); drawIn(svg, fr.body);
      const vals = all.flatMap((s) => [s.v, num(s.ci?.[0]), num(s.ci?.[1])]).filter((v) => v != null).concat([0, base]);
      const x = d3.scaleLinear().domain(d3.extent(vals)).nice().range([lw + (narrow ? 34 : 0), w - (narrow ? 36 : 44)]);
      axisBottom(svg.append('g'), x, { height: Hh - 22, ticks: narrow ? 3 : 5, format: (v) => fmtAED(v, { digits: 0 }) });
      svg.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 14).attr('y2', Hh - 22).attr('stroke', theme.color.lineStrong);
      // the base case is a reference line (DS rule 5: faded titanium, 4 4 dash, faint label), not a teal mark (wave 5)
      refLine(svg, { x1: x(base), x2: x(base), y1: 14, y2: Hh - 22, label: `base ${fmtAED(base)}`, labelAt: 'start', anchor: 'middle', dx: 0, dy: -4 });
      rows.forEach((r, i) => {
        const yc = (narrow ? 46 : 34) + i * rowH;
        svg.append('text').attr('class', 'gnm-label gnm-label--strong').attr('x', 0).attr('y', narrow ? yc - 16 : yc + 4).text(r.label);
        r.settings.forEach((s, j) => {
          const yy = yc - 10 + j * 13;
          const bar = svg.append('rect').attr('x', Math.min(x(base), x(s.v))).attr('width', Math.max(1.5, Math.abs(x(s.v) - x(base)))).attr('y', yy).attr('height', 10).attr('rx', 2).attr('fill', s.v >= base ? SER.neutral : SER.context).attr('fill-opacity', s.v >= base ? 0.85 : 0.9);
          const lo = num(s.ci?.[0]), hi = num(s.ci?.[1]);
          if (lo != null && hi != null) svg.append('line').attr('x1', x(lo)).attr('x2', x(hi)).attr('y1', yy + 5).attr('y2', yy + 5).attr('stroke', theme.color.muted).attr('stroke-width', 1);
          withTooltip(bar, () => ({ title: `${r.label} · ${settingTxt(s.setting)}`, rows: [[S ? 'Net gain / yr' : 'Net benefit / yr', `${fmtAED(s.v)}${ciTxt(lo, hi, (q) => fmtAED(q))}`], [S ? 'Grounded h saved / yr' : 'AOG h saved / yr', fmtHours(s.saved)]] }));
          const right = s.v >= base;
          const lx = right ? x(Math.max(s.v, hi ?? s.v)) + 4 : x(Math.min(s.v, lo ?? s.v)) - 4;
          svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', 10).attr('x', lx).attr('y', yy + 9).attr('text-anchor', right ? 'start' : 'end').text(settingTxt(s.setting));
        });
      });
    }));
    const desk = F.aog_desk_dependence;
    if (desk && typeof desk === 'object' && desk.base_aog_hours != null) fr.body.after(h('p', { class: 't-12 faint m-0' }, S ? `Not drawn (off the scale): with the urgent-parts routes switched off, the ${baseN} rises from ${fmtHours(num(desk.central_base_aog_hours))} to ${fmtHours(num(desk.base_aog_hours))} a year. The ${recN} rises from ${fmtHours(num(desk.central_rec_aog_hours))} to ${fmtHours(num(desk.rec_aog_hours))}. See the limits below.` : `Not drawn (off-scale): with the AOG-desk routes switched off, ${baseN} rises from ${fmtHours(num(desk.central_base_aog_hours))} to ${fmtHours(num(desk.base_aog_hours))} a year and ${recN} from ${fmtHours(num(desk.central_rec_aog_hours))} to ${fmtHours(num(desk.rec_aog_hours))} (selection seeds). See the limitations below.`));
  }

  // ---- levers + variants
  const levCard = h('section', { class: 'card', dataset: { story: 'levers' } });
  const varCard = h('div', { class: 'co-var' });
  colL.append(levCard); colR.append(varCard);
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
      implication: S ? 'For most parts here a spare is the cheaper lever. Faster repair still wins on some, so check both.' : 'Buying a spare is usually cheaper per downtime hour than paying for faster repair.',
      headline: S ? (buyWins >= tatWins
        ? fitHeadline(`A spare is the cheaper way to avoid a grounded hour on ${fmtInt(buyWins)} of ${fmtInt(both)} repairable parts`, `A spare is cheaper on ${fmtInt(buyWins)} of ${fmtInt(both)} parts`)
        : fitHeadline(`Faster repair is the cheaper way to avoid a grounded hour on ${fmtInt(tatWins)} of ${fmtInt(both)} repairable parts`, `Faster repair is cheaper on ${fmtInt(tatWins)} of ${fmtInt(both)} parts`))
      : buyWins >= tatWins
        ? fitHeadline(`Buying a spare is the cheaper way to avoid an AOG hour on ${fmtInt(buyWins)} of ${fmtInt(both)} rotable PNs; cutting repair TAT wins on ${fmtInt(tatWins)}`, `A spare is the cheaper lever on ${fmtInt(buyWins)} of ${fmtInt(both)} rotable PNs; cutting repair TAT wins on ${fmtInt(tatWins)}`)
        : fitHeadline(`Cutting repair TAT is the cheaper way to avoid an AOG hour on ${fmtInt(tatWins)} of ${fmtInt(both)} rotable PNs; a spare wins on ${fmtInt(buyWins)}`, `Cutting TAT is the cheaper lever on ${fmtInt(tatWins)} of ${fmtInt(both)} rotable PNs; a spare wins on ${fmtInt(buyWins)}`),
      subtitle: S ? `AED per grounded hour avoided per year (log scale) · at the ${baseN} levels · top parts by hours avoided · lower is better` : 'AED per AOG hour avoided per year (log scale) · modelled at the base allocation · top PNs by AOG hours avoided · lower is better',
      provenance: prov, source: 'frontier.json (levers)',
      table: { columns: [{ key: 'pn', label: 'PN', mono: true }, { key: 'unit', label: 'Unit cost', num: true, format: (v) => fmtAED(v) }, { key: 'b', label: 'Buy 1: AED/h', num: true, format: (v) => fmtAED(v) }, { key: 'bh', label: 'Buy 1: h avoided', num: true, format: (v) => fmtNum(v, 1) }, { key: 't', label: 'TAT −10 d: AED/h', num: true, format: (v) => fmtAED(v) }, { key: 'th', label: 'TAT −10 d: h avoided', num: true, format: (v) => fmtNum(v, 1) }],
        rows: cmp.map((c) => ({ pn: c.pn, unit: c.unit, b: c.b.cph, bh: c.b.red, t: c.t.cph, th: c.t.red })) },
    });
    stops.push(responsive(fr.body, (w) => {
      const narrow = w < 520;
      const lw = narrow ? 92 : 108, rowH = 26, Hh = top.length * rowH + 52;
      const svg = svgIn(fr.body, w, Hh, 'Lever cost per AOG hour'); drawIn(svg, fr.body);
      const vals = top.flatMap((c) => [c.b.cph, c.t.cph]).filter((v) => v > 0);
      const x = d3.scaleLog().domain([d3.min(vals) * 0.7, d3.max(vals) * 1.4]).range([lw, w - 12]);
      axisBottom(svg.append('g'), x, { height: Hh - 22, ticks: narrow ? 3 : 4, format: (v) => (String(v).match(narrow ? /^1/ : /^[125]/) ? fmtAED(v, { digits: 0 }) : '') });
      svg.append('text').attr('class', 'gnm-label').attr('x', lw).attr('y', 10).style('fill', theme.color.accent).text('● Buy 1 spare');
      svg.append('text').attr('class', 'gnm-label').attr('x', lw + 110).attr('y', 10).style('fill', SER.neutral).text(S ? (narrow ? '◆ Faster repair' : '◆ Repair 10 days faster') : '◆ Cut TAT 10 d');
      top.forEach((c, i) => {
        const yc = 32 + i * rowH;
        svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', 0).attr('y', yc + 4).text(c.pn);
        svg.append('line').attr('x1', x(c.b.cph)).attr('x2', x(c.t.cph)).attr('y1', yc).attr('y2', yc).attr('stroke', theme.color.lineStrong);
        const cb = svg.append('circle').attr('cx', x(c.b.cph)).attr('cy', yc).attr('r', 5).attr('fill', theme.color.accent);
        const ct = svg.append('path').attr('d', d3.symbol(d3.symbolDiamond, 60)()).attr('transform', `translate(${x(c.t.cph)},${yc})`).attr('fill', SER.neutral);
        withTooltip(cb, () => ({ title: `${c.pn} · buy 1 spare`, rows: [['AED / AOG h', fmtAED(c.b.cph)], ['AOG h/yr avoided', fmtNum(c.b.red, 1)], ['Annual holding', fmtAED(c.b.cost)], ['Unit cost', fmtAED(c.unit)]] }));
        withTooltip(ct, () => ({ title: `${c.pn} · ${S ? 'repair 10 days faster' : 'cut TAT 10 d'}`, rows: [['AED / AOG h', fmtAED(c.t.cph)], ['AOG h/yr avoided', fmtNum(c.t.red, 1)], ['Annual fee', fmtAED(c.t.cost)]] }));
      });
    }));
    const med = (arr) => (arr.length ? d3.median(arr) : null);
    const bMed = med(L.filter((r) => r.lever === 'buy_1' && r.red > 0 && r.cph != null).map((r) => r.cph));
    const tMed = med(L.filter((r) => r.lever === 'tat_cut_10d' && r.red > 0 && r.cph != null).map((r) => r.cph));
    const nPn = byPn.size;
    fr.body.after(h('div', { class: 'co-levers' },
      h('div', { class: 'co-lever' }, h('div', { class: 'co-lever-k' }, icon('rotable'), 'Buy another spare'), h('div', { class: 'co-lever-v num' }, bMed != null ? fmtAED(bMed) : 'not run'), h('div', { class: 't-12 faint' }, S ? 'typical AED per grounded hour avoided · holding cost only' : 'median AED per AOG hour avoided · holding cost only')),
      h('div', { class: 'co-lever' }, h('div', { class: 'co-lever-k' }, icon('wrench'), S ? 'Repair 10 days faster' : 'Cut repair TAT 10 d'), h('div', { class: 'co-lever-v num' }, tMed != null ? fmtAED(tMed) : 'not run'), h('div', { class: 't-12 faint' }, levPt?.dBaseAog ? (S ? `${fmtHours(Math.abs(levPt.dBaseAog[0]))} a year ${levPt.dBaseAog[0] > 0 ? 'more' : 'less'} grounded than the ${baseN}${levPt.dBaseAog[1] != null ? ` (range ${fmtInt(levPt.dBaseAog[1])} to ${fmtInt(levPt.dBaseAog[2])})` : ''}` : `simulated on top PNs: ${signH(levPt.dBaseAog[0])}${ciTxt(levPt.dBaseAog[1], levPt.dBaseAog[2], (v) => fmtInt(v))} vs ${baseN}`) : (S ? 'typical AED per grounded hour avoided · rush fee' : 'median AED per AOG hour avoided · acceleration fee'))),
      h('div', { class: 'co-lever' }, h('div', { class: 'co-lever-k' }, icon('route'), S ? 'Move existing spares' : 'Reposition stock'), h('div', { class: 'co-lever-v num' }, `${fmtInt(reposHelps)} of ${fmtInt(nPn)}`), h('div', { class: 't-12 faint' }, S ? `parts where moving one spare cuts grounded time at the ${baseN} levels` : `PNs where moving one unit lowers modelled AOG at the ${baseN} allocation`))));
  }

  function drawVariants(host) {
    const VR = Array.isArray(F.variant_robustness) ? F.variant_robustness : [];
    const LBL = S ? { low_stress: 'Easier', central: 'Central', high_stress: 'Tougher' } : { low_stress: 'Low', central: 'Central', high_stress: 'High' };
    const rows = ['low_stress', 'central', 'high_stress'].map((k) => VR.find((v) => v.variant === k)).filter(Boolean).map((v) => {
      const d = v.rec_vs_P2 || {};
      return { k: v.variant, label: LBL[v.variant] || v.variant, p2: num(v[baseId]?.aog_hours), rec: num(v[rec.id]?.aog_hours), recCap: num(v[rec.id]?.capital_aed), p2Cap: num(v[baseId]?.capital_aed), dA: num(d.aog_reduction), dAlo: num(d.aog_reduction_ci?.[0]), dAhi: num(d.aog_reduction_ci?.[1]), nb: num(d.net_benefit_aed), nblo: num(d.net_benefit_ci?.[0]), nbhi: num(d.net_benefit_ci?.[1]), pick: v.rule_recommends || '—' };
    });
    if (!rows.length) { host.append(card({ title: 'Stress variants', prov, body: h('p', { class: 'muted m-0' }, 'Variant robustness not run.') })); return; }
    const low = rows.find((r) => r.k === 'low_stress');
    const tbl = dataTable({
      caption: S ? 'Easier and tougher worlds' : 'Stress-variant robustness', dense: true, bare: true,
      mobileColumns: ['label', 'nb', 'pick', 'dA', 'rec', 'p2'],
      columns: [
        { key: 'label', label: S ? 'World' : 'Stress' }, { key: 'p2', label: S ? 'Network' : baseId, num: true, format: fmtHours }, { key: 'rec', label: S ? '+ Spares' : rec.id, num: true, format: fmtHours },
        { key: 'dA', label: 'Saved', num: true, render: (r) => h('span', { class: 'co-two' }, fmtHours(r.dA), h('small', {}, ciTxt(r.dAlo, r.dAhi, (v) => fmtNum(v, Math.abs(v) < 20 ? 1 : 0)).trim())) },
        { key: 'nb', label: S ? 'Net / yr (tuning runs)' : 'Net / yr', short: 'Net', num: true, render: (r) => h('span', { class: `co-two ${r.nbhi < 0 ? 'co-neg' : ''}` }, h('span', {}, r.nbhi < 0 ? icon('alert') : null, Math.max(Math.abs(r.nblo ?? 0), Math.abs(r.nbhi ?? 0)) >= 1e6 ? `${r.nb < 0 ? '−' : ''}AED ${sameUnitM(Math.abs(r.nb), r.nblo, r.nbhi)}` : fmtAED(r.nb)), h('small', {}, ciTxt(r.nblo, r.nbhi, (v) => sameUnitM(v, r.nblo, r.nbhi)).trim())) },
        // raw plan codes get a gloss ("B125 · budget point, AED 45.0M"), never a bare code (wave 4)
        { key: 'pick', label: 'Rule picks', short: 'Rule picks', render: (r) => { const q = byId.get(r.pick); return r.pick === '—' || !r.pick ? '—' : h('span', { title: q ? `${KIND_LABEL[q.kind] || q.kind}, ${fmtAED(q.cap)} ${S ? 'in spares' : 'simulated capital'}` : null }, sn(r.pick).replace(/^Frontier point /, ''), q && !isPolicy(q) && q !== rec && !S ? h('span', { class: 'faint t-12' }, ' budget pt') : null); } },
      ],
      rows,
    });
    tbl.classList.add('co-var');
    host.append(card({
      kicker: S ? term('stress_worlds', { first: true, cap: true }) : 'Robustness · selection seeds 100–119', title: S ? 'Do the extra spares still pay in a different world?' : `Does ${recN} survive a different reliability world?`, prov,
      body: h('div', { class: 'stack-3' }, tbl,
        low && low.nb < 0 ? h('p', { class: 'co-honest m-0' }, icon('alert'), h('span', {}, S ? `In the easier world the ${recN} is not worth its extra spares over the ${baseN}. It saves ${fmtHours(low.dA)} but costs ${fmtAED(-low.nb)} a year net. The extra spares are insurance against a harsher world.` : `In the low-stress world ${recN} is not worth its extra capital over ${baseN}: it saves ${fmtHours(low.dA)}${ciTxt(low.dAlo, low.dAhi, (v) => fmtNum(v, 1))}${low.dAlo != null && low.dAlo < 0 ? ' (not significant)' : ''} for ${low.recCap != null && low.p2Cap != null ? `${fmtAED(low.recCap - low.p2Cap)} more capital, and` : ''} costs ${fmtAED(-low.nb)} a year net. The rule would pick ${sn(low.pick)} there. The extra capital is insurance against a harsher world.`)) : null,
        h('p', { class: 't-12 m-0 co-a6', dataset: { role: 'stress-worlds' } }, h('span', { dataset: { readability: 'skip' } }, `${(F.stress_worlds?.text || '').replace(/^./, (c) => c.toUpperCase())}.`), ' ', F.stress_worlds?.ranges_note || ''),
        h('p', { class: 't-12 faint m-0' }, S ? `Spares were planned on central inputs, then tested again in each world. Net gain = cost of grounded hours avoided − extra holding cost, against the ${baseN}.` : `Allocations were planned on central inputs and re-simulated in each world. Net benefit = avoided AOG penalty − extra holding cost, paired against ${baseN}.`)),
    }));
  }

  // ---- method & limitations
  const deskO = typeof F.aog_desk_dependence === 'object' ? F.aog_desk_dependence : null;
  const desk = deskO && deskO.base_aog_hours != null ? { p0_base_aog_hours: deskO.p0_aog_hours, base_aog_hours: deskO.base_aog_hours, rec_aog_hours: deskO.rec_aog_hours } : (F.tornado || []).find((t) => t.factor === 'aog_desk_expedite');
  el.append(card({
    cls: 'mt-3', kicker: S ? 'Method and limits' : 'Method and limitations', title: 'What this frontier can and cannot tell you', prov: 'ASSUMED', story: 'capital-limits',
    body: h('div', { class: 'co-limits' },
      h('div', {}, h('h4', {}, icon('chart'), S ? 'The budget plans use a shortcut' : 'Greedy marginal allocation is a heuristic'), h('p', {}, S
        ? `Each budget plan adds spares one at a time, best value first. This shortcut (a heuristic) is not guaranteed to find the best mix. The frontier option is the ${BEST_EVAL}. Every plan is judged in the full model.`
        : `Budget points come from a greedy walk that adds the unit with the largest modelled delay-cost reduction per AED. Greedy finds the best allocation only for separable convex problems; with hub/outstation coupling and the wait cap it is a heuristic. The frontier option is the ${BEST_EVAL}. The analytic model only ranks candidates; the simulator judges every plan.`)),
      h('div', {}, h('h4', {}, icon('alert'), S ? 'It assumes the urgent-parts routes exist' : 'Conditional on the AOG-desk routes'), h('p', {}, S
        ? ['Every plan leans on the urgent-parts routes (AOG-desk routes). They include ', term('robbery', { first: true }), ' at AUH, borrowing at the same airport, and exchange or loan. Without them, grounded hours rise sharply for every plan.']
        : stripRefs(relabelArchetypeSafe((deskO ? deskO.text : F.aog_desk_dependence) || 'Every policy leans on the simulated AOG-desk routes.').replace(/\bP0\/P1\/P2\b/, `${sn('P0')}, ${sn('P1')} and ${baseN}`))),
        desk ? h('p', { class: 'mono t-12' }, `${S ? 'Routes off (tuning runs)' : 'AOG-desk routes off (selection seeds)'}: ${p0N} ${fmtHours(num(desk.p0_base_aog_hours))} · ${baseN} ${fmtHours(num(desk.base_aog_hours))} · ${recN} ${fmtHours(num(desk.rec_aog_hours))} a year`) : null),
      h('div', {}, h('h4', {}, icon('capital'), S ? 'Money in spares moves with the plan' : 'Capital is partly endogenous'), h('p', {}, S
        ? 'Money in spares is the average value of parts we own over the run. Borrowed or exchanged parts are never owned, so they add nothing. The ranges cover 20 runs of one world; the tougher and easier worlds show the best stopping point moves.'
        : 'Simulated capital is the time-average value of owned stock over the run. Borrowed or exchanged units are never owned, so they never add capital. CIs are over 20 seeds of one world; the stress variants show the knee moves with true reliability.'))),
  }));
  // v2.1 scope line for the Results / Frontier family of pages
  el.append(h('p', { class: 'co-scope t-12 faint mt-2', dataset: { role: 'scope-note' } }, S
    ? 'Scope: 120 modelled part numbers, one fictional airline, simulated data. Part costs, reliability and sourcing are assumed. These are not forecasts of real airline savings.'
    : 'Scope: 120 modelled part numbers, one fictional airline (Falcon Hub Airways), simulated data. Part costs, reliability and sourcing are assumed; results are conditional on the stated scenario and are not forecasts of achievable airline savings.'));

  return () => { dead = true; onBudget.cancel(); stopChart(); stops.forEach((s) => s()); try { window.d3?.selectAll(el.querySelectorAll('svg *')).interrupt(); window.d3?.selectAll(el.querySelectorAll('svg *')).interrupt('sel'); } catch { /* view already gone */ } };
}
