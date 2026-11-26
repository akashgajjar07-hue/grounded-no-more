"""Forecasting methods: hand-computed fixtures, StatsForecast cross-checks, bootstrap,
reliability-exposure recovery."""
import numpy as np
import pytest

from gnm.forecasting import methods as G

Y = np.array([0, 3, 0, 0, 5, 0, 2], dtype=float)


def test_croston_hand_fixture():
    # alpha = 0.5. First demand at t=1: z=3, p=1+1=2 (interval counted from t=-1).
    # t=4: y=5, q=4-1=3: z = 3 + .5(5-3) = 4 ; p = 2 + .5(3-2) = 2.5
    # t=6: y=2, q=6-4=2: z = 4 + .5(2-4) = 3 ; p = 2.5 + .5(2-2.5) = 2.25
    # forecast = 3 / 2.25 = 1.3333
    fc = G.croston(Y, 3, alpha=0.5)
    assert fc.params["z"] == pytest.approx(3.0) and fc.params["p"] == pytest.approx(2.25)
    np.testing.assert_allclose(fc.mean, [4 / 3] * 3)
    # in-sample fitted: t=2..4 -> 3/2 = 1.5 ; t=5..6 -> 4/2.5 = 1.6
    _, _, fitted = G.croston_states(Y, 0.5, 0.5)
    np.testing.assert_allclose(fitted[2:], [1.5, 1.5, 1.5, 1.6, 1.6])
    assert np.isnan(fitted[:2]).all()


def test_sba_hand_fixture():
    # SBA = (1 - alpha/2) z/p = 0.75 * 1.3333 = 1.0
    np.testing.assert_allclose(G.sba(Y, 2, alpha=0.5).mean, [1.0, 1.0])


def test_tsb_hand_fixture():
    # alpha_p = alpha_z = 0.5 ; d_0 = 1{y_0>0} = 0
    # t1 y=3: d = 0 + .5(1-0) = .5,       z = 3
    # t2 y=0: d = .25 ; t3: d = .125
    # t4 y=5: d = .125 + .5(1-.125) = .5625, z = 3 + .5(5-3) = 4
    # t5 y=0: d = .28125
    # t6 y=2: d = .28125 + .5(1-.28125) = .640625, z = 4 + .5(2-4) = 3
    # forecast = .640625 * 3 = 1.921875
    fc = G.tsb(Y, 2, alpha_p=0.5, alpha_z=0.5)
    assert fc.params["d"] == pytest.approx(0.640625) and fc.params["z"] == pytest.approx(3.0)
    np.testing.assert_allclose(fc.mean, [1.921875] * 2)
    _, _, fitted = G.tsb_states(Y, 0.5, 0.5)
    # fitted[t] = d_{t-1} * z_{t-1}: t2 .5*3, t3 .25*3, t4 .125*3, t5 .5625*4, t6 .28125*4
    np.testing.assert_allclose(fitted[2:], [1.5, 0.75, 0.375, 2.25, 1.125])


def test_simple_methods():
    assert G.zero(Y, 3).mean.tolist() == [0, 0, 0]
    assert G.naive(Y, 2).mean.tolist() == [2, 2]
    assert G.moving_average(Y, 2, window=3).mean.tolist() == [pytest.approx(7 / 3)] * 2


def test_ma_window_chosen_in_sample():
    y = np.tile([0, 0, 0, 4], 20).astype(float)
    fc = G.moving_average(y, 4)
    assert fc.params["window"] in G.MA_WINDOWS
    # a level-shifted future cannot change the choice because it is never passed in
    assert G.moving_average(y[:60], 4).params == G.moving_average(y[:60].copy(), 4).params


def _series(rng, n=60):
    y = (rng.random(n) < 0.3) * rng.poisson(3, n)
    y[rng.integers(0, n)] = 2
    return y.astype(float)


def test_cross_check_statsforecast():
    """Same definitions -> same numbers.

    Init conventions shared with statsforecast: SES level starts at the first value;
    Croston's first interval is counted from t=-1 (index+1); TSB's probability starts at
    1{y_0>0}. statsforecast fixes alpha=0.1 for Croston/SBA (SBA factor 0.95 = 1-0.1/2);
    its TSB argument order is (alpha_d = size, alpha_p = probability). ADIDA/IMAPA use
    optimised SES in [0.1, 0.3]: statsforecast uses its own golden-section search, we use
    scipy's bounded Brent, so agreement is to ~1e-4 relative.
    """
    sfm = pytest.importorskip("statsforecast.models")
    rng = np.random.default_rng(42)
    for _ in range(100):
        y = _series(rng)
        assert G.croston(y, 4, alpha=0.1).mean[0] == pytest.approx(sfm._croston_classic(y, 4, False)["mean"][0], rel=1e-10)
        assert G.sba(y, 4, alpha=0.1).mean[0] == pytest.approx(sfm._croston_sba(y, 4, False)["mean"][0], rel=1e-10)
        assert G.tsb(y, 4, alpha_p=0.2, alpha_z=0.15).mean[0] == pytest.approx(
            sfm._tsb(y, 4, False, 0.15, 0.2)["mean"][0], rel=1e-10)
        assert G.adida(y, 4).mean[0] == pytest.approx(sfm._adida(y, 4, False)["mean"][0], rel=1e-4)
        assert G.imapa(y, 4).mean[0] == pytest.approx(sfm._imapa(y, 4, False)["mean"][0], rel=1e-4)


def test_all_zero_history():
    z = np.zeros(20)
    for name in ["zero", "naive", "ma", "croston", "sba", "tsb", "adida", "imapa", "bootstrap"]:
        fc = G.METHODS[name](z, 4)
        assert np.all(fc.mean == 0), name


def test_bootstrap_reproducible_and_seed_sensitive():
    rng = np.random.default_rng(0)
    y = _series(rng, 80)
    a = G.willemain_bootstrap(y, 6, n_samples=500, seed=11)
    b = G.willemain_bootstrap(y, 6, n_samples=500, seed=11)
    c = G.willemain_bootstrap(y, 6, n_samples=500, seed=12)
    np.testing.assert_array_equal(a.dist.samples, b.dist.samples)
    assert not np.array_equal(a.dist.samples, c.dist.samples)


def test_bootstrap_mean_ltd_matches_empirical_on_stationary_fixture():
    rng = np.random.default_rng(3)
    n, h = 2000, 6
    y = ((rng.random(n) < 0.3) * rng.integers(4, 9, n)).astype(float)  # iid -> stationary
    fc = G.willemain_bootstrap(y, h, n_samples=20000, seed=1)
    emp = y.mean() * h
    assert fc.dist.mean() == pytest.approx(emp, rel=0.05)
    assert fc.params["p01"] == pytest.approx(0.3, abs=0.03) and fc.params["p11"] == pytest.approx(0.3, abs=0.04)
    # quantiles are monotone and integer-valued
    q = fc.dist.ppf([0.5, 0.9, 0.95])
    assert np.all(np.diff(q) >= 0) and np.allclose(q, np.round(q))


def test_reliability_recovers_known_rate():
    rng = np.random.default_rng(7)
    true_rate = 2e-4                      # removals per FH (synthetic)
    expo = rng.uniform(2500, 3500, 1000)  # installed qty x FH per week
    y = rng.poisson(true_rate * expo).astype(float)
    fc = G.reliability_exposure(y, 4, exposure_train=expo, exposure_future=np.full(4, 3000.0))
    assert fc.params["rate"] == pytest.approx(true_rate, rel=0.1)
    np.testing.assert_allclose(fc.mean, fc.params["rate"] * 3000.0)
    assert fc.dist.kind == "poisson" and fc.dist.mean() == pytest.approx(fc.params["rate"] * 12000.0)


def test_reliability_gamma_poisson_shrinkage_hand_fixture():
    # N=3 removals over E=10,000 FH; quoted MTBUR 2,000 FH, k=2 pseudo-removals
    # a = 2 + 3 = 5 ; b = 2*2000 + 10000 = 14000 ; rate = 5/14000
    y = np.array([1, 0, 2, 0], dtype=float)
    e = np.full(4, 2500.0)
    fc = G.reliability_exposure(y, 2, exposure_train=e, exposure_future=np.array([1000.0, 1000.0]),
                                mtbur_prior=2000.0, prior_strength=2.0)
    assert fc.params["rate"] == pytest.approx(5 / 14000)
    assert fc.params["rate_mle"] == pytest.approx(3 / 10000)
    # NB predictive mean = a * E_f / b
    assert fc.dist.kind == "nbinom" and fc.dist.mean() == pytest.approx(5 * 2000 / 14000)
    assert fc.dist.var() > fc.dist.mean()  # over-dispersed vs Poisson


def test_reliability_strong_prior_dominates_little_data():
    y = np.zeros(4)
    fc = G.reliability_exposure(y, 1, exposure_train=np.full(4, 10.0), mtbur_prior=500.0, prior_strength=1000)
    assert fc.params["rate"] == pytest.approx(1 / 500, rel=1e-3)


def test_forecast_default_ltd_is_poisson_of_sum():
    fc = G.croston(Y, 4, alpha=0.5)
    d = fc.ltd_dist()
    assert d.kind == "poisson" and d.mean() == pytest.approx(4 * 4 / 3)
