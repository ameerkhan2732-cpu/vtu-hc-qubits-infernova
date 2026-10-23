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


def derive_key512(final_key_bits) -> bytes:
    """64-byte (512-bit) key from the privacy-amplified bits via HKDF-SHA512."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    bits = np.asarray(final_key_bits, dtype=np.uint8)
    if bits.size < 512:
        raise ValueError("final key too short for a 512-bit key")
    return HKDF(algorithm=hashes.SHA512(), length=64, salt=None,
                info=b"quantaguard-chat-v1").derive(np.packbits(bits).tobytes())


def encrypt512(key: bytes, plaintext: str) -> bytes:
    """AES-SIV (RFC 5297) with a 512-bit key. Output = nonce + ciphertext."""
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV
    nonce = os.urandom(16)
    return nonce + AESSIV(key).encrypt(plaintext.encode("utf-8"), [nonce])


def decrypt512(key: bytes, blob: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV
    return AESSIV(key).decrypt(blob[16:], [blob[:16]]).decode("utf-8")
