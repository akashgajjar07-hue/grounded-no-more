/**
 * 03 · Forecast Lab: which forecasting method wins, for which demand pattern, and does it matter for stock.
 * Data: forecast.json, demand_history.json, parts.json
 * Deep links: #/forecast?class=intermittent&part=R&win=holdout · #/forecast?pn=GN-32-R014
 *
 * Sections: sparse demand strips (small multiples per demand class), method leaderboard (dot + 95% CI, champion
 * highlighted, selection / holdout toggle), holdout champion check, lead-time demand distribution, stock-based
 * evaluation (fill rate vs capital), Monash Car Parts REAL benchmark, truth recovery (vendor-quoted vs estimated).
 * Every number on screen comes from the JSON exports; missing blocks show "not run".
 */
import { h, icon, pageHead, card, provChip, pill, segmented, sectionTitle, stateBlock, intro3, scopeLine } from '../ui.js';
import { term, termText } from '../lib/glossary.js';
import { isSimple, byMode } from '../lib/mode.js';
import { nameTag, displayName } from '../lib/names.js';
import { chartFrame, responsive, svgIn, axisBottom, axisLeft, gridY, theme, annotate, withTooltip, directLabel, refLine, dodge, markerRect, labelBox, truncate, fmtAED, fmtInt, fmtNum, fmtPct, fmtPts, fmtWeek } from '../charts/theme.js';
import { assetURL } from '../data.js';
import { demandStrip, demandStats } from './parts-intelligence/strip.js';
import { morphStore, morph, morphAxis, drawIn, liveDraw } from './forecast-lab/morph.js';
import { countUpOnce, MOTION } from '../lib/motion.js';

/** View stylesheet loader (same contract as parts-intelligence.js; kept local so this view does not import another view). */
function ensureCSS(path) {
  const existing = document.querySelector(`link[data-view-css="${path}"]`);
  if (existing) return existing._ready || Promise.resolve();
  const link = h('link', { rel: 'stylesheet', href: assetURL(path), dataset: { viewCss: path } });
  link._ready = new Promise((res) => { link.onload = res; link.onerror = res; });
  document.head.append(link);
  return link._ready;
}
const dcLabel = (c) => String(c || 'unclassified').replace('_', ' ');

/** directLabel whose colour survives the .gnm-label CSS fill. */
const lab = (g, o) => { const t = directLabel(g, o); if (o.color) t.style('fill', o.color); return t; };

export const data = ['forecast', 'demand_history', 'parts', 'method'];

const d3 = () => window.d3;
const num = (v) => (v == null || v === '' || Number.isNaN(+v) ? null : +v);
const DC_ORDER = ['smooth', 'erratic', 'intermittent', 'lumpy', 'insufficient_data'];
const PC_NAME = { R: 'rotables', E: 'expendables', C: 'consumables' };
const METHOD = {
  zero: 'Zero forecast', naive: 'Naive', ma: 'Moving average', croston: 'Croston', sba: 'SBA', tsb: 'TSB',
  adida: 'ADIDA', imapa: 'IMAPA', bootstrap: 'Willemain bootstrap', reliability: 'Reliability-exposure',
};
/**
 * v2.1 C1: Simple mode hides method names. Each method gets a plain description instead (what it does, not what it is
 * called); Expert mode keeps the textbook names (Croston, SBA, TSB …).
 */
const METHOD_SIMPLE = {
  zero: 'Always zero', naive: 'Last value', ma: 'Recent average', croston: 'Size-and-gap', sba: 'Size-and-gap, corrected',
  tsb: 'Weekly chance', adida: 'Grouped weeks', imapa: 'Grouped weeks, mixed', bootstrap: 'Resampled history', reliability: 'Flying-hours rate',
};
const SHORT_SIMPLE = { sba: 'Size-gap, corr.', imapa: 'Grouped, mixed', bootstrap: 'Resampled', reliability: 'Flying-hours' };
/** 'Naive (last 4w mean)' → 'naive', 'tsb' → 'tsb' */
const mKey = (m) => String(m || '').toLowerCase().split(/[\s(]/)[0].replace(/[^a-z0-9-]/g, '');
const mName = (m) => (isSimple() ? METHOD_SIMPLE[mKey(m)] : METHOD[mKey(m)]) || String(m);
const isZero = (m) => mKey(m) === 'zero';
const SHORT = { ma: 'Moving avg', bootstrap: 'Bootstrap', reliability: 'Reliability' };
/** Method name, shortened for narrow charts. */
const mNameS = (m, small) => (small && (isSimple() ? SHORT_SIMPLE : SHORT)[mKey(m)]) || mName(m);
/** Demand patterns: plain words in Simple mode (the ADI / CV² class names are expert vocabulary). */
const DC_SIMPLE = { smooth: 'steady', erratic: 'uneven', intermittent: 'now and then', lumpy: 'now and then, in bursts', insufficient_data: 'too little history' };
const dcName = (c) => (isSimple() ? DC_SIMPLE[c] || dcLabel(c) : dcLabel(c));
const PC_SIMPLE = { R: 'repairable parts', E: 'throw-away parts', C: 'consumables' };
const pcName = (pc) => (isSimple() ? PC_SIMPLE[pc] : PC_NAME[pc]);
const PC_BTN = () => (isSimple() ? { R: 'Repairable', E: 'Throw-away', C: 'Consumable' } : { R: 'Rotable', E: 'Expendable', C: 'Consumable' });
/** MASE as a short plain label. */
const MASE = () => byMode('error score', 'MASE');
const ordinal = (n) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th')}`;
/** A median absolute log error of 0.07 reads as "about 7% off" (|ln(est/true)| ≈ relative error when small). */
const cap1 = (t) => String(t).charAt(0).toUpperCase() + String(t).slice(1);
const offPct = (v) => (v == null ? null : `${Math.round(v * 100)}%`);
const ciOf = (r, k = 'mase') => (Array.isArray(r[`${k}_ci`]) ? r[`${k}_ci`] : [r[`${k}_ci_lo`], r[`${k}_ci_hi`]]);
const champOf = (c) => c?.champion ?? c?.method;
/** First headline candidate that fits the 90-character cap (DESIGN_SYSTEM: one finding, ≤ 90 chars). */
const fit = (...c) => c.filter(Boolean).find((t) => t.length <= 90) || c.filter(Boolean).at(-1);
/** Same, with a tighter cap for half-width cards so the headline stays on ≤ 2 lines (critic: 3-line wraps). */
const fitN = (max, ...c) => c.filter(Boolean).find((t) => t.length <= max) || c.filter(Boolean).at(-1);
const HALF = 64;

export async function render(el, ctx) {
  await ensureCSS('css/views/parts-intelligence.css');
  await ensureCSS('css/views/forecast-lab.css');
  const { forecast: F, demand_history: DH, parts: P, method: MT } = ctx.data;
  const assumption = (key) => (MT?.assumptions || []).find((a) => a.key === key);
  const parts = P.parts || [];
  const byPn = new Map(parts.map((p) => [p.pn, p]));
  const fprov = F.meta?.provenance || 'DERIVED';
  const selStart = DH.split_week ?? (DH.meta?.train_weeks?.[1] ?? 77) + 1;
  const trainEnd = selStart - 1;
  const lastWeek = DH.weeks?.[1] ?? 103;

  // leaderboards by window
  const lbAll = F.leaderboard || [];
  const lbSel = lbAll.filter((r) => !r.window && !r.split ? true : (r.window || r.split) === 'selection');
  const lbHold = F.leaderboard_holdout || F.holdout?.leaderboard || lbAll.filter((r) => (r.window || r.split) === 'holdout');
  const check = F.champion_check || F.holdout_check || F.holdout?.champion_check || [];
  const champs = F.champions || [];
  const selWin = F.meta?.selection_weeks || F.selection_weeks;
  const holdWin = F.meta?.holdout_weeks || F.holdout_weeks || F.holdout?.weeks;
  const winText = (w) => (Array.isArray(w) ? `${fmtWeek(w[0])}–${fmtWeek(w[1])}` : null);

  const classes = DC_ORDER.filter((c) => lbSel.some((r) => r.demand_class === c));
  const pcsFor = (dc) => ['R', 'E', 'C'].filter((pc) => lbSel.some((r) => r.demand_class === dc && r.part_class === pc));
  const pnParam = byPn.get(ctx.params.pn);
  let dc = classes.includes(ctx.params.class) ? ctx.params.class : pnParam && classes.includes(pnParam.demand_class) ? pnParam.demand_class : classes.includes('intermittent') ? 'intermittent' : classes[0];
  let pc = pcsFor(dc).includes(ctx.params.part) ? ctx.params.part : pnParam && pcsFor(dc).includes(pnParam.cls) ? pnParam.cls : pcsFor(dc).includes('R') ? 'R' : pcsFor(dc)[0];
  let win = ctx.params.win === 'holdout' && lbHold.length ? 'holdout' : 'selection';

  const nChamps = champs.length;
  const S = isSimple();
  const nMethods = (F.methods || [...new Set(lbSel.map((r) => mKey(r.method)))]).length;
  el.append(pageHead({
    num: '03', eyebrow: 'Forecast Lab',
    title: byMode('Forecasting parts that are rarely needed', 'Which forecasting method wins, for which demand pattern'),
    lede: S
      ? `Most spare parts are needed only a few times a year. We tested ${fmtInt(nMethods)} ways to forecast them. One method was picked for each group of parts in advance, then checked on fresh data.`
      : `Spare-parts demand is mostly zeros. ${fmtInt(nMethods)} methods are scored by rolling-origin evaluation on the selection weeks; a champion is frozen per demand × part class (${fmtInt(nChamps)} cells) and then checked on the untouched holdout. MASE below 1 beats the in-sample naive forecast.`,
    meta: [provChip(fprov), h('span', { class: 'chip' }, S ? `${fmtInt(nChamps)} groups of parts` : `${fmtInt(nChamps)} champion cells`)],
  }));
  el.append(intro3({
    what: S
      ? ['How well ', term('forecast_methods'), ' predicted demand, and what that means for spares.']
      : ['How ', term('forecast_methods'), ' and six other methods score on intermittent demand, on the selection weeks and on the holdout.'],
    why: S
      ? 'A poor forecast means too few spares on the shelf, or money stuck in too many.'
      : 'Forecast error feeds safety stock and reorder points; a champion that does not hold up out of sample misprices stock.',
    action: S
      ? 'Size repairable spares on how often parts really come off the aircraft. Check any forecast on fresh data first.'
      : 'Size rotables on the reliability (FH/FC) rate fitted to removals; treat the forecast champion as provisional until re-scored.',
  }));

  const cleanups = [];
  const MS = morphStore(); // v2.1 motion: previous mark positions per chart, for keyed transitions

  // ================================================================== 0. the honest result (v2.1): three findings, stated plainly
  {
    const held = check.filter((r) => r.champion_rank === 1).length;
    const ir = check.find((r) => r.demand_class === 'intermittent' && r.part_class === 'R');
    const tr = (F.truth_recovery || []).find((t) => t.vendor_quoted != null && /mtbur/i.test(t.param) && /\+/.test(t.param))
      || (F.truth_recovery || []).find((t) => t.vendor_quoted != null && /mtbur/i.test(t.param));
    // v2.1 motion: the headline numbers count up ONCE per session (countUpOnce, 600 ms), never on re-render
    const cu = (v, fmt, key) => { const sp = h('span', { class: 'fl-cu' }, fmt(v)); countUpOnce(sp, v, fmt, { key }); return sp; };
    const pctF = (v) => `${Math.round(v)}%`;
    const stat = (big, text, extra) => h('div', { class: 'fl-find' }, h('div', { class: 'fl-find-v' }, big), h('p', { class: 'fl-find-t' }, text), extra || null);
    const items = [];
    if (check.length) {
      items.push(stat([cu(held, (v) => fmtInt(Math.round(v)), 'forecast-held'), ` of ${fmtInt(check.length)}`], S
        ? `The method chosen in advance was best in only ${fmtInt(held)} of ${fmtInt(check.length)} groups of parts on the fresh test runs.`
        : `Frozen champions held rank 1 on the holdout in ${fmtInt(held)} of ${fmtInt(check.length)} demand × part-class cells.`));
    }
    if (ir) {
      items.push(stat(S ? `${ordinal(ir.champion_rank)} of ${fmtInt(ir.n_methods)}` : `${fmtInt(ir.champion_rank)} / ${fmtInt(ir.n_methods)}`, S
        ? `For rarely-needed repairable parts, the method chosen in advance ranked ${ordinal(ir.champion_rank)} of ${fmtInt(ir.n_methods)} on the fresh test runs.`
        : `${METHOD[mKey(ir.champion)] || ir.champion}, the intermittent-rotable champion (${fmtInt(ir.n_parts)} PNs), ranked ${fmtInt(ir.champion_rank)} of ${fmtInt(ir.n_methods)} on the holdout; best in hindsight: ${METHOD[mKey(ir.best_in_hindsight)] || ir.best_in_hindsight}.`,
        h('p', { class: 'fl-find-n' }, S ? 'The stocking plans size repairable parts on the flying-hours rate, not on this forecast.' : 'The policies size rotables on the reliability-exposure rate, not on this champion.')));
    }
    if (tr) {
      items.push(stat([cu(Math.round(tr.estimated * 100), pctF, 'forecast-truth-est'), ' vs ', cu(Math.round(tr.vendor_quoted * 100), pctF, 'forecast-truth-quoted')], S
        ? ['Removal rates worked out from our own history were about ', offPct(tr.estimated), ' off the truth. Supplier quotes were about ', offPct(tr.vendor_quoted), ' off.']
        : `MTBUR fitted to removals: median abs log error ${fmtNum(tr.estimated, 3)} vs ${fmtNum(tr.vendor_quoted, 3)} vendor-quoted (${fmtInt(tr.n_parts)} PNs; estimate closer for ${fmtPct(tr.share_estimate_closer, 0)}).`,
        h('p', { class: 'fl-find-n' }, S ? 'The true values are hidden. Only the scoring step reads them.' : 'Truth is read only by the evaluation step, never by forecasting or policy code.')));
    }
    if (items.length) {
      el.append(h('section', { class: 'card fl-findings', dataset: { story: 'forecast-honest' } },
        h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, S ? 'The honest result' : 'Holdout result'), h('h2', { class: 'card-title' }, S ? 'Forecasting rare parts is hard, and the result says so' : 'Champions mostly did not hold up; history-fitted rates did')), provChip(fprov)),
        h('div', { class: 'fl-find-grid' }, items),
        scopeLine({ text: 'across 120 modelled part numbers · simulated · forecast accuracy, not downtime' })));
    }
  }

  // ================================================================== 1. demand strips
  {
    const host = h('section', { class: 'card' });
    el.append(host);
    const all = parts.map((p) => ({ p, s: demandStats(DH.series?.[p.pn] || [], 0, trainEnd) })).filter((x) => x.s.weeks);
    const zs = all.map((x) => x.s.zeroShare).sort((a, b) => a - b);
    const med = zs.length ? zs[Math.floor(zs.length / 2)] : null;
    const f = chartFrame(host, {
      implication: byMode('Most parts are needed rarely, so forecast accuracy alone cannot decide stock.', 'Most parts demand rarely, so forecast accuracy alone cannot drive stocking decisions.'),
      headline: med != null ? (S ? `The typical part is not needed at all in ${fmtPct(med, 0)} of weeks` : `The median part number sees no demand in ${fmtPct(med, 0)} of training weeks`) : 'Weekly demand history',
      subtitle: S
        ? `Units needed per week, ${fmtWeek(0)}–${fmtWeek(lastWeek)}, simulated. Three example parts per demand pattern. Shaded weeks were used to pick the method.`
        : `Units per week · ${fmtWeek(0)}–${fmtWeek(lastWeek)} · three representative PNs per demand class (20th / 50th / 80th percentile of demand weeks) · shaded = selection weeks ${fmtWeek(selStart)}–${fmtWeek(lastWeek)} · simulated`,
      provenance: DH.meta?.provenance || 'SIMULATED', source: 'demand_history.json, parts.json', story: 'forecast-demand-strip',
      table: { columns: [{ key: 'pn', label: S ? 'Part' : 'PN', mono: true }, { key: 'dc', label: S ? 'Demand pattern' : 'Demand class', format: dcName }, { key: 'nz', label: S ? 'Weeks with demand' : 'Weeks with demand (train)', num: true }, { key: 'total', label: S ? 'Units needed' : 'Units (train)', num: true }], rows: all.map((x) => ({ pn: x.p.pn, dc: x.p.demand_class, nz: x.s.nz, total: x.s.total })) },
    });
    const grid = h('div', { class: 'fl-strips' });
    f.body.append(grid);
    if (pnParam) {
      const s = DH.series?.[pnParam.pn] || [];
      const hostSel = h('div', { class: 'fl-strip-hero' });
      grid.before(h('div', { class: 'fl-strip-sel' }, h('div', { class: 'fl-strip-label' }, h('span', { class: 'chip chip-mono' }, 'Selected'), h('a', { class: 'mono', href: `#/parts?pn=${pnParam.pn}` }, pnParam.pn), h('span', { class: 'faint' }, `${pnParam.desc} · ${dcName(pnParam.demand_class)}`)), hostSel));
      cleanups.push(demandStrip(hostSel, s, { height: 120, splitAt: selStart, annot: false }));
    }
    DC_ORDER.filter((c) => all.some((x) => x.p.demand_class === c)).forEach((c) => {
      const inC = all.filter((x) => x.p.demand_class === c).sort((a, b) => a.s.nz - b.s.nz || a.p.pn.localeCompare(b.p.pn));
      const picks = [...new Set([0.2, 0.5, 0.8].map((q) => Math.min(inC.length - 1, Math.floor(q * inC.length))))].map((i) => inC[i]);
      const col = h('div', { class: 'fl-strip-col' }, h('div', { class: 'fl-strip-head' }, h('span', { class: 'fl-dc' }, dcName(c).replace(/^./, (x) => x.toUpperCase())), h('span', { class: 'faint mono' }, S ? `${fmtInt(inC.length)} part${inC.length === 1 ? '' : 's'}` : `${fmtInt(inC.length)} PN${inC.length === 1 ? "" : "s"}`)));
      picks.forEach(({ p, s }) => {
        const sh = h('div', { class: 'fl-strip-plot' });
        col.append(h('div', { class: 'fl-strip' }, h('div', { class: 'fl-strip-meta' }, h('a', { class: 'mono', href: `#/parts?pn=${p.pn}` }, p.pn), h('span', { class: 'faint mono' }, `${fmtInt(s.nz)}/${fmtInt(s.weeks)} wk · max ${fmtInt(Math.max(...(DH.series[p.pn] || [0])))}`)), sh));
        cleanups.push(demandStrip(sh, DH.series[p.pn], { height: 54, compact: true, splitAt: selStart }));
      });
      grid.append(col);
    });
  }

  // ================================================================== 2. leaderboard
  el.append(sectionTitle(byMode('Which method predicted best', 'Method leaderboard'), provChip(fprov)));
  const dcSegHost = h('div');
  const pcSegHost = h('div');
  const winSeg = segmented({ label: 'Evaluation window', value: win, options: [{ value: 'selection', label: byMode('Tuning weeks', 'Selection') }, { value: 'holdout', label: lbHold.length ? byMode('Fresh test', 'Holdout') : byMode('Fresh test · not run', 'Holdout · not run') }], onChange: (v) => { win = v === 'holdout' && !lbHold.length ? 'selection' : v; ctx.setParams({ win: win === 'holdout' ? 'holdout' : '' }); drawBoard(); } });
  el.append(h('div', { class: 'fl-controls' }, h('div', { class: 'fl-control' }, h('span', { class: 'fl-control-l' }, byMode('Demand pattern', 'Demand class')), dcSegHost), h('div', { class: 'fl-control' }, h('span', { class: 'fl-control-l' }, byMode('Part type', 'Part class')), pcSegHost), h('div', { class: 'fl-control' }, h('span', { class: 'fl-control-l' }, byMode('Data', 'Window')), winSeg)));
  const boardCard = h('section', { class: 'card span-8 md-span-12', dataset: { story: 'forecast-leaderboard' } });
  const champCard = h('section', { class: 'card span-4 md-span-12 fl-champ' });
  el.append(h('div', { class: 'grid-12' }, boardCard, champCard));
  let boardStop = null;

  // v2.1 motion: the controls persist across changes so their thumbs slide; the part-type control is rebuilt only
  // when its option set changes
  let pcKeys = '';
  function buildPcSeg() {
    const keys = pcsFor(dc).join(',');
    if (keys === pcKeys) { pcSegHost.querySelectorAll('[role="radio"]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === pc))); return; }
    pcKeys = keys;
    pcSegHost.replaceChildren(segmented({ label: 'Part class', value: pc, options: pcsFor(dc).map((x) => ({ value: x, label: PC_BTN()[x] })), onChange: (v) => { pc = v; ctx.setParams({ part: v }); drawBoard(); } }));
  }
  function buildSegs() {
    dcSegHost.replaceChildren(segmented({ label: 'Demand class', value: dc, options: classes.map((c) => ({ value: c, label: dcName(c) })), onChange: (v) => { dc = v; if (!pcsFor(dc).includes(pc)) pc = pcsFor(dc)[0]; buildPcSeg(); ctx.setParams({ class: dc, part: pc }); drawBoard(); } }));
    buildPcSeg();
  }

  // v2.1 addendum: the leaderboard frame is built once; a control change updates its headline, key line, table and
  // marks in place (the marks morph), so nothing in the frame (e.g. its More button) is torn down under the pointer
  let boardF = null;
  function drawBoard() {
    boardStop?.();
    const src = win === 'holdout' ? lbHold : lbSel;
    const rows = src.filter((r) => r.demand_class === dc && r.part_class === pc && Number.isFinite(r.mase));
    const champ = champs.find((c) => c.demand_class === dc && c.part_class === pc);
    const champKey = mKey(champOf(champ));
    const eligible = rows.filter((r) => !isZero(r.method)).sort((a, b) => a.mase - b.mase);
    const zero = rows.find((r) => isZero(r.method));
    const champRow = rows.find((r) => mKey(r.method) === champKey);
    const best = eligible[0];
    const n = rows[0]?.n ?? rows[0]?.n_parts;
    const winLabel = S
      ? (win === 'holdout' ? 'fresh test data' : 'tuning weeks')
      : win === 'holdout' ? `holdout${winText(holdWin) ? ` ${winText(holdWin)}` : ''}` : `selection weeks${winText(selWin) ? ` ${winText(selWin)}` : ''}`;
    const DC_PHRASE = { smooth: 'with steady demand', erratic: 'with uneven demand', intermittent: 'needed now and then', lumpy: 'needed in bursts', insufficient_data: 'with little history' };
    const cellName = `${pcName(pc)} ${DC_PHRASE[dc] || dcName(dc)}`;
    let headline;
    if (!rows.length) headline = S ? `No ${winLabel} results for ${cellName}` : `No ${win} leaderboard rows for ${dcLabel(dc)} ${PC_NAME[pc]}`;
    else if (champRow && win === 'selection') {
      headline = S
        ? fit(`"${mName(champRow.method)}" was chosen in advance for ${cellName}`, `"${mName(champRow.method)}" was chosen in advance`)
        : fit(zero && zero.mase < champRow.mase ? `${mName(champRow.method)} is the frozen champion for ${dcLabel(dc)} ${PC_NAME[pc]} (MASE ${fmtNum(champRow.mase)}); zero scores lower (${fmtNum(zero.mase)})` : null, `${mName(champRow.method)} is the frozen champion for ${dcLabel(dc)} ${PC_NAME[pc]} (MASE ${fmtNum(champRow.mase)})`, `${mName(champRow.method)} is the frozen champion (MASE ${fmtNum(champRow.mase)})`);
    } else if (champRow) {
      const rank = eligible.indexOf(champRow) + 1;
      headline = S
        ? (rank === 1 ? fit(`On fresh data, the method chosen in advance is still best for ${cellName}`, 'On fresh data, the method chosen in advance is still best') : fit(`On fresh data, the method chosen in advance ranks ${ordinal(rank)} of ${eligible.length} for ${cellName}`, `On fresh data, the method chosen in advance ranks ${ordinal(rank)} of ${eligible.length}`))
        : rank === 1 ? fit(`On the holdout the frozen champion ${mName(champRow.method)} is still best for ${dcLabel(dc)} ${PC_NAME[pc]}`, `On the holdout the frozen champion ${mName(champRow.method)} is still best`) : fit(`On the holdout the frozen champion ${mName(champRow.method)} ranks ${rank} of ${eligible.length}; ${mName(best.method)} would have won`, `On the holdout the frozen champion ${mName(champRow.method)} ranks ${rank} of ${eligible.length}`);
    } else headline = S ? fit(`"${mName(best.method)}" has the lowest error for ${cellName}`, `"${mName(best.method)}" has the lowest error`) : fit(`${mName(best.method)} has the lowest eligible MASE for ${dcLabel(dc)} ${PC_NAME[pc]} (${fmtNum(best.mase)})`, `${mName(best.method)} has the lowest eligible MASE (${fmtNum(best.mase)})`);
    const fresh = !boardF;
    if (fresh) boardF = chartFrame(boardCard, {
      implication: byMode('No method wins everywhere. Base stock on rates that hold up, not on this league table.', 'No method wins everywhere: size stock on rates that hold up, not on the error league table.'),
      headline,
      subtitle: S
        ? 'Forecast error compared with a simple guess, averaged over the parts in this group. Lower is better. Lines show the likely range; the dashed line is the simple guess.'
        : 'MASE, mean over the PNs in the cell with 95% bootstrap CI · lower is better · dashed = naive scale (1.0)',
      provenance: fprov, source: 'forecast.json (leaderboard)',
      table: { columns: [{ key: 'method', label: 'Method', format: mName }, { key: 'mase', label: S ? 'Error score' : 'MASE', num: true, format: (v) => fmtNum(v, 3) }, { key: 'lo', label: S ? 'Range low' : 'CI low', num: true, format: (v) => fmtNum(v, 3) }, { key: 'hi', label: S ? 'Range high' : 'CI high', num: true, format: (v) => fmtNum(v, 3) }, { key: 'bias', label: S ? 'High or low' : 'Bias', num: true, format: (v) => fmtNum(v, 3) }, { key: 'coverage', label: S ? 'Range caught it' : 'Coverage', num: true, format: (v) => fmtPct(v, 0) }], rows: rows.map((r) => ({ ...r, lo: ciOf(r)[0], hi: ciOf(r)[1] })) },
    });
    const f = boardF;
    if (!fresh) {
      f.root.querySelector('.chart-headline').textContent = headline;
      const tb = { columns: [{ key: 'method', label: 'Method', format: mName }, { key: 'mase', label: S ? 'Error score' : 'MASE', num: true, format: (v) => fmtNum(v, 3) }, { key: 'lo', label: S ? 'Range low' : 'CI low', num: true, format: (v) => fmtNum(v, 3) }, { key: 'hi', label: S ? 'Range high' : 'CI high', num: true, format: (v) => fmtNum(v, 3) }, { key: 'bias', label: S ? 'High or low' : 'Bias', num: true, format: (v) => fmtNum(v, 3) }, { key: 'coverage', label: S ? 'Range caught it' : 'Coverage', num: true, format: (v) => fmtPct(v, 0) }], rows: rows.map((r) => ({ ...r, lo: ciOf(r)[0], hi: ciOf(r)[1] })) };
      f.setTable(tb.columns, tb.rows);
      f.root.querySelector('[data-role="board-key"]')?.remove();
      f.body.replaceChildren();
    }
    if (!rows.length) { f.body.append(stateBlock('empty', 'not run')); drawChamp(champ, null, null, null); return; }
    // wave 5: a one-line key, so the starred champion and the teal policy rate never compete for "the answer"
    // v2.1: the cell-specific facts (window, cell size) live in this key line, so the subtitle (and its More button)
    // stays the same when the controls change
    f.body.before(h('p', { class: 'fl-key t-12 faint', dataset: { role: 'board-key' } }, h('span', { class: 'fl-key-w' }, `${n != null ? `${fmtInt(n)} ${S ? 'parts' : 'PNs'}` : ''} · ${winLabel}`), ' · ', h('span', { class: 'fl-key-g' }, h('span', { class: 'fl-key-i' }, '★'), byMode(' chosen in advance (best on the tuning weeks)', ' frozen champion (best MASE on selection weeks)')), pc === 'R' ? h('span', { class: 'fl-key-g' }, h('span', { class: 'fl-key-sw' }), byMode(' teal = the rate the repairable-part plans use', ' teal = the rate the rotable policies use')) : null));
    const ordered = eligible.concat(zero ? [zero] : []);
    // teal = the method the stocking policies actually use for this part class (rotables: the reliability-exposure
    // rate, per forecast.json meta); the frozen champion is marked with ★ + neutral strong, not the recommendation colour
    const policyKey = pc === 'R' && /reliability rate/i.test(F.meta?.notes || '') ? 'reliability' : null;
    boardStop = liveDraw(f.body, (w) => {
      const small = w < 480;
      const rowH = 34, labelW = small ? 104 : 190;
      const m = { top: 22, right: small ? 44 : 64, bottom: 30, left: labelW };
      const hgt = m.top + m.bottom + ordered.length * rowH + (zero ? 10 : 0);
      const iw = Math.max(60, w - m.left - m.right), ih = hgt - m.top - m.bottom;
      const svg = svgIn(f.body, w, hgt, byMode('Forecast error by method with likely ranges', 'MASE by method with 95% confidence intervals'));
      const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
      const vals = ordered.flatMap((r) => [ciOf(r)[0] ?? r.mase, ciOf(r)[1] ?? r.mase, r.mase]).concat([1]);
      const x = d3().scaleLinear().domain([Math.max(0, d3().min(vals) * 0.92), d3().max(vals) * 1.04]).nice().range([0, iw]);
      const yPos = (i) => i * rowH + rowH / 2 + (zero && i === ordered.length - 1 ? 10 : 0);
      morphAxis(MS, 'board-x', w, g.append('g'), x, (ga, sc) => axisBottom(ga, sc, { height: ih, ticks: small ? 3 : 6, format: (v) => fmtNum(v, 1) }));
      refLine(g, { x1: x(1), y1: ih, x2: x(1), y2: -10, label: S ? (small ? 'guess = 1' : 'simple guess = 1.0') : small ? 'naive = 1' : 'naive scale = 1.0', dx: 4, dy: -2, anchor: x(1) > iw * 0.7 ? 'end' : 'start' });
      if (zero) g.append('line').attr('class', 'fl-sep').attr('x1', -labelW + 8).attr('x2', iw).attr('y1', yPos(ordered.length - 1) - rowH / 2 - 2).attr('y2', yPos(ordered.length - 1) - rowH / 2 - 2);
      const rowsG = g.selectAll('g.fl-row').data(ordered).join('g').attr('class', (r) => `fl-row ${mKey(r.method) === champKey ? 'is-champ' : ''} ${mKey(r.method) === policyKey ? 'is-policy' : ''} ${isZero(r.method) ? 'is-zero' : ''}`).attr('transform', (r, i) => `translate(0,${yPos(i)})`);
      rowsG.append('rect').attr('class', 'fl-row-bg').attr('x', -labelW + 4).attr('y', -rowH / 2 + 2).attr('width', labelW + iw + m.right - 8).attr('height', rowH - 4).attr('rx', 6);
      rowsG.append('line').attr('class', 'fl-ci').attr('x1', (r) => x(ciOf(r)[0] ?? r.mase)).attr('x2', (r) => x(ciOf(r)[1] ?? r.mase));
      rowsG.append('line').attr('class', 'fl-ci').attr('x1', (r) => x(ciOf(r)[0] ?? r.mase)).attr('x2', (r) => x(ciOf(r)[0] ?? r.mase)).attr('y1', -4).attr('y2', 4);
      rowsG.append('line').attr('class', 'fl-ci').attr('x1', (r) => x(ciOf(r)[1] ?? r.mase)).attr('x2', (r) => x(ciOf(r)[1] ?? r.mase)).attr('y1', -4).attr('y2', 4);
      rowsG.append('circle').attr('class', 'fl-dot').attr('cx', (r) => x(r.mase)).attr('r', (r) => (mKey(r.method) === champKey ? 6 : 4.5));
      const subOf = (r) => {
        if (small) return null;
        if (mKey(r.method) === champKey) return S ? (win === 'selection' ? 'chosen in advance' : `chosen in advance · ${ordinal(eligible.indexOf(r) + 1)} of ${eligible.length}`) : win === 'selection' ? 'frozen champion' : `frozen champion · rank ${eligible.indexOf(r) + 1}/${eligible.length}`;
        if (mKey(r.method) === policyKey) return byMode('used by repairable-part plans', 'used by rotable policies');
        return null;
      };
      rowsG.append('text').attr('class', 'fl-mlabel').attr('x', -12).attr('dy', (r) => (subOf(r) ? '-0.18em' : '0.32em')).attr('text-anchor', 'end').text((r) => truncate(isZero(r.method) ? (S ? (small ? 'zero (excl.)' : 'Always zero · yardstick') : small ? 'zero (excl.)' : 'Zero · benchmark only') : `${mKey(r.method) === champKey ? '★ ' : ''}${mNameS(r.method, small)}`, labelW - 16));
      rowsG.filter((r) => !!subOf(r)).append('text').attr('class', 'fl-msub').attr('x', -12).attr('y', 11).attr('text-anchor', 'end').text((r) => subOf(r));
      rowsG.append('text').attr('class', 'fl-vlabel').attr('x', iw + 10).attr('dy', '0.32em').text((r) => fmtNum(r.mase));
      // v2.1 motion: rows re-sort and dots / ranges slide to their new values (keyed by method), never redrawn from zero
      const rk = (r) => mKey(r.method);
      morph(MS, 'board', w, rowsG, rk, { transform: (r, i) => `translate(0,${yPos(i)})` });
      morph(MS, 'board', w, rowsG.selectAll('line.fl-ci'), (r, i) => `${rk(r)}#${i}`, { x1: function () { return this.getAttribute('x1'); }, x2: function () { return this.getAttribute('x2'); } }, { drawIn: false });
      morph(MS, 'board', w, rowsG.selectAll('circle.fl-dot'), rk, { cx: (r) => x(r.mase) }, { drawIn: false });
      morph(MS, 'board', w, rowsG.selectAll('text.fl-vlabel'), rk, { x: iw + 10 }, { drawIn: false });
      withTooltip(rowsG, (r) => ({ title: mName(r.method), rows: [[S ? 'Error score' : 'MASE', fmtNum(r.mase, 3)], [termText('ci', { cap: true }), `${fmtNum(ciOf(r)[0], 3)} – ${fmtNum(ciOf(r)[1], 3)}`], [S ? 'High or low (units/wk)' : 'Bias (units/wk)', fmtNum(r.bias, 3)], [S ? 'Range caught it' : 'Coverage', fmtPct(r.coverage, 0)]], note: isZero(r.method) ? byMode('Yardstick only: not allowed to win.', 'Benchmark only: excluded from champion eligibility.') : mKey(r.method) === champKey ? byMode('Chosen in advance (tuning weeks).', 'Frozen champion (selection weeks).') : '' }));
    });
    drawChamp(champ, champRow, zero, eligible);
  }

  function drawChamp(champ, champRow, zero, eligible) {
    const chk = check.find((c) => c.demand_class === dc && c.part_class === pc);
    const runner = champ?.runner_up;
    const tooZero = zero && champRow && zero.mase < champRow.mase;
    champCard.replaceChildren(
      h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, S ? `Chosen in advance · ${dcName(dc)} ${pcName(pc)}` : `Champion · ${dcLabel(dc)} ${PC_NAME[pc]}`), h('h3', { class: 'fl-champ-name' }, champ ? mName(champOf(champ)) : 'not run')), provChip(fprov)),
      champ ? h('dl', { class: 'meta-list' }, ...[
        [S ? 'Error score (tuning)' : 'Selection MASE', fmtNum(champ.mase ?? champ.mean_mase, 2)],
        [S ? 'High or low' : 'Bias', champ.mean_bias != null ? `${fmtNum(champ.mean_bias, 3)} units / wk` : null],
        ['Basis', !S && champ.basis ? String(champ.basis).replace(/_/g, ' ') : null],
        [S ? 'Second best' : 'Runner-up', runner ? mName(runner) : null],
        [S ? 'Rank on fresh data' : 'Holdout rank', chk ? (S ? `${ordinal(chk.champion_rank)} of ${fmtInt(chk.n_methods)}` : `${fmtInt(chk.champion_rank)} of ${fmtInt(chk.n_methods)}`) : 'not run'],
        [S ? 'Best on fresh data' : 'Best in hindsight', chk ? `${mName(chk.best_in_hindsight)} (${fmtNum(chk.best_mase, 2)})` : null],
      ].filter(([, v]) => v != null).flatMap(([k, v]) => [h('dt', {}, k), h('dd', { class: 'mono' }, v)])) : stateBlock('empty', S ? 'No method chosen for this group' : 'No champion exported for this cell'),
      h('div', { class: 'fl-honest', role: 'note' }, icon('info'),
        S
          ? h('div', {}, h('strong', {}, 'Why "always zero" is not allowed to win'),
            h('p', {}, `The error score rewards guessing the most common value. For rare parts, that is often zero.${tooZero ? ` Here zero scores ${fmtNum(zero.mase)}, against ${fmtNum(champRow.mase)} for the chosen method.` : ''} A zero forecast never orders a spare. So it is kept only as a yardstick. Stock is judged below on shelf availability and money.`))
          : h('div', {}, h('strong', {}, 'Why the zero forecast is not allowed to win'),
            h('p', {}, `MASE is an absolute-error metric, so on intermittent series it rewards forecasting the median, which is often zero.${tooZero ? ` Here zero scores ${fmtNum(zero.mase)} against the champion's ${fmtNum(champRow.mase)}.` : ''} A zero forecast never orders a spare, so it is kept as a benchmark and excluded from champion eligibility; stock decisions are judged on fill rate and capital below.`))));
  }
  buildSegs();
  drawBoard();

  // ================================================================== 3. holdout champion check
  {
    const host = h('section', { class: 'card' });
    el.append(h('div', { class: 'mt-3' }, host));
    if (!check.length) {
      chartFrame(host, { headline: byMode('Check on fresh data: not run', 'Holdout champion check: not run'), subtitle: byMode('Chosen methods re-scored on fresh data', 'Frozen champions re-scored on the holdout window'), provenance: fprov, source: 'forecast.json' }).body.append(stateBlock('empty', 'not run'));
    } else {
      const rows = check.slice().sort((a, b) => a.champion_rank / a.n_methods - b.champion_rank / b.n_methods);
      const held = rows.filter((r) => r.champion_rank === 1).length;
      const worst = rows.slice().sort((a, b) => b.champion_rank / b.n_methods - a.champion_rank / a.n_methods || b.n_parts - a.n_parts)[0];
      const f = chartFrame(host, {
      implication: byMode('Methods chosen in advance rarely stay best on fresh data, so plans must allow for forecast error.', 'Frozen champions rarely stay best out of sample, so plans must carry forecast uncertainty.'),
        headline: S
          ? `The method chosen in advance stayed best in ${held * 2 < rows.length ? 'only ' : ''}${fmtInt(held)} of ${fmtInt(rows.length)} groups of parts`
          : `${held * 2 < rows.length ? 'Only ' : ''}${fmtInt(held)} of ${fmtInt(rows.length)} frozen champions stayed best when re-scored on the holdout`,
        subtitle: S
          ? 'Rank of each chosen method on the fresh test runs (1 = best). Dot size shows the number of parts. Methods were chosen before scoring.'
          : `Holdout rank of each frozen champion among eligible methods (1 = best) · MASE${winText(holdWin) ? ` · ${winText(holdWin)}` : ''} · cells sized by PNs · champions were frozen before the holdout was scored`,
        provenance: fprov, source: 'forecast.json (champion_check)', story: 'forecast-holdout-check',
        table: { columns: [{ key: 'cell', label: S ? 'Group of parts' : 'Cell' }, { key: 'champion', label: S ? 'Chosen in advance' : 'Champion', format: mName }, { key: 'champion_rank', label: 'Rank', num: true }, { key: 'n_methods', label: 'of', num: true }, { key: 'best_in_hindsight', label: S ? 'Best on fresh data' : 'Best in hindsight', format: mName }, { key: 'n_parts', label: S ? 'Parts' : 'PNs', num: true }], rows: rows.map((r) => ({ ...r, cell: S ? `${dcName(r.demand_class)} · ${pcName(r.part_class)}` : `${dcLabel(r.demand_class)} · ${r.part_class}` })) },
      });
      cleanups.push(responsive(f.body, (w) => {
        const small = w < 520;
        const rowH = 32, labelW = small ? 136 : 220;
        const nMax = d3().max(rows, (r) => r.n_methods);
        const m = { top: 20, right: small ? 52 : 250, bottom: 44, left: labelW };
        const hgt = m.top + m.bottom + rows.length * rowH;
        const iw = Math.max(80, w - m.left - m.right);
        const svg = svgIn(f.body, w, hgt, byMode('Rank of each chosen method on fresh data', 'Holdout rank of frozen champions'));
        const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
        const x = d3().scaleLinear().domain([1, nMax]).range([0, iw]);
        lab(g, { x: 0, y: -10, text: 'rank 1 · best', color: theme.color.faint, dy: '0' });
        lab(g, { x: iw, y: -10, text: `${nMax} · worst`, color: theme.color.faint, anchor: 'end', dy: '0' });
        const rg = g.selectAll('g.fl-rank').data(rows).join('g').attr('transform', (r, i) => `translate(0,${i * rowH + rowH / 2})`).attr('class', (r) => `fl-rank ${r.champion_rank === r.n_methods ? 'is-last' : r.champion_rank === 1 ? 'is-first' : ''}`);
        rg.append('line').attr('class', 'fl-rank-track').attr('x1', 0).attr('x2', (r) => x(r.n_methods));
        rg.each(function (r) { d3().select(this).selectAll('circle.t').data(d3().range(1, r.n_methods + 1)).join('circle').attr('class', 't fl-rank-tick').attr('cx', (k) => x(k)).attr('r', 2); });
        rg.append('circle').attr('class', 'fl-rank-dot').attr('cx', (r) => x(r.champion_rank)).attr('r', (r) => 4 + Math.min(4, Math.sqrt(r.n_parts || 1)));
        // Simple mode: the group (pattern + part type) leads, since method names are hidden there
        const PCS = { R: 'repairable', E: 'throw-away', C: 'consumable' };
        const DCS = { intermittent: 'now & then', lumpy: 'bursts', insufficient_data: 'little data', smooth: 'steady', erratic: 'uneven' };
        const rowLabel = (r) => (S ? `${small ? DCS[r.demand_class] || r.demand_class : dcName(r.demand_class)} · ${PCS[r.part_class] || r.part_class}` : `${mNameS(r.champion, small)} · ${small ? ({ intermittent: 'interm.', insufficient_data: 'insuff.' }[r.demand_class] || r.demand_class) : dcLabel(r.demand_class)} ${r.part_class}`);
        rg.append('text').attr('class', 'fl-mlabel').attr('x', -12).attr('dy', '0.32em').attr('text-anchor', 'end').text((r) => truncate(rowLabel(r), labelW - 14));
        rg.append('text').attr('class', 'fl-vlabel').attr('x', iw + 14).attr('dy', '0.32em').text((r) => (small ? `${r.champion_rank}/${r.n_methods}` : `${r.champion_rank}/${r.n_methods}${r.champion_rank > 1 ? ` · best: ${mName(r.best_in_hindsight)}` : ' · ★ held'}`));
        drawIn(MS, 'check', w, rg);
        withTooltip(rg, (r) => ({ title: S ? `${dcName(r.demand_class)} · ${pcName(r.part_class)}` : `${dcLabel(r.demand_class)} · ${r.part_class}`, rows: [[S ? 'Chosen in advance' : 'Champion', mName(r.champion)], [S ? 'Rank on fresh data' : 'Holdout rank', `${r.champion_rank} of ${r.n_methods}`], [S ? 'Its error score' : 'Champion MASE', fmtNum(r.champion_mase, 3)], [S ? 'Best on fresh data' : 'Best in hindsight', `${mName(r.best_in_hindsight)} ${fmtNum(r.best_mase, 3)}`], [S ? 'Parts' : 'PNs', fmtInt(r.n_parts)]] }));
        const wi = rows.indexOf(worst);
        annotate(g, { x: x(worst.champion_rank), y: wi * rowH + rowH / 2, dx: -48, dy: wi === rows.length - 1 ? 26 : -14, anchor: 'end', title: S ? `"${mName(worst.champion)}" did not hold up` : mKey(worst.champion) === 'naive' ? 'Naive: a MASE artefact on 0/1 series' : `${mName(worst.champion)} did not hold up`, sub: small ? undefined : S ? `${fmtInt(worst.n_parts)} parts in this group` : mKey(worst.champion) === 'naive' && worst.part_class === 'R' ? `${fmtInt(worst.n_parts)} PNs · rotable policies use the reliability rate` : `${fmtInt(worst.n_parts)} PNs in this cell` });
      }));
    }
  }

  // ================================================================== 4. LTD + stock evaluation
  el.append(sectionTitle(byMode('From forecast to spares on the shelf', 'From forecast to stock'), provChip(fprov)));
  const ltdCard = h('section', { class: 'card span-6 md-span-12' });
  const stockCard = h('section', { class: 'card span-6 md-span-12' });
  el.append(h('div', { class: 'grid-12' }, ltdCard, stockCard));

  // ---- LTD
  {
    const exs = (F.ltd_examples || (F.ltd_example ? [F.ltd_example] : [])).filter((L) => (L.dist || []).some((d) => Number.isFinite(d.p)));
    let li = Math.max(0, exs.findIndex((L) => L.pn === ctx.params.pn));
    if (li < 0) li = 0;
    const segHost = h('div', { class: 'fl-card-seg' });
    const frameHost = h('div');
    ltdCard.append(segHost, frameHost);
    let stop = null;
    const draw = () => {
      stop?.();
      frameHost.replaceChildren();
      const L = exs[li];
      if (!L) { chartFrame(frameHost, { headline: byMode('Demand during the wait: not run', 'Lead-time demand distribution: not run'), subtitle: byMode('chance of each demand level during the wait', 'pmf of demand over the lead time'), provenance: fprov, source: 'forecast.json' }).body.append(stateBlock('empty', 'not run')); return; }
      let cum = 0;
      const rows = L.dist.filter((d) => Number.isFinite(d.p)).map((d) => ({ ...d, cdf: (cum += d.p) }));
      const part = byPn.get(L.pn);
      const slA = part ? assumption(`service_targets.${part.deadline}`) : null;
      const sl = L.service_level ?? (slA ? +slA.value : null);
      const rop = L.reorder_point ?? (sl != null ? rows.find((r) => r.cdf >= sl - 1e-9)?.q ?? rows.at(-1).q : null);
      const mean = L.mean ?? rows.reduce((s2, r) => s2 + r.q * r.p, 0);
      const f = chartFrame(frameHost, {
      implication: byMode('Even at the target level, a small chance of running short remains. That is the planning risk.', 'Stocking to the service-level quantile still leaves a tail; that shortfall chance is the planning risk.'),
        // C8 (wave 4): this is the service-level QUANTILE; the plans position a cost-based number (note under the chart)
        headline: rop != null && S ? fitN(HALF, `Holding ${fmtInt(rop)} spare${rop === 1 ? '' : 's'}${L.station ? ` at ${L.station}` : ''} covers ${fmtPct(sl, 0)} of resupply waits`, `${fmtInt(rop)} spare${rop === 1 ? '' : 's'} cover ${fmtPct(sl, 0)} of resupply waits`)
          : rop != null ? fitN(HALF, `${L.pn}'s ${fmtPct(sl, 0)} service-level quantile${L.station ? ` at ${L.station}` : ''} is ${fmtInt(rop)} units`, `${L.pn}: ${fmtPct(sl, 0)} service-level quantile ${fmtInt(rop)} units`, `Covering ${fmtPct(sl, 0)} of lead times at ${L.station || 'the hub'} takes ${fmtInt(rop)} units of ${L.pn} (mean demand ${fmtNum(mean, 1)})`, `${fmtPct(sl, 0)} service-level quantile: ${fmtInt(rop)} units (mean demand ${fmtNum(mean, 1)})`) : `${L.pn}: expected lead-time demand ${fmtNum(mean, 1)} units`,
        subtitle: S
          ? 'Chance of needing each number of units during the wait for a resupply. The service target is an assumption.'
          : 'P(demand = q) over the resupply lead time · stocking to the service-level quantile (reorder point) · service target ASSUMED',
        provenance: L.provenance || fprov, source: 'forecast.json (ltd_examples), method.json (service_targets)', story: 'forecast-ltd',
        table: { columns: [{ key: 'q', label: 'Units', num: true }, { key: 'p', label: S ? 'Chance of exactly this' : 'P(X = q)', num: true, format: (v) => fmtPct(v, 1) }, { key: 'cdf', label: S ? 'Chance of this or fewer' : 'P(X ≤ q)', num: true, format: (v) => fmtPct(v, 1) }], rows },
      });
      f.body.before(h('p', { class: 'fl-key t-12 faint', dataset: { role: 'ltd-key' } }, S
        ? `${L.pn} · ${L.lead_time_days != null ? `${fmtNum(L.lead_time_days, 1)}-day resupply · ` : ''}rate from "${mName(L.rate_source || L.champion)}"${sl != null ? ` · target ${fmtPct(sl, 0)}` : ''}`
        : `${L.pn} · ${L.lead_time_days != null ? `${fmtNum(L.lead_time_days, 0)} days` : 'lead time'} · ${L.dist_kind || 'champion'} · rate from ${mName(L.rate_source || L.champion)}${sl != null ? ` · ${part?.deadline} target ${fmtPct(sl, 0)} (${slA?.provenance || 'ASSUMED'})` : ''}`));
      // C8 (wave 4): reconcile the quantile with what the plans actually position at this station
      const placed = L.station ? num(part?.stock_by_station?.[L.station]) : null;
      if (rop != null && placed != null && placed !== rop) {
        f.body.after(h('p', { class: 'fl-reconcile t-12 muted' }, icon('info'), S
          ? h('span', {}, `The target level calls for ${fmtInt(rop)}. The ${displayName('P2')}, our core plan, places ${fmtInt(placed)} at ${L.station}. ${placed < rop ? 'It stops short, because one more spare saves less grounded time than it costs to hold.' : 'It adds more, because the cost of a grounded plane pays for the extra spare.'} See the Capital Optimiser.`)
          : h('span', {}, `Service-level quantile ${fmtInt(rop)} vs positioned ${fmtInt(placed)}: `, nameTag('P2', { tag: 'always' }), `, the core plan, places ${fmtInt(placed)} at ${L.station}. Its cost-based allocation ${placed < rop ? `stops short of the quantile because the next unit's modelled AOG saving is worth less than its holding cost` : `goes past the quantile because the D0 penalty pays for the extra unit`} (see Capital Optimiser).`)));
      }
      stop = liveDraw(f.body, (w) => {
        const hgt = 260, m = { top: 30, right: 16, bottom: 34, left: 44 };
        const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
        const svg = svgIn(f.body, w, hgt, byMode('Chance of each demand level during the resupply wait', 'Lead-time demand distribution'));
        const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
        const qMax = Math.max((rop ?? 0) + 1, rows.find((x) => x.cdf >= 0.995)?.q ?? rows.at(-1).q);
        const shown = rows.filter((r) => r.q <= qMax);
        const x = d3().scaleBand().domain(shown.map((r) => r.q)).range([0, iw]).padding(0.22);
        const y = d3().scaleLinear().domain([0, d3().max(shown, (r) => r.p) * 1.12]).nice().range([ih, 0]);
        gridY(g.append('g'), y, iw, 4);
        axisLeft(g.append('g'), y, { ticks: 4, format: (v) => fmtPct(v, 0) });
        const xa = axisBottom(g.append('g'), x, { height: ih });
        const every = Math.ceil(shown.length / (w < 480 ? 8 : 14));
        xa.selectAll('.tick text').attr('opacity', (q, i) => (i % every ? 0 : 1));
        g.append('text').attr('class', 'pi-axis-t').attr('x', iw).attr('y', ih + 30).attr('text-anchor', 'end').text(byMode('units needed during the wait →', 'units demanded over the lead time →'));
        const bars = g.selectAll('rect.fl-bar').data(shown).join('rect').attr('class', (r) => (rop != null && r.q <= rop ? 'fl-bar is-covered' : 'fl-bar')).attr('rx', 2);
        // v2.1 motion: bars keyed by unit count; switching example part slides heights, no redraw from zero
        morph(MS, 'ltd', w, bars, (r) => r.q, { x: (r) => x(r.q), width: x.bandwidth(), y: (r) => y(r.p), height: (r) => ih - y(r.p) });
        withTooltip(bars, (r) => ({ title: `${fmtInt(r.q)} units`, rows: [[S ? 'Exactly this' : 'P(X = q)', fmtPct(r.p, 1)], [S ? 'This or fewer' : 'P(X ≤ q)', fmtPct(r.cdf, 1)]] }));
        if (rop != null && x(rop) != null) {
          const rx = x(rop) + x.bandwidth() + (x.step() * x.paddingInner()) / 2;
          const leftSide = rx > iw * 0.55;
          g.append('line').attr('class', 'fl-rop').attr('x1', rx).attr('x2', rx).attr('y1', -16).attr('y2', ih);
          const ropText = S ? `Hold ${fmtInt(rop)} · covers ${fmtPct(sl, 0)}` : `Reorder point ${fmtInt(rop)} · ${fmtPct(sl, 0)} quantile`;
          lab(g, { x: rx + (leftSide ? -6 : 6), y: -20, text: ropText, color: theme.color.text, anchor: leftSide ? 'end' : 'start', strong: true, dy: '0' });
          const tail = rows.filter((r) => r.q > rop).reduce((s2, r) => s2 + r.p, 0);
          if (shown.some((r) => r.q > rop)) {
            // shortfall label beside the reorder line, clear of every bar (dodge against bar rects, flips sides if needed)
            const barRects = shown.map((r) => ({ x: x(r.q) - 2, y: y(r.p) - 3, width: x.bandwidth() + 4, height: ih - y(r.p) + 3 }));
            const text = S ? `${fmtPct(tail, 1)} chance of running short` : `${fmtPct(tail, 1)} chance of a shortfall`;
            const l = { x: rx + (leftSide ? -8 : 8), flipX: rx + (leftSide ? 8 : -8), y: 10, text, anchor: leftSide ? 'end' : 'start' };
            dodge([l], { gap: 14, obstacles: barRects, bounds: { x: 0, y: 0, width: iw, height: ih - 4 }, flip: true, maxShift: ih - 20 });
            lab(g, { ...l, color: theme.color.text });
            if (w >= 480) lab(g, { x: l.x, y: l.y + 15, text: byMode('needs more than is held', 'demand beyond the reorder point'), color: theme.color.faint, anchor: l.anchor, mono: true });
          }
        }
      });
    };
    if (exs.length > 1) segHost.append(segmented({ label: 'Example part', value: String(li), options: exs.map((L, i) => ({ value: String(i), label: S ? L.pn : `${L.pn} · ${L.part_class || ''}` })), onChange: (v) => { li = +v; draw(); } }));
    draw();
    cleanups.push(() => stop?.());
  }

  // ---- stock-based evaluation
  {
    const SE = F.stock_eval || [];
    const pcs = ['R', 'E', 'C'].filter((x) => SE.some((r) => r.part_class === x));
    let spc = pcs.includes(ctx.params.part) ? ctx.params.part : pcs[0];
    const segHost = h('div', { class: 'fl-card-seg' });
    const frameHost = h('div');
    stockCard.append(frameHost);
    let stop = null;
    const draw = () => {
      stop?.();
      frameHost.replaceChildren();
      const rows = SE.filter((r) => (spc ? r.part_class === spc : true) && Number.isFinite(r.fill_rate)).map((r) => ({ ...r, capital: r.capital_aed ?? r.avg_stock_value_aed }));
      if (!rows.length) { chartFrame(frameHost, { headline: byMode('Spares test: not run', 'Stock-based evaluation: not run'), subtitle: byMode('shelf availability vs money in stock', 'fill rate vs capital'), provenance: fprov, source: 'forecast.json' }).body.append(stateBlock('empty', 'not run')); return; }
      const hi = rows.slice().sort((a, b) => b.fill_rate - a.fill_rate)[0];
      const cheap = rows.slice().sort((a, b) => a.capital - b.capital)[0];
      const rel = rows.find((r) => mKey(r.method) === 'reliability');
      const champSet = new Set(champs.filter((c) => !spc || c.part_class === spc).map((c) => mKey(champOf(c))));
      let named = null; // the method the headline names: it gets a direct label (wave 5)
      let headline = S ? fitN(HALF, `"${mName(hi.method)}" keeps parts on the shelf most, for ${fmtPct(hi.capital / cheap.capital - 1, 0)} more money`, `"${mNameS(hi.method, true)}": most on the shelf, ${fmtPct(hi.capital / cheap.capital - 1, 0)} more money`)
        : fitN(HALF, `${mName(hi.method)} buys the top fill rate (${fmtPct(hi.fill_rate)}) for ${fmtPct(hi.capital / cheap.capital - 1, 0)} more capital`, `${mNameS(hi.method, true)} buys the top fill rate for ${fmtPct(hi.capital / cheap.capital - 1, 0)} more capital`);
      if (rel && rel !== hi) {
        const peers = rows.filter((r) => r !== rel && r !== hi);
        const near = peers.sort((a, b) => Math.abs(a.capital - rel.capital) - Math.abs(b.capital - rel.capital))[0];
        if (near && rel.fill_rate > near.fill_rate) named = near;
        if (near && rel.fill_rate > near.fill_rate) headline = S ? fitN(HALF, `Flying-hours rate: ${fmtPts(rel.fill_rate - near.fill_rate).replace(/\s*pts?$/, ' points')} more on the shelf, ${fmtPct(rel.capital / near.capital - 1, 0)} more money`, `Flying-hours rate: ${fmtPts(rel.fill_rate - near.fill_rate).replace(/\s*pts?$/, ' points')} more on the shelf`)
          : fitN(HALF, `Reliability-exposure adds ${fmtPts(rel.fill_rate - near.fill_rate)} of fill over ${mName(near.method)} for ${fmtPct(rel.capital / near.capital - 1, 0)} more capital`, `Reliability adds ${fmtPts(rel.fill_rate - near.fill_rate)} of fill over ${mName(near.method)} for ${fmtPct(rel.capital / near.capital - 1, 0)} more capital`, `Reliability adds ${fmtPts(rel.fill_rate - near.fill_rate)} of fill over ${mNameS(near.method, true)}`);
      }
      const f = chartFrame(frameHost, {
      implication: byMode('Judge a forecast by the spares and money it leads to, not by its error score.', 'Judge forecasts by the fill and capital they produce, not by error scores.'),
        headline,
        subtitle: S
          ? 'Chance the part is on the shelf vs average money in stock, per method. Each part is stocked to its service target. Simple one-part test over the tuning weeks.'
          : 'Fill rate vs mean stock value per method · base stock at the deadline-class service target · single-item stand-in simulator over the selection weeks',
        provenance: fprov, source: 'forecast.json (stock_eval) · unlabelled points: other methods (hover or View data)', story: 'forecast-stock-eval',
        table: { columns: [{ key: 'method', label: 'Method', format: mName }, { key: 'fill_rate', label: termText('fill_rate', { cap: true }), num: true, format: (v) => fmtPct(v) }, { key: 'capital', label: S ? 'Money in stock' : 'Capital', num: true, format: (v) => fmtAED(v) }, { key: 'backorder_units', label: S ? 'Units waited for' : 'Backorder units', num: true, format: fmtInt }], rows },
      });
      if (spc) f.body.before(h('p', { class: 'fl-key t-12 faint', dataset: { role: 'stock-key' } }, cap1(pcName(spc))));
      stop = liveDraw(f.body, (w) => {
        const small = w < 480;
        const hgt = small ? 300 : 320, m = { top: 16, right: small ? 20 : 96, bottom: 36, left: 52 };
        const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
        const svg = svgIn(f.body, w, hgt, byMode('Shelf availability versus money in stock', 'Fill rate versus capital'));
        const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
        // teal only for the rate the rotable policies use; other key methods are labelled in neutral
        const polM = spc === 'R' && /reliability rate/i.test(F.meta?.notes || '') ? 'reliability' : null;
        // wave 5: fit x to the cluster; a far outlier (e.g. bootstrap at ~1.5× the next capital) is pinned to the right edge
        // with its true value in the label, instead of squeezing every other method into 15% of the plot
        const caps = rows.map((r) => r.capital).sort((a, b) => a - b);
        const cut = caps.length > 3 && caps.at(-1) > caps.at(-2) * 1.3 ? caps.at(-2) : Infinity;
        const inRows = rows.filter((r) => r.capital <= cut);
        const xe = d3().extent(inRows, (r) => r.capital), ye = d3().extent(rows, (r) => r.fill_rate);
        const xp = (xe[1] - xe[0]) * 0.12 || xe[0] * 0.1, yp = (ye[1] - ye[0]) * 0.15 || 0.01;
        const x0 = d3().scaleLinear().domain([xe[0] - xp, xe[1] + xp]).range([0, cut === Infinity ? iw : iw - 28]);
        const x = Object.assign((v) => (v > cut ? iw - 6 : x0(v)), { ticks: (n) => x0.ticks(n), domain: () => x0.domain(), range: () => [0, iw], copy: () => x0.copy(), tickFormat: (...a) => x0.tickFormat(...a), bandwidth: undefined });
        const y = d3().scaleLinear().domain([Math.max(0, ye[0] - yp), Math.min(1, ye[1] + yp)]).nice().range([ih, 0]);
        gridY(g.append('g'), y, iw, 4);
        axisLeft(g.append('g'), y, { ticks: 4, format: (v) => fmtPct(v, 0) });
        const axB = g.append('g');
        axisBottom(axB, x0, { height: ih, ticks: small ? 3 : 5, format: (v) => fmtAED(v) });
        // wave C (F6): drop a tick label that would sit under the "off-scale" note
        if (cut !== Infinity) axB.selectAll('.tick').filter((t) => x0(t) > iw - 80).remove();
        if (cut !== Infinity) g.append('text').attr('class', 'pi-axis-t').attr('x', iw).attr('y', ih + 18).attr('text-anchor', 'end').text('⋯ off-scale');
        g.append('text').attr('class', 'pi-axis-t').attr('x', iw).attr('y', ih + 32).attr('text-anchor', 'end').text(byMode('money in stock →', 'capital (mean stock value) →'));
        g.append('text').attr('class', 'pi-axis-t').attr('x', 0).attr('y', -4).text(byMode('on the shelf ↑', 'fill rate ↑'));
        const pts = g.selectAll('g.p').data(rows).join('g').attr('class', (r) => `fl-pt ${mKey(r.method) === polM ? 'is-key' : r === hi || mKey(r.method) === 'reliability' ? 'is-ref' : ''} ${champSet.has(mKey(r.method)) ? 'is-champ' : ''}`);
        // v2.1 motion: points keyed by method glide to the new part class's values
        morph(MS, 'stock', w, pts, (r) => mKey(r.method), { transform: (r) => `translate(${x(r.capital)},${y(r.fill_rate)})` });
        pts.append('circle').attr('r', (r) => (mKey(r.method) === 'reliability' ? 6 : 4.5));
        withTooltip(pts, (r) => ({ title: mName(r.method), rows: [[termText('fill_rate', { cap: true }), fmtPct(r.fill_rate)], [S ? 'Money in stock' : 'Capital', fmtAED(r.capital)], [S ? 'Units waited for' : 'Backorder units', fmtInt(r.backorder_units)]], note: champSet.has(mKey(r.method)) ? byMode('Chosen in advance for at least one group of these parts', 'MASE champion in at least one cell of this class') : '' }));
        // direct labels for the key methods: dodged against every dot and each other, flipping sides when needed
        const keyM = small ? [...new Set([rel, named, hi].filter(Boolean))] : [...new Set([rel, named, hi, cheap].filter(Boolean))];
        const obstacles = rows.map((r) => markerRect(x(r.capital), y(r.fill_rate), mKey(r.method) === 'reliability' ? 6 : 4.5, 3));
        const labels = keyM.map((r) => {
          const cx = x(r.capital), cy = y(r.fill_rate);
          const off = r.capital > cut ? ` · ${fmtAED(r.capital)} (off-scale)` : '';
          const W = S ? { top: ' · most on shelf', hi: 'most on shelf', least: 'least money', pol: ' · used by plans' } : { top: ' · top fill', hi: 'highest fill', least: 'least capital', pol: ' · policy rate' };
          const text = small ? `${mNameS(r.method, true)}${r === hi && r !== rel ? W.top : ''}${r.capital > cut ? ' ▸' : ''}` : r === hi && r !== rel ? `${mName(r.method)} · ${W.hi}${off}` : r === named ? `${mName(r.method)} · ${fmtPct(r.fill_rate, 0)}` : r === cheap && r !== rel && r !== hi ? `${mName(r.method)} · ${W.least}` : `${mName(r.method)}${mKey(r.method) === polM ? W.pol : ''}`;
          const right = cx < iw * 0.6;
          return { r, text, x: cx + (right ? 10 : -10), flipX: cx + (right ? -10 : 10), y: cy, anchor: right ? 'start' : 'end' };
        });
        dodge(labels, { gap: 14, obstacles, bounds: { x: -m.left + 4, y: 0, width: iw + m.left + m.right - 8, height: ih }, flip: true, maxShift: 48 });
        labels.forEach((l) => {
          const cx = x(l.r.capital), cy = y(l.r.fill_rate);
          if (Math.abs(l.y - cy) > 10) g.append('line').attr('class', 'fl-leader').attr('x1', cx).attr('y1', cy).attr('x2', l.anchor === 'start' ? l.x - 3 : l.x + 3).attr('y2', l.y);
          lab(g, { x: l.x, y: l.y, text: l.text, anchor: l.anchor, color: mKey(l.r.method) === polM ? theme.series.recommended : theme.color.text, strong: mKey(l.r.method) === polM });
        });
      });
    };
    if (pcs.length > 1) {
      segHost.append(segmented({ label: 'Part class', value: spc, options: pcs.map((x) => ({ value: x, label: PC_BTN()[x] })), onChange: (v) => { spc = v; draw(); } }));
      stockCard.prepend(segHost);
    }
    draw();
    cleanups.push(() => stop?.());
  }

  // ================================================================== 5. Monash + truth recovery
  el.append(sectionTitle(byMode('Checks outside the simulation', 'Validation outside the simulator')));
  const monCard = h('section', { class: 'card span-7 md-span-12 fl-monash', dataset: { story: 'forecast-monash' } });
  const truthCard = h('section', { class: 'card span-5 md-span-12' });
  el.append(h('div', { class: 'grid-12' }, monCard, truthCard));

  // ---- Monash
  {
    const Mo = F.monash || {};
    const res = (Mo.results || []).filter((r) => Number.isFinite(r.mase));
    const chips = h('div', { class: 'row-wrap gap-1 fl-monash-chips' }, h('span', { class: 'fl-chip-l' }, 'Data'), provChip(Mo.data_provenance || 'REAL'), h('span', { class: 'fl-chip-l' }, 'Metrics'), provChip(Mo.provenance || 'DERIVED'));
    if (Mo.status !== 'ok' || !res.length) {
      monCard.append(h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, byMode('Real-world check · car-parts data', 'External benchmark · Monash Car Parts')), h('h3', { class: 'card-title' }, byMode('Real-data check: not run', 'Monash benchmark: not run'))), chips), pill('unknown', 'not run'), h('p', { class: 'faint t-12 mt-1' }, Mo.reason || 'The benchmark file was not exported.'));
    } else {
      const eligible = res.filter((r) => !isZero(r.method)).sort((a, b) => a.mase - b.mase);
      const zero = res.find((r) => isZero(r.method));
      const best = eligible[0];
      const info = Mo.info || {};
      const setup = Mo.setup || {};
      monCard.append(chips);
      const f = chartFrame(monCard, {
      implication: byMode('Testing on real public data checks that the ranking is not just a quirk of our simulation.', 'On public data the same methods rank similarly, so the simulated ranking is not an artefact of the simulator.'),
        headline: S ? fit(`On ${fmtInt(info.n_series)} real car-parts demand series, "${mName(best.method)}" predicted best`, `"${mName(best.method)}" predicted best on real car-parts data`) : fit(`On ${fmtInt(info.n_series)} real car-parts series, ${mName(best.method)} is the best eligible method (MASE ${fmtNum(best.mase)})`, `${mName(best.method)} is the best eligible method on real car-parts data (MASE ${fmtNum(best.mase)})`),
        subtitle: S
          ? `Forecast error compared with a simple guess, with likely range. ${(setup.frequency || 'monthly').replace(/^./, (c) => c.toUpperCase())} data, last ${setup.horizon ?? '—'} ${setup.frequency === 'monthly' ? 'months' : 'periods'} held back. ${fmtInt(info.n_mase_undefined)} series with no usable history left out.`
          : `MASE (m = ${setup.mase_seasonality ?? 1}) · mean and 95% CI over series · ${setup.frequency || 'monthly'}, last ${setup.horizon ?? '—'} ${setup.frequency === 'monthly' ? 'months' : 'periods'} held out · ${fmtInt(info.n_mase_undefined)} series with zero training scale excluded`,
        provenance: 'DERIVED', source: `${Mo.dataset || 'Monash Car Parts'} · Zenodo v${Mo.zenodo_version ?? '—'} · downloaded ${Mo.download_date || '—'}`,
        table: { columns: [{ key: 'method', label: 'Method', format: mName }, { key: 'mase', label: S ? 'Error score' : 'MASE', num: true, format: (v) => fmtNum(v, 3) }, { key: 'mase_ci_lo', label: S ? 'Range low' : 'CI low', num: true, format: (v) => fmtNum(v, 3) }, { key: 'mase_ci_hi', label: S ? 'Range high' : 'CI high', num: true, format: (v) => fmtNum(v, 3) }, { key: 'cov_q90', label: S ? '90% range caught it' : 'Coverage q90', num: true, format: (v) => fmtPct(v, 1) }], rows: res },
      });
      const ordered = eligible.concat(zero ? [zero] : []);
      cleanups.push(responsive(f.body, (w) => {
        const small = w < 480;
        const rowH = 26, labelW = small ? 96 : 160;
        const m = { top: 8, right: small ? 44 : 60, bottom: 28, left: labelW };
        const hgt = m.top + m.bottom + ordered.length * rowH + (zero ? 8 : 0);
        const iw = Math.max(60, w - m.left - m.right), ih = hgt - m.top - m.bottom;
        const svg = svgIn(f.body, w, hgt, byMode('Real car-parts data: forecast error by method', 'Monash Car Parts MASE by method'));
        const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
        const x = d3().scaleLinear().domain([Math.max(0, d3().min(ordered, (r) => r.mase_ci_lo ?? r.mase) * 0.9), d3().max(ordered, (r) => r.mase_ci_hi ?? r.mase) * 1.03]).nice().range([0, iw]);
        const yPos = (i) => i * rowH + rowH / 2 + (zero && i === ordered.length - 1 ? 8 : 0);
        axisBottom(g.append('g'), x, { height: ih, ticks: small ? 3 : 5, format: (v) => fmtNum(v, 1) });
        if (x.domain()[0] <= 1 && x.domain()[1] >= 1) refLine(g, { x1: x(1), y1: 0, x2: x(1), y2: ih });
        const rg = g.selectAll('g.fl-row').data(ordered).join('g').attr('class', (r) => `fl-row ${r === best ? 'is-champ' : ''} ${isZero(r.method) ? 'is-zero' : ''}`).attr('transform', (r, i) => `translate(0,${yPos(i)})`);
        drawIn(MS, 'monash', w, rg);
        rg.append('line').attr('class', 'fl-ci').attr('x1', (r) => x(r.mase_ci_lo ?? r.mase)).attr('x2', (r) => x(r.mase_ci_hi ?? r.mase));
        rg.append('circle').attr('class', 'fl-dot').attr('cx', (r) => x(r.mase)).attr('r', (r) => (r === best ? 5.5 : 4));
        rg.append('text').attr('class', 'fl-mlabel').attr('x', -10).attr('dy', '0.32em').attr('text-anchor', 'end').text((r) => truncate(isZero(r.method) ? (small ? 'Zero (excl.)' : byMode('Always zero · yardstick', 'Zero · not eligible')) : mNameS(r.method, small), labelW - 14));
        rg.append('text').attr('class', 'fl-vlabel').attr('x', iw + 8).attr('dy', '0.32em').text((r) => fmtNum(r.mase));
        withTooltip(rg, (r) => ({ title: mName(r.method), rows: [[S ? 'Error score' : 'MASE', fmtNum(r.mase, 3)], [termText('ci', { cap: true }), `${fmtNum(r.mase_ci_lo, 3)} – ${fmtNum(r.mase_ci_hi, 3)}`], [S ? 'Middle score' : 'Median MASE', fmtNum(r.mase_median, 3)], [S ? '90% range caught it' : 'Coverage q90', fmtPct(r.cov_q90, 1)]] }));
        if (best && !small) annotate(g, { x: x(best.mase), y: yPos(0), dx: 28, dy: 4, title: byMode('Best', 'Best eligible') });
      }));
      const mix = info.class_mix ? Object.entries(info.class_mix).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${dcName(k)} ${fmtInt(v)}`).join(' · ') : null;
      const pub = Mo.published_reference;
      monCard.append(h('div', { class: 'fl-monash-foot' },
        mix ? h('p', {}, h('span', { class: 'fl-chip-l' }, byMode('Demand patterns', 'ADI/CV² mix')), ' ', mix) : null,
        pub?.values && !S ? h('p', { class: 'faint' }, `Published archive results, for context only (${pub.note || 'scaling not stated'}): `, Object.entries(pub.values).slice(0, 6).map(([k, v]) => `${k} ${fmtNum(v, 3)}`).join(' · '), '. ') : null,
        h('p', { class: 'fl-attrib', dataset: { readability: 'skip' } }, icon('book'), h('span', {}, Mo.attribution || 'Monash Time Series Forecasting Archive, Car Parts dataset.', ' Licence ', h('strong', {}, Mo.licence || 'CC BY 4.0'), '. ', Mo.source_url ? h('a', { href: Mo.source_url, target: '_blank', rel: 'noopener' }, 'Zenodo record') : null))));
    }
  }

  // ---- truth recovery
  {
    const TR = (F.truth_recovery || []).filter((t) => Number.isFinite(t.estimated));
    const isLog = (t) => /log/i.test(t.metric || '');
    // Simple mode: a median |log error| of 0.07 reads "7% off" (close to the relative error at this size)
    const fmtE = (t, v) => (v == null ? 'not quoted' : S && isLog(t) ? offPct(v) : isLog(t) ? fmtNum(v, 2) : fmtPct(v, 0));
    const SP = (t) => (S ? String(t).replace(/^MTBUR/, 'Removal rate').replace(' (rotables + expendables)', ', all').replace('rotables', 'repairable').replace('expendables', 'throw-away').replace('Purchase lead time (all PNs)', 'Supplier delivery time (all parts)') : String(t));
    if (!TR.length) {
      chartFrame(truthCard, { headline: byMode('Check against the truth: not run', 'Truth recovery: not run'), subtitle: byMode('our estimates vs supplier quotes', 'estimated vs vendor-quoted parameter error'), provenance: 'DERIVED', source: 'forecast.json' }).body.append(stateBlock('empty', 'not run'));
    } else {
      const main = TR.find((t) => t.vendor_quoted != null && /mtbur/i.test(t.param)) || TR.find((t) => t.vendor_quoted != null) || TR[0];
      const f = chartFrame(truthCard, {
      implication: byMode('Our own removal history beats supplier quotes. Update planning numbers from it.', 'History-based reliability beats vendor quotes: update planning parameters from your own removals.'),
        headline: S && main.vendor_quoted != null ? fitN(HALF, `Our history: ${fmtE(main, main.estimated)} off the truth; supplier quotes: ${fmtE(main, main.vendor_quoted)} off`, `Our history: ${fmtE(main, main.estimated)} off; supplier quotes: ${fmtE(main, main.vendor_quoted)} off`)
          : main.vendor_quoted != null ? fitN(HALF, `Fitting ${String(main.param).split(' (')[0]} to removals cuts its error from ${fmtE(main, main.vendor_quoted)} to ${fmtE(main, main.estimated)}`, `Estimating ${main.param} from removals cuts the error from ${fmtE(main, main.vendor_quoted)} (vendor-quoted) to ${fmtE(main, main.estimated)}`, `Fitting ${main.param} to removals cuts its error from ${fmtE(main, main.vendor_quoted)} to ${fmtE(main, main.estimated)}`, `Fitting ${String(main.param).split(' (')[0]} to removals cuts its error from ${fmtE(main, main.vendor_quoted)} to ${fmtE(main, main.estimated)}`) : `${main.param}: estimate error ${fmtE(main, main.estimated)}`,
        subtitle: S
          ? 'Typical gap from the hidden true value, for our estimate and the supplier quote. Lower is better. Estimates use past weeks only.'
          : `${main.metric || 'error'} against the simulator's hidden truth, estimated vs vendor-quoted · lower is better · estimates use history weeks only`,
        provenance: 'DERIVED', source: 'forecast.json (truth_recovery)', story: 'forecast-truth',
        table: { columns: [{ key: 'param', label: S ? 'What was estimated' : 'Parameter', format: SP }, { key: 'metric', label: 'Metric' }, { key: 'vendor_quoted', label: S ? 'Supplier quote' : 'Vendor-quoted', num: true, format: (v) => (v == null ? 'not quoted' : fmtNum(v, 3)) }, { key: 'estimated', label: S ? 'Our estimate' : 'Estimated', num: true, format: (v) => fmtNum(v, 3) }, { key: 'n_parts', label: S ? 'Parts' : 'PNs', num: true, format: (v) => (v == null ? '—' : fmtInt(v)) }], rows: TR },
      });
      cleanups.push(responsive(f.body, (w) => {
        const rowH = 52, labelW = Math.min(170, w * 0.38);
        const m = { top: 18, right: 20, bottom: 26, left: labelW };
        const hgt = m.top + m.bottom + TR.length * rowH;
        const iw = Math.max(60, w - m.left - m.right), ih = hgt - m.top - m.bottom;
        const svg = svgIn(f.body, w, hgt, byMode('Our estimates versus supplier quotes: gap from the truth', 'Estimated versus vendor-quoted error'));
        const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
        const max = d3().max(TR, (t) => Math.max(t.estimated, t.vendor_quoted ?? 0)) * 1.15;
        const x = d3().scaleLinear().domain([0, max]).nice().range([0, iw]);
        axisBottom(g.append('g'), x, { height: ih, ticks: 4, format: (v) => (isLog(main) ? fmtNum(v, x.domain()[1] < 0.5 ? 2 : 1) : fmtPct(v, 0)) }); // wave C (F5): no duplicate ticks on a narrow domain
        const rg = g.selectAll('g.fl-tr').data(TR).join('g').attr('class', 'fl-tr').attr('transform', (t, i) => `translate(0,${i * rowH + rowH / 2})`);
        rg.append('text').attr('class', 'fl-mlabel').attr('x', -10).attr('dy', '0.32em').attr('text-anchor', 'end').each(function (t) {
          const words = SP(t.param).split(' ');
          const lines = []; let cur = '';
          words.forEach((wd) => { if ((cur + ' ' + wd).trim().length * 6.6 > labelW - 14 && cur) { lines.push(cur); cur = wd; } else cur = `${cur} ${wd}`.trim(); });
          lines.push(cur);
          lines.slice(0, 2).forEach((ln, j) => d3().select(this).append('tspan').attr('x', -10).attr('dy', j ? '1.2em' : lines.length > 1 ? '-0.3em' : '0.32em').text(ln));
        });
        rg.filter((t) => t.vendor_quoted != null).append('line').attr('class', 'fl-db').attr('x1', (t) => x(t.estimated)).attr('x2', (t) => x(t.vendor_quoted));
        rg.filter((t) => t.vendor_quoted != null).append('circle').attr('class', 'fl-db-q').attr('cx', (t) => x(t.vendor_quoted)).attr('r', 5);
        rg.append('circle').attr('class', 'fl-db-e').attr('cx', (t) => x(t.estimated)).attr('r', 5.5);
        drawIn(MS, 'truth', w, rg);
        rg.append('text').attr('class', 'fl-db-t is-e').attr('x', (t) => x(t.estimated)).attr('y', 19).attr('text-anchor', 'middle').text((t) => fmtE(t, t.estimated));
        rg.filter((t) => t.vendor_quoted != null).append('text').attr('class', 'fl-db-t is-q').attr('x', (t) => x(t.vendor_quoted)).attr('y', -11).attr('text-anchor', 'middle').text((t) => fmtE(t, t.vendor_quoted));
        rg.filter((t) => t.vendor_quoted == null).append('text').attr('class', 'fl-db-t').attr('x', (t) => x(t.estimated) + 10).attr('dy', '0.32em').text(byMode('no supplier quote', 'no vendor quote'));
        withTooltip(rg, (t) => ({ title: SP(t.param), rows: [[S ? 'Supplier quote: off by' : 'Vendor-quoted error', fmtE(t, t.vendor_quoted)], [S ? 'Our estimate: off by' : 'Estimated error', fmtE(t, t.estimated)], ...(t.n_parts != null ? [[S ? 'Parts' : 'PNs', fmtInt(t.n_parts)]] : []), ...(t.share_estimate_closer != null ? [[S ? 'Ours closer for' : 'Estimate closer', fmtPct(t.share_estimate_closer, 0)]] : [])] }));
        lab(g, { x: 0, y: -8, text: byMode('● our history', '● estimated'), dy: '0', color: theme.color.accent });
        lab(g, { x: S ? 100 : 86, y: -8, text: byMode('○ supplier quote', '○ vendor-quoted'), dy: '0', color: theme.color.muted });
      }));
      truthCard.append(h('div', { class: 'fl-honest mt-2', role: 'note' }, icon('shield'), S
        ? h('div', {}, h('strong', {}, 'Checked against the hidden truth'), h('p', {}, 'The simulation sets true failure and repair rates that the planner never sees. Our estimates use only past removals and repairs. Only this scoring step reads the true values. The forecasting and stocking code never does.'))
        : h('div', {}, h('strong', {}, 'Evaluated against hidden truth'), h('p', {}, 'The simulator draws true reliability and repair parameters that the planner never sees. Estimates are fitted on the demand and repair history only; the true values are read by this evaluation step alone, never by the forecasting or policy code.'))));
    }
  }

  return () => cleanups.forEach((c) => c?.());
}
