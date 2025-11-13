"""
Simple VPN Protocol Adapter
Адаптер для работы с нашим упрощенным VPN клиентом
"""

import asyncio
import socket
import logging
from typing import Dict, Optional, Set
from ipaddress import IPv4Address, IPv4Network

class SimpleVPNAdapter:
    """Адаптер для простого VPN протокола"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 51820):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.clients: Dict[str, dict] = {}  # client_addr -> client_info
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        # IP pool для клиентов
        self.network = IPv4Network('10.8.0.0/24')
        self.available_ips = set(self.network.hosts())
        self.server_ip = IPv4Address('10.8.0.1')
        self.available_ips.discard(self.server_ip)
        
    async def start(self):
        """Запуск адаптера"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.setblocking(False)
            self.running = True
            
            self.logger.info(f"🚀 Simple VPN Adapter запущен на {self.host}:{self.port}")
            
            # Запускаем обработку пакетов
            asyncio.create_task(self._handle_packets())
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка запуска адаптера: {e}")
            raise
    
    async def _handle_packets(self):
        """Обработка входящих пакетов"""
        while self.running:
            try:
                # Получаем пакет от клиента
                loop = asyncio.get_event_loop()
                data, addr = await loop.sock_recvfrom(self.socket, 1024)
                
                await self._process_packet(data, addr)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Ошибка обработки пакета: {e}")
    
    async def _process_packet(self, data: bytes, addr: tuple):
        """Обработка пакета от клиента"""
        client_key = f"{addr[0]}:{addr[1]}"
        
        try:
            if data == b"SECUREVPN_HANDSHAKE":
                # Handshake от нашего клиента
                await self._handle_handshake(addr)
                
            elif data.startswith(b"PING"):
                # Ping от клиента
                await self._handle_ping(addr)
                
            elif data.startswith(b"CONNECT"):
                # Запрос на подключение
                await self._handle_connect(addr)
                
            elif data.startswith(b"DISCONNECT"):
                # Отключение клиента
                await self._handle_disconnect(addr)
                
            else:
                # Обычный трафик - туннелируем
                await self._handle_traffic(data, addr)
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка обработки пакета от {addr}: {e}")
    
    async def _handle_handshake(self, addr: tuple):
        """Обработка handshake"""
        client_key = f"{addr[0]}:{addr[1]}"
        
        if client_key not in self.clients:
            # Новый клиент - назначаем IP
            if self.available_ips:
                client_ip = self.available_ips.pop()
                self.clients[client_key] = {
                    'ip': client_ip,
                    'addr': addr,
                    'connected_at': asyncio.get_event_loop().time(),
                    'last_seen': asyncio.get_event_loop().time()
                }
                
                self.logger.info(f"✅ Новый клиент {addr} получил IP {client_ip}")
                
                # Отправляем подтверждение
                response = b"HANDSHAKE_OK"
                await self._send_to_client(response, addr)
            else:
                # Нет свободных IP
                response = b"HANDSHAKE_ERROR_NO_IP"
                await self._send_to_client(response, addr)
        else:
            # Клиент уже подключен
            self.clients[client_key]['last_seen'] = asyncio.get_event_loop().time()
            response = b"HANDSHAKE_OK"
            await self._send_to_client(response, addr)
    
    async def _handle_ping(self, addr: tuple):
        """Обработка ping"""
        response = b"PONG"
        await self._send_to_client(response, addr)
    
    async def _handle_connect(self, addr: tuple):
        """Обработка запроса подключения"""
        client_key = f"{addr[0]}:{addr[1]}"
        
        if client_key in self.clients:
            client_info = self.clients[client_key]
            client_ip = client_info['ip']
            
            # Отправляем конфигурацию клиенту
            config_data = f"IP:{client_ip},DNS:1.1.1.1,GATEWAY:{self.server_ip}".encode()
            await self._send_to_client(b"CONFIG:" + config_data, addr)
            
            self.logger.info(f"📡 Клиент {addr} подключен с IP {client_ip}")
        else:
            await self._send_to_client(b"CONNECT_ERROR", addr)
    
    async def _handle_disconnect(self, addr: tuple):
        """Обработка отключения клиента"""
        client_key = f"{addr[0]}:{addr[1]}"
        
        if client_key in self.clients:
            client_info = self.clients[client_key]
            client_ip = client_info['ip']
            
            # Возвращаем IP в пул
            self.available_ips.add(client_ip)
            del self.clients[client_key]
            
            self.logger.info(f"👋 Клиент {addr} отключен, IP {client_ip} освобожден")
            
            await self._send_to_client(b"DISCONNECT_OK", addr)
    
    async def _handle_traffic(self, data: bytes, addr: tuple):
        """Обработка обычного трафика"""
        client_key = f"{addr[0]}:{addr[1]}"
        
        if client_key in self.clients:
            # Обновляем время последней активности
            self.clients[client_key]['last_seen'] = asyncio.get_event_loop().time()
            
            # Здесь можно добавить логику туннелирования трафика
            # Пока просто логируем
            self.logger.debug(f"📦 Трафик от {addr}: {len(data)} байт")
    
    async def _send_to_client(self, data: bytes, addr: tuple):
        """Отправка данных клиенту"""
        try:
            loop = asyncio.get_event_loop()
            await loop.sock_sendto(self.socket, data, addr)
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки данных клиенту {addr}: {e}")
    
    async def stop(self):
        """Остановка адаптера"""
        self.running = False
        if self.socket:
            self.socket.close()
        
        self.logger.info("🛑 Simple VPN Adapter остановлен")
    
    def get_stats(self) -> dict:
        """Получение статистики"""
        return {
            'active_clients': len(self.clients),
            'available_ips': len(self.available_ips),
            'clients': {
                addr: {
                    'ip': str(info['ip']),
                    'connected_at': info['connected_at'],
                    'last_seen': info['last_seen']
                }
                for addr, info in self.clients.items()
            }
        }
