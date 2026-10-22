"""Tests for src/postprocess.py, using fake keys (random 0/1 arrays with flipped bits)."""
import math

import numpy as np
import pytest

from src.postprocess import (
    privacy_amplify,
    reconcile,
    secure_key_length,
    _h2,
    _toeplitz_hash,
)


def make_keys(n, n_errors, rng):
    """Alice's random key and a copy of it with exactly n_errors distinct bits flipped."""
    alice = rng.integers(0, 2, size=n, dtype=np.uint8)
    bob = alice.copy()
    if n_errors:
        bob[rng.choice(n, size=n_errors, replace=False)] ^= 1
    return alice, bob


# ----------------------------- reconcile ---------------------------------- #
def test_reconcile_makes_keys_identical_across_error_rates():
    rng = np.random.default_rng(0)
    for n in (1, 2, 3, 10, 64, 257, 1000, 4000):
        for rate in (0.0, 0.005, 0.02, 0.05, 0.08, 0.11, 0.2):
            for seed in range(5):
                alice, bob = make_keys(n, int(round(rate * n)), rng)
                alice_fixed, bob_fixed, leaked = reconcile(alice, bob, seed=seed)
                assert np.array_equal(alice_fixed, bob_fixed)
                assert np.array_equal(alice_fixed, alice)  # Alice's key is the reference
                assert isinstance(leaked, int) and leaked >= 0


def test_reconcile_with_qber_estimate():
    rng = np.random.default_rng(1)
    for q in (0.01, 0.05, 0.1):
        alice, bob = make_keys(2000, int(q * 2000), rng)
        a, b, leaked = reconcile(alice, bob, qber_estimate=q, seed=3)
        assert np.array_equal(a, b)
        assert leaked > 0


def test_reconcile_even_errors_in_one_block_are_still_found():
    # Two adjacent errors land in the same first-pass block, so that block's parity matches.
    rng = np.random.default_rng(2)
    alice = rng.integers(0, 2, size=512, dtype=np.uint8)
    bob = alice.copy()
    bob[100] ^= 1
    bob[101] ^= 1
    a, b, _ = reconcile(alice, bob, seed=0)
    assert np.array_equal(a, b)


def test_reconcile_does_not_modify_inputs():
    rng = np.random.default_rng(3)
    alice, bob = make_keys(500, 25, rng)
    alice_before, bob_before = alice.copy(), bob.copy()
    reconcile(alice, bob, seed=0)
    assert np.array_equal(alice, alice_before)
    assert np.array_equal(bob, bob_before)


def test_reconcile_accepts_lists_and_bool_arrays():
    alice = [1, 0, 1, 1, 0, 0, 1, 0] * 8
    bob = list(alice)
    bob[5] ^= 1
    a, b, _ = reconcile(alice, bob, seed=0)
    assert np.array_equal(a, b)
    a, b, _ = reconcile(np.array(alice, dtype=bool), np.array(bob, dtype=bool), seed=0)
    assert np.array_equal(a, b)


def test_reconcile_leaks_far_less_than_the_key_at_low_qber():
    rng = np.random.default_rng(4)
    n = 4000
    alice, bob = make_keys(n, int(0.02 * n), rng)
    _, _, leaked = reconcile(alice, bob, seed=0)
    assert leaked < n / 3
    # leakage grows with the error rate
    alice, bob = make_keys(n, int(0.10 * n), rng)
    _, _, leaked_high = reconcile(alice, bob, seed=0)
    assert leaked_high > leaked


def test_reconcile_identical_keys_leak_little_and_change_nothing():
    rng = np.random.default_rng(5)
    alice, _ = make_keys(1000, 0, rng)
    a, b, leaked = reconcile(alice, alice.copy(), seed=0)
    assert np.array_equal(a, alice) and np.array_equal(b, alice)
    assert leaked < 200


def test_reconcile_empty_keys():
    a, b, leaked = reconcile([], [])
    assert a.size == 0 and b.size == 0 and leaked == 0


def test_reconcile_input_validation():
    with pytest.raises(ValueError):
        reconcile([0, 1, 0], [0, 1])
    with pytest.raises(ValueError):
        reconcile([0, 1, 2], [0, 1, 0])
    with pytest.raises(ValueError):
        reconcile([[0, 1]], [[0, 1]])
    with pytest.raises(ValueError):
        reconcile([0, 1], [0, 1], verify_bits=12)


# ------------------------- privacy amplification -------------------------- #
def test_final_length_drops_as_qber_rises():
    rng = np.random.default_rng(6)
    key = rng.integers(0, 2, size=4000, dtype=np.uint8)
    qbers = [0.0, 0.01, 0.03, 0.05, 0.08, 0.10]
    lengths = [privacy_amplify(key, q, leaked_bits=100).size for q in qbers]
    assert all(x > y for x, y in zip(lengths, lengths[1:])), lengths


def test_final_length_drops_as_qber_rises_through_the_full_pipeline():
    rng = np.random.default_rng(7)
    n = 4000
    lengths = []
    for q in (0.01, 0.03, 0.05, 0.08):
        alice, bob = make_keys(n, int(q * n), rng)
        _, bob_fixed, leaked = reconcile(alice, bob, seed=0)
        lengths.append(privacy_amplify(bob_fixed, q, leaked).size)
    assert all(x > y for x, y in zip(lengths, lengths[1:])), lengths


def test_no_key_survives_beyond_the_11_percent_limit_with_ideal_reconciliation():
    n = 4000
    for q in (0.12, 0.15, 0.25):
        ideal_leak = math.ceil(n * _h2(q))
        assert secure_key_length(n, q, ideal_leak) == 0
    assert secure_key_length(n, 0.05, math.ceil(n * _h2(0.05))) > 0


def test_secure_key_length_formula():
    n, q, leaked = 1000, 0.05, 300
    expected = math.floor(n - leaked - n * _h2(q))
    assert secure_key_length(n, q, leaked) == expected
    assert secure_key_length(n, 0.0, 0) == n
    assert secure_key_length(100, 0.05, 10_000) == 0  # never negative


def test_output_has_secure_length_and_binary_values():
    rng = np.random.default_rng(8)
    key = rng.integers(0, 2, size=1500, dtype=np.uint8)
    out = privacy_amplify(key, 0.04, 400)
    assert out.size == secure_key_length(1500, 0.04, 400)
    assert out.dtype == np.uint8
    assert set(np.unique(out)) <= {0, 1}


def test_returns_empty_key_when_nothing_is_secure():
    rng = np.random.default_rng(9)
    key = rng.integers(0, 2, size=200, dtype=np.uint8)
    out = privacy_amplify(key, 0.2, 150)
    assert out.size == 0


def test_alice_and_bob_derive_the_same_final_key():
    rng = np.random.default_rng(10)
    n = 3000
    alice, bob = make_keys(n, 90, rng)
    alice_fixed, bob_fixed, leaked = reconcile(alice, bob, seed=1)
    out_a = privacy_amplify(alice_fixed, 0.03, leaked)
    out_b = privacy_amplify(bob_fixed, 0.03, leaked)
    assert out_a.size > 0
    assert np.array_equal(out_a, out_b)


def test_amplification_is_deterministic_and_sensitive_to_input_and_seed():
    rng = np.random.default_rng(11)
    key = rng.integers(0, 2, size=800, dtype=np.uint8)
    base = privacy_amplify(key, 0.03, 100)
    assert np.array_equal(base, privacy_amplify(key.copy(), 0.03, 100))
    flipped = key.copy()
    flipped[0] ^= 1
    assert not np.array_equal(base, privacy_amplify(flipped, 0.03, 100))
    assert not np.array_equal(privacy_amplify(key, 0.03, 100, seed=1),
                              privacy_amplify(key, 0.03, 100, seed=2))
    assert np.array_equal(privacy_amplify(key, 0.03, 100, seed=7),
                          privacy_amplify(key, 0.03, 100, seed=7))


def test_toeplitz_hash_matches_explicit_matrix_product():
    rng = np.random.default_rng(12)
    for n, l in ((37, 15), (64, 64), (5, 1), (100, 80)):
        x = rng.integers(0, 2, size=n, dtype=np.uint8)
        s = rng.integers(0, 2, size=n + l - 1, dtype=np.uint8)
        matrix = np.array([[s[i + j] for j in range(n)] for i in range(l)], dtype=np.int64)
        assert np.array_equal(_toeplitz_hash(x, l, s), (matrix @ x) % 2)


def test_toeplitz_hash_is_linear_over_gf2():
    rng = np.random.default_rng(13)
    n, l = 300, 120
    x = rng.integers(0, 2, size=n, dtype=np.uint8)
    y = rng.integers(0, 2, size=n, dtype=np.uint8)
    s = rng.integers(0, 2, size=n + l - 1, dtype=np.uint8)
    assert np.array_equal(_toeplitz_hash(x ^ y, l, s),
                          _toeplitz_hash(x, l, s) ^ _toeplitz_hash(y, l, s))


def test_privacy_amplify_input_validation():
    key = [0, 1] * 50
    with pytest.raises(ValueError):
        privacy_amplify(key, 0.7, 0)
    with pytest.raises(ValueError):
        privacy_amplify(key, -0.1, 0)
    with pytest.raises(ValueError):
        privacy_amplify(key, 0.05, -1)
    with pytest.raises(ValueError):
        privacy_amplify([0, 3, 1], 0.05, 0)