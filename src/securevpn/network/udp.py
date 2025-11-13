"""
UDP transport layer for SecureVPN

Handles UDP socket operations with async support and connection management.
"""

import asyncio
import socket
import struct
import time
from typing import Tuple, Optional, Callable, Dict, Any
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address

import asyncio_dgram

from ..exceptions import NetworkError
from ..crypto.utils import secure_random


@dataclass
class UDPEndpoint:
    """Represents a UDP endpoint"""
    host: str
    port: int
    family: int = socket.AF_INET
    
    def __post_init__(self):
        # Determine address family
        try:
            IPv4Address(self.host)
            self.family = socket.AF_INET
        except:
            try:
                IPv6Address(self.host)
                self.family = socket.AF_INET6
            except:
                # Hostname - resolve later
                pass
    
    @property
    def address(self) -> Tuple[str, int]:
        return (self.host, self.port)


class UDPTransport:
    """Async UDP transport with connection management"""
    
    def __init__(self, bind_endpoint: Optional[UDPEndpoint] = None):
        """
        Initialize UDP transport
        
        Args:
            bind_endpoint: Local endpoint to bind to (None for client mode)
        """
        self.bind_endpoint = bind_endpoint
        self.socket: Optional[asyncio_dgram.DatagramSocket] = None
        self.is_server = bind_endpoint is not None
        
        # Connection tracking
        self.connections: Dict[Tuple[str, int], 'UDPConnection'] = {}
        self.message_handlers: Dict[int, Callable] = {}
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        
        # Running state
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the UDP transport"""
        if self._running:
            return
        
        try:
            if self.is_server:
                # Server mode - bind to specific address
                self.socket = await asyncio_dgram.bind(self.bind_endpoint.address)
            else:
                # Client mode - connect to remote
                self.socket = await asyncio_dgram.connect(('0.0.0.0', 0))
            
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            
        except Exception as e:
            raise NetworkError(f"Failed to start UDP transport: {e}")
    
    async def stop(self) -> None:
        """Stop the UDP transport"""
        if not self._running:
            return
        
        self._running = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.socket:
            self.socket.close()
            self.socket = None
        
        # Close all connections
        for conn in list(self.connections.values()):
            await conn.close()
        self.connections.clear()
    
    async def send_to(self, data: bytes, endpoint: UDPEndpoint) -> None:
        """Send data to specific endpoint"""
        if not self.socket:
            raise NetworkError("Transport not started")
        
        try:
            await self.socket.send(data, endpoint.address)
            self.bytes_sent += len(data)
            self.packets_sent += 1
            
        except Exception as e:
            raise NetworkError(f"Failed to send UDP packet: {e}")
    
    async def _receive_loop(self) -> None:
        """Main receive loop"""
        while self._running:
            try:
                data, addr = await self.socket.recv()
                self.bytes_received += len(data)
                self.packets_received += 1
                
                # Handle received packet
                await self._handle_received_packet(data, addr)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                print(f"UDP receive error: {e}")
    
    async def _handle_received_packet(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle received packet"""
        try:
            # Get or create connection
            connection = self.get_connection(addr)
            if not connection:
                connection = await self.create_connection(addr)
            
            # Update connection activity
            connection.last_activity = time.time()
            
            # Process packet
            await connection.handle_packet(data)
            
        except Exception as e:
            print(f"Error handling packet from {addr}: {e}")
    
    def get_connection(self, addr: Tuple[str, int]) -> Optional['UDPConnection']:
        """Get existing connection"""
        return self.connections.get(addr)
    
    async def create_connection(self, addr: Tuple[str, int]) -> 'UDPConnection':
        """Create new connection"""
        connection = UDPConnection(self, UDPEndpoint(addr[0], addr[1]))
        self.connections[addr] = connection
        return connection
    
    def remove_connection(self, addr: Tuple[str, int]) -> None:
        """Remove connection"""
        self.connections.pop(addr, None)
    
    def register_message_handler(self, message_type: int, handler: Callable) -> None:
        """Register handler for specific message type"""
        self.message_handlers[message_type] = handler
    
    async def connect_to(self, endpoint: UDPEndpoint) -> 'UDPConnection':
        """Connect to remote endpoint (client mode)"""
        if self.is_server:
            raise NetworkError("Cannot connect in server mode")
        
        if not self._running:
            await self.start()
        
        connection = await self.create_connection(endpoint.address)
        return connection


class UDPConnection:
    """Represents a UDP connection to a peer"""
    
    def __init__(self, transport: UDPTransport, remote_endpoint: UDPEndpoint):
        """
        Initialize UDP connection
        
        Args:
            transport: Parent UDP transport
            remote_endpoint: Remote endpoint
        """
        self.transport = transport
        self.remote_endpoint = remote_endpoint
        self.connection_id = struct.unpack('>I', secure_random(4))[0]
        
        # Connection state
        self.established = False
        self.last_activity = time.time()
        self.created_at = time.time()
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        
        # Packet handlers
        self.packet_handlers: Dict[int, Callable] = {}
    
    async def send(self, data: bytes) -> None:
        """Send data through this connection"""
        try:
            await self.transport.send_to(data, self.remote_endpoint)
            self.bytes_sent += len(data)
            self.packets_sent += 1
            self.last_activity = time.time()
            
        except Exception as e:
            raise NetworkError(f"Failed to send data: {e}")
    
    async def handle_packet(self, data: bytes) -> None:
        """Handle received packet"""
        try:
            self.bytes_received += len(data)
            self.packets_received += 1
            
            # Extract message type (first byte)
            if len(data) < 1:
                return
            
            message_type = data[0]
            
            # Try connection-specific handler first
            handler = self.packet_handlers.get(message_type)
            if handler:
                await handler(data)
                return
            
            # Try transport-level handler
            handler = self.transport.message_handlers.get(message_type)
            if handler:
                await handler(self, data)
                return
            
            # No handler found
            print(f"No handler for message type {message_type}")
            
        except Exception as e:
            print(f"Error handling packet: {e}")
    
    def register_packet_handler(self, message_type: int, handler: Callable) -> None:
        """Register packet handler for this connection"""
        self.packet_handlers[message_type] = handler
    
    async def close(self) -> None:
        """Close the connection"""
        self.established = False
        self.transport.remove_connection(self.remote_endpoint.address)
    
    @property
    def age(self) -> float:
        """Connection age in seconds"""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """Time since last activity in seconds"""
        return time.time() - self.last_activity
    
    def __str__(self) -> str:
        return f"UDPConnection({self.remote_endpoint.host}:{self.remote_endpoint.port})"


class UDPServer(UDPTransport):
    """UDP server with connection management"""
    
    def __init__(self, bind_endpoint: UDPEndpoint, max_connections: int = 1000):
        """
        Initialize UDP server
        
        Args:
            bind_endpoint: Local endpoint to bind to
            max_connections: Maximum number of concurrent connections
        """
        super().__init__(bind_endpoint)
        self.max_connections = max_connections
        
        # Connection cleanup
        self._cleanup_task: Optional[asyncio.Task] = None
        self.connection_timeout = 300  # 5 minutes
    
    async def start(self) -> None:
        """Start the UDP server"""
        await super().start()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop the UDP server"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
    
    async def _cleanup_loop(self) -> None:
        """Cleanup inactive connections"""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = time.time()
                to_remove = []
                
                for addr, conn in self.connections.items():
                    if conn.idle_time > self.connection_timeout:
                        to_remove.append(addr)
                
                for addr in to_remove:
                    conn = self.connections.get(addr)
                    if conn:
                        await conn.close()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Connection cleanup error: {e}")
    
    async def create_connection(self, addr: Tuple[str, int]) -> UDPConnection:
        """Create new connection with limits"""
        if len(self.connections) >= self.max_connections:
            # Remove oldest connection
            oldest_addr = min(self.connections.keys(), 
                            key=lambda a: self.connections[a].created_at)
            await self.connections[oldest_addr].close()
        
        return await super().create_connection(addr)
