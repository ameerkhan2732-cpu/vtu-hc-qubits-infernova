"""Trust meter: classify an observed QBER as safe, noisy or compromised.

The observed QBER is compared with what the configured noise level should
produce, `noise.expected_qber(level)`, plus a tolerance, and with the ~11%
limit above which BB84 cannot yield a secret key:

    compromised   observed > min(expected + tolerance, HARD_LIMIT)
                  (more errors than the noise explains, or too many to be usable)
    noisy         not compromised, but above SAFE_QBER (errors are present
                  and explained by the noise level)
    safe          not compromised and at or below SAFE_QBER

The tolerance is `max(margin, z * sigma)`. `sigma` is the sampling standard
deviation of a QBER measured on `n_samples` bits; it is only used when
`n_samples` is given, and `margin` then acts as a floor that absorbs mismatch
between the analytic expectation and the simulation.

Limits worth knowing: an attacker who disturbs fewer bits than the tolerance
(a small intercept fraction on a short sample) is statistically
indistinguishable from noise, and noise-only runs whose QBER fluctuates above
HARD_LIMIT are flagged because such a key is unusable either way.
"""
from __future__ import annotations

import enum
import math
import warnings
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

__all__ = [
    "Trust",
    "classify",
    "tolerance",
    "calibrate_margin",
    "Calibration",
    "HARD_LIMIT",
    "DEFAULT_MARGIN",
    "DEFAULT_Z",
    "SAFE_QBER",
]

HARD_LIMIT = 0.11      # BB84 key extraction is impossible above this QBER
DEFAULT_MARGIN = 0.03  # floor for the tolerance above the expected QBER
DEFAULT_Z = 5.0        # standard deviations of sampling noise tolerated
SAFE_QBER = 0.03       # at or below this (and not compromised) the channel is "safe"


class Trust(str, enum.Enum):
    """Compares equal to its string value: Trust.SAFE == "safe"."""
    SAFE = "safe"
    NOISY = "noisy"
    COMPROMISED = "compromised"


# --------------------------------------------------------------------------- #
# noise model
# --------------------------------------------------------------------------- #
def _stub_expected_qber(level: float) -> float:
    """Placeholder until the quantum core is merged.

    Mirrors the core's noise model: bb84.run_bb84 flips each of Bob's bits with
    probability `flip_prob`, so the expected QBER equals the noise level.
    """
    return min(0.5, max(0.0, float(level)))


def _load_expected_qber() -> Callable[[float], float]:
    try:
        from src.noise import expected_qber
    except ImportError as exc:
        if exc.name not in ("src.noise", "src"):
            raise  # noise exists but one of *its* imports is missing: do not hide that
        warnings.warn(
            "src.noise is not available yet; using a stub expected_qber (QBER = flip_prob)",
            RuntimeWarning,
            stacklevel=3,
        )
        return _stub_expected_qber
    return expected_qber


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def tolerance(expected: float, n_samples: int | None = None,
              margin: float = DEFAULT_MARGIN, z: float = DEFAULT_Z) -> float:
    """How far above `expected` a noise-only QBER may plausibly land."""
    if n_samples is None:
        return margin
    if n_samples <= 0:
        raise ValueError("n_samples must be positive")
    sigma = math.sqrt(max(expected, 0.0) * (1.0 - min(expected, 1.0)) / n_samples)
    return max(margin, z * sigma)


def classify(observed_qber: float, noise_level: float, *, n_samples: int | None = None,
             margin: float = DEFAULT_MARGIN, z: float = DEFAULT_Z,
             safe_qber: float = SAFE_QBER,
             expected_qber_fn: Callable[[float], float] | None = None) -> Trust:
    """Classify a measured QBER given the noise level the channel was run at.

    Parameters
    ----------
    observed_qber : measured error rate on the sampled bits, in [0, 1].
    noise_level : passed unchanged to `noise.expected_qber`.
    n_samples : number of bits the QBER was measured on; enables the statistical
        part of the tolerance. Recommended whenever it is known.
    margin, z, safe_qber : thresholds (see module docstring).
    expected_qber_fn : override for `noise.expected_qber`, e.g. a test stub.
        Without it, `src.noise.expected_qber` is used, falling back to a stub
        (with a RuntimeWarning) while the quantum core is unmerged.
    """
    try:
        observed_qber = float(observed_qber)
    except (TypeError, ValueError):
        raise ValueError(f"observed_qber must be a number in [0, 1], got {observed_qber!r}") from None
    if not 0.0 <= observed_qber <= 1.0:  # also rejects NaN
        raise ValueError(f"observed_qber must be a number in [0, 1], got {observed_qber!r}")
    fn = expected_qber_fn if expected_qber_fn is not None else _load_expected_qber()
    expected = fn(noise_level)
    limit = min(expected + tolerance(expected, n_samples, margin, z), HARD_LIMIT)
    if observed_qber > limit:
        return Trust.COMPROMISED
    if observed_qber > safe_qber:
        return Trust.NOISY
    return Trust.SAFE


# --------------------------------------------------------------------------- #
# calibration from measured runs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Calibration:
    """Margins that satisfy 'noise-only never flagged, Eve always flagged'.

    A fixed margin m works for the supplied runs iff `lower <= m < upper`.
    """
    lower: float                      # smallest margin that never flags a noise-only run
    upper: float                      # margins must stay strictly below this to catch every Eve run
    noise_over_hard_limit: int = 0    # noise-only runs above HARD_LIMIT: flagged whatever the margin
    eve_caught_by_hard_limit: int = 0  # Eve runs above HARD_LIMIT: flagged whatever the margin

    @property
    def feasible(self) -> bool:
        return self.lower < self.upper and self.noise_over_hard_limit == 0

    @property
    def recommended(self) -> float:
        """Midpoint of the feasible range (or lower + 0.01 when Eve imposes no upper bound)."""
        if math.isinf(self.upper):
            return self.lower + 0.01
        return (self.lower + self.upper) / 2.0


def calibrate_margin(noise_runs: Iterable[Sequence[float]], eve_runs: Iterable[Sequence[float]],
                     expected_qber_fn: Callable[[float], float] | None = None) -> Calibration:
    """Find the range of fixed margins that separates measured noise-only and Eve runs.

    Each run is `(noise_level, observed_qber)`. Use this with the measured data
    in results/ (load them into those pairs) to choose `margin`.
    """
    fn = expected_qber_fn if expected_qber_fn is not None else _load_expected_qber()
    lower = 0.0
    over_limit = 0
    for level, observed in noise_runs:
        if observed > HARD_LIMIT:
            over_limit += 1
            continue
        lower = max(lower, observed - fn(level))
    upper = math.inf
    by_limit = 0
    for level, observed in eve_runs:
        if observed > HARD_LIMIT:
            by_limit += 1  # caught by the hard limit regardless of margin
            continue
        upper = min(upper, observed - fn(level))
    return Calibration(lower=lower, upper=upper, noise_over_hard_limit=over_limit,
                       eve_caught_by_hard_limit=by_limit)
