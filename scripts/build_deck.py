#!/usr/bin/env python3
"""Build the GROUNDED NO MORE v2 case-study deck (PPTX + PDF).

    python scripts/build_deck.py                      # the deck (+ docs/downloads/case_study_deck.pdf)
    python scripts/build_deck.py --only deck          # same (kept for compatibility)
    python scripts/build_deck.py --build-dir /tmp/x   # keep intermediate assets / slide previews there

Rules this script follows:
* Every number shown is read from docs/data/*.json (and, for the calibration band ends, outputs/freeze/calibration_lock.json)
  at build time. Nothing is typed by hand. The only literals are design constants, layout and fixed prose.
* The headline is the v2 HOLDOUT (seeds 2000-2019, central world): the Network Plan (P2) vs the Simple Rulebook (naive
  reference, P0). The Network Plan + Extra Spares (I125) is the frontier option for additional capital. `sanity_checks()` fails the build if the
  export is not that holdout. Selection-seed numbers are labelled as such; the D015 stress check is labelled post-plan.
* v1 is archived, not a finding: it is mentioned as a correction story only, never with its numbers.
* Falcon Hub Airways is fictional. Only the repo's own SVG illustrations (docs/assets/svg, original plan views) and charts
  rendered here are used. No real airline names or logos.
* One layout spec per slide feeds two renderers: python-pptx (editable PPTX) and an HTML page that Playwright prints to PDF
  (no LibreOffice needed). Charts are matplotlib PNGs; SVG illustrations are rasterised with Playwright so their fonts load.
* Fonts: the vendored woff2 files (docs/vendor/fonts, OFL) are converted to TTF in presentations/fonts so matplotlib can use them
  and so a PowerPoint user can install them. PPTX cannot embed fonts via python-pptx; without the fonts installed PowerPoint
  substitutes its defaults and every text box has slack for that.
* Nothing is posted anywhere.
* v2.1 (v2.1 release brief): A3 display names with the code as a small tag, the verbatim scope line on every
  headline KPI, the A2 reading note, the A4 capital table (never the net alone), A5-A8 texts, the post-plan donor recount
  kept apart from the frozen numbers, and the E4 credit on every slide, all read from docs/data. `text_guards()` fails
  the build on forbidden words, manufacturer names, stale labels, a result claim on the title slide or a missing text.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
SVG_DIR = ROOT / "docs" / "assets" / "svg"
FONT_SRC = ROOT / "docs" / "vendor" / "fonts"
OUT = ROOT / "presentations"
FONT_OUT = OUT / "fonts"

LIVE_URL = "https://akashgajjar07-hue.github.io/grounded-no-more/"
REPO_URL = "https://github.com/akashgajjar07-hue/grounded-no-more"
GITHUB_URL = "https://github.com/akashgajjar07-hue"
AIRLINE = "Falcon Hub Airways (fictional)"

# --------------------------------------------------------------------------------------------------------------------
# Design tokens
# --------------------------------------------------------------------------------------------------------------------
TOK = json.loads((ROOT / "docs" / "design" / "tokens.json").read_text())
C = dict(TOK["color"])
C["faint"] = "#8A9BAD"  # --c-text-faint, derived CSS token in DESIGN_SYSTEM.md (tertiary text, AA on midnight)
PROV_COLOR = {k: C[v] for k, v in TOK["provenance_chip"].items()}
PROV_GLYPH = {"REAL": "●", "DERIVED": "◆", "ASSUMED": "○", "SIMULATED": "▲"}


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def blend(fg, bg, a):
    f, b = hex2rgb(fg), hex2rgb(bg)
    return "#%02X%02X%02X" % tuple(round(f[i] * a + b[i] * (1 - a)) for i in range(3))


HAIR = blend(C["titanium"], C["card"], 0.16)
HAIR_BG = blend(C["titanium"], C["midnight"], 0.16)

FAM = {"display": "Space Grotesk", "ui": "Inter", "mono": "IBM Plex Mono"}
CSS_FAM = {"display": "'Space Grotesk', 'Inter', system-ui, sans-serif", "ui": "'Inter', system-ui, sans-serif",
           "mono": "'IBM Plex Mono', ui-monospace, Menlo, monospace"}
BOLD_W = {"display": 700, "ui": 600, "mono": 600}


# --------------------------------------------------------------------------------------------------------------------
# Data + formatting
# --------------------------------------------------------------------------------------------------------------------
def load(name):
    return json.loads((DATA / f"{name}.json").read_text())


def fmt_aed(x, dp=1):
    a = abs(x)
    s = "−" if x < 0 else ""
    if a >= 1e6:
        return f"{s}AED {a / 1e6:.{dp}f}M"
    if a >= 1e3:
        return f"{s}AED {a / 1e3:.0f}k"
    return f"{s}AED {a:.0f}"


def fmt_m(x, dp=1):
    return f"{x / 1e6:.{dp}f}"


def half_up1(x):
    """One decimal, half away from zero: the same rule as the site's fmt1 and render_docs.fmt_half_up1."""
    v = math.floor(abs(x) * 10 + 0.5) / 10
    return f"{-v if x < 0 else v:.1f}"


# v2.2 (review #42): one set of part-type names, as the site's Simple mode uses them
PART_TYPE = {"R": "Repairable", "E": "Throw-away", "C": "Consumable"}


def fmt_int(x):
    s = "−" if x < 0 else ""
    return f"{s}{abs(round(x)):,}"


def fmt_pct(x, dp=1):
    return f"{x * 100:.{dp}f}%"


def fmt_signed(x, fn=fmt_int):
    return ("+" if x > 0 else "") + fn(x)


def ci_txt(ci, fn=fmt_int):
    return f"[{fn(ci[0])}, {fn(ci[1])}]"




DOWNLOADS = ROOT / "docs" / "downloads"
CREDIT = {"text": ""}
SCOPE = {"text": ""}  # verbatim scope line, set from docs/data/kpis.json  # E4 footer credit, set from docs/data/kpis.json by compute_numbers()
CAL_LOCK = ROOT / "outputs" / "freeze" / "calibration_lock.json"
V2_HOLDOUT_SEEDS = list(range(2000, 2020))
V1_HOLDOUT_SEEDS = set(range(1000, 1020))


def fmt_mm(x, dp=1):
    """Always in millions: AED 0.6M, −AED 33.9M."""
    return f"{'−' if x < 0 else ''}AED {abs(x) / 1e6:.{dp}f}M"


def ci_m(ci, dp=1):
    return f"[{ci[0] / 1e6:.{dp}f}, {ci[1] / 1e6:.{dp}f}]".replace("-", "−")


def aed_ci(mean, lo, hi, signed=False):
    """v2.2 (review #20): money with CI on the docs' scale and rounding (render_docs.fmt_aed_ci), deck bracket style:
    AED 33.9M [37.9, 29.9] for millions, AED 0.36M [−0.75, 1.46] below AED 1M."""
    big = max(abs(mean), abs(lo), abs(hi))
    sign = ("+" if mean > 0 else "−" if mean < 0 else "") if signed else ("−" if mean < 0 else "")
    d = 1 if abs(mean) >= 1e6 else 2 if big >= 1e5 else None
    if d is None:
        return f"{sign}AED {abs(mean):,.0f} {ci_txt([lo, hi])}"
    return f"{sign}AED {abs(mean) / 1e6:.{d}f}M {ci_m([lo, hi], d)}"


def ci_h(ci):
    """Hours CI with an en dash: [1,332–1,629] (signs dropped by the caller where it says 'cuts')."""
    return f"[{fmt_int(ci[0])}–{fmt_int(ci[1])}]"


def compute_numbers():
    """Read everything the slides need from docs/data. Returns a flat dict N plus a few tables."""
    k, pol, fr, fc = load("kpis"), load("policies"), load("frontier"), load("forecast")
    rot, net, aog, act = load("rotables"), load("network"), load("aog_lab"), load("actions")
    meth, parts, dh = load("method"), load("parts"), load("demand_history")
    N = {"raw": dict(k=k, pol=pol, fr=fr, fc=fc, rot=rot, net=net, aog=aog, act=act, meth=meth, parts=parts)}
    from collections import Counter
    import statistics as st

    # Headline blocks (computed by the exporter from outputs/holdout; we only read and cross-check them)
    H = k["headline"]
    N["core"], N["fo"], N["hon"] = H["core"], H["frontier_option"], H["honest"]
    N["kpi"] = {x["id"]: x for x in k["kpis"]}
    N["core_id"], N["base_id"], N["fo_id"] = k["core_id"], k["baseline_id"], H["frontier_option"]["id"]
    N["rec_id"] = k["recommended_id"]
    N["seeds"] = k["seeds"]
    N["n_seeds"] = len(k["seeds"])
    N["kpi_weeks"] = k["kpi_weeks"]
    N["seed_txt"] = f"v2 holdout seeds {k['seeds'][0]}–{k['seeds'][-1]} (n={len(k['seeds'])}), central world"
    N["base_label"] = N["core"]["baseline_label"]

    pols = {p["policy_id"]: p for p in pol["policies"]}
    N["pols"] = pols
    N["paired"] = pol["paired"]
    N["fo_vs_P2"] = pol["recommended_vs_P2"]
    N["by_class"] = {(r["policy_id"], r["part_class"]): r for r in pol["by_class"] if r["variant"] == "central"}
    N["pol_split"], N["pol_seeds"] = pol["split"], pol["seeds"]

    # Fleet / scope
    A = {a["key"]: a for a in meth["assumptions"]}
    N["nb"] = int(A["fleet.narrowbody.count"]["value"])
    N["wb"] = int(A["fleet.widebody.count"]["value"])
    N["n_parts"] = len(parts["parts"])
    N["cls_counts"] = Counter(p["cls"] for p in parts["parts"])
    N["n_stations"] = len(net["stations"])
    N["stations"] = net["stations"]
    N["st"] = {s["station"]: s for s in net["stations"]}
    N["hub"] = net["hub"]
    N["n_weeks"] = len(next(iter(dh["series"].values())))
    N["split_week"] = dh["split_week"]
    zs = [sum(1 for v in ser[:dh["split_week"]] if v == 0) / dh["split_week"] for ser in dh["series"].values()]
    N["n_mostly_zero"] = sum(1 for z in zs if z > 0.5)
    N["prov_counts"] = Counter(a["provenance"] for a in meth["assumptions"])
    N["n_assump"] = len(meth["assumptions"])
    N["requests_hist"] = sum(s["requests"] for s in net["stations"])
    # Outstation rotables per policy, summed from network.json (cross-checked against the headline in sanity_checks)
    N["out_rot"] = {p: sum(s["by_policy"][p]["rotable_units"] for s in net["stations"] if s["role"] != "hub")
                    for p in ("P0", "P1", "P2", "I125")}

    # AOG lab
    inc = {i["id"]: i for i in aog["incidents"]}
    N["inc"] = inc[aog["ps1_incident_id"]] if aog.get("ps1_incident_id") in inc else inc["AOG-0001"]
    N["aog_sum"] = aog["summary"]
    N["part"] = {p["pn"]: p for p in parts["parts"]}

    # Forecast honesty
    N["rel_vs_croston"] = fc["reliability_vs_croston"]
    N["champion_check"] = fc["champion_check"]
    N["ltd"] = fc["ltd_example"]
    N["lb_class_hold"] = fc["leaderboard_by_class_holdout"]
    N["monash_n"] = fc["monash"]["info"]["n_series"]
    N["parts"] = parts["parts"]
    N["truth"] = {t["param"]: t for t in fc["truth_recovery"]}
    N["method_labels"] = fc["method_labels"]

    # Rotable float example (the PS1 part) and Palm vs sim
    N["float"] = [x for x in rot["float_examples"] if x["pn"] == N["ltd"]["pn"]][0]
    sv = N["float"]["station_view"]
    N["sv"] = sv
    pvs = [x for x in rot["palm_vs_sim"] if x["station"] == N["hub"] and x["sim_requests"] > 0]
    N["palm_hub_n"] = len(pvs)
    N["palm_hub_palm"] = sum(x["palm_availability"] for x in pvs) / len(pvs)
    N["palm_hub_sim"] = sum(x["sim_immediate_fill"] for x in pvs) / len(pvs)
    N["palm_vs_sim_policy"] = rot.get("palm_vs_sim_policy", "P1")
    lam = N["ltd"]["mean"]
    N["s_bom"] = sv["units"]["P2"]
    # Palm immediate fill at BOM: P(X <= S-1), X ~ Poisson(lambda*T) over the AUH resupply time (V2-SIM-10 semantics)
    N["palm_bom"] = sum(math.exp(-lam) * lam ** j / math.factorial(j) for j in range(N["s_bom"]))

    # Frontier
    N["points"] = fr["points"]
    N["pt"] = {p["id"]: p for p in fr["points"]}
    N["spt"] = {p["id"]: p for p in fr["selection_points"]}
    N["reco"] = fr["recommendation"]
    N["tornado"] = fr["tornado"]
    N["variants"] = {v["variant"]: v for v in fr["variant_robustness"]}
    N["desk"] = fr["aog_desk_dependence"]
    N["consistency"] = {c["id"]: c for c in k["consistency"]}
    N["fr_split"] = fr["split"]

    # buy-1 vs TAT-10d (same comparison the capital screen makes)
    by = {}
    for r in fr["levers"]:
        by.setdefault(r["pn"], {})[r["lever"]] = r
    buy_wins = tat_wins = 0
    for pn, d in by.items():
        b, t = d.get("buy_1"), d.get("tat_cut_10d")
        if not b or not t or not b["annual_cost_per_aog_hour_aed"] or not t["annual_cost_per_aog_hour_aed"]:
            continue
        if b["aog_hours_reduction"] <= 0 or t["aog_hours_reduction"] <= 0:
            continue
        if b["annual_cost_per_aog_hour_aed"] < t["annual_cost_per_aog_hour_aed"]:
            buy_wins += 1
        else:
            tat_wins += 1
    N["buy_wins"], N["tat_wins"] = buy_wins, tat_wins
    lf = fr.get("lever_findings", {})
    ex = [x for x in lf.get("tat_vs_buy_2", []) + lf.get("tat_vs_buy_1", []) if x.startswith(N["ltd"]["pn"])]
    ex = ex or (lf.get("tat_vs_buy_1", []) + lf.get("tat_vs_buy_2", []))
    N["lever_ex"] = ("Example: " + ex[0].replace("1 spares", "1 spare")) if ex else ""
    N["buy_med"] = st.median(r["annual_cost_per_aog_hour_aed"] for r in fr["levers"]
                             if r["lever"] == "buy_1" and r["annual_cost_per_aog_hour_aed"] and r["aog_hours_reduction"] > 0)
    N["tat_med"] = st.median(r["annual_cost_per_aog_hour_aed"] for r in fr["levers"]
                             if r["lever"] == "tat_cut_10d" and r["annual_cost_per_aog_hour_aed"] and r["aog_hours_reduction"] > 0)

    # Actions
    N["act_counts"] = act["counts"]
    N["act_week"] = act["as_of_week"]
    N["n_actions"] = len(act["actions"])
    N["actions"] = act["actions"]

    # Validation, calibration, freeze, v1 archive
    N["validation"] = meth["validation"]
    N["cal"] = meth["calibration"]
    N["v1"] = meth["v1_archive"]
    N["freeze"] = meth["freeze"]
    lock = json.loads(CAL_LOCK.read_text())
    N["cal_lock"] = lock
    N["cal_targets"] = lock["targets"]
    N["cal_ach"] = {v: lock["achieved"][v]["history"] for v in ("central", "low_stress", "high_stress")}
    N["meta_sha"] = k["meta"]["git_sha"]
    N["release"] = k["meta"].get("release", "v2.2")   # shown instead of the hash (review #2)
    N["generated_at"] = k["meta"]["generated_at"]

    # v2.1 verbatim texts and display names (v2.1 release brief): read from docs/data, never typed
    N["dn"] = k["display_names"]
    N["scope"] = k["scope_line"]
    N["reading"] = k["reading_note"]
    N["routes_line"] = k["headline"]["honest"]["routes_line"]   # v2.2 (5.1): one plain line under the reading note
    N["credit"] = k["footer"]
    CREDIT["text"] = k["footer"]
    SCOPE["text"] = k["scope_line"]
    N["landing"] = k["landing"]
    N["cap_t"] = k["capital_table"]
    N["sw"] = k["stress_worlds"]
    N["ins"] = k["frontier_insight"]
    N["donor"] = k["donor_recount"]
    N["cal_note"] = meth["calibration_note"]
    N["esc"] = [p_["escalation"] for p_ in parts["parts"] if p_.get("escalation")][0]
    N["esc_pn"] = [p_["pn"] for p_ in parts["parts"] if p_.get("escalation")][0]
    N["invalid"] = parts["invalid_allocations"]
    N["invalid_text"] = parts["invalid_allocation_text"]
    return N


def sanity_checks(N):
    """Fail the build loudly unless the export is the v2 holdout with the user's headline framing."""
    k, core, fo = N["kpi"], N["core"], N["fo"]
    hold = V2_HOLDOUT_SEEDS
    # 1. The headline must be the v2 holdout, central world (never selection seeds, never the retired v1 holdout).
    assert N["raw"]["k"]["split"] == "holdout", "kpis.json is not the holdout split"
    assert N["seeds"] == hold, f"headline seeds {N['seeds'][:3]}... are not the v2 holdout 2000-2019"
    assert not (set(N["seeds"]) & V1_HOLDOUT_SEEDS), "retired v1 holdout seeds in the headline"
    assert core["split"] == "holdout" and core["variant"] == "central" and core["paired"], "core headline not holdout"
    assert core["seeds"] == hold, "core headline seeds are not 2000-2019"
    assert N["pol_split"] == "holdout" and N["pol_seeds"] == hold, "policies.json is not the v2 holdout"
    assert N["fr_split"] == "holdout", "frontier.json points are not the holdout"
    for x in k.values():
        if x.get("split") not in (None, "history"):
            assert x["split"] == "holdout", f"KPI {x['id']} is not holdout"
    # 2. Framing: P2 is the core finding vs P0; I125 is the frontier option.
    assert N["core_id"] == "P2" and core["id"] == "P2" and core["vs"] == "P0" and N["base_id"] == "P0"
    assert fo["id"] == "I125" and fo["vs"] == "P2" and N["rec_id"] == "I125" and N["pt"]["I125"]["recommended"]
    # 3. Independent cross-checks between files.
    pr = N["paired"]["P2-P0"]
    assert round(-pr["aog_hours"]["mean"]) == round(core["aog_reduction"]["mean"]), "core AOG reduction mismatch"
    assert round(pr["spare_capital_aed"]["mean"]) == round(core["capital_aed"]["mean"]), "core capital mismatch"
    assert abs(N["pols"]["P2"]["kpi"]["aog_hours"]["mean"] - k["aog_hours"]["value"]) < 1e-6
    assert abs(N["pols"]["P0"]["kpi"]["aog_hours"]["mean"] - k["aog_hours"]["baseline"]) < 1e-6
    for p in ("P0", "P1", "P2"):
        assert N["out_rot"][p] == core["outstation_rotables"][p], f"outstation rotables {p} mismatch"
    assert f"only {N['out_rot']['P0']} outstation rotables" in N["base_label"], "baseline label disagrees with network.json"
    assert round(N["fo_vs_P2"]["capital"]["mean"]) == round(fo["extra_capital_aed"]["mean"])
    assert abs(-N["fo_vs_P2"]["aog_hours"]["mean"] - fo["aog_reduction"]["mean"]) < 0.06
    assert abs(N["pt"]["I125"]["aog_hours"] - fo["aog_hours"]) < 0.6
    assert core["holds_all_worlds"] and all(w["significant"] and w["aog_hours"]["ci"][1] < 0 for w in core["worlds"])
    assert core["holds_penalty_range"] and all(v["ci"][1] < 0 for v in core["penalty_range"].values())
    # 4. AOG-0001 exposure reconciles (hours x rate + fixed event cost + logistics).
    inc = N["inc"]
    cf = inc["counterfactual"]
    assert inc["aog_hours"] * inc["rate_aed_per_h"] + inc["event_cost_aed"] + cf["actual_direct_cost_aed"] == \
        cf["actual_exposure_aed"], "AOG-0001 exposure does not reconcile"
    # 5. Palm example: our Poisson calculation must match the exporter's station view.
    assert abs(N["palm_bom"] - N["sv"]["availability"]["P2"]) < 5e-4, (N["palm_bom"], N["sv"]["availability"])
# --------------------------------------------------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------------------------------------------------
def _brotli_shim():
    try:
        import brotli  # noqa: F401
        return True
    except ImportError:
        pass
    node = shutil.which("node")
    if not node:
        return False
    js = ("const z=require('zlib');let c=[];process.stdin.on('data',d=>c.push(d));"
          "process.stdin.on('end',()=>process.stdout.write(z.brotliDecompressSync(Buffer.concat(c))))")

    def decompress(data):
        return subprocess.run([node, "-e", js], input=data, capture_output=True, check=True).stdout

    class Decompressor:
        def process(self, data, output_buffer_limit=None):
            return decompress(data)

        def is_finished(self):
            return True

    mod = types.ModuleType("brotli")
    mod.decompress, mod.Decompressor = decompress, Decompressor
    sys.modules["brotli"] = mod
    import fontTools.ttLib.woff2 as w2
    w2.brotli, w2.haveBrotli = mod, True
    return True


FONT_PLAN = [  # (dir, family, weight, style name)
    ("space-grotesk", "Space Grotesk", 400, "Regular"), ("space-grotesk", "Space Grotesk", 700, "Bold"),
    ("inter", "Inter", 400, "Regular"), ("inter", "Inter", 600, "Bold"),
    ("ibm-plex-mono", "IBM Plex Mono", 400, "Regular"), ("ibm-plex-mono", "IBM Plex Mono", 600, "Bold"),
]


def prepare_fonts():
    """woff2 -> TTF (renamed to plain family + Regular/Bold) in presentations/fonts. Returns list of TTF paths."""
    FONT_OUT.mkdir(parents=True, exist_ok=True)
    out = []
    need = [FONT_OUT / f"{fam.replace(' ', '')}-{sty}.ttf" for _, fam, _, sty in FONT_PLAN]
    if all(p.exists() for p in need):
        return need
    if not _brotli_shim():
        print("! fonts: no brotli/node available; charts fall back to DejaVu Sans", file=sys.stderr)
        return []
    from fontTools.ttLib import TTFont
    for (d, fam, w, sty), dst in zip(FONT_PLAN, need):
        src = FONT_SRC / d / f"{d}-latin-{w}-normal.woff2"
        t = TTFont(str(src))
        t.flavor = None
        name = t["name"]
        ps = f"{fam.replace(' ', '')}-{sty}"
        for rec_id, val in [(1, fam), (2, sty), (4, f"{fam} {sty}"), (6, ps), (16, fam), (17, sty)]:
            name.setName(val, rec_id, 3, 1, 0x409)
            name.setName(val, rec_id, 1, 0, 0)
        t["OS/2"].usWeightClass = w
        if sty == "Bold":
            t["OS/2"].fsSelection = (t["OS/2"].fsSelection | 0x20) & ~0x40 & ~0x01
            t["head"].macStyle |= 0x01
        else:
            t["OS/2"].fsSelection = (t["OS/2"].fsSelection | 0x40) & ~0x20
            t["head"].macStyle &= ~0x01
        t.save(str(dst))
        out.append(dst)
        lic = FONT_SRC / d / "OFL.txt"
        if lic.exists():
            shutil.copy(lic, FONT_OUT / f"OFL-{d}.txt")
    (FONT_OUT / "README.txt").write_text(
        "TTF conversions of the OFL fonts vendored in docs/vendor/fonts (latin subsets), renamed to plain family names.\n"
        "Install them to see case_study_deck.pptx exactly as designed; otherwise PowerPoint substitutes its defaults.\n"
        "Licences: OFL-*.txt (SIL Open Font License 1.1). Generated by scripts/build_deck.py.\n")
    return out


def setup_matplotlib(ttfs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    for p in ttfs:
        fm.fontManager.addfont(str(p))
    fams = {f.name for f in fm.fontManager.ttflist}
    ui = "Inter" if "Inter" in fams else "DejaVu Sans"
    mono = "IBM Plex Mono" if "IBM Plex Mono" in fams else "DejaVu Sans Mono"
    disp = "Space Grotesk" if "Space Grotesk" in fams else ui
    plt.rcParams.update({
        "font.family": ui, "font.size": 9, "text.color": C["titanium"], "axes.labelcolor": C["titanium"],
        "axes.edgecolor": HAIR_BG, "xtick.color": C["faint"], "ytick.color": C["faint"], "axes.facecolor": "none",
        "figure.facecolor": "none", "savefig.facecolor": "none", "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.8, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 3,
        "ytick.major.size": 3, "svg.fonttype": "none", "axes.titlesize": 10,
    })
    return plt, {"ui": ui, "mono": mono, "display": disp}


# --------------------------------------------------------------------------------------------------------------------
# Layout spec: one Slide feeds both renderers. Units are CSS px (96 per inch).
# --------------------------------------------------------------------------------------------------------------------
STY = {
    "eyebrow": dict(f="mono", s=9, c=C["aero_teal"], b=True, sp=1.6),
    "title": dict(f="display", s=26, c=C["ice"], b=True, sp=-0.3),
    "lede": dict(f="ui", s=12.5, c=C["titanium"]),
    "body": dict(f="ui", s=11, c=C["ice"]),
    "bodym": dict(f="ui", s=11, c=C["titanium"]),
    "small": dict(f="ui", s=9, c=C["faint"]),
    "label": dict(f="mono", s=8, c=C["titanium"], sp=1.0),
    "mono": dict(f="mono", s=9.5, c=C["ice"]),
    "monos": dict(f="mono", s=8.5, c=C["titanium"]),
    "big": dict(f="display", s=30, c=C["aero_teal"], b=True, sp=-0.5),
    "mid": dict(f="display", s=18, c=C["ice"], b=True),
    "h3": dict(f="display", s=13, c=C["ice"], b=True),
}


def R(text, sty="body", **ov):
    d = dict(STY[sty])
    d.update(ov)
    d["t"] = text
    return d


def P(*runs, al="l", after=0, ls=1.0):
    return dict(runs=[r if isinstance(r, dict) else R(r) for r in runs], al=al, after=after, ls=ls)


class Slide:
    def __init__(self, w=1280, h=720, bg=None):
        self.w, self.h, self.bg, self.items = w, h, bg, []

    def rect(self, x, y, w, h, fill=None, line=None, lw=1.0, r=0, dash=False):
        self.items.append(dict(k="rect", x=x, y=y, w=w, h=h, fill=fill, line=line, lw=lw, r=r, dash=dash))

    def line(self, x1, y1, x2, y2, color=HAIR_BG, lw=1.0, dash=False):
        self.items.append(dict(k="line", x1=x1, y1=y1, x2=x2, y2=y2, c=color, lw=lw, dash=dash))

    def text(self, x, y, w, h, paras, anchor="t"):
        if isinstance(paras, dict):
            paras = [paras]
        self.items.append(dict(k="text", x=x, y=y, w=w, h=h, paras=paras, anchor=anchor))

    def image(self, x, y, w, h, path, fit="contain", align="c"):
        from PIL import Image
        iw, ih = Image.open(path).size
        if fit == "contain":
            s = min(w / iw, h / ih)
            nw, nh = iw * s, ih * s
            nx = x + {"l": 0, "c": (w - nw) / 2, "r": w - nw}[align]
            ny = y + (h - nh) / 2
        else:
            nx, ny, nw, nh = x, y, w, h
        self.items.append(dict(k="img", x=nx, y=ny, w=nw, h=nh, path=str(path)))

    # composites -----------------------------------------------------------------------------------------------------
    def card(self, x, y, w, h, fill=None, line=None):
        self.rect(x, y, w, h, fill=fill or C["card"], line=line or HAIR, lw=1, r=10)

    def chip(self, x, y, prov, label=None):
        col = PROV_COLOR[prov]
        txt = f"{PROV_GLYPH[prov]} {label or prov}"
        w = 20 + len(txt) * 7.5
        self.rect(x, y, w, 18, fill=blend(col, C["card"], 0.12), line=blend(col, C["card"], 0.55), lw=0.75, r=9)
        self.text(x, y + 3, w, 14, P(R(txt, "label", c=col, s=7.5, b=True, sp=0.6), al="c"))
        return w

    def chip_r(self, right, y, prov, label=None):
        txt = f"{PROV_GLYPH[prov]} {label or prov}"
        return self.chip(right - (20 + len(txt) * 7.5), y, prov, label)

    def header(self, num, eyebrow, title, lede=None, total=10):
        self.text(48, 34, 900, 16, P(R(f"{num:02d} · {eyebrow.upper()}", "eyebrow")))
        self.text(48, 50, 1184, 46, P(R(title, "title", s=24)))
        if lede:
            self.text(48, 92, 1160, 48, P(R(lede, "lede", s=12), ls=1.05))

    def footer(self, num, source, total=10):
        self.line(48, 678, 1232, 678, HAIR_BG, 0.75)
        self.text(48, 683, 1060, 13, P(R(CREDIT["text"], "small", s=7.3, c=C["titanium"])))
        self.text(48, 697, 1060, 13, P(R(f"GROUNDED NO MORE · {AIRLINE} · simulated planning snapshot · {source}",
                                         "small", s=6.8)))
        self.text(1032, 683, 200, 13, P(R(f"{num:02d} / {total:02d}", "label", s=7.3, c=C["faint"]), al="r"))

    def scope(self, x, y, w, s=7.8, al="l"):
        """The verbatim scope line every headline KPI carries (v2.1 brief)."""
        self.text(x, y, w, 14, P(R(SCOPE["text"], "monos", s=s, c=C["aero_teal"]), al=al))


# --------------------------------------------------------------------------------------------------------------------
# HTML renderer (-> PDF + PNG previews via Playwright)
# --------------------------------------------------------------------------------------------------------------------
def font_face_css():
    css = []
    for fam, d, ws in [("Space Grotesk", "space-grotesk", [400, 500, 600, 700]), ("Inter", "inter", [400, 500, 600]),
                       ("IBM Plex Mono", "ibm-plex-mono", [400, 500, 600])]:
        for w in ws:
            css.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:normal;"
                       f"src:url('{(FONT_SRC / d / f'{d}-latin-{w}-normal.woff2').as_uri()}') format('woff2')}}")
    return "\n".join(css)


def run_css(r):
    w = BOLD_W[r["f"]] if r.get("b") else 400
    sp = f"letter-spacing:{r.get('sp', 0)}pt;" if r.get("sp") else ""
    return f"font-family:{CSS_FAM[r['f']]};font-size:{r['s']}pt;color:{r['c']};font-weight:{w};{sp}"


def render_html(slides, page_w, page_h):
    out = [f"<!doctype html><html><head><meta charset='utf-8'><style>{font_face_css()}"
           f"@page{{size:{page_w}px {page_h}px;margin:0}} html,body{{margin:0;padding:0;background:{C['midnight']}}}"
           f".slide{{position:relative;width:{page_w}px;height:{page_h}px;overflow:hidden;page-break-after:always;"
           f"break-after:page}} .slide>*{{position:absolute;box-sizing:border-box}} p{{margin:0;white-space:pre-wrap}}"
           f".tx{{display:flex;flex-direction:column;font-variant-numeric:tabular-nums}}</style></head><body>"]
    for s in slides:
        out.append(f"<section class='slide' style='background:{C['midnight']}'>")
        if s.bg:
            out.append(f"<img src='{Path(s.bg).as_uri()}' style='left:0;top:0;width:{s.w}px;height:{s.h}px'>")
        for it in s.items:
            k = it["k"]
            if k == "rect":
                bd = f"border:{it['lw']}px {'dashed' if it['dash'] else 'solid'} {it['line']};" if it["line"] else ""
                out.append(f"<div style='left:{it['x']}px;top:{it['y']}px;width:{it['w']}px;height:{it['h']}px;"
                           f"background:{it['fill'] or 'transparent'};{bd}border-radius:{it['r']}px'></div>")
            elif k == "line":
                x1, y1, x2, y2 = it["x1"], it["y1"], it["x2"], it["y2"]
                L = math.hypot(x2 - x1, y2 - y1)
                ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
                st = "dashed" if it["dash"] else "solid"
                out.append(f"<div style='left:{x1}px;top:{y1 - it['lw'] / 2}px;width:{L}px;height:0;"
                           f"border-top:{it['lw']}px {st} {it['c']};transform-origin:0 50%;transform:rotate({ang}deg)'></div>")
            elif k == "img":
                out.append(f"<img src='{Path(it['path']).as_uri()}' style='left:{it['x']}px;top:{it['y']}px;"
                           f"width:{it['w']}px;height:{it['h']}px'>")
            elif k == "text":
                jc = {"t": "flex-start", "m": "center", "b": "flex-end"}[it["anchor"]]
                ps = []
                for p in it["paras"]:
                    al = {"l": "left", "c": "center", "r": "right"}[p["al"]]
                    mx = max(r["s"] for r in p["runs"])
                    runs = "".join(f"<span style=\"{run_css(r)}\">{html.escape(r['t'])}</span>" for r in p["runs"])
                    ps.append(f"<p style='font-size:{mx}pt;text-align:{al};line-height:{p['ls'] * 1.2 * mx:.2f}pt;"
                              f"margin-bottom:{p['after']}pt'>{runs}</p>")
                out.append(f"<div class='tx' style='left:{it['x']}px;top:{it['y']}px;width:{it['w']}px;"
                           f"height:{it['h']}px;justify-content:{jc}'>{''.join(ps)}</div>")
        out.append("</section>")
    out.append("</body></html>")
    return "".join(out)


def html_to_pdf_and_png(html_text, page_w, page_h, pdf_path, png_dir, prefix, scale=1.5):
    from playwright.sync_api import sync_playwright
    png_dir.mkdir(parents=True, exist_ok=True)
    hp = png_dir / f"{prefix}.html"
    hp.write_text(html_text)
    pngs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": page_w, "height": page_h}, device_scale_factor=scale)
        pg.goto(hp.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(400)
        overflow = pg.evaluate("""() => [...document.querySelectorAll('.tx')].map((d,i)=>{
            const sl=[...document.querySelectorAll('.slide')].indexOf(d.closest('.slide'))+1;
            return {sl, over: d.scrollHeight - d.clientHeight, wover: d.scrollWidth - d.clientWidth,
                    txt: d.innerText.slice(0,60)}}).filter(o=>o.over>6||o.wover>2)""")
        for o in overflow:
            print(f"  ! overflow slide {o['sl']}: +{o['over']}px h, +{o['wover']}px w :: {o['txt']!r}")
        for i, el in enumerate(pg.locator("section.slide").all(), 1):
            f = png_dir / f"{prefix}-{i:02d}.png"
            el.screenshot(path=str(f))
            pngs.append(f)
        pg.pdf(path=str(pdf_path), width=f"{page_w}px", height=f"{page_h}px", print_background=True,
               margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        b.close()
    return pngs


# --------------------------------------------------------------------------------------------------------------------
# PPTX renderer
# --------------------------------------------------------------------------------------------------------------------
def render_pptx(slides, path):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.dml import MSO_LINE_DASH_STYLE
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.util import Emu, Pt

    E = lambda px: Emu(int(round(px * 9525)))  # noqa: E731
    prs = Presentation()
    prs.slide_width, prs.slide_height = E(slides[0].w), E(slides[0].h)
    blank = prs.slide_layouts[6]
    rgb = lambda h: RGBColor(*hex2rgb(h))  # noqa: E731
    for s in slides:
        sl = prs.slides.add_slide(blank)
        bgf = sl.background.fill
        bgf.solid()
        bgf.fore_color.rgb = rgb(C["midnight"])
        if s.bg:
            sl.shapes.add_picture(s.bg, 0, 0, E(s.w), E(s.h))
        for it in s.items:
            k = it["k"]
            if k == "rect":
                shp = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if it["r"] else MSO_SHAPE.RECTANGLE,
                                          E(it["x"]), E(it["y"]), E(it["w"]), E(it["h"]))
                if it["r"]:
                    shp.adjustments[0] = min(0.5, it["r"] / max(1, min(it["w"], it["h"])))
                if it["fill"]:
                    shp.fill.solid()
                    shp.fill.fore_color.rgb = rgb(it["fill"])
                else:
                    shp.fill.background()
                if it["line"]:
                    shp.line.color.rgb = rgb(it["line"])
                    shp.line.width = Pt(it["lw"] * 0.75)
                    if it["dash"]:
                        shp.line.dash_style = MSO_LINE_DASH_STYLE.DASH
                else:
                    shp.line.fill.background()
                shp.shadow.inherit = False
                shp.text_frame.text = ""
            elif k == "line":
                ln = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, E(it["x1"]), E(it["y1"]), E(it["x2"]), E(it["y2"]))
                ln.line.color.rgb = rgb(it["c"])
                ln.line.width = Pt(it["lw"] * 0.75)
                if it["dash"]:
                    ln.line.dash_style = MSO_LINE_DASH_STYLE.DASH
            elif k == "img":
                sl.shapes.add_picture(it["path"], E(it["x"]), E(it["y"]), E(it["w"]), E(it["h"]))
            elif k == "text":
                tb = sl.shapes.add_textbox(E(it["x"]), E(it["y"]), E(it["w"]), E(it["h"]))
                tf = tb.text_frame
                tf.word_wrap = True
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
                tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[it["anchor"]]
                for pi, p in enumerate(it["paras"]):
                    para = tf.paragraphs[0] if pi == 0 else tf.add_paragraph()
                    para.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[p["al"]]
                    para.line_spacing = p["ls"]
                    para.space_after = Pt(p["after"])
                    for r in p["runs"]:
                        run = para.add_run()
                        run.text = r["t"]
                        f = run.font
                        f.name = FAM[r["f"]]
                        f.size = Pt(r["s"])
                        f.bold = bool(r.get("b"))
                        f.color.rgb = rgb(r["c"])
                        rpr = run._r.get_or_add_rPr()
                        if r.get("sp"):
                            rpr.set("spc", str(int(r["sp"] * 100)))
                        # east-asian / complex-script fallbacks keep glyphs like ● ◆ ▲ rendering
                        for tag in ("a:ea", "a:cs"):
                            el = rpr.find(qn(tag))
                            if el is None:
                                el = rpr.makeelement(qn(tag), {})
                                rpr.append(el)
                            el.set("typeface", FAM[r["f"]])
        if getattr(s, "notes", None):
            sl.notes_slide.notes_text_frame.text = s.notes
    prs.save(path)


# --------------------------------------------------------------------------------------------------------------------
# Assets: background, SVG rasters, charts
# --------------------------------------------------------------------------------------------------------------------
def make_background(path, w, h, scale=2, marks=True):
    from PIL import Image, ImageDraw
    W, H = w * scale, h * scale
    im = Image.new("RGB", (W, H), hex2rgb(C["midnight"]))
    d = ImageDraw.Draw(im, "RGBA")
    teal = hex2rgb(C["aero_teal"])
    step = 24 * scale
    for i, x in enumerate(range(0, W + 1, step)):
        a = 26 if i % 5 == 0 else 12
        d.line([(x, 0), (x, H)], fill=teal + (a,), width=1)
    for i, y in enumerate(range(0, H + 1, step)):
        a = 26 if i % 5 == 0 else 12
        d.line([(0, y), (W, y)], fill=teal + (a,), width=1)
    # soft vignette towards the edges keeps the grid quiet behind text
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    for i in range(40):
        a = int(110 * (1 - i / 40) ** 2)
        vd.rectangle([i * W // 90, i * H // 90, W - i * W // 90, H - i * H // 90], outline=a, width=max(1, W // 90))
    im = Image.composite(Image.new("RGB", (W, H), hex2rgb(C["midnight"])), im, vig)
    d = ImageDraw.Draw(im, "RGBA")
    if marks:  # blueprint corner registration marks
        ti = hex2rgb(C["titanium"]) + (90,)
        m, L = 20 * scale, 14 * scale
        for cx, cy, sx, sy in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
            d.line([(cx, cy), (cx + sx * L, cy)], fill=ti, width=scale)
            d.line([(cx, cy), (cx, cy + sy * L)], fill=ti, width=scale)
    im.save(path)
    return path



def rasterise_svgs(build, N):
    """SVG -> PNG with Playwright so the SVGs' own fonts render. Sheet frames, title blocks and callouts are hidden so the
    original plan views sit on the slide grid; each uses its own data-compact-viewbox (the airframe bounds)."""
    from playwright.sync_api import sync_playwright
    bare = (".bp-frameset,.bp-tblock,.bp-orient,.bp-gridfill,.bp-callout,.hs-badge,.bp-tb{display:none!important}")
    jobs = [  # key, file, extra css, js
        ("nb", "aircraft-narrowbody.svg", bare, None),
        ("wb", "aircraft-widebody.svg", bare, None),
        ("nb-32", "aircraft-narrowbody.svg", bare + "#ata-32 .hs-badge{display:inline!important}",
         "document.querySelector('#ata-32').classList.add('is-active');"),
        ("exploded-32", "exploded-32.svg", ".bp-frameset{display:none}", None),
    ]
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=2)
        for key, fn, css, js in jobs:
            svg = (SVG_DIR / fn).read_text().split("?>", 1)[-1]
            pg.set_content(f"<html><head><style>{font_face_css()} html,body{{margin:0;background:transparent}}"
                           f"svg{{display:block}} {css}</style></head><body>{svg}</body></html>")
            pg.evaluate("document.fonts.ready")
            pg.evaluate("""(()=>{const s=document.querySelector('svg');const vb=s.getAttribute('data-compact-viewbox');
                if(vb){s.setAttribute('viewBox',vb);const v=vb.split(' ').map(Number);
                s.setAttribute('width',v[2]);s.setAttribute('height',v[3]);}})()""")
            if js:
                pg.evaluate(f"(()=>{{{js}}})()")
            pg.evaluate("document.querySelectorAll('.bp-gridfill,.bp-frame,.bp-frame-thin,.bp-tb').forEach(e=>e.style.display='none')")
            pg.wait_for_timeout(250)
            f = build / f"svg-{key}.png"
            pg.locator("svg").first.screenshot(path=str(f), omit_background=True)
            out[key] = f
        b.close()
    return out


class Charts:
    def __init__(self, plt, fonts, build, N):
        self.plt, self.F, self.build, self.N = plt, fonts, build, N

    def _save(self, fig, name):
        f = self.build / f"chart-{name}.png"
        fig.savefig(f, dpi=300, transparent=True)
        self.plt.close(fig)
        return f

    def _fig(self, wpx, hpx):
        return self.plt.figure(figsize=(wpx / 96, hpx / 96))

    def mono_ticks(self, ax, size=8):
        for t in ax.get_xticklabels() + ax.get_yticklabels():
            t.set_fontfamily(self.F["mono"])
            t.set_fontsize(size)

    def adi_cv2(self, wpx, hpx, compact=False):
        N = self.N
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.11, 0.14, 0.86, 0.76])
        rows = [p for p in N["parts"] if p["adi"] is not None and p["cv2"] is not None]
        for cls, col, mk, lab in [("C", C["titanium"], "o", PART_TYPE["C"]), ("E", C["slate"], "s", PART_TYPE["E"]),
                                  ("R", C["aero_teal"], "D", PART_TYPE["R"])]:
            xs = [p["adi"] for p in rows if p["cls"] == cls]
            ys = [p["cv2"] for p in rows if p["cls"] == cls]
            ax.scatter(xs, ys, s=16 if not compact else 22, c=col, marker=mk, alpha=0.85, linewidths=0,
                       label=f"{lab} ({len(xs)})")
        ax.set_xscale("log")
        ax.axvline(1.32, color=C["copper"], lw=0.8, ls=(0, (4, 3)))
        ax.axhline(0.49, color=C["copper"], lw=0.8, ls=(0, (4, 3)))
        ax.set_xlabel("ADI · mean weeks between demands (log)", fontsize=8.5)
        ax.set_ylabel("CV² of demand size", fontsize=8.5)
        xmax = max(p["adi"] for p in rows) * 1.3
        ax.set_xlim(0.9, xmax)
        ymax = max(p["cv2"] for p in rows) * 1.1
        ax.set_ylim(0, ymax)
        lab = dict(fontsize=8, fontfamily=self.F["mono"], color=C["faint"])
        ax.text(0.97, ymax * 0.03, "SMOOTH", ha="left", **lab)
        ax.text(xmax * 0.95, ymax * 0.03, "INTERMITTENT", ha="right", **lab)
        ax.text(0.97, ymax * 0.95, "ERRATIC", ha="left", va="top", **lab)
        ax.text(xmax * 0.95, ymax * 0.95, "LUMPY", ha="right", va="top", **lab)
        from matplotlib.ticker import FixedLocator, NullFormatter, FuncFormatter
        ax.xaxis.set_major_locator(FixedLocator([v for v in [1, 1.32, 2, 4, 8, 16, 32, 64] if v < xmax]))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        self.mono_ticks(ax)
        lg = ax.legend(loc="upper center", frameon=False, fontsize=8, ncol=3, handletextpad=0.3, columnspacing=1.2,
                       bbox_to_anchor=(0.5, 1.13))
        for t in lg.get_texts():
            t.set_color(C["titanium"])
        return self._save(fig, "adi" + ("-c" if compact else ""))

    def palm_pmf(self, wpx, hpx, big=False):
        N = self.N
        d = N["ltd"]["dist"]
        S = N["s_bom"]
        fs = 7.5 if not big else 9
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.06, 0.26 if not big else 0.2, 0.92, 0.66 if not big else 0.72])
        for r in d:
            ok = r["q"] < S
            col = C["aero_teal"] if ok else C["copper"]
            ax.bar(r["q"], r["p"], width=0.62, color=col, alpha=0.9 if ok else 0.75)
            ax.text(r["q"], r["p"] + 0.012, f"{r['p'] * 100:.1f}%", ha="center", fontsize=fs,
                    fontfamily=self.F["mono"], color=C["titanium"])
        ax.axvline(S - 0.5, color=C["ice"], lw=0.9, ls=(0, (4, 3)))
        top = max(r["p"] for r in d)
        ax.text(S - 0.42, top * 1.1, f"S = {S} units at BOM (Network Plan)", fontsize=fs + 0.5, color=C["ice"], va="top",
                fontfamily=self.F["mono"])
        ax.set_xticks([r["q"] for r in d])
        ax.set_ylim(0, top * 1.18)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("Units of this part on the way back to BOM (resupply from AUH) at a random moment", fontsize=fs + 0.5)
        self.mono_ticks(ax, fs + 0.5)
        return self._save(fig, "pmf" + ("-b" if big else ""))

    def stations(self, wpx, hpx, big=False):
        N = self.N
        sts = sorted(N["stations"], key=lambda s: (s["role"] != "hub", -s["aog_hours_by_policy"]["P0"]["mean"]))
        fs = 8 if not big else 10.5
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.13, 0.13 if not big else 0.11, 0.84, 0.78 if not big else 0.80])
        pol_style = [("P0", C["copper"], "s", -0.22), ("P1", C["slate"], "o", 0.0), ("P2", C["aero_teal"], "D", 0.22)]
        floor = 0.5
        for i, s in enumerate(sts):
            for pid, col, mk, off in pol_style:
                v = s["aog_hours_by_policy"][pid]
                lo, hi = max(v["ci"][0], floor), max(v["ci"][1], floor)
                m = max(v["mean"], floor)
                ax.plot([lo, hi], [i + off, i + off], color=col, lw=1.3, alpha=0.75)
                ax.plot([m], [i + off], marker=mk, ms=5.5 if not big else 7, color=col,
                        mfc=col if pid != "P1" else C["midnight"], mew=1.2)
                if v["mean"] < 1:
                    ax.text(hi * 1.25, i + off, f"{v['mean']:.1f} h", va="center", fontsize=fs - 1,
                            fontfamily=self.F["mono"], color=col)
        ax.set_xscale("log")
        ax.set_yticks(range(len(sts)))
        ax.set_yticklabels([f"{s['station']}{' · hub' if s['role'] == 'hub' else ''}" for s in sts], fontsize=fs + 0.5,
                           fontfamily=self.F["mono"])
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.axhline(0.5, color=HAIR_BG, lw=0.8)
        from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
        ax.xaxis.set_major_locator(FixedLocator([1, 3, 10, 30, 100, 300, 1000]))
        ax.set_xlim(0.35, 1400)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Hours waiting for a part / year (log) · 20 test runs, mean and likely range", fontsize=fs)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        for t in ax.get_xticklabels():
            t.set_fontfamily(self.F["mono"])
            t.set_fontsize(fs - 0.5)
        from matplotlib.lines import Line2D
        hs = [Line2D([], [], color=c, marker=m, ls="-", ms=5, lw=1, mfc=c if p != "P1" else C["midnight"])
              for p, c, m, _ in pol_style]
        labels = [f"{N['dn'][p]['short_name']} {p} · {N['out_rot'][p]} outstation" for p, *_ in pol_style]
        lg = ax.legend(hs, labels, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, frameon=False,
                       fontsize=fs - 1 if not big else fs - 1.5, handletextpad=0.4, columnspacing=0.9)
        for t in lg.get_texts():
            t.set_color(C["titanium"])
        return self._save(fig, "stations" + ("-b" if big else ""))

    def frontier(self, wpx, hpx, compact=False):
        N = self.N
        pts = N["points"]
        fs = 8 if not compact else 10
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.10, 0.13, 0.87, 0.83] if not compact else [0.13, 0.17, 0.83, 0.80])
        ymin = 25
        nd = sorted([p for p in pts if not p["dominated"] and p["kind"] in ("greedy", "lever", "policy")],
                    key=lambda p: p["capital_aed"])
        xs = [p["capital_aed"] / 1e6 for p in nd]
        ax.fill_between(xs, [max(p["aog_ci"][0], ymin) for p in nd], [p["aog_ci"][1] for p in nd],
                        color=C["aero_teal"], alpha=0.08, lw=0)
        ax.plot(xs, [p["aog_hours"] for p in nd], color=C["aero_teal"], lw=1.1, alpha=0.6)
        core, fo, base = N["core_id"], N["fo_id"], N["base_id"]
        for p in pts:
            if p["id"] in (core, fo):
                continue
            x, y = p["capital_aed"] / 1e6, p["aog_hours"]
            if p["kind"] == "policy":
                col, mk, ms, mfc = C["copper"], "s", 6.5, C["copper"]
            elif p["kind"] in ("lever", "combo"):
                col, mk, ms, mfc = C["titanium"], "D", 4.5, "none"
            else:
                col = C["titanium"] if not p["dominated"] else C["slate"]
                mk, ms, mfc = "o", 3.8, (col if not p["dominated"] else "none")
            ax.plot([x], [y], marker=mk, ms=ms, color=col, mfc=mfc, mew=1, alpha=0.9)
        # P0 -> P2 arrow: the core finding at (almost) the same capital
        p0, p2, i1 = N["pt"][base], N["pt"][core], N["pt"][fo]
        ax.annotate("", xy=(p2["capital_aed"] / 1e6, p2["aog_hours"] * 1.18),
                    xytext=(p0["capital_aed"] / 1e6, p0["aog_hours"] * 0.86),
                    arrowprops=dict(arrowstyle="-|>", color=C["aero_teal"], lw=1.3, mutation_scale=9))
        for p, col, ms in [(p2, C["aero_teal"], 8), (i1, C["ice"], 7)]:
            x, y = p["capital_aed"] / 1e6, p["aog_hours"]
            ax.plot([x, x], p["aog_ci"], color=col, lw=1.4)
            ax.plot([x], [y], marker="D" if p is p2 else "o", ms=ms, color=col, mfc=col if p is p2 else "none", mew=1.6)
        mono = dict(fontfamily=self.F["mono"], fontsize=fs)
        ax.text(p0["capital_aed"] / 1e6 + 0.9, p0["aog_hours"], f"Simple Rulebook {base}", color=C["copper"],
                va="center", ha="left", **mono)
        p1 = N["pt"]["P1"]
        ax.text(p1["capital_aed"] / 1e6, p1["aog_hours"] * 1.35, "Each Airport for Itself P1", color=C["copper"], va="center",
                ha="center", **mono)
        ax.text(p2["capital_aed"] / 1e6 - 0.9, p2["aog_hours"] * 0.62, f"Network Plan {core}", color=C["aero_teal"],
                va="center", ha="right", fontweight="bold", **mono)
        ax.annotate(f"Network Plan + Extra Spares {fo}\n+{fmt_mm(i1['capital_aed'] - p2['capital_aed'])} vs Network Plan",
                    xy=(i1["capital_aed"] / 1e6, i1["aog_hours"]),
                    xytext=(i1["capital_aed"] / 1e6 + (5 if not compact else 6), i1["aog_hours"] * 2.6),
                    color=C["ice"], fontsize=fs, fontfamily=self.F["ui"], va="center",
                    arrowprops=dict(arrowstyle="-", color=C["ice"], lw=0.7))
        ax.set_yscale("log")
        from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
        ax.yaxis.set_major_locator(FixedLocator([30, 100, 300, 1000, 3000]))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_ylim(ymin, max(p["aog_ci"][1] for p in pts) * 1.15)
        ax.set_xlabel("Simulated spare capital (AED M)", fontsize=fs + 0.5)
        ax.set_ylabel("Hours waiting for a part / year (log)", fontsize=fs + 0.5)
        ax.yaxis.grid(True, color=HAIR_BG, lw=0.6, ls=(0, (2, 3)))
        self.mono_ticks(ax, fs)
        return self._save(fig, "frontier" + ("-c" if compact else ""))

    def tornado(self, wpx, hpx):
        N = self.N
        rows = sorted(N["tornado"], key=lambda r: max(abs(r["low"]), abs(r["high"])), reverse=True)
        base = rows[0]["base"]
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.20, 0.24, 0.76, 0.72])
        mx = max(max(abs(r["low"]), abs(r["high"])) for r in rows)
        for i, r in enumerate(rows):
            tiny = []
            for v, setting in [(r["low"], r["low_setting"]), (r["high"], r["high_setting"])]:
                col = C["aero_teal"] if v >= 0 else C["copper"]
                ax.barh(i, v / 1e6, height=0.55, color=col, alpha=0.85)
                if abs(v) < 0.04 * mx:
                    tiny.append(setting)
                    continue
                ax.text(v / 1e6 + (0.15 if v >= 0 else -0.15), i, setting, va="center",
                        ha="left" if v >= 0 else "right", fontsize=7.5, fontfamily=self.F["mono"], color=C["titanium"])
            if tiny:
                big_ = [v for v in (r["low"], r["high"]) if abs(v) >= 0.04 * mx]
                side = (big_[0] < 0) if big_ else False
                ax.text(0.15 if side else -0.15, i, f"{' / '.join(tiny)} ~0", va="center",
                        ha="left" if side else "right", fontsize=7.5, fontfamily=self.F["mono"], color=C["faint"])
        ax.axvline(0, color=C["ice"], lw=0.8)
        ax.set_yticks(range(len(rows)))
        lab = {"aog_penalty": "Hourly AOG penalty", "repair_tat": "Repair time", "lead_time": "Purchase lead time",
               "carrying_cost": "Carrying cost"}
        ax.set_yticklabels([lab.get(r["factor"], r["factor"]) for r in rows], fontsize=8.5)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        m = max(max(abs(r["low"]), abs(r["high"])) for r in rows) / 1e6
        ax.set_xlim(-m * 1.4, m * 1.4)
        ax.set_xlabel(f"Change in {N['fo_id']} − {N['core_id']} net benefit around base {fmt_mm(base)}/yr "
                      "(AED M) · one at a time", fontsize=8)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        for t in ax.get_xticklabels():
            t.set_fontfamily(self.F["mono"])
            t.set_fontsize(7.5)
        return self._save(fig, "tornado")

    def actions(self, wpx, hpx):
        N = self.N
        bts = N["act_counts"]["by_type_severity"]
        types_ = sorted(N["act_counts"]["by_type"], key=lambda t: -N["act_counts"]["by_type"][t])
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.45, 0.04, 0.51, 0.94])
        sev = [("urgent", C["red"]), ("review", C["amber"]), ("info", C["slate"])]
        for i, t in enumerate(types_):
            left = 0
            for s, col in sev:
                v = bts.get(f"{t}|{s}", 0)
                if v:
                    ax.barh(i, v, left=left, height=0.6, color=col, alpha=0.9)
                left += v
            ax.text(left + 0.5, i, str(left), va="center", fontsize=8, fontfamily=self.F["mono"], color=C["ice"])
        ax.set_yticks(range(len(types_)))
        ax.set_yticklabels([t.replace("_", " ").capitalize() for t in types_], fontsize=8)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])
        ax.set_xlim(0, max(N["act_counts"]["by_type"].values()) * 1.15)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        return self._save(fig, "actions")

    def kpi_bars(self, wpx, hpx):
        """Holdout material AOG h/yr by policy, with capital (square format)."""
        N = self.N
        ids = [N["base_id"], "P1", N["core_id"], N["fo_id"]]
        two = {"P0": "Simple Rulebook", "P1": "Each Airport\nfor Itself", "P2": "Network Plan", "I125": "Network Plan\n+ Extra Spares"}
        names = {p: f"{two[p]} · {p}" for p in ids}
        fs = 11 if wpx <= 620 else 9
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.27, 0.04, 0.71, 0.92])
        top = max(N["pols"][p]["kpi"]["aog_hours"]["ci_hi"] for p in ids)
        for i, pid in enumerate(ids):
            k = N["pols"][pid]["kpi"]["aog_hours"]
            capv = N["pols"][pid]["kpi"]["spare_capital_aed"]["mean"]
            col = {N["base_id"]: C["copper"], N["core_id"]: C["aero_teal"]}.get(pid, C["slate"])
            ax.barh(i, k["mean"], height=0.58, color=col, alpha=0.95 if pid != N["fo_id"] else 0.6)
            ax.plot([k["ci_lo"], k["ci_hi"]], [i, i], color=C["ice"], lw=1, alpha=0.6)
            ax.text(k["ci_hi"] + top * 0.025, i, f"{fmt_int(k['mean'])} h · {fmt_mm(capv)}", va="center",
                    fontsize=fs, fontfamily=self.F["mono"], color=C["ice"])
        ax.set_yticks(range(len(ids)))
        ax.set_yticklabels([names[p] for p in ids], fontsize=fs + 0.5, fontfamily=self.F["ui"], linespacing=1.0)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])
        ax.set_xlim(0, top * 1.75)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        return self._save(fig, "kpibars")


# --------------------------------------------------------------------------------------------------------------------
# Deck content
# --------------------------------------------------------------------------------------------------------------------
def bullet(text_runs, sty="body", col=C["aero_teal"], after=5, ls=1.08):
    runs = [R("›  ", sty, c=col, b=True)]
    for t in text_runs:
        runs.append(t if isinstance(t, dict) else R(t, sty))
    return P(*runs, after=after, ls=ls)


def stat(s, x, y, w, value, label, sub=None, col=C["aero_teal"], size=30):
    s.text(x, y, w, size * 1.8, P(R(value, "big", c=col, s=size)))
    s.text(x, y + size * 1.6, w, 18, P(R(label, "bodym", s=9.5)))
    if sub:
        s.text(x, y + size * 1.6 + 18, w, 30, P(R(sub, "small", s=8), ls=1.05))


def wname(v):
    return {"low_stress": "Low stress", "central": "Central", "high_stress": "High stress"}[v]


def dn(N, code):
    """A3 display name (from docs/data display_names)."""
    return N["dn"][code]["display_name"]


def sn(N, code):
    return N["dn"][code]["short_name"]


def named(N, code, sty="body", s=9.3, c=None, b=False, short=False):
    """Display name followed by the code as a small mono tag (A3)."""
    kw = {"s": s, "b": b}
    if c:
        kw["c"] = c
    return [R(sn(N, code) if short else dn(N, code), sty, **kw), R(f" {code}", "monos", s=max(6.5, s - 2), c=C["faint"])]


def common(N):
    """Phrases used on several slides, all built from data."""
    core, fo = N["core"], N["fo"]
    red = core["aog_reduction"]
    d = dict(
        red=fmt_int(red["mean"]), red_ci=ci_h(red["ci"]),
        out0=N["out_rot"]["P0"], out1=N["out_rot"]["P1"], out2=N["out_rot"]["P2"],
        fo_cap=fmt_mm(fo["extra_capital_aed"]["mean"]),
        fo_red=fmt_int(fo["aog_reduction"]["mean"]), fo_red_ci=ci_h(fo["aog_reduction"]["ci"]),
        fill=f"{abs(core['immediate_fill_pts']['mean']):.2f}",
        fill_ci=f"[{core['immediate_fill_pts']['ci'][0]:.2f}, {core['immediate_fill_pts']['ci'][1]:.2f}]".replace("-", "−"),
    )
    ct = N["cap_t"]
    d["cap_rows"] = [(r["label"], r["text"]) for r in ct["rows"]]
    d["cap_note"] = ct["note"]
    d["buy_units"], d["shed_units"] = ct["bought_units"], ct["removed_units"]
    return d


def capital_table(s, N, x, y, w, size=9.4, label=True):
    """A4: gross lines + net + 'not cash back' note. Never the net row alone. Returns the y below it."""
    ct = N["cap_t"]
    if label:
        s.text(x, y, w, 16, P(R(f"CAPITAL CHANGE · {sn(N, ct['from']).upper()} → {sn(N, ct['to']).upper()}", "label",
                                c=C["faint"])))
        y += 24
    for r_ in ct["rows"]:
        net = r_["id"] == "net_inventory"
        bh = 2 * size * 1.333 * 1.3 + 4
        s.text(x, y, w * 0.44, bh, P(R(r_["label"], "body" if net else "bodym", s=size, b=net), ls=1.05))
        s.text(x + w * 0.44, y, w * 0.56, bh, P(R(r_["text"], "mono", s=size * 0.92, c=C["copper"] if net else C["ice"],
                                                b=True), al="r", ls=1.05))
        lh = size * 1.333 * 1.26
        y += max(30, lh + 14) if len(r_["label"]) * size * 1.333 * 0.52 < w * 0.44 else 2 * lh + 14
        s.line(x, y - 6, x + w, y - 6, HAIR, 0.5)
    lh = (size - 0.4) * 1.333 * 1.3
    s.text(x, y, w, 2 * lh + 4, P(R(ct["note"], "body", s=size - 0.4, c=C["amber"]), ls=1.08))
    return y + 2 * lh + 6


def build_deck(N, A, CH, bg, total=10):
    S = []
    k, core, fo, hon = N["kpi"], N["core"], N["fo"], N["hon"]
    cid, bid, fid = N["core_id"], N["base_id"], N["fo_id"]
    cm = common(N)
    pols = N["pols"]
    L = N["landing"]

    # 1 — Title (no results here: they start on slide 3 with the scope line and the reading note) ------------------
    s = Slide(bg=bg)
    s.image(690, 96, 270, 320, A["nb"])
    s.image(950, 80, 300, 340, A["wb"])
    s.text(690, 424, 270, 16, P(R(f"NARROWBODY ARCHETYPE · {N['nb']} TAILS", "label", s=7.5, c=C["faint"]), al="c"))
    s.text(950, 424, 300, 16, P(R(f"WIDEBODY ARCHETYPE · {N['wb']} TAILS", "label", s=7.5, c=C["faint"]), al="c"))
    s.text(690, 442, 560, 16, P(R("Original plan-view schematics · not manufacturer drawings", "small", s=7.5), al="c"))
    s.card(708, 476, 524, 190, line=blend(C["titanium"], C["card"], 0.3))
    s.text(728, 492, 490, 16, P(R("FOUR PLANS, EACH FACING IDENTICAL EVENTS", "label", c=C["titanium"])))
    s.text(728, 516, 490, 120, [P(R("›  ", "body", c=C["aero_teal"], b=True, s=10.5), *named(N, c_, s=10.5), after=5)
                                for c_ in (bid, "P1", cid, fid)])
    s.text(728, 634, 490, 28, P(R("Results start on slide 3, with their scope and how to read them.", "small", s=8.3),
                                ls=1.05))
    s.text(56, 56, 640, 16, P(R("AVIATION SPARE-PARTS PLANNING · A SIMULATION CASE STUDY", "eyebrow")))
    s.text(56, 76, 640, 166, [P(R("GROUNDED", "title", s=52, sp=-1), ls=0.9),
                              P(R("NO MORE", "title", s=52, sp=-1, c=C["aero_teal"]), ls=0.9)])
    s.text(56, 244, 620, 52, P(R(L["title"], "h3", s=15.5, c=C["ice"]), ls=1.1))
    s.text(56, 298, 610, 66, P(R(L["sub"], "bodym", s=11), ls=1.15))
    xx = 56
    for st_ in L["stats"]:
        s.text(xx, 372, 150, 40, P(R(fmt_int(st_["value"]), "big", s=24, c=C["aero_teal"])))
        s.text(xx, 410, 150, 18, P(R(st_["label"], "bodym", s=9.5)))
        xx += 152
    s.text(56, 436, 610, 16, P(R(L["text"], "monos", s=8.3)))
    s.text(56, 458, 610, 16, P(R(L["footer"], "small", s=8.5, c=C["titanium"])))
    s.line(56, 490, 660, 490, HAIR_BG, 0.75)
    s.text(56, 506, 620, 100, [P(R("Akash Gajjar", "h3", s=13), after=2),
                               P(R("MSc Supply Chain Management, University of Liverpool (2025)", "bodym", s=10),
                                 after=6),
                               P(R(LIVE_URL.replace("https://", ""), "monos", s=8.5, c=C["aero_teal"])),
                               P(R(REPO_URL.replace("https://", ""), "monos", s=8.5))])
    s.footer(1, "numbers read from docs/data at build time", total)
    S.append(s)

    # 2 — The problem + hero-part escalation (A7) -------------------------------------------------------------------
    inc = N["inc"]
    cf = inc["counterfactual"]
    part = N["part"][inc["pn"]]
    sv = N["sv"]
    esc = N["esc"]
    s = Slide(bg=bg)
    s.header(2, "The problem", f"None on the shelf at {inc['station']}: {inc['aog_hours']} hours waiting for one part",
             f"Incident {inc['id']}, replayed from the simulated history: a {inc['deadline']} (no deferral) requirement "
             f"for {inc['pn']}, {inc['desc'][0].lower() + inc['desc'][1:]}, on {inc['tail']} (fictional {inc['archetype']}).")
    s.card(48, 150, 640, 330)
    s.text(70, 166, 400, 16, P(R("INCIDENT TIMELINE · SIMULATED UTC", "label", c=C["faint"])))
    s.chip_r(670, 164, "SIMULATED")
    y = 192
    for st_ in inc["timeline"]:
        hot = st_["step"] in ("aog_start", "released")
        s.text(70, y, 70, 20, P(R(f"T+{st_['t_h']:g} h", "mono", s=8.8, c=C["aero_teal"] if not hot else C["amber"])))
        s.text(132, y, 44, 20, P(R(st_["station"], "mono", s=8.8, c=C["titanium"])))
        s.text(176, y, 496, 20, P(R(st_["event"], "body", s=9, c=C["ice"] if hot else C["titanium"])))
        y += 22
    s.line(70, y + 6, 666, y + 6, HAIR, 0.75)
    s.text(70, y + 14, 596, 40, P(R(f"Material shortage exposure AED {cf['actual_exposure_aed']:,}", "h3", s=11.5,
                                    c=C["copper"]),
                                  R(f"  = {inc['aog_hours']} h × AED {inc['rate_aed_per_h']:,}/h + AED "
                                    f"{inc['event_cost_aed']:,} per event (both ASSUMED) + AED "
                                    f"{cf['actual_direct_cost_aed']:,} logistics", "bodym", s=9), ls=1.1))
    s.card(48, 492, 640, 178, line=blend(C["amber"], C["card"], 0.45))
    s.text(70, 506, 560, 16, P(R("WHY IT KEEPS HAPPENING · AND THE FIRST THING TO DO", "label", c=C["amber"])))
    s.text(70, 526, 600, 40, P(R(f"The {dn(N, bid)} holds {sv['units']['P0']} of these actuators at {inc['station']}. "
                                 f"Across the network {inc['pn']} caused {fmt_int(part['aog_h_52w'])} h waiting for the part "
                                 f"in the last 52 history weeks ({part['aog_events_52w']} events).", "bodym", s=9.3),
                               ls=1.1))
    hero = N["esc_pn"] == inc["pn"]
    s.rect(70, 572, 600, 90, fill=blend(C["amber"], C["card"], 0.10), line=blend(C["amber"], C["card"], 0.4), r=6)
    s.text(84, 580, 576, 80, [
        P(R(("This part: " if hero else f"Hero part {N['esc_pn']}: ") + esc["text"], "body", s=9.6, c=C["ice"]),
          ls=1.1, after=4),
        P(R(f"History-estimated removal rate ≈ {esc['estimated_ratio']:.1f}× the quoted rate; the rule escalates at "
            f"≥ {esc['threshold']:g}×.", "small", s=8.2), ls=1.05)])
    s.image(704, 150, 528, 486, A["nb-32"])
    s.text(704, 646, 528, 16, P(R("ATA 32 ZONE HIGHLIGHTED · NARROWBODY ARCHETYPE · NOT A MANUFACTURER DRAWING", "label",
                                  s=7, c=C["faint"]), al="c"))
    s.footer(2, "Source: simulated history weeks 0–103, docs/data",
             total)
    S.append(s)

    # 3 — Results (scope line + A2 reading note + A6) ----------------------------------------------------------------
    pr = N["paired"]["P2-P0"]
    p10 = N["paired"]["P1-P0"]
    bc = N["by_class"]
    sw = N["sw"]
    s = Slide(bg=bg)
    s.header(3, "Results", f"{dn(N, cid)}: {cm['red']} fewer hours a year waiting for parts",
             "Hours aircraft waited for a part, per year, on 20 fresh test runs the model never saw, each plan facing "
             f"identical events. The {dn(N, bid)} is a deliberately simple starting point.")
    s.card(48, 150, 700, 322)
    s.text(70, 166, 540, 16, P(R("HOURS WAITING / YR · LIKELY RANGE · AVERAGE INVENTORY", "label", c=C["faint"])))
    s.chip_r(730, 164, "SIMULATED")
    s.image(60, 188, 676, 252, CH.kpi_bars(676, 252))
    s.scope(70, 448, 660)
    s.card(766, 150, 466, 322)
    s.text(788, 166, 420, 16, P(R(f"{sn(N, cid).upper()} {cid} − {sn(N, bid).upper()} {bid} · PAIRED",
                                  "label", c=C["aero_teal"])))
    blocks = [
        ("Hours waiting / yr", fmt_int(pr["aog_hours"]["mean"]),
         ci_txt([pr["aog_hours"]["ci_lo"], pr["aog_hours"]["ci_hi"]]), C["aero_teal"]),
        # v2.2 (review #8): no money tile on the results slide; the positioning change instead (from network data)
        ("Outstation spares", f"{N['out_rot'][bid]} → {N['out_rot'][cid]}", "at outstations",
         C["ice"]),
        ("Shelf fill, pts", f"−{cm['fill']}", cm["fill_ci"], C["amber"]),
    ]
    xx = 788
    for lab, val, ci, col in blocks:
        s.text(xx, 188, 144, 16, P(R(lab, "bodym", s=8.6)))
        s.text(xx, 204, 144, 30, P(R(val, "mid", s=16, c=col)))
        s.text(xx, 232, 144, 16, P(R(ci, "monos", s=7.8)))
        xx += 144
    s.line(788, 256, 1210, 256, HAIR, 0.5)
    s.text(788, 264, 420, 16, P(R("HOLDS IN ALL THREE STRESS WORLDS (HOURS / YR)", "label", s=7.5, c=C["faint"])))
    yy = 284
    for w in core["worlds"]:
        s.text(788, yy, 130, 18, P(R(wname(w["variant"]), "body", s=9.3)))
        s.text(918, yy, 292, 18, P(R(f"{fmt_int(w['aog_hours']['mean'])} h {ci_txt(w['aog_hours']['ci'])}", "mono", s=8.8,
                                     c=C["aero_teal"])))
        yy += 21
    s.text(788, yy + 6, 422, 110, [
        P(R("The worlds differ only in reliability: ", "body", s=9, b=True), R(sw["text"] + ".", "bodym", s=9),
          after=5, ls=1.08),
        P(R(sw["ranges_note"], "bodym", s=9, c=C["amber"]), ls=1.08)])
    s.card(48, 484, 1184, 186, line=blend(C["titanium"], C["card"], 0.3))
    s.text(70, 494, 1140, 102, [P(R(N["reading"], "body", s=10.2, c=C["ice"]), after=4, ls=1.12),
                                P(R(N["routes_line"], "body", s=9.6, c=C["amber"]), ls=1.1)])
    s.line(70, 602, 1210, 602, HAIR, 0.5)
    s.text(70, 610, 560, 56, [
        bullet([*named(N, "P1", s=9.2, b=True, short=True),
                R(f" (each station sized alone) holds {cm['out1']} outstation repairable spares and still leaves "
                  f"{fmt_int(pols['P1']['kpi']['aog_hours']['mean'])} h/yr, most of it at the hub.", "bodym", s=9.2)],
               after=0, ls=1.08)])
    s.text(650, 610, 560, 56, [
        bullet([R("The price: ", "body", s=9.2, b=True, c=C["amber"]),
                R(f"the shelf fill is {cm['fill']} pts lower, in cheap consumable "
                  f"({fmt_pct(bc[('P0', 'C')]['immediate_fill_rate'], 2)} → {fmt_pct(bc[('P2', 'C')]['immediate_fill_rate'], 2)}) "
                  f"and throw-away parts; repairable-part fill rises {fmt_pct(bc[('P0', 'R')]['immediate_fill_rate'])} → "
                  f"{fmt_pct(bc[('P2', 'R')]['immediate_fill_rate'])}.", "bodym", s=9.2)], col=C["amber"], after=0,
               ls=1.08)])
    s.footer(3, f"Source: simulated holdout, docs/data · {N['seed_txt']}", total)
    S.append(s)

    # 4 — Not a free move of stock: A4 capital table + where the stock goes + Palm ------------------------------------
    fl, ltd = N["float"], N["ltd"]
    s = Slide(bg=bg)
    s.header(4, "Capital and positioning", f"Not a free move of stock: {cm['buy_units']} parts bought, "
             f"{cm['shed_units']} removed",
             f"It pools most repairable parts at {N['hub']} and places {cm['out2']} at the outstations, against "
             f"{cm['out0']} under the {sn(N, bid)}, only where a no-go part is worth it. Station stock is sized on the "
             f"resupply time from {N['hub']}.")
    s.card(48, 150, 640, 520)
    s.text(70, 166, 520, 16, P(R("HOURS WAITING FOR A PART, BY STATION · 20 TEST RUNS", "label", c=C["faint"])))
    s.chip_r(670, 164, "SIMULATED")
    s.image(58, 190, 620, 448, CH.stations(620, 448))
    s.scope(70, 646, 600)
    s.card(706, 150, 526, 246)
    yb = capital_table(s, N, 728, 166, 482, size=9.6)
    s.text(728, yb - 2, 482, 30, P(R("Units × assumed unit cost from the policy tables; the net is the paired change in "
                                     "time-averaged simulated inventory, so it differs from bought minus removed.",
                                     "small", s=7.6), ls=1.05))
    s.card(706, 408, 526, 262)
    s.text(728, 424, 440, 16, P(R(f"WHY A SPARE AT BOM PAYS · PALM'S THEOREM", "label", c=C["faint"])))
    s.chip_r(1214, 422, "DERIVED")
    s.rect(728, 452, 482, 54, fill=C["deep_steel"], line=HAIR, r=8)
    s.text(740, 462, 458, 40, [P(R("A(S) = P(X ≤ S − 1),   X ~ Poisson(λ · T)", "mono", s=11, c=C["ice"], b=True), al="c"),
                               P(R("chance a removal finds a spare on the shelf with S spares", "small", s=8), al="c")])
    s.text(728, 518, 482, 40, [P(R(f"A({N['s_bom']}) = {fmt_pct(N['palm_bom'])}", "mid", c=C["aero_teal"], s=16),
                                 R(f"   vs A({sv['units']['P0']}) = {fmt_pct(sv['availability']['P0'], 0)} under the "
                                   f"{sn(N, bid)}", "mono", s=9, c=C["copper"]))])
    s.text(728, 556, 482, 110, [
        P(R(f"{fl['desc']}: BOM removal rate {sv['rate_per_30d']:.2f} per 30 days, resupply from {N['hub']} "
            f"{(sv.get('resupply_days') or sv['loop_days']):.1f} days → λT = {ltd['mean']:.3f}.", "bodym", s=8.8),
          after=4, ls=1.08),
        P(R("OUTSTATION REPAIRABLE SPARES, P0 → P2", "label", s=7.2, c=C["faint"]), after=2),
        P(*[R(f"{st_['station']} {st_['by_policy']['P0']['rotable_units']}→{st_['by_policy']['P2']['rotable_units']}  ",
              "mono", s=8.4, c=C["ice"]) for st_ in N["stations"] if st_["role"] != "hub"])])
    s.footer(4, "Source: simulated holdout and history, docs/data",
             total)
    S.append(s)

    # 5 — Forecasting --------------------------------------------------------------------------------------
    cc = N["champion_check"]
    n_cells, n_rank1 = len(cc), sum(1 for c in cc if c["champion_rank"] == 1)
    assert (n_rank1, n_cells) == (hon["forecast_champions_best"], hon["forecast_cells"])
    ir = [c for c in cc if c["demand_class"] == "intermittent" and c["part_class"] == "R"][0]
    rvc = N["rel_vs_croston"]
    n_q90 = sum(1 for r in rvc if r["reliability_pinball_q90"] < r["croston_family_pinball_q90"])
    tr = N["truth"]["MTBUR (rotables + expendables)"]
    from collections import Counter
    dcls = Counter(p["demand_class"] for p in N["parts"])
    s = Slide(bg=bg)
    s.header(5, "Forecasting", f"Methods chosen in advance were best in only {n_rank1} of {n_cells} groups",
             f"{dcls.get('intermittent', 0)} of {N['n_parts']} part numbers are needed only now and then (ADI > 1.32 "
             f"weeks, CV² < 0.49, training weeks 0–{N['split_week'] - 1}). Methods were fixed on earlier runs, then "
             "checked once on the fresh test runs.")
    s.card(48, 150, 560, 520)
    s.text(70, 166, 420, 16, P(R("ADI × CV² · ONE DOT PER PART NUMBER", "label", c=C["faint"])))
    s.chip_r(590, 164, "DERIVED")
    s.image(60, 190, 540, 470, CH.adi_cv2(540, 470))
    s.card(626, 150, 606, 318)
    s.text(648, 166, 520, 16, P(R("CHOSEN METHOD'S RANK ON THE FRESH TEST RUNS", "label", c=C["faint"])))
    s.chip_r(1214, 164, "DERIVED")
    hd = [("Group", 648), ("Chosen in advance", 860), ("Rank", 1010), ("Best in hindsight", 1100)]
    for h_, x_ in hd:
        s.text(x_, 190, 160, 14, P(R(h_.upper(), "label", s=7, c=C["faint"])))
    yy = 208
    lab = N["method_labels"]
    for c in sorted(cc, key=lambda c: (c["part_class"], c["demand_class"])):
        hit = c["champion_rank"] == 1
        col = C["aero_teal"] if hit else (C["amber"] if c is ir else C["titanium"])
        s.text(648, yy, 210, 18, P(R(f"{PART_TYPE.get(c['part_class'], c['part_class'])} · {c['demand_class'].replace('_', ' ')} ({c['n_parts']})", "body",
                                     s=8.8, c=C["ice"])))
        s.text(860, yy, 150, 18, P(R(lab.get(c["champion"], c["champion"]).split(" (")[0], "bodym", s=8.8)))
        s.text(1010, yy, 80, 18, P(R(f"{c['champion_rank']} / {c['n_methods']}", "mono", s=8.8, c=col, b=hit)))
        s.text(1100, yy, 120, 18, P(R(lab.get(c["best_in_hindsight"], c["best_in_hindsight"]).split(" (")[0], "bodym",
                                      s=8.8)))
        yy += 25
    s.card(626, 480, 606, 190)
    s.text(648, 496, 560, 16, P(R("HOW OFTEN A PART COMES OFF · ERROR VS THE SIMULATION'S HIDDEN TRUTH", "label",
                                  c=C["amber"])))
    bars = [("Estimated from history", tr["estimated"], C["aero_teal"]), ("Supplier quote", tr["vendor_quoted"], C["copper"])]
    yy = 522
    for lab_, v, col in bars:
        s.text(648, yy, 160, 18, P(R(lab_, "bodym", s=9.3)))
        s.rect(810, yy + 3, 300 * v / tr["vendor_quoted"], 12, fill=col, r=2)
        s.text(810 + 300 * v / tr["vendor_quoted"] + 8, yy, 90, 18, P(R(f"≈ {v * 100:.0f}% off", "mono", s=9.3)))
        yy += 24
    s.text(648, yy + 4, 566, 84, [
        P(R(f"Median absolute log error over {tr['n_parts']} parts; the history estimate is closer for "
            f"{fmt_pct(tr['share_estimate_closer'], 0)} of them.", "small", s=8.5), after=5, ls=1.05),
        P(R(f"Rarely-needed repairable parts: the chosen method '{lab.get(ir['champion'], ir['champion'])}' ranked "
            f"{ir['champion_rank']}/{ir['n_methods']}, kept as chosen. Repairable spares are sized on the reliability-"
            f"exposure rate (lower q90 pinball in {n_q90} of {len(rvc)} classes) instead.", "bodym", s=9.1), ls=1.08)])
    s.footer(5, "Source: rolling-origin forecasts and the simulated holdout, docs/data",
             total)
    S.append(s)

    # 6 — Frontier option: I125 + A8 insight and levers -------------------------------------------------------------
    i1 = N["pt"][fid]
    reco = N["reco"]
    rt = fo["repair_tat_x0_75"]
    shifts = {r["setting"]: r["recommended"] for r in fo["rule_shifts"]}
    # v2.2 (review #20): post-plan numbers from the unrounded frozen file, as render_docs reads them
    _post = json.loads((ROOT / "outputs" / "holdout" / "postplan_i125_stress.json").read_text())
    pp = {w: {"aog_hours": {"mean": r["d_aog_hours_vs_base_mean"],
                            "ci": [r["d_aog_hours_vs_base_lo"], r["d_aog_hours_vs_base_hi"]]}}
          for w, rows_ in _post["worlds"].items() for r in rows_ if r["id"] == "I125"}
    ins = N["ins"]
    s = Slide(bg=bg)
    s.header(6, "Readiness Frontier · how much readiness each extra dirham buys",
             f"Invest an additional {cm['fo_cap']}: {cm['fo_red']} fewer hours a year",
             f"{len(N['points'])} frozen candidate plans, re-run on the 20 test runs. A rule written down before the test "
             f"walks up the frontier while AED 1M still removes ≥ {reco['h_star_per_aed_1m']:.1f} hours a year, and stops "
             f"at {fid}. It is an option for more capital, on top of the {sn(N, cid)}.")
    s.card(48, 150, 700, 520)
    s.text(70, 166, 560, 16, P(R("SPARE CAPITAL VS HOURS WAITING · 20 TEST RUNS, MEAN AND LIKELY RANGE", "label",
                                 c=C["faint"])))
    s.chip_r(730, 164, "SIMULATED")
    s.image(58, 186, 680, 450, CH.frontier(680, 450))
    s.scope(70, 644, 660)
    s.card(766, 150, 466, 214)
    s.text(788, 166, 420, 16, P(R(f"+ EXTRA SPARES {fid} − {sn(N, cid).upper()} {cid} · PAIRED", "label",
                                  c=C["ice"])))
    s.text(788, 186, 200, 56, [P(R(f"−{cm['fo_red']} h", "big", s=26, c=C["ice"])),
                               P(R(f"waiting / yr {cm['fo_red_ci']}", "monos", s=8))])
    s.text(1000, 186, 210, 56, [P(R(f"+{cm['fo_cap']}", "big", s=26, c=C["copper"])),
                                P(R("extra spare capital", "monos", s=8))])
    s.text(788, 258, 422, 104, [
        bullet([R("Total annual cost ", "body", s=9.3, b=True),
                R(f"{aed_ci(fo['total_cost_aed']['mean'], *fo['total_cost_aed']['ci'])} a year vs the {sn(N, cid)}.",
                  "bodym", s=9.3)], after=4),
        bullet([R(f"With {sn(N, fid).replace(sn(N, cid), '').strip(' +')}: ", "body", s=9.3, b=True),
                R(f"{fmt_int(i1['aog_hours'])} h/yr {ci_txt(i1['aog_ci'])} at {fmt_mm(i1['capital_aed'])} "
                  f"(earlier runs: {fmt_int(N['spt'][fid]['aog_hours'])} h).", "bodym", s=9.3)], after=4),
        bullet([R("The pick moves: ", "body", s=9.3, b=True),
                R(f"{shifts.get('x0.5', '?')} at ×0.5 and {shifts.get('x2.0', '?')} at ×2 the hourly rate.", "bodym",
                  s=9.3)], after=0),
    ])
    s.card(766, 376, 466, 294, line=blend(C["aero_teal"], C["card"], 0.5))
    s.text(788, 392, 420, 16, P(R("THE MOST USEFUL INSIGHT", "label", c=C["aero_teal"])))
    s.text(788, 414, 422, 64, P(R(ins["text"], "h3", s=12.5, c=C["ice"]), ls=1.12))
    xx = 788
    for lv in ins["levers"]:
        w_ = 18 + len(lv) * 5.6
        s.rect(xx, 488, w_, 22, fill=blend(C["aero_teal"], C["card"], 0.14), line=blend(C["aero_teal"], C["card"], 0.6),
               lw=0.75, r=11)
        s.text(xx, 492, w_, 16, P(R(lv, "body", s=8.2, c=C["aero_teal"]), al="c"))
        xx += w_ + 8
    s.text(788, 520, 422, 146, [
        P(R(f"Repair 25% faster: the extra-spares lead over the {sn(N, cid)} is "
            f"{aed_ci(rt['net_benefit_aed']['mean'], *rt['net_benefit_aed']['ci'], signed=True)} a year, "
            f"{'not significant' if not rt['net_benefit_significant'] else 'significant'} (earlier runs, one factor at a "
            "time).", "bodym", s=8.8), after=5, ls=1.08),
        P(R("Post-plan stress check, added after the main test (D015): ", "small", s=8, c=C["titanium"]),
          *[R(f"{wname(v).lower()} {fmt_int(pp[v]['aog_hours']['mean'])} h {ci_txt(pp[v]['aog_hours']['ci'])}"
              + ("; " if v == "low_stress" else "."), "small", s=8, c=C["titanium"])
            for v in ("low_stress", "high_stress") if v in pp], after=5, ls=1.05),
        P(R(N["sw"]["ranges_note"], "small", s=8, c=C["amber"]), ls=1.05)])
    s.footer(6, f"Source: simulated holdout, docs/data · {N['seed_txt']} unless labelled", total)
    S.append(s)

    # 7 — What it depends on (A5 calibration note) ------------------------------------------------------------------
    V = N["variants"]
    desk = N["desk"]
    ro = hon["routes_off"]
    ach = N["cal_ach"]
    lev = N["pt"].get("LEV_TAT10_TOP6")
    s = Slide(bg=bg)
    s.header(7, "What the result depends on", "The starting point chosen, the emergency routes, and the cost assumed",
             "One-at-a-time sensitivity of the extra-spares option, the three stress worlds, the calibration choice, and "
             "the structural stress the whole result rests on: the emergency recovery routes.")
    s.card(48, 150, 740, 256)
    s.text(70, 166, 640, 16, P(R(f"{fid} − {cid} NET BENEFIT · ONE FACTOR AT A TIME · EARLIER RUNS", "label",
                                 c=C["faint"])))
    s.chip_r(770, 164, "SIMULATED")
    s.image(58, 186, 720, 214, CH.tornado(720, 214))
    s.card(806, 150, 426, 256)
    s.text(828, 166, 380, 16, P(R("BUY 1 SPARE VS CUT REPAIR TIME 10 DAYS", "label", c=C["faint"])))
    s.chip_r(1214, 164, "DERIVED")
    s.text(828, 188, 170, 66, [P(R(str(N["buy_wins"]), "big", s=28)), P(R("parts where buying is cheaper", "small", s=8.3))])
    s.text(1010, 188, 200, 66, [P(R(str(N["tat_wins"]), "big", s=28, c=C["copper"])),
                                P(R("parts where faster repair is cheaper", "small", s=8.3))])
    s.text(828, 266, 384, 136, [
        P(R(f"Median annual cost per hour avoided: buy {fmt_aed(N['buy_med'])}, faster repair {fmt_aed(N['tat_med'])}.",
            "bodym", s=9.3), after=5, ls=1.1),
        P(R(f"Simulated: faster repair on the top 6 parts gives {fmt_int(lev['aog_hours'])} h/yr at "
            f"{fmt_mm(lev['capital_aed'])}, close to the {sn(N, cid)}'s {fmt_int(N['pt'][cid]['aog_hours'])} h."
            if lev else "", "bodym", s=9.3), after=5, ls=1.1),
        P(R(N["lever_ex"], "small", s=8.3), ls=1.08),
    ])
    s.card(48, 418, 740, 252, line=blend(C["amber"], C["card"], 0.45))
    s.text(70, 434, 640, 16, P(R("THE STARTING POINT WAS CHOSEN, NOT MEASURED", "label", c=C["amber"])))
    s.chip_r(770, 432, "ASSUMED")
    s.text(70, 456, 696, 64, P(R(N["cal_note"]["text"], "body", s=9.8, c=C["ice"]), ls=1.12))
    hdr = ["World", f"{bid} history fill · hours", f"{cid} − {bid} h (test runs)", f"{fid} − {cid} net / yr (earlier)"]
    cx = [70, 178, 368, 572]
    for c_, h_ in zip(cx, hdr):
        s.text(c_, 534, 210, 14, P(R(h_.upper(), "label", s=7, c=C["faint"])))
    yy = 552
    wmap = {w["variant"]: w for w in core["worlds"]}
    for v in ("low_stress", "central", "high_stress"):
        a_ = ach[v]
        rv_ = V[v]["rec_vs_P2"]
        vals = [(f"{wname(v)} ×{N['sw']['scales'][v]:.2f}", "body", C["ice"]),
                (f"{fmt_pct(a_['rotable_immediate_fill_rate'])} · {fmt_int(a_['aog_hours_per_year'])} h", "mono", C["ice"]),
                (f"{fmt_int(wmap[v]['aog_hours']['mean'])} {ci_txt(wmap[v]['aog_hours']['ci'])}", "mono", C["aero_teal"]),
                (f"{aed_ci(rv_['net_benefit_aed'], *rv_['net_benefit_ci'], signed=True)}", "mono",
                 C["aero_teal"] if rv_["net_benefit_ci"][0] > 0 else C["amber"])]
        for c_, (t, sty, col) in zip(cx, vals):
            s.text(c_, yy, 210, 18, P(R(t, sty, s=8.8, c=col)))
        s.line(70, yy + 20, 766, yy + 20, HAIR, 0.5)
        yy += 25
    s.text(70, yy + 2, 696, 30, P(R(N["sw"]["text"] + ". " + N["sw"]["ranges_note"], "small", s=8), ls=1.05))
    s.card(806, 418, 426, 252, line=blend(C["red"], C["card"], 0.45))
    s.text(828, 434, 380, 16, P(R("THE BIG CONDITION: EMERGENCY RECOVERY ROUTES", "label", c=C["red"])))
    s.text(828, 456, 384, 210, [
        P(R("Every plan leans on the emergency routes: borrowing a part from another of our aircraft at AUH "
            "(engineering/quality approval required), borrowing from other airlines, exchange/loan and local buy. "
            "Switch them off (earlier runs):", "bodym", s=8.7), after=6, ls=1.08),
        P(R(f"{sn(N, bid)} {bid}  ", "mono", s=8.8, c=C["copper"]),
          R(f"{fmt_int(ro['central_p0_aog_hours'])} → {fmt_int(ro['p0_aog_hours'])} h/yr", "mono", s=8.8), after=3),
        P(R(f"{sn(N, cid)} {cid}  ", "mono", s=8.8, c=C["aero_teal"]),
          R(f"{fmt_int(ro['central_p2_aog_hours'])} → {fmt_int(ro['p2_aog_hours'])} h/yr", "mono", s=8.8), after=3),
        P(R(f"+ Extra Spares {fid}  ", "mono", s=8.8, c=C["ice"]),
          R(f"{fmt_int(desk['central_rec_aog_hours'])} → {fmt_int(ro['rec_aog_hours'])} h/yr", "mono", s=8.8), after=6),
        P(R(("The ranking survives, the scale does not: " if ro["p0_aog_hours"] > ro["p2_aog_hours"] > ro["rec_aog_hours"]
             else "") + "results are conditional on those routes existing at the assumed availability.", "body",
            s=8.7), ls=1.08, after=4),
        P(R(SCOPE["text"], "monos", s=7, c=C["aero_teal"]), ls=1.05),
    ])
    s.footer(7, "Source: simulated runs and the calibration lock, docs/data · splits as labelled", total)
    S.append(s)

    # 8 — Planner actions, AOG lab, and the donor recount (post-plan) -------------------------------------------------
    ac = N["act_counts"]
    cfs = N["aog_sum"]["counterfactual"]
    dr = N["donor"]
    s = Slide(bg=bg)
    s.header(8, "Planner actions, AOG lab and donor aircraft",
             f"What the planner does on Monday: {N['n_actions']} exceptions, {ac['by_severity']['urgent']} urgent",
             f"The action centre turns the plan into a week-{N['act_week']} inbox with evidence and an owner. The AOG lab "
             "replays every history grounding and ranks the desk's options on what was known at the time.")
    s.card(48, 150, 560, 520)
    s.text(70, 166, 420, 16, P(R(f"EXCEPTIONS BY TYPE · WEEK {N['act_week']}", "label", c=C["faint"])))
    s.chip_r(590, 164, "DERIVED")
    s.image(58, 188, 540, 250, CH.actions(540, 250))
    xx = 70
    for sev, col in [("urgent", C["red"]), ("review", C["amber"]), ("info", C["slate"])]:
        s.rect(xx, 452, 10, 10, fill=col, r=2)
        s.text(xx + 16, 448, 120, 18, P(R(f"{sev} {ac['by_severity'].get(sev, 0)}", "monos", s=8.5)))
        xx += 120
    acts = N["actions"]
    a1 = ([a for a in acts if a["pn"] == inc["pn"] and a["station"] == inc["station"]] or acts)[0]
    s.text(70, 476, 516, 190, [
        P(R("EXAMPLE FROM THE INBOX", "label", c=C["faint"]), after=4),
        P(R(f"{a1['severity'].upper()} · {a1['owner']} · ", "monos", s=7.8, c=C["red"]), R(a1["summary"], "body", s=9),
          ls=1.05, after=1),
        P(R(f"→ {a1['recommended_action']}", "bodym", s=8.6), ls=1.05, after=8),
        P(R("NEGATIVE RESULT", "label", c=C["amber"]), after=3),
        P(R(f"In {cfs['history_took_best_option']} of {cfs['requests_compared']} history requests the desk already took "
            f"the top-ranked option; history did better overall ({fmt_int(cfs['actual_request_aog_h'])} vs "
            f"{fmt_int(cfs['best_option_request_aog_h'])} h), helped by {cfs['history_used_robbery']} borrowed parts the "
            "lab never ranks. The lever is positioning, before the removal happens.", "bodym", s=8.8), ls=1.08)])
    s.card(626, 150, 606, 286)
    s.text(648, 166, 520, 16, P(R(f"{inc['id']} · THE DESK'S OPTIONS, RANKED ON WHAT WAS KNOWN", "label", c=C["faint"])))
    s.chip_r(1214, 164, "SIMULATED")
    hd = [("Option", 648), ("Wait", 960), ("Down", 1020), ("Direct cost", 1078), ("Rank", 1170)]
    for h_, x_ in hd:
        s.text(x_, 188, 120, 14, P(R(h_.upper(), "label", s=7.2, c=C["faint"])))
    yy = 205
    opts = sorted(inc["options"], key=lambda o: (o["rank"] is None, o["rank"] or 99, not o["feasible"]))
    for o in opts:
        feas = o["feasible"]
        col = C["ice"] if feas else C["faint"]
        if o["rank"] == 1:
            s.rect(640, yy - 3, 584, 20, fill=blend(C["aero_teal"], C["card"], 0.14), r=4)
        nm_ = o["option"].replace(" (human decision)", "")
        s.text(648, yy, 310, 16, P(R(nm_, "body", s=8.4, c=col)))
        s.text(960, yy, 60, 16, P(R(f"{o['wait_h']:g} h" if o["wait_h"] is not None else "—", "mono", s=8.2, c=col)))
        s.text(1020, yy, 58, 16, P(R(f"{o['aog_h']:g} h" if o["aog_h"] is not None else "—", "mono", s=8.2, c=col)))
        s.text(1078, yy, 92, 16, P(R(f"AED {o['direct_cost']:,}" if feas else "—", "mono", s=8.2, c=col)))
        s.text(1170, yy, 56, 16, P(R(str(o["rank"]) if o["rank"] else ("human" if o["human_decision"] else "—"),
                                     "mono", s=8.2, c=C["amber"] if o["human_decision"] else col)))
        yy += 22
    s.card(626, 448, 606, 222, line=blend(C["amber"], C["card"], 0.45))
    s.text(648, 462, 560, 16, P(R("DONOR AIRCRAFT · POST-PLAN, EXPLORATORY · NOT IN THE HEADLINE", "label", c=C["amber"])))
    hold = dr["holdout"]
    rows_ = [P(R("BORROWED FROM ANOTHER OF OUR AIRCRAFT / YR · TEST RUNS", "label", s=6.8, c=C["faint"]),
               after=3)]
    for c_ in (bid, "P1", cid, fid):
        r_ = hold["robberies_per_year"][c_]
        val = (f"{half_up1(r_['mean'])} [{half_up1(r_['ci'][0])}–{half_up1(r_['ci'][1])}]" if "mean" in r_ else r_["status"])
        rows_.append(P(*named(N, c_, "bodym", s=8.6, short=True), R("  " + val, "mono", s=8.4,
                                                                      c=C["ice"] if "mean" in r_ else C["faint"]),
                       after=1))
    p2p0 = hold["robberies_paired"]["P2-P0"]
    rows_.append(P(R(f"{cid} − {bid}: {half_up1(p2p0['mean'])} [{half_up1(p2p0['ci'][0])}, {half_up1(p2p0['ci'][1])}] a year".replace("-", "−"),
                     "monos", s=8, c=C["aero_teal"]), after=3))
    rows_.append(P(R(f"Donor hours in the test runs: {hold['donor_hours']}.", "small", s=7.8, c=C["titanium"]), ls=1.05))
    s.text(648, 484, 330, 182, rows_)
    hp = dr["historical_p0"]
    s.rect(990, 484, 228, 176, fill=blend(C["titanium"], C["card"], 0.06), line=HAIR, r=6)
    s.text(1002, 492, 206, 168, [
        P(R(f"HISTORICAL {bid} · NOT THE TEST RUNS", "label", s=6.8, c=C["faint"]), after=4),
        P(R(f"{fmt_int(hp['gross_donor_hours_per_year'])} h/yr", "mid", s=14, c=C["copper"]), after=0),
        P(R("donor aircraft held, in the history", "small", s=7.8), after=3),
        P(R(f"{fmt_int(hp['counted_material_aog_hours_per_year'])} h/yr", "mid", s=14, c=C["ice"]), after=0),
        P(R("counted waiting-for-part downtime, same history", "small", s=7.8), after=5),
        P(R(dr["label"].split(". ", 1)[1], "small", s=7.3, c=C["amber"]), ls=1.05)])
    s.footer(8, "Source: simulated history weeks 0–103 and holdout as labelled, docs/data", total)
    S.append(s)

    # 9 — How it was protected -------------------------------------------------------------------------------------
    pc = N["prov_counts"]
    val = N["validation"]
    cons = N["consistency"]
    n_in = sum(1 for c in cons.values() if c["selection_inside_holdout_ci"])
    cal = {t["metric"]: t for t in N["cal"]["targets_vs_achieved"]}
    v1 = N["v1"]
    s = Slide(bg=bg)
    s.header(9, "How the result was protected", "Calibrated first, frozen, then tested once on fresh runs",
             f"No operator data exists here. {N['n_assump']} parameters sit in an assumption register with a provenance tag; "
             "the history is simulated from them, and every model output is derived from that history.")
    s.card(48, 150, 380, 520)
    s.text(70, 166, 340, 16, P(R("PROVENANCE OF THE ASSUMPTION REGISTER", "label", c=C["faint"])))
    yy = 194
    for prov in ("ASSUMED", "REAL", "SIMULATED"):
        v = pc.get(prov, 0)
        s.chip(70, yy, prov)
        s.rect(190, yy + 4, 170 * v / N["n_assump"] + 2, 10, fill=PROV_COLOR[prov], r=2)
        s.text(190 + 170 * v / N["n_assump"] + 10, yy + 1, 60, 16, P(R(str(v), "mono", s=9)))
        yy += 28
    s.text(70, yy + 6, 340, 210, [
        bullet([R(f"REAL: station coordinates (OurAirports) and the Monash car-parts benchmark "
                  f"({fmt_int(N['monash_n'])} real intermittent series).", "bodym", s=9.2)], col=PROV_COLOR["REAL"], after=6),
        bullet([R(f"ASSUMED: fleet ({N['nb']} narrowbody + {N['wb']} widebody archetypes), costs, penalties, route odds.",
                  "bodym", s=9.2)], col=PROV_COLOR["ASSUMED"], after=6),
        bullet([R(f"SIMULATED: {N['n_weeks']} weeks of history, {fmt_int(N['requests_hist'])} material requests, "
                  f"plan runs facing identical events.", "bodym", s=9.2)], col=PROV_COLOR["SIMULATED"], after=6),
        bullet([R("DERIVED: forecasts, Palm floats, the frontier, the action list.", "bodym", s=9.2)],
               col=PROV_COLOR["DERIVED"], after=0),
    ])
    s.text(70, 476, 340, 16, P(R("NETWORK · REAL COORDINATES", "label", s=7.2, c=C["faint"])))
    for i, st_ in enumerate(N["stations"]):
        cx, cy = 70 + (i % 2) * 172, 498 + (i // 2) * 26
        s.text(cx, cy, 46, 18, P(R(st_["station"], "mono", s=9.5, b=True,
                                   c=C["aero_teal"] if st_["role"] == "hub" else C["ice"])))
        s.text(cx + 40, cy + 1, 130, 18, P(R(st_["name"].split(", ")[-1].replace(" International", ""),
                                             "small", s=8)))
    s.text(70, 600, 340, 66, P(R(f"{AIRLINE} does not exist. D0/D3/D10 are hypothetical rectification windows; D3/D10 are "
                                 "simplified analogues of MEL repair-interval categories B and C, not operator MEL "
                                 "decisions.", "small", s=8.2), ls=1.08))
    s.card(446, 150, 400, 520)
    s.text(468, 166, 360, 16, P(R("CALIBRATE → FREEZE → ONE TEST", "label", c=C["aero_teal"])))
    steps = [
        (f"1 · Calibrate the {sn(N, bid)} only", f"before any other plan ran: repairable-part fill "
                                                 f"{cal['rotable_immediate_fill_rate']['achieved']:.3f}, "
                                                 f"{fmt_int(cal['aog_hours_per_year']['achieved'])} h/yr, "
                                                 f"{fmt_int(cal['aog_events_per_year']['achieved'])} events/yr, inside an "
                                                 "assumed target range (slide 7)."),
        ("2 · Select on earlier runs", f"forecast methods, plan tables and {len(N['points'])} frontier candidates; the "
                                       "stopping rule written down first."),
        ("3 · Freeze", f"{len(N['freeze']['artefacts'])} artefacts hashed (SHA-256) before the test."),
        ("4 · One test", f"20 fresh runs, seeds {N['seeds'][0]}–{N['seeds'][-1]}, never used before. Later checks are "
                         "labelled post-plan."),
    ]
    yy = 192
    for h_, d_ in steps:
        s.text(468, yy, 360, 70, [P(R(h_, "body", s=9.6, b=True), after=2), P(R(d_, "bodym", s=9), ls=1.08)])
        yy += 70
    s.line(468, yy + 2, 824, yy + 2, HAIR, 0.5)
    s.text(468, yy + 12, 170, 60, [P(R(f"{n_in} of {len(cons)}", "mid", s=18, c=C["aero_teal"])),
                                   P(R("headline numbers from earlier runs inside the test's likely range", "small",
                                       s=8), ls=1.05)])
    s.text(656, yy + 12, 172, 60, [P(R(f"{val['tests_passed']}/{val['tests_total']}", "mid", s=18, c=C["aero_teal"])),
                                   P(R("non-browser tests passed, incl. reconciliation of site numbers" if "non-browser" in (val.get("scope") or "")
                                       else "tests passed, incl. reconciliation of site numbers", "small", s=7.6),
                                     ls=1.05)])
    s.text(468, yy + 78, 360, 40, P(R(f"Earlier runs → test, hours/yr: {cid} "
                                      f"{fmt_int(cons['aog_hours']['selection_recommended'])} → "
                                      f"{fmt_int(cons['aog_hours']['holdout_recommended'])}, {fid} "
                                      f"{fmt_int(N['spt'][fid]['aog_hours'])} → {fmt_int(N['pt'][fid]['aog_hours'])}",
                                      "monos", s=8.2), ls=1.08))
    s.card(864, 150, 368, 520, line=blend(C["amber"], C["card"], 0.45))
    s.text(886, 166, 330, 16, P(R("v1 → v2: A CORRECTION, NOT A RESULT", "label", c=C["amber"])))
    reasons = [r.split(" (AV")[0] for r in v1["superseded_because"]]
    shown = [r_ for r_ in reasons if "%" not in r_][:6]
    s.text(886, 190, 326, 470, [
        P(R("A v1 world was archived after a domain review; see archive/v1.", "body", s=10, b=True), after=8, ls=1.1),
        P(R(f"The review listed {len(reasons)} realism problems that mostly flattered the improvement, for example:",
            "bodym", s=9.2), after=6, ls=1.08),
        *[bullet([R(r_, "bodym", s=8.9)], col=C["amber"], after=4, ls=1.05) for r_ in shown],
        P(R(f"…and {len(reasons) - len(shown)} more (archive/v1/README.md).", "small", s=8.3), after=8),
        P(R("v2 fixed them as domain corrections chosen before any v2 result, recalibrated the starting point only, and "
            "ran its test on fresh seeds. v1 numbers are not findings.", "bodym", s=9.2), after=8, ls=1.08),
    ])
    s.footer(9, f"Source: docs/data and reports/junit.xml · release {N['release']}", total)
    S.append(s)

    # 10 — Limitations, honest findings & author ----------------------------------------------------------------------
    inv_p2 = [x for x in N["invalid"] if x["policy"] == cid]
    inv_i = [x for x in N["invalid"] if x["policy"] == fid]
    s = Slide(bg=bg)
    s.header(10, "Limitations & author", "What this shows, and what it does not",
             "A simulation of a fictional airline, built to be checked. The limits below matter most; all of them are "
             "listed in LIMITATIONS.md and on the app's Data & Method page.")
    s.card(48, 150, 760, 520, line=blend(C["amber"], C["card"], 0.4))
    s.text(70, 166, 600, 16, P(R("LIMITATIONS THAT MATTER MOST", "label", c=C["amber"])))
    lim = [
        ("Simulated data, not a dispatch tool.", "Every airline number is simulated on a world the author designed; "
                                                "not an approved maintenance, airworthiness or dispatch tool."),
        ("A deliberately weak starting point.", f"Most of the {sn(N, bid)}'s few outstation spares are brakes changed "
                                                f"only at {N['hub']}, so much of the gap measures stocking no-go parts at "
                                                "outstations, which a competent operator already does."),
        ("Emergency-route dependence.", f"With the routes off, downtime rises to {fmt_int(ro['p0_aog_hours'])} h/yr for "
                                        f"the {sn(N, bid)}, {fmt_int(ro['p2_aog_hours'])} for the {sn(N, cid)} and "
                                        f"{fmt_int(ro['rec_aog_hours'])} with Extra Spares (earlier runs)."),
        ("Donor downtime not in the headline.", "Hours of aircraft that donated a part are not counted; per-plan donor "
                                                "hours are not reconstructible from current logs (slide 8)."),
        ("Flagged plan lines.", f"Outstation brake allocations are flagged as an {N['invalid_text']}: "
                                f"{len(inv_p2)} in the {sn(N, cid)}, {len(inv_i)} with Extra Spares. Kept in the frozen "
                                "results; no planner should act on them."),
        ("The cost is a scenario.", "Hourly downtime rates and the fixed per-event cost are assumptions; the "
                                    "recommended frontier point moves with them."),
        ("Deadline classes.", "D3/D10 are simplified analogues of MEL repair-interval categories B and C, not operator "
                              "MEL decisions."),
        ("Search, not proof.", "Spares were added one at a time on an analytic proxy with guardrails, then re-simulated; "
                               "the best evaluated allocation under the stated scenario, not a proven best."),
    ]
    half = (len(lim) + 1) // 2
    for col_i, chunk in enumerate((lim[:half], lim[half:])):
        s.text(70 + col_i * 366, 190, 344, 300, [P(R(t + " ", "body", s=9.1, b=True), R(d_, "bodym", s=8.8), after=7,
                                                   ls=1.08) for t, d_ in chunk])
    s.line(70, 486, 786, 486, HAIR, 0.6)
    s.text(70, 496, 700, 16, P(R("FINDINGS AGAINST THE METHOD", "label", c=C["faint"])))
    hs_ = [(f"{hon['forecast_champions_best']}/{hon['forecast_cells']}",
            f"groups where the method chosen in advance was best on the test runs (SBA "
            f"{hon['sba_intermittent_rotables_rank']}th of {hon['sba_intermittent_rotables_n_methods']} for rarely-needed "
            "repairable parts)"),
           (f"{hon['mtbur_history_error'] * 100:.0f}% vs {hon['mtbur_quote_error'] * 100:.0f}%",
            "error in how often a part comes off: own history vs supplier quote"),
           (f"−{cm['fill']} pts", f"shelf fill, {sn(N, cid)} vs {sn(N, bid)} (cheap consumable and throw-away parts)"),
           (f"{fmt_int(ro['central_p2_aog_hours'])}→{fmt_int(ro['p2_aog_hours'])} h",
            f"{sn(N, cid)} hours/yr with the emergency routes switched off")]
    for i, (big_, txt_) in enumerate(hs_):
        x_ = 70 + i * 180
        s.text(x_, 516, 170, 30, P(R(big_, "mid", s=16, c=C["amber"] if i else C["aero_teal"])))
        s.text(x_, 546, 166, 90, P(R(txt_, "bodym", s=8.5), ls=1.08))
    s.scope(70, 648, 716, s=7.4)
    s.card(826, 150, 406, 520)
    s.text(848, 166, 360, 16, P(R("AUTHOR", "label", c=C["faint"])))
    s.text(848, 190, 370, 110, [P(R("Akash Gajjar", "title", s=22), after=6),
                                P(R("MSc Supply Chain Management", "body", s=11)),
                                P(R("University of Liverpool (2025)", "bodym", s=10.5))])
    s.text(848, 290, 370, 140, [P(R("GITHUB", "label", s=7.5, c=C["faint"]), after=2),
                                P(R(GITHUB_URL.replace("https://", ""), "mono", s=9), after=10),
                                P(R("LIVE APP", "label", s=7.5, c=C["faint"]), after=2),
                                P(R(LIVE_URL.replace("https://", ""), "mono", s=8.4), after=10),
                                P(R("CODE", "label", s=7.5, c=C["faint"]), after=2),
                                P(R(REPO_URL.replace("https://", ""), "mono", s=8.4))])
    s.image(848, 440, 362, 200, A["wb"])
    s.footer(10, f"Source: simulated runs, docs/data · release {N['release']}", total)
    S.append(s)

    notes = [
        "Title. No results on this slide: the plans are introduced by name; results start on slide 3 with the scope "
        "line and the reading note. Everything is simulated for a fictional airline.",
        "The problem: one incident (AOG-0001), then the pattern behind it, and the first action for this part: "
        "escalate to reliability engineering and warranty review; extra spares are interim cover.",
        "Results: the four plans on the 20 fresh test runs (seeds 2000-2019, central world, paired), the stress worlds "
        "(a narrow reliability range), and the verbatim reading note.",
        "Capital and positioning: the capital table (gross lines, net, not cash back), where the stock goes, and Palm "
        "at BOM, computed here from the exported Poisson distribution and checked against the exporter.",
        "Forecasting: the chosen methods were best in few groups; history beats the supplier's quote.",
        "Readiness Frontier: the extra-spares option for additional capital, its paired gain, and the most useful "
        "insight: faster repair can beat buying spares.",
        "What it depends on: one-at-a-time sensitivity, the calibration choice (an assumption), the stress worlds, "
        "and the emergency routes.",
        "Planner actions, the AOG lab (a negative result), and the post-plan donor recount kept apart from the "
        "headline; historical donor hours only beside historical counted downtime.",
        "Provenance, calibrate-freeze-test, earlier-runs-to-test consistency, and the v1 to v2 correction.",
        "Limitations, findings against the method, and author.",
    ]
    for s_, n_ in zip(S, notes):
        s_.notes = n_
    return S


# --------------------------------------------------------------------------------------------------------------------
# v2.1 build guards: forbidden words / OEM names gone, verbatim texts present, no result on the title slide
# --------------------------------------------------------------------------------------------------------------------
def slide_texts(slides):
    out = []
    for s in slides:
        t = " ".join(r["t"] for it in s.items if it["k"] == "text" for p in it["paras"] for r in p["runs"])
        out.append(t + " " + (getattr(s, "notes", "") or ""))
    return out


def _gate(texts, where):
    from gnm.export import v21
    bad = [(where, i + 1, kind, pat.search(t).group(0)) for i, t in enumerate(texts)
           for kind, pat in v21.FORBIDDEN_PATTERNS.items() if pat.search(t)]
    for stale in ("legacy OEM-quote", "P0 legacy", "P2 network", "P1 local"):
        bad += [(where, i + 1, "stale label", stale) for i, t in enumerate(texts) if stale in t]
    assert not bad, f"v2.1 text gate failed: {bad[:6]}"


def text_guards(N, deck=None):
    """Fail the build unless the v2.1 story is complete and clean (v2.1 release brief)."""
    names = [dn(N, c) for c in ("P0", "P1", "P2", "I125")]
    red = N["core"]["aog_reduction"]["mean"]
    pct = round(100 * red / N["kpi"]["aog_hours"]["baseline"])
    if deck is not None:
        T = slide_texts(deck)
        _gate(T, "deck")
        assert len(deck) == 10, len(deck)
        # title slide: no result claim (no reduction, no percentage)
        assert fmt_int(red) not in T[0] and f"{pct}%" not in T[0], "result claim on the title slide"
        assert all(nm_ in T[0] for nm_ in names)
        allt = " ".join(T)
        must = [N["scope"], N["reading"], N["cap_t"]["note"], N["sw"]["text"], N["sw"]["ranges_note"],
                N["ins"]["text"], N["cal_note"]["text"], N["esc"]["text"], N["invalid_text"],
                N["donor"]["holdout"]["donor_hours"], *[r["text"] for r in N["cap_t"]["rows"]], *names,
                *N["ins"]["levers"]]
        missing = [m for m in must if m not in allt]
        assert not missing, f"deck is missing verbatim text: {missing}"
        for i, t in enumerate(T, 1):
            assert N["credit"] in t, f"slide {i} has no E4 credit footer"
        # the net capital row never alone: wherever "+AED 0.6M" appears, the gross rows and the note are on that slide
        net = [r["text"] for r in N["cap_t"]["rows"] if r["id"] == "net_inventory"][0]
        for i, t in enumerate(T, 1):
            if net in t:
                assert all(r["text"] in t for r in N["cap_t"]["rows"]) and N["cap_t"]["note"] in t, f"net alone on {i}"
        # every slide with a downtime KPI shows the scope line
        for i in (3, 4, 6, 7, 10):
            assert N["scope"] in T[i - 1], f"slide {i} lacks the scope line"
        # historical donor hours only beside historical counted downtime
        hp = N["donor"]["historical_p0"]
        for i, t in enumerate(T, 1):
            if fmt_int(hp["gross_donor_hours_per_year"]) in t:
                assert fmt_int(hp["counted_material_aog_hours_per_year"]) in t and "HISTORICAL" in t.upper(), i


# --------------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["deck"], default=None)
    ap.add_argument("--build-dir", default=None)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    build = Path(a.build_dir) if a.build_dir else Path(tempfile.mkdtemp(prefix="gnm-deck-"))
    build.mkdir(parents=True, exist_ok=True)
    print(f"build dir: {build}")

    N = compute_numbers()
    sanity_checks(N)
    ttfs = prepare_fonts()
    plt, fonts = setup_matplotlib(ttfs)
    print(f"fonts for charts: {fonts}")
    CH = Charts(plt, fonts, build, N)
    A = rasterise_svgs(build, N)

    if a.only in (None, "deck"):
        bg = str(make_background(build / "bg-deck.png", 1280, 720))
        slides = build_deck(N, A, CH, bg)
        text_guards(N, deck=slides)
        render_pptx(slides, OUT / "case_study_deck.pptx")
        pngs = html_to_pdf_and_png(render_html(slides, 1280, 720), 1280, 720, OUT / "case_study_deck.pdf", build, "deck")
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        shutil.copy(OUT / "case_study_deck.pdf", DOWNLOADS / "case_study_deck.pdf")
        print(f"deck: {OUT / 'case_study_deck.pptx'} + .pdf ({len(slides)} slides; copied to {DOWNLOADS}); "
              f"previews {pngs[0].parent}")


if __name__ == "__main__":
    main()
