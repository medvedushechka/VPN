"""
DNS obfuscation for SecureVPN

Makes VPN traffic appear as legitimate DNS queries by encoding
data in DNS query format.
"""

import struct
import random
import base64
from typing import Tuple, List

from .base import BaseObfuscator, ObfuscationConfig
from ..crypto.utils import secure_random
from ..exceptions import ObfuscationError


class DNSObfuscator(BaseObfuscator):
    """DNS traffic obfuscation"""
    
    def __init__(self, config: ObfuscationConfig):
        """Initialize DNS obfuscator"""
        super().__init__(config)
        
        # DNS configuration
        self.transaction_id = 0
        
        # Common DNS query types
        self.query_types = [
            1,   # A record
            28,  # AAAA record
            15,  # MX record
            16,  # TXT record
            5,   # CNAME record
        ]
        
        # Base domains for queries
        self.base_domains = [
            "example.com",
            "test.local",
            "internal.corp",
            "api.service.com",
            "cdn.example.net"
        ]
    
    async def obfuscate(self, data: bytes) -> bytes:
        """Obfuscate data as DNS query"""
        self.transaction_id = (self.transaction_id + 1) % 65536
        
        # Encode data in DNS-safe format
        encoded_data = self._encode_data_for_dns(data)
        
        # Create DNS query
        dns_query = self._create_dns_query(encoded_data)
        
        return dns_query
    
    async def deobfuscate(self, data: bytes) -> bytes:
        """Extract VPN data from DNS-obfuscated packet"""
        try:
            # Parse DNS packet
            if len(data) < 12:
                raise ObfuscationError("DNS packet too short")
            
            # Parse DNS header
            transaction_id, flags, qdcount, ancount, nscount, arcount = struct.unpack('>HHHHHH', data[:12])
            
            # Check if it's a query (QR bit = 0)
            if flags & 0x8000:
                raise ObfuscationError("Not a DNS query")
            
            # Parse question section
            offset = 12
            domain_name, offset = self._parse_domain_name(data, offset)
            
            if offset + 4 > len(data):
                raise ObfuscationError("Incomplete DNS question")
            
            qtype, qclass = struct.unpack('>HH', data[offset:offset+4])
            
            # Extract encoded data from domain name
            decoded_data = self._decode_data_from_dns(domain_name)
            
            return decoded_data
            
        except Exception as e:
            raise ObfuscationError(f"Failed to deobfuscate DNS data: {e}")
    
    def _encode_data_for_dns(self, data: bytes) -> str:
        """Encode binary data for DNS domain name"""
        # Base32 encoding (DNS-safe)
        import base64
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        
        # Split into DNS labels (max 63 chars each)
        labels = []
        for i in range(0, len(encoded), 60):  # Leave room for subdomain prefix
            chunk = encoded[i:i+60]
            if chunk:
                # Add random prefix to make it look more realistic
                prefix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=2))
                labels.append(f"{prefix}{chunk}")
        
        # Add base domain
        base_domain = random.choice(self.base_domains)
        domain = '.'.join(labels + [base_domain])
        
        return domain
    
    def _decode_data_from_dns(self, domain_name: str) -> bytes:
        """Decode binary data from DNS domain name"""
        # Split domain into labels
        labels = domain_name.split('.')
        
        # Remove base domain (last label)
        if len(labels) > 1:
            labels = labels[:-1]
        
        # Extract encoded data (remove 2-char prefixes)
        encoded_parts = []
        for label in labels:
            if len(label) > 2:
                encoded_parts.append(label[2:])  # Remove prefix
        
        # Combine and decode
        encoded_data = ''.join(encoded_parts).upper()
        
        # Add padding if needed
        padding_needed = (8 - len(encoded_data) % 8) % 8
        encoded_data += '=' * padding_needed
        
        try:
            import base64
            decoded_data = base64.b32decode(encoded_data)
            return decoded_data
        except Exception:
            raise ObfuscationError("Failed to decode DNS domain data")
    
    def _create_dns_query(self, domain_name: str) -> bytes:
        """Create DNS query packet"""
        # DNS Header
        flags = 0x0100  # Standard query, recursion desired
        qdcount = 1     # One question
        ancount = 0     # No answers
        nscount = 0     # No authority records
        arcount = 0     # No additional records
        
        header = struct.pack('>HHHHHH', 
                           self.transaction_id, flags, 
                           qdcount, ancount, nscount, arcount)
        
        # DNS Question
        question = self._encode_domain_name(domain_name)
        qtype = random.choice(self.query_types)
        qclass = 1  # IN (Internet)
        
        question += struct.pack('>HH', qtype, qclass)
        
        return header + question
    
    def _encode_domain_name(self, domain_name: str) -> bytes:
        """Encode domain name in DNS format"""
        encoded = b''
        
        for label in domain_name.split('.'):
            if label:
                label_bytes = label.encode('ascii')
                if len(label_bytes) > 63:
                    raise ObfuscationError("DNS label too long")
                encoded += bytes([len(label_bytes)]) + label_bytes
        
        encoded += b'\x00'  # Root label
        return encoded
    
    def _parse_domain_name(self, data: bytes, offset: int) -> Tuple[str, int]:
        """Parse domain name from DNS packet"""
        labels = []
        original_offset = offset
        jumped = False
        
        while offset < len(data):
            length = data[offset]
            
            if length == 0:
                # End of domain name
                offset += 1
                break
            elif length & 0xC0 == 0xC0:
                # Compression pointer
                if not jumped:
                    original_offset = offset + 2
                    jumped = True
                
                pointer = struct.unpack('>H', data[offset:offset+2])[0] & 0x3FFF
                offset = pointer
                continue
            else:
                # Regular label
                offset += 1
                if offset + length > len(data):
                    raise ObfuscationError("Invalid domain name length")
                
                label = data[offset:offset+length].decode('ascii')
                labels.append(label)
                offset += length
        
        domain_name = '.'.join(labels)
        final_offset = original_offset if jumped else offset
        
        return domain_name, final_offset
    
    def get_target_endpoint(self) -> Tuple[str, int]:
        """Get target endpoint for DNS obfuscation"""
        # Use standard DNS port
        return (self.config.target_host, 53)
    
    async def start(self) -> None:
        """Start DNS obfuscation"""
        await super().start()
        self.transaction_id = random.randint(1, 65535)
    
    def get_stats(self) -> dict:
        """Get DNS obfuscation statistics"""
        stats = super().get_stats()
        stats.update({
            "transaction_id": self.transaction_id,
            "query_types": self.query_types,
            "base_domains": len(self.base_domains)
        })
        return stats
