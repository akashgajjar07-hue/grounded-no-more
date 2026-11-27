/**
 * cutaway.js: interactive systems cutaway of a generic, fictional narrowbody (post-plan, exploratory lab).
 *
 *   import { mountCutaway } from './lab/cutaway.js';
 *   const cw = await mountCutaway(el, { parts, repair, onSelect });   // parts = parts.json .parts
 *   cw.select('GN-32-R014'); cw.destroy();
 *
 * The drawings are generated offline by docs/assets/svg/src/cutaway.mjs: cutaway.svg for wide screens, and
 * cutaway-simple.svg plus a zoned, numbered list for phones (≤ 600 px). This module only binds data and interaction
 * (with D3, window.d3).
 * Options:
 *   parts        parts.json rows (needed for the facts card)
 *   repair       rotables.json .tat rows (repair time per repairable part; optional)
 *   onSelect     (pn) => void; default goes to the site's part page (#/parts?pn=…)
 *   partHref     (pn) => string; link used by the card and the default onSelect
 *   svgBase      URL of the folder holding cutaway.svg / cutaway-simple.svg
 *   mobileQuery  media query for the phone layout (default '(max-width: 600px)')
 *
 * The draw-in (airframe → systems → glowing parts → callouts, ≤ 2 s) plays once per page load. Resizing or switching
 * layouts never replays it, and prefers-reduced-motion skips it.
 */

const HERE = import.meta.url;
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const pad2 = (n) => String(n).padStart(2, '0');
const reduceMotion = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; } };
const svgCache = new Map();
let PLAYED = false; // the draw-in runs once per page load

const ZONES = [
  ['nose', 'Flight deck and nose'], ['avionics', 'Avionics bay'], ['cabin', 'Air conditioning'], ['wing', 'Wing'],
  ['engine', 'Engine and pylon'], ['gear', 'Gear bay and hydraulics'], ['tail', 'Tail and APU'],
];

function roundNice(v) {
  if (v == null || !Number.isFinite(v)) return '—';
  if (v >= 100) return String(Math.round(v / 5) * 5);
  if (v >= 1) return String(Math.round(v));
  return v > 0 ? 'less than 1' : '0';
}
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const cleanName = (desc) => String(desc || '').replace(/\s*\((NB|WB)\)\s*$/, '');

/** Plain-English facts for one part (Simple wording; expert terms only in small grey brackets). */
export function partFacts(p, rep) {
  if (!p) return null;
  const isRep = p.cls === 'R';
  const kind = isRep ? 'Repairable part' : p.cls === 'E' ? 'Replaced, not repaired' : 'Consumable';
  const per = roundNice(p.annual_usage_qty);
  const facts = [];
  facts.push({ id: 'off', k: p.cls === 'C' ? 'Used' : 'Comes off', x: 'removals', v: per === 'less than 1' ? 'Under once a year' : `About ${per} a year`, sub: 'whole fleet' });
  if (isRep && rep) facts.push({ id: 'repair', k: 'Repair time', x: 'TAT', v: `About ${roundNice(rep.actual_mean_d)} days`, sub: rep.quoted_d != null ? `quoted ${roundNice(rep.quoted_d)} days` : '' });
  else facts.push({ id: 'repair', k: 'New one arrives in', x: 'lead time', v: p.lt_est_d != null ? `About ${roundNice(p.lt_est_d)} days` : '—', sub: '' });
  const held = Object.entries(p.stock_by_station || {}).filter(([, v]) => v > 0);
  const total = held.reduce((t, [, v]) => t + v, 0);
  facts.push({ id: 'spares', k: 'Spares held', x: 'Network Plan', stations: held.map(([s, v]) => ({ s, v })), v: total ? `${total} in total` : 'None held', sub: '' });
  facts.push({ id: 'aog', k: 'Hours grounded', x: 'last 52 wk', v: p.aog_h_52w > 0 ? `${Math.round(p.aog_h_52w)} h` : 'None', sub: '' });

  const rec = [];
  const p0 = p.stock_total_p0, p2 = p.stock_total_p2;
  if (p2 != null && p0 != null) {
    const n2 = plural(p2, 'spare', 'spares');
    if (p2 > p0) rec.push(`Network Plan holds ${n2}, up from ${p0} in the Simple Rulebook (naive reference).`);
    else if (p2 < p0) rec.push(`Network Plan holds ${n2}, down from ${p0} in the Simple Rulebook (naive reference).`);
    else rec.push(`Network Plan holds ${n2}, the same as the Simple Rulebook (naive reference).`);
  }
  const flags = [];
  if (p.planted === 'PS1') flags.push({ tone: 'review', text: 'Removing 2.5× faster than quoted → escalate to reliability engineering and warranty review first. Extra spares are interim cover, compared against faster repair or pool access.' });
  const outBrake = p.removal_mode === 'wear_planned' && Object.entries(p.stock_by_station || {}).some(([s, v]) => s !== 'AUH' && v > 0);
  if (outBrake) flags.push({ tone: 'urgent', text: 'Invalid recommendation — brakes are not changed outside the hub in this model.' });
  (p.exceptions || []).forEach((e) => flags.push({ tone: e.severity === 'urgent' ? 'urgent' : 'info', text: `Planner flag: ${e.type_label}${e.station ? ` at ${e.station}` : ''}` }));
  return { pn: p.pn, name: cleanName(p.desc), kind, ata: p.ata, facts, rec, flags };
}

function cardHTML(f, { href, num, compact = false, linkTab = true } = {}) {
  if (!f) return '';
  const fact = (r) => `<div class="cw-fact cw-fact--${r.id}"><dt>${esc(r.k)} <span class="cw-x">(${esc(r.x)})</span></dt><dd>${
    r.stations && r.stations.length ? `<span class="cw-stations">${r.stations.map((s) => `<span class="cw-st"><span class="mono">${esc(s.s)}</span> <b class="mono">${esc(s.v)}</b></span>`).join('')}</span>` : ''
  }<span class="cw-v">${esc(r.v)}</span>${r.sub ? `<span class="cw-sub">${esc(r.sub)}</span>` : ''}</dd></div>`;
  const [first, ...more] = f.flags;
  return `${compact ? '' : `<p class="cw-kicker">${num ? `<span class="cw-cnum mono">${pad2(num)}</span>` : ''}${esc(f.kind)} · ATA <span class="mono">${esc(f.ata)}</span></p>
    <h3 class="cw-title">${esc(f.name)} <span class="cw-pn mono">${esc(f.pn)}</span></h3>`}
    <dl class="cw-facts">${f.facts.map(fact).join('')}</dl>
    <div class="cw-rec"><p class="cw-rec-k">Recommendation</p>${f.rec.map((t) => `<p class="cw-rec-t">${esc(t)}</p>`).join('')}
    ${first ? `<p class="cw-flag cw-flag--${first.tone}" title="${esc(f.flags.map((g) => g.text).join('\n'))}"><span class="cw-flag-t">${esc(first.text)}</span>${more.length ? ` <span class="cw-more">+${more.length} ${more.length === 1 ? 'flag' : 'flags'}</span>` : ''}</p>` : ''}</div>
    <p class="cw-foot"><span class="cw-sim">Simulated · fictional airline</span>${href ? `<a class="cw-link" href="${esc(href)}"${linkTab ? '' : ' tabindex="-1"'}>Open part page <span aria-hidden="true">→</span></a>` : ''}</p>`;
}

async function loadSVG(url) {
  if (!svgCache.has(url)) svgCache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`cutaway: ${r.status} ${url}`); return r.text(); }));
  return svgCache.get(url);
}

export async function mountCutaway(el, opts = {}) {
  const d3 = window.d3;
  if (!d3) throw new Error('cutaway: d3 is not loaded');
  const {
    parts = [], repair = [], svgBase = new URL('../assets/svg/', HERE).href, mobileQuery = '(max-width: 600px)',
    partHref = (pn) => new URL(`../index.html#/parts?pn=${encodeURIComponent(pn)}`, HERE).href,
  } = opts;
  const onSelect = opts.onSelect || ((pn) => { window.location.href = partHref(pn); });
  const byPn = new Map(parts.map((p) => [p.pn, p]));
  const repByPn = new Map((repair || []).map((r) => [r.pn, r]));
  const facts = (pn) => partFacts(byPn.get(pn), repByPn.get(pn));
  const mq = matchMedia(mobileQuery);
  let mode = null, cleanup = () => {}, token = 0, pending = Promise.resolve();

  // Renders are serialised by a token: a layout switch while an SVG is still loading can never leave the host
  // empty, and settled() resolves only when the drawing for the current layout is in the DOM.
  function render() {
    const next = mq.matches ? 'simple' : 'full';
    if (next === mode && el.querySelector('svg.cw-svg')) return pending;
    const my = ++token;
    mode = next;
    pending = (async () => {
      const svgText = await loadSVG(`${svgBase.replace(/\/?$/, '/')}${next === 'full' ? 'cutaway.svg' : 'cutaway-simple.svg'}`);
      if (my !== token) return;
      cleanup();
      el.classList.add('cw-root');
      el.innerHTML = '';
      el.dataset.mode = next;
      cleanup = next === 'full' ? mountFull(svgText) : mountSimple(svgText);
    })();
    return pending;
  }

  function startDraw(svg) {
    if (PLAYED || reduceMotion()) { PLAYED = true; return null; }
    PLAYED = true;
    svg.classList.add('is-drawing');
    const t = setTimeout(() => svg.classList.remove('is-drawing'), 2000);
    return () => { clearTimeout(t); svg.classList.remove('is-drawing'); };
  }
  const lightSystems = (svg, pn) => {
    const g = pn ? svg.querySelector(`.cw-part[data-pn="${pn}"]`) : null;
    const sys = g ? (g.dataset.sys || '').split(' ').filter(Boolean) : [];
    svg.querySelectorAll('.cw-sys').forEach((s) => {
      const on = sys.includes(s.dataset.sys);
      if (on && !s.classList.contains('is-on')) { s.classList.remove('is-on'); void s.getBoundingClientRect(); }
      s.classList.toggle('is-on', on);
    });
  };

  // ------------------------------------------------------------------ wide screens: poster + docked card
  function mountFull(svgText) {
    const stage = document.createElement('div');
    stage.className = 'cw-stage';
    stage.innerHTML = svgText;
    const card = document.createElement('div');
    card.className = 'cw-card';
    card.id = 'cw-card-live';
    card.setAttribute('role', 'status');
    card.setAttribute('aria-live', 'polite');
    card.hidden = true;
    stage.appendChild(card);
    el.appendChild(stage);
    const svgEl = stage.querySelector('svg');
    const svg = d3.select(svgEl);
    const dock = (svgEl.dataset.card || '14 14 372 396').split(' ').map(Number);
    const stopDraw = startDraw(svgEl);
    let active = null, pinned = false, lastPointer = 'mouse', hideT = null;

    svg.selectAll('.cw-focus').each(function () {
      const pn = this.dataset.pn, f = facts(pn), num = this.dataset.n;
      if (!f) return;
      this.setAttribute('aria-label', `${pad2(num)} · ${f.name} (${pn}): comes off ${f.facts[0].v.toLowerCase()}. Open part page.`);
      this.setAttribute('aria-describedby', 'cw-card-live');
    });

    const toScreen = (x, y) => { const m = svgEl.getScreenCTM(); const pt = svgEl.createSVGPoint(); pt.x = x; pt.y = y; return pt.matrixTransform(m); };
    function placeCard() {
      const st = stage.getBoundingClientRect();
      const a = toScreen(dock[0], dock[1]), b = toScreen(dock[2], dock[3]);
      card.style.left = `${Math.round(a.x - st.left)}px`;
      card.style.top = `${Math.round(a.y - st.top)}px`;
      card.style.width = `${Math.round(Math.min(330, b.x - a.x))}px`;
      card.style.maxHeight = `${Math.round(Math.max(220, b.y - a.y))}px`;
    }
    function show(pn, pin = false) {
      clearTimeout(hideT);
      const f = facts(pn);
      if (!f) return;
      if (active !== pn || pinned !== pin) {
        const num = svgEl.querySelector(`.cw-focus[data-pn="${pn}"]`)?.dataset.n;
        card.innerHTML = cardHTML(f, { href: partHref(pn), num, linkTab: pin });
      }
      active = pn; pinned = pin;
      card.hidden = false;
      card.classList.toggle('is-pinned', pin);
      svgEl.classList.add('has-active');
      svg.selectAll('.cw-part, .cw-callout, .cw-focus').classed('is-active', function () { return this.dataset.pn === pn; });
      lightSystems(svgEl, pn);
      placeCard();
    }
    function hide(now = false) {
      clearTimeout(hideT);
      const go = () => {
        if (pinned || card.contains(document.activeElement)) return;
        active = null; card.hidden = true; svgEl.classList.remove('has-active');
        svg.selectAll('.is-active').classed('is-active', false);
        lightSystems(svgEl, null);
      };
      if (now) go(); else hideT = setTimeout(go, 140);
    }
    const choose = (pn) => { if (typeof onSelect === 'function') onSelect(pn); };

    svg.selectAll('.cw-part, .cw-callout')
      .on('pointerenter', function (e) { lastPointer = e.pointerType || 'mouse'; if (lastPointer === 'mouse' && !pinned) show(this.dataset.pn); })
      .on('pointerleave', function (e) { if ((e.pointerType || 'mouse') === 'mouse') hide(); })
      .on('pointerdown', (e) => { lastPointer = e.pointerType || 'mouse'; })
      .on('click', function (e) {
        const pn = this.dataset.pn;
        if (lastPointer !== 'mouse' && !(pinned && active === pn)) { e.preventDefault(); show(pn, true); return; }
        choose(pn);
      });
    svg.selectAll('.cw-focus')
      .on('focus', function () { show(this.dataset.pn); })
      .on('blur', () => { pinned = false; hide(); })
      .on('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(this.dataset.pn); }
        if (e.key === 'Escape') { pinned = false; hide(true); }
      });
    const outside = (e) => { if (pinned && !stage.contains(e.target)) { pinned = false; hide(true); } };
    const onKey = (e) => { if (e.key === 'Escape' && active) { pinned = false; hide(true); } };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', onKey);
    const onResize = () => { if (active) placeCard(); };
    window.addEventListener('resize', onResize);
    api.select = (pn) => show(pn, true);
    return () => { stopDraw && stopDraw(); document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', onKey); window.removeEventListener('resize', onResize); };
  }

  // ------------------------------------------------------------------ phones: simplified drawing + zoned list
  function mountSimple(svgText) {
    const fig = document.createElement('div');
    fig.className = 'cw-mfig';
    fig.innerHTML = svgText;
    const list = document.createElement('div');
    list.className = 'cw-list';
    el.append(fig, list);
    const svgEl = fig.querySelector('svg');
    const svg = d3.select(svgEl);
    const stopDraw = startDraw(svgEl);
    const vb = svgEl.viewBox.baseVal;
    const items = [...svgEl.querySelectorAll('.cw-part')].map((g) => ({ pn: g.dataset.pn, n: +g.dataset.n, label: g.dataset.label, zone: g.dataset.zone, ax: +g.dataset.ax, ay: +g.dataset.ay }))
      .sort((a, b) => a.n - b.n);
    // selection marker + 2.5× zoom inset of the selected part's zone (top-left corner, over the far wing)
    const ns = 'http://www.w3.org/2000/svg';
    const marker = svg.append('g').attr('class', 'cw-marker').attr('aria-hidden', 'true').style('display', 'none');
    marker.append('circle').attr('class', 'cw-ring').attr('r', 34);
    const IW = 320, IH = 190, IX = 22, IY = 22, Z = 2.5;
    const inset = svg.append('g').attr('class', 'cw-inset').attr('aria-hidden', 'true').style('display', 'none');
    const clipId = 'cw-inset-clip';
    svg.select('defs').append('clipPath').attr('id', clipId).append('rect').attr('x', IX).attr('y', IY).attr('width', IW).attr('height', IH).attr('rx', 8);
    inset.append('rect').attr('class', 'cw-inset-bg').attr('x', IX).attr('y', IY).attr('width', IW).attr('height', IH).attr('rx', 8);
    const insetView = inset.append('g').attr('clip-path', `url(#${clipId})`);
    const use = document.createElementNS(ns, 'use');
    use.setAttribute('href', '#cw-root-simple');
    insetView.node().appendChild(use);
    const insetRing = insetView.append('circle').attr('class', 'cw-ring').attr('r', 30);
    inset.append('rect').attr('class', 'cw-inset-halo').attr('x', IX - 1.5).attr('y', IY - 1.5).attr('width', IW + 3).attr('height', IH + 3).attr('rx', 9);
    inset.append('rect').attr('class', 'cw-inset-frame').attr('x', IX).attr('y', IY).attr('width', IW).attr('height', IH).attr('rx', 8);
    const insetTag = inset.append('text').attr('class', 'cw-inset-t').attr('x', IX + 14).attr('y', IY + IH - 14);

    const caption = document.createElement('p');
    caption.className = 'cw-caption';
    caption.setAttribute('aria-hidden', 'true');
    caption.textContent = 'Tap a number or a row';
    fig.appendChild(caption);
    // 44 CSS px tap circles: the radius is set in viewBox units from the rendered scale
    const sizeHits = () => { const k = svgEl.getBoundingClientRect().width / vb.width; if (k > 0) svgEl.querySelectorAll('.cw-ndot-hit').forEach((c) => c.setAttribute('r', (22 / k).toFixed(1))); };
    sizeHits();
    const setFigH = () => { el.style.setProperty('--cw-fig-h', `${Math.round(fig.getBoundingClientRect().height)}px`); sizeHits(); };
    setFigH();
    const onResize = () => setFigH();
    window.addEventListener('resize', onResize);

    let open = null;
    function select(pn, { scroll = false } = {}) {
      const it = items.find((i) => i.pn === pn);
      const willOpen = open !== pn ? pn : null;
      list.querySelectorAll('.cw-item').forEach((b) => {
        const on = b.dataset.pn === willOpen;
        b.setAttribute('aria-expanded', String(on));
        b.closest('li').classList.toggle('is-open', on);
        document.getElementById(b.getAttribute('aria-controls')).hidden = !on;
      });
      open = willOpen;
      const zoneName = (ZONES.find(([z]) => z === (it && it.zone)) || [])[1];
      caption.innerHTML = open && it ? `<span class="mono">${pad2(it.n)}</span> ${esc(zoneName || '')} · ${esc(it.label)}` : 'Tap a number or a row';
      caption.classList.toggle('is-on', !!open);
      svg.selectAll('.cw-part, .cw-ndot').classed('is-active', function () { return this.dataset.pn === open; });
      svgEl.classList.toggle('has-active', !!open);
      lightSystems(svgEl, open);
      if (open && it) {
        marker.style('display', null).attr('transform', `translate(${it.ax} ${it.ay})`);
        const cx = IX + IW / 2, cy = IY + IH / 2;
        use.setAttribute('transform', `translate(${cx - Z * it.ax} ${cy - Z * it.ay}) scale(${Z})`);
        insetRing.attr('cx', cx).attr('cy', cy).attr('r', 34);
        insetTag.text(`${pad2(it.n)} · ${Z}×`);
        // keep the inset off the selected part itself
        const overlaps = it.ax < IX + IW + 30 && it.ay < IY + IH + 30;
        inset.attr('transform', overlaps ? `translate(${vb.width - IW - 2 * IX} 0)` : null).style('display', null);
      } else { marker.style('display', 'none'); inset.style('display', 'none'); }
      if (scroll && open) {
        const li = list.querySelector(`.cw-item[data-pn="${pn}"]`)?.closest('li');
        li?.scrollIntoView({ block: 'start', behavior: reduceMotion() ? 'auto' : 'smooth' });
      }
    }
    for (const [zone, title] of ZONES) {
      const zi = items.filter((i) => i.zone === zone);
      if (!zi.length) continue;
      const sec = document.createElement('section');
      sec.className = 'cw-zone';
      sec.innerHTML = `<h2 class="cw-zone-h">${esc(title)}</h2><ol class="cw-zone-list"></ol>`;
      const ol = sec.querySelector('ol');
      zi.forEach((it) => {
        const f = facts(it.pn);
        const li = document.createElement('li');
        li.className = 'cw-li';
        const id = `cw-d-${it.pn}`;
        const name = f ? f.name : it.label;
        li.innerHTML = `<button type="button" class="cw-item" data-pn="${esc(it.pn)}" aria-expanded="false" aria-controls="${esc(id)}"
            aria-label="${esc(`${pad2(it.n)} · ${name} (${it.pn})${f ? `: comes off ${f.facts[0].v.toLowerCase()}` : ''}. Show details.`)}">
            <span class="cw-num mono">${pad2(it.n)}</span><span class="cw-iname">${esc(name)}<span class="cw-ipn mono">${esc(it.pn)}</span></span>
            <svg class="cw-chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></button>
          <div class="cw-detail" id="${esc(id)}" hidden>${cardHTML(f, { href: partHref(it.pn), compact: true })}</div>`;
        li.querySelector('.cw-item').addEventListener('click', () => select(it.pn, { scroll: true }));
        li.querySelector('.cw-link')?.addEventListener('click', (e) => { if (opts.onSelect) { e.preventDefault(); onSelect(it.pn); } });
        ol.appendChild(li);
      });
      list.appendChild(sec);
    }
    svg.selectAll('.cw-part, .cw-ndot, .cw-ndot-hit').on('click', function () { select(this.dataset.pn, { scroll: true }); });
    api.select = (pn) => select(pn, { scroll: true });
    return () => { stopDraw && stopDraw(); window.removeEventListener('resize', onResize); };
  }

  const api = { select: () => {}, settled: () => pending.then(() => (el.dataset.mode !== (mq.matches ? 'simple' : 'full') ? render() : null)), destroy() { cleanup(); mq.removeEventListener('change', render); el.innerHTML = ''; el.classList.remove('cw-root'); } };
  mq.addEventListener('change', render);
  await render();
  return api;
}
