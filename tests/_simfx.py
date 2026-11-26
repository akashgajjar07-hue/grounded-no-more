"""Shared, cached small-world fixtures for the sim tests (20 PNs, AUH + BOM)."""
from functools import lru_cache

import numpy as np

from gnm.sim.baseline import build_p0
from gnm.sim.engine import run_policy
from gnm.sim.generator import generate_scenario, generate_world, small_config

WEEKS = (0, 29)
SEED = 7


@lru_cache(maxsize=None)
def small_world():
    return generate_world(small_config())


@lru_cache(maxsize=None)
def small_scenario(seed=SEED, w0=WEEKS[0], w1=WEEKS[1]):
    w, gt = small_world()
    return generate_scenario(w, gt, seed, w0, w1)


@lru_cache(maxsize=None)
def small_run():
    w, _ = small_world()
    sc = small_scenario()
    return run_policy(w, sc, build_p0(w), WEEKS[0], WEEKS[1])


@lru_cache(maxsize=None)
def full_world():
    return generate_world()


def expected_removals(world, truth, scenario):
    """Expected removals per R/E PN from true MTBUR and the scenario's exposure (no frailty)."""
    gt = truth.parts.set_index("pn")
    fl = scenario.flights
    arch = dict(zip(world.aircraft["tail"], world.aircraft.archetype))
    fl = fl.assign(arch=fl["tail"].map(arch))
    yrs = (fl.week + 0.5) / 52.0
    out = {}
    for p in world.parts.itertuples(index=False):
        if p.part_class == "C":
            continue
        a = world.applicability[world.applicability.pn == p.pn].set_index("archetype").qty_per_aircraft
        q = fl.arch.map(a).fillna(0).to_numpy()
        expo = np.ones(len(fl)) if p.driver == "FC" else fl.fh.to_numpy()
        tr = gt.loc[p.pn, "trend_per_year"]
        tr = 1.0 if np.isnan(tr) else tr
        out[p.pn] = float((q * expo * tr ** yrs.to_numpy()).sum() / gt.loc[p.pn, "mtbur_true"])
    return out
