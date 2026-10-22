"""Key derivation and message encryption from the BB84 secret key."""
import hashlib
import os

import numpy as np


def derive_key(final_key_bits) -> bytes:
    """32-byte key from the privacy-amplified bits."""
    bits = np.asarray(final_key_bits, dtype=np.uint8)
    return hashlib.sha256(np.packbits(bits).tobytes()).digest()


def encrypt(key: bytes, plaintext: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)


def decrypt(key: bytes, blob: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key).decrypt(blob[:12], blob[12:], None).decode("utf-8")
