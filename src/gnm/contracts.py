"""In-memory interfaces between modules (see docs/data_contract.md).

Module boundary (enforced by tests/test_leakage.py):
  gnm.sim.truth / data/ground_truth  -> ONLY gnm.sim.generator and gnm.eval.truth_recovery
  gnm.forecasting, gnm.policy, gnm.optim, gnm.aog, gnm.export  -> must NEVER import
  gnm.sim.truth or read data/ground_truth.

Flow:
  generate_world(cfg)                 -> (World, GroundTruth)
  generate_scenario(world, truth, seed, week_from, week_to) -> Scenario   (exogenous only)
  run_policy(world, scenario, PolicySpec, kpi_from_week, kpi_to_week) -> RunResult
Paired seeds: every policy is run against the SAME Scenario object (common random
numbers: repair durations, condemnation draws, lead-time draws are pre-sampled in
the Scenario, indexed by event / order sequence), so policy differences are not noise.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class World:
    """Public master data (what an airline's ERP knows). No hidden truth."""
    aircraft: pd.DataFrame          # schemas.aircraft_master
    stations: pd.DataFrame          # schemas.station_master
    parts: pd.DataFrame             # schemas.part_master
    applicability: pd.DataFrame     # schemas.part_applicability
    aog_hours: pd.DataFrame         # station x station AOG transport hours (index/cols = IATA)
    repair_shops: dict              # shop_id -> {location, capacity_slots, transit_days}
    cfg: dict                       # parsed config/assumptions.yaml


@dataclass
class Scenario:
    """Exogenous events for one seed and week range. Identical across policies."""
    seed: int
    week_from: int
    week_to: int                    # inclusive
    flights: pd.DataFrame           # schemas.flight_exposure
    maintenance: pd.DataFrame       # schemas.maintenance_schedule
    removals: pd.DataFrame          # schemas.removal_events
    requests: pd.DataFrame          # schemas.material_requests (outcome cols null)
    # common random numbers, pre-sampled:
    repair_days: dict = field(default_factory=dict)      # removal_id -> shop work days (float)
    condemn_flag: dict = field(default_factory=dict)     # removal_id -> bool (decided by generator from true condemnation prob)
    lead_time_days: dict = field(default_factory=dict)   # pn -> np.ndarray of successive PO lead times (days); engine consumes in order per pn
    transport_jitter: dict = field(default_factory=dict) # optional: stream of U(0,1) for routine transport


@dataclass
class PolicySpec:
    """A policy is a parameter table + network rules. One engine code path runs all.

    stock_params columns:
      pn, station,
      s (int, reorder point on inventory position; consumables/expendables; -1 = none),
      S (int, order-up-to; consumables/expendables),
      base_stock (int, rotable serviceable float target at that station; 0 for C/E)
    Rotable network float for a PN = sum of base_stock over stations (+ units in pipeline
    are generated at t0 so each station starts at target).
    """
    policy_id: str
    label: str
    stock_params: pd.DataFrame
    emergency_sources: dict = field(default_factory=dict)   # requesting station -> ordered list of allowed source stations
    lateral_transfers: bool = False      # allow outstation->outstation emergency sourcing
    rebalance: bool = False              # proactive return of excess outstation stock to hub
    expedite_purchase_on_aog: bool = True
    repair_tat_multiplier: dict = field(default_factory=dict)   # pn -> factor on shop work days (<1 = accelerated, costed)
    pool_exchange: Optional[dict] = None                         # P3 contract terms
    notes: str = ""


@dataclass
class RunResult:
    policy_id: str
    seed: int
    kpis: dict                       # keys == schemas.policy_results numeric columns
    requests: pd.DataFrame           # with outcome columns filled
    aog_events: pd.DataFrame
    inventory_transactions: pd.DataFrame
    repair_orders: pd.DataFrame
    purchase_orders: pd.DataFrame
    transfers: pd.DataFrame
    serial_history: pd.DataFrame     # schemas.serialised_components
    stock_snapshots: pd.DataFrame    # weekly: week, pn, station, on_hand, in_transit_in, backorders, pipeline (rotables)
