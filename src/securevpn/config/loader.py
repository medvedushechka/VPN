"""
Configuration loader for SecureVPN
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from .models import VPNConfig
from ..exceptions import ConfigurationError


class ConfigLoader:
    """Load and validate VPN configuration from various sources"""
    
    @staticmethod
    def from_file(config_path: Path) -> VPNConfig:
        """Load configuration from YAML file"""
        try:
            if not config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                raise ConfigurationError("Configuration file is empty")
            
            return VPNConfig(**config_data)
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    @staticmethod
    def from_dict(config_data: Dict[str, Any]) -> VPNConfig:
        """Load configuration from dictionary"""
        try:
            return VPNConfig(**config_data)
        except Exception as e:
            raise ConfigurationError(f"Invalid configuration data: {e}")
    
    @staticmethod
    def to_file(config: VPNConfig, config_path: Path) -> None:
        """Save configuration to YAML file"""
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    config.dict(exclude_none=True),
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False
                )
                
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}")
    
    @staticmethod
    def create_server_template() -> Dict[str, Any]:
        """Create a server configuration template"""
        return {
            "mode": "server",
            "crypto": {
                "cipher": "chacha20poly1305",
                "key_exchange": "curve25519",
                "hash_function": "blake2s",
                "key_rotation_interval": 120
            },
            "network": {
                "interface_name": "svpn0",
                "mtu": 1420,
                "ipv4_network": "10.8.0.0/24",
                "dns_servers": ["1.1.1.1", "8.8.8.8"]
            },
            "obfuscation": {
                "enabled": True,
                "method": "tls",
                "port_hopping": True,
                "decoy_traffic": False
            },
            "server": {
                "bind_address": "0.0.0.0",
                "port": 51820,
                "max_clients": 100,
                "keepalive_interval": 25,
                "private_key_path": "server_private.key",
                "public_key_path": "server_public.key"
            },
            "logging": {
                "level": "INFO",
                "file_path": "/var/log/securevpn/server.log",
                "max_file_size": 10485760,
                "backup_count": 5
            }
        }
    
    @staticmethod
    def create_client_template(server_address: str, server_public_key: str) -> Dict[str, Any]:
        """Create a client configuration template"""
        return {
            "mode": "client",
            "crypto": {
                "cipher": "chacha20poly1305",
                "key_exchange": "curve25519",
                "hash_function": "blake2s",
                "key_rotation_interval": 120
            },
            "network": {
                "interface_name": "svpn0",
                "mtu": 1420,
                "dns_servers": ["1.1.1.1", "8.8.8.8"]
            },
            "obfuscation": {
                "enabled": True,
                "method": "tls",
                "port_hopping": True,
                "decoy_traffic": False
            },
            "client": {
                "server_address": server_address,
                "server_port": 51820,
                "server_public_key": server_public_key,
                "private_key_path": "client_private.key",
                "public_key_path": "client_public.key",
                "allowed_ips": ["0.0.0.0/0"],
                "split_tunneling": False
            },
            "logging": {
                "level": "INFO",
                "max_file_size": 10485760,
                "backup_count": 5
            }
        }
