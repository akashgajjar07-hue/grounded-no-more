"""Poisson ROP, EBO and availability against SciPy and hand-computed values."""
import numpy as np
import pytest
from scipy import stats

from gnm.policy import analytic as A


@pytest.mark.parametrize("mu", [0.3, 1.0, 2.0, 4.7, 12.0])
@pytest.mark.parametrize("S", [0, 1, 2, 3, 5, 9])
def test_ebo_matches_scipy_definition(mu, S):
    x = np.arange(0, 200)
    ref = float(np.sum(np.maximum(x - S, 0) * stats.poisson.pmf(x, mu)))
    assert A.ebo(S, mu) == pytest.approx(ref, abs=1e-9)


@pytest.mark.parametrize("mu", [0.3, 2.0, 7.5])
@pytest.mark.parametrize("S", [0, 1, 4])
def test_availability_matches_scipy(mu, S):
    assert A.availability(S, mu) == pytest.approx(stats.poisson.cdf(S - 1, mu), abs=1e-12)


def test_hand_example():
    # lambda = 2 removals / 30 d, TAT 30 d -> mu = 2. P(X=0)=e^-2=0.135335
    mu = A.pipeline_mean(2, 30)
    assert mu == 2
    assert A.availability(1, mu) == pytest.approx(np.exp(-2), rel=1e-9)
    # EBO(0)=2 ; EBO(1)=2-1+P0 = 1.135335
    assert A.ebo(0, mu) == pytest.approx(2.0)
    assert A.ebo(1, mu) == pytest.approx(1 + np.exp(-2), rel=1e-9)


def test_ebo_convex_decreasing():
    c = A.ebo_curve(3.2, 15)
    d = np.diff(c)
    assert (d <= 1e-12).all()
    assert (np.diff(d) >= -1e-12).all()   # convex -> marginal analysis optimal per item


def test_reorder_point_poisson_and_nb():
    assert A.reorder_point(4.0, 0.95) == stats.poisson.ppf(0.95, 4.0)
    n, p = A.nb_params(4.0, 10.0)
    assert A.reorder_point(4.0, 0.95, 10.0) == stats.nbinom.ppf(0.95, n, p)
    assert A.reorder_point(4.0, 0.95, 10.0) >= A.reorder_point(4.0, 0.95)
    assert A.reorder_point(0, 0.99) == 0


def test_compare_levers_costs():
    r = A.compare_levers(2, 30, 2, 100000, 10, 1, 400)
    assert r["extra_spares"]["incremental_capital_aed"] == 100000
    assert r["tat_cut"]["incremental_annual_aed"] == pytest.approx(2 * 365 / 30 * 10 * 400)
    assert r["tat_cut"]["pipeline_mean"] < r["base"]["pipeline_mean"]
