"""Metrics against hand fixtures."""
import math

import numpy as np
import pytest

from gnm.forecasting import metrics as M
from gnm.forecasting.methods import LTDDist

Y = [1, 0, 3]
F = [2, 2, 2]   # errors f - y = [1, 2, -1]


def test_mae_bias_cfe_pis():
    assert M.mae(Y, F) == pytest.approx(4 / 3)          # (1+2+1)/3
    assert M.bias(Y, F) == pytest.approx(2 / 3)         # (1+2-1)/3, over-forecast
    np.testing.assert_allclose(M.cumulative_error(Y, F), [1, 3, 2])
    assert M.pis(Y, F) == pytest.approx(6.0)            # 1 + 3 + 2
    # under-forecasting gives negative PIS (stock-out periods): f=0 -> CFE -1,-1,-4 -> -6
    assert M.pis(Y, [0, 0, 0]) == pytest.approx(-6.0)
    assert M.spis(Y, F, [2, 2]) == pytest.approx(3.0)
    assert math.isnan(M.spis(Y, F, [0, 0]))


def test_mase_explicit_naive_scaling():
    # training [0,2,0,4]: |2-0|,|0-2|,|4-0| -> scale = 8/3 ; MAE 4/3 -> MASE 0.5
    r = M.mase(Y, F, [0, 2, 0, 4])
    assert r.status == "ok" and r.scale == pytest.approx(8 / 3) and r.value == pytest.approx(0.5)
    # seasonal scale m=2: |0-0|, |4-2| -> 1 -> MASE 4/3
    assert M.mase(Y, F, [0, 2, 0, 4], m=2).value == pytest.approx(4 / 3)


@pytest.mark.parametrize("train", [[0, 0, 0, 0], [2, 2, 2], [5]])
def test_mase_zero_denominator_is_nan_and_flagged(train):
    r = M.mase(Y, F, train)
    assert math.isnan(r.value) and r.status == "undefined" and not math.isinf(r.value)


def test_pinball_and_coverage():
    # tau .9: y=10,q=8 -> .9*2 = 1.8 ; y=6,q=8 -> (.9-1)(-2) = .2 ; mean 1.0
    assert M.pinball([10, 6], [8, 8], 0.9) == pytest.approx(1.0)
    assert M.quantile_coverage([1, 5, 9], [4, 4, 9]) == pytest.approx(2 / 3)
    assert M.interval_coverage([1, 5, 9], [0, 6, 9], [2, 7, 9]) == pytest.approx(2 / 3)


def test_ltd_metrics_poisson():
    d = LTDDist("poisson", mu=2.0)
    out = M.ltd_metrics(3.0, d, (0.5, 0.95))
    # Poisson(2): median 2, 95% quantile 5
    assert out["ltd_q50"] == 2 and out["ltd_q95"] == 5
    assert out["cov_q50"] == 0.0 and out["cov_q95"] == 1.0
    assert out["pinball_q50"] == pytest.approx(0.5)     # .5*(3-2)
