"""
Configuration models using Pydantic for validation
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, validator, IPvAnyAddress
from ipaddress import IPv4Network, IPv6Network


class CryptoConfig(BaseModel):
    """Cryptographic configuration"""
    
    cipher: str = Field(default="chacha20poly1305", description="Encryption cipher")
    key_exchange: str = Field(default="curve25519", description="Key exchange algorithm")
    hash_function: str = Field(default="blake2s", description="Hash function")
    key_rotation_interval: int = Field(default=120, description="Key rotation interval in seconds")
    
    @validator("cipher")
    def validate_cipher(cls, v):
        allowed = ["chacha20poly1305", "aes256gcm"]
        if v not in allowed:
            raise ValueError(f"Cipher must be one of {allowed}")
        return v


class NetworkConfig(BaseModel):
    """Network configuration"""
    
    interface_name: str = Field(default="svpn0", description="TUN interface name")
    mtu: int = Field(default=1420, description="Maximum transmission unit")
    ipv4_network: IPv4Network = Field(default="10.8.0.0/24", description="IPv4 network range")
    ipv6_network: Optional[IPv6Network] = Field(default=None, description="IPv6 network range")
    dns_servers: List[str] = Field(default=["1.1.1.1", "8.8.8.8"], description="DNS servers")
    
    @validator("mtu")
    def validate_mtu(cls, v):
        if not 576 <= v <= 1500:
            raise ValueError("MTU must be between 576 and 1500")
        return v


class ObfuscationConfig(BaseModel):
    """Traffic obfuscation configuration"""
    
    enabled: bool = Field(default=True, description="Enable traffic obfuscation")
    method: str = Field(default="tls", description="Obfuscation method")
    port_hopping: bool = Field(default=True, description="Enable port hopping")
    decoy_traffic: bool = Field(default=False, description="Generate decoy traffic")
    
    @validator("method")
    def validate_method(cls, v):
        allowed = ["tls", "http", "dns", "none"]
        if v not in allowed:
            raise ValueError(f"Obfuscation method must be one of {allowed}")
        return v


class ServerConfig(BaseModel):
    """Server-specific configuration"""
    
    bind_address: str = Field(default="0.0.0.0", description="Server bind address")
    port: int = Field(default=51820, description="Server port")
    max_clients: int = Field(default=100, description="Maximum concurrent clients")
    keepalive_interval: int = Field(default=25, description="Keepalive interval in seconds")
    
    # Key paths
    private_key_path: Path = Field(default=Path("server_private.key"))
    public_key_path: Path = Field(default=Path("server_public.key"))
    
    @validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class ClientConfig(BaseModel):
    """Client-specific configuration"""
    
    server_address: str = Field(..., description="Server address")
    server_port: int = Field(default=51820, description="Server port")
    server_public_key: str = Field(..., description="Server public key")
    
    # Client keys
    private_key_path: Path = Field(default=Path("client_private.key"))
    public_key_path: Path = Field(default=Path("client_public.key"))
    
    # Tunneling options
    allowed_ips: List[str] = Field(default=["0.0.0.0/0"], description="Allowed IP ranges")
    split_tunneling: bool = Field(default=False, description="Enable split tunneling")
    
    @validator("server_port")
    def validate_server_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Server port must be between 1 and 65535")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration"""
    
    level: str = Field(default="INFO", description="Log level")
    file_path: Optional[Path] = Field(default=None, description="Log file path")
    max_file_size: int = Field(default=10485760, description="Max log file size in bytes")
    backup_count: int = Field(default=5, description="Number of backup log files")
    
    @validator("level")
    def validate_level(cls, v):
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()


class VPNConfig(BaseModel):
    """Main VPN configuration"""
    
    mode: str = Field(..., description="Operation mode: server or client")
    crypto: CryptoConfig = Field(default_factory=CryptoConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    obfuscation: ObfuscationConfig = Field(default_factory=ObfuscationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Mode-specific configs
    server: Optional[ServerConfig] = Field(default=None)
    client: Optional[ClientConfig] = Field(default=None)
    
    @validator("mode")
    def validate_mode(cls, v):
        if v not in ["server", "client"]:
            raise ValueError("Mode must be 'server' or 'client'")
        return v
    
    @validator("server")
    def validate_server_config(cls, v, values):
        if values.get("mode") == "server" and v is None:
            raise ValueError("Server configuration required when mode is 'server'")
        return v
    
    @validator("client")
    def validate_client_config(cls, v, values):
        if values.get("mode") == "client" and v is None:
            raise ValueError("Client configuration required when mode is 'client'")
        return v
