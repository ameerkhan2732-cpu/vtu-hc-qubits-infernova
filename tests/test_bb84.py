import numpy as np
from src.bb84 import (random_bits, sift, estimate_qber, run_bb84)
from src.eve import intercept_resend


def test_sift_keeps_only_matching_bases():
    a_bits = np.array([0, 1, 1, 0])
    b_bits = np.array([0, 0, 1, 1])
    a_bases = np.array([0, 1, 1, 0])
    b_bases = np.array([0, 0, 1, 1])
    a, b = sift(a_bits, a_bases, b_bits, b_bases)
    assert list(a) == [0, 1] and list(b) == [0, 1]


def test_estimate_qber_identical_keys():
    rng = np.random.default_rng(0)
    a = random_bits(1000, rng)
    q, ar, br = estimate_qber(a, a.copy(), 0.15, rng)
    assert q == 0.0 and len(ar) == len(br) == 850


def test_estimate_qber_length_mismatch_raises():
    rng = np.random.default_rng(0)
    try:
        estimate_qber(np.zeros(5), np.zeros(4), 0.15, rng)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_no_eve_gives_zero_qber_and_equal_keys():
    r = run_bb84(200, seed=1)
    assert r["qber"] == 0.0
    assert (r["alice_key"] == r["bob_key"]).all()
    assert 70 <= r["sifted_len"] <= 130


def test_same_seed_reproduces_result():
    r1 = run_bb84(200, seed=1)
    r2 = run_bb84(200, seed=1)
    assert (r1["alice_key"] == r2["alice_key"]).all()


def test_eve_raises_qber_to_about_25_percent():
    r = run_bb84(4000, seed=1, eve=intercept_resend)
    assert 0.18 < r["qber"] < 0.32
