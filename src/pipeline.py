import importlib
import numpy as np
from src import _stubs

_HOME = {
    "run_bb84": "bb84", "build_noise_model": "noise", "expected_qber": "noise",
    "reconcile": "postprocess", "privacy_amplify": "postprocess",
    "classify": "trust_meter", "derive_key": "chat",
    "encrypt": "chat", "decrypt": "chat",
}
N_QUBITS, N_BATCHES = 512, 4  # tune once the real bb84 is merged


def _get(name):
    """Real implementation if merged, else stub."""
    try:
        mod = importlib.import_module(f"src.{_HOME[name]}")
        return getattr(mod, name), False
    except (ImportError, AttributeError):
        return getattr(_stubs, name), True


def using_stubs():
    """Names currently served by stubs (the UI can show a banner)."""
    return [n for n in _HOME if _get(n)[1]]


def _backend():
    try:
        from qiskit_aer import AerSimulator
        return AerSimulator()
    except ImportError:
        return None


def run_exchange(noise_level, eve_on, rng=None):
    rng = rng or np.random.default_rng()
    run_bb84, stub = _get("run_bb84")
    kwargs = {"_level": noise_level} if stub else {}
    res = run_bb84(N_QUBITS, N_BATCHES, _backend(),
                   noise_model=_get("build_noise_model")[0](noise_level),
                   eve=eve_on, rng=rng, **kwargs)
    qber = res["qber"]

    a_fix, _b_fix, leaked = _get("reconcile")[0](res["alice_key"], res["bob_key"])
    verdict = _get("classify")[0](qber, noise_level)["verdict"]

    key, final_len = None, 0
    if verdict != "compromised":
        final = _get("privacy_amplify")[0](a_fix, qber, leaked)
        final_len = len(final)
        if final_len > 0:
            key = _get("derive_key")[0](final)
    return {"qber": qber, "verdict": verdict,
            "final_key_len": final_len, "key": key}


def get_expected_qber(level):
    return _get("expected_qber")[0](level)


def encrypt_msg(key, text):
    return _get("encrypt")[0](key, text)


def decrypt_msg(key, blob):
    return _get("decrypt")[0](key, blob)
