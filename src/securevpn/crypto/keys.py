"""
Key management for SecureVPN

Implements Curve25519 key generation, storage, and management
with secure key rotation and Perfect Forward Secrecy.
"""

import os
import base64
import time
from typing import Tuple, Optional
from pathlib import Path
from dataclasses import dataclass

import nacl.public
import nacl.secret
import nacl.utils
from nacl.encoding import Base64Encoder

from ..exceptions import CryptographyError


@dataclass
class KeyPair:
    """Represents a cryptographic key pair"""
    private_key: nacl.public.PrivateKey
    public_key: nacl.public.PublicKey
    created_at: float
    
    @property
    def private_key_b64(self) -> str:
        """Get base64 encoded private key"""
        return base64.b64encode(bytes(self.private_key)).decode('ascii')
    
    @property
    def public_key_b64(self) -> str:
        """Get base64 encoded public key"""
        return base64.b64encode(bytes(self.public_key)).decode('ascii')
    
    @classmethod
    def from_private_key_b64(cls, private_key_b64: str) -> 'KeyPair':
        """Create KeyPair from base64 encoded private key"""
        try:
            private_key_bytes = base64.b64decode(private_key_b64)
            private_key = nacl.public.PrivateKey(private_key_bytes)
            return cls(
                private_key=private_key,
                public_key=private_key.public_key,
                created_at=time.time()
            )
        except Exception as e:
            raise CryptographyError(f"Invalid private key: {e}")
    
    @classmethod
    def from_public_key_b64(cls, public_key_b64: str) -> 'KeyPair':
        """Create KeyPair with only public key from base64"""
        try:
            public_key_bytes = base64.b64decode(public_key_b64)
            public_key = nacl.public.PublicKey(public_key_bytes)
            return cls(
                private_key=None,
                public_key=public_key,
                created_at=time.time()
            )
        except Exception as e:
            raise CryptographyError(f"Invalid public key: {e}")


class KeyManager:
    """Manages cryptographic keys with rotation and secure storage"""
    
    def __init__(self, key_rotation_interval: int = 120):
        """
        Initialize key manager
        
        Args:
            key_rotation_interval: Key rotation interval in seconds
        """
        self.key_rotation_interval = key_rotation_interval
        self._current_keypair: Optional[KeyPair] = None
        self._previous_keypair: Optional[KeyPair] = None
        self._peer_keys: dict[str, KeyPair] = {}
    
    def generate_keypair(self) -> KeyPair:
        """Generate a new Curve25519 key pair"""
        try:
            private_key = nacl.public.PrivateKey.generate()
            return KeyPair(
                private_key=private_key,
                public_key=private_key.public_key,
                created_at=time.time()
            )
        except Exception as e:
            raise CryptographyError(f"Failed to generate key pair: {e}")
    
    def load_keypair_from_files(self, private_key_path: Path, public_key_path: Path) -> KeyPair:
        """Load key pair from files"""
        try:
            if not private_key_path.exists():
                raise CryptographyError(f"Private key file not found: {private_key_path}")
            
            with open(private_key_path, 'r') as f:
                private_key_b64 = f.read().strip()
            
            keypair = KeyPair.from_private_key_b64(private_key_b64)
            
            # Verify public key matches if file exists
            if public_key_path.exists():
                with open(public_key_path, 'r') as f:
                    expected_public_key_b64 = f.read().strip()
                
                if keypair.public_key_b64 != expected_public_key_b64:
                    raise CryptographyError("Public key file doesn't match private key")
            
            return keypair
            
        except Exception as e:
            raise CryptographyError(f"Failed to load key pair: {e}")
    
    def save_keypair_to_files(self, keypair: KeyPair, private_key_path: Path, public_key_path: Path) -> None:
        """Save key pair to files with secure permissions"""
        try:
            # Create directories if they don't exist
            private_key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            public_key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Save private key with restrictive permissions
            with open(private_key_path, 'w') as f:
                f.write(keypair.private_key_b64)
            os.chmod(private_key_path, 0o600)
            
            # Save public key
            with open(public_key_path, 'w') as f:
                f.write(keypair.public_key_b64)
            os.chmod(public_key_path, 0o644)
            
        except Exception as e:
            raise CryptographyError(f"Failed to save key pair: {e}")
    
    def set_current_keypair(self, keypair: KeyPair) -> None:
        """Set the current key pair"""
        self._previous_keypair = self._current_keypair
        self._current_keypair = keypair
    
    def get_current_keypair(self) -> Optional[KeyPair]:
        """Get the current key pair"""
        return self._current_keypair
    
    def get_previous_keypair(self) -> Optional[KeyPair]:
        """Get the previous key pair (for key rotation)"""
        return self._previous_keypair
    
    def should_rotate_keys(self) -> bool:
        """Check if keys should be rotated"""
        if not self._current_keypair:
            return True
        
        age = time.time() - self._current_keypair.created_at
        return age >= self.key_rotation_interval
    
    def rotate_keys(self) -> KeyPair:
        """Rotate to a new key pair"""
        new_keypair = self.generate_keypair()
        self.set_current_keypair(new_keypair)
        return new_keypair
    
    def add_peer_key(self, peer_id: str, public_key_b64: str) -> None:
        """Add a peer's public key"""
        try:
            keypair = KeyPair.from_public_key_b64(public_key_b64)
            self._peer_keys[peer_id] = keypair
        except Exception as e:
            raise CryptographyError(f"Failed to add peer key: {e}")
    
    def get_peer_key(self, peer_id: str) -> Optional[KeyPair]:
        """Get a peer's public key"""
        return self._peer_keys.get(peer_id)
    
    def remove_peer_key(self, peer_id: str) -> None:
        """Remove a peer's public key"""
        self._peer_keys.pop(peer_id, None)
    
    def derive_shared_secret(self, peer_public_key: nacl.public.PublicKey) -> bytes:
        """Derive shared secret using ECDH"""
        if not self._current_keypair or not self._current_keypair.private_key:
            raise CryptographyError("No private key available for ECDH")
        
        try:
            box = nacl.public.Box(self._current_keypair.private_key, peer_public_key)
            # Use a deterministic method to derive the shared secret
            # In practice, this would be the raw shared secret from ECDH
            return bytes(box._shared_key)
        except Exception as e:
            raise CryptographyError(f"Failed to derive shared secret: {e}")
    
    def clear_keys(self) -> None:
        """Securely clear all keys from memory"""
        # In a production implementation, we would use secure memory clearing
        self._current_keypair = None
        self._previous_keypair = None
        self._peer_keys.clear()
