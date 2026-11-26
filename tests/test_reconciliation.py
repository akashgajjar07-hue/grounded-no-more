"""docs/data/*.json must reconcile with the pipeline outputs they were exported from.

Recomputes the Mission Control KPIs and the policies.json means from outputs/ and compares them with the
exported files (tolerance = the exporter's rounding: 4 significant digits, money to the AED).
Regenerate the site data with `python scripts/export_site.py`.
"""
import json
import math

import pandas as pd
import pytest

from gnm.config import ROOT
from gnm.export.build_site_data import FILES, MAX_TOTAL_BYTES, nondominated

SITE = ROOT / "docs" / "data"
OUT = ROOT / "outputs"

pytestmark = pytest.mark.skipif(not (SITE / "kpis.json").exists() or not (OUT / "holdout" / "frontier_points.csv").exists(),
                                reason="site data or holdout outputs not present (run scripts/export_site.py)")


def _strict_load(path):
    def bad(tok):
        raise ValueError(f"{path.name}: non-finite JSON number {tok}")
    with open(path) as f:
        return json.load(f, parse_constant=bad)


@pytest.fixture(scope="module")
def site():
    return {n: _strict_load(SITE / f"{n}.json") for n in FILES}


def close(a, b, money=False):
    if money:
        return abs(a - b) <= 1.0
    return a == pytest.approx(b, rel=6e-4, abs=1e-9)


MONEY_IDS = {"spare_capital_aed", "total_annual_cost_aed", "expedite_cost_aed"}
FRONTIER_COL = {"immediate_fill_rate": "fill_rate", "aog_hours": "aog_hours", "spare_capital_aed": "capital",
                "total_annual_cost_aed": "total_cost", "expedite_cost_aed": "expedite_cost", "aog_events": "aog_events"}


def test_recommended_point_is_flagged_and_i125(site):
    summ = json.load(open(OUT / "frontier" / "summary.json"))
    sel = pd.read_csv(OUT / "frontier" / "selection_points.csv")
    flagged = sel[(sel.variant == "central") & sel.recommended].id.tolist()
    assert summ["recommendation"]["recommended"] == "I125" == site["kpis"]["recommended_id"] == site["frontier"]["recommended"]
    assert flagged == ["I125"]


def test_mission_control_kpis_reconcile(site):
    """v2 framing: the KPI value is the CORE finding P2 vs the P0 baseline; the reference is the frontier option (I125)."""
    fp = pd.read_csv(OUT / "holdout" / "frontier_points.csv").set_index("id")
    rid = site["kpis"]["recommended_id"]
    core = site["kpis"]["core_id"]
    assert core == "P2"
    k = {x["id"]: x for x in site["kpis"]["kpis"]}
    for kid, col in FRONTIER_COL.items():
        m = kid in MONEY_IDS
        assert close(k[kid]["value"], fp.at[core, f"{col}_mean"], m), kid
        assert close(k[kid]["baseline"], fp.at["P0", f"{col}_mean"], m), kid
        assert close(k[kid]["ci"][0], fp.at[core, f"{col}_lo"], m) and close(k[kid]["ci"][1], fp.at[core, f"{col}_hi"], m), kid
        assert close(k[kid]["delta"], fp.at[core, f"{col}_mean"] - fp.at["P0", f"{col}_mean"], m), kid
        assert k[kid]["reference"]["id"] == rid and close(k[kid]["reference"]["value"], fp.at[rid, f"{col}_mean"], m), kid
    # P0 in the frontier holdout run == P0 in the policy holdout run (same seeds, same frozen tables)
    ps = json.load(open(OUT / "holdout" / "policy_summary.json"))["variants"]["central"]["policies"]["P0"]
    assert close(k["aog_hours"]["baseline"], ps["aog_hours"]["mean"])
    assert close(k["immediate_fill_rate"]["baseline"], ps["immediate_fill_rate"]["mean"])
    assert close(k["spare_capital_aed"]["baseline"], ps["spare_capital_aed"]["mean"], True)
    # open planner actions by severity
    acts = json.load(open(OUT / "actions" / "actions.json"))["actions"]
    assert k["open_exceptions"]["value"] == len(acts)
    for sev in ["urgent", "review", "info"]:
        assert k["open_exceptions"]["by_severity"][sev] == sum(a["severity"] == sev for a in acts)
    # no fabricated sparks
    assert all("spark" not in x for x in site["kpis"]["kpis"])


def test_policies_means_reconcile(site):
    ps = json.load(open(OUT / "holdout" / "policy_summary.json"))
    pol = {p["policy_id"]: p for p in site["policies"]["policies"]}
    for pid, kp in ps["variants"]["central"]["policies"].items():
        for metric, v in kp.items():
            m = metric.endswith("_aed") or "cost" in metric
            got = pol[pid]["kpi"][metric]
            for key in ["mean", "ci_lo", "ci_hi"]:
                assert close(got[key], v[key], m), (pid, metric, key)
    fp = pd.read_csv(OUT / "holdout" / "frontier_points.csv").set_index("id")
    rid = site["policies"]["recommended_id"]
    for metric, col in FRONTIER_COL.items():
        assert close(pol[rid]["kpi"][metric]["mean"], fp.at[rid, f"{col}_mean"], metric in MONEY_IDS), metric
    sel = json.load(open(OUT / "policies" / "selection_summary.json"))["variants"]["central"]["policies"]
    spol = {p["policy_id"]: p for p in site["policies"]["selection"]["policies"]}
    for pid, kp in sel.items():
        assert close(spol[pid]["kpi"]["aog_hours"]["mean"], kp["aog_hours"]["mean"])
    for v in ["low_stress", "high_stress"]:
        sp = {p["policy_id"]: p for p in site["policies"]["sensitivity"][v]["policies"]}
        for pid, kp in ps["variants"][v]["policies"].items():
            assert close(sp[pid]["kpi"]["aog_hours"]["mean"], kp["aog_hours"]["mean"]), (v, pid)


def test_frontier_dominated_flags(site):
    fp = pd.read_csv(OUT / "holdout" / "frontier_points.csv")
    exp = nondominated([(r.id, r.capital_mean, r.aog_hours_mean) for r in fp.itertuples()])
    got = {p["id"]: p["dominated"] for p in site["frontier"]["points"]}
    assert got == exp
    assert len(got) == len(fp)
    assert not got["I125"] and got["P0"]


def test_network_station_means_reconcile(site):
    skp = pd.read_parquet(OUT / "holdout" / "policy_station_kpis.parquet")
    skp = skp[skp.variant == "central"].groupby(["policy_id", "station"]).aog_hours.mean()
    for r in site["network"]["policy_compare"]:
        assert close(r["aog_hours"], skp[(r["policy_id"], r["station"])])


def _walk_numbers(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_numbers(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, obj


def test_no_nan_or_inf_anywhere(site):
    for name, d in site.items():
        for path, x in _walk_numbers(d):
            assert math.isfinite(x), (name, path)


NUMERIC_FIELDS = {
    "kpis": ("kpis", ["value"]),
    "parts": ("parts", ["stock_total", "risk_score", "risk_hours", "unit_cost"]),
    "frontier": ("points", ["capital_aed", "aog_hours", "total_cost_aed", "fill_rate"]),
    "network": ("stations", ["lat", "lon", "serviceable_units", "stock_value", "requests", "risk"]),
    "forecast": ("leaderboard", ["mase", "bias", "coverage", "n"]),
}


def test_no_none_in_numeric_fields(site):
    for name, (key, fields) in NUMERIC_FIELDS.items():
        for row in site[name][key]:
            for f in fields:
                assert isinstance(row.get(f), (int, float)) and not isinstance(row.get(f), bool), (name, row.get("id") or row.get("pn"), f)
    for p in site["parts"]["parts"]:   # ADI/CV2 are undefined only for insufficient_data
        if p["demand_class"] != "insufficient_data":
            assert isinstance(p["adi"], (int, float)) and isinstance(p["cv2"], (int, float)), p["pn"]
    for k in site["kpis"]["kpis"]:
        for f in ["baseline", "recommended", "delta"]:
            if f in k:
                assert isinstance(k[f], (int, float)), (k["id"], f)
        if "ci" in k:
            assert all(isinstance(x, (int, float)) for x in k["ci"]), k["id"]
    for p in site["policies"]["policies"]:
        for metric, v in p["kpi"].items():
            assert all(isinstance(v[x], (int, float)) for x in ["mean", "ci_lo", "ci_hi"]), (p["policy_id"], metric)


def _has_numbers(obj):
    return any(True for _ in _walk_numbers(obj))


def _prov_ok(v):
    """A numeric object is covered if it carries 'provenance' itself or every numeric child is covered."""
    if isinstance(v, dict):
        return "provenance" in v or all(_prov_ok(c) for c in v.values() if _has_numbers(c))
    if isinstance(v, list):
        return bool(v) and all(isinstance(x, (dict, list)) and _prov_ok(x) for x in v if _has_numbers(x))
    return False


def test_every_numeric_object_has_provenance(site):
    for name, d in site.items():
        assert d["meta"].get("provenance") in {"REAL", "DERIVED", "ASSUMED", "SIMULATED"}, name
        by_key = d["meta"].get("provenance_by_key", {})
        for key, val in d.items():
            if key == "meta" or key in by_key or not _has_numbers(val):
                continue
            assert _prov_ok(val), (name, key)


def test_meta_and_manifest(site):
    for name, d in site.items():
        m = d["meta"]
        assert "fixture" not in m, name
        for k in ["generated_at", "git_sha", "provenance", "source", "notes"]:
            assert m.get(k) not in (None, "", []), (name, k)
        assert m["git_sha"] != "fixture"
    man = json.load(open(SITE / "manifest.json"))
    assert sorted(man["files"]) == sorted(FILES)


def test_total_size_under_limit():
    total = sum((SITE / f"{n}.json").stat().st_size for n in FILES)
    assert total < MAX_TOTAL_BYTES, total


def test_v2_headline_recomputes_from_outputs(site):
    """Every number in the site headline (kpis.headline) is recomputed here from outputs/, never typed."""
    H = site["kpis"]["headline"]
    ps = json.load(open(OUT / "holdout" / "policy_summary.json"))
    pc = ps["variants"]["central"]["paired"]["P2-P0"]
    c = H["core"]
    assert close(c["aog_reduction"]["mean"], -pc["aog_hours"]["mean"])
    assert close(c["aog_reduction"]["ci"][0], -pc["aog_hours"]["ci_hi"]) and close(c["aog_reduction"]["ci"][1], -pc["aog_hours"]["ci_lo"])
    assert close(c["capital_aed"]["mean"], pc["spare_capital_aed"]["mean"], True)
    hub = json.load(open(SITE / "network.json"))["hub"]
    for pid in ["P0", "P2"]:
        t = pd.read_csv(OUT / "policies" / f"{pid}_stock_params.csv")
        assert c["outstation_rotables"][pid] == int(t[(t.part_class == "R") & (t.station != hub)].target_units.sum())
    assert str(c["outstation_rotables"]["P0"]) in c["baseline_label"]
    for w in c["worlds"]:
        pr = ps["variants"][w["variant"]]["paired"]["P2-P0"]["aog_hours"]
        assert close(w["aog_hours"]["mean"], pr["mean"]) and w["significant"] == (pr["ci_hi"] < 0)
    assert c["holds_all_worlds"] == all(ps["variants"][v]["paired"]["P2-P0"]["aog_hours"]["ci_hi"] < 0 for v in ["low_stress", "central", "high_stress"])
    assert c["holds_penalty_range"] == all(pc[f"total_cost_pen_{x}"]["ci_hi"] < 0 for x in ["x0.5", "x1", "x2"])
    fp = pd.read_csv(OUT / "holdout" / "frontier_points.csv").set_index("id")
    fo, rid = H["frontier_option"], site["kpis"]["recommended_id"]
    assert close(fo["extra_capital_aed"]["mean"], fp.at[rid, "d_capital_vs_base_mean"], True)
    assert close(fo["aog_reduction"]["mean"], -fp.at[rid, "d_aog_hours_vs_base_mean"])
    pp = json.load(open(OUT / "holdout" / "postplan_i125_stress.json"))
    for w in fo["postplan_stress"]:
        row = next(q for q in pp["worlds"][w["variant"]] if q["id"] == rid)
        assert close(w["aog_hours"]["mean"], row["d_aog_hours_vs_base_mean"])
    chk = pd.read_csv(OUT / "holdout" / "forecast_champion_check.csv")
    ho = H["honest"]
    assert ho["forecast_champions_best"] == int((chk.champion_rank == 1).sum()) and ho["forecast_cells"] == len(chk)
    tr = json.load(open(OUT / "holdout" / "truth_recovery.json"))["reliability"]["all"]
    assert close(ho["mtbur_history_error"], tr["estimated_mdale"]) and close(ho["mtbur_quote_error"], tr["quoted_mdale"])


def test_ps1_is_read_not_hard_coded(site):
    inc = json.load(open(OUT / "aog_lab" / "incidents.json"))
    ps1 = next(i for i in inc["incidents"] if i["id"] == inc["ps1_incident_id"])
    assert site["aog_lab"]["ps1_incident_id"] == inc["ps1_incident_id"]
    assert site["network"]["transfer_replay"]["focus"]["incident_id"] == ps1["id"]
    steps = site["story"]["steps"]
    assert any(ps1["pn"] in s["route"] for s in steps) and any(ps1["id"] in s["route"] for s in steps)
