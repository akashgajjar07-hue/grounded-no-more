"""Site-data exporter: release guard, non-dominated computation, and the §5 shape contract."""
import json
import os

import pytest

from gnm.config import ROOT
from gnm.export.build_site_data import FILES, STORY_IDS, clean, nondominated, sig

SITE = ROOT / "docs" / "data"


def test_fixtures_removed_for_release():
    """The lead deletes docs/data/fixtures before deploy; with GNM_RELEASE=1 their presence fails."""
    if os.environ.get("GNM_RELEASE") == "1":
        assert not (SITE / "fixtures").exists(), "docs/data/fixtures must be removed for a release build"


def test_nondominated_toy():
    pts = [("a", 1, 10), ("b", 2, 5), ("c", 3, 6), ("d", 2, 5), ("e", 0.5, 20), ("f", 4, 1), ("g", 1, 11)]
    dom = nondominated(pts)
    assert dom == {"a": False, "b": False, "c": True, "d": False, "e": False, "f": False, "g": True}


def test_nondominated_single_and_identical():
    assert nondominated([("x", 1, 1)]) == {"x": False}
    assert nondominated([("x", 1, 1), ("y", 1, 1)]) == {"x": False, "y": False}


def test_rounding_rules():
    out = clean({"spare_capital_aed": 41853426.6, "aog_hours": 2870.7, "mase": 0.723662, "lat": 24.43301,
                 "h_star_per_aed_1m": 9.4169, "ci": [float("nan"), 1.23456]})
    assert out == {"spare_capital_aed": 41853427, "aog_hours": 2871, "mase": 0.7237, "lat": 24.433,
                   "h_star_per_aed_1m": 9.417, "ci": [None, 1.235]}
    assert sig(0.000123456) == 0.0001235


REQUIRED = {
    "kpis": ("kpis", ["id", "label", "value", "unit", "provenance"]),
    "parts": ("parts", ["pn", "desc", "ata", "cls", "deadline", "demand_class", "adi", "cv2", "abc", "stock_total",
                        "stock_by_station", "risk_score", "risk_level", "unit_cost", "planted"]),
    "forecast": ("leaderboard", ["demand_class", "part_class", "method", "mase", "mase_ci", "bias", "pis", "coverage", "n"]),
    "rotables": ("repair_queue", ["ro_id", "serial", "pn", "shop", "shop_in_h", "start_h", "due_h", "return_h", "overdue"]),
    "network": ("stations", ["station", "lat", "lon", "role", "serviceable_units", "stock_value", "requests", "risk"]),
    "frontier": ("points", ["id", "capital_aed", "aog_hours", "aog_ci", "dominated", "kind"]),
    "policies": ("policies", ["policy_id", "label", "kpi"]),
    "aog_lab": ("incidents", ["id", "tail", "pn", "station", "deadline", "timeline", "options"]),
    "actions": ("actions", ["exception_id", "type", "severity", "pn", "station", "summary"]),
    "story": ("steps", ["route", "selector", "title", "body"]),
}

needs_site = pytest.mark.skipif(not (SITE / "kpis.json").exists(), reason="run scripts/export_site.py")


@needs_site
def test_shapes_follow_contract():
    for name, (key, fields) in REQUIRED.items():
        d = json.load(open(SITE / f"{name}.json"))
        assert d[key], name
        for row in d[key]:
            missing = [f for f in fields if f not in row]
            assert not missing, (name, missing)
    f = json.load(open(SITE / "frontier.json"))
    assert {p["kind"] for p in f["points"]} <= {"policy", "greedy", "lever", "combo"}
    assert f["recommended"] in {p["id"] for p in f["points"]} and f["baseline"] == "P0"
    m = json.load(open(SITE / "method.json"))
    for k in ["source_manifest", "assumptions", "validation", "licences"]:
        assert m[k]
    assert "tests_passed" in m["validation"] and "tests_total" in m["validation"]


@needs_site
def test_story_selectors_and_numbers():
    s = json.load(open(SITE / "story.json"))
    assert 6 <= len(s["steps"]) <= 8
    # each selector starts at the screen's data-story hook (story_id), optionally narrowed to a child element
    assert [st["story_id"] for st in s["steps"]] == s["selector_ids"]
    assert len(s["selector_ids"]) == len(STORY_IDS)
    for st in s["steps"]:
        assert st["selector"].startswith(f'[data-story="{st["story_id"]}"]') or st["selector"].startswith("[data-incident="), st
        assert len(st["body"]) <= 300, (st["story_id"], len(st["body"]))
    for st in s["steps"]:
        assert st["route"].startswith("#/") and st["body"] and "nan" not in st["body"].lower()


@needs_site
def test_manifest_lists_existing_files():
    man = json.load(open(SITE / "manifest.json"))
    assert man["files"] == FILES
    for n in FILES:
        assert (SITE / f"{n}.json").exists(), n


@needs_site
def test_canonical_cross_screen_fields():
    """wave-3 #2: one per-PN AOG metric set, explicit system fields, outstation-relative risk, story = screen numbers."""
    p = json.load(open(SITE / "parts.json"))
    labels = p["aog_metric_labels"]
    assert set(labels) == {"aog_h_2y", "aog_h_52w", "aog_h_52w_max_station"}
    assert all(v["label"] and v["short"] for v in labels.values())
    acts = json.load(open(SITE / "actions.json"))["actions"]
    for r in p["parts"]:
        assert r["aog_h_2y"] >= r["aog_h_52w"] >= r["aog_h_52w_max_station"] >= 0
        assert (r["aog_h_52w_max_station_id"] is None) == (r["aog_h_52w"] == 0)
        # the action centre's per-station lookback never exceeds the worst-station figure, and matches it there
        lb = {a["station"]: a["evidence"]["aog_hours_lookback"] for a in acts
              if a["pn"] == r["pn"] and a["type"] == "OUTSTATION_DEPLETION"}
        if lb:
            assert max(lb.values()) <= r["aog_h_52w_max_station"] + 0.5
            st = r["aog_h_52w_max_station_id"]
            if st in lb:
                assert abs(lb[st] - r["aog_h_52w_max_station"]) < 0.5
    for s in p["ata_systems"]:
        assert s["system_level"] == s["risk_level"] and s["has_urgent_part"] == (s["n_urgent"] > 0)
        assert not (s["status"] == "ok" and s["has_urgent_part"]), s  # never a bare OK next to urgent parts
    n = json.load(open(SITE / "network.json"))
    outs = [s for s in n["stations"] if s["role"] != "hub"]
    top = min(outs, key=lambda s: s["outstation_rank"])
    assert top["risk_vs_outstations"] == 1 and top["outstation_risk_level"] == "urgent"
    assert all(s["outstation_risk_level"] != "ok" for s in outs if s["n_urgent_actions"])
    # story float numbers use the calculator's S (shelf + loop)
    story = json.load(open(SITE / "story.json"))
    rot = json.load(open(SITE / "rotables.json"))
    step4 = next(s for s in story["steps"] if s["story_id"] == "rotable-float-calc")
    pn = next(s for s in story["steps"] if s["story_id"] == "aircraft")["route"].split("pn=")[1]
    fl = next(f for f in rot["float_examples"] if f["pn"] == pn)
    assert fl["spares_total"]["P2"] == fl["p2_units"] + fl["loop_units"]
    # wave C: step 3 quotes P2's S (the calculator opens on it) and the station view on the AUH resupply time (AV2-14)
    assert f"the Network Plan's {fl['spares_total']['P2']} spares" in step4["body"]
    sv = fl["station_view"]
    assert sv["basis"] == "resupply" and sv["resupply_days"] < sv["loop_days"]
    assert f"the Network Plan holds {sv['units']['P2']} unit" in step4["body"] and f"{100 * sv['availability']['P2']:.1f}%" in step4["body"]
    for s in story["steps"]:
        ms = s.get("mobile_selector")
        assert ms is None or ms.startswith(f'[data-story="{s["story_id"]}"]') or ms.startswith("[data-incident="), s
        assert " M " not in s["body"] and "(step 2" not in s["body"]
    aog = json.load(open(SITE / "aog_lab.json"))
    assert aog["sim_calendar"]["epoch"] == "2023-01-02T00:00:00Z"
    theme = (SITE.parent / "js" / "charts" / "theme.js").read_text()
    assert f"SIM_EPOCH = '{aog['sim_calendar']['epoch']}'" in theme


# ---------------------------------------------------------------------------------------------- v2.1 (final release)
def _j(name):
    return json.load(open(SITE / f"{name}.json"))


def test_display_names_match_names_js():
    """A3: the exporter's names are the same as docs/js/lib/names.js (one source of wording)."""
    import re
    from gnm.export.v21 import DISPLAY_NAMES, LEVER_NAMES, display_name
    js = (ROOT / "docs" / "js" / "lib" / "names.js").read_text()
    for code, name in {**DISPLAY_NAMES, **LEVER_NAMES}.items():
        assert re.search(rf"\b{code}: '{re.escape(name)}'", js), code
    assert display_name("B150") == "Frontier point B150" and display_name("P2@central") == "Network Plan (central plan)"


@needs_site
def test_display_names_exported_beside_codes():
    from gnm.export.v21 import display_name
    for p in _j("policies")["policies"]:
        assert p["display_name"] == display_name(p["policy_id"]) and p["label"] == p["display_name"], p["policy_id"]
    for p in _j("frontier")["points"]:
        assert p["display_name"] == display_name(p["id"]), p["id"]
    for name in ["kpis", "policies", "frontier", "network", "parts"]:
        dn = _j(name)["display_names"]
        assert dn["P0"]["display_name"] == "Simple Rulebook (naive reference)" and dn["I125"]["display_name"] == "Network Plan + Extra Spares"
        assert dn["P2_GUARD"]["display_name"] == "Network Plan held to guardrails"
    assert all(r["display_name"] for r in _j("network")["policy_compare"])


@needs_site
def test_v21_landing_and_verbatim_texts():
    from gnm.config import load_config
    k = _j("kpis")
    c = load_config()
    lo, hi = c["seeds"]["holdout_seeds"]
    st = {x["id"]: x["value"] for x in k["landing"]["stats"]}
    assert st == {"aircraft": c["fleet"]["narrowbody"]["count"] + c["fleet"]["widebody"]["count"], "part_numbers": 120,
                  "stations": 1 + len(c["network"]["outstations"]), "test_runs": hi - lo + 1}
    assert k["landing"]["text"] == "40 aircraft · 120 part numbers · 7 stations · 20 fresh test runs"
    assert k["reading_note"].startswith("How to read these numbers: simulated downtime of the aircraft waiting for the part")
    assert k["stress_worlds"]["text"] == "reliability scaled ×0.96 / ×1.00 / ×1.08 — a narrow range"
    assert k["stress_worlds"]["ranges_note"] == ("Likely ranges reflect simulation randomness only, not uncertainty in "
                                                 "prices, failure rates, suppliers or contracts.")
    fi = k["frontier_insight"]
    assert fi["text"].startswith("Faster repair can beat buying spares: with 25% shorter repair time")
    assert fi["levers"] == ["faster repair", "pool access", "better reliability", "more spares"]
    assert fi["evidence"]["net_benefit_significant"] is False
    m = _j("method")
    assert m["calibration_note"]["text"].startswith("The target range for the starting-point policy was an exploratory assumption")
    assert round(m["calibration_note"]["line_kit_variant_aog_h"]) == 1052
    assert m["calibration_note"]["line_kit_variant_aog_h"] < m["calibration_note"]["target_range_aog_h"][0]


@needs_site
def test_v21_parts_flags():
    p = _j("parts")
    esc = [x for x in p["parts"] if x["escalation"]]
    assert [x["pn"] for x in esc] == ["GN-32-R014"]   # the hero part (PS1)
    e = esc[0]["escalation"]
    # V21-A7: the planner-facing multiple is the HISTORY estimate (planted truth is evaluation-only)
    assert e["quoted_multiple_basis"].startswith("history estimate")
    assert e["estimated_ratio"] >= 2 and e["text"] == (f"Removing {e['estimated_ratio']:.1f}× faster than quoted → escalate to reliability engineering "
                                                       "and warranty review first. Extra spares are interim cover, compared "
                                                       "against faster repair or pool access.")
    flag = "invalid recommendation — brakes are not changed outside the hub in this model"
    bad = p["invalid_allocations"]
    assert bad and all(b["text"] == flag and b["station"] != "AUH" and b["policy"] in ("P2", "I125") for b in bad)
    assert {(b["pn"], b["station"]) for b in bad if b["policy"] == "P2"} == {
        ("GN-32-R013", "BOM"), ("GN-32-R013", "CAI"), ("GN-32-R013", "JED"), ("GN-32-R036", "LHR"), ("GN-32-R036", "SIN")}
    by_pn = {x["pn"]: x for x in p["parts"]}
    assert all(b in by_pn[b["pn"]]["allocation_flags"] for b in bad)
    # frozen results kept: the flagged I125 allocation rows are still in the frontier file
    rows = _j("frontier")["allocations"]["I125"]
    fl = [r for r in rows if r.get("invalid_recommendation")]
    assert fl and all(r["flag_text"] == flag and r["pn"] in ("GN-32-R013", "GN-32-R036") for r in fl)


@needs_site
def test_v21_rotables_calculator_modes():
    r = _j("rotables")
    assert r["calculator_modes"]["hub"]["basis"] == "network repair-loop time"
    assert r["calculator_modes"]["outstation"]["basis"] == "resupply time from AUH"
    assert r["outstation_mode"] == "enabled"
    import pandas as pd
    pp = pd.read_csv(ROOT / "outputs" / "policies" / "p2_positioning.csv").set_index(["pn", "station"])
    n = 0
    for f in r["float_examples"]:
        for v in f["station_views"]:
            assert v["station"] != "AUH" and v["basis"] == "resupply"
            x = pp.loc[(f["pn"], v["station"])]
            assert v["resupply_days"] == pytest.approx(float(x.resupply_days + x.hub_wait_days), rel=6e-4)
            n += 1
    assert n > 0


@needs_site
def test_v21_method_av2_status_table():
    m = _j("method")
    rows = m["av2_findings"]
    assert [r["id"] for r in rows] == [f"AV2-{i:02d}" for i in range(1, 26)]
    assert {r["status"] for r in rows} == {"fixed", "disclosed", "next experiment"}
    st = {r["id"]: r["status"] for r in rows}
    assert {k for k, v in st.items() if v == "fixed"} == {"AV2-03", "AV2-10", "AV2-11", "AV2-14", "AV2-21", "AV2-23"}
    assert st["AV2-01"] == st["AV2-02"] == "next experiment"
    assert all(29 <= r["limitation"] <= 39 for r in rows if r["status"] != "fixed")
    sev = {r["id"]: r["severity"] for r in rows}
    assert [k for k, v in sev.items() if v == "critical"] == ["AV2-01", "AV2-02", "AV2-03"]
    assert [x["title"] for x in m["next_experiments"]] == ["P0-R: a revised reference policy", "Incremental donor unavailability",
                                                          "Combined disruption scenarios", "An MRO-side model"]


def test_scrub_relabels_archetypes_and_words():
    from gnm.export.v21 import scrub_text, text_violations
    assert scrub_text("A320-family archetype (generic single-aisle)") == "narrowbody archetype (generic single-aisle)"
    assert scrub_text("787-family archetype (generic twin-aisle)") == "widebody archetype (generic twin-aisle)"
    assert scrub_text("faster for A320-family LRUs than for 787 LRUs") == "faster for narrowbody LRUs than for widebody LRUs"
    assert scrub_text("787 h a year at 1787 units") == "787 h a year at 1787 units"   # numbers untouched
    assert scrub_text("holdout seeds 1000–1019") == "holdout the retired v1 holdout"
    assert not text_violations({"a": scrub_text("Marginal analysis is optimal only for separable objectives; validated.")})
    assert text_violations({"a": "an A320 fleet"}) and text_violations({"a": "optimal"})
