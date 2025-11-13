"""
HTTP obfuscation for SecureVPN

Makes VPN traffic appear as legitimate HTTP traffic by wrapping
packets in HTTP request/response format.
"""

import random
import time
import base64
from typing import Tuple, List, Dict

from .base import BaseObfuscator, ObfuscationConfig
from ..crypto.utils import secure_random
from ..exceptions import ObfuscationError


class HTTPObfuscator(BaseObfuscator):
    """HTTP traffic obfuscation"""
    
    def __init__(self, config: ObfuscationConfig):
        """Initialize HTTP obfuscator"""
        super().__init__(config)
        
        # HTTP session state
        self.session_id = base64.b64encode(secure_random(16)).decode('ascii')
        self.request_counter = 0
        
        # Realistic HTTP parameters
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        
        self.content_types = [
            "application/json",
            "application/x-www-form-urlencoded",
            "text/plain",
            "application/octet-stream"
        ]
        
        # Common HTTP paths
        self.http_paths = [
            "/api/v1/data",
            "/api/sync",
            "/upload",
            "/download",
            "/status",
            "/health",
            "/metrics",
            "/analytics"
        ]
    
    async def obfuscate(self, data: bytes) -> bytes:
        """Obfuscate data as HTTP request"""
        self.request_counter += 1
        
        # Encode data as base64 for HTTP transport
        encoded_data = base64.b64encode(data).decode('ascii')
        
        # Create realistic HTTP request
        method = random.choice(["POST", "PUT", "PATCH"])
        path = random.choice(self.http_paths)
        user_agent = random.choice(self.user_agents)
        content_type = random.choice(self.content_types)
        
        # Add query parameters for GET-like appearance
        if random.random() < 0.3:  # 30% chance
            query_params = self._generate_query_params()
            path += "?" + query_params
        
        # Build HTTP request
        http_request = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: {self.config.target_host}\r\n"
            f"User-Agent: {user_agent}\r\n"
            f"Accept: */*\r\n"
            f"Accept-Language: en-US,en;q=0.9\r\n"
            f"Accept-Encoding: gzip, deflate, br\r\n"
            f"Connection: keep-alive\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(encoded_data)}\r\n"
            f"X-Session-ID: {self.session_id}\r\n"
            f"X-Request-ID: {self.request_counter}\r\n"
        )
        
        # Add realistic headers
        if random.random() < 0.5:
            http_request += f"Referer: https://{self.config.target_host}/\r\n"
        
        if random.random() < 0.3:
            csrf_token = base64.b64encode(secure_random(16)).decode('ascii')
            http_request += f"X-CSRF-Token: {csrf_token}\r\n"
        
        # End headers and add body
        http_request += "\r\n" + encoded_data
        
        return http_request.encode('utf-8')
    
    async def deobfuscate(self, data: bytes) -> bytes:
        """Extract VPN data from HTTP-obfuscated packet"""
        try:
            http_data = data.decode('utf-8')
            
            # Split headers and body
            if "\r\n\r\n" not in http_data:
                raise ObfuscationError("Invalid HTTP format")
            
            headers, body = http_data.split("\r\n\r\n", 1)
            
            # Parse headers to validate format
            lines = headers.split("\r\n")
            if not lines:
                raise ObfuscationError("No HTTP headers found")
            
            # Check if it's a valid HTTP request/response
            first_line = lines[0]
            if not (first_line.startswith(("GET", "POST", "PUT", "PATCH", "DELETE")) or 
                   first_line.startswith("HTTP/")):
                raise ObfuscationError("Invalid HTTP request/response")
            
            # Decode base64 body
            try:
                decoded_data = base64.b64decode(body.encode('ascii'))
                return decoded_data
            except Exception:
                raise ObfuscationError("Failed to decode HTTP body")
                
        except UnicodeDecodeError:
            raise ObfuscationError("Invalid UTF-8 in HTTP data")
        except Exception as e:
            raise ObfuscationError(f"Failed to deobfuscate HTTP data: {e}")
    
    def _generate_query_params(self) -> str:
        """Generate realistic query parameters"""
        params = []
        
        # Common parameter names
        param_names = ["id", "type", "format", "version", "timestamp", "token", "session"]
        
        num_params = random.randint(1, 3)
        for _ in range(num_params):
            name = random.choice(param_names)
            value = self._generate_param_value()
            params.append(f"{name}={value}")
        
        return "&".join(params)
    
    def _generate_param_value(self) -> str:
        """Generate realistic parameter value"""
        value_types = [
            lambda: str(random.randint(1, 9999)),  # Numeric
            lambda: base64.b64encode(secure_random(8)).decode('ascii')[:12],  # Token-like
            lambda: str(int(time.time())),  # Timestamp
            lambda: random.choice(["json", "xml", "csv", "binary"]),  # Format
        ]
        
        return random.choice(value_types)()
    
    def get_target_endpoint(self) -> Tuple[str, int]:
        """Get target endpoint for HTTP obfuscation"""
        # Use standard HTTP/HTTPS ports
        port = 443 if self.config.target_port == 443 else 80
        return (self.config.target_host, port)
    
    async def start(self) -> None:
        """Start HTTP obfuscation"""
        await super().start()
        
        # Reset session state
        self.session_id = base64.b64encode(secure_random(16)).decode('ascii')
        self.request_counter = 0
    
    def get_stats(self) -> dict:
        """Get HTTP obfuscation statistics"""
        stats = super().get_stats()
        stats.update({
            "session_id": self.session_id,
            "request_counter": self.request_counter,
            "user_agents_count": len(self.user_agents)
        })
        return stats
