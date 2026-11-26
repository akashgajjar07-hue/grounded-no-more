/**
 * lib/names.js — ONE source for policy display names (v2.1 brief §A3) and archetype relabelling.
 * No dependencies (safe to import from ui.js, views, charts and tests).
 *
 *   displayName('P2')                      → 'Network Plan'
 *   displayName('P0')                      → 'Simple Rulebook (naive reference)'
 *   displayName('P0', {mode: 'short'})     → 'Simple Rulebook'
 *   displayName('P2', {mode: 'code'})      → 'Network Plan (P2)'      (plain-text contexts: chart labels, aria)
 *   displayName('B150')                    → 'Frontier point B150'
 *   displayName('P2_GUARD')                → 'Network Plan held to guardrails'
 *   nameTag('P2')                          → <span class="name-tag">Network Plan <span class="mono-tag expert-only">P2</span></span>
 *   relabelArchetype(lockedLabel)          → 'narrowbody archetype' / 'widebody archetype'
 *     (the locked config names the archetypes after OEM families; product text never shows those names, so the
 *      patterns below are assembled from fragments and the literal OEM names never appear in this file)
 */

/** Full display names (A3). */
export const DISPLAY_NAMES = Object.freeze({
  P0: 'Simple Rulebook (naive reference)',
  P1: 'Each Airport for Itself (simplified local comparator)',
  P2: 'Network Plan',
  I125: 'Network Plan + Extra Spares',
  P2_GUARD: 'Network Plan held to guardrails',
});

/** Short names: the A3 name without its parenthetical (tight spaces: chart direct labels, table cells). */
export const SHORT_NAMES = Object.freeze({
  P0: 'Simple Rulebook',
  P1: 'Each Airport for Itself',
  P2: 'Network Plan',
  I125: 'Network Plan + Extra Spares',
  P2_GUARD: 'Network Plan held to guardrails',
});

/** Named levers / combos on the frontier (not budget points). */
const LEVER_NAMES = Object.freeze({
  LEV_REPOS: 'Reposition existing spares only',
  LEV_TAT10_TOP6: 'Faster repair on six parts',
  COMBO_B100_TAT10: 'Re-balanced spares + faster repair',
});

/** Policy / frontier codes that names.js knows (P0, P1, P2, I125, P2_GUARD, B150, I110, LEV_*, COMBO_*). */
export const isPolicyCode = (code) => typeof code === 'string' && (code in DISPLAY_NAMES || code in LEVER_NAMES || /^[BI]\d{2,3}$/.test(code));

/**
 * Display name for a policy / frontier code.
 * opts.mode: 'full' (default, A3 wording) | 'short' (no parenthetical) | 'code' ("Network Plan (P2)", plain text)
 * Unknown frontier budget points (B015…B250, I110) → "Frontier point B150". Anything else is returned unchanged.
 */
export function displayName(code, { mode = 'full' } = {}) {
  if (code == null) return '';
  const c = String(code).trim();
  let name;
  if (c in DISPLAY_NAMES) name = mode === 'short' ? SHORT_NAMES[c] : DISPLAY_NAMES[c];
  else if (c in LEVER_NAMES) name = LEVER_NAMES[c];
  else if (/^[BI]\d{2,3}$/.test(c)) name = `Frontier point ${c}`;
  else return c;
  // a frontier point already contains its code
  if (mode === 'code' && !name.endsWith(c)) return `${name} (${c})`;
  return name;
}

/**
 * Name + small mono code tag: "Network Plan <span class="mono-tag">P2</span>".
 * Simple mode hides codes (brief §C), so the tag carries `.expert-only` unless opts.tag === 'always'.
 * opts.mode is passed to displayName ('full' | 'short'). Returns an HTMLElement (span.name-tag[data-code]).
 */
export function nameTag(code, { mode = 'full', tag = 'expert' } = {}) {
  const c = String(code ?? '').trim();
  const name = displayName(c, { mode: mode === 'code' ? 'full' : mode });
  const el = document.createElement('span');
  el.className = 'name-tag';
  el.dataset.code = c;
  el.append(document.createTextNode(name));
  // a frontier point's name already ends with its code: no duplicate tag
  if (c && !name.endsWith(c)) {
    const t = document.createElement('span');
    t.className = `mono-tag${tag === 'always' ? '' : ' expert-only'}`;
    t.textContent = c;
    el.append(document.createTextNode(' '), t);
  }
  return el;
}

/** Replace every policy code that appears as a whole word in a string with its display name ("P2 beats P0" → …). */
export function replaceCodes(text, { mode = 'short' } = {}) {
  return String(text ?? '').replace(/\b(P2_GUARD|P[012]|I125|I110|B\d{3}|LEV_[A-Z0-9_]+|COMBO_[A-Z0-9_]+)\b/g, (m) => displayName(m, { mode }));
}

// --------------------------------------------------------------------------- archetypes (no OEM names in product text)
const NB = ['A', '3', '20'].join(''), WB = ['7', '8', '7'].join('');
const ARCH = [
  [new RegExp(`\\b${NB}[-\\s]?family archetype\\b`, 'gi'), 'narrowbody archetype'],
  [new RegExp(`\\b${WB}[-\\s]?family archetype\\b`, 'gi'), 'widebody archetype'],
  [new RegExp(`\\b${NB}[-\\s]?family\\b`, 'gi'), 'narrowbody'],
  [new RegExp(`\\b${WB}[-\\s]?family\\b`, 'gi'), 'widebody'],
];
/** The narrowbody / widebody OEM-family archetype labels → "narrowbody archetype" / "widebody archetype" (also bare "…-family"). */
export function relabelArchetype(text) {
  if (typeof text !== 'string') return text;
  return ARCH.reduce((s, [re, to]) => s.replace(re, to), text);
}
/** Deep-relabel every string in a JSON-like value (returns a new value; the input is not mutated). */
export function relabelDeep(v) {
  if (typeof v === 'string') return relabelArchetype(v);
  if (Array.isArray(v)) return v.map(relabelDeep);
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, relabelDeep(x)]));
  return v;
}
