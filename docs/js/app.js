/**
 * app.js — shell + hash router for GROUNDED NO MORE.
 *
 * Routes are deep-linkable: #/parts?ata=32&pn=GN-32-R014
 * Each route lazy-loads its view module from js/views/ and the JSON files the module declares:
 *
 *   // js/views/parts-intelligence.js
 *   export const data = ['parts', 'demand_history'];       // loaded before render()
 *   export async function render(el, ctx) { ... }           // may return a cleanup function
 *
 * ctx = {route, params, data, navigate(hash), setParams(obj), load(name), buildHash(id, params)}
 *
 * Overlays: before any view renders (link click, ctx.navigate, location.hash, Back/Forward, a query change that
 * re-renders) the router calls closeAllOverlays() from ui.js, so no drawer, modal, tooltip, scrim, focus trap or
 * scroll lock survives into the next view. Story mode is exempt (it drives navigation itself).
 * Optional same-route hook: a view may `export function onParams(params, ctx)`. When only the query of the
 * current route changes and the hook returns anything but `false`, the router does NOT re-render; overlays opened
 * with `persistOnParams: true` stay open, all others close. Without the hook the view re-renders.
 * ctx.setParams of a view that is no longer current is ignored (a stale drawer onClose can't rewrite the URL of the
 * next view). ctx.navigate always works (story mode is driven by a view's ctx.navigate).
 * Keyboard: 1–8 jump between workspaces, 0 = Data & Method, ? = shortcuts, S = story mode,
 * Esc closes overlays.
 * v2.1 reading mode (lib/mode.js): a Simple | Expert toggle sits in the top bar. On `gnm:mode` the router re-renders
 * the current view in place (scroll position kept). A view may `export function onMode(mode, ctx)` and return
 * anything but `false` to update itself instead. Before every view render the router calls resetTermUses(), so a
 * term() shows its grey "(expert term)" bracket on its first use in each view. 1–8 / 0 / S also work while a drawer or modal is open (overlays close first, then the
 * shell navigates). A skip link jumps to the main content.
 *
 * v2.2 LINK + SECTION CONTRACT (every internal link works every time)
 *  1. Section targets. `?section=<name>` on any route names an in-page target. The ROUTER owns the scroll + focus:
 *     it resolves the target, scrolls it to the top of the viewport (honouring CSS scroll-margin-top) AFTER the view
 *     has rendered and been revealed, keeps it there while late layout (charts, entry animation) settles (≈0.7 s,
 *     stops at once on user wheel / touch / key / pointer input), and moves focus to the target heading.
 *     Target resolution, first hit wins (all inside #view):
 *       a. the view's optional `export function sectionTarget(section, params, ctx)` → Element | null
 *       b. `[data-section="<name>"]`          (preferred markup for views)
 *       c. `#<name>`
 *       d. the shortest id ending in `-<name>` (e.g. ab-mro), then the shortest id starting with `<name>-`
 *     Focus goes to the target if it is a heading, else to its first h1–h4, else to the target itself (tabindex=-1 is
 *     added where needed, focus never scrolls). Views need not scroll for ?section= themselves; if they still do, the
 *     router runs after them and lands on the same target.
 *  2. When it happens. After every render (link click, ctx.navigate, location.hash, fresh load, hard refresh,
 *     Back/Forward), after a same-route query change, and on a repeated click of a link whose href equals the current
 *     URL (no hashchange fires: the router intercepts the click). history.scrollRestoration is 'manual'.
 *     Without a section a new route starts at the top with focus on #view (unless an overlay the view opened holds it).
 *  3. Same-route hook `onParams(params, ctx)`: the router calls it on same-route query changes AND on repeated clicks of
 *     a link to the current URL (params unchanged). Return `false` to ask for a full re-render. A view that exports
 *     onParams (or `export const ownsSections = true`) OWNS its section scrolling: the router then never scrolls to a
 *     section on that route itself (it still resets to the top and reveals the page; the view jumps after the reveal,
 *     e.g. with views/about/section.js jumpTo(), which waits for the reveal). A view may also catch repeated clicks
 *     inside its own root and call preventDefault(); the router leaves defaultPrevented clicks alone. Without the hook a
 *     change of `section` alone never re-renders; any other change (or a repeated click on a link with other params,
 *     e.g. #/parts?pn=…) re-renders the view. A repeated click on a plain route link (no params) scrolls to the top and
 *     focuses #view.
 *  4. In-page anchors (`href="#some-id"`, e.g. the skip link) never reach the hash router: the router scrolls to and
 *     focuses that element and keeps the route URL. A view that handles its own anchors calls preventDefault().
 *  5. Hooks for tests and the tour: `window.__gnmRendered()` → Promise that resolves when the current route's render
 *     (or same-route update) has finished and the view is revealed and scrolled; `window.__gnmRevealSection(name)`
 *     → re-runs the section scroll on the current view (returns true when a target was found). Tests also use
 *     `window.__gnmSectionTarget(name)` (the resolved element) and `window.__gnmRenderCount()` (bumps once per finished
 *     render, same-route update, repeated click or in-page anchor jump).
 */
import { h, icon, ensureSprite, fixtureChip, disclaimer, modal, kbd, storyMode, stateBlock, closeAllOverlays, openOverlayCount, slidingThumb } from './ui.js';
import { staggerIn } from './lib/motion.js';
import { loadMany, load, onFixture } from './data.js';
import { initMode, modeToggle, MODE_EVENT } from './lib/mode.js';
import { resetTermUses, hideTermTip } from './lib/glossary.js';

export const ROUTES = [
  { id: 'mission', num: '01', label: 'Mission Control', icon: 'aircraft', module: './views/mission-control.js' },
  { id: 'parts', num: '02', label: 'Parts Intelligence', icon: 'part', module: './views/parts-intelligence.js' },
  { id: 'forecast', num: '03', label: 'Forecast Lab', icon: 'flask', module: './views/forecast-lab.js' },
  { id: 'rotables', num: '04', label: 'Rotable & Repair', icon: 'rotable', module: './views/rotable-repair.js' },
  { id: 'network', num: '05', label: 'Network Positioning', icon: 'route', module: './views/network-positioning.js' },
  { id: 'capital', num: '06', label: 'Capital Optimiser', icon: 'capital', module: './views/capital-optimiser.js' },
  { id: 'aog', num: '07', label: 'AOG Response Lab', icon: 'clock', module: './views/aog-response-lab.js' },
  { id: 'actions', num: '08', label: 'Planner Action Centre', icon: 'inbox', module: './views/planner-action-centre.js' },
  { id: 'method', num: '—', label: 'Data & Method', icon: 'book', module: './views/data-method.js', key: '0' },
  { id: 'about', num: '—', label: 'About', icon: 'info', module: './views/about.js' },
  // v2.1 project pages (glossary uses lib/glossary.js glossaryEntries())
  { id: 'glossary', num: '—', label: 'Glossary', icon: 'book', module: './views/glossary.js' },
  { id: 'planner', num: '—', label: 'The Planner Behind the Project', icon: 'info', module: './views/planner.js' },
];
// keyboard: 1–8 keep their original workspace numbers (deep links and muscle memory stay stable), 0 = Data & Method
ROUTES.forEach((r) => { if (!r.key && /^\d\d$/.test(r.num)) r.key = String(+r.num); });
/** Wave A navigation groups (display order); the route ids, numbers and shortcut keys are unchanged. */
export const NAV_GROUPS = [
  { id: 'operations', label: 'Operations', items: ['mission', 'actions', 'aog'] },
  { id: 'material', label: 'Material intelligence', items: ['parts', 'forecast', 'rotables'] },
  { id: 'strategic', label: 'Strategic planning', items: ['network', 'capital'] },
  { id: 'project', label: 'Project', items: ['tour', 'method', 'about', 'glossary', 'planner'] },
];
const groupOf = (id) => NAV_GROUPS.find((g) => g.items.includes(id));
const DEFAULT = 'mission';
const SITE = 'GROUNDED NO MORE';

const $ = (s) => document.querySelector(s);
let cleanup = null;
let renderSeq = 0;
let current = null; // {id, mod, ctx, seq} of the rendered view
let helpModal = null;
let renderedResolve = null;
// v2.2: window.__gnmRendered() hook: a promise per render, resolved when the view is revealed and scrolled
let renderedDone = Promise.resolve();
let renderedDoneResolve = null;
function beginRendered() {
  if (!renderedDoneResolve) renderedDone = new Promise((r) => { renderedDoneResolve = r; });
}
let renderCount = 0;
function endRendered() {
  renderCount += 1;
  const r = renderedDoneResolve; renderedDoneResolve = null; r?.();
  renderedResolve?.(); renderedResolve = null;
}

/** Parse "#/parts?ata=32" → {id:'parts', params:{ata:'32'}} */
export function parseHash(hash = location.hash) {
  const raw = hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const id = ROUTES.some((r) => r.id === path) ? path : DEFAULT;
  return { id, params: Object.fromEntries(new URLSearchParams(query)) };
}

/** Build a hash from a route id and params. */
export function buildHash(id, params = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString();
  return `#/${id}${q ? `?${q}` : ''}`;
}

/** Navigate (re-renders). Resolves after the target view has rendered. */
export function navigate(hash) {
  return new Promise((resolve) => {
    if (location.hash === hash || sameUrl(hash)) { repeatCurrent().then(resolve, resolve); return; }
    renderedResolve = resolve;
    location.hash = hash;
  });
}

/** Update the URL params of the current route WITHOUT re-rendering (deep-link state). */
function setParams(params, { merge = true } = {}) {
  const cur = parseHash();
  const next = buildHash(cur.id, merge ? { ...cur.params, ...params } : params);
  history.replaceState(null, '', next);
  if (current) current.params = parseHash(next).params;
}

/** true when `hash` names exactly the current URL (same route, same params in any order). */
function sameUrl(hash) {
  if (!/^#\/?/.test(hash || '') || !location.hash.startsWith('#/')) return false;
  const path = (x) => x.replace(/^#\/?/, '').split('?')[0];
  return path(hash) === path(location.hash) && ROUTES.some((r) => r.id === path(hash)) && sameParams(parseHash(hash).params, parseHash().params);
}
const sameParams = (a, b, skip = []) => {
  const ka = Object.keys(a).filter((k) => !skip.includes(k)), kb = Object.keys(b).filter((k) => !skip.includes(k));
  return ka.length === kb.length && ka.every((k) => a[k] === b[k]);
};

// --------------------------------------------------------------------------- sections (v2.2 contract §1)
const HEADING = 'h1, h2, h3, h4, [role="heading"]';
function sectionTarget(section, params = {}) {
  const view = $('#view');
  if (!section || !view) return null;
  if (current && typeof current.mod?.sectionTarget === 'function') {
    try { const t = current.mod.sectionTarget(section, params, current.ctx); if (t && t.isConnected) return t; } catch (e) { console.error(e); }
  }
  const esc = CSS.escape(section);
  const byData = view.querySelector(`[data-section="${esc}"]`);
  if (byData) return byData;
  const byId = document.getElementById(section);
  if (byId && view.contains(byId)) return byId;
  const shortest = (list) => [...list].sort((x, y) => x.id.length - y.id.length)[0] || null;
  return shortest(view.querySelectorAll(`[id$="-${esc}"]`)) || shortest(view.querySelectorAll(`[id^="${esc}-"]`));
}
function focusTargetOf(t) {
  if (t.id === 'view') return t;
  if (t.matches(HEADING)) return t;
  return [...t.querySelectorAll(HEADING)].find((x) => x.getClientRects().length) || t;
}
function focusEl(f) {
  if (!f) return;
  if (!f.matches('a[href], button, input, select, textarea, summary, [tabindex]')) f.setAttribute('tabindex', '-1');
  try { f.focus({ preventScroll: true }); } catch { f.focus(); }
}
let settleStop = null;
/** Scroll `t` to the top (scroll-margin aware), focus its heading, and keep it there while late layout settles. */
function revealTarget(t, { focus = true } = {}) {
  settleStop?.();
  const doc = document.documentElement;
  const prev = doc.style.scrollBehavior;
  doc.style.scrollBehavior = 'auto';                              // instant jump, never a smooth scroll fighting later clicks
  t.scrollIntoView({ block: 'start', inline: 'nearest' });
  if (focus) focusEl(focusTargetOf(t));
  let expected = t.getBoundingClientRect().top;
  let stopped = false, raf = 0;
  const t0 = performance.now();
  const stop = () => {
    if (stopped) return; stopped = true; cancelAnimationFrame(raf);
    ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach((ev) => window.removeEventListener(ev, stop, true));
    doc.style.scrollBehavior = prev;
    if (settleStop === stop) settleStop = null;
  };
  ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach((ev) => window.addEventListener(ev, stop, { capture: true, passive: true }));
  const tick = () => {
    if (stopped) return;
    if (!t.isConnected || performance.now() - t0 > 700) { stop(); return; }
    const top = t.getBoundingClientRect().top;
    if (Math.abs(top - expected) > 2) { t.scrollIntoView({ block: 'start', inline: 'nearest' }); expected = t.getBoundingClientRect().top; }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  settleStop = stop;
}
/** A view that exports onParams (or `ownsSections = true`) scrolls its own sections (contract §3). */
const ownsSections = (mod) => typeof mod?.onParams === 'function' || mod?.ownsSections === true;
/** Section scroll for the current params. Returns true when a target was found. */
function revealSection(params = parseHash().params) {
  const t = sectionTarget(params.section, params);
  if (!t) return false;
  revealTarget(t);
  return true;
}
const overlayHoldsFocus = () => !!document.activeElement?.closest?.('.drawer, .modal, [role="dialog"], .story');
function toTop({ focus = true } = {}) {
  settleStop?.();
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (focus && !overlayHoldsFocus()) $('#view').focus({ preventScroll: true });
}

/** Re-run the current URL (repeated click on a link to it, or ctx.navigate to it): contract §2/§3. */
function repeatCurrent() {
  const { id, params } = parseHash();
  if (!current || current.id !== id || current.seq !== renderSeq) return render({ force: true });
  beginRendered();
  closeAllOverlays({ reason: 'params' });
  let handled;
  if (typeof current.mod?.onParams === 'function') {
    try { handled = current.mod.onParams(params, { ...current.ctx, params }); } catch (e) { console.error(e); handled = false; }
  }
  const other = Object.keys(params).some((k) => k !== 'section');
  if (handled === false || (handled === undefined && typeof current.mod?.onParams !== 'function' && other)) return render({ force: true });
  current.params = params;
  if (params.section && !ownsSections(current.mod) && revealSection(params)) { /* scrolled + focused */ }
  else if (!other && !params.section) toTop();
  endRendered();
  return renderedDone;
}

/** Click interception (contract §2 and §4): links to the current URL and in-page anchors. */
function onLinkClick(e) {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest?.('a[href]');
  if (!a || (a.target && a.target !== '_self') || a.hasAttribute('download')) return;
  const href = a.getAttribute('href') || '';
  if (!href.startsWith('#')) return;
  if (href.startsWith('#/') || href === '#') {
    if (href === location.hash || sameUrl(href)) { e.preventDefault(); repeatCurrent(); }
    return;
  }
  // in-page anchor: never let it reach the hash router (it would fall back to the default route)
  let t = null;
  try { t = document.getElementById(decodeURIComponent(href.slice(1))); } catch { t = null; }
  e.preventDefault();
  beginRendered();
  if (t) revealTarget(t);
  endRendered();
}

// --------------------------------------------------------------------------- shell
function buildNav() {
  const item = (r) =>
    h('a', { class: 'nav-item', href: `#/${r.id}`, dataset: { route: r.id }, 'aria-keyshortcuts': r.key || null }, h('span', { class: 'nav-ic', 'aria-hidden': 'true' }, icon(r.icon)), h('span', { class: 'nav-text' }, r.label), r.key ? h('span', { class: 'nav-key', 'aria-hidden': 'true' }, r.key) : null);
  const tour = h('button', { class: 'nav-item nav-item--btn', type: 'button', dataset: { route: 'tour' }, 'aria-keyshortcuts': 'S', onclick: () => { setRail(false); startStory(); } }, h('span', { class: 'nav-ic', 'aria-hidden': 'true' }, icon('play')), h('span', { class: 'nav-text' }, '60-second tour'), h('span', { class: 'nav-key', 'aria-hidden': 'true' }, 'S'));
  $('#nav').replaceChildren(...NAV_GROUPS.map((g) => h('div', { class: 'nav-group', role: 'group', 'aria-labelledby': `nav-g-${g.id}`, dataset: { group: g.id } },
    h('div', { class: 'nav-label', id: `nav-g-${g.id}` }, g.label),
    ...g.items.map((id) => (id === 'tour' ? tour : item(ROUTES.find((r) => r.id === id)))))));
}

function markActive(id) {
  document.querySelectorAll('.nav-item').forEach((a) => (a.dataset.route === id ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  const r = ROUTES.find((x) => x.id === id);
  $('#crumbs').replaceChildren(h('span', { class: 'crumb-group' }, groupOf(id)?.label || 'Project'), h('span', { class: 'faint', 'aria-hidden': 'true' }, '/'), h('strong', {}, r.label));
  document.title = `${r.label} · ${SITE}`;
}

function setRail(open) {
  $('#app').classList.toggle('rail-open', open);
  $('#menu-btn').setAttribute('aria-expanded', String(open));
}

function openHelp() {
  if (helpModal?.isOpen) return;
  const rows = [
    ...ROUTES.filter((r) => r.key).sort((a, b) => (a.key === '0') - (b.key === '0') || a.key - b.key).map((r) => [kbd(r.key), `${r.label} · ${groupOf(r.id)?.label || ''}`]),
    [kbd('S'), 'Start story mode (guided tour)'],
    [kbd('?'), 'Show this help'],
    [kbd('Esc'), 'Close dialogs, drawers and the tour'],
    [kbd('Tab'), 'Move between controls (focus is always visible)'],
  ];
  helpModal = modal({ title: 'Keyboard shortcuts', body: h('div', { class: 'shortcut-list' }, rows.flatMap(([k, d]) => [h('div', {}, k), h('div', {}, d)])) }).open();
}

let storyStarting = null;
/** Start the guided tour (top-bar Story button, rail "60-second tour", S key). Visible at once; idempotent. */
async function startStory() {
  if (window.__gnmStory) return window.__gnmStory;
  if (storyStarting) return storyStarting;
  storyStarting = (async () => {
    try {
      const story = await load('story');
      return storyMode({ steps: story.steps || [], navigate }).start();
    } catch (e) {
      console.warn('story unavailable', e);
      return null;
    } finally { storyStarting = null; }
  })();
  return storyStarting;
}

// --------------------------------------------------------------------------- render
async function render({ force = false, keepScroll = false } = {}) {
  // an in-page fragment that reached the hash (typed, or a link a view did not handle): scroll to it, keep the route URL
  const frag = location.hash.replace(/^#/, '');
  if (frag && !frag.startsWith('/') && current) {
    let t = null;
    try { t = document.getElementById(decodeURIComponent(frag)); } catch { t = null; }
    if (t) { history.replaceState(null, '', buildHash(current.id, current.params || {})); revealTarget(t); endRendered(); return; }
  }
  const { id, params } = parseHash();
  beginRendered();
  // same-route query change: the view's onParams hook, or (no hook) a change of `section` alone → no re-render
  if (!force && current && current.id === id && current.seq === renderSeq) {
    const hook = typeof current.mod?.onParams === 'function';
    if (hook || sameParams(params, current.params || {}, ['section'])) {
      closeAllOverlays({ reason: 'params' });
      let handled = true;
      if (hook) { try { handled = current.mod.onParams(params, { ...current.ctx, params }); } catch (e) { console.error(e); handled = false; } }
      if (handled !== false) {
        current.ctx.params = params; current.params = params;
        if (params.section && !hook) revealSection(params);
        else if (!Object.keys(params).length && !hook) toTop();
        endRendered();
        return;
      }
    }
  }
  const seq = ++renderSeq;
  const route = ROUTES.find((r) => r.id === id);
  // 1) close every drawer / modal / tooltip and release focus traps + scroll locks BEFORE the outgoing cleanup
  closeAllOverlays({ reason: 'route' });
  markActive(id);
  setRail(false);
  const view = $('#view');
  if (typeof cleanup === 'function') { try { cleanup(); } catch { /* ignore */ } }
  cleanup = null;
  current = null;
  view.classList.remove('view-enter');
  const scrollY0 = window.scrollY;
  if (!keepScroll) {
    // to the top before the old page is cleared: a shorter document would otherwise clamp the scroll and pull the
    // footer into view (a layout shift on every route change, e.g. during the auto-advancing tour)
    window.scrollTo({ top: 0, behavior: 'instant' });
    view.replaceChildren(stateBlock('loading'));
  }
  hideTermTip();
  try {
    const mod = await import(route.module);
    const data = await loadMany(mod.data || []);
    if (seq !== renderSeq) return;
    closeAllOverlays({ reason: 'route' }); // anything a stale view opened while we were loading
    view.replaceChildren();
    void view.offsetWidth; // restart entry animation
    if (!keepScroll) view.classList.add('view-enter');
    const live = () => seq === renderSeq;
    const ctx = {
      route, params, data, load, buildHash, navigate,
      setParams: (p, o) => { if (live() && parseHash().id === id) setParams(p, o); },
    };
    current = { id, mod, ctx, seq, params };
    resetTermUses();
    // v2.1 CLS: a new page is laid out but not painted while its async render runs (charts and SVGs arrive late),
    // then revealed in one step; same-page re-renders (mode switch) stay visible
    if (!keepScroll) view.style.visibility = 'hidden';
    try {
      cleanup = (await mod.render(view, ctx)) || null;
    } finally {
      if (seq === renderSeq) view.style.removeProperty('visibility');   // a stale render leaves it to the latest one
    }
    if (!keepScroll && seq === renderSeq) staggerIn(view); // v2.1 motion: first 6 cards rise in, 40 ms apart
  } catch (err) {
    console.error(err);
    if (seq === renderSeq) view.replaceChildren(stateBlock('error', `This workspace could not load (${err.message}).`));
  }
  if (seq === renderSeq) {
    view.style.removeProperty('visibility');   // the latest render always ends visible (also after an error)
    if (keepScroll) window.scrollTo({ top: scrollY0 });
    else if (params.section && !ownsSections(current?.mod) && revealSection(params)) { /* contract §1: scrolled to the section, heading focused */ }
    else toTop({ focus: !!window.__gnmNavigated });
    window.__gnmNavigated = true;
    document.documentElement.dataset.ready = 'true';
    endRendered();
  }
}

function onKey(e) {
  if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
  const t = e.target;
  if (t.closest?.('input, textarea, select, [contenteditable="true"]')) return;
  if (document.querySelector('.story')) return; // the tour owns the keyboard (→ ← Esc)
  const nav = /^[0-8]$/.test(e.key) || e.key === 's' || e.key === 'S';
  // F1: workspace shortcuts also work while a drawer / modal is open: close every overlay first, then act.
  // Esc is handled by the overlay itself (it closes first); other keys stay with the overlay.
  if (openOverlayCount() || document.querySelector('.modal, .drawer.is-open')) {
    if (!nav && e.key !== '?') return;
    if (nav) { e.preventDefault(); closeAllOverlays({ reason: 'route' }); }
  }
  if (/^[0-8]$/.test(e.key)) { const r = ROUTES.find((x) => x.key === e.key); if (r) navigate(`#/${r.id}`); }
  else if (e.key === '?') { e.preventDefault(); openHelp(); }
  else if (e.key === 's' || e.key === 'S') startStory();
  else if (e.key === 'Escape') setRail(false);
}

/** Dev-mode flag (localhost / ?dev): enables console lint warnings in chartFrame() etc. */
function devFlag() {
  try { window.__gnmDev = window.__gnmDev ?? (/^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || /[?&]dev\b/.test(location.search)); } catch { /* ignore */ }
}

/** Mode toggle → let the view update itself (onMode) or re-render it in place. */
function onModeChange(e) {
  const mode = e.detail?.mode;
  if (current && typeof current.mod?.onMode === 'function' && current.seq === renderSeq) {
    let handled;
    try { handled = current.mod.onMode(mode, current.ctx); } catch (err) { console.error(err); handled = false; }
    if (handled !== false) { resetTermUses(); return; }
  }
  closeAllOverlays({ reason: 'route' });
  render({ force: true, keepScroll: true });
}

function boot() {
  devFlag();
  initMode();
  ensureSprite();
  buildNav();
  const foot = $('#footer');
  foot.replaceWith(disclaimer({ meta: 'Simulated planning snapshot · Falcon Hub Airways is fictional' }));
  $('#menu-btn').addEventListener('click', () => setRail(!$('#app').classList.contains('rail-open')));
  $('#rail-scrim').addEventListener('click', () => setRail(false));
  $('#help-btn').addEventListener('click', openHelp);
  $('#mode-slot')?.replaceChildren(slidingThumb(modeToggle()));
  document.addEventListener(MODE_EVENT, onModeChange);
  $('#story-btn').addEventListener('click', startStory);
  $('#rail-story')?.addEventListener('click', startStory);
  onFixture(() => { const slot = $('#fixture-slot'); if (!slot.childElementCount) slot.append(fixtureChip()); });
  try { history.scrollRestoration = 'manual'; } catch { /* ignore */ }
  window.__gnmRendered = () => renderedDone;
  window.__gnmRevealSection = (name) => revealSection({ ...parseHash().params, section: name });
  window.__gnmSectionTarget = (name) => sectionTarget(name, parseHash().params);   // tests: the element a section resolves to
  window.__gnmRenderCount = () => renderCount;                                      // tests: bumps once per finished render / update
  document.addEventListener('click', onLinkClick);
  window.addEventListener('hashchange', () => render());
  document.addEventListener('keydown', onKey);
  if (!location.hash) history.replaceState(null, '', `#/${DEFAULT}`);
  render();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
