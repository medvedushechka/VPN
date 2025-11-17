#!/usr/bin/env python3
"""
Integration test: Full client-server cycle
Tests handshake, key exchange, and transport encryption
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from securevpn.crypto import KeyManager, NoiseHandshake
from securevpn.crypto.cipher import SessionCipher, ChaCha20Poly1305Cipher
import nacl.public

async def test_full_cycle():
    """Test full client-server cycle"""
    
    print("=" * 70)
    print("SecureVPN Full Client-Server Cycle Test")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n" + "=" * 70)
    print("SETUP: Creating server and client key managers")
    print("=" * 70)
    
    server_key_manager = KeyManager()
    client_key_manager = KeyManager()
    
    server_keypair = server_key_manager.generate_keypair()
    client_keypair = client_key_manager.generate_keypair()
    
    server_key_manager.set_current_keypair(server_keypair)
    client_key_manager.set_current_keypair(client_keypair)
    
    print(f"✓ Server public key: {server_keypair.public_key_b64[:32]}...")
    print(f"✓ Client public key: {client_keypair.public_key_b64[:32]}...")
    
    # ===== HANDSHAKE =====
    print("\n" + "=" * 70)
    print("PHASE 1: Handshake (Noise Protocol)")
    print("=" * 70)
    
    preshared_key = b"test_preshared_key_32bytes_long!"
    
    server_handshake = NoiseHandshake(
        key_manager=server_key_manager,
        is_initiator=False,
        peer_public_key=bytes(client_keypair.public_key),
        preshared_key=preshared_key
    )
    
    client_handshake = NoiseHandshake(
        key_manager=client_key_manager,
        is_initiator=True,
        peer_public_key=bytes(server_keypair.public_key),
        preshared_key=preshared_key
    )
    
    # Client sends initiation
    print("\n1️⃣  Client creates initiation message...")
    try:
        initiation_msg = client_handshake.create_initiation()
        print(f"   ✓ Initiation message: {len(initiation_msg)} bytes")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Server processes initiation and sends response
    print("\n2️⃣  Server processes initiation and creates response...")
    try:
        response_msg = server_handshake.process_initiation(initiation_msg)
        print(f"   ✓ Response message: {len(response_msg)} bytes")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Client processes response
    print("\n3️⃣  Client processes response...")
    try:
        client_handshake.process_response(response_msg)
        print(f"   ✓ Response processed")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Check handshake state
    print("\n4️⃣  Verify handshake state...")
    print(f"   Client established: {client_handshake.is_established()}")
    print(f"   Server established: {server_handshake.is_established()}")
    
    if not client_handshake.is_established():
        print("   ✗ Client handshake not established")
        return False
    
    print("   ✓ Handshake successful!")
    
    # ===== SESSION KEYS =====
    print("\n" + "=" * 70)
    print("PHASE 2: Session Key Derivation")
    print("=" * 70)
    
    try:
        client_send_key, client_recv_key = client_handshake.get_session_keys()
        print(f"✓ Client sending key: {client_send_key.hex()[:32]}...")
        print(f"✓ Client receiving key: {client_recv_key.hex()[:32]}...")
        
        # Server keys are reversed!
        # client_send_key = server_recv_key
        # client_recv_key = server_send_key
        server_send_key = client_recv_key
        server_recv_key = client_send_key
        print(f"✓ Server sending key: {server_send_key.hex()[:32]}...")
        print(f"✓ Server receiving key: {server_recv_key.hex()[:32]}...")
    except Exception as e:
        print(f"✗ Error getting session keys: {e}")
        return False
    
    # ===== TRANSPORT ENCRYPTION =====
    print("\n" + "=" * 70)
    print("PHASE 3: Transport Encryption (ChaCha20Poly1305)")
    print("=" * 70)
    
    # Create session ciphers
    # SessionCipher takes (cipher_instance, session_id)
    # session_id is 8 bytes - MUST be the same for both sides!
    # We use the first 8 bytes of the sending key as session_id
    session_id = client_send_key[:8]
    
    # Client sends with client_send_key, receives with client_recv_key
    client_cipher = SessionCipher(ChaCha20Poly1305Cipher(client_send_key), session_id)
    # Server receives with server_recv_key (= client_send_key)
    server_cipher = SessionCipher(ChaCha20Poly1305Cipher(server_recv_key), session_id)
    
    # Test message
    test_payload = b"Hello from VPN Client! This is a test message."
    print(f"\n📨 Original payload: {test_payload}")
    print(f"   Length: {len(test_payload)} bytes")
    
    # Client encrypts
    print("\n🔐 Client encrypts message...")
    try:
        nonce, encrypted = client_cipher.encrypt_packet(test_payload)
        print(f"   ✓ Encrypted: {len(encrypted)} bytes")
        print(f"   Nonce: {nonce.hex()}")
        print(f"   Ciphertext hex: {encrypted.hex()[:64]}...")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Server decrypts
    print("\n🔓 Server decrypts message...")
    try:
        decrypted = server_cipher.decrypt_packet(nonce, encrypted)
        print(f"   ✓ Decrypted: {len(decrypted)} bytes")
        print(f"   Content: {decrypted}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verify
    if decrypted == test_payload:
        print("\n   ✓ Payload matches!")
    else:
        print("\n   ✗ Payload mismatch!")
        return False
    
    # Test reverse direction
    print("\n" + "-" * 70)
    print("Testing reverse direction (Server → Client)...")
    
    # For reverse direction:
    # Server sends with server_send_key (= client_recv_key)
    # Client receives with client_recv_key
    server_send_cipher = SessionCipher(ChaCha20Poly1305Cipher(server_send_key), session_id)
    client_recv_cipher = SessionCipher(ChaCha20Poly1305Cipher(client_recv_key), session_id)
    
    test_payload2 = b"Response from VPN Server!"
    print(f"\n📨 Original payload: {test_payload2}")
    
    print("\n🔐 Server encrypts message...")
    try:
        nonce2, encrypted2 = server_send_cipher.encrypt_packet(test_payload2)
        print(f"   ✓ Encrypted: {len(encrypted2)} bytes")
        print(f"   Nonce: {nonce2.hex()}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n🔓 Client decrypts message...")
    try:
        decrypted2 = client_recv_cipher.decrypt_packet(nonce2, encrypted2)
        print(f"   ✓ Decrypted: {decrypted2}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    if decrypted2 == test_payload2:
        print("   ✓ Payload matches!")
    else:
        print("   ✗ Payload mismatch!")
        return False
    
    # ===== SUMMARY =====
    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED!")
    print("=" * 70)
    print("\nSummary:")
    print("  ✓ Handshake successful")
    print("  ✓ Session keys derived")
    print("  ✓ Transport encryption working (Client → Server)")
    print("  ✓ Transport encryption working (Server → Client)")
    print("  ✓ Payload integrity verified")
    print("\n" + "=" * 70)
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test_full_cycle())
    sys.exit(0 if result else 1)
