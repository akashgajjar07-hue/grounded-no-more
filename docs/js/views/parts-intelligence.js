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
import { chartFrame, responsive, svgIn, axisBottom, axisLeft, theme, annotate, withTooltip, directLabel, fmtAED, fmtInt, fmtNum, fmtPct, fmtWeek } from '../charts/theme.js';
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
    return [a, { ata: a, name: sysName(a), n: ps.length, urgent: ps.filter((p) => p.risk_level === 'urgent').length, review: ps.filter((p) => p.risk_level === 'review').length, level: sysRisk.get(a)?.risk_level || (ps.length ? lvl : 'unknown'), share: sysRisk.get(a)?.risk_share, top, max: top?.risk_score }];
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
  const airHost = h('div', { class: 'pi-aircraft', 'data-story': 'aircraft' });
  const legend = h('div', { class: 'pi-legend', 'aria-hidden': 'true' }, ...['urgent', 'review', 'ok'].map((l) => h('span', { class: `pi-legend-item is-${l}` }, h('b', {}, LEVEL[l].glyph), LEVEL[l].text)), h('span', { class: 'faint' }, 'System level = share of fleet risk-hours'));
  const explorerCard = card({
    cls: 'span-7 md-span-12 pi-explorer', bp: true, prov,
    kicker: 'Aircraft system explorer · plan view · generic twin, fictional',
    title: worst ? `ATA ${worst.ata} ${worst.name.toLowerCase()} carries the most risk: ${worst.share != null ? fmtPct(worst.share, 0) + ' of fleet risk-hours, ' : ''}${worst.urgent} urgent of ${worst.n} PNs` : 'No risk scores exported',
    body: [airHost, legend],
  });

  const sysList = h('ul', { class: 'pi-syslist list-reset', role: 'list', 'aria-label': 'ATA systems (list alternative to the aircraft diagram)' });
  const sysButtons = ATAS.map((a) => {
    const s = sysStat[a];
    const b = h('button', { type: 'button', class: `pi-sys is-${s.level}`, 'aria-pressed': String(a === ata), dataset: { ata: a }, onclick: () => setAta(a) },
      h('span', { class: 'pi-sys-ata mono' }, a),
      h('span', { class: 'pi-sys-main' }, h('span', { class: 'pi-sys-name' }, s.name), h('span', { class: 'pi-sys-meta mono' }, `${fmtInt(s.n)} PNs · ${fmtInt(s.urgent)} urgent · max ${riskPct(s.max)}`)),
      pill(s.level === 'unknown' ? 'unknown' : s.level, LEVEL[s.level].text));
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
    { key: 'stock_total', label: 'Stock', num: true, format: fmtInt },
    { key: 'unit_cost', label: 'Unit cost', num: true, format: (v) => fmtAED(v) },
    { key: 'risk_score', label: 'Risk', num: true, render: (r) => h('span', { title: riskTitle(r) }, pill(r.risk_level, riskPct(r.risk_score))) },
  ];
  function riskTitle(r) {
    return `${r.risk_hours != null ? `${fmtNum(r.risk_hours, 1)} AOG h/yr = ${fmtNum(r.aog_hours_hist_per_yr, 1)} history + ${fmtNum(r.residual_aog_h_per_yr, 1)} modelled residual. ` : ''}Score = ln(1 + AOG h) / ln(1 + fleet max), × 100.`;
  }
  const rowsFor = () => parts.filter((p) => (ata === 'all' || p.ata === ata) && (cls === 'all' || p.cls === cls) && (!query || p.pn.toLowerCase().includes(query) || String(p.desc).toLowerCase().includes(query)));
  const table = dataTable({ columns, rows: rowsFor(), sort: { key: 'risk_score', dir: 'desc' }, onRowClick: (r) => openPart(r.pn), caption: 'Parts for the selected ATA system', maxHeight: 520 });
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
  cleanups.push(air.destroy);

  function decorateAircraft(svg) {
    const NS = 'http://www.w3.org/2000/svg';
    svg.querySelectorAll('.ata-hotspot').forEach((g) => {
      const s = sysStat[g.dataset.ata];
      if (!s) return;
      g.classList.add(`risk-${s.level}`);
      g.dataset.story = `parts-hotspot-${s.ata}`;
      g.setAttribute('aria-label', `ATA ${s.ata} ${s.name}: ${LEVEL[s.level].text}. ${s.n} part numbers, ${s.urgent} urgent.`);
      const c = g.querySelector('.hs-badge circle');
      if (!c) return;
      const cx = +c.getAttribute('cx'), cy = +c.getAttribute('cy');
      const ring = document.createElementNS(NS, 'circle');
      ring.setAttribute('cx', cx); ring.setAttribute('cy', cy); ring.setAttribute('r', '19'); ring.setAttribute('class', 'hs-pulse');
      c.before(ring);
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', cx); t.setAttribute('y', cy + 34); t.setAttribute('class', `hs-risk hs-risk--${s.level}`);
      t.textContent = `${LEVEL[s.level].glyph} ${s.level === 'urgent' ? `${s.urgent} URG` : LEVEL[s.level].text.toUpperCase()}`;
      g.querySelector('.hs-badge').append(t);
    });
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
    svg.querySelectorAll('.bp-label').forEach((lg) => {
      const l = labels.find((x) => String(x.slot) === lg.dataset.slot);
      if (!l?.pn) return;
      lg.classList.add('pi-slot', `risk-${byPn.get(l.pn)?.risk_level || 'unknown'}`);
      lg.setAttribute('tabindex', '0');
      lg.setAttribute('role', 'button');
      lg.setAttribute('aria-label', `${l.pn} ${l.desc}: open part drill-down`);
      const open = () => openPart(l.pn);
      lg.addEventListener('click', open);
      lg.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
    figHost.replaceChildren(svg);
    const matched = labels.filter((l) => l.pn);
    explodedTitle.textContent = `ATA ${ata} · ${sysName(ata)}: ${matched.length} of ${ps.length} PNs drawn`;
    slotKey.replaceChildren(...labels.map((l) => {
      const p = byPn.get(l.pn);
      return h('li', {}, h('button', { type: 'button', class: 'pi-slotkey-btn', disabled: !p, onclick: () => p && openPart(p.pn) },
        h('span', { class: 'pi-slotnum mono' }, String(l.slot)), h('span', { class: 'mono' }, l.pn || '—'), h('span', { class: 'pi-slotdesc' }, p ? p.desc : l.role),
        p ? pill(p.risk_level, riskPct(p.risk_score)) : null));
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
    return out.map((s) => {
      const p = s.p || rest.shift();
      return { slot: s.slot, role: s.role, pn: p?.pn, desc: p?.desc };
    });
  }

  // ------------------------------------------------------------------ ADI / CV² matrix
  function drawMatrix() {
    matrixCard.replaceChildren();
    const pts = parts.filter((p) => Number.isFinite(p.adi) && Number.isFinite(p.cv2) && p.demand_class !== 'insufficient_data');
    const nIns = parts.length - pts.length;
    const counts = Object.fromEntries(['smooth', 'erratic', 'intermittent', 'lumpy'].map((c) => [c, pts.filter((p) => p.demand_class === c).length]));
    const sparse = counts.intermittent + counts.lumpy;
    const f = chartFrame(matrixCard, {
      headline: `${fmtInt(sparse)} of ${fmtInt(pts.length)} classified PNs average at least ${ADI_CUT} weeks between demands: intermittent or lumpy`,
      subtitle: `ADI (weeks between demands, log scale) × CV² of demand sizes · training weeks ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)} only · Syntetos–Boylan cut-offs ${ADI_CUT} / ${CV2_CUT}${nIns ? ` · ${nIns} PNs with < 3 demands not plotted` : ''}`,
      provenance: 'DERIVED', source: 'parts.json (adi, cv2, demand_class)', story: 'parts-adi-matrix',
      table: { columns: [{ key: 'pn', label: 'PN', mono: true }, { key: 'adi', label: 'ADI', num: true, format: (v) => fmtNum(v) }, { key: 'cv2', label: 'CV²', num: true, format: (v) => fmtNum(v) }, { key: 'demand_class', label: 'Class', format: dcLabel }], rows: pts },
    });
    const keyEl = h('div', { class: 'pi-matrix-key' });
    f.body.after(keyEl);
    const stop = responsive(f.body, (w) => {
      const small = w < 480;
      const hgt = small ? 300 : 340;
      const m = { top: 12, right: 16, bottom: 36, left: 44 };
      const iw = w - m.left - m.right, ih = hgt - m.top - m.bottom;
      const svg = svgIn(f.body, w, hgt, 'ADI versus CV squared scatter');
      const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
      const d3 = window.d3;
      const xMax = Math.max(ADI_CUT * 3, d3.max(pts, (p) => p.adi) * 1.15);
      const yMax = Math.max(CV2_CUT * 2.2, d3.max(pts, (p) => p.cv2) * 1.1);
      const x = d3.scaleLog().domain([1, xMax]).range([0, iw]);
      const y = d3.scaleLinear().domain([0, yMax]).nice().range([ih, 0]);
      // quadrants
      const qx = x(ADI_CUT), qy = y(CV2_CUT);
      g.append('rect').attr('class', 'pi-quad pi-quad--sparse').attr('x', qx).attr('y', 0).attr('width', iw - qx).attr('height', ih);
      g.append('line').attr('class', 'pi-cut').attr('x1', qx).attr('x2', qx).attr('y1', 0).attr('y2', ih);
      g.append('line').attr('class', 'pi-cut').attr('x1', 0).attr('x2', iw).attr('y1', qy).attr('y2', qy);
      g.append('text').attr('class', 'pi-cut-t').attr('x', qx + 4).attr('y', ih - 6).text(`ADI ${ADI_CUT}`);
      g.append('text').attr('class', 'pi-cut-t').attr('x', iw - 2).attr('y', qy - 5).attr('text-anchor', 'end').text(`CV² ${CV2_CUT}`);
      const ql = [
        ['smooth', 6, ih - 22, 'start'], ['erratic', 6, 14, 'start'],
        ['intermittent', iw - 6, ih - 22, 'end'], ['lumpy', iw - 6, 14, 'end'],
      ];
      ql.forEach(([c, xx, yy, a]) => {
        const t = g.append('text').attr('class', 'pi-quad-t').attr('x', xx).attr('y', yy).attr('text-anchor', a);
        t.append('tspan').text(c.toUpperCase());
        t.append('tspan').attr('class', 'pi-quad-n').attr('dx', 6).text(fmtInt(counts[c]));
      });
      axisBottom(g.append('g'), x, { height: ih, format: (v) => (Number.isInteger(v) && [1, 2, 5, 10, 20, 50, 100].includes(v) ? v : '') });
      axisLeft(g.append('g'), y, { ticks: 4, format: (v) => fmtNum(v, 1) });
      g.append('text').attr('class', 'pi-axis-t').attr('x', iw).attr('y', ih + 30).attr('text-anchor', 'end').text('ADI · weeks between demands →');
      g.append('text').attr('class', 'pi-axis-t').attr('x', 0).attr('y', -2).text('CV² ↑');
      const sel = (p) => ata !== 'all' && p.ata === ata;
      const ordered = pts.slice().sort((a, b) => sel(a) - sel(b));
      const dots = g.append('g').selectAll('circle').data(ordered).join('circle')
        .attr('cx', (p) => x(Math.min(p.adi, xMax))).attr('cy', (p) => y(Math.min(p.cv2, yMax)))
        .attr('r', (p) => (sel(p) ? 5 : 3.5))
        .attr('class', (p) => (sel(p) ? 'pi-dot is-sel' : 'pi-dot'))
        .attr('tabindex', (p) => (sel(p) ? 0 : null))
        .attr('role', (p) => (sel(p) ? 'button' : null))
        .attr('aria-label', (p) => (sel(p) ? `${p.pn} ${dcLabel(p.demand_class)}, ADI ${fmtNum(p.adi)}, CV² ${fmtNum(p.cv2)}` : null))
        .style('cursor', 'pointer')
        .on('click', (e, p) => openPart(p.pn))
        .on('keydown', (e, p) => { if (e.key === 'Enter') openPart(p.pn); });
      withTooltip(dots, (p) => ({ title: p.pn, rows: [['Description', p.desc], ['ADI', fmtNum(p.adi)], ['CV²', fmtNum(p.cv2)], ['Class', dcLabel(p.demand_class)], ['Risk', riskPct(p.risk_score)]] }));
      const focus = pts.filter(sel).sort((a, b) => b.risk_score - a.risk_score)[0];
      if (focus) {
        const fx = x(Math.min(focus.adi, xMax)), fy = y(Math.min(focus.cv2, yMax));
        annotate(g, { x: fx, y: fy, dx: fx > iw * 0.55 ? -30 : 30, dy: fy < 60 ? 30 : -26, title: focus.pn, sub: `top risk in ATA ${ata} · ${dcLabel(focus.demand_class)}` });
      }
    });
    keyEl.replaceChildren(h('span', { class: 'pi-key-dot is-sel' }), ata === 'all' ? 'All systems shown in neutral' : `ATA ${ata} parts`, h('span', { class: 'pi-key-dot' }), 'other PNs', h('span', { class: 'pi-key-sw' }), 'Croston-family zone (ADI ≥ 1.32)');
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
      headline: topA && nA ? `${fmtInt(topA.n)} of ${fmtInt(nA)} A-class PNs have ${dcLabel(topA.dc)} demand: the high-value items are the hard-to-forecast ones` : 'ABC × demand class',
      subtitle: `Count of PNs · ABC by annual usage value (A = top 80%, B = next 15%) · demand class from training weeks ${fmtWeek(weeks[0])}–${fmtWeek(trainEnd)}`,
      provenance: 'DERIVED', source: 'parts.json (abc, demand_class)',
      table: { columns: [{ key: 'abc', label: 'ABC' }, { key: 'dc', label: 'Demand class', format: dcLabel }, { key: 'n', label: 'PNs', num: true }], rows: cells },
    });
    return responsive(f.body, (w) => {
      const small = w < 520;
      const labW = 44, topH = small ? 46 : 30, rowH = small ? 48 : 56, totW = 48;
      const cw = (w - labW - totW) / dcs.length;
      const hgt = topH + abcs.length * rowH + 30;
      const svg = svgIn(f.body, w, hgt, 'ABC by demand class heatmap');
      const max = Math.max(1, ...cells.map((c) => c.n));
      const op = window.d3.scaleLinear().domain([0, max]).range([0.04, 0.85]);
      dcs.forEach((c, i) => {
        const t = svg.append('text').attr('class', 'pi-hm-col').attr('x', labW + i * cw + cw / 2).attr('y', small ? 16 : 18).attr('text-anchor', 'middle');
        const SHORT = { smooth: 'smooth', erratic: 'erratic', intermittent: 'intermitt.', lumpy: 'lumpy', insufficient_data: 'insuff. data' };
        const words = small ? SHORT[c].split(' ') : [dcLabel(c)];
        words.forEach((wd, j) => t.append('tspan').attr('x', labW + i * cw + cw / 2).attr('dy', j ? 13 : 0).text(wd));
      });
      svg.append('text').attr('class', 'pi-hm-col').attr('x', w - totW / 2).attr('y', small ? 16 : 18).attr('text-anchor', 'middle').text('Σ');
      abcs.forEach((a, r) => {
        const yy = topH + r * rowH;
        svg.append('text').attr('class', 'pi-hm-row').attr('x', 8).attr('y', yy + rowH / 2).attr('dy', '0.32em').text(a);
        dcs.forEach((c, i) => {
          const cell = cells.find((x) => x.abc === a && x.dc === c);
          const gx = labW + i * cw;
          const rect = svg.append('rect').attr('x', gx + 2).attr('y', yy + 2).attr('width', cw - 4).attr('height', rowH - 4).attr('rx', 6).attr('fill', theme.color.accent).attr('fill-opacity', cell.n ? op(cell.n) : 0).attr('stroke', theme.color.line);
          withTooltip(rect.datum(cell), (d) => ({ title: `${d.abc} · ${dcLabel(d.dc)}`, rows: [['PNs', fmtInt(d.n)]] }));
          svg.append('text').attr('class', cell.n && op(cell.n) > 0.5 ? 'pi-hm-n is-dark' : 'pi-hm-n').attr('x', gx + cw / 2).attr('y', yy + rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'middle').style('pointer-events', 'none').text(cell.n ? fmtInt(cell.n) : '·');
        });
        svg.append('text').attr('class', 'pi-hm-tot').attr('x', w - totW / 2).attr('y', yy + rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'middle').text(fmtInt(cells.filter((c) => c.abc === a).reduce((s, c) => s + c.n, 0)));
      });
      // sequential key
      const ky = topH + abcs.length * rowH + 14;
      const kg = svg.append('g').attr('transform', `translate(${labW},${ky})`);
      [0.1, 0.3, 0.5, 0.7, 0.85].forEach((o, i) => kg.append('rect').attr('x', i * 18).attr('y', -6).attr('width', 16).attr('height', 10).attr('rx', 2).attr('fill', theme.color.accent).attr('fill-opacity', o));
      lab(kg, { x: 5 * 18 + 8, y: 0, text: `fewer → more PNs (max ${fmtInt(max)} per cell)`, color: theme.color.faint });
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
        pill(p.risk_level, riskPct(p.risk_score)), icon('chevron-right'))))),
      h('div', { class: 'card-foot' }, h('span', {}, 'Planted in the simulator so the planning logic can be tested against a known answer. The planner sees only the demand and repair history.')));
  }

  // ------------------------------------------------------------------ state changes
  async function setAta(a) {
    ata = a;
    sysButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.ata === a)));
    allBtn.setAttribute('aria-pressed', String(a === 'all'));
    air.setActive(a === 'all' ? null : a);
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
      pill(p.risk_level, `Risk ${riskPct(p.risk_score)}`),
      h('span', { class: `chip pi-cls--${p.cls}` }, CLS_NAME[p.cls] || p.cls),
      h('span', { class: 'chip' }, dcLabel(p.demand_class)),
      h('span', { class: 'chip' }, `ABC ${p.abc}`),
      provChip(p.provenance || prov));
    body.append(head);
    if (p.planted) {
      body.append(h('div', { class: 'pi-planted-banner', role: 'note' }, icon('target'), h('div', {}, h('strong', {}, `Planted situation ${p.planted}`), h('p', { class: 'faint t-12' }, p.planted_note || 'A scenario planted in the simulator for the planning logic to detect from history alone.'))));
    }
    const chartHost = h('div');
    body.append(chartHost);
    body.append(h('dl', { class: 'meta-list' }, ...[
      ['Description', p.desc], ['ATA', `${p.ata} · ${sysName(p.ata)}`], ['Class', `${CLS_NAME[p.cls] || p.cls} · deadline ${p.deadline} (hypothetical)`],
      ['Demand class', `${dcLabel(p.demand_class)} · ADI ${fmtNum(p.adi)} · CV² ${fmtNum(p.cv2)}`], ['ABC', p.abc], ['Unit cost', fmtAED(p.unit_cost)],
      ['Grounding risk', p.risk_hours != null ? `${fmtNum(p.risk_hours, 1)} AOG h / yr (history + modelled residual)` : riskPct(p.risk_score)],
      ['Stock (all stations)', `${fmtInt(p.stock_total)} units`],
    ].flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)])));
    const st = Object.entries(p.stock_by_station || {});
    const maxSt = Math.max(1, ...st.map(([, q]) => q));
    body.append(h('div', {}, h('div', { class: 'card-kicker mb-1' }, `Stock by station · ${P.stock_basis_id || 'target'} allocation`), P.stock_basis ? h('p', { class: 'faint t-12 mb-1' }, P.stock_basis) : null, h('ul', { class: 'list-reset pi-stock' }, ...st.map(([s, q]) => h('li', {}, h('span', { class: 'mono' }, s), h('span', { class: 'pi-stock-bar', 'aria-hidden': 'true' }, h('span', { style: { width: `${(q / maxSt) * 100}%` }, class: q ? '' : 'is-zero' })), h('span', { class: 'mono num' }, fmtInt(q)))))));
    const fq = new URLSearchParams({ class: p.demand_class, part: p.cls, pn }).toString();
    const foot = [h('a', { class: 'btn btn--sm', href: `#/forecast?${fq}` }, icon('flask'), 'See in Forecast Lab')];
    if (p.cls === 'R') foot.push(h('a', { class: 'btn btn--sm', href: `#/rotables?pn=${encodeURIComponent(pn)}` }, icon('rotable'), 'See in Rotable Control'));
    const d = drawer({ kicker: `Part number · ATA ${p.ata}`, title: pn, body, foot, onClose: () => { ctx.setParams({ pn: '' }); openDrawer = null; } }).open();
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
