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
import { h, icon, pageHead, card, provChip, pill, segmented, dataTable, drawer, inlineSVG, fillExploded, blueprintAircraft } from '../ui.js';
import { chartFrame, responsive, svgIn, axisBottom, axisLeft, theme, annotate, withTooltip, directLabel, refLine, markerRect, labelBox, fmtAED, fmtHours, fmtInt, fmtNum, fmtPct, fmtWeek } from '../charts/theme.js';
import { assetURL } from '../data.js';
import { demandStrip, demandStats } from './parts-intelligence/strip.js';

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
const CLS_NAME = { R: 'Rotable', E: 'Expendable', C: 'Consumable' };
export const dcLabel = (c) => String(c || 'unclassified').replace('_', ' ');
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
  const sysStat = Object.fromEntries(ATAS.map((a) => {
    const ps = parts.filter((p) => p.ata === a);
    const lvl = ps.reduce((m, p) => ((LEVEL[p.risk_level]?.rank || 0) > (LEVEL[m]?.rank || 0) ? p.risk_level : m), 'unknown');
    const top = ps.slice().sort((x, y) => y.risk_score - x.risk_score)[0];
    return [a, { ata: a, name: sysName(a), n: ps.length, urgent: ps.filter((p) => p.risk_level === 'urgent').length, review: ps.filter((p) => p.risk_level === 'review').length, level: sysRisk.get(a)?.system_level || sysRisk.get(a)?.risk_level || (ps.length ? lvl : 'unknown'),
      // display status (exporter): the system level, raised to WATCH when an OK chapter holds an urgent part
      tone: sysRisk.get(a)?.status || sysRisk.get(a)?.system_level || sysRisk.get(a)?.risk_level || (ps.length ? lvl : 'unknown'),
      word: String(sysRisk.get(a)?.status_label || '').split(' · ')[0] || null, share: sysRisk.get(a)?.risk_share, top, max: top?.risk_score }];
  }));

  let ata = ctx.params.ata === 'all' ? 'all' : ATAS.includes(ctx.params.ata) ? ctx.params.ata : null;
  const pnParam = byPn.get(ctx.params.pn);
  if (!ata) ata = pnParam && ATAS.includes(pnParam.ata) ? pnParam.ata : ATAS.slice().sort((a, b) => (sysStat[b].max || 0) - (sysStat[a].max || 0))[0];
  let cls = ['C', 'E', 'R'].includes(ctx.params.cls) ? ctx.params.cls : 'all';
  let query = '';

  // ------------------------------------------------------------------ header
  const nUrgent = parts.filter((p) => p.risk_level === 'urgent').length;
  const nIntermittent = parts.filter((p) => ['intermittent', 'lumpy'].includes(p.demand_class)).length;
  el.append(pageHead({
    num: '02', eyebrow: 'Parts Intelligence', title: 'Where the grounding risk sits on the aircraft',
    lede: `${fmtInt(parts.length)} fictional part numbers for Falcon Hub Airways (fictional), mapped to their ATA chapter. ${fmtInt(nIntermittent)} have intermittent or lumpy demand and ${fmtInt(nUrgent)} carry an urgent grounding-risk score. Select a system on the aircraft or in the list.`,
    meta: [provChip(prov), h('span', { class: 'chip' }, `${fmtInt(parts.length)} PNs`), h('span', { class: 'chip' }, `${(P.ata_systems || []).length} ATA chapters`)],
  }));

  // ------------------------------------------------------------------ explorer: aircraft + list
  const worst = ATAS.map((a) => sysStat[a]).sort((a, b) => (LEVEL[b.level].rank - LEVEL[a.level].rank) || ((b.share ?? 0) - (a.share ?? 0)) || b.urgent - a.urgent || (b.max || 0) - (a.max || 0))[0];
  const airHost = h('div', { class: 'pi-aircraft' });
  // phones: the selected system's top-part callout is an HTML line under the drawing (no room between badges)
  const airNote = h('div', { class: 'pi-air-note', hidden: true });
  const legend = h('div', { class: 'pi-legend', 'aria-hidden': 'true' }, ...['urgent', 'review', 'ok'].map((l) => h('span', { class: `pi-legend-item is-${l}` }, h('b', {}, LEVEL[l].glyph), l === 'review' ? 'Review / watch' : LEVEL[l].text)), h('span', { class: 'pi-legend-item is-pip' }, h('b', { class: 'pi-legend-pip' }, 'n'), 'urgent PNs in system'), h('span', { class: 'faint' }, 'Badge = system share of fleet risk-hours · WATCH = OK system holding an urgent part'));
  const explorerCard = card({
    cls: 'span-7 md-span-12 pi-explorer', bp: true, prov,
    kicker: 'Aircraft system explorer · plan view · generic twin, fictional',
    title: explorerTitle(),
    // the story hook wraps the drawing AND the phone's top-part line, so story step 2 frames the part on phones too (wave 5)
    body: [h('div', { class: 'pi-air-wrap', 'data-story': 'aircraft' }, airHost, airNote), legend],
  });
  /** F8 (wave 4): the headline follows the selected ATA; with "All" (or nothing selected) it names the riskiest system. */
  function explorerTitle() {
    const s = ata && ata !== 'all' ? sysStat[ata] : null;
    if (s) return `ATA ${s.ata} ${s.name.toLowerCase()}: ${s.share != null ? `${fmtPct(s.share, 0)} of fleet risk-hours, ` : ''}${fmtInt(s.urgent)} urgent of ${fmtInt(s.n)} PNs${worst && worst.ata === s.ata ? ', the most of any system' : ''}`;
    return worst ? `ATA ${worst.ata} ${worst.name.toLowerCase()} carries the most risk: ${worst.share != null ? fmtPct(worst.share, 0) + ' of fleet risk-hours, ' : ''}${worst.urgent} urgent of ${worst.n} PNs` : 'No risk scores exported';
  }

  const sysList = h('ul', { class: 'pi-syslist list-reset', role: 'list', 'aria-label': 'ATA systems (list alternative to the aircraft diagram)' });
  const sysButtons = ATAS.map((a) => {
    const s = sysStat[a];
    const b = h('button', { type: 'button', class: `pi-sys is-${s.tone}`, 'aria-pressed': String(a === ata), dataset: { ata: a }, onclick: () => setAta(a) },
      h('span', { class: 'pi-sys-ata mono' }, a),
      h('span', { class: 'pi-sys-main' }, h('span', { class: 'pi-sys-name' }, s.name), h('span', { class: 'pi-sys-meta mono' }, `${fmtInt(s.n)} PNs · top risk ${riskPct(s.max)}`)),
      // system level and urgent PARTS are separate facts: never a bare OK pill beside an urgent count
      h('span', { class: 'pi-sys-status' },
        pill(LEVEL[s.tone] && s.tone !== 'unknown' ? s.tone : 'unknown', s.word || LEVEL[s.level]?.text || LEVEL.unknown.text),
        s.urgent ? h('span', { class: 'pi-sys-urg mono', title: 'Part numbers in this chapter at the urgent part-level band' }, `▲ ${fmtInt(s.urgent)} urgent PN${s.urgent === 1 ? '' : 's'}`) : null));
    sysList.append(h('li', {}, b));
    return b;
  });
  const allBtn = h('button', { type: 'button', class: 'btn btn--sm', 'aria-pressed': String(ata === 'all'), onclick: () => setAta('all') }, icon('layers'), `All ${fmtInt(parts.length)} PNs`);
  const listCard = card({ cls: 'span-5 md-span-12', kicker: 'Systems · list view', title: 'Select an ATA chapter', prov: 'DERIVED', actions: allBtn, body: sysList, foot: h('span', {}, `${P.system_risk_bands_share ? `System level: urgent if the chapter holds ≥ ${fmtPct(P.system_risk_bands_share.urgent, 0)} of fleet risk-hours, review ≥ ${fmtPct(P.system_risk_bands_share.review, 0)}. ` : ''}${P.risk_bands_h ? `Part level: urgent ≥ ${fmtInt(P.risk_bands_h.urgent)} AOG h/yr, review ≥ ${fmtInt(P.risk_bands_h.review)} (assumed bands). ` : ''}Risk score 0–100 is log-scaled AOG hours. ${parts.filter((p) => !ATAS.includes(p.ata)).length} PNs sit in other chapters (see “All”).`) });

  el.append(h('div', { class: 'grid-12' }, explorerCard, listCard));

  // ------------------------------------------------------------------ exploded view + demand matrix
  const figHost = h('div', { class: 'bp-figure pi-exploded' });
  const slotKey = h('ol', { class: 'pi-slotkey list-reset' });
  const explodedTitle = h('h3', { class: 'card-title' });
  const explodedCard = card({ cls: 'span-6 md-span-12', prov, kicker: 'Exploded schematic · fictional components', body: [explodedTitle, figHost, slotKey] });
  const matrixCard = h('section', { class: 'card span-6 md-span-12' });
  el.append(h('div', { class: 'grid-12 mt-3' }, explodedCard, matrixCard));

  // ------------------------------------------------------------------ parts table
  const search = h('input', { class: 'input pi-search', type: 'search', placeholder: 'Search PN or description', 'aria-label': 'Search parts by PN or description', oninput: (e) => { query = e.target.value.trim().toLowerCase(); refreshTable(); } });
  const clsSeg = segmented({ label: 'Part class', value: cls, options: [{ value: 'all', label: 'All' }, { value: 'R', label: 'Rotable' }, { value: 'E', label: 'Expendable' }, { value: 'C', label: 'Consumable' }], onChange: (v) => { cls = v; refreshTable(); ctx.setParams({ cls: v === 'all' ? '' : v }); } });
  const columns = [
    { key: 'pn', label: 'Part number', mono: true, render: (r) => h('span', { class: 'pi-pn' }, h('span', { class: 'mono' }, r.pn), r.planted ? h('span', { class: 'chip chip-mono pi-planted', title: 'Planted situation (a scenario the models should detect)' }, r.planted) : null) },
    { key: 'desc', label: 'Description', render: (r) => h('span', { class: 'pi-desc', title: r.desc }, r.desc) },
    { key: 'cls', label: 'Class', render: (r) => h('span', { class: `pi-cls pi-cls--${r.cls}`, title: CLS_NAME[r.cls] }, r.cls) },
    { key: 'deadline', label: 'Deadline', mono: true },
    { key: 'demand_class', label: 'Demand', format: (v) => dcLabel(v) },
    { key: 'abc', label: 'ABC', mono: true },
    // C7 (wave 4): this is the recommended plan's target (all stations), not on-hand stock
    { key: 'stock_total', label: `${P.stock_basis_id || 'Plan'} target`, short: `${P.stock_basis_id || 'Plan'} target`, num: true, format: fmtInt },
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
    return h('span', { class: `chip pi-exc pi-exc--${e.severity}`, title: `${e.type_label} · ${e.severity} planner action (${e.exception_id} at ${e.station}). Risk scores grounding exposure; this action is about planning data.` }, icon(e.severity === 'urgent' ? 'alert' : 'clock'), `${e.type_label} · ${e.severity}`);
  }
  function riskTitle(r) {
    return `${r.risk_hours != null ? `${fmtHours(r.risk_hours)}/yr of AOG = ${fmtHours(r.aog_hours_hist_per_yr)} history + ${fmtNum(r.residual_aog_h_per_yr, 1)} h modelled residual. ` : ''}Score = ln(1 + AOG h) / ln(1 + fleet max), × 100.`;
  }
  const rowsFor = () => parts.filter((p) => (ata === 'all' || p.ata === ata) && (cls === 'all' || p.cls === cls) && (!query || p.pn.toLowerCase().includes(query) || String(p.desc).toLowerCase().includes(query)));
  const table = dataTable({ columns, rows: rowsFor(), sort: { key: 'risk_score', dir: 'desc' }, onRowClick: (r) => openPart(r.pn), rowKey: 'pn', caption: 'Parts for the selected ATA system', maxHeight: 520, mobileColumns: ['pn', 'risk_score', 'stock_total', 'desc'], stickyFirst: true });
  const tableCount = h('span', { class: 'chip' });
  const tableTitle = h('h3', { class: 'card-title' });
  const tableCard = h('section', { class: 'card span-12', dataset: { story: 'parts-table' } },
    h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, 'Part master · demand class · stock · risk'), tableTitle), h('div', { class: 'row-wrap gap-1' }, tableCount, provChip(prov))),
    h('div', { class: 'pi-toolbar' }, search, clsSeg),
    table,
    h('div', { class: 'card-foot' }, h('span', {}, 'Deadline classes D0 / D3 / D10 are hypothetical rectification windows, not MEL categories. Demand class from training weeks only. Click a row for the drill-down.')));
  el.append(h('div', { class: 'grid-12 mt-3' }, tableCard));
  function refreshTable() {
    const rows = rowsFor();
    table.update(rows);
    tableCount.textContent = `${fmtInt(rows.length)} PNs`;
    tableTitle.textContent = ata === 'all' ? 'All part numbers' : `ATA ${ata} · ${sysName(ata)}`;
  }
  refreshTable();

  // ------------------------------------------------------------------ ABC × demand class heatmap + planted
  const heatCard = h('section', { class: 'card span-7 md-span-12' });
  const plantedCard = h('section', { class: 'card span-5 md-span-12' });
  el.append(h('div', { class: 'grid-12 mt-3' }, heatCard, plantedCard));

  const cleanups = [];
  cleanups.push(drawMatrix());
  cleanups.push(drawHeatmap());
  drawPlanted();

  // ------------------------------------------------------------------ aircraft
  const air = await blueprintAircraft(airHost, { active: ata === 'all' ? null : ata, onSelect: (a) => setAta(a), compactBelow: 1e6, label: 'Plan view of a generic twin-engine aircraft (fictional) with ATA system hotspots' });
  decorateAircraft(air.svg);
  const airRO = new ResizeObserver(() => requestAnimationFrame(layoutAircraft));
  airRO.observe(airHost);
  cleanups.push(air.destroy, () => airRO.disconnect());

  /**
   * Hotspot decoration. Badge colour + word = SYSTEM level (chapter share of fleet risk-hours). A red pip with a
   * count marks every system that contains urgent PART numbers, so a "review" chapter holding an urgent part never
   * reads as calm, and the selected system gets a part-level callout for its top-risk PN. All text is sized in
   * screen pixels (≥ 11 px) by layoutAircraft(), not by the viewBox scale.
   */
  function decorateAircraft(svg) {
    svg.querySelectorAll('.ata-hotspot').forEach((g) => {
      const s = sysStat[g.dataset.ata];
      if (!s) return;
      g.classList.add(`risk-${LEVEL[s.tone] ? s.tone : s.level}`);
      g.dataset.story = `parts-hotspot-${s.ata}`;
      g.setAttribute('aria-label', `ATA ${s.ata} ${s.name}: ${s.word || LEVEL[s.level].text} (system level ${LEVEL[s.level].text}). ${s.n} part numbers, ${s.urgent} urgent${s.top ? `; top part ${s.top.pn}, risk ${riskPct(s.top.risk_score)} (${LEVEL[s.top.risk_level]?.text || s.top.risk_level})` : ''}.`);
      const badge = g.querySelector('.hs-badge');
      const c = badge?.querySelector('circle');
      if (!c) return;
      const cx = +c.getAttribute('cx'), cy = +c.getAttribute('cy');
      g._hs = { cx, cy };
      c.before(svgEl('circle', { cx, cy, r: 19, class: 'hs-pulse' }));
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
      g.querySelectorAll('.hs-badge > circle, .hs-pulse').forEach((c) => c.setAttribute('r', R));
      const num = g.querySelector('.hs-badge > text:not(.hs-risk)');
      if (num) num.style.fontSize = `${Math.max(17, 12 * u)}px`;
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
    const top = sysStat[ata]?.top;
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
      explodedTitle.textContent = 'Select a system to see its exploded view';
      figHost.replaceChildren(h('div', { class: 'state' }, icon('layers'), h('p', {}, 'The exploded schematic shows one ATA chapter at a time.')));
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
    figHost.replaceChildren(h('div', { class: 'pi-exploded-stage' }, svg, overlay), h('p', { class: 'pi-exploded-cap' }, 'Schematic · not engineering data'));
    const matched = labels.filter((l) => l.pn);
    explodedTitle.textContent = `ATA ${ata} · ${sysName(ata)}: ${matched.length} of ${ps.length} PNs drawn`;
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
  function drawMatrix() {
    matrixCard.replaceChildren();
    const pts = parts.filter((p) => Number.isFinite(p.adi) && Number.isFinite(p.cv2) && p.demand_class !== 'insufficient_data');
    const nIns = parts.length - pts.length;
    const counts = Object.fromEntries(['smooth', 'erratic', 'intermittent', 'lumpy'].map((c) => [c, pts.filter((p) => p.demand_class === c).length]));
    const sparse = counts.intermittent + counts.lumpy;
    const f = chartFrame(matrixCard, {
      headline: sparse * 2 > pts.length ? `Most PNs demand rarely: ${fmtInt(sparse)} of ${fmtInt(pts.length)} are intermittent or lumpy` : `${fmtInt(sparse)} of ${fmtInt(pts.length)} classified PNs are intermittent or lumpy`,
      subtitle: `ADI (weeks between demands, log) × CV² of demand sizes · training weeks ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)} · Syntetos–Boylan cut-offs ${ADI_CUT} / ${CV2_CUT}${nIns ? ` · ${nIns} PNs with < 3 demands not plotted` : ''}`,
      provenance: 'DERIVED', source: 'parts.json (adi, cv2, demand_class)', story: 'parts-adi-matrix',
      table: { columns: [{ key: 'pn', label: 'PN', mono: true }, { key: 'adi', label: 'ADI', num: true, format: (v) => fmtNum(v) }, { key: 'cv2', label: 'CV²', num: true, format: (v) => fmtNum(v) }, { key: 'demand_class', label: 'Class', format: dcLabel }], rows: pts },
    });
    const keyEl = h('div', { class: 'pi-matrix-key' });
    f.body.after(keyEl);
    const stop = responsive(f.body, (w) => {
      const small = w < 480;
      const hgt = small ? 300 : 340;
      const m = { top: 20, right: 16, bottom: 36, left: 44 };
      const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
      const svg = svgIn(f.body, w, hgt, 'ADI versus CV squared scatter');
      const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
      const d3 = window.d3;
      const xMax = Math.max(ADI_CUT * 3, d3.max(pts, (p) => p.adi) * 1.15);
      const yMax = Math.max(CV2_CUT * 2.2, d3.max(pts, (p) => p.cv2) * 1.1);
      const x = d3.scaleLog().domain([1, xMax]).range([0, iw]);
      const y = d3.scaleLinear().domain([0, yMax]).nice().range([ih, 0]);
      // quadrants + Syntetos–Boylan cut-offs (reference lines, not amber: amber = review status)
      const qx = x(ADI_CUT), qy = y(CV2_CUT);
      g.append('rect').attr('class', 'pi-quad pi-quad--sparse').attr('x', qx).attr('y', 0).attr('width', iw - qx).attr('height', ih);
      axisBottom(g.append('g'), x, { height: ih, format: (v) => (Number.isInteger(v) && [1, 2, 5, 10, 20, 50, 100].includes(v) ? v : '') });
      axisLeft(g.append('g'), y, { ticks: 4, format: (v) => fmtNum(v, 1) });
      refLine(g, { x1: qx, y1: 0, x2: qx, y2: ih });
      refLine(g, { x1: 0, y1: qy, x2: iw, y2: qy });
      g.append('text').attr('class', 'pi-axis-t').attr('x', iw).attr('y', ih + 30).attr('text-anchor', 'end').text('ADI · weeks between demands →');
      g.append('text').attr('class', 'pi-axis-t').attr('x', -m.left + 2).attr('y', -2).text('CV² ↑');
      const sel = (p) => ata !== 'all' && p.ata === ata;
      const ordered = pts.slice().sort((a, b) => sel(a) - sel(b));
      const px = (p) => x(Math.min(p.adi, xMax)), py = (p) => y(Math.min(p.cv2, yMax));
      const dots = g.append('g').selectAll('circle').data(ordered).join('circle')
        .attr('cx', px).attr('cy', py)
        .attr('r', (p) => (sel(p) ? 5 : 3.5))
        .attr('class', (p) => `pi-dot${sel(p) ? ' is-sel' : ''}${p.pn === ctx.params.pn ? ' is-pn' : ''}`)
        .attr('tabindex', (p) => (sel(p) ? 0 : null))
        .attr('role', (p) => (sel(p) ? 'button' : null))
        .attr('aria-label', (p) => (sel(p) ? `${p.pn} ${dcLabel(p.demand_class)}, ADI ${fmtNum(p.adi)}, CV² ${fmtNum(p.cv2)}` : null))
        .style('cursor', 'pointer')
        .on('click', (e, p) => openPart(p.pn))
        .on('keydown', (e, p) => { if (e.key === 'Enter') openPart(p.pn); });
      withTooltip(dots, (p) => ({ title: p.pn, rows: [['Description', p.desc], ['ADI', fmtNum(p.adi)], ['CV²', fmtNum(p.cv2)], ['Class', dcLabel(p.demand_class)], ['Risk', riskPct(p.risk_score)]] }));
      const obstacles = ordered.map((p) => markerRect(px(p), py(p), sel(p) ? 5 : 3.5, 1));
      const ov = (a, b) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
      const placed = [];
      // cut-off labels at the plot edge, clear of points
      [{ text: `ADI ${ADI_CUT}`, x: qx + 4, ys: [-8, ih - 8, 12], anchor: 'start' }, { text: `CV² ${CV2_CUT}`, x: iw - 2, ys: [qy - 8, qy + 10], anchor: 'end' }].forEach((c) => {
        const best = c.ys.map((yy) => ({ yy, cost: obstacles.concat(placed).reduce((s2, o) => s2 + ov(labelBox({ x: c.x, y: yy, text: c.text, anchor: c.anchor, mono: true }), o), 0) })).sort((a, b) => a.cost - b.cost)[0];
        g.append('text').attr('class', 'gnm-ref-label').attr('x', c.x).attr('y', best.yy).attr('dy', '0.32em').attr('text-anchor', c.anchor).text(c.text);
        placed.push(labelBox({ x: c.x, y: best.yy, text: c.text, anchor: c.anchor, mono: true }));
      });
      // quadrant names: pinned to a corner of their own quadrant (inset 8 px), the corner with the fewest points under it
      const Q = {
        smooth: { x0: 0, x1: qx, y0: qy, y1: ih }, erratic: { x0: 0, x1: qx, y0: 0, y1: qy },
        intermittent: { x0: qx, x1: iw, y0: qy, y1: ih }, lumpy: { x0: qx, x1: iw, y0: 0, y1: qy },
      };
      Object.entries(Q).forEach(([c, q]) => {
        const text = `${c.toUpperCase()} ${fmtInt(counts[c])}`;
        const cands = [
          { x: q.x0 + 8, y: q.y0 + 12, anchor: 'start' }, { x: q.x1 - 8, y: q.y0 + 12, anchor: 'end' },
          { x: q.x0 + 8, y: q.y1 - 10, anchor: 'start' }, { x: q.x1 - 8, y: q.y1 - 10, anchor: 'end' },
        ];
        const best = cands.map((cd, i) => {
          const box = labelBox({ ...cd, text, mono: true, width: text.length * 7.6 });
          return { cd, box, cost: obstacles.reduce((s2, o) => s2 + ov(box, o), 0) + placed.reduce((s2, o) => s2 + ov(box, o), 0) * 3 + Math.max(0, -box.x) * 50 + Math.max(0, box.x + box.width - iw) * 50 + i * 0.5 };
        }).sort((a, b) => a.cost - b.cost)[0];
        const t = g.append('text').attr('class', 'pi-quad-t').attr('x', best.cd.x).attr('y', best.cd.y).attr('dy', '0.32em').attr('text-anchor', best.cd.anchor);
        t.append('tspan').text(c.toUpperCase());
        t.append('tspan').attr('class', 'pi-quad-n').attr('dx', 6).text(fmtInt(counts[c]));
        placed.push(best.box);
      });
      // one annotation: the selected system's top-risk PN, placed away from the point cloud
      const focus = pts.filter(sel).sort((a, b) => b.risk_score - a.risk_score)[0];
      if (focus) {
        const fx = px(focus), fy = py(focus);
        const title = focus.pn, sub = small ? `top risk · ATA ${ata}` : `top risk in ATA ${ata} · ${dcLabel(focus.demand_class)}`;
        const bw = Math.max(title.length * 7.2, sub.length * 6.4) + 8, bh = 32;
        const cands = [];
        [28, 44, 64, 88].forEach((d) => [[1, -1], [1, 1], [-1, -1], [-1, 1], [1, 0], [-1, 0], [0, -1], [0, 1]].forEach(([sx, sy]) => cands.push({ sx, sy, d })));
        const box = (c) => { const ax = fx + c.sx * c.d, ay = fy + c.sy * c.d * 0.8; return { x: c.sx < 0 ? ax - bw : c.sx === 0 ? ax - bw / 2 : ax, y: ay - bh / 2, width: bw, height: bh, ax, ay }; };
        const best = cands.map((c, i) => { const b = box(c); return { c, b, cost: obstacles.reduce((s2, o) => s2 + ov(b, o), 0) + placed.reduce((s2, o) => s2 + ov(b, o), 0) * 3 + (Math.max(0, -b.x) + Math.max(0, b.x + b.width - iw) + Math.max(0, -b.y) + Math.max(0, b.y + b.height - ih)) * 60 + i * 0.4 }; }).sort((a, b) => a.cost - b.cost)[0];
        const b = best.b;
        const anchor = best.c.sx < 0 ? 'end' : best.c.sx === 0 ? 'middle' : 'start';
        const tx = anchor === 'end' ? b.x + b.width - 4 : anchor === 'middle' ? b.x + b.width / 2 : b.x + 4;
        const ex = Math.max(b.x, Math.min(fx, b.x + b.width)), ey = Math.max(b.y, Math.min(fy, b.y + b.height));
        const ag = g.append('g').attr('class', 'gnm-annot');
        const ang = Math.atan2(ey - fy, ex - fx);
        ag.append('path').attr('class', 'gnm-annot-line').attr('d', `M${fx + Math.cos(ang) * 7},${fy + Math.sin(ang) * 7}L${ex},${ey}`);
        ag.append('circle').attr('cx', fx).attr('cy', fy).attr('r', 7).attr('fill', 'none').attr('stroke', theme.color.text).attr('stroke-width', 1.25);
        ag.append('text').attr('class', 'gnm-annot-text').attr('x', tx).attr('y', b.y + 11).attr('text-anchor', anchor).text(title);
        ag.append('text').attr('class', 'gnm-annot-sub').attr('x', tx).attr('y', b.y + 26).attr('text-anchor', anchor).text(sub);
      }
    });
    // each swatch + label is one nowrap item, so a swatch is never orphaned at a line end (wave 5)
    const item = (sw, t) => h('span', { class: 'pi-key-item' }, sw, t);
    keyEl.replaceChildren(item(h('span', { class: 'pi-key-dot is-sel' }), ata === 'all' ? 'All systems shown in neutral' : `ATA ${ata} parts`), item(h('span', { class: 'pi-key-dot' }), 'other PNs'), item(h('span', { class: 'pi-key-sw' }), `intermittent / lumpy zone (ADI ≥ ${ADI_CUT})`));
    return stop;
  }

  // ------------------------------------------------------------------ ABC × demand class heatmap
  function drawHeatmap() {
    const dcs = DC_ORDER.filter((c) => parts.some((p) => p.demand_class === c));
    const abcs = ['A', 'B', 'C'].filter((a) => parts.some((p) => p.abc === a));
    const cells = abcs.flatMap((a) => dcs.map((c) => ({ abc: a, dc: c, n: parts.filter((p) => p.abc === a && p.demand_class === c).length, value: parts.filter((p) => p.abc === a && p.demand_class === c).reduce((s, p) => s + (p.annual_usage_value_aed || 0), 0) })));
    const aCells = cells.filter((c) => c.abc === 'A');
    const nA = aCells.reduce((s, c) => s + c.n, 0);
    const topA = aCells.slice().sort((a, b) => b.n - a.n)[0];
    const f = chartFrame(heatCard, {
      headline: topA && nA ? (['intermittent', 'lumpy', 'erratic'].includes(topA.dc) ? `${fmtInt(topA.n)} of ${fmtInt(nA)} A-class PNs have ${dcLabel(topA.dc)} demand: costly items are the hardest to forecast` : `${fmtInt(topA.n)} of ${fmtInt(nA)} A-class PNs have ${dcLabel(topA.dc)} demand`) : 'ABC × demand class',
      subtitle: `Count of PNs · ABC by annual usage value (A = top 80%, B = next 15%) · demand class from ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)}`,
      provenance: 'DERIVED', source: 'parts.json (abc, demand_class)',
      table: { columns: [{ key: 'abc', label: 'ABC' }, { key: 'dc', label: 'Demand class', format: dcLabel }, { key: 'n', label: 'PNs', num: true }], rows: cells },
    });
    const ABBR = { smooth: 'S', erratic: 'E', intermittent: 'I', lumpy: 'L', insufficient_data: 'ID' };
    const hmKey = h('p', { class: 'pi-hm-key' }, dcs.map((c) => `${ABBR[c]} ${dcLabel(c)}`).join(' · '));
    f.body.after(hmKey);
    return responsive(f.body, (w) => {
      const small = w < 520;
      hmKey.hidden = !small;
      const labW = small ? 32 : 44, topH = 30, rowH = small ? 48 : 56, totW = small ? 40 : 48;
      const cw = (w - labW - totW) / dcs.length;
      const hgt = topH + abcs.length * rowH + 30;
      const svg = svgIn(f.body, w, hgt, 'ABC by demand class heatmap');
      const max = Math.max(1, ...cells.map((c) => c.n));
      const op = window.d3.scaleLinear().domain([0, max]).range([0.04, 0.85]);
      dcs.forEach((c, i) => {
        const t = svg.append('text').attr('class', 'pi-hm-col').attr('x', labW + i * cw + cw / 2).attr('y', 18).attr('text-anchor', 'middle').text(small ? ABBR[c] : dcLabel(c));
        t.append('title').text(dcLabel(c));
      });
      svg.append('text').attr('class', 'pi-hm-col').attr('x', w - totW / 2).attr('y', 18).attr('text-anchor', 'middle').text('Σ');
      abcs.forEach((a, r) => {
        const yy = topH + r * rowH;
        svg.append('text').attr('class', 'pi-hm-row').attr('x', 8).attr('y', yy + rowH / 2).attr('dy', '0.32em').text(a);
        dcs.forEach((c, i) => {
          const cell = cells.find((x) => x.abc === a && x.dc === c);
          const gx = labW + i * cw;
          const rect = svg.append('rect').attr('x', gx + 2).attr('y', yy + 2).attr('width', cw - 4).attr('height', rowH - 4).attr('rx', 6).attr('fill', theme.series.neutral).attr('fill-opacity', cell.n ? op(cell.n) : 0).attr('stroke', theme.color.line);
          withTooltip(rect.datum(cell), (d) => ({ title: `${d.abc} · ${dcLabel(d.dc)}`, rows: [['PNs', fmtInt(d.n)]] }));
          svg.append('text').attr('class', cell.n && op(cell.n) > 0.5 ? 'pi-hm-n is-dark' : 'pi-hm-n').attr('x', gx + cw / 2).attr('y', yy + rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'middle').style('pointer-events', 'none').text(cell.n ? fmtInt(cell.n) : '·');
        });
        svg.append('text').attr('class', 'pi-hm-tot').attr('x', w - totW / 2).attr('y', yy + rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'middle').text(fmtInt(cells.filter((c) => c.abc === a).reduce((s, c) => s + c.n, 0)));
      });
      // sequential key
      const ky = topH + abcs.length * rowH + 14;
      const kg = svg.append('g').attr('transform', `translate(${labW},${ky})`);
      [0.1, 0.3, 0.5, 0.7, 0.85].forEach((o, i) => kg.append('rect').attr('x', i * 18).attr('y', -6).attr('width', 16).attr('height', 10).attr('rx', 2).attr('fill', theme.series.neutral).attr('fill-opacity', o));
      lab(kg, { x: 5 * 18 + 8, y: 0, text: small ? `fewer → more PNs (max ${fmtInt(max)})` : `fewer → more PNs (max ${fmtInt(max)} per cell)`, color: theme.color.faint });
      if (topA) {
        const i = dcs.indexOf(topA.dc);
        const r = abcs.indexOf('A');
        svg.append('rect').attr('class', 'pi-hm-focus').attr('x', labW + i * cw + 1).attr('y', topH + r * rowH + 1).attr('width', cw - 2).attr('height', rowH - 2).attr('rx', 7);
      }
    });
  }

  // ------------------------------------------------------------------ planted situations
  function drawPlanted() {
    const pl = parts.filter((p) => p.planted).sort((a, b) => String(a.planted).localeCompare(String(b.planted)));
    plantedCard.replaceChildren(
      h('div', { class: 'card-head' }, h('div', {}, h('div', { class: 'card-kicker' }, 'Planted situations · scenario design'), h('h3', { class: 'card-title' }, pl.length ? `${pl.length} PNs carry a planted situation the models must detect from history alone` : 'No planted situations exported')), provChip('SIMULATED')),
      h('ul', { class: 'list-reset pi-planted-list' }, ...pl.map((p) => h('li', {}, h('button', { type: 'button', class: 'pi-planted-row', onclick: () => openPart(p.pn) },
        h('span', { class: 'chip chip-mono pi-planted' }, p.planted),
        h('span', { class: 'pi-planted-main' }, h('span', { class: 'mono' }, p.pn), h('span', { class: 'faint' }, p.desc)),
        riskPill(p), icon('chevron-right'))))),
      h('div', { class: 'card-foot' }, h('span', {}, 'Planted in the simulator so the planning logic can be tested against a known answer. The planner sees only the demand and repair history.')));
  }

  // ------------------------------------------------------------------ state changes
  async function setAta(a) {
    ata = a;
    const t = explorerCard.querySelector('.card-title'); if (t) t.textContent = explorerTitle();
    sysButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.ata === a)));
    allBtn.setAttribute('aria-pressed', String(a === 'all'));
    air.setActive(a === 'all' ? null : a);
    layoutAircraft();
    refreshTable();
    cleanups[0]?.(); cleanups[0] = drawMatrix();
    ctx.setParams({ ata: a, pn: '' });
    await drawExploded();
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
      h('span', { class: 'chip' }, dcLabel(p.demand_class)),
      h('span', { class: 'chip' }, `ABC ${p.abc}`),
      provChip(p.provenance || prov));
    body.append(head);
    const ex = (p.exceptions || []).find((x) => x.severity === 'urgent' || x.severity === 'review');
    if (ex && p.risk_level !== ex.severity) {
      body.append(h('p', { class: 'pi-exc-note t-12 muted', role: 'note' }, icon('info'), h('span', {}, `Risk ${riskPct(p.risk_score)} measures grounding exposure (AOG hours). The ${ex.severity} ${ex.type_label.toLowerCase()} action (${ex.exception_id}) is about planning data, so it ranks high on Mission and in the Action Centre while the risk score stays low.`)));
    }
    if (p.planted) {
      body.append(h('div', { class: 'pi-planted-banner', role: 'note' }, icon('target'), h('div', {}, h('strong', {}, `Planted situation ${p.planted}`), h('p', { class: 'faint t-12' }, p.planted_note || 'A scenario planted in the simulator for the planning logic to detect from history alone.'))));
    }
    const chartHost = h('div');
    body.append(chartHost);
    body.append(h('dl', { class: 'meta-list' }, ...[
      ['Description', p.desc], ['ATA', `${p.ata} · ${sysName(p.ata)}`], ['Class', `${CLS_NAME[p.cls] || p.cls} · deadline ${p.deadline} (hypothetical)`],
      ['Demand class', `${dcLabel(p.demand_class)} · ADI ${fmtNum(p.adi)} · CV² ${fmtNum(p.cv2)}`], ['ABC', p.abc], ['Unit cost', fmtAED(p.unit_cost)],
      ['Grounding risk', p.risk_hours != null ? `${fmtHours(p.risk_hours)}/yr of AOG (history + modelled residual)` : riskPct(p.risk_score)],
      [`${P.stock_basis_id || 'Plan'} target (all stations)`, `${fmtInt(p.stock_total)} unit${p.stock_total === 1 ? '' : 's'}`],
      // canonical per-PN AOG metrics, labelled exactly as on Mission and the Action Centre
      ...['aog_h_52w', 'aog_h_52w_max_station'].filter((k) => Number.isFinite(p[k])).map((k) => [P.aog_metric_labels?.[k]?.label || k, `${fmtInt(p[k])} h${k === 'aog_h_52w_max_station' && p.aog_h_52w_max_station_id ? ` (${p.aog_h_52w_max_station_id})` : ''}`]),
    ].flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)])));
    const st = Object.entries(p.stock_by_station || {});
    const maxSt = Math.max(1, ...st.map(([, q]) => q));
    body.append(h('div', {}, h('div', { class: 'card-kicker mb-1' }, `Stock by station · ${P.stock_basis_id || 'target'} allocation`), P.stock_basis ? h('p', { class: 'faint t-12 mb-1' }, P.stock_basis) : null, h('ul', { class: 'list-reset pi-stock' }, ...st.map(([s, q]) => h('li', {}, h('span', { class: 'mono' }, s), h('span', { class: 'pi-stock-bar', 'aria-hidden': 'true' }, h('span', { style: { width: `${(q / maxSt) * 100}%` }, class: q ? '' : 'is-zero' })), h('span', { class: 'mono num' }, fmtInt(q)))))));
    const fq = new URLSearchParams({ class: p.demand_class, part: p.cls, pn }).toString();
    const foot = [h('a', { class: 'btn btn--sm', href: `#/forecast?${fq}` }, icon('flask'), 'See in Forecast Lab')];
    if (p.cls === 'R') foot.push(h('a', { class: 'btn btn--sm', href: `#/rotables?pn=${encodeURIComponent(pn)}` }, icon('rotable'), 'See in Rotable Control'));
    const d = drawer({ kicker: `Part number · ATA ${p.ata}`, title: pn, body, foot,
      // F3 (wave 4): opened from a deep link there is no opener; Esc returns focus to the part's table row or its ATA hotspot
      returnFocus: () => [...document.querySelectorAll(`#view [data-story="parts-table"] [data-key="${pn}"]`)].find((e) => e.getClientRects().length) || document.querySelector(`#view .pi-sys[data-ata="${p.ata}"]`),
      onClose: () => { ctx.setParams({ pn: '' }); openDrawer = null; } }).open();
    openDrawer = d;
    requestAnimationFrame(() => {
      const f = chartFrame(chartHost, {
        headline: all.nz ? `Demand in ${fmtInt(all.nz)} of ${fmtInt(all.weeks)} weeks (${fmtInt(all.total)} unit${all.total === 1 ? '' : 's'}); ${fmtPct(tr.zeroShare, 0)} of training weeks are zero` : `No demand recorded in ${fmtInt(all.weeks)} weeks`,
        subtitle: `Units per week · ${fmtWeek(weeks[0])}–${fmtWeek(weeks[1])} · training ${fmtWeek(0)}–${fmtWeek(trainEnd)} | selection ${fmtWeek(selStart)}–${fmtWeek(weeks[1])} · simulated calendar`,
        provenance: DH.meta?.provenance || 'SIMULATED', source: 'demand_history.json',
        table: { columns: [{ key: 'x', label: 'Week', format: fmtWeek }, { key: 'y', label: 'Qty', num: true }], rows: series.map((y, x) => ({ x, y })).filter((r) => r.y > 0) },
      });
      f.root.dataset.story = 'parts-demand-strip';
      d._stop = demandStrip(f.body, series, { height: 170, splitAt: selStart });
    });
    return d;
  }

  await drawExploded();
  // during the guided tour keep the aircraft visible (the tour spotlights the ATA hotspot)
  if (pnParam && !document.querySelector('.story')) openPart(pnParam.pn);
  return () => { cleanups.forEach((c) => c?.()); openDrawer?._stop?.(); };
}
