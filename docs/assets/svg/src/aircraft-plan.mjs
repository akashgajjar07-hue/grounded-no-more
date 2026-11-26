// Wave A: two ORIGINAL orthographic plan views, generated from parameters (no traced OEM drawings).
//   aircraft-narrowbody.svg — single-aisle twin archetype (A320-family proportions)
//   aircraft-widebody.svg   — twin-aisle twin archetype (787-family proportions; no bleed-system callouts)
// Geometry is in metres (x lateral, + = right/starboard seen from above; y = aft from the nose tip) and scaled to px.
// Stroke hierarchy (DESIGN_SYSTEM.md §4): silhouette 1.8 px #B9C8D6 · major structure 1.1 px #71899C · secondary
// 0.7 px #51697D · construction 0.5 px dashed #334C61 · selected system 2.25 px #22C7B8 · unselected systems 0.9 px
// muted titanium · urgent markers 1.75 px #E76B64. ATA hotspots are soft "indicative zones", not component locations.
// Hotspot API (kept for the views): <g id="ata-XX" class="ata-hotspot" data-ata="XX"> with .hs-shapes, .hs-badge
// (circle + text) and .bp-callout; svg[data-compact-viewbox].
import { el, g, path, text, poly, n, svgDoc, titleBlock, sheetFrame } from './lib.mjs';

const W = 1440;
const H = 1000;

const STYLE = `
.bp-grid-minor{stroke-opacity:.035}
.bp-grid-major{stroke-opacity:.05}
.ac-skin{fill:#0B1826;stroke:#B9C8D6;stroke-width:1.8;stroke-linejoin:round;stroke-linecap:round}
.ac-major{fill:none;stroke:#71899C;stroke-width:1.1;stroke-linecap:round;stroke-linejoin:round}
.ac-minor{fill:none;stroke:#51697D;stroke-width:.7;stroke-linecap:round;stroke-linejoin:round}
.ac-bay{fill:none;stroke:#51697D;stroke-width:.7;stroke-dasharray:4 2.5}
.ac-constr{fill:none;stroke:#334C61;stroke-width:.5;stroke-dasharray:10 3 2 3}
.ac-t{font-family:'IBM Plex Mono',ui-monospace,monospace;fill:#8FA5B7;font-size:11px;letter-spacing:.1em}
.ac-t-ice{font-family:'Inter',system-ui,sans-serif;fill:#F2F6FA;font-size:13px;font-weight:600;letter-spacing:.02em}
.ac-t-sub{font-family:'Inter',system-ui,sans-serif;fill:#8FA5B7;font-size:11px;letter-spacing:.06em}
.hs-shape{fill:#8FA5B7;fill-opacity:.07;stroke:#8FA5B7;stroke-width:.9;stroke-opacity:1}
.hs-zone-t{display:none;font-family:'Inter',system-ui,sans-serif;font-size:11px;font-weight:600;letter-spacing:.04em;fill:#22C7B8;paint-order:stroke;stroke:#09131F;stroke-width:4px;stroke-linejoin:round}
.hs-badge circle{fill:#09131F;stroke:#8FA5B7;stroke-width:1.4}
.hs-badge text{font-family:'IBM Plex Mono',ui-monospace,monospace;fill:#F2F6FA;font-size:16px;font-weight:600;text-anchor:middle;dominant-baseline:central}
.bp-bubble{fill:#09131F;stroke:#8FA5B7;stroke-width:1}
.bp-bubble-t{fill:#F2F6FA}
.bp-leader{stroke:#8FA5B7;stroke-opacity:1;stroke-width:.7}
.ata-hotspot:hover .hs-shape,.ata-hotspot:focus .hs-shape{fill-opacity:.12}
.ata-hotspot.is-active .hs-shape{fill:#22C7B8;fill-opacity:.14;stroke:#22C7B8;stroke-width:2.25;filter:none}
.ata-hotspot.is-active .hs-zone-t{display:inline}
.ata-hotspot.is-active .hs-badge circle{stroke:#22C7B8;stroke-width:2.25}
.ata-hotspot.is-active .bp-bubble{fill:#22C7B8;stroke:#22C7B8}
.ata-hotspot.is-active .bp-bubble-t{fill:#09131F}
.ata-hotspot.is-urgent .hs-badge circle,.ata-hotspot.is-missing .hs-badge circle{stroke:#E76B64;stroke-width:1.75}
.ata-hotspot:focus-visible .hs-shape,.ata-hotspot:focus-visible .hs-badge circle{stroke:#7FF3E6;stroke-width:2.4}
.bp-compact .hs-badge{display:inline}
`;

/** Build one plan view from an archetype spec. */
function plan(spec) {
  const { K, L, R, noseLen, tailStart, tailHalf, span, leRoot, sweep, rootChord, kinkFrac, kinkChord, tipChord, rake,
    eng, nacLen, nacR, nacFwd, hsSpan, hsLe, hsSweep, hsRoot, hsTip, finLe, finRoot, nlg, mlg, sections } = spec;
  const CX = W / 2;
  const Y0 = (H - L * K) / 2 - 10;
  const X = (x) => CX + x * K;
  const Y = (y) => Y0 + y * K;
  const pt = (x, y) => `${n(X(x))},${n(Y(y))}`;
  const P = ([x, y]) => [X(x), Y(y)];
  const both = (fn) => [fn(-1), fn(1)];
  const semi = span / 2;
  const rr = (x0, y0, x1, y1, r = 0.5) => el('rect', { x: X(Math.min(x0, x1)), y: Y(Math.min(y0, y1)), width: Math.abs(x1 - x0) * K, height: Math.abs(y1 - y0) * K, rx: r * K, ry: r * K });

  // ---------- fuselage ----------
  const half = (y) => {
    if (y <= 0) return 0;
    if (y < noseLen) { const t = y / noseLen; return R * Math.sqrt(1 - (1 - t) ** 2.25); }
    if (y <= tailStart) return R;
    const t = (y - tailStart) / (L - tailStart);
    return R - (R - tailHalf) * (1 - (1 - t) ** 1.5);
  };
  const fusPath = () => {
    const ys = [];
    for (let y = 0; y <= L + 1e-9; y += 0.25) ys.push(Math.min(y, L));
    const right = ys.map((y) => [half(y), y]);
    const left = right.slice().reverse().map(([x, y]) => [-x, y]);
    return poly(right.concat(left).map(P), true);
  };

  // ---------- wing ----------
  const t = Math.tan((sweep * Math.PI) / 180);
  const leY = (x) => leRoot + (x - R) * t;
  const kinkX = R + (semi - R) * kinkFrac;
  const rootTE = leRoot + rootChord;
  const kinkTE = leY(kinkX) + kinkChord;
  const tipLE = leY(semi);
  const tipTE = tipLE + tipChord;
  const teY = (x) => (x <= kinkX ? rootTE + ((x - R) * (kinkTE - rootTE)) / (kinkX - R) : kinkTE + ((x - kinkX) * (tipTE - kinkTE)) / (semi - kinkX));
  const chordAt = (x, f) => leY(x) + f * (teY(x) - leY(x));
  const wingPath = (s) => {
    const m = ([x, y]) => P([s * x, y]);
    const pts = [[R * 0.98, leRoot]];
    if (rake) {
      // raked tip: the leading edge curves aft over the last `rake` metres of span
      const a = semi - rake;
      pts.push([a, leY(a)]);
      // ends just ahead of the tip trailing edge, so the raked tip closes cleanly
      const endY = tipTE - 0.35;
      for (let i = 1; i <= 8; i++) { const u = i / 8; const x = a + rake * u; pts.push([x, leY(a) + (x - a) * t + (endY - leY(semi)) * u * u]); }
      pts.push([semi, tipTE - 0.05]);
    } else {
      pts.push([semi, tipLE], [semi, tipTE]);
    }
    pts.push([kinkX, kinkTE], [R * 0.98, rootTE]);
    return poly(pts.map(m), true);
  };

  // ---------- tailplane + fin ----------
  const ht = Math.tan((hsSweep * Math.PI) / 180);
  const hsHalf = hsSpan / 2;
  const hsLeY = (x) => hsLe + (x - tailHalf * 2.2) * ht;
  const hsX0 = half(hsLe + 0.5) * 0.9;
  const hsTeY = (x) => hsLeY(hsX0) + hsRoot + ((x - hsX0) / (hsHalf - hsX0)) * (hsLeY(hsHalf) + hsTip - hsLeY(hsX0) - hsRoot);
  const hsChord = (x, f) => hsLeY(x) + f * (hsTeY(x) - hsLeY(x));
  const hsPath = (s) => poly([[hsX0, hsLeY(hsX0)], [hsHalf, hsLeY(hsHalf)], [hsHalf, hsLeY(hsHalf) + hsTip], [hsX0, hsTeY(hsX0)]].map(([x, y]) => P([s * x, y])), true);
  const finPath = () => `M${pt(0, finLe)}C${pt(0.34, finLe + finRoot * 0.25)} ${pt(0.38, finLe + finRoot * 0.6)} ${pt(0.3, finLe + finRoot)}L${pt(0.12, L - 0.25)}L${pt(-0.12, L - 0.25)}L${pt(-0.3, finLe + finRoot)}C${pt(-0.38, finLe + finRoot * 0.6)} ${pt(-0.34, finLe + finRoot * 0.25)} ${pt(0, finLe)}Z`;

  // ---------- nacelles ----------
  const inlet = (x) => leY(x) - nacFwd;
  const nacPath = (s) => {
    const y0 = inlet(eng);
    const prof = [[0.86, 0], [0.97, 0.08], [1, 0.25], [0.98, 0.6], [0.88, 0.85], [0.7, 1]].map(([w, f]) => [nacR * w, y0 + f * nacLen]);
    const right = prof.map(([dx, y]) => [s * eng + dx, y]);
    const left = prof.slice().reverse().map(([dx, y]) => [s * eng - dx, y]);
    return poly(right.concat(left).map(P), true);
  };

  // ---------- drawing ----------
  const air = [];
  // construction: centreline, nacelle centrelines, wing reference line (25% chord)
  air.push(path(`M${pt(0, -2.5)}L${pt(0, L + 2.5)}`, 'ac-constr'));
  air.push(...both((s) => path(`M${pt(s * eng, inlet(eng) - 1.5)}L${pt(s * eng, inlet(eng) + nacLen + 2)}`, 'ac-constr')));
  air.push(...both((s) => path(poly([[s * R, chordAt(R, 0.25)], [s * semi * 0.97, chordAt(semi * 0.97, 0.25)]].map(P)), 'ac-constr')));
  // tailplane under the fuselage
  air.push(...both((s) => path(hsPath(s), 'ac-skin')));
  air.push(...both((s) => path(poly([[s * hsX0 * 1.05, hsChord(hsX0 * 1.05, 0.68)], [s * hsHalf * 0.97, hsChord(hsHalf * 0.97, 0.68)]].map(P)), 'ac-major')));      // elevator hinge
  air.push(...both((s) => path(poly([[s * hsHalf * 0.55, hsChord(hsHalf * 0.55, 0.68)], [s * hsHalf * 0.55, hsTeY(hsHalf * 0.55)]].map(P)), 'ac-minor')));
  // nacelles (ahead of the wing) + pylons
  air.push(...both((s) => path(nacPath(s), 'ac-skin')));
  air.push(...both((s) => path(`M${pt(s * eng - nacR * 0.86, inlet(eng) + nacLen * 0.08)}Q${pt(s * eng, inlet(eng) - 0.1)} ${pt(s * eng + nacR * 0.86, inlet(eng) + nacLen * 0.08)}`, 'ac-minor')));
  air.push(...both((s) => path(`M${pt(s * eng - nacR, inlet(eng) + nacLen * 0.42)}L${pt(s * eng + nacR, inlet(eng) + nacLen * 0.42)}`, 'ac-minor')));
  // wings
  air.push(...both((s) => path(wingPath(s), 'ac-skin')));
  air.push(...both((s) => {
    const out = [];
    const seg = (a, b, f, cls) => path(poly([[s * a, chordAt(a, f)], [s * b, chordAt(b, f)]].map(P)), cls);
    const cut = (x, f0, f1, cls = 'ac-minor') => path(poly([[s * x, chordAt(x, f0)], [s * x, chordAt(x, f1)]].map(P)), cls);
    // slats (secondary): along the leading edge, inboard of the tip
    const s0 = R + (semi - R) * 0.18, s1 = semi * (rake ? 0.86 : 0.95);
    out.push(seg(s0, s1, 0.1, 'ac-minor'));
    for (let i = 0; i <= 5; i++) out.push(cut(s0 + ((s1 - s0) * i) / 5, 0, 0.1));
    // control-surface boundaries (major): flap hinge, aileron, spoiler panels
    const fl0 = R * 1.05, fl1 = R + (semi - R) * 0.72, a0 = fl1 + 0.25, a1 = semi * (rake ? 0.84 : 0.93);
    out.push(path(poly([[s * fl0, teY(fl0)], [s * fl0, chordAt(fl0, 0.74)], [s * kinkX, chordAt(kinkX, 0.74)], [s * fl1, chordAt(fl1, 0.74)], [s * fl1, teY(fl1)]].map(P)), 'ac-major'));
    out.push(cut(kinkX, 0.74, 1, 'ac-major'));
    out.push(path(poly([[s * a0, teY(a0)], [s * a0, chordAt(a0, 0.76)], [s * a1, chordAt(a1, 0.76)], [s * a1, teY(a1)]].map(P)), 'ac-major'));
    const sp = 5;
    for (let i = 0; i < sp; i++) {
      const xa = kinkX * 0.55 + ((fl1 - kinkX * 0.55) * i) / sp + 0.15, xb = kinkX * 0.55 + ((fl1 - kinkX * 0.55) * (i + 1)) / sp - 0.15;
      out.push(path(poly([[s * xa, chordAt(xa, 0.6)], [s * xb, chordAt(xb, 0.6)], [s * xb, chordAt(xb, 0.73)], [s * xa, chordAt(xa, 0.73)]].map(P), true), 'ac-minor'));
    }
    // flap-track fairings (secondary)
    [0.3, 0.52, 0.68].forEach((f) => { const x = R + (semi - R) * f; const te = teY(x); out.push(path(`M${pt(s * x, te - 1.1)}L${pt(s * x, te + 1.0)}`, 'ac-minor')); });
    // spars (major structure, internal): front 15%, rear 65%
    out.push(path(poly([[s * R, chordAt(R, 0.15)], [s * semi * 0.96, chordAt(semi * 0.96, 0.15)]].map(P)), 'ac-bay'));
    out.push(path(poly([[s * R, chordAt(R, 0.65)], [s * kinkX, chordAt(kinkX, 0.65)], [s * semi * 0.96, chordAt(semi * 0.96, 0.65)]].map(P)), 'ac-bay'));
    // wing-root fairing joint
    out.push(path(poly([[s * (R + 0.35), leRoot - 0.6], [s * (R + 0.35), rootTE + 0.4]].map(P)), 'ac-minor'));
    return g({}, out);
  }));
  // fuselage on top
  air.push(path(fusPath(), 'ac-skin'));
  // fuselage section lines (major): production joints
  sections.forEach((y) => { const hh = half(y); air.push(path(`M${pt(-hh, y)}Q${pt(0, y + 0.18)} ${pt(hh, y)}`, 'ac-major')); });
  // windscreen (secondary)
  const ws = noseLen * 0.42;
  air.push(path(`M${pt(-half(ws) * 0.78, ws)}Q${pt(0, ws - noseLen * 0.12)} ${pt(half(ws) * 0.78, ws)}`, 'ac-minor'));
  air.push(path(`M${pt(-half(ws + noseLen * 0.14) * 0.85, ws + noseLen * 0.14)}Q${pt(0, ws + noseLen * 0.02)} ${pt(half(ws + noseLen * 0.14) * 0.85, ws + noseLen * 0.14)}`, 'ac-minor'));
  // wing-to-body fairing (secondary)
  air.push(...both((s) => path(`M${pt(s * R, leRoot - 2.2)}C${pt(s * R * 1.18, leRoot - 0.8)} ${pt(s * R * 1.22, leRoot + 1)} ${pt(s * R * 1.22, leRoot + 2.5)}L${pt(s * R * 1.22, rootTE - 0.5)}C${pt(s * R * 1.22, rootTE + 0.8)} ${pt(s * R * 1.12, rootTE + 1.8)} ${pt(s * R, rootTE + 2.6)}`, 'ac-minor')));
  // gear bays (dashed outlines: internal)
  air.push(path(poly([[-nlg.w / 2, nlg.y0], [nlg.w / 2, nlg.y0], [nlg.w / 2, nlg.y1], [-nlg.w / 2, nlg.y1]].map(P), true), 'ac-bay'));
  air.push(...both((s) => path(poly([[s * mlg.x0, mlg.y0], [s * mlg.x1, mlg.y0], [s * mlg.x1, mlg.y1], [s * mlg.x0, mlg.y1]].map(P), true), 'ac-bay')));
  air.push(...both((s) => path(poly([[s * mlg.x1, mlg.y0 + 0.4], [s * mlg.legX, mlg.y0 - 0.6]].map(P)), 'ac-bay')));
  // fin (lens on the centreline) + rudder hinge
  air.push(path(finPath(), 'ac-skin'));
  air.push(path(`M${pt(-0.28, finLe + finRoot * 0.72)}L${pt(0.28, finLe + finRoot * 0.72)}`, 'ac-major'));

  // ---------- ATA indicative zones ----------
  const z = spec.zones({ X, Y, P, pt, rr, half, leY, teY, chordAt, kinkX, semi, R, eng, inlet, hsLeY, hsTeY, hsChord, hsHalf, hsX0, nlg, mlg, rootTE, leRoot, L, noseLen });
  const zoneGroups = z.map((h) => {
    const [bx, by] = P(h.badge);
    const side = h.side === 'L' ? -1 : 1;
    const cx = side < 0 ? 300 : W - 300;
    const leaderEnd = side < 0 ? cx + 20 : cx - 20;
    const callout = g({ class: 'bp-callout' },
      path(`M${n(bx)},${n(by)}L${n(leaderEnd)},${n(h.calloutY)}`, 'bp-leader'),
      el('circle', { cx, cy: h.calloutY, r: 17, class: 'bp-bubble' }),
      text(cx, h.calloutY + 0.5, h.ata, 'bp-bubble-t'),
      text(cx + side * 28, h.calloutY - 3, h.name, 'ac-t-ice', { 'text-anchor': side < 0 ? 'end' : 'start' }),
      text(cx + side * 28, h.calloutY + 13, `Indicative zone · ${h.sub.charAt(0)}${h.sub.slice(1).toLowerCase()}`, 'ac-t-sub', { 'text-anchor': side < 0 ? 'end' : 'start' }));
    // the "indicative zone" tag sits beside the fuselage (or under a wing zone), never on the badge
    const onWing = Math.abs(h.badge[0]) > R + 1;
    const [lx, ly] = P(h.zoneLabel || (onWing ? [h.badge[0], h.badge[1] + 1.9] : [R + 0.7, h.badge[1]]));
    return g({ id: `ata-${h.ata}`, class: 'ata-hotspot', 'data-ata': h.ata, 'data-name': h.name, tabindex: 0, role: 'button', 'aria-label': `ATA ${h.ata} ${h.name.toLowerCase()}, indicative zone` },
      el('title', {}, `ATA ${h.ata} ${h.name.toLowerCase()} · indicative zone, not a component location`),
      g({ class: 'hs-shapes' }, h.shapes.map((s) => (s.startsWith('<') ? s.replace(/^<(\w+)/, '<$1 class="hs-shape"') : path(s, 'hs-shape')))),
      text(lx, ly + 4, 'indicative zone', 'hs-zone-t', { 'text-anchor': onWing ? 'middle' : 'start' }),
      callout,
      g({ class: 'hs-badge' }, el('circle', { cx: bx, cy: by, r: 19 }), text(bx, by + 1, h.ata, '')));
  });

  const orient = g({ class: 'bp-orient' },
    text(X(0) + 10, Y(-1.6), 'FWD ↑', 'ac-t'),
    text(X(-semi * 0.62), Y(rootTE + 3.2), 'LH', 'ac-t', { 'text-anchor': 'middle' }),
    text(X(semi * 0.62), Y(rootTE + 3.2), 'RH', 'ac-t', { 'text-anchor': 'middle' }));
  const top = Math.min(Y(-3), Y0 - 30);
  const compact = `${n(X(-semi - 1.5))} ${n(Y(-2.5))} ${n((span + 3) * K)} ${n((L + 5) * K)}`;

  const body = [
    el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#bp-grid)', class: 'bp-gridfill' }),
    sheetFrame(W, H, { zonesX: 8, zonesY: 5 }),
    g({ class: 'bp-airframe' }, air),
    orient,
    g({ class: 'bp-hotspots' }, zoneGroups),
    g({ class: 'bp-frameset' },
      text(52, 62, spec.title, 'ac-t-ice'),
      text(52, 80, 'FALCON HUB AIRWAYS (FICTIONAL) · SHADED AREAS ARE INDICATIVE ZONES, NOT COMPONENT LOCATIONS', 'ac-t')),
    titleBlock({ x: W - 32 - 300, y: H - 32 - 116, w: 300, title: spec.sheetTitle, sheet: spec.sheet }),
  ];
  void top;
  return svgDoc({
    w: W, h: H, title: spec.title, desc: spec.desc, extraStyle: STYLE,
    attrs: { 'data-compact-viewbox': compact, 'data-archetype': spec.id, class: 'bp-sheet ac-plan' },
    body: body.join(''),
  });
}

// ---------- archetypes ----------
const NB = {
  id: 'narrowbody', sheet: '01', title: 'SINGLE-AISLE TWIN ARCHETYPE — PLAN VIEW', sheetTitle: 'NARROWBODY ARCHETYPE · PLAN',
  desc: 'Original orthographic plan view of a single-aisle twin-engine airliner archetype (A320-family proportions), generated from parameters. Shaded ATA areas are indicative zones, not component locations. Not an OEM drawing; not engineering data.',
  K: 21, L: 37.6, R: 1.98, noseLen: 5.2, tailStart: 27.2, tailHalf: 0.3, span: 35.8, leRoot: 13.0, sweep: 26, rootChord: 6.3,
  kinkFrac: 0.33, kinkChord: 3.6, tipChord: 1.55, rake: 0, eng: 5.75, nacLen: 4.3, nacR: 1.05, nacFwd: 2.6,
  hsSpan: 12.45, hsLe: 31.6, hsSweep: 30, hsRoot: 3.4, hsTip: 1.3, finLe: 29.6, finRoot: 6.4,
  nlg: { w: 1.0, y0: 3.4, y1: 6.6 }, mlg: { x0: 0.3, x1: 1.75, y0: 17.6, y1: 20.4, legX: 4.6 },
  sections: [5.6, 10.6, 21.4, 27.6, 33.2],
  zones: (u) => {
    const { pt, rr, half, leY, chordAt, teY, kinkX, semi, R, eng, hsChord, hsTeY, hsHalf, hsX0, nlg, mlg, rootTE, leRoot, L, noseLen } = u;
    const ell = (cx, cy, rx, ry) => el('ellipse', { cx: u.X(cx), cy: u.Y(cy), rx: rx * 21, ry: ry * 21 });
    const ail0 = R + (semi - R) * 0.72 + 0.25, ail1 = semi * 0.93;
    const ailZ = (s) => `M${pt(s * ail0, chordAt(ail0, 0.7))}L${pt(s * ail1, chordAt(ail1, 0.7))}Q${pt(s * (ail1 + 0.3), (chordAt(ail1, 0.7) + teY(ail1)) / 2)} ${pt(s * ail1, teY(ail1) + 0.2)}L${pt(s * ail0, teY(ail0) + 0.2)}Q${pt(s * (ail0 - 0.3), (chordAt(ail0, 0.7) + teY(ail0)) / 2)} ${pt(s * ail0, chordAt(ail0, 0.7))}Z`;
    const elevZ = (s) => `M${pt(s * hsX0 * 1.1, hsChord(hsX0 * 1.1, 0.62))}L${pt(s * hsHalf * 0.95, hsChord(hsHalf * 0.95, 0.62))}L${pt(s * hsHalf * 0.95, hsTeY(hsHalf * 0.95) + 0.15)}L${pt(s * hsX0 * 1.1, hsTeY(hsX0 * 1.1) + 0.15)}Z`;
    const ductZ = (s) => `M${pt(s * (R + 0.4), leY(R + 0.4) + 0.2)}L${pt(s * (eng + 1.2), leY(eng + 1.2) + 0.2)}L${pt(s * (eng + 1.2), leY(eng + 1.2) + 1.4)}L${pt(s * (R + 0.4), leY(R + 0.4) + 1.6)}Z`;
    void half; void kinkX; void noseLen;
    return [
      { ata: '34', name: 'NAVIGATION', sub: 'RADOME · AVIONICS', side: 'L', calloutY: 150, badge: [0, 1.9], shapes: [ell(0, 1.5, 1.25, 1.4)], zoneLabelDy: -34 },
      { ata: '24', name: 'ELECTRICAL POWER', sub: 'E/E BAY · FWD', side: 'R', calloutY: 250, badge: [0, 7.6], shapes: [rr(-1.2, 6.3, 1.2, 9.0, 0.6)] },
      { ata: '21', name: 'AIR CONDITIONING', sub: 'PACKS · BELLY', side: 'L', calloutY: 345, badge: [0, 12.3], shapes: [rr(-1.75, 10.9, 1.75, 14.6, 0.8)] },
      { ata: '36', name: 'PNEUMATIC', sub: 'WING ROOT · PYLONS', side: 'L', calloutY: 470, badge: [-(R + eng) / 2 - 0.6, leY((R + eng) / 2 + 0.6) + 0.8], shapes: [ductZ(-1), ductZ(1)], zoneLabelDy: -30 },
      { ata: '32', name: 'LANDING GEAR', sub: 'NLG + MLG BAYS', side: 'L', calloutY: 640, badge: [-1.1, (mlg.y0 + mlg.y1) / 2], shapes: [rr(-nlg.w / 2 - 0.25, nlg.y0 - 0.2, nlg.w / 2 + 0.25, nlg.y1 + 0.2, 0.4), rr(-mlg.x1 - 0.3, mlg.y0 - 0.3, mlg.x1 + 0.3, mlg.y1 + 0.3, 0.6)] },
      { ata: '29', name: 'HYDRAULIC POWER', sub: 'BAYS AFT OF THE MLG', side: 'R', calloutY: 640, badge: [0, rootTE + 2.4], shapes: [rr(-1.45, rootTE + 0.9, 1.45, rootTE + 4.0, 0.6)] },
      { ata: '27', name: 'FLIGHT CONTROLS', sub: 'AILERONS · ELEVATORS · RUDDER', side: 'R', calloutY: 520, badge: [(ail0 + ail1) / 2, (chordAt((ail0 + ail1) / 2, 0.7) + teY((ail0 + ail1) / 2)) / 2], shapes: [ailZ(-1), ailZ(1), elevZ(-1), elevZ(1)], zoneLabelDy: 32 },
      { ata: '49', name: 'AIRBORNE APU', sub: 'TAILCONE', side: 'L', calloutY: 860, badge: [0, L - 2.1], shapes: [ell(0, L - 1.6, 0.55, 1.5)], zoneLabelDy: 34 },
    ];
  },
};

const WB = {
  id: 'widebody', sheet: '02', title: 'TWIN-AISLE TWIN ARCHETYPE — PLAN VIEW', sheetTitle: 'WIDEBODY ARCHETYPE · PLAN',
  desc: 'Original orthographic plan view of a twin-aisle twin-engine airliner archetype (787-family proportions), generated from parameters. Shaded ATA areas are indicative zones, not component locations. Not an OEM drawing; not engineering data.',
  K: 14, L: 57, R: 2.88, noseLen: 7.4, tailStart: 42.5, tailHalf: 0.4, span: 60, leRoot: 19.8, sweep: 32, rootChord: 10.4,
  kinkFrac: 0.3, kinkChord: 6.2, tipChord: 1.7, rake: 4.6, eng: 9.7, nacLen: 6.6, nacR: 1.6, nacFwd: 4.0,
  hsSpan: 19.6, hsLe: 47.6, hsSweep: 34, hsRoot: 5.0, hsTip: 1.7, finLe: 44.8, finRoot: 9.6,
  nlg: { w: 1.3, y0: 4.9, y1: 9.4 }, mlg: { x0: 0.4, x1: 2.6, y0: 27.6, y1: 32.0, legX: 6.4 },
  sections: [8.4, 15.6, 33.2, 42.8, 50.6],
  zones: (u) => {
    const { pt, rr, leY, chordAt, teY, semi, R, hsChord, hsTeY, hsHalf, hsX0, nlg, mlg, rootTE, leRoot, L } = u;
    const ell = (cx, cy, rx, ry) => el('ellipse', { cx: u.X(cx), cy: u.Y(cy), rx: rx * 14, ry: ry * 14 });
    const ail0 = R + (semi - R) * 0.72 + 0.25, ail1 = semi * 0.84;
    const ailZ = (s) => `M${pt(s * ail0, chordAt(ail0, 0.7))}L${pt(s * ail1, chordAt(ail1, 0.7))}L${pt(s * ail1, teY(ail1) + 0.2)}L${pt(s * ail0, teY(ail0) + 0.2)}Z`;
    const elevZ = (s) => `M${pt(s * hsX0 * 1.1, hsChord(hsX0 * 1.1, 0.62))}L${pt(s * hsHalf * 0.95, hsChord(hsHalf * 0.95, 0.62))}L${pt(s * hsHalf * 0.95, hsTeY(hsHalf * 0.95) + 0.2)}L${pt(s * hsX0 * 1.1, hsTeY(hsX0 * 1.1) + 0.2)}Z`;
    void leY;
    return [
      { ata: '34', name: 'NAVIGATION', sub: 'RADOME · AVIONICS', side: 'L', calloutY: 150, badge: [0, 2.6], shapes: [ell(0, 2.2, 1.8, 2.0)], zoneLabelDy: -36 },
      { ata: '24', name: 'ELECTRICAL POWER', sub: 'E/E BAYS', side: 'R', calloutY: 250, badge: [0, 11.6], shapes: [rr(-1.8, 9.9, 1.8, 13.4, 0.8)] },
      { ata: '21', name: 'AIR CONDITIONING', sub: 'PACKS · BELLY', side: 'L', calloutY: 345, badge: [0, leRoot - 2.0], shapes: [rr(-2.5, leRoot - 4.4, 2.5, leRoot + 0.6, 1.0)] },
      // no bleed-system callout on this archetype: a generic pneumatic zone at the wing-to-body fairing
      { ata: '36', name: 'PNEUMATIC', sub: 'WING-TO-BODY FAIRING', side: 'L', calloutY: 470, badge: [-(R + 2.6), leRoot + 3.0], shapes: [rr(-(R + 3.8), leRoot + 1.4, -(R + 0.8), leRoot + 4.6, 0.8), rr(R + 0.8, leRoot + 1.4, R + 3.8, leRoot + 4.6, 0.8)], zoneLabelDy: -30 },
      { ata: '32', name: 'LANDING GEAR', sub: 'NLG + MLG BAYS', side: 'L', calloutY: 640, badge: [-1.6, (mlg.y0 + mlg.y1) / 2], shapes: [rr(-nlg.w / 2 - 0.3, nlg.y0 - 0.3, nlg.w / 2 + 0.3, nlg.y1 + 0.3, 0.5), rr(-mlg.x1 - 0.4, mlg.y0 - 0.4, mlg.x1 + 0.4, mlg.y1 + 0.4, 0.8)] },
      { ata: '29', name: 'HYDRAULIC POWER', sub: 'BAYS AFT OF THE MLG', side: 'R', calloutY: 640, badge: [0, rootTE + 3.6], shapes: [rr(-2.0, rootTE + 1.6, 2.0, rootTE + 5.6, 0.8)] },
      { ata: '27', name: 'FLIGHT CONTROLS', sub: 'AILERONS · ELEVATORS · RUDDER', side: 'R', calloutY: 520, badge: [(ail0 + ail1) / 2, (chordAt((ail0 + ail1) / 2, 0.7) + teY((ail0 + ail1) / 2)) / 2], shapes: [ailZ(-1), ailZ(1), elevZ(-1), elevZ(1)], zoneLabelDy: 32 },
      { ata: '49', name: 'AIRBORNE APU', sub: 'TAILCONE', side: 'L', calloutY: 860, badge: [0, L - 3.0], shapes: [ell(0, L - 2.3, 0.75, 2.1)], zoneLabelDy: 34 },
    ];
  },
};

export function files() {
  return { 'aircraft-narrowbody.svg': plan(NB), 'aircraft-widebody.svg': plan(WB) };
}
