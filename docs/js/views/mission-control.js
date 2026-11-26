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
    const parts2 = [`Across ${seedText}, the core plan (P2) `];
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
        h('div', { class: 'mc-fault-sys', title: `System level = the chapter's share of fleet material shortage exposure${num(sysOf[hotAta]?.risk_share) ? ` (${fmtPct(sysOf[hotAta].risk_share, 0)})` : ''}, as on Parts Intelligence` }, `ATA ${hotAta}${hotSys ? ` · system ${hotSysWord}` : ''}`),
        h('div', { class: 'mc-fault-pn' }, hot.pn),
        h('div', { class: 'mc-fault-at' }, h('span', { title: hot.summary }, hot.type === 'DONOR_NOT_REINSTATED' && hot.destination ? `${hot.station} · donor ${hot.destination}` : hot.station), num(hotPart?.risk_score) ? h('span', { class: 'mc-fault-risk', title: 'Part-level material shortage exposure, 0–100 (log-scaled AOG hours)' }, `risk ${Math.round(hotPart.risk_score * 100)}`) : null),
        h('div', { class: 'mc-fault-d' }, [hotPart?.desc, hot.evidence?.deadline ? `deadline class ${hot.evidence.deadline} (hypothetical)` : null].filter(Boolean).join(' · ') || hot.summary)))
    : null;
  // accessible list alternative for the drawing's hotspots
  const ataList = h('ul', { class: 'sr-only', 'aria-label': 'Aircraft systems (open Parts Intelligence)' },
    HOTSPOTS.map((a) => h('li', {}, h('a', { href: ctx.buildHash('parts', { ata: a, pn: a === hotAta ? hot.pn : undefined }) }, `ATA ${a} ${ataName[a] || ''}${a === hotAta ? ` — urgent missing part ${hot.pn} at ${hot.station}` : ''}`))));

  // Wave A hero: compact (~260 px at 1440), exact copy, the narrowbody plan view with the most urgent part marked
  const hero = card({
    cls: 'mc-hero-card', bp: true, story: 'mission-hero', flush: true,
    body: h('div', { class: 'mc-hero' },
      h('div', { class: 'mc-copy' },
        h('h1', { class: 'mc-title' }, 'GROUNDED NO MORE'),
        h('p', { class: 'mc-tagline' }, 'The right spare. The right station. Before the aircraft needs it.'),
        h('p', { class: 'mc-oneline' }, 'An aviation materials-planning simulation connecting intermittent-demand forecasting, rotable repair planning and inventory optimisation to aircraft readiness.'),
        h('p', { class: 'mc-scope' }, `40 aircraft · 2 fleet families · 7 stations · ${fmtInt((parts.parts || []).length)} AOG-critical part numbers · Independent simulation`),
        h('div', { class: 'mc-cta' },
          h('button', { class: 'btn btn--primary', type: 'button', onclick: startTour, dataset: { story: 'mission-start' } }, icon('play'), '60-second tour'),
          h('a', { class: 'btn btn--ghost', href: '#/method' }, 'Methodology', icon('chevron-right'))),
        h('p', { class: 'mc-byline' }, 'Portfolio project by Akash Gajjar, MSc Supply Chain Management, University of Liverpool')),
      h('div', { class: 'mc-figwrap' }, fig, fault, ataList)),
  });
  el.append(hero);

  inlineSVG('aircraft-narrowbody.svg').then((svg) => {
    if (!fig.isConnected && !el.contains(fig)) return;
    svg.setAttribute('viewBox', svg.dataset.compactViewbox || svg.getAttribute('viewBox'));
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.classList.add('bp-compact');
    svg.setAttribute('aria-label', 'Plan view of a single-aisle twin-engine airliner archetype (original schematic) with indicative ATA system zones');
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
    // wave A wording: "material requirement covered", "expected material-related downtime hours"
    fr && { ...fr, label: 'Material requirement covered immediately' },
    ao && { ...ao, label: 'Expected material-related downtime h / yr' },
    sc,
    openK,
  ].filter(Boolean).map((k) => kpiInstrument(k, baseLabel, ranked, k.core_id || kpis.core_id || 'P2', actions));   // v2: tiles read P0 → P2
  // AV2-03: the capital tile says what the +capital is: a re-mix of the rotable float (bought and shed units)
  const RM = kpis.headline?.core?.remix;
  const capTile = sc ? tiles[[fr, ao, sc].filter(Boolean).indexOf(sc)] : null;
  if (RM && capTile) capTile.querySelector('.kpi-delta')?.after(h('div', { class: 'mc-remix t-12 muted', dataset: { role: 'remix' } },
    `Buys ${fmtInt(RM.buy_units)} rotables (≈${fmtAED(RM.buy_aed)}), sheds ${fmtInt(RM.shed_units)} (≈${fmtAED(RM.shed_aed)})`));
  REMIX = RM || null;
  el.append(h('div', { class: 'mc-kpis', dataset: { story: 'mission-kpis' }, role: 'group', 'aria-label': 'Headline indicators' }, tiles));

  // ================================================================ comparison + actions | map
  const left = h('div', { class: 'mc-col' });
  const right = h('div', { class: 'mc-col' });
  el.append(h('div', { class: 'mc-grid' }, left, right));

  // ---- P0 / P1 / P2 / recommended strip
  const cmpCard = h('section', { class: 'card', dataset: { story: 'mission-compare' } });

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
        h('span', { class: 'mc-pr-type', title: `${a.type_label || a.type}: a planning exception, not a material shortage exposure` }, a.type_label || a.type)),
      h('span', { class: 'mc-pr-sig', title: sig.k }, h('span', { class: 'mc-pr-v' }, sig.v), h('span', { class: 'mc-pr-step' }, TYPE_STEP[a.type] || 'Review')),
      h('span', { class: 'mc-pr-aog num', title: aogLabel }, h('span', { class: 'mc-pr-ml' }, 'Worst stn '), g.aog ? [fmtHours(g.aog), g.aogSt ? h('span', { class: 'mc-pr-st', title: g.stations.includes(g.aogSt) ? null : `No open exception at ${g.aogSt}; its 52-week AOG hours are still the worst for this PN` }, ` · ${g.aogSt}`, g.stations.includes(g.aogSt) ? null : h('span', { class: 'mc-pr-noex' }, 'no exception there')) : null] : '—'),
      h('span', { class: 'mc-pr-due num' }, h('span', { class: 'mc-pr-ml' }, 'Due '), num(g.due) ? fmtWeek(g.due) : '—'),
      h('span', { class: 'mc-pr-do', 'aria-hidden': 'true' }, icon('chevron-right')));
  });
  left.append(card({
    story: 'mission-actions', kicker: 'Today’s planning priorities', prov: actions.meta?.provenance || 'DERIVED',
    title: all.length ? `${fmtInt(nUrg)} urgent actions on ${fmtInt(nUrgPn)} part numbers; top ${fmtInt(groups.length)} shown` : 'No open actions exported',
    body: h('div', { class: 'mc-prio', role: 'list' }, head, rowsEl.map((r) => { r.setAttribute('role', 'listitem'); return r; })),
    foot: [h('span', { title: aogMeta?.definition || aogLabel }, `Ranked by severity then risk · ${aogLabel}, as in the Action Centre`), h('a', { class: 'card-link', href: '#/actions' }, 'Open Planner Action Centre', icon('chevron-right'))],
  }));

  // the policy comparison follows the priorities (wave A: simple bars here; the CI chart lives in Capital Optimiser)
  left.append(cmpCard);
  cleanups.push(compareStrip(cmpCard, { policies, frontier, seedText, baseLabel }));
  const hl = findingsCard(kpis.headline);
  if (hl) left.append(hl);

  // ---- network mini-map
  const mapCard = h('section', { class: 'card', dataset: { story: 'mission-map' } });
  right.append(mapCard);
  const stations = (network.stations || []).slice();
  const byRisk = stations.filter((s) => num(s.risk)).sort((a, b) => b.risk - a.risk);
  const topS = byRisk[0];
  const hub = stations.find((s) => s.role === 'hub');
  const nOut = stations.filter((s) => s.role !== 'hub').length;
  const topOut = byRisk.find((s) => s.role !== 'hub');
  // wave C: one denominator site-wide: each station's share of the network's total material shortage exposure
  const riskSum = byRisk.reduce((a, s) => a + s.risk, 0) || 1;
  const shareOf = (s) => s.risk / riskSum;
  const outShare = byRisk.filter((s) => s.role !== 'hub').reduce((a, s) => a + shareOf(s), 0);
  const mf = chartFrame(mapCard, {
      implication: `Outstations carry ${fmtPct(outShare, 0)} of the exposure between them: position no-go stock there, fed from the hub.`,
    headline: topOut
      ? `${topOut.station} has the most outstation shortage exposure: ${fmtPct(shareOf(topOut), 0)} of the network total`
      : topS ? `${topS.station} carries the most grounding exposure` : 'Station risk not run',
    subtitle: `Material shortage exposure = P0 holdout material AOG h · bars = each station's share of the network total · ${hub ? `${hub.station} hub + ${nOut} outstations · ` : ''}line width = history transfers`,
    provenance: network.meta?.provenance || 'SIMULATED', source: 'network.json',
    table: { columns: [{ key: 'station', label: 'Station', mono: true }, { key: 'role', label: 'Role' }, { key: 'risk', label: 'Share of network exposure', num: true, format: (v) => fmtPct(v / riskSum, 0) }, { key: 'serviceable_units', label: 'Serviceable units', num: true, format: fmtInt }, { key: 'stock_value', label: 'Stock value', num: true, format: fmtAED }], rows: byRisk },
  });
  const mapHost = h('div', { class: 'mc-map' });
  const listHost = h('div', { class: 'mc-stations' });
  mf.body.append(mapHost, listHost);
  let map = null;
  renderNetworkMap(mapHost, {
    stations, arcs: network.arcs || [], selected: topS?.station, inset: false, aspect: 0.62, label: 'Network map: hub and outstations',
    onSelect: (id) => ctx.navigate(ctx.buildHash('network', { station: id })),
  }).then((m) => { map = m; }).catch((e) => { console.warn('map unavailable', e); mapHost.replaceChildren(h('p', { class: 'faint t-12' }, 'Map unavailable.')); });
  listHost.append(h('ul', { class: 'mc-st list-reset', 'aria-label': 'Station material shortage exposure, share of the network total' }, byRisk.map((s) => h('li', { class: `mc-st-row${s === topOut ? ' is-focus' : ''}${s.role === 'hub' ? ' is-hub' : ''}` },
    h('a', { href: ctx.buildHash('network', { station: s.station }), class: 'mc-st-l' }, h('span', { class: 'mono' }, s.station), h('span', { class: 'faint' }, s.role === 'hub' ? ' · hub' : ' · outstation')),
    h('span', { class: 'mc-st-bar', 'aria-hidden': 'true' }, h('span', { style: { width: `${Math.max(1, (s.risk / byRisk[0].risk) * 100)}%` } })),
    h('span', { class: 'mc-st-v mono' }, fmtPct(shareOf(s), 0))))));

  const sysRows = (parts.ata_systems || []).filter((a) => num(a.risk_share)).sort((a, b) => b.risk_share - a.risk_share);
  if (sysRows.length) {
    const nShow = Math.min(innerWidth >= 1100 ? 9 : 4, sysRows.length); // wave C: desktop fills the column (no half-card void)
    const lvWord = (l) => (l === 'ok' ? 'OK' : cap(l));
    const nUrgSys = sysRows.filter((a) => (a.system_level || a.risk_level) === 'urgent').length;
    const nWatch = sysRows.filter((a) => (a.system_level || a.risk_level) !== 'urgent' && (a.has_urgent_part ?? a.n_urgent > 0)).length;
    right.append(card({
      story: 'mission-systems', kicker: 'Aircraft systems', prov: 'DERIVED',
      title: (() => { const shownWatch = sysRows.slice(0, nShow).filter((a) => (a.system_level || a.risk_level) !== 'urgent' && (a.has_urgent_part ?? a.n_urgent > 0)).length; return `${fmtInt(nUrgSys)} system${nUrgSys === 1 ? '' : 's'} rate urgent; ${fmtInt(nWatch)} more ${nWatch === 1 ? 'holds' : 'hold'} an urgent part${nWatch ? ` (${fmtInt(shownWatch)} shown)` : ''}`; })(),
      body: h('ul', { class: 'mc-sys list-reset' }, sysRows.slice(0, nShow).map((a) => {
        const lv = a.system_level || a.risk_level || 'unknown';
        const nU = a.n_urgent ?? 0;
        // exporter status: system level, raised to WATCH when an OK chapter holds an urgent part (same pill as Parts)
        const tone = a.status || lv;
        const word = String(a.status_label || '').split(' · ')[0] || lvWord(lv);
        return h('li', {}, h('a', { class: `mc-sys-row is-${lv}`, href: ctx.buildHash('parts', { ata: a.ata }), 'aria-label': `ATA ${a.ata} ${a.name}: ${word}, system level ${lvWord(lv)}, ${fmtPct(a.risk_share, 0)} of fleet risk-hours, ${nU} urgent part numbers` },
          h('span', { class: 'mc-sys-ata mono' }, a.ata),
          h('span', { class: 'mc-sys-name' }, a.name, h('span', { class: 'faint mono' }, ` · ${fmtPct(a.risk_share, 0)}`)),
          h('span', { class: 'mc-sys-st', title: `System level ${lvWord(lv)} (share of fleet material shortage exposure)${nU ? `; ${nU} urgent part number${nU === 1 ? '' : 's'}` : ''}` }, pill(['urgent', 'review', 'ok'].includes(tone) ? tone : 'unknown', word), nU ? h('span', { class: 'mc-sys-urg mono' }, `▲ ${fmtInt(nU)} urgent PN${nU === 1 ? '' : 's'}`) : null)));
      })),
      foot: [h('span', {}, `Top ${fmtInt(nShow)} of ${fmtInt(sysRows.length)} by share of fleet material shortage exposure · system level and urgent parts are rated separately`), h('a', { class: 'card-link', href: '#/parts' }, 'Parts Intelligence', icon('chevron-right'))],
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
  DONOR_NOT_REINSTATED: 'Reinstate the donor', OPEN_LOAN: 'Return the loan unit', OPEN_REQUIREMENT: 'Keep recovery routes open',
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
    case 'DONOR_NOT_REINSTATED':
      if (num(e.days_waiting)) return { k: 'Donor waiting', v: `donor ${e.donor_tail || ''} · ${fmtInt(e.days_waiting)} d`, long: `robbed donor ${e.donor_tail || ''} waiting ${fmtInt(e.days_waiting)} days` };
      break;
    case 'OPEN_REQUIREMENT':
      return { k: 'Open need', v: `open since ${fmtWeek(e.need_week)}${e.deadline_class ? ` · ${e.deadline_class}` : ''}`, long: `requirement open since ${fmtWeek(e.need_week)}` };
    default:
  }
  return { k: 'Summary', v: truncate(a.summary || '', 300), long: a.summary || '' };
}

// ------------------------------------------------------------------ v2 findings (computed in the exporter: kpis.headline)
const pm = (v) => `${v < 0 ? '−' : '+'}${fmtInt(Math.abs(v))}`;
const rng = (ci, f = fmtInt) => `[${f(ci[0])}–${f(ci[1])}]`;
/** What holds (P2 core finding), the frontier option (I125) and the honest caveats, every number from kpis.headline. */
function findingsCard(H) {
  if (!H?.core) return null;
  const c = H.core, fo = H.frontier_option, ho = H.honest || {};
  const W = { low_stress: 'low stress', central: 'central', high_stress: 'high stress' };
  const items = [
    ['holds', `Holds in all three worlds: P2 vs P0 ${c.worlds.map((w) => `${pm(w.aog_hours.mean)} h (${W[w.variant] || w.variant})`).join(' · ')}.`, c.holds_all_worlds],
    ['holds', `Holds from ×0.5 to ×2 the hourly downtime rate: total cost ${fmtAED(c.penalty_range['x0.5']?.mean)} to ${fmtAED(c.penalty_range.x2?.mean)} a year vs P0.`, c.holds_penalty_range],
    fo ? ['option', `If you invest an additional ${fmtAED(fo.extra_capital_aed.mean)}: ${fo.id} removes a further ${fmtInt(fo.aog_reduction.mean)} h/yr ${rng(fo.aog_reduction.ci)} below P2 (paired holdout).${fo.repair_tat_x0_75 && !fo.repair_tat_x0_75.net_benefit_significant ? ' Its cost lead over P2 is not significant if repair is 25% faster.' : ''}${fo.rule_shifts?.length ? ` The rule picks ${fo.rule_shifts.map((x) => `${x.recommended} at ${String(x.setting).replace('x', '×')}`).join(' / ')} the hourly rate.` : ''}`, true] : null,
    fo?.postplan_stress?.length ? ['option', `Post-plan stress check (added after the holdout): ${fo.id} vs P2 ${fo.postplan_stress.map((w) => `${pm(w.aog_hours.mean)} h (${W[w.variant] || w.variant})`).join(' · ')}.`, true] : null,
    ho.forecast_cells ? ['caveat', `Forecasting: the frozen champions stayed best in ${fmtInt(ho.forecast_champions_best)} of ${fmtInt(ho.forecast_cells)} cells${ho.sba_intermittent_rotables_rank ? ` (SBA ranked ${ho.sba_intermittent_rotables_rank} of ${ho.sba_intermittent_rotables_n_methods} for intermittent rotables)` : ''}.`, false] : null,
    num(ho.mtbur_history_error) ? ['caveat', `History-based MTBUR lands about ${fmtPct(ho.mtbur_history_error, 0)} from the truth, vendor quotes about ${fmtPct(ho.mtbur_quote_error, 0)}.`, false] : null,
    num(ho.fill_pts_P2_vs_P0) ? ['caveat', `P1 and P2 run about ${Math.abs(ho.fill_pts_P2_vs_P0).toFixed(1)} pts lower immediate fill than P0 (leaner count-part stock).`, false] : null,
    ho.routes_off ? ['caveat', `Every policy leans on AOG recovery routes: with them switched off, P2 rises from ${fmtHours(ho.routes_off.central_p2_aog_hours)} to ${fmtHours(ho.routes_off.p2_aog_hours)} a year (selection seeds).`, false] : null,
  ].filter(Boolean);
  const icon2 = { holds: 'check', option: 'capital', caveat: 'info' };
  return card({
    kicker: 'What holds, and what to watch', prov: H.provenance || 'SIMULATED', story: 'mission-findings',
    title: `Network positioning is the core result; ${fo ? fo.id : 'more capital'} is an option, and the caveats stay visible`,
    body: h('ul', { class: 'mc-findings list-reset' }, items.map(([k, t]) => h('li', { class: `is-${k}` }, icon(icon2[k]), h('span', {}, t)))),
  });
}

// ------------------------------------------------------------------ KPI instrument
function kpiInstrument(k, baseLabel, ranked, recLabel, actions) {
  const fmt = !k.unit ? fmtInt : fmtByUnit(k.unit);
  const dfmt = k.unit === '%' ? fmtPts : fmt;
  const hasDelta = num(k.delta);
  // wave C: the fill change is a trade-off (lean C/E stock), told in the neutral tone like capital, not red
  const tile = kpiTile({ ...k, delta: hasDelta ? k.delta : 0, ci: Array.isArray(k.ci) ? k.ci : null }, { format: fmt, deltaFormat: dfmt, sparkline, deltaTone: /fill/.test(k.id || '') ? 'neutral' : 'auto' });
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
let REMIX = null;
function compareStrip(host, { policies, frontier, seedText, baseLabel }) {
  const P = policies.policies || [];
  const get = (id) => P.find((p) => p.policy_id === id);
  const rows = [];
  ['P0', 'P1', 'P2'].forEach((id) => {
    const p = get(id);
    const a = p?.kpi?.aog_hours;
    if (a && num(a.mean)) rows.push({ key: id, name: id, label: p.label || id, value: a.mean, lo: a.ci_lo ?? a.mean, hi: a.ci_hi ?? a.mean, capital: p.kpi?.spare_capital_aed?.mean, role: id === 'P0' ? 'base' : id === 'P2' ? 'core' : 'ctx' });   // v2: P2 is the core finding
  });
  const recId = frontier?.recommended;
  const recP = (frontier?.points || []).find((p) => p.id === recId);
  const recPol = recId ? get(recId) : null;
  if (recPol?.kpi?.aog_hours && !rows.some((r) => r.key === recId)) {
    const a = recPol.kpi.aog_hours;
    rows.push({ key: 'REC', name: `${recId} · frontier option`, label: 'more capital', value: a.mean, lo: a.ci_lo, hi: a.ci_hi, capital: recPol.kpi?.spare_capital_aed?.mean, role: 'opt' });
  } else if (recP && num(recP.aog_hours)) {
    const ci = Array.isArray(recP.aog_ci) ? recP.aog_ci : [recP.aog_hours, recP.aog_hours];
    rows.push({ key: 'REC', name: `${recId} · frontier option`, label: 'more capital', value: recP.aog_hours, lo: ci[0], hi: ci[1], capital: recP.capital_aed, role: 'opt' });
  }
  const base = rows.find((r) => r.role === 'base');
  const rec = rows.find((r) => r.role === 'core');
  let headline = 'Policy comparison not run';
  let ciNote = '';
  if (base && rec) {
    const pct = Math.round((1 - rec.value / base.value) * 100);
    const dCap = num(rec.capital) && num(base.capital) ? rec.capital - base.capital : null;
    const overlap = rec.hi >= base.lo && rec.lo <= base.hi;
    const capTxt = dCap == null ? '' : dCap >= 0 ? ` for ${fmtAED(dCap)} more capital` : ` and frees ${fmtAED(-dCap)}`;
    const verb = pct >= 0 ? 'cuts' : 'raises';
    const cands = [
      `Network positioning (P2) ${verb} material AOG ${Math.abs(pct)}% vs ${baseLabel}${capTxt}${overlap ? '; the intervals overlap' : ''}`,
      `Network positioning (P2) ${verb} material AOG ${Math.abs(pct)}% vs ${baseLabel}${capTxt}`,
      `Network positioning ${verb} material AOG ${Math.abs(pct)}% vs ${baseLabel}`,
    ];
    headline = cands.find((c) => c.length <= HEADLINE_MAX) || cands[cands.length - 1];
    ciNote = overlap ? '95% intervals overlap' : '95% intervals do not overlap';
  } else if (rows.length) {
    const best = rows.reduce((a, b) => (a.value < b.value ? a : b));
    headline = `${best.name} has the lowest modelled material AOG (${fmtHours(best.value)} a year)`;
  }
  const fSplit = frontier?.split || frontier?.meta?.split;
  // Wave A: simple horizontal bars of expected material AOG hours per policy, spare capital as a label. The detailed
  // mean-and-CI chart lives in Capital Optimiser only.
  const f = chartFrame(host, {
      implication: REMIX ? `P2 re-mixes the rotable float (buys ${fmtInt(REMIX.buy_units)} units, sheds ${fmtInt(REMIX.shed_units)}) at roughly flat capital; capital beyond P2 is a secondary option.` : 'P2 re-mixes the rotable float at roughly flat capital; capital beyond P2 is a secondary option.',
    headline: headline.replace(/; the intervals overlap$/, ''),
    subtitle: `Expected material-related downtime: material AOG h/yr, mean · ${seedText}${fSplit && !seedText.includes(fSplit) ? ` (frontier option: ${fSplit} seeds)` : ''} · label: spare capital · intervals in Capital Optimiser`,
    provenance: policies.meta?.provenance || 'SIMULATED', source: 'policies.json + frontier.json',
    table: { columns: [{ key: 'name', label: 'Policy' }, { key: 'label', label: 'Description' }, { key: 'value', label: 'AOG h/yr', num: true, format: fmtHours }, { key: 'lo', label: 'CI low', num: true, format: fmtHours }, { key: 'hi', label: 'CI high', num: true, format: fmtHours }, { key: 'capital', label: 'Spare capital', num: true, format: fmtAED }], rows },
  });
  if (!rows.length) { f.body.append(h('p', { class: 'faint t-14' }, 'Not run.')); return null; }
  f.body.after(h('a', { class: 'card-link mc-cmp-more', href: '#/capital' }, 'Intervals and the full frontier in Capital Optimiser', icon('chevron-right')));
  return responsive(f.body, (w) => {
    const narrow = w < 560;
    const rowH = narrow ? 52 : 44;
    const lw = narrow ? 0 : Math.min(230, Math.max(180, w * 0.32));
    const rw = narrow ? 0 : 150;
    const iw = Math.max(80, w - lw - rw);
    const H = rows.length * rowH + 8;
    const svg = svgIn(f.body, w, H, 'Expected material AOG hours by policy, with spare capital');
    const max = Math.max(...rows.map((r) => r.value));
    const x = d3().scaleLinear().domain([0, max * 1.04]).range([0, iw]);
    const color = (r) => (r.role === 'core' ? theme.series.recommended : r.role === 'base' ? theme.series.baseline : theme.series.neutral);
    rows.forEach((r, i) => {
      const y0 = i * rowH + 4;
      const row = svg.append('g').attr('class', 'mc-cmp-row').datum(r);
      const by = narrow ? y0 + 26 : y0 + rowH / 2 - 7;
      const name = r.role === 'opt' ? r.name : `${r.name} · ${shortPol(r.label)}`;
      row.append('text').attr('class', r.role === 'core' ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', narrow ? y0 + 12 : y0 + rowH / 2).attr('dy', '0.32em').text(narrow ? name : truncate(name, lw - 16));
      row.append('rect').attr('x', lw).attr('y', by).attr('height', 14).attr('rx', 3).attr('width', Math.max(2, x(r.value))).attr('fill', color(r));
      const val = `${fmtHours(r.value)}${num(r.capital) ? ` · ${fmtAED(r.capital)}` : ''}`;
      if (narrow) row.append('text').attr('class', 'gnm-label gnm-label--mono').attr('x', w).attr('y', y0 + 12).attr('dy', '0.32em').attr('text-anchor', 'end').text(val);
      else row.append('text').attr('class', 'gnm-label gnm-label--mono').attr('x', lw + x(r.value) + 8).attr('y', by + 7).attr('dy', '0.32em').text(val);
    });
    withTooltip(svg.selectAll('g.mc-cmp-row'), (d) => ({ title: `${d.name} · ${d.label}`, rows: [['Mean AOG h/yr', fmtHours(d.value)], ['Spare capital', fmtAED(d.capital)]] }));
  });
}
