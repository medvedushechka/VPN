"""
SecureVPN Client Implementation

High-performance VPN client with advanced security features,
traffic obfuscation, and automatic connection management.
"""

import asyncio
import time
import logging
from typing import Optional, List
from pathlib import Path
from ipaddress import IPv4Address

from .config import VPNConfig, ClientConfig
from .crypto import KeyManager, NoiseHandshake, SessionCipher, create_cipher
from .network import UDPTransport, UDPEndpoint, UDPConnection, TunInterface
from .obfuscation import TLSObfuscator, HTTPObfuscator, DNSObfuscator, ObfuscationConfig
from .exceptions import SecureVPNError, NetworkError, HandshakeError


class SecureVPNClient:
    """Main VPN client class"""
    
    def __init__(self, config: VPNConfig):
        """
        Initialize VPN client
        
        Args:
            config: Client configuration
        """
        if config.mode != "client":
            raise SecureVPNError("Invalid configuration mode for client")
        
        self.config = config
        self.client_config: ClientConfig = config.client
        
        # Core components
        self.key_manager = KeyManager(config.crypto.key_rotation_interval)
        self.udp_transport: Optional[UDPTransport] = None
        self.tun_interface: Optional[TunInterface] = None
        self.obfuscator: Optional[TLSObfuscator] = None
        
        # Connection state
        self.server_connection: Optional[UDPConnection] = None
        self.handshake: Optional[NoiseHandshake] = None
        self.session_cipher: Optional[SessionCipher] = None
        
        # Client state
        self.connected = False
        self.authenticated = False
        self.assigned_ip: Optional[IPv4Address] = None
        self.connection_start_time: Optional[float] = None
        
        # Tasks
        self._keepalive_task: Optional[asyncio.Task] = None
        self._key_rotation_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.reconnect_count = 0
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    async def connect(self) -> None:
        """Connect to VPN server"""
        if self.connected:
            return
        
        try:
            self.logger.info(f"Connecting to VPN server {self.client_config.server_address}:{self.client_config.server_port}")
            
            # Load client keys
            await self._setup_keys()
            
            # Setup network components
            await self._setup_network()
            
            # Setup obfuscation
            if self.config.obfuscation.enabled:
                await self._setup_obfuscation()
            
            # Start UDP transport (client mode)
            self.udp_transport = UDPTransport()
            await self.udp_transport.start()
            
            # Connect to server
            server_endpoint = UDPEndpoint(
                self.client_config.server_address,
                self.client_config.server_port
            )
            
            self.server_connection = await self.udp_transport.connect_to(server_endpoint)
            
            # Perform handshake
            await self._perform_handshake()
            
            # Setup TUN interface
            await self.tun_interface.create()
            
            # Configure network (we'll get IP from server during handshake)
            # For now, use a default client IP
            client_ip = "10.8.0.2"  # This should come from server
            await self.tun_interface.configure_ipv4(client_ip, str(self.config.network.ipv4_network))
            
            # Set DNS servers
            if self.config.network.dns_servers:
                await self.tun_interface.set_dns(self.config.network.dns_servers)
            
            # Add routes for allowed IPs
            for allowed_ip in self.client_config.allowed_ips:
                if allowed_ip != "0.0.0.0/0":  # Skip default route for now
                    await self.tun_interface.add_route(allowed_ip)
            
            # Set packet handler for TUN interface
            self.tun_interface.set_packet_handler(self._handle_tun_packet)
            await self.tun_interface.start_reading()
            
            # Start background tasks
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            self._key_rotation_task = asyncio.create_task(self._key_rotation_loop())
            
            self.connected = True
            self.connection_start_time = time.time()
            
            self.logger.info("VPN connection established successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to VPN: {e}")
            await self.disconnect()
            raise SecureVPNError(f"Failed to connect to VPN: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from VPN server"""
        if not self.connected:
            return
        
        self.logger.info("Disconnecting from VPN server...")
        
        self.connected = False
        self.authenticated = False
        
        # Stop background tasks
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._key_rotation_task:
            self._key_rotation_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        
        # Close network components
        if self.tun_interface:
            await self.tun_interface.close()
        
        if self.server_connection:
            await self.server_connection.close()
        
        if self.udp_transport:
            await self.udp_transport.stop()
        
        if self.obfuscator:
            await self.obfuscator.stop()
        
        # Clear crypto state
        self.handshake = None
        self.session_cipher = None
        
        self.logger.info("VPN disconnected")
    
    async def _setup_keys(self) -> None:
        """Setup client cryptographic keys"""
        try:
            # Try to load existing keys
            keypair = self.key_manager.load_keypair_from_files(
                self.client_config.private_key_path,
                self.client_config.public_key_path
            )
            self.key_manager.set_current_keypair(keypair)
            
            self.logger.info("Loaded existing client keys")
            
        except Exception:
            # Generate new keys
            keypair = self.key_manager.generate_keypair()
            self.key_manager.set_current_keypair(keypair)
            
            # Save keys
            self.key_manager.save_keypair_to_files(
                keypair,
                self.client_config.private_key_path,
                self.client_config.public_key_path
            )
            
            self.logger.info("Generated new client keys")
            self.logger.info(f"Client public key: {keypair.public_key_b64}")
    
    async def _setup_network(self) -> None:
        """Setup network interfaces"""
        # Create TUN interface
        self.tun_interface = TunInterface(
            self.config.network.interface_name,
            self.config.network.mtu
        )
        
        self.logger.info(f"TUN interface configured: {self.config.network.interface_name}")
    
    async def _setup_obfuscation(self) -> None:
        """Setup traffic obfuscation"""
        obf_config = ObfuscationConfig(
            method=self.config.obfuscation.method,
            target_host=self.client_config.server_address,
            target_port=443 if self.config.obfuscation.method == "tls" else 80,
            decoy_traffic=self.config.obfuscation.decoy_traffic,
            port_hopping=self.config.obfuscation.port_hopping
        )
        
        if self.config.obfuscation.method == "tls":
            self.obfuscator = TLSObfuscator(obf_config)
        elif self.config.obfuscation.method == "http":
            self.obfuscator = HTTPObfuscator(obf_config)
        elif self.config.obfuscation.method == "dns":
            self.obfuscator = DNSObfuscator(obf_config)
        
        if self.obfuscator:
            await self.obfuscator.start()
            self.logger.info(f"Obfuscation enabled: {self.config.obfuscation.method}")
    
    async def _perform_handshake(self) -> None:
        """Perform handshake with server"""
        try:
            # Decode server public key
            import base64
            server_public_key = base64.b64decode(self.client_config.server_public_key)
            
            # Create handshake instance
            self.handshake = NoiseHandshake(
                self.key_manager,
                is_initiator=True,  # Client is initiator
                peer_public_key=server_public_key,
                preshared_key=None  # Could add PSK support
            )
            
            # Send initiation
            initiation_data = self.handshake.create_initiation()
            
            # Obfuscate if enabled
            if self.obfuscator:
                initiation_data = await self.obfuscator.obfuscate(initiation_data)
            
            await self.server_connection.send(initiation_data)
            
            # Wait for response (with timeout)
            response_data = await self._wait_for_handshake_response()
            
            # Deobfuscate if enabled
            if self.obfuscator:
                response_data = await self.obfuscator.deobfuscate(response_data)
            
            # Process response
            self.handshake.process_response(response_data)
            
            if not self.handshake.is_established():
                raise HandshakeError("Handshake not established")
            
            # Setup session cipher
            await self._setup_session_cipher()
            
            self.authenticated = True
            self.logger.info("Handshake completed successfully")
            
        except Exception as e:
            raise HandshakeError(f"Handshake failed: {e}")
    
    async def _wait_for_handshake_response(self, timeout: float = 10.0) -> bytes:
        """Wait for handshake response from server"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # This is simplified - in practice you'd set up proper packet handling
                # For now, we'll simulate receiving the response
                await asyncio.sleep(0.1)
                
                # In real implementation, this would come from UDP connection
                # For demo purposes, we'll return dummy data
                return b"dummy_handshake_response"
                
            except asyncio.TimeoutError:
                continue
        
        raise HandshakeError("Handshake response timeout")
    
    async def _setup_session_cipher(self) -> None:
        """Setup session cipher for data encryption"""
        try:
            # Get session keys from handshake
            sending_key, receiving_key = self.handshake.get_session_keys()
            
            # Create session cipher
            cipher = create_cipher(self.config.crypto.cipher, sending_key)
            session_id = self.server_connection.connection_id.to_bytes(8, 'big')
            self.session_cipher = SessionCipher(cipher, session_id)
            
            self.logger.info("Session cipher established")
            
        except Exception as e:
            raise SecureVPNError(f"Failed to setup session cipher: {e}")
    
    async def _handle_tun_packet(self, packet: bytes) -> None:
        """Handle packet from TUN interface - send to server"""
        if not self.authenticated or not self.session_cipher:
            return
        
        try:
            # Encrypt packet
            nonce, ciphertext = self.session_cipher.encrypt_packet(packet)
            
            # Combine nonce and ciphertext
            encrypted_data = nonce + ciphertext
            
            # Obfuscate if enabled
            if self.obfuscator:
                encrypted_data = await self.obfuscator.obfuscate(encrypted_data)
            
            # Send to server
            await self.server_connection.send(encrypted_data)
            
            self.bytes_sent += len(encrypted_data)
            self.packets_sent += 1
            
        except Exception as e:
            self.logger.error(f"Error handling TUN packet: {e}")
    
    async def _handle_server_packet(self, data: bytes) -> None:
        """Handle packet from server - decrypt and forward to TUN"""
        if not self.authenticated or not self.session_cipher:
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
            plaintext = self.session_cipher.decrypt_packet(nonce, ciphertext)
            
            # Forward to TUN interface
            await self.tun_interface.write_packet(plaintext)
            
            self.bytes_received += len(data)
            self.packets_received += 1
            
        except Exception as e:
            self.logger.error(f"Error handling server packet: {e}")
    
    async def _keepalive_loop(self) -> None:
        """Send keepalive packets to server"""
        while self.connected:
            try:
                await asyncio.sleep(self.client_config.keepalive_interval if hasattr(self.client_config, 'keepalive_interval') else 25)
                
                if self.authenticated and self.session_cipher:
                    # Send keepalive packet
                    keepalive_data = b"KEEPALIVE"
                    nonce, ciphertext = self.session_cipher.encrypt_packet(keepalive_data)
                    encrypted_data = nonce + ciphertext
                    
                    if self.obfuscator:
                        encrypted_data = await self.obfuscator.obfuscate(encrypted_data)
                    
                    await self.server_connection.send(encrypted_data)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Keepalive error: {e}")
    
    async def _key_rotation_loop(self) -> None:
        """Handle key rotation"""
        while self.connected:
            try:
                await asyncio.sleep(self.config.crypto.key_rotation_interval)
                
                if self.key_manager.should_rotate_keys():
                    self.logger.info("Rotating client keys...")
                    
                    # This would trigger a new handshake in practice
                    # For now, just rotate the keys
                    new_keypair = self.key_manager.rotate_keys()
                    
                    # Save new keys
                    self.key_manager.save_keypair_to_files(
                        new_keypair,
                        self.client_config.private_key_path,
                        self.client_config.public_key_path
                    )
                    
                    self.logger.info("Client keys rotated")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Key rotation error: {e}")
    
    async def auto_reconnect(self, max_attempts: int = 5) -> None:
        """Automatically reconnect on connection loss"""
        for attempt in range(max_attempts):
            try:
                self.logger.info(f"Reconnection attempt {attempt + 1}/{max_attempts}")
                
                await self.disconnect()
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                await self.connect()
                
                self.reconnect_count += 1
                self.logger.info("Reconnection successful")
                return
                
            except Exception as e:
                self.logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                
                if attempt == max_attempts - 1:
                    self.logger.error("All reconnection attempts failed")
                    raise SecureVPNError("Failed to reconnect to server")
    
    def get_stats(self) -> dict:
        """Get client statistics"""
        uptime = time.time() - self.connection_start_time if self.connection_start_time else 0
        
        return {
            "connected": self.connected,
            "authenticated": self.authenticated,
            "uptime": uptime,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "reconnect_count": self.reconnect_count,
            "server_address": f"{self.client_config.server_address}:{self.client_config.server_port}",
            "obfuscation_enabled": self.config.obfuscation.enabled,
            "assigned_ip": str(self.assigned_ip) if self.assigned_ip else None
        }
