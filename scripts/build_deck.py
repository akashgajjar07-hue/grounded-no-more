#!/usr/bin/env python3
"""Build the GROUNDED NO MORE v2 case-study deck (PPTX + PDF), the LinkedIn carousel (PDF, DRAFT) and the post draft.

    python scripts/build_deck.py                      # deck + carousel + post draft
    python scripts/build_deck.py --only deck          # just the deck (+ docs/downloads/case_study_deck.pdf)
    python scripts/build_deck.py --build-dir /tmp/x   # keep intermediate assets / slide previews there

Rules this script follows (see docs/agent_notes/deck-video.md and docs/agent_notes/v2_regen_brief.md):
* Every number shown is read from docs/data/*.json (and, for the calibration band ends, outputs/freeze/calibration_lock.json)
  at build time. Nothing is typed by hand. The only literals are design constants, layout and fixed prose.
* The headline is the v2 HOLDOUT (seeds 2000-2019, central world): P2 network positioning vs P0, the legacy OEM-quote
  policy. I125 is presented as the frontier option for additional capital. `sanity_checks()` fails the build if the
  export is not that holdout. Selection-seed numbers are labelled as such; the D015 stress check is labelled post-plan.
* v1 is archived, not a finding: it is mentioned as a correction story only, never with its numbers.
* Falcon Hub Airways is fictional. Only the repo's own SVG illustrations (docs/assets/svg, original plan views) and charts
  rendered here are used. No real airline names or logos.
* One layout spec per slide feeds two renderers: python-pptx (editable PPTX) and an HTML page that Playwright prints to PDF
  (no LibreOffice needed). Charts are matplotlib PNGs; SVG illustrations are rasterised with Playwright so their fonts load.
* Fonts: the vendored woff2 files (docs/vendor/fonts, OFL) are converted to TTF in presentations/fonts so matplotlib can use them
  and so a PowerPoint user can install them. PPTX cannot embed fonts via python-pptx; without the fonts installed PowerPoint
  substitutes its defaults and every text box has slack for that.
* Nothing is posted anywhere. The carousel and the post are drafts.
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
CAL_LOCK = ROOT / "outputs" / "freeze" / "calibration_lock.json"
V2_HOLDOUT_SEEDS = list(range(2000, 2020))
V1_HOLDOUT_SEEDS = set(range(1000, 1020))


def fmt_mm(x, dp=1):
    """Always in millions: AED 0.6M, −AED 33.9M."""
    return f"{'−' if x < 0 else ''}AED {abs(x) / 1e6:.{dp}f}M"


def ci_m(ci, dp=1):
    return f"[{ci[0] / 1e6:.{dp}f}, {ci[1] / 1e6:.{dp}f}]".replace("-", "−")


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
    N["generated_at"] = k["meta"]["generated_at"]
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
        self.line(48, 682, 1232, 682, HAIR_BG, 0.75)
        self.text(48, 689, 1060, 14, P(R(f"GROUNDED NO MORE · {AIRLINE} · simulated planning snapshot · {source}",
                                         "small", s=7.5)))
        self.text(1032, 689, 200, 14, P(R(f"{num:02d} / {total:02d}", "label", s=7.5, c=C["faint"]), al="r"))


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
        for cls, col, mk, lab in [("C", C["titanium"], "o", "Consumables"), ("E", C["slate"], "s", "Expendables"),
                                  ("R", C["aero_teal"], "D", "Rotables")]:
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
        ax.text(S - 0.42, top * 1.1, f"S = {S} units at BOM (P2)", fontsize=fs + 0.5, color=C["ice"], va="top",
                fontfamily=self.F["mono"])
        ax.set_xticks([r["q"] for r in d])
        ax.set_ylim(0, top * 1.18)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("Units of this PN on the way back to BOM (AUH resupply) at a random moment", fontsize=fs + 0.5)
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
        ax.set_xlabel("Material AOG h / year (log) · holdout mean and 95% CI", fontsize=fs)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        for t in ax.get_xticklabels():
            t.set_fontfamily(self.F["mono"])
            t.set_fontsize(fs - 0.5)
        from matplotlib.lines import Line2D
        hs = [Line2D([], [], color=c, marker=m, ls="-", ms=5, lw=1, mfc=c if p != "P1" else C["midnight"])
              for p, c, m, _ in pol_style]
        names = {"P0": "P0 legacy OEM-quote", "P1": "P1 local", "P2": "P2 network"}
        labels = [f"{names[p]} · {N['out_rot'][p]} outstation rotables" for p, *_ in pol_style]
        lg = ax.legend(hs, labels, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, frameon=False,
                       fontsize=fs - 0.5 if not big else fs - 1.5, handletextpad=0.4, columnspacing=1.0)
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
        ax.text(p0["capital_aed"] / 1e6 + 0.9, p0["aog_hours"], f"{base} legacy OEM-quote", color=C["copper"],
                va="center", ha="left", **mono)
        p1 = N["pt"]["P1"]
        ax.text(p1["capital_aed"] / 1e6, p1["aog_hours"] * 1.35, "P1 local", color=C["copper"], va="center",
                ha="center", **mono)
        ax.text(p2["capital_aed"] / 1e6 - 0.9, p2["aog_hours"] * 0.62, f"{core} network · core", color=C["aero_teal"],
                va="center", ha="right", fontweight="bold", **mono)
        ax.annotate(f"{fo} · frontier option\n+{fmt_mm(i1['capital_aed'] - p2['capital_aed'])} vs {core}",
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
        ax.set_ylabel("Material AOG h / year (log)", fontsize=fs + 0.5)
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
        lab = {"aog_penalty": "Hourly AOG penalty", "repair_tat": "Repair TAT", "lead_time": "Purchase lead time",
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
        """Holdout material AOG h/yr by policy, with capital (carousel)."""
        N = self.N
        ids = [N["base_id"], "P1", N["core_id"], N["fo_id"]]
        names = {N["base_id"]: "P0 legacy", "P1": "P1 local", N["core_id"]: "P2 network", N["fo_id"]: "I125 option"}
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.25, 0.04, 0.73, 0.92])
        top = max(N["pols"][p]["kpi"]["aog_hours"]["ci_hi"] for p in ids)
        for i, pid in enumerate(ids):
            k = N["pols"][pid]["kpi"]["aog_hours"]
            capv = N["pols"][pid]["kpi"]["spare_capital_aed"]["mean"]
            col = {N["base_id"]: C["copper"], N["core_id"]: C["aero_teal"]}.get(pid, C["slate"])
            ax.barh(i, k["mean"], height=0.58, color=col, alpha=0.95 if pid != N["fo_id"] else 0.6)
            ax.plot([k["ci_lo"], k["ci_hi"]], [i, i], color=C["ice"], lw=1, alpha=0.6)
            ax.text(k["ci_hi"] + top * 0.025, i, f"{fmt_int(k['mean'])} h · {fmt_mm(capv)}", va="center",
                    fontsize=11, fontfamily=self.F["mono"], color=C["ice"])
        ax.set_yticks(range(len(ids)))
        ax.set_yticklabels([names[p] for p in ids], fontsize=12, fontfamily=self.F["mono"])
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


def common(N):
    """Phrases used on several slides, all built from data."""
    core, fo = N["core"], N["fo"]
    red = core["aog_reduction"]
    d = dict(
        red=fmt_int(red["mean"]), red_ci=ci_h(red["ci"]),
        cap=fmt_mm(core["capital_aed"]["mean"]), cap_ci=ci_m(core["capital_aed"]["ci"], 2),
        out0=N["out_rot"]["P0"], out1=N["out_rot"]["P1"], out2=N["out_rot"]["P2"],
        fo_cap=fmt_mm(fo["extra_capital_aed"]["mean"]),
        fo_red=fmt_int(fo["aog_reduction"]["mean"]), fo_red_ci=ci_h(fo["aog_reduction"]["ci"]),
        fill=f"{abs(core['immediate_fill_pts']['mean']):.2f}",
        fill_ci=f"[{core['immediate_fill_pts']['ci'][0]:.2f}, {core['immediate_fill_pts']['ci'][1]:.2f}]".replace("-", "−"),
    )
    # AV2-03: P2 re-mixes the float (computed by the exporter from the P0/P2 stock tables)
    rm = core.get("remix")
    d["remix"] = (f"It buys {rm['buy_units']} rotables (≈{fmt_mm(rm['buy_aed'])}) and sheds {rm['shed_units']} high-value ones "
                  f"(≈{fmt_mm(rm['shed_aed'])}), net about +{d['cap']}.") if rm else ""
    return d


def build_deck(N, A, CH, bg, total=10):
    S = []
    k, core, fo, hon = N["kpi"], N["core"], N["fo"], N["hon"]
    cid, bid, fid = N["core_id"], N["base_id"], N["fo_id"]
    aogk, cap = k["aog_hours"], k["spare_capital_aed"]
    cm = common(N)
    pols = N["pols"]

    # 1 — Title ------------------------------------------------------------------------------------------------------
    s = Slide(bg=bg)
    s.image(690, 112, 270, 340, A["nb"])
    s.image(950, 96, 300, 360, A["wb"])
    s.text(690, 462, 270, 16, P(R(f"NARROWBODY ARCHETYPE · {N['nb']} TAILS", "label", s=7.5, c=C["faint"]), al="c"))
    s.text(950, 462, 300, 16, P(R(f"WIDEBODY ARCHETYPE · {N['wb']} TAILS", "label", s=7.5, c=C["faint"]), al="c"))
    s.text(690, 480, 560, 16, P(R("Original plan-view schematics · not OEM drawings", "small", s=7.5), al="c"))
    s.card(708, 524, 524, 124, line=blend(C["titanium"], C["card"], 0.3))
    s.text(728, 540, 490, 16, P(R(f"FRONTIER OPTION · IF YOU INVEST AN ADDITIONAL {cm['fo_cap'].upper()}", "label",
                                  c=C["titanium"])))
    s.text(728, 564, 490, 80, [
        P(R(f"{fid}: a further {cm['fo_red']} AOG h/yr {cm['fo_red_ci']} below {cid}", "h3", s=13), after=4),
        P(R(f"Paired holdout. Not the headline: "
            + (f"its cost lead over {cid} is not significant if repair is 25% faster, and "
               if not fo["repair_tat_x0_75"]["net_benefit_significant"] else "")
            + "the recommended point shifts with the hourly penalty.", "bodym", s=9.3), ls=1.08)])
    s.text(56, 64, 640, 16, P(R("AVIATION SPARE-PARTS PLANNING · A SIMULATION CASE STUDY", "eyebrow")))
    s.text(56, 86, 640, 180, [P(R("GROUNDED", "title", s=58, sp=-1), ls=0.9),
                              P(R("NO MORE", "title", s=58, sp=-1, c=C["aero_teal"]), ls=0.9)])
    s.text(56, 250, 620, 30, P(R("Which rotables you hold, and where, matters.", "lede", s=15, c=C["ice"])))
    s.text(56, 288, 610, 66, P(R(f"Network positioning ({cid}) cuts material AOG by {cm['red']} h/yr {cm['red_ci']} vs "
                                 f"{N['base_label']}, for +{cm['cap']} of capital.", "body", s=12), ls=1.12))
    y0 = 376
    s.line(56, y0 - 12, 660, y0 - 12, HAIR_BG, 0.75)
    stat(s, 56, y0, 196, f"−{cm['red']} h", "material AOG / year vs P0",
         f"{fmt_int(aogk['baseline'])} → {fmt_int(aogk['value'])} h/yr", size=25)
    stat(s, 256, y0, 210, f"+{cm['cap']}", "extra spare capital",
         f"{fmt_mm(cap['baseline'])} → {fmt_mm(cap['value'])}", col=C["copper"], size=25)
    stat(s, 476, y0, 196, f"{cm['out0']} → {cm['out2']}", "outstation rotables",
         f"P2 wins in all {len(core['worlds'])} simulated worlds", col=C["ice"], size=25)
    s.chip(56, 498, "SIMULATED", f"SIMULATED · {cid} VS {bid} · PAIRED · HOLDOUT SEEDS {N['seeds'][0]}–{N['seeds'][-1]}")
    s.text(56, 530, 640, 30, P(R(f"{AIRLINE} · {N['nb'] + N['wb']} aircraft · {N['n_stations']} stations · "
                                 f"{N['n_parts']} PNs · {N['n_weeks']} simulated weeks", "monos", s=8.3), ls=1.15))
    s.text(56, 578, 620, 80, [P(R("Akash Gajjar", "h3", s=13), after=2),
                              P(R("MSc Supply Chain Management, University of Liverpool (2025)", "bodym", s=10),
                                after=4),
                              P(R(LIVE_URL.replace("https://", ""), "monos", s=8.5, c=C["aero_teal"])),
                              P(R(REPO_URL.replace("https://", ""), "monos", s=8.5))])
    s.footer(1, "numbers read from docs/data at build time", total)
    S.append(s)

    # 2 — The problem -----------------------------------------------------------------------------------------------
    inc = N["inc"]
    cf = inc["counterfactual"]
    part = N["part"][inc["pn"]]
    sv = N["sv"]
    asum = N["aog_sum"]
    s = Slide(bg=bg)
    s.header(2, "The problem", f"None on the shelf at {inc['station']}: {inc['aog_hours']} hours of material-related "
             "downtime",
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
    s.card(48, 492, 640, 178)
    s.text(70, 508, 560, 16, P(R("WHY IT KEEPS HAPPENING", "label", c=C["faint"])))
    s.text(70, 530, 600, 60, P(R(f"P0 provisions from vendor-quoted reliability and holds {sv['units']['P0']} of these "
                                 f"actuators at {inc['station']}. Across the network {inc['pn']} caused "
                                 f"{fmt_int(part['aog_h_52w'])} h of material-related downtime in the last 52 history "
                                 f"weeks ({part['aog_events_52w']} events).", "body", s=9.6), ls=1.1))
    s.text(70, 606, 290, 60, [P(R(fmt_int(asum["n_incidents"]), "mid", c=C["copper"], s=18)),
                              P(R("material AOG incidents in two simulated years (P0)", "small", s=8.2))])
    s.text(370, 606, 300, 60, [P(R(f"{fmt_int(asum['aog_hours_total'])} h", "mid", c=C["copper"], s=18)),
                               P(R("material-related downtime, all incidents (P0)", "small", s=8.2))])
    s.image(704, 150, 528, 486, A["nb-32"])
    s.text(704, 646, 528, 16, P(R("ATA 32 ZONE HIGHLIGHTED · NARROWBODY ARCHETYPE · NOT AN OEM DRAWING", "label", s=7,
                                  c=C["faint"]), al="c"))
    s.footer(2, "Source: docs/data/aog_lab.json, parts.json, rotables.json · simulated history weeks 0–103", total)
    S.append(s)

    # 3 — Core finding: P2 ------------------------------------------------------------------------------------------
    pr = N["paired"]["P2-P0"]
    p10 = N["paired"]["P1-P0"]
    bc = N["by_class"]
    s = Slide(bg=bg)
    s.header(3, "The core finding", f"Position the network: {cm['red']} fewer material AOG hours a year for "
             f"+{cm['cap']}",
             f"P2 vs {bid}, {N['base_label']}. P2 pools rotables at {N['hub']} and places {cm['out2']} at the outstations "
             f"where D0 downtime pays for the unit. Every policy runs on the same simulated futures (paired seeds).")
    s.card(48, 150, 700, 520)
    s.text(70, 166, 560, 16, P(R("MATERIAL AOG BY STATION · HOLDOUT, CENTRAL WORLD", "label", c=C["faint"])))
    s.chip_r(730, 164, "SIMULATED")
    s.image(58, 190, 680, 470, CH.stations(680, 470))
    s.card(766, 150, 466, 520)
    s.text(788, 166, 420, 16, P(R(f"{cid} − {bid} · PAIRED · 20 HOLDOUT SEEDS", "label", c=C["aero_teal"])))
    blocks = [
        ("Material AOG h / yr", fmt_int(pr["aog_hours"]["mean"]),
         ci_txt([pr["aog_hours"]["ci_lo"], pr["aog_hours"]["ci_hi"]]), C["aero_teal"]),
        ("Spare capital", fmt_signed(pr["spare_capital_aed"]["mean"], fmt_mm),
         ci_m([pr["spare_capital_aed"]["ci_lo"], pr["spare_capital_aed"]["ci_hi"]], 2), C["copper"]),
        ("Total annual cost", fmt_mm(pr["total_annual_cost_aed"]["mean"]),
         ci_m([pr["total_annual_cost_aed"]["ci_lo"], pr["total_annual_cost_aed"]["ci_hi"]]), C["ice"]),
    ]
    xx = 788
    for lab, val, ci, col in blocks:
        s.text(xx, 188, 148, 16, P(R(lab, "bodym", s=8.6)))
        s.text(xx, 204, 148, 30, P(R(val, "mid", s=16, c=col)))
        s.text(xx, 232, 148, 16, P(R(ci, "monos", s=7.8)))
        xx += 148
    s.line(788, 258, 1210, 258, HAIR, 0.5)
    s.text(788, 268, 420, 16, P(R("HOLDS IN ALL THREE SIMULATED WORLDS", "label", s=7.5, c=C["faint"])))
    yy = 290
    for w in core["worlds"]:
        s.text(788, yy, 110, 18, P(R(wname(w["variant"]), "body", s=9.3)))
        s.text(898, yy, 190, 18, P(R(f"{fmt_int(w['aog_hours']['mean'])} h {ci_txt(w['aog_hours']['ci'])}", "mono", s=8.8,
                                     c=C["aero_teal"])))
        s.text(1090, yy, 120, 18, P(R(f"{fmt_signed(w['capital_aed']['mean'], fmt_mm)} cap.", "mono", s=8.8,
                                      c=C["titanium"]), al="r"))
        yy += 22
    s.line(788, yy + 4, 1210, yy + 4, HAIR, 0.5)
    pe = core["penalty_range"]
    s.text(788, yy + 14, 420, 16, P(R("TOTAL-COST DIFFERENCE ACROSS ×0.5–×2 THE HOURLY PENALTY", "label", s=7.5,
                                      c=C["faint"])))
    s.text(788, yy + 34, 420, 18, P(*[R(f"{lab_} {fmt_mm(pe[key]['mean'])}   ", "mono", s=8.8, c=C["ice"])
                                      for key, lab_ in (("x0.5", "×0.5"), ("x1", "×1"), ("x2", "×2"))]))
    s.text(788, yy + 54, 420, 16, P(R("every 95% CI below zero (fixed per-event cost kept at ×1)", "small", s=8)))
    yy += 82
    s.line(788, yy, 1210, yy, HAIR, 0.5)
    s.text(788, yy + 10, 422, 200, [
        bullet([R("The price: ", "body", s=9.3, b=True, c=C["amber"]),
                R(f"immediate fill is {cm['fill']} pts lower {cm['fill_ci']}, in consumables "
                  f"({fmt_pct(bc[('P0', 'C')]['immediate_fill_rate'], 2)} → {fmt_pct(bc[('P2', 'C')]['immediate_fill_rate'], 2)}) "
                  f"and expendables ({fmt_pct(bc[('P0', 'E')]['immediate_fill_rate'])} → "
                  f"{fmt_pct(bc[('P2', 'E')]['immediate_fill_rate'])}); rotable fill rises "
                  f"{fmt_pct(bc[('P0', 'R')]['immediate_fill_rate'])} → {fmt_pct(bc[('P2', 'R')]['immediate_fill_rate'])}.",
                  "bodym", s=9.3)], after=6),
        bullet([R("P1 ", "body", s=9.3, b=True),
                R(f"(each station optimised alone) holds {cm['out1']} outstation rotables for "
                  f"{fmt_signed(p10['spare_capital_aed']['mean'], fmt_mm)} and still leaves "
                  f"{fmt_int(pols['P1']['kpi']['aog_hours']['mean'])} AOG h/yr, most of it at the hub.", "bodym", s=9.3)],
               after=8),
        P(R("OUTSTATION ROTABLES, P0 → P2", "label", s=7.5, c=C["faint"]), after=3),
        P(*[R(f"{st_['station']} {st_['by_policy']['P0']['rotable_units']}→{st_['by_policy']['P2']['rotable_units']}   ",
              "mono", s=8.6, c=C["ice"]) for st_ in N["stations"] if st_["role"] != "hub"]),
    ])
    s.footer(3, f"Source: docs/data/kpis.json (headline.core), policies.json, network.json · {N['seed_txt']}", total)
    S.append(s)

    # 4 — Why: Palm at BOM -------------------------------------------------------------------------------------------
    fl, ltd = N["float"], N["ltd"]
    hop = [o for o in inc["options"] if o["key"] == "hub_transfer"]
    hop_h = hop[0]["wait_h"] if hop else None
    s = Slide(bg=bg)
    s.header(4, "Why positioning works", f"Palm's theorem: {N['s_bom']} units at BOM turn 0% into "
             f"{round(N['palm_bom'] * 100)}% immediate fill",
             "An outstation's shelf is refilled from AUH, so its own stock is sized on the resupply time T (transit + "
             "expected hub wait), as P2 does; the network float is sized on the repair loop. With Poisson removals, units "
             "on the way back are Poisson with mean λ·T (Palm), whatever the shape of the delay.")
    s.card(48, 150, 560, 520)
    s.text(70, 166, 420, 16, P(R(f"THE CALCULATION · {fl['desc'].upper()}", "label", c=C["faint"])))
    s.chip_r(590, 164, "DERIVED")
    s.rect(70, 192, 516, 64, fill=C["deep_steel"], line=HAIR, r=8)
    s.text(84, 202, 490, 50, [P(R("A(S) = P(X ≤ S − 1),   X ~ Poisson(λ · T)", "mono", s=12.5, c=C["ice"], b=True),
                                al="c"),
                              P(R("immediate fill with S spares = chance fewer than S units are in the loop", "small",
                                  s=8.5), al="c")])
    rows = [
        ("Network removal rate", f"{fl['rate_per_30d']:.2f} per 30 days"),
        (f"BOM removal rate", f"{sv['rate_per_30d']:.2f} per 30 days"),
        ("BOM resupply from AUH T", f"{(sv.get('resupply_days') or sv['loop_days']):.1f} days → λT = {ltd['mean']:.3f}"),
        ("Unit cost · class", f"AED {fl['unit_cost_aed']:,} · {fl['deadline']}"),
        (f"Emergency hop {N['hub']} → BOM", f"{hop_h:g} h" if hop_h is not None else "—"),
    ]
    yy = 270
    for a_, b_ in rows:
        s.text(70, yy, 250, 20, P(R(a_, "bodym", s=9.8)))
        s.text(320, yy, 266, 20, P(R(b_, "mono", s=9.3), al="r"))
        s.line(70, yy + 24, 586, yy + 24, HAIR, 0.5)
        yy += 35
    s.text(70, yy + 10, 516, 16, P(R("TOTAL SPARES IN THE NETWORK (SHELF + REPAIR LOOP), BY POLICY", "label",
                                     c=C["faint"])))
    yy += 36
    tot = fl["spares_total"]
    units = [("P0 legacy", tot["P0"], C["copper"]), ("P1 local", tot["P1"], C["slate"]),
             ("P2 network", tot["P2"], C["aero_teal"]), (f"{fid} option", tot["recommended"], C["titanium"])]
    umax = max(u[1] for u in units)
    for lab, v, col in units:
        s.text(70, yy, 130, 18, P(R(lab, "bodym", s=9.5)))
        s.rect(200, yy + 3, 320 * v / umax, 12, fill=col, r=2)
        s.text(200 + 320 * v / umax + 8, yy, 50, 18, P(R(str(v), "mono", s=9.5)))
        yy += 30
    s.text(70, yy + 8, 516, 40, P(R(f"At BOM: P0 {sv['units']['P0']} units, P2 {sv['units']['P2']}, {fid} "
                                    f"{sv['units']['recommended']}. Pooled at the network level all plans look fine; "
                                    "the station figure decides downtime.", "bodym", s=9), ls=1.08))
    s.card(626, 150, 606, 350)
    s.text(648, 166, 520, 16, P(R(f"LOOP OCCUPANCY AT BOM · POISSON(λT = {ltd['mean']:.3f})", "label", c=C["faint"])))
    s.chip_r(1214, 164, "DERIVED")
    s.image(638, 186, 582, 222, CH.palm_pmf(582, 222))
    s.text(648, 418, 568, 76, [P(R(f"A({N['s_bom']}) = {fmt_pct(N['palm_bom'])}", "mid", c=C["aero_teal"], s=17),
                                 R(f"   vs A({sv['units']['P0']}) = {fmt_pct(sv['availability']['P0'], 0)} under P0",
                                   "mono", s=9.5, c=C["copper"]), after=3),
                               P(R(f"Under P0 every D0 removal at BOM waits for a unit to arrive. With P2's "
                                   f"{N['s_bom']} units, {fmt_pct(N['palm_bom'], 0)} of removals find one on the shelf.",
                                   "bodym", s=9.5), ls=1.08)])
    s.card(626, 512, 606, 158)
    s.text(648, 528, 540, 16, P(R("DOES PALM MATCH THE SIMULATION?", "label", c=C["amber"])))
    s.text(648, 550, 566, 116, [
        P(R(f"Across {N['palm_hub_n']} rotables at the hub ({N['palm_vs_sim_policy']} floats): Palm predicts "
            f"{fmt_pct(N['palm_hub_palm'])} on average, the simulation fills {fmt_pct(N['palm_hub_sim'])} immediately.",
            "body", s=9.8), after=6, ls=1.1),
        P(R("Part by part it is noisier: clustered removals, variable repair times and hub/outstation competition push "
            "some parts below Palm, so every policy is judged in the simulator, not on the formula.", "bodym", s=9.3),
          ls=1.1),
    ])
    s.footer(4, "Source: docs/data/rotables.json (float example, palm_vs_sim), forecast.json (ltd_example), aog_lab.json",
             total)
    S.append(s)

    # 5 — Forecasting, honestly --------------------------------------------------------------------------------------
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
    s.header(5, "Forecasting, honestly", f"Demand is lumpy, and the frozen champions were best in only {n_rank1} of "
             f"{n_cells} cells",
             f"{dcls.get('intermittent', 0)} of {N['n_parts']} part numbers are intermittent (ADI > 1.32 weeks, CV² < 0.49, "
             f"training weeks 0–{N['split_week'] - 1}). Champions were frozen on selection weeks, then checked on the holdout.")
    s.card(48, 150, 560, 520)
    s.text(70, 166, 420, 16, P(R("ADI × CV² · ONE DOT PER PART NUMBER", "label", c=C["faint"])))
    s.chip_r(590, 164, "DERIVED")
    s.image(60, 190, 540, 470, CH.adi_cv2(540, 470))
    s.card(626, 150, 606, 318)
    s.text(648, 166, 520, 16, P(R("CHAMPION CHECK · FROZEN CHAMPION'S RANK ON THE HOLDOUT", "label", c=C["faint"])))
    s.chip_r(1214, 164, "DERIVED")
    hd = [("Cell", 648), ("Frozen champion", 860), ("Rank", 1010), ("Best in hindsight", 1100)]
    for h_, x_ in hd:
        s.text(x_, 190, 160, 14, P(R(h_.upper(), "label", s=7, c=C["faint"])))
    yy = 208
    lab = N["method_labels"]
    for c in sorted(cc, key=lambda c: (c["part_class"], c["demand_class"])):
        hit = c["champion_rank"] == 1
        col = C["aero_teal"] if hit else (C["amber"] if c is ir else C["titanium"])
        s.text(648, yy, 210, 18, P(R(f"{c['part_class']} · {c['demand_class'].replace('_', ' ')} ({c['n_parts']})", "body",
                                     s=8.8, c=C["ice"])))
        s.text(860, yy, 150, 18, P(R(lab.get(c["champion"], c["champion"]).split(" (")[0], "bodym", s=8.8)))
        s.text(1010, yy, 80, 18, P(R(f"{c['champion_rank']} / {c['n_methods']}", "mono", s=8.8, c=col, b=hit)))
        s.text(1100, yy, 120, 18, P(R(lab.get(c["best_in_hindsight"], c["best_in_hindsight"]).split(" (")[0], "bodym",
                                      s=8.8)))
        yy += 25
    s.card(626, 480, 606, 190)
    s.text(648, 496, 560, 16, P(R("WHAT THE HISTORY CAN TELL YOU · MTBUR VS THE SIMULATION'S TRUTH", "label",
                                  c=C["amber"])))
    bars = [("Estimated from history", tr["estimated"], C["aero_teal"]), ("Vendor quote", tr["vendor_quoted"], C["copper"])]
    yy = 522
    for lab_, v, col in bars:
        s.text(648, yy, 160, 18, P(R(lab_, "bodym", s=9.3)))
        s.rect(810, yy + 3, 300 * v / tr["vendor_quoted"], 12, fill=col, r=2)
        s.text(810 + 300 * v / tr["vendor_quoted"] + 8, yy, 90, 18, P(R(f"≈ {v * 100:.0f}% off", "mono", s=9.3)))
        yy += 24
    s.text(648, yy + 4, 566, 84, [
        P(R(f"Median absolute log error over {tr['n_parts']} PNs; the history estimate is closer for "
            f"{fmt_pct(tr['share_estimate_closer'], 0)} of them.", "small", s=8.5), after=5, ls=1.05),
        P(R(f"Intermittent rotables: the champion '{lab.get(ir['champion'], ir['champion'])}' ranked {ir['champion_rank']}/"
            f"{ir['n_methods']}, kept as frozen. Rotables are sized on the reliability-exposure rate (lower q90 pinball "
            f"in {n_q90} of {len(rvc)} classes), not on a MASE champion.", "bodym", s=9.1), ls=1.08)])
    s.footer(5, "Source: docs/data/forecast.json (champion_check, truth_recovery), parts.json · rolling origins, holdout",
             total)
    S.append(s)

    # 6 — Frontier option: I125 -------------------------------------------------------------------------------------
    i1 = N["pt"][fid]
    reco = N["reco"]
    rt = fo["repair_tat_x0_75"]
    shifts = {r["setting"]: r["recommended"] for r in fo["rule_shifts"]}
    pp = {r["variant"]: r for r in fo["postplan_stress"]}
    s = Slide(bg=bg)
    s.header(6, "The frontier option", f"If you invest an additional {cm['fo_cap']}: {fid} cuts a further "
             f"{cm['fo_red']} h/yr",
             f"{len(N['points'])} frozen candidate plans, re-run on the holdout. A rule stated before the holdout walks up "
             f"the hull while AED 1M still removes ≥ {reco['h_star_per_aed_1m']:.1f} AOG h/yr, and stops at {fid}. "
             f"It is an option for more capital, on top of {cid}.")
    s.card(48, 150, 700, 520)
    s.text(70, 166, 560, 16, P(R("CAPITAL VS MATERIAL AOG · HOLDOUT MEANS, 95% CI", "label", c=C["faint"])))
    s.chip_r(730, 164, "SIMULATED")
    s.image(58, 188, 680, 474, CH.frontier(680, 474))
    s.card(766, 150, 466, 232)
    s.text(788, 166, 420, 16, P(R(f"{fid} − {cid} · PAIRED · HOLDOUT", "label", c=C["ice"])))
    s.text(788, 186, 200, 56, [P(R(f"−{cm['fo_red']} h", "big", s=26, c=C["ice"])),
                               P(R(f"AOG / yr {cm['fo_red_ci']}", "monos", s=8))])
    s.text(1000, 186, 210, 56, [P(R(f"+{cm['fo_cap']}", "big", s=26, c=C["copper"])),
                                P(R("extra spare capital", "monos", s=8))])
    s.text(788, 262, 422, 134, [
        bullet([R("Total annual cost ", "body", s=9.5, b=True),
                R(f"{fmt_mm(fo['total_cost_aed']['mean'])}/yr {ci_m(fo['total_cost_aed']['ci'])} vs {cid}.", "bodym",
                  s=9.5)], after=5),
        bullet([R(f"{fid} itself: ", "body", s=9.5, b=True),
                R(f"{fmt_int(i1['aog_hours'])} AOG h/yr {ci_txt(i1['aog_ci'])} at {fmt_mm(i1['capital_aed'])} "
                  f"(selection seeds: {fmt_int(N['spt'][fid]['aog_hours'])} h).", "bodym", s=9.5)], after=5),
        P(R(f"h* = {fmt_pct(reco['carrying_pct'], 0)} × AED 1M ÷ AED {reco['aed_per_aog_hour']:,}/h = "
            f"{reco['h_star_per_aed_1m']:.2f} h per AED 1M", "monos", s=7.8, c=C["faint"]), ls=1.05),
    ])
    s.card(766, 394, 466, 276, line=blend(C["amber"], C["card"], 0.45))
    s.text(788, 410, 420, 16, P(R("SENSITIVITY: WHY IT IS AN OPTION, NOT THE HEADLINE", "label", c=C["amber"])))
    s.text(788, 432, 424, 234, [
        bullet([R("Hourly penalty: ", "body", s=9.3, b=True),
                R(f"the rule picks {shifts.get('x0.5', '?')} at ×0.5 and {shifts.get('x2.0', '?')} at ×2 (selection "
                  "seeds).", "bodym", s=9.3)], col=C["amber"], after=5),
        bullet([R("Repair 25% faster: ", "body", s=9.3, b=True),
                R(f"{fid}'s cost lead over {cid} is {fmt_signed(rt['net_benefit_aed']['mean'], fmt_mm)}/yr "
                  f"{ci_m(rt['net_benefit_aed']['ci'], 2)}, "
                  f"{'not significant' if not rt['net_benefit_significant'] else 'significant'} (selection seeds).",
                  "bodym", s=9.3)], col=C["amber"], after=8),
        P(R("POST-PLAN STRESS CHECK (D015, ADDED AFTER THE MAIN HOLDOUT)", "label", s=7.2, c=C["faint"]), after=4),
        P(R("Frozen central-built candidates, holdout seeds, paired vs the central-built P2, no re-selection:",
            "small", s=8.2), after=4, ls=1.05),
        *[P(R(f"{wname(v):<12}", "mono", s=8.6, c=C["titanium"]),
            R(f"{fmt_int(pp[v]['aog_hours']['mean'])} h {ci_txt(pp[v]['aog_hours']['ci'])} · cost "
              f"{fmt_mm(pp[v]['total_cost_aed']['mean'])} {ci_m(pp[v]['total_cost_aed']['ci'])}", "mono", s=8.4,
              c=C["ice"]), after=2) for v in ("low_stress", "high_stress") if v in pp],
    ])
    s.footer(6, f"Source: docs/data/kpis.json (headline.frontier_option), frontier.json · {N['seed_txt']} unless labelled",
             total)
    S.append(s)

    # 7 — What it depends on ----------------------------------------------------------------------------------------
    V = N["variants"]
    desk = N["desk"]
    ro = hon["routes_off"]
    ach, tg = N["cal_ach"], N["cal_targets"]
    lev = N["pt"].get("LEV_TAT10_TOP6")
    s = Slide(bg=bg)
    s.header(7, "What the result depends on", "An AOG-route market, the world you are in, and the penalty you assume",
             f"One-at-a-time sensitivity of the frontier option, the three calibrated worlds, and the structural stress the "
             f"whole result rests on: the AOG desk's recovery routes.")
    s.card(48, 150, 740, 256)
    s.text(70, 166, 640, 16, P(R(f"TORNADO · {fid} − {cid} NET BENEFIT · ONE AT A TIME · SELECTION SEEDS", "label",
                                 c=C["faint"])))
    s.chip_r(770, 164, "SIMULATED")
    s.image(58, 186, 720, 214, CH.tornado(720, 214))
    s.card(806, 150, 426, 256)
    s.text(828, 166, 380, 16, P(R("BUY 1 SPARE VS CUT REPAIR TAT 10 DAYS", "label", c=C["faint"])))
    s.chip_r(1214, 164, "DERIVED")
    s.text(828, 188, 170, 66, [P(R(str(N["buy_wins"]), "big", s=28)), P(R("PNs where buying is cheaper", "small", s=8.3))])
    s.text(1010, 188, 200, 66, [P(R(str(N["tat_wins"]), "big", s=28, c=C["copper"])),
                                P(R("PNs where a TAT cut is cheaper", "small", s=8.3))])
    s.text(828, 266, 384, 136, [
        P(R(f"Median annual cost per AOG h avoided: buy {fmt_aed(N['buy_med'])}, TAT cut {fmt_aed(N['tat_med'])}.",
            "bodym", s=9.3), after=5, ls=1.1),
        P(R(f"Simulated: cutting TAT on the top 6 PNs gives {fmt_int(lev['aog_hours'])} AOG h/yr at "
            f"{fmt_mm(lev['capital_aed'])} (holdout), close to {cid}'s {fmt_int(N['pt'][cid]['aog_hours'])} h."
            if lev else "", "bodym", s=9.3), after=5, ls=1.1),
        P(R(N["lever_ex"], "small", s=8.3), ls=1.08),
    ])
    s.card(48, 418, 740, 252)
    s.text(70, 434, 640, 16, P(R("THREE CALIBRATED WORLDS · ONLY THE TRUE RELIABILITY DIFFERS", "label", c=C["faint"])))
    s.chip_r(770, 432, "SIMULATED")
    hdr = ["World", "P0 history fill · AOG", f"{cid} − P0 AOG h (holdout)", f"{fid} − {cid} net /yr (selection)"]
    cx = [70, 178, 368, 572]
    for c_, h_ in zip(cx, hdr):
        s.text(c_, 458, 210, 14, P(R(h_.upper(), "label", s=7, c=C["faint"])))
    yy = 478
    wmap = {w["variant"]: w for w in core["worlds"]}
    for v in ("low_stress", "central", "high_stress"):
        a_ = ach[v]
        rv_ = V[v]["rec_vs_P2"]
        vals = [(wname(v), "body", C["ice"]),
                (f"{fmt_pct(a_['rotable_immediate_fill_rate'])} · {fmt_int(a_['aog_hours_per_year'])} h", "mono", C["ice"]),
                (f"{fmt_int(wmap[v]['aog_hours']['mean'])} {ci_txt(wmap[v]['aog_hours']['ci'])}", "mono", C["aero_teal"]),
                (f"{fmt_signed(rv_['net_benefit_aed'], fmt_mm)} {ci_m(rv_['net_benefit_ci'], 2)}", "mono",
                 C["aero_teal"] if rv_["net_benefit_ci"][0] > 0 else C["amber"])]
        for c_, (t, sty, col) in zip(cx, vals):
            s.text(c_, yy, 210, 18, P(R(t, sty, s=9, c=col)))
        s.line(70, yy + 22, 766, yy + 22, HAIR, 0.5)
        yy += 28
    s.text(70, yy + 6, 696, 90, [
        P(R(f"Calibration band for P0 (set before any policy result): rotable fill "
            f"{tg['rotable_immediate_fill_rate'][0]:.2f}–{tg['rotable_immediate_fill_rate'][1]:.2f}, AOG "
            f"{fmt_int(tg['aog_hours_per_year'][0])}–{fmt_int(tg['aog_hours_per_year'][1])} h/yr. The stress worlds sit at "
            f"its ends as far as they could: low stress reaches the AOG end, high stress the fill end (at "
            f"{fmt_int(ach['high_stress']['aog_hours_per_year'])} h, short of {fmt_int(tg['aog_hours_per_year'][1])}).",
            "bodym", s=8.9), after=4, ls=1.08),
        P(R(f"In low stress {fid}'s net benefit over {cid} is marginal (its CI lower end is "
            f"{fmt_aed(V['low_stress']['rec_vs_P2']['net_benefit_ci'][0])})."
            if V["low_stress"]["rec_vs_P2"]["net_benefit_ci"][0] < 0.1e6 else
            f"{fid}'s net benefit over {cid} stays positive in every world shown.", "bodym", s=8.9,
            c=C["amber"]), ls=1.08),
    ])
    s.card(806, 418, 426, 252, line=blend(C["red"], C["card"], 0.45))
    s.text(828, 434, 380, 16, P(R("THE BIG CONDITION: AOG RECOVERY ROUTES", "label", c=C["red"])))
    s.text(828, 456, 384, 210, [
        P(R("Every policy, P0 included, leans on the AOG desk: robbery at AUH (engineering/quality approval required), "
            "local borrow, exchange/loan and local buy. Switch the routes off (selection seeds):", "bodym", s=8.9),
          after=7, ls=1.08),
        P(R(f"{bid}    ", "mono", s=9.3, c=C["copper"]),
          R(f"{fmt_int(ro['central_p0_aog_hours'])} → {fmt_int(ro['p0_aog_hours'])} h/yr", "mono", s=9.3), after=3),
        P(R(f"{cid}    ", "mono", s=9.3, c=C["aero_teal"]),
          R(f"{fmt_int(ro['central_p2_aog_hours'])} → {fmt_int(ro['p2_aog_hours'])} h/yr", "mono", s=9.3), after=3),
        P(R(f"{fid}  ", "mono", s=9.3, c=C["ice"]),
          R(f"{fmt_int(desk['central_rec_aog_hours'])} → {fmt_int(ro['rec_aog_hours'])} h/yr", "mono", s=9.3), after=7),
        P(R(("The ranking survives, the scale does not: " if ro["p0_aog_hours"] > ro["p2_aog_hours"] > ro["rec_aog_hours"]
             else "") + "the results are conditional on those markets existing at the assumed availability.", "body",
            s=8.9), ls=1.08),
    ])
    s.footer(7, "Source: docs/data/frontier.json, kpis.json (headline), outputs/freeze/calibration_lock.json · splits "
                "as labelled", total)
    S.append(s)

    # 8 — Planner actions & AOG lab --------------------------------------------------------------------------------
    ac = N["act_counts"]
    cfs = N["aog_sum"]["counterfactual"]
    s = Slide(bg=bg)
    s.header(8, "Planner actions & AOG lab", f"What the planner does on Monday: {N['n_actions']} exceptions, "
             f"{ac['by_severity']['urgent']} urgent",
             f"The action centre turns the plan into a week-{N['act_week']} inbox with evidence and an owner. The AOG lab "
             "replays every history grounding and ranks the desk's options on what was known at the time.")
    s.card(48, 150, 560, 520)
    s.text(70, 166, 420, 16, P(R(f"EXCEPTIONS BY TYPE · WEEK {N['act_week']}", "label", c=C["faint"])))
    s.chip_r(590, 164, "DERIVED")
    s.image(58, 188, 540, 260, CH.actions(540, 260))
    xx = 70
    for sev, col in [("urgent", C["red"]), ("review", C["amber"]), ("info", C["slate"])]:
        s.rect(xx, 462, 10, 10, fill=col, r=2)
        s.text(xx + 16, 458, 120, 18, P(R(f"{sev} {ac['by_severity'].get(sev, 0)}", "monos", s=8.5)))
        xx += 120
    acts = N["actions"]
    a1 = ([a for a in acts if a["pn"] == inc["pn"] and a["station"] == inc["station"]] or acts)[0]
    a2 = ([a for a in acts if a["severity"] == "urgent" and a["type"] != a1["type"]] or acts)[0]
    s.text(70, 488, 516, 178, [
        P(R("EXAMPLES FROM THE INBOX", "label", c=C["faint"]), after=4),
        P(R(f"{a1['severity'].upper()} · {a1['owner']} · ", "monos", s=7.8, c=C["red"]), R(a1["summary"], "body", s=9),
          ls=1.05, after=1),
        P(R(f"→ {a1['recommended_action']}", "bodym", s=8.6), ls=1.05, after=6),
        P(R(f"{a2['severity'].upper()} · {a2['owner']} · ", "monos", s=7.8, c=C["red"]), R(a2["summary"], "body", s=9),
          ls=1.05, after=1),
        P(R(f"→ {a2['recommended_action']}", "bodym", s=8.6), ls=1.05)])
    s.card(626, 150, 606, 330)
    s.text(648, 166, 520, 16, P(R(f"{inc['id']} · THE DESK'S OPTIONS, RANKED EX ANTE", "label", c=C["faint"])))
    s.chip_r(1214, 164, "SIMULATED")
    hd = [("Option", 648), ("Wait", 960), ("AOG", 1020), ("Direct cost", 1078), ("Rank", 1170)]
    for h_, x_ in hd:
        s.text(x_, 190, 120, 14, P(R(h_.upper(), "label", s=7.2, c=C["faint"])))
    yy = 208
    opts = sorted(inc["options"], key=lambda o: (o["rank"] is None, o["rank"] or 99, not o["feasible"]))
    for o in opts:
        feas = o["feasible"]
        col = C["ice"] if feas else C["faint"]
        if o["rank"] == 1:
            s.rect(640, yy - 4, 584, 23, fill=blend(C["aero_teal"], C["card"], 0.14), r=4)
        nm = o["option"].replace(" (human decision)", "")
        s.text(648, yy, 310, 18, P(R(nm, "body", s=8.7, c=col)))
        s.text(960, yy, 60, 18, P(R(f"{o['wait_h']:g} h" if o["wait_h"] is not None else "—", "mono", s=8.5, c=col)))
        s.text(1020, yy, 58, 18, P(R(f"{o['aog_h']:g} h" if o["aog_h"] is not None else "—", "mono", s=8.5, c=col)))
        s.text(1078, yy, 92, 18, P(R(f"AED {o['direct_cost']:,}" if feas else "—", "mono", s=8.5, c=col)))
        s.text(1170, yy, 56, 18, P(R(str(o["rank"]) if o["rank"] else ("human" if o["human_decision"] else "—"),
                                     "mono", s=8.5, c=C["amber"] if o["human_decision"] else col)))
        yy += 25
    s.card(626, 492, 606, 178)
    s.text(648, 508, 560, 16, P(R("ACROSS ALL HISTORY GROUNDINGS · AN HONEST NEGATIVE", "label", c=C["amber"])))
    ex = cfs["excluding_history_robbery"]
    s.text(648, 530, 180, 60, [P(R(f"{cfs['history_took_best_option']}/{cfs['requests_compared']}", "mid", s=15)),
                               P(R("requests where history already took the top-ranked option", "small", s=8), ls=1.05)])
    s.text(838, 530, 190, 60, [P(R(f"{fmt_int(cfs['actual_request_aog_h'])} vs {fmt_int(cfs['best_option_request_aog_h'])} h",
                                   "mid", s=15, c=C["titanium"])),
                               P(R("actual vs top-ranked option (request-level AOG h)", "small", s=8), ls=1.05)])
    s.text(1038, 530, 180, 60, [P(R(f"{fmt_int(ex['actual_request_aog_h'])} vs {fmt_int(ex['best_option_request_aog_h'])} h",
                                    "mid", s=15, c=C["titanium"])),
                                P(R(f"same, without the {cfs['history_used_robbery']} robbery cases", "small", s=8),
                                  ls=1.05)])
    s.text(648, 600, 566, 66, P(R(f"History did better, driven by {cfs['history_used_robbery']} robberies the lab never ranks "
                                  "(they need engineering/quality approval). The per-incident response is already near the "
                                  "best route; the lever is positioning, before the removal happens.", "bodym", s=9.1),
                                ls=1.1))
    s.footer(8, "Source: docs/data/actions.json, aog_lab.json · simulated history weeks 0–103", total)
    S.append(s)

    # 9 — How it was protected -------------------------------------------------------------------------------------
    pc = N["prov_counts"]
    val = N["validation"]
    cons = N["consistency"]
    n_in = sum(1 for c in cons.values() if c["selection_inside_holdout_ci"])
    cal = {t["metric"]: t for t in N["cal"]["targets_vs_achieved"]}
    v1 = N["v1"]
    s = Slide(bg=bg)
    s.header(9, "How the result was protected", "Calibrated first, frozen, then tested once on unseen seeds",
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
        bullet([R(f"ASSUMED: fleet ({N['nb']} narrowbody + {N['wb']} widebody archetypes), costs, penalties, AOG-route odds.",
                  "bodym", s=9.2)], col=PROV_COLOR["ASSUMED"], after=6),
        bullet([R(f"SIMULATED: {N['n_weeks']} weeks of history, {fmt_int(N['requests_hist'])} material requests, "
                  f"policy runs on paired seeds.", "bodym", s=9.2)], col=PROV_COLOR["SIMULATED"], after=6),
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
                                 "simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions.", "small", s=8.2), ls=1.08))
    s.card(446, 150, 400, 520)
    s.text(468, 166, 360, 16, P(R("CALIBRATE → FREEZE → ONE HOLDOUT", "label", c=C["aero_teal"])))
    steps = [
        ("1 · Calibrate P0 only", f"before any P1/P2 run: rotable fill {cal['rotable_immediate_fill_rate']['achieved']:.3f}, "
                                 f"AOG {fmt_int(cal['aog_hours_per_year']['achieved'])} h/yr, "
                                 f"{fmt_int(cal['aog_events_per_year']['achieved'])} events/yr, all inside the band."),
        ("2 · Select on selection seeds", f"champions, policy tables and {len(N['points'])} frontier candidates; the "
                                         "stopping rule written down first."),
        ("3 · Freeze", f"{len(N['freeze']['artefacts'])} artefacts hashed (SHA-256) before the holdout."),
        ("4 · One holdout", f"seeds {N['seeds'][0]}–{N['seeds'][-1]}, never used before. The D015 stress check was added "
                            "after it and is labelled post-plan."),
    ]
    yy = 192
    for h_, d_ in steps:
        s.text(468, yy, 360, 70, [P(R(h_, "body", s=9.6, b=True), after=2), P(R(d_, "bodym", s=9), ls=1.08)])
        yy += 70
    s.line(468, yy + 2, 824, yy + 2, HAIR, 0.5)
    s.text(468, yy + 12, 170, 60, [P(R(f"{n_in} of {len(cons)}", "mid", s=18, c=C["aero_teal"])),
                                   P(R("headline KPIs: selection value inside the holdout CI", "small", s=8), ls=1.05)])
    s.text(656, yy + 12, 172, 60, [P(R(f"{val['tests_passed']}/{val['tests_total']}", "mid", s=18, c=C["aero_teal"])),
                                   P(R("tests passed, incl. reconciliation of site numbers", "small", s=8), ls=1.05)])
    s.text(468, yy + 78, 360, 40, P(R(f"Selection → holdout AOG h/yr: {cid} {fmt_int(cons['aog_hours']['selection_recommended'])}"
                                      f" → {fmt_int(cons['aog_hours']['holdout_recommended'])}, {fid} "
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
        P(R("v2 fixed them as domain corrections chosen before any v2 result, recalibrated P0 only, and ran its holdout "
            "on fresh seeds. v1 numbers are not findings.", "bodym", s=9.2), after=8, ls=1.08),
        P(R("Lesson: get the domain review before the headline, not after.", "body", s=9.4, c=C["amber"]), ls=1.08),
    ])
    s.footer(9, f"Source: docs/data/method.json (assumptions, calibration, freeze, validation, v1_archive), kpis.json · "
                f"data build {N['meta_sha']}", total)
    S.append(s)

    # 10 — Limitations & author -------------------------------------------------------------------------------------
    s = Slide(bg=bg)
    s.header(10, "Limitations & author", "What this shows, and what it does not",
             "A simulation of a fictional airline, built to be checked. The limits below matter most; all of them are "
             "listed in LIMITATIONS.md and on the app's Data & Method page.")
    s.card(48, 150, 760, 520, line=blend(C["amber"], C["card"], 0.4))
    s.text(70, 166, 600, 16, P(R("LIMITATIONS THAT MATTER MOST", "label", c=C["amber"])))
    lim = [
        ("Synthetic data, not a dispatch tool.", "Every airline number is simulated on a world the author designed; "
                                                "not an approved maintenance, airworthiness or dispatch tool."),
        ("AOG-route dependence.", f"With the recovery routes off, AOG rises to {fmt_int(ro['p0_aog_hours'])} h/yr for P0, "
                                  f"{fmt_int(ro['p2_aog_hours'])} for P2 and {fmt_int(ro['rec_aog_hours'])} for {fid} "
                                  f"(selection seeds; {fmt_int(ro['central_p0_aog_hours'])} / "
                                  f"{fmt_int(ro['central_p2_aog_hours'])} / {fmt_int(desk['central_rec_aog_hours'])} with "
                                  "them)."),
        ("Deadline classes.", "D3/D10 are simplified analogues of MEL repair-interval categories B and C, not operator "
                              "MEL decisions."),
        ("The penalty is a scenario.", "Hourly downtime rates and the fixed per-event cost are assumptions; the "
                                       "recommended frontier point moves with them."),
        ("Brakes.", "Cost-per-landing contracts are not modelled. Brake changes are planned at notice; residual brake "
                    "downtime only occurs when AUH is short and the exchange fails."),
        ("Robbed-donor hours.", "Robbery needs engineering/quality approval. A robbed donor is assumed grounded until "
                                "reinstated, but those hours are not counted, so absolute downtime is understated."),
        ("Optimiser.", "Greedy additions on an analytic proxy with guardrails, then re-simulated; not a proven optimum."),
        ("Legacy baseline.", "Most of P0's few outstation rotables are brakes changed only at AUH, so the P2 gap largely "
                             "measures stocking no-go items at line stations (LIMITATIONS 29–39)."),
    ]
    half = (len(lim) + 1) // 2
    for col_i, chunk in enumerate((lim[:half], lim[half:])):
        s.text(70 + col_i * 366, 192, 344, 330, [P(R(t + " ", "body", s=9.5, b=True), R(d_, "bodym", s=9.2), after=9,
                                                   ls=1.1) for t, d_ in chunk])
    s.line(70, 474, 786, 474, HAIR, 0.6)
    s.text(70, 486, 700, 16, P(R("THE HONEST FINDINGS, IN ONE PLACE", "label", c=C["faint"])))
    tr = N["truth"]["MTBUR (rotables + expendables)"]
    hs_ = [(f"{hon['forecast_champions_best']}/{hon['forecast_cells']}",
            f"cells where the frozen forecast champion was best on the holdout (SBA "
            f"{hon['sba_intermittent_rotables_rank']}th of {hon['sba_intermittent_rotables_n_methods']} for intermittent "
            "rotables)"),
           (f"{hon['mtbur_history_error'] * 100:.0f}% vs {hon['mtbur_quote_error'] * 100:.0f}%",
            "MTBUR error: estimated from history vs vendor quote"),
           (f"−{cm['fill']} pts", f"immediate fill, {cid} vs {bid} (consumables and expendables)"),
           (f"{fmt_int(ro['central_p2_aog_hours'])}→{fmt_int(ro['p2_aog_hours'])} h",
            f"{cid} material AOG/yr with the AOG routes switched off")]
    for i, (big_, txt_) in enumerate(hs_):
        x_ = 70 + i * 180
        s.text(x_, 508, 170, 34, P(R(big_, "mid", s=17, c=C["amber"] if i else C["aero_teal"])))
        s.text(x_, 542, 166, 100, P(R(txt_, "bodym", s=8.8), ls=1.1))
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
    s.footer(10, f"Source: docs/data/frontier.json, kpis.json (honest), method.json · data build {N['meta_sha']}", total)
    S.append(s)

    notes = [
        "Title. Headline: P2 vs P0 on the v2 holdout (seeds 2000-2019, central world, paired). I125 is the frontier "
        "option for additional capital. Everything is simulated for a fictional airline.",
        "The problem: one incident (AOG-0001), then the pattern behind it.",
        "The core finding: P2 network positioning vs the legacy OEM-quote policy, with worlds, penalty range and the fill price.",
        "Palm: station stock covers removals over the AUH resupply time. The BOM figure is computed here from the exported Poisson distribution and checked "
        "against the exporter.",
        "Forecasting honesty: champions best in few cells; MTBUR from history beats vendor quotes.",
        "Frontier option I125: additional capital, its paired gain, its sensitivity, and the post-plan stress check (D015).",
        "What it depends on: tornado (one at a time), the three worlds and the calibration band ends, AOG-route dependence.",
        "Planner actions and the AOG lab (an honest negative: history already near the best route).",
        "Provenance, calibrate-freeze-holdout, selection-to-holdout consistency, and the v1 to v2 correction.",
        "Limitations and author.",
    ]
    for s_, n_ in zip(S, notes):
        s_.notes = n_
    return S


# --------------------------------------------------------------------------------------------------------------------
# Carousel (1080 × 1080, PDF only) — DRAFT
# --------------------------------------------------------------------------------------------------------------------
def build_carousel(N, A, CH, bg):
    S = []
    k, core, fo, hon = N["kpi"], N["core"], N["fo"], N["hon"]
    cid, bid, fid = N["core_id"], N["base_id"], N["fo_id"]
    aogk = k["aog_hours"]
    cm = common(N)
    inc = N["inc"]
    sv = N["sv"]
    total = 7

    def frame(s, n, eyebrow):
        s.text(72, 64, 800, 22, P(R(f"{n:02d} / {total:02d} · {eyebrow.upper()}", "eyebrow", s=13)))
        s.text(808, 64, 200, 22, P(R("DRAFT", "label", s=11, c=C["amber"], b=True), al="r"))
        s.line(72, 1000, 1008, 1000, HAIR_BG, 1)
        s.text(72, 1012, 760, 22, P(R(f"GROUNDED NO MORE · {AIRLINE} · simulated data", "small", s=10.5)))
        s.text(808, 1012, 200, 22, P(R("swipe →" if n < total else "", "label", s=10.5, c=C["aero_teal"]), al="r"))

    # 1 — hook
    s = Slide(1080, 1080, bg)
    frame(s, 1, "case study")
    s.text(72, 120, 936, 200, [P(R("A single missing part", "title", s=52, sp=-1)),
                               P(R("can ground an aircraft.", "title", s=52, sp=-1, c=C["aero_teal"]))])
    s.text(72, 296, 936, 90, P(R("I simulated a fictional airline to learn where spares should sit, and what each extra "
                                 "dirham of stock actually buys.", "lede", s=20, c=C["ice"]), ls=1.12))
    s.image(60, 400, 470, 520, A["nb"])
    s.image(540, 380, 490, 545, A["wb"])
    s.chip(72, 940, "SIMULATED", f"SIMULATED · {AIRLINE.upper()} · ORIGINAL SCHEMATICS")
    S.append(s)

    # 2 — the core finding
    s = Slide(1080, 1080, bg)
    frame(s, 2, "the core finding")
    s.text(72, 120, 936, 70, P(R("A re-mixed float, not a bigger one.", "title", s=40, sp=-0.5)))
    s.text(72, 200, 936, 150, P(R(f"Against {N['base_label']}, positioning the network ({cm['out2']} outstation units) "
                                  f"cuts material AOG by {cm['red']} hours a year {cm['red_ci']}. {cm['remix']}",
                                  "lede", s=19.5, c=C["ice"]), ls=1.12))
    s.text(72, 376, 936, 24, P(R("MATERIAL AOG H / YEAR · SPARE CAPITAL · HOLDOUT, 20 PAIRED SEEDS", "label", s=11,
                                 c=C["faint"])))
    s.image(72, 406, 936, 452, CH.kpi_bars(600, 300))
    s.text(72, 870, 936, 120, [
        bullet([R(f"Holds in all {len(core['worlds'])} simulated worlds and across ×0.5–×2 the hourly downtime penalty.",
                  "bodym", s=17)], after=10, ls=1.12),
        bullet([R(f"The price: immediate fill is {cm['fill']} pts lower, in consumables and expendables.", "bodym",
                  s=17)], col=C["amber"], ls=1.12),
    ])
    S.append(s)

    # 3 — why
    s = Slide(1080, 1080, bg)
    frame(s, 3, "why it works")
    s.text(72, 120, 936, 150, P(R(f"At {inc['station']}, the legacy rule held {sv['units']['P0']} of the part that "
                                  f"grounded the aircraft.", "title", s=40, sp=-0.5), ls=1.1))
    s.text(72, 290, 936, 110, P(R(f"The shelf at {inc['station']} is refilled from AUH in a few days. Palm's theorem says how "
                                  f"many removals that resupply time has to cover. With {N['s_bom']} units at {inc['station']}, {fmt_pct(N['palm_bom'], 0)} of "
                                  f"no-go removals find one on the shelf instead of waiting for the next flight in.",
                                  "lede", s=19), ls=1.15))
    s.image(72, 420, 936, 380, CH.palm_pmf(620, 252, big=True))
    s.text(72, 830, 440, 140, [P(R(f"{inc['aog_hours']} h", "big", s=54, c=C["copper"])),
                               P(R(f"on the ground in {inc['id']}, one D0 removal", "bodym", s=16))])
    s.text(540, 830, 470, 140, [P(R(fmt_pct(N["palm_bom"], 0), "big", s=54, c=C["aero_teal"])),
                                P(R(f"immediate fill with {N['s_bom']} units at {inc['station']}", "bodym", s=16))])
    S.append(s)

    # 4 — frontier option
    shifts = {r["setting"]: r["recommended"] for r in fo["rule_shifts"]}
    rt = fo["repair_tat_x0_75"]
    s = Slide(1080, 1080, bg)
    frame(s, 4, "the frontier option")
    s.text(72, 120, 936, 70, P(R(f"If you invest an additional {cm['fo_cap']}…", "title", s=38, sp=-0.5)))
    s.text(72, 196, 936, 110, P(R(f"…a rule written before the test stops at {fid}: a further {cm['fo_red']} AOG hours a "
                                  f"year {cm['fo_red_ci']} below {cid}. An option, not the headline.", "lede", s=20),
                                ls=1.15))
    s.image(72, 300, 936, 500, CH.frontier(580, 310, compact=True))
    s.text(72, 820, 936, 160, [
        bullet([R(f"The pick moves with the penalty: {shifts.get('x0.5')} at ×0.5, {shifts.get('x2.0')} at ×2.", "bodym",
                  s=17)], col=C["amber"], after=8, ls=1.12),
        bullet([R(f"If repair is 25% faster, its cost lead over {cid} is "
                  f"{'not significant' if not rt['net_benefit_significant'] else 'still significant'}.", "bodym", s=17)],
               col=C["amber"], after=8, ls=1.12),
        bullet([R("A stress check I added after the holdout (labelled post-plan) "
                  + ("still shows it ahead in both stress worlds." if all(r["aog_hours"]["ci"][1] < 0
                                                                          for r in fo["postplan_stress"])
                     else "does not show it ahead in every stress world."), "bodym", s=17)], ls=1.12),
    ])
    S.append(s)

    # 5 — honest findings
    tr = N["truth"]["MTBUR (rotables + expendables)"]
    ro = hon["routes_off"]
    s = Slide(1080, 1080, bg)
    frame(s, 5, "what surprised me")
    s.text(72, 120, 936, 130, P(R("Four things I did not expect.", "title", s=44, sp=-0.5)))
    items = [
        (f"{hon['forecast_champions_best']} of {hon['forecast_cells']}",
         "forecasting cells where the frozen champion was also best on unseen data. For intermittent rotables, SBA "
         f"came {hon['sba_intermittent_rotables_rank']}th of {hon['sba_intermittent_rotables_n_methods']}."),
        (f"{hon['mtbur_history_error'] * 100:.0f}% vs {hon['mtbur_quote_error'] * 100:.0f}%",
         "how far MTBUR estimated from the airline's own history sits from the truth, versus vendor quotes."),
        (f"−{cm['fill']} pts", "immediate fill under the better network plans. Fewer groundings, slightly more waiting "
                               "for cheap parts."),
        (f"{fmt_int(ro['central_p2_aog_hours'])} → {fmt_int(ro['p2_aog_hours'])} h",
         "P2's material AOG a year if the AOG desk's recovery routes (borrow, exchange, robbery) disappear."),
    ]
    yy = 250
    for big_, txt in items:
        s.text(72, yy, 370, 80, P(R(big_, "big", s=34, c=C["aero_teal"])))
        s.text(450, yy + 6, 558, 150, P(R(txt, "bodym", s=18), ls=1.15))
        s.line(72, yy + 160, 1008, yy + 160, HAIR_BG, 0.75)
        yy += 180
    S.append(s)

    # 6 — v1 -> v2
    v1 = N["v1"]
    cons = N["consistency"]
    n_in = sum(1 for c in cons.values() if c["selection_inside_holdout_ci"])
    s = Slide(1080, 1080, bg)
    frame(s, 6, "I got it wrong first")
    s.text(72, 120, 936, 150, P(R("My first version flattered the result.", "title", s=44, sp=-0.5), ls=1.05))
    s.text(72, 296, 936, 160, P(R(f"A domain review of v1 found {len(v1['superseded_because'])} realism problems: parts "
                                  "shared across fleet types, cheap consumables treated as no-go items, an always-available "
                                  "5-day emergency buy, a straw-man baseline. So I archived v1 and rebuilt the world.",
                                  "lede", s=20, c=C["ice"]), ls=1.15))
    steps = [
        ("Fix", "the domain errors first, before looking at any new result"),
        ("Calibrate", "only the legacy baseline, to a band agreed in advance"),
        ("Freeze", f"{len(N['freeze']['artefacts'])} artefacts, hashed"),
        ("Test once", f"on fresh seeds: {n_in} of {len(cons)} headline numbers landed inside the holdout interval"),
    ]
    yy = 500
    for i, (h_, d_) in enumerate(steps, 1):
        s.rect(72, yy, 52, 52, fill=blend(C["aero_teal"], C["midnight"], 0.15), line=C["aero_teal"], lw=1, r=26)
        s.text(72, yy + 12, 52, 30, P(R(str(i), "mid", s=18, c=C["aero_teal"]), al="c"))
        s.text(146, yy + 2, 862, 80, P(R(h_ + "  ", "body", s=19, b=True), R(d_, "bodym", s=18), ls=1.12))
        yy += 92
    s.text(72, 884, 936, 100, P(R("The v1 numbers are archived, not findings. The lesson: get the domain review before "
                                  "the headline.", "body", s=18, c=C["amber"]), ls=1.15))
    S.append(s)

    # 7 — limits + author
    s = Slide(1080, 1080, bg)
    frame(s, 7, "honest limits")
    s.text(72, 120, 936, 150, P(R("It is a simulation. Here is what that means.", "title", s=40, sp=-0.5), ls=1.1))
    lim = [
        f"{AIRLINE} does not exist; every airline number is simulated.",
        "Results lean on AOG recovery routes (borrow, exchange/loan, robbery with engineering approval) existing.",
        "D0/D3/D10 are hypothetical rectification windows; D3/D10 are simplified analogues of MEL repair-interval categories B and C, not operator MEL decisions.",
        f"{N['validation']['tests_passed']} tests, frozen artefacts and a disclosed holdout log keep it honest inside "
        "that world.",
    ]
    s.text(72, 280, 936, 460, [bullet([R(t, "bodym", s=19)], after=16, ls=1.15) for t in lim])
    s.card(72, 760, 936, 210)
    s.text(104, 784, 880, 170, [P(R("Akash Gajjar", "title", s=28), after=4),
                                P(R("MSc Supply Chain Management, University of Liverpool (2025)", "bodym", s=15),
                                    after=14),
                                P(R(LIVE_URL.replace("https://", ""), "mono", s=14, c=C["aero_teal"]), after=4),
                                P(R(REPO_URL.replace("https://", ""), "mono", s=14))])
    S.append(s)
    return S


def write_linkedin_post(N, path):
    """DRAFT post in the author's voice. Numbers are filled from docs/data; nothing is posted anywhere."""
    core, fo, hon = N["core"], N["fo"], N["hon"]
    cm = common(N)
    inc = N["inc"]
    sv = N["sv"]
    ro = hon["routes_off"]
    shifts = {r["setting"]: r["recommended"] for r in fo["rule_shifts"]}
    v1h = {r["policy"]: r for r in N["v1"]["headline"]}
    v1_gap = v1h["P0"]["aog_hours"] - v1h["P2"]["aog_hours"]
    smaller = ("The improvement is smaller now, and I trust it more." if v1_gap > core["aog_reduction"]["mean"]
               else "I trust the result more now.")
    txt = f"""<!--
DRAFT. DO NOT POST. Generated by scripts/build_deck.py from docs/data (data build {N['meta_sha']}).
Akash: edit freely, check every number against the live app before posting, and post it yourself.
Suggested attachment: presentations/linkedin_carousel.pdf (DRAFT) or docs/assets/readme/demo.gif.
-->

# DRAFT — DO NOT POST — LinkedIn post (not posted)

I have been teaching myself how aviation spare parts really work, and I built a project to do it.

My background is retail inventory: forecasts, reorder points, shelves that should never be empty. Aviation materials planning looks similar until you meet a rotable. A steering actuator is not consumed, it is repaired, so the question is not "how many do we sell?" but "how many are sitting in a repair shop right now, and is one where the aircraft is?"

GROUNDED NO MORE is a simulation of a fictional airline, {AIRLINE}, with a Gulf hub, {N['n_stations'] - 1} outstations, {N['nb'] + N['wb']} aircraft and {N['n_parts']} part numbers. To be clear up front: nothing in it is real operator data. The airline does not exist, the history is simulated, and every assumption is written down with a provenance tag.

What I found, on simulated futures the model had never seen:

1. Which rotables you hold, and where, matters. Against {N['base_label']}, positioning the network ({cm['out2']} outstation units) cut material AOG by {cm['red']} hours a year {cm['red_ci']}. It is not a free repositioning: {cm['remix'][0].lower() + cm['remix'][1:] if cm['remix'] else ''} It held in all {len(core['worlds'])} simulated worlds and across half to double the assumed downtime cost.

2. One missing part is enough. In the simulated history, a nose wheel steering actuator is removed at {inc['station']}, the legacy rule holds {sv['units']['P0']} there, and the aircraft is on the ground for {inc['aog_hours']} hours. With {N['s_bom']} units at {inc['station']}, Palm's theorem says {fmt_pct(N['palm_bom'], 0)} of those removals find one on the shelf.

3. More capital is an option, not the answer. If you invest an additional {cm['fo_cap']}, a stopping rule I wrote down before testing picks a plan that cuts a further {cm['fo_red']} hours a year. But the pick moves with the downtime cost ({shifts.get('x0.5')} at half, {shifts.get('x2.0')} at double), and its cost advantage is not significant if repairs get 25% faster.

4. The honest bits. Frozen forecasting champions were best on unseen data in only {hon['forecast_champions_best']} of {hon['forecast_cells']} cells. Reliability estimated from the airline's own history was about {hon['mtbur_history_error'] * 100:.0f}% off the truth, vendor quotes about {hon['mtbur_quote_error'] * 100:.0f}%. The better plans have about {cm['fill']} points lower immediate fill. And everything leans on the AOG desk's recovery routes: switch them off and the network plan goes from {fmt_int(ro['central_p2_aog_hours'])} to {fmt_int(ro['p2_aog_hours'])} hours a year.

5. I got it wrong first. A domain review of my first version found realism problems (parts shared across fleet types, cheap consumables treated as no-go items, an emergency buy that was always available) that flattered the result. I archived it, fixed the world before looking at new results, recalibrated only the baseline, and tested once on fresh seeds. {smaller}

It ends in a web app a materials planner could open on a Monday morning: a ranked action list, an AOG response lab and the capital-vs-readiness trade-off.

I would really value feedback from people who do this for real, especially on what I have oversimplified.

Live app: {LIVE_URL}
Code: {REPO_URL}

#AviationMaintenance #SupplyChain #InventoryManagement
"""
    path.write_text(txt)
    return path


# --------------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["deck", "carousel"], default=None)
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
        render_pptx(slides, OUT / "case_study_deck.pptx")
        pngs = html_to_pdf_and_png(render_html(slides, 1280, 720), 1280, 720, OUT / "case_study_deck.pdf", build, "deck")
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        shutil.copy(OUT / "case_study_deck.pdf", DOWNLOADS / "case_study_deck.pdf")
        print(f"deck: {OUT / 'case_study_deck.pptx'} + .pdf ({len(slides)} slides; copied to {DOWNLOADS}); "
              f"previews {pngs[0].parent}")
    if a.only in (None, "carousel"):
        bgc = str(make_background(build / "bg-sq.png", 1080, 1080))
        cs = build_carousel(N, A, CH, bgc)
        html_to_pdf_and_png(render_html(cs, 1080, 1080), 1080, 1080, OUT / "linkedin_carousel.pdf", build,
                            "carousel", scale=1)
        print(f"carousel (DRAFT): {OUT / 'linkedin_carousel.pdf'} ({len(cs)} slides)")
        print(f"post draft: {write_linkedin_post(N, OUT / 'linkedin_post.md')}")


if __name__ == "__main__":
    main()
