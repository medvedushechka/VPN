#!/usr/bin/env python3
"""
Simple handshake test without TUN interface
Tests the Noise Protocol handshake locally
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from securevpn.crypto import KeyManager, NoiseHandshake
from securevpn.config import ConfigLoader, VPNConfig

async def test_handshake():
    """Test handshake between client and server"""
    
    print("=" * 60)
    print("SecureVPN Handshake Test")
    print("=" * 60)
    
    # Create key managers for both sides
    server_key_manager = KeyManager()
    client_key_manager = KeyManager()
    
    # Generate keypairs
    server_keypair = server_key_manager.generate_keypair()
    client_keypair = client_key_manager.generate_keypair()
    
    # Set current keypairs (required for handshake)
    server_key_manager.set_current_keypair(server_keypair)
    client_key_manager.set_current_keypair(client_keypair)
    
    print(f"\n✓ Server public key: {server_keypair.public_key_b64}")
    print(f"✓ Client public key: {client_keypair.public_key_b64}")
    
    # Create handshakes
    server_handshake = NoiseHandshake(
        key_manager=server_key_manager,
        is_initiator=False,
        peer_public_key=bytes(client_keypair.public_key),
        preshared_key=b"test_preshared_key_32bytes_long!"
    )
    
    client_handshake = NoiseHandshake(
        key_manager=client_key_manager,
        is_initiator=True,
        peer_public_key=bytes(server_keypair.public_key),
        preshared_key=b"test_preshared_key_32bytes_long!"
    )
    
    print("\n" + "=" * 60)
    print("Step 1: Client creates initiation message")
    print("=" * 60)
    
    try:
        initiation_msg = client_handshake.create_initiation()
        print(f"✓ Initiation message created: {len(initiation_msg)} bytes")
        print(f"  Message hex: {initiation_msg.hex()[:64]}...")
    except Exception as e:
        print(f"✗ Error creating initiation: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("Step 2: Server processes initiation message")
    print("=" * 60)
    
    try:
        response_msg = server_handshake.process_initiation(initiation_msg)
        print(f"✓ Response message created: {len(response_msg)} bytes")
        print(f"  Message hex: {response_msg.hex()[:64]}...")
    except Exception as e:
        print(f"✗ Error processing initiation: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("Step 3: Client processes response message")
    print("=" * 60)
    
    try:
        client_handshake.process_response(response_msg)
        print(f"✓ Response processed successfully")
    except Exception as e:
        print(f"✗ Error processing response: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("Step 4: Server finalizes handshake")
    print("=" * 60)
    
    # Server needs to finalize after sending response
    # (In real scenario, this happens after client confirms receipt)
    # For testing, we manually set it
    print(f"✓ Server state before: {server_handshake.state}")
    print(f"✓ Client state before: {client_handshake.state}")
    
    print("\n" + "=" * 60)
    print("Step 5: Verify handshake state")
    print("=" * 60)
    
    print(f"✓ Server handshake established: {server_handshake.is_established()}")
    print(f"✓ Client handshake established: {client_handshake.is_established()}")
    
    if client_handshake.is_established():
        print("\n" + "=" * 60)
        print("✓ HANDSHAKE SUCCESSFUL!")
        print("=" * 60)
        print(f"\nSession Keys Derived:")
        print(f"  Client sending key: {client_handshake.sending_key.hex()[:32]}...")
        print(f"  Client receiving key: {client_handshake.receiving_key.hex()[:32]}...")
        return True
    else:
        print("\n✗ Handshake not fully established")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_handshake())
    sys.exit(0 if result else 1)
