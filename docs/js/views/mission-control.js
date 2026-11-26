/**
 * 01 · Mission Control — the landing page (v2.1).
 * Data: kpis.json, policies.json, parts.json, actions.json (+ story.json on demand for the tour).
 *
 * Hero (A1, verbatim from kpis.landing): title, sub, the stat strip, the landing footer line and the aircraft
 * illustration in the `#hero-art` mount slot (a cutaway can replace its contents later). No result numbers in the hero.
 * Results (#results, deep link #/mission?section=results): intro3, the four plans as simple bars of hours waiting for
 * parts (likely ranges in Expert mode), the scope line, the KPI tiles, the A2 reading note, the A4 capital table, the
 * A6 stress-world sentence, the post-plan donor recount, the honest findings, then today's planner priorities.
 * Every number comes from the JSON exports; nothing is typed in.
 * Story hooks: mission-hero, mission-start, mission-aircraft, mission-results, mission-compare, mission-kpis,
 * mission-capital, mission-donor, mission-findings, mission-actions.
 */
import { h, card, kpiTile, pill, icon, inlineSVG, storyMode, intro3, scopeLine, readingNote, postPlanBadge, capitalTable, sectionTitle } from '../ui.js';
import { chartFrame, truncate, fmtPct, fmtHours, fmtInt, fmtWeek } from '../charts/theme.js';
import { assetURL } from '../data.js';
import { getMode, byMode } from '../lib/mode.js';
import { displayName, nameTag, replaceCodes } from '../lib/names.js';
import { term, termText } from '../lib/glossary.js';

export const data = ['kpis', 'policies', 'parts', 'actions'];

const HOTSPOTS = ['21', '24', '27', '29', '32', '34', '36', '49'];
const SEV_RANK = { urgent: 0, review: 1, info: 2 };
const PLANS = ['P0', 'P1', 'P2', 'I125'];

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
const ord = (n) => { const s = ['th', 'st', 'nd', 'rd'], v = n % 100; return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`; };
const sgn = (v) => `${v < 0 ? '−' : ''}${fmt1(v)}`;
const fmt1 = (v) => (Math.round(Math.abs(v) * 10) / 10).toLocaleString('en-GB', { maximumFractionDigits: 1 });

/** Rank planner actions: severity, then risk score, then due week. */
function rankActions(list = []) {
  return list.slice().sort((a, b) =>
    (SEV_RANK[a.severity] ?? 3) - (SEV_RANK[b.severity] ?? 3) ||
    (b.evidence?.risk_score ?? 0) - (a.evidence?.risk_score ?? 0) ||
    (a.due_week ?? 0) - (b.due_week ?? 0));
}

/** Scroll the Results section into view (after the router has finished its own scroll reset). */
function scrollToResults(smooth = true) {
  const go = () => document.getElementById('results')?.scrollIntoView({ behavior: smooth && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'auto', block: 'start' });
  requestAnimationFrame(() => setTimeout(go, 30));
}

/** Same-route query change (#/mission ↔ #/mission?section=results): scroll instead of re-rendering. */
export function onParams(params) {
  if (params.section === 'results') scrollToResults();
  else window.scrollTo({ top: 0 });
  return true;
}

export async function render(el, ctx) {
  await ensureCSS();
  const { kpis, policies, parts, actions } = ctx.data;
  const cleanups = [];
  const L = kpis.landing || {};
  const ranked = rankActions(actions.actions || []);
  const partBy = Object.fromEntries((parts.parts || []).map((p) => [p.pn, p]));
  const ataName = Object.fromEntries((parts.ata_systems || []).map((a) => [a.ata, a.name]));

  // ================================================================ HERO (A1 verbatim, no result numbers)
  const startTour = async () => {
    try {
      const s = await ctx.load('story');
      storyMode({ steps: s.steps || [], navigate: ctx.navigate }).start();
    } catch (e) { console.warn('story unavailable', e); }
  };
  const toResults = (e) => { e.preventDefault(); ctx.setParams({ section: 'results' }); scrollToResults(); };
  const stats = (L.stats || []).filter((s) => num(s.value));
  const statStrip = h('p', { class: 'mc-stats', dataset: { role: 'landing-stats' }, 'aria-label': L.text || null },
    stats.flatMap((s, i) => [i ? h('span', { class: 'mc-stat-sep', 'aria-hidden': 'true' }, ' · ') : null,
      h('span', { class: 'mc-stat' }, h('b', { class: 'mc-stat-v' }, fmtInt(s.value)), ` ${s.label}`)]));

  // the most urgent missing part that sits on a drawn system zone (the drawing's one live marker)
  const hot = ranked.find((a) => a.severity === 'urgent' && HOTSPOTS.includes(ataOf(a.pn))) || ranked.find((a) => HOTSPOTS.includes(ataOf(a.pn)));
  const hotAta = hot ? ataOf(hot.pn) : null;
  const hotPart = hot ? partBy[hot.pn] : null;
  const sysOf = Object.fromEntries((parts.ata_systems || []).map((a) => [a.ata, a]));
  const hotSysWord = (() => { const w = String(sysOf[hotAta]?.status_label || '').split(' · ')[0]; const v = w || sysOf[hotAta]?.system_level || ''; return v.toUpperCase() === 'OK' ? 'OK' : v.toLowerCase(); })();

  const fig = h('div', { class: 'mc-fig', dataset: { story: 'mission-aircraft' }, role: 'group', 'aria-label': 'Aircraft systems with spare-part risk' });
  const fault = hot
    ? h('a', { class: 'mc-fault', href: ctx.buildHash('actions', { id: hot.exception_id }), 'aria-label': `Most urgent part: ${hot.pn} at ${hot.station || 'the network'}. Open the planner action` },
      icon('alert'),
      h('div', {},
        h('div', { class: 'mc-fault-k' }, byMode('Most urgent part today', `${cap(hot.severity)} part`)),
        h('div', { class: 'mc-fault-sys expert-only' }, `ATA ${hotAta}${hotSysWord ? ` · system ${hotSysWord}` : ''}`),
        h('div', { class: 'mc-fault-pn' }, hot.pn),
        h('div', { class: 'mc-fault-at' }, h('span', {}, hot.station || 'Network'),
          num(hotPart?.risk_score) ? h('span', { class: 'mc-fault-risk expert-only', title: 'Part-level shortage exposure, 0–100' }, `risk ${Math.round(hotPart.risk_score * 100)}`) : null),
        hotPart?.desc ? h('div', { class: 'mc-fault-d' }, hotPart.desc) : null))
    : null;
  const ataList = h('ul', { class: 'sr-only', 'aria-label': 'Aircraft systems (open Parts Intelligence)' },
    HOTSPOTS.map((a) => h('li', {}, h('a', { href: ctx.buildHash('parts', { ata: a, pn: a === hotAta ? hot.pn : undefined }) }, `${ataName[a] || `System ${a}`}${a === hotAta ? `: most urgent part ${hot.pn} at ${hot.station}` : ''}`))));

  const hero = card({
    cls: 'mc-hero-card', bp: true, story: 'mission-hero', flush: true,
    body: h('div', { class: 'mc-hero' },
      h('div', { class: 'mc-copy' },
        h('div', { class: 'mc-eyebrow' }, 'GROUNDED NO MORE'),
        h('h1', { class: 'mc-title', dataset: { role: 'landing-title' } }, L.title || ''),
        // A1 verbatim (mandated wording; its one long sentence is excluded from the readability score)
        h('p', { class: 'mc-sub', dataset: { role: 'landing-sub', readability: 'skip' } }, L.sub || ''),
        statStrip,
        h('div', { class: 'mc-cta' },
          h('button', { class: 'btn btn--primary', type: 'button', onclick: startTour, dataset: { story: 'mission-start' } }, icon('play'), '60-second tour'),
          h('a', { class: 'btn btn--ghost', href: ctx.buildHash('mission', { section: 'results' }), onclick: toResults, dataset: { role: 'to-results' } }, 'See the results', icon('chevron-right')),
          h('a', { class: 'btn btn--ghost', href: '#/method' }, 'How it works', icon('chevron-right'))),
        h('p', { class: 'mc-landing-foot', dataset: { role: 'landing-footer' } }, L.footer || '')),
      // mount slot: the aircraft illustration today; a cutaway may replace the contents of #hero-art later
      h('div', { class: 'mc-figwrap', id: 'hero-art', dataset: { slot: 'hero-art' } }, fig, fault, ataList)),
  });
  el.append(hero);

  inlineSVG('aircraft-narrowbody.svg').then((svg) => {
    if (!fig.isConnected && !el.contains(fig)) return;
    svg.setAttribute('viewBox', svg.dataset.compactViewbox || svg.getAttribute('viewBox'));
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.classList.add('bp-compact');
    svg.setAttribute('aria-label', 'Plan view of a generic narrowbody airliner (original schematic) with indicative aircraft system zones');
    svg.querySelectorAll('.ata-hotspot').forEach((g) => {
      const a = g.dataset.ata;
      const missing = a === hotAta;
      g.classList.toggle('is-missing', missing);
      g.setAttribute('aria-label', `${ataName[a] || g.dataset.name || `System ${a}`}${missing ? `: most urgent part ${hot.pn} at ${hot.station}` : ''}. Open Parts Intelligence`);
      const go = () => ctx.navigate(ctx.buildHash('parts', { ata: a, pn: missing ? hot.pn : undefined }));
      g.addEventListener('click', go);
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
    fig.classList.add('bp-figure');
    fig.replaceChildren(svg);
    // keep badge numerals >= 11 screen px however small the drawing is scaled
    const sizeBadges = () => {
      const vb = svg.viewBox.baseVal, r = svg.getBoundingClientRect();
      if (!vb?.width || !r.width) return;
      const u = Math.max(vb.width / r.width, vb.height / r.height);
      svg.querySelectorAll('.hs-badge').forEach((b) => {
        const c = b.querySelector('circle'); const t = b.querySelector('text');
        if (c) { c.dataset.r0 = c.dataset.r0 || c.getAttribute('r'); c.setAttribute('r', Math.max(+c.dataset.r0, 10 * u)); }
        if (t) t.style.fontSize = `${Math.max(17, 11.5 * u)}px`;
      });
    };
    sizeBadges();
    const ro = new ResizeObserver(() => requestAnimationFrame(sizeBadges)); ro.observe(fig); cleanups.push(() => ro.disconnect());
  }).catch(() => fig.replaceChildren(h('p', { class: 'faint t-12' }, 'Aircraft drawing unavailable.')));

  // ================================================================ RESULTS
  const res = h('section', { class: 'mc-results', id: 'results', dataset: { role: 'results', story: 'mission-results' }, 'aria-labelledby': 'results-h', tabindex: '-1' });
  el.append(res);
  const head = sectionTitle('Results');
  head.querySelector('h2').id = 'results-h';
  res.append(head);
  const core = kpis.headline?.core || {};
  res.append(intro3({
    what: ['How four ', term('policy', { label: 'stocking plans' }), ' compare on ', term('aog_hours'), ', and what each one costs.'],
    why: ['A missing part can ground an aircraft. These numbers show which plan keeps aircraft flying, and where the result is weak.'],
    action: ['Start from the Network Plan. Check its money lines, then the honest findings, before trusting the gap.'],
  }));

  // ---- the four plans (simple bars; likely ranges in Expert mode)
  const cmpCard = h('section', { class: 'card mc-plans', dataset: { story: 'mission-compare' } });
  res.append(cmpCard);
  plansChart(cmpCard, policies);

  // ---- KPI tiles (each carries the verbatim scope line)
  const K = Object.fromEntries((kpis.kpis || []).map((k) => [k.id, k]));
  const tiles = ['aog_hours', 'immediate_fill_rate', 'aog_events'].map((id) => K[id]).filter(Boolean).map((k) => kpiCard(k, kpis));
  if (tiles.length) res.append(h('div', { class: 'mc-kpis', dataset: { story: 'mission-kpis' }, role: 'group', 'aria-label': 'Headline numbers: Network Plan compared with the Simple Rulebook' }, tiles));

  // ---- A2 reading note, directly under the results numbers (verbatim; excluded from the readability score)
  const note = readingNote({ cls: 'mc-reading' });
  note.dataset.readability = 'skip';
  res.append(note);

  // ---- money (A4) + how sure (A6)
  const sw = kpis.stress_worlds || {};
  const W = { low_stress: byMode('easier world', 'low stress'), central: byMode('middle world', 'central'), high_stress: byMode('tougher world', 'high stress') };
  const pm = (v) => `${v < 0 ? '−' : '+'}${fmtInt(Math.abs(v))} h`;
  res.append(h('div', { class: 'mc-pair' },
    card({
      cls: 'mc-capital', story: 'mission-capital', kicker: byMode('Money', 'Capital (A4)'), prov: 'SIMULATED',
      title: 'What the Network Plan buys and removes',
      body: h('div', { class: 'mc-body' },
        h('p', {}, 'The plan changes which ', term('rotable', { label: 'repairable parts' }), ' are held, and where. It buys some and removes others. Read the three lines together.'),
        capitalTable(core)),
    }),
    card({
      cls: 'mc-sure', kicker: byMode('How sure are we?', 'Stress worlds and ranges (A6)'), prov: 'ASSUMED',
      title: 'Tested in three worlds, over a narrow range',
      body: h('div', { class: 'mc-body' },
        h('p', { dataset: { role: 'stress-worlds' } }, 'Every plan also ran in ', term('stress_worlds'), ': ', h('b', { class: 'mc-verbatim' }, sw.text || ''), '.'),
        Array.isArray(core.worlds) && core.worlds.length ? h('p', {}, `The Network Plan beat the Simple Rulebook in all three: ${core.worlds.map((w) => `${pm(w.aog_hours.mean)} (${W[w.variant] || w.variant})`).join(' · ')}.`) : null,
        h('p', { class: 'mc-ranges', dataset: { role: 'ranges-note', readability: 'skip' } }, sw.ranges_note || ''),
        h('p', { class: 'expert-only t-13 muted' }, `Parameter: ${sw.parameter || 'reliability'} · source ${sw.source || 'config'}.`)),
    })));

  // ---- post-plan donor recount (kept apart from the frozen results)
  const dr = donorCard(kpis.donor_recount);
  if (dr) res.append(dr);

  // ---- honest findings
  const hf = honestCard(kpis.headline?.honest || {});
  if (hf) res.append(hf);

  // ================================================================ today's planner priorities
  res.append(prioritiesCard(ranked, actions, parts, partBy, ctx));

  if (ctx.params?.section === 'results') scrollToResults(false);
  return () => { cleanups.forEach((f) => { try { f?.(); } catch { /* ignore */ } }); };
}

// ------------------------------------------------------------------ the four plans
function plansChart(host, policies) {
  const P = policies.policies || [];
  const expert = getMode() === 'expert';
  const rows = PLANS.map((id) => {
    const p = P.find((x) => x.policy_id === id);
    const a = p?.kpi?.aog_hours;
    return a && num(a.mean) ? { id, name: displayName(id), value: a.mean, lo: a.ci_lo ?? a.mean, hi: a.ci_hi ?? a.mean } : null;
  }).filter(Boolean);
  const base = rows.find((r) => r.id === 'P0'), core = rows.find((r) => r.id === 'P2');
  const pct = base && core ? Math.round((1 - core.value / base.value) * 100) : null;
  const ci = termText('ci');
  const f = chartFrame(host, {
    headline: pct != null ? `Network Plan: ${pct}% fewer ${byMode('hours waiting for parts', 'material AOG hours')} than the Simple Rulebook` : 'Plan comparison not run',
    subtitle: byMode('Hours a year planes sat grounded waiting for a part · average of 20 fresh test runs', `Material AOG h/yr, mean of ${fmtInt(policies.n_seeds)} holdout seeds (paired) · whiskers = ${ci}`),
    implication: byMode('Placing spares across the network does most of the work. Extra spares help a little more, at extra cost.',
      'Network positioning carries the core result; extra capital (I125) is a secondary option.'),
    provenance: policies.meta?.provenance || 'SIMULATED', source: 'policies.json',
    table: { columns: [{ key: 'name', label: 'Plan' }, { key: 'value', label: byMode('Hours a year', 'AOG h/yr'), num: true, format: fmtHours }, { key: 'lo', label: `${ci} low`, num: true, format: fmtHours }, { key: 'hi', label: `${ci} high`, num: true, format: fmtHours }], rows },
  });
  if (!rows.length) { f.body.append(h('p', { class: 'faint t-14' }, 'Not run.')); return; }
  const max = Math.max(...rows.map((r) => (expert ? r.hi : r.value))) * 1.04;
  const pc = (v) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  f.body.append(h('ul', { class: 'mc-bars list-reset', role: 'list', 'aria-label': 'Hours waiting for parts per year, by plan' },
    rows.map((r) => h('li', { class: `mc-bar is-${r.id === 'P2' ? 'core' : r.id === 'P0' ? 'base' : 'ctx'}`, dataset: { code: r.id } },
      h('span', { class: 'mc-bar-name' }, nameTag(r.id)),
      h('span', { class: 'mc-bar-track', 'aria-hidden': 'true' },
        h('span', { class: 'mc-bar-fill', style: { width: pc(r.value) } }),
        expert ? h('span', { class: 'mc-bar-ci', style: { left: pc(r.lo), width: `calc(${pc(r.hi)} - ${pc(r.lo)})` } }) : null),
      h('span', { class: 'mc-bar-v' }, h('b', {}, fmtHours(r.value)), expert ? h('span', { class: 'mc-bar-range' }, ` ${ci} ${fmtInt(r.lo)}–${fmtHours(r.hi)}`) : null)))));
  f.body.append(scopeLine());
}

// ------------------------------------------------------------------ KPI tiles
const TILE_LABEL = {
  aog_hours: ['Hours waiting for parts a year', 'Material AOG hours / year'],
  immediate_fill_rate: ['Chance the part is on the shelf', 'Immediate fill rate'],
  aog_events: ['Groundings waiting for a part a year', 'AOG events / year'],
};
function kpiCard(k, kpis) {
  const fmt = k.unit === '%' ? (v) => fmtPct(v) : k.unit === 'h' ? fmtHours : (v) => fmt1(v);
  const dfmt = k.unit === '%' ? (v) => `${(Math.abs(v) * 100).toFixed(1)} pts` : fmt;
  const base = displayName(kpis.baseline_id || 'P0', { mode: 'short' });
  const lab = TILE_LABEL[k.id] || [k.label, k.label];
  const tile = kpiTile({ ...k, label: byMode(lab[0], lab[1]), baseline_label: base, delta: num(k.delta) ? k.delta : (num(k.value) && num(k.baseline) ? k.value - k.baseline : 0), ci: Array.isArray(k.ci) ? k.ci : null },
    { format: fmt, deltaFormat: dfmt, deltaTone: /fill/.test(k.id) ? 'neutral' : 'auto' });
  tile.dataset.kpi = k.id;
  tile.querySelector('.kpi-spark')?.remove();
  const plan = h('div', { class: 'mc-kpi-plan' }, nameTag(kpis.core_id || 'P2', { mode: 'short' }));
  tile.querySelector('.kpi-value')?.before(plan);
  const foot = tile.querySelectorAll('.kpi-foot > span');
  if (foot[0]) { foot[0].classList.add('expert-only'); if (getMode() === 'simple') foot[0].textContent = foot[0].textContent.replace('95% CI', termText('ci', { cap: true })); }
  return tile;
}

// ------------------------------------------------------------------ post-plan donor recount
function donorCard(D) {
  if (!D?.holdout) return null;
  const H = D.holdout, R = H.robberies_per_year || {}, hist = D.historical_p0;
  const nr = (v) => (typeof v === 'string' ? v : null);
  const ci = termText('ci');
  const rows = PLANS.map((id) => {
    const r = R[id] || {};
    return h('tr', { dataset: { code: id } },
      h('th', { scope: 'row' }, nameTag(id, { mode: 'short' })),
      r.status ? h('td', { colspan: '2', class: 'mc-nr' }, r.status) : [
        h('td', { class: 'is-num' }, fmt1(r.mean)),
        h('td', { class: 'is-num expert-only' }, Array.isArray(r.ci) ? `${fmt1(r.ci[0])}–${fmt1(r.ci[1])}` : '—')]);
  });
  const pd = H.robberies_paired?.['P2-P0'];
  const histBlock = hist ? h('div', { class: 'mc-hist', dataset: { role: 'historical-p0' } },
    h('div', { class: 'mc-hist-head' }, h('span', { class: 'chip mc-chip-hist' }, 'history'),
      h('span', { class: 'mc-hist-t' }, byMode('Historical Simple Rulebook: one simulated history, not the fresh test runs', 'Historical P0 (history weeks 0–103, one P0 world)'))),
    h('p', { class: 'mc-hist-label expert-only' }, hist.label),
    h('div', { class: 'mc-hist-pair' },
      h('div', { class: 'mc-hist-fig', dataset: { role: 'hist-gross' } }, h('b', {}, `${fmtInt(hist.gross_donor_hours_per_year)} h`), h('span', {}, 'a year: donor aircraft held after giving up a part (gross, an upper bound)')),
      h('div', { class: 'mc-hist-fig', dataset: { role: 'hist-counted' } }, h('b', {}, `${fmtInt(hist.counted_material_aog_hours_per_year)} h`), h('span', {}, 'a year: counted hours waiting for parts in the same history'))),
    h('p', { class: 'expert-only t-13 muted' }, `${fmtInt(hist.robberies)} robberies (${fmtInt(hist.robberies_per_year)}/yr) from ${fmtInt(hist.donor_tails)} donor tails · mean ${fmt1(hist.mean_days_held)} days held · ${fmtPct(hist.share_d3_d10, 0)} D3/D10 needs · per-tail union ${fmtInt(hist.donor_hours_per_tail_union_per_year)} h/yr.`)) : null;
  return card({
    cls: 'mc-donor', story: 'mission-donor', kicker: byMode('Borrowed parts', 'Donor recount (V21-B)'), prov: 'SIMULATED',
    title: h('span', { class: 'mc-title-row' }, 'Parts borrowed from our other aircraft', postPlanBadge()),
    body: h('div', { class: 'mc-body', dataset: { role: 'donor-recount' } },
      h('p', {}, 'Sometimes a part is taken from another of our aircraft: ', term('robbery'), '. That second aircraft then waits too. Its hours are not in the results above.'),
      h('p', { class: 'mc-donor-label', dataset: { readability: 'skip' } }, D.label),
      h('div', { class: 'table-wrap mc-donor-table' }, h('table', { class: 'data-table data-table--dense' },
        h('caption', { class: 'sr-only' }, 'Times a year a part was borrowed from another aircraft, 20 fresh test runs'),
        h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Plan'), h('th', { scope: 'col', class: 'is-num' }, 'Times a year'), h('th', { scope: 'col', class: 'is-num expert-only' }, ci))),
        h('tbody', {}, rows))),
      pd && num(pd.mean) ? h('p', {}, `The Network Plan borrows about ${fmt1(pd.mean)} ${pd.mean < 0 ? 'fewer' : 'more'} times a year than the Simple Rulebook.`, h('span', { class: 'expert-only' }, ` Paired ${ci} ${sgn(pd.ci[0])} to ${sgn(pd.ci[1])}.`)) : null,
      h('p', { dataset: { role: 'donor-hours' } }, 'Hours the donor aircraft waited, in the fresh test runs: ', h('b', {}, nr(H.donor_hours) || '—'), '.'),
      H.donor_hours_why ? h('p', { class: 'expert-only t-13 muted' }, H.donor_hours_why) : null,
      histBlock),
  });
}

// ------------------------------------------------------------------ honest findings
function honestCard(ho) {
  const items = [];
  if (num(ho.forecast_cells)) items.push(['forecast', ['Our chosen ', term('forecast_methods'), ` were best in only ${fmtInt(ho.forecast_champions_best)} of ${fmtInt(ho.forecast_cells)} test groups.`,
    num(ho.sba_intermittent_rotables_rank) ? [' One of them, ', term('sba', { label: byMode('the method picked for repairable parts', 'SBA') }), `, ranked ${ord(ho.sba_intermittent_rotables_rank)} of ${fmtInt(ho.sba_intermittent_rotables_n_methods)} in its own group.`] : null]]);
  if (num(ho.mtbur_history_error)) items.push(['mtbur', ['Working out ', term('mtbur'), ` from history was about ${fmtPct(ho.mtbur_history_error, 0)} off the truth. Supplier quotes were about ${fmtPct(ho.mtbur_quote_error, 0)} off.`]]);
  if (num(ho.fill_pts_P2_vs_P0)) items.push(['shelf', ['The Network Plan has about a ', `${Math.abs(ho.fill_pts_P2_vs_P0).toFixed(2)}-point lower `, term('fill_rate'), ' than the Simple Rulebook. It keeps fewer cheap parts in stock.']]);
  if (ho.routes_off) items.push(['routes', ['Every plan leans on emergency help from outside, such as ', term('exchange'), `. With that switched off, the Network Plan rises from ${fmtHours(ho.routes_off.central_p2_aog_hours)} to ${fmtHours(ho.routes_off.p2_aog_hours)} a year, in `, term('selection_seeds'), '.']]);
  if (!items.length) return null;
  return card({
    cls: 'mc-honest', story: 'mission-findings', kicker: byMode('Honest findings', 'Unfavourable results, kept visible'), prov: 'SIMULATED',
    title: 'What did not go our way',
    body: h('ul', { class: 'mc-findings list-reset', dataset: { role: 'honest-findings' } }, items.map(([k, t]) => h('li', { class: 'is-caveat', dataset: { finding: k } }, icon('info'), h('span', {}, t)))),
    foot: [h('span', {}, byMode('These limits are part of the result.', 'Disclosed, not re-tuned (LIMITATIONS)')), h('a', { class: 'card-link', href: '#/method' }, 'Data & Method', icon('chevron-right'))],
  });
}

// ------------------------------------------------------------------ planner priorities
/** Short imperative per exception type (copy, not data). */
const TYPE_STEP = {
  OUTSTATION_DEPLETION: 'Position stock', LEAD_TIME_DRIFT: 'Update lead time', OVERDUE_REPAIR: 'Chase repair shop',
  EXCESS_DECLINING_DEMAND: 'Cut min/max', CONDEMNED_AWAITING_REPLACEMENT: 'Track replacement PO', QUARANTINE_DOCS: 'Review certificate',
  EXPIRY_RISK: 'Use or rotate stock', KIT_SHORTAGE: 'Complete the kit',
  DONOR_NOT_REINSTATED: 'Reinstate the donor', OPEN_LOAN: 'Return the loan unit', OPEN_REQUIREMENT: 'Keep recovery routes open',
};

function prioritiesCard(ranked, actions, parts, partBy, ctx) {
  const all = actions.actions || [];
  const groups = groupByPn(ranked).slice(0, 5);
  const nUrg = all.filter((a) => a.severity === 'urgent').length;
  const nUrgPn = new Set(all.filter((a) => a.severity === 'urgent').map((a) => a.pn)).size;
  const aogMeta = parts.aog_metric_labels?.aog_h_52w_max_station;
  const aogLabel = (typeof aogMeta === 'string' ? aogMeta : aogMeta?.label) || 'AOG h · last 52 wk · worst station';
  groups.forEach((g) => { const pv = partBy[g.pn]?.aog_h_52w_max_station; if (num(pv)) { g.aog = pv; g.aogSt = partBy[g.pn]?.aog_h_52w_max_station_id || null; } else if (g.aog != null) g.aogSt = g.list.find((a) => a.evidence?.aog_hours_lookback === g.aog)?.station || null; });
  const head = h('div', { class: 'mc-pr mc-pr--head', 'aria-hidden': 'true' },
    h('span', {}, byMode('How urgent', 'Severity')), h('span', {}, 'Part · where'), h('span', {}, byMode('Problem · next step', 'Signal · next step')),
    h('span', { class: 'num mc-pr-aogh', title: aogLabel }, h('span', {}, byMode('Hours grounded', 'AOG h · 52 wk')), h('span', {}, byMode('worst airport', 'worst station'))), h('span', { class: 'num' }, 'Due'), h('span', {}));
  const rowsEl = groups.map((g) => {
    const a = g.lead;
    const sig = signalOf(a);
    const where = g.stations.length ? (g.stations.length > 1 ? `${g.stations[0]} +${g.stations.length - 1} station${g.stations.length > 2 ? 's' : ''}` : g.stations[0]) : 'Network';
    return h('a', { class: `mc-pr is-${a.severity}`, href: ctx.buildHash('actions', { id: a.exception_id }), role: 'listitem', 'aria-label': `${cap(a.severity)}: ${a.pn}${g.stations.length ? ` at ${g.stations.join(', ')}` : ''}. ${sig.long}. ${a.recommended_action || ''}`, title: a.summary },
      h('span', { class: 'mc-pr-sev' }, pill(SEV_RANK[a.severity] != null ? a.severity : 'unknown')),
      h('span', { class: 'mc-pr-part' }, h('span', { class: 'mc-pr-pn' }, a.pn), h('span', { class: 'mc-pr-where', title: g.stations.join(', ') }, where),
        h('span', { class: 'mc-pr-type', title: a.type_label || a.type }, a.type_label || a.type)),
      h('span', { class: 'mc-pr-sig', title: sig.k }, h('span', { class: 'mc-pr-v' }, sig.v), h('span', { class: 'mc-pr-step' }, TYPE_STEP[a.type] || 'Review')),
      h('span', { class: 'mc-pr-aog num', title: aogLabel }, h('span', { class: 'mc-pr-ml' }, byMode('Worst airport ', 'Worst stn ')), g.aog ? [fmtHours(g.aog), g.aogSt ? h('span', { class: 'mc-pr-st' }, ` · ${g.aogSt}`, g.stations.includes(g.aogSt) ? null : h('span', { class: 'mc-pr-noex' }, 'no exception there')) : null] : '—'),
      h('span', { class: 'mc-pr-due num' }, h('span', { class: 'mc-pr-ml' }, 'Due '), num(g.due) ? fmtWeek(g.due) : '—'),
      h('span', { class: 'mc-pr-do', 'aria-hidden': 'true' }, icon('chevron-right')));
  });
  return card({
    cls: 'mc-prio-card', story: 'mission-actions', kicker: 'Today’s planning priorities', prov: actions.meta?.provenance || 'DERIVED',
    title: all.length ? `${fmtInt(nUrg)} urgent actions on ${fmtInt(nUrgPn)} part numbers; top ${fmtInt(groups.length)} shown` : 'No open actions exported',
    // a data grid (like a table): excluded from the readability score
    body: h('div', { class: 'mc-prio', role: 'list', dataset: { readability: 'skip' } }, head, rowsEl),
    foot: [h('span', { title: aogMeta?.definition || aogLabel }, byMode('Most urgent first, then highest risk', `Ranked by severity then risk · ${aogLabel}`)), h('a', { class: 'card-link', href: '#/actions' }, 'Open Planner Action Centre', icon('chevron-right'))],
  });
}

/** Group ranked actions by PN, keeping rank order; per group: lead action, stations (by AOG h), max AOG h, earliest due. */
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
      if (num(e.days_waiting)) return { k: 'Donor waiting', v: `donor ${e.donor_tail || ''} · ${fmtInt(e.days_waiting)} d`, long: `donor aircraft ${e.donor_tail || ''} waiting ${fmtInt(e.days_waiting)} days` };
      break;
    case 'OPEN_REQUIREMENT':
      return { k: 'Open need', v: `open since ${fmtWeek(e.need_week)}${e.deadline_class ? ` · ${e.deadline_class}` : ''}`, long: `requirement open since ${fmtWeek(e.need_week)}` };
    default:
  }
  return { k: 'Summary', v: truncate(replaceCodes(a.summary || ''), 300), long: replaceCodes(a.summary || '') };
}
