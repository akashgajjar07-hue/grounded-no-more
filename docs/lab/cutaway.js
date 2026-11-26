/**
 * cutaway.js: interactive systems cutaway of a generic, fictional narrowbody (post-plan, exploratory lab).
 *
 *   import { mountCutaway } from './lab/cutaway.js';
 *   const cw = await mountCutaway(el, { parts, repair, onSelect });   // parts = parts.json .parts
 *   cw.select('GN-32-R014'); cw.destroy();
 *
 * The drawings are generated offline by docs/assets/svg/src/cutaway.mjs (cutaway.svg for wide screens,
 * cutaway-simple.svg + a numbered list for phones ≤ 600 px). This module only binds data and interaction (D3).
 * Options:
 *   parts     array of parts.json rows (required for the facts card)
 *   repair    rotables.json .tat rows (repair time per repairable part; optional)
 *   onSelect  (pn) => void; default navigates to the site's part page (#/parts?pn=…)
 *   partHref  (pn) => string; link used by the card and the default onSelect
 *   svgBase   URL of the folder holding cutaway.svg / cutaway-simple.svg
 *   mobileQuery  media query for the phone layout (default '(max-width: 600px)')
 */

const HERE = import.meta.url;
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const pad2 = (n) => String(n).padStart(2, '0');
const reduceMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
const svgCache = new Map();

function roundNice(v) {
  if (v == null || !Number.isFinite(v)) return '—';
  if (v >= 100) return String(Math.round(v / 5) * 5);
  if (v >= 10) return String(Math.round(v));
  if (v >= 1) return String(Math.round(v));
  return v > 0 ? 'less than 1' : '0';
}
const cleanName = (desc) => String(desc || '').replace(/\s*\((NB|WB)\)\s*$/, '');

/** Plain-English facts for one part (Simple wording; expert terms only in small grey brackets). */
export function partFacts(p, rep) {
  if (!p) return null;
  const isRep = p.cls === 'R';
  const kind = isRep ? 'Repairable part' : p.cls === 'E' ? 'Replaced, not repaired' : 'Consumable';
  const rows = [];
  const per = roundNice(p.annual_usage_qty);
  rows.push({ k: p.cls === 'C' ? 'Used' : 'Comes off the aircraft', x: 'removals', v: per === 'less than 1' ? 'Less than once a year, whole fleet' : `About ${per} times a year, whole fleet` });
  if (isRep && rep) {
    rows.push({ k: 'Repair time', x: 'TAT', v: `About ${roundNice(rep.actual_mean_d)} days`, sub: rep.quoted_d != null ? `the repair shop quotes ${roundNice(rep.quoted_d)} days` : '' });
  } else if (p.lt_est_d != null) {
    rows.push({ k: 'Time to get a new one', x: 'lead time', v: `About ${roundNice(p.lt_est_d)} days` });
  }
  const held = Object.entries(p.stock_by_station || {}).filter(([, v]) => v > 0);
  const total = held.reduce((t, [, v]) => t + v, 0);
  rows.push({
    k: 'Where spares are held', x: 'Network Plan',
    stations: held.map(([s, v]) => ({ s, v })),
    v: total ? `${total} in total` : 'None held',
    sub: isRep ? 'on the shelf, not counting units away for repair' : '',
  });
  if (p.aog_h_52w > 0) rows.push({ k: 'Hours grounded waiting for it', x: 'last 52 weeks', v: `${Math.round(p.aog_h_52w)} h` });

  const rec = [];
  const p0 = p.stock_total_p0, p2 = p.stock_total_p2;
  if (p2 != null && p0 != null) {
    if (p2 > p0) rec.push(`The Network Plan holds ${p2} spares, up from ${p0} under the Simple Rulebook (naive reference).`);
    else if (p2 < p0) rec.push(`The Network Plan holds ${p2} spares, down from ${p0} under the Simple Rulebook (naive reference).`);
    else rec.push(`The Network Plan holds ${p2} spares, the same as the Simple Rulebook (naive reference).`);
  }
  const flags = [];
  if (p.planted === 'PS1') flags.push({ tone: 'review', text: 'Removing 2.5× faster than quoted → escalate to reliability engineering and warranty review first. Extra spares are interim cover, compared against faster repair or pool access.' });
  const outBrake = p.removal_mode === 'wear_planned' && Object.entries(p.stock_by_station || {}).some(([s, v]) => s !== 'AUH' && v > 0);
  if (outBrake) flags.push({ tone: 'urgent', text: 'Invalid recommendation — brakes are not changed outside the hub in this model.' });
  (p.exceptions || []).slice(0, 2).forEach((e) => flags.push({ tone: e.severity === 'urgent' ? 'urgent' : 'info', text: `Planner flag: ${e.type_label}${e.station ? ` at ${e.station}` : ''}` }));
  return { pn: p.pn, name: cleanName(p.desc), kind, ata: p.ata, ataName: p.ata_name, rows, rec, flags };
}

function cardHTML(f, { href, num, compact = false } = {}) {
  if (!f) return '';
  const row = (r) => `<div class="cw-row"><dt>${esc(r.k)}${r.x ? ` <span class="cw-x">(${esc(r.x)})</span>` : ''}</dt><dd>${
    r.stations && r.stations.length ? `<span class="cw-stations">${r.stations.map((s) => `<span class="cw-st"><span class="mono">${esc(s.s)}</span> <b class="mono">${esc(s.v)}</b></span>`).join('')}</span> ` : ''
  }<span class="cw-v">${esc(r.v)}</span>${r.sub ? `<span class="cw-sub">${esc(r.sub)}</span>` : ''}</dd></div>`;
  return `${compact ? '' : `<p class="cw-kicker">${num ? `<span class="cw-cnum mono">${pad2(num)}</span>` : ''}${esc(f.kind)} · ATA <span class="mono">${esc(f.ata)}</span></p>
    <h3 class="cw-title">${esc(f.name)} <span class="cw-pn mono">${esc(f.pn)}</span></h3>`}
    <dl class="cw-facts">${f.rows.map(row).join('')}</dl>
    <div class="cw-rec"><p class="cw-rec-k">Recommendation</p>${f.rec.map((t) => `<p>${esc(t)}</p>`).join('')}
    ${f.flags.map((g) => `<p class="cw-flag cw-flag--${g.tone}">${esc(g.text)}</p>`).join('')}</div>
    <p class="cw-foot"><span class="cw-sim">Simulated · fictional airline</span>${href ? `<a class="cw-link" href="${esc(href)}">Open part page <span aria-hidden="true">→</span></a>` : ''}</p>`;
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
  let mode = null, cleanup = () => {};

  async function render() {
    const next = mq.matches ? 'simple' : 'full';
    if (next === mode) return;
    cleanup(); mode = next;
    el.classList.add('cw-root');
    el.innerHTML = '';
    const svgText = await loadSVG(`${svgBase.replace(/\/?$/, '/')}${next === 'full' ? 'cutaway.svg' : 'cutaway-simple.svg'}`);
    if (mode !== next) return; // a later render won
    cleanup = next === 'full' ? mountFull(svgText) : mountSimple(svgText);
  }

  function startDraw(svg) {
    if (reduceMotion()) return;
    svg.classList.add('is-drawing');
    const t = setTimeout(() => svg.classList.remove('is-drawing'), 2000);
    return () => clearTimeout(t);
  }

  // ------------------------------------------------------------------ wide screens: poster + floating card
  function mountFull(svgText) {
    const stage = document.createElement('div');
    stage.className = 'cw-stage';
    stage.innerHTML = svgText;
    const card = document.createElement('div');
    card.className = 'cw-card';
    card.setAttribute('role', 'status');
    card.setAttribute('aria-live', 'polite');
    card.hidden = true;
    stage.appendChild(card);
    el.appendChild(stage);
    const svgEl = stage.querySelector('svg');
    const svg = d3.select(svgEl);
    const vb = svgEl.viewBox.baseVal;
    const stopDraw = startDraw(svgEl);
    let active = null, pinned = false, lastPointer = 'mouse', hideT = null;

    // enrich aria labels with the plain facts
    svg.selectAll('.cw-focus').each(function () {
      const pn = this.dataset.pn, f = facts(pn), num = this.dataset.n;
      if (!f) return;
      const off = f.rows[0].v.toLowerCase();
      this.setAttribute('aria-label', `${pad2(num)} · ${f.name} (${pn}): comes off ${off}. Open part page.`);
      this.setAttribute('aria-describedby', 'cw-card-live');
    });
    card.id = 'cw-card-live';

    function place(pn, from) {
      const g = svgEl.querySelector(`.cw-part[data-pn="${pn}"]`);
      const sr = svgEl.getBoundingClientRect(), st = stage.getBoundingClientRect();
      const k = sr.width / vb.width;
      let ax, ay;
      if (from === 'label') {
        const lab = svgEl.querySelector(`.cw-callout[data-pn="${pn}"] .cw-hitlabel`).getBBox();
        ax = lab.x + lab.width / 2; ay = lab.y + lab.height / 2;
      } else { ax = +g.dataset.ax; ay = +g.dataset.ay; }
      const px = sr.left - st.left + ax * k, py = sr.top - st.top + ay * k;
      const cw = card.offsetWidth, ch = card.offsetHeight, gap = 22;
      let x = px + gap, y = py - ch / 2;
      if (x + cw > st.width - 8) x = px - gap - cw;
      if (x < 8) x = Math.min(st.width - cw - 8, Math.max(8, px - cw / 2));
      y = Math.max(8, Math.min(st.height - ch - 8, y));
      if (from !== 'label' && x <= px && x + cw >= px && y <= py && y + ch >= py) y = py + gap; // never cover the part
      card.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
    }

    function show(pn, from = 'part', pin = false) {
      clearTimeout(hideT);
      const f = facts(pn);
      if (!f) return;
      if (active !== pn) {
        const num = svgEl.querySelector(`.cw-focus[data-pn="${pn}"]`)?.dataset.n;
        card.innerHTML = cardHTML(f, { href: partHref(pn), num });
      }
      active = pn; pinned = pin;
      card.hidden = false;
      card.classList.toggle('is-pinned', pin);
      svgEl.classList.add('has-active');
      svg.selectAll('.cw-part, .cw-callout, .cw-focus').classed('is-active', function () { return this.dataset.pn === pn; });
      place(pn, from);
    }
    function hide(now = false) {
      clearTimeout(hideT);
      const go = () => {
        if (pinned) return;
        active = null; card.hidden = true; svgEl.classList.remove('has-active');
        svg.selectAll('.is-active').classed('is-active', false);
      };
      if (now) go(); else hideT = setTimeout(go, 120);
    }
    const choose = (pn) => { if (typeof onSelect === 'function') onSelect(pn); };

    const targets = svg.selectAll('.cw-part, .cw-callout');
    targets
      .on('pointerenter', function (e) { lastPointer = e.pointerType || 'mouse'; if (lastPointer === 'mouse' && !pinned) show(this.dataset.pn, this.classList.contains('cw-callout') ? 'label' : 'part'); })
      .on('pointerleave', function (e) { if ((e.pointerType || 'mouse') === 'mouse') hide(); })
      .on('pointerdown', (e) => { lastPointer = e.pointerType || 'mouse'; })
      .on('click', function (e) {
        const pn = this.dataset.pn;
        if (lastPointer !== 'mouse' && !(pinned && active === pn)) { e.preventDefault(); show(pn, this.classList.contains('cw-callout') ? 'label' : 'part', true); return; }
        choose(pn);
      });
    svg.selectAll('.cw-focus')
      .on('focus', function () { show(this.dataset.pn, 'part'); })
      .on('blur', () => { pinned = false; hide(); })
      .on('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(this.dataset.pn); }
        if (e.key === 'Escape') { pinned = false; hide(true); }
      });
    const outside = (e) => { if (pinned && !stage.contains(e.target)) { pinned = false; hide(true); } };
    const onKey = (e) => { if (e.key === 'Escape' && active) { pinned = false; hide(true); } };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', onKey);
    const onResize = () => { if (active) place(active, 'part'); };
    window.addEventListener('resize', onResize);
    api.select = (pn) => show(pn, 'part', true);
    return () => { stopDraw && stopDraw(); document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', onKey); window.removeEventListener('resize', onResize); };
  }

  // ------------------------------------------------------------------ phones: simplified drawing + numbered list
  function mountSimple(svgText) {
    const fig = document.createElement('div');
    fig.className = 'cw-mfig';
    fig.innerHTML = svgText;
    const list = document.createElement('ol');
    list.className = 'cw-list';
    list.setAttribute('aria-label', 'Modelled parts in the cutaway');
    el.append(fig, list);
    const svgEl = fig.querySelector('svg');
    const svg = d3.select(svgEl);
    const stopDraw = startDraw(svgEl);
    const items = [...svgEl.querySelectorAll('.cw-part')].map((g) => ({ pn: g.dataset.pn, n: +g.dataset.n, label: g.dataset.label, ax: +g.dataset.ax, ay: +g.dataset.ay }))
      .sort((a, b) => a.n - b.n);
    const marker = svg.append('g').attr('class', 'cw-marker').attr('aria-hidden', 'true').style('display', 'none');
    marker.append('circle').attr('class', 'cw-ring').attr('r', 26);
    marker.append('rect').attr('class', 'cw-badge').attr('x', 18).attr('y', -46).attr('width', 46).attr('height', 30).attr('rx', 5);
    marker.append('text').attr('class', 'cw-badge-t').attr('x', 41).attr('y', -25).attr('text-anchor', 'middle');

    let open = null;
    function select(pn, { scroll = false } = {}) {
      const it = items.find((i) => i.pn === pn);
      list.querySelectorAll('.cw-item').forEach((b) => {
        const on = b.dataset.pn === pn && open !== pn;
        b.setAttribute('aria-expanded', String(on));
        b.closest('li').classList.toggle('is-open', on);
        document.getElementById(b.getAttribute('aria-controls')).hidden = !on;
      });
      open = open === pn ? null : pn;
      svg.selectAll('.cw-part').classed('is-active', function () { return this.dataset.pn === open; });
      svgEl.classList.toggle('has-active', !!open);
      if (open && it) {
        marker.style('display', null).attr('transform', `translate(${it.ax} ${it.ay})`);
        marker.select('text').text(pad2(it.n));
      } else marker.style('display', 'none');
      if (scroll && open) list.querySelector(`.cw-item[data-pn="${pn}"]`)?.scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
    }
    items.forEach((it) => {
      const f = facts(it.pn);
      const li = document.createElement('li');
      li.className = 'cw-li';
      const id = `cw-d-${it.pn}`;
      const name = f ? f.name : it.label;
      li.innerHTML = `<button type="button" class="cw-item" data-pn="${esc(it.pn)}" aria-expanded="false" aria-controls="${esc(id)}"
          aria-label="${esc(`${pad2(it.n)} · ${name} (${it.pn})${f ? `: comes off ${f.rows[0].v.toLowerCase()}` : ''}. Show details.`)}">
          <span class="cw-num mono">${pad2(it.n)}</span><span class="cw-iname">${esc(name)}</span><span class="cw-ipn mono">${esc(it.pn)}</span>
          <svg class="cw-chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></button>
        <div class="cw-detail" id="${esc(id)}" hidden>${cardHTML(f, { href: partHref(it.pn), compact: true })}</div>`;
      li.querySelector('.cw-item').addEventListener('click', () => select(it.pn));
      li.querySelector('.cw-link')?.addEventListener('click', (e) => { if (opts.onSelect) { e.preventDefault(); onSelect(it.pn); } });
      list.appendChild(li);
    });
    svg.selectAll('.cw-part').on('click', function () { select(this.dataset.pn, { scroll: true }); });
    api.select = (pn) => select(pn, { scroll: true });
    return () => { stopDraw && stopDraw(); };
  }

  const api = { select: () => {}, destroy() { cleanup(); mq.removeEventListener('change', render); el.innerHTML = ''; el.classList.remove('cw-root'); } };
  mq.addEventListener('change', render);
  await render();
  return api;
}
