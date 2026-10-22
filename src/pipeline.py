"""Pipeline: BB84 exchange, trust check, error correction, privacy amplification, key."""
import math

import numpy as np

from src import crypto_utils
from src.bb84 import run_bb84
from src.eve import intercept_resend
from src.postprocess import ReconciliationError, privacy_amplify, reconcile
from src.trust_meter import classify

N_QUBITS, N_BATCHES = 512, 4
SAMPLE_FRAC = 0.15
# Interim noise scale until noise.py is filled in: noise_level 0..1 maps to a
# channel bit-flip probability of 0..MAX_FLIP. Above ~7% the post-processing
# leaves no secret key, so 6% is the top of the usable range.
MAX_FLIP = 0.06


def _flip_prob(level):
    return MAX_FLIP * min(1.0, max(0.0, float(level)))


def using_stubs():
    """Names still served by stubs (none: every module is real now)."""
    return []


def get_expected_qber(level):
    return _flip_prob(level)


def run_exchange(noise_level, eve_on, rng=None):
    rng = rng or np.random.default_rng()
    seed = int(rng.integers(0, 2**31 - 1))
    res = run_bb84(N_QUBITS * N_BATCHES, sample_frac=SAMPLE_FRAC, seed=seed,
                   eve=intercept_resend if eve_on else None,
                   flip_prob=_flip_prob(noise_level))
    qber = res["qber"]
    n_samples = max(1, round(SAMPLE_FRAC * res["sifted_len"]))
    verdict = classify(qber, noise_level, n_samples=n_samples,
                       expected_qber_fn=_flip_prob).value

    key, final_len = None, 0
    if verdict != "compromised":
        try:
            a_fix, b_fix, leaked = reconcile(res["alice_key"], res["bob_key"],
                                             qber if qber > 0 else None, seed=seed)
        except ReconciliationError:
            a_fix, b_fix, leaked = None, None, 0
        if a_fix is not None and np.array_equal(a_fix, b_fix):
            qber_key = min(0.5, qber + 2 * math.sqrt(max(qber * (1 - qber), 0.0) / n_samples))
            final = privacy_amplify(a_fix, qber_key, leaked)
            final_len = len(final)
            if final_len > 0:
                key = crypto_utils.derive_key(final)
    return {"qber": qber, "verdict": verdict,
            "final_key_len": final_len, "key": key}


def encrypt_msg(key, text):
    return crypto_utils.encrypt(key, text)


def decrypt_msg(key, blob):
    return crypto_utils.decrypt(key, blob)
