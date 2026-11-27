/**
 * morph.js: keyed "from previous to new" transitions for charts that are rebuilt by responsive() (views:
 * forecast-lab, network-positioning). v2.1 addendum 2.4–2.6.
 *
 *   const M = morphStore();
 *   // inside a draw(w): after creating marks (final attributes NOT set yet)
 *   morph(M, 'board', w, rowsG, (d) => d.method, { transform: (d, i) => `translate(0,${y(i)})` });
 *   morph(M, 'board', w, dots, (d) => d.method, { cx: (d) => x(d.mase) });
 *   morphAxis(M, 'board-x', w, axisG, x, (g, s) => axisBottom(g, s, {...}));
 *
 * - First draw of a chart id: marks get their final attributes and fade in (opacity 0 → 1, slow token, enter easing).
 * - Later draws at the SAME width (filter / toggle / mode changes): every keyed mark starts at its previous
 *   attribute values and transitions to the new ones (chartTransition, base token): no flash, no redraw from zero.
 *   Marks with a new key fade in; nothing is drawn from zero.
 * - A width change (resize) or reduced motion applies the final values at once.
 * Only transform / opacity and SVG geometry attributes are animated; no layout reads.
 */
import { dur, EASE } from '../../lib/motion.js';

/**
 * A transition scheduled on the selection itself (duration / easing from the motion tokens). Unlike
 * sel.transition(chartTransition()), it does not inherit from a document-level transition, so it also works on marks
 * drawn into a view that is still detached from the document (the router renders off-DOM, then swaps it in).
 */
const tr = (sel, d = 'base', e = 'standard') => sel.transition().duration(dur(d)).ease(EASE[e] || EASE.standard);

export const morphStore = () => new Map();

/** Has this chart id been drawn before at width w? (resize → false: snap, don't animate). */
const seenAt = (store, id, w) => store.has(id) && store.get(id).w === w;

export function morph(store, id, w, sel, keyFn, attrs, { drawIn = true } = {}) {
  const prev = store.get(id);
  const animate = seenAt(store, id, w) && dur('base') > 0;
  const first = !prev;
  const next = prev && prev.w === w ? prev.items : new Map();
  const names = Object.keys(attrs);
  sel.each(function (d, i) {
    const k = `${keyFn(d, i)}|${this.tagName}|${this.getAttribute('class') || ''}`;
    const vals = Object.fromEntries(names.map((n) => [n, typeof attrs[n] === 'function' ? attrs[n].call(this, d, i) : attrs[n]]));
    const old = animate ? next.get(k) : null;
    const node = window.d3.select(this);
    if (old) {
      names.forEach((n) => { if (old[n] != null) node.attr(n, old[n]); else node.attr(n, vals[n]); });
      const t = tr(node, 'base');
      names.forEach((n) => t.attr(n, vals[n]));
    } else {
      names.forEach((n) => node.attr(n, vals[n]));
      if ((first && drawIn) || animate) {
        tr(node.style('opacity', 0), first ? 'slow' : 'base', 'enter').style('opacity', null);
      }
    }
    next.set(k, vals);
  });
  store.set(id, { w, items: next });
  return sel;
}

/** Fade a group in on the chart's first draw only (labels, annotations): opacity only. */
export function drawIn(store, id, w, sel) {
  if (store.has(`${id}::in`)) return sel;
  store.set(`${id}::in`, { w });
  if (dur('slow')) tr(sel.style('opacity', 0), 'slow', 'enter').style('opacity', null);
  return sel;
}

/** Axis that transitions from its previous scale to the new one (same width); draws plainly otherwise. */
export function morphAxis(store, id, w, g, scale, draw) {
  const prev = store.get(id);
  if (prev && prev.w === w && prev.scale && dur('base') > 0) {
    draw(g, prev.scale);
    draw(tr(g, 'base'), scale);
  } else {
    draw(g, scale);
  }
  store.set(id, { w, scale: scale.copy ? scale.copy() : scale });
  return g;
}

/**
 * Draw now (synchronously, so a rebuilt chart never shows an empty frame) and again on every later width change.
 * Replaces responsive(el, draw) where marks morph between states. One layout read at set-up, none in the loop.
 */
export function liveDraw(el, draw) {
  let last = Math.floor(el.getBoundingClientRect().width);
  if (last >= 10) draw(last);
  let raf = 0;
  const ro = new ResizeObserver(([e]) => {
    const w = Math.floor(e.contentRect.width);
    if (w === last || w < 10) return;
    last = w;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => draw(w));
  });
  ro.observe(el);
  return () => { cancelAnimationFrame(raf); ro.disconnect(); };
}
