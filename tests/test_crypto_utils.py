from src.crypto_utils import decrypt, derive_key, encrypt
import numpy as np


def test_derive_key_is_32_bytes_and_deterministic():
    bits = np.random.default_rng(1).integers(0, 2, 100)
    assert len(derive_key(bits)) == 32
    assert derive_key(bits) == derive_key(bits.copy())


def test_encrypt_decrypt_round_trip():
    key = derive_key(np.ones(64, dtype=np.uint8))
    assert decrypt(key, encrypt(key, "HELLO BOB")) == "HELLO BOB"
