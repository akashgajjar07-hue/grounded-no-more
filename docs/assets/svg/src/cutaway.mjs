// GROUNDED NO MORE · original technical cutaway of a GENERIC, FICTIONAL twin-engine narrowbody.
//
// Nothing here is traced or copied: a small parametric 3-D wireframe model (fuselage cross-sections along the
// length, a swept wing with dihedral, tailplane, fin, two underwing nacelles, gear and system boxes) is built in
// metres and projected with one orthographic three-quarter (axonometric) view, so every line is consistent.
//
//   node docs/assets/svg/src/cutaway.mjs      → docs/assets/svg/cutaway.svg (poster) + cutaway-simple.svg (phones)
//
// The callouts map to part numbers in docs/data/parts.json (narrowbody-applicable parts only). Output is
// deterministic. Leader lines are untangled (2-opt) and the build fails if any two leaders cross.

import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { C, FONT_MONO, FONT_DISPLAY, n, el } from './lib.mjs';

const FONT_UI = "'Inter', system-ui, sans-serif";
const deg = Math.PI / 180;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// ---------------------------------------------------------------- vector maths
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
const lerp = (a, b, t) => a + (b - a) * t;
const lerp3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const range = (a, b, step) => { const out = []; for (let v = a; v <= b + 1e-9; v += step) out.push(v); return out; };
const smooth = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));

// ---------------------------------------------------------------- view (orthographic three-quarter)
// World: x aft from the nose tip, y to starboard, z up (metres). The viewer sits ahead, to port and above.
const AZ = 40 * deg, EL = 29 * deg;
const ca = Math.cos(AZ), sa = Math.sin(AZ), ce = Math.cos(EL), se = Math.sin(EL);
const V = [-sa * ce, -ca * ce, se]; // unit vector from the model towards the viewer
let S = 1, OX = 0, OY = 0;
const raw = ([x, y, z]) => { const x1 = x * ca - y * sa, y1 = x * sa + y * ca; return [x1, -(z * ce + y1 * se)]; };
const P = (p) => { const [u, v] = raw(p); return [OX + S * u, OY + S * v]; };
const facing = (nrm) => dot(nrm, V) > 0;

// ---------------------------------------------------------------- 2-D helpers
const d2 = (pts, close = false) => (pts.length < 2 ? '' : 'M' + pts.map(([x, y]) => `${n(x)} ${n(y)}`).join('L') + (close ? 'Z' : ''));
const dP = (pts3, close = false) => d2(pts3.map(P), close);
function hull(pts) { // monotone chain convex hull
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
function segX(a, b, c, d) { // proper intersection of segments ab and cd
  const o = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) * o(a, b, d) < 0 && o(c, d, a) * o(c, d, b) < 0;
}

// ---------------------------------------------------------------- airframe parameters (generic, fictional)
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
function FN(x, th) {
  const h = 0.01, a = sub(FS(x, th + h), FS(x, th - h)), b = sub(FS(x + h, th), FS(Math.max(x - h, 0), th));
  return norm(cross(a, b));
}
const FLOOR_Z = -0.62;

// wing (one side; s = +1 starboard, -1 port)
const WG = { y0: 1.9, xle0: 12.7, sw: 27 * deg, yk: 6.3, yt: 16.9, c0: 6.3, ck: 4.15, ct: 1.55, z0: -1.25, dih: 5.5 * deg };
const wXle = (y) => WG.xle0 + (y - WG.y0) * Math.tan(WG.sw);
const wC = (y) => (y < WG.yk ? lerp(WG.c0, WG.ck, (y - WG.y0) / (WG.yk - WG.y0)) : lerp(WG.ck, WG.ct, (y - WG.yk) / (WG.yt - WG.yk)));
const wZ = (y) => WG.z0 + (y - WG.y0) * Math.tan(WG.dih);
const naca = (f) => 5 * (0.2969 * Math.sqrt(f) - 0.126 * f - 0.3516 * f * f + 0.2843 * f ** 3 - 0.1036 * f ** 4);
const wT = (y) => wC(y) * lerp(0.135, 0.105, (y - WG.y0) / (WG.yt - WG.y0));
const wPt = (s, y, f, side = 1) => [wXle(y) + f * wC(y), s * y, wZ(y) + side * 0.5 * wT(y) * naca(f) * (side > 0 ? 1 : 0.55)];

const TP = { y0: 0.55, xle0: 32.0, sw: 31 * deg, yt: 6.25, c0: 3.5, ct: 1.3, z0: 0.95, dih: 6 * deg };
const tXle = (y) => TP.xle0 + (y - TP.y0) * Math.tan(TP.sw);
const tC = (y) => lerp(TP.c0, TP.ct, (y - TP.y0) / (TP.yt - TP.y0));
const tZ = (y) => TP.z0 + (y - TP.y0) * Math.tan(TP.dih);
const tPt = (s, y, f) => [tXle(y) + f * tC(y), s * y, tZ(y)];

const FIN = { xr: 29.4, zr: 1.85, cr: 5.9, h: 6.15, sw: 36 * deg, ct: 1.8 };
const fPt = (eta, f) => { const z = FIN.zr + eta * FIN.h; const xl = FIN.xr + eta * FIN.h * Math.tan(FIN.sw); return [xl + f * lerp(FIN.cr, FIN.ct, eta), 0, z]; };

const NAC = { y: 5.75, z: -2.05, prof: [[10.55, 0.9], [10.75, 1.02], [11.3, 1.08], [12.6, 1.07], [13.7, 1.0], [14.2, 0.9], [14.35, 0.66], [15.6, 0.58], [16.1, 0.44], [16.95, 0.1]] };
const nacR = (x) => { const p = NAC.prof; if (x <= p[0][0]) return p[0][1]; for (let i = 1; i < p.length; i++) if (x <= p[i][0]) return lerp(p[i - 1][1], p[i][1], (x - p[i - 1][0]) / (p[i][0] - p[i - 1][0])); return p[p.length - 1][1]; };

const NG = { x: 5.35, zTop: -1.5, zAx: -3.82, r: 0.39, w: 0.22, dy: 0.27 };
const MG = { x: 18.1, y: 3.85, zTop: -1.4, zAx: -3.64, r: 0.585, w: 0.4, dy: 0.46 };
const GROUND = MG.zAx - MG.r;

const OBST = {};
function obstaclePolys() {
  const polys = [hull(OBST.fus)].length ? [OBST.fus] : [];
  for (const s of [-1, 1]) {
    const span = range(WG.y0, WG.yt, 0.5);
    polys.push([...span.map((y) => P(wPt(s, y, 0))), ...span.slice().reverse().map((y) => P(wPt(s, y, 1)))]);
    polys.push(hull([P(wPt(s, WG.yt, 0)), P(wPt(s, WG.yt, 1)), P([wXle(WG.yt) + 1.25, s * (WG.yt + 0.38), wZ(WG.yt) + 2.05]), P([wXle(WG.yt) + 1.95, s * (WG.yt + 0.42), wZ(WG.yt) + 2.1])]));
    const ts = range(TP.y0, TP.yt, 0.5);
    polys.push([...ts.map((y) => P(tPt(s, y, 0))), ...ts.slice().reverse().map((y) => P(tPt(s, y, 1)))]);
    const nac = [];
    for (const [x, r] of NAC.prof) for (let a = 0; a < 360; a += 20) nac.push(P(nacPt(s, x, r, a * deg)));
    polys.push(hull(nac));
    const g = [];
    for (const dy of [-MG.dy - MG.w, MG.dy + MG.w]) for (let a = 0; a < 360; a += 30) g.push(P([MG.x + MG.r * Math.cos(a * deg), s * MG.y + dy, MG.zAx + MG.r * Math.sin(a * deg)]));
    g.push(P([MG.x, s * MG.y, MG.zTop]));
    polys.push(hull(g));
  }
  const fin = range(0, 1, 0.1);
  polys.push([...fin.map((e) => P(fPt(e, 0))), ...fin.slice().reverse().map((e) => P(fPt(e, 1))), P([FIN.xr, 0, 0])]);
  const ng = [];
  for (const dy of [-NG.dy - NG.w, NG.dy + NG.w]) for (let a = 0; a < 360; a += 30) ng.push(P([NG.x + NG.r * Math.cos(a * deg), dy, NG.zAx + NG.r * Math.sin(a * deg)]));
  ng.push(P([NG.x, 0, NG.zTop]));
  polys.push(hull(ng));
  return polys;
}

// ---------------------------------------------------------------- drawing buckets
// Each bucket is one <path>: ghost wireframe in titanium at low opacity, structure, cut edges in copper.
const STY = {
  grid: { stroke: C.teal, 'stroke-opacity': 0.05, 'stroke-width': 0.6 },
  back: { stroke: C.titanium, 'stroke-opacity': 0.075, 'stroke-width': 0.6 },
  backS: { stroke: C.titanium, 'stroke-opacity': 0.05, 'stroke-width': 0.5 },
  far: { stroke: C.titanium, 'stroke-opacity': 0.26, 'stroke-width': 0.8 },
  farFine: { stroke: C.titanium, 'stroke-opacity': 0.12, 'stroke-width': 0.55 },
  frame: { stroke: C.titanium, 'stroke-opacity': 0.2, 'stroke-width': 0.65 },
  frameMaj: { stroke: C.titanium, 'stroke-opacity': 0.34, 'stroke-width': 0.8 },
  stringer: { stroke: C.titanium, 'stroke-opacity': 0.13, 'stroke-width': 0.55 },
  interior: { stroke: C.titanium, 'stroke-opacity': 0.2, 'stroke-width': 0.6 },
  seat: { stroke: C.titanium, 'stroke-opacity': 0.26, 'stroke-width': 0.6 },
  struct: { stroke: C.titanium, 'stroke-opacity': 0.42, 'stroke-width': 0.8 },
  structFine: { stroke: C.titanium, 'stroke-opacity': 0.24, 'stroke-width': 0.6 },
  panel: { stroke: C.titanium, 'stroke-opacity': 0.4, 'stroke-width': 0.75 },
  sil: { stroke: C.titanium, 'stroke-opacity': 0.82, 'stroke-width': 1.35 },
  silSoft: { stroke: C.titanium, 'stroke-opacity': 0.55, 'stroke-width': 1 },
  cut: { stroke: C.copper, 'stroke-opacity': 0.95, 'stroke-width': 1.15 },
  cutIn: { stroke: C.copper, 'stroke-opacity': 0.4, 'stroke-width': 0.7 },
  cons: { stroke: C.titanium, 'stroke-opacity': 0.32, 'stroke-width': 0.6, 'stroke-dasharray': '14 4 2 4' },
  hidden: { stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.6, 'stroke-dasharray': '4 3' },
  dim: { stroke: C.titanium, 'stroke-opacity': 0.6, 'stroke-width': 0.7 },
};
const NODASH = new Set(['cons', 'hidden', 'grid', 'dim']);
const B = {};
const put = (k, d) => { if (!d) return; (B[k] ||= []).push(d); };
const line3 = (k, pts3, close) => put(k, dP(pts3, close));
let SIMPLE = false;
function bucket(k, extra = {}) {
  if (!B[k] || !B[k].length) return '';
  const st = SIMPLE ? { ...STY[k], 'stroke-width': STY[k]['stroke-width'] * 2.2, 'stroke-opacity': Math.min(1, STY[k]['stroke-opacity'] * 1.4) } : STY[k];
  const draw = NODASH.has(k) ? {} : { class: 'cw-draw', pathLength: 1 };
  return el('path', { d: B[k].join(''), fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', ...st, ...draw, ...extra });
}
const take = (...keys) => { const s = keys.map((k) => bucket(k)).join(''); keys.forEach((k) => delete B[k]); return s; };

// surface curve split into front-facing and back-facing runs
function surfCurve(pts, nrms, kF, kB) {
  let run = [], vis = null;
  const flush = () => { if (run.length > 1) line3(vis ? kF : kB, run); };
  pts.forEach((p, i) => {
    const v = facing(nrms[i]);
    if (vis === null) vis = v;
    if (v !== vis) { run.push(p); flush(); run = [p]; vis = v; } else run.push(p);
  });
  flush();
}

// ---------------------------------------------------------------- cut-away regions (in fuselage surface coords)
// th measured from +y (starboard) through +z; the port side faces the viewer (th ≈ 150–245°).
const cutHi = (x) => { // upper boundary of the big port-side cut (deg); below it, down to the horizon, skin is removed
  if (x < 0.25 || x > 28.3) return null;
  if (x < 1.35) return 112; // radome
  if (x < 1.75) return null;
  if (x < 9.2) return 203;
  if (x < 10.6) return lerp(203, 132, smooth((x - 9.2) / 1.4));
  if (x < 26.6) return 132 + 5 * Math.sin((x - 10.6) / 16 * Math.PI * 3);
  return lerp(132, 246, smooth((x - 26.6) / 1.7));
};
const CUT_LO = 246;
const tailCut = (x) => (x > 34.1 && x < 37.25 ? [lerp(118, 102, (x - 34.1) / 3.15), 252] : null);
function isCut(x, thDeg) {
  const t = ((thDeg % 360) + 360) % 360;
  const hi = cutHi(x);
  if (hi !== null && t >= hi && t <= CUT_LO) return true;
  const tc = tailCut(x);
  return !!(tc && t >= tc[0] && t <= tc[1]);
}

// ================================================================= MODEL
function buildAirframe(mode) {
  const full = mode === 'full';
  const out = { farSide: '', fill: '', back: '', interior: '', front: '', fin: '', nearSide: '', cons: '' };

  // ---------- far side (drawn first, dimmed by the fuselage fill)
  drawWing(+1, full);
  drawTailplane(+1, full);
  drawNacelle(+1, full);
  drawMainGear(+1, full);
  out.farSide = take('farFine', 'far');

  // ---------- fuselage silhouette + translucent skin fill
  const up = [], lo = [];
  for (let x = 0.02; x <= FL - 0.02; x += 0.12) {
    let prev = null; const hits = [];
    for (let a = 0; a <= 360; a += 2) {
      const th = a * deg, v = dot(FN(x, th), V);
      if (prev && Math.sign(v) !== Math.sign(prev.v)) {
        const t = prev.v / (prev.v - v); hits.push(lerp(prev.a, a, t) * deg);
      }
      prev = { a, v };
    }
    if (hits.length >= 2) {
      const pa = P(FS(x, hits[0])), pb = P(FS(x, hits[1]));
      if (pa[1] < pb[1]) { up.push(pa); lo.push(pb); } else { up.push(pb); lo.push(pa); }
    }
  }
  const tipRing = range(0, 360, 10).map((a) => P(FS(FL - 0.02, a * deg)));
  const nose = P(FS(0.001, 0));
  const silPts = [nose, ...up, ...lo.reverse()];
  OBST.fus = silPts;
  out.fill = el('path', { d: d2(silPts, true), fill: C.midnight, 'fill-opacity': full ? 0.62 : 0.88, stroke: 'none' });
  put('sil', d2([nose, ...up])); put('sil', d2([nose, ...lo.slice().reverse()])); put('silSoft', d2(tipRing, true));

  if (full) {
    // frames (rings) + stringers, split front / back; skin lines stop inside the cut regions
    const frameXs = range(1.0, FL - 0.4, 0.62);
    frameXs.forEach((x, i) => {
      const pts = [], nr = [], cutRun = [];
      for (let a = 0; a <= 360; a += 4) {
        const th = a * deg; pts.push(FS(x, th)); nr.push(FN(x, th)); cutRun.push(isCut(x, a));
      }
      const maj = i % 5 === 0;
      // front, outside cut: frame lines; inside cut: frame drawn as structure (the cut frame stays)
      let run = [], key = null;
      const flush = () => { if (run.length > 1) line3(key, run); };
      pts.forEach((p, j) => {
        const vis = facing(nr[j]);
        const k = !vis ? 'back' : cutRun[j] ? 'structFine' : maj ? 'frameMaj' : 'frame';
        if (k !== key) { if (run.length) run.push(p); flush(); run = [p]; key = k; } else run.push(p);
      });
      flush();
    });
    for (let a = 0; a < 360; a += 11.25) {
      const pts = [], nr = [], cutF = [];
      for (let x = 1.2; x <= FL - 0.6; x += 0.3) { pts.push(FS(x, a * deg)); nr.push(FN(x, a * deg)); cutF.push(isCut(x, a)); }
      let run = [], key = null;
      const flush = () => { if (run.length > 1 && key) line3(key, run); };
      pts.forEach((p, j) => {
        const vis = facing(nr[j]);
        const k = !vis ? 'backS' : cutF[j] ? null : 'stringer';
        if (k !== key) { flush(); run = [p]; key = k; } else run.push(p);
      });
      flush();
    }
    // cut edges (copper) with an inner skin-thickness line
    const edge = [], edgeIn = [];
    for (let x = 0.25; x <= 28.3; x += 0.08) { const hi = cutHi(x); if (hi === null) { if (edge.length) { put('cut', dP(edge)); put('cutIn', dP(edgeIn)); edge.length = 0; edgeIn.length = 0; } continue; } edge.push(FS(x, hi * deg)); edgeIn.push(mul(FS(x, (hi + 2.2) * deg), 0.985)); }
    if (edge.length) { put('cut', dP(edge)); put('cutIn', dP(edgeIn)); }
    for (const xc of [0.25, 1.35, 1.75, 28.3]) {
      const hi = cutHi(xc + (xc === 1.35 || xc === 28.3 ? -0.02 : 0.02)); if (hi === null) continue;
      const seg = range(hi, CUT_LO, 3).map((a) => FS(xc, a * deg)); put('cut', dP(seg));
    }
    const te = [], tb = [];
    for (let x = 34.15; x <= 37.2; x += 0.08) { const tc = tailCut(x); te.push(FS(x, tc[0] * deg)); tb.push(FS(x, tc[1] * deg)); }
    put('cut', dP(te)); put('cut', dP(tb));
    put('cut', dP(range(118, 252, 4).map((a) => FS(34.15, a * deg))));
    put('cut', dP(range(102, 252, 4).map((a) => FS(37.2, a * deg))));
    out.back = take('backS', 'back');

    // ---------- interior: floor, seats, bins, bulkheads, bays
    const floorY = (x) => { const s = sec(x); const k = (FLOOR_Z - s.zc) / s.rz; return Math.abs(k) >= 1 ? 0 : s.ry * Math.sqrt(1 - k * k); };
    out.floor = el('path', { d: dP([...range(9.4, 28.2, 0.4).map((x) => [x, -floorY(x), FLOOR_Z]), ...range(28.2, 9.4, -0.4).map((x) => [x, floorY(x), FLOOR_Z])], true), fill: C.titanium, 'fill-opacity': 0.035, stroke: 'none' });
    line3('interior', range(2.2, 31.5, 0.3).map((x) => [x, -floorY(x), FLOOR_Z]));
    line3('structFine', range(2.2, 31.5, 0.3).map((x) => [x, floorY(x), FLOOR_Z]));
    for (const x of range(2.4, 31.2, 0.62)) line3('structFine', [[x, -floorY(x), FLOOR_Z], [x, floorY(x), FLOOR_Z]]);
    // seats (6 abreast, 30 in pitch) in the cabin cut window
    for (let x = 10.9; x <= 26.2; x += 0.78) {
      if (Math.abs(x - 15.6) < 0.5) continue; // over-wing exit row
      for (const y of [-1.58, -1.07, -0.56, 0.56, 1.07, 1.58]) {
        const w = 0.22;
        line3('seat', [[x - 0.05, y - w, FLOOR_Z + 0.42], [x + 0.42, y - w, FLOOR_Z + 0.42], [x + 0.5, y - w, FLOOR_Z + 1.1], [x + 0.5, y + w, FLOOR_Z + 1.1], [x + 0.42, y + w, FLOOR_Z + 0.42], [x - 0.05, y + w, FLOOR_Z + 0.42], [x - 0.05, y - w, FLOOR_Z + 0.42]]);
        line3('seat', [[x + 0.05, y, FLOOR_Z], [x + 0.12, y, FLOOR_Z + 0.42]]);
      }
    }
    // overhead bins + ceiling
    for (const s of [-1, 1]) {
      line3('interior', range(7, 28.5, 0.5).map((x) => [x, s * 1.42, 1.25]));
      line3('interior', range(7, 28.5, 0.5).map((x) => [x, s * 1.05, 1.62]));
    }
    // flight-deck floor, pressure bulkheads, E/E bay, gear bays, cargo holds
    line3('struct', range(0, 360, 6).map((a) => FS(1.4, a * deg)), false);
    const ab = range(0, 360, 6).map((a) => { const s = sec(29.6); return [29.6 + 0.35 * Math.cos(a * deg) ** 2 * 0, s.ry * 0.97 * Math.cos(a * deg), s.zc + s.rz * 0.97 * Math.sin(a * deg)]; });
    line3('struct', ab); // aft pressure bulkhead
    for (let r = 0.25; r < 0.95; r += 0.18) line3('structFine', range(0, 360, 10).map((a) => { const s = sec(29.6); return [29.6 + 0.5 * (1 - r), s.ry * r * Math.cos(a * deg), s.zc + s.rz * r * Math.sin(a * deg)]; }));
    // E/E bay box (under the flight deck / forward cabin floor)
    boxEdges('struct', [5.85, -0.85, -1.92], [9.35, 0.85, FLOOR_Z - 0.04]);
    // racks
    for (const yy of [-0.62, 0.32]) {
      boxEdges('structFine', [6.0, yy, -1.82], [9.15, yy + 0.3, -0.72]);
      for (const z of [-1.5, -1.12]) line3('structFine', [[6.0, yy, z], [9.15, yy, z]]);
    }
    // nose gear well
    boxEdges('struct', [3.85, -0.5, -1.95], [6.35, 0.5, -1.0]);
    // forward / aft cargo holds (dashed hidden)
    for (const [x0, x1] of [[9.6, 12.2], [21.0, 27.6]]) {
      line3('hidden', range(x0, x1, 0.4).map((x) => [x, -1.25, -1.3]));
      line3('hidden', [[x0, -1.25, -1.3], [x0, -1.25, -0.7]]); line3('hidden', [[x1, -1.25, -1.3], [x1, -1.25, -0.7]]);
    }
    // keel / centre wing box + main gear bay + belly fairing
    boxEdges('struct', [12.75, -1.7, -1.95], [16.3, 1.7, -0.95]); // centre wing box (also centre tank)
    boxEdges('struct', [16.5, -1.25, -2.05], [19.7, 1.25, -1.0]); // main gear bay
    line3('structFine', [[16.5, 0, -2.05], [19.7, 0, -2.05]]);
    const fair = range(10.6, 22.4, 0.3).map((x) => { const t = (x - 10.6) / 11.8; return [x, -1.25 - 0.55 * Math.sin(Math.PI * t), -2.1 - 0.32 * Math.sin(Math.PI * t) ** 0.6]; });
    line3('struct', fair); // belly fairing outline (port)
    // pack bay floor
    boxEdges('structFine', [10.9, -1.35, -2.2], [12.7, 1.35, -1.25]);
    out.interior = take('structFine', 'struct', 'interior', 'seat', 'hidden');

    // ---------- front skin: windows, doors, panel lines
    const winTh = 167;
    for (let x = 3.9; x <= 33.4; x += 0.53) {
      if (isCut(x, winTh) || (x > 3.0 && x < 3.75) || (x > 32.8 && x < 33.7)) continue;
      const c = FS(x, winTh * deg), w = 0.13, hgt = 0.2;
      line3('panel', range(0, 360, 30).map((a) => add(c, [w * Math.cos(a * deg), -0.0, hgt * Math.sin(a * deg)])), true);
    }
    const door = (x0, x1, a0, a1) => line3('panel', [...range(a0, a1, 4).map((a) => FS(x0, a * deg)), ...range(x0, x1, 0.1).map((x) => FS(x, a1 * deg)), ...range(a1, a0, -4).map((a) => FS(x1, a * deg)), ...range(x1, x0, -0.1).map((x) => FS(x, a0 * deg))]);
    door(2.95, 3.75, 142, 196);
    door(32.85, 33.65, 146, 194);
    // cargo door (forward), visible below the windows
    door(8.0, 9.0, 205, 222);
    out.front = take('stringer', 'frame', 'frameMaj', 'panel', 'cut', 'cutIn');
  } else {
    out.back = '';
    out.interior = '';
    out.front = '';
  }

  // ---------- fin (above the fuselage) + near-side lifting surfaces
  drawFin(full);
  out.fin = take('structFine', 'struct', 'panel', 'silSoft', 'sil');
  return out;
}

function boxEdges(k, a, b) {
  const [x0, y0, z0] = a, [x1, y1, z1] = b;
  const c = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
  [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]].forEach(([i, j]) => line3(k, [c[i], c[j]]));
}

// ---------------------------------------------------------------- wing
function drawWing(s, full, near = false) {
  const K = near ? { sil: 'sil', st: 'struct', fine: 'structFine', pan: 'panel' } : { sil: 'far', st: 'farFine', fine: 'farFine', pan: 'farFine' };
  const yIn = near ? 4.7 : WG.y0; // the near wing's inboard skin is cut away
  const span = range(yIn, WG.yt, 0.25);
  const le = span.map((y) => wPt(s, y, 0)), te = span.map((y) => wPt(s, y, 1));
  const tip = range(0, 1, 0.1).map((f) => wPt(s, WG.yt, f));
  const out = [];
  if (near) {
    // translucent upper skin with the tank-inspection window removed
    const outline = [...le, ...tip, ...te.slice().reverse()];
    const win = winPoly(s);
    out.push(el('path', { d: dP(outline, true) + dP(win, true), fill: C.midnight, 'fill-opacity': 0.55, 'fill-rule': 'evenodd', stroke: 'none' }));
  }
  line3(K.sil, le); line3(K.sil, te); line3(K.sil, tip);
  // lower surface leading edge / tip thickness
  line3(near ? 'silSoft' : 'farFine', span.map((y) => wPt(s, y, 0.12, -1)));
  // winglet (generic blended tip)
  const wt = wPt(s, WG.yt, 0), wtTe = wPt(s, WG.yt, 1);
  const wlTop = [wt[0] + 1.25, s * (WG.yt + 0.38), wt[2] + 2.05], wlTopTe = [wt[0] + 1.95, s * (WG.yt + 0.42), wt[2] + 2.1];
  const blendLe = range(0, 1, 0.1).map((t) => { const a = t * Math.PI / 2; return [lerp(wt[0], wlTop[0], 1 - Math.cos(a)), s * (WG.yt + 0.38 * Math.sin(a) ** 1.5), wt[2] + 2.05 * (1 - Math.cos(a)) ** 0.9]; });
  const blendTe = range(0, 1, 0.1).map((t) => { const a = t * Math.PI / 2; return [lerp(wtTe[0], wlTopTe[0], (1 - Math.cos(a)) * 0.8 + 0.2 * t), s * (WG.yt + 0.42 * Math.sin(a) ** 1.5), wtTe[2] + 2.1 * (1 - Math.cos(a))]; });
  line3(K.sil, blendLe); line3(K.sil, blendTe); line3(K.sil, [wlTop, wlTopTe]);
  if (!full) return out.join('');
  // spars + ribs (hidden lines under the skin)
  const yS = near ? WG.y0 : WG.y0;
  line3(near ? 'hidden' : 'farFine', range(yS, WG.yt - 0.3, 0.3).map((y) => wPt(s, y, 0.15)));
  line3(near ? 'hidden' : 'farFine', range(yS, WG.yt - 0.3, 0.3).map((y) => wPt(s, y, 0.62)));
  // slats
  for (const [a, b] of [[2.3, 5.0], [6.9, 9.3], [9.3, 11.8], [11.8, 14.2], [14.2, 16.5]]) {
    line3(K.pan, range(a, b, 0.25).map((y) => wPt(s, y, 0.13)));
    line3(K.pan, [wPt(s, a, 0), wPt(s, a, 0.13)]); line3(K.pan, [wPt(s, b, 0), wPt(s, b, 0.13)]);
  }
  // flaps, aileron, spoilers
  const cs = (a, b, f0, f1) => { line3(K.pan, range(a, b, 0.25).map((y) => wPt(s, y, f0))); line3(K.pan, [wPt(s, a, f0), wPt(s, a, f1)]); line3(K.pan, [wPt(s, b, f0), wPt(s, b, f1)]); };
  cs(Math.max(WG.y0 + 0.1, yIn), WG.yk, 0.73, 1); cs(WG.yk, 12.7, 0.72, 1); cs(12.85, 16.25, 0.76, 1);
  for (const [a, b] of [[3.0, 5.1], [6.6, 8.1], [8.1, 9.6], [9.6, 11.1], [11.1, 12.5]]) if (a >= yIn - 0.01 || !near) cs(a, b, 0.6, 0.72);
  // flap-track fairings (canoes) under the wing
  for (const y of [4.2, 8.0, 10.7, 13.2]) {
    if (near && y < yIn) continue;
    const pts = range(0, 1, 0.08).map((t) => { const f = lerp(0.55, 1.28, t); return [wXle(y) + f * wC(y), s * y, wZ(y) - 0.22 * Math.sin(Math.PI * t) - 0.05]; });
    line3(K.fine, pts);
  }
  if (near) {
    // cut root: spars, ribs and cut edges where the inboard skin was removed
    for (const f of [0.15, 0.62]) line3('struct', range(WG.y0, yIn, 0.2).map((y) => wPt(s, y, f)));
    for (const y of range(WG.y0 + 0.4, yIn, 0.6)) line3('structFine', range(0.15, 0.62, 0.05).map((f) => wPt(s, y, f)));
    line3('structFine', range(WG.y0, yIn, 0.2).map((y) => wPt(s, y, 0.15, -1)));
    line3('cons', range(WG.y0, yIn, 0.25).map((y) => wPt(s, y, 0)));
    line3('cons', range(WG.y0, yIn, 0.25).map((y) => wPt(s, y, 1)));
    line3('cut', range(0, 1, 0.05).map((f) => wPt(s, yIn, f)));
    line3('cutIn', range(0, 1, 0.05).map((f) => wPt(s, yIn - 0.08, f, -1)));
    // tank window ribs
    for (const y of range(7.6, 11.4, 0.55)) line3('struct', range(0.15, 0.62, 0.04).map((f) => wPt(s, y, f)));
    for (const f of [0.15, 0.62]) line3('struct', range(7.5, 11.5, 0.2).map((y) => wPt(s, y, f)));
    for (const f of [0.27, 0.39, 0.51]) line3('structFine', range(7.5, 11.5, 0.2).map((y) => wPt(s, y, f, -1)));
    line3('cut', winPoly(s), true);
  }
  return out.join('');
}
const winPoly = (s) => [...range(7.5, 11.5, 0.25).map((y) => wPt(s, y, 0.14)), ...range(0.14, 0.63, 0.07).map((f) => wPt(s, 11.5, f)), ...range(11.5, 7.5, -0.25).map((y) => wPt(s, y, 0.63)), ...range(0.63, 0.14, -0.07).map((f) => wPt(s, 7.5, f))];

function drawTailplane(s, full, near = false) {
  const K = near ? { sil: 'sil', pan: 'panel' } : { sil: 'far', pan: 'farFine' };
  const span = range(TP.y0, TP.yt, 0.2);
  line3(K.sil, span.map((y) => tPt(s, y, 0))); line3(K.sil, span.map((y) => tPt(s, y, 1)));
  line3(K.sil, [tPt(s, TP.yt, 0), tPt(s, TP.yt, 1)]);
  if (!full) return;
  line3(K.pan, range(TP.y0 + 0.3, TP.yt - 0.2, 0.2).map((y) => tPt(s, y, 0.7)));
  line3(K.pan, [tPt(s, TP.yt - 0.2, 0.7), tPt(s, TP.yt - 0.2, 1)]);
  line3(near ? 'hidden' : 'farFine', range(TP.y0, TP.yt - 0.2, 0.2).map((y) => tPt(s, y, 0.18)));
}

function drawFin(full) {
  const etas = range(0, 1, 0.05);
  line3('sil', etas.map((e) => fPt(e, 0))); line3('sil', etas.map((e) => fPt(e, 1)));
  line3('sil', range(0, 1, 0.1).map((f) => fPt(1, f)));
  // dorsal fillet
  const top = (x) => { const s = sec(x); return s.zc + s.rz; };
  line3('sil', range(0, 1, 0.05).map((t) => { const x = lerp(26.4, FIN.xr + 0.9, t); return [x, 0, lerp(top(26.4), fPt(0.12, 0)[2], t ** 1.8)]; }));
  if (!full) return;
  line3('panel', range(0.02, 0.97, 0.05).map((e) => fPt(e, 0.68)));
  line3('panel', [fPt(0.97, 0.68), fPt(0.97, 1)]);
  for (const e of [0.33, 0.66]) line3('panel', [fPt(e, 0.68), fPt(e, 1)]);
  for (const f of [0.15, 0.62]) line3('structFine', etas.map((e) => fPt(e, f)));
  for (const e of range(0.1, 0.95, 0.12)) line3('structFine', [fPt(e, 0.15), fPt(e, 0.62)]);
  // root thickness section
  line3('structFine', range(0, 1, 0.05).map((f) => add(fPt(0, f), [0, -0.5 * 0.12 * FIN.cr * naca(f), 0])));
}

// ---------------------------------------------------------------- nacelle (revolved profile)
function nacPt(s, x, r, a) { return [x, s * NAC.y + r * Math.cos(a), NAC.z + r * Math.sin(a)]; }
function drawNacelle(s, full, near = false) {
  const K = near ? { sil: 'sil', st: 'struct', fine: 'structFine', pan: 'panel' } : { sil: 'far', st: 'farFine', fine: 'farFine', pan: 'farFine' };
  const u = [1, 0, 0], sv = norm(cross(u, V));
  const xs = range(10.55, 16.95, 0.1);
  const out = [];
  // cut window on the near nacelle (lower fan cowl, viewer side) reveals the accessory gearbox
  const cutA = [150 * deg, 250 * deg], cutX = [11.8, 14.1];
  if (near) {
    const silU = xs.map((x) => add([x, s * NAC.y, NAC.z], mul(sv, nacR(x)))), silL = xs.map((x) => add([x, s * NAC.y, NAC.z], mul(sv, -nacR(x))));
    out.push(el('path', { d: dP([...silU, ...silL.reverse()], true), fill: C.midnight, 'fill-opacity': 0.6, stroke: 'none' }));
  }
  line3(K.sil, xs.map((x) => add([x, s * NAC.y, NAC.z], mul(sv, nacR(x)))));
  line3(K.sil, xs.map((x) => add([x, s * NAC.y, NAC.z], mul(sv, -nacR(x)))));
  // inlet lip (outer + inner) and fan face
  line3(K.sil, range(0, 360, 6).map((a) => nacPt(s, 10.55, 0.9, a * deg)), true);
  line3(K.st, range(0, 360, 6).map((a) => nacPt(s, 10.62, 0.8, a * deg)), true);
  if (full) {
    line3(K.fine, range(0, 360, 8).map((a) => nacPt(s, 11.15, 0.78, a * deg)), true);
    for (let b = 0; b < 26; b++) { const a = b / 26 * 2 * Math.PI; line3(K.fine, [nacPt(s, 11.05, 0.24, a), nacPt(s, 11.2, 0.76, a + 0.12)]); }
    line3(K.st, range(0, 360, 10).map((a) => nacPt(s, 11.0, 0.24, a * deg)), true); // spinner base
    line3(K.st, [nacPt(s, 10.75, 0, 0), nacPt(s, 11.0, 0.24, 140 * deg)]); line3(K.st, [nacPt(s, 10.75, 0, 0), nacPt(s, 11.0, 0.24, 320 * deg)]);
    // panel stations: fan cowl / thrust reverser / core
    for (const x of [11.3, 12.6, 13.7, 14.35, 15.6]) {
      const pts = [], nr = [];
      for (let a = 0; a <= 360; a += 6) { pts.push(nacPt(s, x, nacR(x), a * deg)); nr.push([0, Math.cos(a * deg), Math.sin(a * deg)]); }
      surfCurve(pts, nr, K.pan, near ? 'back' : 'farFine');
    }
    // nozzle plug
    line3(K.pan, range(0, 360, 10).map((a) => nacPt(s, 16.1, 0.3, a * deg)), true);
  }
  // pylon
  const yP = s * NAC.y;
  const pyl = [[11.6, yP, NAC.z + 0.95], [14.2, yP, NAC.z + 1.02], [wXle(NAC.y) + 0.4, yP, wZ(NAC.y) - 0.12], [wXle(NAC.y) + wC(NAC.y) * 0.75, yP, wZ(NAC.y) - 0.15], [16.6, yP, NAC.z + 0.55], [15.4, yP, NAC.z + 0.58]];
  line3(K.st, pyl);
  if (near && full) {
    // cowl cut edges + core casing + accessory gearbox (ghost)
    const e1 = range(cutA[0], cutA[1], 4 * deg).map((a) => nacPt(s, cutX[0], nacR(cutX[0]), a));
    const e2 = range(cutA[0], cutA[1], 4 * deg).map((a) => nacPt(s, cutX[1], nacR(cutX[1]), a));
    line3('cut', e1); line3('cut', e2);
    line3('cut', range(cutX[0], cutX[1], 0.1).map((x) => nacPt(s, x, nacR(x), cutA[0])));
    line3('cut', range(cutX[0], cutX[1], 0.1).map((x) => nacPt(s, x, nacR(x), cutA[1])));
    tube('struct', [11.9, yP, NAC.z], [15.7, yP, NAC.z], 0.5);
    for (const x of [12.5, 13.1, 13.7, 14.3, 14.9]) line3('structFine', range(0, 360, 10).map((a) => nacPt(s, x, 0.5, a * deg)), true);
    boxEdges('structFine', [12.0, yP - 0.75, NAC.z - 0.95], [13.5, yP - 0.35, NAC.z - 0.62]);
  }
  return out.join('');
}

function tube(k, p0, p1, r, nSeg = 36) {
  const u = norm(sub(p1, p0)), sv = norm(cross(u, V));
  line3(k, [add(p0, mul(sv, r)), add(p1, mul(sv, r))]); line3(k, [add(p0, mul(sv, -r)), add(p1, mul(sv, -r))]);
  const [e1, e2] = basis(u);
  for (const c of [p0, p1]) line3(k, range(0, nSeg, 1).map((i) => add(c, add(mul(e1, r * Math.cos(i / nSeg * 2 * Math.PI)), mul(e2, r * Math.sin(i / nSeg * 2 * Math.PI))))), true);
}
function basis(u) { const t = Math.abs(u[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0]; const e1 = norm(cross(u, t)); return [e1, cross(u, e1)]; }

// ---------------------------------------------------------------- landing gear (ghost legs; wheels are parts)
function drawMainGear(s, full, near = false) {
  const k = near ? 'struct' : 'far';
  const y = s * MG.y;
  tube(k, [MG.x - 0.05, y, MG.zTop], [MG.x + 0.05, y, MG.zAx + 0.2], 0.13, 16);
  line3(k, [[MG.x, y, MG.zTop - 0.6], [MG.x - 0.1, s * 2.2, -1.75]]); // side brace
  line3(k, [[MG.x + 0.05, y - s * (MG.dy + 0.25), MG.zAx], [MG.x + 0.05, y + s * (MG.dy + 0.25), MG.zAx]]); // axle
  if (!near) { for (const dy of [-MG.dy, MG.dy]) wheelGhost('far', [MG.x + 0.05, y + dy, MG.zAx], MG.r, MG.w); }
  // gear doors (ghost)
  if (full) line3(near ? 'structFine' : 'farFine', [[MG.x - 0.75, y - s * 0.32, MG.zTop + 0.1], [MG.x + 0.75, y - s * 0.32, MG.zTop + 0.1], [MG.x + 0.75, y - s * 0.28, -2.7], [MG.x - 0.75, y - s * 0.28, -2.7], [MG.x - 0.75, y - s * 0.32, MG.zTop + 0.1]]);
}
function wheelGhost(k, c, r, w) {
  const u = [0, 1, 0], [e1, e2] = basis(u);
  const ring = (cc, rr) => range(0, 36, 1).map((i) => add(cc, add(mul(e1, rr * Math.cos(i / 36 * 2 * Math.PI)), mul(e2, rr * Math.sin(i / 36 * 2 * Math.PI)))));
  const a = add(c, [0, -w / 2, 0]), b = add(c, [0, w / 2, 0]);
  const sv = norm(cross(u, V));
  line3(k, ring(a, r), true); line3(k, ring(b, r), true);
  line3(k, [add(a, mul(sv, r)), add(b, mul(sv, r))]); line3(k, [add(a, mul(sv, -r)), add(b, mul(sv, -r))]);
}

// ================================================================= PARTS (teal, interactive)
// Each part returns a group of solid-looking primitives (convex-hull bodies with a faint teal fill).
const TEAL = C.teal;
const prim = { body: [], line: [], anchor: null, pts: [] };
function startPart() { prim.body = []; prim.line = []; prim.pts = []; }
function solidHull(pts3, faceEdges = []) {
  const pts = pts3.map(P); prim.pts.push(...pts);
  prim.body.push(d2(hull(pts), true));
  faceEdges.forEach((e) => prim.line.push(dP(e)));
}
function circlePts(c, u, r, N = 32) { const [e1, e2] = basis(norm(u)); return range(0, N - 1, 1).map((i) => add(c, add(mul(e1, r * Math.cos(i / N * 2 * Math.PI)), mul(e2, r * Math.sin(i / N * 2 * Math.PI))))); }
function pCyl(p0, p1, r, { rings = [], capDetail = false } = {}) {
  const u = norm(sub(p1, p0));
  const c0 = circlePts(p0, u, r), c1 = circlePts(p1, u, r);
  const front = dot(u, V) > 0 ? c1 : c0;
  solidHull([...c0, ...c1], [[...front, front[0]]]);
  rings.forEach((t) => { const c = circlePts(lerp3(p0, p1, t), u, r); const vis = c.filter((p) => dot(norm(sub(p, lerp3(p0, p1, t))), V) > -0.05); if (vis.length > 1) prim.line.push(dP(halfRing(lerp3(p0, p1, t), u, r))); });
  if (capDetail) { const cc = dot(u, V) > 0 ? p1 : p0; prim.line.push(dP([...circlePts(cc, u, r * 0.45), circlePts(cc, u, r * 0.45)[0]])); }
}
function halfRing(c, u, r) { // visible half of a ring around axis u
  const sv = norm(cross(u, V)), w = norm(cross(sv, u)); // w points towards the viewer
  return range(0, 180, 10).map((a) => add(c, add(mul(sv, r * Math.cos(a * deg)), mul(w, r * Math.sin(a * deg)))));
}
function pBox(c, sz) {
  const [hx, hy, hz] = sz.map((v) => v / 2);
  const cs = [];
  for (const dx of [-hx, hx]) for (const dy of [-hy, hy]) for (const dz of [-hz, hz]) cs.push(add(c, [dx, dy, dz]));
  // visible face edges
  const faces = [
    { n: [-1, 0, 0], idx: [0, 1, 3, 2] }, { n: [1, 0, 0], idx: [4, 5, 7, 6] },
    { n: [0, -1, 0], idx: [0, 1, 5, 4] }, { n: [0, 1, 0], idx: [2, 3, 7, 6] },
    { n: [0, 0, -1], idx: [0, 2, 6, 4] }, { n: [0, 0, 1], idx: [1, 3, 7, 5] },
  ];
  const edges = faces.filter((f) => facing(f.n)).map((f) => [...f.idx.map((i) => cs[i]), cs[f.idx[0]]]);
  solidHull(cs, edges);
}
function pWheel(c, r, w, { tread = true, hub = true } = {}) {
  const u = [0, 1, 0];
  const a = add(c, [0, -w / 2, 0]), b = add(c, [0, w / 2, 0]);
  const c0 = circlePts(a, u, r, 40), c1 = circlePts(b, u, r, 40);
  const fc = dot(u, V) > 0 ? b : a, front = dot(u, V) > 0 ? c1 : c0;
  solidHull([...c0, ...c1], [[...front, front[0]]]);
  if (tread) { const cm = circlePts(c, u, r, 40); prim.line.push(dP(halfRing(c, u, r))); void cm; }
  if (hub) { for (const k of [0.66, 0.5, 0.18]) { const cc = circlePts(fc, u, r * k, 28); prim.line.push(dP([...cc, cc[0]])); } }
}
function pLine(pts3) { prim.line.push(dP(pts3)); prim.pts.push(...pts3.map(P)); }
function finishPart(anchor3) {
  const anchor = P(anchor3);
  const bb = bbox(prim.pts.length ? prim.pts : [anchor]);
  return { body: prim.body.join(''), line: prim.line.join(''), anchor, bb };
}

// Catalogue mapping: narrowbody-applicable part numbers from docs/data/parts.json (matched by ATA + description).
const PART_DEFS = [
  { pn: 'GN-34-R020', label: 'Weather radar transceiver', build() { pBox([1.65, -0.3, -0.95], [0.4, 0.5, 0.36]); return [1.65, -0.3, -0.95]; } },
  { pn: 'GN-30-E009', label: 'Flight deck windshield', build() {
    // raked panes: the aft edge sweeps back towards the side windows
    const pane = (a0, a1, x0, x1, rake) => {
      const fwd = range(a0, a1, 3).map((a) => FS(x0 + rake * (a - a0) / (a1 - a0), a * deg));
      const aft = range(a1, a0, -3).map((a) => FS(x1 + rake * (a - a0) / (a1 - a0), a * deg));
      const pts = [...fwd, ...aft]; solidHull(pts, [[...pts, pts[0]]]);
    };
    pane(96, 124, 1.62, 2.3, 0.1); pane(128, 156, 1.72, 2.42, 0.18); pane(160, 184, 2.05, 2.95, 0.25);
    return FS(2.1, 142 * deg);
  } },
  { pn: 'GN-34-R021', label: 'Pitot probe', build() {
    const base = FS(2.9, 196 * deg), out = add(base, [0, -0.2, -0.02]), tip = add(out, [-0.24, 0, 0]);
    pCyl(base, out, 0.035); pCyl(out, tip, 0.03); pLine([base, out, tip]);
    return out;
  } },
  { pn: 'GN-34-R018', label: 'Air data module', build() { pBox([3.35, -1.1, -0.95], [0.4, 0.2, 0.28]); return [3.35, -1.1, -0.95]; } },
  { pn: 'GN-34-R019', label: 'Air data inertial reference unit', build() { pBox([6.4, -0.47, -0.9], [0.7, 0.34, 0.36]); return [6.4, -0.47, -0.9]; } },
  { pn: 'GN-27-R009', label: 'Elevator aileron computer', build() { pBox([7.3, -0.47, -0.9], [0.6, 0.34, 0.34]); return [7.3, -0.47, -0.9]; } },
  { pn: 'GN-32-R017', label: 'Brake control unit', build() { pBox([8.2, -0.47, -0.9], [0.56, 0.34, 0.34]); return [8.2, -0.47, -0.9]; } },
  { pn: 'GN-24-R005', label: 'Transformer rectifier unit', build() { pBox([7.0, -0.47, -1.38], [0.85, 0.34, 0.36]); pLine([[6.65, -0.645, -1.25], [7.35, -0.645, -1.25]]); return [7.0, -0.47, -1.38]; } },
  { pn: 'GN-32-R014', label: 'Nose wheel steering actuator', build() {
    pCyl([NG.x - 0.05, -0.36, -1.82], [NG.x - 0.05, -0.08, -1.82], 0.075, { capDetail: true });
    pCyl([NG.x - 0.05, 0.08, -1.82], [NG.x - 0.05, 0.36, -1.82], 0.075);
    pBox([NG.x, 0, -1.82], [0.24, 0.16, 0.2]);
    return [NG.x - 0.05, -0.22, -1.82];
  } },
  { pn: 'GN-32-R016', label: 'Nose wheel and tyre', build() {
    pWheel([NG.x + 0.12, -NG.dy, NG.zAx], NG.r, NG.w);
    pWheel([NG.x + 0.12, NG.dy, NG.zAx], NG.r, NG.w, { hub: false });
    return [NG.x + 0.12, -NG.dy - NG.w / 2, NG.zAx];
  } },
  { pn: 'GN-21-R001', label: 'Pack flow control valve', build() {
    pCyl([11.15, -0.78, -1.62], [11.45, -0.78, -1.62], 0.13, { capDetail: true });
    pBox([11.3, -0.78, -1.42], [0.16, 0.14, 0.16]);
    return [11.3, -0.78, -1.62];
  } },
  { pn: 'GN-21-R002', label: 'Air cycle machine', build() {
    pCyl([11.75, -0.82, -1.7], [12.4, -0.82, -1.7], 0.26, { rings: [0.35, 0.7], capDetail: true });
    return [12.1, -0.82, -1.7];
  } },
  { pn: 'GN-28-R010', label: 'Fuel boost pump', build() {
    for (const y of [2.6, 3.3]) { const x = wXle(y) + 0.17 * wC(y), z = wZ(y); pCyl([x, -y, z - 0.3], [x, -y, z + 0.05], 0.13, { capDetail: true }); }
    const y = 2.95; return [wXle(y) + 0.17 * wC(y), -y, wZ(y) - 0.12];
  } },
  { pn: 'GN-28-E006', label: 'Fuel quantity probe', build() {
    for (const [y, f] of [[8.2, 0.3], [9.3, 0.45], [10.4, 0.33], [11.0, 0.5]]) { const p = wPt(-1, y, f), q = wPt(-1, y, f, -1); pCyl(add(q, [0, 0, -0.02]), add(p, [0, 0, 0.04]), 0.045); }
    return wPt(-1, 9.3, 0.45);
  } },
  { pn: 'GN-24-R004', label: 'Integrated drive generator', build() {
    pCyl([12.55, -NAC.y - 0.42, NAC.z - 0.78], [13.2, -NAC.y - 0.42, NAC.z - 0.78], 0.22, { rings: [0.5], capDetail: true });
    return [12.9, -NAC.y - 0.42, NAC.z - 0.78];
  } },
  { pn: 'GN-29-R011', label: 'Engine-driven hydraulic pump', build() {
    pCyl([12.05, -NAC.y - 0.2, NAC.z - 0.92], [12.45, -NAC.y - 0.2, NAC.z - 0.92], 0.14, { capDetail: true });
    return [12.25, -NAC.y - 0.2, NAC.z - 0.92];
  } },
  { pn: 'GN-36-R022', label: 'Bleed air valve', build() {
    const a = [14.6, -NAC.y, NAC.z + 0.5], b = [14.6, -NAC.y, NAC.z + 1.05];
    pCyl(a, b, 0.09); pCyl([14.5, -NAC.y, NAC.z + 0.8], [14.7, -NAC.y, NAC.z + 0.8], 0.15, { capDetail: true });
    return [14.6, -NAC.y, NAC.z + 0.8];
  } },
  { pn: 'GN-32-R015', label: 'Main wheel and tyre', build() {
    pWheel([MG.x + 0.05, -MG.y - MG.dy, MG.zAx], MG.r, MG.w);
    return [MG.x + 0.05, -MG.y - MG.dy - MG.w / 2, MG.zAx + 0.25];
  } },
  { pn: 'GN-32-R013', label: 'Carbon brake assembly', build() {
    // inboard wheel shown with its tyre cut away: the brake heat stack inside the rim
    const c = [MG.x + 0.05, -MG.y + MG.dy, MG.zAx];
    pCyl(add(c, [0, -0.2, 0]), add(c, [0, 0.16, 0]), 0.36, { rings: [0.2, 0.4, 0.6, 0.8], capDetail: true });
    pLine([add(c, [0, -0.22, 0.36]), add(c, [0.5, -0.22, 0.55])]); // torque rod
    return add(c, [0, -0.2, 0]);
  } },
  { pn: 'GN-29-R012', label: 'Power transfer unit', build() {
    pCyl([18.75, -0.55, -1.55], [19.35, -0.55, -1.55], 0.14, { rings: [0.5], capDetail: true });
    return [19.05, -0.55, -1.55];
  } },
  { pn: 'GN-27-R008', label: 'Spoiler servo control', build() {
    const y = 9.1; const a = wPt(-1, y, 0.5, -1), b = wPt(-1, y, 0.68, -1);
    pCyl(add(a, [0, 0, 0.05]), add(b, [0, 0, 0.1]), 0.065, { capDetail: true }); return lerp3(a, b, 0.5);
  } },
  { pn: 'GN-27-E005', label: 'Flap position sensor', build() {
    const y = 6.55; const p = wPt(-1, y, 0.7, -1); pBox(add(p, [0, 0, 0.02]), [0.2, 0.16, 0.12]); return p;
  } },
  { pn: 'GN-27-R007', label: 'Aileron servo control', build() {
    const y = 14.5; const a = wPt(-1, y, 0.56, -1), b = wPt(-1, y, 0.76, -1);
    pCyl(add(a, [0, 0, 0.04]), add(b, [0, 0, 0.07]), 0.06, { capDetail: true }); return lerp3(a, b, 0.5);
  } },
  { pn: 'GN-27-R006', label: 'Elevator servo control', build() {
    const y = 1.75; const a = tPt(-1, y, 0.5), b = tPt(-1, y, 0.7);
    pCyl(a, b, 0.07, { capDetail: true }); return lerp3(a, b, 0.5);
  } },
  { pn: 'GN-49-R023', label: 'APU starter motor', build() {
    pCyl([34.75, -0.2, 0.45], [35.15, -0.2, 0.45], 0.12, { capDetail: true }); return [34.95, -0.2, 0.45];
  } },
  { pn: 'GN-49-R024', label: 'APU fuel control unit', build() { pBox([35.75, -0.34, 0.58], [0.3, 0.12, 0.2]); return [35.75, -0.34, 0.58]; } },
];

// APU body (ghost-bold structure, not a catalogue part) drawn under the APU parts
function drawAPU() {
  tube('struct', [34.85, 0, 0.78], [36.6, 0, 0.8], 0.34, 32);
  for (const x of [35.3, 35.8, 36.2]) line3('structFine', range(0, 360, 10).map((a) => [x, 0.34 * Math.cos(a * deg), 0.79 + 0.34 * Math.sin(a * deg)]), true);
  line3('struct', [[36.6, 0.2, 0.86], [37.55, 0.1, 0.87]]); line3('struct', [[36.6, -0.2, 0.74], [37.55, -0.1, 0.83]]); // exhaust
  line3('structFine', [[35.4, 0, 1.12], [35.0, 0, 1.33]]); line3('structFine', [[35.8, 0, 1.12], [35.6, 0, 1.36]]); // inlet duct
  // firewall rings
  for (const x of [34.3, 37.0]) { const s = sec(x); line3('structFine', range(0, 360, 8).map((a) => [x, s.ry * 0.96 * Math.cos(a * deg), s.zc + s.rz * 0.96 * Math.sin(a * deg)]), true); }
  // E/E nose gear leg (ghost)
  tube('struct', [NG.x, 0, NG.zTop], [NG.x + 0.08, 0, NG.zAx + 0.1], 0.085, 16);
  line3('struct', [[NG.x + 0.12, -NG.dy - 0.15, NG.zAx], [NG.x + 0.12, NG.dy + 0.15, NG.zAx]]);
  line3('struct', [[NG.x, 0, -2.4], [4.3, 0, -1.65]]); // drag brace
  // packs (ghost heat-exchanger boxes), far pack ghost
  boxEdges('structFine', [11.0, -1.2, -2.0], [12.6, -0.4, -1.35]);
  boxEdges('structFine', [11.0, 0.4, -2.0], [12.6, 1.2, -1.35]);
  // hydraulic reservoirs (ghost) in the gear bay
  tube('structFine', [17.0, -0.8, -1.35], [17.6, -0.8, -1.35], 0.15, 20);
  tube('structFine', [17.0, 0.8, -1.35], [17.6, 0.8, -1.35], 0.15, 20);
  // radar antenna plate
  line3('struct', range(0, 360, 10).map((a) => [0.95, 0.62 * Math.cos(a * deg), -0.45 + 0.6 * Math.sin(a * deg)]), true);
  line3('structFine', [[0.95, 0, -0.45], [1.4, 0, -0.45]]);
  return take('structFine', 'struct');
}

// ================================================================= CALLOUT LAYOUT (+ crossing check)
function wrap(s, max) {
  const words = s.split(' '), lines = []; let cur = '';
  for (const w of words) { if ((cur + ' ' + w).trim().length > max && cur) { lines.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); }
  if (cur) lines.push(cur);
  return lines;
}
// Label cells on a grid over the free canvas (cells touching the airframe, reserved blocks or each other are
// excluded). Leaders are assigned by a minimum-total-length matching (Hungarian). A minimum Euclidean matching never
// has two crossing segments; the build still verifies it, and also that no leader runs through another label.
const CELL = { w: 196, h: 42 };
function hungarian(a) {
  const nR = a.length, m = a[0].length, INF = 1e18;
  const u = new Array(nR + 1).fill(0), v = new Array(m + 1).fill(0), p = new Array(m + 1).fill(0), way = new Array(m + 1).fill(0);
  for (let i = 1; i <= nR; i++) {
    p[0] = i; let j0 = 0; const minv = new Array(m + 1).fill(INF), used = new Array(m + 1).fill(false);
    do {
      used[j0] = true; const i0 = p[j0]; let delta = INF, j1 = 0;
      for (let j = 1; j <= m; j++) if (!used[j]) {
        const cur = a[i0 - 1][j - 1] - u[i0] - v[j];
        if (cur < minv[j]) { minv[j] = cur; way[j] = j0; }
        if (minv[j] < delta) { delta = minv[j]; j1 = j; }
      }
      for (let j = 0; j <= m; j++) if (used[j]) { u[p[j]] += delta; v[j] -= delta; } else minv[j] -= delta;
      j0 = j1;
    } while (p[j0] !== 0);
    do { const j1 = way[j0]; p[j0] = p[j1]; j0 = j1; } while (j0);
  }
  const ans = new Array(nR); for (let j = 1; j <= m; j++) if (p[j]) ans[p[j] - 1] = j - 1; return ans;
}
function inPoly(pt, poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) c = !c;
  }
  return c;
}
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
const labelW = (label) => 30 + 8 + Math.max(...wrap(label, 19).map((t) => t.length)) * 7.9;
// Label cells live on the sheet's perimeter: a left column, a right column, a top row and a bottom row. Each cell
// has one fixed leader end on its inner edge (column labels are flush to that edge; row leaders end on the tag), so
// a leader never enters another label. With fixed ends, a minimum-total-length matching cannot cross itself.
function layoutCallouts(parts, { W, H, obstacles, reserved, margin }) {
  const cells = [];
  const ok = (r) => {
    const grown = { x0: r.x0 - 8, y0: r.y0 - 6, x1: r.x1 + 8, y1: r.y1 + 6 };
    if (obstacles.some((poly) => rectHitsPoly(grown, poly))) return false;
    return !reserved.some((q) => !(r.x1 < q.x0 || r.x0 > q.x1 || r.y1 < q.y0 || r.y1 < q.y0 || r.y0 > q.y1));
  };
  for (let y = margin.top + 56; y + CELL.h <= H - margin.bottom; y += 46) {
    const L = { x0: margin.left, y0: y, x1: margin.left + CELL.w, y1: y + CELL.h, kind: 'L' };
    if (ok(L)) cells.push({ ...L, attach: [L.x1, y + 11] });
    const R = { x0: W - margin.right - CELL.w, y0: y, x1: W - margin.right, y1: y + CELL.h, kind: 'R' };
    if (ok(R)) cells.push({ ...R, attach: [R.x0, y + 11] });
  }
  for (let x = margin.left + CELL.w + 20; x + CELL.w <= W - margin.right - CELL.w - 10; x += CELL.w + 14) {
    const T = { x0: x, y0: margin.top, x1: x + CELL.w, y1: margin.top + CELL.h, kind: 'T' };
    if (ok(T)) cells.push({ ...T, attach: [x + 14, margin.top + 20] });
    const yb = H - margin.bottom - CELL.h;
    const Bc = { x0: x, y0: yb, x1: x + CELL.w, y1: yb + CELL.h, kind: 'B' };
    if (ok(Bc)) cells.push({ ...Bc, attach: [x + 14, yb + 2] });
  }
  if (cells.length < parts.length) throw new Error(`only ${cells.length} label cells for ${parts.length} parts`);
  const cost = parts.map((p) => cells.map((c) => Math.hypot(c.attach[0] - p.anchor[0], c.attach[1] - p.anchor[1])));
  const pick = hungarian(cost);
  parts.forEach((p, i) => { p.cell = cells[pick[i]]; p.lead = p.cell.attach; });
  for (let it = 0, changed = true; changed && it < 500; it++) { // belt and braces (ties)
    changed = false;
    for (let i = 0; i < parts.length; i++) for (let k = i + 1; k < parts.length; k++) {
      const a = parts[i], b = parts[k];
      if (segX(a.anchor, a.lead, b.anchor, b.lead)) { [a.cell, b.cell] = [b.cell, a.cell]; a.lead = a.cell.attach; b.lead = b.cell.attach; changed = true; }
    }
  }
  parts.forEach((p) => {
    const w = labelW(p.label), c = p.cell, h = wrap(p.label, 19).length > 1 ? CELL.h : 24;
    p.rect = c.kind === 'L' ? { x0: c.x1 - w, y0: c.y0, x1: c.x1, y1: c.y0 + h } : { x0: c.x0, y0: c.y0, x1: c.x0 + w, y1: c.y0 + h };
  });
  // number anticlockwise from the top left: left column down, bottom row left→right, right column up, top row right→left
  const rank = { L: 0, B: 1, R: 2, T: 3 };
  const key = (p) => { const c = p.cell; return c.kind === 'L' ? c.y0 : c.kind === 'B' ? c.x0 : c.kind === 'R' ? -c.y0 : -c.x0; };
  const ordered = parts.slice().sort((a, b) => rank[a.cell.kind] - rank[b.cell.kind] || key(a) - key(b));
  ordered.forEach((p, i) => { p.num = i + 1; });
  for (let i = 0; i < ordered.length; i++) for (let j = i + 1; j < ordered.length; j++) {
    const a = ordered[i], b = ordered[j];
    if (segX(a.anchor, a.lead, b.anchor, b.lead)) throw new Error(`leader crossing: ${a.pn} × ${b.pn}`);
  }
  ordered.forEach((p) => ordered.forEach((q) => { if (p !== q && segHitsRect(p.anchor, p.lead, { x0: q.rect.x0 + 1, y0: q.rect.y0 + 1, x1: q.rect.x1 - 1, y1: q.rect.y1 - 1 })) throw new Error(`leader ${p.pn} passes label ${q.pn}`); }));
  return ordered;
}

// ================================================================= COMPOSE
const GLOW = el('defs', {},
  el('filter', { id: 'cw-glow', x: '-40%', y: '-40%', width: '180%', height: '180%' },
    el('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: 2.4, result: 'b' }),
    el('feMerge', {}, el('feMergeNode', { in: 'b' }), el('feMergeNode', { in: 'SourceGraphic' }))),
  el('filter', { id: 'cw-glow-hi', x: '-50%', y: '-50%', width: '200%', height: '200%' },
    el('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: 4.5, result: 'b' }),
    el('feMerge', {}, el('feMergeNode', { in: 'b' }), el('feMergeNode', { in: 'b' }), el('feMergeNode', { in: 'SourceGraphic' }))),
  el('pattern', { id: 'cw-grid', width: 24, height: 24, patternUnits: 'userSpaceOnUse' }, el('path', { d: 'M24 0H0V24', fill: 'none', stroke: C.teal, 'stroke-opacity': 0.035, 'stroke-width': 0.6 })),
  el('pattern', { id: 'cw-grid-maj', width: 120, height: 120, patternUnits: 'userSpaceOnUse' }, el('path', { d: 'M120 0H0V120', fill: 'none', stroke: C.teal, 'stroke-opacity': 0.06, 'stroke-width': 0.7 })),
);

function fit(W, H, box) {
  // bounds of the key geometry at unit scale
  S = 1; OX = 0; OY = 0;
  const pts = [];
  for (let x = 0; x <= FL; x += 0.5) for (let a = 0; a < 360; a += 30) pts.push(P(FS(x, a * deg)));
  for (const s of [-1, 1]) { pts.push(P(wPt(s, WG.yt, 0)), P(wPt(s, WG.yt, 1)), P([wXle(WG.yt) + 1.3, s * (WG.yt + 0.4), wZ(WG.yt) + 2.1]), P(tPt(s, TP.yt, 0)), P([MG.x, s * (MG.y + 0.7), GROUND])); }
  pts.push(P(fPt(1, 0)), P(fPt(1, 1)), P([NG.x, 0, GROUND]));
  const bb = bbox(pts);
  S = Math.min((box.x1 - box.x0) / (bb.x1 - bb.x0), (box.y1 - box.y0) / (bb.y1 - bb.y0));
  OX = box.x0 - S * bb.x0 + ((box.x1 - box.x0) - S * (bb.x1 - bb.x0)) / 2;
  OY = box.y0 - S * bb.y0 + ((box.y1 - box.y0) - S * (bb.y1 - bb.y0)) / 2;
}

function partGroup(p, { simple }) {
  const common = { 'data-pn': p.pn, 'data-n': p.num, 'data-ax': n(p.anchor[0]), 'data-ay': n(p.anchor[1]), 'data-label': p.label, class: 'cw-part' };
  const pad = simple ? 16 : 7;
  const hit = el('rect', { class: 'cw-hit', x: p.bb.x0 - pad, y: p.bb.y0 - pad, width: p.bb.x1 - p.bb.x0 + 2 * pad, height: p.bb.y1 - p.bb.y0 + 2 * pad, rx: 4, fill: 'transparent', stroke: 'none' });
  return el('g', common,
    hit,
    el('path', { class: 'cw-body', d: p.body, fill: TEAL, 'fill-opacity': 0.16, stroke: TEAL, 'stroke-width': simple ? 2.6 : 1.25, 'stroke-linejoin': 'round' }),
    p.line ? el('path', { class: 'cw-detail', d: p.line, fill: 'none', stroke: TEAL, 'stroke-width': simple ? 1.6 : 0.8, 'stroke-opacity': 0.9, 'stroke-linecap': 'round' }) : '');
}

function focusTarget(p) { // keyboard target (tab order = callout number), bracket drawn on focus only
  const pad = 9, { x0, y0, x1, y1 } = p.bb;
  const X0 = x0 - pad, Y0 = y0 - pad, X1 = x1 + pad, Y1 = y1 + pad, k = Math.min(8, (X1 - X0) / 3, (Y1 - Y0) / 3);
  const d = `M${n(X0)} ${n(Y0 + k)}V${n(Y0)}H${n(X0 + k)}M${n(X1 - k)} ${n(Y0)}H${n(X1)}V${n(Y0 + k)}M${n(X1)} ${n(Y1 - k)}V${n(Y1)}H${n(X1 - k)}M${n(X0 + k)} ${n(Y1)}H${n(X0)}V${n(Y1 - k)}`;
  return el('g', { class: 'cw-focus', 'data-pn': p.pn, 'data-n': p.num, tabindex: 0, role: 'link', 'aria-label': `${String(p.num).padStart(2, '0')} · ${p.label}` },
    el('rect', { x: X0, y: Y0, width: X1 - X0, height: Y1 - Y0, fill: 'transparent', stroke: 'none', 'pointer-events': 'none' }),
    el('path', { class: 'cw-bracket', d, fill: 'none', stroke: C.tealHi, 'stroke-width': 1.5, opacity: 0 }));
}

function callout(p) {
  const num = String(p.num).padStart(2, '0');
  const c = p.cell, tagW = 30, tagH = 19;
  const lines = wrap(p.label, 19);
  const L = c.kind === 'L';
  const tagX = L ? c.x1 - tagW : c.x0;
  const tx = L ? c.x1 - tagW - 8 : c.x0 + tagW + 8;
  const ty = c.y0 + 15;
  return el('g', { class: 'cw-callout', 'data-pn': p.pn, 'aria-hidden': 'true' },
    el('path', { class: 'cw-leader-halo', d: d2([p.anchor, p.lead]), stroke: C.midnight, 'stroke-width': 3.4, 'stroke-opacity': 0.8, fill: 'none' }),
    el('path', { class: 'cw-leader', d: d2([p.anchor, p.lead]), stroke: C.titanium, 'stroke-width': 0.9, 'stroke-opacity': 0.75, fill: 'none' }),
    el('circle', { class: 'cw-dot', cx: p.anchor[0], cy: p.anchor[1], r: 2.8, fill: C.tealHi, stroke: C.midnight, 'stroke-width': 1.2 }),
    el('rect', { class: 'cw-hitlabel', x: p.rect.x0 - 4, y: p.rect.y0 - 2, width: p.rect.x1 - p.rect.x0 + 8, height: p.rect.y1 - p.rect.y0 + 4, fill: 'transparent' }),
    el('rect', { class: 'cw-tag', x: tagX, y: c.y0 + 2, width: tagW, height: tagH, rx: 3, fill: C.midnight, stroke: TEAL, 'stroke-width': 1 }),
    el('text', { class: 'cw-num', x: tagX + tagW / 2, y: c.y0 + 15.5, 'text-anchor': 'middle', 'font-family': FONT_MONO, 'font-size': 13, 'font-weight': 500, fill: C.ice }, num),
    el('text', { class: 'cw-name', x: tx, y: ty, 'text-anchor': L ? 'end' : 'start', 'font-family': FONT_UI, 'font-size': 14, 'font-weight': 500, fill: C.titanium },
      ...lines.map((t, i) => el('tspan', { x: tx, dy: i ? 16 : 0 }, esc(t)))));
}

const DIM_RES = [];
function dimensions() {
  const out = [];
  const arrow = (p, dir) => { const [dx, dy] = dir, L = 7, W = 2.6; const px = -dy, py = dx; return d2([[p[0] + dx * L + px * W, p[1] + dy * L + py * W], p, [p[0] + dx * L - px * W, p[1] + dy * L - py * W]]); };
  const dimLine = (a3, b3, label, off = 0) => {
    const a = P(a3), b = P(b3); const L = Math.hypot(b[0] - a[0], b[1] - a[1]); const dir = [(b[0] - a[0]) / L, (b[1] - a[1]) / L];
    put('dim', d2([a, b])); put('dim', arrow(a, dir)); put('dim', arrow(b, [-dir[0], -dir[1]]));
    { const bb = bbox([a, b]); DIM_RES.push({ x0: bb.x0 - 14, y0: bb.y0 - 14, x1: bb.x1 + 14, y1: bb.y1 + 14 }); }
    const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; let ang = Math.atan2(dir[1], dir[0]) / deg; if (ang > 90) ang -= 180; if (ang < -90) ang += 180;
    out.push(el('g', { transform: `translate(${n(mid[0])} ${n(mid[1])}) rotate(${n(ang)})` },
      el('rect', { x: -label.length * 3.9 - 6, y: -8 + off, width: label.length * 7.8 + 12, height: 15, fill: C.midnight, 'fill-opacity': 0.9 }),
      el('text', { x: 0, y: 4 + off, 'text-anchor': 'middle', 'font-family': FONT_MONO, 'font-size': 11, fill: C.titanium, 'letter-spacing': '.08em' }, label)));
  };
  // overall length on the ground line
  const gz = GROUND - 0.9;
  void gz;
  // height to fin tip
  const tipZ = fPt(1, 0)[2], xh = FL + 0.7;
  line3('cons', [[fPt(1, 1)[0], 0, tipZ], [xh + 0.4, 0, tipZ]]); line3('cons', [[FL, 0, GROUND], [xh + 0.4, 0, GROUND]]);
  dimLine([xh, 0, GROUND], [xh, 0, tipZ], `${(tipZ - GROUND).toFixed(1)} m`);
  // wing span outside the fuselage, far wing (ahead of its leading edge, in clear sheet)
  const ys0 = RY, ys1 = WG.yt + 0.42, xs = wXle(WG.yt) - 2.2, zs = wZ(WG.yt);
  line3('cons', [[wXle(WG.yt) - 0.2, ys1, zs], [xs - 0.5, ys1, zs]]);
  line3('cons', [[wXle(ys0) - 0.2, ys0, wZ(ys0)], [xs - 0.5, ys0, zs]]);
  dimLine([xs, ys0, zs], [xs, ys1, zs], `${(ys1 - ys0).toFixed(1)} m`);
  // centreline
  line3('cons', [[-1.0, 0, 0], [FL + 1.2, 0, 0]]);
  return { lines: take('dim'), labels: out.join('') };
}

function titleBlock(x, y) {
  const w = 600, h = 92;
  const t = 'GROUNDED NO MORE · GENERIC NARROWBODY · SCHEMATIC — NOT ENGINEERING DATA · NTS';
  const span = 2 * (WG.yt + 0.42), height = fPt(1, 0)[2] - GROUND;
  const spec = `LENGTH ${FL.toFixed(1)} m · SPAN ${span.toFixed(1)} m · HEIGHT ${height.toFixed(1)} m · 2 × UNDERWING ENGINES`;
  const mono = (tx, ty, s, size = 10, fill = C.titanium) => el('text', { x: tx, y: ty, 'font-family': FONT_MONO, 'font-size': size, fill, 'letter-spacing': '.06em' }, esc(s));
  return el('g', { class: 'cw-titleblock', transform: `translate(${x} ${y})` },
    el('rect', { width: w, height: h, fill: C.midnight, 'fill-opacity': 0.94, stroke: C.titanium, 'stroke-opacity': 0.45, 'stroke-width': 1 }),
    el('line', { x1: 0, y1: 40, x2: w, y2: 40, stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.75 }),
    el('line', { x1: 0, y1: 64, x2: w, y2: 64, stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.75 }),
    el('line', { x1: 418, y1: 0, x2: 418, y2: 40, stroke: C.titanium, 'stroke-opacity': 0.3, 'stroke-width': 0.75 }),
    el('rect', { x: 14, y: 14, width: 4, height: 14, fill: C.copper }),
    el('text', { x: 26, y: 27, 'font-family': FONT_DISPLAY, 'font-size': 17, 'font-weight': 600, fill: C.ice, 'letter-spacing': '.14em' }, 'SYSTEMS CUTAWAY'),
    mono(432, 17, 'SHEET 1 / 1'), mono(432, 32, 'VIEW · ¾ AXONOMETRIC'),
    mono(14, 56, spec),
    el('text', { class: 'cw-tb-line', x: 14, y: 82, 'font-family': FONT_MONO, 'font-size': 10.5, fill: C.ice, 'letter-spacing': '.03em' }, esc(t)));
}

function legend(x, y) {
  const row = (i, sw, label) => el('g', { transform: `translate(0 ${i * 18})` }, sw, el('text', { x: 30, y: 4, 'font-family': FONT_UI, 'font-size': 11.5, fill: C.titanium }, label));
  return el('g', { class: 'cw-legend', transform: `translate(${x} ${y})` },
    row(0, el('rect', { x: 0, y: -5, width: 20, height: 9, rx: 2, fill: TEAL, 'fill-opacity': 0.18, stroke: TEAL }), 'Modelled part (hover or tab)'),
    row(1, el('line', { x1: 0, y1: 0, x2: 20, y2: 0, stroke: C.copper, 'stroke-width': 1.4 }), 'Skin cut away'),
    row(2, el('line', { x1: 0, y1: 0, x2: 20, y2: 0, stroke: C.titanium, 'stroke-opacity': 0.5 }), 'Airframe (ghost)'));
}

function triad(x, y) { // orientation triad: FWD / STBD / UP
  const o = raw([0, 0, 0]);
  const ax = (v, label) => { const p = raw(v); const dx = p[0] - o[0], dy = p[1] - o[1]; const L = Math.hypot(dx, dy); const ux = dx / L * 34, uy = dy / L * 34; return el('g', {}, el('line', { x1: x, y1: y, x2: x + ux, y2: y + uy, stroke: C.titanium, 'stroke-opacity': 0.7, 'stroke-width': 0.9 }), el('text', { x: x + ux * 1.45, y: y + uy * 1.45 + 3.5, 'text-anchor': 'middle', 'font-family': FONT_MONO, 'font-size': 9.5, fill: C.titanium, 'letter-spacing': '.08em' }, label)); };
  return el('g', { class: 'cw-triad' }, ax([-1, 0, 0], 'FWD'), ax([0, 1, 0], 'STBD'), ax([0, 0, 1], 'UP'), el('circle', { cx: x, cy: y, r: 2, fill: C.titanium }));
}

function build(mode) {
  const full = mode === 'full';
  SIMPLE = !full;
  const W = full ? 1600 : 1000, H = full ? 1000 : 600;
  const drawBox = full ? { x0: 120, y0: 60, x1: 1480, y1: 890 } : { x0: 18, y0: 18, x1: W - 18, y1: H - 18 };
  fit(W, H, drawBox);
  for (const k of Object.keys(B)) delete B[k];

  const air = buildAirframe(mode);
  const apu = full ? drawAPU() : '';
  // near-side pieces (painted over the fuselage)
  const nearWingFill = drawWing(-1, full, true);
  const nearWing = take('hidden', 'cons', 'structFine', 'struct', 'panel', 'silSoft', 'sil', 'cut', 'cutIn');
  drawTailplane(-1, full, true);
  const nearTail = take('hidden', 'panel', 'sil');
  const nacFill = drawNacelle(-1, full, true);
  const nearNac = take('back', 'structFine', 'struct', 'panel', 'sil', 'cut');
  drawMainGear(-1, full, true);
  const nearGear = take('structFine', 'struct');

  DIM_RES.length = 0;
  const dims = full ? dimensions() : { lines: '', labels: '' };
  const cons = full ? take('cons') : '';
  // parts
  const parts = PART_DEFS.map((d) => { startPart(); const a3 = d.build(); const r = finishPart(a3); return { ...d, ...r }; });
  // full poster: callouts in two bands; simple: no callouts
  let ordered = parts;
  const TB = { x: 24, y: 22 }, LG = { x: 40, y: H - 70 };
  if (full) {
    const obstacles = [...obstaclePolys(), ...parts.map((p) => [[p.bb.x0, p.bb.y0], [p.bb.x1, p.bb.y0], [p.bb.x1, p.bb.y1], [p.bb.x0, p.bb.y1]])];
    const reserved = [{ x0: 0, y0: 0, x1: TB.x + 610, y1: TB.y + 104 }, { x0: 0, y0: LG.y - 16, x1: 420, y1: H }, ...DIM_RES];
    ordered = layoutCallouts(parts, { W, H, obstacles, reserved, margin: { left: 24, right: 24, top: 22, bottom: 16 } });
  }
  else {
    // simple drawing keeps the poster's numbering (computed on the full layout)
    const ref = build.numbers || {};
    parts.forEach((p) => { p.num = ref[p.pn]; });
  }
  if (full) build.numbers = Object.fromEntries(ordered.map((p) => [p.pn, p.num]));
  const byNum = ordered.slice().sort((a, b) => a.num - b.num);


  // z-order: parts belonging to the near wing / nacelle / gear paint after those surfaces
  const zLate = new Set(['GN-32-R015', 'GN-32-R013', 'GN-24-R004', 'GN-29-R011', 'GN-36-R022', 'GN-27-R008', 'GN-27-E005', 'GN-27-R007', 'GN-28-E006', 'GN-27-R006']);
  const partsEarly = parts.filter((p) => !zLate.has(p.pn)).map((p) => partGroup(p, { simple: !full })).join('');
  const partsLateWing = parts.filter((p) => ['GN-27-R008', 'GN-27-E005', 'GN-27-R007', 'GN-28-E006'].includes(p.pn)).map((p) => partGroup(p, { simple: !full })).join('');
  const partsLateNac = parts.filter((p) => ['GN-24-R004', 'GN-29-R011', 'GN-36-R022'].includes(p.pn)).map((p) => partGroup(p, { simple: !full })).join('');
  const partsLateGear = parts.filter((p) => ['GN-32-R015', 'GN-32-R013'].includes(p.pn)).map((p) => partGroup(p, { simple: !full })).join('');
  const partsLateTail = parts.filter((p) => p.pn === 'GN-27-R006').map((p) => partGroup(p, { simple: !full })).join('');
  const T = (s) => el('g', { class: 'cw-parts', filter: 'url(#cw-glow)' }, s);

  const title = 'Generic narrowbody systems cutaway';
  const desc = 'Original schematic three-quarter cutaway of a generic, fictional twin-engine narrowbody airliner. Not engineering data, not to scale. Teal shapes are modelled spare parts; numbers match the part list.';
  const svg = el('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: `0 0 ${W} ${H}`, class: `cw-svg cw-${mode}`, role: 'group', 'aria-labelledby': `cw-title-${mode} cw-desc-${mode}`, 'data-mode': mode, 'font-family': FONT_UI },
    el('title', { id: `cw-title-${mode}` }, title), el('desc', { id: `cw-desc-${mode}` }, desc),
    GLOW,
    full ? el('rect', { width: W, height: H, fill: 'url(#cw-grid)' }) : '',
    full ? el('rect', { width: W, height: H, fill: 'url(#cw-grid-maj)' }) : '',
    el('g', { class: 'cw-air' },
      el('g', { class: 'cw-cons' }, cons, dims.lines),
      air.farSide, air.fill, air.back, air.floor || '', air.interior, apu,
      T(partsEarly),
      air.front, air.fin,
      nearTail, T(partsLateTail),
      nearWingFill, nearWing, T(partsLateWing),
      nacFill, nearNac, T(partsLateNac),
      nearGear, T(partsLateGear)),
    full ? el('g', { class: 'cw-dims' }, dims.labels) : '',
    full ? el('g', { class: 'cw-callouts' }, byNum.map(callout).join('')) : '',
    el('g', { class: 'cw-focus-layer' }, full ? byNum.map(focusTarget).join('') : ''),
    full ? titleBlock(TB.x, TB.y) : '',
    full ? legend(LG.x, LG.y) : '',
    full ? triad(370, H - 44) : '');
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
  for (const name of ['cutaway.svg', 'cutaway-simple.svg']) {
    writeFileSync(join(here, '..', name), f[name] + '\n');
    console.log(`wrote ${name} (${(f[name].length / 1024).toFixed(1)} kB)`);
  }
  console.log(f.parts.map((p) => `${String(p.num).padStart(2, '0')} ${p.pn} ${p.label}`).join('\n'));
}
