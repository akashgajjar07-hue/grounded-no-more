"""The three portfolio notebooks are committed EXECUTED (outputs saved) and error-free.

Re-execute with: jupyter nbconvert --to notebook --execute --inplace notebooks/0*.ipynb
"""
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")

NB_DIR = Path(__file__).resolve().parents[1] / "notebooks"
NOTEBOOKS = ["01_simulation_audit.ipynb", "02_forecasting_arena.ipynb", "03_policy_and_frontier.ipynb"]
TRUTH_MARKERS = ("ground_truth", "gt_part_truth", "truth_recovery_reliability")


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_executed_without_errors(name):
    nb = nbformat.read(NB_DIR / name, as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    assert code and all(c.execution_count is not None for c in code), "notebook not executed"
    errors = [o for c in code for o in c.outputs if o.output_type == "error"]
    assert not errors, errors[0].get("evalue")
    images = sum("image/png" in o.get("data", {}) for c in code for o in c.outputs)
    assert images >= 3
    md = " ".join(c.source for c in nb.cells if c.cell_type == "markdown")
    assert "Independent educational simulation" in md


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_reads_no_hidden_truth(name):
    nb = nbformat.read(NB_DIR / name, as_version=4)
    src = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert not any(m in src for m in TRUTH_MARKERS)
