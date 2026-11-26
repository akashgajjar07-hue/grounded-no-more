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
    # wave 4: step 4 quotes the recommended S the calculator opens on, and the station view's own units/availability
    assert f"recommended {fl['spares_total']['recommended']} spares" in step4["body"]
    sv = fl["station_view"]
    assert f"the {sv['units']['recommended']} unit" in step4["body"] and f"{round(100 * sv['availability']['recommended'])}%" in step4["body"]
    for s in story["steps"]:
        ms = s.get("mobile_selector")
        assert ms is None or ms.startswith(f'[data-story="{s["story_id"]}"]') or ms.startswith("[data-incident="), s
        assert " M " not in s["body"] and "(step 2" not in s["body"]
    aog = json.load(open(SITE / "aog_lab.json"))
    assert aog["sim_calendar"]["epoch"] == "2023-01-02T00:00:00Z"
    theme = (SITE.parent / "js" / "charts" / "theme.js").read_text()
    assert f"SIM_EPOCH = '{aog['sim_calendar']['epoch']}'" in theme
