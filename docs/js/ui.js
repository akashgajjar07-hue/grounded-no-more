/**
 * ui.js — DOM component helpers for GROUNDED NO MORE.
 * Every function returns a real Element styled by css/components.css. Views compose these;
 * they should not invent new visual styles. See docs/design/DESIGN_SYSTEM.md for the API.
 */
import { assetURL } from './data.js';
import { isSimple } from './lib/mode.js';
import { MOTION, reducedMotion as motionReduced, tooltipFade, flip } from './lib/motion.js';

// --------------------------------------------------------------------------- basics
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

/**
 * Hyperscript element builder.
 *   h('div', {class: 'card', onclick: fn, dataset: {ata: '32'}, 'aria-label': 'x'}, child, 'text', [more])
 * Strings become text nodes (safe). Pass {html: '...'} only for trusted markup.
 */
export function h(tag, attrs = {}, ...children) {
  const svgTags = new Set(['svg', 'use', 'path', 'g', 'circle', 'line', 'rect', 'text', 'polyline']);
  const el = svgTags.has(tag) ? document.createElementNS('http://www.w3.org/2000/svg', tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.setAttribute('class', v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === undefined || c === null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

// --------------------------------------------------------------------------- icons
let spritePromise = null;
/** Inline the icon sprite once so <use href="#i-name"> works from any page. */
export function ensureSprite() {
  if (!spritePromise) {
    spritePromise = fetch(assetURL('assets/svg/icons.svg'))
      .then((r) => r.text())
      .then((txt) => {
        const holder = document.createElement('div');
        holder.innerHTML = txt.replace(/<\?xml[^>]*>/, '').replace(/<!--[\s\S]*?-->/, '');
        const svg = holder.querySelector('svg');
        svg.setAttribute('aria-hidden', 'true');
        svg.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';
        document.body.prepend(svg);
      })
      .catch(() => {});
  }
  return spritePromise;
}

/** <svg class="icon"><use href="#i-name"/></svg>. Decorative unless `label` is given. */
export function icon(name, { cls = '', label } = {}) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', `icon ${cls}`.trim());
  svg.setAttribute('viewBox', '0 0 24 24');
  if (label) { svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', label); } else svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

// --------------------------------------------------------------------------- chips & pills
const PROV_HELP = {
  REAL: 'REAL — sourced from a public, cited dataset',
  DERIVED: 'DERIVED — computed in this repo from REAL / SIMULATED data',
  ASSUMED: 'ASSUMED — a planning assumption chosen by the author',
  SIMULATED: 'SIMULATED — produced by the synthetic generator',
};
/** Provenance chip: REAL (teal) / DERIVED (titanium) / ASSUMED (amber) / SIMULATED (copper). */
/**
 * Provenance chip. Wave A: SIMULATED is the default state of the whole site, announced once by the shell's
 * "Simulation" indicator, so a SIMULATED chip renders visually quiet (screen-reader text + title, no badge).
 * REAL / DERIVED / ASSUMED chips stay visible because they mark the items that are NOT simulated.
 * provChip(p, {force: true}) shows the SIMULATED badge anyway (the provenance legend on Data & Method).
 */
export function provChip(p = 'DERIVED', { force = false } = {}) {
  const key = String(p).toUpperCase();
  const quiet = key === 'SIMULATED' && !force;
  return h('span', { class: `chip chip-prov chip-prov--${key.toLowerCase()}${quiet ? ' chip-prov--quiet sr-only' : ''}`, title: PROV_HELP[key] || key, 'aria-label': `Provenance: ${PROV_HELP[key] || key}`, dataset: { prov: key } }, key);
}

/** The amber hatched "FIXTURE DATA" warning chip. */
export function fixtureChip() {
  return h('span', { class: 'chip chip-fixture', role: 'status', title: 'Layout fixtures loaded — not model output. Real exports replace these.' }, icon('alert'), 'Fixture data');
}

const PILL = {
  ok: ['check', 'OK'],
  review: ['clock', 'Review'],
  urgent: ['alert', 'Urgent'],
  unknown: ['info', 'Unknown'],
  info: ['info', 'Info'],
};
/** Status pill — icon + text, never colour alone. status: ok | review | urgent | unknown | info */
/**
 * Wave A: pills are sentence case (uppercase letter-spacing is reserved for small section labels). An all-caps pill
 * text from data ("HIGH · TOP OUTSTATION", "WATCH") becomes "High · top outstation"; codes stay as written
 * (BOM, AOG, PS1, D0, I125, OK).
 */
export function sentenceCase(t) {
  if (typeof t !== 'string' || /[a-z]/.test(t)) return t;
  const keep = (w) => (/\d/.test(w) || (w.length <= 3 && !['HUB', 'LOW', 'MET', 'TOP', 'NOT', 'AND', 'FOR', 'THE', 'OUT'].includes(w)));
  const out = t.replace(/[A-Z][A-Z0-9]*/g, (w) => (keep(w) ? w : w.toLowerCase()));
  return out.replace(/[a-z]/, (c) => c.toUpperCase());
}
export function pill(status = 'unknown', text) {
  const s = PILL[status] ? status : 'unknown';
  const [ic, label] = PILL[s];
  const cls = s === 'info' ? 'unknown' : s;
  const t = sentenceCase(text ?? label);
  // the full text rides along as a tooltip, so a pill clipped by a narrow container never loses its meaning
  return h('span', { class: `pill pill--${cls}`, title: typeof t === 'string' ? t : null }, icon(ic), h('span', { class: 'pill-text' }, t));
}

export const kbd = (k) => h('kbd', { class: 'kbd' }, k);

// --------------------------------------------------------------------------- layout
/** Page header: eyebrow "02 · PARTS INTELLIGENCE", H1, lede, right-aligned meta chips. */
export function pageHead({ num, eyebrow, title, lede, meta = [] }) {
  return h(
    'header',
    { class: 'page-head' },
    h('div', {}, h('div', { class: 'eyebrow' }, num ? `${num} · ${eyebrow || title}` : eyebrow || ''), h('h1', {}, title), lede ? h('p', { class: 'lede' }, lede) : null),
    meta.length ? h('div', { class: 'page-head-meta' }, meta) : null
  );
}

/** Section divider with title and hairline rule. */
export const sectionTitle = (title, extra) => h('div', { class: 'section-title' }, h('h2', {}, title), h('span', { class: 'rule' }), extra || null);

/**
 * Card. Options: {title, kicker, prov, actions, body, foot, cls, story, flush, bp}
 * `body` may be a Node, array of Nodes or a string.
 */
export function card({ title, kicker, prov, actions, body, foot, cls = '', story, flush = false, bp = false } = {}) {
  const head = title || kicker || prov || actions
    ? h('div', { class: 'card-head' }, h('div', {}, kicker ? h('div', { class: 'card-kicker' }, kicker) : null, title ? h('h3', { class: 'card-title' }, title) : null), h('div', { class: 'row' }, actions || null, prov ? provChip(prov) : null))
    : null;
  return h('section', { class: `card ${flush ? 'card--flush' : ''} ${bp ? 'card--bp' : ''} ${cls}`.trim(), dataset: story ? { story } : undefined }, head, body, foot ? h('div', { class: 'card-foot' }, foot) : null);
}

// --------------------------------------------------------------------------- KPI instrument tile
/** v2.1 brief: the verbatim scope line every headline KPI carries. */
export const SCOPE_LINE = 'across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part';
/**
 * KPI tile from a kpis.json row: {id,label,value,unit,baseline,baseline_label?,delta,better,provenance,ci,spark,target}
 * baseline_label names the comparison when it is not the P0 baseline ("vs P2", footer "P2 AED 37M").
 * opts.format(value) → string (defaults chosen by unit), opts.sparkline(el, values) to draw the spark.
 * opts.scale: {min, max} for the instrument ruler (optional).
 * opts.capital: capital deltas are NEUTRAL (titanium + arrow + "more/less capital"), never red/green.
 *   Default: auto — true when the KPI id or label mentions "capital". Pass false to force signed colouring.
 * opts.deltaTone: 'auto' (default) | 'neutral' | 'signed' — explicit override of the delta colour logic.
 * opts.scope (or k.scope): the scope line under the tile (p.kpi-scope[data-role=scope]). Defaults to SCOPE_LINE (v2.1);
 *   an empty / missing value falls back to the default, so no KPI renders without a scope line.
 */
export const isCapitalKpi = (k) => /capital/i.test(`${k?.id || ''} ${k?.label || ''}`);
export function kpiTile(k, { format, deltaFormat, sparkline, scale, hero = false, capital, deltaTone = 'auto', scope } = {}) {
  const fmt = format || ((v) => String(v));
  const dfmt = deltaFormat || fmt;
  const isCap = capital ?? isCapitalKpi(k);
  const neutral = deltaTone === 'neutral' || (deltaTone === 'auto' && isCap);
  const good = k.delta === 0 ? 'flat' : neutral ? 'neutral' : (k.better === 'lower' ? k.delta < 0 : k.delta > 0) ? 'good' : 'bad';
  const [num, unit] = splitUnit(fmt(k.value));
  // "baseline" means P0 site-wide: a tile compared with anything else names it (k.baseline_label, e.g. 'P2')
  const refName = k.baseline_label || 'baseline';
  const delta = h(
    'span',
    { class: `kpi-delta is-${good}` },
    icon(k.delta < 0 ? 'arrow-down' : k.delta > 0 ? 'arrow-up' : 'minus'),
    `${k.delta > 0 ? '+' : k.delta < 0 ? '−' : ''}${dfmt(Math.abs(k.delta))}`,
    isCap && k.delta ? h('span', { class: 'kpi-delta-word' }, k.delta > 0 ? ' more capital' : ' less capital') : null,
    h('span', { class: 'kpi-delta-ref' }, ` vs ${refName}`),
    h('span', { class: 'sr-only' }, good === 'good' ? ' (improvement)' : good === 'bad' ? ' (worse)' : '')
  );
  const spark = h('div', { class: 'kpi-spark', 'aria-hidden': 'true' });
  let ruler = null;
  if (scale) {
    const pct = (v) => `${Math.max(0, Math.min(100, ((v - scale.min) / (scale.max - scale.min)) * 100))}%`;
    ruler = h(
      'div',
      { class: 'kpi-scale', 'aria-hidden': 'true' },
      h('div', { class: 'kpi-scale-fill', style: { width: pct(k.value) } }),
      h('div', { class: 'kpi-scale-marker', style: { left: pct(k.value) } }),
      k.target != null ? h('div', { class: 'kpi-scale-target', style: { left: pct(k.target) }, title: `Target ${fmt(k.target)}` }) : null
    );
  }
  const ci = Array.isArray(k.ci) ? `95% CI ${compactRange(fmt(k.ci[0]), fmt(k.ci[1]))}` : 'No interval';
  const tile = h(
    'article',
    { class: `card kpi ${hero ? 'kpi--hero' : ''}`, 'aria-label': `${k.label}: ${fmt(k.value)}` },
    h('div', { class: 'kpi-top' }, h('div', { class: 'kpi-label' }, k.label), provChip(k.provenance)),
    h('div', { class: 'kpi-value' }, num, unit ? h('span', { class: 'kpi-unit' }, unit) : null),
    ruler,
    delta,
    spark,
    h('div', { class: 'kpi-foot' }, h('span', {}, ci), h('span', {}, `${k.baseline_label || 'Baseline'} ${fmt(k.baseline)}`)),
    // v2.1: every KPI carries its scope line (opts.scope or k.scope overrides the text; it can never be removed)
    h('p', { class: 'kpi-scope', dataset: { role: 'scope' } }, (typeof scope === 'string' && scope.trim()) || (typeof k.scope === 'string' && k.scope.trim()) || SCOPE_LINE)
  );
  if (sparkline && Array.isArray(k.spark)) requestAnimationFrame(() => sparkline(spark, k.spark, { better: k.better, color: isCap ? '#B9C8D6' : undefined }));
  return tile;
}
/** "AED 43.9M" + "AED 45.4M" → "AED 43.9–45.4M"; "196 h" + "263 h" → "196–263 h" */
function compactRange(a, b) {
  const [na, ua] = splitUnit(a), [nb, ub] = splitUnit(b);
  if (ua !== ub) return `${a} – ${b}`;
  const sa = na.match(/^([\d.,]+)([kMB]?)$/), sb = nb.match(/^([\d.,]+)([kMB]?)$/);
  const core = sa && sb && sa[2] === sb[2] ? `${sa[1]}–${sb[1]}${sb[2]}` : `${na}–${nb}`;
  if (!ua) return core;
  return /^[A-Z]{3}$/.test(ua) ? `${ua} ${core}` : `${core}${ua === '%' ? '' : ' '}${ua}`;
}
/** "AED 4.8M" → ["4.8M", "AED"]; "98.7%" → ["98.7", "%"]; "124 h" → ["124", "h"] */
function splitUnit(s) {
  const str = String(s);
  let m = str.match(/^([A-Z]{3})\s(.+)$/);
  if (m) return [m[2], m[1]];
  m = str.match(/^(.+?)\s?(%|h|d|pts)$/);
  if (m) return [m[1], m[2]];
  return [str, ''];
}

// --------------------------------------------------------------------------- data table
/**
 * Dense sortable data table.
 *   dataTable({columns: [{key, label, num, mono, sortable=true, format(v,row), render(row)→Node, short?}],
 *              rows, sort: {key, dir:'desc'}, onRowClick(row), selected, rowKey, maxHeight, dense, caption, bare,
 *              mobileColumns: ['pn', 'risk_score', 'stock_total'], stack = true, stickyFirst = false})
 * Mobile (see DESIGN_SYSTEM §2):
 *  - mobileColumns: priority list of column keys. Below 768 px the table shows only these columns.
 *  - At ≤ 480 px (when stack !== false) each row becomes a two-line stacked card: mobileColumns[0] on line 1
 *    (mono for mono columns), mobileColumns[1] right-aligned in a metric pill, the rest on line 2 in 12 px faint
 *    "Label value" pairs. A compact sort control replaces the header. `short` overrides a column label there.
 *  - stickyFirst: the first column stays pinned (position: sticky; left: 0) with a hairline shadow while the
 *    table scrolls horizontally.
 * Returns the wrapper element; `.update(rows)` re-renders the body, `.setSelected(key)` moves the selection.
 */
export function dataTable({ columns, rows, sort, onRowClick, rowKey, selected, maxHeight, dense = false, caption, bare = false, mobileColumns, stack = true, stickyFirst = false }) {
  let state = { rows: rows || [], sort: sort || null, selected };
  const prio = Array.isArray(mobileColumns) && mobileColumns.length ? mobileColumns.filter((k) => columns.some((c) => c.key === k)) : null;
  const hiddenSm = (c) => (prio && !prio.includes(c.key) ? 'is-mobile-hidden' : '');
  const table = h('table', { class: `data-table ${dense ? 'data-table--dense' : ''} ${stickyFirst ? 'data-table--sticky' : ''}`.replace(/\s+/g, ' ').trim() });
  if (caption) table.append(h('caption', { class: 'sr-only' }, caption));
  const thead = h('thead');
  const tbody = h('tbody');
  table.append(thead, tbody);
  const useStack = !!(prio && stack !== false);
  const stackEl = useStack ? h('div', { class: 'data-table-stack' }) : null;
  const wrap = h('div', { class: `table-wrap ${bare ? 'table-wrap--bare' : ''} ${useStack ? 'has-stack' : ''}`.replace(/\s+/g, ' ').trim(), style: maxHeight ? { maxHeight: `${maxHeight}px` } : undefined, tabindex: '0', role: 'region', 'aria-label': caption || 'Data table' }, table, stackEl);
  const mq = useStack ? matchMedia('(max-width: 480px)') : null;
  // an empty string prints as "—" (never a bare label with no value, e.g. a licence row without a version)
  const cell = (c, r) => { const v = c.render ? c.render(r) : c.format ? c.format(r[c.key], r) : r[c.key]; return v === '' ? '—' : v; };

  function renderHead() {
    thead.replaceChildren(
      h(
        'tr',
        {},
        columns.map((c) => {
          const sorted = state.sort?.key === c.key;
          const th = h('th', { scope: 'col', class: `${c.num ? 'is-num' : ''} ${hiddenSm(c)}`.trim(), 'aria-sort': sorted ? (state.sort.dir === 'asc' ? 'ascending' : 'descending') : null });
          if (c.sortable === false) th.append(c.label);
          else th.append(h('button', { class: 'th-sort', type: 'button', onclick: () => toggleSort(c.key) }, c.label, icon('sort')));
          return th;
        })
      )
    );
  }
  function toggleSort(key, dir) {
    const d = dir || (state.sort?.key === key && state.sort.dir === 'desc' ? 'asc' : 'desc');
    state.sort = { key, dir: d };
    renderHead();
    renderBody();
  }
  function sorted() {
    const data = state.rows.slice();
    if (state.sort) {
      const { key, dir } = state.sort;
      const m = dir === 'asc' ? 1 : -1;
      data.sort((a, b) => (a[key] > b[key] ? m : a[key] < b[key] ? -m : 0));
    }
    return data;
  }
  function rowAttrs(r) {
    return {
      'aria-selected': rowKey && state.selected != null ? String(r[rowKey] === state.selected) : null,
      'data-key': rowKey ? String(r[rowKey]) : null,
      tabindex: onRowClick ? '0' : null,
      style: onRowClick ? { cursor: 'pointer' } : undefined,
      onclick: onRowClick ? () => onRowClick(r) : null,
      onkeydown: onRowClick ? (e) => { if (e.key === 'Enter') onRowClick(r); } : null,
    };
  }
  /** Line-1 metric: a value in a labelled capsule, or a status pill on its own (never a pill inside a capsule). */
  function metricSlot(c, v) {
    if (v instanceof Element && v.classList.contains('pill')) {
      if (!v.title) v.title = `${c.short || c.label}: ${v.textContent}`;
      return h('div', { class: 'dts-metric dts-metric--pill', 'aria-label': `${c.short || c.label}: ${v.textContent}` }, v);
    }
    return h('div', { class: 'dts-metric' }, h('span', { class: 'dts-metric-label' }, c.short || c.label), v ?? '—');
  }
  function renderStack(data) {
    if (!stackEl || !mq.matches) { stackEl?.replaceChildren(); return; }
    const byKey = Object.fromEntries(columns.map((c) => [c.key, c]));
    const [k1, k2, ...rest] = prio;
    const c1 = byKey[k1], c2 = k2 ? byKey[k2] : null;
    const sortable = columns.filter((c) => c.sortable !== false);
    const sel = h('select', { 'aria-label': 'Sort rows by', onchange: (e) => toggleSort(e.target.value, state.sort?.dir || 'desc') },
      // an unsorted (pre-ordered) table says so, instead of showing the first column as if it were the sort key (F7)
      state.sort ? null : h('option', { value: '', selected: true, disabled: true }, 'As listed'),
      sortable.map((c) => h('option', { value: c.key, selected: state.sort?.key === c.key ? true : null }, c.short || c.label)));
    const dirBtn = h('button', { class: 'btn btn--sm btn--icon', type: 'button', 'aria-label': state.sort?.dir === 'asc' ? 'Sort ascending (switch to descending)' : 'Sort descending (switch to ascending)', onclick: () => toggleSort(state.sort?.key || sortable[0]?.key, state.sort?.dir === 'asc' ? 'desc' : 'asc') }, icon(state.sort?.dir === 'asc' ? 'arrow-up' : 'arrow-down'));
    const list = h('ul', { class: 'dts-list', 'aria-label': caption || 'Rows' }, data.map((r) => {
      const a = rowAttrs(r);
      return h('li', { class: 'dts-row', 'data-key': a['data-key'], role: onRowClick ? 'button' : null, tabindex: a.tabindex, 'aria-selected': a['aria-selected'], onclick: a.onclick, onkeydown: a.onkeydown },
        h('div', { class: `dts-primary ${c1.mono ? '' : 'is-text'}`.trim() }, cell(c1, r) ?? '—'),
        c2 ? metricSlot(c2, cell(c2, r)) : h('span'),
        rest.length ? h('div', { class: 'dts-secondary' }, rest.map((k) => byKey[k]).map((c) => h('span', {}, h('span', {}, `${c.short || c.label} `, h('b', {}, cell(c, r) ?? '—'))))) : null);
    }));
    stackEl.replaceChildren(sortable.length ? h('div', { class: 'dts-sort' }, h('label', {}, 'Sort'), sel, dirBtn) : null, list);
  }
  function renderBody() {
    const data = sorted();
    tbody.replaceChildren(
      ...data.map((r) =>
        h('tr', rowAttrs(r),
          columns.map((c) => h('td', { class: `${c.num ? 'is-num' : ''} ${c.mono ? 'mono' : ''} ${hiddenSm(c)}`.replace(/\s+/g, ' ').trim() }, cell(c, r) ?? '—'))
        )
      )
    );
    renderStack(data);
  }
  renderHead();
  renderBody();
  if (mq) {
    const onMq = () => { if (!wrap.isConnected && wrap.dataset.mounted) { mq.removeEventListener('change', onMq); return; } renderStack(sorted()); };
    mq.addEventListener('change', onMq);
    requestAnimationFrame(() => { if (wrap.isConnected) wrap.dataset.mounted = '1'; });
  }
  wrap.update = (rows2) => { state.rows = rows2; renderBody(); };
  wrap.setSelected = (key) => { state.selected = key; renderBody(); };
  return wrap;
}

// --------------------------------------------------------------------------- controls
/** Tabs (ARIA tablist). tabs: [{id, label, count}], onChange(id). Arrow keys move focus. */
export function tabs({ tabs: items, value, onChange, label = 'Sections' }) {
  const list = h('div', { class: 'tabs', role: 'tablist', 'aria-label': label });
  const set = (id, focus) => {
    value = id;
    [...list.children].forEach((b) => { const on = b.dataset.id === id; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
    onChange?.(id);
  };
  items.forEach((t) => list.append(h('button', { class: 'tab', role: 'tab', type: 'button', dataset: { id: t.id }, 'aria-selected': String(t.id === value), tabindex: t.id === value ? '0' : '-1', onclick: () => set(t.id) }, t.label, t.count != null ? h('span', { class: 'chip' }, String(t.count)) : null)));
  list.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    const ids = items.map((t) => t.id);
    const i = ids.indexOf(value);
    set(ids[(i + (e.key === 'ArrowRight' ? 1 : ids.length - 1)) % ids.length], true);
  });
  return list;
}

/** Segmented control (radio group). options: [{value, label}] */
export function segmented({ options, value, onChange, label = 'Options' }) {
  const g = h('div', { class: 'seg', role: 'radiogroup', 'aria-label': label });
  const set = (v) => { value = v; g.querySelectorAll('[role="radio"]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === String(v)))); onChange?.(v); };
  options.forEach((o) => g.append(h('button', { type: 'button', role: 'radio', dataset: { value: o.value }, 'aria-checked': String(o.value === value), onclick: () => set(o.value) }, o.label)));
  slidingThumb(g);
  return g;
}

/**
 * v2.1 motion: give a segmented control (.seg with [aria-checked] / [aria-pressed] buttons) a thumb that slides to the
 * selected option (transform only, 250 ms standard). Idempotent; follows attribute changes and resizes.
 */
export function slidingThumb(g) {
  if (!g || g.querySelector(':scope > .seg-thumb')) return g;
  const thumb = h('span', { class: 'seg-thumb no-anim', 'aria-hidden': 'true' });
  g.prepend(thumb);
  g.classList.add('has-thumb');
  const sync = () => {
    const on = g.querySelector(':scope > button[aria-checked="true"], :scope > button[aria-pressed="true"]');
    if (!on || !g.isConnected) { thumb.style.opacity = on ? '' : '0'; return; }
    thumb.style.opacity = '';
    thumb.style.width = `${on.offsetWidth}px`;
    thumb.style.transform = `translateX(${on.offsetLeft}px)`;
  };
  new MutationObserver(() => requestAnimationFrame(sync)).observe(g, { subtree: true, attributes: true, attributeFilter: ['aria-checked', 'aria-pressed'] });
  if (typeof ResizeObserver === 'function') new ResizeObserver(() => { thumb.classList.add('no-anim'); sync(); requestAnimationFrame(() => thumb.classList.remove('no-anim')); }).observe(g);
  let tries = 0;
  const first = () => { if (g.isConnected) { sync(); requestAnimationFrame(() => thumb.classList.remove('no-anim')); } else if (tries++ < 120) requestAnimationFrame(first); };
  requestAnimationFrame(first);
  return g;
}

/**
 * Keep a range input's aria-valuetext in sync with a formatter, so screen readers announce "AED 41.9M" rather
 * than "41850000" (F5). Sets it now and on every input/change event; returns update() for programmatic changes.
 *   const update = bindValueText(rangeInput, (v) => fmtAED(v)); input.value = 3; update();
 */
/** Set a range input's --pct (the filled part of the track) from its value, min and max. */
export function fillPct(input) {
  const min = +input.min || 0, max = input.max === '' ? 100 : +input.max, v = +input.value;
  input.style.setProperty('--pct', `${max > min ? Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100)) : 0}%`);
}
export function bindValueText(input, fmt = String) {
  const update = () => {
    try { input.setAttribute('aria-valuetext', String(fmt(+input.value))); } catch { input.removeAttribute('aria-valuetext'); }
    fillPct(input); // wave 5 (F1): the teal track fill always follows the thumb
  };
  update();
  input.addEventListener('input', update);
  input.addEventListener('change', update);
  return update;
}

/**
 * Labelled range slider with live <output> and min/max scale.
 * slider({label, min, max, step, value, format, valueText, onInput, id}) → field element with
 *   .input (the <input type=range>) and .setValue(v) (moves thumb, output and aria-valuetext; does not call onInput).
 * format(v) → the visible output / scale text. valueText(v) → aria-valuetext (defaults to format): always set (F5).
 */
export function slider({ label, min, max, step = 1, value, format = String, valueText, onInput, id }) {
  const sid = id || `sl-${Math.random().toString(36).slice(2, 8)}`;
  const out = h('output', { for: sid, 'aria-hidden': 'true' }, format(value));
  // F4 (wave 4): the accessible name is the label text only ("Capital budget"); the live value is in aria-valuetext
  const input = h('input', { class: 'slider', type: 'range', id: sid, min, max, step, value, 'aria-labelledby': `${sid}-l` });
  const pct = () => input.style.setProperty('--pct', `${max > min ? ((input.value - min) / (max - min)) * 100 : 0}%`);
  pct();
  const vt = bindValueText(input, valueText || format);
  input.addEventListener('input', () => { pct(); out.textContent = format(+input.value); onInput?.(+input.value); });
  const field = h('div', { class: 'field' }, h('div', { class: 'field-label' }, h('label', { for: sid, id: `${sid}-l` }, label), out), input, h('div', { class: 'slider-scale', 'aria-hidden': 'true' }, h('span', {}, format(min)), h('span', {}, format(max))));
  field.input = input;
  field.setValue = (v) => { input.value = v; pct(); out.textContent = format(+input.value); vt(); };
  return field;
}

// --------------------------------------------------------------------------- overlays
/*
 * Overlay registry. Every drawer / modal registers itself while open so the router can close them all
 * (releasing focus traps and scroll locks) before it renders another view: closeAllOverlays().
 * Story mode is NOT registered: it drives navigation itself and must survive route changes.
 */
const openOverlays = new Set();
let scrollLocks = 0;
function lockScroll() { if (scrollLocks++ === 0) document.documentElement.classList.add('has-overlay'); }
function unlockScroll() { scrollLocks = Math.max(0, scrollLocks - 1); if (!scrollLocks) document.documentElement.classList.remove('has-overlay'); }

/**
 * Register any custom overlay so the router closes it on navigation.
 *   const off = registerOverlay({ close: (opts) => …, persistOnParams: false });  // call off() when it closes itself
 * close(opts) receives {reason: 'route' | 'params' | 'user', immediate: true}.
 */
export function registerOverlay(entry) { openOverlays.add(entry); return () => openOverlays.delete(entry); }

/**
 * Close every registered overlay (drawers, modals, custom), hide the tooltip and release scroll locks.
 * opts.reason: 'route' (default; everything closes) | 'params' (overlays with persistOnParams stay open).
 * Returns the number of overlays closed.
 */
export function closeAllOverlays({ reason = 'route' } = {}) {
  let n = 0;
  [...openOverlays].forEach((o) => {
    if (reason === 'params' && o.persistOnParams) return;
    openOverlays.delete(o);
    try { o.close({ reason, immediate: true }); } catch (e) { console.warn('overlay close failed', e); }
    n++;
  });
  tooltip.hide();
  // belt and braces: nothing may leave a dimmed, click-blocking layer behind
  document.querySelectorAll('body > .scrim, body > .drawer, body > .modal').forEach((el) => {
    if ([...openOverlays].some((o) => o.el === el || o.scrim === el)) return;
    el.remove();
  });
  if (!openOverlays.size) { scrollLocks = 0; document.documentElement.classList.remove('has-overlay'); }
  return n;
}
/** Number of overlays currently open (tests / debugging). */
export const openOverlayCount = () => openOverlays.size;

function trapFocus(container, e) {
  if (e.key !== 'Tab') return;
  const f = container.querySelectorAll('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])');
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

/**
 * Right-hand drawer. drawer({title, kicker, body, foot, onClose, persistOnParams, returnFocus}) → {open(), close(), el, body, isOpen}
 * returnFocus: element or () => element that receives focus on close when nothing had focus before (deep links).
 * Closes on Esc, scrim click and the close button; returns focus to the opener; locks page scroll while open.
 * The router closes it on every route change (onClose receives {reason: 'route'}); set persistOnParams: true to keep
 * it open across same-route param updates that the view handles itself (see `onParams` in app.js).
 */
export function drawer({ title, kicker, body, foot, onClose, persistOnParams = false, returnFocus } = {}) {
  const scrim = h('div', { class: 'scrim' });
  const bodyEl = h('div', { class: 'drawer-body' }, body);
  const el = h(
    'aside',
    { class: 'drawer', role: 'dialog', 'aria-modal': 'true', 'aria-label': title || 'Details' },
    h('div', { class: 'drawer-head' }, h('div', {}, kicker ? h('div', { class: 'card-kicker' }, kicker) : null, h('h2', { class: 't-20' }, title || '')), h('button', { class: 'btn btn--ghost btn--icon', type: 'button', 'aria-label': 'Close', onclick: () => api.close() }, icon('close'))),
    bodyEl,
    foot ? h('div', { class: 'drawer-foot' }, foot) : null
  );
  let lastFocus = null;
  const onKey = (e) => { if (e.key === 'Escape') api.close(); trapFocus(el, e); };
  const entry = { el, scrim, persistOnParams, close: (o) => api.close(o) };
  const api = {
    el, body: bodyEl, isOpen: false,
    open() {
      if (api.isOpen) return api;
      api.isOpen = true;
      lastFocus = document.activeElement;
      document.body.append(scrim, el);
      requestAnimationFrame(() => { if (!api.isOpen) return; scrim.classList.add('is-open'); el.classList.add('is-open'); el.querySelector('button')?.focus(); });
      scrim.onclick = () => api.close();
      document.addEventListener('keydown', onKey);
      openOverlays.add(entry);
      lockScroll();
      return api;
    },
    /** close({reason, immediate}) — idempotent. immediate removes the nodes synchronously (router path). */
    close({ reason = 'user', immediate = false } = {}) {
      if (!api.isOpen) return;
      api.isOpen = false;
      openOverlays.delete(entry);
      unlockScroll();
      scrim.classList.remove('is-open'); el.classList.remove('is-open');
      document.removeEventListener('keydown', onKey);
      if (immediate) { scrim.remove(); el.remove(); } else setTimeout(() => { scrim.remove(); el.remove(); }, (motionReduced() ? 0 : MOTION.base) + 70);
      if (reason === 'user') {
        // returnFocus(): where focus goes when there was no opener (a deep-linked drawer opened on load)
        const back = lastFocus?.isConnected && lastFocus !== document.body ? lastFocus : (typeof returnFocus === 'function' ? returnFocus() : returnFocus);
        back?.focus?.({ preventScroll: true });
      }
      onClose?.({ reason });
    },
  };
  return api;
}

/** Centred modal dialog. modal({title, body}) → {open(), close(), isOpen}. Registered like drawer(). */
export function modal({ title, body, persistOnParams = false, returnFocus } = {}) {
  const scrim = h('div', { class: 'scrim' });
  const cardEl = h('div', { class: 'modal-card', role: 'dialog', 'aria-modal': 'true', 'aria-label': title }, h('div', { class: 'row-between mb-3' }, h('h2', { class: 't-20' }, title), h('button', { class: 'btn btn--ghost btn--icon', type: 'button', 'aria-label': 'Close', onclick: () => api.close() }, icon('close'))), body);
  const wrap = h('div', { class: 'modal' }, cardEl);
  let lastFocus = null;
  const onKey = (e) => { if (e.key === 'Escape') api.close(); trapFocus(cardEl, e); };
  const entry = { el: wrap, scrim, persistOnParams, close: (o) => api.close(o) };
  const api = {
    isOpen: false,
    open() {
      if (api.isOpen) return api;
      lastFocus = document.activeElement; document.body.append(scrim, wrap);
      requestAnimationFrame(() => scrim.classList.add('is-open'));
      wrap.onclick = (e) => { if (e.target === wrap) api.close(); };
      document.addEventListener('keydown', onKey); cardEl.querySelector('button').focus();
      api.isOpen = true; openOverlays.add(entry); lockScroll();
      return api;
    },
    close({ reason = 'user' } = {}) {
      if (!api.isOpen) return;
      api.isOpen = false; openOverlays.delete(entry); unlockScroll();
      scrim.remove(); wrap.remove(); document.removeEventListener('keydown', onKey);
      if (reason === 'user') {
        // returnFocus(): where focus goes when there was no opener (a deep-linked drawer opened on load)
        const back = lastFocus?.isConnected && lastFocus !== document.body ? lastFocus : (typeof returnFocus === 'function' ? returnFocus() : returnFocus);
        back?.focus?.({ preventScroll: true });
      }
    },
  };
  return api;
}

// --------------------------------------------------------------------------- tooltip (card style, singleton)
let tipEl = null;
/**
 * Shared tooltip. tooltip.show(event, {title, rows: [[label, value], ...]} | html string); tooltip.hide()
 */
export const tooltip = {
  show(evt, content) {
    if (!tipEl) { tipEl = h('div', { class: 'tooltip', role: 'tooltip' }); document.body.append(tipEl); }
    if (typeof content === 'string') tipEl.innerHTML = content;
    else tipEl.replaceChildren(content.title ? h('div', { class: 'tooltip-title' }, content.title) : '', ...(content.rows || []).map(([k, v]) => h('div', { class: 'tooltip-row' }, h('span', {}, k), h('b', {}, v))), content.note ? h('div', { class: 'mt-1 faint' }, content.note) : '');
    tooltipFade.show(tipEl);
    this.move(evt);
  },
  /** v2.1: cursor tracking via motion.js tooltipFade.follow (one transform write per frame, size measured once). */
  move(evt) {
    if (!tipEl) return;
    tooltipFade.follow(tipEl, evt || {});
  },
  hide() { tooltipFade.hide(tipEl); },
};

// --------------------------------------------------------------------------- inline SVG illustrations
const svgCache = new Map();
let svgSeq = 0;
/**
 * Fetch an illustration from docs/assets/svg/ and inline it (so hotspots/labels are scriptable).
 * Ids inside <defs> that start with "bp-" are made unique per instance; hotspot ids (ata-XX) are kept.
 * @param {string} name e.g. 'blueprint-aircraft-top.svg'
 */
export async function inlineSVG(name) {
  if (!svgCache.has(name)) svgCache.set(name, fetch(assetURL(`assets/svg/${name}`)).then((r) => r.text()));
  const txt = await svgCache.get(name);
  const p = `i${++svgSeq}-`;
  const fixed = txt
    .replace(/<\?xml[^>]*>/, '')
    .replace(/id="(bp-[\w-]+)"/g, `id="${p}$1"`)
    .replace(/url\(#(bp-[\w-]+)\)/g, `url(#${p}$1)`)
    .replace(/aria-labelledby="bp-title bp-desc"/, `aria-labelledby="${p}bp-title ${p}bp-desc"`);
  const holder = document.createElement('div');
  holder.innerHTML = fixed;
  const svg = holder.querySelector('svg');
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  return svg;
}

/**
 * Mount the plan-view aircraft with interactive ATA hotspots.
 *   blueprintAircraft(host, {active: '32', onSelect(ata), risk: {32: 0.9}, compactBelow: 640})
 * Below `compactBelow` px (default 1000) the drawing crops to the airframe and shows numbered badges instead of
 * callout labels (labels move to an HTML legend the caller renders).
 * Returns {svg, setActive(ata), destroy()}.
 */
export async function blueprintAircraft(host, { active, onSelect, compactBelow = 1000, label = 'Aircraft systems', fleet = 'narrowbody' } = {}) {
  // wave A: original plan-view archetypes (aircraft-narrowbody.svg / aircraft-widebody.svg); same hotspot API
  const svg = await inlineSVG(fleet === 'widebody' ? 'aircraft-widebody.svg' : 'aircraft-narrowbody.svg');
  host.classList.add('bp-figure');
  host.replaceChildren(svg);
  const full = svg.getAttribute('viewBox');
  const compact = svg.dataset.compactViewbox;
  const spots = [...svg.querySelectorAll('.ata-hotspot')];
  svg.setAttribute('aria-label', label);
  const setActive = (ata) => spots.forEach((g) => { const on = g.dataset.ata === String(ata); g.classList.toggle('is-active', on); g.setAttribute('aria-pressed', String(on)); });
  spots.forEach((g) => {
    const fire = () => { setActive(g.dataset.ata); onSelect?.(g.dataset.ata); };
    g.addEventListener('click', fire);
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fire(); } });
  });
  if (active) setActive(active);
  const ro = new ResizeObserver(([entry]) => {
    const small = entry.contentRect.width < compactBelow;
    svg.classList.toggle('bp-compact', small);
    svg.setAttribute('viewBox', small && compact ? compact : full);
  });
  ro.observe(host);
  return { svg, setActive, destroy: () => ro.disconnect() };
}

/** Fill the label slots of an exploded-<ata>.svg: labels = [{slot, pn, desc}] */
export function fillExploded(svg, labels = []) {
  labels.forEach(({ slot, pn, desc }) => {
    const g = svg.querySelector(`.bp-label[data-slot="${slot}"]`);
    if (!g) return;
    if (pn) g.querySelector('[data-field="pn"]').textContent = pn;
    if (desc) g.querySelector('[data-field="desc"]').textContent = String(desc).toUpperCase();
  });
}

/** Fill rotable-lifecycle.svg count slots: counts {STATE: n}, flows [{from,to,count}] */
export function fillLifecycle(svg, { counts = {}, flows = [] } = {}) {
  Object.entries(counts).forEach(([k, v]) => svg.querySelectorAll(`[data-count="${k}"]`).forEach((t) => (t.textContent = Number(v).toLocaleString('en-GB'))));
  flows.forEach((f) => svg.querySelectorAll(`[data-flow="${f.from}>${f.to}"]`).forEach((t) => (t.textContent = Number(f.count).toLocaleString('en-GB'))));
}

// --------------------------------------------------------------------------- story mode
/**
 * Story-mode overlay: spotlight + step card. steps: [{route, selector, mobile_selector?, title, body}]
 * Targets are framed just under the sticky top bar (+16 px). At ≤ 480 px the card is a bottom sheet that collapses to
 * a peek strip (~25% of the viewport) when it would cover the target; the grab handle toggles it. `mobile_selector`
 * (optional) names a narrower element to spotlight on phones.
 * navigate(route) must return a Promise that resolves once the view has rendered.
 */
let activeStory = null;
/**
 * Where to put a floating card of size cw × ch next to target rect r inside a vw × vh viewport.
 * Tries right, left, below and above (then the four corners), each clamped to a 16 px margin, and returns the
 * candidate with the least overlap with the target (inflated by 16 px clearance); ties keep that order.
 * `top` is the smallest allowed card top (story mode passes the sticky top-bar height + 16 so the card never sits under
 * the bar). Exported for tests and for any other anchored popover. → {left, top, side, overlap}
 */
export function storyCardPosition(r, { cw, ch, vw, vh, gap = 24, margin = 16, clearance = 16, top: minTop = margin }) {
  const clampX = (x) => Math.max(margin, Math.min(x, vw - cw - margin));
  const clampY = (y) => Math.max(minTop, Math.min(y, vh - ch - margin));
  const cands = [
    { side: 'right', left: r.right + gap, top: clampY(r.top) },
    { side: 'left', left: r.left - gap - cw, top: clampY(r.top) },
    { side: 'below', left: clampX(r.left), top: r.bottom + gap },
    { side: 'above', left: clampX(r.left), top: r.top - gap - ch },
    { side: 'bottom-right', left: vw - cw - margin, top: vh - ch - margin },
    { side: 'top-right', left: vw - cw - margin, top: minTop },
    { side: 'bottom-left', left: margin, top: vh - ch - margin },
    { side: 'top-left', left: margin, top: minTop },
  ].map((c) => ({ ...c, left: clampX(c.left), top: clampY(c.top) }));
  const t = { l: r.left - clearance, t: r.top - clearance, r: r.right + clearance, b: r.bottom + clearance };
  let best = null;
  cands.forEach((c, i) => {
    const ox = Math.max(0, Math.min(c.left + cw, t.r) - Math.max(c.left, t.l));
    const oy = Math.max(0, Math.min(c.top + ch, t.b) - Math.max(c.top, t.t));
    const overlap = ox * oy;
    if (!best || overlap < best.overlap - 1 || (Math.abs(overlap - best.overlap) <= 1 && i < best.i)) best = { ...c, overlap, i };
  });
  return best;
}
/**
 * v2.1 tour engine.
 *  - Text: Simple mode shows step.title_simple / step.body_simple (plain English), Expert mode step.title / step.body;
 *    a mode change while the tour is open swaps the text and re-finds the target.
 *  - Play auto-advances every MOTION.tourStep (7 s; opts.stepMs or window.__gnmTourStepMs override for tests). One rAF
 *    loop drives the timer AND the current segment's progress fill (transform: scaleX). The clock only runs once the
 *    step's target is framed. Pause freezes both. Next/Back work while playing (the clock restarts on the new step).
 *    At the last step the bar fills, playback stops and the button resets to Play (Play again restarts at step 1).
 *    Repeated play() never creates a second loop. Esc / Skip / exit() cancel the loop and every pending timer.
 *  - The spotlight moves with a 450 ms transform-only FLIP and the target is scrolled into view; reduced motion →
 *    instant moves (the tour still auto-advances; the bar steps once per second).
 *  - While open, window.__gnmStory = api (tests): api.play(), api.pause(), api.state() →
 *    {index, playing, elapsed, stepMs, loops, timers}.
 */
export function storyMode({ steps, navigate, onExit, stepMs }) {
  const STEP_MS = () => +(stepMs || window.__gnmTourStepMs || MOTION.tourStep);
  let i = 0;
  let seq = 0; // guards against overlapping go() calls (fast ←/→)
  let target = null;
  const pending = new Set(); // every setTimeout the tour owns (cleared on exit)
  const sleep = (ms) => new Promise((r) => { const id = setTimeout(() => { pending.delete(id); r(); }, ms); pending.add(id); });
  const root = h('div', { class: 'story', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Guided tour' });
  const spot = h('div', { class: 'story-spot' });
  const stepEl = h('div', { class: 'story-step', 'aria-live': 'polite' });
  const titleEl = h('h3', {});
  const bodyEl = h('p', {});
  const fills = steps.map(() => h('i', { class: 'story-fill' }));
  const prog = h('div', { class: 'story-progress', 'aria-hidden': 'true' }, fills.map((f) => h('span', {}, f)));
  const back = h('button', { class: 'btn btn--ghost btn--sm', type: 'button', onclick: () => go(i - 1) }, 'Back');
  const next = h('button', { class: 'btn btn--primary btn--sm', type: 'button', onclick: () => (i < steps.length - 1 ? go(i + 1) : exit()) }, 'Next');
  let peekUser = null; // null = automatic, true/false = the reader toggled the sheet on this step
  const grab = h('button', { class: 'story-grab', type: 'button', 'aria-expanded': 'true', 'aria-label': 'Collapse the tour card', onclick: () => { setPeek(!cardEl.classList.contains('is-peek')); peekUser = cardEl.classList.contains('is-peek'); } }, h('span', { 'aria-hidden': 'true' }));

  // ---------------------------------------------------------------- playback clock (one rAF loop)
  let playing = false, elapsed = 0, lastT = 0, loop = 0, ready = false;
  const playBtn = h('button', { class: 'btn btn--ghost btn--sm story-play', type: 'button', 'aria-pressed': 'false', 'aria-label': 'Play the tour automatically', onclick: () => setPlaying(!playing) }, icon('play'), h('span', {}, 'Play'));
  function paintFill() {
    const ms = STEP_MS();
    let p = Math.max(0, Math.min(1, elapsed / ms));
    if (motionReduced() && p < 1) p = Math.floor(elapsed / 1000) * 1000 / ms;
    prog.querySelectorAll('span').forEach((sp, j) => { sp.classList.toggle('is-done', j < i); sp.classList.toggle('is-current', j === i); });
    fills.forEach((f, j) => { f.style.transform = `scaleX(${j < i ? 1 : j === i ? p : 0})`; });
  }
  function frameLoop(t) {
    loop = 0;
    if (!playing) return;
    if (ready) { if (lastT) elapsed += Math.min(t - lastT, 250); lastT = t; } else lastT = 0;
    paintFill();
    if (ready && elapsed >= STEP_MS()) {
      if (i < steps.length - 1) go(i + 1);
      else { elapsed = STEP_MS(); setPlaying(false); return; }
    }
    loop = requestAnimationFrame(frameLoop);
  }
  function setPlaying(on) {
    on = !!on;
    if (on && i === steps.length - 1 && elapsed >= STEP_MS()) { playing = true; go(0); } // finished: Play restarts the tour
    playing = on;
    root.classList.toggle('is-playing', playing);
    playBtn.setAttribute('aria-pressed', String(playing));
    playBtn.setAttribute('aria-label', playing ? 'Pause the tour' : 'Play the tour automatically');
    playBtn.querySelector('span').textContent = playing ? 'Pause' : 'Play';
    playBtn.querySelector('use')?.setAttribute('href', playing ? '#i-minus' : '#i-play');
    lastT = 0;
    if (playing) { if (!loop) loop = requestAnimationFrame(frameLoop); }
    else if (loop) { cancelAnimationFrame(loop); loop = 0; }
    paintFill();
  }

  const cardEl = h('div', { class: 'story-card' }, grab, stepEl, titleEl, bodyEl, prog, h('div', { class: 'story-actions' }, h('div', { class: 'row' }, h('button', { class: 'btn btn--ghost btn--sm story-skip', type: 'button', onclick: () => exit() }, 'Skip tour'), playBtn), h('div', { class: 'row' }, back, next)));
  root.append(spot, cardEl);
  let opener = null;
  let spaceEat = false;
  // a button activates on Space keyup: swallow that keyup when the keydown already toggled Play
  const onKeyUp = (e) => { if (e.key === ' ' && spaceEat) { e.preventDefault(); e.stopPropagation(); spaceEat = false; } };
  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); exit(); return; }
    if (e.target.closest?.('input, textarea, select')) return;
    // Space is Play/Pause anywhere in the tour, including when Next/Back has focus; only the Play button itself, the grab
    // handle and Skip keep their native Space activation (so Play is not toggled twice)
    if (e.key === ' ' && (!e.target.closest?.('button') || (e.target.closest('.story-card') && e.target !== playBtn && e.target !== grab && !e.target.classList.contains('story-skip')))) { e.preventDefault(); spaceEat = true; setPlaying(!playing); return; }
    if (e.key === 'ArrowRight') { e.preventDefault(); next.click(); }
    if (e.key === 'ArrowLeft' && i > 0) { e.preventDefault(); back.click(); }
    trapFocus(cardEl, e);
  };
  /** Wait (up to `ms`) for the step's target to exist and have a size: views render charts asynchronously. */
  async function waitFor(selector, ms = 10000, my = seq) {
    const t0 = performance.now();
    while (performance.now() - t0 < ms && my === seq) {
      const el = selector ? document.querySelector(selector) : null;
      if (el && el.getBoundingClientRect().height > 0) return el;
      await sleep(100);
    }
    return null;
  }
  const SHEET_MAX = 480; // px viewport width at or below which the card becomes a bottom sheet
  const isSheet = () => innerWidth <= SHEET_MAX;
  /** Bottom of the sticky top bar (0 if absent): story targets and the card stay below it. */
  const barBottom = () => { const b = document.querySelector('.topbar'); return b ? Math.max(0, Math.round(b.getBoundingClientRect().bottom)) : 0; };
  const BAR_GAP = 16;
  let animateNext = false; // the next placement with a live target is a step change: FLIP the spot (and slide the card)
  function setPeek(on) {
    cardEl.classList.toggle('is-peek', !!on);
    grab.setAttribute('aria-expanded', String(!on));
    grab.setAttribute('aria-label', on ? 'Expand the tour card' : 'Collapse the tour card');
    onViewport();
  }
  function place() {
    const sheet = isSheet();
    cardEl.classList.toggle('is-sheet', sheet);
    if (!sheet && cardEl.classList.contains('is-peek')) cardEl.classList.remove('is-peek');
    const bar = barBottom();
    if (!target || !target.isConnected) {
      Object.assign(spot.style, { left: '50%', top: '50%', width: '0px', height: '0px' });
      if (!sheet) Object.assign(cardEl.style, { left: `${(innerWidth - Math.min(380, innerWidth - 32)) / 2}px`, top: `${Math.max(bar + BAR_GAP, innerHeight / 3)}px` });
      return;
    }
    const anim = animateNext && !motionReduced();
    animateNext = false;
    const spotFrom = anim ? spot.getBoundingClientRect() : null;
    const cardFrom = anim && !sheet ? cardEl.getBoundingClientRect() : null;
    const r = target.getBoundingClientRect();
    const pad = 8;
    // the spotlight never covers the sticky top bar
    const top0 = Math.max(r.top - pad, bar + 4), bot0 = Math.min(r.bottom + pad, innerHeight - 4);
    Object.assign(spot.style, { left: `${r.left - pad}px`, top: `${top0}px`, width: `${r.width + pad * 2}px`, height: `${Math.max(0, bot0 - top0)}px` });
    if (spotFrom) flip(spot, spotFrom.width ? spotFrom : { left: r.left + r.width / 2, top: top0 + (bot0 - top0) / 2, width: 1, height: 1 });
    if (sheet) {
      cardEl.style.left = ''; cardEl.style.top = '';
      // automatic peek: collapse to ~25% of the viewport when the expanded sheet would cover the target
      if (peekUser == null) {
        const wasPeek = cardEl.classList.contains('is-peek');
        if (wasPeek) cardEl.classList.remove('is-peek');
        const sheetTop = innerHeight - cardEl.offsetHeight;
        const covered = Math.min(r.bottom, innerHeight) - Math.max(r.top, sheetTop);
        cardEl.classList.toggle('is-peek', covered > 24);
        grab.setAttribute('aria-expanded', String(!cardEl.classList.contains('is-peek')));
      }
      return;
    }
    // clip the target rect to the visible area below the bar, so a tall target leaves room for the card
    const vis = { left: r.left, right: r.right, top: Math.max(r.top, bar), bottom: Math.min(r.bottom, innerHeight), width: r.width };
    vis.height = Math.max(0, vis.bottom - vis.top);
    const ch = cardEl.offsetHeight || 240, cw = Math.min(380, innerWidth - 32);
    const pos = storyCardPosition(vis, { cw, ch, vw: innerWidth, vh: innerHeight, top: bar + BAR_GAP });
    // sub-pixel / few-px contact with the spotlight's bottom edge: nudge the card down into the bottom margin
    const spotBot = top0 + Math.max(0, bot0 - top0), spotL = r.left - pad, spotR = r.right + pad;
    const xHit = Math.min(pos.left + cw, spotR) > Math.max(pos.left, spotL);
    const yOver = spotBot - pos.top;
    if (xHit && yOver > 0 && yOver <= 12 && pos.top + yOver + ch <= innerHeight - 2) pos.top = Math.ceil(spotBot) + 1;
    Object.assign(cardEl.style, { left: `${pos.left}px`, top: `${pos.top}px` });
    if (cardFrom && cardFrom.width) flip(cardEl, cardFrom, { scale: false });
  }
  let raf = 0;
  const onViewport = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(place); };

  /**
   * Scroll so the target's top sits just under the sticky top bar (bar + 16 px on desktop, bar + 8 px on phones).
   * A target already fully inside the free band below the bar stays put.
   */
  function frame(el) {
    const bar = barBottom();
    const r = el.getBoundingClientRect();
    const gapTop = isSheet() ? 8 : BAR_GAP;
    const freeTop = bar + gapTop, freeBot = innerHeight - (isSheet() ? Math.round(innerHeight * 0.25) : BAR_GAP);
    if (r.top >= freeTop && r.bottom <= freeBot) return false;
    const y = Math.max(0, Math.round(scrollY + r.top - freeTop));
    window.scrollTo({ top: y, behavior: motionReduced() ? 'auto' : 'smooth' });
    return true;
  }

  const text = (s, k) => (isSimple() && s[`${k}_simple`]) || s[k] || '';
  function paintText() {
    const s = steps[i];
    stepEl.textContent = `STEP ${String(i + 1).padStart(2, '0')} / ${String(steps.length).padStart(2, '0')}`;
    titleEl.textContent = text(s, 'title');
    bodyEl.textContent = text(s, 'body');
  }

  async function locate(s, my) {
    target = null;
    if (isSheet() && s.mobile_selector) target = await waitFor(s.mobile_selector, 2500, my);
    if (my !== seq) return false;
    if (!target) target = await waitFor(s.selector, 10000, my);
    if (my !== seq) return false;
    if (target) {
      cardEl.classList.toggle('is-sheet', isSheet());
      // views render charts asynchronously: content above the target can still grow after the first scroll, so
      // re-frame until the target stops moving (max 4 passes)
      for (let pass = 0; pass < 4; pass++) {
        const moved = frame(target);
        await sleep(moved && !motionReduced() ? MOTION.slow : 120);
        if (my !== seq) return false;
        if (!moved && pass > 0) break;
      }
    }
    return true;
  }

  async function go(n) {
    const my = ++seq;
    i = Math.max(0, Math.min(steps.length - 1, n));
    const s = steps[i];
    peekUser = null;
    elapsed = 0; ready = false; lastT = 0;
    animateNext = true;
    paintText();
    paintFill();
    back.disabled = i === 0;
    next.textContent = i === steps.length - 1 ? 'Finish' : 'Next';
    root.setAttribute('aria-busy', 'true');
    if (s.route) {
      const cur = location.hash, want = s.route;
      const differs = cur.split('?')[0] !== want.split('?')[0] || (want.includes('?') && cur !== want);
      if (differs) await navigate(want);
    }
    if (my !== seq) return;
    if (!(await locate(s, my))) return;
    place();
    root.removeAttribute('aria-busy');
    if (document.activeElement !== playBtn) next.focus({ preventScroll: true });
    ready = true; lastT = 0; // the clock starts once the step is framed
  }
  // a reading-mode switch re-renders the view: swap the text and re-find the (new) target element
  const onMode = async () => {
    paintText();
    const my = seq;
    await sleep(60);
    if (my !== seq || !root.isConnected) return;
    ready = false;
    if (await locate(steps[i], my)) { place(); ready = true; lastT = 0; }
  };
  function exit() {
    seq++;
    playing = false; ready = false;
    if (loop) cancelAnimationFrame(loop);
    loop = 0;
    cancelAnimationFrame(raf);
    pending.forEach((id) => clearTimeout(id)); pending.clear();
    document.removeEventListener('keydown', onKey, true); document.removeEventListener('keyup', onKeyUp, true);
    document.removeEventListener('gnm:mode', onMode);
    removeEventListener('resize', onViewport);
    removeEventListener('scroll', onViewport, true);
    root.remove();
    if (activeStory === api) activeStory = null;
    if (window.__gnmStory === api) delete window.__gnmStory;
    opener?.focus?.({ preventScroll: true });
    onExit?.();
  }
  const api = {
    start() {
      if (activeStory) return activeStory;
      if (!steps?.length) return api;
      activeStory = api;
      window.__gnmStory = api;
      opener = document.activeElement;
      document.body.append(root);
      document.addEventListener('keydown', onKey, true); document.addEventListener('keyup', onKeyUp, true);
      document.addEventListener('gnm:mode', onMode);
      addEventListener('resize', onViewport);
      addEventListener('scroll', onViewport, true);
      go(0);
      return api;
    },
    exit,
    go,
    play: () => setPlaying(true),
    pause: () => setPlaying(false),
    state: () => ({ index: i, playing, elapsed, stepMs: STEP_MS(), ready, loops: loop ? 1 : 0, timers: pending.size }),
    get index() { return i; },
  };
  return api;
}

// --------------------------------------------------------------------------- footer + states
export const DISCLAIMER = 'Independent educational simulation. Not an airline system or an approved maintenance, airworthiness or dispatch tool. Models run offline; the site loads exported results.';
/** v2.1 brief §E4: the credit line on every page (verbatim). */
export const CREDIT_LINE = 'Built by Akash Gajjar with AI-assisted development (Claude Code). Fictional airline, simulated data.';
/**
 * Site footer (the shell mounts ONE on every page): the disclaimer (exact wording is a project requirement — do not
 * edit) + the E4 credit line (p[data-role=credit]) + optional meta.
 */
export function disclaimer({ meta } = {}) {
  return h('footer', { class: 'disclaimer', role: 'contentinfo' }, icon('shield'),
    h('div', { class: 'disclaimer-text' }, h('p', {}, DISCLAIMER), h('p', { class: 'disclaimer-credit', dataset: { role: 'credit' } }, CREDIT_LINE)),
    meta ? h('span', { class: 'disclaimer-meta' }, meta) : null);
}
export const siteFooter = disclaimer;

// --------------------------------------------------------------------------- v2.1 shared copy blocks
/** v2.1 brief §A2 (verbatim): goes under every results number block. */
export const READING_NOTE = 'How to read these numbers: simulated downtime of the aircraft waiting for the part, across 120 modelled part numbers. Downtime of aircraft that donated a part (cannibalisation) is shown separately, not included. The Simple Rulebook is a deliberately simplified starting point, not a model of a competent airline. Part costs, reliability and sourcing are assumed. These are not forecasts of achievable airline savings.';
/** v2.1 brief §A4 (verbatim) note under the capital table. */
export const CAPITAL_NOTE = 'Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a discount.';
export const POST_PLAN = 'post-plan, exploratory';
export const INTRO_LABELS = { what: 'What this shows', why: 'Why it matters', action: 'What a planner would do' };

/**
 * The three intro lines every workspace starts with (brief §C2):
 *   intro3({what: 'Which parts…', why: '…', action: '…'})  → section.intro3[data-role=intro3] (a <dl>)
 * Values may be strings, Nodes or arrays (so term() can be used inside).
 */
export function intro3({ what, why, action, label = 'About this page' } = {}) {
  const row = (k, v) => h('div', { class: 'intro3-row', dataset: { key: k } }, h('dt', {}, INTRO_LABELS[k]), h('dd', {}, v ?? '—'));
  return h('section', { class: 'intro3', 'aria-label': label, dataset: { role: 'intro3' } }, h('dl', {}, row('what', what), row('why', why), row('action', action)));
}

/** The verbatim KPI scope line as a small paragraph: p.scope-line[data-role=scope]. opts.text overrides (non-empty). */
export const scopeLine = ({ text, cls = '' } = {}) => h('p', { class: `scope-line ${cls}`.trim(), dataset: { role: 'scope' } }, (typeof text === 'string' && text.trim()) || SCOPE_LINE);

/** The verbatim A2 reading note: aside.reading-note[data-role=reading-note]. */
export const readingNote = ({ cls = '' } = {}) => h('aside', { class: `reading-note ${cls}`.trim(), dataset: { role: 'reading-note' } }, icon('info'), h('p', {}, READING_NOTE));

/** "post-plan, exploratory" badge for anything added after the frozen holdout: span.chip.chip-postplan[data-role=postplan]. */
export const postPlanBadge = (text = POST_PLAN) => h('span', { class: 'chip chip-postplan', dataset: { role: 'postplan' }, title: 'Added after the frozen v2 holdout results; kept separate and does not change them.' }, text);

const aedM = (v) => `AED ${(Math.abs(+v) / 1e6).toFixed(1)}M`;
const signed = (v, s) => `${+v > 0 ? '+' : +v < 0 ? '−' : ''}${s}`;
/**
 * The A4 capital table: gross buys, gross removals, THEN the net — never the net alone.
 *   capitalTable(kpis.headline.core)                          // {remix, capital_aed: {mean}} → net = capital_aed.mean
 *   capitalTable(remix, {net: 614985})                         // remix = {buy_units, buy_aed, shed_units, shed_aed}
 * The net comes from opts.net ?? remix.net_aed ?? core.capital_aed.mean. Without a net the table shows the two gross
 * lines + the note. Without the gross lines it renders nothing but an error state (a net alone is not allowed).
 * → figure.capital-table[data-role=capital-table] with a <table> (rows tr[data-row=buy|shed|net]) and the note.
 */
export function capitalTable(src, { net, caption = 'Capital change: gross buys and removals, then the net' } = {}) {
  const remix = src?.remix || src || {};
  const netV = net ?? remix.net_aed ?? src?.capital_aed?.mean ?? (typeof src?.capital_aed === 'number' ? src.capital_aed : null);
  const ok = [remix.buy_units, remix.buy_aed, remix.shed_units, remix.shed_aed].every((v) => v != null && !Number.isNaN(+v));
  if (!ok) return stateBlock('error', 'Capital breakdown unavailable (the gross buy and removal lines are missing, so no net is shown).');
  const tr = (key, label, units, value) => h('tr', { dataset: { row: key } }, h('th', { scope: 'row' }, label), h('td', { class: 'is-num' }, units), h('td', { class: 'is-num' }, value));
  const table = h('table', { class: 'data-table data-table--dense capital-table-grid' },
    h('caption', { class: 'sr-only' }, caption),
    h('tbody', {},
      tr('buy', 'New rotables bought', `${signed(remix.buy_units, Math.abs(+remix.buy_units))} units`, `≈ ${aedM(remix.buy_aed)} assumed value`),
      tr('shed', 'Rotables removed', `${signed(-Math.abs(+remix.shed_units), Math.abs(+remix.shed_units))} units`, `≈ ${aedM(remix.shed_aed)}`),
      netV != null ? tr('net', 'Net change in average simulated spare inventory', '', signed(netV, aedM(netV))) : null));
  return h('figure', { class: 'capital-table', dataset: { role: 'capital-table' } }, table, h('figcaption', { class: 'capital-note' }, CAPITAL_NOTE));
}

/** Dashed note marking a placeholder area that a screen agent will replace. */
export const stubNote = (text) => h('div', { class: 'stub-note' }, icon('wrench'), text);

/** Loading / empty / error state block. kind: 'loading' | 'empty' | 'error' */
export function stateBlock(kind, message) {
  if (kind === 'loading') return h('div', { class: 'stack', 'aria-busy': 'true' }, h('div', { class: 'skeleton', style: { height: '28px', width: '40%' } }), h('div', { class: 'skeleton', style: { height: '180px' } }));
  return h('div', { class: `state state--${kind}`, role: kind === 'error' ? 'alert' : null }, icon(kind === 'error' ? 'alert' : 'info'), h('p', {}, message));
}
