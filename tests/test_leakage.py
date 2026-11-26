"""Leakage boundary (docs/data_contract.md §3): downstream modules never touch the hidden truth."""
import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "gnm"
GUARDED = ["forecasting", "policy", "optim", "aog", "export"]
FORBIDDEN_MODULES = ("gnm.sim.truth", "gnm.sim.generator")
FORBIDDEN_TEXT = re.compile(r"ground_truth|gt_part_truth|GROUND_TRUTH")


def _files():
    for pkg in GUARDED:
        d = SRC / pkg
        if d.exists():
            yield from d.rglob("*.py")


def _imported(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield a.name
        elif isinstance(n, ast.ImportFrom):
            m = n.module or ""
            yield m
            for a in n.names:
                yield f"{m}.{a.name}"


def test_no_truth_imports_or_references():
    bad = []
    for f in _files():
        text = f.read_text()
        for m in _imported(ast.parse(text)):
            if any(m == x or m.startswith(x + ".") for x in FORBIDDEN_MODULES) or m in ("gnm.sim.truth", "gnm.sim.generator"):
                bad.append(f"{f.relative_to(SRC)} imports {m}")
            if m.startswith("gnm.sim") and m.split(".")[-1] in ("truth", "generator", "GroundTruth"):
                bad.append(f"{f.relative_to(SRC)} imports {m}")
        if FORBIDDEN_TEXT.search(text):
            bad.append(f"{f.relative_to(SRC)} references ground truth")
    assert not bad, bad


def test_api_exposes_no_truth():
    from gnm.sim import api
    public = [n for n in dir(api) if not n.startswith("_")]
    assert "GroundTruth" not in public and "truth" not in public
    w = api.load_world()
    assert not any("truth" in k.lower() for k in vars(w))
