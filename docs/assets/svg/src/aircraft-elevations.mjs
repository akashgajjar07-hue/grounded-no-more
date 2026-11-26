// Side and front elevations of the same GENERIC twin-engine airliner as the plan view.
// Original, archetypal geometry in metres (not any OEM type). Small companion drawings.
import { el, g, path, text, poly, n, svgDoc, dimension } from './lib.mjs';

const label = (x, y, a, b) => g({ class: 'bp-frameset' }, text(x, y, a, 'bp-t-ice'), text(x, y + 18, b, 'bp-t-xs'));

function note(x, y) {
  return text(x, y, 'SCHEMATIC — NOT ENGINEERING DATA', 'bp-t-warn', { 'text-anchor': 'end', class: 'bp-t-warn bp-frameset' });
}

// ------------------------------------------------------------------ side
export function side() {
  const W = 1200, H = 470, K = 16, X0 = 96, G = 392; // ground line y
  const X = (x) => X0 + x * K;
  const Z = (z) => G - z * K;
  const pt = (x, z) => `${n(X(x))},${n(Z(z))}`;
  const P = ([x, z]) => [X(x), Z(z)];
  const parts = [];

  parts.push(el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#bp-grid)', class: 'bp-gridfill' }));
  parts.push(path(`M${n(X(-3))},${n(G)}H${n(X(66))}`, 'bp-center'));
  parts.push(text(X(65.6), G - 6, 'GROUND LINE', 'bp-t-xs', { 'text-anchor': 'end' }));

  // far-side wing (phantom) and fin first, then fuselage
  const fin = `M${pt(47.2, 8.7)}L${pt(55.4, 17.4)}L${pt(58.6, 17.4)}L${pt(61.0, 8.0)}Z`;
  parts.push(path(fin, 'bp-skin'));
  parts.push(path(poly([[56.9, 17.2], [59.4, 8.3]].map(P)), 'bp-line')); // rudder hinge
  parts.push(path(poly([[50.2, 11.8], [59.3, 11.8]].map(P)), 'bp-panel'));

  // fuselage profile
  const fus =
    `M${pt(0, 5.2)}C${pt(0.25, 6.5)} ${pt(1.8, 7.7)} ${pt(3.7, 8.25)}C${pt(5.4, 8.75)} ${pt(7.6, 8.9)} ${pt(10.2, 8.9)}` +
    `L${pt(43, 8.9)}C${pt(50, 8.9)} ${pt(56, 8.15)} ${pt(61.6, 7.15)}L${pt(62.5, 6.95)}L${pt(62.5, 6.55)}` +
    `C${pt(56, 5.9)} ${pt(48.5, 3.2)} ${pt(40.5, 3.0)}L${pt(6, 3.0)}C${pt(2.6, 3.1)} ${pt(0.4, 4.0)} ${pt(0, 5.2)}Z`;
  parts.push(path(fus, 'bp-skin'));
  // cockpit windows
  parts.push(path(poly([[2.15, 7.45], [3.05, 8.02], [4.35, 8.38], [4.35, 7.62], [2.55, 7.25]].map(P), true), 'bp-line'));
  parts.push(path(poly([[3.3, 8.08], [3.3, 7.4]].map(P)), 'bp-panel'));
  // radome joint
  parts.push(path(`M${pt(1.25, 7.15)}C${pt(1.55, 6.0)} ${pt(1.55, 4.6)} ${pt(1.15, 3.75)}`, 'bp-panel'));
  // cabin windows
  for (let x = 9.2; x < 53; x += 1.02) {
    if (x > 18.6 && x < 19.9) continue;
    if (x > 48.4 && x < 50.1) continue;
    parts.push(el('rect', { x: X(x), y: Z(7.25), width: 0.32 * K, height: 0.48 * K, rx: 2, class: 'bp-panel' }));
  }
  // doors
  [6.6, 19.0, 33.4, 48.9].forEach((x) => parts.push(el('rect', { x: X(x), y: Z(7.7), width: 1.05 * K, height: 1.95 * K, rx: 3, class: 'bp-line' })));
  // production joints
  [10.9, 19.6, 39.0, 47.6].forEach((x) => parts.push(path(poly([[x, 8.9], [x, 3.0]].map(P)), 'bp-panel')));
  // cargo doors
  [[12.8, 15.4], [41.2, 43.6]].forEach(([a, b]) => parts.push(el('rect', { x: X(a), y: Z(4.8), width: (b - a) * K, height: 1.45 * K, rx: 2, class: 'bp-panel' })));
  // horizontal stabiliser (edge-on)
  parts.push(path(`M${pt(51.6, 7.5)}L${pt(60.6, 8.3)}L${pt(61.2, 8.05)}L${pt(55.6, 7.25)}Z`, 'bp-skin-2'));
  // wing (near side, dihedral up toward tip) + belly fairing
  parts.push(path(`M${pt(20.8, 3.2)}C${pt(23, 2.6)} ${pt(33, 2.5)} ${pt(39.4, 3.05)}`, 'bp-line'));
  parts.push(path(`M${pt(22.4, 4.15)}L${pt(40.2, 5.7)}L${pt(42.3, 5.82)}L${pt(42.0, 5.55)}L${pt(36.0, 4.2)}L${pt(28.5, 3.8)}Z`, 'bp-skin-2'));
  // engine: pylon, nacelle, core
  const NX = 22.3, NZ = 2.65;
  parts.push(path(`M${pt(NX + 1.6, NZ + 1.7)}L${pt(NX + 2.4, 4.6)}L${pt(NX + 8.4, 4.75)}L${pt(NX + 9.2, NZ + 1.0)}Z`, 'bp-skin-2'));
  parts.push(
    path(
      `M${pt(NX, NZ + 1.5)}C${pt(NX + 0.2, NZ + 1.82)} ${pt(NX + 1.2, NZ + 1.84)} ${pt(NX + 2.1, NZ + 1.84)}L${pt(NX + 4.6, NZ + 1.78)}C${pt(NX + 5.8, NZ + 1.7)} ${pt(NX + 6.6, NZ + 1.45)} ${pt(NX + 6.9, NZ + 1.25)}` +
        `L${pt(NX + 6.9, NZ - 1.25)}C${pt(NX + 6.6, NZ - 1.45)} ${pt(NX + 5.8, NZ - 1.7)} ${pt(NX + 4.6, NZ - 1.78)}L${pt(NX + 2.1, NZ - 1.84)}C${pt(NX + 1.2, NZ - 1.84)} ${pt(NX + 0.2, NZ - 1.82)} ${pt(NX, NZ - 1.5)}Z`,
      'bp-skin'
    )
  );
  parts.push(path(`M${pt(NX + 6.9, NZ + 1.1)}L${pt(NX + 9.2, NZ + 0.55)}L${pt(NX + 10.6, NZ)}L${pt(NX + 9.2, NZ - 0.55)}L${pt(NX + 6.9, NZ - 1.1)}`, 'bp-skin-2'));
  [2.4, 4.3].forEach((dx) => parts.push(path(poly([[NX + dx, NZ + 1.82], [NX + dx, NZ - 1.82]].map(P)), 'bp-panel')));
  parts.push(path(poly([[NX + 0.45, NZ + 1.6], [NX + 0.45, NZ - 1.6]].map(P)), 'bp-line'));
  parts.push(path(`M${pt(NX - 1.2, NZ)}L${pt(NX + 11.6, NZ)}`, 'bp-center'));
  // landing gear (extended)
  const wheel = (x, r = 0.62) => [el('circle', { cx: X(x), cy: Z(r), r: r * K, class: 'bp-skin-2' }), el('circle', { cx: X(x), cy: Z(r), r: r * 0.38 * K, class: 'bp-panel' })];
  parts.push(path(poly([[5.7, 3.05], [5.7, 0.62]].map(P)), 'bp-line'), path(poly([[5.9, 2.6], [6.6, 3.05]].map(P)), 'bp-panel'), ...wheel(5.7, 0.55));
  parts.push(path(poly([[34.7, 3.2], [34.7, 0.9]].map(P)), 'bp-line'), path(poly([[33.4, 0.66], [36.0, 0.66]].map(P)), 'bp-line'), path(poly([[34.9, 2.4], [36.2, 3.15]].map(P)), 'bp-panel'));
  parts.push(...wheel(33.4, 0.66), ...wheel(36.0, 0.66));
  // centreline
  parts.push(path(`M${pt(-1.5, 5.95)}L${pt(64, 5.95)}`, 'bp-center'));

  const dims = g(
    { class: 'bp-dims' },
    dimension({ x1: X(0), y1: G + 40, x2: X(62.5), y2: G + 40, label: 'LENGTH', ext: [[[X(0), Z(5.2) + 8], [X(0), G + 48]], [[X(62.5), Z(6.6) + 8], [X(62.5), G + 48]]] }),
    dimension({ x1: X(66.5), y1: Z(17.4), x2: X(66.5), y2: G, label: 'HEIGHT', vertical: true, ext: [[[X(58.6) + 8, Z(17.4)], [X(66.5) + 8, Z(17.4)]]] })
  );
  const body = [parts.join(''), dims, label(40, 46, 'SIDE ELEVATION · LH', 'GENERIC TWIN-ENGINE AIRLINER · SHEET 02'), note(W - 40, 46)];
  return svgDoc({ w: W, h: H, title: 'Blueprint side elevation of a generic twin-engine airliner', desc: 'Original schematic side view of a generic, fictional twin-engine airliner. Not an OEM drawing and not engineering data.', body: body.join(''), attrs: { class: 'bp-sheet' } });
}

// ------------------------------------------------------------------ front
export function front() {
  const W = 1000, H = 470, K = 14.4, CX = 500, G = 400;
  const X = (x) => CX + x * K;
  const Z = (z) => G - z * K;
  const pt = (x, z) => `${n(X(x))},${n(Z(z))}`;
  const P = ([x, z]) => [X(x), Z(z)];
  const parts = [];
  const both = (f) => [f(-1), f(1)];

  parts.push(el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#bp-grid)', class: 'bp-gridfill' }));
  parts.push(path(`M${n(X(-33))},${n(G)}H${n(X(33))}`, 'bp-center'));
  parts.push(path(`M${pt(0, -0.6)}L${pt(0, 19)}`, 'bp-center'));

  // fin (behind), horizontal stabiliser
  parts.push(path(`M${pt(-0.5, 8.6)}L${pt(-0.18, 17.4)}L${pt(0.18, 17.4)}L${pt(0.5, 8.6)}Z`, 'bp-skin-2'));
  parts.push(...both((s) => path(`M${pt(s * 1.4, 7.75)}L${pt(s * 9.7, 8.85)}L${pt(s * 9.7, 8.62)}L${pt(s * 1.4, 7.35)}Z`, 'bp-skin-2')));
  // wings with dihedral
  const wing = (s) => `M${pt(s * 2.2, 4.75)}L${pt(s * 27.3, 6.95)}C${pt(s * 28.6, 7.1)} ${pt(s * 29.3, 7.35)} ${pt(s * 29.55, 7.6)}L${pt(s * 29.55, 7.3)}L${pt(s * 27.2, 6.7)}L${pt(s * 2.4, 3.75)}Z`;
  parts.push(...both((s) => path(wing(s), 'bp-skin')));
  // engines
  const NX = 10.15, NZ = 2.7;
  parts.push(...both((s) => path(`M${pt(s * NX - 0.32, NZ + 1.7)}L${pt(s * NX - 0.3, 5.45)}L${pt(s * NX + 0.3, 5.5)}L${pt(s * NX + 0.32, NZ + 1.7)}Z`, 'bp-skin-2')));
  parts.push(...both((s) => el('circle', { cx: X(s * NX), cy: Z(NZ), r: 1.82 * K, class: 'bp-skin' })));
  parts.push(...both((s) => el('circle', { cx: X(s * NX), cy: Z(NZ), r: 1.48 * K, class: 'bp-line' })));
  parts.push(...both((s) => el('circle', { cx: X(s * NX), cy: Z(NZ), r: 0.36 * K, class: 'bp-line' })));
  // fan blades (radial, faint)
  parts.push(
    ...both((s) =>
      g(
        {},
        Array.from({ length: 22 }, (_, i) => {
          const a = (i / 22) * Math.PI * 2;
          const r0 = 0.42, r1 = 1.44;
          return path(`M${pt(s * NX + Math.cos(a) * r0, NZ + Math.sin(a) * r0)}Q${pt(s * NX + Math.cos(a + 0.18) * 0.95, NZ + Math.sin(a + 0.18) * 0.95)} ${pt(s * NX + Math.cos(a + 0.3) * r1, NZ + Math.sin(a + 0.3) * r1)}`, 'bp-panel');
        })
      )
    )
  );
  // landing gear
  const mlg = (s) => [
    path(poly([[s * 5.6, 4.0], [s * 5.6, 0.95]].map(P)), 'bp-line'),
    path(poly([[s * 5.6, 3.3], [s * 3.4, 3.05]].map(P)), 'bp-panel'),
    el('rect', { x: X(s * 5.6) - (s > 0 ? -0.15 * K : 0.67 * K) - (s > 0 ? 0 : 0), y: Z(1.32), width: 0.52 * K, height: 1.3 * K, rx: 3, class: 'bp-skin-2' }),
    el('rect', { x: X(s * 5.6) + (s > 0 ? -0.67 * K : 0.15 * K), y: Z(1.32), width: 0.52 * K, height: 1.3 * K, rx: 3, class: 'bp-skin-2' }),
  ];
  parts.push(...mlg(-1), ...mlg(1));
  parts.push(path(poly([[0, 3.0], [0, 0.8]].map(P)), 'bp-line'));
  [-0.42, 0.42].forEach((x) => parts.push(el('rect', { x: X(x) - 0.2 * K, y: Z(1.1), width: 0.4 * K, height: 1.1 * K, rx: 3, class: 'bp-skin-2' })));
  // fuselage cross-section
  parts.push(el('ellipse', { cx: X(0), cy: Z(5.95), rx: 2.9 * K, ry: 2.97 * K, class: 'bp-skin' }));
  parts.push(el('ellipse', { cx: X(0), cy: Z(5.45), rx: 1.55 * K, ry: 1.5 * K, class: 'bp-panel' }));
  // windscreen panels
  parts.push(path(poly([[-1.95, 7.3], [-0.12, 7.75], [-0.12, 8.35], [-1.7, 8.0]].map(P), true), 'bp-line'));
  parts.push(path(poly([[1.95, 7.3], [0.12, 7.75], [0.12, 8.35], [1.7, 8.0]].map(P), true), 'bp-line'));
  parts.push(path(poly([[-2.55, 7.0], [-2.1, 7.25], [-1.85, 7.95], [-2.3, 7.75]].map(P), true), 'bp-panel'));
  parts.push(path(poly([[2.55, 7.0], [2.1, 7.25], [1.85, 7.95], [2.3, 7.75]].map(P), true), 'bp-panel'));

  const dims = g(
    { class: 'bp-dims' },
    dimension({ x1: X(-29.55), y1: G + 40, x2: X(29.55), y2: G + 40, label: 'SPAN', ext: [[[X(-29.55), Z(7.3) + 8], [X(-29.55), G + 48]], [[X(29.55), Z(7.3) + 8], [X(29.55), G + 48]]] })
  );
  const body = [parts.join(''), dims, label(36, 46, 'FRONT ELEVATION', 'GENERIC TWIN-ENGINE AIRLINER · SHEET 03'), note(W - 36, 46)];
  return svgDoc({ w: W, h: H, title: 'Blueprint front elevation of a generic twin-engine airliner', desc: 'Original schematic front view of a generic, fictional twin-engine airliner. Not an OEM drawing and not engineering data.', body: body.join(''), attrs: { class: 'bp-sheet' } });
}

export function files() {
  return { 'blueprint-aircraft-side.svg': side(), 'blueprint-aircraft-front.svg': front() };
}
