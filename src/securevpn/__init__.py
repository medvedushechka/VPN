"""
SecureVPN - High-Performance Encrypted VPN Solution

A modern, high-performance VPN implementation with advanced obfuscation
and military-grade encryption.
"""

__version__ = "1.0.0"
__author__ = "SecureVPN Team"
__license__ = "MIT"

from .config import VPNConfig
from .exceptions import SecureVPNError

__all__ = ["VPNConfig", "SecureVPNError", "__version__"]
