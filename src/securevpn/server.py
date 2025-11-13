"""
SecureVPN Server Implementation

High-performance VPN server with advanced security features,
traffic obfuscation, and connection management.
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Set, List
from ipaddress import IPv4Network, IPv4Address
from pathlib import Path

from .config import VPNConfig, ServerConfig
from .crypto import KeyManager, NoiseHandshake, create_cipher
from .crypto.cipher import SessionCipher
from .network import UDPServer, UDPEndpoint, UDPConnection, TunInterface
from .obfuscation import TLSObfuscator, ObfuscationConfig
from .auth import AuthServer, UserManager
from .exceptions import SecureVPNError, NetworkError, HandshakeError


class VPNPeer:
    """Represents a connected VPN peer"""
    
    def __init__(self, connection: UDPConnection, public_key: bytes):
        self.connection = connection
        self.public_key = public_key
        self.peer_id = connection.connection_id
        
        # Network assignment
        self.assigned_ip: Optional[IPv4Address] = None
        self.allowed_ips: List[str] = ["0.0.0.0/0"]
        
        # Crypto state
        self.handshake: Optional[NoiseHandshake] = None
        self.session_cipher: Optional[SessionCipher] = None
        
        # Connection state
        self.connected_at = time.time()
        self.last_handshake = 0
        self.last_keepalive = time.time()
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
    
    @property
    def is_authenticated(self) -> bool:
        """Check if peer is authenticated"""
        return (self.handshake is not None and 
                self.handshake.is_established() and 
                self.session_cipher is not None)
    
    @property
    def connection_age(self) -> float:
        """Get connection age in seconds"""
        return time.time() - self.connected_at
    
    @property
    def idle_time(self) -> float:
        """Get idle time since last keepalive"""
        return time.time() - self.last_keepalive


class SecureVPNServer:
    """Main VPN server class"""
    
    def __init__(self, config: VPNConfig):
        """
        Initialize VPN server
        
        Args:
            config: Server configuration
        """
        if config.mode != "server":
            raise SecureVPNError("Invalid configuration mode for server")
        
        self.config = config
        self.server_config: ServerConfig = config.server
        
        # Core components
        self.key_manager = KeyManager(config.crypto.key_rotation_interval)
        self.udp_server: Optional[UDPServer] = None
        self.tun_interface: Optional[TunInterface] = None
        self.obfuscator: Optional[TLSObfuscator] = None
        
        # Authentication system
        self.user_manager = UserManager()
        self.auth_server: Optional[AuthServer] = None
        
        # Peer management
        self.peers: Dict[int, VPNPeer] = {}  # peer_id -> VPNPeer
        self.ip_assignments: Dict[str, int] = {}  # ip -> peer_id
        self.available_ips: Set[IPv4Address] = set()
        
        # Server state
        self.running = False
        self.start_time: Optional[float] = None
        
        # Tasks
        self._maintenance_task: Optional[asyncio.Task] = None
        self._key_rotation_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.total_connections = 0
        self.active_connections = 0
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    async def start(self) -> None:
        """Start the VPN server"""
        if self.running:
            return
        
        try:
            self.logger.info("Starting SecureVPN server...")
            
            # Load or generate server keys
            await self._setup_keys()
            
            # Setup network components
            await self._setup_network()
            
            # Setup obfuscation
            if self.config.obfuscation.enabled:
                await self._setup_obfuscation()
            
            # Start authentication server
            await self._setup_auth_server()
            
            # Start UDP server
            bind_endpoint = UDPEndpoint(
                self.server_config.bind_address,
                self.server_config.port
            )
            self.udp_server = UDPServer(bind_endpoint, self.server_config.max_clients)
            
            # Register message handlers
            self.udp_server.register_message_handler(1, self._handle_handshake_initiation)
            self.udp_server.register_message_handler(2, self._handle_handshake_response)
            self.udp_server.register_message_handler(4, self._handle_transport_data)
            
            await self.udp_server.start()
            
            # Start TUN interface
            await self.tun_interface.create()
            await self.tun_interface.configure_ipv4(
                str(self.config.network.ipv4_network.network_address + 1),
                str(self.config.network.ipv4_network)
            )
            
            # Set packet handler for TUN interface
            self.tun_interface.set_packet_handler(self._handle_tun_packet)
            await self.tun_interface.start_reading()
            
            # Start background tasks
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
            self._key_rotation_task = asyncio.create_task(self._key_rotation_loop())
            
            self.running = True
            self.start_time = time.time()
            
            self.logger.info(f"SecureVPN server started on {bind_endpoint.host}:{bind_endpoint.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            await self.stop()
            raise SecureVPNError(f"Failed to start server: {e}")
    
    async def stop(self) -> None:
        """Stop the VPN server"""
        if not self.running:
            return
        
        self.logger.info("Stopping SecureVPN server...")
        
        self.running = False
        
        # Stop background tasks
        if self._maintenance_task:
            self._maintenance_task.cancel()
        if self._key_rotation_task:
            self._key_rotation_task.cancel()
        
        # Disconnect all peers
        for peer in list(self.peers.values()):
            await self._disconnect_peer(peer.peer_id)
        
        # Stop network components
        if self.tun_interface:
            await self.tun_interface.close()
        
        if self.udp_server:
            await self.udp_server.stop()
        
        if self.obfuscator:
            await self.obfuscator.stop()
        
        if self.auth_server:
            await self.auth_server.stop()
        
        self.logger.info("SecureVPN server stopped")
    
    async def _setup_keys(self) -> None:
        """Setup server cryptographic keys"""
        try:
            # Try to load existing keys
            keypair = self.key_manager.load_keypair_from_files(
                self.server_config.private_key_path,
                self.server_config.public_key_path
            )
            self.key_manager.set_current_keypair(keypair)
            
            self.logger.info("Loaded existing server keys")
            
        except Exception:
            # Generate new keys
            keypair = self.key_manager.generate_keypair()
            self.key_manager.set_current_keypair(keypair)
            
            # Save keys
            self.key_manager.save_keypair_to_files(
                keypair,
                self.server_config.private_key_path,
                self.server_config.public_key_path
            )
            
            self.logger.info("Generated new server keys")
            self.logger.info(f"Server public key: {keypair.public_key_b64}")
    
    async def _setup_network(self) -> None:
        """Setup network interfaces and IP allocation"""
        # Create TUN interface
        self.tun_interface = TunInterface(
            self.config.network.interface_name,
            self.config.network.mtu
        )
        
        # Setup IP allocation pool
        network = self.config.network.ipv4_network
        
        # Reserve first IP for server, rest for clients
        for ip in network.hosts():
            if ip != network.network_address + 1:  # Skip server IP
                self.available_ips.add(ip)
        
        self.logger.info(f"Network configured: {network} ({len(self.available_ips)} IPs available)")
    
    async def _setup_obfuscation(self) -> None:
        """Setup traffic obfuscation"""
        obf_config = ObfuscationConfig(
            method=self.config.obfuscation.method,
            target_host="cloudflare.com",
            target_port=443,
            decoy_traffic=self.config.obfuscation.decoy_traffic,
            port_hopping=self.config.obfuscation.port_hopping
        )
        
        if self.config.obfuscation.method == "tls":
            self.obfuscator = TLSObfuscator(obf_config)
        
        if self.obfuscator:
            await self.obfuscator.start()
            self.logger.info(f"Obfuscation enabled: {self.config.obfuscation.method}")
    
    async def _setup_auth_server(self) -> None:
        """Setup authentication server for GUI clients"""
        self.auth_server = AuthServer(
            user_manager=self.user_manager,
            vpn_config=self.config,
            host="127.0.0.1",  # Only local access for security
            port=8080
        )
        
        await self.auth_server.start()
        self.logger.info("Authentication server started on http://127.0.0.1:8080")
    
    async def _handle_handshake_initiation(self, connection: UDPConnection, data: bytes) -> None:
        """Handle handshake initiation from client"""
        try:
            # Check if peer already exists
            peer = self.peers.get(connection.connection_id)
            if not peer:
                # Create new peer
                peer = VPNPeer(connection, b'')  # Public key will be extracted from handshake
                self.peers[connection.connection_id] = peer
                self.total_connections += 1
            
            # Create handshake handler
            peer.handshake = NoiseHandshake(
                self.key_manager,
                is_initiator=False,  # Server is responder
                preshared_key=None  # Could add PSK support
            )
            
            # Process initiation and create response
            response_data = peer.handshake.process_initiation(data)
            
            # Send response
            await connection.send(response_data)
            
            # If handshake is established, setup session
            if peer.handshake.is_established():
                await self._setup_peer_session(peer)
            
            peer.last_handshake = time.time()
            
        except Exception as e:
            self.logger.error(f"Handshake initiation error: {e}")
            await self._disconnect_peer(connection.connection_id)
    
    async def _handle_handshake_response(self, connection: UDPConnection, data: bytes) -> None:
        """Handle handshake response (not typically used by server)"""
        self.logger.warning("Received unexpected handshake response")
    
    async def _handle_transport_data(self, connection: UDPConnection, data: bytes) -> None:
        """Handle encrypted transport data from client"""
        peer = self.peers.get(connection.connection_id)
        if not peer or not peer.is_authenticated:
            self.logger.warning(f"Received data from unauthenticated peer {connection.connection_id}")
            return
        
        try:
            # Deobfuscate if enabled
            if self.obfuscator:
                data = await self.obfuscator.deobfuscate(data)
            
            # Extract nonce and ciphertext
            if len(data) < 28:  # 12 bytes nonce + 16 bytes auth tag minimum
                return
            
            nonce = data[:12]
            ciphertext = data[12:]
            
            # Decrypt packet
            plaintext = peer.session_cipher.decrypt_packet(nonce, ciphertext)
            
            # Forward to TUN interface
            await self.tun_interface.write_packet(plaintext)
            
            peer.bytes_received += len(data)
            peer.packets_received += 1
            peer.last_keepalive = time.time()
            
        except Exception as e:
            self.logger.error(f"Error handling transport data: {e}")
    
    async def _handle_tun_packet(self, packet: bytes) -> None:
        """Handle packet from TUN interface - route to appropriate peer"""
        try:
            # Parse IP packet to get destination
            if len(packet) < 20:
                return
            
            # Extract destination IP (bytes 16-20 in IPv4 header)
            dst_ip = ".".join(str(b) for b in packet[16:20])
            
            # Find peer with this IP assignment
            peer_id = self.ip_assignments.get(dst_ip)
            if not peer_id:
                return  # No peer for this destination
            
            peer = self.peers.get(peer_id)
            if not peer or not peer.is_authenticated:
                return
            
            # Encrypt packet
            nonce, ciphertext = peer.session_cipher.encrypt_packet(packet)
            
            # Combine nonce and ciphertext
            encrypted_data = nonce + ciphertext
            
            # Obfuscate if enabled
            if self.obfuscator:
                encrypted_data = await self.obfuscator.obfuscate(encrypted_data)
            
            # Send to peer
            await peer.connection.send(encrypted_data)
            
            peer.bytes_sent += len(encrypted_data)
            peer.packets_sent += 1
            
        except Exception as e:
            self.logger.error(f"Error handling TUN packet: {e}")
    
    async def _setup_peer_session(self, peer: VPNPeer) -> None:
        """Setup encrypted session for authenticated peer"""
        try:
            # Get session keys from handshake
            sending_key, receiving_key = peer.handshake.get_session_keys()
            
            # Create session cipher
            cipher = create_cipher(self.config.crypto.cipher, receiving_key)
            session_id = peer.connection.connection_id.to_bytes(8, 'big')
            peer.session_cipher = SessionCipher(cipher, session_id)
            
            # Assign IP address
            if self.available_ips:
                assigned_ip = self.available_ips.pop()
                peer.assigned_ip = assigned_ip
                self.ip_assignments[str(assigned_ip)] = peer.peer_id
                
                self.logger.info(f"Peer {peer.peer_id} authenticated, assigned IP: {assigned_ip}")
                self.active_connections += 1
            else:
                raise SecureVPNError("No available IP addresses")
                
        except Exception as e:
            self.logger.error(f"Failed to setup peer session: {e}")
            raise
    
    async def _disconnect_peer(self, peer_id: int) -> None:
        """Disconnect a peer and clean up resources"""
        peer = self.peers.get(peer_id)
        if not peer:
            return
        
        # Release IP assignment
        if peer.assigned_ip:
            ip_str = str(peer.assigned_ip)
            self.ip_assignments.pop(ip_str, None)
            self.available_ips.add(peer.assigned_ip)
        
        # Close connection
        await peer.connection.close()
        
        # Remove from peers
        self.peers.pop(peer_id, None)
        
        if peer.is_authenticated:
            self.active_connections -= 1
        
        self.logger.info(f"Peer {peer_id} disconnected")
    
    async def _maintenance_loop(self) -> None:
        """Background maintenance tasks"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                
                current_time = time.time()
                to_disconnect = []
                
                # Check for idle peers
                for peer_id, peer in self.peers.items():
                    if peer.idle_time > 300:  # 5 minutes idle
                        to_disconnect.append(peer_id)
                
                # Disconnect idle peers
                for peer_id in to_disconnect:
                    await self._disconnect_peer(peer_id)
                
                # Log statistics
                if len(self.peers) > 0:
                    self.logger.info(f"Active peers: {len(self.peers)}, "
                                   f"Authenticated: {self.active_connections}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Maintenance error: {e}")
    
    async def _key_rotation_loop(self) -> None:
        """Background key rotation"""
        while self.running:
            try:
                await asyncio.sleep(self.config.crypto.key_rotation_interval)
                
                if self.key_manager.should_rotate_keys():
                    self.logger.info("Rotating server keys...")
                    new_keypair = self.key_manager.rotate_keys()
                    
                    # Save new keys
                    self.key_manager.save_keypair_to_files(
                        new_keypair,
                        self.server_config.private_key_path,
                        self.server_config.public_key_path
                    )
                    
                    self.logger.info("Server keys rotated")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Key rotation error: {e}")
    
    def get_stats(self) -> dict:
        """Get server statistics"""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        return {
            "running": self.running,
            "uptime": uptime,
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "available_ips": len(self.available_ips),
            "obfuscation_enabled": self.config.obfuscation.enabled,
            "server_public_key": self.key_manager.get_current_keypair().public_key_b64 if self.key_manager.get_current_keypair() else None
        }
