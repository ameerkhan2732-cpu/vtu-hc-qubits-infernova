import importlib
import inspect
import os
from functools import lru_cache

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src import _stubs

_HOME = {
    "run_bb84": "bb84", "build_noise_model": "noise", "expected_qber": "noise",
    "reconcile": "postprocess", "privacy_amplify": "postprocess",
    "classify": "trust_meter", "derive_key": "chat",
    "encrypt": "chat", "decrypt": "chat",
}
N_QUBITS, N_BATCHES = 512, 4  # used with a contract-style bb84 (or stubs)
N_REAL = 4096                  # qubits per exchange for the real run_bb84(n, ...)


def _tm_expected_qber(level):
    """Expected QBER for a noise level, from the source the Trust Meter uses."""
    try:
        from src.trust_meter import _load_expected_qber
        return float(_load_expected_qber()(level))
    except Exception:
        return 0.02 + 0.08 * float(level)


def _fb_build_noise_model(level):
    return None  # real bb84 takes flip_prob; no Aer noise model needed yet


def _fb_derive_key(final_key_bits):
    data = np.packbits(np.asarray(final_key_bits, dtype=np.uint8)).tobytes()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=b"QuantaGuard Chat").derive(data)


def _fb_encrypt(key, plaintext):
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext.encode(), None)


def _fb_decrypt(key, blob):
    return AESGCM(key).decrypt(blob[:12], blob[12:], None).decode()


_FALLBACK = {
    "expected_qber": _tm_expected_qber,
    "build_noise_model": _fb_build_noise_model,
    "derive_key": _fb_derive_key,
    "encrypt": _fb_encrypt,
    "decrypt": _fb_decrypt,
}


def _get(name):
    """Real implementation if merged, else a fallback, else a stub.
    Returns (function, is_substitute)."""
    try:
        mod = importlib.import_module(f"src.{_HOME[name]}")
        return getattr(mod, name), False
    except (ImportError, AttributeError):
        pass
    if name in _FALLBACK:
        return _FALLBACK[name], True
    return getattr(_stubs, name), True


def using_stubs():
    """Names currently served by fallbacks/stubs (the UI shows a banner)."""
    return [n for n in _HOME if _get(n)[1]]


@lru_cache(maxsize=1)
def _backend():
    try:
        from qiskit_aer import AerSimulator
        return AerSimulator()
    except ImportError:
        return None


def _call(fn, *args, **kw):
    """Call fn, passing only the optional kwargs its signature accepts."""
    params = inspect.signature(fn).parameters
    return fn(*args, **{k: v for k, v in kw.items() if k in params})


def _seed(rng):
    return int(rng.integers(0, 2**31 - 1))


def _verdict(res):
    v = res.get("verdict") if isinstance(res, dict) else res
    v = str(getattr(v, "value", v)).lower()
    if "compromis" in v or "eaves" in v:
        return "compromised"
    if "noisy" in v:
        return "noisy"
    if "safe" in v:
        return "safe"
    return "compromised"  # unknown value: fail closed


def _recon_error():
    try:
        from src.postprocess import ReconciliationError
        return ReconciliationError
    except ImportError:
        return RuntimeError


def _run_bb84(noise_level, eve_on, rng):
    fn, stub = _get("run_bb84")
    if "n_qubits" in inspect.signature(fn).parameters:  # contract signature or stub
        kw = {"_level": noise_level} if stub else {}
        return fn(N_QUBITS, N_BATCHES, _backend(),
                  noise_model=_get("build_noise_model")[0](noise_level),
                  eve=eve_on, rng=rng, **kw)
    # Real module: run_bb84(n, sample_frac, seed, backend, eve, flip_prob)
    from src.eve import intercept_resend
    return fn(N_REAL, seed=_seed(rng),
              eve=intercept_resend if eve_on else None,
              flip_prob=float(_get("expected_qber")[0](noise_level)))


def run_exchange(noise_level, eve_on, rng=None):
    rng = rng or np.random.default_rng()
    res = _run_bb84(noise_level, eve_on, rng)
    qber = float(res["qber"])

    try:
        a_fix, _b_fix, leaked = _call(_get("reconcile")[0], res["alice_key"],
                                      res["bob_key"], qber_estimate=qber, seed=_seed(rng))
    except _recon_error():
        a_fix, leaked = None, 0
    n_samples = int(res.get("sifted_len", 0) * 0.15) or None
    verdict = _verdict(_call(_get("classify")[0], qber, noise_level,
                             n_samples=n_samples, expected_qber_fn=_get("expected_qber")[0]))

    key, final_len = None, 0
    if verdict != "compromised" and a_fix is not None:
        final = _call(_get("privacy_amplify")[0], a_fix, qber, leaked,
                      seed=_seed(rng))
        final_len = len(final)
        if final_len > 0:
            key = _get("derive_key")[0](final)
    return {"qber": qber, "verdict": verdict,
            "final_key_len": final_len, "key": key}


def get_expected_qber(level):
    return float(_get("expected_qber")[0](level))


def encrypt_msg(key, text):
    return _get("encrypt")[0](key, text)


def decrypt_msg(key, blob):
    return _get("decrypt")[0](key, blob)


