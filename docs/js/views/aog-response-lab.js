/**
 * 07 · AOG Response Lab — screen agent D.
 * Data: aog_lab.json (gnm.aog: incidents, options a–h, decision panel, counterfactual; SIMULATED)
 * Deep links: #/aog?incident=AOG-0001
 * Shows: the 12 showcase incidents, a precise response timeline (removal → request → stock checks →
 * sourcing → shipped → fitted), the options with feasibility, reason codes, wait, direct cost, exposure
 * and deadline, a "Human decision required" panel, and the history-vs-best-option counterfactual.
 * The recommended option is the one ranked 1 by the lab (decision.recommended): exposure_aed already
 * includes direct cost, so the two are never added.
 */
import { h, pageHead, card, provChip, pill, icon } from '../ui.js';
import { chartFrame, responsive, svgIn, theme, fmtAED, fmtHours, fmtInt, fmtPct, withTooltip, truncate } from '../charts/theme.js';

export const data = ['aog_lab'];

const STEP_LABEL = { removal: 'Removal', request: 'Request', local_check: 'Local stock check', network_check: 'Network stock check', aog_start: 'AOG starts', sourcing: 'Sourcing decided', ordered: 'Ordered', shipped: 'Shipped', arrived: 'Arrived', received: 'Received', fitted: 'Fitted · released', unfilled: 'Unfilled', context: 'Context' };
const SHORT = { removal: 'REM', request: 'REQ', local_check: 'CHK', network_check: 'NET', aog_start: 'AOG', sourcing: 'SRC', shipped: 'SHP', arrived: 'ARR', fitted: 'FIT' };
const BASIS = {
  transport_matrix: 'Transfers keep their estimate: transport times in this world are fixed.',
  actual_order_arrival: 'Scored on the order’s actual arrival.',
  replan_expedite_at_quoted_due: 'The order missed its quoted date, so the best option is re-planned to an expedite at that date.',
  estimate_not_realisable: 'Not taken in history, so it keeps the ex-ante estimate (cannot be realised from the record).',
};
const stepLabel = (s) => STEP_LABEL[s] || String(s || 'step').replace(/_/g, ' ');
const fmtAEDfull = (v) => (v == null ? '—' : `AED ${Math.round(v).toLocaleString('en-GB')}`);

function ensureCSS() {
  if (document.querySelector('link[data-view-css="aog-response-lab"]')) return;
  document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/aog-response-lab.css', import.meta.url).href, dataset: { viewCss: 'aog-response-lab' } }));
}

/** The lab's recommendation: decision.recommended, else the rank-1 option. Never direct_cost + exposure. */
export function recommendedOption(inc) {
  const opts = inc.options || [];
  const key = inc.decision?.recommended ?? inc.recommended_option;
  return (key && opts.find((o) => o.key === key)) || opts.find((o) => o.rank === 1) || null;
}

function optState(o, rec) {
  if (o.human_decision) return { cls: 'human', pill: pill('review', 'Human decision'), order: 5 };
  if (rec && o === rec) return { cls: 'rec', pill: pill('ok', 'Recommended'), order: 0 };
  if (o.indicative || (o.reason_codes || []).includes('NOT_CONTRACTED')) return { cls: 'greyed', pill: pill('unknown', 'Not contracted'), order: 3 };
  if (o.feasible) return { cls: 'feasible', pill: pill('info', o.rank ? `Feasible · rank ${o.rank}` : 'Feasible'), order: 1 };
  return { cls: 'infeasible', pill: pill('unknown', 'Infeasible'), order: 4 };
}

export async function render(el, ctx) {
  ensureCSS();
  const { aog_lab: A } = ctx.data;
  const codes = A.reason_codes || {};
  const labels = A.option_labels || {};
  const prov = A.meta?.provenance || A.provenance || 'SIMULATED';
  const showIds = Array.isArray(A.showcase_ids) && A.showcase_ids.length ? A.showcase_ids : (A.incidents || []).map((i) => i.id);
  const incidents = showIds.map((id) => A.incidents.find((i) => i.id === id)).filter(Boolean);
  let inc = incidents.find((i) => i.id === ctx.params.incident) || incidents[0];
  const optLabel = (o) => o.option || labels[o.key] || o.key;

  el.append(pageHead({
    num: '07', eyebrow: 'AOG Response Lab',
    title: 'An aircraft is on the ground. What are the options?',
    lede: `${fmtInt(incidents.length)} showcase groundings from the simulated history of Falcon Hub Airways (fictional). Each is replayed at the moment of the request, using only what the AOG desk knew then: stock before the request, open orders at their quoted dates. Deadline classes D0/D3/D10 are hypothetical simulation classes, not MEL categories.`,
    meta: [provChip(prov), h('span', { class: 'chip chip-mono' }, 'History W0–W103 · policy P0')],
  }));

  // ---- incident picker
  const picker = h('div', { class: 'aog-picker', role: 'radiogroup', 'aria-label': 'Showcase incident' });
  const tiles = incidents.map((i) => h('button', {
    type: 'button', role: 'radio', class: 'aog-tile', dataset: { id: i.id }, 'aria-checked': String(i === inc),
    onclick: () => select(i),
  },
  h('span', { class: 'aog-tile-top' }, h('span', { class: 'mono' }, i.id), h('span', { class: `aog-dl aog-dl--${String(i.deadline).toLowerCase()}` }, i.deadline)),
  h('span', { class: 'aog-tile-pn mono' }, i.pn),
  h('span', { class: 'aog-tile-desc' }, i.desc || ''),
  h('span', { class: 'aog-tile-foot mono' }, h('span', {}, i.station), h('span', {}, i.aog_hours != null ? fmtHours(i.aog_hours) : 'AOG h not run'))));
  picker.append(...tiles);
  picker.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;
    e.preventDefault();
    const k = incidents.indexOf(inc) + (e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1);
    select(incidents[(k + incidents.length) % incidents.length], true);
  });
  el.append(card({ kicker: 'Showcase incidents', title: 'Pick a grounding to replay', prov, story: 'aog-picker', body: picker }));

  const host = h('div', { class: 'mt-3' });
  el.append(host);
  const summaryHost = h('div', { class: 'mt-3' });
  el.append(summaryHost);
  let stops = [];

  function select(i, focus) {
    inc = i;
    tiles.forEach((t) => { const on = t.dataset.id === i.id; t.setAttribute('aria-checked', String(on)); t.tabIndex = on ? 0 : -1; if (on && focus) t.focus(); });
    ctx.setParams({ incident: i.id });
    draw();
  }
  tiles.forEach((t) => (t.tabIndex = t.dataset.id === inc?.id ? 0 : -1));

  function draw() {
    stops.forEach((s) => s()); stops = [];
    if (!inc) { host.replaceChildren(h('div', { class: 'state' }, icon('info'), h('p', {}, 'No incidents exported.'))); return; }
    const rec = recommendedOption(inc);
    const cf = inc.counterfactual || {};
    const req = (inc.timeline || []).find((s) => s.step === 'request');
    const slack = req?.evidence?.slack_h ?? (inc.deadline === 'D0' ? 0 : null);

    // incident header
    const facts = [
      ['Tail', `${inc.tail} (fictional)`], ['Station', inc.station], ['Part', `${inc.pn}`], ['ATA · class', [inc.ata ? `ATA ${inc.ata}` : null, inc.part_class ? { R: 'Rotable', C: 'Consumable', E: 'Expendable' }[inc.part_class] || inc.part_class : null].filter(Boolean).join(' · ') || '—'],
      ['Deadline', `${inc.deadline}${slack != null ? ` · ${fmtHours(slack)} slack` : ''} (hypothetical)`], ['Trigger', inc.trigger ? inc.trigger.replace(/_/g, ' ') : '—'],
      ['AOG (history)', inc.aog_hours != null ? fmtHours(inc.aog_hours) : 'not run'], ['AOG penalty', inc.penalty_aed_per_h != null ? `${fmtAEDfull(inc.penalty_aed_per_h)} / h · ${inc.archetype || ''}` : 'not run'],
    ];
    const head = card({
      cls: 'aog-head', kicker: `${inc.id}${inc.need_datetime ? ` · ${inc.need_datetime.replace('T', ' ').replace('Z', ' UTC (simulated)')}` : ''}`,
      title: `${inc.pn} · ${inc.desc || ''}`, prov,
      body: h('dl', { class: 'aog-facts' }, facts.map(([k, v]) => h('div', {}, h('dt', {}, k), h('dd', { class: k === 'Part' || k === 'Station' ? 'mono' : '' }, v)))),
    });

    // timeline
    const tlCard = h('section', { class: 'card span-12', dataset: { story: 'aog-timeline' } });
    const incWrap = h('div', { class: 'span-12 aog-incident', dataset: { story: inc.id === 'AOG-0001' ? 'aog-incident-ps1' : 'aog-incident', incident: inc.id } });
    const fitted = (inc.timeline || []).find((s) => s.step === 'fitted');
    const tf = chartFrame(tlCard, {
      headline: fitted ? `Released ${fmtHours(fitted.t_h)} after the request: ${cf.actual_route_label || 'route not recorded'}` : `Not released within the history window: ${cf.actual_route_label || 'route not recorded'}`,
      subtitle: 'Hours from the material request (T+) · simulated UTC · steps marked context happened before the request',
      provenance: prov, source: 'aog_lab.json',
      table: { columns: [{ key: 'datetime', label: 'Simulated UTC', mono: true }, { key: 't_h', label: 'T+ h', num: true }, { key: 'station', label: 'Station', mono: true }, { key: 'step', label: 'Step', format: stepLabel }, { key: 'event', label: 'Event' }], rows: inc.timeline || [] },
    });
    stops.push(responsive(tf.body, (w) => drawTimeline(tf.body, w, inc, slack)));
    const tlList = h('ol', { class: 'aog-tl list-reset' }, (inc.timeline || []).map((s, i) => h('li', { class: `aog-tl-row ${s.evidence?.context ? 'is-context' : ''} ${s.step === 'fitted' ? 'is-fitted' : ''}` },
      h('span', { class: 'aog-tl-n mono' }, String(i + 1).padStart(2, '0')),
      h('span', { class: 'aog-tl-time mono' }, h('span', {}, (s.datetime || '').replace('T', ' ').replace('Z', '')), h('span', { class: 'faint' }, `T${s.t_h >= 0 ? '+' : '−'}${Math.abs(s.t_h)} h`)),
      h('span', { class: 'aog-tl-stn mono' }, s.station || ''),
      h('span', { class: 'aog-tl-ev' }, h('b', {}, stepLabel(s.step)), ' ', s.event))));
    tf.body.after(tlList);

    // options
    const opts = (inc.options || []).slice().sort((a, b) => optState(a, rec).order - optState(b, rec).order || (a.rank ?? 99) - (b.rank ?? 99) || String(a.key).localeCompare(String(b.key)));
    const optCards = opts.map((o) => optionCard(o, rec, inc, codes, optLabel, slack));
    const feas = opts.filter((o) => o.feasible && o.exposure_aed != null && !o.human_decision);
    const runner = feas.filter((o) => o !== rec).sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))[0];
    const exCard = h('section', { class: 'card span-12' });
    const ef = chartFrame(exCard, {
      headline: rec ? `${optLabel(rec)} has the lowest exposure: ${fmtAED(rec.exposure_aed)}${runner ? ` against ${fmtAED(runner.exposure_aed)} for ${optLabel(runner).toLowerCase()}` : ''}` : 'No feasible option at the time of the request',
      subtitle: `Exposure = hours beyond the ${slack != null ? `${fmtHours(slack)} ` : ''}deadline slack × AOG penalty + direct cost (AED) · ex-ante estimate at request time · greyed = not contracted`,
      provenance: prov, source: 'aog_lab.json',
      table: { columns: [{ key: 'key', label: 'Key', mono: true }, { key: 'option', label: 'Option' }, { key: 'feasible', label: 'Feasible', format: (v) => (v ? 'yes' : 'no') }, { key: 'wait_h', label: 'Wait', num: true, format: fmtHours }, { key: 'direct_cost', label: 'Direct cost', num: true, format: (v) => fmtAEDfull(v) }, { key: 'exposure_aed', label: 'Exposure', num: true, format: (v) => fmtAEDfull(v) }, { key: 'rank', label: 'Rank', num: true, format: (v) => (v == null ? '—' : v) }], rows: opts },
    });
    stops.push(responsive(ef.body, (w) => drawExposure(ef.body, w, opts, rec, optLabel)));

    // human decision panel
    const d = inc.decision || {};
    const robbery = opts.find((o) => o.human_decision);
    const human = card({
      cls: 'span-7 aog-human', bp: true, kicker: 'Human decision required', title: rec ? `Recommend: ${d.recommended_label || optLabel(rec)}${d.source || rec.source ? ` (${d.source || rec.source})` : ''}` : 'No feasible option to recommend', prov, story: 'aog-decision',
      body: h('div', { class: 'stack-3' },
        h('p', { class: 'aog-why m-0' }, d.why || 'No reasoning exported.'),
        h('div', {}, h('div', { class: 'card-kicker mb-1' }, 'What a human must check before acting'),
          h('ul', { class: 'aog-checks list-reset' }, (d.checks || []).map((c) => h('li', {}, icon('check'), h('span', {}, c))))),
        h('div', { class: 'aog-robbery' }, h('div', { class: 'row' }, icon('alert'), h('b', {}, 'Robbery / cannibalisation')),
          h('p', { class: 'm-0' }, 'Requires engineering/quality approval — human decision. Never ranked or recommended by the lab.'),
          d.robbery_note ? h('p', { class: 'm-0 faint' }, d.robbery_note) : null,
          robbery?.evidence?.donors?.length ? h('p', { class: 'm-0 mono t-12' }, `Donor aircraft: ${robbery.evidence.donors.map((x) => (typeof x === 'string' ? x : `${x.tail || x.aircraft || ''} ${x.status || ''}`.trim())).join(', ')}`) : null,
          h('ul', { class: 'aog-checks list-reset' }, (d.robbery_checks || []).map((c) => h('li', {}, icon('shield'), h('span', {}, c))))),
        h('p', { class: 't-12 faint m-0' }, 'The lab supports the AOG desk. It is not an approved maintenance, airworthiness or dispatch tool.')),
    });
    const optsWrap = card({ cls: 'span-12', kicker: `Options a–h · ${fmtInt(opts.filter((o) => o.feasible && !o.human_decision).length)} feasible`, title: 'Every sourcing route the desk could have taken', prov, body: h('div', { class: 'aog-opts' }, optCards) });

    // counterfactual for this incident
    const cfCard = counterfactualCard(inc, cf, prov, optLabel);

    head.classList.add('mb-3');
    incWrap.append(head, tlCard);
    host.replaceChildren(
      h('div', { class: 'grid-12' }, incWrap, exCard),
      h('div', { class: 'grid-12 mt-3' }, optsWrap),
      h('div', { class: 'grid-12 mt-3' }, human, h('div', { class: 'span-5 aog-side' }, cfCard)),
    );
  }

  // ---- network-wide counterfactual summary (all requests)
  function drawSummary() {
    const S = A.summary || A.counterfactual_summary || null;
    const C = S?.counterfactual || S;
    if (!C || C.actual_request_aog_h == null) {
      summaryHost.replaceChildren(card({ kicker: 'Counterfactual · all requests', title: 'History versus the best feasible option', prov, body: h('p', { class: 'muted m-0' }, 'The network-wide counterfactual summary is not in this export (not run).') }));
      return;
    }
    const sc = h('section', { class: 'card span-7' });
    const rows = [
      { key: 'actual', label: 'History (route taken)', value: C.actual_request_aog_h, ex: C.actual_exposure_aed },
      { key: 'post', label: 'Best option, scored ex post', value: C.best_option_request_aog_h, ex: C.best_option_exposure_aed, hi: true },
      { key: 'ante', label: 'Best option, ex-ante estimate', value: C.best_option_request_aog_h_ex_ante, ex: C.best_option_exposure_aed_ex_ante },
    ].filter((r) => r.value != null);
    const saved = C.actual_request_aog_h - C.best_option_request_aog_h;
    const fr = chartFrame(sc, {
      headline: `Taking the best feasible option at request time would have cut request-level AOG from ${fmtHours(C.actual_request_aog_h)} to ${fmtHours(C.best_option_request_aog_h)}${C.net_exposure_saving_aed != null ? `, ${fmtAED(C.net_exposure_saving_aed)} less exposure` : ''}`,
      subtitle: `${fmtInt(C.requests_compared)} requests · history weeks 0–103 under P0 · AOG hours before merging per incident · exposure in AED`,
      provenance: prov, source: 'aog_lab.json',
      table: { columns: [{ key: 'label', label: 'Basis' }, { key: 'value', label: 'AOG h', num: true, format: fmtHours }, { key: 'ex', label: 'Exposure', num: true, format: (v) => fmtAED(v) }], rows },
    });
    stops2.push(responsive(fr.body, (w) => {
      const d3 = window.d3;
      const narrow = w < 520, lw = narrow ? 0 : 210, rowH = narrow ? 46 : 38, H = rows.length * rowH + 30;
      const svg = svgIn(fr.body, w, H, 'Counterfactual AOG hours');
      const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.value) * 1.05]).range([0, Math.max(40, w - lw - 150)]);
      rows.forEach((r, i) => {
        const y = i * rowH + (narrow ? 16 : 8);
        svg.append('text').attr('class', r.hi ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', narrow ? y - 4 : y + 11).text(r.label);
        svg.append('rect').attr('x', lw).attr('y', y + (narrow ? 2 : 2)).attr('height', 14).attr('rx', 2).attr('width', Math.max(1, x(r.value))).attr('fill', r.key === 'actual' ? theme.color.accent2 : r.hi ? theme.color.accent : theme.color.neutral).attr('fill-opacity', r.key === 'ante' ? 0.6 : 0.95);
        svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', lw + x(r.value) + 8).attr('y', y + 13).text(`${fmtHours(r.value)} · ${fmtAED(r.ex)}`);
      });
      if (saved > 0 && !narrow) {
        const y0 = (rows.length) * rowH + 18;
        svg.append('text').attr('class', 'gnm-annot-sub').attr('x', lw).attr('y', y0).text(`${fmtHours(saved)} fewer AOG hours over two simulated years, ex post`);
      }
    }));
    const n = C.requests_compared;
    const cav = card({
      cls: 'span-5', kicker: 'Honest caveats', title: 'How to read this counterfactual', prov,
      body: h('div', { class: 'stack-3' },
        h('dl', { class: 'meta-list' },
          h('dt', {}, 'Best option taken'), h('dd', {}, C.history_took_best_option != null ? `${fmtInt(C.history_took_best_option)} of ${fmtInt(n)} requests (${fmtPct(C.history_took_best_option / n, 0)})` : 'not run'),
          h('dt', {}, 'History did better'), h('dd', {}, C.requests_where_history_beat_estimate != null ? `${fmtInt(C.requests_where_history_beat_estimate)} requests` : 'not run'),
          h('dt', {}, 'Scoring basis'), h('dd', {}, C.realised_basis_counts ? Object.entries(C.realised_basis_counts).map(([k, v]) => `${fmtInt(v)} ${k.replace(/_/g, ' ')}`).join(' · ') : 'not run')),
        h('ul', { class: 'aog-caveats' },
          h('li', {}, 'Options are ex-ante estimates built on quoted figures. Quoted repair and purchase dates are unreliable in this world, and expedite lead times are a cap, not a supplier quote.'),
          h('li', {}, 'Accelerated repair, expedite and pool were not taken in history, so they keep their estimate; they cannot be realised from the record.'),
          h('li', {}, '“Await inbound” queues behind earlier unfilled requests network-wide; the engine may have allocated units differently.'),
          h('li', {}, 'Fitting time is zero, as in the engine: issue = fitted = released. Pool exchange is shown for reference only: no contract existed under P0.'))),
    });
    summaryHost.replaceChildren(h('div', { class: 'grid-12' }, sc, cav));
  }
  let stops2 = [];
  draw();
  drawSummary();
  return () => { stops.forEach((s) => s()); stops2.forEach((s) => s()); };
}

// ----------------------------------------------------------------------------- pieces
function optionCard(o, rec, inc, codes, optLabel, slack) {
  const st = optState(o, rec);
  const metric = (k, v, extra) => h('div', { class: 'aog-m' }, h('dt', {}, k), h('dd', { class: 'num' }, v, extra || null));
  const met = o.human_decision ? h('span', { class: 'faint' }, 'n/a') : o.wait_h == null ? h('span', { class: 'faint' }, '—') : o.deadline_met ? pill('ok', 'Met') : pill('urgent', 'Missed');
  const rc = (o.reason_codes || []).map((c) => h('li', {}, h('span', { class: 'mono aog-code' }, c), h('span', { class: 'aog-code-txt' }, codes[c] || '')));
  return h('article', { class: `aog-opt aog-opt--${st.cls}`, dataset: { key: o.key, state: st.cls }, 'aria-label': `Option ${o.key}: ${optLabel(o)}` },
    h('div', { class: 'aog-opt-head' }, h('span', { class: 'aog-key mono' }, o.key), h('h4', { class: 'aog-opt-title' }, optLabel(o)), st.pill),
    o.human_decision ? h('p', { class: 'aog-human-note m-0' }, icon('alert'), 'Requires engineering/quality approval — human decision') : null,
    st.cls === 'greyed' ? h('p', { class: 'aog-human-note aog-human-note--grey m-0' }, icon('info'), 'Not contracted: indicative P3 terms shown for reference') : null,
    h('dl', { class: 'aog-metrics' },
      metric('Wait', o.wait_h == null ? '—' : fmtHours(o.wait_h)),
      metric('Cost', o.human_decision && !o.feasible ? '—' : fmtAEDfull(o.direct_cost)),
      metric('Exposure', o.exposure_aed == null ? '—' : fmtAED(o.exposure_aed)),
      h('div', { class: 'aog-m' }, h('dt', {}, 'Deadline'), h('dd', {}, met))),
    o.source ? h('div', { class: 'aog-src mono t-12 faint' }, `Source: ${o.source}${o.mode ? ` · ${o.mode.replace(/_/g, ' ')}` : ''}`) : null,
    rc.length ? h('ul', { class: 'aog-codes list-reset' }, rc) : null);
}

function counterfactualCard(inc, cf, prov, optLabel) {
  if (!cf || cf.actual_aog_h == null) return card({ kicker: 'This incident · counterfactual', title: 'History versus best option', prov, body: h('p', { class: 'muted m-0' }, 'Counterfactual not run for this incident.') });
  const better = (cf.aog_h_saving ?? 0) > 0;
  const worse = (cf.aog_h_saving ?? 0) < 0;
  const rows = [
    ['', 'History', 'Best option'],
    ['Route', cf.actual_route_label || cf.actual_route || '—', `${cf.best_option || ''} · ${cf.best_option_label || '—'}`],
    ['AOG hours', fmtHours(cf.actual_aog_h), fmtHours(cf.best_realised_aog_h ?? cf.best_aog_h)],
    ['Direct cost', fmtAEDfull(cf.actual_direct_cost_aed), fmtAEDfull(cf.best_realised_direct_cost_aed ?? cf.best_direct_cost_aed)],
    ['Exposure', fmtAED(cf.actual_exposure_aed), fmtAED(cf.best_realised_exposure_aed ?? cf.best_exposure_aed)],
  ];
  const verdict = better ? `The best option would have saved ${fmtHours(cf.aog_h_saving)} AOG and ${fmtAED(cf.exposure_saving_aed)} of exposure.`
    : worse ? `History did better than the estimate here, by ${fmtHours(-cf.aog_h_saving)}.`
      : 'History already took the best-ranked route; nothing to save.';
  return card({
    kicker: 'This incident · counterfactual', title: better ? 'A better route existed' : worse ? 'History beat the estimate' : 'History matched the best option', prov,
    body: h('div', { class: 'stack-3' },
      h('table', { class: 'data-table data-table--dense aog-cf' }, h('caption', { class: 'sr-only' }, 'History versus best option'),
        h('thead', {}, h('tr', {}, rows[0].map((c, i) => h('th', { scope: 'col', class: i ? 'is-num' : '' }, c)))),
        h('tbody', {}, rows.slice(1).map((r) => h('tr', {}, h('th', { scope: 'row' }, r[0]), h('td', { class: 'is-num' }, r[1]), h('td', { class: 'is-num' }, r[2]))))),
      h('p', { class: 'm-0' }, verdict),
      h('p', { class: 't-12 faint m-0' }, `Scoring basis: ${BASIS[cf.realised_basis] || (cf.realised_basis ? cf.realised_basis.replace(/_/g, ' ') : 'not recorded')}`)),
  });
}

function drawTimeline(body, w, inc, slack) {
  const d3 = window.d3;
  const steps = (inc.timeline || []).map((s, i) => ({ ...s, n: i + 1 }));
  if (!steps.length) { body.replaceChildren(h('p', { class: 'muted' }, 'No timeline exported.')); return; }
  const narrow = w < 560;
  const tMin = Math.min(0, d3.min(steps, (s) => s.t_h)), tMax = Math.max(d3.max(steps, (s) => s.t_h), slack ?? 0, 1);
  const groups = d3.groups(steps, (s) => s.t_h).sort((a, b) => a[0] - b[0]).map(([t, ss]) => [t, ss.length > 3 ? [{ ...ss[0], group: ss }] : ss]);
  const maxStack = d3.max(groups, (g) => g[1].length);
  const badge = narrow ? 18 : 22, gap = 4;
  const m = { t: 16 + maxStack * (badge + gap), r: narrow ? 24 : 56, b: 44, l: narrow ? 20 : 40 };
  const H = m.t + m.b + 24;
  const svg = svgIn(body, w, H, `Timeline of ${inc.id}`);
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);
  const iw = Math.max(60, w - m.l - m.r);
  const x = d3.scaleLinear().domain([tMin, tMax]).range([0, iw]);
  const axisY = 24;
  // AOG interval band
  const aog = steps.find((s) => s.step === 'aog_start');
  const fit = steps.find((s) => s.step === 'fitted');
  if (aog && fit && fit.t_h > aog.t_h) {
    g.append('rect').attr('x', x(aog.t_h)).attr('width', Math.max(2, x(fit.t_h) - x(aog.t_h))).attr('y', axisY - 6).attr('height', 12).attr('rx', 2).attr('fill', theme.color.accent2).attr('fill-opacity', 0.28).attr('stroke', theme.color.accent2).attr('stroke-opacity', 0.6);
    g.append('text').attr('class', 'gnm-label gnm-label--strong').attr('font-family', theme.font.mono).style('fill', theme.color.accent2).attr('x', (x(aog.t_h) + x(fit.t_h)) / 2).attr('y', axisY + 34).attr('text-anchor', 'middle').text(`AOG ${fmtHours(fit.t_h - aog.t_h)}`);
  }
  // axis
  const ax = g.append('g').attr('transform', `translate(0,${axisY})`).call(d3.axisBottom(x).ticks(narrow ? 4 : 8).tickSize(4).tickFormat((v) => `${v >= 0 ? '+' : '−'}${Math.abs(v)}h`));
  ax.attr('class', 'gnm-axis').selectAll('text').attr('font-family', theme.font.mono);
  ax.select('.domain').attr('stroke', theme.color.lineStrong);
  // deadline
  if (slack != null && slack > 0 && slack <= tMax) {
    g.append('line').attr('x1', x(slack)).attr('x2', x(slack)).attr('y1', -m.t + 8).attr('y2', axisY + 8).attr('stroke', theme.color.review).attr('stroke-dasharray', '3 3');
    g.append('text').attr('class', 'gnm-label').style('fill', theme.color.review).attr('font-family', theme.font.mono).attr('x', x(slack) + 4).attr('y', -m.t + 14).text(`Deadline +${slack}h`);
  } else if (slack === 0) {
    g.append('text').attr('class', 'gnm-label').style('fill', theme.color.review).attr('font-family', theme.font.mono).attr('x', x(0)).attr('y', axisY + 34).attr('text-anchor', 'start').text(aog && fit && fit.t_h - aog.t_h > (tMax - tMin) * 0.3 ? '' : 'D0 · no slack');
  }
  // badges
  groups.forEach(([t, ss]) => {
    const cx = x(t);
    g.append('line').attr('x1', cx).attr('x2', cx).attr('y1', axisY - 6 - ss.length * (badge + gap) + gap).attr('y2', axisY).attr('stroke', theme.color.lineStrong);
    ss.forEach((s, j) => {
      const cy = axisY - 10 - j * (badge + gap) - badge / 2;
      const gg = g.append('g').attr('transform', `translate(${cx},${cy})`);
      const isFit = s.step === 'fitted';
      gg.append('rect').attr('x', -badge * 1.1).attr('y', -badge / 2).attr('width', badge * 2.2).attr('height', badge).attr('rx', 4)
        .attr('fill', isFit ? theme.color.accent : theme.color.panel).attr('stroke', isFit ? theme.color.accent : s.evidence?.context ? theme.color.neutral : theme.color.lineStrong).attr('stroke-dasharray', s.evidence?.context ? '2 2' : null);
      const grp = s.group;
      const txt = grp ? `${String(grp[0].n).padStart(2, '0')}–${String(grp.at(-1).n).padStart(2, '0')}` : narrow ? String(s.n) : `${String(s.n).padStart(2, '0')} ${SHORT[s.step] || ''}`.trim();
      gg.append('text').attr('text-anchor', 'middle').attr('dy', '0.35em').attr('font-family', theme.font.mono).attr('font-size', narrow ? 9 : 10).attr('fill', isFit ? theme.color.bg : theme.color.text).text(txt);
      if (grp) gg.append('text').attr('class', 'gnm-label').attr('x', badge * 1.1 + 6).attr('dy', '0.35em').attr('font-size', 11).text(narrow ? `${grp.length} steps` : `${grp.length} steps in the same hour: ${grp.map((q) => SHORT[q.step] || q.step).join(' · ')}`);
      withTooltip(gg, () => (grp ? { title: `Steps ${txt} · T+${fmtHours(s.t_h)}`, rows: grp.map((q) => [String(q.n).padStart(2, '0'), stepLabel(q.step)]) } : { title: `${String(s.n).padStart(2, '0')} · ${stepLabel(s.step)}`, rows: [['Time', `${(s.datetime || '').replace('T', ' ').replace('Z', '')} UTC`], ['T+', fmtHours(s.t_h)], ['Station', s.station || '—']], note: s.event }));
    });
  });
}

function drawExposure(body, w, opts, rec, optLabel) {
  const d3 = window.d3;
  const rows = opts.filter((o) => !o.human_decision);
  const narrow = w < 560;
  const lw = narrow ? 0 : Math.min(300, w * 0.34), rowH = narrow ? 44 : 32;
  const H = rows.length * rowH + 8;
  const svg = svgIn(body, w, H, 'Exposure by option');
  const vals = rows.map((o) => o.exposure_aed).filter((v) => v != null);
  const x = d3.scaleLinear().domain([0, (d3.max(vals) || 1) * 1.02]).range([0, Math.max(40, w - lw - (narrow ? 120 : 170))]);
  rows.forEach((o, i) => {
    const y = i * rowH + (narrow ? 16 : 6);
    const isRec = o === rec, grey = o.indicative || o.greyed;
    const lab = `${o.key} · ${optLabel(o)}`;
    svg.append('text').attr('class', isRec ? 'gnm-label gnm-label--strong' : 'gnm-label').attr('x', 0).attr('y', narrow ? y - 4 : y + 11).style('fill', o.feasible || grey ? null : theme.color.faint).text(truncate(lab, narrow ? w : lw - 12));
    if (o.exposure_aed == null) {
      svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).style('fill', theme.color.faint).attr('x', lw).attr('y', y + 12).text(`infeasible · ${(o.reason_codes || [])[0] || ''}`);
      return;
    }
    const bar = svg.append('rect').attr('x', lw).attr('y', y + 2).attr('height', 14).attr('rx', 2).attr('width', Math.max(2, x(o.exposure_aed)))
      .attr('fill', isRec ? theme.color.accent : o.feasible ? theme.color.neutral : 'transparent')
      .attr('stroke', o.feasible || isRec ? null : theme.color.neutral).attr('stroke-dasharray', o.feasible ? null : '3 2');
    withTooltip(bar, () => ({ title: optLabel(o), rows: [['Wait', o.wait_h == null ? '—' : fmtHours(o.wait_h)], ['Direct cost', fmtAEDfull(o.direct_cost)], ['Exposure', fmtAEDfull(o.exposure_aed)]], note: o.feasible ? (isRec ? 'Recommended (rank 1)' : `Rank ${o.rank ?? '—'}`) : grey ? 'Not contracted (indicative)' : 'Infeasible: estimate shown with its reason' }));
    svg.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', lw + Math.max(2, x(o.exposure_aed)) + 8).attr('y', y + 13)
      .text(`${fmtAED(o.exposure_aed)} · ${o.wait_h == null ? '—' : fmtHours(o.wait_h)}${o.feasible ? '' : grey ? ' · not contracted' : ' · infeasible'}`);
  });
}
