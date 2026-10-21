import numpy as np
from qiskit import QuantumCircuit


def random_bits(n, rng):
    """n random 0/1 values."""
    return rng.integers(0, 2, size=n)


def build_circuit(bits, alice_bases, bob_bases):
    """One circuit, n qubits. Basis 0 = Z, basis 1 = X."""
    n = len(bits)
    qc = QuantumCircuit(n, n)
    # Alice encodes
    for i in range(n):
        if bits[i] == 1:
            qc.x(i)
        if alice_bases[i] == 1:
            qc.h(i)
    qc.barrier()  # Eve and channel noise go here later
    # Bob measures
    for i in range(n):
        if bob_bases[i] == 1:
            qc.h(i)
        qc.measure(i, i)
    return qc


def run_circuit(qc, backend):
    """Run once (1 shot) and return Bob's bits as a numpy array."""
    result = backend.run(qc, shots=1).result()
    bitstring = list(result.get_counts().keys())[0]
    # Qiskit prints the highest qubit first, so reverse it
    return np.array([int(b) for b in reversed(bitstring.replace(" ", ""))])


def sift(alice_bits, alice_bases, bob_bits, bob_bases):
    """Keep only the positions where both bases match."""
    keep = alice_bases == bob_bases
    return alice_bits[keep], bob_bits[keep]

def estimate_qber(alice_key, bob_key, sample_frac, rng):
    """Publicly compare a random sample of the sifted key.

    Returns (qber, alice_rest, bob_rest). The sampled bits are removed,
    because they were revealed.
    """
    alice_key = np.asarray(alice_key)
    bob_key = np.asarray(bob_key)
    n = len(alice_key)
    if n != len(bob_key):
        raise ValueError("alice_key and bob_key must have the same length")
    if n == 0:
        raise ValueError("empty key: nothing to sample")
    k = min(n, max(1, int(round(sample_frac * n))))
    idx = rng.choice(n, size=k, replace=False)
    keep = np.ones(n, dtype=bool)
    keep[idx] = False
    qber = float(np.mean(alice_key[idx] != bob_key[idx]))
    return qber, alice_key[keep], bob_key[keep]

if __name__ == "__main__":
    from qiskit_aer import AerSimulator
    rng = np.random.default_rng(1)
    n = 20
    bits = random_bits(n, rng)
    a_bases = random_bits(n, rng)
    b_bases = random_bits(n, rng)
    qc = build_circuit(bits, a_bases, b_bases)
    bob = run_circuit(qc, AerSimulator())
    a_key, b_key = sift(bits, a_bases, bob, b_bases)
    print(len(a_key), "sifted bits; mismatches:", int((a_key != b_key).sum()))
