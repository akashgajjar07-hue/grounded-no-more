/**
 * 05 · Network Positioning — placeholder by design-system (screen agent will extend).
 * Data: network.json
 * Deep links: #/network?station=BOM
 * Shows: hub-and-spoke map (REAL coordinates), station table, transfer replay.
 */
import { h, pageHead, card, provChip, pill, dataTable, icon, stubNote } from '../ui.js';
import { renderNetworkMap } from '../charts/map.js';
import { fmtAED, fmtInt, fmtPct } from '../charts/theme.js';

export const data = ['network'];

export async function render(el, ctx) {
  const { network: n } = ctx.data;
  let alive = true;
  el.append(pageHead({ num: '05', eyebrow: 'Network Positioning', title: 'Where the stock sits, and how fast it can move', lede: 'AUH supports six outstations. Arc weight shows transfer volume; hover an arc for the AOG transport time. Station coordinates are real (OurAirports); the network activity is simulated.', meta: [provChip('REAL'), provChip('SIMULATED')] }));

  const mapHost = h('div', { style: { minHeight: '260px' } });
  const replayBtn = h('button', { class: 'btn btn--sm', type: 'button' }, icon('play'), 'Replay transfers');
  const stationInfo = h('div', { class: 'faint t-12 mono' }, 'Select a station');
  el.append(card({ bp: true, story: 'map', kicker: 'Hub-and-spoke network', title: 'Seven stations, one hub', actions: replayBtn, body: [mapHost, h('div', { class: 'row-between mt-2' }, stationInfo, h('div', { class: 'legend-inline' }, h('span', {}, h('i', { style: { color: '#22C7B8' } }), 'Routine'), h('span', {}, h('i', { style: { color: '#C47F52' } }), 'Emergency')))], prov: 'SIMULATED' }));

  const show = (id) => { const s = n.stations.find((x) => x.station === id); if (s) stationInfo.textContent = `${s.station} · ${s.name} · ${fmtInt(s.serviceable_units)} serviceable · ${fmtAED(s.stock_value)}`; ctx.setParams({ station: id }); };
  const map = await renderNetworkMap(mapHost, { stations: n.stations, arcs: n.arcs, selected: ctx.params.station, onSelect: show, labelSub: (s) => (s.role === 'hub' ? 'HUB' : `${s.serviceable_units} u`) });
  if (ctx.params.station) show(ctx.params.station);
  replayBtn.addEventListener('click', async () => {
    replayBtn.disabled = true;
    for (const e of n.transfer_replay.events.slice(0, 8)) { if (!alive) break; await map.animateTransfer(e.from, e.to, { kind: e.kind, duration: 900 }); }
    replayBtn.disabled = false;
  });

  el.append(h('div', { class: 'mt-3' }, card({ kicker: 'Stations', title: 'Stock and exposure by station', prov: 'SIMULATED', body: dataTable({ caption: 'Stations', columns: [{ key: 'station', label: 'Station', mono: true }, { key: 'role', label: 'Role' }, { key: 'serviceable_units', label: 'Serviceable', num: true, format: fmtInt }, { key: 'stock_value', label: 'Stock value', num: true, format: (v) => fmtAED(v) }, { key: 'requests', label: 'Requests', num: true, format: fmtInt }, { key: 'risk', label: 'Risk', render: (s) => pill(s.risk > 0.66 ? 'urgent' : s.risk > 0.33 ? 'review' : 'ok', fmtPct(s.risk, 0)) }], rows: n.stations, sort: { key: 'risk', dir: 'desc' }, onRowClick: (s) => { map.select(s.station); show(s.station); } }) })));
  el.append(h('div', { class: 'mt-4' }, stubNote('Placeholder: policy comparison per station and the full transfer replay timeline arrive with the Network screen agent.')));
  return () => { alive = false; map.destroy(); };
}
