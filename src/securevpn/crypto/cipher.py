"""
Encryption ciphers for SecureVPN

Implements ChaCha20Poly1305 and AES-256-GCM ciphers with
authenticated encryption and additional data (AEAD).
"""

import struct
from abc import ABC, abstractmethod
from typing import Tuple, Optional

import nacl.secret
import nacl.utils
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305, AESGCM
from cryptography.exceptions import InvalidTag

from ..exceptions import CryptographyError


class BaseCipher(ABC):
    """Base class for all ciphers"""
    
    @abstractmethod
    def encrypt(self, plaintext: bytes, nonce: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Encrypt plaintext with authenticated encryption"""
        pass
    
    @abstractmethod
    def decrypt(self, ciphertext: bytes, nonce: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Decrypt ciphertext with authentication verification"""
        pass
    
    @abstractmethod
    def generate_nonce(self) -> bytes:
        """Generate a random nonce"""
        pass
    
    @property
    @abstractmethod
    def key_size(self) -> int:
        """Required key size in bytes"""
        pass
    
    @property
    @abstractmethod
    def nonce_size(self) -> int:
        """Required nonce size in bytes"""
        pass


class ChaCha20Poly1305Cipher(BaseCipher):
    """ChaCha20Poly1305 AEAD cipher implementation"""
    
    def __init__(self, key: bytes):
        """
        Initialize cipher with key
        
        Args:
            key: 32-byte encryption key
        """
        if len(key) != 32:
            raise CryptographyError("ChaCha20Poly1305 requires 32-byte key")
        
        try:
            self._cipher = ChaCha20Poly1305(key)
        except Exception as e:
            raise CryptographyError(f"Failed to initialize ChaCha20Poly1305: {e}")
    
    def encrypt(self, plaintext: bytes, nonce: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Encrypt plaintext with ChaCha20Poly1305"""
        if len(nonce) != 12:
            raise CryptographyError("ChaCha20Poly1305 requires 12-byte nonce")
        
        try:
            return self._cipher.encrypt(nonce, plaintext, associated_data)
        except Exception as e:
            raise CryptographyError(f"Encryption failed: {e}")
    
    def decrypt(self, ciphertext: bytes, nonce: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Decrypt ciphertext with ChaCha20Poly1305"""
        if len(nonce) != 12:
            raise CryptographyError("ChaCha20Poly1305 requires 12-byte nonce")
        
        try:
            return self._cipher.decrypt(nonce, ciphertext, associated_data)
        except InvalidTag:
            raise CryptographyError("Authentication verification failed")
        except Exception as e:
            raise CryptographyError(f"Decryption failed: {e}")
    
    def generate_nonce(self) -> bytes:
        """Generate 12-byte random nonce"""
        return nacl.utils.random(12)
    
    @property
    def key_size(self) -> int:
        return 32
    
    @property
    def nonce_size(self) -> int:
        return 12


class AES256GCMCipher(BaseCipher):
    """AES-256-GCM AEAD cipher implementation"""
    
    def __init__(self, key: bytes):
        """
        Initialize cipher with key
        
        Args:
            key: 32-byte encryption key
        """
        if len(key) != 32:
            raise CryptographyError("AES-256-GCM requires 32-byte key")
        
        try:
            self._cipher = AESGCM(key)
        except Exception as e:
            raise CryptographyError(f"Failed to initialize AES-256-GCM: {e}")
    
    def encrypt(self, plaintext: bytes, nonce: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Encrypt plaintext with AES-256-GCM"""
        if len(nonce) != 12:
            raise CryptographyError("AES-256-GCM requires 12-byte nonce")
        
        try:
            return self._cipher.encrypt(nonce, plaintext, associated_data)
        except Exception as e:
            raise CryptographyError(f"Encryption failed: {e}")
    
    def decrypt(self, ciphertext: bytes, nonce: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Decrypt ciphertext with AES-256-GCM"""
        if len(nonce) != 12:
            raise CryptographyError("AES-256-GCM requires 12-byte nonce")
        
        try:
            return self._cipher.decrypt(nonce, ciphertext, associated_data)
        except InvalidTag:
            raise CryptographyError("Authentication verification failed")
        except Exception as e:
            raise CryptographyError(f"Decryption failed: {e}")
    
    def generate_nonce(self) -> bytes:
        """Generate 12-byte random nonce"""
        return nacl.utils.random(12)
    
    @property
    def key_size(self) -> int:
        return 32
    
    @property
    def nonce_size(self) -> int:
        return 12


class SessionCipher:
    """Session-based cipher with counter-based nonces and key rotation"""
    
    def __init__(self, cipher: BaseCipher, session_id: bytes):
        """
        Initialize session cipher
        
        Args:
            cipher: Base cipher implementation
            session_id: 8-byte session identifier
        """
        self.cipher = cipher
        self.session_id = session_id[:8]  # Ensure 8 bytes
        self._send_counter = 0
        self._recv_counter = 0
        self._recv_window = set()  # For replay protection
        self._window_size = 1000
    
    def encrypt_packet(self, plaintext: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt packet with session-based nonce
        
        Returns:
            Tuple of (nonce, ciphertext)
        """
        # Create nonce: session_id (8 bytes) + counter (4 bytes)
        nonce = self.session_id + struct.pack('>I', self._send_counter)
        
        # Encrypt with session_id as associated data
        ciphertext = self.cipher.encrypt(plaintext, nonce, self.session_id)
        
        self._send_counter += 1
        if self._send_counter >= 2**32:
            raise CryptographyError("Send counter overflow - key rotation required")
        
        return nonce, ciphertext
    
    def decrypt_packet(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """
        Decrypt packet with replay protection
        
        Args:
            nonce: 12-byte nonce (session_id + counter)
            ciphertext: Encrypted data
            
        Returns:
            Decrypted plaintext
        """
        if len(nonce) != 12:
            raise CryptographyError("Invalid nonce length")
        
        # Extract counter from nonce
        packet_session_id = nonce[:8]
        counter = struct.unpack('>I', nonce[8:])[0]
        
        # Verify session ID
        if packet_session_id != self.session_id:
            raise CryptographyError("Invalid session ID")
        
        # Replay protection
        if counter in self._recv_window:
            raise CryptographyError("Replay attack detected")
        
        # Check if counter is too old
        if counter < self._recv_counter - self._window_size:
            raise CryptographyError("Packet too old")
        
        # Decrypt with session_id as associated data
        plaintext = self.cipher.decrypt(ciphertext, nonce, self.session_id)
        
        # Update receive window
        self._recv_window.add(counter)
        if len(self._recv_window) > self._window_size:
            # Remove oldest entries
            min_counter = min(self._recv_window)
            self._recv_window.discard(min_counter)
        
        # Update receive counter
        if counter > self._recv_counter:
            self._recv_counter = counter
        
        return plaintext
    
    def reset_counters(self) -> None:
        """Reset counters for key rotation"""
        self._send_counter = 0
        self._recv_counter = 0
        self._recv_window.clear()


def create_cipher(cipher_name: str, key: bytes) -> BaseCipher:
    """
    Factory function to create cipher instances
    
    Args:
        cipher_name: Name of the cipher ('chacha20poly1305' or 'aes256gcm')
        key: Encryption key
        
    Returns:
        Cipher instance
    """
    cipher_name = cipher_name.lower()
    
    if cipher_name == "chacha20poly1305":
        return ChaCha20Poly1305Cipher(key)
    elif cipher_name == "aes256gcm":
        return AES256GCMCipher(key)
    else:
        raise CryptographyError(f"Unsupported cipher: {cipher_name}")
