"""
Cryptographic utilities for SecureVPN
"""

import os
import hmac
import hashlib
from typing import Union

import nacl.utils
import nacl.hash
from nacl.encoding import RawEncoder

from ..exceptions import CryptographyError


def secure_random(length: int) -> bytes:
    """Generate cryptographically secure random bytes"""
    try:
        return nacl.utils.random(length)
    except Exception as e:
        raise CryptographyError(f"Failed to generate random bytes: {e}")


def constant_time_compare(a: Union[bytes, str], b: Union[bytes, str]) -> bool:
    """Constant-time comparison to prevent timing attacks"""
    if isinstance(a, str):
        a = a.encode('utf-8')
    if isinstance(b, str):
        b = b.encode('utf-8')
    
    return hmac.compare_digest(a, b)


def blake2s_hash(data: bytes, digest_size: int = 32) -> bytes:
    """BLAKE2s hash function"""
    try:
        return nacl.hash.blake2b(data, digest_size=digest_size, encoder=RawEncoder)
    except Exception as e:
        raise CryptographyError(f"BLAKE2s hash failed: {e}")


def hkdf_extract(salt: bytes, input_key_material: bytes) -> bytes:
    """HKDF Extract step using HMAC-SHA256"""
    if not salt:
        salt = b'\x00' * 32  # Default salt
    
    return hmac.new(salt, input_key_material, hashlib.sha256).digest()


def hkdf_expand(pseudo_random_key: bytes, info: bytes = b'', length: int = 32) -> bytes:
    """HKDF Expand step using HMAC-SHA256"""
    if length > 255 * 32:
        raise CryptographyError("HKDF expand length too large")
    
    output = b''
    counter = 1
    
    while len(output) < length:
        h = hmac.new(pseudo_random_key, info + bytes([counter]), hashlib.sha256)
        output += h.digest()
        counter += 1
    
    return output[:length]


def hkdf(input_key_material: bytes, salt: bytes = b'', info: bytes = b'', length: int = 32) -> bytes:
    """HKDF key derivation function"""
    prk = hkdf_extract(salt, input_key_material)
    return hkdf_expand(prk, info, length)


def derive_key_from_password(password: str, salt: bytes, iterations: int = 100000) -> bytes:
    """Derive key from password using PBKDF2"""
    try:
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, 32)
    except Exception as e:
        raise CryptographyError(f"Key derivation failed: {e}")


def secure_zero(data: bytearray) -> None:
    """Securely zero out memory (best effort)"""
    # This is a best-effort approach to clear sensitive data
    # In production, consider using specialized libraries like PyNaCl's utils
    for i in range(len(data)):
        data[i] = 0


def generate_session_id() -> bytes:
    """Generate a unique session identifier"""
    return secure_random(8)


def generate_salt() -> bytes:
    """Generate a cryptographic salt"""
    return secure_random(32)


def xor_bytes(a: bytes, b: bytes) -> bytes:
    """XOR two byte arrays"""
    if len(a) != len(b):
        raise CryptographyError("Byte arrays must be same length for XOR")
    
    return bytes(x ^ y for x, y in zip(a, b))


def pad_to_multiple(data: bytes, multiple: int) -> bytes:
    """Pad data to a multiple of given size using PKCS#7 padding"""
    padding_length = multiple - (len(data) % multiple)
    if padding_length == 0:
        padding_length = multiple
    
    padding = bytes([padding_length] * padding_length)
    return data + padding


def unpad_pkcs7(data: bytes) -> bytes:
    """Remove PKCS#7 padding"""
    if not data:
        raise CryptographyError("Cannot unpad empty data")
    
    padding_length = data[-1]
    if padding_length == 0 or padding_length > len(data):
        raise CryptographyError("Invalid padding")
    
    # Verify padding
    for i in range(padding_length):
        if data[-(i + 1)] != padding_length:
            raise CryptographyError("Invalid padding")
    
    return data[:-padding_length]


class SecureBuffer:
    """A buffer that attempts to clear its contents when destroyed"""
    
    def __init__(self, size: int):
        self._buffer = bytearray(size)
        self._size = size
    
    def __enter__(self):
        return self._buffer
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        secure_zero(self._buffer)
    
    def __len__(self):
        return self._size
    
    def clear(self):
        """Explicitly clear the buffer"""
        secure_zero(self._buffer)
