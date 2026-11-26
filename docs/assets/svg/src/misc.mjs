// Rotable lifecycle flow, line-icon sprite, favicon mark and OG card — all original artwork.
import { el, g, path, text, n, svgDoc, C, FONT_MONO, FONT_DISPLAY } from './lib.mjs';

// ------------------------------------------------------------------ rotable lifecycle
const STATES = [
  { id: 'SERVICEABLE', label: 'SERVICEABLE', sub: 'IN STORES · STATIONS' },
  { id: 'INSTALLED', label: 'INSTALLED', sub: 'FITTED ON AIRCRAFT' },
  { id: 'REMOVED', label: 'REMOVED (U/S)', sub: 'CORE RETURNING TO AUH' },
  { id: 'IN_REPAIR', label: 'IN REPAIR', sub: 'QUEUE + SHOP WORK' },
];
const lifeStyle = `
.lc-node{fill:${C.midnight};fill-opacity:.9;stroke:${C.teal};stroke-width:1.2}
.lc-node-bad{fill:${C.midnight};stroke:${C.red};stroke-width:1.2;stroke-dasharray:5 3}
.lc-tick{stroke:${C.teal};stroke-width:2}
.lc-state{font-family:${FONT_MONO};fill:${C.ice};font-size:13px;font-weight:500;letter-spacing:.12em}
.lc-sub{font-family:${FONT_MONO};fill:${C.titanium};fill-opacity:.75;font-size:10px;letter-spacing:.12em}
.lc-count{font-family:${FONT_DISPLAY};fill:${C.teal};font-size:36px;font-weight:500;font-variant-numeric:tabular-nums}
.lc-count-bad{font-family:${FONT_DISPLAY};fill:${C.red};font-size:28px;font-weight:500}
.lc-unit{font-family:${FONT_MONO};fill:${C.titanium};font-size:11px;letter-spacing:.1em}
.lc-flow{fill:none;stroke:${C.teal};stroke-width:1.4;stroke-opacity:.85}
.lc-flow-bad{fill:none;stroke:${C.red};stroke-width:1.2;stroke-dasharray:5 3}
.lc-flowlab{font-family:${FONT_MONO};fill:${C.titanium};font-size:10px;letter-spacing:.14em}
.lc-flowcount{font-family:${FONT_MONO};fill:${C.ice};font-size:13px;font-weight:500}
.lc-step{font-family:${FONT_MONO};fill:${C.teal};font-size:10px;letter-spacing:.14em}
[data-state].is-active .lc-node{fill:${C.teal};fill-opacity:.1;stroke:${C.tealHi};filter:url(#bp-glow)}
`;

function node(x, y, w, h, st, i, bad = false) {
  return g(
    { 'data-state': st.id, class: 'lc-state-g' },
    el('rect', { x, y, width: w, height: h, rx: 10, class: bad ? 'lc-node-bad' : 'lc-node' }),
    bad ? '' : el('line', { x1: x + 16, y1: y, x2: x + 48, y2: y, class: 'lc-tick' }),
    text(x + 16, y + 24, bad ? 'TERMINAL' : `STATE 0${i + 1}`, 'lc-step'),
    text(x + 16, y + 44, st.label, 'lc-state'),
    text(x + 16, y + 84, '–', bad ? 'lc-count-bad' : 'lc-count', { 'data-count': st.id }),
    text(x + w - 16, y + 84, 'UNITS', 'lc-unit', { 'text-anchor': 'end' }),
    text(x + 16, y + h - 14, st.sub, 'lc-sub')
  );
}

function flowLabel(x, y, label, key, anchor = 'middle') {
  return g({}, text(x, y, label, 'lc-flowlab', { 'text-anchor': anchor }), text(x, y + 17, '–', 'lc-flowcount', { 'text-anchor': anchor, 'data-flow': key }));
}

function lifecycleH() {
  const W = 1200, H = 400, w = 222, h = 124, gap = (W - 80 - 4 * w) / 3, y = 92;
  const xs = STATES.map((_, i) => 40 + i * (w + gap));
  const parts = [];
  for (let i = 0; i < 3; i++) {
    const x1 = xs[i] + w + 6, x2 = xs[i + 1] - 6, yy = y + h / 2;
    parts.push(path(`M${n(x1)},${yy}H${n(x2)}`, 'lc-flow', { 'marker-end': 'url(#bp-arr-teal)' }));
  }
  parts.push(flowLabel((xs[0] + w + xs[1]) / 2, y + h / 2 - 26, 'FIT', 'SERVICEABLE>INSTALLED'));
  parts.push(flowLabel((xs[1] + w + xs[2]) / 2, y + h / 2 - 26, 'REMOVAL', 'INSTALLED>REMOVED'));
  parts.push(flowLabel((xs[2] + w + xs[3]) / 2, y + h / 2 - 26, 'INDUCT', 'REMOVED>IN_REPAIR'));
  // return to stock
  const rx = xs[3] + 26, lx = xs[0] + w / 2, by = y + h + 70;
  parts.push(path(`M${n(rx)},${y + h + 6}V${by - 12}Q${n(rx)},${by} ${n(rx - 12)},${by}H${n(lx + 12)}Q${n(lx)},${by} ${n(lx)},${by - 12}V${y + h + 8}`, 'lc-flow', { 'marker-end': 'url(#bp-arr-teal)' }));
  parts.push(flowLabel((rx + lx) / 2, by - 10, 'REPAIRED · RETURN TO STOCK (AUH)', 'IN_REPAIR>SERVICEABLE'));
  // condemned
  const cw = 172, cx = xs[3] + w - cw, cy = y + h + 44;
  parts.push(path(`M${n(cx + cw / 2)},${y + h + 6}V${cy - 6}`, 'lc-flow-bad', { 'marker-end': 'url(#bp-arr-teal)' }));
  parts.push(node(cx, cy, cw, 112, { id: 'CONDEMNED', label: 'CONDEMNED', sub: 'BER · REPLACE BY PO' }, 4, true));
  parts.push(flowLabel(cx + cw / 2 - 10, y + h + 22, 'BER', 'IN_REPAIR>CONDEMNED', 'end'));
  STATES.forEach((st, i) => parts.push(node(xs[i], y, w, h, st, i)));
  const head = g({ class: 'bp-frameset' }, text(40, 44, 'ROTABLE LIFECYCLE · SERIALISED UNITS', 'bp-t-ice'), text(40, 62, 'EACH SERIAL IS IN EXACTLY ONE STATE · COUNTS INJECTED FROM rotables.json', 'bp-t-xs'));
  return svgDoc({ w: W, h: H, title: 'Rotable lifecycle state flow', desc: 'Serviceable, installed, removed (unserviceable), in repair, then back to serviceable or condemned, with count slots.', extraStyle: lifeStyle, attrs: { class: 'bp-sheet bp-lifecycle' }, body: parts.join('') + head });
}

function lifecycleV() {
  const W = 420, H = 900, w = 300, h = 112, x = 84, gap = 56;
  const ys = STATES.map((_, i) => 96 + i * (h + gap));
  const parts = [];
  for (let i = 0; i < 3; i++) {
    parts.push(path(`M${x + 40},${ys[i] + h + 6}V${ys[i + 1] - 6}`, 'lc-flow', { 'marker-end': 'url(#bp-arr-teal)' }));
  }
  const keys = ['SERVICEABLE>INSTALLED', 'INSTALLED>REMOVED', 'REMOVED>IN_REPAIR'];
  const labs = ['ISSUE + FIT', 'REMOVAL', 'INDUCT'];
  keys.forEach((k, i) => parts.push(flowLabel(x + 56, ys[i] + h + 24, labs[i], k, 'start')));
  // return path on the left
  const lx = 40;
  parts.push(path(`M${x - 6},${ys[3] + h / 2}H${lx + 12}Q${lx},${ys[3] + h / 2} ${lx},${ys[3] + h / 2 - 12}V${ys[0] + h / 2 + 12}Q${lx},${ys[0] + h / 2} ${lx + 12},${ys[0] + h / 2}H${x - 6}`, 'lc-flow', { 'marker-end': 'url(#bp-arr-teal)' }));
  parts.push(g({}, text(lx - 10, (ys[0] + ys[3]) / 2 + h / 2, 'RETURN TO STOCK', 'lc-flowlab', { 'text-anchor': 'middle', transform: `rotate(-90 ${lx - 10} ${(ys[0] + ys[3]) / 2 + h / 2})` })));
  const cy = ys[3] + h + 48;
  parts.push(path(`M${x + w - 60},${ys[3] + h + 6}V${cy - 6}`, 'lc-flow-bad', { 'marker-end': 'url(#bp-arr-teal)' }));
  parts.push(node(x + 80, cy, w - 80, 112, { id: 'CONDEMNED', label: 'CONDEMNED', sub: 'BER · REPLACE BY PO' }, 4, true));
  STATES.forEach((st, i) => parts.push(node(x, ys[i], w, h, st, i)));
  const head = g({ class: 'bp-frameset' }, text(40, 44, 'ROTABLE LIFECYCLE', 'bp-t-ice'), text(40, 62, 'SERIALISED UNITS · COUNT SLOTS', 'bp-t-xs'));
  return svgDoc({ w: W, h: H, title: 'Rotable lifecycle state flow (vertical)', desc: 'Vertical variant of the rotable lifecycle for narrow screens.', extraStyle: lifeStyle, attrs: { class: 'bp-sheet bp-lifecycle' }, body: parts.join('') + head });
}

// ------------------------------------------------------------------ icons
// 24-px grid, 1.5-px stroke, round caps/joins, currentColor. Original drawings.
const ICONS = {
  aircraft: 'M12 2.6c.75 0 1.25.95 1.25 2.1v5.1l7.25 4.15v1.85l-7.25-2.05v4.55l2.25 1.7v1.55L12 20.7l-3.5.85V20l2.25-1.7v-4.55L3.5 15.8v-1.85l7.25-4.15V4.7c0-1.15.5-2.1 1.25-2.1z',
  part: 'M12 3.2l7.6 4.4v8.8L12 20.8l-7.6-4.4V7.6zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  rotable: 'M19.8 12a7.8 7.8 0 0 1-13.4 5.4M4.2 12a7.8 7.8 0 0 1 13.4-5.4M17.9 3.2v3.6h-3.6M6.1 20.8v-3.6h3.6',
  warehouse: 'M3.2 20V9.2L12 4.2l8.8 5V20M7 20v-7.2h10V20M7 16.4h10M2.5 20h19',
  route: 'M5.5 19.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM18.5 8.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6.6 15.8C8.4 10.4 12.2 7.6 16.6 6.9',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7.2V12l3.2 2',
  alert: 'M12 3.6 2.6 19.8h18.8zM12 9.8v4.4M12 16.9v.1',
  check: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8.2 12.3l2.6 2.6 5-5.3',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5.2M12 7.9v.1',
  capital: 'M5 6.8c0-1.4 3.1-2.5 7-2.5s7 1.1 7 2.5-3.1 2.5-7 2.5-7-1.1-7-2.5zM5 6.8v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-5M5 11.8v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-5',
  wrench: 'M14.6 3.6a4.6 4.6 0 0 0-4.4 6.1L3.6 16.3a1.9 1.9 0 0 0 2.7 2.7l6.6-6.6a4.6 4.6 0 0 0 6.1-4.4l-2.7 2.7-2.6-.5-.5-2.6z',
  filter: 'M3.8 5h16.4l-6.3 7.6v6.2l-3.8-1.9v-4.3z',
  download: 'M12 3.8v11M7.4 10.4 12 15l4.6-4.6M4.8 19.6h14.4',
  play: 'M8 5.2v13.6L18.8 12z',
  'map-pin': 'M12 21.2s-6.6-5.7-6.6-11.1a6.6 6.6 0 0 1 13.2 0c0 5.4-6.6 11.1-6.6 11.1zM12 7.8a2.3 2.3 0 1 0 0 4.6 2.3 2.3 0 0 0 0-4.6z',
  chart: 'M4 3.8V20h16.2M7.6 15.4l3.6-4.2 3 2.6 4.6-5.6',
  flask: 'M9.2 3.6h5.6M10.4 3.6v5.3l-5.2 9.2a1.6 1.6 0 0 0 1.4 2.4h10.8a1.6 1.6 0 0 0 1.4-2.4l-5.2-9.2V3.6M7.4 14.2h9.2',
  inbox: 'M3.4 13.6 6 5.2h12l2.6 8.4v5.2H3.4zM3.4 13.6h5.2l1.2 2.5h4.4l1.2-2.5h5.2',
  shield: 'M12 3l7.6 3v5.6c0 4.5-3.2 8-7.6 9.6-4.4-1.6-7.6-5.1-7.6-9.6V6zM8.9 12.1l2.2 2.2 4.1-4.3',
  book: 'M12 6.6C10.2 5.2 7.5 4.6 3.8 4.6v13.2c3.7 0 6.4.6 8.2 2 1.8-1.4 4.5-2 8.2-2V4.6c-3.7 0-6.4.6-8.2 2zM12 6.6v13.2',
  'arrow-up': 'M12 19V5.4M6.6 10.8 12 5.4l5.4 5.4',
  'arrow-down': 'M12 5v13.6M6.6 13.2 12 18.6l5.4-5.4',
  'chevron-right': 'M9.5 5.5 16 12l-6.5 6.5',
  close: 'M6 6l12 12M18 6 6 18',
  menu: 'M4 7h16M4 12h16M4 17h10',
  sort: 'M8 4.5v15M4.5 8 8 4.5 11.5 8M16 19.5v-15M12.5 16l3.5 3.5 3.5-3.5',
  keyboard: 'M3 6.5h18v11H3zM6.5 10h.1M10 10h.1M13.5 10h.1M17 10h.1M7.5 14h9',
  minus: 'M5 12h14',
  layers: 'M12 3.6 2.8 8.4 12 13.2l9.2-4.8zM2.8 12.4 12 17.2l9.2-4.8M2.8 16.4 12 21.2l9.2-4.8',
  target: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7.4a4.6 4.6 0 1 0 0 9.2 4.6 4.6 0 0 0 0-9.2zM12 11.2v1.6',
};

function sprite() {
  const syms = Object.entries(ICONS).map(([id, d]) =>
    el('symbol', { id: `i-${id}`, viewBox: '0 0 24 24' }, el('path', { d, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }))
  );
  return `<?xml version="1.0" encoding="UTF-8"?>\n<!-- GROUNDED NO MORE original line-icon sprite: 24 px grid, 1.5 px stroke, currentColor. Use: <svg><use href="assets/svg/icons.svg#i-aircraft"/></svg> -->\n` + el('svg', { xmlns: 'http://www.w3.org/2000/svg', style: 'display:none' }, syms) + '\n';
}

// ------------------------------------------------------------------ favicon mark
const MARK_PLANE = 'M16 7.2c.5 0 .85.6.85 1.4v4l5.4 3.1v1.35l-5.4-1.5v3.3l1.6 1.2v1.1L16 20.6l-2.45.55v-1.1l1.6-1.2v-3.3l-5.4 1.5V15.7l5.4-3.1v-4c0-.8.35-1.4.85-1.4z';
function favicon() {
  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n<!-- GROUNDED NO MORE mark: original blueprint aircraft silhouette in a ring. -->\n` +
    el(
      'svg',
      { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 32 32', width: 32, height: 32 },
      el('rect', { width: 32, height: 32, rx: 8, fill: C.midnight }),
      el('circle', { cx: 16, cy: 16, r: 11.5, fill: 'none', stroke: C.teal, 'stroke-width': 1.4 }),
      el('path', { d: 'M16 2.8v3M16 26.2v3M2.8 16h3M26.2 16h3', stroke: C.titanium, 'stroke-opacity': 0.6, 'stroke-width': 1.2, 'stroke-linecap': 'round' }),
      el('path', { d: MARK_PLANE, fill: C.teal, transform: 'translate(0 -1.6) scale(1)' })
    ) +
    '\n'
  );
}

// ------------------------------------------------------------------ OG card (rendered to PNG by scripts/screenshot.py)
function ogCard(topSvg) {
  const inner = topSvg.replace(/^[\s\S]*?<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '').replace(/<title[\s\S]*?<\/desc>/, '');
  return svgDoc({
    w: 1200,
    h: 630,
    title: 'GROUNDED NO MORE — aviation spare-parts intelligence',
    desc: 'Open-graph card: blueprint aircraft and project title.',
    body:
      el('rect', { width: 1200, height: 630, fill: C.midnight }) +
      el('rect', { width: 1200, height: 630, fill: 'url(#bp-grid)' }) +
      `<svg class="bp-compact" x="560" y="16" width="640" height="598" viewBox="335 75 769 818" preserveAspectRatio="xMidYMid meet">${inner}</svg>` +
      el('text', { x: 64, y: 120, 'font-family': FONT_MONO, 'font-size': 18, fill: C.teal, 'letter-spacing': '0.2em' }, 'SPARES INTELLIGENCE WORKSPACE') +
      el('text', { x: 64, y: 210, 'font-family': FONT_DISPLAY, 'font-size': 72, 'font-weight': 600, fill: C.ice, 'letter-spacing': '0.02em' }, 'GROUNDED') +
      el('text', { x: 64, y: 290, 'font-family': FONT_DISPLAY, 'font-size': 72, 'font-weight': 600, fill: C.ice, 'letter-spacing': '0.02em' }, 'NO MORE') +
      el('text', { x: 64, y: 360, 'font-family': FONT_DISPLAY, 'font-size': 24, fill: C.titanium }, 'A single missing part can ground an aircraft.') +
      el('text', { x: 64, y: 394, 'font-family': FONT_DISPLAY, 'font-size': 24, fill: C.titanium }, 'Know which ones, where, and what to do.') +
      el('text', { x: 64, y: 560, 'font-family': FONT_MONO, 'font-size': 14, fill: C.amber, 'letter-spacing': '0.12em' }, 'FALCON HUB AIRWAYS (FICTIONAL) · EDUCATIONAL SIMULATION'),
  });
}

export function files(ctx = {}) {
  return {
    'rotable-lifecycle.svg': lifecycleH(),
    'rotable-lifecycle-vertical.svg': lifecycleV(),
    'icons.svg': sprite(),
    '../favicon.svg': favicon(),
    'og-card.svg': ctx.top ? ogCard(ctx.top) : undefined,
  };
}
export { ICONS };
