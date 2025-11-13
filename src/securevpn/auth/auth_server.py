"""
HTTP Authentication server for SecureVPN GUI clients
"""

import json
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from aiohttp import web, web_request
from aiohttp.web_response import Response

from .user_manager import UserManager
from .models import User, AuthToken
from ..config import VPNConfig
from ..exceptions import SecureVPNError


class AuthServer:
    """HTTP server for client authentication and VPN configuration"""
    
    def __init__(self, user_manager: UserManager, vpn_config: VPNConfig, 
                 host: str = "127.0.0.1", port: int = 8080):
        """
        Initialize authentication server
        
        Args:
            user_manager: User manager instance
            vpn_config: VPN configuration
            host: Server host
            port: Server port
        """
        self.user_manager = user_manager
        self.vpn_config = vpn_config
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup HTTP routes"""
        self.app.router.add_post('/auth/login', self._handle_login)
        self.app.router.add_post('/auth/logout', self._handle_logout)
        self.app.router.add_get('/auth/validate', self._handle_validate)
        self.app.router.add_get('/vpn/config', self._handle_get_config)
        self.app.router.add_get('/vpn/server-key', self._handle_get_server_key)
        self.app.router.add_get('/health', self._handle_health)
        
        # CORS middleware for GUI applications
        self.app.middlewares.append(self._cors_middleware)
    
    async def _cors_middleware(self, request: web_request.Request, handler) -> Response:
        """CORS middleware for cross-origin requests"""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    
    async def _handle_login(self, request: web_request.Request) -> Response:
        """Handle user login"""
        try:
            data = await request.json()
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return web.json_response({
                    'success': False,
                    'error': 'Username and password required'
                }, status=400)
            
            # Authenticate user
            user = self.user_manager.authenticate_user(username, password)
            if not user:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid credentials'
                }, status=401)
            
            # Create authentication token
            token = self.user_manager.create_auth_token(username, expires_in_hours=24)
            if not token:
                return web.json_response({
                    'success': False,
                    'error': 'Failed to create authentication token'
                }, status=500)
            
            return web.json_response({
                'success': True,
                'token': token.token,
                'expires_at': token.expires_at,
                'user': {
                    'username': user.username,
                    'last_login': user.last_login
                }
            })
            
        except json.JSONDecodeError:
            return web.json_response({
                'success': False,
                'error': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)
    
    async def _handle_logout(self, request: web_request.Request) -> Response:
        """Handle user logout"""
        try:
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return web.json_response({
                    'success': False,
                    'error': 'Authorization token required'
                }, status=401)
            
            token_string = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Invalidate token
            success = self.user_manager.invalidate_token(token_string)
            
            return web.json_response({
                'success': success,
                'message': 'Logged out successfully' if success else 'Token not found'
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)
    
    async def _handle_validate(self, request: web_request.Request) -> Response:
        """Validate authentication token"""
        try:
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return web.json_response({
                    'success': False,
                    'error': 'Authorization token required'
                }, status=401)
            
            token_string = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Validate token
            token = self.user_manager.validate_token(token_string)
            if not token:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid or expired token'
                }, status=401)
            
            # Get user info
            user = self.user_manager.get_user(token.username)
            if not user:
                return web.json_response({
                    'success': False,
                    'error': 'User not found'
                }, status=404)
            
            return web.json_response({
                'success': True,
                'token': {
                    'expires_at': token.expires_at,
                    'username': token.username
                },
                'user': {
                    'username': user.username,
                    'last_login': user.last_login,
                    'is_active': user.is_active
                }
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)
    
    async def _handle_get_config(self, request: web_request.Request) -> Response:
        """Get VPN configuration for authenticated user"""
        try:
            # Validate authentication
            token = await self._validate_request(request)
            if not token:
                return web.json_response({
                    'success': False,
                    'error': 'Authentication required'
                }, status=401)
            
            # Generate client configuration
            client_config = {
                'server_address': self._get_server_address(),
                'server_port': self.vpn_config.server.port,
                'server_public_key': self._get_server_public_key(),
                'obfuscation': {
                    'enabled': self.vpn_config.obfuscation.enabled,
                    'method': self.vpn_config.obfuscation.method
                },
                'crypto': {
                    'cipher': self.vpn_config.crypto.cipher,
                    'key_rotation_interval': self.vpn_config.crypto.key_rotation_interval
                },
                'network': {
                    'mtu': self.vpn_config.network.mtu,
                    'dns_servers': self.vpn_config.network.dns_servers
                }
            }
            
            return web.json_response({
                'success': True,
                'config': client_config
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)
    
    async def _handle_get_server_key(self, request: web_request.Request) -> Response:
        """Get server public key"""
        try:
            # This endpoint might be public for initial setup
            public_key = self._get_server_public_key()
            
            if not public_key:
                return web.json_response({
                    'success': False,
                    'error': 'Server public key not available'
                }, status=500)
            
            return web.json_response({
                'success': True,
                'public_key': public_key
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)
    
    async def _handle_health(self, request: web_request.Request) -> Response:
        """Health check endpoint"""
        stats = self.user_manager.get_stats()
        
        return web.json_response({
            'success': True,
            'status': 'healthy',
            'stats': stats,
            'server_info': {
                'version': '1.0.0',
                'uptime': 'N/A'  # Could add actual uptime tracking
            }
        })
    
    async def _validate_request(self, request: web_request.Request) -> Optional[AuthToken]:
        """Validate request authentication"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token_string = auth_header[7:]  # Remove 'Bearer ' prefix
        return self.user_manager.validate_token(token_string)
    
    def _get_server_address(self) -> str:
        """Get server address for clients"""
        # In production, this should be the public IP
        # For now, return the configured bind address or detect public IP
        bind_address = self.vpn_config.server.bind_address
        if bind_address == "0.0.0.0":
            # Try to get public IP or use localhost
            return "127.0.0.1"  # This should be replaced with actual public IP detection
        return bind_address
    
    def _get_server_public_key(self) -> Optional[str]:
        """Get server public key"""
        try:
            public_key_path = self.vpn_config.server.public_key_path
            if public_key_path.exists():
                with open(public_key_path, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return None
    
    async def start(self) -> None:
        """Start the authentication server"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            site = web.TCPSite(self.runner, self.host, self.port)
            await site.start()
            
            print(f"Authentication server started on http://{self.host}:{self.port}")
            
        except Exception as e:
            raise SecureVPNError(f"Failed to start authentication server: {e}")
    
    async def stop(self) -> None:
        """Stop the authentication server"""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
        return {
            'host': self.host,
            'port': self.port,
            'running': self.runner is not None,
            'user_stats': self.user_manager.get_stats()
        }
