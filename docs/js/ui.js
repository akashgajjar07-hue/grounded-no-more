/**
 * ui.js — DOM component helpers for GROUNDED NO MORE.
 * Every function returns a real Element styled by css/components.css. Views compose these;
 * they should not invent new visual styles. See docs/design/DESIGN_SYSTEM.md for the API.
 */
import { assetURL } from './data.js';

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
export function provChip(p = 'DERIVED') {
  const key = String(p).toUpperCase();
  return h('span', { class: `chip chip-prov chip-prov--${key.toLowerCase()}`, title: PROV_HELP[key] || key, 'aria-label': `Provenance: ${PROV_HELP[key] || key}` }, key);
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
export function pill(status = 'unknown', text) {
  const s = PILL[status] ? status : 'unknown';
  const [ic, label] = PILL[s];
  const cls = s === 'info' ? 'unknown' : s;
  return h('span', { class: `pill pill--${cls}` }, icon(ic), text ?? label);
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
/**
 * KPI tile from a kpis.json row: {id,label,value,unit,baseline,delta,better,provenance,ci,spark,target}
 * opts.format(value) → string (defaults chosen by unit), opts.sparkline(el, values) to draw the spark.
 * opts.scale: {min, max} for the instrument ruler (optional).
 */
export function kpiTile(k, { format, deltaFormat, sparkline, scale, hero = false } = {}) {
  const fmt = format || ((v) => String(v));
  const dfmt = deltaFormat || fmt;
  const good = k.delta === 0 ? 'flat' : (k.better === 'lower' ? k.delta < 0 : k.delta > 0) ? 'good' : 'bad';
  const [num, unit] = splitUnit(fmt(k.value));
  const delta = h(
    'span',
    { class: `kpi-delta is-${good}` },
    icon(k.delta < 0 ? 'arrow-down' : k.delta > 0 ? 'arrow-up' : 'minus'),
    `${k.delta > 0 ? '+' : k.delta < 0 ? '−' : ''}${dfmt(Math.abs(k.delta))}`,
    h('span', { class: 'kpi-delta-ref' }, ' vs baseline'),
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
    h('div', { class: 'kpi-foot' }, h('span', {}, ci), h('span', {}, `Baseline ${fmt(k.baseline)}`))
  );
  if (sparkline && Array.isArray(k.spark)) requestAnimationFrame(() => sparkline(spark, k.spark, { better: k.better }));
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
 *   dataTable({columns: [{key, label, num, mono, sortable=true, format(v,row), render(row)→Node}],
 *              rows, sort: {key, dir:'desc'}, onRowClick(row), selectedKey, rowKey, maxHeight, dense, caption})
 * Returns the wrapper element; `.update(rows)` re-renders the body.
 */
export function dataTable({ columns, rows, sort, onRowClick, rowKey, selected, maxHeight, dense = false, caption, bare = false }) {
  let state = { rows: rows || [], sort: sort || null };
  const table = h('table', { class: `data-table ${dense ? 'data-table--dense' : ''}` });
  if (caption) table.append(h('caption', { class: 'sr-only' }, caption));
  const thead = h('thead');
  const tbody = h('tbody');
  table.append(thead, tbody);
  const wrap = h('div', { class: `table-wrap ${bare ? 'table-wrap--bare' : ''}`, style: maxHeight ? { maxHeight: `${maxHeight}px` } : undefined, tabindex: '0', role: 'region', 'aria-label': caption || 'Data table' }, table);

  function renderHead() {
    thead.replaceChildren(
      h(
        'tr',
        {},
        columns.map((c) => {
          const sorted = state.sort?.key === c.key;
          const th = h('th', { scope: 'col', class: c.num ? 'is-num' : '', 'aria-sort': sorted ? (state.sort.dir === 'asc' ? 'ascending' : 'descending') : null });
          if (c.sortable === false) th.append(c.label);
          else th.append(h('button', { class: 'th-sort', type: 'button', onclick: () => toggleSort(c.key) }, c.label, icon('sort')));
          return th;
        })
      )
    );
  }
  function toggleSort(key) {
    const dir = state.sort?.key === key && state.sort.dir === 'desc' ? 'asc' : 'desc';
    state.sort = { key, dir };
    renderHead();
    renderBody();
  }
  function renderBody() {
    let data = state.rows.slice();
    if (state.sort) {
      const { key, dir } = state.sort;
      const m = dir === 'asc' ? 1 : -1;
      data.sort((a, b) => (a[key] > b[key] ? m : a[key] < b[key] ? -m : 0));
    }
    tbody.replaceChildren(
      ...data.map((r) =>
        h(
          'tr',
          {
            'aria-selected': rowKey && selected != null ? String(r[rowKey] === selected) : null,
            tabindex: onRowClick ? '0' : null,
            style: onRowClick ? { cursor: 'pointer' } : undefined,
            onclick: onRowClick ? () => onRowClick(r) : null,
            onkeydown: onRowClick ? (e) => { if (e.key === 'Enter') onRowClick(r); } : null,
          },
          columns.map((c) => {
            const content = c.render ? c.render(r) : c.format ? c.format(r[c.key], r) : r[c.key];
            return h('td', { class: `${c.num ? 'is-num' : ''} ${c.mono ? 'mono' : ''}`.trim() }, content ?? '—');
          })
        )
      )
    );
  }
  renderHead();
  renderBody();
  wrap.update = (rows2) => { state.rows = rows2; renderBody(); };
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
  const set = (v) => { value = v; [...g.children].forEach((b) => b.setAttribute('aria-checked', String(b.dataset.value === String(v)))); onChange?.(v); };
  options.forEach((o) => g.append(h('button', { type: 'button', role: 'radio', dataset: { value: o.value }, 'aria-checked': String(o.value === value), onclick: () => set(o.value) }, o.label)));
  return g;
}

/** Labelled range slider with live <output>. format(v) → display string. */
export function slider({ label, min, max, step = 1, value, format = String, onInput, id }) {
  const sid = id || `sl-${Math.random().toString(36).slice(2, 8)}`;
  const out = h('output', { for: sid }, format(value));
  const input = h('input', { class: 'slider', type: 'range', id: sid, min, max, step, value });
  const pct = () => input.style.setProperty('--pct', `${((input.value - min) / (max - min)) * 100}%`);
  pct();
  input.addEventListener('input', () => { pct(); out.textContent = format(+input.value); onInput?.(+input.value); });
  return h('div', { class: 'field' }, h('label', { class: 'field-label', for: sid }, label, out), input, h('div', { class: 'slider-scale', 'aria-hidden': 'true' }, h('span', {}, format(min)), h('span', {}, format(max))));
}

// --------------------------------------------------------------------------- overlays
let lastFocus = null;
function trapFocus(container, e) {
  if (e.key !== 'Tab') return;
  const f = container.querySelectorAll('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])');
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

/**
 * Right-hand drawer. drawer({title, kicker, body, foot}) → {open(), close(), el, body}
 * Closes on Esc, scrim click and the close button; returns focus to the opener.
 */
export function drawer({ title, kicker, body, foot, onClose } = {}) {
  const scrim = h('div', { class: 'scrim' });
  const bodyEl = h('div', { class: 'drawer-body' }, body);
  const el = h(
    'aside',
    { class: 'drawer', role: 'dialog', 'aria-modal': 'true', 'aria-label': title || 'Details' },
    h('div', { class: 'drawer-head' }, h('div', {}, kicker ? h('div', { class: 'card-kicker' }, kicker) : null, h('h2', { class: 't-20' }, title || '')), h('button', { class: 'btn btn--ghost btn--icon', type: 'button', 'aria-label': 'Close', onclick: () => api.close() }, icon('close'))),
    bodyEl,
    foot ? h('div', { class: 'drawer-foot' }, foot) : null
  );
  const onKey = (e) => { if (e.key === 'Escape') api.close(); trapFocus(el, e); };
  const api = {
    el, body: bodyEl,
    open() {
      lastFocus = document.activeElement;
      document.body.append(scrim, el);
      requestAnimationFrame(() => { scrim.classList.add('is-open'); el.classList.add('is-open'); el.querySelector('button')?.focus(); });
      scrim.onclick = () => api.close();
      document.addEventListener('keydown', onKey);
      return api;
    },
    close() {
      scrim.classList.remove('is-open'); el.classList.remove('is-open');
      document.removeEventListener('keydown', onKey);
      setTimeout(() => { scrim.remove(); el.remove(); }, 320);
      lastFocus?.focus?.();
      onClose?.();
    },
  };
  return api;
}

/** Centred modal dialog. modal({title, body}) → {open(), close()} */
export function modal({ title, body } = {}) {
  const scrim = h('div', { class: 'scrim' });
  const cardEl = h('div', { class: 'modal-card', role: 'dialog', 'aria-modal': 'true', 'aria-label': title }, h('div', { class: 'row-between mb-3' }, h('h2', { class: 't-20' }, title), h('button', { class: 'btn btn--ghost btn--icon', type: 'button', 'aria-label': 'Close', onclick: () => api.close() }, icon('close'))), body);
  const wrap = h('div', { class: 'modal' }, cardEl);
  const onKey = (e) => { if (e.key === 'Escape') api.close(); trapFocus(cardEl, e); };
  const api = {
    isOpen: false,
    open() { lastFocus = document.activeElement; document.body.append(scrim, wrap); requestAnimationFrame(() => scrim.classList.add('is-open')); wrap.onclick = (e) => { if (e.target === wrap) api.close(); }; document.addEventListener('keydown', onKey); cardEl.querySelector('button').focus(); api.isOpen = true; return api; },
    close() { scrim.remove(); wrap.remove(); document.removeEventListener('keydown', onKey); lastFocus?.focus?.(); api.isOpen = false; },
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
    tipEl.classList.add('is-on');
    this.move(evt);
  },
  move(evt) {
    if (!tipEl) return;
    const pad = 14, r = tipEl.getBoundingClientRect();
    let x = (evt.clientX ?? 0) + pad, y = (evt.clientY ?? 0) + pad;
    if (x + r.width > innerWidth - 8) x = (evt.clientX ?? 0) - r.width - pad;
    if (y + r.height > innerHeight - 8) y = (evt.clientY ?? 0) - r.height - pad;
    tipEl.style.left = `${Math.max(8, x)}px`; tipEl.style.top = `${Math.max(8, y)}px`;
  },
  hide() { tipEl?.classList.remove('is-on'); },
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
export async function blueprintAircraft(host, { active, onSelect, compactBelow = 1000, label = 'Aircraft systems' } = {}) {
  const svg = await inlineSVG('blueprint-aircraft-top.svg');
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
 * Story-mode overlay: spotlight + step card. steps: [{route, selector, title, body}]
 * navigate(route) must return a Promise that resolves once the view has rendered.
 */
let activeStory = null;
export function storyMode({ steps, navigate, onExit }) {
  let i = 0;
  let seq = 0; // guards against overlapping go() calls (fast ←/→)
  let target = null;
  const root = h('div', { class: 'story', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Guided tour' });
  const spot = h('div', { class: 'story-spot' });
  const stepEl = h('div', { class: 'story-step', 'aria-live': 'polite' });
  const titleEl = h('h3', {});
  const bodyEl = h('p', {});
  const prog = h('div', { class: 'story-progress', 'aria-hidden': 'true' }, steps.map(() => h('span')));
  const back = h('button', { class: 'btn btn--ghost btn--sm', type: 'button', onclick: () => go(i - 1) }, 'Back');
  const next = h('button', { class: 'btn btn--primary btn--sm', type: 'button', onclick: () => (i < steps.length - 1 ? go(i + 1) : exit()) }, 'Next');
  const cardEl = h('div', { class: 'story-card' }, stepEl, titleEl, bodyEl, prog, h('div', { class: 'story-actions' }, h('button', { class: 'btn btn--ghost btn--sm', type: 'button', onclick: () => exit() }, 'Exit tour'), h('div', { class: 'row' }, back, next)));
  root.append(spot, cardEl);
  let opener = null;
  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); exit(); return; }
    if (e.target.closest?.('input, textarea, select')) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); next.click(); }
    if (e.key === 'ArrowLeft' && i > 0) { e.preventDefault(); back.click(); }
    trapFocus(cardEl, e);
  };
  const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  /** Wait (up to `ms`) for the step's target to exist and have a size: views render charts asynchronously. */
  async function waitFor(selector, ms = 10000) {
    const t0 = performance.now();
    while (performance.now() - t0 < ms) {
      const el = selector ? document.querySelector(selector) : null;
      if (el && el.getBoundingClientRect().height > 0) return el;
      await new Promise((r) => setTimeout(r, 100));
    }
    return null;
  }
  function place() {
    if (!target || !target.isConnected) {
      Object.assign(spot.style, { left: '50%', top: '50%', width: '0px', height: '0px' });
      Object.assign(cardEl.style, { left: `${(innerWidth - Math.min(380, innerWidth - 32)) / 2}px`, top: `${innerHeight / 3}px` });
      return;
    }
    const r = target.getBoundingClientRect();
    const pad = 8;
    const top0 = Math.max(r.top - pad, 4), bot0 = Math.min(r.bottom + pad, innerHeight - 4);
    Object.assign(spot.style, { left: `${r.left - pad}px`, top: `${top0}px`, width: `${r.width + pad * 2}px`, height: `${Math.max(0, bot0 - top0)}px` });
    const cw = Math.min(380, innerWidth - 32), ch = cardEl.offsetHeight || 240, gap = 24;
    let left, top;
    if (r.right + gap + cw <= innerWidth - 16) { left = r.right + gap; top = r.top; }
    else if (r.left - gap - cw >= 16) { left = r.left - gap - cw; top = r.top; }
    else if (r.bottom + gap + ch <= innerHeight - 16) { left = Math.max(16, Math.min(r.left, innerWidth - cw - 16)); top = r.bottom + gap; }
    else if (r.top - gap - ch >= 16) { left = Math.max(16, Math.min(r.left, innerWidth - cw - 16)); top = r.top - gap - ch; }
    else { left = Math.max(16, innerWidth - cw - 16); top = innerHeight - ch - 16; }
    top = Math.min(Math.max(16, top), innerHeight - ch - 16);
    Object.assign(cardEl.style, { left: `${left}px`, top: `${Math.max(16, top)}px` });
  }
  let raf = 0;
  const onViewport = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(place); };

  async function go(n) {
    const my = ++seq;
    i = Math.max(0, Math.min(steps.length - 1, n));
    const s = steps[i];
    stepEl.textContent = `STEP ${String(i + 1).padStart(2, '0')} / ${String(steps.length).padStart(2, '0')}`;
    titleEl.textContent = s.title;
    bodyEl.textContent = s.body;
    [...prog.children].forEach((b, j) => b.classList.toggle('is-done', j <= i));
    back.disabled = i === 0;
    next.textContent = i === steps.length - 1 ? 'Finish' : 'Next';
    root.setAttribute('aria-busy', 'true');
    if (s.route) {
      const cur = location.hash, want = s.route;
      const differs = cur.split('?')[0] !== want.split('?')[0] || (want.includes('?') && cur !== want);
      if (differs) await navigate(want);
    }
    if (my !== seq) return;
    target = await waitFor(s.selector);
    if (my !== seq) return;
    if (target) {
      target.scrollIntoView({ block: 'center', behavior: reduce() ? 'auto' : 'smooth' });
      await new Promise((r) => setTimeout(r, reduce() ? 50 : 350));
      if (my !== seq) return;
    }
    place();
    root.removeAttribute('aria-busy');
    next.focus({ preventScroll: true });
  }
  function exit() {
    seq++;
    document.removeEventListener('keydown', onKey, true);
    removeEventListener('resize', onViewport);
    removeEventListener('scroll', onViewport, true);
    root.remove();
    if (activeStory === api) activeStory = null;
    opener?.focus?.({ preventScroll: true });
    onExit?.();
  }
  const api = {
    start() {
      if (activeStory) return activeStory;
      if (!steps?.length) return api;
      activeStory = api;
      opener = document.activeElement;
      document.body.append(root);
      document.addEventListener('keydown', onKey, true);
      addEventListener('resize', onViewport);
      addEventListener('scroll', onViewport, true);
      go(0);
      return api;
    },
    exit,
    go,
    get index() { return i; },
  };
  return api;
}

// --------------------------------------------------------------------------- footer + states
export const DISCLAIMER = 'Independent educational simulation. Not an airline system or an approved maintenance, airworthiness or dispatch tool. Models run offline; the site loads exported results.';
/** Footer disclaimer component (exact wording is a project requirement — do not edit). */
export function disclaimer({ meta } = {}) {
  return h('footer', { class: 'disclaimer', role: 'contentinfo' }, icon('shield'), h('p', {}, DISCLAIMER), meta ? h('span', { class: 'disclaimer-meta' }, meta) : null);
}

/** Dashed note marking a placeholder area that a screen agent will replace. */
export const stubNote = (text) => h('div', { class: 'stub-note' }, icon('wrench'), text);

/** Loading / empty / error state block. kind: 'loading' | 'empty' | 'error' */
export function stateBlock(kind, message) {
  if (kind === 'loading') return h('div', { class: 'stack', 'aria-busy': 'true' }, h('div', { class: 'skeleton', style: { height: '28px', width: '40%' } }), h('div', { class: 'skeleton', style: { height: '180px' } }));
  return h('div', { class: `state state--${kind}`, role: kind === 'error' ? 'alert' : null }, icon(kind === 'error' ? 'alert' : 'info'), h('p', {}, message));
}
