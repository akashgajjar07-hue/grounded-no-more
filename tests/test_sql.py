"""Planner SQL (sql/*.sql): every query runs against the DuckDB history views and returns rows.

Also checks that the planted situations surface where the query comments say they do, and that each
file documents its question, assumptions and an example output block produced by sql/run_all.py.
Planted PNs and the PS1 station are read from metadata (part_master.planted and
outputs/holdout/truth_recovery.json), never hard-coded. Counts are reconciled with the history tables,
docs/data/*.json and outputs/aog_lab/incidents.json.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
DB = ROOT / "data" / "processed" / "grounded.duckdb"

pytestmark = pytest.mark.skipif(not DB.exists(), reason="run scripts/build_history.py first")


def _runner():
    spec = importlib.util.spec_from_file_location("sql_run_all", SQL_DIR / "run_all.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


@pytest.fixture(scope="module")
def runner():
    return _runner()


@pytest.fixture(scope="module")
def results(runner):
    out = {}
    with runner.connect() as con:
        for f in runner.query_files():
            out[f.stem] = runner.run_query(con, f)
    return out


@pytest.fixture(scope="module")
def db(runner):
    con = runner.connect()
    yield lambda q: con.execute(q).fetchone()[0]
    con.close()


@pytest.fixture(scope="module")
def planted(runner):
    """{PS1: pn, ...} from part_master.planted, plus the PS1 station from the planted metadata."""
    with runner.connect() as con:
        rows = con.execute("SELECT planted, pn FROM part_master WHERE planted IS NOT NULL AND planted <> ''").fetchall()
    meta = _json("outputs/holdout/truth_recovery.json")["planted"]
    pns = dict(rows)
    for k, v in meta.items():
        assert pns[k] == v["pn"], f"{k}: part_master and truth_recovery planted metadata disagree"
    return {**pns, "PS1_station": meta["PS1"]["station"]}


@pytest.fixture(scope="module")
def actions():
    return _json("docs/data/actions.json")["actions"]


def test_query_count():
    files = sorted(SQL_DIR.glob("[0-9][0-9]_*.sql"))
    assert len(files) == 12, [f.name for f in files]


@pytest.mark.parametrize("path", sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")), ids=lambda p: p.stem)
def test_query_documented(path):
    text = path.read_text()
    assert text.startswith("-- Question:")
    assert "-- Assumptions:" in text and "-- Provenance:" in text
    block = text.split("-- <<EXAMPLE>>", 1)[1].split("-- <</EXAMPLE>>", 1)[0]
    assert block.count("\n--") >= 2, "example block empty: run `python sql/run_all.py --update-examples`"
    assert "rows in total" in block or "row in total" in block


@pytest.mark.parametrize("path", sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")), ids=lambda p: p.stem)
def test_no_hard_coded_planted_pn(path, planted):
    head, _, rest = path.read_text().partition("-- <<EXAMPLE>>")
    body = rest.partition("-- <</EXAMPLE>>")[2]
    for k in ("PS1", "PS2", "PS3", "PS4"):
        assert planted[k] not in head + body, f"{path.name}: {k} PN typed in; read it from part_master.planted"


def test_examples_are_current(results):
    """Each example block's row count matches the current result (stale examples fail)."""
    for f in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        block = f.read_text().split("-- <<EXAMPLE>>", 1)[1].split("-- <</EXAMPLE>>", 1)[0]
        n = len(results[f.stem])
        assert f"({n} row{'s' if n != 1 else ''} in total" in block, f"{f.name}: rerun sql/run_all.py --update-examples"


def test_every_query_returns_rows(results):
    assert results
    empty = [k for k, df in results.items() if df.empty]
    assert not empty, empty


def test_ps1_outstation_d0(results, planted):
    pn, st = planted["PS1"], planted["PS1_station"]
    d0 = results["07_d0_outstation_no_stock"]
    first = d0.iloc[0]
    assert (first.pn, first.station, first.planted) == (pn, st, "PS1")
    assert first.share_without_stock == 1.0 and first.p0_base_stock == 0
    drivers = results["01_top_aog_drivers"]
    part = next(p for p in _json("docs/data/parts.json")["parts"] if p["pn"] == pn)
    assert drivers[drivers.pn == pn].aog_events.sum() == part["aog_events_hist"]
    top = drivers.iloc[0]
    assert (top.pn, top.station, top.planted) == (pn, st, "PS1")
    mt = results["10_removal_rate_vs_quoted"].iloc[0]
    assert mt.pn == pn and mt.quoted_vs_observed > 2.0


def test_ps2_overdue_and_replacement(results, planted, actions):
    ro = results["03_overdue_repair_orders"]
    over = ro[ro.status == "overdue_repair"]
    rep = ro[ro.status.str.startswith("replacement_po")]
    assert len(over) == _json("docs/data/rotables.json")["repair_summary"]["overdue"]
    assert set(over.ro_id) == {a["evidence"]["ro_id"] for a in actions if a["type"] == "OVERDUE_REPAIR"}
    assert set(rep.ro_id) == {a["evidence"]["ro_id"] for a in actions if a["type"] == "CONDEMNED_AWAITING_REPLACEMENT"}
    ps2 = planted["PS2"]
    assert (over.pn == ps2).sum() >= 1 and (rep.pn == ps2).sum() >= 1
    assert set(ro[ro.pn == ps2].planted) == {"PS2"}
    assert over.weeks_late.is_monotonic_decreasing


def test_ps3_ps4_surface(results, planted, actions):
    lt = results["05_lead_time_drift"].set_index("pn")
    ps4 = lt.loc[planted["PS4"]]
    assert ps4.planted == "PS4" and ps4.recent_vs_quoted >= 2.0
    drift = next(a for a in actions if a["type"] == "LEAD_TIME_DRIFT" and a["pn"] == planted["PS4"])
    assert ps4.recent_vs_quoted == pytest.approx(drift["evidence"]["ratio"], abs=0.01)
    ex = results["06_declining_demand_excess"]
    assert planted["PS3"] in set(ex.pn)
    assert set(ex.pn) == {a["pn"] for a in actions if a["type"] == "EXCESS_DECLINING_DEMAND"}


def test_totals_reconcile(results, db):
    fill = results["02_immediate_fill_station_class"]
    assert fill.requests.sum() == db("SELECT count(*) FROM material_requests")
    pipe = results["04_rotable_pipeline_by_shop"]
    assert pipe.in_repair.sum() == _json("docs/data/rotables.json")["lifecycle"]["counts"]["IN_REPAIR"]
    lanes = results["09_emergency_transfer_cost_by_lane"]
    assert lanes.emergency_transfers.sum() == db("SELECT count(*) FROM transfers WHERE kind = 'emergency'")


def test_aog_routes_reconcile(results, db):
    r = results["11_aog_recovery_routes"]
    tot = r[r.station == "ALL"].set_index("route")
    per = r[r.station != "ALL"].groupby("route").requests.sum()
    assert (tot.requests == per.reindex(tot.index)).all()
    assert set(tot.index) <= {"local_borrow", "robbery", "exchange_loan", "local_buy", "none"}
    assert (r[r.route == "robbery"].station == "ALL").sum() == 1 and set(r[r.route == "robbery"].station) <= {"ALL", "AUH"}
    assert (tot.loc["robbery", "approval_flagged"] == tot.loc["robbery", "requests"])
    br = results["12_brake_changes_sourced_at_notice"].groupby("sourced_as").planned_changes.sum()
    assert tot.loc["robbery", "requests"] + br.get("robbery", 0) == db("SELECT count(*) FROM aog_robberies")
    loans = tot.loc["exchange_loan", "requests"] + tot.loc["local_borrow", "requests"] + br.get("planned_loan", 0)
    assert loans == db("SELECT count(*) FROM aog_loans")
    assert (tot.median_wait_h >= 0).all()


def test_brakes_sourced_at_notice(results, db):
    b = results["12_brake_changes_sourced_at_notice"]
    assert b.planned_changes.sum() == db(
        "SELECT count(*) FROM removal_events JOIN part_master USING (pn) WHERE removal_mode = 'wear_planned'")
    covered = b[b.sourced_as.str.startswith("planned_")]
    assert covered.downtime_hours.sum() == 0
    assert covered.planned_changes.sum() / b.planned_changes.sum() > 0.9
    assert b.downtime_hours.sum() == pytest.approx(db(
        "SELECT coalesce(sum(hours), 0) FROM aog_events a JOIN part_master pm ON pm.pn = a.pns "
        "WHERE pm.removal_mode = 'wear_planned'"))
    assert (b.mean_notice_days.between(5, 10)).all()
