import numpy as np
from src.bb84 import build_circuit, run_circuit, random_bits

def intercept_resend(bits, alice_bases, rng, backend):
    """Full intercept-resend: Eve measures every qubit in a random basis.

    Returns (eve_bits, eve_bases). Bob then receives qubits that Eve
    re-encoded with these bits and bases.
    """
    eve_bases = random_bits(len(bits), rng)
    qc = build_circuit(bits, alice_bases, eve_bases)
    eve_bits = run_circuit(qc, backend)
    return eve_bits, eve_bases
