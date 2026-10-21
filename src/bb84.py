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
