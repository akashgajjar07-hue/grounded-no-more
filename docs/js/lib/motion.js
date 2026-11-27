/**
 * lib/motion.js — THE motion tokens and helpers (mirror of docs/css/motion.css). No dependencies.
 *
 * Rules: animate only transform / opacity; JS animation runs on requestAnimationFrame; will-change only while
 * animating; no layout reads inside animation loops; prefers-reduced-motion → no movement, instant state changes
 * (the guided tour still auto-advances).
 * v2.2 tour quiet mode: while the guided tour is open (html.tour-active), reducedMotion() is true as well, so every
 * helper here (dur, tx, chartTransition, tween, countUpOnce, staggerIn, flip) goes instant: chart draw-ins, count-ups
 * and card rises never replay behind the tour card. prefersReducedMotion() is the reader's setting alone (the tour's
 * own fades use it).
 *
 *   import { MOTION, reducedMotion, dur, countUpOnce, chartTransition, throttleRAF, tooltipFade, staggerIn } from '../lib/motion.js';
 *   countUpOnce(valueEl, 1480, (v) => fmtInt(v), { key: 'mission-aog-cut' });   // 600 ms ease-out, once per key per session
 *   sel.transition(chartTransition()).attr('y', …);                            // D3 transition with the tokens
 *   chartTransition({ duration: 'slow', ease: 'enter' })                        // named token or ms
 *   slider.addEventListener('input', throttleRAF((e) => redraw(+e.target.value)));
 *   tooltipFade.show(tipEl); tooltipFade.follow(tipEl, evt); tooltipFade.hide(tipEl);
 */
export const MOTION = Object.freeze({
  fast: 150, base: 250, slow: 450, hero: 1200,
  stagger: 40, staggerMax: 6, rise: 8, countUp: 600, tourStep: 7000,
  ease: Object.freeze({ standard: 'cubic-bezier(0.2, 0, 0, 1)', enter: 'cubic-bezier(0, 0, 0, 1)', exit: 'cubic-bezier(0.3, 0, 1, 1)' }),
});

/** The reader's prefers-reduced-motion setting (nothing else). */
export const prefersReducedMotion = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; } };
/** The guided tour is open: page animations go instant (html.tour-active, set by storyMode in ui.js). */
export const tourActive = () => { try { return document.documentElement.classList.contains('tour-active'); } catch { return false; } };
/** No page motion: the reader asked for reduced motion, or the guided tour is open. */
export const reducedMotion = () => prefersReducedMotion() || tourActive();

/** Duration in ms for a token name ('fast' | 'base' | 'slow' | 'hero') or a number; 0 under reduced motion / the tour. */
export const dur = (d = 'base') => (reducedMotion() ? 0 : typeof d === 'number' ? d : MOTION[d] ?? MOTION.base);

/** CSS cubic-bezier → easing function t∈[0,1] → progress (Newton–Raphson on x, as browsers do). */
export function bezier(x1, y1, x2, y2) {
  const A = (a, b) => 1 - 3 * b + 3 * a, B = (a, b) => 3 * b - 6 * a, C = (a) => 3 * a;
  const calc = (t, a, b) => ((A(a, b) * t + B(a, b)) * t + C(a)) * t;
  const slope = (t, a, b) => 3 * A(a, b) * t * t + 2 * B(a, b) * t + C(a);
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) { const s = slope(t, x1, x2); if (Math.abs(s) < 1e-6) break; t -= (calc(t, x1, x2) - x) / s; }
    t = Math.min(1, Math.max(0, t));
    return calc(t, y1, y2);
  };
}
export const EASE = Object.freeze({ standard: bezier(0.2, 0, 0, 1), enter: bezier(0, 0, 0, 1), exit: bezier(0.3, 0, 1, 1) });

/** Wrap fn so it runs at most once per animation frame with the latest arguments (sliders, pointer moves). */
export function throttleRAF(fn) {
  let id = 0, args = null;
  const run = () => { id = 0; const a = args; args = null; fn(...a); };
  const wrapped = (...a) => { args = a; if (!id) id = requestAnimationFrame(run); };
  wrapped.cancel = () => { if (id) cancelAnimationFrame(id); id = 0; args = null; };
  wrapped.flush = () => { if (id) { cancelAnimationFrame(id); run(); } };
  return wrapped;
}

/** Run a rAF tween: onFrame(easedProgress, rawProgress). Returns {cancel}. Reduced motion → one frame at 1. */
export function tween(ms, onFrame, { ease = 'standard', onEnd } = {}) {
  const fn = typeof ease === 'function' ? ease : EASE[ease] || EASE.standard;
  const d = dur(ms);
  let id = 0, t0 = 0, done = false;
  const step = (t) => {
    if (!t0) t0 = t;
    const p = d ? Math.min(1, (t - t0) / d) : 1;
    onFrame(fn(p), p);
    if (p < 1) id = requestAnimationFrame(step); else { done = true; onEnd?.(); }
  };
  id = requestAnimationFrame(step);
  return { cancel() { if (!done) cancelAnimationFrame(id); done = true; } };
}

// --------------------------------------------------------------------------- count-up (once per element per session)
const counted = new Set();
const SKEY = 'gnm-countup';
function seen(key) {
  if (counted.has(key)) return true;
  try { return (JSON.parse(sessionStorage.getItem(SKEY) || '[]')).includes(key); } catch { return false; }
}
function remember(key) {
  counted.add(key);
  try { const a = JSON.parse(sessionStorage.getItem(SKEY) || '[]'); if (!a.includes(key)) { a.push(key); sessionStorage.setItem(SKEY, JSON.stringify(a.slice(-200))); } } catch { /* storage blocked: in-memory only */ }
}
/**
 * Count a number up from 0 to value in 600 ms (ease-out), ONCE per key per browser session. Re-renders (route
 * changes, mode toggles) and reduced motion print the final value immediately. The final text is always exactly
 * fmt(value). key: opts.key ?? el.dataset.countup ?? el.id (required for "once per session" across re-renders; without
 * one the element itself is the key, so a re-rendered element animates again).
 * Returns {cancel}.
 */
export function countUpOnce(el, value, fmt = (v) => String(Math.round(v)), { key, from = 0 } = {}) {
  const k = key ?? el?.dataset?.countup ?? (el?.id || null);
  const final = () => { el.textContent = fmt(value); };
  const v = +value;
  if (!el || !Number.isFinite(v) || reducedMotion() || (k && seen(k)) || el.__gnmCounted) { if (el) final(); return { cancel() {} }; }
  if (k) remember(k);
  el.__gnmCounted = true;
  el.dataset.counting = 'true';
  el.textContent = fmt(from);
  return tween(MOTION.countUp, (e) => { el.textContent = fmt(from + (v - from) * e); }, { ease: 'enter', onEnd: () => { final(); delete el.dataset.counting; } });
}

// --------------------------------------------------------------------------- D3
/**
 * A d3 transition carrying the motion tokens: chartTransition({duration: 'base'|'slow'|ms, ease: 'standard'|'enter'|'exit', delay, name}).
 * Use as sel.transition(chartTransition()) (shared timing) or chartTransition().… directly. Reduced motion → 0 ms.
 */
/**
 * Preferred: a transition created ON the selection (never inherits a document-level transition, so a newer
 * transition elsewhere can't cancel its parent and throw "transition N not found" mid-navigation).
 */
export function tx(sel, { duration = 'base', ease = 'standard', delay = 0, name } = {}) {
  const t = sel.transition(name).duration(dur(duration)).ease(EASE[ease] || EASE.standard);
  return delay && !reducedMotion() ? t.delay(delay) : t;
}

/** @deprecated for inheritance (`sel.transition(chartTransition())`): use tx(sel) instead. */
export function chartTransition({ duration = 'base', ease = 'standard', delay = 0, name } = {}) {
  const d3 = window.d3;
  const t = d3.transition(name).duration(dur(duration)).ease(EASE[ease] || EASE.standard);
  return delay && !reducedMotion() ? t.delay(delay) : t;
}

// --------------------------------------------------------------------------- tooltips
/**
 * Tooltip fade (150 ms opacity via CSS class `.is-on` + motion.css) and lag-free cursor tracking: follow() writes a
 * transform once per frame from the latest pointer event; the tooltip's size is measured once on show().
 */
export const tooltipFade = {
  show(el) { if (!el) return; el.__tipSize = null; el.classList.add('is-on'); },
  hide(el) { el?.classList.remove('is-on'); },
  follow(el, evt, { pad = 14 } = {}) {
    if (!el) return;
    el.__tipEvt = { x: evt.clientX ?? 0, y: evt.clientY ?? 0 };
    if (el.__tipRaf) return;
    el.__tipRaf = requestAnimationFrame(() => {
      el.__tipRaf = 0;
      const { x: cx, y: cy } = el.__tipEvt;
      if (!el.__tipSize) { const r = el.getBoundingClientRect(); el.__tipSize = { w: r.width, h: r.height }; }
      const { w, h } = el.__tipSize;
      let x = cx + pad, y = cy + pad;
      if (x + w > innerWidth - 8) x = cx - w - pad;
      if (y + h > innerHeight - 8) y = cy - h - pad;
      el.style.left = '0px'; el.style.top = '0px';
      el.style.transform = `translate3d(${Math.round(Math.max(8, x))}px, ${Math.round(Math.max(8, y))}px, 0)`;
    });
  },
};

// --------------------------------------------------------------------------- workspace entry
/**
 * Stagger the first `max` (6) matching elements in: each gets class `motion-stagger` and --stagger-i (40 ms steps).
 * The router calls it on #view after every render; views may call it on their own sub-sections.
 */
export function staggerIn(root, selector = '.card', { max = MOTION.staggerMax } = {}) {
  if (!root || reducedMotion()) return;
  [...root.querySelectorAll(selector)].slice(0, max).forEach((el, i) => {
    el.style.setProperty('--stagger-i', String(i));
    el.classList.add('motion-stagger');
    el.addEventListener('animationend', () => el.classList.remove('motion-stagger'), { once: true });
  });
}

/**
 * FLIP an element from its previous rect to its current layout using transform only (450 ms standard).
 * Call after the element's final position/size is applied. from = {left, top, width, height}.
 * opts.scale: false → translate only (for elements whose content reflows, e.g. a text card).
 */
export function flip(el, from, { duration = 'slow', scale = true } = {}) {
  if (!el || !from || reducedMotion()) return;
  const to = el.getBoundingClientRect();
  if (!to.width || !to.height) return;
  const sx = scale ? from.width / to.width : 1, sy = scale ? from.height / to.height : 1;
  const dx = from.left - to.left, dy = from.top - to.top;
  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && Math.abs(sx - 1) < 0.01 && Math.abs(sy - 1) < 0.01) return;
  el.style.transformOrigin = '0 0';
  el.style.transition = 'none';
  el.style.willChange = 'transform';
  el.style.transform = `translate(${dx}px, ${dy}px) scale(${sx || 0.001}, ${sy || 0.001})`;
  void el.offsetWidth; // one style flush per FLIP (not in a loop)
  el.style.transition = `transform ${dur(duration)}ms ${MOTION.ease.standard}`;
  el.style.transform = '';
  const tok = (el.__flipTok = (el.__flipTok || 0) + 1);
  const end = () => { el.removeEventListener('transitionend', end); if (el.__flipTok !== tok) return; el.style.willChange = ''; el.style.transition = ''; };
  el.addEventListener('transitionend', end);
  setTimeout(end, dur(duration) + 50);
}
