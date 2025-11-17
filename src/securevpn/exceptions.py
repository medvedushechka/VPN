"""
Custom exceptions for SecureVPN
"""


class SecureVPNError(Exception):
    """Base exception for all SecureVPN errors"""
    pass


class CryptographyError(SecureVPNError):
    """Raised when cryptographic operations fail"""
    pass


class NetworkError(SecureVPNError):
    """Raised when network operations fail"""
    pass


class ConfigurationError(SecureVPNError):
    """Raised when configuration is invalid"""
    pass


class AuthenticationError(SecureVPNError):
    """Raised when authentication fails"""
    pass


class TunnelError(SecureVPNError):
    """Raised when tunnel operations fail"""
    pass


class HandshakeError(SecureVPNError):
    """Raised when handshake process fails"""
    pass


class ObfuscationError(SecureVPNError):
    """Raised when traffic obfuscation fails"""
    pass
