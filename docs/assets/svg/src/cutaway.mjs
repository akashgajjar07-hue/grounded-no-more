// GROUNDED NO MORE · original technical cutaway of a GENERIC, FICTIONAL twin-engine narrowbody (v3).
//
// Nothing here is traced or copied. A parametric 3-D model is built in metres and projected with one orthographic
// three-quarter (axonometric) view, so every line is consistent. The model has:
//   - fuselage cross-sections along the length, with a structure-rich cut-away;
//   - a swept wing with dihedral and real thickness;
//   - tailplane and fin with closed tips;
//   - two underwing nacelles (one sectioned to show the engine core);
//   - nose and main gear with legs, braces and bays;
//   - schematic system runs (bleed, hydraulics, fuel, electrical) and the catalogue parts.
//
//   node docs/assets/svg/src/cutaway.mjs  → docs/assets/svg/cutaway.svg (poster) + cutaway-simple.svg (phones)
//
// The callouts map to narrowbody-applicable part numbers in docs/data/parts.json. Output is deterministic.
// Callout leaders are elbow leaders assigned by a minimum-length matching. The build FAILS if two leaders cross,
// a leader runs through a label, or a leader is longer than LEADER_MAX.
//
// The displayed dimensions are deliberately generic (36.8 m length, 33.9 m span, 11.9 m height): the model is drawn
// in its own units and reported through MODEL_SCALE, so no figure matches a real aircraft type.

import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { C, FONT_MONO, FONT_DISPLAY, n, el } from './lib.mjs';

const FONT_UI = "'Inter', system-ui, sans-serif";
const deg = Math.PI / 180;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const T1C = '#C9D4DF';

// ---------------------------------------------------------------- vector maths
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
const lerp = (a, b, t) => a + (b - a) * t;
const lerp3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const range = (a, b, step) => { const out = []; if (step > 0) for (let v = a; v <= b + 1e-9; v += step) out.push(v); else for (let v = a; v >= b - 1e-9; v += step) out.push(v); return out; };
const smooth = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
const hash = (i) => { const s = Math.sin(i * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };

// ---------------------------------------------------------------- view (orthographic three-quarter)
// World: x aft from the nose tip, y to starboard, z up (model units). The viewer sits ahead, to port and above.
let ca, sa, ce, se, V;
function setView(azDeg, elDeg) {
  const az = azDeg * deg, e = elDeg * deg;
  ca = Math.cos(az); sa = Math.sin(az); ce = Math.cos(e); se = Math.sin(e);
  V = [-sa * ce, -ca * ce, se];
}
let S = 1, OX = 0, OY = 0, DMIN = 0, DMAX = 1;
const raw = ([x, y, z]) => { const x1 = x * ca - y * sa, y1 = x * sa + y * ca; return [x1, -(z * ce + y1 * se)]; };
const P = (p) => { const [u, v] = raw(p); return [OX + S * u, OY + S * v]; };
const dep = ([x, y, z]) => (x * sa + y * ca) * ce - z * se; // larger = further from the viewer
const facing = (nrm) => dot(nrm, V) > 0;

// ---------------------------------------------------------------- 2-D helpers
const d2 = (pts, close = false) => (pts.length < 2 ? '' : 'M' + pts.map(([x, y]) => `${n(x)} ${n(y)}`).join('L') + (close ? 'Z' : ''));
const dP = (pts3, close = false) => d2(pts3.map(P), close);
function smoothD(pts) { // Catmull-Rom → cubic Bézier through 2-D points
  if (pts.length < 3) return d2(pts);
  let d = `M${n(pts[0][0])} ${n(pts[0][1])}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6], c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${n(c1[0])} ${n(c1[1])} ${n(c2[0])} ${n(c2[1])} ${n(p2[0])} ${n(p2[1])}`;
  }
  return d;
}
function hull(pts) {
  const p = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (p.length < 3) return p;
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], up = [];
  for (const q of p) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
  for (const q of p.slice().reverse()) { while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
  return lo.slice(0, -1).concat(up.slice(0, -1));
}
const bbox = (pts) => {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return { x0, y0, x1, y1 };
};
function segX(a, b, c, d) {
  const o = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) * o(a, b, d) < 0 && o(c, d, a) * o(c, d, b) < 0;
}

// ---------------------------------------------------------------- airframe parameters (generic, fictional)
const MODEL_SCALE = 36.8 / 37.6; // reported dimensions = model units × MODEL_SCALE (generic figures)
const FL = 37.6, XN = 6.4, XT = 24.6, RY = 1.98, RZ = 2.07;
function sec(x) {
  if (x < XN) {
    const t = Math.max(x, 0.001) / XN, f = Math.pow(1 - Math.pow(1 - t, 2.3), 0.5);
    return { ry: RY * f, rz: RZ * f * (1 - 0.06 * (1 - t)), zc: -0.5 * Math.pow(1 - t, 2) };
  }
  if (x <= XT) return { ry: RY, rz: RZ, zc: 0 };
  const t = Math.min((x - XT) / (FL - XT), 1);
  const top = RZ - 1.05 * Math.pow(t, 1.7), bot = -RZ + 2.72 * Math.pow(t, 1.12);
  return { ry: RY * (1 - 0.86 * Math.pow(t, 1.5)), rz: (top - bot) / 2, zc: (top + bot) / 2 };
}
const FS = (x, th) => { const s = sec(x); return [x, s.ry * Math.cos(th), s.zc + s.rz * Math.sin(th)]; };
const FSin = (x, th, d = 0.17) => { const s = sec(x); return [x, Math.max(s.ry - d, 0.05) * Math.cos(th), s.zc + Math.max(s.rz - d, 0.05) * Math.sin(th)]; };
function FN(x, th) {
  const h = 0.01, a = sub(FS(x, th + h), FS(x, th - h)), b = sub(FS(x + h, th), FS(Math.max(x - h, 0), th));
  return norm(cross(a, b));
}
const FLOOR_Z = -0.62;
const floorY = (x, z = FLOOR_Z) => { const s = sec(x); const k = (z - s.zc) / s.rz; return Math.abs(k) >= 1 ? 0 : s.ry * Math.sqrt(1 - k * k); };

const WG = { y0: 1.9, xle0: 12.7, sw: 27 * deg, yk: 6.3, yt: 16.9, c0: 6.3, ck: 4.15, ct: 1.55, z0: -1.25, dih: 5.5 * deg };
const wXle = (y) => WG.xle0 + (y - WG.y0) * Math.tan(WG.sw);
const wC = (y) => (y < WG.yk ? lerp(WG.c0, WG.ck, (y - WG.y0) / (WG.yk - WG.y0)) : lerp(WG.ck, WG.ct, (y - WG.yk) / (WG.yt - WG.yk)));
const wZ = (y) => WG.z0 + (y - WG.y0) * Math.tan(WG.dih);
const naca = (f) => 5 * (0.2969 * Math.sqrt(Math.max(f, 0)) - 0.126 * f - 0.3516 * f * f + 0.2843 * f ** 3 - 0.1036 * f ** 4);
const wT = (y) => wC(y) * lerp(0.11, 0.09, (y - WG.y0) / (WG.yt - WG.y0)); // thickness / chord 0.11 → 0.09
const wPt = (s, y, f, side = 1) => [wXle(y) + f * wC(y), s * y, wZ(y) + (side > 0 ? 1.1 : -0.9) * wT(y) * naca(f)];

let FIN_FILL = '';
const TP = { y0: 0.55, xle0: 32.0, sw: 31 * deg, yt: 6.25, c0: 3.5, ct: 1.3, z0: 0.95, dih: 6 * deg };
const tXle = (y) => TP.xle0 + (y - TP.y0) * Math.tan(TP.sw);
const tC = (y) => lerp(TP.c0, TP.ct, (y - TP.y0) / (TP.yt - TP.y0));
const tZ = (y) => TP.z0 + (y - TP.y0) * Math.tan(TP.dih);
const tPt = (s, y, f, side = 0) => [tXle(y) + f * tC(y), s * y, tZ(y) + side * 0.1 * tC(y) * naca(f)];

const FIN = { xr: 29.4, zr: 1.85, cr: 5.9, h: 6.15, sw: 36 * deg, ct: 1.8 };
const fC = (eta) => lerp(FIN.cr, FIN.ct, eta);
const fPt = (eta, f, side = 0) => { const z = FIN.zr + eta * FIN.h; const xl = FIN.xr + eta * FIN.h * Math.tan(FIN.sw); return [xl + f * fC(eta), side * 0.1 * fC(eta) * naca(f), z]; };

// engines sit forward and outboard of the main gear so the two read separately
const NAC = { y: 7.0, z: -2.55, prof: [[7.95, 0.9], [8.15, 1.02], [8.7, 1.08], [10, 1.07], [11.1, 1.0], [11.6, 0.9], [11.75, 0.66], [13, 0.58], [13.5, 0.44], [14.35, 0.1]] };
const nacR = (x) => { const p = NAC.prof; if (x <= p[0][0]) return p[0][1]; for (let i = 1; i < p.length; i++) if (x <= p[i][0]) return lerp(p[i - 1][1], p[i][1], (x - p[i - 1][0]) / (p[i][0] - p[i - 1][0])); return p[p.length - 1][1]; };
const nacPt = (s, x, r, a) => [x, s * NAC.y + r * Math.cos(a), NAC.z + r * Math.sin(a)];

const NG = { x: 5.25, zTop: -1.55, zAx: -3.78, r: 0.39, w: 0.22, dy: 0.27 };
// main gear inboard of the engine under the wing root: axle ≈ 0.55 root chord aft of the root leading edge, ≈ 2.6 m out
const MGy = 2.62;
const MG = { x: WG.xle0 + 0.6 * WG.c0, y: MGy, zTop: wPt(1, MGy, 0.62, -1)[2] - 0.05, zAx: -3.62, r: 0.585, w: 0.38, dy: 0.42 };
const GROUND = MG.zAx - MG.r;

// ---------------------------------------------------------------- line tiers + depth fading
// T1 silhouette · T2 cut edges · T3 primary structure · T4 secondary · T5 far side / hidden (dashed)
const STY = {
  T1: { stroke: T1C, 'stroke-opacity': 0.95, 'stroke-width': 2.0, cap: 'round' },
  T1b: { stroke: T1C, 'stroke-opacity': 0.7, 'stroke-width': 1.2, cap: 'round' },
  T2: { stroke: C.copper, 'stroke-opacity': 1, 'stroke-width': 1.6, cap: 'round' },
  T2b: { stroke: C.copper, 'stroke-opacity': 0.85, 'stroke-width': 0.9, cap: 'round' },
  T3: { stroke: C.titanium, 'stroke-opacity': 0.55, 'stroke-width': 0.9, cap: 'butt' },
  T4: { stroke: C.titanium, 'stroke-opacity': 0.22, 'stroke-width': 0.5, cap: 'butt' },
  SEAT: { stroke: C.titanium, 'stroke-opacity': 0.18, 'stroke-width': 0.5, cap: 'butt' },
  T5: { stroke: C.titanium, 'stroke-opacity': 0.12, 'stroke-width': 0.5, cap: 'butt', dash: '3 3' },
  FAR: { stroke: T1C, 'stroke-opacity': 0.34, 'stroke-width': 1.0, cap: 'round' },
  PAN: { stroke: C.titanium, 'stroke-opacity': 0.42, 'stroke-width': 0.7, cap: 'butt' },
  CONS: { stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.6, cap: 'butt', dash: '14 4 2 4' },
  DIM: { stroke: C.titanium, 'stroke-opacity': 0.7, 'stroke-width': 0.8, cap: 'butt' },
};
const FADE = new Set(['T3', 'T4', 'T5', 'PAN', 'T1b', 'SEAT']);
const FADE_K = [1, 0.72, 0.46];
let SIMPLE = false;
const B = {};
const put = (k, d) => { if (!d) return; (B[k] ||= []).push(d); };
function line3(k, pts3, close) {
  if (pts3.length < 2) return;
  if (FADE.has(k)) {
    const dm = pts3.reduce((t, p) => t + dep(p), 0) / pts3.length;
    const t = (dm - DMIN) / (DMAX - DMIN);
    put(`${k}|${t < 0.42 ? 0 : t < 0.7 ? 1 : 2}`, dP(pts3, close));
  } else put(k, dP(pts3, close));
}
function bucketOne(key) {
  if (!B[key] || !B[key].length) return '';
  const [k, bin] = key.split('|');
  const st = STY[k];
  let op = st['stroke-opacity'] * (bin ? FADE_K[+bin] : 1), w = st['stroke-width'];
  if (SIMPLE) { w *= 2.4; op = Math.min(1, op * 1.5); }
  const draw = st.dash ? {} : { class: 'cw-draw', pathLength: 1 };
  return el('path', { d: B[key].join(''), fill: 'none', stroke: st.stroke, 'stroke-opacity': n(op), 'stroke-width': n(w), 'stroke-linecap': st.cap, 'stroke-linejoin': 'round', 'stroke-dasharray': st.dash, ...draw });
}
function take(...keys) {
  let s = '';
  for (const k of keys) for (const key of Object.keys(B).filter((q) => q === k || q.startsWith(k + '|')).sort()) { s += bucketOne(key); delete B[key]; }
  return s;
}
const HATCH = [];
const sectionFace = (outer3, inner3) => HATCH.push(d2([...outer3.map(P), ...inner3.slice().reverse().map(P)], true));
function takeHatch() {
  const d = HATCH.join(''); HATCH.length = 0;
  if (!d) return '';
  return el('path', { d, fill: C.copper, 'fill-opacity': 0.1, stroke: 'none' }) + el('path', { class: 'cw-hatch', d, fill: 'url(#cw-hatch)', stroke: 'none' });
}

// surface curve split into front / back runs
function surfCurve(pts, nrms, kF, kB) {
  let run = [], vis = null;
  const flush = () => { if (run.length > 1 && (vis ? kF : kB)) line3(vis ? kF : kB, run); };
  pts.forEach((p, i) => {
    const v = facing(nrms[i]);
    if (vis === null) vis = v;
    if (v !== vis) { run.push(p); flush(); run = [p]; vis = v; } else run.push(p);
  });
  flush();
}
function boxEdges(k, a, b) {
  const [x0, y0, z0] = a, [x1, y1, z1] = b;
  const c = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
  [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]].forEach(([i, j]) => line3(k, [c[i], c[j]]));
}
function halfRing3(c, u, r) { const sv = norm(cross(u, V)), w = norm(cross(sv, u)); return range(0, 180, 9).map((a) => add(c, add(mul(sv, r * Math.cos(a * deg)), mul(w, r * Math.sin(a * deg))))); }
function basis(u) { const t = Math.abs(u[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0]; const e1 = norm(cross(u, t)); return [e1, cross(u, e1)]; }
const circle3 = (c, u, r, N = 32) => { const [e1, e2] = basis(norm(u)); return range(0, N - 1, 1).map((i) => add(c, add(mul(e1, r * Math.cos(i / N * 2 * Math.PI)), mul(e2, r * Math.sin(i / N * 2 * Math.PI))))); };
function tube(k, p0, p1, r, nSeg = 28, caps = true) {
  const u = norm(sub(p1, p0)), sv = norm(cross(u, V));
  line3(k, [add(p0, mul(sv, r)), add(p1, mul(sv, r))]); line3(k, [add(p0, mul(sv, -r)), add(p1, mul(sv, -r))]);
  if (caps) for (const c of [p0, p1]) line3(k, circle3(c, u, r, nSeg), true);
}

// ---------------------------------------------------------------- cut-away regions (fuselage surface coords, deg)
// th is measured from +y (starboard) through +z; the port side faces the viewer.
const vnoise = (t) => { const i = Math.floor(t), f = t - i; return lerp(hash(i), hash(i + 1), smooth(f)) * 2 - 1; };
const tri = (t) => { const f = t - Math.floor(t); return Math.abs(f - 0.5) * 4 - 1; };
const JAG = (x) => 2.2 * vnoise(x / 0.42) + 1.0 * tri(x / 0.17 + hash(Math.floor(x / 0.17))); // torn, irregular skin edge
const cutHiBase = (x) => {
  if (x < 0.25 || x > 28.3) return null;
  if (x < 1.35) return 112; // radome removed
  if (x < 1.75) return null;
  if (x < 2.9) return 203;
  if (x < 3.25) return lerp(203, 148, smooth((x - 2.9) / 0.35)); // flight-deck window
  if (x < 5.2) return 148;
  if (x < 5.55) return lerp(148, 203, smooth((x - 5.2) / 0.35));
  if (x < 9.2) return 203;
  if (x < 10.6) return lerp(203, 132, smooth((x - 9.2) / 1.4));
  if (x < 26.6) return 132;
  return lerp(132, 246, smooth((x - 26.6) / 1.7));
};
const cutHi = (x) => { const b = cutHiBase(x); if (b === null) return null; return x < 1.35 ? b : b + JAG(x); };
const CUT_LO = 246;
const tailCut = (x) => (x > 34.1 && x < 37.25 ? [lerp(118, 102, (x - 34.1) / 3.15) + JAG(x + 0.13), 252] : null);
function isCut(x, a) {
  const t = ((a % 360) + 360) % 360;
  const hi = cutHi(x);
  if (hi !== null && t >= hi && t <= CUT_LO) return true;
  const tc = tailCut(x);
  return !!(tc && t >= tc[0] && t <= tc[1]);
}

// ================================================================= AIRFRAME
const OBST = {};
function fuselageSilhouette() {
  const up = [], lo = [];
  for (let x = 0.02; x <= FL - 0.02; x += 0.12) {
    let prev = null; const hits = [];
    for (let a = 0; a <= 360; a += 2) {
      const v = dot(FN(x, a * deg), V);
      if (prev && Math.sign(v) !== Math.sign(prev.v)) hits.push(lerp(prev.a, a, prev.v / (prev.v - v)) * deg);
      prev = { a, v };
    }
    if (hits.length >= 2) {
      const pa = P(FS(x, hits[0])), pb = P(FS(x, hits[1]));
      if (pa[1] < pb[1]) { up.push(pa); lo.push(pb); } else { up.push(pb); lo.push(pa); }
    }
  }
  const nose = P(FS(0.001, 0));
  return { up, lo, nose, poly: [nose, ...up, ...lo.slice().reverse()] };
}

function drawFuselage(full) {
  const out = {};
  const sil = fuselageSilhouette();
  OBST.fus = sil.poly;
  out.fill = el('path', { d: d2(sil.poly, true), fill: C.midnight, 'fill-opacity': full ? 0.66 : 0.9, stroke: 'none' });
  put('T1', d2([sil.nose, ...sil.up])); put('T1', d2([sil.nose, ...sil.lo]));
  line3('T1b', range(0, 360, 10).map((a) => FS(FL - 0.02, a * deg)), true);
  if (!full) {
    // phone: primary structure only (every 4th frame front face, floor edge, cut edge)
    range(1.0, FL - 0.4, 0.62).forEach((x, i) => { if (i % 2) return; const pts = [], nr = []; for (let a = 0; a <= 360; a += 6) { pts.push(FS(x, a * deg)); nr.push(FN(x, a * deg)); } surfCurve(pts, nr, i % 4 ? 'T4' : 'T3', null); });
    const edge = []; for (let x = 0.25; x <= 28.3; x += 0.1) { const hi = cutHi(x); if (hi === null) { if (edge.length > 1) line3('T2', edge); edge.length = 0; continue; } edge.push(FS(x, hi * deg)); }
    if (edge.length > 1) line3('T2', edge);
    line3('T3', range(9.4, 28.2, 0.4).map((x) => [x, -floorY(x), FLOOR_Z]));
    return out;
  }
  // frames: T3 every 4th station, T4 otherwise; back side T5 every 2nd; inside the cut the frames stay (T3/T4)
  const frameXs = range(1.0, FL - 0.4, 0.62);
  frameXs.forEach((x, i) => {
    const pts = [], keys = [];
    for (let a = 0; a <= 360; a += 4) {
      const th = a * deg; pts.push(FS(x, th));
      const vis = facing(FN(x, th));
      keys.push(!vis ? (i % 2 ? null : 'T5') : i % 4 === 0 ? 'T3' : 'T4');
    }
    let run = [], key;
    const flush = () => { if (run.length > 1 && key) line3(key, run); };
    pts.forEach((p, j) => { if (keys[j] !== key) { if (run.length) run.push(p); flush(); run = [p]; key = keys[j]; } else run.push(p); });
    flush();
  });
  // stringers: front skin only, stopping at the cut
  for (let a = 0; a < 360; a += 11.25) {
    let run = [];
    for (let x = 1.2; x <= FL - 0.6; x += 0.3) {
      const ok = facing(FN(x, a * deg)) && !isCut(x, a);
      if (ok) run.push(FS(x, a * deg)); else { if (run.length > 1) line3('T4', run); run = []; }
    }
    if (run.length > 1) line3('T4', run);
  }
  // torn cut edge (T2) + section face (45° copper hatch) + frame and stringer stubs past the edge
  const segs = []; let cur = [];
  for (let x = 0.25; x <= 28.3; x += 0.05) { const hi = cutHi(x); if (hi === null) { if (cur.length > 1) segs.push(cur); cur = []; continue; } cur.push([x, hi]); }
  if (cur.length > 1) segs.push(cur);
  for (const sg of segs) {
    line3('T2', sg.map(([x, a]) => FS(x, a * deg)));
    line3('T2b', sg.map(([x, a]) => FSin(x, a * deg)));
    sectionFace(sg.map(([x, a]) => FS(x, a * deg)), sg.map(([x, a]) => FSin(x, a * deg)));
    // closing ends of each cut run
    for (const [x, a] of [sg[0], sg[sg.length - 1]]) {
      const end = range(a, CUT_LO, 3).map((t) => FS(x, t * deg));
      line3('T2', end); line3('T2b', range(a, CUT_LO, 3).map((t) => FSin(x, t * deg)));
      sectionFace(end, range(a, CUT_LO, 3).map((t) => FSin(x, t * deg)));
    }
  }
  frameXs.forEach((x) => { const hi = cutHi(x); if (hi === null) return; line3('T3', [FS(x, (hi - 0.5) * deg), FS(x, (hi + 6) * deg)]); });
  for (let a = 0; a < 360; a += 11.25) { // stringer stubs where a stringer runs into the cut boundary
    for (let x = 0.4; x <= 28.2; x += 0.05) {
      const h0 = cutHi(x), h1 = cutHi(x + 0.05);
      if (h0 === null || h1 === null) continue;
      if ((a - h0) * (a - h1) < 0 && facing(FN(x, a * deg))) { const dir = h1 < h0 ? 1 : -1; line3('T3', [FS(x, a * deg), FS(x + dir * 0.3, a * deg)]); }
    }
  }
  // tailcone cut
  const te = [], tb = [];
  for (let x = 34.15; x <= 37.2; x += 0.06) { const tc = tailCut(x); te.push([x, tc[0]]); tb.push([x, tc[1]]); }
  for (const sg of [te]) { line3('T2', sg.map(([x, a]) => FS(x, a * deg))); line3('T2b', sg.map(([x, a]) => FSin(x, a * deg, 0.1))); sectionFace(sg.map(([x, a]) => FS(x, a * deg)), sg.map(([x, a]) => FSin(x, a * deg, 0.1))); }
  line3('T2', tb.map(([x, a]) => FS(x, a * deg)));
  for (const x of [34.15, 37.2]) { const a0 = tailCut(x + (x > 35 ? -0.01 : 0.01))[0]; const ed = range(a0, 252, 4).map((t) => FS(x, t * deg)); line3('T2', ed); sectionFace(ed, range(a0, 252, 4).map((t) => FSin(x, t * deg, 0.1))); }
  // cut window inner glow
  const cab = segs.find((sg) => sg[0][0] > 1.5 && sg[sg.length - 1][0] > 20);
  if (cab) out.glow = el('path', { d: d2([...cab.map(([x, a]) => P(FS(x, a * deg))), ...cab.slice().reverse().map(([x]) => P(FS(x, CUT_LO * deg)))], true), fill: 'url(#cw-innerglow)', stroke: 'none' });
  // windows and doors on the uncut front skin; starboard doors as hidden lines
  for (let x = 3.9; x <= 33.4; x += 0.53) {
    if (isCut(x, 167) || (x > 5.8 && x < 6.95) || (x > 32.7 && x < 33.8)) continue;
    const c = FS(x, 167 * deg);
    line3('PAN', range(0, 360, 30).map((a) => add(c, [0.13 * Math.cos(a * deg), 0, 0.2 * Math.sin(a * deg)])), true);
  }
  const door = (k, x0, x1, a0, a1) => line3(k, [...range(a0, a1, 4).map((a) => FS(x0, a * deg)), ...range(x0, x1, 0.1).map((x) => FS(x, a1 * deg)), ...range(a1, a0, -4).map((a) => FS(x1, a * deg)), ...range(x1, x0, -0.1).map((x) => FS(x, a0 * deg))]);
  door('T3', 5.95, 6.8, 142, 196); door('T3', 32.85, 33.65, 146, 194);
  door('T5', 5.95, 6.8, -16, 38); door('T5', 32.85, 33.65, -14, 34); // service doors (starboard, hidden)
  door('T3', 8.0, 9.0, 205, 222); // forward cargo door
  return out;
}

function drawInterior() {
  // floor plane, beams, seat tracks
  const fl = el('path', { d: dP([...range(9.4, 28.2, 0.4).map((x) => [x, -floorY(x), FLOOR_Z]), ...range(28.2, 9.4, -0.4).map((x) => [x, floorY(x), FLOOR_Z])], true), fill: C.titanium, 'fill-opacity': 0.04, stroke: 'none' });
  line3('T3', range(2.2, 31.5, 0.3).map((x) => [x, -floorY(x), FLOOR_Z]));
  line3('T4', range(2.2, 31.5, 0.3).map((x) => [x, floorY(x), FLOOR_Z]));
  range(2.4, 31.2, 0.62).forEach((x) => line3(x > 9.2 && x < 28.5 ? 'T3' : 'T4', [[x, -floorY(x), FLOOR_Z], [x, floorY(x), FLOOR_Z]])); // floor-beam ladder
  for (const y of [-1.32, -0.56, 0.56, 1.32]) line3('T4', [[9.6, y, FLOOR_Z + 0.01], [28, y, FLOOR_Z + 0.01]]);
  // seats: near half of the cabin only (the far half made moiré)
  for (let x = 10.9; x <= 26.2; x += 0.78) {
    if (Math.abs(x - 15.6) < 0.5) continue;
    for (const y of [-1.58, -1.07, -0.56]) {
      const w = 0.22, zc = FLOOR_Z + 0.44, zb = FLOOR_Z + 1.12;
      line3('SEAT', [[x - 0.04, y - w, zc], [x + 0.4, y - w, zc], [x + 0.5, y - w, zb]]); // cushion + back (one seat-row glyph)
    }
  }
  line3('T4', range(7, 28.5, 0.5).map((x) => [x, -1.42, 1.25])); line3('T4', range(7, 28.5, 0.5).map((x) => [x, -1.05, 1.62]));
  // pressure bulkheads
  line3('T3', range(0, 360, 6).map((a) => FS(1.4, a * deg)));
  const s29 = sec(29.6);
  for (const r of [0.97, 0.75, 0.52, 0.3]) line3(r > 0.9 ? 'T3' : 'T4', range(0, 360, 8).map((a) => [29.6 + 0.55 * (1 - r), s29.ry * r * Math.cos(a * deg), s29.zc + s29.rz * r * Math.sin(a * deg)]));
  // flight deck: floor, two seats, glareshield, instrument panel, centre pedestal, cockpit door bulkhead
  line3('T3', [[2.3, -floorY(2.3, -0.35), -0.35], [4.7, -floorY(4.7, -0.35), -0.35]]);
  for (const y of [-0.5, 0.5]) {
    const x = 3.55, zc = -0.35 + 0.45, zb = -0.35 + 1.15;
    line3('T3', [[x - 0.25, y - 0.24, zc], [x + 0.25, y - 0.24, zc], [x + 0.36, y - 0.24, zb], [x + 0.36, y + 0.24, zb], [x + 0.25, y + 0.24, zc], [x - 0.25, y + 0.24, zc], [x - 0.25, y - 0.24, zc]]);
    line3('T4', [[x, y, -0.35], [x, y, zc]]);
  }
  line3('T3', range(-0.82, 0.82, 0.1).map((y) => [2.55 + 0.12 * (y * y), y, 0.5 - 0.05 * y * y]));
  boxEdges('T4', [2.5, -0.8, -0.2], [2.62, 0.8, 0.48]);
  boxEdges('T3', [2.8, -0.13, -0.35], [3.55, 0.13, 0.12]);
  line3('T3', range(0, 360, 8).map((a) => FSin(4.75, a * deg, 0.05)));
  // E/E bay with racks and shelves (parts sit on the shelves)
  boxEdges('T3', [5.85, -0.85, -1.92], [9.35, 0.85, FLOOR_Z - 0.04]);
  for (const [y0, y1] of [[-0.72, -0.22], [0.25, 0.72]]) {
    boxEdges(y0 < 0 ? 'T3' : 'T4', [5.95, y0, -1.86], [9.2, y1, -0.68]);
    for (const z of [-1.57, -1.13]) line3(y0 < 0 ? 'T3' : 'T4', [[5.95, y0, z], [9.2, y0, z], [9.2, y1, z]]);
    for (const x of [6.95, 7.85, 8.6]) line3('T4', [[x, y0, -1.86], [x, y0, -0.68]]);
  }
  // nose-gear bay with open doors
  boxEdges('T3', [3.9, -0.5, -1.95], [6.35, 0.5, -1.0]);
  for (const s of [-1, 1]) line3('T3', [[4.0, s * 0.52, -1.98], [6.25, s * 0.52, -1.98], [6.25, s * 0.6, -2.62], [4.0, s * 0.6, -2.62], [4.0, s * 0.52, -1.98]]);
  // keel beam + centre wing box (spars + 4 ribs) + main-gear wheel well with door hinge lines
  line3('T3', [[11.0, 0, -2.0], [21.5, 0, -2.0]]); line3('T3', [[11.0, 0, -1.8], [21.5, 0, -1.8]]);
  for (const x of range(11.4, 21.2, 0.62)) line3('T4', [[x, 0, -2.0], [x, 0, -1.8]]);
  boxEdges('T3', [12.75, -1.7, -1.95], [16.3, 1.7, -0.95]); // centre wing box (tank)
  line3('T2b', [[12.75, -1.7, -0.95], [16.3, -1.7, -0.95], [16.3, 1.7, -0.95]]); // its upper skin, cut
  for (const x of [12.75, 16.3]) for (const z of [-1.7, -1.2]) line3('T4', [[x, -1.7, z], [x, 1.7, z]]); // spar stiffeners
  for (const y of [-1.0, -0.33, 0.33, 1.0]) line3('T3', [[12.75, y, -1.95], [16.3, y, -1.95], [16.3, y, -0.95], [12.75, y, -0.95], [12.75, y, -1.95]]);
  const wx0 = 16.55, wx1 = 19.6, wy = 1.25; // main-gear wheel well behind the wing box
  line3('T3', [[wx0, -wy, -2.06], [wx1, -wy, -2.06], [wx1, wy, -2.06], [wx0, wy, -2.06], [wx0, -wy, -2.06]]);
  for (const y of [-wy, wy]) line3('T3', [[wx0, y, -2.06], [wx0, y, -1.0], [wx1, y, -1.0], [wx1, y, -2.06]]);
  for (const y of [-0.62, 0.62]) line3('T4', [[wx0 + 0.1, y, -2.08], [wx1 - 0.1, y, -2.08]]); // door hinge lines
  // cargo holds: hold floor + containers / bags
  for (const [x0, x1] of [[9.6, 12.4], [20.8, 27.8]]) {
    line3('T4', [[x0, -1.3, -1.45], [x1, -1.3, -1.45]]); line3('T4', [[x0, 1.3, -1.45], [x1, 1.3, -1.45]]);
  }
  for (const [x0, x1] of [[21.0, 22.5], [22.7, 24.2], [24.4, 25.9], [10.0, 11.4]]) {
    boxEdges('T4', [x0, -0.75, -1.45], [x1, 0.75, -0.72]);
    line3('T4', [[x0, -0.75, -1.45], [x1, -0.75, -0.72]]);
  }
  for (const [x, y] of [[26.4, -0.6], [26.9, -0.2], [27.2, -0.75]]) boxEdges('T4', [x, y, -1.45], [x + 0.45, y + 0.3, -1.2]);
  // belly fairing where the wing meets the fuselage (near side)
  line3('T1b', range(10.6, 22.4, 0.3).map((x) => { const t = (x - 10.6) / 11.8; return [x, -1.45 - 0.5 * Math.sin(Math.PI * t), -2.05 - 0.3 * Math.sin(Math.PI * t) ** 0.6]; }));
  // aft bulkhead of the forward hold, radar antenna
  line3('T3', range(0, 360, 10).map((a) => [0.95, 0.62 * Math.cos(a * deg), -0.45 + 0.6 * Math.sin(a * deg)]), true);
  line3('T4', [[0.95, 0, -0.45], [1.4, 0, -0.45]]);
  // APU bay: firewalls, APU body, exhaust and inlet
  for (const x of [34.3, 37.0]) { const s = sec(x); line3('T3', range(0, 360, 8).map((a) => [x, s.ry * 0.96 * Math.cos(a * deg), s.zc + s.rz * 0.96 * Math.sin(a * deg)]), true); }
  tube('T3', [34.85, 0, 0.78], [36.6, 0, 0.8], 0.34, 32);
  boxEdges('T3', [34.45, -0.3, 0.5], [34.85, 0.3, 1.05]); // reduction gearbox (carries the starter and fuel control)
  for (const x of [35.3, 35.8, 36.2]) line3('T4', range(0, 360, 10).map((a) => [x, 0.34 * Math.cos(a * deg), 0.79 + 0.34 * Math.sin(a * deg)]), true);
  line3('T3', [[36.6, 0.2, 0.86], [37.55, 0.1, 0.87]]); line3('T3', [[36.6, -0.2, 0.74], [37.55, -0.1, 0.83]]);
  line3('T4', [[35.4, 0, 1.12], [35.0, 0, 1.33]]); line3('T4', [[35.8, 0, 1.12], [35.6, 0, 1.36]]);
  // packs (heat-exchanger boxes)
  boxEdges('T3', [10.95, -1.2, -2.0], [12.6, -0.4, -1.35]); boxEdges('T4', [10.95, 0.4, -2.0], [12.6, 1.2, -1.35]);
  // hydraulic reservoirs
  tube('T4', [17.0, -0.8, -1.35], [17.6, -0.8, -1.35], 0.15, 20); tube('T4', [17.0, 0.8, -1.35], [17.6, 0.8, -1.35], 0.15, 20);
  return fl;
}

// ---------------------------------------------------------------- wing (with thickness, closed tips)
function wingOutline(s, y0, y1) {
  const span = range(y0, y1, 0.25);
  return [...span.map((y) => wPt(s, y, 0)), ...range(0, 1, 0.05).map((f) => wPt(s, y1, f)), ...span.slice().reverse().map((y) => wPt(s, y, 1))];
}
function drawWing(s, full, near = false) {
  const K = near ? { sil: 'T1', sil2: 'T1b', st: 'T3', fine: 'T4', pan: 'PAN', hid: 'T5' } : { sil: 'FAR', sil2: 'T5', st: 'T5', fine: 'T5', pan: 'T5', hid: 'T5' };
  const yIn = near ? 4.8 : WG.y0;
  const span = range(yIn, WG.yt, 0.25);
  const out = [];
  if (near) out.push(el('path', { d: dP(wingOutline(s, yIn, WG.yt), true) + dP(winPoly(s), true), fill: C.midnight, 'fill-opacity': 0.5, 'fill-rule': 'evenodd', stroke: 'none' }));
  line3(K.sil, span.map((y) => wPt(s, y, 0))); line3(K.sil, span.map((y) => wPt(s, y, 1)));
  // thickness: lower leading-edge line, closed tip section
  line3(K.sil2, span.map((y) => wPt(s, y, 0.05, -1)));
  line3(K.sil, [...range(0, 1, 0.05).map((f) => wPt(s, WG.yt, f, 1)), ...range(1, 0, -0.05).map((f) => wPt(s, WG.yt, f, -1))], true);
  // winglet
  const wt = wPt(s, WG.yt, 0), wtTe = wPt(s, WG.yt, 1);
  const wlTop = [wt[0] + 1.25, s * (WG.yt + 0.38), wt[2] + 2.05], wlTopTe = [wt[0] + 1.95, s * (WG.yt + 0.42), wt[2] + 2.1];
  const blendLe = range(0, 1, 0.1).map((t) => { const a = t * Math.PI / 2; return [lerp(wt[0], wlTop[0], 1 - Math.cos(a)), s * (WG.yt + 0.38 * Math.sin(a) ** 1.5), wt[2] + 2.05 * (1 - Math.cos(a)) ** 0.9]; });
  const blendTe = range(0, 1, 0.1).map((t) => { const a = t * Math.PI / 2; return [lerp(wtTe[0], wlTopTe[0], (1 - Math.cos(a)) * 0.8 + 0.2 * t), s * (WG.yt + 0.42 * Math.sin(a) ** 1.5), wtTe[2] + 2.1 * (1 - Math.cos(a))]; });
  line3(K.sil, blendLe); line3(K.sil, blendTe); line3(K.sil, [wlTop, wlTopTe]);
  if (!full) {
    if (near) { for (const f of [0.15, 0.62]) line3('T3', range(yIn, WG.yt - 0.3, 0.4).map((y) => wPt(s, y, f))); line3('T2', winPoly(s), true); }
    return out.join('');
  }
  // spars (hidden under the skin) + control surfaces
  // spars (front 15 %, rear 62 %) and ribs every ~1.2 m, seen through the skin
  for (const f of [0.15, 0.62]) line3(near ? 'T3' : 'T5', range(yIn, WG.yt - 0.3, 0.3).map((y) => wPt(s, y, f)));
  for (const y of range(yIn + 0.6, WG.yt - 0.4, 1.2)) line3(near ? 'T4' : 'T5', range(0.15, 0.62, 0.05).map((f) => wPt(s, y, f)));
  if (near) line3('T1b', range(yIn, WG.yt, 0.25).map((y) => wPt(s, y, 0.16, -1))); // lower surface: the wing's thickness
  for (const [a, b] of [[2.3, 5.0], [6.9, 9.3], [9.3, 11.8], [11.8, 14.2], [14.2, 16.5]]) {
    if (near && a < yIn) continue;
    line3(K.pan, range(a, b, 0.25).map((y) => wPt(s, y, 0.13))); line3(K.pan, [wPt(s, a, 0), wPt(s, a, 0.13)]); line3(K.pan, [wPt(s, b, 0), wPt(s, b, 0.13)]);
  }
  const cs = (a, b, f0, f1) => { line3(K.pan, range(a, b, 0.25).map((y) => wPt(s, y, f0))); line3(K.pan, [wPt(s, a, f0), wPt(s, a, f1)]); line3(K.pan, [wPt(s, b, f0), wPt(s, b, f1)]); };
  cs(Math.max(WG.y0 + 0.1, yIn), WG.yk, 0.73, 1); cs(WG.yk, 12.7, 0.72, 1); cs(12.85, 16.25, 0.76, 1);
  for (const [a, b] of [[3.0, 5.1], [6.6, 8.1], [8.1, 9.6], [9.6, 11.1], [11.1, 12.5]]) if (!near || a >= yIn) cs(a, b, 0.6, 0.72);
  for (const y of [4.2, 8.0, 10.7, 13.2]) {
    if (near && y < yIn) continue;
    line3(K.fine, range(0, 1, 0.08).map((t) => { const f = lerp(0.55, 1.28, t); return [wXle(y) + f * wC(y), s * y, wZ(y) - 0.25 * Math.sin(Math.PI * t) - 0.08]; }));
  }
  if (near) {
    // cut wing root: spars, ribs, torn cut + hatched section face
    for (const f of [0.15, 0.62]) { line3('T3', range(WG.y0, yIn, 0.2).map((y) => wPt(s, y, f))); line3('T3', range(WG.y0, yIn, 0.2).map((y) => wPt(s, y, f, -1))); }
    for (const y of range(WG.y0 + 0.3, yIn, 0.6)) { line3('T3', range(0.15, 0.62, 0.04).map((f) => wPt(s, y, f))); line3('T4', [wPt(s, y, 0.15), wPt(s, y, 0.15, -1)]); line3('T4', [wPt(s, y, 0.62), wPt(s, y, 0.62, -1)]); }
    line3('T4', range(WG.y0, yIn, 0.2).map((y) => wPt(s, y, 0.15, -1)));
    line3('CONS', range(WG.y0, yIn, 0.25).map((y) => wPt(s, y, 0))); line3('CONS', range(WG.y0, yIn, 0.25).map((y) => wPt(s, y, 1)));
    const up = range(0, 1, 0.04).map((f) => wPt(s, yIn + 0.12 * Math.sin(f * 37), f, 1)), lo = range(0, 1, 0.04).map((f) => wPt(s, yIn + 0.12 * Math.sin(f * 37), f, -1));
    line3('T2', [...up, ...lo.slice().reverse()], true);
    sectionFace(up, lo);
    // tank window: ribs every ~1.2 m section, spars, stringers on the lower skin
    for (const y of range(7.6, 11.4, 0.6)) line3('T3', range(0.15, 0.62, 0.04).map((f) => wPt(s, y, f)));
    for (const f of [0.15, 0.62]) line3('T3', range(7.5, 11.5, 0.2).map((y) => wPt(s, y, f)));
    for (const f of [0.27, 0.39, 0.51]) line3('T4', range(7.5, 11.5, 0.2).map((y) => wPt(s, y, f, -1)));
    const w = winPoly(s); line3('T2', w, true);
    sectionFace(w, w.map((p) => add(p, [0, 0, -0.07])));
  }
  return out.join('');
}
const winPoly = (s) => [...range(7.5, 11.5, 0.25).map((y) => wPt(s, y, 0.14 + 0.012 * Math.sin(y * 9))), ...range(0.14, 0.63, 0.07).map((f) => wPt(s, 11.5, f)), ...range(11.5, 7.5, -0.25).map((y) => wPt(s, y, 0.63 + 0.012 * Math.sin(y * 7))), ...range(0.63, 0.14, -0.07).map((f) => wPt(s, 7.5, f))];

function drawTailplane(s, full, near = false) {
  const K = near ? { sil: 'T1', pan: 'PAN' } : { sil: 'FAR', pan: 'T5' };
  const span = range(TP.y0, TP.yt, 0.2);
  line3(K.sil, span.map((y) => tPt(s, y, 0))); line3(K.sil, span.map((y) => tPt(s, y, 1)));
  line3(K.sil, [...range(0, 1, 0.05).map((f) => tPt(s, TP.yt, f, 1)), ...range(1, 0, -0.05).map((f) => tPt(s, TP.yt, f, -1))], true); // closed tip
  line3(near ? 'T3' : 'FAR', [tPt(s, TP.y0, 0), tPt(s, TP.y0, 1)]); // root chord closes the outline
  for (const f of [0.15, 0.62]) line3(near ? 'T4' : 'T5', range(TP.y0, TP.yt - 0.2, 0.3).map((y) => tPt(s, y, f)));
  for (const y of range(TP.y0 + 0.8, TP.yt - 0.3, 1.2)) line3(near ? 'T4' : 'T5', [tPt(s, y, 0.15), tPt(s, y, 0.62)]);
  if (near) line3('T1b', span.map((y) => tPt(s, y, 0.04, -1))); // leading-edge radius line
  if (!full) return;
  line3(K.pan, range(TP.y0 + 0.3, TP.yt - 0.2, 0.2).map((y) => tPt(s, y, 0.7)));
  line3(K.pan, [tPt(s, TP.yt - 0.2, 0.7), tPt(s, TP.yt - 0.2, 1)]);
  line3('T5', range(TP.y0, TP.yt - 0.2, 0.2).map((y) => tPt(s, y, 0.18)));
}
function drawFin(full) {
  const etas = range(0, 1, 0.05);
  FIN_FILL = el('path', { d: dP([...etas.map((e) => fPt(e, 0)), ...etas.slice().reverse().map((e) => fPt(e, 1))], true), fill: C.midnight, 'fill-opacity': 0.55, stroke: 'none' });
  line3('T1', etas.map((e) => fPt(e, 0))); line3('T1', etas.map((e) => fPt(e, 1)));
  line3('T1', [...range(0, 1, 0.05).map((f) => fPt(1, f, -1)), ...range(1, 0, -0.05).map((f) => fPt(1, f, 1))], true); // closed tip
  line3('T1b', etas.map((e) => fPt(e, 0.035, -1))); // leading-edge radius line (port side)
  { const te = fPt(0, 1), s2 = sec(te[0]); line3('T1', [te, [te[0] + 0.25, 0, s2.zc + s2.rz]]); } // trailing edge closes into the tail cone
  const top = (x) => { const s = sec(x); return s.zc + s.rz; };
  line3('T1', range(0, 1, 0.05).map((t) => { const x = lerp(26.4, FIN.xr + 0.9, t); return [x, 0, lerp(top(26.4), fPt(0.12, 0)[2], t ** 1.8)]; }));
  if (!full) return;
  line3('PAN', range(0.02, 0.97, 0.05).map((e) => fPt(e, 0.68, -1)));
  line3('PAN', [fPt(0.97, 0.68, -1), fPt(0.97, 1)]);
  for (const e of [0.33, 0.66]) line3('PAN', [fPt(e, 0.68, -1), fPt(e, 1)]);
  for (const f of [0.15, 0.62]) line3('T4', etas.map((e) => fPt(e, f, -1)));
  for (const e of range(0.1, 0.95, 0.12)) line3('T4', [fPt(e, 0.15, -1), fPt(e, 0.62, -1)]);
  line3('T3', [...range(0, 1, 0.05).map((f) => fPt(0, f, -1)), ...range(1, 0, -0.05).map((f) => fPt(0, f, 1))], true);
}

// ---------------------------------------------------------------- nacelle (revolved profile; near one sectioned)
const NCUT = { a0: 132 * deg, a1: 262 * deg, x0: 8.65, x1: 12.85 };
function drawNacelle(s, full, near = false) {
  const K = near ? { sil: 'T1', st: 'T3', fine: 'T4', pan: 'PAN' } : { sil: 'FAR', st: 'T5', fine: 'T5', pan: 'T5' };
  const u = [1, 0, 0], sv = norm(cross(u, V));
  const xs = range(NAC.prof[0][0], NAC.prof[NAC.prof.length - 1][0], 0.1);
  const out = [];
  const ax = (x) => [x, s * NAC.y, NAC.z];
  if (near) out.push(el('path', { d: dP([...xs.map((x) => add(ax(x), mul(sv, nacR(x)))), ...xs.slice().reverse().map((x) => add(ax(x), mul(sv, -nacR(x))))], true), fill: C.midnight, 'fill-opacity': 0.62, stroke: 'none' }));
  line3(K.sil, xs.map((x) => add(ax(x), mul(sv, nacR(x))))); line3(K.sil, xs.map((x) => add(ax(x), mul(sv, -nacR(x)))));
  const x0 = NAC.prof[0][0];
  line3(K.sil, range(0, 360, 6).map((a) => nacPt(s, x0, 0.9, a * deg)), true);
  line3(K.st, range(0, 360, 6).map((a) => nacPt(s, x0 + 0.07, 0.8, a * deg)), true);
  if (full || near) {
    const fx = x0 + 0.55;
    line3(K.fine, range(0, 360, 8).map((a) => nacPt(s, fx, 0.78, a * deg)), true);
    for (let b = 0; b < 20; b++) { const a = b / 20 * 2 * Math.PI; line3(K.st, [nacPt(s, fx - 0.08, 0.24, a), nacPt(s, fx + 0.06, 0.76, a + 0.14)]); }
    line3(K.st, range(0, 360, 10).map((a) => nacPt(s, fx - 0.1, 0.24, a * deg)), true);
    line3(K.st, [nacPt(s, x0 + 0.2, 0, 0), nacPt(s, fx - 0.1, 0.24, 140 * deg)]); line3(K.st, [nacPt(s, x0 + 0.2, 0, 0), nacPt(s, fx - 0.1, 0.24, 320 * deg)]);
  }
  if (full) for (const x of [8.7, 10, 11.1, 11.75, 13]) {
    const pts = [], nr = [];
    for (let a = 0; a <= 360; a += 6) { const inCut = near && x > NCUT.x0 && x < NCUT.x1 && a * deg > NCUT.a0 && a * deg < NCUT.a1; pts.push(nacPt(s, x, nacR(x), a * deg)); nr.push(inCut ? [0, 0, 0] : [0, Math.cos(a * deg), Math.sin(a * deg)]); }
    surfCurve(pts, nr, K.pan, near ? null : null);
  }
  // swept-box pylon: two side profiles (±0.24) joined by edges, plus the aft fairing curve
  const yP = s * NAC.y;
  const prof = (dy) => [[9.2, yP + dy, NAC.z + 1.0], [wXle(NAC.y) - 0.2, yP + dy, wPt(1, NAC.y, 0.02, -1)[2] - 0.02], [wXle(NAC.y) + wC(NAC.y) * 0.62, yP + dy, wPt(1, NAC.y, 0.62, -1)[2] - 0.02], [13.4, yP + dy, NAC.z + 0.62], [12.4, yP + dy, NAC.z + 0.7]];
  const pa = prof(-0.24), pb = prof(0.24);
  if (near) out.push(el('path', { d: dP(pa, true), fill: C.midnight, 'fill-opacity': 0.55, stroke: 'none' }));
  line3(near ? 'T1' : 'T5', [...pa, pa[0]]); line3(near ? 'T3' : 'FAR', [...pb, pb[0]]);
  for (let i = 0; i < pa.length; i++) line3(near ? 'T3' : 'T5', [pa[i], pb[i]]);
  line3(near ? 'T3' : 'T5', range(0, 1, 0.1).map((t) => [lerp(13.4, wXle(NAC.y) + wC(NAC.y) * 0.95, t), yP, lerp(NAC.z + 0.62, wPt(1, NAC.y, 0.95, -1)[2] - 0.05, Math.sin(t * Math.PI / 2))]));
  if (near && full) {
    // cowl cut: torn edges + hatched cowl section; inside, the core: fan, 3 compressor discs, combustor, turbine
    const jag = (t, i) => 0.04 * vnoise(t * 5 + i * 0.1) + 0.02 * tri(t * 7.3);
    const eA = range(NCUT.x0, NCUT.x1, 0.12).map((x, i) => nacPt(s, x, nacR(x), NCUT.a0 + jag(x, i)));
    const eB = range(NCUT.x0, NCUT.x1, 0.12).map((x, i) => nacPt(s, x, nacR(x), NCUT.a1 + jag(x, i)));
    const e0 = range(NCUT.a0, NCUT.a1, 4 * deg).map((a) => nacPt(s, NCUT.x0, nacR(NCUT.x0), a));
    const e1 = range(NCUT.a0, NCUT.a1, 4 * deg).map((a) => nacPt(s, NCUT.x1, nacR(NCUT.x1), a));
    for (const e of [eA, eB, e0, e1]) { line3('T2', e); sectionFace(e, e.map((p) => { const r = sub(p, ax(p[0])); return add(ax(p[0]), mul(r, 0.88)); })); }
    // engine core as a drum with discrete stages (visible half of each disc, so it reads as stages, not a coil)
    const u = [1, 0, 0], svx = norm(cross(u, V));
    const stage = (x, r, k = 'T3') => line3(k, halfRing3(ax(x), u, r));
    const drum = (x0, r0, x1, r1, k = 'T1b') => { line3(k, [add(ax(x0), mul(svx, r0)), add(ax(x1), mul(svx, r1))]); line3(k, [add(ax(x0), mul(svx, -r0)), add(ax(x1), mul(svx, -r1))]); };
    drum(9.35, 0.5, 10.55, 0.36); range(0, 6, 1).forEach((i) => stage(9.4 + i * 0.19, lerp(0.5, 0.37, i / 6))); // 7-stage compressor
    drum(10.65, 0.46, 11.4, 0.46, 'T3'); for (const x of [10.65, 11.4]) stage(x, 0.46, 'T1b'); line3('T4', halfRing3(ax(11.02), u, 0.3)); // combustor ring
    drum(11.5, 0.42, 12.15, 0.38, 'T3'); [11.55, 11.8, 12.05].forEach((x, i) => stage(x, 0.42 - i * 0.02)); // 3-stage turbine
    line3('T3', [add(ax(12.2), mul(svx, 0.3)), ax(13.2)]); line3('T3', [add(ax(12.2), mul(svx, -0.3)), ax(13.2)]); stage(12.2, 0.3); // tail cone
    line3('T4', [ax(9.2), ax(12.2)]); // shaft
    boxEdges('T3', [9.3, yP - 0.82, NAC.z - 0.98], [10.85, yP - 0.38, NAC.z - 0.66]); // accessory gearbox
  }
  return out.join('');
}

// ---------------------------------------------------------------- landing gear structure (legs, braces, axles)
function drawMainGear(s, near) {
  const k = near ? 'T3' : 'T5', kb = near ? 'T1b' : 'T5';
  // trunnion at the rear spar, oleo (two nested cylinders), two-link side brace, drag brace, axle aft of the leg
  const y = s * MG.y, lx = MG.x - 0.35, top = [lx, y, MG.zTop], knee = [lx + 0.05, y, MG.zTop - 1.3], ax = [MG.x, y, MG.zAx];
  tube(kb, [lx - 0.35, y, MG.zTop], [lx + 0.3, y, MG.zTop], 0.09, 14); // trunnion
  tube(kb, top, knee, 0.16, 18); // oleo outer cylinder
  tube(k, knee, [lx + 0.1, y, MG.zAx + 0.18], 0.1, 14); // sliding piston
  line3(kb, [[lx + 0.1, y, MG.zAx + 0.18], add(ax, [0, 0, 0.05])]); // bogie arm to the axle (wheels sit aft of the leg)
  line3(k, [add(knee, [0.14, 0, -0.05]), add(lerp3(knee, ax, 0.5), [0.4, 0, 0.05]), [lx + 0.24, y, MG.zAx + 0.3]]); // torque link
  const sb0 = lerp3(top, knee, 0.62), sbK = [lx + 0.05, s * (MG.y - 0.75), MG.zTop - 0.55], sb1 = [lx + 0.05, s * 1.35, -1.7];
  line3(kb, [sb0, sbK, sb1]); line3(k, range(0, 360, 30).map((a) => add(sbK, [0.05 * Math.cos(a * deg), 0, 0.05 * Math.sin(a * deg)])), true); // two-link side brace
  line3(k, [lerp3(top, knee, 0.5), [lx - 0.7, s * (MG.y + 0.9), wZ(MG.y + 0.9) - 0.32]]); // drag brace to the rear spar
  line3(kb, [add(ax, [0, -MG.dy - 0.22, 0]), add(ax, [0, MG.dy + 0.22, 0])]); // axle
  line3(k, [[lx - 0.55, y - s * 0.3, MG.zTop - 0.1], [lx + 0.5, y - s * 0.3, MG.zTop - 0.1], [lx + 0.45, y - s * 0.26, -2.7], [lx - 0.5, y - s * 0.26, -2.7], [lx - 0.55, y - s * 0.3, MG.zTop - 0.1]]); // leg door
  // wheel well in the belly fairing (dashed ellipse)
  line3('T5', range(0, 360, 10).map((a) => [MG.x + 0.9 + 1.1 * Math.cos(a * deg), s * (1.15 + 0.62 * Math.sin(a * deg)), -2.12]), true);
  if (!near) for (const dy of [-MG.dy, MG.dy]) { const c = [MG.x, y + dy, MG.zAx]; for (const yy of [-MG.w / 2, MG.w / 2]) line3('T5', circle3(add(c, [0, yy, 0]), [0, 1, 0], MG.r, 32), true); }
}
function drawNoseGear() {
  const top = [NG.x - 0.05, 0, NG.zTop], ax = [NG.x, 0, NG.zAx];
  tube('T1b', top, [NG.x - 0.02, 0, -2.75], 0.095, 16);
  tube('T3', [NG.x - 0.02, 0, -2.75], add(ax, [0, 0, 0.02]), 0.065, 14);
  line3('T3', [[NG.x - 0.08, 0, -2.7], [NG.x - 0.35, 0, -3.2], [NG.x - 0.05, 0, -3.6]]); // torque link
  line3('T1b', [[NG.x - 0.03, 0, -2.3], [4.05, 0, -1.8]]); // drag brace into the bay
  line3('T3', [add(ax, [0, -NG.dy - 0.14, 0]), add(ax, [0, NG.dy + 0.14, 0])]); // axle on the strut end
}

// ================================================================= PARTS (teal, interactive)
const TEAL = C.teal;
const prim = { body: [], line: [], pts: [] };
function startPart() { prim.body = []; prim.line = []; prim.pts = []; }
function solidHull(pts3, faceEdges = []) {
  const pts = pts3.map(P); prim.pts.push(...pts);
  prim.body.push(d2(hull(pts), true));
  faceEdges.forEach((e) => prim.line.push(dP(e)));
}
function halfRing(c, u, r) { const sv = norm(cross(u, V)), w = norm(cross(sv, u)); return range(0, 180, 10).map((a) => add(c, add(mul(sv, r * Math.cos(a * deg)), mul(w, r * Math.sin(a * deg))))); }
function pCyl(p0, p1, r, { rings = [], cap = false } = {}) {
  const u = norm(sub(p1, p0));
  const c0 = circle3(p0, u, r), c1 = circle3(p1, u, r);
  const front = dot(u, V) > 0 ? c1 : c0;
  solidHull([...c0, ...c1], [[...front, front[0]]]);
  rings.forEach((t) => prim.line.push(dP(halfRing(lerp3(p0, p1, t), u, r))));
  if (cap) { const cc = dot(u, V) > 0 ? p1 : p0; const q = circle3(cc, u, r * 0.45); prim.line.push(dP([...q, q[0]])); }
}
function pBox(c, sz) {
  const [hx, hy, hz] = sz.map((v) => v / 2);
  const cs = [];
  for (const dx of [-hx, hx]) for (const dy of [-hy, hy]) for (const dz of [-hz, hz]) cs.push(add(c, [dx, dy, dz]));
  const faces = [{ n: [-1, 0, 0], idx: [0, 1, 3, 2] }, { n: [1, 0, 0], idx: [4, 5, 7, 6] }, { n: [0, -1, 0], idx: [0, 1, 5, 4] }, { n: [0, 1, 0], idx: [2, 3, 7, 6] }, { n: [0, 0, -1], idx: [0, 2, 6, 4] }, { n: [0, 0, 1], idx: [1, 3, 7, 5] }];
  solidHull(cs, faces.filter((f) => facing(f.n)).map((f) => [...f.idx.map((i) => cs[i]), cs[f.idx[0]]]));
}
const pLine = (pts3) => { prim.line.push(dP(pts3)); prim.pts.push(...pts3.map(P)); };
// recognisable silhouettes
function pLRU(c, [lx, ly, lz]) { // box + front-panel handle (port face) + connector strip (aft face top)
  pBox(c, [lx, ly, lz]);
  const f = c[1] - ly / 2 - 0.005;
  pLine([[c[0] - lx * 0.3, f, c[2] - lz * 0.25], [c[0] - lx * 0.3, f - 0.05, c[2] - lz * 0.25], [c[0] - lx * 0.3, f - 0.05, c[2] + lz * 0.25], [c[0] - lx * 0.3, f, c[2] + lz * 0.25]]);
  pLine([[c[0] + lx * 0.3, f, c[2] - lz * 0.25], [c[0] + lx * 0.3, f - 0.05, c[2] - lz * 0.25], [c[0] + lx * 0.3, f - 0.05, c[2] + lz * 0.25], [c[0] + lx * 0.3, f, c[2] + lz * 0.25]]);
  pLine([[c[0] - lx * 0.4, f, c[2] + lz * 0.38], [c[0] + lx * 0.4, f, c[2] + lz * 0.38]]); // vent / label strip
  pBox([c[0] + lx / 2 + 0.02, c[1], c[2] + lz * 0.3], [0.04, ly * 0.7, lz * 0.18]); // connector strip
}
function pPump(p0, p1, r) { // cylinder + mounting flange + two port nubs
  pCyl(p0, p1, r, { rings: [0.55], cap: true });
  const u = norm(sub(p1, p0));
  pCyl(lerp3(p0, p1, -0.04), lerp3(p0, p1, 0.08), r * 1.35);
  const [e1, e2] = basis(u);
  for (const e of [e1, mul(e2, -1)]) { const b = add(lerp3(p0, p1, 0.6), mul(e, r * 0.9)); pCyl(b, add(b, mul(e, r * 0.55)), r * 0.28); }
}
function pValve(p0, p1, r) { // duct + butterfly disc + actuator box
  pCyl(p0, p1, r);
  const m = lerp3(p0, p1, 0.5), u = norm(sub(p1, p0));
  const disc = circle3(m, norm(add(u, [0, 0, 0.9])), r * 0.85, 20); prim.line.push(dP([...disc, disc[0]]));
  pBox(add(m, [0, 0, r + 0.09]), [0.16, 0.14, 0.14]);
  pLine([add(m, [0, 0, r]), add(m, [0, 0, r + 0.02])]);
}
function pActuator(p0, p1, r) { // body + piston rod + rod-end eye
  pCyl(p0, lerp3(p0, p1, 0.65), r, { rings: [0.3], cap: true });
  pCyl(lerp3(p0, p1, 0.65), p1, r * 0.45);
  const eye = circle3(p1, [0, 1, 0], r * 0.7, 14); prim.line.push(dP([...eye, eye[0]]));
}
function pWheel(c, r, w, { hub = true } = {}) { // tyre torus look + hub + bolt circle
  const u = [0, 1, 0], a = add(c, [0, -w / 2, 0]), b = add(c, [0, w / 2, 0]);
  const c0 = circle3(a, u, r, 40), c1 = circle3(b, u, r, 40);
  const fc = dot(u, V) > 0 ? b : a, front = dot(u, V) > 0 ? c1 : c0;
  solidHull([...c0, ...c1], [[...front, front[0]]]);
  prim.line.push(dP(halfRing(c, u, r))); prim.line.push(dP(halfRing(c, u, r * 0.93)));
  if (hub) {
    for (const k of [0.62, 0.42, 0.14]) { const cc = circle3(fc, u, r * k, 28); prim.line.push(dP([...cc, cc[0]])); }
    for (let i = 0; i < 8; i++) { const p = circle3(fc, u, r * 0.3, 8)[i]; prim.line.push(dP([p, add(p, [0.012, 0, 0.012])])); }
  }
}
function finishPart(anchor3) { const anchor = P(anchor3); const bb = bbox(prim.pts.length ? prim.pts : [anchor]); return { body: prim.body.join(''), line: prim.line.join(''), anchor, bb }; }

const NY = -NAC.y; // near nacelle centre y
// zone groups the phone list; sys links a part to the system runs lit on hover
const PART_DEFS = [
  { pn: 'GN-34-R020', label: 'Weather radar transceiver', zone: 'nose', sys: 'elec', build() { pLRU([1.65, -0.3, -0.95], [0.38, 0.46, 0.34]); return [1.65, -0.3, -0.95]; } },
  { pn: 'GN-30-E009', label: 'Flight deck windshield', zone: 'nose', sys: 'elec', build() {
    const pane = (a0, a1, x0, x1, rake) => { const fwd = range(a0, a1, 3).map((a) => FS(x0 + rake * (a - a0) / (a1 - a0), a * deg)); const aft = range(a1, a0, -3).map((a) => FS(x1 + rake * (a - a0) / (a1 - a0), a * deg)); const pts = [...fwd, ...aft]; solidHull(pts, [[...pts, pts[0]]]); };
    pane(96, 124, 1.62, 2.3, 0.1); pane(128, 156, 1.72, 2.42, 0.18);
    return FS(2.05, 140 * deg);
  } },
  { pn: 'GN-34-R021', label: 'Pitot probe', zone: 'nose', sys: 'elec', build() { const base = FS(2.75, 200 * deg), out = add(base, [0, -0.24, -0.02]), tip = add(out, [-0.3, 0, 0]); pCyl(base, out, 0.04); pCyl(out, tip, 0.032, { cap: true }); return out; } },
  { pn: 'GN-34-R018', label: 'Air data module', zone: 'nose', sys: 'elec', build() { pLRU([3.3, -1.0, -1.0], [0.36, 0.2, 0.26]); return [3.3, -1.0, -1.0]; } },
  { pn: 'GN-34-R019', label: 'Air data inertial reference unit', zone: 'avionics', sys: 'elec', build() { pLRU([6.45, -0.47, -0.9], [0.72, 0.36, 0.38]); return [6.45, -0.47, -0.9]; } },
  { pn: 'GN-27-R009', label: 'Elevator aileron computer', zone: 'avionics', sys: 'elec', build() { pLRU([7.4, -0.47, -0.9], [0.62, 0.36, 0.36]); return [7.4, -0.47, -0.9]; } },
  { pn: 'GN-32-R017', label: 'Brake control unit', zone: 'avionics', sys: 'elec', build() { pLRU([8.3, -0.47, -0.92], [0.56, 0.36, 0.34]); return [8.3, -0.47, -0.92]; } },
  { pn: 'GN-24-R005', label: 'Transformer rectifier unit', zone: 'avionics', sys: 'elec', build() { pLRU([7.05, -0.47, -1.37], [0.9, 0.36, 0.38]); return [7.05, -0.47, -1.37]; } },
  { pn: 'GN-32-R014', label: 'Nose wheel steering actuator', zone: 'gear', sys: 'hyd', build() {
    pActuator([NG.x - 0.1, -0.42, -1.85], [NG.x - 0.1, -0.1, -1.85], 0.075); pActuator([NG.x - 0.1, 0.42, -1.85], [NG.x - 0.1, 0.1, -1.85], 0.075);
    pBox([NG.x - 0.05, 0, -1.85], [0.26, 0.18, 0.22]); return [NG.x - 0.1, -0.3, -1.85];
  } },
  { pn: 'GN-32-R016', label: 'Nose wheel and tyre', zone: 'gear', build() { pWheel([NG.x, -NG.dy, NG.zAx], NG.r, NG.w); pWheel([NG.x, NG.dy, NG.zAx], NG.r, NG.w, { hub: false }); return [NG.x, -NG.dy - NG.w / 2, NG.zAx]; } },
  { pn: 'GN-21-R001', label: 'Pack flow control valve', zone: 'cabin', sys: 'bleed', build() { pValve([11.0, -0.78, -1.15], [11.5, -0.78, -1.15], 0.14); return [11.25, -0.78, -1.15]; } },
  { pn: 'GN-21-R002', label: 'Air cycle machine', zone: 'cabin', sys: 'bleed', build() {
    pCyl([11.8, -0.82, -1.68], [12.45, -0.82, -1.68], 0.27, { rings: [0.3, 0.62], cap: true }); pCyl([11.6, -0.82, -1.68], [11.8, -0.82, -1.68], 0.18); pCyl([12.45, -0.82, -1.68], [12.62, -0.82, -1.68], 0.2);
    const sp = range(0, 470, 15).map((a) => { const r = 0.12 + 0.2 * a / 470; return [11.58, -0.82 + r * Math.cos(a * deg), -1.68 + r * Math.sin(a * deg)]; }); pLine(sp); // fan-scroll volute
    return [12.1, -0.82, -1.68];
  } },
  { pn: 'GN-28-R010', label: 'Fuel boost pump', zone: 'wing', sys: 'fuel', build() {
    // two pumps inside the centre wing box (tank), on the rear-spar face
    for (const y of [-1.3, -0.62]) pPump([16.08, y, -1.85], [16.08, y, -1.32], 0.14);
    return [16.08, -0.96, -1.55];
  } },
  { pn: 'GN-28-E006', label: 'Fuel quantity probe', zone: 'wing', sys: 'fuel', build() { for (const [y, f] of [[8.2, 0.3], [9.3, 0.45], [10.4, 0.33], [11.0, 0.5]]) { const p = wPt(-1, y, f), q = wPt(-1, y, f, -1); pCyl(add(q, [0, 0, -0.02]), add(p, [0, 0, 0.06]), 0.05, { cap: true }); } return wPt(-1, 9.3, 0.45); } },
  { pn: 'GN-24-R004', label: 'Integrated drive generator', zone: 'engine', sys: 'elec', build() { const c0 = [9.95, NY - 0.5, NAC.z - 0.82], c1 = [10.65, NY - 0.5, NAC.z - 0.82]; pCyl(c0, c1, 0.23, { rings: [0.35, 0.7], cap: true }); pCyl([9.85, NY - 0.5, NAC.z - 0.82], c0, 0.28); return lerp3(c0, c1, 0.5); } },
  { pn: 'GN-29-R011', label: 'Engine-driven hydraulic pump', zone: 'engine', sys: 'hyd', build() { pPump([10, NY - 0.22, NAC.z - 0.98], [9.82, NY - 0.22, NAC.z - 0.98], 0.13); return [9.6, NY - 0.22, NAC.z - 0.98]; } },
  { pn: 'GN-36-R022', label: 'Bleed air valve', zone: 'engine', sys: 'bleed', build() { pValve([11.3, NY, NAC.z + 1.14], [11.3, NY, NAC.z + 1.5], 0.11); return [11.3, NY - 0.1, NAC.z + 1.32]; } },
  { pn: 'GN-32-R015', label: 'Main wheel and tyre', zone: 'gear', build() { pWheel([MG.x, -MG.y - MG.dy, MG.zAx], MG.r, MG.w); return [MG.x, -MG.y - MG.dy - MG.w / 2, MG.zAx + 0.2]; } },
  { pn: 'GN-32-R013', label: 'Carbon brake assembly', zone: 'gear', sys: 'hyd', build() {
    const c = [MG.x, -MG.y + MG.dy, MG.zAx];
    pCyl(add(c, [0, -0.2, 0]), add(c, [0, 0.16, 0]), 0.37, { rings: [0.15, 0.3, 0.45, 0.6, 0.75, 0.9], cap: true }); // disc stack
    pCyl(add(c, [0, -0.24, 0]), add(c, [0, -0.2, 0]), 0.42); // piston housing
    pLine([add(c, [0, -0.22, 0.37]), add(c, [0.55, -0.22, 0.6])]); // torque rod
    return add(c, [0, -0.22, 0]);
  } },
  { pn: 'GN-29-R012', label: 'Power transfer unit', zone: 'gear', sys: 'hyd', build() { pPump([18.65, -0.55, -1.55], [19.3, -0.55, -1.55], 0.14); return [18.97, -0.55, -1.55]; } },
  { pn: 'GN-27-R008', label: 'Spoiler servo control', zone: 'wing', sys: 'hyd', build() { const y = 9.1, a = wPt(-1, y, 0.5, -1), b = wPt(-1, y, 0.7, -1); pActuator(add(a, [0, 0, 0.06]), add(b, [0, 0, 0.1]), 0.07); return lerp3(a, b, 0.4); } },
  { pn: 'GN-27-E005', label: 'Flap position sensor', zone: 'wing', sys: 'elec', build() { const p = wPt(-1, 6.55, 0.7, -1); pBox(add(p, [0, 0, 0.02]), [0.22, 0.18, 0.14]); pCyl(add(p, [0.11, 0, 0.02]), add(p, [0.26, 0, 0.02]), 0.04); return p; } },
  { pn: 'GN-27-R007', label: 'Aileron servo control', zone: 'wing', sys: 'hyd', build() { const y = 14.5, a = wPt(-1, y, 0.55, -1), b = wPt(-1, y, 0.77, -1); pActuator(add(a, [0, 0, 0.04]), add(b, [0, 0, 0.07]), 0.065); return lerp3(a, b, 0.4); } },
  { pn: 'GN-27-R006', label: 'Elevator servo control', zone: 'tail', sys: 'hyd', build() { const y = 1.75, a = tPt(-1, y, 0.48), b = tPt(-1, y, 0.7); pActuator(a, b, 0.075); return lerp3(a, b, 0.4); } },
  { pn: 'GN-49-R023', label: 'APU starter motor', zone: 'tail', sys: 'elec', build() { pPump([34.12, -0.16, 0.66], [34.45, -0.16, 0.66], 0.12); return [34.28, -0.16, 0.66]; } },
  { pn: 'GN-49-R024', label: 'APU fuel control unit', zone: 'tail', sys: 'fuel', build() { pLRU([34.65, -0.38, 0.62], [0.3, 0.12, 0.22]); pCyl([34.55, -0.38, 0.5], [34.55, -0.38, 0.38], 0.03); return [34.65, -0.44, 0.62]; } },
];

// ---------------------------------------------------------------- system runs (schematic routes)
const SYSTEMS = {
  bleed: { label: 'Bleed air', width: 1.4, dash: null, routes: [[[11.3, NY, NAC.z + 1.5], [12.5, NY, wZ(NAC.y) - 0.3], [13.9, -4.0, wZ(4.0) - 0.2], [13.2, -2.2, -1.35], [11.8, -1.0, -1.15], [11.5, -0.78, -1.15]], [[11.0, -0.78, -1.15], [10.8, -0.82, -1.4], [11.6, -0.82, -1.68]]] },
  hyd: { label: 'Hydraulics', width: 0.9, routes: [
    { dash: null, pts: [[9.6, NY - 0.22, NAC.z - 0.98], [10.3, NY, NAC.z + 0.85], [16.6, -NAC.y + 0.3, wZ(5.6) - 0.22], [17.2, -3.0, wZ(3.0) - 0.25], [18.6, -1.0, -1.5], [18.65, -0.55, -1.55]] },
    { dash: '4 2', pts: [[17.0, -NAC.y + 0.2, wZ(5.8) - 0.2], [wXle(9.1) + 0.6 * wC(9.1), -9.1, wZ(9.1) - 0.15], [wXle(14.5) + 0.6 * wC(14.5), -14.5, wZ(14.5) - 0.1]] },
    { dash: '1 2', pts: [[19.3, -0.55, -1.55], [24.0, -0.5, -1.5], [30.0, -0.4, -0.2], [tXle(1.0) + 1.0, -1.0, tZ(1.0)], [tXle(1.75) + 1.68, -1.75, tZ(1.75)]] },
    { dash: '1 2', pts: [[18.65, -0.55, -1.55], [14.0, -0.6, -1.95], [8.0, -0.6, -1.95], [NG.x, -0.3, -1.85]] },
    { dash: '4 2', pts: [[17.2, -2.6, -1.6], [MG.x - 0.15, -MG.y, MG.zTop - 0.6], [MG.x, -MG.y + MG.dy - 0.22, MG.zAx + 0.1]] },
  ] },
  fuel: { label: 'Fuel', width: 0.9, routes: [
    { dash: '6 2', pts: [wPt(-1, 9.3, 0.45, -1), [wXle(6.0) + 0.6 * wC(6.0), -6.0, wZ(6.0) - 0.1], [16.2, -2.4, -1.4], [16.08, -1.3, -1.6]] },
    { dash: '6 2', pts: [[16.0, -0.96, -1.3], [15.2, -2.6, wZ(2.6) - 0.2], [wXle(NAC.y) + 0.1, NY, wZ(NAC.y) - 0.4], [11.0, NY, NAC.z + 1.2], [11, NY, NAC.z]] },
    { dash: '6 2', pts: [[16.1, -0.62, -1.85], [24.0, -0.9, -1.6], [31.0, -0.5, -0.1], [34.68, -0.4, 0.5]] },
  ] },
  elec: { label: 'Electrical', width: 0.8, routes: [
    { dash: '8 2 2 2', pts: [[10.3, NY - 0.5, NAC.z - 0.82], [10, NY + 0.3, NAC.z + 0.9], [13.2, -3.6, wZ(3.6) - 0.15], [12.5, -1.3, -1.2], [9.5, -0.7, -1.3], [7.5, -0.6, -1.37]] },
    { dash: '8 2 2 2', pts: [[7.05, -0.67, -1.2], [6.45, -0.66, -1.0], [7.4, -0.66, -1.0], [8.3, -0.66, -1.0]] },
    { dash: '8 2 2 2', pts: [[6.2, -0.6, -1.3], [4.5, -0.9, -1.0], [3.3, -1.0, -1.0], [2.75, -1.6, -0.6], [1.65, -0.3, -0.95]] },
    { dash: '8 2 2 2', pts: [[9.5, -0.6, -1.3], [20.0, -0.95, -1.15], [31.5, -0.5, 0.0], [34.28, -0.16, 0.6]] },
    { dash: '8 2 2 2', pts: [[13.2, -3.6, wZ(3.6) - 0.15], [wXle(6.55) + 0.7 * wC(6.55), -6.55, wZ(6.55) - 0.15]] },
  ] },
};
function drawSystems(simple) {
  return Object.entries(SYSTEMS).map(([id, sy]) => {
    const routes = sy.routes.map((r) => (Array.isArray(r) ? { dash: sy.dash, pts: r } : r));
    const paths = routes.map((r) => {
      const d = smoothD(r.pts.map(P));
      return el('path', { class: 'cw-sys-base', d, fill: 'none', stroke: TEAL, 'stroke-width': n(sy.width * (simple ? 2 : 1)), 'stroke-opacity': simple ? 0.3 : 0.15, 'stroke-dasharray': r.dash || undefined, 'stroke-linecap': 'round' })
        + el('path', { class: 'cw-sys-flow', d, fill: 'none', stroke: C.tealHi, 'stroke-width': n(sy.width + 0.6), pathLength: 1, 'stroke-linecap': 'round' });
    }).join('');
    return el('g', { class: 'cw-sys', 'data-sys': id, 'aria-hidden': 'true' }, paths);
  }).join('');
}

// ================================================================= CALLOUTS (nearest side, elbow leaders)
const LEADER_MAX = 300, LEADER_TARGET = 270; // hard cap / soft target (units at 1600 wide)
const FAIL = (m) => { if (process.env.CW_LAX) console.warn(m); else throw new Error(m); };
const NAME_FS = 13.5, CHAR_W = 8.1, TAG_W = 30, WRAP = 18;
function wrap(s, max) { const words = s.split(' '), lines = []; let cur = ''; for (const w of words) { if ((cur + ' ' + w).trim().length > max && cur) { lines.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); } if (cur) lines.push(cur); return lines; }
const labelW = (label) => TAG_W + 8 + Math.max(...wrap(label, WRAP).map((t) => t.length)) * CHAR_W;
function hungarian(a) {
  const nR = a.length, m = a[0].length, INF = 1e18;
  const u = new Array(nR + 1).fill(0), v = new Array(m + 1).fill(0), p = new Array(m + 1).fill(0), way = new Array(m + 1).fill(0);
  for (let i = 1; i <= nR; i++) {
    p[0] = i; let j0 = 0; const minv = new Array(m + 1).fill(INF), used = new Array(m + 1).fill(false);
    do {
      used[j0] = true; const i0 = p[j0]; let delta = INF, j1 = 0;
      for (let j = 1; j <= m; j++) if (!used[j]) { const cur = a[i0 - 1][j - 1] - u[i0] - v[j]; if (cur < minv[j]) { minv[j] = cur; way[j] = j0; } if (minv[j] < delta) { delta = minv[j]; j1 = j; } }
      for (let j = 0; j <= m; j++) if (used[j]) { u[p[j]] += delta; v[j] -= delta; } else minv[j] -= delta;
      j0 = j1;
    } while (p[j0] !== 0);
    do { const j1 = way[j0]; p[j0] = p[j1]; j0 = j1; } while (j0);
  }
  const ans = new Array(nR); for (let j = 1; j <= m; j++) if (p[j]) ans[p[j] - 1] = j - 1; return ans;
}
function inPoly(pt, poly) { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) c = !c; } return c; }
function rectHitsPoly(r, poly) {
  const cs = [[r.x0, r.y0], [r.x1, r.y0], [r.x1, r.y1], [r.x0, r.y1]];
  if (cs.some((c) => inPoly(c, poly))) return true;
  if (poly.some(([x, y]) => x >= r.x0 && x <= r.x1 && y >= r.y0 && y <= r.y1)) return true;
  for (let i = 0; i < poly.length; i++) { const a = poly[i], b = poly[(i + 1) % poly.length]; for (let k = 0; k < 4; k++) if (segX(a, b, cs[k], cs[(k + 1) % 4])) return true; }
  return false;
}
function segHitsRect(a, b, r) {
  const inside = (p) => p[0] > r.x0 && p[0] < r.x1 && p[1] > r.y0 && p[1] < r.y1;
  if (inside(a) || inside(b)) return true;
  const cs = [[r.x0, r.y0], [r.x1, r.y0], [r.x1, r.y1], [r.x0, r.y1]];
  for (let k = 0; k < 4; k++) if (segX(a, b, cs[k], cs[(k + 1) % 4])) return true;
  return false;
}
// Slots on each side carry a fixed elbow point; the leader is anchor → elbow (diagonal) → tag (short straight run).
// All diagonals end on fixed points, so the minimum-total-length matching has no crossing diagonals, and the short
// runs live in each side's own margin strip, outside every diagonal.
function layoutCallouts(parts, { W, H, obstacles, reserved, side }) {
  const slots = [];
  const okRect = (r) => !obstacles.some((poly) => rectHitsPoly({ x0: r.x0 - 6, y0: r.y0 - 5, x1: r.x1 + 6, y1: r.y1 + 5 }, poly)) && !reserved.some((q) => !(r.x1 < q.x0 || r.x0 > q.x1 || r.y1 < q.y0 || r.y0 > q.y1));
  const colW = side.colW;
  // Every leader is one angled segment plus one short horizontal run into the tag. A slot is a tag position plus
  // the side the run arrives from: attach 'L' (tag at the left end of its label, elbow 28 units further left) or
  // attach 'R' (tag at the right end, label text right-aligned before it, elbow to the right).
  const add = (kind, attach, tx, y) => {
    const elbow = attach === 'L' ? [tx - 28, y + 11.5] : [tx + TAG_W + 28, y + 11.5];
    const end = attach === 'L' ? [tx, y + 11.5] : [tx + TAG_W, y + 11.5];
    const r = attach === 'L' ? { x0: tx, y0: y, x1: tx + colW, y1: y + 40 } : { x0: tx + TAG_W - colW, y0: y, x1: tx + TAG_W, y1: y + 40 };
    slots.push({ kind, attach, r, tag: [tx, y + 2], elbow, end });
  };
  for (let y = side.top; y + 40 <= side.leftBottom; y += 44) add('L', 'R', side.left + colW - TAG_W, y); // left column
  for (let y = side.top; y + 40 <= side.rightBottom; y += 44) add('R', 'L', W - side.right - colW, y); // right column
  const yb = H - side.bottom - 40;
  for (let x = side.bottomLeft; x + 60 <= side.bottomRight; x += 30) { add('B', 'L', x, yb); add('B', 'R', x, yb); }
  if (side.topRow != null) for (let x = side.topLeft; x + 60 <= side.topRight; x += 30) { add('T', 'L', x, side.topRow); add('T', 'R', x, side.topRow); }
  for (let y = side.top - 140; y + 40 <= H - side.bottom - 50; y += 22) {
    for (let x = side.left + colW + 60; x + 60 <= W - side.right - colW - 60; x += 30) { add('I', 'L', x, y); add('I', 'R', x, y); }
  }
  const lenOf = (p, s) => Math.hypot(s.elbow[0] - p.anchor[0], s.elbow[1] - p.anchor[1]) + Math.hypot(s.end[0] - s.elbow[0], s.end[1] - s.elbow[1]);
  const rectOf = (p, s) => { const w = labelW(p.label), h = wrap(p.label, WRAP).length > 1 ? 38 : 22; return s.attach === 'R' ? { x0: s.r.x1 - w, y0: s.r.y0, x1: s.r.x1, y1: s.r.y0 + h } : { x0: s.r.x0, y0: s.r.y0, x1: s.r.x0 + w, y1: s.r.y0 + h }; };
  const segsOf = (p, s) => [[p.anchor, s.elbow], [s.elbow, s.end]];
  // the diagonal must head towards its slot (a leader never doubles back over its own label)
  const valid = (p, s) => {
    const r = rectOf(p, s);
    if (segHitsRect(p.anchor, s.elbow, { x0: r.x0 - 3, y0: r.y0 - 3, x1: r.x1 + 3, y1: r.y1 + 3 })) return false; // never over its own label
    const dx = Math.abs(p.anchor[0] - s.elbow[0]), dy = Math.abs(p.anchor[1] - s.elbow[1]);
    if (s.attach === 'L' && p.anchor[0] > s.elbow[0] + 4 && dy < 50) return false; // the angled run must not double back
    if (s.attach === 'R' && p.anchor[0] < s.elbow[0] - 4 && dy < 50) return false;
    return dx + dy > 20;
  };
  // prefer leaders that leave the airframe outline once (not across it again and again)
  const outline = obstacles[0];
  const crossings = (a, b) => { let c = 0; for (let i = 0; i < outline.length; i += 2) { const q = outline[(i + 2) % outline.length]; if (segX(a, b, outline[i], q)) c++; } return c; };
  const cost = parts.map((p) => slots.map((s) => { const L = lenOf(p, s); if (L > LEADER_MAX + 60) return 1e7; if (!valid(p, s) || !okRect(rectOf(p, s))) return 1e7; return L + 45 * Math.max(0, crossings(p.anchor, s.elbow) - 1); }));
  const shr = (r) => ({ x0: r.x0 - 2, y0: r.y0 - 2, x1: r.x1 + 2, y1: r.y1 + 2 });
  // Interior U and D variants share a cell: never give one cell to two parts.
  const cellOf = (j) => `${slots[j].tag[0]},${slots[j].tag[1]}`;
  // geometry cache per (part, slot)
  const G = parts.map((p) => slots.map((sl) => { const r = rectOf(p, sl); return { r, rg: shr(r), s: segsOf(p, sl) }; }));
  const badPair = (i, si, k, sk) => {
    if (si === sk || cellOf(si) === cellOf(sk)) return true;
    const A = G[i][si], Bq = G[k][sk], ra = A.r, rb = Bq.r;
    const ki = slots[si].kind, kk = slots[sk].kind; // columns keep the parts' screen order (leaders fan out)
    if (ki === kk && (ki === 'L' || ki === 'R') && (slots[si].r.y0 - slots[sk].r.y0) * (parts[i].anchor[1] - parts[k].anchor[1]) < 0) return true;
    if (!(ra.x1 + 10 < rb.x0 || rb.x1 + 10 < ra.x0 || ra.y1 + 4 < rb.y0 || rb.y1 + 4 < ra.y0)) return true;
    for (const [p1, p2] of A.s) { if (segHitsRect(p1, p2, Bq.rg)) return true; for (const [q1, q2] of Bq.s) if (segX(p1, p2, q1, q2)) return true; }
    for (const [q1, q2] of Bq.s) if (segHitsRect(q1, q2, A.rg)) return true;
    return false;
  };
  // simulated annealing over the assignment (deterministic PRNG, several seeds; the strict best wins):
  // energy = Wc per conflict + leader length + 150 × overrun beyond the cap
  const nP = parts.length;
  const cand = parts.map((_, i) => slots.map((_, j) => j).filter((j) => cost[i][j] < 1e6));
  const own = (i, j) => { const L = lenOf(parts[i], slots[j]); return L + (L > LEADER_TARGET - 10 ? 40 * (L - LEADER_TARGET + 10) : 0) + (L > LEADER_MAX - 5 ? 400 * (L - LEADER_MAX + 5) : 0); };
  let best = null;
  for (const [seed0, Wc] of [[2024, 2e4], [31337, 1e4], [555, 1e4], [777, 2e4], [8086, 1e4], [12345, 1e4], [4242, 1e4], [555, 1e4], [9001, 2e4], [1234, 1e4], [42, 2e4]]) {
    let seed = seed0; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
    const asg = hungarian(cost);
    const pairE = (i, j, k, jk) => (badPair(i, j, k, jk) ? Wc : 0);
    const partE = (i, j) => { let e = own(i, j); for (let k = 0; k < nP; k++) if (k !== i) e += pairE(i, j, k, asg[k]); return e; };
    let E = 0; for (let i = 0; i < nP; i++) { E += own(i, asg[i]); for (let k = i + 1; k < nP; k++) E += pairE(i, asg[i], k, asg[k]); }
    let run = { E, asg: asg.slice() };
    const STEPS = 140000;
    for (let t = 0; t < STEPS; t++) {
      const T = 600 * Math.pow(0.002, t / STEPS);
      const i = Math.floor(rnd() * nP);
      if (rnd() < 0.75) {
        const j = cand[i][Math.floor(rnd() * cand[i].length)];
        if (asg.indexOf(j) >= 0) continue;
        const before = partE(i, asg[i]), old = asg[i]; asg[i] = j; const dE = partE(i, j) - before;
        if (dE <= 0 || rnd() < Math.exp(-dE / T)) E += dE; else asg[i] = old;
      } else {
        const k = Math.floor(rnd() * nP); if (k === i || cost[i][asg[k]] >= 1e6 || cost[k][asg[i]] >= 1e6) continue;
        const before = partE(i, asg[i]) + partE(k, asg[k]) - pairE(i, asg[i], k, asg[k]);
        [asg[i], asg[k]] = [asg[k], asg[i]];
        const dE = partE(i, asg[i]) + partE(k, asg[k]) - pairE(i, asg[i], k, asg[k]) - before;
        if (dE <= 0 || rnd() < Math.exp(-dE / T)) E += dE; else [asg[i], asg[k]] = [asg[k], asg[i]];
      }
      if (E < run.E) run = { E, asg: asg.slice() };
    }
    // repair: move any part still in conflict to its cheapest conflict-free slot (few passes)
    const A = run.asg;
    const confl = (i, j) => { for (let k = 0; k < nP; k++) if (k !== i && (A[k] === j || badPair(i, j, k, A[k]))) return true; return false; };
    for (let pass = 0; pass < 4; pass++) {
      let moved = false;
      for (let i = 0; i < nP; i++) {
        if (!confl(i, A[i])) continue;
        const opts2 = cand[i].filter((j) => !confl(i, j)).sort((x, y) => own(i, x) - own(i, y));
        if (opts2.length) { A[i] = opts2[0]; moved = true; }
      }
      // also try shortening any over-cap leader without creating a conflict
      for (let i = 0; i < nP; i++) {
        if (lenOf(parts[i], slots[A[i]]) <= LEADER_TARGET) continue;
        const better = cand[i].filter((j) => own(i, j) < own(i, A[i]) && !confl(i, j)).sort((x, y) => own(i, x) - own(i, y));
        if (better.length) { A[i] = better[0]; moved = true; }
      }
      if (!moved) break;
    }
    let nc = 0, over = 0, len = 0;
    for (let i = 0; i < nP; i++) { const L = lenOf(parts[i], slots[run.asg[i]]); len += L; over += Math.max(0, L - LEADER_TARGET) + 50 * Math.max(0, L - LEADER_MAX); for (let k = i + 1; k < nP; k++) if (badPair(i, run.asg[i], k, run.asg[k])) nc++; }
    const score = nc * 1e7 + over * 100 + len;
    if (process.env.CW_DEBUG) console.warn('seed', seed0, 'conflicts', nc, 'overrun', Math.round(over), 'length', Math.round(len));
    if (!best || score < best.score) best = { score, asg: run.asg };
    if (!nc && over < 150) break;
  }
  const pick = best.asg;
  parts.forEach((p, i) => { p.slot = slots[pick[i]]; p.rect = rectOf(p, p.slot); p.leader = [p.anchor, p.slot.elbow, p.slot.end]; p.leaderLen = lenOf(p, p.slot); });
  // number by sweeping the labels anticlockwise around the sheet centre, starting top left
  const cx = W / 2, cy = H / 2;
  const ang = (p) => { const r = p.rect; const a = Math.atan2((r.y0 + r.y1) / 2 - cy, ((r.x0 + r.x1) / 2 - cx) * 0.6) / deg; return (-120 - a + 720) % 360; };
  const ordered = parts.slice().sort((a, b) => ang(a) - ang(b));
  ordered.forEach((p, i) => { p.num = i + 1; });
  // verify: no crossings (any leader segment pair), no leader through a label, length cap
  const segL = (p) => [[p.leader[0], p.leader[1]], [p.leader[1], p.leader[2]]];
  for (let i = 0; i < ordered.length; i++) for (let j = i + 1; j < ordered.length; j++) for (const [a, b] of segL(ordered[i])) for (const [c, d] of segL(ordered[j])) if (segX(a, b, c, d)) FAIL(`leader crossing: ${ordered[i].pn} × ${ordered[j].pn}`);
  for (const p of ordered) for (const q of ordered) if (p !== q) for (const [a, b] of segL(p)) if (segHitsRect(a, b, { x0: q.rect.x0 + 1, y0: q.rect.y0 + 1, x1: q.rect.x1 - 1, y1: q.rect.y1 - 1 })) FAIL(`leader ${p.pn} passes label ${q.pn}`);
  const long = ordered.filter((p) => p.leaderLen > LEADER_MAX);
  if (long.length) (process.env.CW_LAX ? console.warn : (m) => { throw new Error(m); })(`leaders over ${LEADER_MAX}: ${long.map((p) => `${p.pn} ${Math.round(p.leaderLen)}`).join(', ')}`);
  return ordered;
}

// ================================================================= COMPOSE
const DEFS = el('defs', {},
  el('filter', { id: 'cw-glow', x: '-40%', y: '-40%', width: '180%', height: '180%' }, el('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: 2.4, result: 'b' }), el('feMerge', {}, el('feMergeNode', { in: 'b' }), el('feMergeNode', { in: 'SourceGraphic' }))),
  el('filter', { id: 'cw-glow-hi', x: '-50%', y: '-50%', width: '200%', height: '200%' }, el('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: 4.5, result: 'b' }), el('feMerge', {}, el('feMergeNode', { in: 'b' }), el('feMergeNode', { in: 'b' }), el('feMergeNode', { in: 'SourceGraphic' }))),
  el('pattern', { id: 'cw-grid', width: 24, height: 24, patternUnits: 'userSpaceOnUse' }, el('path', { d: 'M24 0H0V24', fill: 'none', stroke: C.teal, 'stroke-opacity': 0.035, 'stroke-width': 0.6 })),
  el('pattern', { id: 'cw-grid-maj', width: 120, height: 120, patternUnits: 'userSpaceOnUse' }, el('path', { d: 'M120 0H0V120', fill: 'none', stroke: C.teal, 'stroke-opacity': 0.06, 'stroke-width': 0.7 })),
  el('pattern', { id: 'cw-hatch', width: 3, height: 3, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, el('path', { d: 'M1.5 0V3', stroke: C.copper, 'stroke-width': 0.4, 'stroke-opacity': 0.5 })),
  el('radialGradient', { id: 'cw-vig', cx: '50%', cy: '52%', r: '70%' }, el('stop', { offset: '55%', 'stop-color': '#060E17', 'stop-opacity': 0 }), el('stop', { offset: '100%', 'stop-color': '#060E17', 'stop-opacity': 0.9 })),
  el('radialGradient', { id: 'cw-innerglow', cx: '50%', cy: '55%', r: '60%' }, el('stop', { offset: '0%', 'stop-color': C.teal, 'stop-opacity': 0.09 }), el('stop', { offset: '100%', 'stop-color': C.teal, 'stop-opacity': 0 })),
);

function fit(box) {
  S = 1; OX = 0; OY = 0;
  const pts = [], deps = [];
  for (let x = 0; x <= FL; x += 0.5) for (let a = 0; a < 360; a += 30) { pts.push(P(FS(x, a * deg))); deps.push(dep(FS(x, a * deg))); }
  for (const s of [-1, 1]) { for (const p of [wPt(s, WG.yt, 0), wPt(s, WG.yt, 1), [wXle(WG.yt) + 1.3, s * (WG.yt + 0.4), wZ(WG.yt) + 2.1], tPt(s, TP.yt, 0), [MG.x, s * (MG.y + 0.7), GROUND]]) { pts.push(P(p)); deps.push(dep(p)); } }
  pts.push(P(fPt(1, 0)), P(fPt(1, 1)), P([NG.x, 0, GROUND]));
  DMIN = Math.min(...deps); DMAX = Math.max(...deps);
  const bb = bbox(pts);
  S = Math.min((box.x1 - box.x0) / (bb.x1 - bb.x0), (box.y1 - box.y0) / (bb.y1 - bb.y0));
  OX = box.x0 - S * bb.x0 + ((box.x1 - box.x0) - S * (bb.x1 - bb.x0)) / 2;
  OY = box.y0 - S * bb.y0 + ((box.y1 - box.y0) - S * (bb.y1 - bb.y0)) / 2;
  return { x0: OX + S * bb.x0, y0: OY + S * bb.y0, x1: OX + S * bb.x1, y1: OY + S * bb.y1 };
}

function obstaclePolys() {
  const polys = [OBST.fus];
  for (const s of [-1]) { // the ghosted far side may sit under a label (labels carry a dark backing)
    polys.push(wingOutline(s, WG.y0, WG.yt).map(P));
    polys.push(hull([P(wPt(s, WG.yt, 0)), P(wPt(s, WG.yt, 1)), P([wXle(WG.yt) + 1.25, s * (WG.yt + 0.38), wZ(WG.yt) + 2.05]), P([wXle(WG.yt) + 1.95, s * (WG.yt + 0.42), wZ(WG.yt) + 2.1])]));
    const ts = range(TP.y0, TP.yt, 0.5); polys.push([...ts.map((y) => P(tPt(s, y, 0))), ...ts.slice().reverse().map((y) => P(tPt(s, y, 1)))]);
    const nac = []; for (const [x, r] of NAC.prof) for (let a = 0; a < 360; a += 20) nac.push(P(nacPt(s, x, r, a * deg))); polys.push(hull(nac));
    const g = []; for (const dy of [-MG.dy - MG.w, MG.dy + MG.w]) for (let a = 0; a < 360; a += 30) g.push(P([MG.x + MG.r * Math.cos(a * deg), s * MG.y + dy, MG.zAx + MG.r * Math.sin(a * deg)])); g.push(P([MG.x, s * MG.y, MG.zTop])); polys.push(hull(g));
  }
  const fin = range(0, 1, 0.1); polys.push([...fin.map((e) => P(fPt(e, 0))), ...fin.slice().reverse().map((e) => P(fPt(e, 1))), P([FIN.xr, 0, 0])]);
  const ng = []; for (const dy of [-NG.dy - NG.w, NG.dy + NG.w]) for (let a = 0; a < 360; a += 30) ng.push(P([NG.x + NG.r * Math.cos(a * deg), dy, NG.zAx + NG.r * Math.sin(a * deg)])); ng.push(P([NG.x, 0, NG.zTop])); polys.push(hull(ng));
  return polys;
}

function partGroup(p, simple) {
  const tf = simple ? `translate(${n(p.anchor[0])} ${n(p.anchor[1])}) scale(1.8) translate(${n(-p.anchor[0])} ${n(-p.anchor[1])})` : undefined;
  const pad = 7;
  return el('g', { 'data-pn': p.pn, 'data-n': p.num, 'data-ax': n(p.anchor[0]), 'data-ay': n(p.anchor[1]), 'data-label': p.label, 'data-zone': p.zone, 'data-sys': p.sys || '', class: 'cw-part' },
    simple ? '' : el('rect', { class: 'cw-hit', x: p.bb.x0 - pad, y: p.bb.y0 - pad, width: p.bb.x1 - p.bb.x0 + 2 * pad, height: p.bb.y1 - p.bb.y0 + 2 * pad, rx: 4, fill: 'transparent' }),
    el('g', { transform: tf },
      el('path', { class: 'cw-body', d: p.body, fill: TEAL, 'fill-opacity': 0.18, stroke: TEAL, 'stroke-width': simple ? 1.3 : 1.25, 'stroke-linejoin': 'round' }),
      p.line ? el('path', { class: 'cw-detail', d: p.line, fill: 'none', stroke: TEAL, 'stroke-width': simple ? 0.8 : 0.75, 'stroke-opacity': 0.9, 'stroke-linecap': 'round' }) : ''));
}
function focusTarget(p) {
  const pad = 9, { x0, y0, x1, y1 } = p.bb;
  const X0 = x0 - pad, Y0 = y0 - pad, X1 = x1 + pad, Y1 = y1 + pad, k = Math.min(8, (X1 - X0) / 3, (Y1 - Y0) / 3);
  const d = `M${n(X0)} ${n(Y0 + k)}V${n(Y0)}H${n(X0 + k)}M${n(X1 - k)} ${n(Y0)}H${n(X1)}V${n(Y0 + k)}M${n(X1)} ${n(Y1 - k)}V${n(Y1)}H${n(X1 - k)}M${n(X0 + k)} ${n(Y1)}H${n(X0)}V${n(Y1 - k)}`;
  return el('g', { class: 'cw-focus', 'data-pn': p.pn, 'data-n': p.num, tabindex: 0, role: 'link', 'aria-label': `${String(p.num).padStart(2, '0')} · ${p.label}` },
    el('rect', { x: X0, y: Y0, width: X1 - X0, height: Y1 - Y0, fill: 'transparent', 'pointer-events': 'none' }),
    el('path', { class: 'cw-bracket', d, fill: 'none', stroke: C.tealHi, 'stroke-width': 1.5, opacity: 0 }));
}
function callout(p) {
  const num = String(p.num).padStart(2, '0'), s = p.slot, lines = wrap(p.label, WRAP), L = s.attach === 'R';
  const tx = L ? s.tag[0] - 8 : s.tag[0] + TAG_W + 8, ty = s.r.y0 + 16;
  const d = d2(p.leader);
  return el('g', { class: 'cw-callout', 'data-pn': p.pn, 'aria-hidden': 'true' },
    el('path', { class: 'cw-leader-halo', d, stroke: C.midnight, 'stroke-width': 3.2, 'stroke-opacity': 0.85, fill: 'none', 'stroke-linejoin': 'round' }),
    el('path', { class: 'cw-leader', d, stroke: C.titanium, 'stroke-width': 0.9, 'stroke-opacity': 0.8, fill: 'none', 'stroke-linejoin': 'round' }),
    el('circle', { class: 'cw-dot', cx: p.anchor[0], cy: p.anchor[1], r: 2.8, fill: C.tealHi, stroke: C.midnight, 'stroke-width': 1.2 }),
    el('rect', { class: 'cw-back', x: p.rect.x0 - 3, y: p.rect.y0 - 1, width: p.rect.x1 - p.rect.x0 + 6, height: p.rect.y1 - p.rect.y0 + 3, rx: 3, fill: C.midnight, 'fill-opacity': 0.82 }),
    el('rect', { class: 'cw-hitlabel', x: p.rect.x0 - 4, y: p.rect.y0 - 2, width: p.rect.x1 - p.rect.x0 + 8, height: p.rect.y1 - p.rect.y0 + 4, fill: 'transparent' }),
    el('rect', { class: 'cw-tag', x: s.tag[0], y: s.tag[1], width: TAG_W, height: 19, rx: 3, fill: C.midnight, stroke: TEAL, 'stroke-width': 1 }),
    el('text', { class: 'cw-num', x: s.tag[0] + TAG_W / 2, y: s.tag[1] + 14, 'text-anchor': 'middle', 'font-family': FONT_MONO, 'font-size': 13, 'font-weight': 600, fill: C.ice }, num),
    el('text', { class: 'cw-name', x: tx, y: ty, 'text-anchor': L ? 'end' : 'start', 'font-family': FONT_MONO, 'font-size': NAME_FS, 'font-weight': 500, 'letter-spacing': '0.02em', fill: C.titanium },
      ...lines.map((t, i) => el('tspan', { x: tx, dy: i ? 16 : 0 }, esc(t)))));
}

const DIM_OBS = [];
function dimensions() {
  const labels = [];
  DIM_OBS.length = 0;
  const arrow = (p, dir) => { const [dx, dy] = dir, L = 8, W = 2.8; const px = -dy, py = dx; return d2([[p[0] + dx * L + px * W, p[1] + dy * L + py * W], p, [p[0] + dx * L - px * W, p[1] + dy * L - py * W]]); };
  const dimLine = (a3, b3, label, t = 0.5) => {
    const a = P(a3), b = P(b3), L = Math.hypot(b[0] - a[0], b[1] - a[1]), dir = [(b[0] - a[0]) / L, (b[1] - a[1]) / L];
    put('DIM', d2([a, b])); put('DIM', arrow(a, dir)); put('DIM', arrow(b, [-dir[0], -dir[1]]));
    const nx = -dir[1] * 6, ny = dir[0] * 6;
    DIM_OBS.push([[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny], [b[0] - nx, b[1] - ny], [a[0] - nx, a[1] - ny]]);
    const m = [lerp(a[0], b[0], t), lerp(a[1], b[1], t)];
    { const hw = label.length * 4.3 + 10, ux = dir[0], uy = dir[1]; DIM_OBS.push([[m[0] - ux * hw - uy * 12, m[1] - uy * hw + ux * 12], [m[0] + ux * hw - uy * 12, m[1] + uy * hw + ux * 12], [m[0] + ux * hw + uy * 12, m[1] + uy * hw - ux * 12], [m[0] - ux * hw + uy * 12, m[1] - uy * hw - ux * 12]]); }
    void m; labels.push({ a, b, dir, label, t });
  };
  const m = (v) => (v * MODEL_SCALE).toFixed(1);
  // overall length: parallel to the fuselage, offset above the crown (only ghosted far-side lines lie behind it),
  // with extension lines rising from the nose tip and the tail cone
  const lz = RZ + 1.35, ly = 1.2;
  line3('CONS', [[0, 0, FS(0.001, 0)[2]], [0, ly, lz + 0.3]]); line3('CONS', [[FL, 0, FS(FL - 0.01, 0)[2]], [FL, ly, lz + 0.3]]);
  dimLine([0, ly, lz], [FL, ly, lz], `LENGTH ≈ ${Math.round(FL * MODEL_SCALE)} m`, 0.3);
  // near semi-span, along (and aft of) the near wing's trailing edge, from the centreline plane to the tip
  const ys = WG.yt + 0.42, zs = wZ(WG.yt) - 0.1;
  const xsOf = (y) => wXle(Math.max(y, WG.y0)) + wC(Math.max(y, WG.y0)) + 1.0;
  line3('CONS', [[wXle(WG.yt) + wC(WG.yt) + 0.1, -ys, zs], [xsOf(WG.yt) + 0.5, -ys, zs]]);
  dimLine([xsOf(WG.yt), -ys, zs], [xsOf(WG.yt), -RY, zs], `½ SPAN ≈ ${Math.round(ys * MODEL_SCALE)} m`, 0.45);
  // height to the fin tip
  const tipZ = fPt(1, 0)[2], xh = FL + 0.9;
  line3('CONS', [[fPt(1, 1)[0], 0, tipZ], [xh + 0.4, 0, tipZ]]); line3('CONS', [[FL, 0, GROUND], [xh + 0.4, 0, GROUND]]);
  dimLine([xh, 0, GROUND], [xh, 0, tipZ], `≈ ${Math.round((tipZ - GROUND) * MODEL_SCALE)} m`, 0.5);
  return { lines: take('DIM'), specs: labels };
}
function dimLabels(specs, avoid) {
  return specs.map(({ a, b, dir, label, t }) => {
    let ang = Math.atan2(dir[1], dir[0]) / deg; if (ang > 90) ang -= 180; if (ang < -90) ang += 180;
    const hw = label.length * 4.3 + 8;
    const boxAt = (tt) => { const m = [lerp(a[0], b[0], tt), lerp(a[1], b[1], tt)]; const ex = Math.abs(dir[0]) * hw + Math.abs(dir[1]) * 10, ey = Math.abs(dir[1]) * hw + Math.abs(dir[0]) * 10; return { m, r: { x0: m[0] - ex, y0: m[1] - ey, x1: m[0] + ex, y1: m[1] + ey } }; };
    const free = (r) => !avoid.some((q) => !(r.x1 < q.x0 || r.x0 > q.x1 || r.y1 < q.y0 || r.y0 > q.y1));
    let pick = boxAt(t);
    for (let d = 0; d <= 0.14 && !free(pick.r); d += 0.01) { for (const tt of [t + d, t - d]) { if (tt < 0.06 || tt > 0.94) continue; const c = boxAt(tt); if (free(c.r)) { pick = c; break; } } }
    return el('g', { transform: `translate(${n(pick.m[0])} ${n(pick.m[1])}) rotate(${n(ang)})` },
      el('rect', { x: -label.length * 4.3 - 7, y: -9, width: label.length * 8.6 + 14, height: 17, rx: 3, fill: C.midnight, stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.6 }),
      el('text', { x: 0, y: 4.5, 'text-anchor': 'middle', 'font-family': FONT_MONO, 'font-size': 12.5, fill: C.ice, 'letter-spacing': '.04em' }, label));
  }).join('');
}
function titleBlock(x, y) {
  const w = 600, h = 92;
  const t = 'GROUNDED NO MORE · GENERIC NARROWBODY · SCHEMATIC — NOT ENGINEERING DATA · NTS';
  const span = 2 * (WG.yt + 0.42) * MODEL_SCALE, height = (fPt(1, 0)[2] - GROUND) * MODEL_SCALE;
  const spec = `ILLUSTRATIVE PROPORTIONS · ≈ ${Math.round(FL * MODEL_SCALE)} m CLASS · SPAN ≈ ${Math.round(span)} m · 2 × UNDERWING ENGINES`;
  const mono = (tx, ty, s, size = 10.5, fill = C.titanium) => el('text', { x: tx, y: ty, 'font-family': FONT_MONO, 'font-size': size, fill, 'letter-spacing': '.06em' }, esc(s));
  return el('g', { class: 'cw-titleblock', transform: `translate(${x} ${y})` },
    el('rect', { width: w, height: h, fill: C.midnight, 'fill-opacity': 0.94, stroke: C.titanium, 'stroke-opacity': 0.45, 'stroke-width': 1 }),
    el('line', { x1: 0, y1: 40, x2: w, y2: 40, stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.75 }),
    el('line', { x1: 0, y1: 64, x2: w, y2: 64, stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.75 }),
    el('line', { x1: 418, y1: 0, x2: 418, y2: 40, stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.75 }),
    el('rect', { x: 14, y: 14, width: 4, height: 14, fill: C.copper }),
    el('text', { x: 26, y: 27, 'font-family': FONT_DISPLAY, 'font-size': 17, 'font-weight': 600, fill: C.ice, 'letter-spacing': '.14em' }, 'SYSTEMS CUTAWAY'),
    mono(432, 17, 'SHEET 1 / 1'), mono(432, 32, 'VIEW · ¾ AXONOMETRIC'), mono(14, 56, spec),
    el('text', { class: 'cw-tb-line', x: 14, y: 82, 'font-family': FONT_MONO, 'font-size': 10.5, fill: C.ice, 'letter-spacing': '.03em' }, esc(t)));
}
function legend(x, y) {
  const item = (dx, sw, label) => el('g', { transform: `translate(${dx} 0)` }, sw, el('text', { x: 26, y: 4, 'font-family': FONT_MONO, 'font-size': 11, fill: C.titanium }, label));
  return el('g', { class: 'cw-legend', transform: `translate(${x} ${y})` },
    item(0, el('rect', { x: 0, y: -5, width: 18, height: 9, rx: 2, fill: TEAL, 'fill-opacity': 0.18, stroke: TEAL }), 'Modelled part'),
    item(140, el('line', { x1: 0, y1: 0, x2: 18, y2: 0, stroke: TEAL, 'stroke-opacity': 0.6, 'stroke-dasharray': '4 2' }), 'System run'),
    item(270, el('rect', { x: 0, y: -5, width: 18, height: 9, fill: 'url(#cw-hatch)', stroke: C.copper, 'stroke-width': 1.2 }), 'Cut skin'),
    item(380, el('line', { x1: 0, y1: 0, x2: 18, y2: 0, stroke: T1C, 'stroke-opacity': 0.6 }), 'Airframe'));
}
function triad(x, y) {
  const o = raw([0, 0, 0]);
  const ax = (v, label) => { const p = raw(v); const dx = p[0] - o[0], dy = p[1] - o[1], L = Math.hypot(dx, dy), ux = dx / L * 30, uy = dy / L * 30; return el('g', {}, el('line', { x1: x, y1: y, x2: x + ux, y2: y + uy, stroke: C.titanium, 'stroke-opacity': 0.7, 'stroke-width': 0.9 }), el('text', { x: x + ux * 1.5, y: y + uy * 1.5 + 3.5, 'text-anchor': 'middle', 'font-family': FONT_MONO, 'font-size': 10, fill: C.titanium, 'letter-spacing': '.08em' }, label)); };
  return el('g', { class: 'cw-triad' }, ax([-1, 0, 0], 'FWD'), ax([0, 1, 0], 'STBD'), ax([0, 0, 1], 'UP'), el('circle', { cx: x, cy: y, r: 2, fill: C.titanium }));
}

// phone: number dots placed near their parts, pushed apart (min distance), short leaders
function numberDots(parts, W, H) {
  const R = 19, MIN = 2 * R + 2;
  const dots = parts.map((p) => ({ p, x: p.anchor[0] + 18, y: p.anchor[1] - 22 }));
  for (let it = 0; it < 400; it++) {
    for (let i = 0; i < dots.length; i++) for (let j = i + 1; j < dots.length; j++) {
      const a = dots[i], b = dots[j]; let dx = b.x - a.x, dy = b.y - a.y; const d = Math.hypot(dx, dy) || 0.01;
      if (d < MIN) { const push = (MIN - d) / 2; dx /= d; dy /= d; a.x -= dx * push; a.y -= dy * push; b.x += dx * push; b.y += dy * push; }
    }
    const pull = it < 300 ? 0.02 : 0; // last 100 rounds: pushes only, so no two badges overlap (≥ 2-unit gap)
    for (const dt of dots) { dt.x += (dt.p.anchor[0] + 18 - dt.x) * pull; dt.y += (dt.p.anchor[1] - 22 - dt.y) * pull; dt.x = Math.max(R + 2, Math.min(W - R - 2, dt.x)); dt.y = Math.max(R + 2, Math.min(H - R - 2, dt.y)); }
  }
  for (let i = 0; i < dots.length; i++) for (let j = i + 1; j < dots.length; j++) if (Math.hypot(dots[i].x - dots[j].x, dots[i].y - dots[j].y) < 2 * R + 1.5) throw new Error(`phone badges overlap: ${dots[i].p.pn} × ${dots[j].p.pn}`);
  // hit circles (≈ 32 px) sit underneath every visible dot, so a tap on a dot always picks that dot
  const hits = dots.map(({ p, x, y }) => el('circle', { class: 'cw-ndot-hit', 'data-pn': p.pn, cx: x, cy: y, r: 44, fill: 'transparent' })).join('');
  return el('g', { class: 'cw-ndot-hits', 'aria-hidden': 'true' }, hits) + dots.map(({ p, x, y }) => el('g', { class: 'cw-ndot', 'data-pn': p.pn, 'aria-hidden': 'true' },
    el('line', { class: 'cw-tick', x1: p.anchor[0], y1: p.anchor[1], x2: x, y2: y, stroke: C.titanium, 'stroke-opacity': 0.75, 'stroke-width': 0.9 }),
    el('circle', { cx: x, cy: y, r: R, fill: C.midnight, stroke: TEAL, 'stroke-width': 1.8 }),
    el('text', { x, y: y + 8.5, 'text-anchor': 'middle', 'font-family': FONT_MONO, 'font-size': 25, 'font-weight': 600, fill: C.ice }, String(p.num).padStart(2, '0')))).join('');
}

const CARD_RES = { x0: 14, y0: 14, x1: 384, y1: 420 }; // the facts card docks here; the title block sits beside it
function build(mode) {
  const full = mode === 'full';
  SIMPLE = !full;
  if (full) setView(40, 29); else setView(34, 13); // the phone view is flatter, so the plane is longer than tall
  let W = full ? 1600 : 1000, H = full ? 880 : 1000;
  for (const k of Object.keys(B)) delete B[k];
  HATCH.length = 0;
  const box = full ? { x0: 225, y0: 24, x1: 1375, y1: 812 } : { x0: 12, y0: 30, x1: W - 30, y1: H - 8 };
  const fb = fit(box);
  if (!full) { OY += 14 - fb.y0; H = Math.ceil(fb.y1 - fb.y0 + 14 + 22); }

  // far side
  drawWing(+1, full); drawTailplane(+1, full); drawNacelle(+1, full); drawMainGear(+1, false);
  const farSide = take('FAR', 'T5', 'T4', 'T3');
  // dimensions + construction (behind the fuselage fill)
  const dims = full ? dimensions() : { lines: '', specs: [] };
  line3('CONS', [[-1.0, 0, 0], [FL + 1.2, 0, 0]]);
  const cons = full ? take('CONS') : (take('CONS'), '');
  const fus = drawFuselage(full);
  const back = take('T5');
  const floorFill = full ? drawInterior() : '';
  if (!full) { drawNoseGear(); line3('T3', [[12.75, -1.7, -1.95], [16.3, -1.7, -1.95]]); }
  const interior = take('SEAT', 'T4', 'T3', 'PAN');
  if (full) drawNoseGear();
  const noseGear = full ? take('T1b', 'T3') : '';
  const front = take('T1b', 'T1', 'T2b', 'T2') ;
  const fusHatch = full ? takeHatch() : '';
  drawFin(full);
  const fin = take('T4', 'T3', 'PAN', 'T1b', 'T1');
  drawTailplane(-1, full, true);
  const nearTail = take('T5', 'PAN', 'T1b', 'T1');
  const nearWingFill = drawWing(-1, full, true);
  const nearWing = take('T5', 'CONS', 'T4', 'T3', 'PAN', 'T1b', 'T1', 'T2');
  const wingHatch = full ? takeHatch() : '';
  const nacFill = drawNacelle(-1, full, true);
  const nearNac = take('T5', 'T4', 'T3', 'PAN', 'T1b', 'T1', 'T2');
  const nacHatch = full ? takeHatch() : '';
  drawMainGear(-1, true);
  const nearGear = take('T5', 'T4', 'T3', 'T1b');
  if (!full) takeHatch();

  const parts = PART_DEFS.map((d) => { startPart(); const a3 = d.build(); return { ...d, ...finishPart(a3) }; });
  const LG = { x: 30, y: 140 };
  let ordered = parts;
  if (full) {
    const dimBoxes = dims.specs.map(({ a, b, dir, label, t }) => { const m = [lerp(a[0], b[0], t), lerp(a[1], b[1], t)], hw = label.length * 4.3 + 12, ux = dir[0], uy = dir[1]; return [[m[0] - ux * hw - uy * 13, m[1] - uy * hw + ux * 13], [m[0] + ux * hw - uy * 13, m[1] + uy * hw + ux * 13], [m[0] + ux * hw + uy * 13, m[1] + uy * hw - ux * 13], [m[0] - ux * hw + uy * 13, m[1] - uy * hw - ux * 13]]; });
    const obstacles = [...obstaclePolys(), ...dimBoxes, ...DIM_OBS, ...parts.map((p) => [[p.bb.x0, p.bb.y0], [p.bb.x1, p.bb.y0], [p.bb.x1, p.bb.y1], [p.bb.x0, p.bb.y1]])];
    const reserved = [{ x0: 392, y0: 0, x1: 1072, y1: 160 }, { x0: 0, y0: 0, x1: CARD_RES.x1 + 8, y1: CARD_RES.y1 + 8 }];
    ordered = layoutCallouts(parts, { W, H, obstacles, reserved, side: { left: 14, right: 14, bottom: 6, colW: 196, top: 172, leftBottom: H - 56, rightBottom: H - 10, bottomLeft: 250, bottomRight: W - 14 - 196 - 12, topRow: 14, topLeft: 660, topRight: 1400 } });
    build.numbers = Object.fromEntries(ordered.map((p) => [p.pn, p.num]));
  } else parts.forEach((p) => { p.num = build.numbers[p.pn]; });
  const byNum = ordered.slice().sort((a, b) => a.num - b.num);

  const groupOf = { wing: ['GN-27-R008', 'GN-27-E005', 'GN-27-R007', 'GN-28-E006'], nac: ['GN-24-R004', 'GN-29-R011', 'GN-36-R022'], gear: ['GN-32-R015', 'GN-32-R013'], tail: ['GN-27-R006'] };
  const late = new Set(Object.values(groupOf).flat());
  const T = (pns) => el('g', { class: 'cw-parts', filter: 'url(#cw-glow)' }, parts.filter((p) => pns.includes(p.pn)).map((p) => partGroup(p, !full)).join(''));
  const early = parts.filter((p) => !late.has(p.pn)).map((p) => p.pn);
  const systems = el('g', { class: 'cw-systems' }, drawSystems(!full));

  const title = 'Generic narrowbody systems cutaway';
  const desc = 'Original schematic three-quarter cutaway of a generic, fictional twin-engine narrowbody airliner. Not engineering data, not to scale. Teal shapes are modelled spare parts; numbers match the part list.';
  const svg = el('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet', class: `cw-svg cw-${mode}`, role: 'group', 'aria-labelledby': `cw-title-${mode} cw-desc-${mode}`, 'data-mode': mode, 'data-card': full ? `${CARD_RES.x0} ${CARD_RES.y0} ${CARD_RES.x1} ${CARD_RES.y1}` : undefined, 'font-family': FONT_UI },
    el('title', { id: `cw-title-${mode}` }, title), el('desc', { id: `cw-desc-${mode}` }, desc),
    DEFS,
    full ? el('rect', { width: W, height: H, fill: 'url(#cw-grid)' }) + el('rect', { width: W, height: H, fill: 'url(#cw-grid-maj)' }) : '',
    el('rect', { class: 'cw-vignette', width: W, height: H, fill: 'url(#cw-vig)' }),
    el('g', { id: `cw-root-${mode}`, class: 'cw-air' },
      el('g', { class: 'cw-cons' }, cons, dims.lines),
      el('g', { class: 'cw-frame' }, farSide, fus.fill, fus.glow || '', back, floorFill, interior, noseGear),
      systems,
      T(early),
      el('g', { class: 'cw-frame' }, front, fusHatch, FIN_FILL, fin, nearTail), T(groupOf.tail),
      el('g', { class: 'cw-frame' }, nearWingFill, nearWing, wingHatch), T(groupOf.wing),
      el('g', { class: 'cw-frame' }, nacFill, nearNac, nacHatch), T(groupOf.nac),
      el('g', { class: 'cw-frame' }, nearGear), T(groupOf.gear)),
    full ? el('g', { class: 'cw-dims' }, dimLabels(dims.specs, [])) : '',
    full ? el('g', { class: 'cw-callouts' }, byNum.map(callout).join('')) : el('g', { class: 'cw-ndots' }, numberDots(byNum, W, H)),
    el('path', { class: 'cw-conn', d: '', fill: 'none', stroke: TEAL, 'stroke-width': 1.3, opacity: 0, 'pointer-events': 'none' }),
    el('g', { class: 'cw-focus-layer' }, full ? byNum.map(focusTarget).join('') : ''),
    full ? el('g', { class: 'cw-sheet' }, titleBlock(402, 18), legend(410, 132), triad(1050, 70)) : '');
  return { svg, parts: byNum };
}

export function files() {
  const full = build('full');
  const simple = build('simple');
  return { 'cutaway.svg': full.svg, 'cutaway-simple.svg': simple.svg, parts: full.parts };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const here = dirname(fileURLToPath(import.meta.url));
  const f = files();
  for (const name of ['cutaway.svg', 'cutaway-simple.svg']) { writeFileSync(join(here, '..', name), f[name] + '\n'); console.log(`wrote ${name} (${(f[name].length / 1024).toFixed(1)} kB)`); }
  console.log(f.parts.map((p) => `${String(p.num).padStart(2, '0')} ${p.slot.kind} ${String(Math.round(p.leaderLen)).padStart(4)} ${p.pn} ${p.label}`).join('\n'));
}
