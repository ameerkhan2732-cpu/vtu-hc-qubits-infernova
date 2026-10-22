"""Tests for src/postprocess.py: reconciliation, key length and privacy amplification."""
import numpy as np

from src.postprocess import privacy_amplify, reconcile, secure_key_length


def make_keys(n=400, every=25, seed=1):
    a = np.random.default_rng(seed).integers(0, 2, n)
    b = a.copy()
    b[::every] ^= 1
    return a, b


def test_reconcile_makes_bobs_key_equal_alices():
    a, b = make_keys()
    assert not np.array_equal(a, b)
    a_rec, b_rec, leaked = reconcile(a, b, 0.04, seed=1)
    assert np.array_equal(a_rec, a)
    assert np.array_equal(a_rec, b_rec)
    assert leaked > 0


def test_reconcile_leaves_identical_keys_equal():
    a, _ = make_keys()
    a_rec, b_rec, _ = reconcile(a, a.copy(), 0.01, seed=1)
    assert np.array_equal(a_rec, a)
    assert np.array_equal(b_rec, a)


def test_secure_key_length_is_zero_when_qber_is_too_high():
    assert secure_key_length(1000, 0.2, 500) == 0


def test_secure_key_length_shrinks_as_qber_rises():
    low = secure_key_length(1000, 0.01, 100)
    high = secure_key_length(1000, 0.05, 100)
    assert 0 < high < low <= 1000


def test_privacy_amplify_output_has_the_secure_length():
    a, b = make_keys()
    a_rec, _, leaked = reconcile(a, b, 0.04, seed=1)
    out = privacy_amplify(a_rec, 0.05, leaked)
    assert len(out) == secure_key_length(len(a_rec), 0.05, leaked)
    assert set(np.unique(out)) <= {0, 1}


def test_privacy_amplify_is_the_same_for_alice_and_bob():
    a, b = make_keys()
    a_rec, b_rec, leaked = reconcile(a, b, 0.04, seed=1)
    assert np.array_equal(privacy_amplify(a_rec, 0.05, leaked),
                          privacy_amplify(b_rec, 0.05, leaked))


def test_privacy_amplify_returns_nothing_when_no_key_is_possible():
    a, _ = make_keys()
    assert len(privacy_amplify(a, 0.2, 500)) == 0
