"""BB84 chat demo: key exchange, trust check, error correction, privacy amplification, then an encrypted message.

Run from the repo root:
    python -m src.chat --message "HELLO BOB"
    python -m src.chat --message "HELLO BOB" --eve
    python -m src.chat --message "HELLO BOB" --noise 0.05
"""
import argparse
import math
import sys

import numpy as np

from src.bb84 import run_bb84
from src.eve import intercept_resend
from src.postprocess import ReconciliationError, privacy_amplify, reconcile
from src.trust_meter import Trust, classify

SAMPLE_FRAC = 0.15


def to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def to_bytes(bits: np.ndarray) -> bytes:
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--message", default="HELLO BOB")
    p.add_argument("--n", type=int, default=2048, help="number of qubits Alice sends")
    p.add_argument("--noise", type=float, default=0.0, help="channel bit-flip probability")
    p.add_argument("--eve", action="store_true", help="Eve intercepts every qubit")
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args(argv)

    result = run_bb84(args.n, sample_frac=SAMPLE_FRAC, seed=args.seed,
                      eve=intercept_resend if args.eve else None,
                      flip_prob=args.noise)

    sifted = result["sifted_len"]
    n_samples = max(1, round(SAMPLE_FRAC * sifted))
    qber = result["qber"]
    # In this simulation each bit is flipped with probability `noise`, so QBER = noise.
    trust = classify(qber, args.noise, n_samples=n_samples,
                     expected_qber_fn=lambda level: level)

    print(f"qubits sent: {args.n}   sifted: {sifted}   sampled: {n_samples}")
    print(f"observed QBER: {qber:.3f}   trust: {trust.value.upper()}")

    if trust is Trust.COMPROMISED:
        print("Channel looks compromised. Key discarded, no message sent.")
        return 1

    a_key, b_key = result["alice_key"], result["bob_key"]
    mismatches = int((a_key != b_key).sum())
    print(f"key after sampling: {len(a_key)} bits, {mismatches} differ between Alice and Bob")

    # Error correction over the public channel
    try:
        a_rec, b_rec, leaked = reconcile(a_key, b_key, qber if qber > 0 else None, seed=args.seed)
    except ReconciliationError as exc:
        print("Error correction failed:", exc)
        return 3
    print(f"reconciled: keys now equal = {bool(np.array_equal(a_rec, b_rec))}, bits leaked = {leaked}")

    # Privacy amplification, using a QBER with a small safety margin for the sample size
    qber_key = min(0.5, qber + 2 * math.sqrt(max(qber * (1 - qber), 0.0) / n_samples))
    a_final = privacy_amplify(a_rec, qber_key, leaked)
    b_final = privacy_amplify(b_rec, qber_key, leaked)
    print(f"secret key length: {len(a_final)} bits (QBER used: {qber_key:.3f})")

    if not np.array_equal(a_final, b_final):
        print("Final keys differ. Aborting.")
        return 3

    bits = to_bits(args.message.encode("utf-8"))
    if len(bits) > len(a_final):
        print(f"Message needs {len(bits)} key bits but only {len(a_final)} are available. "
              f"Use a larger --n or a shorter message.")
        return 2

    cipher = bits ^ a_final[: len(bits)]
    print("Alice sends (hex):", to_bytes(cipher).hex())
    plain = to_bytes(cipher ^ b_final[: len(bits)])
    print("Bob decrypts:", plain.decode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
