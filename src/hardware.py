import numpy as np
from qiskit import transpile
from src.bb84 import random_bits, build_circuit, sift, estimate_qber, decide


def run_chunked(bits, a_bases, b_bases, backend, chunk=5):
    """Run BB84 in small circuits (1 shot each). Returns Bob's bits."""
    n = len(bits)
    circuits = []
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        circuits.append(build_circuit(bits[s:e], a_bases[s:e], b_bases[s:e]))
    tqc = transpile(circuits, backend=backend, optimization_level=1)
    result = backend.run(tqc, shots=1).result()
    out = []
    for i in range(len(circuits)):
        bitstring = list(result.get_counts(i).keys())[0]
        out.extend(int(b) for b in reversed(bitstring.replace(" ", "")))
    return np.array(out)


def run_bb84_hardware(n, backend, sample_frac=0.15, seed=None, chunk=5):
    """Honest BB84 round on a (fake or Aer) device. Same dict as run_bb84."""
    rng = np.random.default_rng(seed)
    bits = random_bits(n, rng)
    a_bases = random_bits(n, rng)
    b_bases = random_bits(n, rng)
    bob = run_chunked(bits, a_bases, b_bases, backend, chunk)
    a_key, b_key = sift(bits, a_bases, bob, b_bases)
    full_qber = float((a_key != b_key).mean())  # error rate over the whole sifted key
    qber, a_final, b_final = estimate_qber(a_key, b_key, sample_frac, rng)
    return {
        "sifted_len": len(a_key),
        "qber": qber,
        "full_qber": full_qber,
        "verdict": decide(qber),
        "alice_key": a_final,
        "bob_key": b_final,
    }
