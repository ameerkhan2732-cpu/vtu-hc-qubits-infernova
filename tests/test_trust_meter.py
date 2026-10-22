"""Tests for src/trust_meter.py, with a stub standing in for noise.expected_qber."""
import numpy as np
import pytest

from src.trust_meter import (
    DEFAULT_MARGIN,
    HARD_LIMIT,
    Trust,
    calibrate_margin,
    classify,
    tolerance,
)


def expected(level):
    """Stub for noise.expected_qber: level is a depolarising probability, QBER = level / 2."""
    return level / 2


def run(observed, level, **kw):
    return classify(observed, level, expected_qber_fn=expected, **kw)


def eve_qber(e):
    """Full intercept-resend adds 25% errors on sifted bits on top of channel noise e."""
    return 0.25 + 0.5 * e


# ----------------------------- basic classes ------------------------------ #
def test_classes_compare_equal_to_strings():
    assert run(0.0, 0.0) == "safe"
    assert run(0.05, 0.1) == "noisy"
    assert run(0.25, 0.0) == "compromised"
    assert Trust.SAFE.value == "safe"


def test_clean_channel_is_safe():
    assert run(0.0, 0.0) is Trust.SAFE
    assert run(0.01, 0.0) is Trust.SAFE


def test_qber_matching_a_noisy_channel_is_noisy_not_compromised():
    # level 0.1 -> expected 0.05; observed right at expectation
    assert run(0.05, 0.1) is Trust.NOISY
    assert run(0.07, 0.1) is Trust.NOISY       # within expected + margin (0.08)
    assert run(0.02, 0.1) is Trust.SAFE        # lucky low sample


def test_excess_over_expected_plus_margin_is_compromised():
    assert run(0.05 + DEFAULT_MARGIN + 0.005, 0.1) is Trust.COMPROMISED
    assert run(0.04, 0.0) is Trust.COMPROMISED  # clean channel, 4% errors: not explained


def test_hard_limit_overrides_a_generous_expectation():
    # expected 0.10, +margin would allow 0.13, but 0.12 is above the ~11% limit
    assert run(0.105, 0.2) is Trust.NOISY
    assert run(0.12, 0.2) is Trust.COMPROMISED
    assert run(HARD_LIMIT + 0.001, 0.2) is Trust.COMPROMISED


def test_boundaries_are_inclusive_on_the_safe_side():
    assert run(0.05 + DEFAULT_MARGIN - 1e-9, 0.1) is Trust.NOISY
    assert run(0.03, 0.0) is Trust.SAFE


def test_n_samples_widens_tolerance_for_short_samples():
    # 200 bits at expected 4%: sigma ~1.4%, 5 sigma ~7% -> tolerance well above the 3% floor
    assert tolerance(0.04, n_samples=200) > 0.06
    assert run(0.10, 0.08, n_samples=200) is Trust.NOISY
    assert run(0.10, 0.08) is Trust.COMPROMISED  # same numbers with the fixed margin: flagged
    # with a huge sample the floor takes over
    assert tolerance(0.04, n_samples=10**7) == DEFAULT_MARGIN


def test_default_margin_and_hard_limit_values():
    assert HARD_LIMIT == 0.11
    assert tolerance(0.05) == DEFAULT_MARGIN


def test_input_validation():
    with pytest.raises(ValueError):
        run(-0.01, 0.0)
    with pytest.raises(ValueError):
        run(1.5, 0.0)
    with pytest.raises(ValueError):
        run(float("nan"), 0.0)
    with pytest.raises(ValueError):
        run("high", 0.0)
    with pytest.raises(ValueError):
        tolerance(0.05, n_samples=0)


def test_numpy_scalars_are_accepted():
    assert run(np.float32(0.0), 0.0) is Trust.SAFE
    assert run(np.float64(0.25), 0.0) is Trust.COMPROMISED



LEVELS = [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12]
N_SAMPLES = 2000
TRIALS = 2000


def sample_qber(p, rng):
    return rng.binomial(N_SAMPLES, p, size=TRIALS) / N_SAMPLES


def test_noise_only_runs_never_flag_an_attack():
    rng = np.random.default_rng(2024)
    for level in LEVELS:
        for obs in sample_qber(expected(level), rng):
            assert run(obs, level, n_samples=N_SAMPLES) is not Trust.COMPROMISED, (level, obs)


def test_eve_runs_always_flag_an_attack():
    rng = np.random.default_rng(2025)
    for level in LEVELS:
        for obs in sample_qber(eve_qber(expected(level)), rng):
            assert run(obs, level, n_samples=N_SAMPLES) is Trust.COMPROMISED, (level, obs)


def test_eve_is_also_caught_with_the_fixed_margin_and_no_sample_size():
    rng = np.random.default_rng(2026)
    for level in LEVELS:
        for obs in sample_qber(eve_qber(expected(level)), rng):
            assert run(obs, level) is Trust.COMPROMISED, (level, obs)


def test_half_intercepting_eve_is_still_caught_at_this_sample_size():
    rng = np.random.default_rng(2027)
    for level in LEVELS:
        e = expected(level)
        p = e + 0.5 * 0.25 * (1 - 2 * e)
        for obs in sample_qber(p, rng):
            assert run(obs, level, n_samples=N_SAMPLES) is Trust.COMPROMISED, (level, obs)


def test_calibrate_margin_finds_the_separating_range():
    noise = [(0.0, 0.004), (0.1, 0.061), (0.1, 0.044), (0.04, 0.026)]
    eve = [(0.0, 0.24), (0.1, 0.27), (0.04, 0.26), (0.0, 0.06)]
    cal = calibrate_margin(noise, eve, expected_qber_fn=expected)
    assert abs(cal.lower - 0.011) < 1e-9
    assert abs(cal.upper - 0.06) < 1e-9
    assert cal.feasible
    assert cal.lower <= cal.recommended < cal.upper
    assert cal.eve_caught_by_hard_limit == 3


def test_recommended_margin_classifies_the_calibration_runs_correctly():
    rng = np.random.default_rng(5)
    levels = rng.choice([0.0, 0.04, 0.08, 0.12], size=300)
    noise = [(l, float(np.clip(expected(l) + rng.normal(0, 0.006), 0, 1))) for l in levels]
    eve = [(l, float(np.clip(eve_qber(expected(l)) + rng.normal(0, 0.01), 0, 1))) for l in levels]
    cal = calibrate_margin(noise, eve, expected_qber_fn=expected)
    assert cal.feasible
    for level, obs in noise:
        assert run(obs, level, margin=cal.recommended) is not Trust.COMPROMISED
    for level, obs in eve:
        assert run(obs, level, margin=cal.recommended) is Trust.COMPROMISED


def test_calibrate_margin_reports_overlap_as_infeasible():
    noise = [(0.0, 0.08)]
    eve = [(0.0, 0.05)]
    cal = calibrate_margin(noise, eve, expected_qber_fn=expected)
    assert cal.lower > cal.upper
    assert not cal.feasible


def test_calibrate_margin_flags_noise_runs_above_the_hard_limit():
    cal = calibrate_margin([(0.2, 0.13), (0.0, 0.0)], [(0.0, 0.25)], expected_qber_fn=expected)
    assert cal.noise_over_hard_limit == 1
    assert not cal.feasible
    assert cal.eve_caught_by_hard_limit == 1


def test_calibrate_margin_with_only_hard_limit_eve_runs_has_no_upper_bound():
    cal = calibrate_margin([(0.0, 0.01)], [(0.0, 0.25)], expected_qber_fn=expected)
    assert cal.upper == float("inf")
    assert cal.recommended > cal.lower
