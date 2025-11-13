"""
Base obfuscation interface and common utilities
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

from ..exceptions import ObfuscationError


@dataclass
class ObfuscationConfig:
    """Configuration for traffic obfuscation"""
    method: str = "tls"
    target_host: str = "cloudflare.com"
    target_port: int = 443
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    decoy_traffic: bool = False
    port_hopping: bool = True
    randomize_timing: bool = True


class BaseObfuscator(ABC):
    """Base class for all obfuscation methods"""
    
    def __init__(self, config: ObfuscationConfig):
        """
        Initialize obfuscator
        
        Args:
            config: Obfuscation configuration
        """
        self.config = config
        self.is_active = False
    
    @abstractmethod
    async def obfuscate(self, data: bytes) -> bytes:
        """
        Obfuscate outgoing data
        
        Args:
            data: Raw VPN data to obfuscate
            
        Returns:
            Obfuscated data that looks like legitimate traffic
        """
        pass
    
    @abstractmethod
    async def deobfuscate(self, data: bytes) -> bytes:
        """
        Deobfuscate incoming data
        
        Args:
            data: Obfuscated data received from network
            
        Returns:
            Original VPN data
        """
        pass
    
    @abstractmethod
    def get_target_endpoint(self) -> Tuple[str, int]:
        """
        Get the target endpoint that traffic should appear to be going to
        
        Returns:
            Tuple of (host, port)
        """
        pass
    
    async def start(self) -> None:
        """Start the obfuscator"""
        self.is_active = True
    
    async def stop(self) -> None:
        """Stop the obfuscator"""
        self.is_active = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get obfuscation statistics"""
        return {
            "method": self.config.method,
            "is_active": self.is_active,
            "target_host": self.config.target_host,
            "target_port": self.config.target_port
        }
