#!/usr/bin/env python3
"""Build the GROUNDED NO MORE case-study deck (PPTX + PDF) and the LinkedIn carousel (PDF).

    python scripts/build_deck.py                      # deck + carousel
    python scripts/build_deck.py --only deck          # just the deck
    python scripts/build_deck.py --build-dir /tmp/x   # keep intermediate assets / slide previews there

Rules this script follows (see docs/agent_notes/deck-video.md):
* Every number shown is read from docs/data/*.json at build time (holdout headline, central variant). Nothing is typed by hand.
  The only literals are design constants (colours from docs/design/tokens.json, layout) and fixed prose.
* Falcon Hub Airways is fictional. Only the repo's own SVG illustrations (docs/assets/svg) and charts rendered here are used.
* One layout spec per slide feeds two renderers: python-pptx (editable PPTX) and an HTML page that Playwright prints to PDF
  (no LibreOffice needed). Charts are matplotlib PNGs; SVG illustrations are rasterised with Playwright so their fonts load.
* Fonts: the vendored woff2 files (docs/vendor/fonts, OFL) are converted to TTF in presentations/fonts so matplotlib can use them
  and so a PowerPoint user can install them. PPTX cannot embed fonts via python-pptx; without the fonts installed PowerPoint
  substitutes its defaults and every text box has slack for that.
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


def compute_numbers():
    """Read everything the slides need from docs/data. Returns a flat dict N plus a few tables."""
    k, pol, fr, fc = load("kpis"), load("policies"), load("frontier"), load("forecast")
    rot, net, aog, act = load("rotables"), load("network"), load("aog_lab"), load("actions")
    meth, parts, story, dh = load("method"), load("parts"), load("story"), load("demand_history")
    N = {"raw": dict(k=k, pol=pol, fr=fr, fc=fc, rot=rot, net=net, aog=aog, act=act, meth=meth, parts=parts, story=story)}

    kp = {x["id"]: x for x in k["kpis"]}
    N["kpi"] = kp
    N["rec_id"], N["base_id"], N["ref_id"] = k["recommended_id"], k["baseline_id"], k["reference_id"]
    N["seeds"] = k["seeds"]
    N["n_seeds"] = len(k["seeds"])
    N["kpi_weeks"] = k["kpi_weeks"]
    N["seed_txt"] = f"holdout seeds {k['seeds'][0]}–{k['seeds'][-1]} (n={len(k['seeds'])}), central variant"

    pols = {p["policy_id"]: p for p in pol["policies"]}
    N["pols"] = pols
    N["paired"] = pol["paired"]
    N["rec_vs_P2"] = pol["recommended_vs_P2"]

    # Fleet / scope (assumption register values are ASSUMED; counts of files are DERIVED)
    A = {a["key"]: a for a in meth["assumptions"]}
    N["assump"] = A
    N["nb"] = int(A["fleet.narrowbody.count"]["value"])
    N["wb"] = int(A["fleet.widebody.count"]["value"])
    N["n_parts"] = len(parts["parts"])
    from collections import Counter
    N["cls_counts"] = Counter(p["cls"] for p in parts["parts"])
    N["n_stations"] = len(net["stations"])
    N["stations"] = net["stations"]
    N["hub"] = [s for s in net["stations"] if s["role"] == "hub"][0]["station"]
    N["n_weeks"] = len(next(iter(dh["series"].values())))
    N["split_week"] = dh["split_week"]
    zs = [sum(1 for v in ser[:dh["split_week"]] if v == 0) / dh["split_week"] for ser in dh["series"].values()]
    N["n_mostly_zero"] = sum(1 for z in zs if z > 0.5)  # parts with no demand in more than half the training weeks
    N["prov_counts"] = Counter(a["provenance"] for a in meth["assumptions"])
    N["n_assump"] = len(meth["assumptions"])
    N["requests_hist"] = sum(s["requests"] for s in net["stations"])
    N["manifest"] = meth["source_manifest"]

    # AOG lab
    inc = {i["id"]: i for i in aog["incidents"]}
    N["inc"] = inc["AOG-0001"]
    N["aog_sum"] = aog["summary"]
    N["option_labels"] = aog["option_labels"]

    # Story text (templated from data at export time)
    N["story"] = {s["story_id"]: s for s in story["steps"]}

    # Forecast honesty
    N["rel_vs_croston"] = fc["reliability_vs_croston"]
    N["champion_check"] = fc["champion_check"]
    N["champions"] = fc["champions"]
    N["ltd"] = fc["ltd_example"]
    N["method_labels"] = fc["method_labels"]
    N["lb_class_hold"] = fc["leaderboard_by_class_holdout"]
    N["monash_n"] = fc["monash"]["info"]["n_series"]
    N["parts"] = parts["parts"]

    # Rotable float example
    N["float"] = [x for x in rot["float_examples"] if x["pn"] == N["ltd"]["pn"]][0]
    pvs = [x for x in rot["palm_vs_sim"] if x["station"] == N["hub"] and x["sim_requests"] > 0]
    N["palm_hub_n"] = len(pvs)
    N["palm_hub_palm"] = sum(x["palm_availability"] for x in pvs) / len(pvs)
    N["palm_hub_sim"] = sum(x["sim_immediate_fill"] for x in pvs) / len(pvs)
    N["palm_vs_sim_policy"] = rot.get("palm_vs_sim_policy", "P1")

    # Frontier
    N["points"] = fr["points"]
    N["pt"] = {p["id"]: p for p in fr["points"]}
    N["reco"] = fr["recommendation"]
    N["tornado"] = fr["tornado"]
    N["variants"] = {v["variant"]: v for v in fr["variant_robustness"]}
    N["desk"] = fr["aog_desk_dependence"]
    N["levers"] = fr["levers"]
    N["consistency"] = {c["id"]: c for c in k["consistency"]}

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
    import statistics as st
    N["buy_med"] = st.median(r["annual_cost_per_aog_hour_aed"] for r in fr["levers"]
                             if r["lever"] == "buy_1" and r["annual_cost_per_aog_hour_aed"] and r["aog_hours_reduction"] > 0)
    N["tat_med"] = st.median(r["annual_cost_per_aog_hour_aed"] for r in fr["levers"]
                             if r["lever"] == "tat_cut_10d" and r["annual_cost_per_aog_hour_aed"] and r["aog_hours_reduction"] > 0)

    # Actions
    N["act_counts"] = act["counts"]
    N["act_week"] = act["as_of_week"]
    N["n_actions"] = len(act["actions"])

    # Validation + limitations
    N["validation"] = meth["validation"]
    N["limits"] = {l["n"]: l for l in meth["limitations"]}

    # Palm availability at BOM for the units P2 places there (Poisson pipeline demand over BOM's repair loop)
    lam = N["ltd"]["mean"]
    s_bom = parts_stock(parts, N["ltd"]["pn"], "BOM")
    N["s_bom"] = s_bom
    N["palm_bom"] = sum(math.exp(-lam) * lam ** j / math.factorial(j) for j in range(s_bom))
    N["meta_sha"] = k["meta"]["git_sha"]
    N["generated_at"] = k["meta"]["generated_at"]
    return N


def parts_stock(parts, pn, station):
    """Units of `pn` that the network policy (P2) places at `station`: read from the exported story/policy data.

    parts.json stock_by_station is I125 target units (P2 + I125 additions). For the Palm example we want P2's BOM units,
    which the exporter also states in story.json (rotable-float-calc body). We take I125's units at the station when the
    I125 allocation adds nothing there, which the check below asserts against story text."""
    p = [x for x in parts["parts"] if x["pn"] == pn][0]
    return int(p["stock_by_station"][station])


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
    """SVG -> PNG with Playwright so the SVGs' own fonts render. Frames/grids hidden so they sit on the slide grid."""
    from playwright.sync_api import sync_playwright
    lc = N["raw"]["rot"]["lifecycle"]
    counts = lc["counts"]
    flows = {f"{f['from']}>{f['to']}": f["count"] for f in lc["flows"]}
    jobs = [
        ("aircraft-top", "blueprint-aircraft-top.svg", "335 60 770 860", None, ".bp-frameset{display:none}"),
        ("aircraft-top-32", "blueprint-aircraft-top.svg", "40 40 1360 900",
         "document.querySelector('#ata-32').classList.add('is-active');"
         "document.querySelectorAll('svg text, svg rect, svg line, svg path').forEach(e=>{try{const b=e.getBBox();"
         "if(b.x>1090&&b.y>830)e.style.display='none'}catch(_){}})", ".bp-frameset{display:none}"),
        ("aircraft-side", "blueprint-aircraft-side.svg", None, None, ".bp-frameset{display:none}"),
        ("exploded-32", "exploded-32.svg", None, None, ".bp-frameset{display:none}"),
        ("lifecycle", "rotable-lifecycle.svg", None,
         f"const c={json.dumps(counts)},f={json.dumps(flows)};"
         "document.querySelectorAll('[data-count]').forEach(e=>{const v=c[e.dataset.count];if(v!=null)e.textContent=v.toLocaleString('en-US')});"
         "document.querySelectorAll('text[data-flow]').forEach(e=>{const v=f[e.dataset.flow];if(v!=null)e.textContent=v.toLocaleString('en-US')});",
         ".bp-frameset{display:none}"),
    ]
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=2)
        for key, fn, vb, js, css in jobs:
            svg = (SVG_DIR / fn).read_text().split("?>", 1)[-1]
            pg.set_content(f"<html><head><style>{font_face_css()} html,body{{margin:0;background:transparent}}"
                           f"svg{{display:block}} {css}</style></head><body>{svg}</body></html>")
            pg.evaluate("document.fonts.ready")
            if vb:
                pg.evaluate(f"(()=>{{const s=document.querySelector('svg');s.setAttribute('viewBox','{vb}');"
                            f"const v='{vb}'.split(' ').map(Number);s.setAttribute('width',v[2]);s.setAttribute('height',v[3]);}})()")
            if js:
                pg.evaluate(f"(()=>{{{js}}})()")
            # hide any full-sheet background rect (grid fill) that survived
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
        N, plt = self.N, self.plt
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
        ax.xaxis.set_major_locator(FixedLocator([1, 1.32, 2, 4, 8, 16]))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        self.mono_ticks(ax)
        lg = ax.legend(loc="upper center", frameon=False, fontsize=8, ncol=3, handletextpad=0.3, columnspacing=1.2,
                       bbox_to_anchor=(0.5, 1.13))
        for t in lg.get_texts():
            t.set_color(C["titanium"])
        return self._save(fig, "adi" + ("-c" if compact else ""))

    def leaderboard(self, wpx, hpx, part_class="R"):
        N, plt = self.N, self.plt
        rows = [r for r in N["lb_class_hold"] if r["part_class"] == part_class and r["demand_class"] == "all"
                and r["method"] != "zero"]
        rows.sort(key=lambda r: r["mase"])
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.37, 0.19, 0.58, 0.79])
        best = rows[0]["method"]
        for i, r in enumerate(rows):
            hl = r["method"] == "reliability"
            col = C["aero_teal"] if hl else (C["copper"] if r["method"] == best else C["titanium"])
            ax.plot(r["mase_ci"], [i, i], color=col, lw=1.2, alpha=0.7, solid_capstyle="butt")
            ax.plot([r["mase"]], [i], marker="o", ms=5, color=col)
            ax.text(r["mase_ci"][1] + 0.01, i, f"{r['mase']:.3f}", va="center", fontsize=7.5,
                    fontfamily=self.F["mono"], color=col)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r["method_label"] for r in rows], fontsize=8)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        lo = min(r["mase_ci"][0] for r in rows)
        hi = max(r["mase_ci"][1] for r in rows)
        ax.set_xlim(lo - 0.03, hi + 0.12)
        ax.set_xlabel("Holdout MASE (lower is better) · 95% CI", fontsize=8)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        for t in ax.get_xticklabels():
            t.set_fontfamily(self.F["mono"])
            t.set_fontsize(7.5)
        return self._save(fig, f"lb-{part_class}")

    def palm_pmf(self, wpx, hpx):
        N = self.N
        d = N["ltd"]["dist"]
        S = N["s_bom"]
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.12, 0.17, 0.85, 0.74])
        for r in d:
            col = C["aero_teal"] if r["q"] < S else C["copper"]
            ax.bar(r["q"], r["p"], width=0.62, color=col, alpha=0.9 if r["q"] < S else 0.75)
            ax.text(r["q"], r["p"] + 0.012, f"{r['p'] * 100:.1f}%", ha="center", fontsize=7.5,
                    fontfamily=self.F["mono"], color=C["titanium"])
        ax.axvline(S - 0.5, color=C["ice"], lw=0.9, ls=(0, (4, 3)))
        top = max(r["p"] for r in d)
        ax.text(S - 0.42, top * 0.98, f"S = {S} units at BOM", fontsize=8, color=C["ice"], va="top",
                fontfamily=self.F["mono"])
        ax.set_xticks([r["q"] for r in d])
        ax.set_ylim(0, top * 1.18)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("Units in the BOM repair pipeline at a random moment", fontsize=8)
        self.mono_ticks(ax)
        return self._save(fig, "pmf")

    def stations(self, wpx, hpx):
        N = self.N
        sts = sorted(N["stations"], key=lambda s: (s["role"] != "hub", -s["aog_hours_by_policy"]["P0"]["mean"]))
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.13, 0.12, 0.84, 0.80])
        pol_style = [("P0", C["copper"], "s", -0.22), ("P1", C["slate"], "o", 0.0), ("P2", C["aero_teal"], "D", 0.22)]
        for i, s in enumerate(sts):
            for pid, col, mk, off in pol_style:
                v = s["aog_hours_by_policy"][pid]
                floor = 2.0
                lo, hi = max(v["ci"][0], floor), max(v["ci"][1], floor)
                m = max(v["mean"], floor)
                ax.plot([lo, hi], [i + off, i + off], color=col, lw=1.3, alpha=0.75)
                ax.plot([m], [i + off], marker=mk, ms=5.5, color=col, mfc=col if pid != "P1" else C["midnight"],
                        mew=1.2)
                if v["mean"] < floor:
                    ax.text(hi * 1.12, i + off, f"{v['mean']:.1f} h", va="center", fontsize=7,
                            fontfamily=self.F["mono"], color=col)
        ax.set_xscale("log")
        ax.set_yticks(range(len(sts)))
        ax.set_yticklabels([f"{s['station']}{' · hub' if s['role'] == 'hub' else ''}" for s in sts], fontsize=8.5,
                           fontfamily=self.F["mono"])
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.axhline(0.5, color=HAIR_BG, lw=0.8)
        from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
        ax.xaxis.set_major_locator(FixedLocator([3, 10, 30, 100, 300, 1000, 3000]))
        ax.set_xlim(1.6, 4000)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Expected material-related downtime: material AOG hours / year (log) · holdout mean and 95% CI", fontsize=8)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        for t in ax.get_xticklabels():
            t.set_fontfamily(self.F["mono"])
            t.set_fontsize(7.5)
        from matplotlib.lines import Line2D
        hs = [Line2D([], [], color=c, marker=m, ls="-", ms=5, lw=1, mfc=c if p != "P1" else C["midnight"])
              for p, c, m, _ in pol_style]
        labels = [f"{p} · {N['pols'][p]['label']}" for p, *_ in pol_style]
        lg = ax.legend(hs, labels, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, frameon=False, fontsize=8,
                       handletextpad=0.4, columnspacing=1.2)
        for t in lg.get_texts():
            t.set_color(C["titanium"])
        return self._save(fig, "stations")

    def frontier(self, wpx, hpx, compact=False):
        N = self.N
        pts = N["points"]
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.10, 0.14, 0.87, 0.82] if not compact else [0.14, 0.16, 0.82, 0.80])
        nd = sorted([p for p in pts if not p["dominated"] and p["kind"] in ("greedy", "lever")],
                    key=lambda p: p["capital_aed"])
        xs = [p["capital_aed"] / 1e6 for p in nd]
        ax.fill_between(xs, [max(p["aog_ci"][0], 60) for p in nd], [p["aog_ci"][1] for p in nd],
                        color=C["aero_teal"], alpha=0.10, lw=0)
        ax.plot(xs, [p["aog_hours"] for p in nd], color=C["aero_teal"], lw=1.2, alpha=0.9)
        for p in pts:
            x, y = p["capital_aed"] / 1e6, p["aog_hours"]
            lo = max(p["aog_ci"][0], 60)
            if p["id"] == N["rec_id"]:
                continue
            if p["kind"] == "policy":
                col, mk, ms, mfc = C["copper"], "s", 6, C["copper"]
            elif p["kind"] in ("lever", "combo"):
                col, mk, ms, mfc = C["titanium"], "D", 5, "none"
            else:
                col, mk, ms, mfc = (C["titanium"] if not p["dominated"] else C["slate"]), "o", 4, None
                mfc = col if not p["dominated"] else "none"
            if not compact:
                ax.plot([x, x], [lo, p["aog_ci"][1]], color=col, lw=0.7, alpha=0.5)
            ax.plot([x], [y], marker=mk, ms=ms, color=col, mfc=mfc, mew=1)
        r = N["pt"][N["rec_id"]]
        rx, ry = r["capital_aed"] / 1e6, r["aog_hours"]
        ax.plot([rx, rx], r["aog_ci"], color=C["aero_teal"], lw=1.6)
        ax.plot([rx], [ry], marker="o", ms=11, mfc="none", mec=C["aero_teal"], mew=1.6)
        ax.plot([rx], [ry], marker="o", ms=5, color=C["aero_teal"])
        mono = dict(fontfamily=self.F["mono"], fontsize=8 if not compact else 9)
        for pid, dx, dy, ha in [("P0", 0.6, 1.0, "left"), ("P1", -0.6, 1.0, "right"), ("P2", 0.6, 1.0, "left")]:
            p = N["pt"][pid]
            ax.text(p["capital_aed"] / 1e6 + dx, p["aog_hours"] * dy, pid, color=C["copper"], va="center", ha=ha,
                    **mono)
        ax.annotate(f"{N['rec_id']} · recommended\n{fmt_aed(r['capital_aed'])} · {fmt_int(ry)} h/yr",
                    xy=(rx, ry), xytext=(rx + (3.2 if not compact else 4), ry * (0.42 if not compact else 0.45)),
                    color=C["aero_teal"], fontsize=8.5 if not compact else 10, fontfamily=self.F["ui"],
                    fontweight="bold", arrowprops=dict(arrowstyle="-", color=C["aero_teal"], lw=0.8), va="center")
        ax.set_yscale("log")
        from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
        ax.yaxis.set_major_locator(FixedLocator([100, 200, 500, 1000, 2000, 5000]))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_ylim(80, 4200)
        ax.set_xlabel("Simulated spare capital (AED M)", fontsize=8.5 if not compact else 10)
        ax.set_ylabel("Material AOG h / year (log)", fontsize=8.5 if not compact else 10)
        ax.yaxis.grid(True, color=HAIR_BG, lw=0.6, ls=(0, (2, 3)))
        self.mono_ticks(ax, 8 if not compact else 9)
        return self._save(fig, "frontier" + ("-c" if compact else ""))

    def tornado(self, wpx, hpx):
        N = self.N
        rows = sorted(N["tornado"], key=lambda r: max(abs(r["low"]), abs(r["high"])), reverse=True)
        base = rows[0]["base"]
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.24, 0.22, 0.72, 0.74])
        for i, r in enumerate(rows):
            for v, side, setting in [(r["low"], "low", r["low_setting"]), (r["high"], "high", r["high_setting"])]:
                col = C["aero_teal"] if v >= 0 else C["copper"]
                ax.barh(i, v / 1e6, height=0.55, color=col, alpha=0.85)
                ax.text(v / 1e6 + (0.12 if v >= 0 else -0.12), i, setting, va="center",
                        ha="left" if v >= 0 else "right", fontsize=7.5, fontfamily=self.F["mono"], color=C["titanium"])
        ax.axvline(0, color=C["ice"], lw=0.8)
        ax.set_yticks(range(len(rows)))
        lab = {"aog_penalty": "AOG penalty", "repair_tat": "Repair TAT", "lead_time": "Purchase lead time",
               "carrying_cost": "Carrying cost"}
        ax.set_yticklabels([lab.get(r["factor"], r["factor"]) for r in rows], fontsize=8.5)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        m = max(max(abs(r["low"]), abs(r["high"])) for r in rows) / 1e6
        ax.set_xlim(-m * 1.45, m * 1.45)
        ax.set_xlabel(f"Change in {N['rec_id']} vs P2 net benefit around base {fmt_aed(base)}/yr (AED M)", fontsize=8)
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
        ax = fig.add_axes([0.42, 0.06, 0.54, 0.90])
        sev = [("urgent", C["red"]), ("review", C["amber"]), ("info", C["slate"])]
        for i, t in enumerate(types_):
            left = 0
            for s, col in sev:
                v = bts.get(f"{t}|{s}", 0)
                if v:
                    ax.barh(i, v, left=left, height=0.6, color=col, alpha=0.9)
                left += v
            ax.text(left + 0.6, i, str(left), va="center", fontsize=8, fontfamily=self.F["mono"], color=C["ice"])
        ax.set_yticks(range(len(types_)))
        ax.set_yticklabels([t.replace("_", " ").capitalize() for t in types_], fontsize=8)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])
        ax.set_xlim(0, max(N["act_counts"]["by_type"].values()) * 1.18)
        for t in ax.get_yticklabels():
            t.set_color(C["titanium"])
        return self._save(fig, "actions")

    def kpi_bars(self, wpx, hpx):
        """P0 vs P2 vs recommended AOG h/yr (carousel)."""
        N = self.N
        ids = [N["base_id"], "P1", N["ref_id"], N["rec_id"]]
        fig = self._fig(wpx, hpx)
        ax = fig.add_axes([0.20, 0.10, 0.70, 0.86])
        for i, pid in enumerate(ids):
            k = N["pols"][pid]["kpi"]["aog_hours"]
            col = C["aero_teal"] if pid == N["rec_id"] else (C["copper"] if pid == N["base_id"] else C["slate"])
            ax.barh(i, k["mean"], height=0.55, color=col)
            ax.plot([k["ci_lo"], k["ci_hi"]], [i, i], color=C["ice"], lw=1, alpha=0.6)
            ax.text(k["ci_hi"] + 40, i, f"{fmt_int(k['mean'])} h", va="center", fontsize=11,
                    fontfamily=self.F["mono"], color=C["ice"])
        ax.set_yticks(range(len(ids)))
        ax.set_yticklabels(ids, fontsize=12, fontfamily=self.F["mono"])
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])
        ax.set_xlim(0, max(N["pols"][p]["kpi"]["aog_hours"]["ci_hi"] for p in ids) * 1.25)
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


def build_deck(N, A, CH, bg, total=10):
    S = []
    k = N["kpi"]
    rec, base, ref = N["rec_id"], N["base_id"], N["ref_id"]
    aogk, fill, cap = k["aog_hours"], k["immediate_fill_rate"], k["spare_capital_aed"]
    src_hold = f"Source: docs/data · {N['seed_txt']}"

    # 1 — Title ------------------------------------------------------------------------------------------------------
    s = Slide(bg=bg)
    s.image(700, 40, 560, 620, A["aircraft-top"])
    s.text(56, 70, 640, 16, P(R("AVIATION SPARE-PARTS INTELLIGENCE · CASE STUDY", "eyebrow")))
    s.text(56, 92, 640, 196, [P(R("GROUNDED", "title", s=60, sp=-1), ls=0.9), P(R("NO MORE", "title", s=60, sp=-1,
                                                                            c=C["aero_teal"]), ls=0.9)])
    s.text(56, 268, 600, 60, P(R("A single missing part can ground an aircraft. Know which ones, where, and what to "
                                 "do about it.", "lede", s=15, c=C["ice"]), ls=1.1))
    s.text(56, 332, 600, 40, P(R(f"{AIRLINE} · {N['nb'] + N['wb']} aircraft · {N['n_stations']} stations · "
                                 f"{N['n_parts']} part numbers · {N['n_weeks']} weeks of simulated history",
                                 "monos", s=8.5), ls=1.15))
    y0 = 392
    s.line(56, y0 - 10, 640, y0 - 10, HAIR_BG, 0.75)
    stat(s, 56, y0, 190, f"{fmt_int(aogk['value'])} h", "material AOG / year",
         f"from {fmt_int(aogk['baseline'])} h under {base} legacy rules", size=28)
    stat(s, 256, y0, 190, fmt_pct(fill["value"]), "immediate fill rate",
         f"from {fmt_pct(fill['baseline'])} under {base}", size=28)
    stat(s, 456, y0, 200, fmt_signed(cap["delta"], lambda v: fmt_aed(v)), "extra spare capital",
         f"{fmt_aed(cap['baseline'])} → {fmt_aed(cap['value'])}", col=C["copper"], size=28)
    s.chip(56, 510, "SIMULATED", f"SIMULATED · {rec} · HOLDOUT SEEDS {N['seeds'][0]}–{N['seeds'][-1]}")
    s.text(56, 576, 620, 80, [P(R("Akash Gajjar", "h3", s=13), after=2),
                              P(R("MSc Supply Chain Management, University of Liverpool (2025)", "bodym", s=10),
                                after=4),
                              P(R(LIVE_URL.replace("https://", ""), "monos", s=8.5, c=C["aero_teal"])),
                              P(R(REPO_URL.replace("https://", ""), "monos", s=8.5))])
    s.footer(1, "numbers read from docs/data at build time", total)
    S.append(s)

    # 2 — The problem -----------------------------------------------------------------------------------------------
    inc = N["inc"]
    cf = inc["counterfactual"]
    s = Slide(bg=bg)
    s.header(2, "The problem", f"One brake, zero on the shelf at {inc['station']}: {inc['aog_hours']} hours on the ground",
             f"Incident {inc['id']} replayed from the simulated history: a {inc['deadline']} (no deferral) requirement "
             f"for {inc['pn']}, {inc['desc'].lower()}, on {inc['tail']} (fictional {inc['archetype']}).")
    s.card(48, 150, 600, 340)
    s.text(70, 166, 400, 16, P(R("INCIDENT TIMELINE · SIMULATED UTC", "label", c=C["faint"])))
    s.chip_r(630, 164, "SIMULATED")
    y = 194
    for st_ in inc["timeline"]:
        hot = st_["step"] in ("aog_start", "fitted")
        s.text(70, y, 70, 20, P(R(f"T+{st_['t_h']:g} h", "mono", s=9, c=C["aero_teal"] if not hot else C["amber"])))
        s.text(136, y, 52, 20, P(R(st_["station"], "mono", s=9, c=C["titanium"])))
        s.text(184, y, 446, 20, P(R(st_["event"], "body", s=9.6, c=C["ice"] if hot else C["titanium"])))
        y += 23
    s.line(70, y + 6, 626, y + 6, HAIR, 0.75)
    s.text(70, y + 14, 560, 40, P(R(f"Exposure {fmt_aed(cf['actual_exposure_aed'])}", "h3", s=12, c=C["copper"]),
                                  R(f"  = {inc['aog_hours']} AOG h × AED {inc['penalty_aed_per_h']:,}/h penalty (ASSUMED) "
                                    f"+ AED {cf['actual_direct_cost_aed']:,} logistics", "bodym", s=9.3), ls=1.1))
    st2 = N["story"]["parts-hotspot-32"]
    asum = N["aog_sum"]
    s.card(48, 502, 600, 168)
    s.text(70, 518, 560, 16, P(R("WHY IT KEEPS HAPPENING", "label", c=C["faint"])))
    s.text(70, 540, 556, 60, P(R(st2["body"], "body", s=10), ls=1.1))
    s.text(70, 606, 270, 60, [P(R(fmt_int(asum["n_incidents"]), "mid", c=C["copper"], s=19)),
                              P(R("material AOG incidents in 2 years of history (P0)", "small", s=8.3))])
    s.text(350, 606, 280, 60, [P(R(f"{fmt_int(asum['aog_hours_total'])} h", "mid", c=C["copper"], s=19)),
                               P(R("aircraft on the ground, all incidents (P0)", "small", s=8.3))])
    s.image(664, 146, 576, 520, A["aircraft-top-32"])
    s.text(664, 646, 568, 16, P(R("ATA 32 · LANDING GEAR highlighted · original schematic, not an OEM drawing",
                                  "label", s=7, c=C["faint"]), al="c"))
    s.footer(2, "Source: docs/data/aog_lab.json, story.json · simulated history weeks 0–103", total)
    S.append(s)

    # 3 — Airline & provenance --------------------------------------------------------------------------------------
    s = Slide(bg=bg)
    pc = N["prov_counts"]
    s.header(3, "The fictional airline & data provenance",
             f"A Gulf hub, {N['n_stations'] - 1} outstations, and every number tagged by its source",
             f"No operator data exists here. {N['n_assump']} parameters sit in an assumption register with a provenance "
             "tag; the simulated history is generated from them, and every model output is DERIVED from that history.")
    cols = [
        ("REAL", "Facts from public sources",
         [f"Station coordinates for {N['n_stations']} airports (OurAirports, public domain)",
          f"Monash Car Parts benchmark: {fmt_int(N['monash_n'])} real intermittent series (CC BY 4.0)",
          f"{pc.get('REAL', 0)} register rows (e.g. station identities)"]),
        ("ASSUMED", "Stated, sourced judgement",
         [f"Fleet: {N['nb']} narrowbody + {N['wb']} widebody (generic archetypes)",
          f"AOG penalty and carrying cost ({fmt_pct(N['reco']['carrying_pct'], 0)}/yr) are scenarios",
          f"{pc.get('ASSUMED', 0)} of {N['n_assump']} register rows"]),
        ("SIMULATED", "Generated by the engine",
         [f"{N['n_weeks']} weeks of history: {fmt_int(N['requests_hist'])} material requests",
          f"{fmt_int(N['aog_sum']['n_incidents'])} AOG incidents, removals, repair orders",
          f"Policy KPIs on {N['n_seeds']} paired holdout seeds"]),
        ("DERIVED", "Computed from the history",
         ["Forecasts, ADI/CV² classes, Palm floats",
          f"Readiness Frontier and the {rec} recommendation",
          f"{N['n_actions']} planner actions for week {N['act_week']}"]),
    ]
    x = 48
    for prov, head, items in cols:
        s.card(x, 160, 284, 262)
        s.rect(x, 160, 284, 4, fill=PROV_COLOR[prov], r=0)
        s.chip(x + 18, 180, prov)
        s.text(x + 18, 210, 250, 24, P(R(head, "h3", s=13)))
        s.text(x + 18, 242, 252, 210, [bullet([t], "bodym", col=PROV_COLOR[prov], after=8) for t in items])
        x += 300
    s.image(48, 440, 560, 230, A["aircraft-side"], align="l")
    s.card(632, 438, 600, 232)
    s.text(654, 456, 560, 16, P(R("NETWORK · COORDINATES REAL, EVERYTHING ELSE SIMULATED", "label", c=C["faint"])))
    yy = 486
    for i, st_ in enumerate(N["stations"]):
        cx = 654 + (i % 2) * 290
        cy = yy + (i // 2) * 44
        s.text(cx, cy, 50, 20, P(R(st_["station"], "mono", s=11, b=True,
                                   c=C["aero_teal"] if st_["role"] == "hub" else C["ice"])))
        s.text(cx + 48, cy + 1, 232, 30, P(R(f"{st_['name']}", "bodym", s=8.5),
                                           R(f"  {st_['role']}", "small", s=8), ls=1.05))
    s.footer(3, "Source: docs/data/method.json (assumption register, source manifest), network.json", total)
    S.append(s)

    # 4 — Demand is lumpy ------------------------------------------------------------------------------------------
    s = Slide(bg=bg)
    cc = N["champion_check"]
    n_cells = len(cc)
    n_rank1 = sum(1 for c in cc if c["champion_rank"] == 1)
    ir = [c for c in cc if c["demand_class"] == "intermittent" and c["part_class"] == "R"][0]
    rvc = N["rel_vs_croston"]
    n_rel_better = sum(1 for r in rvc if r["reliability_better"])
    n_q90_better = sum(1 for r in rvc if r["reliability_pinball_q90"] < r["croston_family_pinball_q90"])
    rr = [r for r in rvc if r["part_class"] == "R"][0]
    from collections import Counter
    dcls = Counter(p["demand_class"] for p in N["parts"])
    s.header(4, "Forecasting", "Demand is lumpy, and no method wins everywhere",
             f"{dcls.get('intermittent', 0)} of {N['n_parts']} part numbers are intermittent (ADI > 1.32 weeks, CV² < 0.49, training "
             f"weeks 0–{N['split_week'] - 1}). Champions were frozen on selection weeks, then checked on the holdout.")
    s.card(48, 150, 590, 520)
    s.text(70, 166, 420, 16, P(R("ADI × CV² · ONE DOT PER PART NUMBER", "label", c=C["faint"])))
    s.chip_r(620, 164, "DERIVED")
    s.image(60, 190, 570, 470, CH.adi_cv2(570, 470))
    s.card(656, 150, 576, 300)
    s.text(678, 166, 420, 16, P(R("ROTABLES · HOLDOUT LEADERBOARD", "label", c=C["faint"])))
    s.chip_r(1214, 164, "DERIVED")
    s.image(668, 186, 552, 258, CH.leaderboard(552, 258, "R"))
    s.card(656, 462, 576, 208)
    s.text(678, 476, 540, 16, P(R("HONEST READING", "label", c=C["amber"])))
    s.text(678, 498, 540, 170, [
        bullet([R("Reliability-exposure vs best Croston-family: ", "body", s=9.8, b=True),
                R(f"better on MASE in {n_rel_better} of {len(rvc)} part classes (rotables {rr['reliability_mase']:.3f} vs "
                  f"{rr['croston_family_mase']:.3f}, CIs overlap); lower q90 pinball loss in {n_q90_better} of {len(rvc)}.",
                  "bodym", s=9.8)], after=6),
        bullet([R("Champion check: ", "body", s=9.8, b=True),
                R(f"the frozen champion was also best on the holdout in {n_rank1} of {n_cells} cells. For intermittent "
                  f"rotables '{ir['champion']}' ranked {ir['champion_rank']}/{ir['n_methods']}, kept as frozen, not swapped.",
                  "bodym", s=9.8)], after=6),
        bullet([R("So: ", "body", s=9.8, b=True),
                R("rotables are sized from the reliability-exposure removal rate (Palm needs a rate), not from a MASE "
                  "champion.", "bodym", s=9.8)], after=0),
    ])
    s.footer(4, "Source: docs/data/forecast.json, parts.json · rolling origins, h = 4 weeks, holdout", total)
    S.append(s)

    # 5 — Rotable float maths --------------------------------------------------------------------------------------
    fl, ltd = N["float"], N["ltd"]
    s = Slide(bg=bg)
    s.header(5, "Rotable float maths", f"Palm's theorem: put the {fl['desc'].lower().split()[-2]} float where the D0 demand is",
             f"A rotable is repaired, not consumed. Spares needed = units tied up in the repair pipeline. With Poisson "
             f"removals, pipeline occupancy is Poisson with mean λ·T (Palm), whatever the shape of the repair time.")
    s.card(48, 150, 560, 520)
    s.text(70, 166, 400, 16, P(R("THE CALCULATION · ONE CARBON BRAKE", "label", c=C["faint"])))
    s.chip_r(590, 164, "DERIVED")
    s.rect(70, 192, 516, 64, fill=C["deep_steel"], line=HAIR, r=8)
    s.text(84, 202, 490, 50, [P(R("A(S) = P(X < S),   X ~ Poisson(λ · T)", "mono", s=13, c=C["ice"], b=True), al="c"),
                              P(R("availability of S spares = chance fewer than S units are in repair", "small", s=8.5),
                                al="c")])
    rows = [
        ("Network removal rate λ", f"{fl['rate_per_30d']:.2f} per 30 days"),
        ("Hub pipeline T (repair + transport)", f"{fl['pipeline_days']:.1f} days"),
        (f"BOM repair loop", f"{ltd['lead_time_days']:.1f} days → λT = {ltd['mean']:.3f} units"),
        ("Unit cost", f"AED {fl['unit_cost_aed']:,}"),
        ("Deadline class", f"{fl['deadline']} (aircraft cannot dispatch)"),
    ]
    yy = 272
    for a_, b_ in rows:
        s.text(70, yy, 260, 20, P(R(a_, "bodym", s=10)))
        s.text(330, yy, 256, 20, P(R(b_, "mono", s=9.5), al="r"))
        s.line(70, yy + 24, 586, yy + 24, HAIR, 0.5)
        yy += 34
    s.text(70, yy + 12, 516, 16, P(R("SERVICEABLE UNITS IN THE NETWORK, BY POLICY", "label", c=C["faint"])))
    yy += 40
    units = [("P0 legacy", fl["p0_units"], C["copper"]), ("P1 local", fl["p1_units"], C["slate"]),
             ("P2 network", fl["p2_units"], C["titanium"]), (f"{rec} recommended", fl["rec_units"], C["aero_teal"])]
    umax = max(u[1] for u in units)
    for lab, v, col in units:
        s.text(70, yy, 130, 18, P(R(lab, "bodym", s=9.5)))
        s.rect(200, yy + 3, 330 * v / umax, 12, fill=col, r=2)
        s.text(200 + 330 * v / umax + 8, yy, 50, 18, P(R(str(v), "mono", s=9.5)))
        yy += 27
    s.text(70, yy + 6, 516, 30, P(R(f"+ {fl['loop_units']} units seeded in the repair loop (Palm's S counts serviceable "
                                    f"+ pipeline).", "small", s=8.5)))
    s.card(632, 150, 600, 330)
    s.text(654, 166, 520, 16, P(R(f"PIPELINE DEMAND AT BOM · POISSON(λT = {ltd['mean']:.3f})", "label",
                                  c=C["faint"])))
    s.chip_r(1214, 164, "DERIVED")
    s.image(644, 186, 576, 206, CH.palm_pmf(576, 206))
    s.text(654, 412, 560, 64, [P(R(f"A({N['s_bom']}) = {fmt_pct(N['palm_bom'])}", "mid", c=C["aero_teal"], s=17),
                                 after=2),
                               P(R(f"availability for the {N['s_bom']} units the network plan places at BOM: "
                                   f"{fmt_pct(1 - N['palm_bom'])} of the time a D0 removal finds the shelf empty.",
                                   "bodym", s=9.5), ls=1.05)])
    s.card(632, 492, 600, 178)
    s.text(654, 508, 540, 16, P(R("DOES PALM MATCH THE SIMULATION?", "label", c=C["amber"])))
    s.text(654, 530, 556, 140, [
        P(R(f"Across {N['palm_hub_n']} rotables at the hub ({N['palm_vs_sim_policy']} floats, 20 seeds): Palm predicts "
            f"{fmt_pct(N['palm_hub_palm'])} availability on average, the simulation fills {fmt_pct(N['palm_hub_sim'])} "
            f"immediately.", "body", s=10), after=6, ls=1.1),
        P(R("Part by part it is noisier: clustered removals, non-stationary repair times and hub/outstation competition "
            "push some parts below Palm, which is why every policy is judged in the simulator, not on the formula.",
            "bodym", s=9.5), ls=1.1),
    ])
    s.footer(5, "Source: docs/data/rotables.json, forecast.json (ltd_example), parts.json, story.json", total)
    S.append(s)

    # 6 — Hub vs outstation ----------------------------------------------------------------------------------------
    pr = N["paired"]
    p20, p10 = pr["P2-P0"], pr["P1-P0"]
    hubst = [x for x in N["stations"] if x["role"] == "hub"][0]
    bom = [x for x in N["stations"] if x["station"] == "BOM"][0]
    s = Slide(bg=bg)
    s.header(6, "Hub vs outstation", "Positioning beats reacting: P2 cuts AOG at every station",
             f"{base} keeps the float at {N['hub']}. P1 optimises each station on its own. P2 pools at the hub and stocks "
             "an outstation only where the D0 penalty pays for the unit. Same simulated futures for all three (paired seeds).")
    s.card(48, 150, 760, 520)
    s.text(70, 166, 560, 16, P(R("MATERIAL AOG BY STATION · HOLDOUT", "label", c=C["faint"])))
    s.chip_r(790, 164, "SIMULATED")
    s.image(58, 190, 740, 470, CH.stations(740, 470))
    s.card(826, 150, 406, 520)
    s.text(848, 166, 360, 16, P(R("PAIRED DIFFERENCES VS P0 · NETWORK", "label", c=C["faint"])))
    blocks = [
        ("P2 − P0 · AOG h/yr", fmt_int(p20["aog_hours"]["mean"]), ci_txt([p20["aog_hours"]["ci_lo"], p20["aog_hours"]["ci_hi"]]),
         f"better on {fmt_pct(p20['aog_hours']['share_seeds_better'], 0)} of seeds", C["aero_teal"]),
        ("P2 − P0 · spare capital", fmt_aed(p20["spare_capital_aed"]["mean"], 2),
         ci_txt([p20["spare_capital_aed"]["ci_lo"], p20["spare_capital_aed"]["ci_hi"]], lambda v: fmt_aed(v, 2)),
         "the CI spans zero: same money, placed differently", C["titanium"]),
        ("P1 − P0 · spare capital", fmt_signed(p10["spare_capital_aed"]["mean"], lambda v: fmt_aed(v)),
         f"AOG {fmt_int(p10['aog_hours']['mean'])} h/yr", "local optimisation buys stock, the hub stays exposed",
         C["copper"]),
    ]
    yy = 192
    for lab, val, ci, note, col in blocks:
        s.text(848, yy, 360, 16, P(R(lab, "bodym", s=9.5)))
        s.text(848, yy + 16, 360, 40, P(R(val, "mid", s=21, c=col), R(f"  {ci}", "mono", s=9, c=C["titanium"])))
        s.text(848, yy + 52, 360, 18, P(R(note, "small", s=8.5)))
        yy += 84
    s.line(848, yy, 1210, yy, HAIR, 0.5)
    bp0, bp2 = bom["aog_hours_by_policy"]["P0"], bom["aog_hours_by_policy"]["P2"]
    hp0, hp1, hp2 = (hubst["aog_hours_by_policy"][x] for x in ("P0", "P1", "P2"))
    s.text(848, yy + 12, 362, 220, [
        bullet([R(f"BOM: {fmt_int(bp0['mean'])} → {fmt_int(bp2['mean'])} h/yr ", "body", s=9.8, b=True),
                R(f"under P2 {ci_txt(bp2['ci'])}.", "bodym", s=9.8)], after=6),
        bullet([R(f"{N['hub']} hub: {fmt_int(hp0['mean'])} → {fmt_int(hp2['mean'])} h/yr ", "body", s=9.8, b=True),
                R(f"under P2, but still {fmt_int(hp1['mean'])} under P1, which spends its capital at the outstations.",
                  "bodym", s=9.8)], after=6),
        bullet([R("Honest: ", "body", s=9.8, b=True, c=C["amber"]),
                R(f"at the outstations P1's local floats beat P2 (BOM {bom['aog_hours_by_policy']['P1']['mean']:.1f} vs "
                  f"{fmt_int(bp2['mean'])} h/yr), but P1 needs {fmt_aed(p10['spare_capital_aed']['mean'])} more capital "
                  "and most demand sits at the hub.", "bodym", s=9.8)], after=0),
    ])
    s.footer(6, f"Source: docs/data/network.json, policies.json · {N['seed_txt']}", total)
    S.append(s)

    # 7 — Readiness Frontier ---------------------------------------------------------------------------------------
    r = N["pt"][rec]
    rv = N["rec_vs_P2"]
    cons = N["consistency"]["aog_hours"]
    reco = N["reco"]
    stab = reco["stability"]
    stab_same = all(x["recommended"] == rec for x in stab)
    s = Slide(bg=bg)
    s.header(7, "The Readiness Frontier", f"Where to stop buying: {rec}, by a rule fixed before the holdout",
             f"{len(N['points'])} frozen candidate plans, re-run on unseen holdout seeds. Walk up the hull while an extra "
             f"AED 1M still removes at least {reco['h_star_per_aed_1m']:.1f} AOG h/yr (the break-even of the assumed penalty).")
    s.card(48, 150, 760, 520)
    s.text(70, 166, 560, 16, P(R("CAPITAL VS MATERIAL AOG · HOLDOUT MEANS, 95% CI", "label", c=C["faint"])))
    s.chip_r(790, 164, "SIMULATED")
    s.image(58, 188, 740, 474, CH.frontier(740, 474))
    s.card(826, 150, 406, 300)
    s.text(848, 166, 360, 16, P(R(f"{rec} ON THE HOLDOUT", "label", c=C["aero_teal"])))
    s.text(848, 188, 180, 70, [P(R(f"{fmt_int(r['aog_hours'])} h", "big", s=28)),
                               P(R(f"AOG / yr {ci_txt(r['aog_ci'])}", "monos", s=8))])
    s.text(1030, 188, 190, 70, [P(R(fmt_aed(r["capital_aed"]), "big", s=28, c=C["copper"])),
                                P(R(f"capital {ci_txt(r['capital_ci'], lambda v: fmt_m(v) + 'M')}", "monos", s=8))])
    s.text(848, 270, 362, 176, [
        bullet([R(f"vs P2 (paired): ", "body", s=9.8, b=True),
                R(f"{fmt_int(rv['aog_hours']['mean'])} AOG h/yr {ci_txt([rv['aog_hours']['ci_lo'], rv['aog_hours']['ci_hi']])} "
                  f"for {fmt_signed(rv['capital']['mean'], fmt_aed)} capital; total annual cost "
                  f"{fmt_aed(rv['total_cost']['mean'])}.", "bodym", s=9.8)], after=6),
        bullet([R(f"vs {base}: ", "body", s=9.8, b=True),
                R(f"{fmt_int(aogk['baseline'])} → {fmt_int(aogk['value'])} AOG h/yr, fill {fmt_pct(fill['baseline'])} → "
                  f"{fmt_pct(fill['value'])}.", "bodym", s=9.8)], after=6),
        bullet([R("Stable choice: ", "body", s=9.8, b=True),
                R(f"the rule still picks {rec} with the penalty ×0.5/×2 and carrying cost 15%/25%." if stab_same else
                  "the rule's pick moves under some penalty/carrying settings.", "bodym", s=9.8)], after=0),
    ])
    s.text(848, 410, 362, 36, P(R(f"h* = {fmt_pct(reco['carrying_pct'], 0)} carrying × AED 1M ÷ AED "
                                  f"{reco['aed_per_aog_hour']:,}/AOG h = {reco['h_star_per_aed_1m']:.2f} h per AED 1M",
                                  "monos", s=7.8, c=C["faint"]), ls=1.05))
    s.card(826, 462, 406, 208, line=blend(C["amber"], C["card"], 0.45))
    s.text(848, 478, 360, 16, P(R("SELECTION VS HOLDOUT GAP", "label", c=C["amber"])))
    s.text(848, 498, 180, 56, [P(R(f"{fmt_int(cons['selection_recommended'])} h", "mid", s=20, c=C["titanium"])),
                               P(R("selection seeds", "small", s=8))])
    s.text(1030, 498, 180, 56, [P(R(f"{fmt_int(cons['holdout_recommended'])} h", "mid", s=20, c=C["amber"])),
                                P(R("holdout seeds (headline)", "small", s=8))])
    s.text(848, 560, 362, 106, P(R(f"{rec} was picked on selection seeds, where its AOG looked {fmt_int(cons['selection_recommended'])} h. "
                                   f"On fresh seeds it is {fmt_int(cons['holdout_recommended'])} h; the selection value is "
                                   f"{'inside' if cons['selection_inside_holdout_ci'] else 'outside'} the holdout CI. "
                                   "Optimism from choosing on the same seeds you score on is real; the holdout is the "
                                   "number reported.", "bodym", s=9.3), ls=1.1))
    s.footer(7, f"Source: docs/data/frontier.json, kpis.json · {N['seed_txt']}", total)
    S.append(s)

    # 8 — Levers & sensitivity -------------------------------------------------------------------------------------
    V = N["variants"]
    lo_v, ce_v, hi_v = V["low_stress"], V["central"], V["high_stress"]
    lev = N["pt"].get("LEV_TAT10_TOP8")
    desk = N["desk"]
    s = Slide(bg=bg)
    s.header(8, "Levers & sensitivity", "Spares usually beat TAT cuts, and the world matters",
             "Per part number: the annual cost per AOG hour avoided by buying one more spare vs paying a shop to cut 10 days "
             f"of repair TAT. Then: how {rec}'s value over P2 moves with each assumption, and across stress variants.")
    s.card(48, 150, 380, 248)
    s.text(70, 166, 340, 16, P(R("BUY 1 SPARE VS CUT TAT 10 DAYS", "label", c=C["faint"])))
    s.chip_r(410, 164, "DERIVED")
    s.text(70, 188, 160, 70, [P(R(str(N["buy_wins"]), "big", s=30)), P(R("PNs where buying is cheaper", "small", s=8.5))])
    s.text(240, 188, 170, 70, [P(R(str(N["tat_wins"]), "big", s=30, c=C["copper"])),
                               P(R("PNs where a TAT cut is cheaper", "small", s=8.5))])
    s.text(70, 270, 340, 124, [
        P(R(f"Median annual cost per AOG h avoided: buy {fmt_aed(N['buy_med'])} vs TAT cut {fmt_aed(N['tat_med'])}.",
            "bodym", s=9.5), after=5, ls=1.1),
        P(R(f"Simulated: cutting TAT on the top 8 PNs alone gives {fmt_int(lev['aog_hours'])} AOG h/yr at "
            f"{fmt_aed(lev['capital_aed'])} capital (holdout), vs {fmt_int(N['pt']['P2']['aog_hours'])} h for P2."
            if lev else "", "bodym", s=9.5), ls=1.1),
    ])
    s.card(446, 150, 786, 248)
    s.text(468, 166, 600, 16, P(R(f"TORNADO · {rec} VS P2 NET BENEFIT · SELECTION SEEDS", "label", c=C["faint"])))
    s.chip_r(1214, 164, "SIMULATED")
    s.image(456, 186, 766, 206, CH.tornado(766, 206))
    s.card(48, 410, 760, 260)
    s.text(70, 426, 600, 16, P(R("STRESS VARIANTS · RE-PLANNED, SELECTION SEEDS", "label", c=C["faint"])))
    s.chip_r(790, 424, "SIMULATED")
    hdr = ["Variant", "P0 AOG h", "P2 AOG h", f"{rec} AOG h", f"{rec} − P2 net benefit /yr", "Rule picks"]
    cx = [70, 190, 290, 390, 500, 700]
    for c_, h_ in zip(cx, hdr):
        s.text(c_, 452, 200, 16, P(R(h_.upper(), "label", s=7.5, c=C["faint"])))
    yy = 476
    for v in (lo_v, ce_v, hi_v):
        rv_ = v["rec_vs_P2"]
        good = rv_["net_benefit_aed"] > 0
        vals = [v["variant"].replace("_", " "), fmt_int(v["P0"]["aog_hours"]), fmt_int(v["P2"]["aog_hours"]),
                fmt_int(v["I125"]["aog_hours"]),
                f"{fmt_signed(rv_['net_benefit_aed'], fmt_aed)} {ci_txt(rv_['net_benefit_ci'], lambda q: fmt_m(q, 2))}",
                v["rule_recommends"]]
        for j, (c_, t) in enumerate(zip(cx, vals)):
            col = C["ice"]
            if j == 4:
                col = C["aero_teal"] if good else C["red"]
            if j == 5 and v["rule_recommends"] != rec:
                col = C["amber"]
            s.text(c_, yy, 200, 18, P(R(t, "mono" if j else "body", s=9.5, c=col)))
        s.line(70, yy + 22, 786, yy + 22, HAIR, 0.5)
        yy += 30
    lrv = lo_v["rec_vs_P2"]
    s.text(70, yy + 6, 716, 80, P(R("Honest: ", "body", s=9.8, b=True, c=C["amber"]),
                                  R(f"if reliability is better than the central history suggests (low stress), P2 alone is "
                                    f"enough: {rec} saves {lrv['aog_reduction']:.1f} AOG h/yr "
                                    f"{ci_txt(lrv['aog_reduction_ci'], lambda q: f'{q:.1f}')} and costs "
                                    f"{fmt_aed(-lrv['net_benefit_aed'], 2)}/yr more, so the rule picks P2. Under high stress "
                                    f"it picks {hi_v['rule_recommends']}.", "bodym", s=9.8), ls=1.1))
    s.card(826, 410, 406, 260, line=blend(C["red"], C["card"], 0.45))
    s.text(848, 426, 360, 16, P(R("THE BIG CONDITION: AN AOG-DESK MARKET", "label", c=C["red"])))
    s.text(848, 450, 362, 220, [
        P(R("Every policy leans on the engine's AOG-desk emergency buy (an expedited rotable within days at a premium). "
            "Switch it off and material AOG explodes:", "bodym", s=9.5), after=8, ls=1.1),
        P(R(f"{rec}  ", "mono", s=9.5, c=C["aero_teal"]), R(f"{fmt_int(desk['central_rec_aog_hours'])} → "
                                                          f"{fmt_int(desk['rec_aog_hours'])} h/yr", "mono", s=9.5),
          after=3),
        P(R("P2    ", "mono", s=9.5, c=C["titanium"]), R(f"{fmt_int(desk['central_base_aog_hours'])} → "
                                                         f"{fmt_int(desk['base_aog_hours'])} h/yr", "mono", s=9.5),
          after=3),
        P(R(f"{base}    ", "mono", s=9.5, c=C["copper"]), R(f"{fmt_int(desk['central_p0_aog_hours'])} → "
                                                           f"{fmt_int(desk['p0_aog_hours'])} h/yr", "mono", s=9.5),
          after=8),
        P(R("The frontier is conditional on an exchange/loan market existing for each part.", "body", s=9.5), ls=1.1),
    ])
    s.footer(8, "Source: docs/data/frontier.json · lever card holdout; tornado and variants on selection seeds", total)
    S.append(s)

    # 9 — Planner actions & AOG lab --------------------------------------------------------------------------------
    ac = N["act_counts"]
    cfs = N["aog_sum"]["counterfactual"]
    s = Slide(bg=bg)
    s.header(9, "Planner actions & AOG lab", f"What the planner does on Monday: {N['n_actions']} exceptions, "
             f"{ac['by_severity']['urgent']} urgent",
             f"The action centre turns the plan into a week-{N['act_week']} inbox with evidence and an owner. The AOG lab "
             "replays every history grounding and ranks the desk's options on information available at the time.")
    s.card(48, 150, 560, 520)
    s.text(70, 166, 420, 16, P(R(f"EXCEPTIONS BY TYPE · WEEK {N['act_week']}", "label", c=C["faint"])))
    s.chip_r(590, 164, "DERIVED")
    s.image(58, 190, 540, 300, CH.actions(540, 300))
    xx = 70
    for sev, col in [("urgent", C["red"]), ("review", C["amber"]), ("info", C["slate"])]:
        s.rect(xx, 504, 10, 10, fill=col, r=2)
        s.text(xx + 16, 500, 120, 18, P(R(f"{sev} {ac['by_severity'].get(sev, 0)}", "monos", s=8.5)))
        xx += 120
    acts = N["raw"]["act"]["actions"]
    a1 = [a for a in acts if a["pn"] == N["inc"]["pn"] and a["station"] == N["inc"]["station"]] or acts
    a2 = [a for a in acts if a["severity"] == "urgent" and a["type"] != a1[0]["type"]] or acts
    s.text(70, 530, 516, 136, [
        P(R("EXAMPLES FROM THE INBOX", "label", c=C["faint"]), after=4),
        P(R(f"{a1[0]['severity'].upper()} · ", "monos", s=8, c=C["red"]), R(a1[0]["summary"], "body", s=9.5), ls=1.05,
          after=1),
        P(R(f"→ {a1[0]['recommended_action']}", "bodym", s=8.8), ls=1.05, after=6),
        P(R(f"{a2[0]['severity'].upper()} · ", "monos", s=8, c=C["red"]), R(a2[0]["summary"], "body", s=9.5), ls=1.05,
          after=1),
        P(R(f"→ {a2[0]['recommended_action']}", "bodym", s=8.8), ls=1.05)])
    s.card(632, 150, 600, 300)
    s.text(654, 166, 520, 16, P(R(f"{inc['id']} · THE DESK'S OPTIONS, RANKED", "label", c=C["faint"])))
    s.chip_r(1214, 164, "SIMULATED")
    hd = [("Option", 654), ("Wait", 930), ("AOG", 990), ("Direct cost", 1050), ("Rank", 1160)]
    for h_, x_ in hd:
        s.text(x_, 192, 120, 14, P(R(h_.upper(), "label", s=7.5, c=C["faint"])))
    yy = 212
    opts = sorted(inc["options"], key=lambda o: (o["rank"] is None, o["rank"] or 99))
    for o in opts:
        feas = o["feasible"]
        col = C["ice"] if feas else C["faint"]
        if o["rank"] == 1:
            s.rect(646, yy - 4, 578, 24, fill=blend(C["aero_teal"], C["card"], 0.12), r=4)
        s.text(654, yy, 280, 18, P(R(f"{o['key']}  ", "mono", s=9, c=C["aero_teal"] if feas else C["faint"]),
                                   R(o["option"], "body", s=9.3, c=col)))
        s.text(930, yy, 60, 18, P(R(f"{o['wait_h']:g} h" if o["wait_h"] is not None else "—", "mono", s=9, c=col)))
        s.text(990, yy, 60, 18, P(R(f"{o['aog_h']:g} h" if o["aog_h"] is not None else "—", "mono", s=9, c=col)))
        s.text(1050, yy, 110, 18, P(R(f"AED {o['direct_cost']:,}" if feas else "—", "mono", s=9, c=col)))
        s.text(1160, yy, 50, 18, P(R(str(o["rank"]) if o["rank"] else ("human" if o["human_decision"] else "n/a"),
                                     "mono", s=9, c=col)))
        yy += 27
    s.card(632, 462, 600, 208)
    s.text(654, 478, 540, 16, P(R("ACROSS ALL HISTORY GROUNDINGS (REPLAYED, NO HINDSIGHT IN THE RANKING)", "label",
                                  c=C["faint"])))
    s.text(654, 502, 170, 70, [P(R(f"{cfs['history_took_best_option']}/{cfs['requests_compared']}", "mid", s=17)),
                               P(R("requests where history already took the best option", "small", s=8), ls=1.1)])
    s.text(834, 502, 200, 60, [P(R(f"{fmt_int(cfs['actual_request_aog_h'])} → {fmt_int(cfs['best_option_request_aog_h'])} h",
                                   "mid", s=17, c=C["aero_teal"])),
                               P(R("request-level AOG hours, actual → best option (realised)", "small", s=8), ls=1.1)])
    s.text(1044, 502, 170, 70, [P(R(fmt_aed(cfs["net_exposure_saving_aed"]), "mid", s=17, c=C["copper"])),
                                P(R("net exposure saving (penalty + direct cost)", "small", s=8), ls=1.1)])
    s.text(654, 590, 556, 76, P(R(f"Robbery (cannibalisation) is never auto-recommended: it needs engineering and quality "
                                  f"approval. Where the ranked estimate was not realisable ({cfs['realised_basis_counts'].get('estimate_not_realisable', 0)} "
                                  "requests) the saving is re-costed on what could actually have happened.", "bodym",
                                  s=9.3), ls=1.1))
    s.footer(9, "Source: docs/data/actions.json, aog_lab.json · simulated history weeks 0–103", total)
    S.append(s)

    # 10 — Validation, limitations, author -------------------------------------------------------------------------
    val = N["validation"]
    L = N["limits"]
    s = Slide(bg=bg)
    s.header(10, "Validation, limitations & author", "What this shows, and what it does not",
             "A simulation of a fictional airline, built to be checked: frozen artefacts, a disclosed holdout log, "
             "reconciliation tests on every exported number, and the limits stated next to the results.")
    s.card(48, 150, 380, 520)
    s.text(70, 166, 340, 16, P(R("VALIDATION", "label", c=C["aero_teal"])))
    s.text(70, 184, 340, 56, P(R(f"{val['tests_passed']}/{val['tests_total']}", "big", s=30)))
    s.text(70, 236, 340, 30, P(R("tests passed, incl. reconciliation of every site number to outputs/", "small", s=8.5),
                               ls=1.05))
    yy = 276
    for chk in val["checks"][:7]:
        nm = chk["name"]
        s.text(70, yy, 24, 16, P(R("✓" if chk["status"] == "pass" else "!", "mono", s=10,
                                   c=C["aero_teal"] if chk["status"] == "pass" else C["amber"])))
        s.text(92, yy, 318, 46, P(R(nm, "bodym", s=8.6), ls=1.12))
        yy += 26 if len(nm) < 58 else 38
    s.card(446, 150, 400, 520, line=blend(C["amber"], C["card"], 0.4))
    s.text(468, 166, 360, 16, P(R("LIMITATIONS THAT MATTER MOST", "label", c=C["amber"])))
    lim = [
        (L[1]["title"], "Every airline number is simulated; the models are tested on a world the author designed."),
        ("AOG-desk dependence", f"Results assume an exchange/loan market: without it AOG rises to "
                                f"{fmt_int(N['desk']['rec_aog_hours'])} h/yr for {rec} (selection seeds)."),
        (L[8]["title"], "D0/D3/D10 are hypothetical urgency classes, not an operator's MEL or dispatch rules."),
        (L[16]["title"], f"The AED/AOG-hour penalty drives the stopping rule; it is a stated scenario."),
        (L[18]["title"], "Greedy additions on an analytic proxy, then re-simulated; not a proven optimum."),
        ("Scope", "A learning project on simulated data, not an approved maintenance, airworthiness or dispatch tool."),
    ]
    s.text(468, 192, 362, 420, [P(R(t + "  ", "body", s=9.6, b=True), R(d_, "bodym", s=9.3), after=8, ls=1.1)
                                for t, d_ in lim])
    s.text(468, 630, 362, 30, P(R(f"All {len(L)} numbered limitations: LIMITATIONS.md and the app's Data & Method page.",
                                  "small", s=8.3), ls=1.05))
    s.card(864, 150, 368, 520)
    s.text(886, 166, 320, 16, P(R("AUTHOR", "label", c=C["faint"])))
    s.text(886, 192, 330, 120, [P(R("Akash Gajjar", "title", s=22), after=6),
                                P(R("MSc Supply Chain Management", "body", s=11)),
                                P(R("University of Liverpool (2025)", "bodym", s=10.5), after=10),
                                ])
    s.text(886, 300, 330, 140, [P(R("GITHUB", "label", s=7.5, c=C["faint"]), after=2),
                                P(R(GITHUB_URL.replace("https://", ""), "mono", s=9), after=10),
                                P(R("LIVE APP", "label", s=7.5, c=C["faint"]), after=2),
                                P(R(LIVE_URL.replace("https://", ""), "mono", s=8.4), after=10),
                                P(R("CODE", "label", s=7.5, c=C["faint"]), after=2),
                                P(R(REPO_URL.replace("https://", ""), "mono", s=8.4))])
    s.image(876, 450, 344, 200, A["exploded-32"])
    s.footer(10, f"Source: docs/data/method.json (validation, limitations) · data build {N['meta_sha']}", total)
    S.append(s)

    notes = [
        "Title. Numbers: holdout seeds, central variant. Everything is simulated for a fictional airline.",
        "The problem: one incident, then the pattern behind it.",
        "Provenance: REAL / ASSUMED / SIMULATED / DERIVED.",
        "Forecasting: lumpy demand; honest about reliability vs Croston and the champion check.",
        "Palm: spares = pipeline. The BOM availability figure is computed from the exported Poisson pipeline distribution.",
        "Hub vs outstation: paired holdout differences.",
        "Frontier: stopping rule, recommendation, and the selection-vs-holdout gap.",
        "Levers & sensitivity: buy vs TAT, tornado, variants, AOG-desk dependence.",
        "Planner actions and the AOG lab.",
        "Validation, limitations and author.",
    ]
    for s_, n_ in zip(S, notes):
        s_.notes = n_
    return S


# --------------------------------------------------------------------------------------------------------------------
# Carousel (1080 × 1080, PDF only)
# --------------------------------------------------------------------------------------------------------------------
def build_carousel(N, A, CH, bg):
    S = []
    k = N["kpi"]
    rec, base = N["rec_id"], N["base_id"]
    aogk, fill, cap = k["aog_hours"], k["immediate_fill_rate"], k["spare_capital_aed"]
    inc = N["inc"]
    total = 7

    def frame(s, n, eyebrow):
        s.text(72, 64, 800, 22, P(R(f"{n:02d} / {total:02d} · {eyebrow.upper()}", "eyebrow", s=13)))
        s.line(72, 1000, 1008, 1000, HAIR_BG, 1)
        s.text(72, 1012, 760, 22, P(R(f"GROUNDED NO MORE · {AIRLINE} · simulated data", "small", s=10.5)))
        s.text(808, 1012, 200, 22, P(R("swipe →" if n < total else "", "label", s=10.5, c=C["aero_teal"]), al="r"))

    # 1
    s = Slide(1080, 1080, bg)
    frame(s, 1, "case study")
    s.text(72, 120, 936, 220, [P(R("A single missing part", "title", s=52, sp=-1)),
                               P(R("can ground an aircraft.", "title", s=52, sp=-1, c=C["aero_teal"]))])
    s.text(72, 300, 900, 80, P(R("I simulated a fictional airline to learn where spares should sit, and what each extra "
                                 "dirham of stock actually buys.", "lede", s=20, c=C["ice"]), ls=1.12))
    s.image(150, 400, 780, 560, A["aircraft-top"])
    s.chip(72, 940, "SIMULATED", f"SIMULATED · {AIRLINE.upper()}")
    S.append(s)

    # 2
    s = Slide(1080, 1080, bg)
    frame(s, 2, "the problem")
    s.text(72, 120, 936, 150, P(R(f"{inc['station']}, {inc['need_datetime'][11:16]} UTC: a brake is removed. "
                                  f"The shelf is empty.", "title", s=40, sp=-0.5), ls=1.1))
    s.text(72, 290, 936, 120, P(R(f"{inc['pn']} is a {inc['deadline']} part: the aircraft cannot leave without it. "
                                  f"The legacy rule keeps the whole float at {N['hub']}, so the aircraft waits "
                                  f"{inc['aog_hours']} hours for the next flight in.", "lede", s=19), ls=1.15))
    s.image(72, 420, 936, 380, A["exploded-32"])
    asum = N["aog_sum"]
    s.text(72, 830, 440, 140, [P(R(fmt_int(asum["n_incidents"]), "big", s=56, c=C["copper"])),
                               P(R("material AOG incidents in 2 simulated years", "bodym", s=16))])
    s.text(540, 830, 470, 140, [P(R(f"{fmt_int(asum['aog_hours_total'])} h", "big", s=56, c=C["copper"])),
                                P(R("aircraft on the ground, legacy rules", "bodym", s=16))])
    S.append(s)

    # 3
    rvc = N["rel_vs_croston"]
    n_rel_better = sum(1 for r in rvc if r["reliability_better"])
    from collections import Counter
    dcls = Counter(p["demand_class"] for p in N["parts"])
    s = Slide(1080, 1080, bg)
    frame(s, 3, "demand is lumpy")
    s.text(72, 120, 936, 150, P(R(f"{N['n_mostly_zero']} of {N['n_parts']} parts see no demand in most weeks.",
                                  "title", s=40, sp=-0.5), ls=1.1))
    s.image(72, 270, 936, 520, CH.adi_cv2(520, 289, compact=True))
    s.text(72, 810, 936, 170, [
        P(R("What surprised me: ", "body", s=17, b=True, c=C["amber"]),
          R((f"my reliability-based forecast beat the best Croston-family method on MASE in {n_rel_better} of {len(rvc)} "
             "part classes" if n_rel_better else
             f"my reliability-based forecast did not beat the best Croston-family method on MASE in any of the "
             f"{len(rvc)} part classes") + ", and frozen champions often lost on the holdout. So rotables are sized "
            "from removal rates and repair pipelines, not a forecast leaderboard.", "bodym", s=17), ls=1.15)])
    S.append(s)

    # 4
    bom = [x for x in N["stations"] if x["station"] == "BOM"][0]
    bp0, bp2 = bom["aog_hours_by_policy"]["P0"], bom["aog_hours_by_policy"]["P2"]
    p20 = N["paired"]["P2-P0"]
    s = Slide(1080, 1080, bg)
    frame(s, 4, "hub vs outstation")
    s.text(72, 120, 936, 130, P(R("Same money, placed differently.", "title", s=44, sp=-0.5)))
    s.text(72, 200, 936, 110, P(R(f"Pooling at the hub and stocking an outstation only where the no-go penalty pays for "
                                  f"the unit (P2) changes network spare capital by {fmt_aed(p20['spare_capital_aed']['mean'], 2)} "
                                  f"(CI spans zero) and cuts AOG by {fmt_int(-p20['aog_hours']['mean'])} h/yr.",
                                  "lede", s=19), ls=1.15))
    s.image(72, 330, 936, 570, CH.stations(600, 365))
    s.text(72, 920, 936, 60, P(R(f"BOM: {fmt_int(bp0['mean'])} → {fmt_int(bp2['mean'])} AOG h/yr", "mid", s=24,
                                 c=C["aero_teal"]), R("   holdout, 20 paired seeds", "small", s=13)))
    S.append(s)

    # 5
    r = N["pt"][rec]
    cons = N["consistency"]["aog_hours"]
    s = Slide(1080, 1080, bg)
    frame(s, 5, "the readiness frontier")
    s.text(72, 120, 936, 130, P(R("Where to stop buying spares.", "title", s=44, sp=-0.5)))
    s.text(72, 196, 936, 110, P(R(f"A rule written before the test: keep adding capital while AED 1M still removes "
                                  f"{N['reco']['h_star_per_aed_1m']:.1f}+ AOG hours a year. It stops at {rec}.", "lede",
                                  s=19), ls=1.15))
    s.image(72, 290, 936, 510, CH.frontier(560, 305, compact=True))
    s.text(72, 820, 300, 150, [P(R(f"{fmt_int(aogk['value'])} h", "big", s=36)),
                               P(R(f"AOG / yr, from {fmt_int(aogk['baseline'])} h (legacy)", "bodym", s=14))])
    s.text(390, 820, 300, 150, [P(R(fmt_signed(cap["delta"], fmt_aed), "big", s=36, c=C["copper"])),
                                P(R("more spare capital", "bodym", s=15))])
    s.text(700, 820, 310, 150, [P(R(f"{fmt_int(cons['selection_recommended'])} → {fmt_int(cons['holdout_recommended'])} h",
                                    "big", s=36, c=C["amber"])),
                                P(R("selection → holdout: I report the worse one", "bodym", s=14), ls=1.1)])
    S.append(s)

    # 6
    ac = N["act_counts"]
    lo_v = N["variants"]["low_stress"]
    s = Slide(1080, 1080, bg)
    frame(s, 6, "what a planner gets")
    s.text(72, 120, 936, 130, P(R("Monday morning, not a model.", "title", s=44, sp=-0.5)))
    s.text(72, 200, 936, 110, P(R(f"{N['n_actions']} exceptions for week {N['act_week']}, {ac['by_severity']['urgent']} "
                                  "urgent, each with evidence, an owner and a due week. Plus an AOG lab that ranks the "
                                  "desk's options for any grounding.", "lede", s=19), ls=1.15))
    s.image(72, 320, 936, 420, CH.actions(560, 251))
    s.text(72, 770, 936, 200, [
        bullet([R(f"Buying one spare beat cutting repair TAT in {N['buy_wins']} of {N['buy_wins'] + N['tat_wins']} parts "
                  "on cost per AOG hour avoided.", "bodym", s=17)], after=10, ls=1.12),
        bullet([R(f"In a low-stress world, the recommendation is not worth it: it costs "
                  f"{fmt_aed(-lo_v['rec_vs_P2']['net_benefit_aed'], 2)}/yr more than P2 for no clear AOG gain.",
                  "bodym", s=17)], ls=1.12),
    ])
    S.append(s)

    # 7
    s = Slide(1080, 1080, bg)
    frame(s, 7, "honest limits")
    s.text(72, 120, 936, 150, P(R("It is a simulation. Here is what that means.", "title", s=40, sp=-0.5), ls=1.1))
    items = [
        f"{AIRLINE} does not exist; every airline number is simulated. Station coordinates are the only real operational data.",
        "Results lean on an AOG-desk exchange market; switch it off and groundings rise by orders of magnitude.",
        "D0/D3/D10 deadline classes are my simplification, not an MEL.",
        f"{N['validation']['tests_passed']} tests, frozen artefacts and a disclosed holdout log keep me honest inside that world.",
    ]
    s.text(72, 290, 936, 440, [bullet([R(t, "bodym", s=19)], after=16, ls=1.15) for t in items])
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
    k = N["kpi"]
    aogk, fill, cap = k["aog_hours"], k["immediate_fill_rate"], k["spare_capital_aed"]
    cons = N["consistency"]["aog_hours"]
    lo = N["variants"]["low_stress"]
    inc = N["inc"]
    rvc = N["rel_vs_croston"]
    n_rel_better = sum(1 for r in rvc if r["reliability_better"])
    forecast_line = (f"my reliability-based forecast beat the classic intermittent-demand methods in {n_rel_better} of "
                     f"{len(rvc)} part classes" if n_rel_better else
                     "my reliability-based forecast did not beat the classic intermittent-demand methods (Croston, SBA, "
                     "TSB) on accuracy in any part class")
    txt = f"""<!--
DRAFT. DO NOT POST. Generated by scripts/build_deck.py from docs/data (data build {N['meta_sha']}).
Akash: edit freely, check every number against the live app before posting, and post it yourself.
Suggested attachment: presentations/linkedin_carousel.pdf (or docs/assets/readme/demo.gif).
-->

# DRAFT: LinkedIn post (not posted)

I have been teaching myself how aviation spare parts actually work, and I built a project to do it.

My background is retail inventory: forecasts, reorder points, shelves that should never be empty. Aviation materials planning looks similar until you meet a rotable. A brake assembly is not consumed, it is repaired, and the question is not "how many do we sell?" but "how many are sitting in a repair shop right now, and is one where the aircraft is?"

So I built GROUNDED NO MORE: a simulation of a fictional airline, {AIRLINE}, with a Gulf hub, {N['n_stations'] - 1} outstations, {N['nb'] + N['wb']} aircraft and {N['n_parts']} part numbers. To be clear up front: nothing in it is real operator data. The airline does not exist, the history is simulated, and every assumption is written down with a provenance tag.

A few things I learned:

1. One missing part is enough. In the simulated history, a carbon brake is removed at {inc['station']}, the shelf is empty, and the aircraft waits {inc['aog_hours']} hours for a unit from {N['hub']}. Across two simulated years the legacy rules produced {fmt_int(N['aog_sum']['n_incidents'])} groundings like that.

2. Where you hold stock matters as much as how much. Pooling at the hub and stocking an outstation only where the no-go penalty justifies it cut modelled groundings sharply for roughly the same capital.

3. Forecasting was humbling. {N['n_mostly_zero']} of the {N['n_parts']} parts see no demand at all in more than half the weeks, and {forecast_line}. Rotables ended up sized from removal rates and repair pipelines (Palm's theorem), not from a forecast leaderboard.

4. Decide where to stop before you look at the answer. I wrote the stopping rule down first, then tested on simulated futures the model had never seen. The recommended plan cuts modelled material AOG from {fmt_int(aogk['baseline'])} to {fmt_int(aogk['value'])} hours a year and lifts fill rate from {fmt_pct(fill['baseline'])} to {fmt_pct(fill['value'])}, for {fmt_aed(cap['delta'])} more spare capital. On the seeds I chose it with, it looked even better ({fmt_int(cons['selection_recommended'])} hours); I report the worse number.

5. Be honest about when it does not pay. In a lower-stress world the extra stock is not worth it (about {fmt_aed(-lo['rec_vs_P2']['net_benefit_aed'], 2)} a year more than the simpler network policy for no clear gain), and every result leans on an AOG-desk exchange market existing.

It ends in a web app a materials planner could open on a Monday morning: a ranked action list, an AOG response lab, and the capital-vs-readiness trade-off.

I would really value feedback from people who do this for real, especially on what I have oversimplified.

Live app: {LIVE_URL}
Code: {REPO_URL}

#AviationMaintenance #SupplyChain #InventoryManagement
"""
    path.write_text(txt)
    return path


# --------------------------------------------------------------------------------------------------------------------
def sanity_checks(N):
    """Cross-checks between independently exported numbers; fail loudly instead of printing a wrong slide."""
    k = N["kpi"]
    assert N["rec_id"] == "I125" and N["pt"][N["rec_id"]]["recommended"], "recommended point mismatch"
    assert abs(k["aog_hours"]["value"] - N["pt"][N["rec_id"]]["aog_hours"]) < 1e-6
    assert k["aog_hours"]["split"] == "holdout"
    # Palm example: story.json states the BOM availability for the units P2 places at BOM; ours must agree to the %.
    body = N["story"]["rotable-float-calc"]["body"]
    want = f"{round(N['palm_bom'] * 100)}% availability for the {N['s_bom']} units"
    assert want in body, f"Palm check failed: {want!r} not in story text {body!r}"


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
        print(f"deck: {OUT / 'case_study_deck.pptx'} + .pdf ({len(slides)} slides); previews {pngs[0].parent}")
    if a.only in (None, "carousel"):
        bgc = str(make_background(build / "bg-sq.png", 1080, 1080))
        cs = build_carousel(N, A, CH, bgc)
        pngs = html_to_pdf_and_png(render_html(cs, 1080, 1080), 1080, 1080, OUT / "linkedin_carousel.pdf", build,
                                   "carousel", scale=1)
        print(f"carousel: {OUT / 'linkedin_carousel.pdf'} ({len(cs)} slides)")
        print(f"post draft: {write_linkedin_post(N, OUT / 'linkedin_post.md')}")


if __name__ == "__main__":
    main()
