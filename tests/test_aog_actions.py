"""Planner Action Centre (v2): planted situations surface, severity rules, schema, no invented data."""
import json

import pytest

from gnm.aog import actions as A
from gnm.aog.data import HISTORY_DIR
from gnm.schemas import validate_table

needs_history = pytest.mark.skipif(not (HISTORY_DIR / "aog_events.parquet").exists(), reason="history not built")


# ---- severity rules on fixtures --------------------------------------------------------------
def test_severity_rules():
    assert A.severity_kit(1) == "urgent" and A.severity_kit(2) == "review"
    assert A.severity_overdue(10.3, 5, "D3") == "urgent"
    assert A.severity_overdue(1.0, 0, "D3") == "urgent"
    assert A.severity_overdue(1.0, 1, "D0") == "urgent"
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
    assert A.severity_excess(0.5, 10) is None
    assert A.severity_excess(0.9, 80) is None
    assert A.severity_open_loan(20) == "urgent" and A.severity_open_loan(5) == "review"
    assert A.severity_donor(10) == "urgent" and A.severity_donor(3) == "review"
    assert A.severity_open_requirement("D0", -5) == "urgent"
    assert A.severity_open_requirement("D10", -5) == "review"
    assert A.severity_open_requirement("D10", 5) == "urgent"


@pytest.fixture(scope="module")
def actions():
    from gnm.aog.data import default_view
    v = default_view()
    return A.generate_actions(v), v


def _planted(view, ps):
    pm = view.t["part_master"]
    return pm[pm.planted == ps].pn.iloc[0]


@needs_history
def test_ps1_outstation_depletion(actions):
    df, view = actions
    pn = _planted(view, "PS1")
    from gnm.aog.incidents import ps1_station
    st = ps1_station(view, pn)                       # data-driven: the PS1 PN's worst outstation
    hit = df[(df.type == "OUTSTATION_DEPLETION") & (df.pn == pn) & (df.station == st)]
    assert len(hit) == 1 and hit.severity.iloc[0] == "urgent"
    r = hit.iloc[0]
    assert r.evidence["p0_target"] == 0 and r.evidence["target"] >= 1 and r.evidence["on_hand"] == 0
    assert r.source == view.net.hub and r.destination == st and r.quantity >= 1


@needs_history
def test_ps2_overdue_repair(actions):
    df, view = actions
    pn = _planted(view, "PS2")
    hit = df[(df.type == "OVERDUE_REPAIR") & (df.pn == pn)]
    assert len(hit) >= 1 and (hit.severity == "urgent").any()
    assert set(hit.owner) == {"Repair control"}
    assert all(e["shop"] == "EU_VENDOR" for e in hit.evidence)


@needs_history
def test_ps3_declining_demand_excess(actions):
    df, view = actions
    pn = _planted(view, "PS3")
    hit = df[(df.type == "EXCESS_DECLINING_DEMAND") & (df.pn == pn)]
    assert len(hit) == 1
    ev = hit.evidence.iloc[0]
    assert ev["ratio"] < 0.75 and ev["cover_weeks_at_recent_rate"] > 26
    assert hit.expected_benefit.iloc[0]["capital_above_26w_cover_aed"] > 0


@needs_history
def test_ps4_lead_time_drift(actions):
    df, view = actions
    pn = _planted(view, "PS4")
    hit = df[(df.type == "LEAD_TIME_DRIFT") & (df.pn == pn)]
    assert len(hit) == 1 and hit.owner.iloc[0] == "Procurement"
    ev = hit.evidence.iloc[0]
    assert ev["ratio"] >= 1.5 and ev["mean_lead_d"] > ev["master_quoted_lead_d"]


@needs_history
def test_no_simulated_documentation_exceptions(actions):
    df, _ = actions
    assert "QUARANTINE_DOCS" not in set(df.type)
    assert set(df.type) <= set(A.OWNER)
    assert not df.summary.str.contains("SIMULATED|certificate review", regex=True).any()


@needs_history
def test_v2_route_exceptions_match_history(actions):
    df, view = actions
    T = 104 * 168
    rb = view.t["aog_robberies"]
    open_rb = rb[(rb.robbed_h < T) & (rb.reinstated_h.isna() | (rb.reinstated_h >= T))]
    assert (df.type == "DONOR_NOT_REINSTATED").sum() == len(open_rb)
    ln = view.t["aog_loans"]
    open_ln = ln[(ln.start_h < T) & (ln.returned_h.isna() | (ln.returned_h >= T))]
    assert (df.type == "OPEN_LOAN").sum() == len(open_ln)
    for r in df[df.type == "DONOR_NOT_REINSTATED"].itertuples():
        assert any("engineering/quality approval" in c for c in r.constraints)


@needs_history
def test_schema_and_fields(actions):
    df, _ = actions
    tab = A.to_table(df)
    assert validate_table("planner_exceptions", tab) == []
    assert df.exception_id.is_unique
    assert set(df.owner) <= {"Materials planning", "Repair control", "Procurement", "AOG desk"}
    assert (df.due_week > df.week).all() and (df.week == 103).all()
    for c in A.ACTION_FIELDS:
        assert c in df.columns
    for r in df.itertuples():
        assert r.severity_icon == A.SEVERITY_ICON[r.severity] and r.trigger
        json.dumps(r.evidence)
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
