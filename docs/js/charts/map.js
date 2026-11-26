/**
 * charts/map.js — network map (d3-geo + topojson + world-atlas, all self-hosted).
 *
 *   const map = await renderNetworkMap(host, {stations, arcs, onSelect, selected: 'BOM'});
 *   await map.animateTransfer('AUH', 'BOM', {kind: 'emergency'});   // replay helper
 *   map.select('LHR'); map.destroy();
 *
 * - Natural Earth land (1:110m) in very low-contrast steel + faint graticule.
 * - Geodesic arcs from the hub in teal with a gradient (faint at the hub, bright at the station).
 * - Airport nodes as precise rings with IATA labels in IBM Plex Mono; AUH hub has a soft radar
 *   pulse (disabled under prefers-reduced-motion).
 * - Detailed Europe–Middle East–Asia conic projection + world locator inset.
 * Station coordinates come from the data (network.json stations[]), which come from
 * config/assumptions.yaml network.stations (REAL, OurAirports).
 */
import { responsive, reducedMotion, tooltip, theme, fmtInt, fmtAED } from './theme.js';
import { assetURL } from '../data.js';

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
  const { stations = [], arcs = [], onSelect, inset = true, aspect = 0.56, labelSub, label = 'Network map' } = opts;
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
    const projection = d3().geoConicConformal().parallels([12, 46]).rotate([-50, 0]).fitExtent([[12, 12], [w - 12, hgt - 12]], boxPolygon(EXTENT)).clipExtent([[0, 0], [w, hgt]]);
    const path = d3().geoPath(projection);
    const defs = svg.append('defs');

    svg.append('path').datum(d3().geoGraticule10()).attr('class', 'map-graticule').attr('d', path);
    svg.append('path').datum(atlas.land).attr('class', 'map-land').attr('d', path);
    svg.append('path').datum(atlas.borders).attr('d', path).attr('fill', 'none').attr('stroke', 'rgba(185,200,214,0.09)').attr('stroke-width', 0.5);

    // arcs
    const arcLayer = svg.append('g').attr('class', 'map-arcs');
    const maxT = d3().max(arcs, (a) => a.transfers || 1) || 1;
    arcs.forEach((a, i) => {
      const A = byId[a.from], B = byId[a.to];
      if (!A || !B) return;
      const p0 = projection([A.lon, A.lat]), p1 = projection([B.lon, B.lat]);
      const gid = `${uid}-g${i}`;
      const grad = defs.append('linearGradient').attr('id', gid).attr('gradientUnits', 'userSpaceOnUse').attr('x1', p0[0]).attr('y1', p0[1]).attr('x2', p1[0]).attr('y2', p1[1]);
      grad.append('stop').attr('offset', '0%').attr('stop-color', theme.color.accent).attr('stop-opacity', 0.18);
      grad.append('stop').attr('offset', '100%').attr('stop-color', theme.color.accent).attr('stop-opacity', 0.95);
      const geo = { type: 'LineString', coordinates: [[A.lon, A.lat], [B.lon, B.lat]] };
      arcLayer.append('path').datum(a).attr('class', 'map-arc').attr('d', path(geo)).attr('stroke', `url(#${gid})`).attr('stroke-width', 1 + 2.2 * ((a.transfers || 1) / maxT))
        .on('pointerenter', (e) => tooltip.show(e, { title: `${a.from} → ${a.to}`, rows: [['AOG transport', `${a.aog_transport_h ?? '—'} h`], ['Transfers', fmtInt(a.transfers)], ['Emergency', fmtInt(a.emergency)]] }))
        .on('pointermove', (e) => tooltip.move(e)).on('pointerleave', () => tooltip.hide());
    });

    // nodes
    const nodeLayer = svg.append('g').attr('class', 'map-nodes');
    stations.forEach((s) => {
      const [x, y] = projection([s.lon, s.lat]);
      const isHub = s.role === 'hub';
      const g = nodeLayer.append('g').attr('transform', `translate(${x},${y})`).attr('tabindex', 0).attr('role', 'button').attr('aria-label', `${s.station} ${s.name || ''}`).style('cursor', onSelect ? 'pointer' : 'default').attr('data-station', s.station);
      if (isHub && !reducedMotion()) { g.append('circle').attr('class', 'map-pulse').attr('r', 9); g.append('circle').attr('class', 'map-pulse').attr('r', 9); }
      g.append('circle').attr('class', 'map-hit').attr('r', 16).attr('fill', 'transparent');
      g.append('circle').attr('class', `map-node ${isHub ? 'map-node--hub' : ''}`).attr('r', isHub ? 8 : 5.5);
      g.append('circle').attr('class', 'map-node-inner').attr('r', isHub ? 3 : 2).attr('fill', isHub ? theme.color.text : theme.color.accent);
      g.append('circle').attr('class', 'map-sel').attr('r', isHub ? 13 : 10).attr('fill', 'none').attr('stroke', theme.color.accentHi).attr('stroke-width', 1.25).attr('stroke-dasharray', '2 3').style('display', s.station === selected ? null : 'none');
      const [dx, dy, anchor] = LABEL[s.station] || [10, 4, 'start'];
      g.append('text').attr('class', 'map-label').attr('x', dx).attr('y', dy).attr('text-anchor', anchor).text(s.station);
      const sub = labelSub ? labelSub(s) : null;
      if (sub && w >= 520) g.append('text').attr('class', 'map-label-sub').attr('x', dx).attr('y', dy + 14).attr('text-anchor', anchor).text(sub);
      const tip = (e) => tooltip.show(e, { title: `${s.station} · ${s.name || ''}`, rows: [['Role', s.role], ['Serviceable units', fmtInt(s.serviceable_units)], ['Stock value', fmtAED(s.stock_value)], ['Requests', fmtInt(s.requests)]] });
      g.on('pointerenter', tip).on('pointermove', (e) => tooltip.move(e)).on('pointerleave', () => tooltip.hide());
      const fire = () => { api.select(s.station); onSelect?.(s.station); };
      g.on('click', fire).on('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fire(); } });
    });

    const tokenLayer = svg.append('g').attr('class', 'map-tokens');
    ctx = { svg, projection, path, tokenLayer, w, hgt };

    // world locator inset
    if (inset && w >= 520) {
      const iw = Math.max(120, Math.min(220, Math.round(w * 0.24))), ih = Math.round(iw * 0.52);
      const box = d3().select(host).append('div').attr('class', 'map-inset').attr('aria-hidden', 'true');
      const isvg = box.append('svg').attr('viewBox', `0 0 ${iw} ${ih}`).attr('width', iw).attr('height', ih);
      const ip = d3().geoNaturalEarth1().fitExtent([[4, 4], [iw - 4, ih - 4]], { type: 'Sphere' });
      const ipath = d3().geoPath(ip);
      isvg.append('path').datum({ type: 'Sphere' }).attr('class', 'map-sphere').attr('d', ipath);
      isvg.append('path').datum(atlas.land).attr('d', ipath).attr('fill', 'rgba(185,200,214,0.22)');
      isvg.append('path').datum(boxPolygon(EXTENT)).attr('class', 'map-inset-frame').attr('d', ipath);
      if (hub) { const [hx, hy] = ip([hub.lon, hub.lat]); isvg.append('circle').attr('cx', hx).attr('cy', hy).attr('r', 2.2).attr('fill', theme.color.accent); }
    }
  }

  const stop = responsive(host, draw);

  const api = {
    select(id) {
      selected = id;
      host.querySelectorAll('.map-sel').forEach((c) => { c.style.display = c.parentNode.dataset.station === id ? '' : 'none'; });
    },
    /** Animate one transfer along a geodesic arc. Resolves when done. kind: 'routine' | 'emergency' */
    animateTransfer(from, to, { duration = 1400, kind = 'routine' } = {}) {
      if (!ctx) return Promise.resolve();
      const A = byId[from], B = byId[to];
      if (!A || !B) return Promise.resolve();
      const color = kind === 'emergency' ? theme.color.accent2 : theme.color.accentHi;
      const p = ctx.tokenLayer.append('path').attr('d', ctx.path({ type: 'LineString', coordinates: [[A.lon, A.lat], [B.lon, B.lat]] })).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2).attr('stroke-linecap', 'round');
      const len = p.node().getTotalLength();
      if (reducedMotion()) {
        return new Promise((res) => setTimeout(() => { p.transition().duration(0).delay(600).remove(); res(); }, 600));
      }
      const dot = ctx.tokenLayer.append('circle').attr('r', 3.5).attr('class', 'map-token').attr('fill', color);
      p.attr('stroke-dasharray', `${len} ${len}`).attr('stroke-dashoffset', len);
      return new Promise((res) => {
        p.transition().duration(duration).ease(d3().easeCubicOut).attr('stroke-dashoffset', 0)
          .tween('dot', () => (t) => { const pt = p.node().getPointAtLength(d3().easeCubicOut(t) * len); dot.attr('cx', pt.x).attr('cy', pt.y); })
          .on('end', () => { dot.transition().duration(300).attr('r', 9).style('opacity', 0).remove(); p.transition().duration(600).style('opacity', 0).remove(); res(); });
      });
    },
    get projection() { return ctx?.projection; },
    destroy() { stop(); host.replaceChildren(); },
  };
  return api;
}
