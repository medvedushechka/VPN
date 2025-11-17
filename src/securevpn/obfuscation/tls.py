"""
TLS obfuscation for SecureVPN

Makes VPN traffic appear as legitimate HTTPS traffic by wrapping
packets in TLS-like headers and using realistic connection patterns.
"""

import struct
import time
import random
from typing import Tuple, List, Optional

from .base import BaseObfuscator, ObfuscationConfig
from ..crypto.utils import secure_random
from ..exceptions import ObfuscationError


class TLSObfuscator(BaseObfuscator):
    """TLS traffic obfuscation"""
    
    # TLS constants
    TLS_CONTENT_TYPE_HANDSHAKE = 22
    TLS_CONTENT_TYPE_APPLICATION_DATA = 23
    TLS_VERSION_1_2 = 0x0303
    TLS_VERSION_1_3 = 0x0304
    
    # TLS handshake types
    TLS_HANDSHAKE_CLIENT_HELLO = 1
    TLS_HANDSHAKE_SERVER_HELLO = 2
    TLS_HANDSHAKE_CERTIFICATE = 11
    TLS_HANDSHAKE_SERVER_HELLO_DONE = 14
    TLS_HANDSHAKE_CLIENT_KEY_EXCHANGE = 16
    TLS_HANDSHAKE_FINISHED = 20
    
    def __init__(self, config: ObfuscationConfig):
        """Initialize TLS obfuscator"""
        super().__init__(config)
        
        # TLS session state
        self.session_established = False
        self.client_random: Optional[bytes] = None
        self.server_random: Optional[bytes] = None
        self.session_id: Optional[bytes] = None
        
        # Packet sequence
        self.sequence_number = 0
        self.handshake_complete = False
        
        # Realistic TLS parameters
        self.cipher_suites = [
            0x1301,  # TLS_AES_128_GCM_SHA256
            0x1302,  # TLS_AES_256_GCM_SHA384
            0x1303,  # TLS_CHACHA20_POLY1305_SHA256
            0xc02f,  # TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
            0xc030,  # TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
        ]
        
        # SNI (Server Name Indication) for realism
        self.sni_hostname = config.target_host
    
    async def obfuscate(self, data: bytes) -> bytes:
        """Obfuscate data as TLS application data"""
        if not self.handshake_complete:
            # First packet should look like TLS handshake
            return await self._create_handshake_sequence(data)
        
        return await self._create_application_data(data)
    
    async def deobfuscate(self, data: bytes) -> bytes:
        """Extract VPN data from TLS-obfuscated packet"""
        try:
            # Parse TLS record header
            if len(data) < 5:
                raise ObfuscationError("Invalid TLS record length")
            
            content_type, version, length = struct.unpack('>BHH', data[:5])
            
            if content_type == self.TLS_CONTENT_TYPE_HANDSHAKE:
                # Handle handshake messages
                return await self._handle_handshake(data[5:])
            elif content_type == self.TLS_CONTENT_TYPE_APPLICATION_DATA:
                # Extract application data
                return await self._extract_application_data(data[5:])
            else:
                raise ObfuscationError(f"Unknown TLS content type: {content_type}")
                
        except Exception as e:
            raise ObfuscationError(f"Failed to deobfuscate TLS data: {e}")
    
    async def _create_handshake_sequence(self, first_data: bytes) -> bytes:
        """Create realistic TLS handshake sequence"""
        if not self.client_random:
            # Generate Client Hello
            self.client_random = secure_random(32)
            self.session_id = secure_random(32)
            
            client_hello = await self._create_client_hello()
            
            # Embed first VPN data in the handshake
            # This is a simplified approach - production code would be more sophisticated
            embedded_data = client_hello + first_data
            
            self.handshake_complete = True
            return embedded_data
        
        return await self._create_application_data(first_data)
    
    async def _create_client_hello(self) -> bytes:
        """Create TLS Client Hello message"""
        # TLS Record Header
        record_header = struct.pack('>BHH', 
                                   self.TLS_CONTENT_TYPE_HANDSHAKE,
                                   self.TLS_VERSION_1_3,
                                   0)  # Length will be filled later
        
        # Handshake Header
        handshake_header = struct.pack('>B', self.TLS_HANDSHAKE_CLIENT_HELLO)
        
        # Client Hello payload
        client_hello = bytearray()
        
        # Protocol version
        client_hello.extend(struct.pack('>H', self.TLS_VERSION_1_3))
        
        # Random (32 bytes)
        client_hello.extend(self.client_random)
        
        # Session ID
        client_hello.append(len(self.session_id))
        client_hello.extend(self.session_id)
        
        # Cipher suites
        cipher_suites_data = b''.join(struct.pack('>H', cs) for cs in self.cipher_suites)
        client_hello.extend(struct.pack('>H', len(cipher_suites_data)))
        client_hello.extend(cipher_suites_data)
        
        # Compression methods (null compression)
        client_hello.extend(b'\x01\x00')
        
        # Extensions
        extensions = await self._create_extensions()
        client_hello.extend(struct.pack('>H', len(extensions)))
        client_hello.extend(extensions)
        
        # Complete handshake message
        handshake_length = len(client_hello)
        handshake_msg = handshake_header + struct.pack('>I', handshake_length)[1:] + client_hello
        
        # Complete TLS record
        record_length = len(handshake_msg)
        record = record_header[:3] + struct.pack('>H', record_length) + handshake_msg
        
        return bytes(record)
    
    async def _create_extensions(self) -> bytes:
        """Create TLS extensions for Client Hello"""
        extensions = bytearray()
        
        # Server Name Indication (SNI)
        if self.sni_hostname:
            sni_data = bytearray()
            sni_data.extend(struct.pack('>H', 0))  # Server name list length
            sni_data.append(0)  # Name type: hostname
            hostname_bytes = self.sni_hostname.encode('utf-8')
            sni_data.extend(struct.pack('>H', len(hostname_bytes)))
            sni_data.extend(hostname_bytes)
            
            # Fix server name list length
            struct.pack_into('>H', sni_data, 0, len(sni_data) - 2)
            
            # SNI extension
            extensions.extend(struct.pack('>HH', 0x0000, len(sni_data)))  # SNI extension type
            extensions.extend(sni_data)
        
        # Supported Groups (elliptic curves)
        supported_groups = [0x001d, 0x0017, 0x0018, 0x0019]  # x25519, secp256r1, secp384r1, secp521r1
        groups_data = b''.join(struct.pack('>H', group) for group in supported_groups)
        groups_ext = struct.pack('>H', len(groups_data)) + groups_data
        extensions.extend(struct.pack('>HH', 0x000a, len(groups_ext)))
        extensions.extend(groups_ext)
        
        # Signature Algorithms
        sig_algs = [0x0804, 0x0805, 0x0806]  # RSA-PSS variants
        sig_algs_data = b''.join(struct.pack('>H', alg) for alg in sig_algs)
        sig_algs_ext = struct.pack('>H', len(sig_algs_data)) + sig_algs_data
        extensions.extend(struct.pack('>HH', 0x000d, len(sig_algs_ext)))
        extensions.extend(sig_algs_ext)
        
        # Supported Versions (TLS 1.3)
        versions_data = struct.pack('>BH', 2, self.TLS_VERSION_1_3)  # Length + TLS 1.3
        extensions.extend(struct.pack('>HH', 0x002b, len(versions_data)))
        extensions.extend(versions_data)
        
        return bytes(extensions)
    
    async def _create_application_data(self, data: bytes) -> bytes:
        """Create TLS application data record"""
        # Add some padding for realism
        padding_length = random.randint(0, 16)
        padded_data = data + secure_random(padding_length)
        
        # TLS record header
        record_header = struct.pack('>BHH',
                                   self.TLS_CONTENT_TYPE_APPLICATION_DATA,
                                   self.TLS_VERSION_1_3,
                                   len(padded_data))
        
        self.sequence_number += 1
        return record_header + padded_data
    
    async def _handle_handshake(self, handshake_data: bytes) -> bytes:
        """Handle TLS handshake messages and extract embedded data"""
        # This is a simplified implementation
        # In practice, we would properly parse handshake messages
        
        if len(handshake_data) > 100:  # Assume data is embedded after handshake
            # Extract embedded VPN data (simplified)
            return handshake_data[100:]
        
        return b''  # No embedded data
    
    async def _extract_application_data(self, app_data: bytes) -> bytes:
        """Extract VPN data from TLS application data"""
        # Remove padding (simplified - would need proper padding detection)
        if len(app_data) > 16:
            # Assume last 0-16 bytes might be padding
            for i in range(min(16, len(app_data))):
                if app_data[-(i+1):] == b'\x00' * (i+1):
                    return app_data[:-(i+1)]
        
        return app_data
    
    def get_target_endpoint(self) -> Tuple[str, int]:
        """Get target endpoint for TLS obfuscation"""
        return (self.config.target_host, self.config.target_port)
    
    async def start(self) -> None:
        """Start TLS obfuscation"""
        await super().start()
        
        # Reset session state
        self.session_established = False
        self.client_random = None
        self.server_random = None
        self.session_id = None
        self.sequence_number = 0
        self.handshake_complete = False
    
    def get_stats(self) -> dict:
        """Get TLS obfuscation statistics"""
        stats = super().get_stats()
        stats.update({
            "session_established": self.session_established,
            "handshake_complete": self.handshake_complete,
            "sequence_number": self.sequence_number,
            "sni_hostname": self.sni_hostname
        })
        return stats
