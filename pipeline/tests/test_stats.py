import numpy as np

from lapse import stats


def ar1(rng, n, phi):
    e = rng.standard_normal(n)
    x = np.empty(n)
    x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + np.sqrt(1 - phi * phi) * e[i]
    return x


def test_recovers_a_known_slope():
    rng = np.random.default_rng(0)
    t = np.arange(240)
    y = 0.5 * t / 120.0 + 0.3 * rng.standard_normal(240)      # 0.5 per decade
    res = stats.trend(y, t)
    assert abs(res["slope"] - 0.5) < 0.1
    assert res["lo"] < 0.5 < res["hi"]
    assert res["p"] < 0.001


def test_one_wild_month_does_not_bend_the_slope():
    rng = np.random.default_rng(1)
    t = np.arange(240)
    y = 0.5 * t / 120.0 + 0.2 * rng.standard_normal(240)
    y[10] = 50.0
    assert abs(stats.trend(y, t)["slope"] - 0.5) < 0.1


def test_false_alarm_rate_with_memory_and_no_trend():
    """Noise with month-to-month memory and NO trend should rarely be flagged."""
    rng = np.random.default_rng(2)
    t = np.arange(240)
    runs = 300
    hits = sum(stats.trend(ar1(rng, 240, 0.5), t)["p"] < 0.05 for _ in range(runs))
    assert hits / runs < 0.10        # target 5%; uncorrected test gives about 25%


def test_power_on_a_real_trend():
    rng = np.random.default_rng(3)
    t = np.arange(240)
    runs = 100
    hits = sum(stats.trend(ar1(rng, 240, 0.5) + 1.0 * t / 120.0, t)["p"] < 0.05 for _ in range(runs))
    assert hits / runs > 0.8


def test_gaps_and_nans_are_handled():
    rng = np.random.default_rng(4)
    t = np.arange(300)
    y = -0.8 * t / 120.0 + 0.3 * rng.standard_normal(300)
    y[100:124] = np.nan                                        # a masked event
    res = stats.trend(y, t)
    assert res["n"] == 276
    assert abs(res["slope"] + 0.8) < 0.1


def test_too_short_returns_nan():
    res = stats.trend(np.arange(5.0), np.arange(5))
    assert np.isnan(res["slope"]) and res["n"] == 5


def test_deseasonalize_removes_the_cycle():
    months = np.tile(np.arange(1, 13), 20)
    y = 10 * np.sin(2 * np.pi * months / 12.0) + 0.01 * np.arange(240)
    anom = stats.deseasonalize(y, months)
    assert np.abs(anom).max() < 3.0
    assert abs(np.nanmean(anom)) < 1e-9


def test_deseasonalize_relative_is_percent():
    months = np.tile(np.arange(1, 13), 10)
    y = np.full(120, 2.0)
    y[60:] = 2.2
    anom = stats.deseasonalize(y, months, relative=True)
    assert np.allclose(anom[:60], -100 * 0.1 / 2.1)


def test_bh_qvalues():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.6, np.nan])
    q = stats.bh_qvalues(p)
    assert np.isnan(q[-1])
    assert np.all(q[:5] >= p[:5])
    assert np.all(np.diff(q[:5]) >= -1e-12)
    assert np.isclose(q[0], 0.005)


def test_flip_pressure():
    levels = np.array([1000, 500, 100, 10, 1])
    slope = np.array([0.2, 0.2, 0.1, -0.1, -0.5])
    flip = stats.flip_pressure(slope, levels)
    assert 10 < flip < 100
    assert np.isnan(stats.flip_pressure(np.abs(slope), levels))
    # order of levels must not matter
    assert np.isclose(stats.flip_pressure(slope[::-1], levels[::-1]), flip)
