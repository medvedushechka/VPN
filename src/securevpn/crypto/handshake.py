"""
Noise Protocol Framework implementation for SecureVPN

Implements a WireGuard-like handshake protocol based on Noise_IKpsk2
pattern with additional obfuscation and Perfect Forward Secrecy.
"""

import struct
import time
from enum import Enum
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

import nacl.public
import nacl.secret
import nacl.utils
import nacl.hash
from nacl.encoding import RawEncoder

from .keys import KeyPair, KeyManager
from .cipher import ChaCha20Poly1305Cipher, create_cipher
from .utils import secure_random, constant_time_compare, hkdf_expand
from ..exceptions import HandshakeError, CryptographyError


class HandshakeState(Enum):
    """Handshake state machine states"""
    INIT = "init"
    SENT_INITIATION = "sent_initiation"
    RECEIVED_INITIATION = "received_initiation"
    SENT_RESPONSE = "sent_response"
    RECEIVED_RESPONSE = "received_response"
    ESTABLISHED = "established"
    FAILED = "failed"


@dataclass
class HandshakeMessage:
    """Handshake message structure"""
    message_type: int
    sender_index: int
    data: bytes
    timestamp: float = None
    
    def serialize(self) -> bytes:
        """Serialize message to bytes"""
        timestamp_bytes = struct.pack('>Q', int(time.time() * 1000))  # milliseconds
        header = struct.pack('>BII', self.message_type, self.sender_index, len(self.data))
        return header + timestamp_bytes + self.data
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'HandshakeMessage':
        """Deserialize message from bytes"""
        if len(data) < 17:  # 1 + 4 + 4 + 8 minimum
            raise HandshakeError("Invalid message length")
        
        message_type, sender_index, data_len = struct.unpack('>BII', data[:9])
        timestamp = struct.unpack('>Q', data[9:17])[0] / 1000.0  # Convert to seconds
        
        if len(data) != 17 + data_len:
            raise HandshakeError("Message length mismatch")
        
        return cls(
            message_type=message_type,
            sender_index=sender_index,
            data=data[17:],
            timestamp=timestamp
        )


class NoiseHandshake:
    """Noise Protocol Framework handshake implementation"""
    
    # Message types
    MSG_INITIATION = 1
    MSG_RESPONSE = 2
    MSG_COOKIE_REPLY = 3
    MSG_TRANSPORT = 4
    
    # Protocol constants
    CONSTRUCTION = b"Noise_IKpsk2_25519_ChaChaPoly_BLAKE2s"
    IDENTIFIER = b"SecureVPN_v1"
    LABEL_MAC1 = b"mac1----"
    LABEL_COOKIE = b"cookie--"
    
    def __init__(self, key_manager: KeyManager, is_initiator: bool, 
                 peer_public_key: Optional[bytes] = None, preshared_key: Optional[bytes] = None):
        """
        Initialize handshake
        
        Args:
            key_manager: Key manager instance
            is_initiator: True if this is the initiator
            peer_public_key: Peer's static public key (32 bytes)
            preshared_key: Optional preshared key for additional security
        """
        self.key_manager = key_manager
        self.is_initiator = is_initiator
        self.peer_public_key = peer_public_key
        self.preshared_key = preshared_key or b'\x00' * 32
        
        # Handshake state
        self.state = HandshakeState.INIT
        self.local_index = struct.unpack('>I', secure_random(4))[0]
        self.remote_index: Optional[int] = None
        
        # Noise state variables
        self.chaining_key = self.CONSTRUCTION
        self.hash_value = self._hash(self.CONSTRUCTION + self.IDENTIFIER)
        
        # Ephemeral keys
        self.ephemeral_private: Optional[nacl.public.PrivateKey] = None
        self.ephemeral_public: Optional[nacl.public.PublicKey] = None
        self.remote_ephemeral: Optional[nacl.public.PublicKey] = None
        
        # Session keys
        self.sending_key: Optional[bytes] = None
        self.receiving_key: Optional[bytes] = None
        
        # Timestamps for replay protection
        self.last_initiation_time = 0
        self.last_response_time = 0
        
    def _hash(self, data: bytes) -> bytes:
        """BLAKE2s hash function"""
        return nacl.hash.blake2b(data, digest_size=32, encoder=RawEncoder)
    
    def _hmac(self, key: bytes, data: bytes) -> bytes:
        """HMAC using BLAKE2s"""
        if len(key) > 32:
            key = self._hash(key)
        elif len(key) < 32:
            key = key + b'\x00' * (32 - len(key))
        
        ipad = bytes(x ^ 0x36 for x in key)
        opad = bytes(x ^ 0x5c for x in key)
        
        return self._hash(opad + self._hash(ipad + data))
    
    def _hkdf(self, chaining_key: bytes, input_key_material: bytes) -> Tuple[bytes, bytes]:
        """HKDF key derivation"""
        temp_key = self._hmac(chaining_key, input_key_material)
        output1 = self._hmac(temp_key, b'\x01')
        output2 = self._hmac(temp_key, output1 + b'\x02')
        return output1, output2
    
    def _mix_hash(self, data: bytes) -> None:
        """Mix data into hash"""
        self.hash_value = self._hash(self.hash_value + data)
    
    def _mix_key(self, input_key_material: bytes) -> None:
        """Mix key material into chaining key"""
        self.chaining_key, temp_key = self._hkdf(self.chaining_key, input_key_material)
    
    def _encrypt_and_hash(self, key: bytes, plaintext: bytes) -> bytes:
        """Encrypt plaintext and mix into hash"""
        if len(key) == 0:
            # No encryption, just return plaintext
            self._mix_hash(plaintext)
            return plaintext
        
        cipher = ChaCha20Poly1305Cipher(key)
        nonce = b'\x00' * 12  # Zero nonce for handshake
        ciphertext = cipher.encrypt(plaintext, nonce, self.hash_value)
        self._mix_hash(ciphertext)
        return ciphertext
    
    def _decrypt_and_hash(self, key: bytes, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext and mix into hash"""
        if len(key) == 0:
            # No decryption, just return ciphertext
            self._mix_hash(ciphertext)
            return ciphertext
        
        cipher = ChaCha20Poly1305Cipher(key)
        nonce = b'\x00' * 12  # Zero nonce for handshake
        plaintext = cipher.decrypt(ciphertext, nonce, self.hash_value)
        self._mix_hash(ciphertext)
        return plaintext
    
    def create_initiation(self) -> bytes:
        """Create handshake initiation message"""
        if self.state != HandshakeState.INIT:
            raise HandshakeError("Invalid state for initiation")
        
        if not self.peer_public_key:
            raise HandshakeError("Peer public key required for initiation")
        
        # Generate ephemeral key pair
        self.ephemeral_private = nacl.public.PrivateKey.generate()
        self.ephemeral_public = self.ephemeral_private.public_key
        
        # Initialize Noise state
        self.chaining_key = self.CONSTRUCTION
        self.hash_value = self._hash(self.CONSTRUCTION + self.IDENTIFIER)
        
        # Mix peer's public key
        peer_key = nacl.public.PublicKey(self.peer_public_key)
        self._mix_hash(bytes(peer_key))
        
        # Mix ephemeral public key
        self._mix_hash(bytes(self.ephemeral_public))
        
        # DH with peer's static key
        static_keypair = self.key_manager.get_current_keypair()
        if not static_keypair or not static_keypair.private_key:
            raise HandshakeError("No static private key available")
        
        dh1 = self.key_manager.derive_shared_secret(peer_key)
        self._mix_key(dh1)
        
        # Encrypt static public key
        encrypted_static = self._encrypt_and_hash(
            self.chaining_key[:32], 
            bytes(static_keypair.public_key)
        )
        
        # DH with ephemeral and peer's static
        box = nacl.public.Box(self.ephemeral_private, peer_key)
        dh2 = bytes(box._shared_key)
        self._mix_key(dh2)
        
        # Mix preshared key
        self._mix_key(self.preshared_key)
        
        # Encrypt timestamp
        timestamp = struct.pack('>Q', int(time.time() * 1000))
        encrypted_timestamp = self._encrypt_and_hash(self.chaining_key[:32], timestamp)
        
        # Build message
        message_data = (
            bytes(self.ephemeral_public) +  # 32 bytes
            encrypted_static +              # 32 + 16 bytes
            encrypted_timestamp             # 8 + 16 bytes
        )
        
        message = HandshakeMessage(
            message_type=self.MSG_INITIATION,
            sender_index=self.local_index,
            data=message_data
        )
        
        self.state = HandshakeState.SENT_INITIATION
        self.last_initiation_time = time.time()
        
        return message.serialize()
    
    def process_initiation(self, message_data: bytes) -> bytes:
        """Process handshake initiation message"""
        if self.state != HandshakeState.INIT:
            raise HandshakeError("Invalid state for processing initiation")
        
        try:
            message = HandshakeMessage.deserialize(message_data)
        except Exception as e:
            raise HandshakeError(f"Failed to deserialize message: {e}")
        
        if message.message_type != self.MSG_INITIATION:
            raise HandshakeError("Expected initiation message")
        
        if len(message.data) != 104:  # 32 + 48 + 24
            raise HandshakeError("Invalid initiation message length")
        
        # Extract components
        ephemeral_public_bytes = message.data[:32]
        encrypted_static = message.data[32:80]
        encrypted_timestamp = message.data[80:104]
        
        # Initialize Noise state
        self.chaining_key = self.CONSTRUCTION
        self.hash_value = self._hash(self.CONSTRUCTION + self.IDENTIFIER)
        
        # Get our static key
        static_keypair = self.key_manager.get_current_keypair()
        if not static_keypair or not static_keypair.private_key:
            raise HandshakeError("No static private key available")
        
        # Mix our public key
        self._mix_hash(bytes(static_keypair.public_key))
        
        # Mix peer's ephemeral public key
        self.remote_ephemeral = nacl.public.PublicKey(ephemeral_public_bytes)
        self._mix_hash(ephemeral_public_bytes)
        
        # DH with peer's ephemeral
        dh1 = self.key_manager.derive_shared_secret(self.remote_ephemeral)
        self._mix_key(dh1)
        
        # Decrypt peer's static public key
        peer_static_bytes = self._decrypt_and_hash(self.chaining_key[:32], encrypted_static)
        peer_static_key = nacl.public.PublicKey(peer_static_bytes)
        
        # Verify peer's static key if we have it
        if self.peer_public_key and peer_static_bytes != self.peer_public_key:
            raise HandshakeError("Peer static key mismatch")
        
        self.peer_public_key = peer_static_bytes
        
        # DH with peer's static
        box = nacl.public.Box(static_keypair.private_key, peer_static_key)
        dh2 = bytes(box._shared_key)
        self._mix_key(dh2)
        
        # Mix preshared key
        self._mix_key(self.preshared_key)
        
        # Decrypt and verify timestamp
        timestamp_bytes = self._decrypt_and_hash(self.chaining_key[:32], encrypted_timestamp)
        timestamp = struct.unpack('>Q', timestamp_bytes)[0] / 1000.0
        
        # Check timestamp (allow 60 second skew)
        current_time = time.time()
        if abs(current_time - timestamp) > 60:
            raise HandshakeError("Timestamp too old or too far in future")
        
        self.remote_index = message.sender_index
        self.state = HandshakeState.RECEIVED_INITIATION
        
        return self.create_response()
    
    def create_response(self) -> bytes:
        """Create handshake response message"""
        if self.state != HandshakeState.RECEIVED_INITIATION:
            raise HandshakeError("Invalid state for response")
        
        # Generate ephemeral key pair
        self.ephemeral_private = nacl.public.PrivateKey.generate()
        self.ephemeral_public = self.ephemeral_private.public_key
        
        # Mix ephemeral public key
        self._mix_hash(bytes(self.ephemeral_public))
        
        # DH operations
        if not self.remote_ephemeral:
            raise HandshakeError("No remote ephemeral key")
        
        # DH: ephemeral-ephemeral
        box = nacl.public.Box(self.ephemeral_private, self.remote_ephemeral)
        dh1 = bytes(box._shared_key)
        self._mix_key(dh1)
        
        # DH: ephemeral-static (peer's ephemeral, our static)
        static_keypair = self.key_manager.get_current_keypair()
        box2 = nacl.public.Box(static_keypair.private_key, self.remote_ephemeral)
        dh2 = bytes(box2._shared_key)
        self._mix_key(dh2)
        
        # Mix preshared key again
        self._mix_key(self.preshared_key)
        
        # Encrypt empty payload (just for authentication)
        encrypted_empty = self._encrypt_and_hash(self.chaining_key[:32], b'')
        
        # Derive session keys
        self._derive_session_keys()
        
        # Build message
        message_data = bytes(self.ephemeral_public) + encrypted_empty
        
        message = HandshakeMessage(
            message_type=self.MSG_RESPONSE,
            sender_index=self.local_index,
            data=message_data
        )
        
        self.state = HandshakeState.SENT_RESPONSE
        self.last_response_time = time.time()
        
        return message.serialize()
    
    def process_response(self, message_data: bytes) -> None:
        """Process handshake response message"""
        if self.state != HandshakeState.SENT_INITIATION:
            raise HandshakeError("Invalid state for processing response")
        
        try:
            message = HandshakeMessage.deserialize(message_data)
        except Exception as e:
            raise HandshakeError(f"Failed to deserialize message: {e}")
        
        if message.message_type != self.MSG_RESPONSE:
            raise HandshakeError("Expected response message")
        
        if len(message.data) != 48:  # 32 + 16
            raise HandshakeError("Invalid response message length")
        
        # Extract components
        ephemeral_public_bytes = message.data[:32]
        encrypted_empty = message.data[32:48]
        
        # Mix peer's ephemeral public key
        self.remote_ephemeral = nacl.public.PublicKey(ephemeral_public_bytes)
        self._mix_hash(ephemeral_public_bytes)
        
        # DH operations
        if not self.ephemeral_private:
            raise HandshakeError("No ephemeral private key")
        
        # DH: ephemeral-ephemeral
        box = nacl.public.Box(self.ephemeral_private, self.remote_ephemeral)
        dh1 = bytes(box._shared_key)
        self._mix_key(dh1)
        
        # DH: static-ephemeral (our static, peer's ephemeral)
        static_keypair = self.key_manager.get_current_keypair()
        box2 = nacl.public.Box(static_keypair.private_key, self.remote_ephemeral)
        dh2 = bytes(box2._shared_key)
        self._mix_key(dh2)
        
        # Mix preshared key again
        self._mix_key(self.preshared_key)
        
        # Decrypt and verify empty payload
        self._decrypt_and_hash(self.chaining_key[:32], encrypted_empty)
        
        # Derive session keys
        self._derive_session_keys()
        
        self.remote_index = message.sender_index
        self.state = HandshakeState.ESTABLISHED
    
    def _derive_session_keys(self) -> None:
        """Derive session keys from handshake state"""
        # Final key derivation
        temp_key1, temp_key2 = self._hkdf(self.chaining_key, b'')
        
        if self.is_initiator:
            self.sending_key = temp_key1
            self.receiving_key = temp_key2
        else:
            self.sending_key = temp_key2
            self.receiving_key = temp_key1
    
    def get_session_keys(self) -> Tuple[bytes, bytes]:
        """Get session keys for transport encryption"""
        if self.state != HandshakeState.ESTABLISHED:
            raise HandshakeError("Handshake not established")
        
        if not self.sending_key or not self.receiving_key:
            raise HandshakeError("Session keys not derived")
        
        return self.sending_key, self.receiving_key
    
    def is_established(self) -> bool:
        """Check if handshake is established"""
        return self.state == HandshakeState.ESTABLISHED
