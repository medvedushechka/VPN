"""
User management for SecureVPN authentication
"""

import sqlite3
import json
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

from .models import User, AuthToken
from ..exceptions import SecureVPNError


class UserManager:
    """Manages users and authentication tokens"""
    
    def __init__(self, db_path: Path = Path("/etc/securevpn/users.db")):
        """
        Initialize user manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_database()
        self._create_default_user()
    
    def _init_database(self) -> None:
        """Initialize SQLite database"""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_login REAL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    vpn_config TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    is_valid BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (username) REFERENCES users (username)
                )
            ''')
            
            # Create indexes for performance
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tokens_username 
                ON auth_tokens (username)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tokens_expires 
                ON auth_tokens (expires_at)
            ''')
            
            conn.commit()
    
    def _create_default_user(self) -> None:
        """Create default user if no users exist"""
        if not self.user_exists("Medvedushkaa"):
            user = User.create("Medvedushkaa", "1q2w3e4r5t6y")
            self.create_user(user)
    
    def create_user(self, user: User) -> bool:
        """
        Create new user
        
        Args:
            user: User object to create
            
        Returns:
            True if user created successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO users (username, password_hash, created_at, 
                                     last_login, is_active, vpn_config)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user.username,
                    user.password_hash,
                    user.created_at,
                    user.last_login,
                    user.is_active,
                    json.dumps(user.vpn_config) if user.vpn_config else None
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # User already exists
    
    def get_user(self, username: str) -> Optional[User]:
        """
        Get user by username
        
        Args:
            username: Username to lookup
            
        Returns:
            User object or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT username, password_hash, created_at, last_login, 
                       is_active, vpn_config
                FROM users WHERE username = ?
            ''', (username,))
            
            row = cursor.fetchone()
            if row:
                username, password_hash, created_at, last_login, is_active, vpn_config = row
                return User(
                    username=username,
                    password_hash=password_hash,
                    created_at=created_at,
                    last_login=last_login,
                    is_active=bool(is_active),
                    vpn_config=json.loads(vpn_config) if vpn_config else None
                )
        return None
    
    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        return self.get_user(username) is not None
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password
        
        Args:
            username: Username
            password: Password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.get_user(username)
        if user and user.is_active and user.verify_password(password):
            # Update last login
            user.update_last_login()
            self.update_user(user)
            return user
        return None
    
    def update_user(self, user: User) -> bool:
        """
        Update existing user
        
        Args:
            user: User object to update
            
        Returns:
            True if updated successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE users SET password_hash = ?, last_login = ?, 
                                    is_active = ?, vpn_config = ?
                    WHERE username = ?
                ''', (
                    user.password_hash,
                    user.last_login,
                    user.is_active,
                    json.dumps(user.vpn_config) if user.vpn_config else None,
                    user.username
                ))
                conn.commit()
                return True
        except sqlite3.Error:
            return False
    
    def create_auth_token(self, username: str, expires_in_hours: int = 24) -> Optional[AuthToken]:
        """
        Create authentication token for user
        
        Args:
            username: Username
            expires_in_hours: Token expiration time in hours
            
        Returns:
            AuthToken object or None if user not found
        """
        if not self.user_exists(username):
            return None
        
        token = AuthToken.create(username, expires_in_hours)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO auth_tokens (token, username, created_at, 
                                           expires_at, is_valid)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    token.token,
                    token.username,
                    token.created_at,
                    token.expires_at,
                    token.is_valid
                ))
                conn.commit()
                return token
        except sqlite3.Error:
            return None
    
    def validate_token(self, token_string: str) -> Optional[AuthToken]:
        """
        Validate authentication token
        
        Args:
            token_string: Token string to validate
            
        Returns:
            AuthToken object if valid, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT token, username, created_at, expires_at, is_valid
                FROM auth_tokens WHERE token = ?
            ''', (token_string,))
            
            row = cursor.fetchone()
            if row:
                token, username, created_at, expires_at, is_valid = row
                auth_token = AuthToken(
                    token=token,
                    username=username,
                    created_at=created_at,
                    expires_at=expires_at,
                    is_valid=bool(is_valid)
                )
                
                # Check if token is still valid and not expired
                if auth_token.is_valid and not auth_token.is_expired():
                    return auth_token
                elif auth_token.is_expired():
                    # Auto-invalidate expired token
                    self.invalidate_token(token_string)
        
        return None
    
    def invalidate_token(self, token_string: str) -> bool:
        """
        Invalidate authentication token
        
        Args:
            token_string: Token to invalidate
            
        Returns:
            True if invalidated successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE auth_tokens SET is_valid = 0 WHERE token = ?
                ''', (token_string,))
                conn.commit()
                return True
        except sqlite3.Error:
            return False
    
    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from database
        
        Returns:
            Number of tokens removed
        """
        current_time = time.time()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM auth_tokens WHERE expires_at < ?
                ''', (current_time,))
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error:
            return 0
    
    def get_user_tokens(self, username: str) -> List[AuthToken]:
        """
        Get all valid tokens for user
        
        Args:
            username: Username
            
        Returns:
            List of valid AuthToken objects
        """
        tokens = []
        current_time = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT token, username, created_at, expires_at, is_valid
                FROM auth_tokens 
                WHERE username = ? AND is_valid = 1 AND expires_at > ?
            ''', (username, current_time))
            
            for row in cursor.fetchall():
                token, username, created_at, expires_at, is_valid = row
                tokens.append(AuthToken(
                    token=token,
                    username=username,
                    created_at=created_at,
                    expires_at=expires_at,
                    is_valid=bool(is_valid)
                ))
        
        return tokens
    
    def get_stats(self) -> Dict[str, Any]:
        """Get user management statistics"""
        with sqlite3.connect(self.db_path) as conn:
            # Count users
            cursor = conn.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
            active_users = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # Count tokens
            current_time = time.time()
            cursor = conn.execute('''
                SELECT COUNT(*) FROM auth_tokens 
                WHERE is_valid = 1 AND expires_at > ?
            ''', (current_time,))
            active_tokens = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(*) FROM auth_tokens')
            total_tokens = cursor.fetchone()[0]
            
            return {
                'active_users': active_users,
                'total_users': total_users,
                'active_tokens': active_tokens,
                'total_tokens': total_tokens
            }
