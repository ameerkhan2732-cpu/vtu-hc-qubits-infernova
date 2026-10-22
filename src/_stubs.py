"""Fake versions of the contract functions. Delete once all modules are merged."""
import hashlib
import numpy as np


def build_noise_model(level):
    return None


def expected_qber(level):
    return 0.02 + 0.08 * float(level)


def run_bb84(n_qubits, n_batches, backend, noise_model=None, eve=False,
             rng=None, sample_frac=0.15, _level=0.0):
    rng = rng or np.random.default_rng()
    raw_len = n_qubits * n_batches
    sifted_len = raw_len // 2
    n = int(sifted_len * (1 - sample_frac))
    qber = 0.25 if eve else expected_qber(_level)
    qber = float(np.clip(qber + rng.normal(0, 0.005), 0, 1))
    alice = rng.integers(0, 2, n, dtype=np.uint8)
    flips = (rng.random(n) < qber).astype(np.uint8)
    return {"alice_key": alice, "bob_key": alice ^ flips, "qber": qber,
            "raw_len": raw_len, "sifted_len": sifted_len}


def reconcile(alice_key, bob_key):
    return alice_key.copy(), alice_key.copy(), int(0.1 * len(alice_key))


def privacy_amplify(key, qber, leaked_bits):
    n = max(0, len(key) - leaked_bits - int(len(key) * qber * 3))
    return key[:n]


def classify(observed_qber, noise_level):
    exp = expected_qber(noise_level)
    if observed_qber > 0.11:
        verdict = "compromised"
    elif exp > 0.05:
        verdict = "noisy"
    else:
        verdict = "safe"
    return {"verdict": verdict, "expected_qber": exp,
            "margin": observed_qber - exp}


def derive_key(final_key_bits):
    return hashlib.sha256(np.packbits(final_key_bits).tobytes()).digest()


def encrypt(key, plaintext):
    return b"stub:" + plaintext.encode()


def decrypt(key, blob):
    return blob[len(b"stub:"):].decode()