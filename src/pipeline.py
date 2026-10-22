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
        kw["backend"] =