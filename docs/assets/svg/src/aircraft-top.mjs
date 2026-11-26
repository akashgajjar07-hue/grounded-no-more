// Top view of a GENERIC twin-engine airliner (original geometry; not any OEM type).
// Geometry is defined in "metres" (x = lateral, + = right/starboard as seen from above; y = from nose
// tip aft) and scaled to px. The proportions are archetypal (swept wing ~33° LE, span ≈ length,
// underwing nacelles at ~1/3 semi-span, tailplane ≈ 1/3 span), not a reproduction of a real aircraft.
import { C, el, g, path, text, poly, n, svgDoc, dimension, titleBlock, sheetFrame } from './lib.mjs';

const W = 1440;
const H = 1000;
const K = 12.4; // px per metre
const CX = 720;
const Y0 = 112; // nose tip
// The nose section (y <= 8.2 m) is drawn as-is; everything aft is shifted by FWD so the wing sits at
// ~40% of overall length (a forward-fuselage plug, the way stretched variants are built).
const FWD = 2.4;
const X = (x) => CX + x * K;
const Y = (y) => Y0 + (y > 8.2 ? y + FWD : y) * K;
const P = ([x, y]) => [X(x), Y(y)];
const pt = (x, y) => `${n(X(x))},${n(Y(y))}`;

// ---------------- geometry (metres) ----------------
const FUS_R = 2.9;
// Fuselage right-half as cubic segments, nose → tail.
const fusRight = [
  ['M', [0, 0]],
  ['C', [1.18, 0], [2.32, 1.5], [2.66, 3.4]],
  ['C', [2.86, 4.6], [2.9, 6.2], [FUS_R, 8.2]],
  ['L', [FUS_R, 39.2]],
  ['C', [FUS_R, 45.2], [1.95, 50.6], [1.36, 54.2]],
  ['C', [1.02, 56.4], [0.72, 58.3], [0.5, 59.55]],
  ['L', [0.34, 60.1]],
];
// half-width of the fuselage at station y (numeric, sampled from the curve for detail placement)
function fusHalf(y) {
  if (y <= 0) return 0;
  if (y < 8.2) {
    // elliptical approximation of the nose
    const t = y / 8.2;
    return FUS_R * Math.sqrt(1 - (1 - t) ** 2.3);
  }
  if (y <= 39.2) return FUS_R;
  const t = (y - 39.2) / (60.1 - 39.2);
  return FUS_R - (FUS_R - 0.34) * (1 - (1 - t) ** 1.45);
}

function fuselagePath() {
  // right side then mirrored left side back to the nose
  let d = `M${pt(0, 0)}`;
  const segsR = [];
  let cur = [0, 0];
  for (const s of fusRight.slice(1)) {
    if (s[0] === 'C') { segsR.push({ t: 'C', p0: cur, c1: s[1], c2: s[2], p1: s[3] }); cur = s[3]; }
    else { segsR.push({ t: 'L', p0: cur, p1: s[1] }); cur = s[1]; }
  }
  for (const s of segsR) d += s.t === 'C' ? `C${pt(...s.c1)} ${pt(...s.c2)} ${pt(...s.p1)}` : `L${pt(...s.p1)}`;
  d += `L${pt(-0.34, 60.1)}`;
  const m = ([x, y]) => [-x, y];
  for (const s of segsR.slice(0, -1).reverse()) {
    d += s.t === 'C' ? `C${pt(...m(s.c2))} ${pt(...m(s.c1))} ${pt(...m(s.p0))}` : `L${pt(...m(s.p0))}`;
  }
  return d + 'Z';
}

// Wing (right). Leading edge is a straight swept line; trailing edge kinks at the "yehudi".
const LE0 = [1.6, 20.0];
const SWEEP = 0.6535; // tan(33.2°)
const leY = (x) => LE0[1] + (x - LE0[0]) * SWEEP;
const KINK = [10.6, 33.55];
const TIP_TE = [29.25, 40.05];
const ROOT_TE = [1.6, 33.15];
const teY = (x) => (x <= KINK[0] ? ROOT_TE[1] + ((x - ROOT_TE[0]) * (KINK[1] - ROOT_TE[1])) / (KINK[0] - ROOT_TE[0]) : KINK[1] + ((x - KINK[0]) * (TIP_TE[1] - KINK[1])) / (TIP_TE[0] - KINK[0]));
const chordAt = (x, f) => leY(x) + f * (teY(x) - leY(x));
const WING_LE_END = 27.2;
const TIP = [29.55, 39.35];

function wingPath(s) {
  const m = ([x, y]) => [s * x, y];
  const d = [
    `M${pt(...m(LE0))}`,
    `L${pt(...m([WING_LE_END, leY(WING_LE_END)]))}`,
    `C${pt(...m([28.35, leY(WING_LE_END) + 0.62]))} ${pt(...m([29.35, 38.2]))} ${pt(...m(TIP))}`,
    `L${pt(...m(TIP_TE))}`,
    `L${pt(...m(KINK))}`,
    `L${pt(...m(ROOT_TE))}`,
    'Z',
  ];
  return d.join('');
}

// Horizontal stabiliser (right)
const HS_LE0 = [0.9, 49.6];
const HS_SWEEP = 0.69;
const hsLe = (x) => HS_LE0[1] + (x - HS_LE0[0]) * HS_SWEEP;
const HS_TIP_X = 9.7;
const hsTe = (x) => 56.0 + (x - 0.9) * 0.2;
const hsChord = (x, f) => hsLe(x) + f * (hsTe(x) - hsLe(x));
function hsPath(s) {
  const m = ([x, y]) => [s * x, y];
  const le = HS_TIP_X - 0.5;
  return [
    `M${pt(...m(HS_LE0))}`,
    `L${pt(...m([le, hsLe(le)]))}`,
    `C${pt(...m([le + 0.35, hsLe(le) + 0.3]))} ${pt(...m([HS_TIP_X, hsTe(HS_TIP_X) - 0.9]))} ${pt(...m([HS_TIP_X, hsTe(HS_TIP_X) - 0.25]))}`,
    `L${pt(...m([HS_TIP_X - 0.05, hsTe(HS_TIP_X)]))}`,
    `L${pt(...m([0.9, hsTe(0.9)]))}`,
    'Z',
  ].join('');
}

// Engine nacelle (right), centred at NX
const NX = 10.15;
const NY = 19.9; // inlet station
const NPROF = [[1.42, 0], [1.64, 0.32], [1.77, 1.0], [1.82, 2.1], [1.8, 3.5], [1.7, 4.9], [1.5, 6.1], [1.24, 6.85]];
const NAFT = NY + 6.85;
function nacellePts(s) {
  const r = NPROF.map(([dx, dy]) => [dx, NY + dy]);
  const right = r.map(([dx, y]) => [s * (NX + dx), y]);
  const left = r.slice().reverse().map(([dx, y]) => [s * (NX - dx), y]);
  return right.concat(left);
}
function nacellePath(s) {
  const pts = nacellePts(s);
  // round the inlet lip with a small arc between the first left/right points
  const a = pts[pts.length - 1];
  const b = pts[0];
  return `M${pt(...b)}` + pts.slice(1).map((p) => `L${pt(...p)}`).join('') + `Q${pt((a[0] + b[0]) / 2, NY - 0.32)} ${pt(...b)}Z`;
}
// Core nozzle + plug (aft of fan cowl, hidden under the wing in top view)
function corePath(s) {
  const r = [[1.12, NAFT], [0.92, NAFT + 1.3], [0.7, NAFT + 2.3], [0.42, NAFT + 3.1], [0.0, NAFT + 3.9]];
  const right = r.map(([dx, y]) => [s * (NX + dx), y]);
  const left = r.slice(0, -1).reverse().map(([dx, y]) => [s * (NX - dx), y]);
  return poly(right.concat(left).map(P));
}

// Fin seen from above: a slim lens on the centreline
function finPath() {
  return `M${pt(0, 45.6)}C${pt(0.42, 47.2)} ${pt(0.48, 50.5)} ${pt(0.4, 54.5)}L${pt(0.16, 59.3)}L${pt(-0.16, 59.3)}L${pt(-0.4, 54.5)}C${pt(-0.48, 50.5)} ${pt(-0.42, 47.2)} ${pt(0, 45.6)}Z`;
}

// ---------------- drawing ----------------
const both = (fn) => [fn(-1), fn(1)];
const rectM = (x0, y0, x1, y1) => poly([[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(P), true);

function flapTrackFairings() {
  const xs = [6.4, 13.4, 17.7, 22.1];
  return both((s) =>
    xs.map((x) => {
      const te = teY(x);
      return path(
        `M${pt(s * x, te - 2.2)}C${pt(s * (x + 0.36), te - 1.2)} ${pt(s * (x + 0.34), te + 1.1)} ${pt(s * x, te + 1.9)}C${pt(s * (x - 0.34), te + 1.1)} ${pt(s * (x - 0.36), te - 1.2)} ${pt(s * x, te - 2.2)}Z`,
        'bp-skin-2'
      );
    })
  );
}

function wingDetails(s) {
  const out = [];
  const seg = (x0, x1, f) => path(poly([[s * x0, chordAt(x0, f)], [s * x1, chordAt(x1, f)]].map(P)), 'bp-panel');
  // slats (outboard) and Krueger-style inboard LE devices
  out.push(seg(11.9, 27.0, 0.11));
  for (let x = 11.9; x <= 27.01; x += 3.02) out.push(path(poly([[s * x, leY(x)], [s * x, chordAt(x, 0.11)]].map(P)), 'bp-panel'));
  out.push(seg(3.4, 8.6, 0.09));
  out.push(path(poly([[s * 3.4, leY(3.4)], [s * 3.4, chordAt(3.4, 0.09)]].map(P)), 'bp-panel'));
  out.push(path(poly([[s * 8.6, leY(8.6)], [s * 8.6, chordAt(8.6, 0.09)]].map(P)), 'bp-panel'));
  // flaps: inboard + outboard, hinge line at ~76% chord
  [[3.1, 10.3], [10.9, 20.3]].forEach(([a, b]) => {
    out.push(path(poly([[s * a, teY(a)], [s * a, chordAt(a, 0.76)], [s * b, chordAt(b, 0.76)], [s * b, teY(b)]].map(P)), 'bp-line'));
  });
  // spars (phantom: internal structure)
  out.push(path(poly([[s * 2.9, chordAt(2.9, 0.16)], [s * 27, chordAt(27, 0.16)]].map(P)), 'bp-phantom'));
  out.push(path(poly([[s * 2.9, chordAt(2.9, 0.66)], [s * 10.6, chordAt(10.6, 0.66)], [s * 27, chordAt(27, 0.66)]].map(P)), 'bp-phantom'));
  // nav light
  out.push(el('circle', { cx: X(s * 29.15), cy: Y(39.05), r: 2.2, class: 'bp-line' }));
  // wing root / fairing panel line
  out.push(path(poly([[s * 3.3, 19.4], [s * 3.3, 34.2]].map(P)), 'bp-panel'));
  return out;
}

function fuselageDetails() {
  const out = [];
  // production joints (panel lines)
  [8.6, 17.2, 36.6, 45.2].forEach((y) => {
    const h = fusHalf(y);
    out.push(path(`M${pt(-h, y)}Q${pt(0, y + 0.35)} ${pt(h, y)}`, 'bp-panel'));
  });
  // windscreen frames
  out.push(path(`M${pt(-2.02, 3.0)}Q${pt(0, 1.85)} ${pt(2.02, 3.0)}`, 'bp-line'));
  out.push(path(`M${pt(-2.52, 4.25)}Q${pt(0, 3.15)} ${pt(2.52, 4.25)}`, 'bp-line'));
  out.push(path(poly([[0, 2.42], [0, 3.6]].map(P)), 'bp-panel'));
  [-1.2, 1.2].forEach((x) => out.push(path(poly([[x, 2.62 + Math.abs(x) * 0.1], [x * 1.12, 3.75 + Math.abs(x) * 0.08]].map(P)), 'bp-panel')));
  // belly fairing (hidden)
  both((s) => out.push(path(`M${pt(s * FUS_R, 15.2)}C${pt(s * 3.55, 17.2)} ${pt(s * 3.75, 19.6)} ${pt(s * 3.75, 22)}L${pt(s * 3.75, 33.2)}C${pt(s * 3.75, 35.6)} ${pt(s * 3.4, 37.4)} ${pt(s * FUS_R, 38.6)}`, 'bp-hidden')));
  // centre wing box between spars (hidden)
  out.push(path(rectM(-FUS_R, chordAt(2.9, 0.16), FUS_R, chordAt(2.9, 0.66)), 'bp-phantom'));
  // crown antennas (VHF blade, SATCOM radome)
  out.push(path(`M${pt(0, 13.2)}C${pt(0.22, 13.6)} ${pt(0.22, 14.5)} ${pt(0, 14.9)}C${pt(-0.22, 14.5)} ${pt(-0.22, 13.6)} ${pt(0, 13.2)}Z`, 'bp-line'));
  out.push(el('ellipse', { cx: X(0), cy: Y(42.6), rx: 0.5 * K, ry: 1.05 * K, class: 'bp-line' }));
  out.push(path(`M${pt(0, 26.4)}C${pt(0.2, 26.8)} ${pt(0.2, 27.7)} ${pt(0, 28.1)}C${pt(-0.2, 27.7)} ${pt(-0.2, 26.8)} ${pt(0, 26.4)}Z`, 'bp-line'));
  // tailcone section joint
  out.push(path(`M${pt(-fusHalf(55.4), 55.4)}Q${pt(0, 55.7)} ${pt(fusHalf(55.4), 55.4)}`, 'bp-panel'));
  return out;
}

// ---------- ATA hotspots ----------
// Each: shapes (in px path strings), anchor (leader start, metres), bubble (px), badge (metres).
function hotspots() {
  const hs = [];
  const shp = (d, cls = 'hs-shape') => path(d, cls);
  const hid = (d) => path(d, 'hs-shape hs-hidden');

  // 34 Navigation — radome + avionics/GPS antennas
  hs.push({
    ata: '34', name: 'NAVIGATION', sub: 'RADOME · AVIONICS', side: 'L', anchor: [0, 1.0], bubble: [250, 150], badge: [0, 4.6],
    shapes: [
      shp(`M${pt(0, 0)}C${pt(0.62, 0)} ${pt(1.2, 0.42)} ${pt(1.62, 1.35)}Q${pt(0, 1.75)} ${pt(-1.62, 1.35)}C${pt(-1.2, 0.42)} ${pt(-0.62, 0)} ${pt(0, 0)}Z`),
      el('circle', { cx: X(-0.55), cy: Y(10.7), r: 3.2, class: 'hs-shape' }),
      el('circle', { cx: X(0.55), cy: Y(10.7), r: 3.2, class: 'hs-shape' }),
    ],
  });
  // 24 Electrical — E/E bay (hidden, forward lower lobe)
  hs.push({
    ata: '24', name: 'ELECTRICAL POWER', sub: 'E/E BAY · FWD', side: 'R', anchor: [1.25, 11.7], bubble: [1190, 250], badge: [0, 11.9],
    shapes: [hid(rectM(-1.25, 10.2, 1.25, 13.4)), shp(rectM(-0.8, 10.6, -0.1, 12.0), 'hs-line'), shp(rectM(0.1, 10.6, 0.8, 12.0), 'hs-line')],
  });
  // 21 Air conditioning — two packs in the belly fairing forward of the wing box
  hs.push({
    ata: '21', name: 'AIR CONDITIONING', sub: 'PACKS · BELLY FAIRING', side: 'L', anchor: [-1.65, 19.4], bubble: [250, 345], badge: [0, 19.6],
    shapes: [hid(rectM(-2.65, 17.7, -0.55, 21.3)), hid(rectM(0.55, 17.7, 2.65, 21.3)), shp(`M${pt(-1.6, 21.3)}V${n(Y(22.3))}H${n(X(1.6))}V${n(Y(21.3))}`, 'hs-line')],
  });
  // 36 Pneumatic — bleed ducts from engine pylons along the wing LE to the packs
  const duct = (s) => `M${pt(s * NX, NY + 4.4)}L${pt(s * NX, chordAt(NX, 0.1))}L${pt(s * 3.1, chordAt(3.1, 0.1))}L${pt(s * 1.9, 21.0)}`;
  const aice = (s) => `M${pt(s * NX, chordAt(NX, 0.1))}L${pt(s * 26.4, chordAt(26.4, 0.1))}`;
  hs.push({
    ata: '36', name: 'PNEUMATIC', sub: 'BLEED DUCTS · WING', side: 'L', anchor: [-15.2, chordAt(15.2, 0.1)], bubble: [250, 490], badge: [-15.5, chordAt(15.5, 0.1)],
    shapes: [shp(duct(-1), 'hs-line'), shp(duct(1), 'hs-line'), shp(aice(-1), 'hs-line'), shp(aice(1), 'hs-line')],
  });
  // 32 Landing gear — NLG bay, MLG wells, MLG legs retracted into wing root (hidden)
  const mlg = (s) => [
    hid(rectM(s * 0.55, 33.5, s * 3.0, 37.4)),
    shp(`M${pt(s * 6.2, 32.0)}L${pt(s * 2.2, 34.2)}`, 'hs-line'),
    el('circle', { cx: X(s * 6.2), cy: Y(32.0), r: 2.6, class: 'hs-shape' }),
  ];
  hs.push({
    ata: '32', name: 'LANDING GEAR', sub: 'NLG + MLG BAYS', side: 'L', anchor: [-2.4, 37.4], bubble: [250, 730], badge: [-1.8, 35.4],
    shapes: [hid(rectM(-0.62, 4.9, 0.62, 8.1)), ...mlg(-1), ...mlg(1)],
  });
  // 29 Hydraulics — EDP feed lines along the rear spar + reservoirs aft of the MLG wells
  const hyd = (s) => `M${pt(s * NX, NAFT + 0.4)}L${pt(s * NX, chordAt(NX, 0.66) - 0.3)}L${pt(s * 3.2, chordAt(3.2, 0.66) - 0.3)}L${pt(s * 1.3, 37.9)}`;
  hs.push({
    ata: '29', name: 'HYDRAULIC POWER', sub: 'RESERVOIRS · LINES', side: 'R', anchor: [1.0, 38.45], bubble: [1190, 700], badge: [14.6, chordAt(14.6, 0.66) - 0.3],
    shapes: [shp(hyd(-1), 'hs-line'), shp(hyd(1), 'hs-line'), hid(rectM(-1.6, 37.9, -0.3, 39.0)), hid(rectM(0.3, 37.9, 1.6, 39.0))],
  });
  // 27 Flight controls — ailerons, spoilers, elevators, rudder
  const ail = (s) => shp(poly([[s * 20.7, chordAt(20.7, 0.76)], [s * 26.7, chordAt(26.7, 0.76)], [s * 26.7, teY(26.7)], [s * 20.7, teY(20.7)]].map(P), true));
  const spoilers = (s) =>
    [[4.0, 6.7], [6.9, 9.6], [11.3, 13.4], [13.6, 15.7], [15.9, 18.0], [18.2, 20.2]].map(([a, b]) =>
      shp(poly([[s * a, chordAt(a, 0.6)], [s * b, chordAt(b, 0.6)], [s * b, chordAt(b, 0.74)], [s * a, chordAt(a, 0.74)]].map(P), true))
    );
  const elev = (s) => shp(poly([[s * 1.5, hsChord(1.5, 0.7)], [s * 9.2, hsChord(9.2, 0.7)], [s * 9.2, hsTe(9.2)], [s * 1.5, hsTe(1.5)]].map(P), true));
  hs.push({
    ata: '27', name: 'FLIGHT CONTROLS', sub: 'AIL · SPLR · ELEV · RUD', side: 'R', anchor: [24.2, chordAt(24.2, 0.9)], bubble: [1190, 600], badge: [23.7, chordAt(23.7, 0.88)],
    shapes: [ail(-1), ail(1), ...spoilers(-1), ...spoilers(1), elev(-1), elev(1), shp(`M${pt(-0.3, 55.6)}L${pt(0.3, 55.6)}L${pt(0.16, 59.3)}L${pt(-0.16, 59.3)}Z`)],
  });
  // 49 APU — tailcone compartment + exhaust
  hs.push({
    ata: '49', name: 'AIRBORNE APU', sub: 'TAILCONE', side: 'L', anchor: [-0.25, 59.2], bubble: [250, 900], badge: [0, 57.4],
    shapes: [hid(rectM(-0.72, 55.9, 0.72, 58.9)), shp(rectM(0.5, 54.6, 1.05, 55.5)), el('circle', { cx: X(0), cy: Y(59.75), r: 3.4, class: 'hs-shape' })],
  });
  return hs;
}

function callout(h) {
  const [ax, ay] = P(h.anchor);
  const [bx, by] = h.bubble;
  const dir = h.side === 'L' ? -1 : 1;
  const dy = by - ay;
  // 45° elbow, then horizontal to the bubble
  const ex = ax + dir * Math.abs(dy);
  const elbow = dir < 0 ? Math.max(ex, bx + 40) : Math.min(ex, bx - 40);
  const d = `M${n(ax)},${n(ay)}L${n(elbow)},${n(by)}L${n(bx - dir * 17)},${n(by)}`;
  const tx = bx + dir * 28;
  const anchor = dir < 0 ? 'end' : 'start';
  return g(
    { class: 'bp-callout' },
    path(d, 'bp-halo'),
    path(d, 'bp-leader'),
    el('circle', { cx: ax, cy: ay, r: 3.2, class: 'bp-anchor' }),
    el('circle', { cx: bx, cy: by, r: 17, class: 'bp-bubble' }),
    text(bx, by + 0.5, h.ata, 'bp-bubble-t'),
    text(tx, by - 3, h.name, 'bp-t-ice', { 'text-anchor': anchor }),
    text(tx, by + 13, h.sub, 'bp-t-xs', { 'text-anchor': anchor })
  );
}

export function build() {
  const hs = hotspots();
  const tailY = 60.1;
  const body = [];

  body.push(el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#bp-grid)', class: 'bp-gridfill' }));
  body.push(sheetFrame(W, H, { zonesX: 8, zonesY: 5 }));

  // centreline + nacelle centrelines
  const air = [];
  air.push(path(`M${pt(0, -4)}L${pt(0, tailY + 4.5)}`, 'bp-center'));

  // horizontal stabiliser (under fuselage)
  air.push(...both((s) => path(hsPath(s), 'bp-skin')));
  air.push(...both((s) => path(poly([[s * 1.5, hsChord(1.5, 0.7)], [s * 9.2, hsChord(9.2, 0.7)]].map(P)), 'bp-line')));
  air.push(...both((s) => path(poly([[s * 1.3, hsChord(1.3, 0.22)], [s * 9.2, hsChord(9.2, 0.22)]].map(P)), 'bp-phantom')));

  // nacelles (drawn first; the wing hides the aft part — that part is redrawn as hidden lines)
  air.push(...both((s) => path(nacellePath(s), 'bp-skin')));
  air.push(...both((s) => path(`M${pt(s * NX - 1.66, NY + 0.42)}Q${pt(s * NX, NY + 0.05)} ${pt(s * NX + 1.66, NY + 0.42)}`, 'bp-line')));
  air.push(...both((s) => path(`M${pt(s * NX - 1.81, NY + 2.4)}Q${pt(s * NX, NY + 2.75)} ${pt(s * NX + 1.81, NY + 2.4)}`, 'bp-panel')));
  air.push(...both((s) => path(`M${pt(s * NX - 1.76, NY + 4.3)}Q${pt(s * NX, NY + 4.65)} ${pt(s * NX + 1.76, NY + 4.3)}`, 'bp-panel')));
  // pylon strip seen over the nacelle
  air.push(...both((s) => path(rectM(s * NX - 0.3, NY + 1.6, s * NX + 0.3, leY(NX) + 0.3), 'bp-line')));

  // flap track fairings + wings
  air.push(...flapTrackFairings());
  air.push(...both((s) => path(wingPath(s), 'bp-skin')));
  air.push(...both((s) => g({}, wingDetails(s))));
  // hidden part of nacelle + core under the wing
  air.push(...both((s) => path(corePath(s), 'bp-hidden')));
  air.push(...both((s) => path(poly([[s * (NX + 1.66), leY(NX + 1.66)], [s * (NX + 1.7), NY + 4.9], [s * (NX + 1.5), NY + 6.1], [s * (NX + 1.24), NAFT], [s * (NX - 1.24), NAFT], [s * (NX - 1.5), NY + 6.1], [s * (NX - 1.7), NY + 4.9], [s * (NX - 1.66), leY(NX - 1.66)]].map(P)), 'bp-hidden')));
  air.push(...both((s) => path(`M${pt(s * NX, NY - 1.6)}L${pt(s * NX, NAFT + 5)}`, 'bp-center')));
  // engine label tags
  air.push(...both((s) => text(X(s * NX), Y(NY - 1.0), s < 0 ? 'ENG 1' : 'ENG 2', 'bp-t-xs', { 'text-anchor': 'middle' })));

  // fuselage on top
  air.push(path(fuselagePath(), 'bp-skin'));
  air.push(...fuselageDetails());
  // fin + rudder hinge
  air.push(path(finPath(), 'bp-skin-2'));
  air.push(path(`M${pt(-0.42, 55.6)}L${pt(0.42, 55.6)}`, 'bp-line'));
  // re-draw centreline over fuselage, faint
  air.push(path(`M${pt(0, 4.2)}L${pt(0, 45.4)}`, 'bp-center'));

  // hidden equipment outlines belonging to hotspots (dashed so they read as internal)
  const hsGroups = hs.map((h) =>
    g(
      { id: `ata-${h.ata}`, class: 'ata-hotspot', 'data-ata': h.ata, 'data-name': h.name, tabindex: 0, role: 'button', 'aria-label': `ATA ${h.ata} ${h.name.toLowerCase()}` },
      g({ class: 'hs-shapes' }, h.shapes),
      callout(h),
      g({ class: 'hs-badge' }, el('circle', { cx: X(h.badge[0]), cy: Y(h.badge[1]), r: 19 }), text(X(h.badge[0]), Y(h.badge[1]) + 1, h.ata, ''))
    )
  );

  // orientation marks
  const orient = g(
    { class: 'bp-orient' },
    path(`M${n(X(0))},${n(Y(-5.2))}V${n(Y(-1.4))}`, 'bp-dim', { 'marker-start': 'url(#bp-arr)' }),
    text(X(0) + 10, Y(-3.8), 'FWD', 'bp-t-xs'),
    text(X(-21), Y(32.6), 'LH', 'bp-t-xs', { 'text-anchor': 'middle' }),
    text(X(21), Y(32.6), 'RH', 'bp-t-xs', { 'text-anchor': 'middle' })
  );

  // dimensions
  const spanY = 948;
  const tipL = X(-TIP[0]);
  const tipR = X(TIP[0]);
  const lenX = 300;
  const dims = g(
    { class: 'bp-dims' },
    dimension({ x1: tipL, y1: spanY, x2: tipR, y2: spanY, label: 'SPAN', ext: [[[tipL, Y(TIP[1]) + 8], [tipL, spanY + 8]], [[tipR, Y(TIP[1]) + 8], [tipR, spanY + 8]]] }),
    dimension({ x1: lenX, y1: Y(0), x2: lenX, y2: Y(tailY), label: 'LENGTH', vertical: true, at: 0.4, ext: [[[X(0) - 8, Y(0)], [lenX - 8, Y(0)]], [[X(-0.6) - 6, Y(tailY)], [lenX - 8, Y(tailY)]]] })
  );

  body.push(dims);
  body.push(g({ class: 'bp-airframe' }, air));
  body.push(orient);
  body.push(g({ class: 'bp-hotspots' }, hsGroups));
  body.push(g({ class: 'bp-frameset' }, text(52, 62, 'GENERIC TWIN-ENGINE AIRLINER — PLAN VIEW', 'bp-t-ice'), text(52, 80, 'FALCON HUB AIRWAYS (FICTIONAL) · ATA ZONE KEY', 'bp-t-xs')));
  body.push(titleBlock({ x: W - 32 - 300, y: H - 32 - 116, w: 300, title: 'TWIN-ENGINE AIRLINER · PLAN VIEW', sheet: '01' }));

  return svgDoc({
    w: W,
    h: H,
    title: 'Blueprint plan view of a generic twin-engine airliner with ATA zone hotspots',
    desc: 'Original schematic of a generic, fictional twin-engine airliner seen from above, with numbered callouts to ATA chapters 21, 24, 27, 29, 32, 34, 36 and 49. Not an OEM drawing and not engineering data.',
    attrs: { 'data-compact-viewbox': `${n(X(-31))} ${n(Y(-3))} ${n(62 * K)} ${n(66 * K)}`, class: 'bp-sheet' },
    body: body.join(''),
  });
}
