import numpy as np
import pytest
from cryptography.exceptions import InvalidTag

from src.crypto_utils import decrypt512, derive_key512, encrypt512


def _key(n=600, seed=1):
    bits = np.random.default_rng(seed).integers(0, 2, n)
    return derive_key512(bits)


def test_key_is_512_bits():
    assert len(_key()) == 64


def test_round_trip():
    k = _key()
    assert decrypt512(k, encrypt512(k, "HELLO BOB")) == "HELLO BOB"


def test_short_key_is_refused():
    with pytest.raises(ValueError):
        derive_key512(np.zeros(300, dtype=np.uint8))


def test_tampering_is_detected():
    k = _key()
    blob = bytearray(encrypt512(k, "HELLO BOB"))
    blob[-1] ^= 1
    with pytest.raises(InvalidTag):
        decrypt512(k, bytes(blob))


def test_wrong_key_fails():
    blob = encrypt512(_key(seed=1), "HELLO BOB")
    with pytest.raises(InvalidTag):
        decrypt512(_key(seed=2), blob)
