/**
 * Data & Method — where every number comes from.
 * Data: method.json
 * Shows: provenance legend + flow diagram (sources → generator → engine → models → exports, with ASSUMED
 * inputs), source manifest, searchable assumption register, validation (tests, calibration targets vs achieved,
 * freeze + holdout log including any forced rerun), limitations, author, licences and the full disclaimer.
 * Story hooks: method-provenance, method-assumptions, method-validation.
 */
import { h, pageHead, card, provChip, pill, icon, dataTable, sectionTitle, segmented, DISCLAIMER } from '../ui.js';
import { chartFrame, responsive, svgIn, theme, truncate, refLine, fmtPct, fmtInt, fmtNum, fmtStamp } from '../charts/theme.js';
import { assetURL } from '../data.js';

export const data = ['method', 'kpis'];
const d3 = () => window.d3;
const PROV = ['REAL', 'DERIVED', 'ASSUMED', 'SIMULATED'];
const GLYPH = { REAL: '●', DERIVED: '◆', ASSUMED: '○', SIMULATED: '▲' };
const PROV_TEXT = {
  REAL: 'Sourced from a public, cited dataset, such as airport coordinates.',
  DERIVED: 'Computed in this repo from REAL or SIMULATED data.',
  ASSUMED: 'A planning assumption chosen by the author, with a rationale.',
  SIMULATED: 'Produced by the synthetic world generator and simulation engine.',
};
const AUTHOR_FALLBACK = { name: 'Akash Gajjar', degree: 'MSc Supply Chain Management, University of Liverpool (2025)', github: 'https://github.com/akashgajjar07-hue', linkedin: '' };

function ensureCSS() {
  const id = 'css-data-method';
  const existing = document.getElementById(id);
  if (existing) return existing.__ready || Promise.resolve();
  const link = h('link', { id, rel: 'stylesheet', href: assetURL('css/views/data-method.css') });
  link.__ready = new Promise((res) => { link.onload = res; link.onerror = res; setTimeout(res, 1500); });
  document.head.append(link);
  return link.__ready;
}
const up = (p) => String(p || '').toUpperCase();
const num = (v) => typeof v === 'number' && Number.isFinite(v);
const stripMd = (s) => String(s ?? '').replace(/`([^`]*)`/g, '$1').replace(/\*([^*]+)\*/g, '$1');
/** REAL build timestamps → shared fmtStamp ("26 Nov 02:25 UTC"; critic: no raw ISO on screen). */
const fmtTime = (iso) => (Number.isFinite(Date.parse(iso)) ? fmtStamp(iso) : String(iso || '—'));
const fmtDate = (iso) => fmtStamp(iso, { year: true }).replace(/ \d{2}:\d{2} UTC$/, '');
/** Replace ISO timestamps embedded in exported prose with the readable form. */
const humanISO = (s) => String(s ?? '').replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})/g, (m) => fmtTime(m));

export async function render(el, ctx) {
  await ensureCSS();
  const M = ctx.data.method || {};
  const cleanups = [];
  const sources = M.source_manifest || [];
  // wave 5: rows with a real rationale first (stable within each group); site metadata without one (meta.*) sinks to the end
  const assumptions = (M.assumptions || []).map((a, i) => ({ a, i })).sort((x, y) => (!x.a.rationale - !y.a.rationale) || x.i - y.i).map(({ a }) => a);
  const countBy = (list) => Object.fromEntries(PROV.map((p) => [p, list.filter((x) => up(x.provenance) === p).length]));
  const srcN = countBy(sources), asmN = countBy(assumptions);

  el.append(pageHead({
    eyebrow: 'Reference · Data & Method', title: 'Where every number comes from',
    lede: 'Every value on this site carries a provenance tag. Models run offline in Python; the site only loads their exported results. Falcon Hub Airways (fictional) and its fleet do not exist.',
    meta: [provChip(M.meta?.provenance || 'DERIVED'), M.meta?.git_sha ? h('span', { class: 'chip chip-mono' }, `build ${String(M.meta.git_sha).slice(0, 7)}`) : null, M.meta?.generated_at ? h('span', { class: 'chip chip-mono', title: `Exported ${fmtTime(M.meta.generated_at)}` }, `exported ${fmtDate(M.meta.generated_at)}`) : null].filter(Boolean),
  }));

  // ---------------------------------------------------------------- legend
  el.append(h('div', { class: 'dm-legend' }, PROV.map((p) => card({ body: [h('div', { class: 'row' }, provChip(p, { force: true }), h('span', { class: 'dm-count' }, `${fmtInt(srcN[p])} src · ${fmtInt(asmN[p])} asm`)), h('p', {}, PROV_TEXT[p])] }))));

  // ---------------------------------------------------------------- provenance flow
  const flowCard = h('section', { class: 'card mt-3', dataset: { story: 'method-provenance' } });
  el.append(flowCard);
  const realNames = sources.filter((s) => up(s.provenance) === 'REAL').map((s) => s.name);
  const stages = [
    { id: 'src', tag: 'REAL', title: 'Public sources', text: realNames.length ? realNames.join(' · ') : 'No REAL sources listed' },
    { id: 'gen', tag: 'SIMULATED', title: 'World generator', text: 'Fictional fleet, part master, removals, demand and repair TATs' },
    { id: 'eng', tag: 'SIMULATED', title: 'Simulation engine', text: 'Stock, transfers, repairs, AOG desk; seeded scenarios' },
    { id: 'mod', tag: 'DERIVED', title: 'Models', text: 'Forecasting, inventory policy, capital frontier, AOG lab' },
    { id: 'exp', tag: 'DERIVED', title: 'Site exports', text: 'docs/data/*.json, loaded read-only by this site' },
  ];
  const asm = { id: 'asm', tag: 'ASSUMED', title: 'Assumptions', text: `${fmtInt(asmN.ASSUMED)} tagged ASSUMED in the register (config/*.yaml)` };
  const ff = chartFrame(flowCard, {
    headline: `${fmtInt(srcN.REAL)} of ${fmtInt(sources.length)} sources are real public data; every result is derived from simulation`,
    subtitle: 'Sources → generator → engine → models → exports · the fleet, demand and repairs are SIMULATED · holdout seeds run only after the freeze',
    provenance: 'DERIVED', source: 'method.json (source_manifest, assumptions)',
    table: { columns: [{ key: 'title', label: 'Stage' }, { key: 'tag', label: 'Provenance' }, { key: 'text', label: 'What' }], rows: [stages[0], asm, ...stages.slice(1)] },
  });
  ff.body.classList.add('dm-flow');
  cleanups.push(responsive(ff.body, (w) => drawFlow(ff.body, w, stages, asm)));

  // ---------------------------------------------------------------- sources
  el.append(sectionTitle('Source manifest', provChip('REAL')));
  el.append(card({
    prov: 'DERIVED', kicker: 'Where inputs come from', title: `${fmtInt(sources.length)} sources`,
    body: h('div', { class: 'dm-wrap' }, dataTable({
      caption: 'Source manifest', bare: true, rows: sources, mobileColumns: ['name', 'provenance', 'used_for', 'licence'],
      columns: [
        { key: 'name', label: 'Source', render: (r) => (r.url ? h('a', { href: r.url, target: '_blank', rel: 'noopener noreferrer' }, r.name) : r.name) },
        { key: 'licence', label: 'Licence' }, { key: 'used_for', label: 'Used for' },
        { key: 'provenance', label: 'Provenance', render: (r) => provChip(r.provenance, { force: true }) },
      ],
    })),
  }));

  // ---------------------------------------------------------------- assumption register
  el.append(sectionTitle('Assumption register'));
  let q = '', pf = 'ALL', gf = 'ALL';
  const groups = [...new Set(assumptions.map((a) => a.group || String(a.key || '').split('.')[0]).filter(Boolean))];
  const showing = h('span', { class: 'dm-showing', 'aria-live': 'polite' });
  const table = dataTable({
    caption: 'Assumption register', bare: true, maxHeight: 520, rows: assumptions, mobileColumns: ['key', 'value', 'provenance', 'rationale'],
    columns: [
      { key: 'key', label: 'Key', mono: true },
      { key: 'value', label: 'Value', mono: true, format: (v, r) => `${v == null ? '—' : String(v).replace(/^"(.*)"$/, '$1')}${r.unit ? ` ${r.unit}` : ''}` },
      { key: 'provenance', label: 'Tag', render: (r) => provChip(r.provenance, { force: true }) },
      { key: 'rationale', label: 'Rationale', render: (r) => (r._same ? h('span', { class: 'dm-same', title: r.rationale }, '↑ same rationale as above') : (r.rationale ?? (String(r.key).startsWith('meta.') ? h('span', { class: 'faint' }, 'Site metadata (labels, not a modelling choice)') : '—'))) },
    ],
  });
  const apply = () => {
    const ql = q.trim().toLowerCase();
    const rows = assumptions.filter((a) => (pf === 'ALL' || up(a.provenance) === pf) && (gf === 'ALL' || (a.group || String(a.key || '').split('.')[0]) === gf) &&
      (!ql || [a.key, a.value, a.rationale, a.source, a.group].some((v) => String(v ?? '').toLowerCase().includes(ql))));
    // consecutive rows with an identical rationale: print it once, then "same as above" (critic smaller issue)
    table.update(rows.map((r, i) => ({ ...r, _same: i > 0 && !!r.rationale && r.rationale === rows[i - 1].rationale })));
    showing.textContent = `Showing ${fmtInt(rows.length)} of ${fmtInt(assumptions.length)}`;
  };
  const search = h('input', { class: 'dm-search', type: 'search', placeholder: 'Search key, value or rationale', 'aria-label': 'Search assumptions', oninput: (e) => { q = e.target.value; apply(); } });
  const filters = h('div', { class: 'dm-filters' }, search,
    segmented({ label: 'Filter by provenance', value: 'ALL', options: [{ value: 'ALL', label: 'All' }, ...PROV.filter((p) => asmN[p]).map((p) => ({ value: p, label: `${GLYPH[p]} ${p[0]}${p.slice(1).toLowerCase()}` }))], onChange: (v) => { pf = v; apply(); } }),
    groups.length > 1 ? h('select', { class: 'dm-search', style: { flex: '0 1 200px' }, 'aria-label': 'Filter by group', onchange: (e) => { gf = e.target.value; apply(); } }, h('option', { value: 'ALL' }, 'All groups'), groups.map((g) => h('option', { value: g }, g))) : null,
    showing);
  el.append(card({ story: 'method-assumptions', prov: 'ASSUMED', kicker: 'Planning assumptions, with rationale', title: `${fmtInt(assumptions.length)} entries · ${PROV.filter((p) => asmN[p]).map((p) => `${fmtInt(asmN[p])} ${p.toLowerCase()}`).join(' · ')}`, body: [filters, h('div', { class: 'dm-wrap' }, table)] }));
  apply();

  // ---------------------------------------------------------------- validation
  el.append(sectionTitle('Validation'));
  const V = M.validation || {};
  const checks = V.checks || [];
  const testsRun = num(V.tests_total) && V.tests_total > 0;
  const nPassChk = checks.filter((c) => c.status === 'pass').length;
  const testsCard = card({
    cls: 'dm-tests-card', prov: 'DERIVED', kicker: 'Automated tests (pytest) and pipeline checks',
    body: h('div', { class: 'dm-tests' },
      h('div', { class: 'dm-tests-sum' },
        testsRun ? h('div', { class: 'dm-big' }, fmtInt(V.tests_passed), h('small', {}, ` / ${fmtInt(V.tests_total)} passed`)) : h('div', {}, h('div', { class: 'dm-big' }, h('small', {}, 'pytest: not run')), V.reason ? h('p', { class: 'faint t-12 mt-1' }, V.reason) : null),
        V.ran_at ? h('p', { class: 'dm-tests-at' }, `Run ${fmtTime(V.ran_at)}`) : null,
        h('p', { class: 't-14 muted mt-2' }, `${fmtInt(nPassChk)} of ${fmtInt(checks.length)} pipeline checks pass`)),
      h('div', { class: 'dm-checks' }, checks.map((c) => h('div', { class: 'dm-check' }, pill(c.status === 'pass' ? 'ok' : c.status === 'fail' ? 'urgent' : c.status === 'warn' ? 'review' : 'unknown', c.status === 'pass' ? 'Pass' : c.status === 'fail' ? 'Fail' : c.status === 'warn' ? 'Warn' : 'Not run'), h('span', {}, humanISO(c.name)), c.detail ? h('span', { class: 'faint' }, humanISO(c.detail)) : null)))),
  });
  const calCard = h('section', { class: 'card' });
  cleanups.push(calibration(calCard, M.calibration));
  const conCard = h('section', { class: 'card' });
  cleanups.push(consistency(conCard, ctx.data.kpis));
  const freeze = M.freeze || {};
  const log = freeze.holdout_log || M.holdout_log || [];
  const forced = log.filter((r) => r.forced);
  const nArt = num(freeze.n_artefacts) ? freeze.n_artefacts : Array.isArray(freeze.artefacts) ? freeze.artefacts.length : null;
  const logCard = card({
    prov: 'DERIVED', kicker: 'Freeze and holdout log',
    title: freeze.frozen_at ? `Selection frozen ${fmtTime(freeze.frozen_at)}${nArt != null ? ` · ${fmtInt(nArt)} artefacts hashed${freeze.verified ? ', verified unchanged' : ''}` : ''}` : 'Freeze not exported',
    body: [
      forced.length ? h('div', { class: 'dm-callout', role: 'note' }, icon('alert'), h('div', {}, h('b', {}, `Disclosed: ${forced.length} forced rerun${forced.length > 1 ? 's' : ''} (${forced.map((r) => `${r.run}, ${fmtTime(r.at)}`).join('; ')}). `), humanISO(stripMd(freeze.forced_rerun_note || forced.map((r) => r.note).filter(Boolean).join(' '))))) : null,
      freeze.note ? h('p', { class: 't-14 muted mb-2' }, humanISO(freeze.note)) : null,
      freeze.reporting_note ? h('p', { class: 't-14 muted mb-2' }, humanISO(stripMd(freeze.reporting_note))) : null,
      log.length ? h('div', { class: 'dm-log' }, log.map((r) => h('div', { class: `dm-log-item ${r.forced ? 'is-forced' : ''}` }, h('span', { class: 'dm-log-dot', 'aria-hidden': 'true' }), h('div', { style: { minWidth: 0 } }, h('div', { class: 'dm-log-run' }, r.run), h('div', { class: 'dm-log-at' }, fmtTime(r.at)), r.note ? h('div', { class: 'dm-log-note' }, humanISO(r.note)) : null), pill(r.forced ? 'review' : 'ok', r.forced ? 'Forced rerun' : 'Single run')))) : h('p', { class: 'faint t-14' }, 'Holdout log not exported.'),
    ],
  });
  el.append(h('div', { class: 'dm-stack', dataset: { story: 'method-validation' } }, testsCard, calCard, conCard, logCard));

  // ---------------------------------------------------------------- limitations
  el.append(sectionTitle('Limitations'));
  const lims = M.limitations || [];
  el.append(card({ prov: 'DERIVED', kicker: 'Read before using any number', title: lims.length ? `${fmtInt(lims.length)} known limitations` : 'Limitations not exported',
    body: lims.length ? h('div', { class: 'dm-limits' }, lims.map((l) => h('div', { class: 'dm-limit' }, typeof l === 'string' ? stripMd(l) : [l.title ? h('b', {}, stripMd(l.title)) : null, stripMd(l.text || l.detail || ''), l.section ? h('span', { class: 'faint t-12' }, ` · ${l.section}`) : null]))) : h('p', { class: 'faint t-14' }, 'See LIMITATIONS.md in the repository.') }));

  // ---------------------------------------------------------------- author, licences, disclaimer
  el.append(sectionTitle('Author, licences and disclaimer'));
  const A = { ...AUTHOR_FALLBACK, ...(M.author || {}) };
  const initials = A.name.split(/\s+/).map((s) => s[0]).join('').slice(0, 2);
  const authorCard = card({ cls: 'dm-span-5', kicker: 'Author', body: h('div', { class: 'dm-author' }, h('div', { class: 'dm-avatar', 'aria-hidden': 'true' }, initials), h('div', {}, h('h3', {}, A.name), h('p', { class: 'muted' }, A.degree), h('div', { class: 'dm-links' },
    A.github ? h('a', { class: 'btn btn--sm', href: A.github, target: '_blank', rel: 'noopener noreferrer' }, 'GitHub', icon('chevron-right')) : null,
    // LinkedIn is shown only once a real URL exists (no placeholder chip)
    A.linkedin ? h('a', { class: 'btn btn--sm', href: A.linkedin, target: '_blank', rel: 'noopener noreferrer' }, 'LinkedIn', icon('chevron-right')) : null))) });
  const licCard = card({ cls: 'dm-span-12', kicker: 'Third-party licences', title: `${fmtInt((M.licences || []).length)} vendored packages and fonts`, prov: 'REAL',
    body: h('div', { class: 'dm-wrap' }, dataTable({ caption: 'Licences', bare: true, dense: true, rows: (M.licences || []).map((r) => ({ ...r, name: stripMd(r.name) })), mobileColumns: ['name', 'licence', 'version'], columns: [{ key: 'name', label: 'Package' }, { key: 'version', label: 'Version', mono: true }, { key: 'licence', label: 'Licence' }] })) });
  const discCard = card({ cls: 'dm-span-7', bp: true, kicker: 'Disclaimer', body: [h('p', { class: 'dm-disclaimer' }, M.disclaimer || DISCLAIMER), h('p', {}, 'Falcon Hub Airways, its tails and its part numbers are fictional; no real airline names, logos or liveries are used. Simulated rates are not measured reliability. Deadline classes D0/D3/D10 are hypothetical and are not MEL categories.')] });
  el.append(h('div', { class: 'dm-grid' }, authorCard, discCard, licCard));

  return () => cleanups.forEach((f) => { try { f?.(); } catch { /* ignore */ } });
}

// ------------------------------------------------------------------ provenance flow (original SVG via D3)
function drawFlow(body, w, stages, asm) {
  // provenance is carried by glyph + word (as on the chips); strokes stay neutral so the diagram adds no accents
  const color = () => theme.series.neutral;
  const wide = w >= 760;
  const boxes = [];
  const arrows = [];
  let H;
  if (wide) {
    const gap = 44, bw = (w - gap * 4) / 5, bh = 112, y0 = 24;
    stages.forEach((s, i) => boxes.push({ ...s, x: i * (bw + gap), y: y0, w: bw, h: bh }));
    for (let i = 0; i < 4; i++) arrows.push({ d: `M${boxes[i].x + bw + 4},${y0 + bh / 2}H${boxes[i + 1].x - 6}`, gate: i === 3 ? 'FREEZE' : null, gx: boxes[i].x + bw + gap / 2, gy: 12, gateLine: i === 3 ? [y0 + 2, y0 + bh - 2] : null });
    const ay = y0 + bh + 56, ax = boxes[1].x, aw = boxes[3].x + bw - ax;
    boxes.push({ ...asm, x: ax, y: ay, w: aw, h: 76 });
    [1, 2, 3].forEach((i) => arrows.push({ d: `M${boxes[i].x + bw / 2},${ay - 4}V${y0 + bh + 6}`, assumed: true }));
    H = ay + 76 + 8;
  } else {
    const bw = w - 28, bh = 92, gap = 28;
    const order = [stages[0], stages[1], stages[2], stages[3], stages[4]];
    let y = 4;
    order.forEach((s, i) => { boxes.push({ ...s, x: 0, y, w: bw, h: bh }); if (i < order.length - 1) arrows.push({ d: `M${bw / 2},${y + bh + 4}V${y + bh + gap - 6}`, gate: i === 3 ? 'FREEZE' : null, gx: bw / 2 + 10, gy: y + bh + gap / 2 + 4, anchor: 'start' }); y += bh + gap; });
    boxes.push({ ...asm, x: 0, y, w: bw, h: 80 });
    // ASSUMED rail on the right edge feeding generator, engine, models
    const rx = w - 10;
    arrows.push({ d: `M${bw},${y + 40}H${rx}V${boxes[1].y + bh / 2}`, assumed: true, noHead: true });
    [1, 2, 3].forEach((i) => arrows.push({ d: `M${rx},${boxes[i].y + bh / 2}H${bw + 6}`, assumed: true }));
    H = y + 80 + 8;
  }
  const svg = svgIn(body, w, H, 'Provenance flow: public sources and the world generator feed the simulation engine; models derive results that are exported to this site; assumptions feed generator, engine and models');
  const defs = svg.append('defs');
  [['dm-head', theme.color.faint], ['dm-head-a', theme.color.faint]].forEach(([id, c]) => defs.append('marker').attr('id', id).attr('viewBox', '0 0 8 8').attr('refX', 7).attr('refY', 4).attr('markerWidth', 8).attr('markerHeight', 8).attr('orient', 'auto').append('path').attr('d', 'M0,0L8,4L0,8z').attr('fill', c));
  arrows.forEach((a) => {
    svg.append('path').attr('class', `dm-arrow ${a.assumed ? 'dm-arrow--assumed' : ''}`).attr('d', a.d).attr('marker-end', a.noHead ? null : `url(#${a.assumed ? 'dm-head-a' : 'dm-head'})`);
    if (a.gateLine) svg.append('line').attr('class', 'dm-gate-line').attr('x1', a.gx).attr('x2', a.gx).attr('y1', a.gateLine[0]).attr('y2', a.gateLine[1]);
    if (a.gate) svg.append('text').attr('class', 'dm-gate').attr('x', a.gx).attr('y', a.gy).attr('text-anchor', a.anchor || 'middle').text(a.gate);
  });
  boxes.forEach((b) => {
    const g = svg.append('g').attr('transform', `translate(${b.x},${b.y})`);
    g.append('rect').attr('class', 'dm-box').attr('width', b.w).attr('height', b.h).attr('rx', 10).attr('stroke', color(b.tag)).attr('stroke-opacity', 0.7).attr('stroke-dasharray', b.tag === 'ASSUMED' ? '5 4' : null);
    g.append('text').attr('class', 'dm-box-tag').attr('x', 14).attr('y', 22).attr('fill', theme.color.muted).text(`${GLYPH[b.tag]} ${b.tag}`);
    g.append('text').attr('class', 'dm-box-title').attr('x', 14).attr('y', 44).text(truncate(b.title, b.w - 28, 8.4));
    // wrap description into up to 3 lines
    const maxC = Math.max(10, Math.floor((b.w - 28) / 6.4));
    const words = String(b.text).split(/\s+/); const lines = [''];
    words.forEach((wd) => { const cur = lines[lines.length - 1]; if ((cur + ' ' + wd).trim().length > maxC && cur) lines.push(wd); else lines[lines.length - 1] = (cur + ' ' + wd).trim(); });
    const maxL = Math.max(1, Math.floor((b.h - 52) / 16));
    lines.slice(0, maxL).forEach((ln, i) => g.append('text').attr('class', 'dm-box-text').attr('x', 14).attr('y', 64 + i * 16).text(i === maxL - 1 && lines.length > maxL ? `${ln.slice(0, maxC - 1)}…` : ln));
  });
}

// ------------------------------------------------------------------ calibration: target band vs achieved
/** Diagonal-hatch pattern for ASSUMED target bands (titanium outline + hatch, never a copper fill). */
function hatch(svg, id) {
  const p = svg.append('defs').append('pattern').attr('id', id).attr('patternUnits', 'userSpaceOnUse').attr('width', 6).attr('height', 6).attr('patternTransform', 'rotate(45)');
  p.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 6).attr('stroke', theme.series.neutral).attr('stroke-opacity', 0.35).attr('stroke-width', 2);
  return `url(#${id})`;
}
let hatchSeq = 0;

function calibration(host, cal) {
  const list = Array.isArray(cal) ? cal : cal?.targets_vs_achieved || [];
  const rows = list.filter((r) => num(r.achieved) && num(r.target_lo) && num(r.target_hi)).map((r) => ({ ...r, pass: r.pass ?? r.in_band, label: r.label || String(r.metric || '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()).replace(/\baog\b/gi, 'AOG') }));
  const nPass = rows.filter((r) => (r.pass ?? (r.achieved >= r.target_lo && r.achieved <= r.target_hi))).length;
  const f = chartFrame(host, {
    headline: rows.length ? `${fmtInt(nPass)} of ${fmtInt(rows.length)} calibration targets met by the P0 history` : 'Calibration results not exported',
    subtitle: `Hatched band = target range (ASSUMED) · dot = achieved · ${cal?.policy || 'P0'} on the public history · each row on its own scale`,
    provenance: cal?.provenance || 'SIMULATED', source: 'method.json (calibration)',
    table: { columns: [{ key: 'label', label: 'Metric' }, { key: 'target_lo', label: 'Target low', num: true, format: (v, r) => fmtV(v, r) }, { key: 'target_hi', label: 'Target high', num: true, format: (v, r) => fmtV(v, r) }, { key: 'achieved', label: 'Achieved', num: true, format: (v, r) => fmtV(v, r) }], rows: rows.map((r) => ({ ...r, label: r.label || r.metric })) },
  });
  if (!rows.length) { f.body.append(h('p', { class: 'faint t-14' }, 'Not run.')); return null; }
  return responsive(f.body, (w) => {
    const narrow = w < 560;
    const rowH = narrow ? 70 : 48, labelW = narrow ? 0 : Math.min(200, w * 0.3), valW = narrow ? 0 : 120;
    const iw = Math.max(60, w - labelW - valW - 24);
    const svg = svgIn(f.body, w, rows.length * rowH + 8, 'Calibration targets versus achieved values');
    const fill = hatch(svg, `dm-hatch-${++hatchSeq}`);
    rows.forEach((r, i) => {
      const y0 = i * rowH + 4;
      const cy = narrow ? y0 + 52 : y0 + rowH / 2 + 4;
      // domain always contains the band AND the achieved value (never clamped)
      const lo = Math.min(r.target_lo, r.achieved), hi = Math.max(r.target_hi, r.achieved), pad = (hi - lo) * 0.25 || Math.abs(hi) * 0.1 || 1;
      const x = d3().scaleLinear().domain([lo - pad, hi + pad]).range([labelW, labelW + iw]);
      const ok = r.pass ?? (r.achieved >= r.target_lo && r.achieved <= r.target_hi);
      const g = svg.append('g');
      g.append('line').attr('x1', labelW).attr('x2', labelW + iw).attr('y1', cy).attr('y2', cy).attr('stroke', theme.color.line);
      g.append('rect').attr('x', x(r.target_lo)).attr('y', cy - 7).attr('width', Math.max(2, x(r.target_hi) - x(r.target_lo))).attr('height', 14).attr('rx', 3).attr('fill', fill).attr('stroke', theme.series.neutral).attr('stroke-opacity', 0.55);
      g.append('circle').attr('cx', x(r.achieved)).attr('cy', cy).attr('r', 5.5).attr('fill', ok ? theme.series.baseline : theme.color.bg).attr('stroke', ok ? theme.series.baseline : theme.series.urgent).attr('stroke-width', 2); // P0 = copper
      // band edges as faint mono ticks above the band, so every row states its own target
      const tl = `${fmtV(r.target_lo, r)}–${fmtV(r.target_hi, r)}`;
      g.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', 11).attr('x', (x(r.target_lo) + x(r.target_hi)) / 2).attr('y', cy - 13).attr('text-anchor', 'middle').attr('fill', theme.color.faint).text(`target ${tl}`);
      const label = r.label || r.metric;
      const val = `${fmtV(r.achieved, r)} ${ok ? '✓' : '✕'}`;
      if (narrow) g.append('text').attr('class', 'gnm-label').attr('x', 0).attr('y', y0 + 10).attr('dy', '0.32em').text(truncate(label, w * 0.6));
      else g.append('text').attr('class', 'gnm-label').attr('x', 0).attr('y', cy).attr('dy', '0.32em').text(truncate(label, labelW - 12));
      g.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', w).attr('y', narrow ? y0 + 10 : cy).attr('dy', '0.32em').attr('text-anchor', 'end').attr('fill', ok ? theme.color.text : theme.series.urgent).text(`${val} ${ok ? 'in band' : 'outside'}`);
    });
  });
}
// ------------------------------------------------------------------ selection vs holdout consistency
/**
 * One shared axis: every value as % difference from the holdout mean, so no row is clamped or squashed and
 * rows can be compared. Holdout 95% CI = teal whisker around 0; selection-seed mean = neutral diamond with its
 * real value printed beside it.
 */
function consistency(host, kpis) {
  const rows0 = (kpis?.consistency || []).filter((r) => num(r.holdout_recommended) && num(r.selection_recommended) && Array.isArray(r.holdout_ci) && r.holdout_recommended !== 0);
  const label = (id) => (kpis?.kpis || []).find((k) => k.id === id)?.label || String(id).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
  const fmtU = (v, r) => (r.unit === '%' ? fmtPct(v) : r.unit === 'AED' ? `AED ${(v / 1e6).toFixed(1)}M` : r.unit === 'h' ? `${fmtInt(v)} h` : fmtNum(v, 1));
  const rel = (v, r) => v / r.holdout_recommended - 1;
  const rows = rows0.map((r) => ({ ...r, ok: r.selection_inside_holdout_ci ?? (r.selection_recommended >= r.holdout_ci[0] && r.selection_recommended <= r.holdout_ci[1]), dSel: rel(r.selection_recommended, r), dLo: rel(r.holdout_ci[0], r), dHi: rel(r.holdout_ci[1], r) }));
  const inside = rows.filter((r) => r.ok);
  const worst = rows.filter((r) => !r.ok).sort((a, b) => Math.abs(b.dSel) - Math.abs(a.dSel))[0];
  const rec = kpis?.recommended_id || 'the recommended plan';
  const f = chartFrame(host, {
    headline: rows.length ? `${fmtInt(inside.length)} of ${fmtInt(rows.length)} selection-seed results fall inside the holdout 95% CI` : 'Selection vs holdout comparison not exported',
    subtitle: `${rec} · % difference from the holdout mean · teal = holdout 95% CI · ◇ = selection-seed mean${worst ? ` · largest gap: ${label(worst.id)}, ${fmtU(worst.selection_recommended, worst)} on selection vs ${fmtU(worst.holdout_recommended, worst)} on holdout` : ''}`,
    provenance: 'SIMULATED', source: 'kpis.json (consistency)',
    table: { columns: [{ key: 'label', label: 'KPI' }, { key: 'sel', label: 'Selection' }, { key: 'hold', label: 'Holdout' }, { key: 'ci', label: 'Holdout 95% CI' }, { key: 'd', label: 'Selection vs holdout' }, { key: 'in', label: 'Selection inside CI' }],
      rows: rows.map((r) => ({ label: label(r.id), sel: fmtU(r.selection_recommended, r), hold: fmtU(r.holdout_recommended, r), ci: `${fmtU(r.holdout_ci[0], r)} – ${fmtU(r.holdout_ci[1], r)}`, d: fmtSignedPct(r.dSel), in: r.ok ? 'yes' : 'no' })) },
  });
  if (!rows.length) { f.body.append(h('p', { class: 'faint t-14' }, 'Not run.')); return null; }
  return responsive(f.body, (w) => {
    const narrow = w < 560;
    const headH = 22, axisH = 24;
    // phones: label on line 1, values on line 2, the CI row on line 3 (no truncation, no text over the diamonds)
    const rowH = narrow ? 76 : 40, labelW = narrow ? 0 : Math.min(190, w * 0.28), valW = narrow ? 0 : 168;
    const iw = Math.max(80, w - labelW - valW - 24);
    const H = headH + rows.length * rowH + axisH;
    const svg = svgIn(f.body, w, H, 'Selection versus holdout results for the recommended plan, as % difference from the holdout mean');
    const ext = d3().max(rows, (r) => Math.max(Math.abs(r.dSel), Math.abs(r.dLo), Math.abs(r.dHi))) || 0.1;
    const x = d3().scaleLinear().domain([-ext * 1.12, ext * 1.12]).nice(4).range([labelW + 8, labelW + 8 + iw]);
    const top = headH, bottom = headH + rows.length * rowH;
    // column headers: the ✓/✕ column is named so the glyph is never the only signal
    if (!narrow) {
      svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', 11).attr('x', 0).attr('y', 10).attr('fill', theme.color.faint).text('KPI');
      svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', 11).attr('x', w).attr('y', 10).attr('text-anchor', 'end').attr('fill', theme.color.faint).text('SELECTION → HOLDOUT · IN CI');
    } else {
      svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', 11).attr('x', w).attr('y', 10).attr('text-anchor', 'end').attr('fill', theme.color.faint).text('SEL → HOLDOUT · IN CI');
    }
    // axis + zero reference (= holdout mean)
    const ticks = x.ticks(narrow ? 3 : 5);
    const ax = svg.append('g');
    ticks.forEach((t) => {
      ax.append('line').attr('class', 'gnm-grid-line').attr('x1', x(t)).attr('x2', x(t)).attr('y1', top).attr('y2', bottom).attr('stroke', theme.color.line).attr('stroke-opacity', t === 0 ? 0 : 0.5);
      ax.append('text').attr('class', 'gnm-tick').attr('font-family', theme.font.mono).attr('font-size', 11).attr('x', x(t)).attr('y', bottom + 16).attr('text-anchor', 'middle').attr('fill', theme.color.faint).text(fmtSignedPct(t, 0));
    });
    refLine(svg, { x1: x(0), x2: x(0), y1: top - 2, y2: bottom, label: narrow ? '' : 'holdout mean', labelAt: 'start', anchor: 'middle', dx: 0, dy: -4 });
    rows.forEach((r, i) => {
      const y0 = top + i * rowH, cy = narrow ? y0 + 56 : y0 + rowH / 2;
      const g = svg.append('g');
      g.append('line').attr('x1', x(r.dLo)).attr('x2', x(r.dHi)).attr('y1', cy).attr('y2', cy).attr('stroke', theme.series.recommended).attr('stroke-width', 2);
      [r.dLo, r.dHi].forEach((v) => g.append('line').attr('x1', x(v)).attr('x2', x(v)).attr('y1', cy - 5).attr('y2', cy + 5).attr('stroke', theme.series.recommended));
      g.append('circle').attr('cx', x(0)).attr('cy', cy).attr('r', 4.5).attr('fill', theme.series.recommended);
      const sx = x(r.dSel);
      g.append('path').attr('d', d3().symbol(d3().symbolDiamond, 64)()).attr('transform', `translate(${sx},${cy})`).attr('fill', theme.color.bg).attr('stroke', theme.series.neutral).attr('stroke-width', 2);
      // the selection value sits beside its own diamond, on the side away from the CI
      if (!r.ok) {
        const leftSide = r.dSel < 0;
        g.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', 11).attr('x', sx + (leftSide ? -9 : 9)).attr('y', cy).attr('dy', '0.32em').attr('text-anchor', leftSide ? 'end' : 'start').attr('fill', theme.color.muted).text(fmtSignedPct(r.dSel, 0));
      }
      const txt = `${fmtU(r.selection_recommended, r)} → ${fmtU(r.holdout_recommended, r)}`;
      const flag = r.ok ? '✓ in' : '✕ out';
      if (narrow) g.append('text').attr('class', 'gnm-label gnm-label--strong').attr('x', 0).attr('y', y0 + 12).attr('dy', '0.32em').text(truncate(label(r.id), w));
      else g.append('text').attr('class', 'gnm-label').attr('x', 0).attr('y', cy).attr('dy', '0.32em').text(truncate(label(r.id), labelW - 12));
      const vt = g.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('font-size', narrow ? 11 : null).attr('x', narrow ? 0 : w).attr('y', narrow ? y0 + 30 : cy).attr('dy', '0.32em').attr('text-anchor', narrow ? 'start' : 'end').attr('fill', theme.color.text);
      vt.append('tspan').text(`${txt}  `);
      vt.append('tspan').attr('fill', r.ok ? theme.color.text : theme.color.muted).attr('font-weight', r.ok ? 400 : 600).text(flag);
    });
  });
}

const fmtSignedPct = (v, d = 1) => (!num(v) ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${(Math.abs(v) * 100).toFixed(d).replace(/\.0$/, '')}%`);

function fmtV(v, r) {
  if (!num(v)) return '—';
  if (r?.unit === '%' || (Math.abs(v) <= 1 && Math.abs(r?.target_hi ?? v) <= 1)) return fmtPct(v);
  return Math.abs(v) >= 100 ? fmtInt(v) : fmtNum(v, 1);
}
