"""
Authentication models for SecureVPN
"""

import time
import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


@dataclass
class User:
    """User model"""
    username: str
    password_hash: str
    created_at: float
    last_login: Optional[float] = None
    is_active: bool = True
    vpn_config: Optional[Dict[str, Any]] = None
    
    @classmethod
    def create(cls, username: str, password: str) -> 'User':
        """Create new user with hashed password"""
        password_hash = cls.hash_password(password)
        return cls(
            username=username,
            password_hash=password_hash,
            created_at=time.time(),
            is_active=True
        )
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA-256 with salt"""
        salt = secrets.token_hex(32)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash"""
        try:
            salt, stored_hash = self.password_hash.split(':', 1)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return secrets.compare_digest(stored_hash, password_hash)
        except ValueError:
            return False
    
    def update_last_login(self) -> None:
        """Update last login timestamp"""
        self.last_login = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'username': self.username,
            'password_hash': self.password_hash,
            'created_at': self.created_at,
            'last_login': self.last_login,
            'is_active': self.is_active,
            'vpn_config': self.vpn_config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create from dictionary"""
        return cls(
            username=data['username'],
            password_hash=data['password_hash'],
            created_at=data['created_at'],
            last_login=data.get('last_login'),
            is_active=data.get('is_active', True),
            vpn_config=data.get('vpn_config')
        )


@dataclass
class AuthToken:
    """Authentication token"""
    token: str
    username: str
    created_at: float
    expires_at: float
    is_valid: bool = True
    
    @classmethod
    def create(cls, username: str, expires_in_hours: int = 24) -> 'AuthToken':
        """Create new authentication token"""
        token = secrets.token_urlsafe(32)
        now = time.time()
        expires_at = now + (expires_in_hours * 3600)
        
        return cls(
            token=token,
            username=username,
            created_at=now,
            expires_at=expires_at,
            is_valid=True
        )
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return time.time() > self.expires_at
    
    def invalidate(self) -> None:
        """Invalidate token"""
        self.is_valid = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'token': self.token,
            'username': self.username,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'is_valid': self.is_valid
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthToken':
        """Create from dictionary"""
        return cls(
            token=data['token'],
            username=data['username'],
            created_at=data['created_at'],
            expires_at=data['expires_at'],
            is_valid=data.get('is_valid', True)
        )
