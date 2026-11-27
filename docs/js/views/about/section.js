/**
 * views/about/section.js — reliable section jumps for the page views (About, Planner, Glossary, Data & Method).
 *
 *   import { jumpTo, sameRouteLinks } from './about/section.js';
 *   jumpTo(() => document.getElementById('ab-mro'), { heading: (t) => t.querySelector('.card-title') });
 *   const off = sameRouteLinks(el, 'about', (params) => jumpTo(...));   // call off() in the view cleanup
 *
 * Why this exists (v2.2): section links worked "only sometimes". Three causes, all handled here:
 *  1. Timing. A view rendered for a deep link scrolled from inside render(); the router then revealed the page and
 *     reset the scroll to the top (and focused #view) after render() resolved, so the jump was undone whenever it
 *     landed first. jumpTo() waits until the target exists AND the router has finished (the view is no longer
 *     `visibility:hidden`, the shell is ready), then jumps on the next frame.
 *  2. A repeat click on the link of the section you are already on changes nothing in the URL, so no `hashchange`
 *     fires and nothing scrolled. sameRouteLinks() catches those clicks (same route, same query) and jumps directly;
 *     any other same-route link still changes the hash, and the view's onParams() jumps.
 *  3. Late layout (fonts, entry animation, charts, the browser's own scroll restoration on reload or Back) moved the
 *     target after the jump. For a short settle window the jump is re-applied if the target drifts, unless the reader
 *     scrolls, taps or types. Positions are read from the layout box (offsetTop), so entry transforms do not count.
 * Jumps are instant (no smooth scrolling to fight later clicks); focus moves to the target heading (tabindex=-1).
 */
const GAP = 16;          // px between the sticky bar(s) and the target heading
const SETTLE_MS = 800;   // re-apply window for late layout shifts
const WAIT_MS = 6000;    // give up waiting for a target that never renders
let token = 0;
let stopSettle = null;

/** Height of the sticky bars covering the top of the page: the shell top bar plus any extra sticky selectors. */
export function stickyOffset(extra = []) {
  let off = 0;
  ['.topbar', ...extra].forEach((sel) => {
    const e = document.querySelector(sel);
    if (!e || e.hidden) return;
    const pos = getComputedStyle(e).position;
    if (pos === 'sticky' || pos === 'fixed') off += e.getBoundingClientRect().height;
  });
  return off + GAP;
}

/** Document-space top of an element from its layout box (ignores transforms such as the entry animation). */
function docTop(el) {
  let y = 0;
  for (let e = el; e; e = e.offsetParent) y += e.offsetTop;
  return y;
}

const routerDone = () => {
  const v = document.getElementById('view');
  return (!v || v.style.visibility !== 'hidden') && document.documentElement.dataset.ready === 'true';
};
const maxScroll = () => Math.max(0, document.documentElement.scrollHeight - window.innerHeight);

/**
 * Jump to a section once it is rendered. resolve() → the target element (or null while not rendered yet).
 * opts.heading(target) → the element that takes focus (defaults to the target; tabindex=-1 is added if missing).
 * opts.sticky: extra sticky selectors to clear (e.g. a sticky search bar). opts.focus=false keeps focus where it is.
 * Resolves true once placed, false if superseded or the target never appeared.
 */
export function jumpTo(resolve, { heading, sticky = [], focus = true } = {}) {
  const my = ++token;
  stopSettle?.();
  const t0 = performance.now();
  return new Promise((done) => {
    const place = (t) => {
      const want = Math.min(maxScroll(), Math.max(0, Math.round(docTop(t) - stickyOffset(sticky))));
      if (Math.abs(window.scrollY - want) > 1) window.scrollTo({ top: want, left: window.scrollX, behavior: 'instant' });
    };
    const tick = () => {
      if (my !== token) { done(false); return; }
      const t = resolve();
      if (!t || !t.isConnected || !routerDone()) {
        if (performance.now() - t0 > WAIT_MS) { done(false); return; }
        requestAnimationFrame(tick);
        return;
      }
      place(t);
      const f = (heading && heading(t)) || t;
      if (focus && f) {
        if (!f.hasAttribute('tabindex') && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(f.tagName)) f.setAttribute('tabindex', '-1');
        f.focus({ preventScroll: true });
      }
      settle(t, f, my);
      done(true);
    };
    const settle = (t, f, id) => {
      const end = performance.now() + SETTLE_MS;
      let live = true;
      const stop = () => { live = false; ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach((ev) => window.removeEventListener(ev, stop, true)); if (stopSettle === stop) stopSettle = null; };
      ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach((ev) => window.addEventListener(ev, stop, { capture: true, passive: true }));
      stopSettle = stop;
      const again = () => {
        if (!live || id !== token || !t.isConnected) { stop(); return; }
        place(t);
        if (focus && f && (document.activeElement === document.body || document.activeElement?.id === 'view')) f.focus({ preventScroll: true });
        if (performance.now() < end) requestAnimationFrame(again); else stop();
      };
      requestAnimationFrame(again);
    };
    tick();
  });
}

const norm = (hash) => {
  const [path, q = ''] = String(hash || '').replace(/^#\/?/, '').split('?');
  const p = new URLSearchParams(q);
  return `${path}?${[...p.entries()].sort().map(([k, v]) => `${k}=${v}`).join('&')}`;
};

/**
 * Catch clicks on links inside `root` that point to the CURRENT url of this route (a repeat click: no hashchange
 * would fire) and hand their params to handle(params). Other links are left to the router. Returns an unsubscribe.
 */
export function sameRouteLinks(root, route, handle) {
  const onClick = (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest?.('a[href^="#/"]');
    if (!a || !root.contains(a) || a.target) return;
    const href = a.getAttribute('href');
    if (href.replace(/^#\/?/, '').split('?')[0] !== route) return;
    if (norm(href) !== norm(location.hash)) return;   // a different section: the hash changes, the view's onParams jumps
    e.preventDefault();
    handle(Object.fromEntries(new URLSearchParams(href.split('?')[1] || '')));
  };
  root.addEventListener('click', onClick);
  return () => root.removeEventListener('click', onClick);
}
