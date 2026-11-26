"""Config loading and the split calendar."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "assumptions.yaml"
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
GROUND_TRUTH = DATA / "ground_truth"      # hidden: truth-recovery evaluation only
HOLDOUT = DATA / "holdout"                # sealed until freeze
OUTPUTS = ROOT / "outputs"
SITE_DATA = ROOT / "docs" / "data"

HOURS_PER_WEEK = 168


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _rng(pair):
    return list(range(pair[0], pair[1] + 1))


def calendar() -> dict:
    c = load_config()["calendar"]
    return {
        "train_weeks": tuple(c["train_weeks"]),
        "selection_weeks": tuple(c["selection_weeks"]),
        "history_weeks": tuple(c["history_weeks"]),
        "evaluation_weeks": tuple(c["evaluation_weeks"]),
        "warmup_weeks": c["warmup_weeks"],
    }


def seeds() -> dict:
    s = load_config()["seeds"]
    return {
        "world": s["world_seed"],
        "history": s["history_seed"],
        "selection": _rng(s["selection_seeds"]),
        "holdout": _rng(s["holdout_seeds"]),
    }


def week_to_h(week: int) -> int:
    return int(week) * HOURS_PER_WEEK


def h_to_week(h) -> int:
    return int(h) // HOURS_PER_WEEK


def flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def _walk(node: dict, prefix: str, prov: str, rationale, rows: list) -> None:
    """Flatten with inherited provenance. A nested `provenance` key overrides its parent;
    sibling keys named `<x>_provenance` / `<x>_rationale` annotate key `<x>`."""
    prov = node.get("provenance", prov)
    rationale = node.get("rationale", rationale)
    annot = {k[: -len("_provenance")]: v for k, v in node.items() if k.endswith("_provenance")}
    annot_r = {k[: -len("_rationale")]: v for k, v in node.items() if k.endswith("_rationale")}

    def _own(k):
        return annot.get(k, prov), annot_r.get(k, rationale)

    for k, v in node.items():
        if k in ("provenance", "rationale") or k.endswith("_provenance") or k.endswith("_rationale"):
            continue
        key = f"{prefix}.{k}"
        p, r = _own(k)
        if isinstance(v, dict):
            _walk(v, key, p, r, rows)
        else:
            rows.append({"key": key, "value": json.dumps(v), "provenance": p, "rationale": r})


def assumption_register():
    """Flatten the YAML into the assumption_register table (key, value, provenance, rationale)."""
    import pandas as pd

    cfg = load_config()
    rows = []
    for section, body in cfg.items():
        if not isinstance(body, dict) or section == "planted_situations":
            continue
        _walk(body, section, body.get("provenance", "ASSUMED"), body.get("rationale"), rows)
    if isinstance(cfg.get("planted_situations"), dict):
        for ps in cfg["planted_situations"]["items"]:
            rows.append({"key": f"planted_situations.{ps['id']}", "value": json.dumps(ps["description"]),
                         "provenance": "SIMULATED", "rationale": "Documented demo situation"})
    return pd.DataFrame(rows)
