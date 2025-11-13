"""
Traffic obfuscation layer for SecureVPN

Implements various obfuscation techniques to bypass Deep Packet Inspection (DPI)
and make VPN traffic appear as regular HTTPS, DNS, or other protocols.
"""

from .base import BaseObfuscator, ObfuscationConfig
from .tls import TLSObfuscator
from .http import HTTPObfuscator
from .dns import DNSObfuscator

__all__ = [
    "BaseObfuscator",
    "ObfuscationConfig",
    "TLSObfuscator",
    "HTTPObfuscator", 
    "DNSObfuscator"
]
