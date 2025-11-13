"""
TUN/TAP interface management for SecureVPN

Cross-platform TUN interface creation and management with
support for Linux, Windows, and macOS.
"""

import os
import sys
import struct
import asyncio
import subprocess
from typing import Optional, Callable, List
from ipaddress import IPv4Network, IPv6Network, IPv4Address, IPv6Address
from pathlib import Path

from ..exceptions import NetworkError, TunnelError


class TunInterface:
    """Cross-platform TUN interface manager"""
    
    def __init__(self, interface_name: str = "svpn0", mtu: int = 1420):
        """
        Initialize TUN interface
        
        Args:
            interface_name: Name of the TUN interface
            mtu: Maximum transmission unit
        """
        self.interface_name = interface_name
        self.mtu = mtu
        self.fd: Optional[int] = None
        self.is_open = False
        
        # Network configuration
        self.ipv4_address: Optional[IPv4Address] = None
        self.ipv4_network: Optional[IPv4Network] = None
        self.ipv6_address: Optional[IPv6Address] = None
        self.ipv6_network: Optional[IPv6Network] = None
        
        # Packet handling
        self.packet_handler: Optional[Callable] = None
        self._read_task: Optional[asyncio.Task] = None
        
        # Platform detection
        self.platform = sys.platform.lower()
        
        # Statistics
        self.bytes_read = 0
        self.bytes_written = 0
        self.packets_read = 0
        self.packets_written = 0
    
    async def create(self) -> None:
        """Create TUN interface"""
        if self.is_open:
            return
        
        try:
            if self.platform.startswith('linux'):
                await self._create_linux()
            elif self.platform.startswith('win'):
                await self._create_windows()
            elif self.platform.startswith('darwin'):
                await self._create_macos()
            else:
                raise TunnelError(f"Unsupported platform: {self.platform}")
            
            self.is_open = True
            
        except Exception as e:
            raise TunnelError(f"Failed to create TUN interface: {e}")
    
    async def _create_linux(self) -> None:
        """Create TUN interface on Linux"""
        import fcntl
        
        # TUN/TAP constants for Linux
        TUNSETIFF = 0x400454ca
        IFF_TUN = 0x0001
        IFF_NO_PI = 0x1000
        
        try:
            # Open TUN device
            self.fd = os.open('/dev/net/tun', os.O_RDWR)
            
            # Configure interface
            ifr = struct.pack('16sH', self.interface_name.encode('utf-8'), IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.fd, TUNSETIFF, ifr)
            
            # Set non-blocking
            flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
        except Exception as e:
            if self.fd:
                os.close(self.fd)
                self.fd = None
            raise TunnelError(f"Failed to create Linux TUN interface: {e}")
    
    async def _create_windows(self) -> None:
        """Create TUN interface on Windows"""
        try:
            # Windows requires WinTun driver
            # This is a simplified implementation - production code would use WinTun API
            
            # Check if WinTun is available
            wintun_dll = Path("wintun.dll")
            if not wintun_dll.exists():
                raise TunnelError("WinTun driver not found. Please install WinTun.")
            
            # For now, use TAP-Windows adapter via subprocess
            # In production, use proper WinTun API bindings
            cmd = [
                "netsh", "interface", "ip", "set", "interface",
                self.interface_name, "admin=enable"
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise TunnelError(f"Failed to enable interface: {stderr.decode()}")
            
            # Open device (simplified - would use WinTun API)
            self.fd = 1  # Placeholder
            
        except Exception as e:
            raise TunnelError(f"Failed to create Windows TUN interface: {e}")
    
    async def _create_macos(self) -> None:
        """Create TUN interface on macOS"""
        try:
            # macOS uses utun devices
            import socket
            
            # Create socket for utun
            sock = socket.socket(socket.AF_SYSTEM, socket.SOCK_DGRAM, 2)  # SYSPROTO_CONTROL
            
            # Connect to utun control
            # This is simplified - production code would use proper utun API
            
            self.fd = sock.fileno()
            
        except Exception as e:
            raise TunnelError(f"Failed to create macOS TUN interface: {e}")
    
    async def configure_ipv4(self, address: str, network: str) -> None:
        """Configure IPv4 address and network"""
        try:
            self.ipv4_address = IPv4Address(address)
            self.ipv4_network = IPv4Network(network, strict=False)
            
            if self.platform.startswith('linux'):
                await self._configure_ipv4_linux(address, network)
            elif self.platform.startswith('win'):
                await self._configure_ipv4_windows(address, network)
            elif self.platform.startswith('darwin'):
                await self._configure_ipv4_macos(address, network)
            
        except Exception as e:
            raise TunnelError(f"Failed to configure IPv4: {e}")
    
    async def _configure_ipv4_linux(self, address: str, network: str) -> None:
        """Configure IPv4 on Linux"""
        commands = [
            ["ip", "addr", "add", f"{address}/{network.split('/')[1]}", "dev", self.interface_name],
            ["ip", "link", "set", "dev", self.interface_name, "up"],
            ["ip", "link", "set", "dev", self.interface_name, "mtu", str(self.mtu)]
        ]
        
        for cmd in commands:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise TunnelError(f"Command failed: {' '.join(cmd)}: {stderr.decode()}")
    
    async def _configure_ipv4_windows(self, address: str, network: str) -> None:
        """Configure IPv4 on Windows"""
        network_obj = IPv4Network(network, strict=False)
        netmask = str(network_obj.netmask)
        
        cmd = [
            "netsh", "interface", "ip", "set", "address",
            self.interface_name, "static", address, netmask
        ]
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            raise TunnelError(f"Failed to set IP address: {stderr.decode()}")
    
    async def _configure_ipv4_macos(self, address: str, network: str) -> None:
        """Configure IPv4 on macOS"""
        network_obj = IPv4Network(network, strict=False)
        netmask = str(network_obj.netmask)
        
        commands = [
            ["ifconfig", self.interface_name, address, netmask],
            ["ifconfig", self.interface_name, "mtu", str(self.mtu)],
            ["ifconfig", self.interface_name, "up"]
        ]
        
        for cmd in commands:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise TunnelError(f"Command failed: {' '.join(cmd)}: {stderr.decode()}")
    
    async def add_route(self, destination: str, gateway: Optional[str] = None) -> None:
        """Add route through TUN interface"""
        try:
            if self.platform.startswith('linux'):
                cmd = ["ip", "route", "add", destination, "dev", self.interface_name]
                if gateway:
                    cmd.extend(["via", gateway])
            elif self.platform.startswith('win'):
                cmd = ["route", "add", destination, "mask", "255.255.255.255"]
                if gateway:
                    cmd.append(gateway)
                cmd.extend(["if", self.interface_name])
            elif self.platform.startswith('darwin'):
                cmd = ["route", "add", destination]
                if gateway:
                    cmd.append(gateway)
                cmd.extend(["-interface", self.interface_name])
            else:
                raise TunnelError(f"Unsupported platform for routing: {self.platform}")
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise TunnelError(f"Failed to add route: {stderr.decode()}")
                
        except Exception as e:
            raise TunnelError(f"Failed to add route: {e}")
    
    async def set_dns(self, dns_servers: List[str]) -> None:
        """Set DNS servers for the interface"""
        try:
            if self.platform.startswith('linux'):
                # Write to resolv.conf or use systemd-resolved
                resolv_conf = "/etc/resolv.conf"
                dns_lines = [f"nameserver {dns}" for dns in dns_servers]
                
                # This is simplified - production code would handle this more carefully
                print(f"Would set DNS servers: {dns_servers}")
                
            elif self.platform.startswith('win'):
                for i, dns in enumerate(dns_servers):
                    cmd = [
                        "netsh", "interface", "ip", "set", "dns",
                        self.interface_name, "static", dns
                    ]
                    if i > 0:
                        cmd[-1] = "index={}".format(i + 1)
                    
                    result = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    await result.communicate()
                    
            elif self.platform.startswith('darwin'):
                # Use networksetup on macOS
                for dns in dns_servers:
                    cmd = ["networksetup", "-setdnsservers", self.interface_name, dns]
                    
                    result = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    await result.communicate()
                    
        except Exception as e:
            raise TunnelError(f"Failed to set DNS: {e}")
    
    async def start_reading(self) -> None:
        """Start reading packets from TUN interface"""
        if not self.is_open or not self.fd:
            raise TunnelError("TUN interface not open")
        
        if self._read_task:
            return
        
        self._read_task = asyncio.create_task(self._read_loop())
    
    async def stop_reading(self) -> None:
        """Stop reading packets"""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
    
    async def _read_loop(self) -> None:
        """Main packet reading loop"""
        while True:
            try:
                packet = await self._read_packet()
                if packet and self.packet_handler:
                    await self.packet_handler(packet)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"TUN read error: {e}")
                await asyncio.sleep(0.1)
    
    async def _read_packet(self) -> Optional[bytes]:
        """Read single packet from TUN interface"""
        if not self.fd:
            return None
        
        try:
            # Use asyncio to read from file descriptor
            loop = asyncio.get_event_loop()
            
            if self.platform.startswith('linux'):
                # Linux TUN interface
                packet = await loop.run_in_executor(None, os.read, self.fd, 65536)
            else:
                # Other platforms might need different handling
                packet = await loop.run_in_executor(None, os.read, self.fd, 65536)
            
            if packet:
                self.bytes_read += len(packet)
                self.packets_read += 1
                return packet
                
        except BlockingIOError:
            # No data available
            await asyncio.sleep(0.001)
        except Exception as e:
            print(f"Error reading packet: {e}")
        
        return None
    
    async def write_packet(self, packet: bytes) -> None:
        """Write packet to TUN interface"""
        if not self.is_open or not self.fd:
            raise TunnelError("TUN interface not open")
        
        try:
            loop = asyncio.get_event_loop()
            
            if self.platform.startswith('linux'):
                # Linux TUN interface
                written = await loop.run_in_executor(None, os.write, self.fd, packet)
            else:
                # Other platforms
                written = await loop.run_in_executor(None, os.write, self.fd, packet)
            
            self.bytes_written += written
            self.packets_written += 1
            
        except Exception as e:
            raise TunnelError(f"Failed to write packet: {e}")
    
    def set_packet_handler(self, handler: Callable) -> None:
        """Set packet handler callback"""
        self.packet_handler = handler
    
    async def close(self) -> None:
        """Close TUN interface"""
        if not self.is_open:
            return
        
        await self.stop_reading()
        
        if self.fd:
            try:
                os.close(self.fd)
            except:
                pass
            self.fd = None
        
        self.is_open = False
    
    def get_stats(self) -> dict:
        """Get interface statistics"""
        return {
            "bytes_read": self.bytes_read,
            "bytes_written": self.bytes_written,
            "packets_read": self.packets_read,
            "packets_written": self.packets_written,
            "is_open": self.is_open,
            "interface_name": self.interface_name,
            "mtu": self.mtu
        }
