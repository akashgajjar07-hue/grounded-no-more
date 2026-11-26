"""Planner Action Centre: planted situations surface, severity rules, schema."""
import json

import pytest

from gnm.aog import actions as A
from gnm.aog.data import HISTORY_DIR
from gnm.schemas import validate_table

needs_history = pytest.mark.skipif(not (HISTORY_DIR / "aog_events.parquet").exists(), reason="history not built")


# ---- severity rules on fixtures --------------------------------------------------------------
def test_severity_rules():
    assert A.severity_kit(1) == "urgent" and A.severity_kit(2) == "review"
    assert A.severity_overdue(10.3, 5, "D3") == "urgent"          # > 4 weeks late
    assert A.severity_overdue(1.0, 0, "D3") == "urgent"           # nothing serviceable in the network
    assert A.severity_overdue(1.0, 1, "D0") == "urgent"           # D0 part with a single spare left
    assert A.severity_overdue(1.0, 3, "D3") == "review"
    assert A.severity_condemn(0, False) == "urgent"
    assert A.severity_condemn(2, True) == "review"
    assert A.severity_condemn(2, False) == "info"
    assert A.severity_depletion(0, 63.0) == "urgent"
    assert A.severity_depletion(0, 0.0) == "review"
    assert A.severity_depletion(1, 50.0) == "review"
    assert A.severity_lead_drift(2.4) == "urgent"
    assert A.severity_lead_drift(1.6) == "review"
    assert A.severity_lead_drift(1.2) is None
    assert A.severity_excess(0.5, 40) == "review"
    assert A.severity_excess(0.5, 10) is None                     # declining but not excess
    assert A.severity_excess(0.9, 80) is None                     # excess but not declining


@pytest.fixture(scope="module")
def actions():
    from gnm.aog.data import default_view
    return A.generate_actions(default_view()), default_view()


def _planted(view, ps):
    pm = view.t["part_master"]
    return pm[pm.planted == ps].pn.iloc[0]


@needs_history
def test_ps1_outstation_depletion_bom(actions):
    df, view = actions
    pn = _planted(view, "PS1")
    hit = df[(df.type == "OUTSTATION_DEPLETION") & (df.pn == pn) & (df.station == "BOM")]
    assert len(hit) == 1 and hit.severity.iloc[0] == "urgent"
    ev = hit.evidence.iloc[0]
    assert ev["p0_target"] == 0 and ev["target"] >= 1 and ev["on_hand"] == 0


@needs_history
def test_ps2_overdue_repair(actions):
    df, view = actions
    pn = _planted(view, "PS2")
    hit = df[(df.type == "OVERDUE_REPAIR") & (df.pn == pn)]
    assert len(hit) >= 1
    longest = hit.loc[hit.evidence.map(lambda e: e["weeks_overdue"]).idxmax()]
    assert longest.severity == "urgent" and longest.evidence["shop"] == "EU_VENDOR"
    assert longest.evidence["removed_week"] == 84
    assert longest.owner == "Repair & warranty administrator"


@needs_history
def test_ps3_declining_demand_excess(actions):
    df, view = actions
    pn = _planted(view, "PS3")
    hit = df[(df.type == "EXCESS_DECLINING_DEMAND") & (df.pn == pn)]
    assert len(hit) == 1
    ev = hit.evidence.iloc[0]
    assert ev["ratio"] < 0.75 and ev["cover_weeks_at_recent_rate"] > 26


@needs_history
def test_ps4_lead_time_drift(actions):
    df, view = actions
    pn = _planted(view, "PS4")
    hit = df[(df.type == "LEAD_TIME_DRIFT") & (df.pn == pn)]
    assert len(hit) == 1
    ev = hit.evidence.iloc[0]
    assert ev["ratio"] >= 1.5 and ev["mean_lead_d"] > ev["master_quoted_lead_d"]


@needs_history
def test_quarantine_is_simulated_and_deterministic(actions):
    df, view = actions
    q = df[df.type == "QUARANTINE_DOCS"]
    assert len(q) >= 1
    assert all(e["simulated"] and e["provenance"] == "SIMULATED" for e in q.evidence)
    assert all(s.startswith("SIMULATED") for s in q.summary)
    again = A.generate_actions(view)
    assert again[again.type == "QUARANTINE_DOCS"].summary.tolist() == q.summary.tolist()


@needs_history
def test_schema_and_fields(actions):
    df, _ = actions
    tab = A.to_table(df)
    assert validate_table("planner_exceptions", tab) == []
    assert df.exception_id.is_unique
    assert set(df.severity) <= {"urgent", "review", "info"}
    assert (df.due_week > df.week).all() and (df.week == 103).all()
    for r in df.itertuples():
        assert r.severity_icon == A.SEVERITY_ICON[r.severity]
        assert r.owner in {"Materials planner", "Repair & warranty administrator", "AOG desk", "Stores / quality"}
        json.dumps(r.evidence)
    # severities follow the published rules
    for r in df[df.type == "OVERDUE_REPAIR"].itertuples():
        e = r.evidence
        assert r.severity == A.severity_overdue(e["weeks_overdue"], e["network_serviceable"], e["deadline_class"])
    for r in df[df.type == "OUTSTATION_DEPLETION"].itertuples():
        e = r.evidence
        assert r.severity == A.severity_depletion(e["on_hand"] + e["inbound"], e["aog_hours_lookback"])


@needs_history
def test_actions_use_history_weeks_only(actions):
    _, view = actions
    proj = A.project_kits(view, 104 * 168, 3)
    assert proj.empty or (proj.due_h >= 104 * 168).all()
    assert view.t["material_requests"].need_h.max() < 104 * 168
