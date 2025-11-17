"""
Cryptographic layer for SecureVPN

This module implements the cryptographic primitives and protocols
used by SecureVPN, including key generation, handshake, and encryption.
"""

from .keys import KeyManager, KeyPair
from .handshake import NoiseHandshake
from .cipher import ChaCha20Poly1305Cipher, AES256GCMCipher, create_cipher
from .utils import secure_random, constant_time_compare

__all__ = [
    "KeyManager",
    "KeyPair",
    "NoiseHandshake",
    "ChaCha20Poly1305Cipher",
    "AES256GCMCipher",
    "create_cipher",
    "secure_random",
    "constant_time_compare"
]
