"""Runtime leakage check (complements the static scan in test_leakage.py).

Builds the planning artefacts (forecasts, P1/P2) with an audit hook that records every
file opened under data/ground_truth and every call into gnm.sim.truth. Planning code
must trigger none. (The generator itself may read truth to simulate reality; scenario
generation is therefore done BEFORE the hook is armed.)
"""
import sys

import pytest

from gnm.config import GROUND_TRUTH, PROCESSED


@pytest.mark.slow
def test_planning_code_never_touches_truth(monkeypatch):
    if not (PROCESSED / "history" / "part_master.parquet").exists():
        pytest.skip("history not built")
    import pandas as pd

    from gnm.policy import forecast_pipeline as fp
    from gnm.policy.policies import build_p1, build_p2
    from gnm.sim.api import load_world

    world = load_world("central")
    hist = fp.load_history()
    champs = pd.read_csv(fp.FC_OUT / "champions.csv")

    opened = []
    gt = str(GROUND_TRUTH.resolve())

    def hook(event, args):
        if event == "open" and args and isinstance(args[0], (str, bytes)) or (event == "open" and hasattr(args[0], "__fspath__")):
            p = str(args[0])
            if gt in p or "ground_truth" in p:
                opened.append(p)

    sys.addaudithook(hook)   # audit hooks cannot be removed; the list is local to this test
    import gnm.sim.truth as truth_mod
    calls = []
    for name in dir(truth_mod):
        obj = getattr(truth_mod, name)
        if callable(obj) and getattr(obj, "__module__", "") == truth_mod.__name__:
            monkeypatch.setattr(truth_mod, name, lambda *a, _n=name, **k: calls.append(_n))

    before = len(opened)
    ff = fp.final_forecasts(hist, world, champs)
    build_p1(world, ff)
    build_p2(world, ff)
    assert opened[before:] == [], f"planning code opened ground truth: {opened[before:]}"
    assert calls == [], f"planning code called gnm.sim.truth: {calls}"

# v2 rebuild (D012): exercises P1/P2 planning code on v1 forecasting outputs; skipped until v2 regeneration.
import pytest as _pytest_v2  # noqa: E402
pytestmark = [_pytest_v2.mark.v1_outputs, _pytest_v2.mark.skip(reason="awaiting v2 regeneration")]
