/**
 * charts/map.js — network map (d3-geo + topojson + world-atlas, all self-hosted).
 *
 *   const map = await renderNetworkMap(host, {stations, arcs, onSelect, selected: 'BOM'});
 *   await map.animateTransfer('AUH', 'BOM', {kind: 'emergency'});   // replay helper
 *   map.select('LHR'); map.destroy();
 *
 * - Natural Earth land (1:110m) in very low-contrast steel + faint graticule.
 * - Geodesic arcs from the hub in neutral titanium with a gradient (faint at the hub, bright at the station).
 * - Airport nodes as precise rings with IATA labels in IBM Plex Mono; AUH hub has a soft radar
 *   pulse (disabled under prefers-reduced-motion).
 * - Detailed Europe–Middle East–Asia conic projection + world locator inset.
 * Station coordinates come from the data (network.json stations[]), which come from
 * config/assumptions.yaml network.stations (REAL, OurAirports).
 *
 * Labels: the IATA code and its optional sub-label (labelSub) are placed as ONE block directly under/beside the
 * node, avoiding every node ring, arc value chip and previously placed label (preferred offset first:
 * labelOffsets[station] → LABEL default → 8 fallback positions). All labels carry a halo.
 * Arc values: arcLabel(arc) → string draws a chipLabel() (filled pill) at the arc midpoint.
 * The world locator inset only renders when the map is ≥ 900 px wide (it collided with SIN on narrower cards).
 * Emergency replays use theme.series.urgent (red = urgent / AOG risk); copper is reserved for capital/baseline.
 */
import { responsive, reducedMotion, tooltip, theme, fmtInt, fmtAED, chipLabel, markerRect } from './theme.js';
import { assetURL } from '../data.js';
import { MOTION, EASE } from '../lib/motion.js';

const d3 = () => window.d3;
let atlasPromise = null;
function loadAtlas() {
  if (!atlasPromise) {
    atlasPromise = Promise.all([
      fetch(assetURL('vendor/world-atlas/land-110m.json')).then((r) => r.json()),
      fetch(assetURL('vendor/world-atlas/countries-110m.json')).then((r) => r.json()),
    ]).then(([land, countries]) => ({
      land: window.topojson.feature(land, land.objects.land),
      borders: window.topojson.mesh(countries, countries.objects.countries, (a, b) => a !== b),
    }));
  }
  return atlasPromise;
}

// label placement (dx, dy, anchor) per station; default right
const LABEL = { AUH: [12, 18, 'start'], LHR: [-12, -4, 'end'], FRA: [12, 4, 'start'], CAI: [-12, 4, 'end'], JED: [-12, 10, 'end'], BOM: [12, 4, 'start'], SIN: [12, 4, 'start'] };
// detail extent (lon/lat) — Europe, Middle East, South & South-East Asia
const EXTENT = { lon: [-14, 114], lat: [-8, 60] };

/** Label block (IATA 12 px mono + optional 11 px sub line) bbox for a text anchored at (x, y) = baseline. */
function blockBox(x, y, anchor, code, sub) {
  const w = Math.max(code.length * 8, sub ? sub.length * 6.9 : 0);
  const hgt = sub ? 30 : 15;
  const x0 = anchor === 'end' ? x - w : anchor === 'middle' ? x - w / 2 : x;
  return { x: x0 - 2, y: y - 11, width: w + 4, height: hgt };
}
const ov = (a, b) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
/** Pick [dx, dy, anchor] for a station label: preferred offset first, then 8 positions around the node; least overlap wins. */
function placeStationLabel(x, y, r, pref, code, sub, obstacles, placed, w, hgt) {
  const d = r + 6;
  const subH = sub ? 14 : 0;
  const cands = [pref,
    [0, d + 11, 'middle'], [d, 4, 'start'], [-d, 4, 'end'], [0, -d - 4 - subH, 'middle'],
    [d * 0.8, d + 8, 'start'], [-d * 0.8, d + 8, 'end'], [d * 0.8, -d - subH, 'start'], [-d * 0.8, -d - subH, 'end']];
  const self = markerRect(x, y, r + 1, 2);
  let best = null;
  cands.forEach((c, i) => {
    const box = blockBox(x + c[0], y + c[1], c[2], code, sub);
    const out = Math.max(0, -box.x) + Math.max(0, box.x + box.width - w) + Math.max(0, -box.y) + Math.max(0, box.y + box.height - hgt);
    const cost = obstacles.filter((o) => o !== self && !(Math.abs(o.x - self.x) < 0.5 && Math.abs(o.y - self.y) < 0.5)).reduce((t, o) => t + ov(box, o), 0) + placed.reduce((t, o) => t + ov(box, o) * 2, 0) + out * 30 + i * 0.5;
    if (!best || cost < best.cost) best = { cost, c, box };
  });
  placed.push(best.box);
  return best.c;
}

function boxPolygon({ lon, lat }, n = 24) {
  const pts = [];
  for (let i = 0; i <= n; i++) pts.push([lon[0] + ((lon[1] - lon[0]) * i) / n, lat[0]]);
  for (let i = 0; i <= n; i++) pts.push([lon[1], lat[0] + ((lat[1] - lat[0]) * i) / n]);
  for (let i = 0; i <= n; i++) pts.push([lon[1] - ((lon[1] - lon[0]) * i) / n, lat[1]]);
  for (let i = 0; i <= n; i++) pts.push([lon[0], lat[1] - ((lat[1] - lat[0]) * i) / n]);
  return { type: 'Polygon', coordinates: [pts.reverse()] };
}

/**
 * @param {HTMLElement} host
 * @param {{stations: object[], arcs?: object[], selected?: string, onSelect?: Function,
 *          inset?: boolean, aspect?: number, labelSub?: (s)=>string, label?: string}} opts
 */
export async function renderNetworkMap(host, opts = {}) {
  const { stations = [], arcs = [], proposed = [], onSelect, inset = true, insetMinWidth = 900, aspect = 0.56, labelSub, label = 'Network map', nodeRadius, nodeColor, tooltipRows, onDraw, nodeAria, labelOffsets = {}, arcLabel, autoLabels = true } = opts;
  let selected = opts.selected || null;
  const atlas = await loadAtlas();
  host.classList.add('map-host');
  const hub = stations.find((s) => s.role === 'hub') || stations[0];
  const byId = Object.fromEntries(stations.map((s) => [s.station, s]));
  let ctx = null; // current render context (projection, layers)
  const uid = `m${Math.random().toString(36).slice(2, 7)}`;

  function draw(w) {
    const hgt = Math.max(260, Math.round(w * aspect));
    host.querySelectorAll('svg.map-main, .map-inset').forEach((n) => n.remove());
    const svg = d3().select(host).append('svg').attr('class', 'map-main').attr('viewBox', `0 0 ${w} ${hgt}`).attr('width', w).attr('height', hgt).attr('role', 'img').attr('aria-label', label);
    // wave A: the projection is fitted to the network itself (AUH, Europe, the Middle East and Asia), not a world box
    const pad = Math.max(36, Math.round(w * 0.06));
    const fitTo = stations.length >= 2 ? { type: 'MultiPoint', coordinates: stations.map((s) => [s.lon, s.lat]) } : boxPolygon(EXTENT);
    const projection = d3().geoConicConformal().parallels([12, 46]).rotate([-50, 0]).fitExtent([[pad, pad * 1.35], [w - pad - 28, hgt - pad * 1.2]], fitTo).clipExtent([[0, 0], [w, hgt]]);
    const path = d3().geoPath(projection);
    const defs = svg.append('defs');

    svg.append('path').datum(d3().geoGraticule10()).attr('class', 'map-graticule').attr('d', path);
    svg.append('path').datum(atlas.land).attr('class', 'map-land').attr('d', path);
    svg.append('path').datum(atlas.borders).attr('class', 'map-border').attr('d', path);

    // arcs
    const arcLayer = svg.append('g').attr('class', 'map-arcs');
    const arcChipLayer = svg.append('g').attr('class', 'map-arc-chips');
    const obstacles = []; // px rects (node rings, arc chips) that station labels must avoid
    const maxT = d3().max(arcs, (a) => a.transfers || 1) || 1;
    arcs.forEach((a, i) => {
      const A = byId[a.from], B = byId[a.to];
      if (!A || !B) return;
      const p0 = projection([A.lon, A.lat]), p1 = projection([B.lon, B.lat]);
      const gid = `${uid}-g${i}`;
      const grad = defs.append('linearGradient').attr('id', gid).attr('gradientUnits', 'userSpaceOnUse').attr('x1', p0[0]).attr('y1', p0[1]).attr('x2', p1[0]).attr('y2', p1[1]);
      // routine arcs are neutral titanium: teal is reserved for the recommended plan (wave 4, C5)
      grad.append('stop').attr('offset', '0%').attr('stop-color', theme.series.neutral).attr('stop-opacity', 0.15);
      grad.append('stop').attr('offset', '100%').attr('stop-color', theme.series.neutral).attr('stop-opacity', 0.7);
      const geo = { type: 'LineString', coordinates: [[A.lon, A.lat], [B.lon, B.lat]] };
      // route hierarchy: width follows history transfer volume (1–5 px), so the busy hub routes read first
      arcLayer.append('path').datum(a).attr('class', 'map-arc map-arc--hist').attr('d', path(geo)).attr('stroke', `url(#${gid})`).attr('stroke-width', 1 + 4 * Math.sqrt((a.transfers || 1) / maxT))
        .on('pointerenter', (e) => tooltip.show(e, { title: `${a.from} → ${a.to}`, rows: [['AOG transport', `${a.aog_transport_h ?? '—'} h`], ['Transfers', fmtInt(a.transfers)], ['Emergency', fmtInt(a.emergency)]] }))
        .on('pointermove', (e) => tooltip.move(e)).on('pointerleave', () => tooltip.hide());
      // sample the arc into small boxes so station labels avoid sitting on top of it
      try { const pn = arcLayer.select('path:last-child').node(); const L = pn.getTotalLength(); for (let t = 10; t < L - 10; t += 8) { const q = pn.getPointAtLength(t); obstacles.push({ x: q.x - 2, y: q.y - 2, width: 4, height: 4, arc: true }); } } catch { /* ignore */ }
      const txt = arcLabel ? arcLabel(a) : null;
      if (txt != null && txt !== '') {
        const node = arcLayer.select('path:last-child').node();
        let mid = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2];
        try { const L = node.getTotalLength(); const pt = node.getPointAtLength(L / 2); mid = [pt.x, pt.y]; } catch { /* keep chord midpoint */ }
        const chip = chipLabel(arcChipLayer, { x: mid[0], y: mid[1], text: String(txt), color: theme.color.text });
        obstacles.push(chip.datum().box);
      }
    });
    // proposed movements (recommended plan): dashed teal arrows, visually distinct from the solid history arcs
    const propLayer = svg.append('g').attr('class', 'map-proposed');
    defs.append('marker').attr('id', `${uid}-arr`).attr('viewBox', '0 0 10 10').attr('refX', 9).attr('refY', 5).attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto').attr('markerUnits', 'userSpaceOnUse')
      .append('path').attr('d', 'M0,1L10,5L0,9Z').attr('fill', theme.series.recommended);
    proposed.forEach((m) => {
      const A = byId[m.from], B = byId[m.to];
      if (!A || !B) return;
      const p0 = projection([A.lon, A.lat]), p1 = projection([B.lon, B.lat]);
      const dx = p1[0] - p0[0], dy = p1[1] - p0[1], L = Math.hypot(dx, dy) || 1;
      const rB = (nodeRadius ? nodeRadius(B) : 6) + 5;
      const end = [p1[0] - (dx / L) * rB, p1[1] - (dy / L) * rB];
      const bend = [(p0[0] + end[0]) / 2 - (dy / L) * L * 0.12, (p0[1] + end[1]) / 2 + (dx / L) * L * 0.12];
      propLayer.append('path').datum(m).attr('class', 'map-arc map-arc--proposed').attr('d', `M${p0[0]},${p0[1]}Q${bend[0]},${bend[1]} ${end[0]},${end[1]}`).attr('marker-end', `url(#${uid}-arr)`)
        .on('pointerenter', (e) => tooltip.show(e, { title: `Proposed · ${m.from} → ${m.to}`, rows: [['Movement', m.label || 'positioning'], ['Basis', m.basis || 'recommended plan']] }))
        .on('pointermove', (e) => tooltip.move(e)).on('pointerleave', () => tooltip.hide());
    });
    stations.forEach((s) => { const [x, y] = projection([s.lon, s.lat]); const r = nodeRadius ? nodeRadius(s) : s.role === 'hub' ? 8 : 5.5; obstacles.push(markerRect(x, y, r + 1, 2)); });
    const placedLabels = [];

    // nodes
    const nodeLayer = svg.append('g').attr('class', 'map-nodes');
    stations.forEach((s) => {
      const [x, y] = projection([s.lon, s.lat]);
      const isHub = s.role === 'hub';
      const g = nodeLayer.append('g').attr('transform', `translate(${x},${y})`).attr('tabindex', 0).attr('role', 'button').attr('aria-label', nodeAria ? nodeAria(s) : `${s.station} ${s.name || ''}`).style('cursor', onSelect ? 'pointer' : 'default').attr('data-station', s.station);
      if (isHub && !reducedMotion()) { g.append('circle').attr('class', 'map-pulse').attr('r', 9); g.append('circle').attr('class', 'map-pulse').attr('r', 9); }
      g.append('circle').attr('class', 'map-hit').attr('r', 16).attr('fill', 'transparent');
      // optional (additive): nodeRadius(s) → px, nodeColor(s) → stroke colour; defaults unchanged
      const nr = nodeRadius ? nodeRadius(s) : isHub ? 8 : 5.5;
      const nc = nodeColor ? nodeColor(s) : null;
      const node = g.append('circle').attr('class', `map-node ${isHub ? 'map-node--hub' : ''}`).attr('r', nr);
      if (nc) node.style('stroke', nc);
      g.append('circle').attr('class', 'map-node-inner').attr('r', isHub ? 3 : 2).attr('fill', nc || (isHub ? theme.color.text : theme.series.neutral));
      g.append('circle').attr('class', 'map-sel').attr('r', nr + 5).attr('fill', 'none').attr('stroke', theme.color.accentHi).attr('stroke-width', 1.25).attr('stroke-dasharray', '2 3').style('display', s.station === selected ? null : 'none');
      const sub = labelSub ? labelSub(s) : null;
      const showSub = !!(sub && w >= 520);
      // labelOffsets: optional per-view override. With a sub-label the block defaults to centred under the node.
      const pref = labelOffsets[s.station] || (showSub && autoLabels ? [0, nr + 17, 'middle'] : LABEL[s.station] || [10, 4, 'start']);
      const [dx, dy, anchor] = autoLabels ? placeStationLabel(x, y, nr, pref, s.station, showSub ? sub : null, obstacles, placedLabels, w, hgt) : pref;
      g.append('text').attr('class', 'map-label').attr('x', dx).attr('y', dy).attr('text-anchor', anchor).text(s.station);
      if (showSub) g.append('text').attr('class', 'map-label-sub').attr('x', dx).attr('y', dy + 14).attr('text-anchor', anchor).text(sub);
      const tip = (e) => tooltip.show(e, { title: `${s.station} · ${s.name || ''}`, rows: tooltipRows ? tooltipRows(s) : [['Role', s.role], ['Serviceable units', fmtInt(s.serviceable_units)], ['Stock value', fmtAED(s.stock_value)], ['Requests', fmtInt(s.requests)]] });
      g.on('pointerenter', tip).on('pointermove', (e) => tooltip.move(e)).on('pointerleave', () => tooltip.hide());
      const fire = () => { api.select(s.station); onSelect?.(s.station); };
      g.on('click', fire).on('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fire(); } });
    });

    const tokenLayer = svg.append('g').attr('class', 'map-tokens');
    ctx = { svg, projection, path, tokenLayer, w, hgt };
    onDraw?.(ctx); // optional (additive): lets a view decorate after each responsive redraw

    // world locator inset
    if (inset && w >= insetMinWidth) {
      const iw = Math.max(120, Math.min(220, Math.round(w * 0.24))), ih = Math.round(iw * 0.52);
      const box = d3().select(host).append('div').attr('class', 'map-inset').attr('aria-hidden', 'true');
      const isvg = box.append('svg').attr('viewBox', `0 0 ${iw} ${ih}`).attr('width', iw).attr('height', ih);
      const ip = d3().geoNaturalEarth1().fitExtent([[4, 4], [iw - 4, ih - 4]], { type: 'Sphere' });
      const ipath = d3().geoPath(ip);
      isvg.append('path').datum({ type: 'Sphere' }).attr('class', 'map-sphere').attr('d', ipath);
      isvg.append('path').datum(atlas.land).attr('d', ipath).attr('fill', 'rgba(185,200,214,0.22)');
      isvg.append('path').datum(boxPolygon(EXTENT)).attr('class', 'map-inset-frame').attr('d', ipath);
      if (hub) { const [hx, hy] = ip([hub.lon, hub.lat]); isvg.append('circle').attr('cx', hx).attr('cy', hy).attr('r', 2.2).attr('fill', theme.color.text); }
    }
  }

  const stop = responsive(host, draw);

  const api = {
    select(id) {
      selected = id;
      host.querySelectorAll('.map-sel').forEach((c) => { c.style.display = c.parentNode.dataset.station === id ? '' : 'none'; });
    },
    /** Animate one transfer along a geodesic arc. Resolves when done. kind: 'routine' | 'emergency' */
    animateTransfer(from, to, { duration = MOTION.hero, kind = 'routine' } = {}) {
      if (!ctx) return Promise.resolve();
      const A = byId[from], B = byId[to];
      if (!A || !B) return Promise.resolve();
      const color = kind === 'emergency' ? theme.series.urgent : theme.series.neutral;
      const p = ctx.tokenLayer.append('path').attr('d', ctx.path({ type: 'LineString', coordinates: [[A.lon, A.lat], [B.lon, B.lat]] })).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2).attr('stroke-linecap', 'round');
      const len = p.node().getTotalLength();
      if (reducedMotion()) {
        return new Promise((res) => setTimeout(() => { p.remove(); res(); }, MOTION.slow));
      }
      const dot = ctx.tokenLayer.append('circle').attr('r', 3.5).attr('class', 'map-token').attr('fill', color);
      p.attr('stroke-dasharray', `${len} ${len}`).attr('stroke-dashoffset', len);
      return new Promise((res) => {
        p.transition().duration(duration).ease(EASE.standard).attr('stroke-dashoffset', 0)
          .tween('dot', () => (t) => { const pt = p.node().getPointAtLength(t * len); dot.attr('cx', pt.x).attr('cy', pt.y); })
          .on('end', () => { dot.transition().duration(MOTION.base).ease(EASE.exit).attr('r', 9).style('opacity', 0).remove(); p.transition().duration(MOTION.slow).ease(EASE.exit).style('opacity', 0).remove(); res(); });
      });
    },
    get projection() { return ctx?.projection; },
    destroy() { stop(); host.replaceChildren(); },
  };
  return api;
}
