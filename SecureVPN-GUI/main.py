#!/usr/bin/env python3
"""
SecureVPN GUI Client
Простое и красивое приложение для подключения к VPN
"""

import sys
import os
import json
import time
import subprocess
import threading
import socket
import struct
import select
import ctypes
import ctypes.wintypes
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

import requests
import psutil
import asyncio
from ping3 import ping
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QMessageBox, QSystemTrayIcon, QMenu, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QPixmap, QFont, QPalette, QColor, QMovie
import winshell
import win32api
import win32con

# Импортируем SecureVPN клиент
from securevpn.client import SecureVPNClient
from securevpn.config import ConfigLoader

# Конфигурация сервера
SERVER_CONFIG = {
    "api_url": "http://79.132.136.194:8080",  # Внешний IP для API
    "vpn_server": "79.132.136.194",
    "vpn_port": 51822,  # Порт VPN сервера
    "server_public_key": "yzY1xSqfLP6AIlf6l8NKIJ4MKuN/Ay4zcXjwVoXQV1w="
}

class NetworkChecker(QThread):
    """Проверка сетевого подключения"""
    result_ready = pyqtSignal(dict)
    
    def run(self):
        result = {
            "internet": False,
            "server": False,
            "api": False,
            "error": None
        }
        
        try:
            # Проверка интернета
            response = ping("8.8.8.8", timeout=3)
            result["internet"] = response is not None
            
            if result["internet"]:
                # Проверка сервера
                server_response = ping(SERVER_CONFIG["vpn_server"], timeout=5)
                result["server"] = server_response is not None
                
                # Проверка API
                try:
                    api_response = requests.get(
                        f"{SERVER_CONFIG['api_url']}/health",
                        timeout=5
                    )
                    result["api"] = api_response.status_code == 200
                except:
                    result["api"] = False
            
        except Exception as e:
            result["error"] = str(e)
        
        self.result_ready.emit(result)

class AuthWorker(QThread):
    """Авторизация пользователя"""
    auth_result = pyqtSignal(dict)
    
    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password
    
    def run(self):
        result = {
            "success": False,
            "token": None,
            "error": None,
            "user_info": None
        }
        
        try:
            response = requests.post(
                f"{SERVER_CONFIG['api_url']}/auth/login",
                json={
                    "username": self.username,
                    "password": self.password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    result["success"] = True
                    result["token"] = data.get("token")
                    result["user_info"] = data.get("user")
                else:
                    result["error"] = data.get("error", "Неизвестная ошибка")
            else:
                result["error"] = f"Ошибка сервера: {response.status_code}"
                
        except requests.exceptions.ConnectTimeout:
            result["error"] = "Время ожидания подключения истекло"
        except requests.exceptions.ConnectionError:
            result["error"] = "Не удается подключиться к серверу"
        except Exception as e:
            result["error"] = f"Ошибка авторизации: {str(e)}"
        
        self.auth_result.emit(result)

class RealVPNClient:
    """Полноценный VPN клиент с туннелированием трафика через SecureVPN"""
    
    def __init__(self):
        self.server_ip = SERVER_CONFIG['vpn_server']
        self.server_port = SERVER_CONFIG['vpn_port']
        self.is_connected = False
        self.vpn_client: Optional[SecureVPNClient] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
    
    def setup_vpn_tunnel(self):
        """Настройка полноценного VPN туннеля с использованием SecureVPNClient"""
        try:
            print(f"🔗 Создание VPN туннеля к {self.server_ip}:{self.server_port}")
            
            # Создаём новый event loop для asyncio
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            
            # Загружаем конфиг клиента
            config_path = Path.home() / "securevpn_client.yaml"
            if not config_path.exists():
                print(f"⚠️  Конфиг не найден: {config_path}")
                print("📝 Создаём конфиг...")
                self._create_default_config(config_path)
            
            # Загружаем конфиг
            loader = ConfigLoader()
            config = loader.from_file(config_path)
            
            # Создаём VPN клиент
            self.vpn_client = SecureVPNClient(config)
            
            # Подключаемся (это блокирующий вызов)
            print("⏳ Подключение к VPN серверу...")
            self.event_loop.run_until_complete(self.vpn_client.connect())
            
            self.is_connected = True
            print("✅ VPN туннель установлен!")
            print("✅ Весь трафик маршрутизируется через VPN")
            
            return True, "VPN туннель установлен. Весь трафик маршрутизируется через VPN."
            
        except Exception as e:
            print(f"❌ Ошибка создания туннеля: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Не удалось создать VPN туннель: {e}"
    
    def _create_default_config(self, config_path: Path) -> None:
        """Создание конфига клиента по умолчанию"""
        config_content = f"""
client:
  server_address: {self.server_ip}
  server_port: {self.server_port}
  server_public_key: {SERVER_CONFIG['server_public_key']}
  allowed_ips:
    - 0.0.0.0/0
  
network:
  interface_name: svpn0
  ipv4_network: 10.8.0.0/24
  dns_servers:
    - 1.1.1.1
    - 8.8.8.8
  mtu: 1420

crypto:
  cipher: chacha20poly1305
  
obfuscation:
  enabled: false
"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(config_content)
        print(f"✅ Конфиг создан: {config_path}")
    
    def _get_default_gateway(self):
        """Получение текущего шлюза по умолчанию"""
        try:
            result = subprocess.run(['route', 'print', '0.0.0.0'], 
                                  capture_output=True, text=True, shell=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if '0.0.0.0' in line and 'Gateway' not in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]  # IP шлюза
        except:
            pass
        return "192.168.1.1"  # Fallback
    
    def _setup_routing(self):
        """Настройка маршрутизации для VPN"""
        try:
            # Добавляем маршрут для VPN сервера через оригинальный шлюз
            subprocess.run([
                'route', 'add', self.server_ip, 'mask', '255.255.255.255', self.original_gateway
            ], shell=True, capture_output=True)
            
            # Перенаправляем весь трафик через VPN
            subprocess.run([
                'route', 'add', '0.0.0.0', 'mask', '128.0.0.0', self.vpn_interface_ip
            ], shell=True, capture_output=True)
            
            subprocess.run([
                'route', 'add', '128.0.0.0', 'mask', '128.0.0.0', self.vpn_interface_ip  
            ], shell=True, capture_output=True)
            
            print("✅ Маршрутизация настроена")
            
        except Exception as e:
            print(f"❌ Ошибка настройки маршрутизации: {e}")
    
    def _run_tunnel(self):
        """Основной цикл туннелирования трафика"""
        print("🚇 Запуск туннеля трафика...")
        
        # Создаем raw socket для перехвата пакетов (требует прав администратора)
        try:
            # Простая реализация - перенаправляем DNS запросы
            self._redirect_dns()
            
            while self.is_connected:
                time.sleep(1)
                # Здесь можно добавить логику туннелирования
                
        except Exception as e:
            print(f"❌ Ошибка в туннеле: {e}")
    
    def _redirect_dns(self):
        """Перенаправление DNS запросов через VPN"""
        try:
            # Изменяем DNS на публичные серверы
            subprocess.run([
                'netsh', 'interface', 'ip', 'set', 'dns', 
                'name="Ethernet"', 'static', '1.1.1.1', 'primary'
            ], shell=True, capture_output=True)
            
            subprocess.run([
                'netsh', 'interface', 'ip', 'add', 'dns',
                'name="Ethernet"', '8.8.8.8', 'index=2'  
            ], shell=True, capture_output=True)
            
            print("✅ DNS перенаправлен через VPN")
            
        except Exception as e:
            print(f"❌ Ошибка настройки DNS: {e}")
    
    def disconnect_tunnel(self):
        """Отключение VPN туннеля"""
        try:
            print("🔌 Отключение VPN туннеля...")
            
            self.is_connected = False
            
            # Отключаемся от VPN сервера
            if self.vpn_client and self.event_loop:
                try:
                    self.event_loop.run_until_complete(self.vpn_client.disconnect())
                except Exception as e:
                    print(f"⚠️  Ошибка при отключении: {e}")
            
            # Закрываем event loop
            if self.event_loop:
                self.event_loop.close()
                self.event_loop = None
            
            self.vpn_client = None
            
            print("✅ VPN туннель отключен")
            return True, "VPN отключен."
            
        except Exception as e:
            print(f"❌ Ошибка отключения: {e}")
            return False, f"Ошибка отключения: {e}"
    
    def _restore_routing(self):
        """Восстановление оригинальной маршрутизации"""
        try:
            # Удаляем VPN маршруты
            subprocess.run(['route', 'delete', '0.0.0.0', 'mask', '128.0.0.0'], 
                          shell=True, capture_output=True)
            subprocess.run(['route', 'delete', '128.0.0.0', 'mask', '128.0.0.0'], 
                          shell=True, capture_output=True)
            subprocess.run(['route', 'delete', self.server_ip], 
                          shell=True, capture_output=True)
            
            print("✅ Маршрутизация восстановлена")
            
        except Exception as e:
            print(f"❌ Ошибка восстановления маршрутизации: {e}")
    
    def _restore_dns(self):
        """Восстановление оригинальных DNS настроек"""
        try:
            # Восстанавливаем автоматическое получение DNS
            subprocess.run([
                'netsh', 'interface', 'ip', 'set', 'dns', 
                'name="Ethernet"', 'dhcp'
            ], shell=True, capture_output=True)
            
            print("✅ DNS восстановлен")
            
        except Exception as e:
            print(f"❌ Ошибка восстановления DNS: {e}")

class VPNManager:
    """Управление VPN подключением"""
    
    def __init__(self):
        self.config_path = Path.home() / "securevpn_client.conf"
        self.is_connected = False
        self.vpn_client = RealVPNClient()
    
    def create_config(self, token: str) -> bool:
        """Создание конфигурации WireGuard"""
        try:
            # Получаем простую конфигурацию для текущего тестового клиента
            response = requests.get(
                f"{SERVER_CONFIG['api_url']}/config",
                timeout=10
            )
            
            if response.status_code != 200:
                return False
            
            config_data = response.json()
            if not config_data.get("success"):
                return False
            
            # Используем данные от API сервера
            private_key = config_data.get("private_key", self._generate_private_key())
            server_public_key = config_data.get("server_public_key", SERVER_CONFIG['server_public_key'])
            server_endpoint = config_data.get("server_endpoint", f"{SERVER_CONFIG['vpn_server']}:{SERVER_CONFIG['vpn_port']}")
            address = config_data.get("address", "10.8.0.2/24")
            dns_servers = config_data.get("dns", ["1.1.1.1", "8.8.8.8"])
            allowed_ips = config_data.get("allowed_ips", "0.0.0.0/0")
            
            # Создаем конфигурацию WireGuard для текущего встроенного клиента
            config = f"""[Interface]
PrivateKey = {private_key}
Address = {address}
DNS = {', '.join(dns_servers)}

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = {allowed_ips}
PersistentKeepalive = 25
"""
            
            with open(self.config_path, 'w') as f:
                f.write(config)

            # Дополнительно создаем конфигурацию для полноценного SecureVPN-клиента
            try:
                headers = {}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                full_cfg_response = requests.get(
                    f"{SERVER_CONFIG['api_url']}/vpn/config",
                    headers=headers,
                    timeout=10
                )
                if full_cfg_response.status_code == 200:
                    full_cfg_data = full_cfg_response.json()
                    if full_cfg_data.get("success") and full_cfg_data.get("config"):
                        cfg = full_cfg_data["config"]
                        crypto_cfg = cfg.get("crypto", {})
                        net_cfg = cfg.get("network", {})
                        obf_cfg = cfg.get("obfuscation", {})
                        
                        securevpn_config = {
                            "mode": "client",
                            "crypto": {
                                "cipher": crypto_cfg.get("cipher", "chacha20poly1305"),
                                "key_rotation_interval": crypto_cfg.get("key_rotation_interval", 120),
                            },
                            "network": {
                                # Основная сеть такая же, как на сервере
                                "ipv4_network": net_cfg.get("ipv4_network", "10.8.0.0/24"),
                                "mtu": net_cfg.get("mtu", 1420),
                                "dns_servers": net_cfg.get("dns_servers", ["1.1.1.1", "8.8.8.8"]),
                            },
                            "obfuscation": {
                                "enabled": obf_cfg.get("enabled", False),
                                "method": obf_cfg.get("method", "tls"),
                            },
                            "logging": {
                                "level": "INFO",
                            },
                            "client": {
                                "server_address": cfg.get("server_address", SERVER_CONFIG['vpn_server']),
                                "server_port": cfg.get("server_port", SERVER_CONFIG['vpn_port']),
                                "server_public_key": cfg.get("server_public_key", SERVER_CONFIG['server_public_key']),
                                "private_key_path": str(Path.home() / "securevpn_client_private.key"),
                                "public_key_path": str(Path.home() / "securevpn_client_public.key"),
                                "allowed_ips": ["0.0.0.0/0"],
                                "split_tunneling": False,
                            },
                        }

                        securevpn_config_path = Path.home() / "securevpn_client.yaml"
                        with open(securevpn_config_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(securevpn_config, f, sort_keys=False, allow_unicode=True)
                        print(f"✅ SecureVPN конфигурация создана: {securevpn_config_path}")
            except Exception as e:
                print(f"Ошибка создания конфигурации SecureVPN: {e}")
            
            return True
            
        except Exception as e:
            print(f"Ошибка создания конфигурации: {e}")
            print(f"URL: {SERVER_CONFIG['api_url']}/config")
            if 'response' in locals():
                print(f"HTTP Status: {response.status_code}")
                print(f"Response: {response.text}")
            return False
    
    def _generate_private_key(self) -> str:
        """Генерация приватного ключа"""
        # Используем Python для генерации ключа (без WireGuard)
        import secrets
        import base64
        key = secrets.token_bytes(32)
        return base64.b64encode(key).decode()
    
    def _get_public_key(self, private_key: str) -> str:
        """Получение публичного ключа из приватного"""
        # Для тестирования возвращаем фиктивный ключ
        # В реальном приложении нужна криптографическая библиотека
        import hashlib
        import base64
        hash_obj = hashlib.sha256(private_key.encode())
        return base64.b64encode(hash_obj.digest()).decode()[:44]
    
    def connect(self) -> tuple[bool, str]:
        """Подключение к VPN через реальный туннель"""
        try:
            if not self.config_path.exists():
                return False, "Конфигурация не найдена"
            
            # Используем реальный VPN клиент с туннелированием
            success, message = self.vpn_client.setup_vpn_tunnel()
            
            if success:
                self.is_connected = True
                print("✅ Соединение с VPN сервером активно (тестовый режим)")
                print(f"🌐 Подключение к {SERVER_CONFIG['vpn_server']} установлено")
                return True, message
            else:
                return False, message
                
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    def disconnect(self) -> tuple[bool, str]:
        """Отключение от VPN"""
        try:
            print("🔌 Отключение соединения с VPN сервером...")
            
            # Отключаем реальный VPN туннель
            success, message = self.vpn_client.disconnect_tunnel()
            
            if success:
                self.is_connected = False
                print("✅ Соединение с VPN сервером закрыто")
                return True, message
            else:
                return False, message
            
        except Exception as e:
            return False, f"Ошибка отключения: {str(e)}"
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса подключения"""
        return {
            "connected": self.is_connected,
            "server": SERVER_CONFIG['vpn_server'],
            "port": SERVER_CONFIG['vpn_port'],
            "client_type": "Built-in VPN Client",
            "info": f"Подключен к {SERVER_CONFIG['vpn_server']}:{SERVER_CONFIG['vpn_port']}" if self.is_connected else "Отключен"
        }

class LoginWidget(QWidget):
    """Виджет авторизации"""
    login_success = pyqtSignal(str, dict)  # token, user_info
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Логотип
        logo_label = QLabel()
        logo_pixmap = QPixmap("assets/logo.png")
        if not logo_pixmap.isNull():
            # Масштабируем логотип
            scaled_pixmap = logo_pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            # Fallback если логотип не найден
            logo_label.setText("🔒")
            logo_label.setStyleSheet("font-size: 48px;")
        
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)
        
        # Заголовок
        title = QLabel("SecureVPN")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                color: #2196F3;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(title)
        
        # Подзаголовок
        subtitle = QLabel("Безопасное VPN подключение")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                margin-bottom: 30px;
            }
        """)
        layout.addWidget(subtitle)
        
        # Поля ввода
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Логин")
        self.username_input.setText("Medvedushkaa")  # Предзаполнено
        self.username_input.setStyleSheet(self._get_input_style())
        layout.addWidget(self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(self._get_input_style())
        self.password_input.returnPressed.connect(self.login)
        layout.addWidget(self.password_input)
        
        # Кнопка входа
        self.login_btn = QPushButton("Войти")
        self.login_btn.setStyleSheet(self._get_button_style())
        self.login_btn.clicked.connect(self.login)
        layout.addWidget(self.login_btn)
        
        # Статус
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Прогресс бар
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Проверка сети при запуске
        self.check_network()
    
    def _get_input_style(self) -> str:
        return """
            QLineEdit {
                padding: 12px;
                font-size: 14px;
                border: 2px solid #ddd;
                border-radius: 8px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
        """
    
    def _get_button_style(self) -> str:
        return """
            QPushButton {
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                color: white;
                background: #2196F3;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #1976D2;
            }
            QPushButton:pressed {
                background: #1565C0;
            }
            QPushButton:disabled {
                background: #ccc;
            }
        """
    
    def check_network(self):
        """Проверка сетевого подключения"""
        self.show_status("Проверка подключения...", "info")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Индикатор загрузки
        
        self.network_checker = NetworkChecker()
        self.network_checker.result_ready.connect(self.on_network_check)
        self.network_checker.start()
    
    def on_network_check(self, result: dict):
        """Обработка результата проверки сети"""
        self.progress.setVisible(False)
        
        if result.get("error"):
            self.show_status(f"Ошибка проверки: {result['error']}", "error")
            return
        
        if not result.get("internet"):
            self.show_status("❌ Нет подключения к интернету", "error")
            return
        
        if not result.get("server"):
            self.show_status("❌ Сервер VPN недоступен", "error")
            return
        
        if not result.get("api"):
            self.show_status("❌ API сервер недоступен", "error")
            return
        
        self.show_status("✅ Все системы готовы", "success")
    
    def show_status(self, message: str, status_type: str):
        """Показать статус с цветовым кодированием"""
        colors = {
            "info": "#2196F3",
            "success": "#4CAF50", 
            "error": "#F44336",
            "warning": "#FF9800"
        }
        
        bg_colors = {
            "info": "#E3F2FD",
            "success": "#E8F5E8",
            "error": "#FFEBEE", 
            "warning": "#FFF3E0"
        }
        
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.get(status_type, '#666')};
                background: {bg_colors.get(status_type, '#f5f5f5')};
                font-size: 12px;
                padding: 10px;
                border-radius: 5px;
                border: 1px solid {colors.get(status_type, '#ddd')};
            }}
        """)
    
    def login(self):
        """Авторизация пользователя"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            self.show_status("Введите логин и пароль", "warning")
            return
        
        self.login_btn.setEnabled(False)
        self.show_status("Авторизация...", "info")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        
        self.auth_worker = AuthWorker(username, password)
        self.auth_worker.auth_result.connect(self.on_auth_result)
        self.auth_worker.start()
    
    def on_auth_result(self, result: dict):
        """Обработка результата авторизации"""
        self.progress.setVisible(False)
        self.login_btn.setEnabled(True)
        
        if result.get("success"):
            self.show_status("✅ Авторизация успешна", "success")
            self.login_success.emit(result["token"], result["user_info"])
        else:
            error_msg = result.get("error", "Неизвестная ошибка")
            self.show_status(f"❌ {error_msg}", "error")

class MainWidget(QWidget):
    """Главный виджет управления VPN"""
    
    def __init__(self, token: str, user_info: dict):
        super().__init__()
        self.token = token
        self.user_info = user_info
        self.vpn_manager = VPNManager()
        self.init_ui()
        self.setup_timer()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Приветствие
        welcome = QLabel(f"Добро пожаловать, {self.user_info.get('username', 'Пользователь')}!")
        welcome.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #333;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(welcome)
        
        # Статус подключения
        self.connection_status = QLabel("Отключено")
        self.connection_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_status.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                padding: 20px;
                border-radius: 10px;
                background: #FFEBEE;
                color: #F44336;
            }
        """)
        layout.addWidget(self.connection_status)
        
        # Кнопка подключения
        self.connect_btn = QPushButton("Использовать VPN")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                padding: 15px;
                font-size: 16px;
                font-weight: bold;
                color: white;
                background: #4CAF50;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: #45a049;
            }
            QPushButton:pressed {
                background: #3d8b40;
            }
        """)
        self.connect_btn.clicked.connect(self.toggle_vpn)
        layout.addWidget(self.connect_btn)
        
        # Информация о сервере
        server_info = QFrame()
        server_info.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        server_layout = QVBoxLayout()
        
        server_layout.addWidget(QLabel(f"Сервер: {SERVER_CONFIG['vpn_server']}"))
        server_layout.addWidget(QLabel(f"Порт: {SERVER_CONFIG['vpn_port']}"))
        server_layout.addWidget(QLabel("Шифрование: ChaCha20-Poly1305"))
        
        server_info.setLayout(server_layout)
        layout.addWidget(server_info)
        
        # Лог
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_text)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Создание конфигурации
        self.create_vpn_config()
        
    def create_vpn_config(self):
        """Создание конфигурации VPN"""
        self.log("Создание конфигурации VPN...")
        
        if self.vpn_manager.create_config(self.token):
            self.log("✅ Конфигурация создана")
        else:
            self.log("❌ Ошибка создания конфигурации")
    
    def setup_timer(self):
        """Настройка таймера для проверки статуса"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(2000)  # Каждые 2 секунды
        
    def update_status(self):
        """Обновление статуса подключения"""
        status = self.vpn_manager.get_status()
        connected = status.get("connected")
        
        if connected:
            self.connection_status.setText("🔒 Подключено")
            self.connection_status.setStyleSheet("""
                QLabel {
                    font-size: 24px;
                    font-weight: bold;
                    padding: 20px;
                    border-radius: 10px;
                    background: #E8F5E8;
                    color: #4CAF50;
                }
            """)
            self.connect_btn.setText("Отключить VPN")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    padding: 15px;
                    font-size: 16px;
                    font-weight: bold;
                    color: white;
                    background: #F44336;
                    border: none;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background: #da190b;
                }
            """)
        else:
            self.connection_status.setText("🔓 Отключено")
            self.connection_status.setStyleSheet("""
                QLabel {
                    font-size: 24px;
                    font-weight: bold;
                    padding: 20px;
                    border-radius: 10px;
                    background: #FFEBEE;
                    color: #F44336;
                }
            """)
            self.connect_btn.setText("Использовать VPN")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    padding: 15px;
                    font-size: 16px;
                    font-weight: bold;
                    color: white;
                    background: #4CAF50;
                    border: none;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background: #45a049;
                }
            """)
        
        # Обновляем меню системного трея
        app = MDApp.get_running_app() if 'MDApp' in globals() else QApplication.instance()
        if hasattr(app, 'activeWindow') and app.activeWindow():
            main_window = app.activeWindow()
            if hasattr(main_window, 'update_tray_menu'):
                main_window.update_tray_menu(connected)
    
    def toggle_vpn(self):
        """Переключение VPN подключения"""
        status = self.vpn_manager.get_status()
        
        if status.get("connected"):
            self.log("Отключение от VPN...")
            success, message = self.vpn_manager.disconnect()
        else:
            self.log("Подключение к VPN...")
            success, message = self.vpn_manager.connect()
        
        if success:
            self.log(f"✅ {message}")
        else:
            self.log(f"❌ {message}")
            QMessageBox.warning(self, "Ошибка VPN", message)
    
    def log(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

class SecureVPNApp(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_tray()
        self.setup_autostart()
        
    def init_ui(self):
        self.setWindowTitle("SecureVPN Client")
        self.setFixedSize(450, 600)
        
        # Устанавливаем иконку окна
        window_icon = QIcon("assets/logo.png")
        if not window_icon.isNull():
            self.setWindowIcon(window_icon)
        
        self.setStyleSheet("""
            QMainWindow {
                background: white;
            }
        """)
        
        # Стек виджетов
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Виджет авторизации
        self.login_widget = LoginWidget()
        self.login_widget.login_success.connect(self.on_login_success)
        self.stacked_widget.addWidget(self.login_widget)
        
        # Центрирование окна
        self.center_window()
    
    def center_window(self):
        """Центрирование окна на экране"""
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)
    
    def on_login_success(self, token: str, user_info: dict):
        """Обработка успешной авторизации"""
        # Создаем главный виджет
        self.main_widget = MainWidget(token, user_info)
        self.stacked_widget.addWidget(self.main_widget)
        self.stacked_widget.setCurrentWidget(self.main_widget)
    
    def setup_tray(self):
        """Настройка системного трея"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        
        self.tray_icon = QSystemTrayIcon(self)
        
        # Меню трея
        tray_menu = QMenu()
        
        show_action = tray_menu.addAction("Показать окно")
        show_action.triggered.connect(self.show_window)
        
        tray_menu.addSeparator()
        
        # Действия VPN (будут обновляться динамически)
        self.vpn_action = tray_menu.addAction("Подключить VPN")
        self.vpn_action.triggered.connect(self.toggle_vpn_from_tray)
        
        self.status_action = tray_menu.addAction("Статус: Отключено")
        self.status_action.setEnabled(False)  # Только для отображения
        
        tray_menu.addSeparator()
        
        quit_action = tray_menu.addAction("Выход")
        quit_action.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Иконка
        tray_pixmap = QPixmap("assets/logo.png")
        if not tray_pixmap.isNull():
            # Масштабируем для трея
            scaled_tray = tray_pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.tray_icon.setIcon(QIcon(scaled_tray))
        else:
            # Fallback иконка
            self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.show()
    
    def on_tray_activated(self, reason):
        """Обработка клика по иконке в трее"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()
    
    def show_window(self):
        """Показать главное окно"""
        self.show()
        self.raise_()
        self.activateWindow()
        self.setWindowState(Qt.WindowState.WindowNoState)
    
    def toggle_vpn_from_tray(self):
        """Переключение VPN из системного трея"""
        if hasattr(self, 'main_widget') and self.main_widget:
            self.main_widget.toggle_vpn()
        else:
            self.tray_icon.showMessage(
                "SecureVPN",
                "Сначала выполните авторизацию",
                QSystemTrayIcon.MessageIcon.Warning,
                3000
            )
    
    def update_tray_menu(self, connected: bool):
        """Обновление меню системного трея"""
        if hasattr(self, 'vpn_action') and hasattr(self, 'status_action'):
            if connected:
                self.vpn_action.setText("Отключить VPN")
                self.status_action.setText("Статус: 🔒 Подключено")
                # Меняем иконку трея на "подключено"
                if hasattr(self, 'tray_icon'):
                    self.tray_icon.setToolTip("SecureVPN - Подключено")
            else:
                self.vpn_action.setText("Подключить VPN")
                self.status_action.setText("Статус: 🔓 Отключено")
                # Меняем иконку трея на "отключено"
                if hasattr(self, 'tray_icon'):
                    self.tray_icon.setToolTip("SecureVPN - Отключено")
    
    def quit_application(self):
        """Полное закрытие приложения"""
        # Отключаем VPN перед выходом
        if hasattr(self, 'main_widget') and self.main_widget:
            vpn_status = self.main_widget.vpn_manager.get_status()
            if vpn_status.get("connected"):
                self.main_widget.vpn_manager.disconnect()
        
        QApplication.quit()
    
    def setup_autostart(self):
        """Настройка автозапуска с Windows"""
        try:
            startup_folder = winshell.startup()
            shortcut_path = os.path.join(startup_folder, "SecureVPN.lnk")
            
            if not os.path.exists(shortcut_path):
                target = sys.executable if getattr(sys, 'frozen', False) else __file__
                winshell.CreateShortcut(
                    Path=shortcut_path,
                    Target=target,
                    Icon=(target, 0),
                    Description="SecureVPN Client"
                )
        except Exception as e:
            print(f"Ошибка настройки автозапуска: {e}")
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.tray_icon and self.tray_icon.isVisible():
            # Показываем уведомление о сворачивании в трей
            self.tray_icon.showMessage(
                "SecureVPN",
                "Приложение свернуто в системный трей и продолжает работать в фоне",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
            self.hide()
            event.ignore()
        else:
            # Если трей недоступен, закрываем приложение
            event.accept()
    
    def changeEvent(self, event):
        """Обработка изменения состояния окна"""
        if event.type() == event.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                # При минимизации сворачиваем в трей
                if self.tray_icon and self.tray_icon.isVisible():
                    self.hide()
                    event.ignore()
                    return
        super().changeEvent(event)

def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Не закрывать при сворачивании в трей
    
    # Применяем стиль
    app.setStyleSheet("""
        * {
            font-family: 'Segoe UI', Arial, sans-serif;
        }
    """)
    
    window = SecureVPNApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
