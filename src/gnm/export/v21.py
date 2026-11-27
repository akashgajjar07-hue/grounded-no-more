"""v2.1 final-release additions to the site data (internal development notes (kept privately)). Additive only.

* Display names (A3) exported beside every policy / frontier code (mirrors docs/js/lib/names.js).
* Verbatim texts from the brief (scope line, A1 stat strip, A2, A4 note, A5, A6, A7, A8, A9).
* `scrub()`: the final pass over every exported string. It relabels the locked config's OEM-family archetype names to
  "narrowbody archetype" / "widebody archetype", replaces forbidden words and drops stale v1 strings.
  `text_violations()` is the matching gate used by the tests.

Numbers are never typed here: every figure is computed by build_site_data from outputs/ (or config / seeds).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------------------------- A3 display names
DISPLAY_NAMES = {
    "P0": "Simple Rulebook (naive reference)",
    "P1": "Each Airport for Itself (simplified local comparator)",
    "P2": "Network Plan",
    "I125": "Network Plan + Extra Spares",
    "P2_GUARD": "Network Plan held to guardrails",
}
SHORT_NAMES = {
    "P0": "Simple Rulebook", "P1": "Each Airport for Itself", "P2": "Network Plan",
    "I125": "Network Plan + Extra Spares", "P2_GUARD": "Network Plan held to guardrails",
}
LEVER_NAMES = {
    "LEV_REPOS": "Reposition existing spares only",
    "LEV_TAT10_TOP6": "Faster repair on six parts",
    "COMBO_B100_TAT10": "Re-balanced spares + faster repair",
}


def display_name(code: str, short: bool = False) -> str:
    c = str(code).split("@")[0]
    if c in DISPLAY_NAMES:
        name = (SHORT_NAMES if short else DISPLAY_NAMES)[c]
    elif c in LEVER_NAMES:
        name = LEVER_NAMES[c]
    elif re.fullmatch(r"[BI]\d{2,3}", c):
        name = f"Frontier point {c}"
    else:
        return str(code)
    return name + (" (central plan)" if "@" in str(code) else "")


def names_map(codes) -> dict:
    return {c: {"display_name": display_name(c), "short_name": display_name(c, short=True)} for c in codes}


# ---------------------------------------------------------------------------------------------- verbatim texts
SCOPE_LINE = "across 120 modelled part numbers · simulated · downtime of the aircraft waiting for the part"
A1_TITLE = "The right spare, at the right station, before an aircraft needs it."
A1_SUB = ("An aviation materials-planning simulation exploring how spare-parts forecasting, repair time, stock positioning "
          "and capital affect how long aircraft sit grounded waiting for parts.")
A1_FOOTER = "Independent educational simulation · Fictional airline · No operational airline data."
A2_READING_NOTE = (
    "How to read these numbers: simulated downtime of the aircraft waiting for the part, across 120 modelled part "
    "numbers. Downtime of aircraft that donated a part (cannibalisation) is shown separately, not included. The Simple "
    "Rulebook is a deliberately simplified starting point, not a model of a competent airline. Part costs, reliability "
    "and sourcing are assumed. These are not forecasts of achievable airline savings.")
A4_NOTE = "Removed stock is not cash back — it may be redeployed, consumed, exchanged or sold at a discount."
A5_CALIBRATION = (
    "The target range for the starting-point policy was an exploratory assumption chosen after diagnosing the model, "
    "not benchmarked against real airline KPIs. A line-kit variant (≈1,052 h) was measured but not adopted because it "
    "fell outside that range. All results are conditional on this choice.")
A6_RANGES = ("Likely ranges reflect simulation randomness only, not uncertainty in prices, failure rates, suppliers or "
             "contracts.")
A7_ESCALATION_TMPL = ("Removing {x}× faster than quoted → escalate to reliability engineering and warranty review first. "
                      "Extra spares are interim cover, compared against faster repair or pool access.")
A8_INSIGHT = ("Faster repair can beat buying spares: with 25% shorter repair time, the extra-investment option loses its "
              "clear cost advantage.")
A8_LEVERS = ["faster repair", "pool access", "better reliability", "more spares"]
A9_FLAG = "invalid recommendation — brakes are not changed outside the hub in this model"
DONOR_LABEL = ("Post-plan exploratory recount. Gross donor hours are an upper bound — a donor may already be in "
               "maintenance or not scheduled to fly.")
NOT_RECONSTRUCTIBLE = "not reconstructible from current logs"
E4_FOOTER = "Built by Akash Gajjar with AI-assisted development (Claude Code). Fictional airline, simulated data."


def a6_text(lo: float, mid: float, hi: float) -> str:
    """'reliability scaled ×0.96 / ×1.00 / ×1.08 — a narrow range' from the config scales (sorted ascending)."""
    a, b, c = sorted([lo, mid, hi])
    return f"reliability scaled ×{a:.2f} / ×{b:.2f} / ×{c:.2f} — a narrow range"


# ---------------------------------------------------------------------------------------------- AV2 findings (A12)
# short neutral titles for the 25 findings of reports/review_aviation_v2.md (ids and severities are parsed from it)
AV2_TITLES = {
    "AV2-01": "Downtime of robbed donor aircraft is not counted",
    "AV2-02": "The Simple Rulebook's outstation stock is mostly unusable; no line kit, no re-provisioning",
    "AV2-03": "The Network Plan re-mixes the spares (buys some, removes others), not only repositions them",
    "AV2-04": "Wheels and tyres modelled as rare unscheduled removals",
    "AV2-05": "Brakes positioned at outstations where they are never changed",
    "AV2-06": "Hero part removal rate is high; no warranty or reliability escalation",
    "AV2-07": "Robbery is the automatic first recovery route at the hub",
    "AV2-08": "Deferring a defect has no cost of its own",
    "AV2-09": "Downtime counted from removal, not from the next departure",
    "AV2-10": "Stale v1 text in the app",
    "AV2-11": "The calibration range has no external anchor",
    "AV2-12": "Exchange and loan are one route; no pool contract",
    "AV2-13": "Unit costs drawn per part family, not per aircraft type",
    "AV2-14": "Outstation spares view used the repair-loop time instead of resupply time",
    "AV2-15": "Some removal rates are high for mature parts",
    "AV2-16": "Local buy of windshields and masks is too fast",
    "AV2-17": "The in-house shop has no queue",
    "AV2-18": "Fitting capability assumed at every outstation",
    "AV2-19": "Hub robbery is not used to supply outstations",
    "AV2-20": "A few parts shared by both aircraft types are implausible",
    "AV2-21": "Inconsistent wording for the rectification classes",
    "AV2-22": "Network page headline wording",
    "AV2-23": "Headline scope: 120 modelled part numbers, not the whole fleet",
    "AV2-24": "The simple local comparator sizes the hub on hub demand only",
    "AV2-25": "The optimiser's hub floor is low",
}
# per reports/VALIDATION_REPORT.md "v2 reviews" (fixed list) and LIMITATIONS 29-39 (disclosed list)
AV2_FIXED = {"AV2-03": "P2 re-mix stated: rotables bought and removed shown with the net change",
             "AV2-10": "v1 leftovers removed", "AV2-11": "range wording: an assumed plausibility band",
             "AV2-14": "outstation float view uses the resupply time from AUH",
             "AV2-21": "one rectification-class wording site-wide", "AV2-23": "the 120-part scope stated on every headline KPI"}
AV2_LIMITATION = {"AV2-01": 29, "AV2-02": 30, "AV2-04": 31, "AV2-05": 32, "AV2-06": 33, "AV2-07": 34, "AV2-08": 35,
                  "AV2-09": 36, "AV2-12": 37, "AV2-13": 38}
AV2_MINOR_LIMITATION = 39
# findings answered by a listed next experiment (docs/content/next_experiments.md)
AV2_NEXT = {"AV2-01": "Incremental donor unavailability", "AV2-02": "P0-R: a revised reference policy"}
AV2_V21_NOTE = {"AV2-01": "v2.1: post-plan exploratory donor recount (robbery counts per policy; historical donor hours)",
                "AV2-05": "v2.1: outstation brake allocations flagged as invalid recommendations (frozen results kept)",
                "AV2-06": "v2.1: escalation to reliability engineering and warranty review shown first for the hero part",
                "AV2-07": "robbery wording fixed (used automatically first at AUH, approval flagged, never ranked by the AOG Lab)"}


# ---------------------------------------------------------------------------------------------- text scrub + gate
# The locked config names the archetypes after OEM families. Product text never shows those names, and neither does
# this file: like docs/js/lib/names.js, the patterns are assembled from fragments (as are the forbidden words).
_NB, _WB = "A3" + "20", "78" + "7"
_OEM_NB, _OEM_WB, _BRAND = "Air" + "bus", "Boe" + "ing", "Eti" + "had"
_W_VAL, _W_OPT = "valid" + "ated", "optim" + "al"
_PHRASES = ["represent" + "ative legacy airline practice", "panel" + "-proof", "robust across " + "worlds",
            "saves the airline " + "AED"]
_V1 = "1000[–-]1019"
_ARCH = [
    (re.compile(rf"\b{_NB}(?:-family)?-? and {_WB}-family archetypes\b"), "narrowbody and widebody archetypes"),
    (re.compile(rf"\b{_NB}-family archetype\b"), "narrowbody archetype"),
    (re.compile(rf"\b{_WB}-family archetype\b"), "widebody archetype"),
    (re.compile(rf"\b{_NB}(?:-family|neo|ceo)?\b"), "narrowbody"),
    (re.compile(rf"(?<![\w.,]){_WB}(?:-family|-\d+)?(?=[\s-]+(?:family|archetypes?|LRUs?|fleet|aircraft|types?|IRU|fuel|"
                r"parts?|sectors?|operat|ETOPS|VFSG|boost|tails?|and|or)\b)"), "widebody"),
    (re.compile(rf"\b{_OEM_NB}\b"), "the narrowbody manufacturer"),
    (re.compile(rf"\b{_OEM_WB}\b"), "the widebody manufacturer"),
    (re.compile(rf"\b{_BRAND}\b"), "the airline"),
]
_WORDS = [
    (re.compile(rf"\bis {_W_OPT} only\b"), "gives the best allocation only"),
    (re.compile(rf"\bsub{_W_OPT}\b", re.I), "not the best evaluated"),
    (re.compile(rf"\b{_W_OPT}ity\b", re.I), "being the best evaluated allocation"),
    (re.compile(rf"\b{_W_OPT}\b"), "best evaluated"),
    (re.compile(rf"\b{_W_OPT.capitalize()}\b"), "Best evaluated"),
    (re.compile(rf"\b{_W_VAL}\b"), "verified"),
    (re.compile(rf"\b{_W_VAL.capitalize()}\b"), "Verified"),
    (re.compile(_PHRASES[0], re.I), "a deliberately simplified starting point"),
    (re.compile(_PHRASES[1], re.I), "reviewed"),
    (re.compile(_PHRASES[2], re.I), "consistent across the three stress worlds tested"),
    (re.compile(_PHRASES[3], re.I), "changes simulated cost by AED"),
    (re.compile(rf"seeds {_V1}"), "the retired v1 holdout"),
    (re.compile(_V1), "retired v1 holdout"),
    (re.compile(r"\bnaive 9/9\b"), "naive (lowest-ranked)"),
]

FORBIDDEN_PATTERNS = {
    "OEM name": re.compile(rf"\b{_NB}|\b{_OEM_NB}\b|\b{_OEM_WB}\b|(?<![\w.,]){_WB}(?![\d.,]*\d)(?!\s*(?:h\b|AED|units?\b|k\b|%))"),
    "airline brand": re.compile(rf"\b{_BRAND}\b"),
    "forbidden word": re.compile(rf"\b{_W_VAL}\b|\b{_W_OPT}\b|" + "|".join(_PHRASES), re.I),
    "stale v1 string": re.compile(rf"{_V1}|seeds 1000\b|naive 9/9"),
}


def scrub_text(s: str) -> str:
    for pat, rep in _ARCH + _WORDS:
        s = pat.sub(rep, s)
    return s


def scrub(obj):
    """Apply scrub_text to every string value (keys are left alone)."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        return scrub_text(obj)
    return obj


def _strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def text_violations(obj, skip_paths: tuple = (".meta.git_sha",)) -> list[tuple[str, str, str]]:
    """[(kind, path, excerpt)] for every exported string that breaks the v2.1 text gate. Hashes are skipped."""
    out = []
    for path, s in _strings(obj):
        if path.endswith(skip_paths) or path.endswith(".sha256") or re.fullmatch(r"[0-9a-f]{7,64}", s):
            continue
        for kind, pat in FORBIDDEN_PATTERNS.items():
            m = pat.search(s)
            if m:
                out.append((kind, path, s[max(0, m.start() - 40): m.end() + 40]))
    return out
