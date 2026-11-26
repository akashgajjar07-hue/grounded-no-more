// Exploded schematic diagrams of FICTIONAL components, one per ATA system.
// Stylised isometric LRUs (boxes, cylinders, valves, actuators). No OEM part is depicted.
// Each part has a label slot the app fills at runtime:
//   <g class="bp-label" data-slot="1" data-role="pack-valve">
//     <text data-field="pn">GN-21-·····</text><text data-field="desc">PACK FLOW CONTROL VALVE</text>
//   </g>
import { el, g, path, text, poly, n, svgDoc, iso, isoBox, isoCyl, C } from './lib.mjs';

const W = 960, H = 600;
const O = [W / 2, 318];
const S = 1;
const P = (p) => iso(p, S, O);
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
const AX = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };

const isoStyle = `
.bp-iso .bp-face-t{fill:${C.teal};fill-opacity:.13;stroke:${C.teal};stroke-width:1.1;stroke-linejoin:round}
.bp-iso .bp-face-l{fill:${C.paper};stroke:${C.teal};stroke-width:1.1;stroke-linejoin:round}
.bp-iso .bp-face-r{fill:${C.teal};fill-opacity:.05;stroke:${C.teal};stroke-width:1.1;stroke-linejoin:round}
.bp-iso .bp-detail,.bp-detail{fill:none;stroke:${C.teal};stroke-width:.7;stroke-opacity:.55}
.bp-part{transition:opacity .3s}
.bp-part.is-active .bp-face-t{fill-opacity:.3;stroke:${C.tealHi}}
.bp-part.is-active{filter:url(#bp-glow)}
.bp-label .bp-pn{font-family:'IBM Plex Mono',ui-monospace,monospace;fill:${C.ice};font-size:16px;font-weight:500;letter-spacing:.06em}
.bp-label .bp-desc{font-family:'IBM Plex Mono',ui-monospace,monospace;fill:${C.titanium};font-size:12.5px;letter-spacing:.08em}
`;

// ---------- primitives (each returns {svg, top, bottom} with 3-D anchor points) ----------
function box(c, [w, d, h], { fins = 0, plate = false, conns = 0, vents = 0 } = {}) {
  const o = add(c, [-w / 2, -d / 2, -h / 2]);
  const Q = (a, b, z) => P(add(o, [a, b, z]));
  const parts = [isoBox(O, o, [w, d, h], S)];
  const det = [];
  for (let i = 1; i <= fins; i++) {
    const yy = (d * i) / (fins + 1);
    det.push(path(poly([Q(w, yy, h * 0.14), Q(w, yy, h * 0.86)]), 'bp-detail'));
  }
  for (let i = 1; i <= vents; i++) {
    const zz = h * (0.2 + (0.25 * i) / vents);
    det.push(path(poly([Q(w * 0.18, d, zz), Q(w * 0.82, d, zz)]), 'bp-detail'));
  }
  if (plate) det.push(path(poly([Q(w * 0.16, d, h * 0.58), Q(w * 0.84, d, h * 0.58), Q(w * 0.84, d, h * 0.86), Q(w * 0.16, d, h * 0.86)], true), 'bp-detail'));
  const conn = [];
  for (let i = 1; i <= conns; i++) {
    const yy = (d * i) / (conns + 1);
    conn.push(isoCyl(O, add(o, [w, yy, h * 0.42]), AX.x, Math.min(d / (conns + 2), h / 5), 7, S, { capInner: 0.55 }));
  }
  return { svg: g({}, parts, det, conn), top: add(c, [0, 0, h / 2]), bottom: add(c, [0, 0, -h / 2]) };
}

function cyl(c, r, len, axis = 'x', { rings = [], cap = 0, flange = 0 } = {}) {
  const a = AX[axis];
  const start = add(c, mul(a, -len / 2));
  const parts = [];
  if (flange) parts.push(isoCyl(O, add(start, mul(a, -4)), a, r * flange, 5, S));
  parts.push(isoCyl(O, start, a, r, len, S, { rings, capInner: cap }));
  if (flange) parts.push(isoCyl(O, add(start, mul(a, len - 1)), a, r * flange, 5, S, { capInner: 0.7 }));
  const up = axis === 'z' ? len / 2 : r;
  return { svg: g({}, parts), top: add(c, [0, 0, up]), bottom: add(c, [0, 0, -up]) };
}

function valve(c, r, len, axis = 'x') {
  const body = cyl(c, r, len, axis, { flange: 1.42, rings: [0.5] });
  const act = box(add(c, [0, 0, r + 15]), [r * 1.5, r * 1.5, 26], { conns: 1 });
  const stem = isoCyl(O, add(c, [0, 0, r * 0.7]), AX.z, r * 0.28, 6, S);
  return { svg: g({}, body.svg, stem, act.svg), top: add(c, [0, 0, r + 28]), bottom: body.bottom };
}

function actuator(c, r, len) {
  const a = AX.x;
  const s0 = add(c, [-len / 2, 0, 0]);
  const eyeA = isoCyl(O, add(s0, [-r * 0.9, -r * 0.45, 0]), AX.y, r * 0.55, r * 0.9, S, { capInner: 0.45 });
  const barrel = isoCyl(O, s0, a, r, len * 0.62, S, { rings: [0.12, 0.88], capInner: 0.42 });
  const rod = isoCyl(O, add(s0, [len * 0.62, 0, 0]), a, r * 0.36, len * 0.38, S);
  const eyeB = isoCyl(O, add(s0, [len + r * 0.5, -r * 0.4, 0]), AX.y, r * 0.5, r * 0.8, S, { capInner: 0.45 });
  const port = isoCyl(O, add(s0, [len * 0.2, 0, r * 0.8]), AX.z, r * 0.22, r * 0.5, S);
  return { svg: g({}, eyeA, barrel, port, rod, eyeB), top: add(c, [-len * 0.15, 0, r]), bottom: add(c, [-len * 0.15, 0, -r]) };
}

function stack(c, r, t, count, gap, axis = 'y') {
  const a = AX[axis];
  const out = [];
  for (let i = 0; i < count; i++) out.push(isoCyl(O, add(c, mul(a, (i - (count - 1) / 2) * (t + gap) - t / 2)), a, r, t, S, { capInner: 0.42 }));
  return { svg: g({}, out), top: add(c, [0, 0, r]), bottom: add(c, [0, 0, -r]) };
}

function hardware(c, count, r, len, axis = 'x') {
  const a = AX[axis];
  const out = [];
  for (let i = 0; i < count; i++) {
    const p = add(c, mul(a, (i - (count - 1) / 2) * (len + 14)));
    out.push(isoCyl(O, p, a, r, len, S));
    out.push(isoCyl(O, add(p, mul(a, len)), a, r * 1.7, 4, S, { capInner: 0.4 }));
  }
  return { svg: g({}, out), top: add(c, [0, 0, r * 2]), bottom: add(c, [0, 0, -r * 2]) };
}

function antenna(c) {
  const base = box(add(c, [0, 0, -8]), [70, 40, 6]);
  const Q = (p) => P(add(c, p));
  const blade = path(poly([Q([-28, 0, -5]), Q([22, 0, -5]), Q([34, 0, 50]), Q([10, 0, 50])], true), 'bp-face-t');
  return { svg: g({ class: 'bp-iso' }, base.svg, blade), top: add(c, [20, 0, 50]), bottom: add(c, [0, 0, -11]) };
}

// ---------- scenes ----------
// positions along the horizontal iso row: t => [t, -t, z]
const row = (t, z = 0) => [t, -t, z];

const SCENES = {
  21: {
    name: 'AIR CONDITIONING', fig: 'PACK — EXPLODED',
    parts: [
      { role: 'pack-controller', desc: 'PACK CONTROLLER', make: (c) => box(c, [52, 70, 40], { plate: true, conns: 2, vents: 3 }) },
      { role: 'air-cycle-machine', desc: 'AIR CYCLE MACHINE', make: (c) => cyl(c, 30, 84, 'x', { rings: [0.25, 0.7], cap: 0.55, flange: 1.18 }) },
      { role: 'heat-exchanger', desc: 'PRIMARY HEAT EXCHANGER', make: (c) => box(c, [62, 92, 56], { fins: 9 }) },
      { role: 'pack-valve', desc: 'PACK FLOW CONTROL VALVE', make: (c) => valve(c, 17, 60, 'y') },
      { role: 'temp-sensor', desc: 'PACK OUTLET TEMP SENSOR', make: (c) => cyl(c, 11, 46, 'z', { rings: [0.3], cap: 0.45, flange: 1.3 }) },
    ],
  },
  24: {
    name: 'ELECTRICAL POWER', fig: 'AC GENERATION — EXPLODED',
    parts: [
      { role: 'generator', desc: 'AC GENERATOR (DRIVE-MOUNTED)', make: (c) => cyl(c, 36, 74, 'x', { rings: [0.3, 0.62], cap: 0.6, flange: 1.22 }) },
      { role: 'gcu', desc: 'GENERATOR CONTROL UNIT', make: (c) => box(c, [48, 72, 46], { plate: true, conns: 2 }) },
      { role: 'tru', desc: 'TRANSFORMER RECTIFIER UNIT', make: (c) => box(c, [60, 84, 50], { fins: 8 }) },
      { role: 'battery', desc: 'MAIN BATTERY', make: (c) => { const b = box(c, [56, 78, 40], { vents: 2 }); const t1 = cyl(add(c, [10, -18, 25]), 6, 10, 'z'); const t2 = cyl(add(c, [10, 18, 25]), 6, 10, 'z'); return { svg: g({}, b.svg, t1.svg, t2.svg), top: add(c, [0, 0, 30]), bottom: b.bottom }; } },
      { role: 'contactor', desc: 'BUS POWER CONTACTOR', make: (c) => { const b = box(c, [34, 40, 30], { conns: 1 }); const k = cyl(add(c, [0, 0, 22]), 10, 14, 'z', { cap: 0.5 }); return { svg: g({}, b.svg, k.svg), top: add(c, [0, 0, 29]), bottom: b.bottom }; } },
    ],
  },
  27: {
    name: 'FLIGHT CONTROLS', fig: 'AILERON ACTUATION — EXPLODED',
    parts: [
      { role: 'fcc-module', desc: 'FLIGHT CONTROL MODULE', make: (c) => box(c, [46, 78, 52], { plate: true, conns: 3, vents: 2 }) },
      { role: 'pcu-actuator', desc: 'AILERON POWER CONTROL UNIT', make: (c) => actuator(c, 18, 118) },
      { role: 'servo-valve', desc: 'ELECTRO-HYDRAULIC SERVO VALVE', make: (c) => { const b = box(c, [40, 46, 30], { conns: 1 }); const t = cyl(add(c, [0, 0, 24]), 9, 18, 'z', { cap: 0.5 }); return { svg: g({}, b.svg, t.svg), top: add(c, [0, 0, 33]), bottom: b.bottom }; } },
      { role: 'lvdt', desc: 'POSITION TRANSDUCER (LVDT)', make: (c) => cyl(c, 8, 70, 'x', { rings: [0.2, 0.8], cap: 0.4 }) },
      { role: 'rod-end', desc: 'ROD-END BEARING KIT', make: (c) => hardware(c, 2, 5, 22, 'x') },
    ],
  },
  29: {
    name: 'HYDRAULIC POWER', fig: 'SYSTEM A SUPPLY — EXPLODED',
    parts: [
      { role: 'edp', desc: 'ENGINE-DRIVEN PUMP', make: (c) => { const b = cyl(c, 28, 66, 'x', { rings: [0.35, 0.7], cap: 0.5, flange: 1.3 }); const p = cyl(add(c, [0, 0, 32]), 7, 14, 'z', { cap: 0.4 }); return { svg: g({}, b.svg, p.svg), top: add(c, [0, 0, 39]), bottom: b.bottom }; } },
      { role: 'accumulator', desc: 'PISTON ACCUMULATOR', make: (c) => cyl(c, 20, 96, 'z', { rings: [0.12, 0.88], cap: 0.35 }) },
      { role: 'reservoir', desc: 'BOOTSTRAP RESERVOIR', make: (c) => cyl(c, 30, 80, 'y', { rings: [0.2, 0.8], cap: 0.55 }) },
      { role: 'filter', desc: 'PRESSURE FILTER MODULE', make: (c) => { const h = box(add(c, [0, 0, 18]), [36, 36, 18], { conns: 1 }); const b = cyl(add(c, [0, 0, -10]), 13, 38, 'z', { rings: [0.5] }); return { svg: g({}, b.svg, h.svg), top: add(c, [0, 0, 27]), bottom: add(c, [0, 0, -29]) }; } },
      { role: 'pressure-transducer', desc: 'PRESSURE TRANSDUCER', make: (c) => cyl(c, 12, 48, 'z', { rings: [0.35], cap: 0.45, flange: 1.3 }) },
    ],
  },
  32: {
    name: 'LANDING GEAR', fig: 'MAIN WHEEL & BRAKE — EXPLODED',
    parts: [
      { role: 'retract-actuator', desc: 'RETRACTION ACTUATOR', make: (c) => actuator(c, 16, 110) },
      { role: 'wheel', desc: 'MAIN WHEEL ASSEMBLY', make: (c) => { const t = cyl(c, 66, 38, 'y', { cap: 0.62 }); const hub = cyl(add(c, [0, 22, 0]), 22, 8, 'y', { cap: 0.4 }); return { svg: g({}, t.svg, hub.svg), top: add(c, [0, 0, 66]), bottom: add(c, [0, 0, -66]) }; } },
      { role: 'brake', desc: 'CARBON BRAKE HEAT STACK', make: (c) => stack(c, 46, 6, 4, 9, 'y') },
      { role: 'brake-temp', desc: 'BRAKE TEMPERATURE SENSOR', make: (c) => cyl(c, 9, 52, 'x', { rings: [0.3], cap: 0.45, flange: 1.4 }) },
      { role: 'prox-sensor', desc: 'GEAR PROXIMITY SENSOR', make: (c) => { const b = box(c, [44, 32, 26], { conns: 1 }); const h = cyl(add(c, [0, 0, -22]), 10, 20, 'z'); return { svg: g({}, h.svg, b.svg), top: add(c, [0, 0, 13]), bottom: add(c, [0, 0, -32]) }; } },
    ],
  },
  34: {
    name: 'NAVIGATION', fig: 'AVIONICS RACK — EXPLODED',
    parts: [
      { role: 'gps-antenna', desc: 'GNSS ANTENNA', make: (c) => { const b = cyl(c, 28, 8, 'z', { cap: 0.6 }); const d = cyl(add(c, [0, 0, 8]), 16, 6, 'z', { cap: 0.4 }); return { svg: g({}, b.svg, d.svg), top: add(c, [0, 0, 14]), bottom: add(c, [0, 0, -4]) }; } },
      { role: 'adiru', desc: 'AIR DATA / INERTIAL REF UNIT', make: (c) => box(c, [48, 96, 58], { plate: true, conns: 3, vents: 3 }) },
      { role: 'mmr', desc: 'MULTI-MODE RECEIVER', make: (c) => box(c, [44, 80, 40], { plate: true, conns: 2 }) },
      { role: 'wx-radar', desc: 'WEATHER RADAR TRANSCEIVER', make: (c) => box(c, [54, 70, 46], { fins: 6, conns: 1 }) },
      { role: 'vhf-antenna', desc: 'VHF BLADE ANTENNA', make: (c) => antenna(c) },
    ],
  },
  36: {
    name: 'PNEUMATIC', fig: 'ENGINE BLEED — EXPLODED',
    parts: [
      { role: 'hp-valve', desc: 'HIGH-PRESSURE BLEED VALVE', make: (c) => valve(c, 18, 58, 'x') },
      { role: 'precooler', desc: 'BLEED PRECOOLER', make: (c) => box(c, [64, 88, 58], { fins: 10 }) },
      { role: 'prsov', desc: 'PRESSURE REG. SHUTOFF VALVE', make: (c) => valve(c, 20, 62, 'y') },
      { role: 'duct', desc: 'BLEED DUCT SECTION', make: (c) => cyl(c, 15, 96, 'x', { rings: [0.2, 0.8], flange: 1.35, cap: 0.75 }) },
      { role: 'check-valve', desc: 'BLEED CHECK VALVE', make: (c) => cyl(c, 14, 26, 'x', { flange: 1.4, cap: 0.6 }) },
    ],
  },
  49: {
    name: 'AIRBORNE APU', fig: 'APU ACCESSORIES — EXPLODED',
    parts: [
      { role: 'ecb', desc: 'APU ELECTRONIC CONTROL BOX', make: (c) => box(c, [48, 80, 50], { plate: true, conns: 3 }) },
      { role: 'starter-generator', desc: 'APU STARTER-GENERATOR', make: (c) => cyl(c, 32, 80, 'x', { rings: [0.3, 0.65], cap: 0.55, flange: 1.2 }) },
      { role: 'fcu', desc: 'APU FUEL CONTROL UNIT', make: (c) => { const b = box(c, [46, 56, 40], { conns: 2 }); const m = cyl(add(c, [0, 0, 27]), 11, 14, 'z', { cap: 0.4 }); return { svg: g({}, b.svg, m.svg), top: add(c, [0, 0, 34]), bottom: b.bottom }; } },
      { role: 'inlet-actuator', desc: 'INLET DOOR ACTUATOR', make: (c) => actuator(c, 13, 92) },
      { role: 'igniter', desc: 'IGNITER PLUG KIT', make: (c) => hardware(c, 2, 5, 26, 'x') },
    ],
  },
};

function scene(ata) {
  const sc = SCENES[ata];
  const nParts = sc.parts.length;
  const spacing = 92; // iso units along the row
  const zs = [26, -26, 26, -26, 26];
  const built = sc.parts.map((p, i) => {
    const t = (i - (nParts - 1) / 2) * spacing;
    const c = row(t, zs[i]);
    return { ...p, i, c, b: p.make(c) };
  });
  // draw far (left/up) to near: order by x+y+z ascending — row t keeps x+y=0, so sort by z
  const order = built.slice().sort((a, b) => a.c[2] - b.c[2]);

  const axisY = O[1];
  const parts = [];
  parts.push(el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#bp-grid)', class: 'bp-gridfill' }));
  // assembly axis + drop lines
  parts.push(path(`M${60},${n(axisY)}H${W - 60}`, 'bp-phantom'));
  built.forEach((p) => {
    const [x, y] = P(p.c);
    parts.push(path(`M${n(x)},${n(y)}V${n(axisY)}`, 'bp-hidden'));
  });
  order.forEach((p) => parts.push(g({ class: 'bp-part bp-iso', 'data-slot': p.i + 1, 'data-role': p.role }, p.b.svg)));

  // labels: even index above, odd below
  built.forEach((p) => {
    const above = p.i % 2 === 0;
    const a = P(above ? p.b.top : p.b.bottom);
    const lx = a[0];
    const ly = above ? 112 : H - 104;
    const by = above ? ly + 28 : ly - 24;
    const leader = above ? `M${n(a[0])},${n(a[1] - 6)}V${n(by + 14)}` : `M${n(a[0])},${n(a[1] + 6)}V${n(by - 14)}`;
    parts.push(
      g(
        { class: 'bp-callout' },
        path(leader, 'bp-halo'),
        path(leader, 'bp-leader'),
        el('circle', { cx: a[0], cy: above ? a[1] - 6 : a[1] + 6, r: 2.6, class: 'bp-anchor' }),
        el('circle', { cx: lx, cy: by, r: 14, class: 'bp-bubble' }),
        text(lx, by + 0.5, String(p.i + 1), 'bp-bubble-t')
      )
    );
    const ty = above ? ly - 18 : ly + 24;
    parts.push(
      g(
        { class: 'bp-label', 'data-slot': p.i + 1, 'data-role': p.role, transform: `translate(${n(lx)} ${n(ty)})` },
        text(0, 0, `GN-${ata}-·····`, 'bp-pn', { 'text-anchor': 'middle', 'data-field': 'pn' }),
        text(0, 19, p.desc, 'bp-desc', { 'text-anchor': 'middle', 'data-field': 'desc' })
      )
    );
  });

  const head = g(
    { class: 'bp-frameset' },
    text(40, 46, `ATA ${ata} · ${sc.name}`, 'bp-t-ice'),
    text(40, 64, `${sc.fig} · FICTIONAL COMPONENTS`, 'bp-t-xs'),
    text(W - 40, 46, `FIG. ${ata}-1`, 'bp-t-sm', { 'text-anchor': 'end' }),
    text(W - 40, 64, 'SCHEMATIC — NOT ENGINEERING DATA', 'bp-t-warn', { 'text-anchor': 'end' })
  );

  return svgDoc({
    w: W,
    h: H,
    title: `Exploded schematic, ATA ${ata} ${sc.name.toLowerCase()}`,
    desc: `Original exploded isometric schematic of fictional ATA ${ata} components with numbered label slots. Not an OEM illustration and not engineering data.`,
    extraStyle: isoStyle,
    attrs: { class: 'bp-sheet bp-exploded', 'data-ata': ata },
    body: parts.join('') + head,
  });
}

export const ATAS = Object.keys(SCENES);
export function files() {
  return Object.fromEntries(ATAS.map((a) => [`exploded-${a}.svg`, scene(a)]));
}
