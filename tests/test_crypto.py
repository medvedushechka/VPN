"""
Tests for cryptographic components
"""

import pytest
import time
from pathlib import Path
import tempfile

from securevpn.crypto import (
    KeyManager, KeyPair, NoiseHandshake, 
    ChaCha20Poly1305Cipher, SessionCipher,
    secure_random, constant_time_compare
)
from securevpn.exceptions import CryptographyError, HandshakeError


class TestKeyManager:
    """Test key management functionality"""
    
    def test_generate_keypair(self):
        """Test key pair generation"""
        key_manager = KeyManager()
        keypair = key_manager.generate_keypair()
        
        assert keypair.private_key is not None
        assert keypair.public_key is not None
        assert len(keypair.private_key_b64) > 0
        assert len(keypair.public_key_b64) > 0
        assert keypair.created_at > 0
    
    def test_keypair_from_base64(self):
        """Test creating keypair from base64 strings"""
        key_manager = KeyManager()
        original_keypair = key_manager.generate_keypair()
        
        # Test private key reconstruction
        reconstructed = KeyPair.from_private_key_b64(original_keypair.private_key_b64)
        assert reconstructed.public_key_b64 == original_keypair.public_key_b64
        
        # Test public key only
        public_only = KeyPair.from_public_key_b64(original_keypair.public_key_b64)
        assert public_only.public_key_b64 == original_keypair.public_key_b64
        assert public_only.private_key is None
    
    def test_save_load_keypair(self):
        """Test saving and loading keypairs"""
        key_manager = KeyManager()
        keypair = key_manager.generate_keypair()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            private_path = Path(temp_dir) / "private.key"
            public_path = Path(temp_dir) / "public.key"
            
            # Save keypair
            key_manager.save_keypair_to_files(keypair, private_path, public_path)
            
            # Load keypair
            loaded_keypair = key_manager.load_keypair_from_files(private_path, public_path)
            
            assert loaded_keypair.private_key_b64 == keypair.private_key_b64
            assert loaded_keypair.public_key_b64 == keypair.public_key_b64
    
    def test_key_rotation(self):
        """Test key rotation functionality"""
        key_manager = KeyManager(key_rotation_interval=1)  # 1 second for testing
        
        # Generate initial keypair
        keypair1 = key_manager.generate_keypair()
        key_manager.set_current_keypair(keypair1)
        
        # Should not need rotation immediately
        assert not key_manager.should_rotate_keys()
        
        # Wait for rotation interval
        time.sleep(1.1)
        assert key_manager.should_rotate_keys()
        
        # Rotate keys
        keypair2 = key_manager.rotate_keys()
        
        assert keypair2.public_key_b64 != keypair1.public_key_b64
        assert key_manager.get_current_keypair() == keypair2
        assert key_manager.get_previous_keypair() == keypair1
    
    def test_peer_key_management(self):
        """Test peer key management"""
        key_manager = KeyManager()
        
        # Generate test peer key
        peer_keypair = key_manager.generate_keypair()
        peer_id = "test_peer"
        
        # Add peer key
        key_manager.add_peer_key(peer_id, peer_keypair.public_key_b64)
        
        # Retrieve peer key
        retrieved = key_manager.get_peer_key(peer_id)
        assert retrieved is not None
        assert retrieved.public_key_b64 == peer_keypair.public_key_b64
        
        # Remove peer key
        key_manager.remove_peer_key(peer_id)
        assert key_manager.get_peer_key(peer_id) is None


class TestCiphers:
    """Test encryption ciphers"""
    
    def test_chacha20poly1305(self):
        """Test ChaCha20Poly1305 cipher"""
        key = secure_random(32)
        cipher = ChaCha20Poly1305Cipher(key)
        
        plaintext = b"Hello, SecureVPN!"
        nonce = cipher.generate_nonce()
        associated_data = b"test_data"
        
        # Encrypt
        ciphertext = cipher.encrypt(plaintext, nonce, associated_data)
        assert len(ciphertext) == len(plaintext) + 16  # +16 for auth tag
        
        # Decrypt
        decrypted = cipher.decrypt(ciphertext, nonce, associated_data)
        assert decrypted == plaintext
        
        # Test authentication failure
        with pytest.raises(CryptographyError):
            cipher.decrypt(ciphertext, nonce, b"wrong_data")
    
    def test_session_cipher(self):
        """Test session cipher with counter-based nonces"""
        key = secure_random(32)
        base_cipher = ChaCha20Poly1305Cipher(key)
        session_id = secure_random(8)
        
        session_cipher = SessionCipher(base_cipher, session_id)
        
        plaintext = b"Test packet data"
        
        # Encrypt packet
        nonce, ciphertext = session_cipher.encrypt_packet(plaintext)
        assert len(nonce) == 12
        assert nonce[:8] == session_id
        
        # Decrypt packet
        decrypted = session_cipher.decrypt_packet(nonce, ciphertext)
        assert decrypted == plaintext
        
        # Test replay protection
        with pytest.raises(CryptographyError):
            session_cipher.decrypt_packet(nonce, ciphertext)


class TestHandshake:
    """Test Noise handshake protocol"""
    
    def test_handshake_success(self):
        """Test successful handshake between client and server"""
        # Setup key managers
        client_km = KeyManager()
        server_km = KeyManager()
        
        client_keypair = client_km.generate_keypair()
        server_keypair = server_km.generate_keypair()
        
        client_km.set_current_keypair(client_keypair)
        server_km.set_current_keypair(server_keypair)
        
        # Create handshake instances
        client_handshake = NoiseHandshake(
            client_km,
            is_initiator=True,
            peer_public_key=bytes(server_keypair.public_key)
        )
        
        server_handshake = NoiseHandshake(
            server_km,
            is_initiator=False
        )
        
        # Perform handshake
        # 1. Client creates initiation
        initiation = client_handshake.create_initiation()
        assert len(initiation) > 0
        
        # 2. Server processes initiation and creates response
        response = server_handshake.process_initiation(initiation)
        assert len(response) > 0
        
        # 3. Client processes response
        client_handshake.process_response(response)
        
        # Both should be established
        assert client_handshake.is_established()
        assert server_handshake.is_established()
        
        # Get session keys
        client_keys = client_handshake.get_session_keys()
        server_keys = server_handshake.get_session_keys()
        
        # Keys should be swapped (client send = server receive)
        assert client_keys[0] == server_keys[1]  # client send = server receive
        assert client_keys[1] == server_keys[0]  # client receive = server send
    
    def test_handshake_invalid_peer_key(self):
        """Test handshake with invalid peer key"""
        client_km = KeyManager()
        client_keypair = client_km.generate_keypair()
        client_km.set_current_keypair(client_keypair)
        
        # Use invalid peer key
        invalid_peer_key = secure_random(32)
        
        client_handshake = NoiseHandshake(
            client_km,
            is_initiator=True,
            peer_public_key=invalid_peer_key
        )
        
        # This should not raise an exception during initiation creation
        # The error would occur during the actual handshake process
        initiation = client_handshake.create_initiation()
        assert len(initiation) > 0


class TestCryptoUtils:
    """Test cryptographic utilities"""
    
    def test_secure_random(self):
        """Test secure random generation"""
        random1 = secure_random(32)
        random2 = secure_random(32)
        
        assert len(random1) == 32
        assert len(random2) == 32
        assert random1 != random2  # Should be different
    
    def test_constant_time_compare(self):
        """Test constant-time comparison"""
        data1 = b"test_data"
        data2 = b"test_data"
        data3 = b"different"
        
        assert constant_time_compare(data1, data2) is True
        assert constant_time_compare(data1, data3) is False
        
        # Test with strings
        assert constant_time_compare("hello", "hello") is True
        assert constant_time_compare("hello", "world") is False


if __name__ == "__main__":
    pytest.main([__file__])
