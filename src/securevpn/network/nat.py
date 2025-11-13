"""
NAT traversal and STUN-like functionality for SecureVPN
"""

import asyncio
import socket
import struct
import time
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

from ..exceptions import NetworkError


@dataclass
class NATMapping:
    """Represents a NAT mapping"""
    internal_addr: Tuple[str, int]
    external_addr: Tuple[str, int]
    created_at: float
    last_used: float
    mapping_type: str  # "full_cone", "restricted_cone", "port_restricted", "symmetric"


class NATTraversal:
    """NAT traversal helper using STUN-like techniques"""
    
    # STUN servers for NAT detection
    STUN_SERVERS = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
        ("stun2.l.google.com", 19302),
        ("stun.cloudflare.com", 3478),
    ]
    
    def __init__(self):
        self.mappings: Dict[str, NATMapping] = {}
        self.external_ip: Optional[str] = None
        self.nat_type: Optional[str] = None
        
    async def detect_nat_type(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect NAT type and external IP address
        
        Returns:
            Tuple of (external_ip, nat_type)
        """
        try:
            # Try multiple STUN servers
            for stun_server in self.STUN_SERVERS:
                try:
                    external_ip = await self._query_stun_server(stun_server)
                    if external_ip:
                        self.external_ip = external_ip
                        break
                except Exception:
                    continue
            
            if not self.external_ip:
                return None, None
            
            # Detect NAT type through multiple tests
            nat_type = await self._detect_nat_behavior()
            self.nat_type = nat_type
            
            return self.external_ip, nat_type
            
        except Exception as e:
            raise NetworkError(f"NAT detection failed: {e}")
    
    async def _query_stun_server(self, server: Tuple[str, int]) -> Optional[str]:
        """Query STUN server for external IP"""
        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5.0)
            
            # STUN Binding Request
            stun_request = self._create_stun_binding_request()
            
            # Send request
            sock.sendto(stun_request, server)
            
            # Receive response
            response, addr = sock.recvfrom(1024)
            sock.close()
            
            # Parse STUN response
            external_ip = self._parse_stun_response(response)
            return external_ip
            
        except Exception:
            return None
    
    def _create_stun_binding_request(self) -> bytes:
        """Create STUN Binding Request message"""
        # STUN message header
        message_type = 0x0001  # Binding Request
        message_length = 0x0000  # No attributes
        magic_cookie = 0x2112A442
        transaction_id = struct.unpack('>III', b'\x00' * 12)  # Simplified
        
        return struct.pack('>HHIII', 
                          message_type, 
                          message_length, 
                          magic_cookie,
                          transaction_id[0],
                          transaction_id[1])
    
    def _parse_stun_response(self, response: bytes) -> Optional[str]:
        """Parse STUN Binding Response"""
        if len(response) < 20:
            return None
        
        # Parse header
        message_type, message_length = struct.unpack('>HH', response[:4])
        
        if message_type != 0x0101:  # Binding Success Response
            return None
        
        # Parse attributes
        offset = 20
        while offset < len(response):
            if offset + 4 > len(response):
                break
                
            attr_type, attr_length = struct.unpack('>HH', response[offset:offset+4])
            offset += 4
            
            if attr_type == 0x0001:  # MAPPED-ADDRESS
                if attr_length >= 8:
                    family = struct.unpack('>H', response[offset+2:offset+4])[0]
                    if family == 0x01:  # IPv4
                        port = struct.unpack('>H', response[offset+4:offset+6])[0]
                        ip_bytes = response[offset+6:offset+10]
                        ip = socket.inet_ntoa(ip_bytes)
                        return ip
            elif attr_type == 0x0020:  # XOR-MAPPED-ADDRESS
                if attr_length >= 8:
                    family = struct.unpack('>H', response[offset+2:offset+4])[0]
                    if family == 0x01:  # IPv4
                        port = struct.unpack('>H', response[offset+4:offset+6])[0] ^ 0x2112
                        ip_int = struct.unpack('>I', response[offset+6:offset+10])[0] ^ 0x2112A442
                        ip = socket.inet_ntoa(struct.pack('>I', ip_int))
                        return ip
            
            # Move to next attribute
            offset += attr_length
            # Pad to 4-byte boundary
            offset = (offset + 3) & ~3
        
        return None
    
    async def _detect_nat_behavior(self) -> str:
        """Detect NAT behavior type"""
        # This is a simplified NAT type detection
        # In practice, you'd need multiple STUN queries with different servers
        
        # For now, assume most common NAT types
        return "port_restricted"  # Most home routers use this
    
    async def create_hole_punch(self, target_addr: Tuple[str, int], 
                               local_port: int) -> Optional[socket.socket]:
        """
        Create UDP hole punch for NAT traversal
        
        Args:
            target_addr: Target address to punch hole to
            local_port: Local port to bind to
            
        Returns:
            Socket ready for communication or None if failed
        """
        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to local port
            sock.bind(('0.0.0.0', local_port))
            
            # Send hole punch packets
            punch_data = b"PUNCH"
            for _ in range(5):  # Send multiple packets
                sock.sendto(punch_data, target_addr)
                await asyncio.sleep(0.1)
            
            # Set socket to non-blocking for async use
            sock.setblocking(False)
            
            return sock
            
        except Exception as e:
            raise NetworkError(f"Hole punch failed: {e}")
    
    async def test_connectivity(self, sock: socket.socket, 
                               target_addr: Tuple[str, int]) -> bool:
        """Test if hole punch was successful"""
        try:
            # Send test packet
            test_data = b"TEST_CONNECTIVITY"
            sock.sendto(test_data, target_addr)
            
            # Wait for response (with timeout)
            loop = asyncio.get_event_loop()
            
            try:
                # Wait up to 5 seconds for response
                await asyncio.wait_for(
                    loop.sock_recv(sock, 1024),
                    timeout=5.0
                )
                return True
            except asyncio.TimeoutError:
                return False
                
        except Exception:
            return False
    
    def get_mapping_info(self, internal_addr: Tuple[str, int]) -> Optional[NATMapping]:
        """Get NAT mapping information"""
        key = f"{internal_addr[0]}:{internal_addr[1]}"
        return self.mappings.get(key)
    
    def add_mapping(self, internal_addr: Tuple[str, int], 
                   external_addr: Tuple[str, int], 
                   mapping_type: str = "unknown") -> None:
        """Add NAT mapping"""
        key = f"{internal_addr[0]}:{internal_addr[1]}"
        self.mappings[key] = NATMapping(
            internal_addr=internal_addr,
            external_addr=external_addr,
            created_at=time.time(),
            last_used=time.time(),
            mapping_type=mapping_type
        )
    
    def cleanup_old_mappings(self, max_age: int = 300) -> None:
        """Clean up old NAT mappings"""
        current_time = time.time()
        to_remove = []
        
        for key, mapping in self.mappings.items():
            if current_time - mapping.last_used > max_age:
                to_remove.append(key)
        
        for key in to_remove:
            del self.mappings[key]
    
    def get_stats(self) -> dict:
        """Get NAT traversal statistics"""
        return {
            "external_ip": self.external_ip,
            "nat_type": self.nat_type,
            "active_mappings": len(self.mappings),
            "mappings": {
                key: {
                    "external_addr": mapping.external_addr,
                    "age": time.time() - mapping.created_at,
                    "type": mapping.mapping_type
                }
                for key, mapping in self.mappings.items()
            }
        }
