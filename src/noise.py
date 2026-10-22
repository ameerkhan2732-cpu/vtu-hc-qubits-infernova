"""Channel noise model for QuantaGuard Chat.

expected_qber(level) is a linear model fitted to the 110 no-Eve rows of
results/sweep.csv (least squares: 0.0204 + 0.0794 * level, rounded to
0.02 + 0.08 * level). The simulated channel flips bits with this same
probability, so the fit describes the simulator, not real hardware.
"""


def build_noise_model(level):
    """No Aer noise model: the simulator applies flip_prob classically."""
    return None


def expected_qber(level):
    """Expected QBER for a noise level in [0, 1]."""
    return min(0.5, max(0.0, 0.02 + 0.08 * float(level)))
