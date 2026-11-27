/**
 * lib/mode.js — Simple / Expert reading mode (v2.1 brief §C). No dependencies.
 *
 *   import { getMode, isSimple, setMode, onMode } from '../lib/mode.js';
 *   getMode()            → 'simple' | 'expert'   (default 'simple')
 *   isSimple()           → boolean
 *   setMode('expert')    → persists (localStorage "gnm-mode", try/catch), sets <body class="mode-expert">,
 *                          dispatches `gnm:mode` on document ({detail: {mode}})
 *   const off = onMode((mode) => …)   subscribe; call off() in your view cleanup
 *
 * The router (app.js) re-renders the current view on `gnm:mode`, so most views need nothing: read getMode() / use
 * term() while rendering. A view that wants to update in place exports `onMode(mode, ctx)` and returns anything
 * but `false` (then the router does not re-render).
 * CSS utilities: `.simple-only` (hidden in Expert) and `.expert-only` (hidden in Simple), in components.css.
 */
export const MODE_KEY = 'gnm-mode';
export const MODES = ['simple', 'expert'];
export const MODE_EVENT = 'gnm:mode';

let mode = read();

function read() {
  try {
    const v = localStorage.getItem(MODE_KEY);
    return MODES.includes(v) ? v : 'simple';
  } catch { return 'simple'; }
}

function applyClass() {
  const b = document.body;
  if (!b) return;
  b.classList.toggle('mode-simple', mode === 'simple');
  b.classList.toggle('mode-expert', mode === 'expert');
  document.documentElement.dataset.mode = mode;
}

export const getMode = () => mode;
export const isSimple = () => mode === 'simple';
export const isExpert = () => mode === 'expert';

/** Pick a value by mode: byMode('plain words', 'expert words'). */
export const byMode = (simple, expert) => (mode === 'simple' ? simple : expert);

/** Set the mode (no-op if unchanged unless opts.force). Persists, updates the body class, fires `gnm:mode`. */
export function setMode(m, { force = false } = {}) {
  const next = MODES.includes(m) ? m : 'simple';
  if (next === mode && !force) { applyClass(); return mode; }
  mode = next;
  try { localStorage.setItem(MODE_KEY, mode); } catch { /* private window / blocked storage: session-only */ }
  applyClass();
  document.querySelectorAll('.mode-toggle').forEach(syncToggle);
  document.dispatchEvent(new CustomEvent(MODE_EVENT, { detail: { mode } }));
  return mode;
}

/** Subscribe to mode changes. Returns an unsubscribe function. */
export function onMode(fn) {
  const h = (e) => fn(e.detail.mode);
  document.addEventListener(MODE_EVENT, h);
  return () => document.removeEventListener(MODE_EVENT, h);
}

/** Apply the stored mode to <body> (the shell calls this once at boot, before the first render). */
export function initMode() { mode = read(); applyClass(); return mode; }

function syncToggle(g) {
  g.querySelectorAll('[role="radio"]').forEach((b) => {
    const on = b.dataset.mode === mode;
    b.setAttribute('aria-checked', String(on));
    b.tabIndex = on ? 0 : -1;
  });
}

/**
 * The top-bar toggle: an ARIA radiogroup (segmented control) "Simple | Expert".
 * Keyboard: Tab focuses the checked option; ←/→/↑/↓ (and Home/End) move AND select; Space/Enter select.
 */
export function modeToggle({ label = 'Reading mode' } = {}) {
  const g = document.createElement('div');
  g.className = 'seg mode-toggle';
  g.setAttribute('role', 'radiogroup');
  g.setAttribute('aria-label', label);
  const opts = [['simple', 'Simple', 'Plain-English wording'], ['expert', 'Expert', 'Planner terms, codes and methods']];
  opts.forEach(([m, text, title]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('role', 'radio');
    b.dataset.mode = m;
    b.title = title;
    b.textContent = text;
    b.addEventListener('click', () => setMode(m));
    g.append(b);
  });
  g.addEventListener('keydown', (e) => {
    const keys = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1, Home: 'first', End: 'last' };
    if (!(e.key in keys)) return;
    e.preventDefault();
    const i = MODES.indexOf(mode), k = keys[e.key];
    const next = k === 'first' ? MODES[0] : k === 'last' ? MODES[MODES.length - 1] : MODES[(i + k + MODES.length) % MODES.length];
    setMode(next);
    g.querySelector(`[data-mode="${next}"]`)?.focus();
  });
  syncToggle(g);
  return g;
}

/**
 * v2.2 shared note for a page whose wording does not change with the reading mode. Put it directly under the page
 * head: `el.append(pageHead(...), sameInBothModesNote())`. Returns a <p data-role="mode-same">.
 */
export const SAME_IN_BOTH_MODES = 'This page reads the same in Simple and Expert.';
export function sameInBothModesNote(text = SAME_IN_BOTH_MODES) {
  const p = document.createElement('p');
  p.className = 'mode-same-note t-13 muted';
  p.dataset.role = 'mode-same';
  p.textContent = text;
  return p;
}
