"""Pipeline: BB84 exchange, trust check, error correction, privacy amplification, key."""
import inspect

import numpy as np

from src.bb84 import run_bb84
from src.crypto_utils import decrypt, derive_key, encrypt
from src.postprocess import ReconciliationError, privacy_amplify, reconcile
from src.trust_meter import classify

N_QUBITS, N_BATCHES = 512, 4  # for contract-style run_bb84(n_qubits, n_batches, ...)
N_REAL = 4096                 # for run_bb84(n, ...)
SAMPLE_FRAC = 0.15
# Interim noise scale until noise.py is wired in: noise_level 0..1 maps to a
# channel bit-flip probability of 0..MAX_FLIP. Above ~7% post-processing leaves
# no secret key, so 6% is the top of the usable range.
MAX_FLIP = 0.06


def _flip_prob(level):
    return MAX_FLIP * min(1.0, max(0.0, float(level)))


def using_stubs():
    """Names still served by stubs (none: every module is real now)."""
    return []


def get_expected_qber(level):
    return _flip_prob(level)


def _call_bb84(level, eve_on, rng):
    """Call run_bb84 with only the arguments it actually accepts."""
    params = inspect.signature(run_bb84).parameters
    var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())

    def accepts(name):
        return var_kw or name in params

    kw = {}
    if "n_qubits" in params:
        kw["n_qubits"] = N_QUBITS
        if accepts("n_batches"):
            kw["n_batches"] = N_BATCHES
    else:
        kw["n"] = N_REAL

    if "backend" in params and params["backend"].default is inspect.Parameter.empty:
        from qiskit_aer import AerSimulator
        kw["backend"] = AerSimulator()

    if accepts("noise_model") and "noise_model" in params:
        from src.noise import build_noise_model
        kw["noise_model"] = build_noise_model(level)
    elif accepts("flip_prob"):
        kw["flip_prob"] = _flip_prob(level)

    if accepts("sample_frac"):
        kw["sample_frac"] = SAMPLE_FRAC

    if accepts("rng"):
        kw["rng"] = rng
    elif accepts("seed"):
        kw["seed"] = int(rng.integers(2**31 - 1))

    if eve_on:
        if not accepts("eve"):
            raise RuntimeError("run_bb84 has no 'eve' argument; Eve is not wired in yet.")
        from src.eve import intercept_resend
        kw["eve"] = intercept_resend
    elif "eve" in params:
        kw["eve"] = None

    return run_bb84(**kw)


def run_exchange(noise_level, eve_on, rng=None):
    """One full exchange. Returns qber, verdict, final_key_len, key (bytes or None)."""
    rng = np.random.default_rng() if rng is None else rng
    res = _call_bb84(noise_level, eve_on, rng)
    qber = float(res["qber"])

    info = classify(qber, noise_level)
    if not isinstance(info, dict):
        info = {"verdict": str(getattr(info, "value", info)).lower()}
    info.setdefault("expected_qber", get_expected_qber(noise_level))
    out = {
        "qber": qber,
        "verdict": info["verdict"],
        "expected_qber": info.get("expected_qber"),
        "margin": info.get("margin"),
        "final_key_len": 0,
        "key": None,
    }
    if info["verdict"] == "compromised":
        return out  # discard the key

    try:
        a_fix, _b_fix, leaked = reconcile(res["alice_key"], res["bob_key"],
                                          qber_estimate=qber,
                                          seed=int(rng.integers(0, 2**31 - 1)))
    except ReconciliationError:
        return out
    final = privacy_amplify(a_fix, qber, leaked,
                            seed=int(rng.integers(0, 2**31 - 1)))
    out["final_key_len"] = len(final)
    if len(final) > 0:
        out["key"] = derive_key(final)
    return out


def encrypt_msg(key, text):
    return encrypt(key, text)


def decrypt_msg(key, blob):
    return decrypt(key, blob)