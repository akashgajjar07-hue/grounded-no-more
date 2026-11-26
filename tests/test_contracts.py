"""Phase-1 contract tests: config parses, calendar is chronological, schemas are consistent."""
from gnm import schemas
from gnm.config import load_config, calendar, seeds, assumption_register


def test_config_loads_and_has_provenance():
    cfg = load_config()
    for section in ["calendar", "fleet", "parts", "economics", "network"]:
        assert section in cfg
    assert cfg["meta"]["airline_name"].endswith("(fictional)")


def test_calendar_chronological_and_disjoint():
    c = calendar()
    tr, se, ev = c["train_weeks"], c["selection_weeks"], c["evaluation_weeks"]
    assert tr[0] == 0 and tr[1] + 1 == se[0] and se[1] + 1 == ev[0]
    assert ev[1] - ev[0] + 1 == 52
    assert c["history_weeks"] == (tr[0], se[1])


def test_seed_sets_disjoint():
    s = seeds()
    assert len(s["selection"]) == 20 and len(s["holdout"]) == 20
    assert not set(s["selection"]) & set(s["holdout"])
    assert s["history"] not in s["selection"] + s["holdout"]


def test_schema_tables_have_pk_in_columns():
    for name, t in schemas.TABLES.items():
        for k in t.pk:
            assert k in t.colnames, (name, k)
        for col, other, ocol in t.fks:
            assert col in t.colnames and other in schemas.TABLES


def test_only_ground_truth_tables_hidden():
    hidden = [n for n, t in schemas.TABLES.items() if t.hidden]
    assert hidden == ["gt_part_truth"]


def test_assumption_register_provenance_valid():
    df = assumption_register()
    assert len(df) > 50
    assert set(df["provenance"]) <= set(schemas.PROVENANCE_VALUES)
    assert (df[df.key.str.contains("network.stations")]["provenance"] == "REAL").all()
