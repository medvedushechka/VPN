"""
IP packet parsing and routing for SecureVPN
"""

import struct
import socket
from typing import Optional, Tuple, List
from ipaddress import IPv4Address, IPv6Address
from dataclasses import dataclass

from ..exceptions import NetworkError


@dataclass
class IPPacket:
    """Represents an IP packet"""
    version: int
    header_length: int
    dscp: int
    ecn: int
    total_length: int
    identification: int
    flags: int
    fragment_offset: int
    ttl: int
    protocol: int
    header_checksum: int
    source_ip: str
    destination_ip: str
    payload: bytes
    
    @classmethod
    def parse(cls, data: bytes) -> 'IPPacket':
        """Parse IP packet from raw bytes"""
        if len(data) < 20:
            raise NetworkError("Packet too short for IP header")
        
        # Parse IP header
        version_ihl = data[0]
        version = (version_ihl >> 4) & 0xF
        header_length = (version_ihl & 0xF) * 4
        
        if version != 4:
            raise NetworkError(f"Unsupported IP version: {version}")
        
        if len(data) < header_length:
            raise NetworkError("Packet shorter than header length")
        
        # Parse remaining header fields
        dscp_ecn = data[1]
        dscp = (dscp_ecn >> 2) & 0x3F
        ecn = dscp_ecn & 0x3
        
        total_length = struct.unpack('>H', data[2:4])[0]
        identification = struct.unpack('>H', data[4:6])[0]
        
        flags_fragment = struct.unpack('>H', data[6:8])[0]
        flags = (flags_fragment >> 13) & 0x7
        fragment_offset = flags_fragment & 0x1FFF
        
        ttl = data[8]
        protocol = data[9]
        header_checksum = struct.unpack('>H', data[10:12])[0]
        
        source_ip = socket.inet_ntoa(data[12:16])
        destination_ip = socket.inet_ntoa(data[16:20])
        
        payload = data[header_length:]
        
        return cls(
            version=version,
            header_length=header_length,
            dscp=dscp,
            ecn=ecn,
            total_length=total_length,
            identification=identification,
            flags=flags,
            fragment_offset=fragment_offset,
            ttl=ttl,
            protocol=protocol,
            header_checksum=header_checksum,
            source_ip=source_ip,
            destination_ip=destination_ip,
            payload=payload
        )
    
    def to_bytes(self) -> bytes:
        """Convert packet back to bytes"""
        # Build IP header
        version_ihl = (self.version << 4) | (self.header_length // 4)
        dscp_ecn = (self.dscp << 2) | self.ecn
        flags_fragment = (self.flags << 13) | self.fragment_offset
        
        header = struct.pack('>BBHHHBBH4s4s',
            version_ihl,
            dscp_ecn,
            self.total_length,
            self.identification,
            flags_fragment,
            self.ttl,
            self.protocol,
            self.header_checksum,
            socket.inet_aton(self.source_ip),
            socket.inet_aton(self.destination_ip)
        )
        
        return header + self.payload
    
    def calculate_checksum(self) -> int:
        """Calculate IP header checksum"""
        # Create header with checksum = 0
        version_ihl = (self.version << 4) | (self.header_length // 4)
        dscp_ecn = (self.dscp << 2) | self.ecn
        flags_fragment = (self.flags << 13) | self.fragment_offset
        
        header = struct.pack('>BBHHHBBH4s4s',
            version_ihl,
            dscp_ecn,
            self.total_length,
            self.identification,
            flags_fragment,
            self.ttl,
            self.protocol,
            0,  # Checksum = 0
            socket.inet_aton(self.source_ip),
            socket.inet_aton(self.destination_ip)
        )
        
        # Calculate checksum
        checksum = 0
        for i in range(0, len(header), 2):
            word = struct.unpack('>H', header[i:i+2])[0]
            checksum += word
        
        # Add carry
        while checksum >> 16:
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        
        return ~checksum & 0xFFFF


class PacketRouter:
    """Routes packets between TUN interface and VPN peers"""
    
    def __init__(self):
        self.routing_table: List[Tuple[str, str, str]] = []  # (network, netmask, gateway)
        self.nat_table: dict = {}  # For NAT translation
        
    def add_route(self, network: str, netmask: str, gateway: str) -> None:
        """Add route to routing table"""
        self.routing_table.append((network, netmask, gateway))
    
    def remove_route(self, network: str, netmask: str) -> None:
        """Remove route from routing table"""
        self.routing_table = [
            (net, mask, gw) for net, mask, gw in self.routing_table
            if not (net == network and mask == netmask)
        ]
    
    def find_route(self, destination_ip: str) -> Optional[str]:
        """Find gateway for destination IP"""
        dest_addr = IPv4Address(destination_ip)
        
        for network, netmask, gateway in self.routing_table:
            try:
                net_addr = IPv4Address(network)
                mask_addr = IPv4Address(netmask)
                
                # Calculate network address
                network_int = int(net_addr) & int(mask_addr)
                dest_int = int(dest_addr) & int(mask_addr)
                
                if network_int == dest_int:
                    return gateway
                    
            except Exception:
                continue
        
        return None
    
    def should_route_packet(self, packet: IPPacket) -> bool:
        """Determine if packet should be routed through VPN"""
        # Check if destination is in VPN network
        try:
            dest_addr = IPv4Address(packet.destination_ip)
            
            # Check against routing table
            gateway = self.find_route(packet.destination_ip)
            return gateway is not None
            
        except Exception:
            return False
    
    def modify_packet_for_routing(self, packet: IPPacket, new_source_ip: str) -> IPPacket:
        """Modify packet for routing (NAT)"""
        # Store original mapping for return traffic
        original_key = f"{packet.source_ip}:{packet.destination_ip}"
        self.nat_table[original_key] = packet.source_ip
        
        # Create new packet with modified source IP
        new_packet = IPPacket(
            version=packet.version,
            header_length=packet.header_length,
            dscp=packet.dscp,
            ecn=packet.ecn,
            total_length=packet.total_length,
            identification=packet.identification,
            flags=packet.flags,
            fragment_offset=packet.fragment_offset,
            ttl=max(1, packet.ttl - 1),  # Decrement TTL
            protocol=packet.protocol,
            header_checksum=0,  # Will be recalculated
            source_ip=new_source_ip,
            destination_ip=packet.destination_ip,
            payload=packet.payload
        )
        
        # Recalculate checksum
        new_packet.header_checksum = new_packet.calculate_checksum()
        
        return new_packet
    
    def restore_packet_from_nat(self, packet: IPPacket) -> Optional[IPPacket]:
        """Restore original packet from NAT table"""
        nat_key = f"{packet.destination_ip}:{packet.source_ip}"
        original_dest = self.nat_table.get(nat_key)
        
        if not original_dest:
            return None
        
        # Create restored packet
        restored_packet = IPPacket(
            version=packet.version,
            header_length=packet.header_length,
            dscp=packet.dscp,
            ecn=packet.ecn,
            total_length=packet.total_length,
            identification=packet.identification,
            flags=packet.flags,
            fragment_offset=packet.fragment_offset,
            ttl=packet.ttl,
            protocol=packet.protocol,
            header_checksum=0,  # Will be recalculated
            source_ip=packet.source_ip,
            destination_ip=original_dest,
            payload=packet.payload
        )
        
        # Recalculate checksum
        restored_packet.header_checksum = restored_packet.calculate_checksum()
        
        # Clean up NAT entry
        del self.nat_table[nat_key]
        
        return restored_packet
