# Data contract

This is the contract every module and agent builds against. The code version lives in
[`src/gnm/schemas.py`](../src/gnm/schemas.py) (tables, enums, keys) and
[`src/gnm/contracts.py`](../src/gnm/contracts.py) (in-memory objects). Parameters live
in [`config/assumptions.yaml`](../config/assumptions.yaml). If this document and the
code disagree, the code wins and this document gets fixed.

## 1. Conventions

| Item | Rule |
|---|---|
| Time | Integer `*_h` = hours since simulated epoch `2023-01-02T00:00Z` (a Monday). `week = h // 168`. Simulated calendar, not real dates. UTC; the UI may show hub local time (UTC+4). |
| Money | AED, float, columns end `_aed`. **Capital** (value of spares owned) is never added to **annual operating cost**. |
| Quantities | int64, ≥ 0. Only `inventory_transactions.qty_delta` is signed. |
| Provenance | Every table has a provenance tag (`REAL`, `DERIVED`, `ASSUMED`, `SIMULATED`); every exported JSON object carries `"provenance"`. |
| IDs | PN `GN-<ATA>-<C|E|R><nnn>`; serial `<PN>-S<nnnn>`; tail `A6-FH?`/`A6-FW?` (fictional). |
| Storage | Parquet per table in `data/processed/<run>/` plus `data/processed/grounded.duckdb` (views over the Parquet files). |

## 2. Split calendar and seeds

| Block | Weeks | Use |
|---|---|---|
| Train | 0–77 | Fit forecasting models; estimate removal rates |
| Selection | 78–103 | Rolling-origin model selection (origins every 4 weeks, horizon 4 weeks) |
| Evaluation horizon (holdout) | 104–155 | Run **once** after freeze |
| Policy warm-up | 96–103 | Policy runs start at week 96; KPIs counted from week 104 |

| Seed | Value | Use |
|---|---|---|
| `world_seed` | 2023 | Master data + hidden ground truth |
| `history_seed` | 7 | The airline's realised history (weeks 0–103, run under policy P0). Its continuation (weeks 104–155) is the forecasting holdout, generated only after freeze. |
| `selection_seeds` | 100–119 | Tune policy parameters, pick frontier candidates |
| `holdout_seeds` | 1000–1019 | Final paired evaluation of frozen policies/candidates — run once |

**Freeze.** Before any holdout run, `scripts/freeze.py` writes `outputs/freeze/manifest.json`
holding SHA-256 hashes of: the forecasting champion table, every PolicySpec parameter table,
the frontier candidate set, and the config. The holdout runner refuses to run if the hashes
don't match, and `tests/test_freeze.py` checks this. Git history must show the freeze commit
before the holdout-results commit.

## 3. Module boundaries (leakage rule)

```
gnm.sim.generator ──reads──► gnm.sim.truth (GroundTruth)      writes data/ground_truth/*.parquet
gnm.sim.engine    (policy-agnostic event engine; never reads truth; runs any PolicySpec)
gnm.forecasting   ─┐
gnm.policy        ─┤  must NEVER import gnm.sim.truth / gnm.sim.generator internals
gnm.optim         ─┤  or open data/ground_truth   (tests/test_leakage.py scans the source)
gnm.aog           ─┤
gnm.export        ─┘
gnm.eval.truth_recovery  ← the ONLY consumer of data/ground_truth besides the generator
```

`generate_scenario()` lives in `gnm.sim.generator` and needs the truth. Downstream code gets
Scenarios through `gnm.sim.api.load_or_generate_scenario(seed, week_from, week_to)`, which
returns only the exogenous `Scenario`. A Scenario has unconstrained demand and pre-sampled
random numbers. It never contains true rates.

## 4. Engine semantics (gnm.sim.engine)

* Continuous time at hour resolution, with an event heap. Deterministic for a given (Scenario, PolicySpec).
* **Request lifecycle.** At `need_h` the engine tries local serviceable stock first. If none is available it sources by the policy's rules:
  1. emergency transfer from `emergency_sources[station]` in order (AUH first for P0/P1). Arrives after `aog_hours[from][to]`.
  2. lateral transfer from another outstation, if `lateral_transfers`.
  3. pool exchange, if `pool_exchange` is set (P3).
  4. otherwise a backorder: filled by the next receipt (repair return or PO). An expedite PO is raised if `expedite_purchase_on_aog`.
* **Deadline classes.** `D0`: the aircraft is AOG from `need_h` until fitted. `D3`/`D10`: AOG only from `need_h + 72/240 h` until fitted, if not fitted by then. Intervals are merged per aircraft, and `aog_events.hours` = merged duration.
* **Rotables (serialised).** Each serial is in exactly one state and location: `SERVICEABLE@station → INSTALLED@tail → REMOVED → IN_REPAIR@shop → SERVICEABLE@AUH` or `CONDEMNED`. The removed core travels to AUH (`removed_unit_return_days`), then to the shop (`vendor_transit_days_from_auh`). The shop queues work against `capacity_slots`, with work time `repair_days[removal_id] × repair_tat_multiplier[pn]`. Condemned if `condemn_flag[removal_id]`. **Note:** reality needs the true condemnation probability and true repair durations; they arrive **pre-sampled in the Scenario** (`condemn_flag`, `repair_days`), so the engine never touches truth. A condemnation triggers a replacement PO (lead time from `lead_time_days[pn]` stream).
  * Base stock: the network keeps each station at its `base_stock`. After a station issues a unit, AUH sends a routine replenishment if it has stock. Repair returns land at AUH.
* **Consumables/expendables (counts).** Continuous review on inventory position = on-hand + on-order + in-transit-in − backorders − reservations. When IP ≤ s, order up to S. Outstations replenish from AUH (routine transfer); AUH replenishes by PO. Scheduled kits reserve stock from `known_h`. Shelf-life items expire FIFO.
* **Conservation invariants** (tests): each serial has exactly one current state; per PN, `opening serials + purchased − condemned = closing serials`; for counts, `opening + receipts − issues − expiries ± transfers = closing`; every transfer debits its origin; repairs never create units.
* **KPIs** (window = evaluation weeks, annualised to 52 w): `immediate_fill_rate` = qty filled from local serviceable stock at need time ÷ requested qty; `aog_hours`; `spare_capital_aed` = time-average value (unit cost) of owned spares (serviceable anywhere + in transit + rotable units in the U/S + repair pipeline); annual `holding_cost_aed` = carrying % × spare capital; `repair_cost_aed`; `logistics_cost_aed`; `expedite_cost_aed`; `aog_penalty_aed` = AOG hours × penalty by archetype. Total annual cost = holding + repair + logistics + expedite + AOG penalty. Capital is reported separately and never summed into it.

## 5. Exports for the web app (`docs/data/*.json`)

Each file is `{ "meta": {generated_at, git_sha, provenance, source, notes}, ...payload }`, lazy-loaded per view, total < 4 MB. Every number shown in the UI must come from these files (`tests/test_reconciliation.py` recomputes the KPIs from `outputs/`).

| File | View(s) | Payload sketch |
|---|---|---|
| `kpis.json` | Mission Control | `kpis[]: {id, label, value, unit, baseline, recommended, delta, provenance, ci:[lo,hi]}` |
| `parts.json` | Parts Intelligence | `parts[]: {pn, desc, ata, cls, deadline, demand_class, adi, cv2, abc, stock_total, stock_by_station{}, risk_score, risk_level, unit_cost, planted}`, `ata_systems[]: {ata, name, n_parts, risk}` |
| `demand_history.json` | Parts drill-down, Forecast Lab | `series{pn: [weekly qty × 104]}` (training+selection only) |
| `forecast.json` | Forecast Lab | `leaderboard[]: {demand_class, part_class, method, mase, mase_ci, bias, pis, coverage, n}`, `champions[]`, `stock_eval[]`, `truth_recovery[]`, `monash{...} or {status:"not run", reason}`, `ltd_example{pn, dist[]}` |
| `rotables.json` | Rotable & Repair | `lifecycle{states[], flows[]: {from, to, count}}`, `repair_queue[]: {ro_id, serial, pn, shop, shop_in_h, start_h, due_h, return_h, overdue}`, `tat[]`, `float_examples[]` |
| `network.json` | Network Positioning | `stations[]: {station, lat, lon, role, serviceable_units, stock_value, requests, risk}`, `arcs[]`, `transfer_replay{...}`, `policy_compare[]` |
| `frontier.json` | Capital Optimiser | `points[]: {id, budget_aed, capital_aed, aog_hours, aog_ci:[lo,hi], dominated, kind}`, `baseline`, `recommended`, `allocations{point_id: [{pn, station, current, proposed, delta_capital, risk_reduction, alt_action}]}`, `levers[]`, `tornado[]` |
| `policies.json` | Mission Control, Network, Optimiser | `policies[]: {policy_id, label, kpi: {mean, ci_lo, ci_hi} per KPI}`, `split: "holdout"` |
| `aog_lab.json` | AOG Response Lab | `incidents[]: {id, tail, pn, station, deadline, timeline[], options[]: {option, feasible, reason_codes[], wait_h, direct_cost, exposure_aed, deadline_met}}` |
| `actions.json` | Planner Action Centre, Mission Control | `actions[]` (schemas.planner_exceptions + parsed evidence) |
| `method.json` | Data & Method | `source_manifest[]`, `assumptions[]`, `validation{tests_passed, tests_total, checks[]}`, `licences[]` |
| `story.json` | Story mode | `steps[]: {route, selector, title, body}` |

Until real exports exist, the design system uses **fixture** files under `docs/data/fixtures/`. Every fixture carries `"meta": {"fixture": true}`, and the UI shows a visible "FIXTURE DATA" chip when it loads one. Fixtures must never ship in the final build (`tests/test_site.py` checks this).
