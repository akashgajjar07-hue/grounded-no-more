/**
 * 01 · Mission Control — the landing workspace.
 * Data: kpis.json, parts.json, policies.json, frontier.json, network.json, actions.json (+ story.json on demand)
 *
 * Above the fold: the blueprint hero (title, tagline, a one-sentence story built from the KPIs, the plan-view
 * aircraft with the most urgent missing part marked) and four KPI instruments.
 * Below: the P0 / P1 / P2 / recommended comparison strip (dot-and-whisker, holdout CIs), the top five
 * priority actions (deep links into #/actions?id=…) and a network mini-map with station risk.
 * Every number on screen comes from the JSON exports; nothing is hard-coded.
 * Story hooks: mission-hero, mission-aircraft, mission-kpis, mission-compare, mission-actions, mission-map.
 */
import { h, card, kpiTile, provChip, pill, icon, inlineSVG, storyMode } from '../ui.js';
import { chartFrame, responsive, svgIn, axisBottom, styleAxis, barList, withTooltip, truncate, theme, sparkline, fmtByUnit, fmtPct, fmtPts, fmtHours, fmtAED, fmtInt } from '../charts/theme.js';
import { renderNetworkMap } from '../charts/map.js';
import { assetURL } from '../data.js';

export const data = ['kpis', 'parts', 'policies', 'frontier', 'network', 'actions'];

const HOTSPOTS = ['21', '24', '27', '29', '32', '34', '36', '49'];
const SEV_RANK = { urgent: 0, review: 1, info: 2 };
const d3 = () => window.d3;

/** Inject the view stylesheet once; resolves when it has loaded (or after a short timeout). */
function ensureCSS() {
  const id = 'css-mission-control';
  const existing = document.getElementById(id);
  if (existing) return existing.__ready || Promise.resolve();
  const link = h('link', { id, rel: 'stylesheet', href: assetURL('css/views/mission-control.css') });
  link.__ready = new Promise((res) => { link.onload = res; link.onerror = res; setTimeout(res, 1500); });
  document.head.append(link);
  return link.__ready;
}

const ataOf = (pn) => (String(pn || '').match(/^GN-(\d{2})-/) || [])[1];
const num = (v) => typeof v === 'number' && Number.isFinite(v);
const cap = (s) => String(s || '').charAt(0).toUpperCase() + String(s || '').slice(1);

/** Rank planner actions: severity, then risk score, then due week. */
function rankActions(list = []) {
  return list.slice().sort((a, b) =>
    (SEV_RANK[a.severity] ?? 3) - (SEV_RANK[b.severity] ?? 3) ||
    (b.evidence?.risk_score ?? 0) - (a.evidence?.risk_score ?? 0) ||
    (a.due_week ?? 0) - (b.due_week ?? 0));
}

export async function render(el, ctx) {
  await ensureCSS();
  const { kpis, parts, policies, frontier, network, actions } = ctx.data;
  const cleanups = [];
  const K = Object.fromEntries((kpis.kpis || []).map((k) => [k.id, k]));
  const split = kpis.split || policies.split || 'holdout';
  const nSeeds = policies.n_seeds ?? kpis.seeds?.length;
  const seedText = num(nSeeds) ? `${nSeeds} ${split} seeds` : `${split} seeds`;
  const baseLabel = kpis.baseline_label || kpis.baseline_id || 'P0';
  const recId = kpis.recommended_id || frontier.recommended;
  const ranked = rankActions(actions.actions || []);
  const partBy = Object.fromEntries((parts.parts || []).map((p) => [p.pn, p]));
  const ataName = Object.fromEntries((parts.ata_systems || []).map((a) => [a.ata, a.name]));

  // ================================================================ HERO
  const fr = K.immediate_fill_rate, ao = K.aog_hours, sc = K.spare_capital_aed;
  const clauses = [];
  if (fr && num(fr.value) && num(fr.baseline)) clauses.push([`${fr.value >= fr.baseline ? 'lifts' : 'moves'} immediate material fill rate from `, h('b', {}, fmtPct(fr.baseline)), ' to ', h('b', {}, fmtPct(fr.value))]);
  if (ao && num(ao.value) && num(ao.baseline)) clauses.push([`${ao.value <= ao.baseline ? 'cuts' : 'raises'} modelled material AOG from `, h('b', {}, fmtHours(ao.baseline)), ' to ', h('b', {}, fmtHours(ao.value)), ' a year']);
  const story = h('p', { class: 'mc-story' });
  if (clauses.length) {
    const parts2 = [`Across ${seedText}, the recommended stocking plan${recId ? ` (${recId})` : ''} `];
    clauses.forEach((c, i) => { if (i) parts2.push(i === clauses.length - 1 ? ' and ' : ', '); parts2.push(...c); });
    if (sc && num(sc.value) && num(sc.baseline)) {
      const d = sc.value - sc.baseline;
      parts2.push(d >= 0 ? ', for ' : ', while releasing ', h('b', {}, fmtAED(Math.abs(d))), d >= 0 ? ' more spare capital than ' : ' of spare capital versus ', baseLabel);
    }
    parts2.push('.');
    story.append(...parts2);
  } else story.append('Headline results have not been run yet.');

  // the most urgent missing part that sits on a drawn ATA zone
  const hot = ranked.find((a) => a.severity === 'urgent' && HOTSPOTS.includes(ataOf(a.pn))) || ranked.find((a) => HOTSPOTS.includes(ataOf(a.pn)));
  const hotAta = hot ? ataOf(hot.pn) : null;
  const hotPart = hot ? partBy[hot.pn] : null;

  const startTour = async () => {
    try {
      const s = await ctx.load('story');
      storyMode({ steps: s.steps || [], navigate: ctx.navigate }).start();
    } catch (e) { console.warn('story unavailable', e); }
  };

  const fig = h('div', { class: 'mc-fig', dataset: { story: 'mission-aircraft' }, role: 'group', 'aria-label': 'Aircraft systems with spare-part risk' });
  const fault = hot
    ? h('a', { class: 'mc-fault', href: ctx.buildHash('actions', { id: hot.exception_id }), 'aria-label': `Urgent: ${hot.summary}. Open action ${hot.exception_id}` },
      icon('alert'),
      h('div', {},
        h('div', { class: 'mc-fault-k' }, `${cap(hot.severity)} · ATA ${hotAta} · ${hot.station}`),
        h('div', { class: 'mc-fault-pn' }, hot.pn),
        h('div', { class: 'mc-fault-d' }, [hotPart?.desc, hot.evidence?.deadline ? `deadline class ${hot.evidence.deadline} (hypothetical)` : null].filter(Boolean).join(' · ') || hot.summary)))
    : null;
  // accessible list alternative for the drawing's hotspots
  const ataList = h('ul', { class: 'sr-only', 'aria-label': 'Aircraft systems (open Parts Intelligence)' },
    HOTSPOTS.map((a) => h('li', {}, h('a', { href: ctx.buildHash('parts', { ata: a, pn: a === hotAta ? hot.pn : undefined }) }, `ATA ${a} ${ataName[a] || ''}${a === hotAta ? ` — urgent missing part ${hot.pn} at ${hot.station}` : ''}`))));

  const hero = card({
    cls: 'mc-hero-card', bp: true, story: 'mission-hero', flush: true,
    body: h('div', { class: 'mc-hero' },
      h('div', { class: 'mc-copy' },
        h('div', { class: 'mc-eyebrow' }, '01 · Mission Control ', h('span', { class: 'faint' }, '· Falcon Hub Airways (fictional)')),
        h('h1', { class: 'mc-title' }, h('span', {}, 'Grounded'), h('span', { class: 'mc-title-accent' }, 'No More')),
        h('p', { class: 'mc-tagline' }, 'A single missing part can ground an aircraft. Know which ones, where, and what to do about it.'),
        story,
        h('div', { class: 'mc-cta' },
          h('button', { class: 'btn btn--primary', type: 'button', onclick: startTour, dataset: { story: 'mission-start' } }, icon('play'), 'Start the story'),
          h('a', { class: 'btn btn--ghost', href: '#/actions' }, 'Open action centre', icon('chevron-right'))),
        h('div', { class: 'mc-meta' }, provChip(kpis.meta?.provenance || 'SIMULATED'), h('span', { class: 'chip chip-mono' }, seedText), h('span', { class: 'chip chip-mono' }, `Baseline ${baseLabel}`))),
      h('div', { class: 'mc-figwrap' }, fig, fault, ataList)),
  });
  el.append(hero);

  inlineSVG('blueprint-aircraft-top.svg').then((svg) => {
    if (!fig.isConnected && !el.contains(fig)) return;
    svg.setAttribute('viewBox', svg.dataset.compactViewbox || svg.getAttribute('viewBox'));
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.classList.add('bp-compact');
    svg.setAttribute('aria-label', 'Plan view of a generic twin-engine airliner (original schematic) with ATA system hotspots');
    svg.querySelectorAll('.ata-hotspot').forEach((g) => {
      const a = g.dataset.ata;
      const missing = a === hotAta;
      g.classList.toggle('is-missing', missing);
      g.setAttribute('aria-label', `ATA ${a} ${ataName[a] || g.dataset.name || ''}${missing ? `: urgent missing part ${hot.pn} at ${hot.station}` : ''}. Open Parts Intelligence`);
      const go = () => ctx.navigate(ctx.buildHash('parts', { ata: a, pn: missing ? hot.pn : undefined }));
      g.addEventListener('click', go);
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
    fig.classList.add('bp-figure');
    fig.replaceChildren(svg);
  }).catch(() => fig.replaceChildren(h('p', { class: 'faint t-12' }, 'Aircraft drawing unavailable.')));

  // ================================================================ KPI instruments
  const openK = K.open_actions || K.open_exceptions || {
    id: 'open_actions', label: 'Open planner actions', value: (actions.actions || []).length, unit: '', provenance: actions.meta?.provenance || 'DERIVED', ci: null, delta: null, baseline: null,
  };
  const tiles = [
    fr && { ...fr, label: fr.label && /material/i.test(fr.label) ? fr.label : 'Immediate material fill rate' },
    ao && { ...ao, label: ao.label && /material/i.test(ao.label) ? ao.label : 'Material AOG hours / year' },
    sc,
    openK,
  ].filter(Boolean).map((k) => kpiInstrument(k, baseLabel, ranked, k.recommended_id || recId || 'Rec.'));
  el.append(h('div', { class: 'mc-kpis', dataset: { story: 'mission-kpis' }, role: 'group', 'aria-label': 'Headline indicators' }, tiles));

  // ================================================================ comparison + actions | map
  const left = h('div', { class: 'mc-col' });
  const right = h('div', { class: 'mc-col' });
  el.append(h('div', { class: 'mc-grid' }, left, right));

  // ---- P0 / P1 / P2 / recommended strip
  const cmpCard = h('section', { class: 'card', dataset: { story: 'mission-compare' } });
  left.append(cmpCard);
  cleanups.push(compareStrip(cmpCard, { policies, frontier, seedText, baseLabel }));

  // ---- top 5 priority actions (one per part number, so the list shows breadth)
  const seenPn = new Set();
  const top = ranked.filter((a) => (seenPn.has(a.pn) ? false : seenPn.add(a.pn))).slice(0, 5);
  const nUrg = (actions.actions || []).filter((a) => a.severity === 'urgent').length;
  left.append(card({
    story: 'mission-actions', kicker: 'Planner priorities', prov: actions.meta?.provenance || 'DERIVED',
    title: (actions.actions || []).length ? `${fmtInt(nUrg)} urgent of ${fmtInt((actions.actions || []).length)} open actions; the top five` : 'No open actions exported',
    body: h('div', { class: 'mc-actions' }, top.map((a, i) => h('a', { class: 'mc-action', href: ctx.buildHash('actions', { id: a.exception_id }), 'aria-label': `${cap(a.severity)}: ${a.summary}. ${a.recommended_action || ''}` },
      h('span', { class: 'mc-action-rank', 'aria-hidden': 'true' }, String(i + 1).padStart(2, '0')),
      pill(SEV_RANK[a.severity] != null ? a.severity : 'unknown'),
      h('div', { style: { minWidth: 0 } }, h('div', { class: 'mc-action-title' }, a.summary), h('div', { class: 'mc-action-meta' }, [a.exception_id, a.pn, a.station, num(a.due_week) ? `due W${a.due_week}` : null, a.owner].filter(Boolean).join(' · '))),
      h('span', { class: 'mc-action-do' }, a.recommended_action || 'Review', icon('chevron-right'))))),
    foot: [h('span', {}, 'Ranked by severity; one action per part number'), h('a', { class: 'card-link', href: '#/actions' }, 'Open Planner Action Centre', icon('chevron-right'))],
  }));

  // ---- network mini-map
  const mapCard = h('section', { class: 'card', dataset: { story: 'mission-map' } });
  right.append(mapCard);
  const stations = (network.stations || []).slice();
  const byRisk = stations.filter((s) => num(s.risk)).sort((a, b) => b.risk - a.risk);
  const topS = byRisk[0];
  const hub = stations.find((s) => s.role === 'hub');
  const nOut = stations.filter((s) => s.role !== 'hub').length;
  const topOut = byRisk.find((s) => s.role !== 'hub');
  const mf = chartFrame(mapCard, {
    headline: topS ? `${topS.station} carries the most grounding exposure${topOut && topOut !== topS ? `; ${topOut.station} is the riskiest outstation (${fmtPct(topOut.risk, 0)} of ${topS.station})` : ` (${fmtPct(topS.risk, 0)})`}` : 'Station risk not run',
    subtitle: `Station risk: ${network.risk_definition || 'material AOG exposure relative to the worst station'}, 0–100% · ${hub ? `${hub.station} hub + ${nOut} outstations · ` : ''}arc width = transfers`,
    provenance: network.meta?.provenance || 'SIMULATED', source: 'network.json',
    table: { columns: [{ key: 'station', label: 'Station', mono: true }, { key: 'role', label: 'Role' }, { key: 'risk', label: 'Risk', num: true, format: (v) => fmtPct(v, 0) }, { key: 'serviceable_units', label: 'Serviceable units', num: true, format: fmtInt }, { key: 'stock_value', label: 'Stock value', num: true, format: fmtAED }], rows: byRisk },
  });
  const mapHost = h('div', { class: 'mc-map' });
  const listHost = h('div', { class: 'mc-stations' });
  mf.body.append(mapHost, listHost);
  let map = null;
  renderNetworkMap(mapHost, {
    stations, arcs: network.arcs || [], selected: topS?.station, inset: false, aspect: 0.62, label: 'Network map: hub and outstations',
    onSelect: (id) => ctx.navigate(ctx.buildHash('network', { station: id })),
  }).then((m) => { map = m; }).catch((e) => { console.warn('map unavailable', e); mapHost.replaceChildren(h('p', { class: 'faint t-12' }, 'Map unavailable.')); });
  cleanups.push(barList(listHost, { rows: byRisk.map((s, i) => ({ label: `${s.station} · ${s.role === 'hub' ? 'hub' : 'outstation'}`, value: s.risk, highlight: i === 0 })), format: (v) => fmtPct(v, 0), max: 1, barHeight: 6 }));

  return () => { cleanups.forEach((f) => { try { f?.(); } catch { /* ignore */ } }); map?.destroy(); };
}

// ------------------------------------------------------------------ KPI instrument
function kpiInstrument(k, baseLabel, ranked, recLabel) {
  const fmt = !k.unit ? fmtInt : fmtByUnit(k.unit);
  const dfmt = k.unit === '%' ? fmtPts : fmt;
  const hasDelta = num(k.delta);
  const tile = kpiTile({ ...k, delta: hasDelta ? k.delta : 0, ci: Array.isArray(k.ci) ? k.ci : null }, { format: fmt, deltaFormat: dfmt, sparkline });
  const ref = tile.querySelector('.kpi-delta-ref');
  if (ref) ref.textContent = ` vs ${baseLabel}`;
  const footSpans = tile.querySelectorAll('.kpi-foot > span');
  if (!hasDelta) {
    const urgent = ranked.filter((a) => a.severity === 'urgent').length;
    const nU = k.by_severity?.urgent ?? urgent;
    tile.querySelector('.kpi-delta')?.replaceWith(h('span', { class: 'kpi-delta is-flat' }, pill(nU ? 'urgent' : 'ok', `${fmtInt(nU)} urgent`), k.by_severity?.review != null ? h('span', { class: 'kpi-delta-ref' }, ` · ${fmtInt(k.by_severity.review)} review`) : null));
  }
  if (footSpans[1]) footSpans[1].textContent = num(k.baseline) ? `${baseLabel} ${fmt(k.baseline)}` : num(k.as_of_week) ? `As of W${k.as_of_week}` : 'Source: actions.json';
  if (!Array.isArray(k.spark)) {
    const sp = tile.querySelector('.kpi-spark');
    // no time series exported: show a baseline → recommended dumbbell with both 95% CIs instead
    if (sp && num(k.baseline) && num(k.value)) sp.replaceWith(dumbbell(k, fmt, baseLabel, recLabel));
    else sp?.remove();
  }
  if (footSpans[0] && !Array.isArray(k.ci)) footSpans[0].textContent = k.provenance === 'DERIVED' ? 'Count, no interval' : 'No interval';
  // provenance chip moves from the label row to the delta row so labels get the full width
  const chip = tile.querySelector('.kpi-top .chip-prov');
  const delta = tile.querySelector('.kpi-delta');
  if (chip && delta) { const row = h('div', { class: 'mc-kpi-row' }); delta.replaceWith(row); row.append(delta, chip); }
  tile.dataset.kpi = k.id;
  return tile;
}

/** Baseline → recommended dumbbell on a shared track, with each value's 95% CI as a faint band. */
function dumbbell(k, fmt, baseLabel, recLabel) {
  const bci = Array.isArray(k.baseline_ci) ? k.baseline_ci : [k.baseline, k.baseline];
  const rci = Array.isArray(k.ci) ? k.ci : [k.value, k.value];
  const all = [...bci, ...rci, k.baseline, k.value].filter(num);
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1; lo -= pad; hi += pad;
  const pct = (v) => `${((v - lo) / (hi - lo)) * 100}%`;
  const span = (a, b, cls) => h('span', { class: cls, style: { left: pct(Math.min(a, b)), width: `calc(${pct(Math.max(a, b))} - ${pct(Math.min(a, b))})` } });
  const recLeft = k.value < k.baseline;
  return h('div', { class: 'mc-db', role: 'img', 'aria-label': `${baseLabel} ${fmt(k.baseline)} to ${recLabel} ${fmt(k.value)}${k.reference && num(k.reference.value) ? `; ${k.reference.id || 'reference'} ${fmt(k.reference.value)}` : ''}` },
    h('div', { class: 'mc-db-track' },
      span(bci[0], bci[1], 'mc-db-ci mc-db-ci--base'), span(rci[0], rci[1], 'mc-db-ci mc-db-ci--rec'), span(k.baseline, k.value, 'mc-db-seg'),
      h('span', { class: 'mc-db-dot mc-db-dot--base', style: { left: pct(k.baseline) } }), h('span', { class: 'mc-db-dot mc-db-dot--rec', style: { left: pct(k.value) } })),
    h('div', { class: 'mc-db-labels', 'aria-hidden': 'true' },
      h('span', { class: recLeft ? 'is-rec' : 'is-base' }, recLeft ? recLabel : baseLabel),
      k.reference && num(k.reference.value) ? h('span', { class: 'is-ref' }, `${k.reference.id || 'ref'} ${fmt(k.reference.value)}`) : null,
      h('span', { class: recLeft ? 'is-base' : 'is-rec' }, recLeft ? baseLabel : recLabel)));
}

// ------------------------------------------------------------------ P0 / P1 / P2 / recommended strip
function compareStrip(host, { policies, frontier, seedText, baseLabel }) {
  const P = policies.policies || [];
  const get = (id) => P.find((p) => p.policy_id === id);
  const rows = [];
  ['P0', 'P1', 'P2'].forEach((id) => {
    const p = get(id);
    const a = p?.kpi?.aog_hours;
    if (a && num(a.mean)) rows.push({ key: id, name: id, label: p.label || id, value: a.mean, lo: a.ci_lo ?? a.mean, hi: a.ci_hi ?? a.mean, capital: p.kpi?.spare_capital_aed?.mean, role: id === 'P0' ? 'base' : 'ctx' });
  });
  const recId = frontier?.recommended;
  const recP = (frontier?.points || []).find((p) => p.id === recId);
  const recPol = recId ? get(recId) : null;
  if (recPol?.kpi?.aog_hours && !rows.some((r) => r.key === recId)) {
    const a = recPol.kpi.aog_hours;
    rows.push({ key: 'REC', name: `Recommended · ${recId}`, label: String(recPol.label || 'frontier point').replace(/^Recommended:\s*/, ''), value: a.mean, lo: a.ci_lo, hi: a.ci_hi, capital: recPol.kpi?.spare_capital_aed?.mean, role: 'rec' });
  } else if (recP && num(recP.aog_hours)) {
    const ci = Array.isArray(recP.aog_ci) ? recP.aog_ci : [recP.aog_hours, recP.aog_hours];
    rows.push({ key: 'REC', name: `Recommended · ${recId}`, label: recP.label || 'balanced frontier point', value: recP.aog_hours, lo: ci[0], hi: ci[1], capital: recP.capital_aed, role: 'rec' });
  }
  const base = rows.find((r) => r.role === 'base');
  const rec = rows.find((r) => r.role === 'rec');
  let headline = 'Policy comparison not run';
  if (base && rec) {
    const pct = Math.round((1 - rec.value / base.value) * 100);
    const dCap = num(rec.capital) && num(base.capital) ? rec.capital - base.capital : null;
    const overlap = rec.hi >= base.lo && rec.lo <= base.hi;
    const capTxt = dCap == null ? '' : dCap >= 0 ? `, for ${fmtAED(dCap)} more spare capital` : `, while releasing ${fmtAED(-dCap)} of spare capital`;
    headline = `The recommended plan ${pct >= 0 ? 'cuts' : 'raises'} modelled material AOG by ${Math.abs(pct)}% versus ${baseLabel}${capTxt}; the 95% intervals ${overlap ? 'overlap' : 'do not overlap'}`;
  } else if (rows.length) {
    const best = rows.reduce((a, b) => (a.value < b.value ? a : b));
    headline = `${best.name} has the lowest modelled material AOG (${fmtHours(best.value)} a year)`;
  }
  const fSplit = frontier?.split || frontier?.meta?.split;
  const vals = rows.flatMap((r) => [r.lo, r.hi]).filter((v) => num(v) && v > 0);
  const log = vals.length && Math.max(...vals) / Math.min(...vals) > 8;
  const f = chartFrame(host, {
    headline,
    subtitle: `Material AOG hours per year · mean and 95% CI · ${seedText}${fSplit && !seedText.includes(fSplit) ? ` (recommended point: ${fSplit} seeds)` : ''}${log ? ' · log scale' : ''} · capital = simulated spare capital`,
    provenance: policies.meta?.provenance || 'SIMULATED', source: 'policies.json + frontier.json',
    table: { columns: [{ key: 'name', label: 'Policy' }, { key: 'label', label: 'Description' }, { key: 'value', label: 'AOG h/yr', num: true, format: fmtHours }, { key: 'lo', label: 'CI low', num: true, format: fmtHours }, { key: 'hi', label: 'CI high', num: true, format: fmtHours }, { key: 'capital', label: 'Spare capital', num: true, format: fmtAED }], rows },
  });
  if (!rows.length) { f.body.append(h('p', { class: 'faint t-14' }, 'Not run.')); return null; }

  return responsive(f.body, (w) => {
    const narrow = w < 560;
    const rowH = narrow ? 58 : 50;
    const m = narrow ? { top: 8, right: 8, bottom: 28, left: 8 } : { top: 8, right: 132, bottom: 28, left: 196 };
    const iw = Math.max(60, w - m.left - m.right), ih = rows.length * rowH;
    const svg = svgIn(f.body, w, ih + m.top + m.bottom, 'Material AOG hours by policy, mean and 95% interval');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const x = log ? d3().scaleLog().domain([lo / 1.35, hi * 1.35]).range([0, iw]) : d3().scaleLinear().domain([0, hi * 1.1]).nice().range([0, iw]);
    // log ticks at 1-3-10 steps
    let ticks = null;
    if (log) {
      ticks = [];
      for (let e = Math.floor(Math.log10(lo / 1.35)); e <= Math.ceil(Math.log10(hi * 1.35)); e++) [1, 3].forEach((mlt) => { const t = mlt * 10 ** e; if (t >= x.domain()[0] && t <= x.domain()[1]) ticks.push(t); });
      if (narrow && ticks.length > 4) ticks = ticks.filter((t) => String(t)[0] === '1');
    }
    const ax = g.append('g');
    if (ticks) styleAxis(ax.attr('transform', `translate(0,${ih})`).call(d3().axisBottom(x).tickValues(ticks).tickFormat(fmtHours).tickSize(4).tickPadding(6).tickSizeOuter(0)));
    else axisBottom(ax, x, { ticks: narrow ? 3 : 5, format: fmtHours, height: ih });
    // faint vertical guides at ticks
    g.append('g').attr('class', 'gnm-grid').selectAll('line').data(ticks || x.ticks(5)).join('line').attr('x1', (d) => x(d)).attr('x2', (d) => x(d)).attr('y1', 0).attr('y2', ih);

    const color = (r) => (r.role === 'rec' ? theme.color.accent : r.role === 'base' ? theme.color.accent2 : theme.color.muted);
    rows.forEach((r, i) => {
      const y0 = i * rowH;
      const cy = narrow ? y0 + 38 : y0 + rowH / 2;
      const row = g.append('g').attr('class', 'mc-cmp-row').datum(r);
      row.append('rect').attr('x', narrow ? 0 : -m.left).attr('y', y0 + 2).attr('width', narrow ? iw : w).attr('height', rowH - 4).attr('rx', 6).attr('fill', r.role === 'rec' ? 'rgba(34,199,184,0.06)' : 'transparent');
      // labels
      if (narrow) {
        row.append('text').attr('class', r.role === 'rec' ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 8).attr('y', y0 + 16).attr('dy', '0.32em').text(truncate(`${r.name} · ${r.label}`, iw * 0.58));
        row.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', iw - 8).attr('y', y0 + 16).attr('dy', '0.32em').attr('text-anchor', 'end').attr('fill', r.role === 'rec' ? theme.color.text : theme.color.muted).text(`${fmtHours(r.value)}${num(r.capital) ? ` · ${fmtAED(r.capital)}` : ''}`);
      } else {
        row.append('text').attr('class', r.role === 'rec' ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', -m.left + 16).attr('y', cy - 8).attr('dy', '0.32em').attr('fill', r.role === 'rec' ? theme.color.text : null).text(r.name);
        row.append('text').attr('class', 'gnm-label').attr('x', -m.left + 16).attr('y', cy + 9).attr('dy', '0.32em').attr('fill', theme.color.faint).text(truncate(r.label, m.left - 28));
        row.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', iw + m.right - 16).attr('y', cy - 8).attr('dy', '0.32em').attr('text-anchor', 'end').attr('fill', r.role === 'rec' ? theme.color.text : theme.color.muted).text(fmtHours(r.value));
        if (num(r.capital)) row.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', iw + m.right - 16).attr('y', cy + 9).attr('dy', '0.32em').attr('text-anchor', 'end').attr('fill', theme.color.faint).text(fmtAED(r.capital));
      }
      // whisker + dot
      const c = color(r);
      row.append('line').attr('x1', x(r.lo)).attr('x2', x(r.hi)).attr('y1', cy).attr('y2', cy).attr('stroke', c).attr('stroke-width', r.role === 'rec' ? 2.5 : 1.5).attr('stroke-opacity', 0.85);
      [r.lo, r.hi].forEach((v) => row.append('line').attr('x1', x(v)).attr('x2', x(v)).attr('y1', cy - 5).attr('y2', cy + 5).attr('stroke', c).attr('stroke-opacity', 0.85));
      row.append('circle').attr('cx', x(r.value)).attr('cy', cy).attr('r', r.role === 'rec' ? 6 : 4.5).attr('fill', r.role === 'rec' ? c : theme.color.bg).attr('stroke', c).attr('stroke-width', 2);
    });
    // one annotation: the recommended reduction versus the baseline
    if (base && rec) {
      const i = rows.indexOf(rec);
      const cy = narrow ? i * rowH + 38 : i * rowH + rowH / 2;
      const pct = Math.round((1 - rec.value / base.value) * 100);
      const xEnd = x(rec.hi) + 6;
      const room = iw - xEnd;
      if (room > 90) g.append('text').attr('class', 'gnm-annot-text').attr('x', xEnd + 8).attr('y', cy).attr('dy', '0.32em').attr('fill', theme.color.accent).text(`${pct >= 0 ? '−' : '+'}${Math.abs(pct)}% vs ${base.name}`);
    }
    withTooltip(g.selectAll('g.mc-cmp-row'), (d) => ({ title: `${d.name} · ${d.label}`, rows: [['Mean AOG h/yr', fmtHours(d.value)], ['95% CI', `${fmtHours(d.lo)} – ${fmtHours(d.hi)}`], ['Spare capital', fmtAED(d.capital)]] }));
  });
}
