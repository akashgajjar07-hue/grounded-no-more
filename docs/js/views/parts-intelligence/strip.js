/**
 * Sparse weekly demand as a lollipop strip with the train / selection split marked.
 * Shared by 02 Parts Intelligence (drill-down drawer) and 03 Forecast Lab (small multiples).
 *
 *   demandStrip(host, values, {height, compact, splitAt, trainLabel, selLabel, annotate}) → cleanup()
 *
 * Zero weeks are drawn as faint baseline ticks so "no demand" reads as data, not as missing.
 */
import { drawIn } from './motion-helpers.js';
import { responsive, svgIn, axisLeft, theme, annotate, fmtWeek, fmtInt, withTooltip } from '../../charts/theme.js';

const d3 = () => window.d3;

export function demandStrip(host, values, { height = 160, compact = false, splitAt = 78, trainLabel, selLabel, annot = true, label = 'Weekly demand', animate = false } = {}) {
  const data = values.map((y, x) => ({ x, y: +y || 0 }));
  const maxY = Math.max(1, d3().max(data, (d) => d.y));
  return responsive(host, (w) => {
    const m = compact ? { top: 6, right: 4, bottom: 8, left: 4 } : { top: 26, right: 12, bottom: 26, left: 36 };
    const iw = Math.max(40, w - m.left - m.right), ih = height - m.top - m.bottom;
    const svg = svgIn(host, w, height, label);
    if (animate) drawIn(host, svg); // addendum: draw-in once (slow token)
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const x = d3().scaleLinear().domain([-0.5, data.length - 0.5]).range([0, iw]);
    const y = d3().scaleLinear().domain([0, maxY]).nice(compact ? 2 : 4).range([ih, 0]);
    // selection window shading
    if (splitAt != null && splitAt < data.length) {
      g.append('rect').attr('class', 'strip-sel').attr('x', x(splitAt - 0.5)).attr('y', compact ? 0 : -8).attr('width', x(data.length - 0.5) - x(splitAt - 0.5)).attr('height', ih + (compact ? 0 : 8));
      g.append('line').attr('class', 'strip-split').attr('x1', x(splitAt - 0.5)).attr('x2', x(splitAt - 0.5)).attr('y1', compact ? 0 : -14).attr('y2', ih);
      if (!compact) {
        g.append('text').attr('class', 'strip-zone').attr('x', 0).attr('y', -16).attr('text-anchor', 'start').text(trainLabel || `TRAIN ${fmtWeek(0)}–${fmtWeek(splitAt - 1)}`);
        g.append('text').attr('class', 'strip-zone strip-zone--sel').attr('x', iw).attr('y', -16).attr('text-anchor', 'end').text(w < 420 ? `SEL ${fmtWeek(splitAt)}+` : selLabel || `SELECTION ${fmtWeek(splitAt)}–${fmtWeek(data.length - 1)}`);
      }
    }
    if (!compact) {
      axisLeft(g.append('g'), y, { ticks: Math.min(4, maxY), integer: true });
      const xa = g.append('g').attr('class', 'gnm-axis').attr('transform', `translate(0,${ih})`);
      xa.append('line').attr('x1', 0).attr('x2', iw).attr('stroke', theme.color.lineStrong);
      const ticks = [0, 26, 52, 78, data.length - 1].filter((t, i, a) => t < data.length && a.indexOf(t) === i);
      xa.selectAll('text').data(ticks).join('text').attr('x', (t) => x(t)).attr('y', 16).attr('text-anchor', (t, i) => (i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle')).text(fmtWeek);
    } else {
      g.append('line').attr('x1', 0).attr('x2', iw).attr('y1', ih).attr('y2', ih).attr('stroke', theme.color.lineStrong);
    }
    // zero ticks
    g.append('g').selectAll('line').data(data.filter((d) => d.y === 0)).join('line').attr('class', 'strip-zero').attr('x1', (d) => x(d.x)).attr('x2', (d) => x(d.x)).attr('y1', ih).attr('y2', ih + 3);
    // lollipops
    const nz = data.filter((d) => d.y > 0);
    const col = (d) => (splitAt != null && d.x >= splitAt ? theme.color.accentHi : theme.color.accent);
    const lp = g.append('g').selectAll('g').data(nz).join('g');
    lp.append('line').attr('x1', (d) => x(d.x)).attr('x2', (d) => x(d.x)).attr('y1', ih).attr('y2', (d) => y(d.y)).attr('stroke', col).attr('stroke-width', compact ? 1.25 : 1.5).attr('stroke-opacity', 0.8);
    if (!compact || nz.length <= 30) lp.append('circle').attr('cx', (d) => x(d.x)).attr('cy', (d) => y(d.y)).attr('r', compact ? 2 : 3).attr('fill', theme.color.bg).attr('stroke', col).attr('stroke-width', 1.5);
    withTooltip(lp, (d) => ({ title: fmtWeek(d.x), rows: [['Units demanded', fmtInt(d.y)], ['Window', splitAt != null && d.x >= splitAt ? 'Selection' : 'Training']] }));
    if (!compact && annot && nz.length) {
      const peak = nz.reduce((a, b) => (b.y > a.y ? b : a));
      const ties = nz.filter((d) => d.y === peak.y);
      const px = x(peak.x), py = y(peak.y);
      annotate(g, { x: px, y: py, dx: px > iw * 0.6 ? -26 : 26, dy: py < 20 ? 18 : -10, title: ties.length === 1 ? `Peak ${fmtWeek(peak.x)}` : ties.length === 2 ? `Peaks ${fmtWeek(ties[0].x)} and ${fmtWeek(ties[1].x)}` : `Peak, ${ties.length} weeks (first ${fmtWeek(ties[0].x)})`, sub: `${fmtInt(peak.y)} unit${peak.y === 1 ? '' : 's'}` });
    }
  });
}

/** Summary statistics used by headlines: total, non-zero weeks, zero share. */
export function demandStats(values, from = 0, to = values.length - 1) {
  const s = values.slice(from, to + 1).map((v) => +v || 0);
  const total = s.reduce((a, b) => a + b, 0);
  const nz = s.filter((v) => v > 0).length;
  return { total, nz, weeks: s.length, zeroShare: s.length ? 1 - nz / s.length : 0 };
}
