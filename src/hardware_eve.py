import numpy as np
from src.bb84 import random_bits, sift, estimate_qber, decide
from src.hardware import run_chunked


def run_bb84_hardware_eve(n, backend, sample_frac=0.3, seed=None, chunk=5):
    """Intercept-resend Eve, then Bob measures on the noisy device."""
    rng = np.random.default_rng(seed)
    bits = random_bits(n, rng)
    a_bases = random_bits(n, rng)
    e_bases = random_bits(n, rng)
    b_bases = random_bits(n, rng)
    # Eve's result: correct bit if her basis matches Alice's, else a coin flip
    e_bits = np.where(e_bases == a_bases, bits, random_bits(n, rng))
    # Eve resends her bit in her basis; Bob measures that on the device
    bob = run_chunked(e_bits, e_bases, b_bases, backend, chunk)
    a_key, b_key = sift(bits, a_bases, bob, b_bases)
    full_qber = float((a_key != b_key).mean())
    qber, a_final, b_final = estimate_qber(a_key, b_key, sample_frac, rng)
    return {"sifted_len": len(a_key), "qber": qber,
            "full_qber": full_qber, "verdict": decide(qber)}
