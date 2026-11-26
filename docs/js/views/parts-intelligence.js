/**
 * 02 · Parts Intelligence: Aircraft System Explorer.
 * Data: parts.json, demand_history.json
 * Deep links: #/parts?ata=32 · #/parts?pn=GN-32-R014 · #/parts?ata=all&cls=R
 *
 * Shows: plan-view blueprint aircraft with risk-coloured ATA hotspots (+ accessible list), exploded view of the
 * selected system with fictional PNs injected, ADI/CV² demand matrix (training weeks only), dense parts table,
 * ABC × demand-class heatmap, and a part drill-down drawer with the sparse weekly demand strip.
 * Every number on screen comes from the JSON exports.
 */
import { h, icon, pageHead, card, provChip, pill, segmented, dataTable, drawer, inlineSVG, fillExploded, blueprintAircraft, intro3, scopeLine } from '../ui.js';
import { chartFrame, responsive, svgIn, axisBottom, axisLeft, styleAxis, theme, annotate, withTooltip, directLabel, refLine, markerRect, labelBox, fmtAED, fmtHours, fmtInt, fmtNum, fmtPct, fmtWeek } from '../charts/theme.js';
import { assetURL } from '../data.js';
import { isSimple, byMode } from '../lib/mode.js';
import { term } from '../lib/glossary.js';
import { displayName, nameTag } from '../lib/names.js';
import { demandStrip, demandStats } from './parts-intelligence/strip.js';
import { drawIn, tweenNumber } from './parts-intelligence/motion-helpers.js';
import { chartTransition, throttleRAF, tx as txSel } from '../lib/motion.js';
import { escalationBlock, allocationFlagNote, flagsAt } from './parts-intelligence/flags.js';

/** directLabel whose colour survives the .gnm-label CSS fill. */
const lab = (g, o) => { const t = directLabel(g, o); if (o.color) t.style('fill', o.color); return t; };

export const data = ['parts', 'demand_history'];

const ATAS = ['21', '24', '27', '29', '32', '34', '36', '49'];
const ADI_CUT = 1.32;
const CV2_CUT = 0.49;
const DC_ORDER = ['smooth', 'erratic', 'intermittent', 'lumpy', 'insufficient_data'];
const LEVEL = {
  urgent: { glyph: '▲', text: 'Urgent', rank: 3 },
  review: { glyph: '◆', text: 'Review', rank: 2 },
  ok: { glyph: '●', text: 'OK', rank: 1 },
  unknown: { glyph: '○', text: 'No data', rank: 0 },
};
const CLS_EXPERT = { R: 'Rotable', E: 'Expendable', C: 'Consumable' };
const CLS_SIMPLE = { R: 'Repairable', E: 'Thrown away', C: 'Used once' };
/** v2.1: class names follow the reading mode (Simple: plain words). */
const CLS_NAME = new Proxy({}, { get: (_, k) => (isSimple() ? CLS_SIMPLE : CLS_EXPERT)[k] });
export const dcLabel = (c) => String(c || 'unclassified').replace('_', ' ');
/** Plain-English demand class (same words as the Forecast Lab's Simple mode). */
const DC_SIMPLE = { smooth: 'steady', erratic: 'uneven', intermittent: 'now and then', lumpy: 'now and then, in bursts', insufficient_data: 'too little history' };
const DC_SHORT = { smooth: 'STEADY', erratic: 'UNEVEN', intermittent: 'NOW AND THEN', lumpy: 'IN BURSTS', insufficient_data: 'TOO LITTLE DATA' };
const dcName = (c) => (isSimple() ? DC_SIMPLE[c] || dcLabel(c) : dcLabel(c));
/** Plain-English rectification window. */
const WINDOW_SIMPLE = { D0: 'next flight', D3: '3 days', D10: '10 days', NONE: 'none' };
const riskPct = (v) => (v == null ? '—' : String(Math.round(v * 100)));
const SVG_NS = 'http://www.w3.org/2000/svg';
/** createElementNS + attributes (+ append to parent). */
const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(SVG_NS, tag); Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); parent?.append(e); return e; };

/** Inject a view stylesheet once; resolves when it has loaded (avoids measuring unstyled charts). */
export function ensureCSS(path) {
  const existing = document.querySelector(`link[data-view-css="${path}"]`);
  if (existing) return existing._ready || Promise.resolve();
  const link = h('link', { rel: 'stylesheet', href: assetURL(path), dataset: { viewCss: path } });
  link._ready = new Promise((res) => { link.onload = res; link.onerror = res; });
  document.head.append(link);
  return link._ready;
}

export async function render(el, ctx) {
  await ensureCSS('css/views/parts-intelligence.css');
  const { parts: P, demand_history: DH } = ctx.data;
  const parts = P.parts || [];
  const byPn = new Map(parts.map((p) => [p.pn, p]));
  const sysName = (a) => (P.ata_systems || []).find((s) => s.ata === a)?.name || `ATA ${a}`;
  const prov = P.meta?.provenance || 'SIMULATED';
  const weeks = DH.weeks || [0, 103];
  const selStart = DH.split_week ?? (DH.meta?.train_weeks?.[1] ?? 77) + 1;
  const trainEnd = selStart - 1;

  // per-system roll-up. Level = exported relative system risk (chapter share of fleet risk-hours), else worst PN
  const sysRisk = new Map((P.ata_systems || []).map((s) => [s.ata, s]));
  // wave B: fleet filter from the v2 applicability table (parts.json applicability: NB / WB / both)
  let fleet = ['NB', 'WB', 'all'].includes(ctx.params.fleet) ? ctx.params.fleet : 'all';
  const inFleet = (p) => fleet === 'all' || !p.applicability || p.applicability === 'both' || p.applicability === fleet;
  const FLEET_LABEL = { NB: 'Narrowbody', WB: 'Widebody', all: 'All fleet' };
  const BANDS = P.system_risk_bands_share || { urgent: 0.15, review: 0.07 };
  /** wave C: per-system roll-up recomputed from the FILTERED part set (counts, urgent PNs, share, band, top PN). */
  const computeSysStat = () => (fleet === 'all' ? exportedSysStat() : Object.fromEntries(ATAS.map((a) => {
    const fp = parts.filter(inFleet), ps = fp.filter((p) => p.ata === a);
    const tot = fp.reduce((x, p) => x + (+p.risk_hours || 0), 0);
    const share = tot ? ps.reduce((x, p) => x + (+p.risk_hours || 0), 0) / tot : 0;
    const urgent = ps.filter((p) => p.risk_level === 'urgent').length;
    const level = !ps.length ? 'unknown' : share >= BANDS.urgent ? 'urgent' : share >= BANDS.review ? 'review' : 'ok';
    const tone = level === 'ok' && urgent ? 'review' : level;
    const word = level === 'urgent' ? 'URGENT' : level === 'review' ? 'REVIEW' : level === 'ok' ? (urgent ? 'WATCH' : 'OK') : null;
    const top = ps.slice().sort((x, y) => y.risk_score - x.risk_score)[0];
    return [a, { ata: a, name: sysName(a), n: ps.length, urgent, review: ps.filter((p) => p.risk_level === 'review').length, level, tone, word, share, top, max: top?.risk_score }];
  })));
  const exportedSysStat = () => Object.fromEntries(ATAS.map((a) => {
    const ps = parts.filter((p) => p.ata === a);
    const lvl = ps.reduce((m, p) => ((LEVEL[p.risk_level]?.rank || 0) > (LEVEL[m]?.rank || 0) ? p.risk_level : m), 'unknown');
    const top = ps.slice().sort((x, y) => y.risk_score - x.risk_score)[0];
    return [a, { ata: a, name: sysName(a), n: ps.length, urgent: ps.filter((p) => p.risk_level === 'urgent').length, review: ps.filter((p) => p.risk_level === 'review').length, level: sysRisk.get(a)?.system_level || sysRisk.get(a)?.risk_level || (ps.length ? lvl : 'unknown'),
      // display status (exporter): the system level, raised to WATCH when an OK chapter holds an urgent part
      tone: sysRisk.get(a)?.status || sysRisk.get(a)?.system_level || sysRisk.get(a)?.risk_level || (ps.length ? lvl : 'unknown'),
      word: String(sysRisk.get(a)?.status_label || '').split(' · ')[0] || null, share: sysRisk.get(a)?.risk_share, top, max: top?.risk_score }];
  }));
  let sysStat = computeSysStat();
  const topSystem = () => ATAS.filter((a) => sysStat[a].n).sort((a, b) => (sysStat[b].max || 0) - (sysStat[a].max || 0))[0];

  let ata = ctx.params.ata === 'all' ? 'all' : ATAS.includes(ctx.params.ata) ? ctx.params.ata : null;
  const pnParam = byPn.get(ctx.params.pn);
  if (!ata) ata = pnParam && ATAS.includes(pnParam.ata) ? pnParam.ata : topSystem();
  let cls = ['C', 'E', 'R'].includes(ctx.params.cls) ? ctx.params.cls : 'all';
  let query = '';

  // ------------------------------------------------------------------ header
  const nUrgent = parts.filter((p) => p.risk_level === 'urgent').length;
  const nIntermittent = parts.filter((p) => ['intermittent', 'lumpy'].includes(p.demand_class)).length;
  const S = isSimple();
  const PN = (n) => (S ? `part${n === 1 ? '' : 's'}` : `PN${n === 1 ? '' : 's'}`);
  const planName = displayName(P.stock_basis_id || 'P2', { mode: 'short' });
  el.append(pageHead({
    num: '02', eyebrow: 'Parts Intelligence', title: byMode('Which parts could leave a plane waiting on the ground', 'Where material shortage exposure sits on the aircraft'),
    lede: S
      ? h('span', {}, `${fmtInt(parts.length)} made-up parts for a fictional airline, grouped by `, term('ata'), `. ${fmtInt(nIntermittent)} are `, term('intermittent'), `. ${fmtInt(nUrgent)} are urgent risks. Pick a system on the aircraft or in the list.`)
      : `${fmtInt(parts.length)} fictional part numbers for Falcon Hub Airways (fictional), mapped to their ATA chapter. ${fmtInt(nIntermittent)} have intermittent or lumpy demand and ${fmtInt(nUrgent)} carry urgent material shortage exposure. Select a system on the aircraft or in the list.`,
    meta: [provChip(prov), h('span', { class: 'chip' }, `${fmtInt(parts.length)} ${PN(parts.length)}`), h('span', { class: 'chip' }, `${(P.ata_systems || []).length} ${byMode('aircraft systems', 'ATA chapters')}`)],
  }));
  el.append(intro3({
    what: ['Which aircraft systems and parts are most likely to leave a plane waiting for a spare.'],
    why: ['A few parts cause most of the ', term('aog_hours'), '. Knowing which ones tells you where spares and fixes pay off.'],
    action: 'Start with the urgent parts. Check their spares at each airport. Escalate any part that breaks far more often than its supplier said.',
  }));

  // ------------------------------------------------------------------ explorer: aircraft + list
  const worstOf = () => ATAS.map((a) => sysStat[a]).filter((x) => x.n).sort((a, b) => (LEVEL[b.level].rank - LEVEL[a.level].rank) || ((b.share ?? 0) - (a.share ?? 0)) || b.urgent - a.urgent || (b.max || 0) - (a.max || 0))[0];
  let worst = worstOf();
  const airHost = h('div', { class: 'pi-aircraft' });
  // phones: the selected system's top-part callout is an HTML line under the drawing (no room between badges)
  const airNote = h('div', { class: 'pi-air-note', hidden: true });
  const legend = h('div', { class: 'pi-legend', 'aria-hidden': 'true' }, ...['urgent', 'review', 'ok'].map((l) => h('span', { class: `pi-legend-item is-${l}` }, h('b', {}, LEVEL[l].glyph), l === 'review' ? 'Review / watch' : LEVEL[l].text)), h('span', { class: 'pi-legend-item is-pip' }, h('b', { class: 'pi-legend-pip' }, 'n'), `urgent ${PN(2)} in system`),
    h('span', { class: 'faint' }, byMode('Shaded areas are rough zones, not exact part locations. The badge is the system’s share of the risk. WATCH means an OK system holds an urgent part.', 'Shaded areas are indicative zones, not component locations · badge = system share of material shortage exposure · WATCH = OK system holding an urgent part')));
  const explorerKicker = () => byMode(`Aircraft systems · ${fleet === 'WB' ? 'widebody' : 'narrowbody'} drawing · rough zones`, `Aircraft system explorer · ${fleet === 'WB' ? 'widebody' : 'narrowbody'} archetype · indicative zones`);
  const explorerCard = card({
    cls: 'span-7 md-span-12 pi-explorer', bp: true, prov,
    kicker: explorerKicker(),
    title: explorerTitle(),
    // the story hook wraps the drawing AND the phone's top-part line, so story step 2 frames the part on phones too (wave 5)
    body: [h('div', { class: 'pi-air-wrap', 'data-story': 'aircraft' }, airHost, airNote), legend],
  });
  /** F8 (wave 4): the headline follows the selected ATA; with "All" (or nothing selected) it names the riskiest system. */
  /** Fleet-filtered system stats (share of the fleet's material shortage exposure, PN count, urgent PNs, top PN). */
  function fleetStat(a) {
    const fp = parts.filter(inFleet), sp = fp.filter((p) => p.ata === a);
    const tot = fp.reduce((x, p) => x + (+p.risk_hours || 0), 0);
    return { ata: a, name: sysName(a), n: sp.length, urgent: sp.filter((p) => p.risk_level === 'urgent').length, share: tot ? sp.reduce((x, p) => x + (+p.risk_hours || 0), 0) / tot : null, top: sp.slice().sort((x, y) => (y.risk_score || 0) - (x.risk_score || 0))[0] };
  }
  function explorerTitle() {
    if (S) {
      const fl = fleet === 'all' ? 'all-fleet' : FLEET_LABEL[fleet].toLowerCase();
      const f = ata && ata !== 'all' ? (fleet === 'all' ? sysStat[ata] : fleetStat(ata)) : worst;
      if (!f) return 'No risk scores exported';
      const sh = f.share != null ? `${fmtPct(f.share, 0)} of ${fl} risk, ` : '';
      if (ata && ata !== 'all') return `${f.name}: ${sh}${fmtInt(f.urgent)} urgent of ${fmtInt(f.n)} parts${fleet === 'all' && worst && worst.ata === f.ata ? ', the most of any system' : ''}`;
      return `${f.name} carries the most risk: ${sh}${fmtInt(f.urgent)} urgent of ${fmtInt(f.n)} parts`;
    }
    if (fleet !== 'all' && ata && ata !== 'all') {
      const f = fleetStat(ata);
      return `ATA ${f.ata} ${f.name.toLowerCase()}: ${f.share != null ? `${fmtPct(f.share, 0)} of ${FLEET_LABEL[fleet].toLowerCase()} shortage exposure, ` : ''}${fmtInt(f.urgent)} urgent of ${fmtInt(f.n)} PNs`;
    }
    const s = ata && ata !== 'all' ? sysStat[ata] : null;
    if (s) return `ATA ${s.ata} ${s.name.toLowerCase()}: ${s.share != null ? `${fmtPct(s.share, 0)} of all-fleet shortage exposure, ` : ''}${fmtInt(s.urgent)} urgent of ${fmtInt(s.n)} PNs${worst && worst.ata === s.ata ? ', the most of any system' : ''}`;
    return worst ? `ATA ${worst.ata} ${worst.name.toLowerCase()} carries the most exposure: ${worst.share != null ? fmtPct(worst.share, 0) + ` of ${fleet === 'all' ? 'all-fleet' : FLEET_LABEL[fleet].toLowerCase()} shortage exposure, ` : ''}${worst.urgent} urgent of ${worst.n} PNs` : 'No risk scores exported';
  }

  const sysList = h('ul', { class: 'pi-syslist list-reset', role: 'list', 'aria-label': 'ATA systems (list alternative to the aircraft diagram)' });
  const fillSys = (b) => {
    const a = b.dataset.ata, s = sysStat[a];
    b.className = `pi-sys is-${s.tone}`;
    b.disabled = !s.n; b.title = s.n ? '' : `No part numbers on the ${FLEET_LABEL[fleet].toLowerCase()} fleet`;
    b.closest('li')?.classList.toggle('is-empty', !s.n);
    b.replaceChildren(
      h('span', { class: 'pi-sys-ata mono' }, a),
      h('span', { class: 'pi-sys-main' }, h('span', { class: 'pi-sys-name' }, s.name), h('span', { class: 'pi-sys-meta mono' }, `${fmtInt(s.n)} ${PN(s.n)} · top risk ${riskPct(s.max)}`)),
      // system level and urgent PARTS are separate facts: never a bare OK pill beside an urgent count
      h('span', { class: 'pi-sys-status' },
        pill(LEVEL[s.tone] && s.tone !== 'unknown' ? s.tone : 'unknown', s.word || LEVEL[s.level]?.text || LEVEL.unknown.text),
        s.urgent ? h('span', { class: 'pi-sys-urg mono', title: 'Part numbers in this chapter at the urgent part-level band' }, `▲ ${fmtInt(s.urgent)} urgent ${PN(s.urgent)}`) : null));
  };
  const sysButtons = ATAS.map((a) => {
    const b = h('button', { type: 'button', 'aria-pressed': String(a === ata), dataset: { ata: a }, onclick: () => setAta(a) });
    sysList.append(h('li', {}, b));
    fillSys(b);
    return b;
  });
  const allLabel = () => `All ${fmtInt(parts.filter(inFleet).length)} ${PN(2)}`;
  const allBtn = h('button', { type: 'button', class: 'btn btn--sm', 'aria-pressed': String(ata === 'all'), onclick: () => setAta('all') }, icon('layers'), h('span', { dataset: { role: 'all-label' } }, allLabel()));
  const listKicker = () => `${FLEET_LABEL[fleet]} · ${fmtInt(parts.filter(inFleet).length)} ${PN(2)} · list view`;
  const nOther = parts.filter((p) => !ATAS.includes(p.ata)).length;
  const bandsS = P.system_risk_bands_share, bandsP = P.risk_bands_h;
  const listFoot = S
    ? [bandsS ? `A system is urgent if it holds ${fmtPct(bandsS.urgent, 0)} or more of the fleet’s risk, and review at ${fmtPct(bandsS.review, 0)}. ` : '',
      bandsP ? `A part is urgent at ${fmtInt(bandsP.urgent)} or more grounded hours a year, and review at ${fmtInt(bandsP.review)} (assumed). ` : '',
      `The risk score runs from 0 to 100. ${nOther} ${PN(nOther)} sit in other systems (see “All”).`].join('')
    : `${bandsS ? `System level: urgent if the chapter holds ≥ ${fmtPct(bandsS.urgent, 0)} of fleet material shortage exposure, review ≥ ${fmtPct(bandsS.review, 0)}. ` : ''}${bandsP ? `Part level: urgent ≥ ${fmtInt(bandsP.urgent)} AOG h/yr, review ≥ ${fmtInt(bandsP.review)} (assumed bands). ` : ''}Risk score 0–100 is log-scaled AOG hours. ${nOther} PNs sit in other chapters (see “All”).`;
  const listCard = card({ cls: 'span-5 md-span-12', kicker: listKicker(), title: byMode('Pick an aircraft system', 'Select an ATA chapter'), prov: 'DERIVED', actions: allBtn, body: sysList, foot: h('span', {}, listFoot) });

  const fleetSeg = segmented({ label: 'Fleet', value: fleet, options: [{ value: 'NB', label: 'Narrowbody' }, { value: 'WB', label: 'Widebody' }, { value: 'all', label: 'All fleet' }], onChange: (v) => setFleet(v) });
  fleetSeg.dataset.role = 'fleet-filter';
  explorerCard.querySelector('.card-head')?.after(h('div', { class: 'pi-fleet-row' }, fleetSeg, h('span', { class: 'pi-fleet-note faint' })));
  const panelCard = h('section', { class: 'card pi-panel', dataset: { story: 'parts-system-panel' }, 'aria-live': 'polite' });
  listCard.classList.remove('span-5', 'md-span-12');
  // wave C: the left column holds the explorer AND the planted-situations card, so it ends level with the side column
  explorerCard.classList.remove('span-7', 'md-span-12');
  const piMain = h('div', { class: 'span-7 md-span-12 pi-main' }, explorerCard);
  el.append(h('div', { class: 'grid-12' }, piMain, h('div', { class: 'span-5 md-span-12 pi-side' }, panelCard, listCard)));

  // ------------------------------------------------------------------ exploded view + demand matrix
  const figHost = h('div', { class: 'bp-figure pi-exploded' });
  const slotKey = h('ol', { class: 'pi-slotkey list-reset' });
  const explodedTitle = h('h3', { class: 'card-title' });
  const explodedCard = card({ cls: 'span-6 md-span-12', prov, kicker: byMode('Exploded drawing · made-up parts', 'Exploded schematic · fictional components'), body: [explodedTitle, figHost, slotKey] });
  const matrixCard = h('section', { class: 'card span-6 md-span-12' });
  el.append(h('div', { class: 'grid-12 mt-3' }, explodedCard, matrixCard));

  // ------------------------------------------------------------------ parts table
  const search = h('input', { class: 'input pi-search', type: 'search', placeholder: byMode('Search part number or name', 'Search PN or description'), 'aria-label': 'Search parts by part number or description', oninput: (e) => { query = e.target.value.trim().toLowerCase(); refreshTable(); } });
  const clsSeg = segmented({ label: 'Part class', value: cls, options: [{ value: 'all', label: 'All' }, ...['R', 'E', 'C'].map((c) => ({ value: c, label: CLS_NAME[c] }))], onChange: (v) => { cls = v; refreshTable(); ctx.setParams({ cls: v === 'all' ? '' : v }); } });
  const columns = [
    { key: 'pn', label: 'Part number', mono: true, render: (r) => h('span', { class: 'pi-pn' }, h('span', { class: 'mono' }, r.pn),
      r.planted ? h('span', { class: 'chip chip-mono pi-planted expert-only', title: 'Planted situation (a scenario the models should detect)' }, r.planted) : null,
      // A9: parts whose frozen-plan allocation puts brakes at an outstation carry a visible flag
      (r.allocation_flags || []).length ? h('span', { class: 'chip pi-flag-chip', dataset: { role: 'alloc-flag' }, title: P.invalid_allocation_text || 'invalid recommendation' }, icon('alert'), byMode('flagged', 'invalid alloc.')) : null,
      r.escalation ? h('span', { class: 'chip pi-esc-chip', dataset: { role: 'esc-flag' }, title: r.escalation.text }, icon('alert'), 'escalate') : null) },
    { key: 'desc', label: byMode('Name', 'Description'), render: (r) => h('span', { class: 'pi-desc', title: r.desc }, r.desc) },
    { key: 'cls', label: byMode('Type', 'Class'), render: (r) => (S ? h('span', { class: 'pi-cls-word' }, CLS_NAME[r.cls]) : h('span', { class: `pi-cls pi-cls--${r.cls}`, title: CLS_NAME[r.cls] }, r.cls)) },
    { key: 'deadline', label: byMode('Fix within', 'Window'), mono: !S, format: (v) => (S ? WINDOW_SIMPLE[v] || v : v) },
    { key: 'demand_class', label: byMode('Needed', 'Demand'), format: (v) => dcName(v) },
    { key: 'abc', label: byMode('Value class', 'ABC'), mono: true },
    // C7 (wave 4): this is the recommended plan's target (all stations), not on-hand stock
    { key: 'stock_total', label: S ? `${planName} target` : `${P.stock_basis_id || 'Plan'} target`, short: S ? 'Plan target' : `${P.stock_basis_id || 'Plan'} target`, num: true, format: fmtInt },
    { key: 'unit_cost', label: 'Unit cost', num: true, format: (v) => fmtAED(v) },
    { key: 'risk_score', label: 'Risk', short: 'Risk', num: true, render: (r) => h('span', { class: 'pi-risk-cell', title: riskTitle(r) }, riskPill(r), excChip(r)) },
  ];
  /** Risk pill: urgent red, review amber; a calm score is a neutral pill (teal is the recommended plan only). */
  function riskPill(r, text = riskPct(r.risk_score)) {
    const pl = pill(r.risk_level === 'ok' ? 'unknown' : r.risk_level, text);
    if (r.risk_level === 'ok') { pl.querySelector('.icon use')?.setAttribute('href', '#i-check'); pl.classList.add('pill--calm'); }
    return pl;
  }
  /**
   * C10 (wave 4): risk is grounding exposure; an exception's severity is planning urgency. A PN with a low risk score but an
   * urgent/review exception (PS4 GN-30-E025: lead-time drift) shows that exception beside its score.
   */
  function excChip(r) {
    // urgent actions only (wave 5): review-level housekeeping (quarantine, excess) stays in the drawer, not as row noise
    const e = (r.exceptions || []).find((x) => x.severity === 'urgent');
    if (!e || r.risk_level === e.severity) return null;
    return h('span', { class: `chip pi-exc pi-exc--${e.severity}`, title: `${e.type_label} · ${e.severity} planner action (${e.exception_id} at ${e.station}). Risk measures material shortage exposure; this action is about planning data.` }, icon(e.severity === 'urgent' ? 'alert' : 'clock'), `${e.type_label} · ${e.severity}`);
  }
  function riskTitle(r) {
    if (S) return `${r.risk_hours != null ? `About ${fmtHours(r.risk_hours)} a year grounded waiting for this part (past record plus model). ` : ''}The score runs from 0 to 100.`;
    return `${r.risk_hours != null ? `${fmtHours(r.risk_hours)}/yr of AOG = ${fmtHours(r.aog_hours_hist_per_yr)} history + ${fmtNum(r.residual_aog_h_per_yr, 1)} h modelled residual. ` : ''}Score = ln(1 + AOG h) / ln(1 + fleet max), × 100.`;
  }
  const rowsFor = () => parts.filter((p) => inFleet(p) && (ata === 'all' || p.ata === ata) && (cls === 'all' || p.cls === cls) && (!query || p.pn.toLowerCase().includes(query) || String(p.desc).toLowerCase().includes(query)));
  const table = dataTable({ columns, rows: rowsFor(), sort: { key: 'risk_score', dir: 'desc' }, onRowClick: (r) => openPart(r.pn), rowKey: 'pn', caption: 'Parts for the selected ATA system', maxHeight: 520, mobileColumns: ['pn', 'risk_score', 'stock_total', 'desc'], stickyFirst: true });
  const tableCount = h('span', { class: 'chip' });
  const tableTitle = h('h3', { class: 'card-title' });
  const tableCard = h('section', { class: 'card span-12', dataset: { story: 'parts-table' } },
    h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, byMode('Every part · how often needed · spares · risk', 'Part master · demand class · stock · risk')), tableTitle), h('div', { class: 'row-wrap gap-1' }, tableCount, provChip(prov))),
    h('div', { class: 'pi-toolbar' }, search, clsSeg),
    table,
    h('div', { class: 'card-foot pi-foot' }, h('span', {}, S
      ? ['The ', term('rectification_window'), ' (next flight, 3 days or 10 days) is assumed, not taken from an airline. How often a part is needed comes from the training weeks only. Click a row for details.']
      : 'Rectification windows D0 / D3 / D10 are hypothetical; D3 and D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions. NONE = servicing fluids, never a downtime driver. Demand class from training weeks only. Click a row for the drill-down.'),
      // v2 brake disclosure (exporter: parts.json brake_note, from the P0 gap diagnosis)
      P.brake_note ? h('p', { class: 'pi-brake-note', dataset: { role: 'brake-note' } }, icon('info'), h('span', {}, P.brake_note)) : null,
      // A9: the frozen plan's outstation brake units stay in the numbers, flagged
      (P.invalid_allocations || []).length ? allocationFlagNote(P.invalid_allocations, { text: P.invalid_allocation_text, compact: true }) : null,
      scopeLine()));
  el.append(h('div', { class: 'grid-12 mt-3' }, tableCard));
  function refreshTable() {
    const rows = rowsFor();
    table.update(rows);
    tableCount.textContent = `${fmtInt(rows.length)} ${PN(rows.length)}`;
    tableTitle.textContent = ata === 'all' ? byMode('All parts', 'All part numbers') : S ? sysName(ata) : `ATA ${ata} · ${sysName(ata)}`;
  }
  refreshTable();

  // ------------------------------------------------------------------ ABC × demand class heatmap + planted
  const heatCard = h('section', { class: 'card span-12' });
  const plantedCard = h('section', { class: 'card pi-planted-card' });
  piMain.append(plantedCard);
  el.append(h('div', { class: 'grid-12 mt-3' }, heatCard));

  const cleanups = [];
  const matrix = drawMatrix();
  cleanups.push(matrix.stop);
  const heat = drawHeatmap();
  cleanups.push(heat.stop);
  drawPlanted();

  // ------------------------------------------------------------------ aircraft
  let air = null;
  async function buildAircraft() {
    air?.destroy?.();
    const wb = fleet === 'WB';
    air = await blueprintAircraft(airHost, { fleet: wb ? 'widebody' : 'narrowbody', active: ata === 'all' ? null : ata, onSelect: (a) => setAta(a), compactBelow: 1e6,
      label: wb ? 'Plan view of a twin-aisle twin-engine airliner archetype (original schematic) with indicative ATA system zones' : 'Plan view of a single-aisle twin-engine airliner archetype (original schematic) with indicative ATA system zones' });
    decorateAircraft(air.svg);
  }
  await buildAircraft();
  const airRO = new ResizeObserver(() => requestAnimationFrame(layoutAircraft));
  airRO.observe(airHost);
  cleanups.push(() => air?.destroy?.(), () => airRO.disconnect());

  /**
   * Hotspot decoration. Badge colour + word = SYSTEM level (chapter share of fleet risk-hours). A red pip with a
   * count marks every system that contains urgent PART numbers, so a "review" chapter holding an urgent part never
   * reads as calm, and the selected system gets a part-level callout for its top-risk PN. All text is sized in
   * screen pixels (≥ 11 px) by layoutAircraft(), not by the viewBox scale.
   */
  function decorateAircraft(svg) {
    svg.querySelectorAll('.ata-hotspot').forEach((g) => {
      const s = sysStat[g.dataset.ata];
      // a system with no part number on the selected fleet is not drawn (e.g. no ATA 36 pneumatic parts on the widebody)
      const nFleet = parts.filter((p) => p.ata === g.dataset.ata && inFleet(p)).length;
      if (!nFleet) { g.style.display = 'none'; g.setAttribute('aria-hidden', 'true'); g.setAttribute('tabindex', '-1'); return; }
      if (!s) return;
      g.classList.add(`risk-${LEVEL[s.tone] ? s.tone : s.level}`);
      g.dataset.story = `parts-hotspot-${s.ata}`;
      g.setAttribute('aria-label', `ATA ${s.ata} ${s.name}: ${s.word || LEVEL[s.level].text} (system level ${LEVEL[s.level].text}). ${s.n} part numbers, ${s.urgent} urgent${s.top ? `; top part ${s.top.pn}, risk ${riskPct(s.top.risk_score)} (${LEVEL[s.top.risk_level]?.text || s.top.risk_level})` : ''}.`);
      const badge = g.querySelector('.hs-badge');
      const c = badge?.querySelector('circle');
      if (!c) return;
      // addendum (audit): the badge is the button. A split zone (both wings) has empty space at its centre, so the
      // whole group made a poor pointer target; the group keeps its click/keydown handlers (events bubble from the badge).
      badge.setAttribute('role', 'button'); badge.setAttribute('tabindex', '0');
      badge.setAttribute('aria-label', g.getAttribute('aria-label'));
      badge.setAttribute('aria-pressed', g.getAttribute('aria-pressed') || 'false');
      badge.classList.add('pi-hs-btn');
      g.removeAttribute('role'); g.removeAttribute('tabindex');
      const cx = +c.getAttribute('cx'), cy = +c.getAttribute('cy');
      g._hs = { cx, cy };
      // the pulse ring lives in its own layer beside the hotspot (pointer-events none), so the clickable hotspot's
      // bounding box never animates (stable for pointer hit-testing)
      const wrap = svgEl('g', { class: `pi-pulse-wrap risk-${LEVEL[s.tone] ? s.tone : s.level}`, 'aria-hidden': 'true' });
      wrap.setAttribute('data-ata', s.ata);
      svgEl('circle', { cx, cy, r: 19, class: 'hs-pulse' }, wrap);
      g.parentNode.insertBefore(wrap, g);
      const tn = LEVEL[s.tone] ? s.tone : s.level;
      svgEl('text', { x: cx, y: cy + 34, class: `hs-risk hs-risk--${tn}` }, badge).textContent = `${LEVEL[tn].glyph} ${(s.word || LEVEL[tn].text).toUpperCase()}`;
      if (s.urgent) {
        const pip = svgEl('g', { class: 'hs-pip', 'aria-hidden': 'true' }, badge);
        svgEl('circle', { cx, cy, r: 8 }, pip);
        svgEl('text', { x: cx, y: cy }, pip).textContent = fmtInt(s.urgent);
      }
    });
    layoutAircraft();
  }

  /** The badge buttons mirror the shell's aria-pressed on their hotspot group. */
  function syncPressed() {
    air?.svg?.querySelectorAll('.ata-hotspot').forEach((g) => g.querySelector('.pi-hs-btn')?.setAttribute('aria-pressed', g.getAttribute('aria-pressed') || 'false'));
  }
  function layoutAircraft() {
    const svg = air?.svg;
    if (!svg?.isConnected) return;
    const vb = svg.viewBox.baseVal;
    const wpx = svg.getBoundingClientRect().width;
    if (!vb?.width || !wpx) return;
    const u = vb.width / wpx; // user units per screen px
    svg.querySelectorAll('.ata-hotspot').forEach((g) => {
      if (!g._hs) return;
      const { cx, cy } = g._hs;
      const R = Math.max(19, 12 * u);
      g.querySelectorAll('.hs-badge > circle').forEach((c) => c.setAttribute('r', R));
      svg.querySelectorAll(`.pi-pulse-wrap[data-ata="${g.dataset.ata}"] .hs-pulse`).forEach((c) => c.setAttribute('r', R));
      const num = g.querySelector('.hs-badge > text:not(.hs-risk)');
      if (num) num.style.fontSize = `${Math.max(17, 12 * u)}px`;
      const zt = g.querySelector('.hs-zone-t');
      if (zt) { zt.style.fontSize = `${11 * u}px`; zt.style.strokeWidth = `${4 * u}px`; }
      const lbl = g.querySelector('.hs-risk');
      if (lbl) { lbl.setAttribute('x', cx); lbl.setAttribute('y', cy + R + 9 * u); lbl.style.textAnchor = 'middle'; lbl.style.fontSize = `${11 * u}px`; lbl.style.strokeWidth = `${4 * u}px`; }
      const pip = g.querySelector('.hs-pip');
      if (pip) {
        const pd = (R + 6 * u) * 0.8, px = cx + pd, py = cy - pd;
        pip.querySelector('circle').setAttribute('cx', px); pip.querySelector('circle').setAttribute('cy', py); pip.querySelector('circle').setAttribute('r', 8 * u);
        pip.querySelector('circle').style.strokeWidth = `${1.5 * u}px`;
        const t = pip.querySelector('text'); t.setAttribute('x', px); t.setAttribute('y', py); t.style.fontSize = `${11 * u}px`;
      }
    });
    // risk words that would leave the drawing or sit on another badge/pip move beside their own badge
    const spots = [...svg.querySelectorAll('.ata-hotspot')].filter((g) => g._hs);
    const ov = (a, b) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
    const marks = (g) => [...g.querySelectorAll('.hs-badge > circle, .hs-pip circle')].map((c) => { try { return c.getBBox(); } catch { return null; } }).filter(Boolean);
    spots.forEach((g) => {
      const lbl = g.querySelector('.hs-risk');
      if (!lbl) return;
      const others = spots.filter((o) => o !== g).flatMap(marks);
      const bad = () => { const b = lbl.getBBox(); return b.y + b.height > vb.y + vb.height || others.some((o) => ov(b, o)); };
      if (!bad()) return;
      const { cx, cy } = g._hs, R = Math.max(19, 12 * u);
      for (const side of [-1, 1]) {
        lbl.setAttribute('x', cx + side * (R + 6 * u)); lbl.setAttribute('y', cy + (side > 0 ? 8 * u : 0)); lbl.style.textAnchor = side < 0 ? 'end' : 'start';
        if (!bad()) return;
      }
    });
    drawHotspotCallout(svg, u, wpx);
  }

  /** Part-level callout for the selected system: its top-risk PN, placed clear of the other badges. */
  function drawHotspotCallout(svg, u, wpx) {
    svg.querySelectorAll('.pi-hs-callout').forEach((e) => e.remove());
    airNote.hidden = true;
    if (ata === 'all') return;
    const g = svg.querySelector(`.ata-hotspot[data-ata="${ata}"]`);
    const top = fleet === 'all' ? sysStat[ata]?.top : fleetStat(ata).top;   // the fleet's own top part
    if (!g?._hs || !top) return;
    const lv = LEVEL[top.risk_level] ? top.risk_level : 'unknown';
    const small = wpx < 480;
    if (small) {
      const sl = sysStat[ata].level;
      airNote.replaceChildren(h('button', { type: 'button', class: `pi-air-note-btn is-${lv}`, onclick: () => openPart(top.pn), 'aria-label': `Top-risk part in ATA ${ata}: ${top.pn}, risk ${riskPct(top.risk_score)}, ${LEVEL[lv].text}. Open the part drill-down.` },
        h('span', { class: 'pi-air-note-k mono' }, `ATA ${ata} · ${(sysStat[ata].word || LEVEL[sl]?.text || sl).toLowerCase()} system · top part`),
        h('span', { class: 'pi-air-note-v mono' }, `${LEVEL[lv].glyph} ${top.pn} · risk ${riskPct(top.risk_score)} · ${LEVEL[lv].text.toUpperCase()}`), icon('chevron-right')));
      airNote.hidden = false;
      return;
    }
    const text = small ? `${LEVEL[lv].glyph} ${top.pn} · ${riskPct(top.risk_score)}` : `${LEVEL[lv].glyph} ${top.pn} · risk ${riskPct(top.risk_score)} · ${LEVEL[lv].text.toUpperCase()}`;
    const grp = svgEl('g', { class: `pi-hs-callout is-${lv}`, role: 'button', tabindex: '0', 'aria-label': `Top-risk part in ATA ${ata}: ${top.pn}, risk ${riskPct(top.risk_score)}, ${LEVEL[lv].text}. Open the part drill-down.` }, g);
    const lead = svgEl('path', { class: 'pi-hs-leader' }, grp);
    const rect = svgEl('rect', { class: 'pi-hs-box', rx: 4 * u }, grp);
    const t = svgEl('text', { class: 'pi-hs-text' }, grp);
    t.textContent = text;
    t.style.fontSize = `${11.5 * u}px`;
    const tw = t.getComputedTextLength();
    const padX = 8 * u, bh = 24 * u, bw = tw + padX * 2;
    const { cx, cy } = g._hs;
    const R = Math.max(19, 12 * u), gap = 16 * u;
    const lblBelow = 9 * u + 14 * u; // risk word under the badge
    const cands = [
      { x: cx + R + gap, y: cy - bh / 2 }, { x: cx - R - gap - bw, y: cy - bh / 2 },
      { x: cx + R * 0.4, y: cy + R + lblBelow + 8 * u }, { x: cx - R * 0.4 - bw, y: cy + R + lblBelow + 8 * u },
      { x: cx + R * 0.4, y: cy - R - gap - bh }, { x: cx - R * 0.4 - bw, y: cy - R - gap - bh },
      { x: cx - bw / 2, y: cy + R + lblBelow + 8 * u }, { x: cx - bw / 2, y: cy - R - gap - bh },
    ];
    // extra candidates: beside the badge, stepped up / down, so a free slot is found between neighbouring badges
    [-3, -2, -1, 1, 2, 3].forEach((k) => [cx + R + gap, cx - R - gap - bw].forEach((xx) => cands.push({ x: xx, y: cy - bh / 2 + k * bh * 0.75 })));
    // obstacles: every badge circle, risk word and urgent pip (own system included) so the callout never sits on a label
    const bb = (e) => { try { return e.getBBox(); } catch { return null; } };
    const obstacles = [...svg.querySelectorAll('.ata-hotspot .hs-badge > circle, .ata-hotspot .hs-risk, .ata-hotspot .hs-pip circle')].map(bb).filter(Boolean)
      .map((b) => ({ x: b.x - 4 * u, y: b.y - 4 * u, width: b.width + 8 * u, height: b.height + 8 * u }));
    const vb = svg.viewBox.baseVal;
    const ov = (a, b) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
    const out = (b) => Math.max(0, vb.x - b.x) + Math.max(0, b.x + b.width - vb.x - vb.width) + Math.max(0, vb.y - b.y) + Math.max(0, b.y + b.height - vb.y - vb.height);
    const best = cands.map((c, i) => ({ ...c, cost: obstacles.reduce((s, o) => s + ov({ ...c, width: bw, height: bh }, o), 0) * 50 + out({ ...c, width: bw, height: bh }) * 1e6 + Math.hypot(Math.max(c.x - cx, cx - c.x - bw, 0), Math.max(c.y - cy, cy - c.y - bh, 0)) * 6 / u + i })).sort((a, b) => a.cost - b.cost)[0];
    rect.setAttribute('x', best.x); rect.setAttribute('y', best.y); rect.setAttribute('width', bw); rect.setAttribute('height', bh);
    rect.style.strokeWidth = `${1.25 * u}px`;
    t.setAttribute('x', best.x + padX); t.setAttribute('y', best.y + bh / 2);
    const ex = Math.max(best.x, Math.min(cx, best.x + bw)), ey = Math.max(best.y, Math.min(cy, best.y + bh));
    const ang = Math.atan2(ey - cy, ex - cx);
    lead.setAttribute('d', `M${cx + Math.cos(ang) * R},${cy + Math.sin(ang) * R}L${ex},${ey}`);
    lead.style.strokeWidth = `${1.25 * u}px`;
    const open = (e) => { e.stopPropagation(); e.preventDefault(); openPart(top.pn); };
    grp.addEventListener('click', open);
    grp.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') open(e); });
  }

  // ------------------------------------------------------------------ exploded view
  async function drawExploded() {
    if (ata === 'all') {
      explodedTitle.textContent = byMode('Pick a system to see its parts drawing', 'Select a system to see its exploded view');
      figHost.replaceChildren(h('div', { class: 'state' }, icon('layers'), h('p', {}, byMode('The drawing shows one aircraft system at a time.', 'The exploded schematic shows one ATA chapter at a time.'))));
      slotKey.replaceChildren();
      return;
    }
    const svg = await inlineSVG(`exploded-${ata}.svg`);
    const ps = parts.filter((p) => p.ata === ata);
    const labels = matchSlots(svg, ps);
    fillExploded(svg, labels);
    // HTML label overlay: the SVG's own label text renders at 6–7 px once the 960-wide sheet is scaled to card width,
    // so the PN / description labels are drawn in HTML (12 / 11 px) at the slot bubble positions instead.
    const vb = svg.viewBox.baseVal;
    const hot = labels.map((l) => byPn.get(l.pn)).filter(Boolean).sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))[0];
    const hotSlot = hot && ['urgent', 'review'].includes(hot.risk_level) ? labels.find((l) => l.pn === hot.pn)?.slot : null;
    const overlay = h('div', { class: 'pi-xlabels' });
    svg.querySelectorAll('.bp-callout').forEach((co) => {
      const bub = co.querySelector('.bp-bubble');
      const slot = co.querySelector('.bp-bubble-t')?.textContent?.trim();
      const l = labels.find((x) => String(x.slot) === slot);
      if (!bub || !l) return;
      const bx = +bub.getAttribute('cx'), by = +bub.getAttribute('cy'), br = +bub.getAttribute('r') || 14;
      const above = by < vb.y + vb.height / 2;
      const p = byPn.get(l.pn);
      const isHot = String(l.slot) === String(hotSlot);
      const btn = h('button', {
        type: 'button', class: `pi-xlabel ${above ? 'is-above' : 'is-below'}${isHot ? ` is-hot risk-${p.risk_level}` : ''}`, disabled: !p, 'aria-label': p ? `${l.pn} ${p.desc}, risk ${riskPct(p.risk_score)}: open part drill-down` : `Slot ${l.slot}: no part`,
        style: { left: `${((bx - vb.x) / vb.width) * 100}%`, top: `${(((above ? by - br - 6 : by + br + 6) - vb.y) / vb.height) * 100}%` },
        onclick: () => p && openPart(p.pn),
      }, isHot ? h('span', { class: 'pi-xlabel-risk' }, `${LEVEL[p.risk_level].glyph} risk ${riskPct(p.risk_score)}`) : null, h('span', { class: 'pi-xlabel-pn mono' }, l.pn || '—'), h('span', { class: 'pi-xlabel-desc' }, p ? p.desc : l.role));
      overlay.append(btn);
      if (isHot) {
        svg.querySelector(`.bp-part[data-slot="${l.slot}"]`)?.classList.add('pi-hot', `risk-${p.risk_level}`);
        co.classList.add('pi-hot', `risk-${p.risk_level}`);
      }
    });
    figHost.replaceChildren(h('div', { class: 'pi-exploded-stage' }, svg, overlay), h('p', { class: 'pi-exploded-cap' }, byMode('Drawing · not engineering data', 'Schematic · not engineering data')));
    const matched = labels.filter((l) => l.pn);
    explodedTitle.textContent = S ? `${sysName(ata)}: ${matched.length} of ${ps.length} parts drawn` : `ATA ${ata} · ${sysName(ata)}: ${matched.length} of ${ps.length} PNs drawn`;
    slotKey.replaceChildren(...labels.map((l) => {
      const p = byPn.get(l.pn);
      return h('li', {}, h('button', { type: 'button', class: 'pi-slotkey-btn', disabled: !p, onclick: () => p && openPart(p.pn) },
        h('span', { class: 'pi-slotnum mono' }, String(l.slot)), h('span', { class: 'mono' }, l.pn || '—'), h('span', { class: 'pi-slotdesc' }, p ? p.desc : l.role),
        p ? riskPill(p) : null));
    }));
  }

  /** Assign PNs to the 5 schematic slots by description similarity, falling back to the highest-risk R/E part. */
  function matchSlots(svg, ps) {
    const tok = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).filter((w) => w.length > 2 && !['unit', 'kit', 'variant', 'assembly', 'the', 'and', 'main'].includes(w));
    const used = new Set();
    const slots = [...svg.querySelectorAll('.bp-label')].map((lg) => ({ slot: +lg.dataset.slot, role: lg.querySelector('[data-field="desc"]')?.textContent || '' }));
    const pool = ps.filter((p) => p.cls !== 'C').concat(ps.filter((p) => p.cls === 'C'));
    const out = slots.map((s) => {
      const st = new Set(tok(s.role));
      let best = null, bestScore = 0;
      pool.forEach((p) => {
        if (used.has(p.pn)) return;
        const sc = tok(p.desc).filter((w) => st.has(w) || [...st].some((x) => x.startsWith(w.slice(0, 5)) && w.length > 4)).length;
        if (sc > bestScore || (sc === bestScore && sc > 0 && p.risk_score > best.risk_score)) { best = p; bestScore = sc; }
      });
      if (best) used.add(best.pn);
      return { ...s, p: best };
    });
    const rest = pool.filter((p) => !used.has(p.pn)).sort((a, b) => b.risk_score - a.risk_score);
    const res = out.map((s) => {
      const p = s.p || rest.shift();
      return { slot: s.slot, role: s.role, pn: p?.pn, desc: p?.desc, risk: p?.risk_score ?? -1 };
    });
    // the chapter's top-risk PN (the one the aircraft callout names) must be among the drawn parts:
    // if no slot matched it, it replaces the lowest-risk drawn part
    const top = ps.slice().sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))[0];
    if (top && res.length && !res.some((r) => r.pn === top.pn)) {
      const low = res.slice().sort((a, b) => a.risk - b.risk)[0];
      Object.assign(low, { pn: top.pn, desc: top.desc, risk: top.risk_score });
    }
    return res.map(({ risk, ...r }) => r);
  }

  // ------------------------------------------------------------------ ADI / CV² matrix
  /**
   * ADI / CV² matrix. Built once; ATA and fleet changes call update(): dots are a keyed join on the PN, so they move,
   * grow, fade in or fade out (transform / opacity, base token) and the axes transition. A resize redraws in place.
   */
  function drawMatrix() {
    matrixCard.replaceChildren();
    const ptsOf = () => parts.filter((p) => inFleet(p) && Number.isFinite(p.adi) && Number.isFinite(p.cv2) && p.demand_class !== 'insufficient_data');
    const countsOf = (pts) => Object.fromEntries(['smooth', 'erratic', 'intermittent', 'lumpy'].map((c) => [c, pts.filter((p) => p.demand_class === c).length]));
    const headOf = (pts) => {
      const c = countsOf(pts), sparse = c.intermittent + c.lumpy;
      return S
        ? (sparse * 2 > pts.length ? `Most parts are needed rarely: ${fmtInt(sparse)} of ${fmtInt(pts.length)} only now and then` : `${fmtInt(sparse)} of ${fmtInt(pts.length)} parts are needed only now and then`)
        : (sparse * 2 > pts.length ? `Most PNs demand rarely: ${fmtInt(sparse)} of ${fmtInt(pts.length)} are intermittent or lumpy` : `${fmtInt(sparse)} of ${fmtInt(pts.length)} classified PNs are intermittent or lumpy`);
    };
    const subOf = (pts) => {
      const nIns = parts.filter(inFleet).length - pts.length;
      return S
        ? `One dot per part. Further right means longer gaps between orders. Higher means order sizes vary more. Training weeks ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)} only.${nIns ? ` ${nIns} ${PN(nIns)} with too little history ${nIns === 1 ? 'is' : 'are'} not shown.` : ''}`
        : `ADI (weeks between demands, log) × CV² of demand sizes · training weeks ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)} · Syntetos–Boylan cut-offs ${ADI_CUT} / ${CV2_CUT}${nIns ? ` · ${nIns} PN${nIns === 1 ? '' : 's'} with insufficient history (< 3 demands) not plotted` : ''}`;
    };
    const cols = [{ key: 'pn', label: 'PN', mono: true }, { key: 'adi', label: 'ADI', num: true, format: (v) => fmtNum(v) }, { key: 'cv2', label: 'CV²', num: true, format: (v) => fmtNum(v) }, { key: 'demand_class', label: 'Class', format: dcName }];
    const pts0 = ptsOf();
    const f = chartFrame(matrixCard, {
      implication: byMode('Parts needed only now and then need forecasts built for the many zero weeks, and spares sized on risk.', 'Intermittent and lumpy demand needs methods built for zeros and safety stock sized on exposure.'),
      headline: headOf(pts0), subtitle: subOf(pts0),
      provenance: 'DERIVED', source: 'parts.json (adi, cv2, demand_class)', story: 'parts-adi-matrix',
      table: { columns: cols, rows: pts0 },
    });
    const keyEl = h('div', { class: 'pi-matrix-key' });
    f.body.after(keyEl);
    const d3 = window.d3;
    let W = 0, L = null;
    function render(w, animate) {
      const pts = ptsOf();
      const counts = countsOf(pts);
      const hl = f.root.querySelector('.chart-headline'); if (hl) hl.textContent = headOf(pts);
      const sb = f.root.querySelector('.chart-subtitle'); if (sb) sb.textContent = subOf(pts);
      if (animate) f.setTable(cols, pts);
      const small = w < 480;
      const hgt = small ? 300 : 340;
      const m = { top: 20, right: 16, bottom: 36, left: 44 };
      const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
      if (w !== W || !L) {
        // skeleton (once per width): layers keep their order; marks are joined into them
        const svg = svgIn(f.body, w, hgt, 'ADI versus CV squared scatter');
        const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
        L = { svg, g, quad: g.append('rect').attr('class', 'pi-quad pi-quad--sparse').attr('y', 0).attr('height', ih), xa: g.append('g'), ya: g.append('g') };
        refLine(g, { x1: 0, y1: 0, x2: 0, y2: ih }); refLine(g, { x1: 0, y1: 0, x2: iw, y2: 0 });
        [L.refV, L.refH] = g.selectAll('.gnm-ref').nodes().map((n) => d3.select(n));
        g.append('text').attr('class', 'pi-axis-t').attr('x', iw).attr('y', ih + 30).attr('text-anchor', 'end').text(byMode('Weeks between orders →', 'ADI · weeks between demands →'));
        g.append('text').attr('class', 'pi-axis-t').attr('x', -m.left + 2).attr('y', -2).text(byMode('Size varies ↑', 'CV² ↑'));
        L.dots = g.append('g').attr('class', 'pi-dots');
        L.labels = g.append('g');
        L.annot = g.append('g');
        W = w;
        animate = false;
      }
      const { g } = L;
      const T = (sel) => (animate ? txSel(sel) : sel);
      const xMax = Math.max(ADI_CUT * 3, (d3.max(pts, (p) => p.adi) || 1) * 1.15);
      const yMax = Math.max(CV2_CUT * 2.2, (d3.max(pts, (p) => p.cv2) || 0) * 1.1);
      const x = d3.scaleLog().domain([1, xMax]).range([0, iw]);
      const y = d3.scaleLinear().domain([0, yMax]).nice().range([ih, 0]);
      // quadrants + Syntetos–Boylan cut-offs (reference lines, not amber: amber = review status)
      const qx = x(ADI_CUT), qy = y(CV2_CUT);
      T(L.quad).attr('x', qx).attr('width', iw - qx);
      L.xa.attr('transform', `translate(0,${ih})`);
      T(L.xa).call(d3.axisBottom(x).tickSizeOuter(0).tickSize(4).tickPadding(6).tickFormat((v) => (Number.isInteger(v) && [1, 2, 5, 10, 20, 50, 100].includes(v) ? v : '')));
      styleAxis(L.xa);
      T(L.ya).call(d3.axisLeft(y).ticks(4).tickSizeOuter(0).tickSize(0).tickPadding(8).tickFormat((v) => fmtNum(v, 1)));
      styleAxis(L.ya, { domain: false });
      T(L.refV).attr('transform', `translate(${qx},0)`);
      T(L.refH).attr('transform', `translate(0,${qy})`);
      const sel = (p) => ata !== 'all' && p.ata === ata;
      const px = (p) => x(Math.min(p.adi, xMax)), py = (p) => y(Math.min(p.cv2, yMax));
      const tf = (p) => `translate(${px(p)},${py(p)}) scale(${sel(p) ? 5 / 3.5 : 1})`;
      const dots = L.dots.selectAll('circle.pi-dot').data(pts, (p) => p.pn).join(
        (enter) => enter.append('circle').attr('class', 'pi-dot').attr('r', 3.5).attr('vector-effect', 'non-scaling-stroke').attr('transform', tf).style('opacity', 0)
          .style('cursor', 'pointer').on('click', (e, p) => openPart(p.pn)).on('keydown', (e, p) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPart(p.pn); } })
          .call((en) => (animate ? txSel(en).style('opacity', 1) : en.style('opacity', 1))),
        (update) => update,
        (exit) => (animate ? txSel(exit, { ease: 'exit' }).style('opacity', 0).remove() : exit.remove()));
      dots.attr('class', (p) => `pi-dot${sel(p) ? ' is-sel' : ''}${p.pn === ctx.params.pn ? ' is-pn' : ''}`)
        .attr('tabindex', (p) => (sel(p) ? 0 : null))
        .attr('role', (p) => (sel(p) ? 'button' : null))
        .attr('aria-label', (p) => (sel(p) ? `${p.pn} ${dcName(p.demand_class)}, ADI ${fmtNum(p.adi)}, CV² ${fmtNum(p.cv2)}` : null));
      T(dots).attr('transform', tf);
      dots.filter(sel).raise();
      withTooltip(dots, (p) => ({ title: p.pn, rows: [['Description', p.desc], [byMode('Weeks between orders', 'ADI'), fmtNum(p.adi)], [byMode('Size spread', 'CV²'), fmtNum(p.cv2)], [byMode('Needed', 'Class'), dcName(p.demand_class)], ['Risk', riskPct(p.risk_score)]] }));
      const obstacles = pts.map((p) => markerRect(px(p), py(p), sel(p) ? 5 : 3.5, 1));
      const ov = (a, b) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
      const placed = [];
      L.labels.selectAll('*').remove();
      // cut-off labels at the plot edge, clear of points
      (S ? [] : [{ text: `ADI ${ADI_CUT}`, x: qx + 4, ys: [-8, ih - 8, 12], anchor: 'start' }, { text: `CV² ${CV2_CUT}`, x: iw - 2, ys: [qy - 8, qy + 10], anchor: 'end' }]).forEach((c) => {
        const best = c.ys.map((yy) => ({ yy, cost: obstacles.concat(placed).reduce((s2, o) => s2 + ov(labelBox({ x: c.x, y: yy, text: c.text, anchor: c.anchor, mono: true }), o), 0) })).sort((a, b) => a.cost - b.cost)[0];
        L.labels.append('text').attr('class', 'gnm-ref-label').attr('x', c.x).attr('y', best.yy).attr('dy', '0.32em').attr('text-anchor', c.anchor).text(c.text);
        placed.push(labelBox({ x: c.x, y: best.yy, text: c.text, anchor: c.anchor, mono: true }));
      });
      // quadrant names: pinned to a corner of their own quadrant (inset 8 px), the corner with the fewest points under it
      const Q = {
        smooth: { x0: 0, x1: qx, y0: qy, y1: ih }, erratic: { x0: 0, x1: qx, y0: 0, y1: qy },
        intermittent: { x0: qx, x1: iw, y0: qy, y1: ih }, lumpy: { x0: qx, x1: iw, y0: 0, y1: qy },
      };
      Object.entries(Q).forEach(([c, q]) => {
        const qn = S ? DC_SHORT[c] : c.toUpperCase();
        const text = `${qn} ${fmtInt(counts[c])}`;
        const cands = [
          { x: q.x0 + 8, y: q.y0 + 12, anchor: 'start' }, { x: q.x1 - 8, y: q.y0 + 12, anchor: 'end' },
          { x: q.x0 + 8, y: q.y1 - 10, anchor: 'start' }, { x: q.x1 - 8, y: q.y1 - 10, anchor: 'end' },
        ];
        const best = cands.map((cd, i) => {
          const box = labelBox({ ...cd, text, mono: true, width: text.length * 7.6 });
          return { cd, box, cost: obstacles.reduce((s2, o) => s2 + ov(box, o), 0) + placed.reduce((s2, o) => s2 + ov(box, o), 0) * 3 + Math.max(0, -box.x) * 50 + Math.max(0, box.x + box.width - iw) * 50 + i * 0.5 };
        }).sort((a, b) => a.cost - b.cost)[0];
        const t = L.labels.append('text').attr('class', 'pi-quad-t').attr('x', best.cd.x).attr('y', best.cd.y).attr('dy', '0.32em').attr('text-anchor', best.cd.anchor);
        t.append('tspan').text(qn);
        t.append('tspan').attr('class', 'pi-quad-n').attr('dx', 6).text(fmtInt(counts[c]));
        placed.push(best.box);
      });
      // one annotation: the selected system's top-risk PN, placed away from the point cloud (fades in after a change)
      L.annot.selectAll('*').interrupt().remove();
      const focus = pts.filter(sel).sort((a, b) => b.risk_score - a.risk_score)[0];
      if (focus) {
        const fx = px(focus), fy = py(focus);
        const title = focus.pn, sub = S ? (small ? 'top risk' : `top risk · ${dcName(focus.demand_class)}`) : small ? `top risk · ATA ${ata}` : `top risk in ATA ${ata} · ${dcLabel(focus.demand_class)}`;
        const bw = Math.max(title.length * 7.2, sub.length * 6.4) + 8, bh = 32;
        const cands = [];
        [28, 44, 64, 88].forEach((d) => [[1, -1], [1, 1], [-1, -1], [-1, 1], [1, 0], [-1, 0], [0, -1], [0, 1]].forEach(([sx, sy]) => cands.push({ sx, sy, d })));
        const box = (c) => { const ax = fx + c.sx * c.d, ay = fy + c.sy * c.d * 0.8; return { x: c.sx < 0 ? ax - bw : c.sx === 0 ? ax - bw / 2 : ax, y: ay - bh / 2, width: bw, height: bh, ax, ay }; };
        const best = cands.map((c, i) => { const b = box(c); return { c, b, cost: obstacles.reduce((s2, o) => s2 + ov(b, o), 0) + placed.reduce((s2, o) => s2 + ov(b, o), 0) * 3 + (Math.max(0, -b.x) + Math.max(0, b.x + b.width - iw) + Math.max(0, -b.y) + Math.max(0, b.y + b.height - ih)) * 60 + i * 0.4 }; }).sort((a, b) => a.cost - b.cost)[0];
        const b = best.b;
        const anchor = best.c.sx < 0 ? 'end' : best.c.sx === 0 ? 'middle' : 'start';
        const tx = anchor === 'end' ? b.x + b.width - 4 : anchor === 'middle' ? b.x + b.width / 2 : b.x + 4;
        const ex = Math.max(b.x, Math.min(fx, b.x + b.width)), ey = Math.max(b.y, Math.min(fy, b.y + b.height));
        const ag = L.annot.append('g').attr('class', 'gnm-annot');
        const ang = Math.atan2(ey - fy, ex - fx);
        ag.append('path').attr('class', 'gnm-annot-line').attr('d', `M${fx + Math.cos(ang) * 7},${fy + Math.sin(ang) * 7}L${ex},${ey}`);
        ag.append('circle').attr('cx', fx).attr('cy', fy).attr('r', 7).attr('fill', 'none').attr('stroke', theme.color.text).attr('stroke-width', 1.25);
        ag.append('text').attr('class', 'gnm-annot-text').attr('x', tx).attr('y', b.y + 11).attr('text-anchor', anchor).text(title);
        ag.append('text').attr('class', 'gnm-annot-sub').attr('x', tx).attr('y', b.y + 26).attr('text-anchor', anchor).text(sub);
        if (animate) txSel(ag.style('opacity', 0), { delay: 120 }).style('opacity', 1);
      }
      // each swatch + label is one nowrap item, so a swatch is never orphaned at a line end (wave 5)
      const item = (sw, t) => h('span', { class: 'pi-key-item' }, sw, t);
      keyEl.replaceChildren(item(h('span', { class: 'pi-key-dot is-sel' }), ata === 'all' ? 'All systems shown in neutral' : S ? `${sysName(ata)} parts` : `ATA ${ata} parts`), item(h('span', { class: 'pi-key-dot' }), `other ${PN(2)}`), item(h('span', { class: 'pi-key-sw' }), S ? 'needed only now and then' : `intermittent / lumpy zone (ADI ≥ ${ADI_CUT})`));
      drawIn(f.body, L.svg);
    }
    const stop = responsive(f.body, (w) => render(w, false));
    return { stop, update: () => { if (W) render(W, true); } };
  }

  // ------------------------------------------------------------------ ABC × demand class heatmap
  /** ABC × demand class heatmap: follows the fleet filter; cells are keyed (ABC|class), so counts and shading interpolate. */
  function drawHeatmap() {
    const dcs = DC_ORDER.filter((c) => parts.some((p) => p.demand_class === c));
    const abcs = ['A', 'B', 'C'].filter((a) => parts.some((p) => p.abc === a));
    const cellsOf = () => { const fp = parts.filter(inFleet); return abcs.flatMap((a) => dcs.map((c) => { const ps = fp.filter((p) => p.abc === a && p.demand_class === c); return { key: `${a}|${c}`, abc: a, dc: c, n: ps.length, value: ps.reduce((x, p) => x + (p.annual_usage_value_aed || 0), 0) }; })); };
    const topOf = (cells) => { const aCells = cells.filter((c) => c.abc === 'A'); return { nA: aCells.reduce((x, c) => x + c.n, 0), topA: aCells.slice().sort((x, y) => y.n - x.n)[0] }; };
    const headOf = (cells) => {
      const { nA, topA } = topOf(cells);
      return S ? (topA && nA ? `${fmtInt(topA.n)} of ${fmtInt(nA)} top-value parts are needed ${dcName(topA.dc)}${['intermittent', 'lumpy', 'erratic'].includes(topA.dc) ? ': costly parts are the hardest to forecast' : ''}` : 'Value class by how often parts are needed') : topA && nA ? (['intermittent', 'lumpy', 'erratic'].includes(topA.dc) ? `${fmtInt(topA.n)} of ${fmtInt(nA)} A-class PNs have ${dcLabel(topA.dc)} demand: costly items are the hardest to forecast` : `${fmtInt(topA.n)} of ${fmtInt(nA)} A-class PNs have ${dcLabel(topA.dc)} demand`) : 'ABC × demand class';
    };
    const cols = [{ key: 'abc', label: byMode('Value class', 'ABC') }, { key: 'dc', label: byMode('Needed', 'Demand class'), format: dcName }, { key: 'n', label: byMode('Parts', 'PNs'), num: true }];
    const cells0 = cellsOf();
    const f = chartFrame(heatCard, {
      implication: byMode('The costliest parts are the hardest to forecast, so they need the most planning care.', 'The costliest parts are the hardest to forecast, so they deserve the most planning attention.'),
      headline: headOf(cells0),
      subtitle: S ? `Number of parts. Value class A covers the parts behind the top 80% of yearly spend, B the next 15%, C the rest. Training weeks ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)}.` : `Count of PNs · ABC by annual usage value (A = top 80%, B = next 15%) · demand class from ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)}`,
      provenance: 'DERIVED', source: 'parts.json (abc, demand_class)',
      table: { columns: cols, rows: cells0 },
    });
    const ABBR = S ? { smooth: 'ST', erratic: 'UN', intermittent: 'NT', lumpy: 'BU', insufficient_data: '?' } : { smooth: 'S', erratic: 'E', intermittent: 'I', lumpy: 'L', insufficient_data: 'ID' };
    const HM_SIMPLE = { smooth: 'steady', erratic: 'uneven', intermittent: 'now & then', lumpy: 'in bursts', insufficient_data: 'too little data' };
    const hmName = (c) => (S ? HM_SIMPLE[c] : dcLabel(c));
    const hmKey = h('p', { class: 'pi-hm-key' }, dcs.map((c) => `${ABBR[c]} ${hmName(c)}`).join(' · '));
    f.body.after(hmKey);
    const cellTxt = (v) => (Math.round(v) ? fmtInt(v) : '·');
    let W = 0, L = null;
    function render(w, animate) {
      const cells = cellsOf();
      const { topA } = topOf(cells);
      const hl = f.root.querySelector('.chart-headline'); if (hl) hl.textContent = headOf(cells);
      if (animate) f.setTable(cols, cells);
      const small = w < 520;
      hmKey.hidden = !small;
      const labW = small ? 32 : 44, topH = 30, rowH = small ? 48 : 56, totW = small ? 40 : 48;
      const cw = (w - labW - totW) / dcs.length;
      const hgt = topH + abcs.length * rowH + 30;
      const max = Math.max(1, ...cells.map((c) => c.n));
      const op = window.d3.scaleLinear().domain([0, max]).range([0.04, 0.85]);
      const pos = (c) => [labW + dcs.indexOf(c.dc) * cw, topH + abcs.indexOf(c.abc) * rowH];
      if (w !== W || !L) {
        const svg = svgIn(f.body, w, hgt, 'ABC by demand class heatmap');
        dcs.forEach((c, i) => {
          const t = svg.append('text').attr('class', 'pi-hm-col').attr('x', labW + i * cw + cw / 2).attr('y', 18).attr('text-anchor', 'middle').text(small ? ABBR[c] : hmName(c));
          t.append('title').text(dcName(c));
        });
        svg.append('text').attr('class', 'pi-hm-col').attr('x', w - totW / 2).attr('y', 18).attr('text-anchor', 'middle').text('Σ');
        abcs.forEach((a, r) => svg.append('text').attr('class', 'pi-hm-row').attr('x', 8).attr('y', topH + r * rowH + rowH / 2).attr('dy', '0.32em').text(a));
        const cg = svg.append('g');
        // one keyed group per cell: the rect's shading and the count interpolate on a fleet change
        const gs = cg.selectAll('g').data(cells, (c) => c.key).join('g').attr('class', 'pi-hm-cell').attr('transform', (c) => `translate(${pos(c)[0]},${pos(c)[1]})`);
        gs.append('rect').attr('x', 2).attr('y', 2).attr('width', cw - 4).attr('height', rowH - 4).attr('rx', 6).attr('fill', theme.series.neutral).attr('stroke', theme.color.line);
        gs.append('text').attr('class', 'pi-hm-n').attr('x', cw / 2).attr('y', rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'middle').style('pointer-events', 'none');
        const tots = abcs.map((a, r) => svg.append('text').attr('class', 'pi-hm-tot').attr('x', w - totW / 2).attr('y', topH + r * rowH + rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'middle'));
        const ky = topH + abcs.length * rowH + 14;
        const kg = svg.append('g').attr('transform', `translate(${labW},${ky})`);
        [0.1, 0.3, 0.5, 0.7, 0.85].forEach((o, i) => kg.append('rect').attr('x', i * 18).attr('y', -6).attr('width', 16).attr('height', 10).attr('rx', 2).attr('fill', theme.series.neutral).attr('fill-opacity', o));
        const keyT = lab(kg, { x: 5 * 18 + 8, y: 0, text: '', color: theme.color.faint });
        const focus = svg.append('rect').attr('class', 'pi-hm-focus').attr('x', 1).attr('y', 1).attr('width', cw - 2).attr('height', rowH - 2).attr('rx', 7);
        L = { svg, cg, tots, keyT, focus };
        W = w; animate = false;
      }
      const T = (sel) => (animate ? txSel(sel) : sel);
      const gs = L.cg.selectAll('g.pi-hm-cell').data(cells, (c) => c.key);
      T(gs.select('rect')).attr('fill-opacity', (c) => (c.n ? op(c.n) : 0));
      gs.select('rect').each(function (c) { withTooltip(window.d3.select(this).datum(c), (d) => ({ title: `${d.abc} · ${dcName(d.dc)}`, rows: [[byMode('Parts', 'PNs'), fmtInt(d.n)]] })); });
      gs.select('text').attr('class', (c) => (c.n && op(c.n) > 0.5 ? 'pi-hm-n is-dark' : 'pi-hm-n')).each(function (c) { if (animate) tweenNumber(this, c.n, cellTxt); else { this.textContent = cellTxt(c.n); this.__num = c.n; } });
      L.tots.forEach((t, r) => { const v = cells.filter((c) => c.abc === abcs[r]).reduce((x, c) => x + c.n, 0); const n = t.node(); if (animate) tweenNumber(n, v, fmtInt); else { n.textContent = fmtInt(v); n.__num = v; } });
      L.keyT.text(small ? `fewer → more ${PN(2)} (max ${fmtInt(max)})` : `fewer → more ${PN(2)} (max ${fmtInt(max)} per cell)`);
      L.focus.style('display', topA ? null : 'none');
      if (topA) T(L.focus).attr('transform', `translate(${pos(topA)[0]},${pos(topA)[1]})`);
      drawIn(f.body, L.svg);
    }
    const stop = responsive(f.body, (w) => render(w, false));
    return { stop, update: () => { if (W) render(W, true); } };
  }

  // ------------------------------------------------------------------ planted situations
  function drawPlanted() {
    const pl = parts.filter((p) => p.planted).sort((a, b) => String(a.planted).localeCompare(String(b.planted)));
    plantedCard.replaceChildren(
      h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, byMode('Test cases built into the model', 'Planted situations · scenario design')), h('h3', { class: 'card-title' }, pl.length ? byMode(`${pl.length} parts hide a known problem the planning must find from history alone`, `${pl.length} PNs carry a planted situation the models must detect from history alone`) : 'No planted situations exported')), provChip('SIMULATED')),
      h('ul', { class: 'list-reset pi-planted-list' }, ...pl.map((p) => h('li', {}, h('button', { type: 'button', class: 'pi-planted-row', onclick: () => openPart(p.pn) },
        h('span', { class: 'chip chip-mono pi-planted' }, p.planted),
        h('span', { class: 'pi-planted-main' }, h('span', { class: 'mono' }, p.pn), h('span', { class: 'faint', title: p.desc }, p.desc)),
        riskPill(p), icon('chevron-right'))))),
      h('div', { class: 'card-foot' }, h('span', {}, byMode('Built into the simulation so the planning can be checked against a known answer. The planner sees only the past orders and repairs.', 'Planted in the simulator so the planning logic can be tested against a known answer. The planner sees only the demand and repair history.'))));
  }

  // ------------------------------------------------------------------ state changes
  async function setAta(a) {
    ata = a;
    const t = explorerCard.querySelector('.card-title'); if (t) t.textContent = explorerTitle();
    sysButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.ata === a)));
    allBtn.setAttribute('aria-pressed', String(a === 'all'));
    air.setActive(a === 'all' ? null : a);
    syncPressed();
    layoutAircraft();
    refreshTable();
    showPanel();
    matrix.update(); heat.update();
    ctx.setParams({ ata: a, pn: '' });
    await drawExploded();
  }
  async function setFleet(f) {
    fleet = f;
    const kk = explorerCard.querySelector('.card-kicker'); if (kk) kk.textContent = explorerKicker();
    const tt = explorerCard.querySelector('.card-title'); if (tt) tt.textContent = explorerTitle();
    ctx.setParams({ fleet: f === 'all' ? '' : f });
    // wave C: everything below the filter is recomputed from the filtered part set
    sysStat = computeSysStat(); worst = worstOf();
    sysButtons.forEach(fillSys);
    allBtn.querySelector('[data-role="all-label"]').textContent = allLabel();
    const lk = listCard.querySelector('.card-kicker'); if (lk) lk.textContent = listKicker();
    if (ata !== 'all') { ata = topSystem() || 'all'; sysButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.ata === ata))); ctx.setParams({ ata }); }
    if (tt) tt.textContent = explorerTitle();
    await buildAircraft();
    air?.setActive?.(ata === 'all' ? null : ata);
    syncPressed();
    layoutAircraft();
    refreshTable();
    showPanel();
    matrix.update(); heat.update();
    await drawExploded();
  }
  /** Side panel for the selected system: fleet-filtered exposure share, PN count, urgent exceptions, affected PNs. */
  const panelPrev = {};
  function showPanel() {
    const fp = parts.filter(inFleet);
    explorerCard.querySelector('.pi-fleet-note').textContent = `${fmtInt(fp.length)} of ${fmtInt(parts.length)} ${byMode('parts', 'part numbers')} apply to ${FLEET_LABEL[fleet].toLowerCase()}${fleet === 'WB' ? ' · widebody drawing' : ' · narrowbody drawing'}`;
    if (ata === 'all') {
      panelCard.replaceChildren(h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, 'Selected system'), h('h3', { class: 'card-title' }, 'Select a system on the aircraft or in the list'))),
        h('p', { class: 'muted t-14 m-0' }, byMode('The panel shows the system’s share of the risk, its parts, its urgent actions and the parts behind them.', 'The panel shows the system\'s share of material shortage exposure, its part numbers, urgent exceptions and the parts that drive them, for the selected fleet.')));
      return;
    }
    const sp = fp.filter((p) => p.ata === ata);
    const tot = fp.reduce((a, p) => a + (+p.risk_hours || 0), 0);
    const share = tot ? sp.reduce((a, p) => a + (+p.risk_hours || 0), 0) / tot : null;
    const exc = sp.flatMap((p) => (p.exceptions || []).map((e) => ({ ...e, pn: p.pn })));
    const urgentExc = exc.filter((e) => e.severity === 'urgent');
    const urgentPn = sp.filter((p) => p.risk_level === 'urgent');
    const top = sp.slice().sort((a, b) => (b.risk_hours || 0) - (a.risk_hours || 0)).slice(0, 6);
    // addendum: stat values count up once (first view), then interpolate from the previous selection's value
    const stat = (k, v, sub, id) => {
      const ve = h('div', { class: 'pi-pstat-v', dataset: { stat: id } });
      if (typeof v === 'number') { ve.__num = panelPrev[id] ?? null; tweenNumber(ve, v, id === 'share' ? (x) => fmtPct(x, 0) : fmtInt, { key: `parts-panel-${id}` }); panelPrev[id] = v; } else ve.textContent = v;
      return h('div', { class: 'pi-pstat' }, h('div', { class: 'pi-pstat-k' }, k), ve, sub ? h('div', { class: 'pi-pstat-s' }, sub) : null);
    };
    const firstUrgent = urgentExc[0] || exc[0];
    // A7: a part flagged for escalation (the hero part) leads the panel; A9: flagged outstation brake allocations follow
    const escParts = sp.filter((p) => p.escalation);
    const flagged = sp.flatMap((p) => p.allocation_flags || []);
    panelCard.replaceChildren(...[
      h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, `Selected system · ${FLEET_LABEL[fleet]}`), h('h3', { class: 'card-title' }, S ? [sysName(ata), ' ', h('span', { class: 'mono-tag pi-ata-tag' }, `ATA ${ata}`)] : `ATA ${ata} ${sysName(ata).toLowerCase()}`)), provChip(prov)),
      ...escParts.map((p) => escalationBlock(p, { onOpen: () => openPart(p.pn), compact: true })),
      h('div', { class: 'pi-pstats' },
        stat(byMode('Share of the risk', 'Shortage exposure share'), share == null ? '—' : share, `of the ${FLEET_LABEL[fleet].toLowerCase()} total`, 'share'),
        stat(byMode('Parts', 'Part numbers'), sp.length, `${fmtInt(urgentPn.length)} urgent`, 'parts'),
        stat(byMode('Urgent actions', 'Urgent exceptions'), urgentExc.length, `${fmtInt(exc.length)} open in all`, 'urgent')),
      scopeLine({ cls: 'pi-panel-scope' }),
      dataTable({ caption: S ? `Parts driving ${sysName(ata)}` : `Part numbers driving ATA ${ata}`, bare: true, dense: true, rowKey: 'pn', onRowClick: (r) => openPart(r.pn), rows: top, mobileColumns: ['pn', 'risk_score', 'desc'],
        columns: [{ key: 'pn', label: byMode('Part', 'PN'), mono: true }, { key: 'desc', label: byMode('Name', 'Description'), render: (r) => h('span', { class: 'pi-desc', title: r.desc }, r.desc) },
          { key: 'risk_score', label: 'Risk', num: true, render: (r) => h('span', { class: 'pi-risk-cell' }, riskPill(r), excChip(r)) }] }),
      flagged.length ? allocationFlagNote(flagged, { text: P.invalid_allocation_text, compact: true }) : null,
      h('div', { class: 'pi-panel-foot' },
        h('a', { class: 'btn btn--sm', href: firstUrgent ? ctx.buildHash('actions', { id: firstUrgent.exception_id }) : '#/actions' }, icon('inbox'), firstUrgent ? (S ? 'Open the first urgent action' : `Open ${firstUrgent.exception_id} in the Planner Action Centre`) : 'Open the Planner Action Centre'),
        h('span', { class: 't-12 faint' }, byMode('Share = this system’s expected grounded hours (past record plus model) over the fleet total.', 'Share = this system\'s material shortage exposure (AOG h/yr: history + modelled residual) over the fleet total.')))].filter(Boolean));
  }

  // ------------------------------------------------------------------ drill-down drawer
  let openDrawer = null;
  function openPart(pn) {
    const p = byPn.get(pn);
    if (!p) return null;
    openDrawer?.close?.();
    ctx.setParams({ pn });
    const series = DH.series?.[pn] || [];
    const all = demandStats(series);
    const tr = demandStats(series, 0, trainEnd);
    const body = h('div', { class: 'stack-3 pi-drawer' });
    const head = h('div', { class: 'row-wrap gap-1' },
      riskPill(p, `Risk ${riskPct(p.risk_score)}`), excChip(p),
      h('span', { class: 'chip' }, CLS_NAME[p.cls] || p.cls),
      h('span', { class: 'chip' }, S ? `needed ${dcName(p.demand_class)}` : dcLabel(p.demand_class)),
      h('span', { class: 'chip' }, `${byMode('Value class', 'ABC')} ${p.abc}`),
      provChip(p.provenance || prov));
    body.append(head);
    // A7: the escalation text leads the drawer for a flagged part (the hero part)
    if (p.escalation) body.append(escalationBlock(p, { first: true }));
    const ex = (p.exceptions || []).find((x) => x.severity === 'urgent' || x.severity === 'review');
    if (ex && p.risk_level !== ex.severity) {
      body.append(h('p', { class: 'pi-exc-note t-12 muted', role: 'note' }, icon('info'), h('span', {}, S
        ? `Risk ${riskPct(p.risk_score)} measures expected grounded hours. The ${ex.severity} ${ex.type_label.toLowerCase()} action is about planning data. So it ranks high in the Action Centre while the risk score stays low.`
        : `Risk ${riskPct(p.risk_score)} measures material shortage exposure (expected material-related downtime hours). The ${ex.severity} ${ex.type_label.toLowerCase()} action (${ex.exception_id}) is about planning data, so it ranks high on Mission and in the Action Centre while the risk score stays low.`)));
    }
    if (p.removal_mode === 'wear_planned' && P.brake_note) body.append(h('p', { class: 'pi-brake-note', role: 'note' }, icon('info'), h('span', {}, P.brake_note)));
    if (p.planted) {
      body.append(h('div', { class: 'pi-planted-banner', role: 'note' }, icon('target'), h('div', {}, h('strong', {}, S ? `Built-in test case ${p.planted}` : `Planted situation ${p.planted}`), h('p', { class: 'faint t-12' }, p.planted_note || byMode('A known problem built into the simulation. The planning must find it from history alone.', 'A scenario planted in the simulator for the planning logic to detect from history alone.')))));
    }
    const chartHost = h('div');
    body.append(chartHost);
    const fleetTxt = p.applicability === 'NB' ? 'Narrowbody' : p.applicability === 'WB' ? 'Widebody' : p.applicability ? 'Both fleets' : '—';
    const metaRows = S ? [
      ['Name', p.desc], ['Aircraft system', sysName(p.ata)], ['Type', `${CLS_NAME[p.cls] || p.cls} · fix within ${WINDOW_SIMPLE[p.deadline] || p.deadline} (assumed)`],
      ['Removal', p.removal_mode === 'wear_planned' ? 'Planned (wear), known 5–10 days ahead' : p.removal_mode ? 'Unplanned' : '—'], ['Fleet', fleetTxt],
      ['How often needed', dcName(p.demand_class)], ['Value class', p.abc], ['Unit cost', fmtAED(p.unit_cost)],
      ['Grounded hours risk', p.risk_hours != null ? `${fmtHours(p.risk_hours)} a year (past record plus model)` : riskPct(p.risk_score)],
      [`${planName} target (all airports)`, `${fmtInt(p.stock_total)} unit${p.stock_total === 1 ? '' : 's'}`],
    ] : [
      ['Description', p.desc], ['ATA', `${p.ata} · ${sysName(p.ata)}`], ['Class', `${CLS_NAME[p.cls] || p.cls} · rectification window ${p.deadline} (hypothetical)`], ['Removal', p.removal_mode === 'wear_planned' ? 'Planned (wear), known 5–10 days ahead' : p.removal_mode ? 'Unscheduled' : '—'], ['Fleet', fleetTxt],
      ['Demand class', `${dcLabel(p.demand_class)} · ADI ${fmtNum(p.adi)} · CV² ${fmtNum(p.cv2)}`], ['ABC', p.abc], ['Unit cost', fmtAED(p.unit_cost)],
      ['Material shortage exposure', p.risk_hours != null ? `${fmtHours(p.risk_hours)}/yr of AOG (history + modelled residual)` : riskPct(p.risk_score)],
      [`${P.stock_basis_id || 'Plan'} target (all stations)`, `${fmtInt(p.stock_total)} unit${p.stock_total === 1 ? '' : 's'}`],
    ];
    body.append(h('dl', { class: 'meta-list' }, ...[
      ...metaRows,
      // canonical per-PN AOG metrics, labelled exactly as on Mission and the Action Centre
      ...['aog_h_52w', 'aog_h_52w_max_station'].filter((k) => Number.isFinite(p[k])).map((k) => [P.aog_metric_labels?.[k]?.label || k, `${fmtInt(p[k])} h${k === 'aog_h_52w_max_station' && p.aog_h_52w_max_station_id ? ` (${p.aog_h_52w_max_station_id})` : ''}`]),
    ].flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)])), scopeLine());
    const st = Object.entries(p.stock_by_station || {});
    const maxSt = Math.max(1, ...st.map(([, q]) => q));
    // A9: outstation brake units in the frozen plan keep their numbers and carry the invalid-recommendation flag
    const basisId = P.stock_basis_id || 'P2';
    const flags = p.allocation_flags || [];
    body.append(h('div', { dataset: { role: 'stock-by-station' } },
      h('div', { class: 'card-kicker mb-1' }, S ? `Spares by airport · ${planName}` : `Stock by station · ${P.stock_basis_id || 'target'} allocation`),
      P.stock_basis ? h('p', { class: 'faint t-12 mb-1' }, S ? `Target spares in the ${planName}. For repairable parts this counts spares on the shelf, not parts away for repair.` : P.stock_basis) : null,
      h('ul', { class: 'list-reset pi-stock' }, ...st.map(([s, q]) => {
        const bad = flagsAt(flags, basisId, s);
        return h('li', { class: bad.length ? 'is-flagged' : '', dataset: bad.length ? { flag: 'invalid_recommendation' } : undefined },
          h('span', { class: 'mono' }, s), h('span', { class: 'pi-stock-bar', 'aria-hidden': 'true' }, h('span', { style: { width: `${(q / maxSt) * 100}%` }, class: q ? '' : 'is-zero' })), h('span', { class: 'mono num' }, fmtInt(q)),
          bad.length ? h('span', { class: 'pi-stock-flag', title: bad[0].text }, icon('alert'), 'invalid') : null);
      })),
      flags.length ? allocationFlagNote(flags, { text: P.invalid_allocation_text }) : null));
    const fq = new URLSearchParams({ class: p.demand_class, part: p.cls, pn }).toString();
    const foot = [h('a', { class: 'btn btn--sm', href: `#/forecast?${fq}` }, icon('flask'), 'See in Forecast Lab')];
    if (p.cls === 'R') foot.push(h('a', { class: 'btn btn--sm', href: `#/rotables?pn=${encodeURIComponent(pn)}` }, icon('rotable'), 'Open in Rotable & Repair'));
    const d = drawer({ kicker: S ? `Part number · ${sysName(p.ata)}` : `Part number · ATA ${p.ata}`, title: pn, body, foot,
      // F3 (wave 4): opened from a deep link there is no opener; Esc returns focus to the part's table row or its ATA hotspot
      returnFocus: () => [...document.querySelectorAll(`#view [data-story="parts-table"] [data-key="${pn}"]`)].find((e) => e.getClientRects().length) || document.querySelector(`#view .pi-sys[data-ata="${p.ata}"]`),
      onClose: () => { ctx.setParams({ pn: '' }); openDrawer = null; } }).open();
    openDrawer = d;
    requestAnimationFrame(() => {
      const f = chartFrame(chartHost, {
      implication: byMode('A part with long gaps between orders needs a choice of where to keep spares, not just when to reorder.', 'A part with long gaps between demands needs a positioning decision, not just a reorder point.'),
        headline: S ? (all.nz ? `Needed in ${fmtInt(all.nz)} of ${fmtInt(all.weeks)} weeks (${fmtInt(all.total)} unit${all.total === 1 ? '' : 's'}); ${fmtPct(tr.zeroShare, 0)} of training weeks had none` : `Not needed in ${fmtInt(all.weeks)} weeks`) : all.nz ? `Demand in ${fmtInt(all.nz)} of ${fmtInt(all.weeks)} weeks (${fmtInt(all.total)} unit${all.total === 1 ? '' : 's'}); ${fmtPct(tr.zeroShare, 0)} of training weeks are zero` : `No demand recorded in ${fmtInt(all.weeks)} weeks`,
        subtitle: S ? `Units needed per week, ${fmtWeek(weeks[0])}–${fmtWeek(weeks[1])}. Training weeks ${fmtWeek(0)}–${fmtWeek(trainEnd)}, then check weeks ${fmtWeek(selStart)}–${fmtWeek(weeks[1])}. Simulated calendar.` : `Units per week · ${fmtWeek(weeks[0])}–${fmtWeek(weeks[1])} · training ${fmtWeek(0)}–${fmtWeek(trainEnd)} | selection ${fmtWeek(selStart)}–${fmtWeek(weeks[1])} · simulated calendar`,
        provenance: DH.meta?.provenance || 'SIMULATED', source: 'demand_history.json',
        table: { columns: [{ key: 'x', label: 'Week', format: fmtWeek }, { key: 'y', label: 'Qty', num: true }], rows: series.map((y, x) => ({ x, y })).filter((r) => r.y > 0) },
      });
      f.root.dataset.story = 'parts-demand-strip';
      d._stop = demandStrip(f.body, series, { height: 170, splitAt: selStart, animate: true });
    });
    return d;
  }

  showPanel();
  await drawExploded();
  // during the guided tour keep the aircraft visible (the tour spotlights the ATA hotspot)
  if (pnParam && !document.querySelector('.story')) openPart(pnParam.pn);
  return () => { cleanups.forEach((c) => c?.()); openDrawer?._stop?.(); };
}
