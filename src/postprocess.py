"""Classical post-processing for BB84: error reconciliation and privacy amplification.

Pipeline (run identically on both sides after sifting):

    alice_fixed, bob_fixed, leaked = reconcile(alice_key, bob_key)
    final_key = privacy_amplify(bob_fixed, qber, leaked)

`reconcile` is a Cascade-style protocol: block parities, binary search for the
error inside every block whose parity disagrees, several passes over reshuffled
blocks, and a back-tracking step so that a correction in a later pass re-checks
the earlier passes' blocks that contain the corrected bit.

Every bit of information announced over the public channel is counted in the
returned `leaked` figure, including the final verification tag, so it can be
subtracted honestly during privacy amplification.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

__all__ = [
    "ReconciliationError",
    "reconcile",
    "privacy_amplify",
    "secure_key_length",
]

_CASCADE_PASSES = 4          # passes before the first verification
_PROBE_BLOCK = 16            # first-pass block size when no QBER estimate is given
_VERIFY_BITS = 64            # length of the hash tag used to confirm the keys match
_MAX_EXTRA_PASSES = 20       # safety valve for the "repeat until verified" loop
_EXTRA_SIZES = (16, 8, 4, 2, 1)  # block sizes for verification-failure passes


class ReconciliationError(RuntimeError):
    """Raised when the keys still disagree after the maximum number of passes."""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _as_bits(key, name: str) -> np.ndarray:
    arr = np.asarray(key)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1-D array of bits")
    if arr.size and not np.isin(arr, (0, 1)).all():
        raise ValueError(f"{name} must contain only 0/1 values")
    return arr.astype(np.uint8)


def _h2(p: float) -> float:
    """Binary entropy in bits."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def _block_size(qber: float, n: int) -> int:
    """Cascade's first-pass block size, about 0.73 / QBER, clamped to [2, n]."""
    if qber <= 0.0:
        return max(1, n)
    return max(2, min(n, int(round(0.73 / qber))))


def _qber_from_parity_rate(rate: float, block: int) -> float:
    """Invert P(odd number of errors in a block) = (1 - (1 - 2q)^k) / 2."""
    if rate <= 0.0:
        return 0.0
    rate = min(rate, 0.49)
    return (1.0 - (1.0 - 2.0 * rate) ** (1.0 / block)) / 2.0


def _tag(bits: np.ndarray, nbytes: int) -> bytes:
    return hashlib.sha256(np.packbits(bits).tobytes()).digest()[:nbytes]


# --------------------------------------------------------------------------- #
# error reconciliation
# --------------------------------------------------------------------------- #
class _Cascade:
    """State for one reconciliation run. Alice's key is never modified."""

    def __init__(self, alice: np.ndarray, bob: np.ndarray):
        self.a = alice
        self.b = bob.copy()
        self.leaked = 0
        self.blocks: list[list[np.ndarray]] = []   # per pass: ordered index arrays
        self.block_of: list[np.ndarray] = []       # per pass: bit index -> block number
        self._announced: set[tuple[int, int]] = set()

    @staticmethod
    def _parity(key: np.ndarray, idx: np.ndarray) -> int:
        return int(key[idx].sum()) & 1

    def add_pass(self, perm: np.ndarray, size: int) -> int:
        n = self.a.size
        blocks = [perm[i:i + size] for i in range(0, n, size)]
        block_of = np.empty(n, dtype=np.int64)
        for j, idx in enumerate(blocks):
            block_of[idx] = j
        self.blocks.append(blocks)
        self.block_of.append(block_of)
        return len(self.blocks) - 1

    def _mismatch(self, p: int, j: int) -> bool:
        """Compare one block's parity; Alice's parity is announced (and counted) once."""
        if (p, j) not in self._announced:
            self._announced.add((p, j))
            self.leaked += 1
        idx = self.blocks[p][j]
        return self._parity(self.a, idx) != self._parity(self.b, idx)

    def _binary_search(self, idx: np.ndarray) -> int:
        """Locate one error in a block known to have mismatching parity."""
        while idx.size > 1:
            half = idx.size // 2
            left = idx[:half]
            self.leaked += 1  # Alice announces the parity of the left half
            if self._parity(self.a, left) != self._parity(self.b, left):
                idx = left
            else:
                idx = idx[half:]
        return int(idx[0])

    def _correct(self, p: int, j: int) -> None:
        """Fix the block, then re-check every block (in any pass) touched by a fix."""
        stack = [(p, j)]
        while stack:
            q, blk = stack.pop()
            if not self._mismatch(q, blk):
                continue
            pos = self._binary_search(self.blocks[q][blk])
            self.b[pos] ^= 1
            for r in range(len(self.blocks)):
                if r != q:
                    stack.append((r, int(self.block_of[r][pos])))

    def run_pass(self, p: int) -> int:
        """Check every block of pass p; return how many mismatched before correction."""
        mismatched = 0
        for j in range(len(self.blocks[p])):
            if self._mismatch(p, j):
                mismatched += 1
                self._correct(p, j)
        return mismatched


def reconcile(alice_key, bob_key, qber_estimate: float | None = None, *,
              seed=None, verify_bits: int = _VERIFY_BITS):
    """Make Bob's key equal to Alice's using public parity checks.

    Parameters
    ----------
    alice_key, bob_key : 1-D arrays of 0/1, same length (the sifted keys).
    qber_estimate : optional QBER estimate used to size the first blocks. If
        omitted it is estimated from the first pass's parity-mismatch rate.
    seed : seeds the block shuffles (both parties need the same shuffles; in a
        real run Alice announces the permutations).
    verify_bits : size of the hash tag exchanged at the end to confirm the keys
        match. Must be a positive multiple of 8. Counted as leaked.

    Returns
    -------
    (alice_fixed, bob_fixed, leaked_bits) with alice_fixed == bob_fixed.
    `leaked_bits` counts every parity and tag bit announced publicly.

    Raises
    ------
    ReconciliationError if the keys still differ after the maximum number of passes.
    """
    a = _as_bits(alice_key, "alice_key")
    b = _as_bits(bob_key, "bob_key")
    if a.size != b.size:
        raise ValueError(f"key lengths differ: {a.size} vs {b.size}")
    if verify_bits <= 0 or verify_bits % 8:
        raise ValueError("verify_bits must be a positive multiple of 8")
    n = a.size
    if n == 0:
        return a.copy(), b.copy(), 0

    rng = np.random.default_rng(seed)
    st = _Cascade(a, b)

    # Pass 0 uses the natural order; later passes shuffle and double the block size.
    first = _block_size(qber_estimate, n) if qber_estimate is not None else min(n, _PROBE_BLOCK)
    st.add_pass(np.arange(n), first)
    mismatched = st.run_pass(0)
    if qber_estimate is None:
        rate = mismatched / len(st.blocks[0])
        qber_estimate = _qber_from_parity_rate(rate, first)
    base = _block_size(qber_estimate, n)

    for p in range(1, _CASCADE_PASSES):
        st.add_pass(rng.permutation(n), min(n, base * 2 ** p))
        st.run_pass(p)

    # Confirm with a hash tag. If it fails (an even number of errors hid in every
    # block so far), run extra shuffled passes with ever smaller blocks. The last
    # size, 1, announces every bit, so the loop is guaranteed to end with equal keys.
    nbytes = verify_bits // 8
    for extra in range(_MAX_EXTRA_PASSES + 1):
        st.leaked += verify_bits
        if _tag(st.a, nbytes) == _tag(st.b, nbytes):
            return a.copy(), st.b, st.leaked
        size = _EXTRA_SIZES[min(extra, len(_EXTRA_SIZES) - 1)]
        p = st.add_pass(rng.permutation(n), min(n, size))
        st.run_pass(p)

    raise ReconciliationError(  # unreachable unless something is badly wrong
        f"keys still differ after {_CASCADE_PASSES + _MAX_EXTRA_PASSES} passes")


# --------------------------------------------------------------------------- #
# privacy amplification
# --------------------------------------------------------------------------- #
def secure_key_length(n: int, qber: float, leaked_bits: int) -> int:
    """Bits of secret key left after reconciliation and privacy amplification.

    Asymptotic BB84 (Shor-Preskill style) estimate:

        l = n - leaked_bits - n * h2(qber)

    `leaked_bits` is what error correction revealed; n * h2(qber) is the
    privacy-amplification cost of the phase errors implied by the QBER. With
    ideal reconciliation (leaked = n * h2(qber)) this is n * (1 - 2 * h2(qber)),
    which reaches zero at the well-known ~11% QBER limit. Finite-key penalties
    are not included. Returns 0 when no secret key can be extracted.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if not 0.0 <= qber <= 0.5:
        raise ValueError("qber must be in [0, 0.5]")
    if leaked_bits < 0:
        raise ValueError("leaked_bits must be non-negative")
    length = n - leaked_bits - n * _h2(qber)
    return max(0, math.floor(length + 1e-9))


def _toeplitz_hash(key: np.ndarray, out_len: int, seed_bits: np.ndarray) -> np.ndarray:
    """Multiply `key` by the out_len x n Toeplitz matrix T[i, j] = seed_bits[i + j] over GF(2).

    Computed with an FFT correlation, so it stays fast for long keys.
    """
    n = key.size
    if seed_bits.size != n + out_len - 1:
        raise ValueError("seed_bits must have n + out_len - 1 entries")
    # y[i] = sum_j s[i + j] * x[j]  ==  conv(s, reversed x)[n - 1 + i]
    nfft = 1 << (seed_bits.size + n - 2).bit_length()
    prod = np.fft.irfft(np.fft.rfft(seed_bits.astype(np.float64), nfft)
                        * np.fft.rfft(key[::-1].astype(np.float64), nfft), nfft)
    y = np.rint(prod[n - 1:n - 1 + out_len]).astype(np.int64)
    return (y & 1).astype(np.uint8)


def _seed_rng(seed, key: np.ndarray) -> np.random.Generator:
    if seed is None:
        material = b"bb84-privacy-amplification" + key.size.to_bytes(8, "big") \
            + np.packbits(key).tobytes()
    elif isinstance(seed, bytes):
        material = seed
    else:
        material = repr(seed).encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(material).digest()[:16], "big"))


def privacy_amplify(key, qber: float, leaked_bits: int, seed=None) -> np.ndarray:
    """Hash the reconciled key down to its secure length with a Toeplitz hash.

    The output length is `secure_key_length(len(key), qber, leaked_bits)`, so it
    shrinks as the QBER rises and is empty when no secret key can be extracted.

    Alice and Bob must apply the same hash. By default the Toeplitz matrix is
    derived from the (identical) reconciled key, so no seed needs to be sent;
    pass an explicit `seed` (int or bytes) to use public randomness instead, as
    a real deployment would, where Alice picks a fresh seed and announces it.
    """
    bits = _as_bits(key, "key")
    out_len = secure_key_length(bits.size, qber, leaked_bits)
    if out_len == 0:
        return np.zeros(0, dtype=np.uint8)
    rng = _seed_rng(seed, bits)
    seed_bits = rng.integers(0, 2, size=bits.size + out_len - 1, dtype=np.uint8)
    return _toeplitz_hash(bits, out_len, seed_bits)
