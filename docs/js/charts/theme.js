/**
 * charts/theme.js — THE shared chart theme for GROUNDED NO MORE.
 *
 * Rules (enforced by convention, see docs/design/DESIGN_SYSTEM.md):
 *  - every chart lives in a chartFrame(): takeaway headline, subtitle (units · grain · as-of),
 *    provenance chip, source line and a <details> "View data" table fallback;
 *  - at most 2 accent colours per chart (teal = primary series, copper = capital / comparison)
 *    plus neutrals; direct labels instead of legends; one annotation for the key point;
 *  - hairline axes, no heavy gridlines, no pies, no 3-D, no rainbow;
 *  - show uncertainty (band() / dotWhisker()) whenever an interval exists;
 *  - charts re-layout on resize via responsive() and must work at 390 px.
 * D3 v7 and Observable Plot are loaded as globals (window.d3, window.Plot) by index.html.
 */
import { h, provChip, tooltip, dataTable } from '../ui.js';

const d3 = () => window.d3;

// --------------------------------------------------------------------------- tokens
export const theme = {
  color: {
    bg: '#09131F', panel: '#132638', surface: '#0F1E2E',
    text: '#F2F6FA', muted: '#B9C8D6', faint: '#8A9BAD',
    line: 'rgba(185,200,214,0.14)', lineStrong: 'rgba(185,200,214,0.26)',
    accent: '#22C7B8',        // accent 1 — recommended / primary data series (teal)
    accent2: '#C47F52',       // accent 2 — capital or baseline (P0) ONLY (copper)
    accentHi: '#7FF3E6',
    neutral: '#6B7C8F',       // context series (non-text)
    neutralSoft: 'rgba(185,200,214,0.35)',
    ok: '#22C7B8', review: '#F5B942', urgent: '#E76B64', unknown: '#6B7C8F',
    prov: { REAL: '#22C7B8', DERIVED: '#B9C8D6', ASSUMED: '#F5B942', SIMULATED: '#C47F52' },
  },
  /**
   * Semantic series colours — the ONLY colours a screen should pick for marks (DESIGN_SYSTEM §3, accent table).
   *   recommended: teal  · the recommended plan / primary data series
   *   baseline:    copper · capital or the P0 baseline (never "returns", vendors, emergencies, targets)
   *   reference:   faded titanium · reference lines, thresholds, targets (draw with refLine())
   *   neutral:     titanium/slate · every other comparison or context series
   *   urgent:      red · urgent / AOG-risk STATUS only (never a capital delta)
   *   review:      amber · review STATUS only (never reference lines)
   * Pair at most TWO of {recommended, baseline, urgent, review} in one chart.
   */
  series: {
    recommended: '#22C7B8',
    baseline: '#C47F52',
    reference: 'rgba(185,200,214,0.5)',
    neutral: '#B9C8D6',
    neutralSoft: 'rgba(185,200,214,0.35)',
    context: '#6B7C8F',
    urgent: '#E76B64',
    review: '#F5B942',
  },
  font: { display: "'Space Grotesk', system-ui, sans-serif", ui: "'Inter', system-ui, sans-serif", mono: "'IBM Plex Mono', ui-monospace, monospace" },
  margin: { top: 16, right: 64, bottom: 32, left: 52 },
  motion: { ms: 300, ease: 'cubic-bezier(0.16, 1, 0.3, 1)' },
  /** Reference line (threshold, target, "naive = 1.0", "on quote"): faded titanium 4 4 dashes + faint label. */
  refLine: (g, opts) => refLine(g, opts),
};
/** Accent colours counted by lintAccents() (≤ 2 per chart). */
const ACCENTS = { teal: ['#22c7b8', '34,199,184', '#7ff3e6', '127,243,230'], copper: ['#c47f52', '196,127,82'], red: ['#e76b64', '231,107,100'], amber: ['#f5b942', '245,185,66'] };
const isDev = () => !!window.__gnmDev;
export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// --------------------------------------------------------------------------- formatters
const trim = (s) => s.replace(/\.0(?=[^\d]|$)/, '');
/** AED 4.8M / AED 820k / AED 950 (accepts negative values). */
export function fmtAED(v, { digits = 1, sign = false } = {}) {
  if (v == null || Number.isNaN(+v)) return '—';
  const a = Math.abs(v);
  const s = v < 0 ? '−' : sign && v > 0 ? '+' : '';
  // one sign style site-wide (wave 5): the sign leads the currency, "+AED 4.8M" / "−AED 951k"
  if (a >= 1e9) return `${s}AED ${trim((a / 1e9).toFixed(digits))}B`;
  if (a >= 1e6) return `${s}AED ${trim((a / 1e6).toFixed(digits))}M`;
  if (a >= 1e3) return `${s}AED ${Math.round(a / 1e3)}k`;
  return `${s}AED ${Math.round(a)}`;
}
/** Fraction → percent: fmtPct(0.987) = "98.7%". */
export const fmtPct = (v, digits = 1) => (v == null || Number.isNaN(+v) ? '—' : `${(v * 100).toFixed(digits)}%`);
/** Percentage-point delta: fmtPts(0.034) = "3.4 pts". */
export const fmtPts = (v, digits = 1) => (v == null ? '—' : `${(Math.abs(v) * 100).toFixed(digits)} pts`);
/** Hours: fmtHours(124) = "124 h"; fmtHours(3.5) = "3.5 h". */
export const fmtHours = (v) => (v == null || Number.isNaN(+v) ? '—' : `${Math.abs(v) >= 10 ? Math.round(v).toLocaleString('en-GB') : +(+v).toFixed(1)} h`);
/** Days: fmtDays(42) = "42 d". */
export const fmtDays = (v) => (v == null ? '—' : `${Math.round(v)} d`);
/** Integer with thousands separators: 12,345. */
export const fmtInt = (v) => (v == null || Number.isNaN(+v) ? '—' : Math.round(v).toLocaleString('en-GB'));
/** Number with fixed decimals. */
export const fmtNum = (v, d = 2) => (v == null || Number.isNaN(+v) ? '—' : (+v).toFixed(d));
/**
 * Simulated week label — THE one week format on the site: fmtWeek(103) = "W103", fmtWeek('W103') = "W103",
 * fmtWeek(103.6) = "W104", fmtWeek(null) = "—". Simulated calendar, never real dates.
 */
export const fmtWeek = (w) => {
  if (w == null || w === '') return '—';
  const n = typeof w === 'string' ? +w.replace(/^W/i, '') : +w;
  return Number.isFinite(n) ? `W${Math.round(n)}` : '—';
};
/** Week range: fmtWeekRange(104, 155) = "W104–W155". */
export const fmtWeekRange = (a, b) => `${fmtWeek(a)}–${fmtWeek(b)}`;
/**
 * Capital delta in NEUTRAL wording (capital changes are never red/green):
 * fmtCapitalDelta(5.04e6) = "+AED 5M more capital"; fmtCapitalDelta(-3.6e6) = "AED 3.6M less capital".
 */
export const fmtCapitalDelta = (v) => (v == null || Number.isNaN(+v) ? '—' : v === 0 ? 'no capital change' : `${v > 0 ? '+' : ''}${fmtAED(Math.abs(v))} ${v > 0 ? 'more' : 'less'} capital`);
/** Money, ALWAYS compact ("AED 138k", "AED 1.9M"): use for every AED value, prose included. Alias of fmtAED. */
export const fmtMoney = (v, opts) => fmtAED(v, opts);
/** Count with thousands separators: fmtCount(47977) = "47,977"; accepts numeric strings; null → "—". */
export const fmtCount = (v) => (v == null || v === '' || Number.isNaN(+v) ? '—' : Math.round(+v).toLocaleString('en-GB'));
/** The multiplication sign. Never write "x2" / "2x": use fmtMult() or `${TIMES}`. */
export const TIMES = '×';
/** Multiplier: fmtMult(2) = "×2.0", fmtMult(0.5) = "×0.5", fmtMult(1.25, 2) = "×1.25". */
export const fmtMult = (v, digits = 1) => (v == null || Number.isNaN(+v) ? '—' : `${TIMES}${(+v).toFixed(digits)}`);
/**
 * Simulated calendar epoch (config/assumptions.yaml → calendar.epoch, a Monday; also exported as
 * aog_lab.json → sim_calendar.epoch). Simulated time, never presented as real dates.
 */
export const SIM_EPOCH = '2023-01-02T00:00:00Z';
const SIM_EPOCH_MS = Date.parse(SIM_EPOCH);
/**
 * Simulated timestamp → "W103 · d4 06:00" (week · day-of-week 1–7, d1 = Monday · hh:mm).
 * Accepts an ISO string on the simulated calendar ('2023-01-18T01:00Z') or simulated hours since the epoch (number).
 * {day: false} → "W103 · 06:00"; {time: false} → "W103 · d4"; both false → "W103".
 */
export function fmtSimTime(x, { day = true, time = true } = {}) {
  if (x == null || x === '') return '—';
  const hrs = typeof x === 'number' ? x : (Date.parse(/(Z|[+-]\d\d:?\d\d)$/.test(String(x)) ? String(x) : `${x}Z`) - SIM_EPOCH_MS) / 3.6e6;
  if (!Number.isFinite(hrs)) return '—';
  const totalMin = Math.round(hrs * 60);
  const w = Math.floor(totalMin / (168 * 60));
  const inWeek = totalMin - w * 168 * 60;
  const d = Math.floor(inWeek / (24 * 60)) + 1;
  const m = inWeek % (24 * 60);
  const hh = String(Math.floor(m / 60)).padStart(2, '0'), mm = String(m % 60).padStart(2, '0');
  const tail = [day ? `d${d}` : null, time ? `${hh}:${mm}` : null].filter(Boolean).join(' ');
  return tail ? `W${w} · ${tail}` : `W${w}`;
}
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** REAL build/run timestamp (generated_at, frozen_at) → "26 Nov 02:25 UTC" ({year: true} → "26 Nov 2026 02:25 UTC"). */
export function fmtStamp(iso, { year = false } = {}) {
  const t = Date.parse(iso);
  if (iso == null || !Number.isFinite(t)) return '—';
  const d = new Date(t);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}${year ? ` ${d.getUTCFullYear()}` : ''} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`;
}
/** Acronyms kept upper-case by fmtEnum(). */
const ENUM_ACRONYMS = new Set(['AOG', 'EU', 'US', 'UK', 'PO', 'RO', 'BER', 'TAT', 'MRO', 'OEM', 'PN', 'ATA', 'MEL', 'AUH', 'LHR', 'FRA', 'CAI', 'JED', 'BOM', 'SIN', 'D0', 'D3', 'D10', 'P0', 'P1', 'P2', 'U/S', 'FH', 'FC', 'LRU', 'ME', 'APAC', 'GCC']);
/** Override labels for specific enums (add here rather than in views). */
export const ENUM_LABELS = { CONDEMNED_AWAITING_REPLACEMENT: 'Condemned, awaiting replacement', EXCESS_DECLINING_DEMAND: 'Excess / declining demand', QUARANTINE_DOCS: 'Quarantine (docs)', IN_REPAIR: 'In repair', D0_no_stock: 'D0, no stock', deadline_expired: 'Deadline expired' };
/** Raw enum → readable label: "OVERDUE_REPAIR" → "Overdue repair", "EU_VENDOR" → "EU vendor", "shop_return" → "Shop return". */
export function fmtEnum(s) {
  if (s == null || s === '') return '—';
  const raw = String(s);
  if (ENUM_LABELS[raw]) return ENUM_LABELS[raw];
  if (!/[_]/.test(raw) && !/^[A-Z0-9]+$/.test(raw)) return raw; // already prose
  const words = raw.split(/[_\s]+/).filter(Boolean).map((w, i) => {
    const up = w.toUpperCase();
    if (ENUM_ACRONYMS.has(up)) return up;
    const lo = w.toLowerCase();
    return i === 0 ? lo.charAt(0).toUpperCase() + lo.slice(1) : lo;
  });
  return words.join(' ');
}
/** "3 options" / "1 option"; plural(n, 'unit', 'units'); the count uses fmtCount. Never write "option(s)". */
export const plural = (n, one, many = `${one}s`) => `${fmtCount(n)} ${Math.round(+n) === 1 ? one : many}`;
/** Pick a formatter from a KPI unit string. */
export const fmtByUnit = (unit) => (unit === 'AED' ? fmtAED : unit === '%' ? fmtPct : unit === 'h' ? fmtHours : unit === 'd' ? fmtDays : fmtInt);

// --------------------------------------------------------------------------- frame
/**
 * chartFrame(host, {headline, subtitle, provenance, source, table: {columns, rows}, story, minHeight})
 * Renders headline + subtitle + provenance chip + chart body + source + "View data" table.
 * - headline: one finding, ≤ 90 characters (dev builds console.warn above that).
 * - subtitle: units · grain · window. Clamped to 2 lines (Inter 12); the full text is always in the `title`
 *   attribute and a "More" toggle appears when it is clamped.
 * - In dev builds the body is linted ~1.5 s after creation: > 2 accent colours → console.warn (lintAccents).
 * Returns {root, body, setTable(columns, rows)}. Draw your chart into `body`.
 */
export const HEADLINE_MAX = 90;
export function chartFrame(host, { headline, subtitle, provenance, source, table, story, minHeight } = {}) {
  const body = h('div', { class: 'chart-body', style: minHeight ? { minHeight: `${minHeight}px` } : undefined });
  const details = h('details', { class: 'chart-data' }, h('summary', {}, 'View data'));
  const sub = subtitle ? h('div', { class: 'chart-subtitle', title: String(subtitle) }, subtitle) : null;
  const more = sub ? h('button', { class: 'chart-subtitle-more', type: 'button', hidden: true, 'aria-expanded': 'false', onclick: () => {
    const on = !sub.classList.contains('is-expanded');
    sub.classList.toggle('is-expanded', on); more.setAttribute('aria-expanded', String(on)); more.textContent = on ? 'Less' : 'More';
  } }, 'More') : null;
  const root = h(
    'figure',
    { class: 'chart-frame', dataset: story ? { story } : undefined },
    h('div', { class: 'chart-head' }, h('div', {}, h('figcaption', { class: 'chart-headline' }, headline || ''), sub, more), provenance ? provChip(provenance) : null),
    body,
    h('div', { class: 'chart-foot' }, source ? h('span', { class: 'chart-source' }, `Source: ${source}`) : h('span'), details)
  );
  const setTable = (columns, rows) => {
    details.querySelector('.table-wrap')?.remove();
    details.append(dataTable({ columns, rows, dense: true, caption: headline }));
  };
  if (table) setTable(table.columns, table.rows);
  host.append(root);
  if (sub) {
    const check = () => { if (!sub.isConnected || sub.classList.contains('is-expanded')) return; more.hidden = !(sub.scrollHeight > sub.clientHeight + 2); };
    requestAnimationFrame(check);
    const ro = new ResizeObserver(() => check());
    ro.observe(sub);
  }
  if (isDev()) {
    const len = String(headline || '').length;
    if (len > HEADLINE_MAX) console.warn(`[chartFrame] headline is ${len} chars (max ${HEADLINE_MAX}): "${headline}"`);
    setTimeout(() => {
      if (!root.isConnected) return;
      const n = lintAccents(body);
      if (n.length > 2) console.warn(`[chartFrame] ${n.length} accent colours (${n.join(', ')}) in "${headline}" (max 2)`);
      const t = lintTeal(body);
      if (t.length > 1) console.warn(`[chartFrame] teal on ${t.length} series (${t.join(', ')}) in "${headline}": teal = the recommended / primary result ONLY; use theme.series.neutral for other categories`);
    }, 1500);
  }
  return { root, body, setTable };
}

/**
 * Which semantic accents (teal, copper, red, amber) are painted inside `root`'s SVG marks.
 * Returns e.g. ['teal', 'copper']. Provenance chips and HTML text are not counted.
 */
export function lintAccents(root) {
  const found = new Set();
  const els = [...root.querySelectorAll('svg *')].slice(0, 2500);
  els.forEach((el) => {
    if (el.closest('.chip')) return;
    const cs = getComputedStyle(el);
    const vals = [el.getAttribute('fill'), el.getAttribute('stroke'), el.getAttribute('stop-color'), cs.fill, cs.stroke].filter(Boolean).map((v) => v.toLowerCase().replace(/\s/g, ''));
    for (const [name, keys] of Object.entries(ACCENTS)) if (vals.some((v) => keys.some((k) => v.includes(k.replace(/\s/g, ''))))) found.add(name);
  });
  return [...found];
}

const TEAL_KEYS = ACCENTS.teal.map((k) => k.replace(/\s/g, ''));
const isTealPaint = (el) => {
  const cs = getComputedStyle(el);
  return [el.getAttribute('fill'), el.getAttribute('stroke'), cs.fill, cs.stroke].filter(Boolean)
    .map((v) => v.toLowerCase().replace(/\s/g, '')).some((v) => TEAL_KEYS.some((k) => v.includes(k)));
};
/**
 * Accent linter for rule "teal = recommended / primary result only". Returns the distinct SERIES painted teal in
 * `root`'s SVG: (a) `data-series` ids of teal marks (set by markSeries(), lineChart, dotWhiskerChart, barList,
 * pickSeries()), and (b) the text of teal-coloured, non-numeric direct labels. More than one → teal is being used
 * as a category colour. chartFrame console.warns about it in dev builds; tests call it on every chart.
 */
export function lintTeal(root) {
  const ids = new Set(), labels = new Set();
  [...root.querySelectorAll('svg [data-series]')].slice(0, 2500).forEach((el) => {
    if (el.closest('.chip')) return;
    const marks = el.matches('g') ? [...el.querySelectorAll('path,rect,circle,line,polygon')] : [el];
    if (marks.some(isTealPaint)) ids.add(el.getAttribute('data-series'));
  });
  [...root.querySelectorAll('svg text')].slice(0, 1500).forEach((el) => {
    if (el.closest('[data-series]') || el.closest('.chip') || el.closest('.gnm-chip')) return;
    const txt = (el.textContent || '').trim();
    if (!txt || /^[\s\d.,%+−\-–×hdkMBAED·$()/]+$/.test(txt)) return; // values, ticks
    if (isTealPaint(el)) labels.add(txt.length > 32 ? `${txt.slice(0, 31)}…` : txt);
  });
  // a labelled series that also carries a data-series id is counted once
  return [...new Set([...ids, ...labels])];
}
/** Tag marks with their series id so lintTeal() can tell series apart: markSeries(sel, 'P2') (d3 selection or element). */
export function markSeries(sel, id) {
  if (!sel) return sel;
  if (typeof sel.attr === 'function') sel.attr('data-series', typeof id === 'function' ? id : String(id));
  else sel.setAttribute?.('data-series', String(id));
  return sel;
}
/**
 * Semantic colour picker with linting: pickSeries('recommended', 'I125') → teal, and records which series asked for
 * teal. Use it with markSeries(). In dev, asking for 'recommended' for two different series in one chart warns.
 * role: recommended | baseline | reference | neutral | neutralSoft | context | urgent | review
 */
const tealAsked = new Map();
export function pickSeries(role, seriesId, chartKey = 'default') {
  const c = theme.series[role];
  if (!c) { if (isDev()) console.warn(`[pickSeries] unknown role "${role}"`); return theme.series.neutral; }
  if (role === 'recommended' && seriesId != null && isDev()) {
    const set = tealAsked.get(chartKey) || new Set();
    set.add(String(seriesId)); tealAsked.set(chartKey, set);
    if (set.size > 1) console.warn(`[pickSeries] teal requested for ${set.size} series in "${chartKey}" (${[...set].join(', ')}): teal = recommended / primary only`);
    setTimeout(() => tealAsked.delete(chartKey), 0);
  }
  return c;
}

/** Re-run draw(width) whenever the element's width changes (debounced to animation frames). */
export function responsive(el, draw) {
  let last = -1, raf = 0;
  const ro = new ResizeObserver(([e]) => {
    const w = Math.floor(e.contentRect.width);
    if (w === last || w < 10) return;
    last = w;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => draw(w));
  });
  ro.observe(el);
  return () => ro.disconnect();
}

/** Create a themed <svg> sized to width × height inside el (replacing previous content). */
export function svgIn(el, width, height, label) {
  el.replaceChildren();
  return d3().select(el).append('svg').attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`).attr('role', 'img').attr('aria-label', label || 'Chart').style('max-width', '100%');
}

// --------------------------------------------------------------------------- axes & marks
/** Hairline axis styling: thin domain, small ticks, mono tabular labels. */
export function styleAxis(sel, { domain = true } = {}) {
  sel.attr('class', 'gnm-axis');
  sel.selectAll('text').attr('font-family', theme.font.mono);
  if (!domain) sel.select('.domain').remove();
  sel.selectAll('.tick line').attr('stroke', theme.color.lineStrong);
  return sel;
}
export function axisBottom(g, scale, { ticks = 5, format, height } = {}) {
  return styleAxis(g.attr('transform', `translate(0,${height})`).call(d3().axisBottom(scale).ticks(ticks).tickSizeOuter(0).tickSize(4).tickPadding(6).tickFormat(format || null)));
}
export function axisLeft(g, scale, { ticks = 4, format, domain = false, integer = false } = {}) {
  const ax = d3().axisLeft(scale).ticks(ticks).tickSizeOuter(0).tickSize(0).tickPadding(8).tickFormat(format || null);
  if (integer) ax.tickValues(scale.ticks(ticks).filter(Number.isInteger));
  return styleAxis(g.call(ax), { domain });
}
/** Faint dashed horizontal guides (use instead of heavy gridlines). */
export function gridY(g, scale, width, ticks = 4, integer = false) {
  g.attr('class', 'gnm-grid').selectAll('line').data(scale.ticks(ticks).filter((t) => !integer || Number.isInteger(t))).join('line').attr('x1', 0).attr('x2', width).attr('y1', (d) => scale(d)).attr('y2', (d) => scale(d));
  return g;
}

/** Line path. data: [{x, y}] (already in data space) with scales x, y. */
export function line(g, data, { x, y, color = theme.color.accent, width = 1.75, dash, curve, label } = {}) {
  return g.append('path').datum(data).attr('fill', 'none').attr('stroke', color).attr('stroke-width', width).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round').attr('stroke-dasharray', dash || null).attr('aria-label', label || null)
    .attr('d', d3().line().x((d) => x(d.x)).y((d) => y(d.y)).curve(curve || d3().curveMonotoneX));
}

/** Uncertainty band. data: [{x, lo, hi}] */
export function band(g, data, { x, y, color = theme.color.accent, opacity = 0.16, curve } = {}) {
  return g.append('path').datum(data).attr('fill', color).attr('fill-opacity', opacity).attr('stroke', 'none')
    .attr('d', d3().area().x((d) => x(d.x)).y0((d) => y(d.lo)).y1((d) => y(d.hi)).curve(curve || d3().curveMonotoneX));
}

/**
 * Dot-and-whisker (point estimate with interval). rows: [{key, value, lo, hi, color?}]
 * orientation 'h': value on x, rows on band scale y.
 */
export function dotWhisker(g, rows, { x, y, color = theme.color.accent, r = 4.5, cap = 6 } = {}) {
  const sel = g.selectAll('g.dw').data(rows).join('g').attr('class', 'dw').attr('transform', (d) => `translate(0,${y(d.key) + y.bandwidth() / 2})`);
  sel.append('line').attr('x1', (d) => x(d.lo)).attr('x2', (d) => x(d.hi)).attr('stroke', (d) => d.color || color).attr('stroke-width', 1.5).attr('stroke-opacity', 0.7);
  sel.append('line').attr('x1', (d) => x(d.lo)).attr('x2', (d) => x(d.lo)).attr('y1', -cap / 2).attr('y2', cap / 2).attr('stroke', (d) => d.color || color).attr('stroke-opacity', 0.7);
  sel.append('line').attr('x1', (d) => x(d.hi)).attr('x2', (d) => x(d.hi)).attr('y1', -cap / 2).attr('y2', cap / 2).attr('stroke', (d) => d.color || color).attr('stroke-opacity', 0.7);
  sel.append('circle').attr('cx', (d) => x(d.value)).attr('r', r).attr('fill', theme.color.bg).attr('stroke', (d) => d.color || color).attr('stroke-width', 2);
  return sel;
}

/**
 * Direct label at (x, y) in px. Use instead of legends. Every label gets a halo (paint-order stroke in the
 * surface colour, CSS .gnm-label) so it stays legible over lines, bars and arcs; pass halo: false to drop it.
 */
export function directLabel(g, { x, y, text, color = theme.color.muted, anchor = 'start', strong = false, dy = '0.32em', halo = true, mono = false }) {
  const t = g.append('text').attr('x', x).attr('y', y).attr('dy', dy).attr('text-anchor', anchor)
    .attr('class', `gnm-label${strong ? ' gnm-label--strong' : ''}${halo ? '' : ' gnm-label--nohalo'}${mono ? ' gnm-label--mono' : ''}`).style('fill', color || null).text(text);
  return t;
}

// ----- label geometry (all in px, chart-local coordinates)
const CHAR_W = 6.6, CHAR_W_MONO = 6.9, LABEL_H = 14;
/** Estimated bbox of a label {x, y, text, anchor, width?, height?, mono?} (y = baseline-centre as drawn with dy .32em). */
export function labelBox(l) {
  const w = l.width ?? String(l.text ?? '').length * (l.mono ? CHAR_W_MONO : CHAR_W);
  const hgt = l.height ?? LABEL_H;
  const x0 = l.anchor === 'end' ? l.x - w : l.anchor === 'middle' ? l.x - w / 2 : l.x;
  return { x: x0, y: l.y - hgt / 2, width: w, height: hgt };
}
/** Rect for a circular marker (dot, ring, node): markerRect(cx, cy, r, pad=2). Use as a dodge() obstacle. */
export const markerRect = (cx, cy, r = 4, pad = 2) => ({ x: cx - r - pad, y: cy - r - pad, width: 2 * (r + pad), height: 2 * (r + pad) });
/** Rect for an SVG element already in the DOM (bars, groups): elementRect(node) in its parent's user space. */
export function elementRect(node) { try { const b = node.getBBox(); return { x: b.x, y: b.y, width: b.width, height: b.height }; } catch { return null; } }
const overlap = (a, b) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
const outside = (r, bd) => (bd ? Math.max(0, bd.x - r.x) + Math.max(0, r.x + r.width - (bd.x + bd.width)) + Math.max(0, bd.y - r.y) + Math.max(0, r.y + r.height - (bd.y + bd.height)) : 0);

/**
 * Resolve label collisions against other labels AND obstacles (marker boxes, bars, annotations).
 *   dodge(labels, 14)                                       // legacy: spread vertically, min gap 14 px
 *   dodge(labels, {gap: 14, obstacles: [markerRect(cx, cy, r), …], bounds: {x:0, y:0, width: iw, height: ih}})
 * labels: [{x, y, text, anchor?, width?, height?, mono?}] — y is mutated (and x/anchor when `flip` helps).
 * Each label tries vertical offsets ±step…±maxShift (and, with flip: true, the opposite side of its anchor
 * point) and keeps the position with the least overlap; labels are placed in y order. Mutates and returns.
 */
export function dodge(labels, opts = 14) {
  const o = typeof opts === 'number' ? { gap: opts } : opts || {};
  const gap = o.gap ?? 14, obstacles = (o.obstacles || []).filter(Boolean), bounds = o.bounds, step = o.step ?? 3, maxShift = o.maxShift ?? 60;
  if (!obstacles.length && !bounds && !o.flip) {
    labels.sort((a, b) => a.y - b.y);
    for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < gap) labels[i].y = labels[i - 1].y + gap;
    return labels;
  }
  labels.sort((a, b) => a.y - b.y);
  const placed = [];
  for (const l of labels) {
    const base = { x: l.x, y: l.y, anchor: l.anchor || 'start' };
    const sides = [base];
    if (o.flip && l.flipX != null) sides.push({ x: l.flipX, y: l.y, anchor: base.anchor === 'start' ? 'end' : 'start' });
    let best = null;
    for (const sd of sides) {
      for (let k = 0; k <= maxShift / step; k++) {
        for (const sgn of k ? [1, -1] : [1]) {
          const cand = { ...l, ...sd, y: sd.y + sgn * k * step };
          const box = labelBox({ ...cand, height: Math.max(cand.height ?? LABEL_H, gap) });
          const cost = placed.reduce((s, p) => s + overlap(box, p), 0) * 2 + obstacles.reduce((s, r) => s + overlap(box, r), 0) + outside(box, bounds) * 40 + k * 0.01 + (sd === base ? 0 : 0.5);
          if (!best || cost < best.cost) best = { cost, cand, box };
          if (cost < 0.5) break;
        }
        if (best && best.cost < 0.5) break;
      }
      if (best && best.cost < 0.5) break;
    }
    Object.assign(l, { x: best.cand.x, y: best.cand.y, anchor: best.cand.anchor });
    placed.push(best.box);
  }
  return labels;
}

/**
 * Position for a label next to a marker, on the side AWAY from the data centroid, offset r + 6 px, avoiding
 * obstacles and already placed labels. Returns {x, y, anchor} (pass straight to directLabel / chipLabel).
 *   const p = labelAround({x: cx, y: cy}, {r: 5, text: 'Reliability-exposure', centroid: {x: mx, y: my},
 *                                           obstacles: dots.map((d) => markerRect(d.x, d.y, 5)), placed, bounds});
 *   placed.push(labelBox({...p, text}));
 */
export function labelAround(pt, { r = 4, text = '', centroid, obstacles = [], placed = [], bounds, mono = false, offset = 6 } = {}) {
  const d = r + offset;
  const away = centroid ? { x: Math.sign(pt.x - centroid.x) || 1, y: Math.sign(pt.y - centroid.y) || -1 } : { x: 1, y: -1 };
  const opts = [
    { x: pt.x + d * away.x, y: pt.y, anchor: away.x > 0 ? 'start' : 'end' },
    { x: pt.x + d * 0.7 * away.x, y: pt.y + d * away.y, anchor: away.x > 0 ? 'start' : 'end' },
    { x: pt.x, y: pt.y + (d + 4) * away.y, anchor: 'middle' },
    { x: pt.x - d * away.x, y: pt.y, anchor: away.x > 0 ? 'end' : 'start' },
    { x: pt.x, y: pt.y - (d + 4) * away.y, anchor: 'middle' },
    { x: pt.x - d * 0.7 * away.x, y: pt.y - d * away.y, anchor: away.x > 0 ? 'end' : 'start' },
    { x: pt.x + d * 0.7 * away.x, y: pt.y - d * away.y, anchor: away.x > 0 ? 'start' : 'end' },
    { x: pt.x - d * 0.7 * away.x, y: pt.y + d * away.y, anchor: away.x > 0 ? 'end' : 'start' },
  ];
  let best = null;
  opts.forEach((c, i) => {
    const box = labelBox({ ...c, text, mono });
    const cost = [...obstacles, ...placed].reduce((s, o) => s + overlap(box, o), 0) + outside(box, bounds) * 40 + i * 0.1;
    if (!best || cost < best.cost) best = { cost, c };
  });
  return best.c;
}

/**
 * Value chip: text on a filled pill (surface colour + hairline) so it reads over arcs, flows and bars.
 * Use for map arc values and lifecycle / flow counts (place at the arc apex).
 *   chipLabel(g, {x, y, text: '39', color: theme.series.neutral, anchor: 'middle'})
 * Returns the <g class="gnm-chip">; its bbox is in .datum().box (for dodge obstacles).
 */
export function chipLabel(g, { x, y, text, color, anchor = 'middle', padX = 6, padY = 2, mono = true, fill = theme.color.surface, stroke = theme.color.lineStrong, cls = '' }) {
  const gg = g.append('g').attr('class', `gnm-chip ${cls}`.trim());
  const rect = gg.append('rect').attr('rx', 8).attr('ry', 8).attr('fill', fill).attr('stroke', stroke).attr('stroke-width', 1);
  const t = gg.append('text').attr('x', x).attr('y', y).attr('dy', '0.34em').attr('text-anchor', anchor)
    .attr('class', `gnm-chip-text${mono ? ' gnm-label--mono' : ''}`).style('fill', color || null).text(text);
  let bb = null;
  try { bb = t.node().getBBox(); } catch { /* not in DOM */ }
  if (!bb || !bb.width) { const w = String(text).length * (mono ? CHAR_W_MONO : CHAR_W); bb = { x: anchor === 'end' ? x - w : anchor === 'middle' ? x - w / 2 : x, y: y - 7, width: w, height: 14 }; }
  const box = { x: bb.x - padX, y: bb.y - padY, width: bb.width + padX * 2, height: bb.height + padY * 2 };
  rect.attr('x', box.x).attr('y', box.y).attr('width', box.width).attr('height', box.height).attr('rx', Math.min(8, box.height / 2));
  gg.datum({ box });
  return gg;
}

/**
 * Reference line: faded titanium, 4 4 dashes, label in --c-text-faint (never amber: amber = review status).
 *   refLine(g, {x1, y1, x2, y2, label: 'naive = 1.0', labelAt: 'end' | 'start', dx: 4, dy: -4})
 * Also available as theme.refLine(g, opts). Returns the <g class="gnm-ref">.
 */
export function refLine(g, { x1, y1, x2, y2, label, labelAt = 'end', dx = 4, dy = -4, anchor } = {}) {
  const gg = g.append('g').attr('class', 'gnm-ref');
  gg.append('line').attr('class', 'gnm-ref-line').attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2);
  if (label) {
    const [lx, ly] = labelAt === 'start' ? [x1, y1] : [x2, y2];
    gg.append('text').attr('class', 'gnm-ref-label').attr('x', lx + dx).attr('y', ly + dy).attr('text-anchor', anchor || (x1 === x2 ? 'start' : labelAt === 'start' ? 'start' : 'end')).text(label);
  }
  return gg;
}

/** Truncate a label to roughly maxPx at ~6.6 px per character (11–12 px UI font). */
export const truncate = (s, maxPx, cw = 6.6) => (String(s).length * cw <= maxPx ? String(s) : `${String(s).slice(0, Math.max(1, Math.floor(maxPx / cw) - 1))}…`);

/** One annotation: leader from (x, y) to (x+dx, y+dy) with a title and optional sub line. */
export function annotate(g, { x, y, dx = 24, dy = -24, title, sub, anchor }) {
  const a = anchor || (dx >= 0 ? 'start' : 'end');
  const gg = g.append('g').attr('class', 'gnm-annot');
  gg.append('path').attr('class', 'gnm-annot-line').attr('d', `M${x},${y}L${x + dx * 0.6},${y + dy}L${x + dx},${y + dy}`);
  gg.append('circle').attr('cx', x).attr('cy', y).attr('r', 3).attr('fill', theme.color.bg).attr('stroke', theme.color.text).attr('stroke-width', 1.25);
  gg.append('text').attr('class', 'gnm-annot-text').attr('x', x + dx + (dx >= 0 ? 6 : -6)).attr('y', y + dy).attr('dy', sub ? '-0.15em' : '0.32em').attr('text-anchor', a).text(title);
  if (sub) gg.append('text').attr('class', 'gnm-annot-sub').attr('x', x + dx + (dx >= 0 ? 6 : -6)).attr('y', y + dy).attr('dy', '1.15em').attr('text-anchor', a).text(sub);
  return gg;
}

/** Attach the shared card tooltip to a selection: content(d) → {title, rows} */
export function withTooltip(sel, content) {
  return sel.on('pointerenter', (e, d) => tooltip.show(e, content(d))).on('pointermove', (e) => tooltip.move(e)).on('pointerleave', () => tooltip.hide());
}
export { tooltip, provChip as provenanceChip };

// --------------------------------------------------------------------------- sparkline
/** Minimal sparkline in a KPI tile: line + last-point dot. better: 'lower' | 'higher' */
export function sparkline(el, values, { color = theme.color.accent } = {}) {
  if (!window.d3 || !values?.length) return;
  const w = el.clientWidth || 200, hgt = el.clientHeight || 36;
  const svg = svgIn(el, w, hgt, 'Trend');
  const x = d3().scaleLinear().domain([0, values.length - 1]).range([2, w - 4]);
  const [lo, hi] = d3().extent(values);
  const y = d3().scaleLinear().domain(lo === hi ? [lo - 1, hi + 1] : [lo, hi]).range([hgt - 3, 3]);
  const data = values.map((v, i) => ({ x: i, y: v }));
  svg.append('path').datum(data).attr('fill', color).attr('fill-opacity', 0.08).attr('d', d3().area().x((d) => x(d.x)).y0(hgt).y1((d) => y(d.y)).curve(d3().curveMonotoneX));
  line(svg, data, { x, y, color, width: 1.5 });
  svg.append('circle').attr('cx', x(values.length - 1)).attr('cy', y(values.at(-1))).attr('r', 3).attr('fill', theme.color.bg).attr('stroke', color).attr('stroke-width', 1.5);
}

// --------------------------------------------------------------------------- Observable Plot wrapper
/**
 * Plot.plot with the theme applied (transparent bg, mono ticks, hairline axes, no grid).
 * Pass normal Plot options; width defaults to the host width.
 */
export function plot(options = {}) {
  const P = window.Plot;
  const fig = P.plot({
    marginLeft: theme.margin.left, marginRight: 24, marginTop: theme.margin.top, marginBottom: theme.margin.bottom,
    style: { background: 'transparent', color: theme.color.faint, fontFamily: theme.font.mono, fontSize: '11px', overflow: 'visible' },
    ...options,
    x: { line: true, tickSize: 4, labelAnchor: 'right', ...(options.x || {}) },
    y: { tickSize: 0, labelAnchor: 'top', ...(options.y || {}) },
  });
  fig.classList?.add('gnm-plot');
  return fig;
}

// --------------------------------------------------------------------------- ready-made charts
/**
 * Line chart with optional uncertainty band, direct end labels and one annotation.
 *   lineChart(body, {series: [{id, label, color?, primary?, width?, dash?, values: [{x, y}]}], band: {x, lo, hi}[], bandColor,
 *                    x: {format, ticks, label}, y: {format, ticks, domain}, annotation: {x, y, title, sub}, height})
 */
export function lineChart(body, { series = [], band: bandData, bandColor, x: xo = {}, y: yo = {}, annotation, height = 260 } = {}) {
  return responsive(body, (w) => {
    const m = { ...theme.margin, right: w < 480 ? 16 : theme.margin.right };
    const iw = Math.max(40, w - m.left - m.right), ih = height - m.top - m.bottom;
    const svg = svgIn(body, w, height, 'Line chart');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const all = series.flatMap((s) => s.values);
    const x = d3().scaleLinear().domain(xo.domain || d3().extent(all, (d) => d.x)).range([0, iw]);
    const ys = all.map((d) => d.y).concat(bandData ? bandData.flatMap((d) => [d.lo, d.hi]) : []);
    const y = d3().scaleLinear().domain(yo.domain || [Math.min(0, d3().min(ys)), d3().max(ys) * 1.08]).nice().range([ih, 0]);
    const integer = yo.integer ?? all.every((d) => Number.isInteger(d.y));
    gridY(g.append('g'), y, iw, yo.ticks || 4, integer);
    axisLeft(g.append('g'), y, { ticks: yo.ticks || 4, format: yo.format, integer });
    axisBottom(g.append('g'), x, { ticks: w < 480 ? 4 : xo.ticks || 6, format: xo.format, height: ih });
    if (bandData) band(g, bandData, { x, y, color: bandColor || series[0]?.color || theme.color.accent });
    const labels = [];
    const colorOf = (s, i) => s.color || (s.role && theme.series[s.role]) || (i === 0 ? theme.series.recommended : i === 1 ? theme.series.neutral : theme.series.neutralSoft);
    series.forEach((s, i) => {
      const color = colorOf(s, i);
      const primary = s.primary ?? i === 0;
      markSeries(line(g, s.values, { x, y, color, width: s.width || (primary ? 2 : 1.5), dash: s.dash, curve: s.curve }), s.label || s.id || `s${i}`);
      const last = s.values.at(-1);
      if (s.label) labels.push({ x: x(last.x) + 8, y: y(last.y), text: s.label, color: primary ? color : theme.color.muted, strong: primary });
    });
    if (w >= 480) dodge(labels, { gap: 14, bounds: { x: 0, y: -m.top, width: w - m.left, height: ih + m.top } }).forEach((l) => directLabel(g, l));
    if (w < 480 && series.some((s) => s.label)) {
      // narrow: labels move to a compact key above the plot
      series.forEach((s, i) => directLabel(g, { x: i * 120, y: -6, text: `— ${s.label}`, color: colorOf(s, i) }));
    }
    if (annotation) annotate(g, { x: x(annotation.x), y: y(annotation.y), dx: x(annotation.x) > iw * 0.6 ? -28 : 28, dy: -28, title: annotation.title, sub: annotation.sub });
    // hover readout
    const focus = g.append('g').style('display', 'none');
    focus.append('line').attr('y1', 0).attr('y2', ih).attr('stroke', theme.color.lineStrong);
    g.append('rect').attr('width', iw).attr('height', ih).attr('fill', 'transparent')
      .on('pointermove', (e) => {
        const [mx] = d3().pointer(e);
        const xv = Math.round(x.invert(mx));
        focus.style('display', null).attr('transform', `translate(${x(xv)},0)`);
        tooltip.show(e, { title: xo.format ? xo.format(xv) : String(xv), rows: series.map((s) => [s.label || s.id, (yo.format || String)(s.values.find((d) => d.x === xv)?.y)]) });
      })
      .on('pointerleave', () => { focus.style('display', 'none'); tooltip.hide(); });
  });
}

/**
 * Horizontal dot-and-whisker comparison. rows: [{key, label, value, lo, hi, highlight?}]
 * The highlighted row uses accent; others neutral. Direct value labels at the right.
 */
export function dotWhiskerChart(body, { rows = [], format = String, height, domain, refValue, refLabel } = {}) {
  return responsive(body, (w) => {
    const hgt = height || rows.length * 44 + 40;
    const labelW = w < 480 ? 92 : Math.min(240, Math.round(w * 0.4));
    const m = { top: 8, right: w < 480 ? 56 : 88, bottom: 28, left: labelW };
    const iw = Math.max(40, w - m.left - m.right), ih = hgt - m.top - m.bottom;
    const svg = svgIn(body, w, hgt, 'Interval comparison');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const x = d3().scaleLinear().domain(domain || [d3().min(rows, (d) => d.lo), d3().max(rows, (d) => d.hi)]).nice().range([0, iw]);
    const y = d3().scaleBand().domain(rows.map((d) => d.key)).range([0, ih]).padding(0.3);
    axisBottom(g.append('g'), x, { ticks: w < 480 ? 3 : 5, format, height: ih });
    if (refValue != null) refLine(g, { x1: x(refValue), x2: x(refValue), y1: -4, y2: ih, label: refLabel, labelAt: 'start', dx: 4, dy: 2 });
    const colored = rows.map((r) => ({ ...r, color: r.highlight ? theme.color.accent : theme.color.muted }));
    const sel = dotWhisker(g, colored, { x, y });
    markSeries(sel, (d) => d.key);
    withTooltip(sel, (d) => ({ title: d.label, rows: [['Mean', format(d.value)], ['95% CI', `${format(d.lo)} – ${format(d.hi)}`]] }));
    g.selectAll('text.rl').data(rows).join('text').attr('class', (d) => (d.highlight ? 'gnm-label gnm-label--strong' : 'gnm-label')).attr('x', -12).attr('y', (d) => y(d.key) + y.bandwidth() / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((d) => truncate(w < 480 ? d.key : d.label, labelW - 16));
    g.selectAll('text.vl').data(rows).join('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', iw + 10).attr('y', (d) => y(d.key) + y.bandwidth() / 2).attr('dy', '0.32em').text((d) => format(d.value));
  });
}

/** Ranked horizontal bars with direct labels. rows: [{label, value, highlight?}] */
export function barList(body, { rows = [], format = String, max, barHeight = 10 } = {}) {
  return responsive(body, (w) => {
    const rowH = 36, hgt = rows.length * rowH;
    const svg = svgIn(body, w, hgt, 'Ranked bars');
    const bw = Math.max(40, w - 72);
    const x = d3().scaleLinear().domain([0, max || d3().max(rows, (d) => d.value)]).range([0, bw]);
    const g = svg.selectAll('g').data(rows).join('g').attr('transform', (d, i) => `translate(0,${i * rowH})`).attr('data-series', (d) => d.label);
    g.append('text').attr('class', (d) => (d.highlight ? 'gnm-label gnm-label--strong' : 'gnm-label')).attr('y', 12).text((d) => d.label);
    g.append('rect').attr('y', 19).attr('width', bw).attr('height', barHeight).attr('rx', 2).attr('fill', 'rgba(185,200,214,0.08)');
    g.append('rect').attr('y', 19).attr('width', (d) => Math.max(1, x(d.value))).attr('height', barHeight).attr('rx', 2).attr('fill', (d) => (d.highlight ? theme.color.accent : theme.color.neutral));
    g.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', w).attr('y', 28).attr('text-anchor', 'end').text((d) => format(d.value));
  });
}
