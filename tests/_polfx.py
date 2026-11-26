"""Shared cached fixtures for the policy tests (public history only)."""
from functools import lru_cache

import pandas as pd

from gnm.policy import forecast_pipeline as fp
from gnm.sim.api import load_world


@lru_cache(maxsize=None)
def world():
    return load_world()


@lru_cache(maxsize=None)
def history():
    return fp.load_history()


def champions() -> pd.DataFrame:
    p = fp.FC_OUT / "champions.csv"
    if p.exists():
        return pd.read_csv(p)
    cells = [(d, c) for d in ("smooth", "erratic", "intermittent", "lumpy", "insufficient_data") for c in "CER"]
    return pd.DataFrame([{"demand_class": d, "part_class": c, "champion": "sba"} for d, c in cells])


@lru_cache(maxsize=None)
def forecasts(origin: int = 104):
    return fp.final_forecasts(history(), world(), champions(), origin=origin)
