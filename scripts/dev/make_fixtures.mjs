// Generates LAYOUT FIXTURES for every export named in docs/data_contract.md §5.
//   node docs/design/make_fixtures.mjs
// Values are placeholder-shaped (deterministic pseudo-random), NOT model output and NOT
// real aviation data. Every file carries meta.fixture = true so the UI shows "FIXTURE DATA".
// Fixtures must never ship: delete docs/data/fixtures/ once real exports exist.
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'data', 'fixtures');
mkdirSync(OUT, { recursive: true });

// mulberry32 — deterministic
let seed = 20261126;
const rnd = () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const pick = (a) => a[Math.floor(rnd() * a.length)];
const between = (a, b) => a + rnd() * (b - a);
const logU = (a, b) => Math.exp(between(Math.log(a), Math.log(b)));
const r1 = (v) => Math.round(v * 10) / 10;
const r2 = (v) => Math.round(v * 100) / 100;
const r3 = (v) => Math.round(v * 1000) / 1000;
const poisson = (lam) => { let L = Math.exp(-lam), k = 0, p = 1; do { k++; p *= rnd(); } while (p > L); return k - 1; };

const meta = (provenance, notes) => ({
  generated_at: '2026-11-26T00:00:00Z',
  git_sha: 'fixture',
  provenance,
  source: 'docs/design/make_fixtures.mjs',
  notes: `FIXTURE — layout placeholder, not model output. ${notes || ''}`.trim(),
  fixture: true,
});
const write = (name, obj) => { writeFileSync(join(OUT, `${name}.json`), JSON.stringify(obj, null, 1) + '\n'); console.log('wrote', name); };

const STATIONS = {
  AUH: { name: 'Abu Dhabi International', lat: 24.433, lon: 54.6511, role: 'hub' },
  LHR: { name: 'London Heathrow', lat: 51.4706, lon: -0.4619, role: 'outstation' },
  FRA: { name: 'Frankfurt am Main', lat: 50.0333, lon: 8.5706, role: 'outstation' },
  CAI: { name: 'Cairo International', lat: 30.1219, lon: 31.4056, role: 'outstation' },
  JED: { name: 'King Abdulaziz International, Jeddah', lat: 21.6796, lon: 39.1565, role: 'outstation' },
  BOM: { name: 'Chhatrapati Shivaji Maharaj International, Mumbai', lat: 19.0887, lon: 72.8679, role: 'outstation' },
  SIN: { name: 'Singapore Changi', lat: 1.3644, lon: 103.9915, role: 'outstation' },
};
const ATA = { 21: 'Air conditioning & pressurisation', 24: 'Electrical power', 27: 'Flight controls', 29: 'Hydraulic power', 32: 'Landing gear', 34: 'Navigation', 36: 'Pneumatic', 49: 'Airborne auxiliary power (APU)', 28: 'Fuel', 30: 'Ice & rain protection', 33: 'Lights', 35: 'Oxygen', 38: 'Water & waste' };
const ATA_W = { 21: 0.11, 24: 0.1, 27: 0.1, 29: 0.1, 32: 0.13, 34: 0.11, 36: 0.09, 49: 0.08, 28: 0.04, 30: 0.04, 33: 0.04, 35: 0.03, 38: 0.03 };
const NAMES = {
  R: { 21: ['Pack flow control valve', 'Air cycle machine', 'Pack temperature controller', 'Cabin pressure controller'], 24: ['AC generator', 'Generator control unit', 'Transformer rectifier unit', 'Static inverter'], 27: ['Aileron power control unit', 'Spoiler actuator', 'Elevator servo actuator', 'Flight control module'], 29: ['Engine-driven pump', 'Electric motor pump', 'Hydraulic accumulator', 'Power transfer unit'], 32: ['Main wheel assembly', 'Carbon brake assembly', 'Retraction actuator', 'Brake control unit'], 34: ['Air data inertial ref unit', 'Multi-mode receiver', 'Weather radar transceiver', 'Radio altimeter'], 36: ['High-pressure bleed valve', 'Pressure-reg. shutoff valve', 'Bleed precooler', 'Bleed monitoring computer'], 49: ['APU starter-generator', 'APU fuel control unit', 'APU electronic control box', 'Inlet door actuator'], 28: ['Fuel boost pump'], 30: ['Window heat controller'], 33: ['Landing light assembly'], 35: ['Crew oxygen regulator'], 38: ['Vacuum generator'] },
  E: { 21: ['Pack outlet temp sensor', 'Recirculation fan filter'], 24: ['Bus power contactor', 'Circuit breaker assy'], 27: ['Rod-end bearing kit', 'Position transducer (LVDT)'], 29: ['Pressure filter module', 'Pressure transducer'], 32: ['Brake temperature sensor', 'Gear proximity sensor', 'Tyre (main)'], 34: ['GNSS antenna', 'Pitot probe'], 36: ['Bleed check valve', 'Duct clamp (V-band)'], 49: ['Igniter plug', 'APU oil filter'], 28: ['Fuel quantity probe'], 30: ['Wiper blade'], 33: ['Strobe lamp'], 35: ['Mask stowage box'], 38: ['Drain mast heater'] },
  C: { 21: ['O-ring kit, pack', 'Filter element, cabin'], 24: ['Connector seal kit', 'Lamp, indicator'], 27: ['Cotter pin pack', 'Grease cartridge'], 29: ['Hydraulic fluid (US gal)', 'Seal kit, actuator'], 32: ['Brake wear pin', 'Tyre valve core pack'], 34: ['Static port plug set', 'Antenna gasket'], 36: ['Duct gasket', 'Clamp liner'], 49: ['APU oil (qt)', 'Chip detector seal'], 28: ['Fuel filter element'], 30: ['Rain repellent'], 33: ['Lens gasket'], 35: ['Oxygen mask valve kit'], 38: ['Toilet seal kit'] },
};
const ataKeys = Object.keys(ATA_W);
const pickAta = () => { let x = rnd(), acc = 0; for (const k of ataKeys) { acc += ATA_W[k]; if (x <= acc) return k; } return '21'; };

// ------------------------------------------------------------------ parts
const parts = [];
const counters = {};
const COST = { C: [20, 500], E: [500, 15000], R: [15000, 500000] };
const DCLS = ['smooth', 'erratic', 'intermittent', 'lumpy', 'insufficient_data'];
for (const [cls, count] of [['C', 45], ['E', 35], ['R', 40]]) {
  for (let i = 0; i < count; i++) {
    const ata = pickAta();
    const key = `${ata}-${cls}`;
    counters[key] = (counters[key] || 0) + 1;
    const pn = `GN-${ata}-${cls}${String(counters[key]).padStart(3, '0')}`;
    const desc = pick(NAMES[cls][ata]);
    const deadline = cls === 'R' ? pick(['D0', 'D0', 'D3', 'D3', 'D10']) : cls === 'E' ? pick(['D0', 'D3', 'D3', 'D10', 'D10']) : pick(['D3', 'D10', 'D10', 'D10']);
    const adi = r2(cls === 'C' ? between(1.0, 2.2) : between(1.4, 9));
    const cv2 = r2(between(0.15, 1.4));
    const demand_class = adi < 1.32 ? (cv2 < 0.49 ? 'smooth' : 'erratic') : cv2 < 0.49 ? 'intermittent' : 'lumpy';
    const by = {};
    let total = 0;
    for (const s of Object.keys(STATIONS)) { const q = s === 'AUH' ? Math.round(between(cls === 'C' ? 20 : 1, cls === 'C' ? 140 : 9)) : Math.round(rnd() < 0.55 ? between(0, cls === 'C' ? 30 : 3) : 0); by[s] = q; total += q; }
    const risk = r3(Math.min(0.99, Math.pow(rnd(), 1.7) * (deadline === 'D0' ? 1.25 : 0.85)));
    parts.push({ pn, desc, ata, cls, deadline, demand_class, adi, cv2, abc: '', stock_total: total, stock_by_station: by, risk_score: risk, risk_level: risk > 0.66 ? 'urgent' : risk > 0.33 ? 'review' : 'ok', unit_cost: Math.round(logU(...COST[cls])), planted: null, provenance: 'SIMULATED' });
  }
}
// ABC by annual value proxy
parts.slice().sort((a, b) => b.unit_cost * (3 / b.adi) - a.unit_cost * (3 / a.adi)).forEach((p, i, arr) => { p.abc = i < arr.length * 0.2 ? 'A' : i < arr.length * 0.5 ? 'B' : 'C'; });
// planted demo situations (labels only — mirrors config planted_situations)
const rot = parts.filter((p) => p.cls === 'R');
const r14 = rot.find((p) => p.ata === '32') || rot[0];
r14.pn = 'GN-32-R014'; r14.desc = 'Carbon brake assembly'; r14.planted = 'PS1'; r14.deadline = 'D0'; r14.risk_score = 0.91; r14.risk_level = 'urgent'; r14.stock_by_station = { AUH: 2, LHR: 0, FRA: 0, CAI: 0, JED: 0, BOM: 0, SIN: 0 }; r14.stock_total = 2;
const r27 = rot.find((p) => p.ata === '27' && p !== r14) || rot[1]; r27.planted = 'PS2'; r27.risk_score = 0.78; r27.risk_level = 'urgent';
const c36 = parts.find((p) => p.cls === 'C' && p.ata === '36') || parts[0]; c36.planted = 'PS3'; c36.risk_level = 'review'; c36.risk_score = 0.41;
const e = parts.find((p) => p.cls === 'E' && p.ata === '29') || parts[50]; e.planted = 'PS4'; e.risk_level = 'review'; e.risk_score = 0.55;
const ata_systems = Object.entries(ATA).map(([ata, name]) => { const ps = parts.filter((p) => p.ata === ata); return { ata, name, n_parts: ps.length, risk: r3(ps.length ? ps.reduce((m, p) => Math.max(m, p.risk_score), 0) : 0), n_urgent: ps.filter((p) => p.risk_level === 'urgent').length }; });
write('parts', { meta: meta('SIMULATED', '120 fictional part numbers.'), parts, ata_systems });

// ------------------------------------------------------------------ demand history
const series = {};
for (const p of parts) {
  const lam = p.cls === 'C' ? between(1.5, 9) : 1 / p.adi;
  const out = [];
  for (let w = 0; w < 104; w++) {
    let l = lam * (1 + 0.12 * Math.sin((w / 52) * Math.PI * 2 + 1));
    if (p.planted === 'PS3') l *= Math.max(0.15, 1 - w / 120);
    out.push(rnd() < (p.cls === 'C' ? 0.9 : 1 / p.adi) ? Math.max(0, poisson(Math.max(0.3, l * (p.cls === 'C' ? 1 : 1.4)))) : 0);
  }
  series[p.pn] = out;
}
write('demand_history', { meta: meta('SIMULATED', 'Weekly quantities, weeks 0–103.'), weeks: [0, 103], series });

// ------------------------------------------------------------------ KPIs + policies
const spark = (start, end, n = 26, noise = 0.02) => Array.from({ length: n }, (_, i) => r3(start + ((end - start) * i) / (n - 1) + (rnd() - 0.5) * noise * Math.abs(start || 1)));
const kpis = [
  { id: 'immediate_fill_rate', label: 'Immediate fill rate', value: 0.981, unit: '%', baseline: 0.947, recommended: 0.981, delta: 0.034, better: 'higher', provenance: 'SIMULATED', ci: [0.976, 0.985], target: 0.97, spark: spark(0.947, 0.981, 26, 0.01) },
  { id: 'aog_hours', label: 'AOG hours / year', value: 228, unit: 'h', baseline: 412, recommended: 228, delta: -184, better: 'lower', provenance: 'SIMULATED', ci: [196, 263], spark: spark(412, 228, 26, 0.06) },
  { id: 'spare_capital_aed', label: 'Spare capital', value: 44.6e6, unit: 'AED', baseline: 48.2e6, recommended: 44.6e6, delta: -3.6e6, better: 'lower', provenance: 'SIMULATED', ci: [43.9e6, 45.4e6], spark: spark(48.2e6, 44.6e6, 26, 0.004) },
  { id: 'total_annual_cost_aed', label: 'Total annual cost', value: 24.9e6, unit: 'AED', baseline: 31.5e6, recommended: 24.9e6, delta: -6.6e6, better: 'lower', provenance: 'SIMULATED', ci: [23.1e6, 26.8e6], spark: spark(31.5e6, 24.9e6, 26, 0.02) },
  { id: 'expedite_cost_aed', label: 'Expedite + AOG logistics', value: 1.9e6, unit: 'AED', baseline: 3.4e6, recommended: 1.9e6, delta: -1.5e6, better: 'lower', provenance: 'SIMULATED', ci: [1.6e6, 2.2e6], spark: spark(3.4e6, 1.9e6, 26, 0.05) },
  { id: 'open_exceptions', label: 'Open planner exceptions', value: 17, unit: '', baseline: 41, recommended: 17, delta: -24, better: 'lower', provenance: 'DERIVED', ci: null, spark: spark(41, 17, 26, 0.08).map(Math.round) },
];
write('kpis', { meta: meta('SIMULATED', 'Holdout KPI placeholders (P0 baseline vs recommended).'), split: 'holdout', kpis });

const POL = [['P0', 'Legacy rules (baseline)'], ['P1', 'Service-level targets'], ['P2', 'Multi-echelon optimised'], ['P3', 'P2 + pool exchange']];
const policies = POL.map(([id, label], i) => {
  const f = [0.947, 0.968, 0.981, 0.984][i], a = [412, 301, 228, 205][i], c = [48.2, 46.9, 44.6, 43.1][i] * 1e6, t = [31.5, 27.8, 24.9, 25.6][i] * 1e6;
  return { policy_id: id, label, kpi: { immediate_fill_rate: { mean: f, ci_lo: r3(f - 0.006), ci_hi: r3(f + 0.005) }, aog_hours: { mean: a, ci_lo: Math.round(a * 0.86), ci_hi: Math.round(a * 1.15) }, spare_capital_aed: { mean: c, ci_lo: c * 0.985, ci_hi: c * 1.016 }, total_annual_cost_aed: { mean: t, ci_lo: t * 0.93, ci_hi: t * 1.08 } }, provenance: 'SIMULATED' };
});
write('policies', { meta: meta('SIMULATED', '20 paired holdout seeds (placeholder).'), split: 'holdout', n_seeds: 20, policies });

// ------------------------------------------------------------------ forecast
const METHODS = ['Naive (last 4w mean)', 'Croston', 'SBA', 'TSB', 'ETS (ANN)', 'Reliability-exposure (FH/FC)'];
const leaderboard = [];
for (const dc of ['smooth', 'erratic', 'intermittent', 'lumpy']) for (const pc of ['C', 'E', 'R']) {
  const base = between(0.7, 1.3);
  METHODS.forEach((m, j) => { const mase = r3(base * (j === 0 ? 1.08 : j === 5 && pc !== 'C' ? 0.78 : between(0.82, 1.02))); leaderboard.push({ demand_class: dc, part_class: pc, method: m, mase, mase_ci: [r3(mase * 0.9), r3(mase * 1.1)], bias: r3(between(-0.25, 0.25)), pis: r2(between(2, 30)), coverage: r3(between(0.78, 0.95)), n: Math.round(between(4, 26)) }); });
}
const champions = [];
for (const dc of ['smooth', 'erratic', 'intermittent', 'lumpy']) for (const pc of ['C', 'E', 'R']) { const rows = leaderboard.filter((r) => r.demand_class === dc && r.part_class === pc).sort((a, b) => a.mase - b.mase); champions.push({ demand_class: dc, part_class: pc, method: rows[0].method, mase: rows[0].mase }); }
write('forecast', {
  meta: meta('DERIVED', 'Rolling-origin selection weeks 78–103 (placeholder).'),
  leaderboard, champions,
  stock_eval: METHODS.map((m, j) => ({ method: m, fill_rate: r3(0.93 + j * 0.008 + rnd() * 0.004), capital_aed: Math.round((47 - j * 0.5 + rnd()) * 1e6) })),
  truth_recovery: [{ param: 'MTBUR (rotables)', metric: 'median abs % error', vendor_quoted: 0.31, estimated: 0.12 }, { param: 'Line usage rate (consumables)', metric: 'median abs % error', vendor_quoted: null, estimated: 0.09 }, { param: 'Repair TAT mean', metric: 'median abs % error', vendor_quoted: 0.22, estimated: 0.08 }],
  monash: { status: 'not run', reason: 'Fixture placeholder: external benchmark not evaluated.' },
  ltd_example: { pn: 'GN-32-R014', lead_time_days: 60, dist: Array.from({ length: 9 }, (_, q) => ({ q, p: r3(Math.exp(-2.1) * Math.pow(2.1, q) / [1, 1, 2, 6, 24, 120, 720, 5040, 40320][q]) })) },
});

// ------------------------------------------------------------------ rotables
const shops = ['AUH_INHOUSE', 'EU_VENDOR'];
const repair_queue = Array.from({ length: 22 }, (_, i) => {
  const p = rot[i % rot.length];
  const shop_in_h = Math.round(between(17000, 17400));
  const start_h = shop_in_h + Math.round(between(0, 200));
  const due_h = start_h + Math.round(between(15, 90) * 24);
  const overdue = i === 2 || rnd() < 0.15;
  return { ro_id: `RO-${String(4100 + i)}`, serial: `${p.pn}-S${String(1000 + i * 7).padStart(4, '0')}`, pn: p.pn, shop: ['27', '32', '34', '49', '28', '30'].includes(p.ata) ? 'EU_VENDOR' : 'AUH_INHOUSE', shop_in_h, start_h, due_h, return_h: null, overdue };
});
repair_queue[2].pn = r27.pn; repair_queue[2].serial = `${r27.pn}-S0042`; repair_queue[2].shop = 'EU_VENDOR'; repair_queue[2].overdue = true;
write('rotables', {
  meta: meta('SIMULATED', 'Serial lifecycle counts and repair queue (placeholder).'),
  lifecycle: { states: ['SERVICEABLE', 'INSTALLED', 'REMOVED', 'IN_REPAIR', 'CONDEMNED'], counts: { SERVICEABLE: 96, INSTALLED: 412, REMOVED: 14, IN_REPAIR: 31, CONDEMNED: 6 }, flows: [{ from: 'SERVICEABLE', to: 'INSTALLED', count: 188 }, { from: 'INSTALLED', to: 'REMOVED', count: 191 }, { from: 'REMOVED', to: 'IN_REPAIR', count: 186 }, { from: 'IN_REPAIR', to: 'SERVICEABLE', count: 178 }, { from: 'IN_REPAIR', to: 'CONDEMNED', count: 6 }] },
  repair_queue,
  tat: rot.slice(0, 12).map((p) => { const q = Math.round(between(15, 60)); return { pn: p.pn, shop: shops[Math.round(rnd())], quoted_d: q, actual_mean_d: r1(q * between(0.95, 1.5)), p90_d: r1(q * between(1.4, 2.1)), n: Math.round(between(4, 30)) }; }),
  float_examples: [{ pn: 'GN-32-R014', station: 'BOM', current: 0, recommended: 1, reason: 'D0 exposure at outstation; 9 h AOG transfer from AUH' }, { pn: r27.pn, station: 'AUH', current: 2, recommended: 3, reason: 'Vendor TAT p90 well above quoted' }],
});

// ------------------------------------------------------------------ network
const stations = Object.entries(STATIONS).map(([station, s]) => ({ station, name: s.name, lat: s.lat, lon: s.lon, role: s.role, serviceable_units: s.role === 'hub' ? 74 : Math.round(between(3, 14)), stock_value: Math.round((s.role === 'hub' ? 31e6 : between(0.8, 3.6) * 1e6)), requests: Math.round(s.role === 'hub' ? 1210 : between(80, 420)), risk: r3(s.role === 'hub' ? 0.18 : between(0.2, 0.8)) }));
stations.find((s) => s.station === 'BOM').risk = 0.82;
const AOGH = { LHR: 16, FRA: 14, CAI: 11, JED: 9, BOM: 9, SIN: 13 };
const arcs = Object.keys(AOGH).map((to) => ({ from: 'AUH', to, aog_transport_h: AOGH[to], transfers: Math.round(between(8, 60)), emergency: Math.round(between(1, 12)) }));
write('network', {
  meta: meta('SIMULATED', 'Station coordinates are REAL (config/assumptions.yaml); everything else is placeholder.'),
  stations, arcs,
  transfer_replay: { window_h: [17472, 17640], events: Array.from({ length: 14 }, (_, i) => ({ t_h: 17472 + i * 12, from: 'AUH', to: pick(Object.keys(AOGH)), pn: pick(rot).pn, kind: rnd() < 0.3 ? 'emergency' : 'routine' })) },
  policy_compare: POL.flatMap(([id]) => Object.keys(STATIONS).map((s, j) => ({ policy_id: id, station: s, fill_rate: r3(0.9 + rnd() * 0.09), aog_hours: Math.round(between(5, 90)) }))),
});

// ------------------------------------------------------------------ frontier
const points = [];
for (let i = 0; i < 28; i++) {
  const cap = 38e6 + i * 0.55e6;
  const aog = Math.round(620 * Math.exp(-(cap - 38e6) / 6.5e6) + 120 + (rnd() - 0.5) * 18);
  points.push({ id: `F${String(i).padStart(2, '0')}`, budget_aed: cap, capital_aed: Math.round(cap - rnd() * 2e5), aog_hours: aog, aog_ci: [Math.round(aog * 0.86), Math.round(aog * 1.15)], dominated: false, kind: 'frontier' });
}
for (let i = 0; i < 26; i++) { const cap = between(39e6, 54e6); const aog = Math.round(620 * Math.exp(-(cap - 38e6) / 6.5e6) + 160 + rnd() * 220); points.push({ id: `D${String(i).padStart(2, '0')}`, budget_aed: cap, capital_aed: Math.round(cap), aog_hours: aog, aog_ci: [Math.round(aog * 0.85), Math.round(aog * 1.16)], dominated: true, kind: 'candidate' }); }
points.push({ id: 'BASE', budget_aed: 48.2e6, capital_aed: 48.2e6, aog_hours: 412, aog_ci: [352, 471], dominated: true, kind: 'baseline' });
const rec = points.find((p) => p.id === 'F12');
rec.kind = 'recommended';
write('frontier', {
  meta: meta('SIMULATED', 'Capital vs AOG-hours frontier (placeholder).'),
  points, baseline: 'BASE', recommended: rec.id,
  allocations: { [rec.id]: rot.slice(0, 10).map((p, i) => ({ pn: p.pn, station: pick(['AUH', 'BOM', 'LHR', 'SIN', 'JED']), current: Math.round(between(0, 3)), proposed: Math.round(between(0, 4)), delta_capital: Math.round((rnd() - 0.4) * p.unit_cost), risk_reduction: r1(between(2, 40)), alt_action: pick(['—', 'Pool exchange', 'Accelerate repair', 'Lateral from AUH']) })) },
  levers: [{ id: 'budget', label: 'Capital budget', min: 38e6, max: 54e6, step: 0.5e6, value: rec.budget_aed, unit: 'AED' }, { id: 'aog_penalty', label: 'AOG penalty multiplier', min: 0.5, max: 2, step: 0.5, value: 1, unit: '×' }, { id: 'carrying', label: 'Carrying cost', min: 0.15, max: 0.25, step: 0.01, value: 0.2, unit: '%/yr' }],
  tornado: [{ param: 'AOG penalty ×0.5 / ×2', low: -2.9e6, high: 5.8e6 }, { param: 'Repair TAT ±25%', low: -1.4e6, high: 2.1e6 }, { param: 'Carrying cost 15–25%', low: -1.1e6, high: 1.1e6 }, { param: 'Lead time ±25%', low: -0.6e6, high: 0.9e6 }, { param: 'Condemnation ±50%', low: -0.3e6, high: 0.5e6 }],
});

// ------------------------------------------------------------------ AOG lab
write('aog_lab', {
  meta: meta('SIMULATED', 'AOG response options for placeholder incidents.'),
  incidents: [
    { id: 'AOG-0193', tail: 'A6-FW07', pn: 'GN-32-R014', desc: 'Carbon brake assembly', station: 'BOM', deadline: 'D0', archetype: 'widebody', need_h: 17531,
      timeline: [{ t_h: 0, event: 'Defect raised on walkaround' }, { t_h: 1, event: 'No serviceable unit at BOM' }, { t_h: 2, event: 'Options evaluated' }, { t_h: 11, event: 'Unit arrives (AUH emergency)' }, { t_h: 14, event: 'Fitted, released' }],
      options: [
        { option: 'Emergency transfer from AUH', feasible: true, reason_codes: ['STOCK_AT_HUB'], wait_h: 11, direct_cost: 9200, exposure_aed: 330000, deadline_met: false },
        { option: 'Lateral from SIN', feasible: true, reason_codes: ['LATERAL_OK'], wait_h: 16, direct_cost: 12400, exposure_aed: 480000, deadline_met: false },
        { option: 'Pool exchange', feasible: false, reason_codes: ['NOT_CONTRACTED_P0'], wait_h: 24, direct_cost: 0, exposure_aed: 0, deadline_met: false },
        { option: 'Expedite purchase', feasible: true, reason_codes: ['LEAD_TIME_LONG'], wait_h: 960, direct_cost: 51000, exposure_aed: 28800000, deadline_met: false },
      ] },
    { id: 'AOG-0207', tail: 'A6-FH12', pn: 'GN-36-E004', desc: 'Bleed check valve', station: 'JED', deadline: 'D3', archetype: 'narrowbody', need_h: 17602,
      timeline: [{ t_h: 0, event: 'Fault isolated' }, { t_h: 3, event: 'Routine replenishment due in 40 h' }, { t_h: 43, event: 'Fitted within window' }],
      options: [
        { option: 'Wait for routine replenishment', feasible: true, reason_codes: ['WITHIN_WINDOW'], wait_h: 43, direct_cost: 150, exposure_aed: 0, deadline_met: true },
        { option: 'Emergency transfer from AUH', feasible: true, reason_codes: ['STOCK_AT_HUB'], wait_h: 9, direct_cost: 4100, exposure_aed: 0, deadline_met: true },
      ] },
  ],
});

// ------------------------------------------------------------------ actions
const TYPES = [['UNDERSTOCK_D0', 'urgent', 'Raise float at outstation'], ['OVERDUE_REPAIR', 'urgent', 'Chase vendor / accelerate repair'], ['EXCESS_STOCK', 'review', 'Reduce max; redistribute'], ['LEAD_TIME_SHIFT', 'review', 'Update planning lead time'], ['FORECAST_DRIFT', 'info', 'Review forecast champion']];
const actions = Array.from({ length: 17 }, (_, i) => {
  const [type, severity, act] = i < 2 ? TYPES[i] : i === 2 ? TYPES[2] : i === 3 ? TYPES[3] : pick(TYPES);
  const p = i === 0 ? r14 : i === 1 ? r27 : i === 2 ? c36 : i === 3 ? e : pick(parts);
  return { exception_id: `EX-${String(1040 + i)}`, week: 104 + Math.floor(i / 4), type, severity, pn: p.pn, station: i === 0 ? 'BOM' : pick(Object.keys(STATIONS)), summary: i === 0 ? `${p.pn} has no serviceable unit at BOM; D0 exposure on 2 fleets` : `${type.replace(/_/g, ' ').toLowerCase()} on ${p.pn}`, evidence: { risk_score: p.risk_score, deadline: p.deadline, stock_total: p.stock_total }, recommended_action: act, owner: pick(['Materials planner', 'Repair controller', 'Logistics lead']), due_week: 105 + Math.floor(i / 3) };
});
write('actions', { meta: meta('DERIVED', 'Planner exceptions (placeholder).'), actions });

// ------------------------------------------------------------------ method
write('method', {
  meta: meta('DERIVED', 'Method & provenance (placeholder).'),
  source_manifest: [
    { id: 'ourairports', name: 'OurAirports airport coordinates', url: 'https://ourairports.com/data/', licence: 'Public domain', used_for: 'Station lat/lon', provenance: 'REAL' },
    { id: 'naturalearth', name: 'Natural Earth 1:110m land (via world-atlas)', url: 'https://www.naturalearthdata.com/', licence: 'Public domain', used_for: 'Map basemap', provenance: 'REAL' },
    { id: 'generator', name: 'Synthetic world generator', url: '', licence: 'MIT (this repo)', used_for: 'Fleet, parts, demand, repairs', provenance: 'SIMULATED' },
  ],
  assumptions: [{ key: 'economics.carrying_cost_pct_per_year', value: '0.20', provenance: 'ASSUMED', rationale: 'Planning assumption; sensitivity-tested 15–25%.' }, { key: 'economics.aog_penalty_aed_per_hour.widebody', value: '30000', provenance: 'ASSUMED', rationale: 'Scenario value for decision-making.' }, { key: 'network.stations.*', value: '7 stations', provenance: 'REAL', rationale: 'OurAirports coordinates.' }],
  validation: { tests_passed: 0, tests_total: 0, checks: [{ name: 'Fixture placeholder — no validation run', status: 'unknown' }] },
  licences: [{ name: 'd3', version: '7.9.0', licence: 'ISC' }, { name: '@observablehq/plot', version: '0.6.16', licence: 'ISC' }, { name: 'topojson-client', version: '3.1.0', licence: 'ISC' }, { name: 'world-atlas', version: '2.0.2', licence: 'ISC (data: Natural Earth, public domain)' }, { name: 'Space Grotesk / Inter / IBM Plex Mono', version: '@fontsource 5.1.0', licence: 'SIL OFL 1.1' }],
});

// ------------------------------------------------------------------ story
write('story', {
  meta: meta('DERIVED', 'Story-mode steps (placeholder copy).'),
  steps: [
    { route: '#/mission', selector: '[data-story="kpis"]', title: 'Where the network stands', body: 'Four instruments summarise service, groundings, capital and cost — baseline policy versus the recommendation, each with its uncertainty.' },
    { route: '#/mission', selector: '[data-story="aircraft"]', title: 'Risk by aircraft system', body: 'Each ATA zone on the schematic glows by the share of high-risk part numbers it contains. Select one to open Parts Intelligence.' },
    { route: '#/parts', selector: '[data-story="parts-table"]', title: 'Part-level evidence', body: 'Demand class, stock by station and a risk score for every fictional part number.' },
    { route: '#/network', selector: '[data-story="map"]', title: 'Where the stock sits', body: 'The hub at AUH supports six outstations. Arcs show AOG transport times and transfer volumes.' },
    { route: '#/capital', selector: '[data-story="frontier"]', title: 'Capital versus groundings', body: 'Every dot is a stocking plan. The frontier shows the lowest AOG hours reachable for each capital level.' },
  ],
});
