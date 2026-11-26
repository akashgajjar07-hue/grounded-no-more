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
 * Esc closes overlays. 1–8 / 0 / S also work while a drawer or modal is open (overlays close first, then the
 * shell navigates). A skip link jumps to the main content.
 */
import { h, icon, ensureSprite, fixtureChip, disclaimer, modal, kbd, storyMode, stateBlock, closeAllOverlays, openOverlayCount } from './ui.js';
import { loadMany, load, onFixture } from './data.js';

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
];
// keyboard: 1–8 keep their original workspace numbers (deep links and muscle memory stay stable), 0 = Data & Method
ROUTES.forEach((r) => { if (!r.key && /^\d\d$/.test(r.num)) r.key = String(+r.num); });
/** Wave A navigation groups (display order); the route ids, numbers and shortcut keys are unchanged. */
export const NAV_GROUPS = [
  { id: 'operations', label: 'Operations', items: ['mission', 'actions', 'aog'] },
  { id: 'material', label: 'Material intelligence', items: ['parts', 'forecast', 'rotables'] },
  { id: 'strategic', label: 'Strategic planning', items: ['network', 'capital'] },
  { id: 'project', label: 'Project', items: ['tour', 'method', 'about'] },
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
    if (location.hash === hash) { resolve(); return; }
    renderedResolve = resolve;
    location.hash = hash;
  });
}

/** Update the URL params of the current route WITHOUT re-rendering (deep-link state). */
function setParams(params, { merge = true } = {}) {
  const cur = parseHash();
  const next = buildHash(cur.id, merge ? { ...cur.params, ...params } : params);
  history.replaceState(null, '', next);
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

async function startStory() {
  try {
    const story = await load('story');
    storyMode({ steps: story.steps || [], navigate }).start();
  } catch (e) {
    console.warn('story unavailable', e);
  }
}

// --------------------------------------------------------------------------- render
async function render() {
  const { id, params } = parseHash();
  // same-route query change that the view handles itself: no re-render
  if (current && current.id === id && typeof current.mod?.onParams === 'function' && current.seq === renderSeq) {
    closeAllOverlays({ reason: 'params' });
    let handled;
    try { handled = current.mod.onParams(params, { ...current.ctx, params }); } catch (e) { console.error(e); handled = false; }
    if (handled !== false) { current.ctx.params = params; renderedResolve?.(); renderedResolve = null; return; }
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
  view.replaceChildren(stateBlock('loading'));
  try {
    const mod = await import(route.module);
    const data = await loadMany(mod.data || []);
    if (seq !== renderSeq) return;
    closeAllOverlays({ reason: 'route' }); // anything a stale view opened while we were loading
    view.replaceChildren();
    void view.offsetWidth; // restart entry animation
    view.classList.add('view-enter');
    const live = () => seq === renderSeq;
    const ctx = {
      route, params, data, load, buildHash, navigate,
      setParams: (p, o) => { if (live() && parseHash().id === id) setParams(p, o); },
    };
    current = { id, mod, ctx, seq };
    cleanup = (await mod.render(view, ctx)) || null;
  } catch (err) {
    console.error(err);
    if (seq === renderSeq) view.replaceChildren(stateBlock('error', `This workspace could not load (${err.message}).`));
  }
  if (seq === renderSeq) {
    if (window.__gnmNavigated) { view.focus({ preventScroll: true }); window.scrollTo({ top: 0 }); }
    window.__gnmNavigated = true;
    renderedResolve?.(); renderedResolve = null;
    document.documentElement.dataset.ready = 'true';
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

function boot() {
  devFlag();
  ensureSprite();
  buildNav();
  const foot = $('#footer');
  foot.replaceWith(disclaimer({ meta: 'Simulated planning snapshot · Falcon Hub Airways is fictional' }));
  $('#menu-btn').addEventListener('click', () => setRail(!$('#app').classList.contains('rail-open')));
  $('#rail-scrim').addEventListener('click', () => setRail(false));
  $('#help-btn').addEventListener('click', openHelp);
  $('#story-btn').addEventListener('click', startStory);
  $('#rail-story')?.addEventListener('click', startStory);
  onFixture(() => { const slot = $('#fixture-slot'); if (!slot.childElementCount) slot.append(fixtureChip()); });
  window.addEventListener('hashchange', render);
  document.addEventListener('keydown', onKey);
  if (!location.hash) history.replaceState(null, '', `#/${DEFAULT}`);
  render();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
