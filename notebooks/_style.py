"""Shared helpers for the GROUNDED NO MORE notebooks: paths, the dark design palette, small formatters.

Palette and fonts come from docs/design/tokens.json ("Aerospace Titanium x Blueprint").
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
TOKENS = json.loads((ROOT / "docs" / "design" / "tokens.json").read_text())
C = TOKENS["color"]
MIDNIGHT, STEEL, CARD = C["midnight"], C["deep_steel"], C["card"]
TEAL, COPPER, TITANIUM, ICE = C["aero_teal"], C["copper"], C["titanium"], C["ice"]
AMBER, RED, SLATE = C["amber"], C["red"], C["slate"]
PROV = {"REAL": TEAL, "DERIVED": TITANIUM, "ASSUMED": AMBER, "SIMULATED": COPPER}
POLICY_COLORS = {"P0": SLATE, "P1": AMBER, "P2": TEAL, "I125": COPPER}  # v2: P2 is the core finding, I125 the frontier option
DISCLAIMER = ("Independent educational simulation. Not an airline system or an approved maintenance, "
              "airworthiness or dispatch tool.")


def _font_family() -> list[str]:
    """Inter when installed, else matplotlib's bundled DejaVu Sans (no missing-font warnings)."""
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    return [n for n in ("Inter", "DejaVu Sans") if n in names] or ["sans-serif"]


def apply_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": MIDNIGHT, "axes.facecolor": CARD, "savefig.facecolor": MIDNIGHT,
        "axes.edgecolor": "#2A3C50", "axes.labelcolor": TITANIUM, "axes.titlecolor": ICE,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.labelsize": 10,
        "xtick.color": TITANIUM, "ytick.color": TITANIUM, "text.color": ICE,
        "axes.grid": False, "axes.spines.top": False, "axes.spines.right": False,
        "legend.facecolor": STEEL, "legend.edgecolor": "#2A3C50", "legend.labelcolor": ICE, "legend.fontsize": 9,
        "font.family": _font_family(), "font.size": 10,
        "axes.prop_cycle": mpl.cycler(color=[TEAL, COPPER, TITANIUM, AMBER, SLATE, RED]),
        "figure.dpi": 110, "figure.figsize": (9, 4.2),
    })


def stamp(ax, text: str, tag: str = "SIMULATED") -> None:
    """Provenance chip in the lower-right corner of an axes."""
    ax.text(0.995, 0.015, f"{tag} · {text}", transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5,
            color=PROV.get(tag, TITANIUM), alpha=0.9)


def aed_m(x: float) -> str:
    return f"AED {x / 1e6:,.1f}M"


def ci(d: dict, fmt: str = "{:,.0f}", scale: float = 1.0, signed: bool = False) -> str:
    """'mean [lo, hi]' for a dict with mean + ci_lo/ci_hi (or mean + ci=[lo, hi], or *_mean/_lo/_hi columns)."""
    if "ci" in d:
        lo, hi = d["ci"]
    else:
        lo, hi = d["ci_lo"], d["ci_hi"]
    f = (lambda v: ("+" if v > 0 else "") + fmt.format(v / scale)) if signed else (lambda v: fmt.format(v / scale))
    return f"{f(d['mean'])} [{f(lo)}, {f(hi)}]"


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


apply_style()
plt.rcParams["axes.unicode_minus"] = False
