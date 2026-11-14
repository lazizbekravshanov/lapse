import numpy as np

from lapse import verdict as V


def g(slope, sig, half=0.1):
    slope = np.array(slope, dtype=float)
    return {"slope": slope, "lo": slope - half, "hi": slope + half, "sig": np.array(sig, dtype=float)}


def reason(name):
    return V.R[name]


def test_not_proven_when_the_test_fails():
    v, r = V.classify(g([0.5], [0]), b=g([0.5], [1]))
    assert v[0] == V.NOT_PROVEN and r[0] == reason("fails_test")


def test_clear_needs_two_datasets_same_sign_overlapping():
    v, r = V.classify(g([0.5], [1]), alt=g([0.5], [1]), b=g([0.55], [1]))
    assert v[0] == V.CLEAR and r[0] == reason("both_agree")


def test_likely_when_sizes_differ():
    v, r = V.classify(g([0.5], [1]), b=g([1.5], [1]))
    assert v[0] == V.LIKELY and r[0] == reason("size_differs")


def test_likely_when_witness_agrees_but_is_not_proven():
    v, r = V.classify(g([0.5], [1]), b=g([0.2], [0]))
    assert v[0] == V.LIKELY and r[0] == reason("witness_agrees_weakly")


def test_likely_when_witness_is_unsure():
    v, r = V.classify(g([0.5], [1]), b=g([-0.05], [0]))
    assert v[0] == V.LIKELY and r[0] == reason("witness_unsure")


def test_likely_without_a_witness():
    v, r = V.classify(g([0.5], [1]))
    assert v[0] == V.LIKELY and r[0] == reason("no_witness")
    v, r = V.classify(g([0.5], [1]), b=g([np.nan], [np.nan]))
    assert v[0] == V.LIKELY and r[0] == reason("no_witness")


def test_disputed_when_witness_proves_the_opposite():
    v, r = V.classify(g([0.5], [1]), b=g([-0.5], [1]))
    assert v[0] == V.DISPUTED and r[0] == reason("opposite_sign")


def test_disputed_when_volcano_months_drive_it():
    v, r = V.classify(g([0.5], [1]), alt=g([0.1], [1]), b=g([0.5], [1]))      # loses 80% of its size
    assert v[0] == V.DISPUTED and r[0] == reason("event_sensitive")
    v, r = V.classify(g([0.5], [1]), alt=g([-0.1], [0]), b=g([0.5], [1]))     # sign flips
    assert v[0] == V.DISPUTED
    v, r = V.classify(g([0.5], [1]), alt=g([0.45], [0]), b=g([0.5], [1]))     # small change: still clear
    assert v[0] == V.CLEAR


def test_every_cell_gets_exactly_one_label():
    rng = np.random.default_rng(0)
    shape = (20, 30)
    a = g(rng.normal(size=shape), rng.integers(0, 2, shape))
    alt = g(a["slope"] + rng.normal(scale=0.3, size=shape), rng.integers(0, 2, shape))
    b = g(rng.normal(size=shape), rng.integers(0, 2, shape))
    b["slope"][:3] = np.nan
    a["slope"][5, 5] = np.nan
    v, r = V.classify(a, alt, b)
    assert np.isnan(v[5, 5]) and np.isnan(r[5, 5])
    rest = np.isfinite(a["slope"])
    assert set(np.unique(v[rest])) <= {0.0, 1.0, 2.0, 3.0}
    assert set(np.unique(r[rest])) <= set(float(x) for x in V.R.values())
    assert (v[rest & (a["sig"] == 0)] == V.NOT_PROVEN).all()


def test_align_levels_uses_exact_matches_only():
    b = g(np.arange(6.0).reshape(3, 2), np.ones((3, 2)))
    out = V.align_levels(b, [1000, 500, 10], [1000, 700, 10, 1])
    assert out["slope"].shape == (4, 2)
    assert (out["slope"][0] == [0, 1]).all() and (out["slope"][2] == [4, 5]).all()
    assert np.isnan(out["slope"][1]).all() and np.isnan(out["slope"][3]).all()


def test_data_source_jump_makes_it_disputed():
    a = g([0.5, 0.5], [1, 1])
    a["jump"] = np.array([True, False])
    v, r = V.classify(a, b=g([0.5, 0.5], [1, 1]))
    assert v[0] == V.DISPUTED and r[0] == reason("data_change") and v[1] == V.CLEAR


def test_a_jumping_witness_cannot_confirm():
    b = g([0.5], [1])
    b["jump"] = np.array([True])
    v, r = V.classify(g([0.5], [1]), b=b)
    assert v[0] == V.LIKELY and r[0] == reason("witness_jumps")


def test_jumps_needs_an_unusual_step_that_explains_half_the_change():
    # trend 0.5 per decade over 4 decades = 2.0 total
    assert V.jumps([0.5], 4.0, [1.2], [0.6])[0]            # unusual and 60% of the change
    assert not V.jumps([0.5], 4.0, [0.5], [0.3])[0]        # unusual but only 25%
    assert not V.jumps([0.5], 4.0, [1.2], [1.5])[0]        # big, but normal for this series
