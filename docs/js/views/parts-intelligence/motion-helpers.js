/**
 * View-level motion helpers for Parts Intelligence and Rotable & Repair (v2.1 addendum). Built only on lib/motion.js
 * tokens: opacity / transform only, rAF tweens, reduced motion → instant.
 */
import { tx as txSel, chartTransition, tween, countUpOnce, reducedMotion } from '../../lib/motion.js';
import { tooltip } from '../../ui.js';

/**
 * Chart draw-in (slow token, 450 ms): the svg's mark layers fade in ONCE per host. Later redraws of the same host
 * (resize) appear at once. → the transition, or null.
 */
export function drawIn(host, svg) {
  if (!host || !svg || host.__drawn) return null;
  host.__drawn = true;
  if (reducedMotion()) return null;
  const node = svg.node ? svg.node() : svg;
  const sel = window.d3.select(node);
  sel.style('opacity', 0);
  return txSel(sel, { duration: 'slow', ease: 'enter' }).style('opacity', 1).on('end', () => node.style.removeProperty('opacity'));
}

/**
 * Number text that interpolates from its previous value to the next one (base token). The first time an element is
 * seen with a key it counts up once (countUpOnce, 600 ms, once per session); later updates tween old → new.
 * The final text is always exactly fmt(value).
 */
export function tweenNumber(el, value, fmt, { key } = {}) {
  if (!el) return;
  const v = +value;
  if (!Number.isFinite(v)) { el.textContent = fmt(value); el.__num = null; return; }
  el.__tw?.cancel?.();
  if (el.__num == null) {
    el.__num = v;
    el.__tw = countUpOnce(el, v, fmt, { key });
    return;
  }
  const from = el.__num;
  el.__num = v;
  if (from === v || reducedMotion()) { el.textContent = fmt(v); return; }
  el.__tw = tween('base', (e) => { el.textContent = fmt(from + (v - from) * e); }, { onEnd: () => { el.textContent = fmt(v); } });
}

/**
 * Keyboard tooltips (addendum audit): a focusable chart mark shows the same tooltip on focus (and on Enter / Space),
 * anchored to the mark, and hides it on blur. Pointer behaviour stays withTooltip's.
 */
export function focusTip(sel, content) {
  const at = (el) => { const r = el.getBoundingClientRect(); return { clientX: r.left + Math.min(r.width, 160) / 2, clientY: r.top + r.height / 2, pageX: r.left + window.scrollX, pageY: r.top + window.scrollY }; };
  return sel
    .on('focus.tip', function (e, d) { tooltip.show(at(this), content(d)); })
    .on('keydown.tip', function (e, d) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); tooltip.show(at(this), content(d)); } else if (e.key === 'Escape') tooltip.hide(); })
    .on('blur.tip', () => tooltip.hide());
}
