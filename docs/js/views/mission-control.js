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
import { chartFrame, responsive, svgIn, axisBottom, styleAxis, withTooltip, truncate, theme, sparkline, fmtByUnit, fmtPct, fmtPts, fmtHours, fmtAED, fmtInt, fmtWeek, HEADLINE_MAX } from '../charts/theme.js';
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
  const sysOf = Object.fromEntries((parts.ata_systems || []).map((a) => [a.ata, a]));
  const sysLevel = (a) => sysOf[a]?.system_level || sysOf[a]?.risk_level || null;
  const hotSys = hotAta ? sysLevel(hotAta) : null;
  // the system's display status as Parts prints it (exporter status_label: URGENT / REVIEW / WATCH / OK)
  const hotSysWord = (() => { const w = String(sysOf[hotAta]?.status_label || '').split(' · ')[0]; const v = w || hotSys || ''; return v.toUpperCase() === 'OK' ? 'OK' : v.toLowerCase(); })();

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
        h('div', { class: 'mc-fault-k' }, `${cap(hot.severity)} part`),
        h('div', { class: 'mc-fault-sys', title: `System level = the chapter's share of fleet risk-hours${num(sysOf[hotAta]?.risk_share) ? ` (${fmtPct(sysOf[hotAta].risk_share, 0)})` : ''}, as on Parts Intelligence` }, `ATA ${hotAta}${hotSys ? ` · system ${hotSysWord}` : ''}`),
        h('div', { class: 'mc-fault-pn' }, hot.pn),
        h('div', { class: 'mc-fault-at' }, h('span', {}, hot.station), num(hotPart?.risk_score) ? h('span', { class: 'mc-fault-risk', title: 'Part-level risk score, 0–100 (log-scaled AOG hours)' }, `risk ${Math.round(hotPart.risk_score * 100)}`) : null),
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
    // keep ATA badge numerals ≥ 11 screen px however small the drawing is scaled (critic: ~8 px at 390)
    const sizeBadges = () => {
      const vb = svg.viewBox.baseVal, wpx = svg.getBoundingClientRect().width, hpx = svg.getBoundingClientRect().height;
      if (!vb?.width || !wpx) return;
      const u = Math.max(vb.width / wpx, vb.height / hpx);
      svg.querySelectorAll('.hs-badge').forEach((b) => {
        const c = b.querySelector('circle'); const t = b.querySelector('text');
        if (c) { c.dataset.r0 = c.dataset.r0 || c.getAttribute('r'); c.setAttribute('r', Math.max(+c.dataset.r0, 10 * u)); }
        if (t) t.style.fontSize = `${Math.max(17, 11.5 * u)}px`;
      });
    };
    sizeBadges();
    const ro = new ResizeObserver(() => requestAnimationFrame(sizeBadges)); ro.observe(fig); cleanups.push(() => ro.disconnect());
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
  ].filter(Boolean).map((k) => kpiInstrument(k, baseLabel, ranked, k.recommended_id || recId || 'Rec.', actions));
  el.append(h('div', { class: 'mc-kpis', dataset: { story: 'mission-kpis' }, role: 'group', 'aria-label': 'Headline indicators' }, tiles));

  // ================================================================ comparison + actions | map
  const left = h('div', { class: 'mc-col' });
  const right = h('div', { class: 'mc-col' });
  el.append(h('div', { class: 'mc-grid' }, left, right));

  // ---- P0 / P1 / P2 / recommended strip
  const cmpCard = h('section', { class: 'card', dataset: { story: 'mission-compare' } });
  left.append(cmpCard);
  cleanups.push(compareStrip(cmpCard, { policies, frontier, seedText, baseLabel }));

  // ---- top 5 priority part numbers: a scannable grid, actions grouped by PN (critic #5)
  const all = actions.actions || [];
  const groups = groupByPn(ranked).slice(0, 5);
  const nUrg = all.filter((a) => a.severity === 'urgent').length;
  const nUrgPn = new Set(all.filter((a) => a.severity === 'urgent').map((a) => a.pn)).size;
  const lookback = all.find((a) => num(a.evidence?.lookback_weeks) && a.type === 'OUTSTATION_DEPLETION')?.evidence.lookback_weeks;
  // canonical per-PN AOG metric shared with the Action Centre: the largest single-station total in the last 52 weeks
  // (exporter field aog_h_52w_max_station when present, else the max over the PN's actions), with the exporter's label
  const aogMeta = parts.aog_metric_labels?.aog_h_52w_max_station;
  const aogLabel = (typeof aogMeta === 'string' ? aogMeta : aogMeta?.label) || `AOG h · last ${lookback || 52} wk · worst station`;
  // C1 (wave 4): the worst-station number always travels with its station id ("120 h · AUH")
  groups.forEach((g) => { const pv = partBy[g.pn]?.aog_h_52w_max_station; if (num(pv)) { g.aog = pv; g.aogSt = partBy[g.pn]?.aog_h_52w_max_station_id || null; } else if (g.aog != null) g.aogSt = g.list.find((a) => a.evidence?.aog_hours_lookback === g.aog)?.station || null; });
  const head = h('div', { class: 'mc-pr mc-pr--head', 'aria-hidden': 'true' },
    h('span', {}, 'Severity'), h('span', {}, 'Part · where'), h('span', {}, 'Signal · next step'), h('span', { class: 'num mc-pr-aogh', title: aogLabel }, h('span', {}, 'AOG h · 52 wk'), h('span', {}, 'worst station')), h('span', { class: 'num' }, 'Due'), h('span', {}));
  const rowsEl = groups.map((g) => {
    const a = g.lead;
    const sig = signalOf(a);
    const where = g.stations.length ? (g.stations.length > 1 ? `${g.stations[0]} +${g.stations.length - 1} station${g.stations.length > 2 ? "s" : ""}` : g.stations[0]) : 'Network';
    const label = `${cap(a.severity)}: ${a.pn}${g.stations.length ? ` at ${g.stations.join(', ')}` : ''}. ${sig.long}. ${a.recommended_action || ''}`;
    return h('a', { class: `mc-pr is-${a.severity}`, href: ctx.buildHash('actions', { id: a.exception_id }), 'aria-label': label, title: a.summary },
      h('span', { class: 'mc-pr-sev' }, pill(SEV_RANK[a.severity] != null ? a.severity : 'unknown')),
      h('span', { class: 'mc-pr-part' }, h('span', { class: 'mc-pr-pn' }, a.pn), h('span', { class: 'mc-pr-where', title: g.stations.join(', ') }, where),
        // C10 (wave 4): the exception type, so a low-risk PN ranked urgent for planning data is not puzzling
        h('span', { class: 'mc-pr-type', title: `${a.type_label || a.type}: a planning exception, not a grounding-risk score` }, a.type_label || a.type)),
      h('span', { class: 'mc-pr-sig', title: sig.k }, h('span', { class: 'mc-pr-v' }, sig.v), h('span', { class: 'mc-pr-step' }, TYPE_STEP[a.type] || 'Review')),
      h('span', { class: 'mc-pr-aog num', title: aogLabel }, h('span', { class: 'mc-pr-ml' }, 'Worst stn '), g.aog ? [fmtHours(g.aog), g.aogSt ? h('span', { class: 'mc-pr-st', title: g.stations.includes(g.aogSt) ? null : `No open exception at ${g.aogSt}; its 52-week AOG hours are still the worst for this PN` }, ` · ${g.aogSt}`, g.stations.includes(g.aogSt) ? null : h('span', { class: 'mc-pr-noex' }, 'no exception there')) : null] : '—'),
      h('span', { class: 'mc-pr-due num' }, h('span', { class: 'mc-pr-ml' }, 'Due '), num(g.due) ? fmtWeek(g.due) : '—'),
      h('span', { class: 'mc-pr-do', 'aria-hidden': 'true' }, icon('chevron-right')));
  });
  left.append(card({
    story: 'mission-actions', kicker: 'Planner priorities', prov: actions.meta?.provenance || 'DERIVED',
    title: all.length ? `${fmtInt(nUrg)} urgent actions on ${fmtInt(nUrgPn)} part numbers; top ${fmtInt(groups.length)} shown` : 'No open actions exported',
    body: h('div', { class: 'mc-prio', role: 'list' }, head, rowsEl.map((r) => { r.setAttribute('role', 'listitem'); return r; })),
    foot: [h('span', { title: aogMeta?.definition || aogLabel }, `Ranked by severity then risk · ${aogLabel}, as in the Action Centre`), h('a', { class: 'card-link', href: '#/actions' }, 'Open Planner Action Centre', icon('chevron-right'))],
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
    headline: topOut && topOut !== topS
      ? `${topOut.station} is the riskiest outstation (${fmtPct(topOut.risk, 0)} of ${topS.role === 'hub' ? 'hub ' : ''}${topS.station})`
      : topS ? `${topS.station} carries the most grounding exposure` : 'Station risk not run',
    subtitle: `Risk = ${network.risk_definition || 'material AOG exposure vs the worst station'} · ${hub ? `${hub.station} hub + ${nOut} outstations · ` : ''}arc width = transfers`,
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
  listHost.append(h('ul', { class: 'mc-st list-reset', 'aria-label': 'Station risk, share of the worst station' }, byRisk.map((s) => h('li', { class: `mc-st-row${s === topOut ? ' is-focus' : ''}${s.role === 'hub' ? ' is-hub' : ''}` },
    h('a', { href: ctx.buildHash('network', { station: s.station }), class: 'mc-st-l' }, h('span', { class: 'mono' }, s.station), h('span', { class: 'faint' }, s.role === 'hub' ? ' · hub' : ' · outstation')),
    h('span', { class: 'mc-st-bar', 'aria-hidden': 'true' }, h('span', { style: { width: `${Math.max(1, s.risk * 100)}%` } })),
    h('span', { class: 'mc-st-v mono' }, fmtPct(s.risk, 0))))));

  const sysRows = (parts.ata_systems || []).filter((a) => num(a.risk_share)).sort((a, b) => b.risk_share - a.risk_share);
  if (sysRows.length) {
    const nShow = Math.min(4, sysRows.length);
    const lvWord = (l) => (l === 'ok' ? 'OK' : cap(l));
    const nUrgSys = sysRows.filter((a) => (a.system_level || a.risk_level) === 'urgent').length;
    const nWatch = sysRows.filter((a) => (a.system_level || a.risk_level) !== 'urgent' && (a.has_urgent_part ?? a.n_urgent > 0)).length;
    right.append(card({
      story: 'mission-systems', kicker: 'Aircraft systems', prov: 'DERIVED',
      title: (() => { const shownWatch = sysRows.slice(0, nShow).filter((a) => (a.system_level || a.risk_level) !== 'urgent' && (a.has_urgent_part ?? a.n_urgent > 0)).length; return `${fmtInt(nUrgSys)} system${nUrgSys === 1 ? '' : 's'} rate urgent; ${fmtInt(nWatch)} more hold an urgent part${nWatch ? ` (${fmtInt(shownWatch)} shown)` : ''}`; })(),
      body: h('ul', { class: 'mc-sys list-reset' }, sysRows.slice(0, nShow).map((a) => {
        const lv = a.system_level || a.risk_level || 'unknown';
        const nU = a.n_urgent ?? 0;
        // exporter status: system level, raised to WATCH when an OK chapter holds an urgent part (same pill as Parts)
        const tone = a.status || lv;
        const word = String(a.status_label || '').split(' · ')[0] || lvWord(lv);
        return h('li', {}, h('a', { class: `mc-sys-row is-${lv}`, href: ctx.buildHash('parts', { ata: a.ata }), 'aria-label': `ATA ${a.ata} ${a.name}: ${word}, system level ${lvWord(lv)}, ${fmtPct(a.risk_share, 0)} of fleet risk-hours, ${nU} urgent part numbers` },
          h('span', { class: 'mc-sys-ata mono' }, a.ata),
          h('span', { class: 'mc-sys-name' }, a.name, h('span', { class: 'faint mono' }, ` · ${fmtPct(a.risk_share, 0)}`)),
          h('span', { class: 'mc-sys-st', title: `System level ${lvWord(lv)} (share of fleet risk-hours)${nU ? `; ${nU} urgent part number${nU === 1 ? '' : 's'}` : ''}` }, pill(['urgent', 'review', 'ok'].includes(tone) ? tone : 'unknown', word), nU ? h('span', { class: 'mc-sys-urg mono' }, `▲ ${fmtInt(nU)} urgent PN${nU === 1 ? '' : 's'}`) : null)));
      })),
      foot: [h('span', {}, `Top ${fmtInt(nShow)} of ${fmtInt(sysRows.length)} by share of fleet risk-hours · system level and urgent parts are rated separately`), h('a', { class: 'card-link', href: '#/parts' }, 'Parts Intelligence', icon('chevron-right'))],
    }));
  }

  return () => { cleanups.forEach((f) => { try { f?.(); } catch { /* ignore */ } }); map?.destroy(); };
}

// ------------------------------------------------------------------ planner priorities helpers
/** Short imperative per exception type (copy, not data). */
const TYPE_STEP = {
  OUTSTATION_DEPLETION: 'Position stock', LEAD_TIME_DRIFT: 'Update lead time', OVERDUE_REPAIR: 'Chase repair shop',
  EXCESS_DECLINING_DEMAND: 'Cut min/max', CONDEMNED_AWAITING_REPLACEMENT: 'Track replacement PO', QUARANTINE_DOCS: 'Review certificate',
  EXPIRY_RISK: 'Use or rotate stock', KIT_SHORTAGE: 'Complete the kit',
};

/** Group ranked actions by PN, keeping rank order; per group: lead action, stations (by AOG h), summed AOG h, earliest due. */
function groupByPn(ranked) {
  const by = new Map();
  ranked.forEach((a) => {
    if (!by.has(a.pn)) by.set(a.pn, { pn: a.pn, lead: a, list: [] });
    by.get(a.pn).list.push(a);
  });
  return [...by.values()].map((g) => {
    const aogs = g.list.map((a) => a.evidence?.aog_hours_lookback).filter(num);
    const st = g.list.filter((a) => a.station).sort((x, y) => (y.evidence?.aog_hours_lookback ?? 0) - (x.evidence?.aog_hours_lookback ?? 0)).map((a) => a.station);
    const dues = g.list.map((a) => a.due_week).filter(num);
    return { ...g, n: g.list.length, stations: [...new Set(st)], aog: aogs.length ? Math.max(...aogs) : null, due: dues.length ? Math.min(...dues) : null };
  });
}

/** The one number that decides each exception type, as {k: label, v: value, long: sentence}. */
function signalOf(a) {
  const e = a.evidence || {};
  switch (a.type) {
    case 'OUTSTATION_DEPLETION':
      if (num(e.on_hand) && num(e.target)) return { k: 'On hand / target', v: `${fmtInt(e.on_hand)} of ${fmtInt(e.target)} on hand`, long: `${fmtInt(e.on_hand)} of ${fmtInt(e.target)} on hand` };
      break;
    case 'LEAD_TIME_DRIFT':
      if (num(e.mean_lead_d) && num(e.mean_quoted_d)) return { k: 'Lead time vs quote', v: `${fmtInt(e.mean_lead_d)} d vs ${fmtInt(e.mean_quoted_d)} d quote`, long: `lead time ${fmtInt(e.mean_lead_d)} d against ${fmtInt(e.mean_quoted_d)} d quoted` };
      break;
    case 'OVERDUE_REPAIR':
      if (num(e.weeks_overdue)) return { k: 'Past quoted due', v: `${e.weeks_overdue.toFixed(1)} wk overdue`, long: `repair ${e.weeks_overdue.toFixed(1)} weeks past quoted due` };
      break;
    case 'EXCESS_DECLINING_DEMAND':
    case 'EXPIRY_RISK':
      if (num(e.cover_weeks_at_recent_rate)) return { k: 'Cover', v: `${fmtInt(e.cover_weeks_at_recent_rate)} wk of cover`, long: `${fmtInt(e.cover_weeks_at_recent_rate)} weeks of cover` };
      break;
    case 'CONDEMNED_AWAITING_REPLACEMENT':
      if (num(e.quoted_due_week)) return { k: 'Replacement due', v: `replacement ${fmtWeek(e.quoted_due_week)}`, long: `replacement due ${fmtWeek(e.quoted_due_week)}` };
      break;
    default:
  }
  return { k: 'Summary', v: truncate(a.summary || '', 300), long: a.summary || '' };
}

// ------------------------------------------------------------------ KPI instrument
function kpiInstrument(k, baseLabel, ranked, recLabel, actions) {
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
  if (footSpans[1]) footSpans[1].textContent = num(k.baseline) ? `${baseLabel} ${fmt(k.baseline)}` : num(k.as_of_week) ? `As of ${fmtWeek(k.as_of_week)}` : 'Source: actions.json';
  if (!Array.isArray(k.spark)) {
    const sp = tile.querySelector('.kpi-spark');
    // no time series exported: show a baseline → recommended dumbbell with both 95% CIs instead
    if (sp && num(k.baseline) && num(k.value)) sp.replaceWith(dumbbell(k, fmt, baseLabel, recLabel));
    else if (sp && !hasDelta) {
      // count tile: a severity ruler in the dumbbell's slot, so the four tile footers line up
      const sev = k.by_severity || actions?.counts?.by_severity || {};
      const ruler = severityRuler(sev);
      if (ruler) sp.replaceWith(ruler); else sp.remove();
    } else sp?.remove();
  }
  if (footSpans[0] && !Array.isArray(k.ci)) footSpans[0].textContent = k.provenance === 'DERIVED' ? 'Count, no interval' : 'No interval';
  // provenance chip moves from the label row to the delta row so labels get the full width
  const chip = tile.querySelector('.kpi-top .chip-prov');
  const delta = tile.querySelector('.kpi-delta');
  if (chip && delta) { const row = h('div', { class: 'mc-kpi-row' }); delta.replaceWith(row); row.append(delta, chip); }
  tile.dataset.kpi = k.id;
  return tile;
}

/** Stacked severity ruler (urgent / review / info) for the open-actions count tile. */
function severityRuler(sev) {
  const order = [['urgent', 'urgent'], ['review', 'review'], ['info', 'info']].filter(([key]) => num(sev[key]) && sev[key] > 0);
  const total = order.reduce((s, [key]) => s + sev[key], 0);
  if (!total) return null;
  return h('div', { class: 'mc-db mc-sev', role: 'img', 'aria-label': order.map(([key, l]) => `${fmtInt(sev[key])} ${l}`).join(', ') },
    h('div', { class: 'mc-sev-track' }, order.map(([key]) => h('span', { class: `mc-sev-seg is-${key}`, style: { flexGrow: String(sev[key]) } }))),
    h('div', { class: 'mc-db-labels', 'aria-hidden': 'true' }, order.map(([key, l]) => h('span', { class: `is-${key}` }, `${l} ${fmtInt(sev[key])}`))));
}

/** Baseline → recommended dumbbell on a shared track, with each value's 95% CI as a faint band. */
function dumbbell(k, fmt, baseLabel, recLabel) {
  const bci = Array.isArray(k.baseline_ci) ? k.baseline_ci : [k.baseline, k.baseline];
  const rci = Array.isArray(k.ci) ? k.ci : [k.value, k.value];
  const all = [...bci, ...rci, k.baseline, k.value].filter(num);
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1; lo -= pad; hi += pad;
  // every tile reads baseline → recommended from left to right; for lower-is-better KPIs the axis runs high → low
  const flip = k.value < k.baseline;
  const frac = (v) => (flip ? (hi - v) / (hi - lo) : (v - lo) / (hi - lo));
  const pct = (v) => `${frac(v) * 100}%`;
  const span = (a, b, cls) => { const l = Math.min(frac(a), frac(b)), r = Math.max(frac(a), frac(b)); return h('span', { class: cls, style: { left: `${l * 100}%`, width: `${(r - l) * 100}%` } }); };
  const recLeft = false;
  return h('div', { class: 'mc-db', role: 'img', title: flip ? 'Axis runs high → low so the baseline sits on the left on every tile' : undefined, 'aria-label': `${baseLabel} ${fmt(k.baseline)} to ${recLabel} ${fmt(k.value)}${k.reference && num(k.reference.value) ? `; ${k.reference.id || 'reference'} ${fmt(k.reference.value)}` : ''}` },
    h('div', { class: 'mc-db-track' },
      span(bci[0], bci[1], 'mc-db-ci mc-db-ci--base'), span(rci[0], rci[1], 'mc-db-ci mc-db-ci--rec'), span(k.baseline, k.value, 'mc-db-seg'),
      h('span', { class: 'mc-db-dot mc-db-dot--base', style: { left: pct(k.baseline) } }), h('span', { class: 'mc-db-dot mc-db-dot--rec', style: { left: pct(k.value) } })),
    h('div', { class: 'mc-db-labels', 'aria-hidden': 'true' },
      h('span', { class: recLeft ? 'is-rec' : 'is-base' }, recLeft ? recLabel : baseLabel),
      k.reference && num(k.reference.value) ? h('span', { class: 'is-ref' }, `${k.reference.id || 'ref'} ${fmt(k.reference.value)}`) : null,
      h('span', { class: recLeft ? 'is-base' : 'is-rec' }, recLeft ? baseLabel : recLabel)));
}

// ------------------------------------------------------------------ P0 / P1 / P2 / recommended strip
/** 'Legacy rules (baseline)' → 'Legacy', 'Network (multi-echelon)' → 'Network' (phones: no truncated policy names). */
const shortPol = (l) => String(l || '').split(/[\s(]/)[0] || String(l || '');
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
    rows.push({ key: 'REC', name: `Recommended · ${recId}`, label: String(recPol.label || 'frontier point').replace(/^Recommended:\s*/, '').replace(new RegExp(`\\s*\\(${recId}\\)$`), ''), value: a.mean, lo: a.ci_lo, hi: a.ci_hi, capital: recPol.kpi?.spare_capital_aed?.mean, role: 'rec' });
  } else if (recP && num(recP.aog_hours)) {
    const ci = Array.isArray(recP.aog_ci) ? recP.aog_ci : [recP.aog_hours, recP.aog_hours];
    rows.push({ key: 'REC', name: `Recommended · ${recId}`, label: recP.label || 'balanced frontier point', value: recP.aog_hours, lo: ci[0], hi: ci[1], capital: recP.capital_aed, role: 'rec' });
  }
  const base = rows.find((r) => r.role === 'base');
  const rec = rows.find((r) => r.role === 'rec');
  let headline = 'Policy comparison not run';
  let ciNote = '';
  if (base && rec) {
    const pct = Math.round((1 - rec.value / base.value) * 100);
    const dCap = num(rec.capital) && num(base.capital) ? rec.capital - base.capital : null;
    const overlap = rec.hi >= base.lo && rec.lo <= base.hi;
    const capTxt = dCap == null ? '' : dCap >= 0 ? ` for ${fmtAED(dCap)} more capital` : ` and frees ${fmtAED(-dCap)}`;
    const verb = pct >= 0 ? 'cuts' : 'raises';
    const cands = [
      `The recommended plan ${verb} material AOG ${Math.abs(pct)}% vs ${baseLabel}${capTxt}${overlap ? '; the intervals overlap' : ''}`,
      `The recommended plan ${verb} material AOG ${Math.abs(pct)}% vs ${baseLabel}${capTxt}`,
      `The recommended plan ${verb} material AOG ${Math.abs(pct)}% vs ${baseLabel}`,
    ];
    headline = cands.find((c) => c.length <= HEADLINE_MAX) || cands[cands.length - 1];
    ciNote = overlap ? '95% intervals overlap' : '95% intervals do not overlap';
  } else if (rows.length) {
    const best = rows.reduce((a, b) => (a.value < b.value ? a : b));
    headline = `${best.name} has the lowest modelled material AOG (${fmtHours(best.value)} a year)`;
  }
  const fSplit = frontier?.split || frontier?.meta?.split;
  const vals = rows.flatMap((r) => [r.lo, r.hi]).filter((v) => num(v) && v > 0);
  const log = vals.length && Math.max(...vals) / Math.min(...vals) > 8;
  const f = chartFrame(host, {
    headline,
    subtitle: `Material AOG h/yr · mean and 95% CI${ciNote ? ` (${ciNote.replace('95% intervals ', '')})` : ''} · ${seedText}${fSplit && !seedText.includes(fSplit) ? ` (recommended point: ${fSplit} seeds)` : ''}${log ? ' · log scale' : ''} · right: spare capital`,
    provenance: policies.meta?.provenance || 'SIMULATED', source: 'policies.json + frontier.json',
    table: { columns: [{ key: 'name', label: 'Policy' }, { key: 'label', label: 'Description' }, { key: 'value', label: 'AOG h/yr', num: true, format: fmtHours }, { key: 'lo', label: 'CI low', num: true, format: fmtHours }, { key: 'hi', label: 'CI high', num: true, format: fmtHours }, { key: 'capital', label: 'Spare capital', num: true, format: fmtAED }], rows },
  });
  if (!rows.length) { f.body.append(h('p', { class: 'faint t-14' }, 'Not run.')); return null; }

  return responsive(f.body, (w) => {
    const narrow = w < 560;
    const rowH = narrow ? 58 : 50;
    const m = narrow ? { top: 8, right: 8, bottom: 28, left: 8 } : { top: 8, right: 112, bottom: 28, left: Math.min(240, Math.max(196, w * 0.34)) };
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

    const color = (r) => (r.role === 'rec' ? theme.series.recommended : r.role === 'base' ? theme.series.baseline : theme.series.neutral);
    rows.forEach((r, i) => {
      const y0 = i * rowH;
      const cy = narrow ? y0 + 38 : y0 + rowH / 2;
      const row = g.append('g').attr('class', 'mc-cmp-row').datum(r);
      row.append('rect').attr('x', narrow ? 0 : -m.left).attr('y', y0 + 2).attr('width', narrow ? iw : w).attr('height', rowH - 4).attr('rx', 6).attr('fill', r.role === 'rec' ? 'rgba(34,199,184,0.06)' : 'transparent');
      // labels
      if (narrow) {
        row.append('text').attr('class', r.role === 'rec' ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 8).attr('y', y0 + 16).attr('dy', '0.32em').text(truncate(r.role === 'rec' ? r.name : `${r.name} · ${shortPol(r.label)}`, iw * 0.58));
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
