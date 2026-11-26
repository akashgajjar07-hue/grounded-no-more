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
    accent: '#22C7B8',        // accent 1 — primary series / recommended
    accent2: '#C47F52',       // accent 2 — capital, comparison or baseline
    accentHi: '#7FF3E6',
    neutral: '#6B7C8F',       // context series (non-text)
    neutralSoft: 'rgba(185,200,214,0.35)',
    ok: '#22C7B8', review: '#F5B942', urgent: '#E76B64', unknown: '#6B7C8F',
    prov: { REAL: '#22C7B8', DERIVED: '#B9C8D6', ASSUMED: '#F5B942', SIMULATED: '#C47F52' },
  },
  font: { display: "'Space Grotesk', system-ui, sans-serif", ui: "'Inter', system-ui, sans-serif", mono: "'IBM Plex Mono', ui-monospace, monospace" },
  margin: { top: 16, right: 64, bottom: 32, left: 52 },
  motion: { ms: 300, ease: 'cubic-bezier(0.16, 1, 0.3, 1)' },
};
export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// --------------------------------------------------------------------------- formatters
const trim = (s) => s.replace(/\.0(?=[^\d]|$)/, '');
/** AED 4.8M / AED 820k / AED 950 (accepts negative values). */
export function fmtAED(v, { digits = 1, sign = false } = {}) {
  if (v == null || Number.isNaN(+v)) return '—';
  const a = Math.abs(v);
  const s = v < 0 ? '−' : sign && v > 0 ? '+' : '';
  if (a >= 1e9) return `AED ${s}${trim((a / 1e9).toFixed(digits))}B`;
  if (a >= 1e6) return `AED ${s}${trim((a / 1e6).toFixed(digits))}M`;
  if (a >= 1e3) return `AED ${s}${Math.round(a / 1e3)}k`;
  return `AED ${s}${Math.round(a)}`;
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
/** Simulated week label: fmtWeek(104) = "W104". Simulated calendar, not real dates. */
export const fmtWeek = (w) => `W${w}`;
/** Pick a formatter from a KPI unit string. */
export const fmtByUnit = (unit) => (unit === 'AED' ? fmtAED : unit === '%' ? fmtPct : unit === 'h' ? fmtHours : unit === 'd' ? fmtDays : fmtInt);

// --------------------------------------------------------------------------- frame
/**
 * chartFrame(host, {headline, subtitle, provenance, source, table: {columns, rows}, story})
 * Renders headline + subtitle + provenance chip + chart body + source + "View data" table.
 * Returns {root, body, setTable(columns, rows)}. Draw your chart into `body`.
 */
export function chartFrame(host, { headline, subtitle, provenance, source, table, story, minHeight } = {}) {
  const body = h('div', { class: 'chart-body', style: minHeight ? { minHeight: `${minHeight}px` } : undefined });
  const details = h('details', { class: 'chart-data' }, h('summary', {}, 'View data'));
  const root = h(
    'figure',
    { class: 'chart-frame', dataset: story ? { story } : undefined },
    h('div', { class: 'chart-head' }, h('div', {}, h('figcaption', { class: 'chart-headline' }, headline || ''), subtitle ? h('div', { class: 'chart-subtitle' }, subtitle) : null), provenance ? provChip(provenance) : null),
    body,
    h('div', { class: 'chart-foot' }, source ? h('span', { class: 'chart-source' }, `Source: ${source}`) : h('span'), details)
  );
  const setTable = (columns, rows) => {
    details.querySelector('.table-wrap')?.remove();
    details.append(dataTable({ columns, rows, dense: true, caption: headline }));
  };
  if (table) setTable(table.columns, table.rows);
  host.append(root);
  return { root, body, setTable };
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

/** Direct label at (x, y) in px. Use instead of legends. */
export function directLabel(g, { x, y, text, color = theme.color.muted, anchor = 'start', strong = false, dy = '0.32em' }) {
  return g.append('text').attr('x', x).attr('y', y).attr('dy', dy).attr('text-anchor', anchor).attr('class', strong ? 'gnm-label gnm-label--strong' : 'gnm-label').style('fill', color || null).text(text);
}

/** Spread direct labels vertically so they never overlap (min gap in px). Mutates and returns. */
export function dodge(labels, gap = 14) {
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < gap) labels[i].y = labels[i - 1].y + gap;
  return labels;
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
    series.forEach((s, i) => {
      const color = s.color || (i === 0 ? theme.color.accent : i === 1 ? theme.color.accent2 : theme.color.neutralSoft);
      const primary = s.primary ?? i === 0;
      line(g, s.values, { x, y, color, width: s.width || (primary ? 2 : 1.5), dash: s.dash, curve: s.curve });
      const last = s.values.at(-1);
      if (s.label) labels.push({ x: x(last.x) + 8, y: y(last.y), text: s.label, color: primary ? color : theme.color.muted, strong: primary });
    });
    if (w >= 480) dodge(labels, 14).forEach((l) => directLabel(g, l));
    if (w < 480 && series.some((s) => s.label)) {
      // narrow: labels move to a compact key above the plot
      series.forEach((s, i) => directLabel(g, { x: i * 120, y: -6, text: `— ${s.label}`, color: s.color || (i === 0 ? theme.color.accent : theme.color.accent2) }));
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
    if (refValue != null) {
      g.append('line').attr('x1', x(refValue)).attr('x2', x(refValue)).attr('y1', -4).attr('y2', ih).attr('stroke', theme.color.review).attr('stroke-dasharray', '3 3');
      if (refLabel) directLabel(g, { x: x(refValue) + 4, y: -2, text: refLabel, color: theme.color.review, dy: '0' });
    }
    const colored = rows.map((r) => ({ ...r, color: r.highlight ? theme.color.accent : theme.color.muted }));
    const sel = dotWhisker(g, colored, { x, y });
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
    const g = svg.selectAll('g').data(rows).join('g').attr('transform', (d, i) => `translate(0,${i * rowH})`);
    g.append('text').attr('class', (d) => (d.highlight ? 'gnm-label gnm-label--strong' : 'gnm-label')).attr('y', 12).text((d) => d.label);
    g.append('rect').attr('y', 19).attr('width', bw).attr('height', barHeight).attr('rx', 2).attr('fill', 'rgba(185,200,214,0.08)');
    g.append('rect').attr('y', 19).attr('width', (d) => Math.max(1, x(d.value))).attr('height', barHeight).attr('rx', 2).attr('fill', (d) => (d.highlight ? theme.color.accent : theme.color.neutral));
    g.append('text').attr('class', 'gnm-label').attr('font-family', theme.font.mono).attr('x', w).attr('y', 28).attr('text-anchor', 'end').text((d) => format(d.value));
  });
}
