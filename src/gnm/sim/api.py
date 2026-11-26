"""Public entry points of the simulator.

Downstream modules (forecasting, policy, optim, aog, export) may import this module. It hands
out the public :class:`~gnm.contracts.World` and exogenous :class:`~gnm.contracts.Scenario`
objects only; the hidden ground truth stays inside the generator and is written to
``data/ground_truth`` solely by :func:`build_history` / :func:`write_ground_truth`.
"""
from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path

import pandas as pd

from gnm import schemas
from gnm.config import OUTPUTS, PROCESSED, assumption_register, load_config
from gnm.contracts import Scenario, World

CACHE = OUTPUTS / "cache"
HISTORY_DIR = PROCESSED / "history"
DUCKDB_PATH = PROCESSED / "grounded.duckdb"

HISTORY_TABLES = ["aircraft_master", "station_master", "part_master", "part_applicability", "flight_exposure",
                  "maintenance_schedule", "removal_events", "material_requests", "serialised_components",
                  "inventory_transactions", "repair_orders", "purchase_orders", "transfers", "aog_events",
                  "assumption_register"]


@lru_cache(maxsize=8)
def _world_and_truth(cfg_key: str, variant: str = "central"):
    from gnm.sim import generator
    return generator.generate_world(load_config(), variant=variant)


def _key() -> str:
    from gnm.sim.generator import config_hash
    return config_hash(load_config())


def load_world(variant: str = "central") -> World:
    """Public master data (no truth). Deterministic from world_seed and the config.
    Public data is identical across calibration variants; only the hidden truth differs."""
    return _world_and_truth(_key(), variant)[0]


def load_or_generate_scenario(seed: int, week_from: int, week_to: int, use_cache: bool = True,
                              variant: str = "central") -> Scenario:
    """Exogenous Scenario for (seed, weeks, variant). Cached as a pickle under outputs/cache/."""
    key = _key()
    path = CACHE / f"scenario_{key}_{variant}_{int(seed)}_{int(week_from)}_{int(week_to)}.pkl"
    if use_cache and path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    from gnm.sim import generator
    world, truth = _world_and_truth(key, variant)
    sc = generator.generate_scenario(world, truth, seed, week_from, week_to)
    if use_cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(sc, f, protocol=pickle.HIGHEST_PROTOCOL)
    return sc


def write_ground_truth() -> Path:
    """Write data/ground_truth/gt_part_truth.parquet (central) + gt_part_truth_<variant>.parquet + planted.json."""
    import json
    from gnm.sim.generator import VARIANTS
    world, truth = _world_and_truth(_key(), "central")
    p = truth.write()
    for v in VARIANTS[1:]:
        t = _world_and_truth(_key(), v)[1].table()
        t.to_parquet(p.parent / f"gt_part_truth_{v}.parquet", index=False)
    (p.parent / "planted.json").write_text(json.dumps(truth.planted, indent=2, default=str))
    return p


def _station_master(world: World) -> pd.DataFrame:
    return world.stations[schemas.TABLES["station_master"].colnames]


def history_tables(world: World, scenario: Scenario, result) -> dict[str, pd.DataFrame]:
    """Assemble the operational tables of a run in contract column order (extra columns kept at the end)."""
    def order(name, df):
        cols = schemas.TABLES[name].colnames
        return df[cols + [c for c in df.columns if c not in cols]].reset_index(drop=True)

    sh = result.serial_history
    t = {
        "aircraft_master": world.aircraft,
        "station_master": _station_master(world),
        "part_master": world.parts,
        "part_applicability": world.applicability,
        "flight_exposure": scenario.flights,
        "maintenance_schedule": scenario.maintenance,
        "removal_events": scenario.removals,
        "material_requests": result.requests,
        "serialised_components": sh,
        "inventory_transactions": result.inventory_transactions,
        "repair_orders": result.repair_orders,
        "purchase_orders": result.purchase_orders,
        "transfers": result.transfers,
        "aog_events": result.aog_events,
        "assumption_register": assumption_register(),
    }
    return {k: order(k, v) for k, v in t.items()}


def validate_all(tables: dict[str, pd.DataFrame]) -> list[str]:
    errs = []
    for name, df in tables.items():
        errs += schemas.validate_table(name, df)
    errs += schemas.validate_fks(tables)
    return errs


def build_history(out_dir: Path | None = None, duckdb_path: Path | None = None, verify_stations: bool = False) -> dict:
    """Run weeks 0–103 on history_seed under P0 and write every operational table.

    Writes Parquet files to data/processed/history/, DuckDB views to data/processed/grounded.duckdb,
    weekly stock snapshots (``stock_snapshots.parquet``, extra), and the hidden ground truth.
    Returns a summary dict."""
    from gnm.sim.baseline import build_p0
    from gnm.sim.engine import run_policy

    if verify_stations:
        from gnm.sim.generator import verify_station_coordinates
        verify_station_coordinates()
        _world_and_truth.cache_clear()
    cfg = load_config()
    out_dir = Path(out_dir or HISTORY_DIR)
    duckdb_path = Path(duckdb_path or DUCKDB_PATH)
    w0, w1 = cfg["calendar"]["history_weeks"]
    seed = int(cfg["seeds"]["history_seed"])
    world = load_world()
    sc = load_or_generate_scenario(seed, w0, w1)
    p0 = build_p0(world)
    res = run_policy(world, sc, p0, w0, w1)
    tables = history_tables(world, sc, res)
    errs = validate_all(tables)
    if errs:
        raise ValueError("history tables violate the contract:\n" + "\n".join(errs))
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
    res.stock_snapshots.to_parquet(out_dir / "stock_snapshots.parquet", index=False)
    # s/S renamed: DuckDB identifiers are case-insensitive
    p0.stock_params.rename(columns={"s": "reorder_point_s", "S": "order_up_to_S"}).to_parquet(
        out_dir / "policy_p0_stock_params.parquet", index=False)
    import duckdb
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    if duckdb_path.exists():
        duckdb_path.unlink()
    con = duckdb.connect(str(duckdb_path))
    for f in sorted(out_dir.glob("*.parquet")):
        con.execute(f"CREATE OR REPLACE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.resolve()}')")
    con.close()
    write_ground_truth()
    return {"tables": {k: len(v) for k, v in tables.items()}, "kpis": res.kpis, "out_dir": str(out_dir),
            "duckdb": str(duckdb_path)}
