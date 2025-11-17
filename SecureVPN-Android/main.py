#!/usr/bin/env python3
"""
SecureVPN Android Client
Мобильное приложение для подключения к VPN
"""

import json
import threading
import time
from pathlib import Path

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar
from plyer import notification
from android.permissions import request_permissions, Permission
from kivy.logger import Logger

# Для фонового режима
try:
    from android import mActivity
    from jnius import autoclass, PythonJavaClass, java_method
    
    # Android классы
    PythonService = autoclass('org.kivy.android.PythonService')
    Context = autoclass('android.content.Context')
    Intent = autoclass('android.content.Intent')
    PendingIntent = autoclass('android.app.PendingIntent')
    AndroidString = autoclass('java.lang.String')
    
    ANDROID_AVAILABLE = True
except ImportError:
    ANDROID_AVAILABLE = False
    Logger.info("Android: Not running on Android, background service disabled")

# Конфигурация сервера
SERVER_CONFIG = {
    "api_url": "http://79.132.136.194:8080",
    "vpn_server": "79.132.136.194", 
    "vpn_port": 51820,
    "server_public_key": "yzY1xSqfLP6AIlf6l8NKIJ4MKuN/Ay4zcXjwVoXQV1w="
}

class NetworkChecker:
    """Проверка сетевого подключения"""
    
    @staticmethod
    def check_connection():
        """Проверка подключения к серверу"""
        try:
            response = requests.get(f"{SERVER_CONFIG['api_url']}/health", timeout=5)
            return {
                "internet": True,
                "server": True,
                "api": response.status_code == 200
            }
        except requests.exceptions.ConnectionError:
            return {
                "internet": False,
                "server": False,
                "api": False
            }
        except Exception:
            return {
                "internet": True,
                "server": False,
                "api": False
            }

class AuthManager:
    """Управление авторизацией"""
    
    @staticmethod
    def login(username, password):
        """Авторизация пользователя"""
        try:
            response = requests.post(
                f"{SERVER_CONFIG['api_url']}/auth/login",
                json={"username": username, "password": password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return {
                        "success": True,
                        "token": data.get("token"),
                        "user_info": data.get("user")
                    }
            
            return {"success": False, "error": "Неверные учетные данные"}
            
        except Exception as e:
            return {"success": False, "error": f"Ошибка подключения: {str(e)}"}

class BackgroundService:
    """Фоновый сервис для Android"""
    
    @staticmethod
    def start_service():
        """Запуск фонового сервиса"""
        if not ANDROID_AVAILABLE:
            Logger.info("BackgroundService: Not available on this platform")
            return False
        
        try:
            service = Intent(mActivity, PythonService)
            service.putExtra("service_name", AndroidString("SecureVPN Background Service"))
            mActivity.startService(service)
            Logger.info("BackgroundService: Started successfully")
            return True
        except Exception as e:
            Logger.error(f"BackgroundService: Failed to start - {e}")
            return False
    
    @staticmethod
    def stop_service():
        """Остановка фонового сервиса"""
        if not ANDROID_AVAILABLE:
            return False
        
        try:
            service = Intent(mActivity, PythonService)
            mActivity.stopService(service)
            Logger.info("BackgroundService: Stopped successfully")
            return True
        except Exception as e:
            Logger.error(f"BackgroundService: Failed to stop - {e}")
            return False

class VPNManager:
    """Управление VPN подключением"""
    
    def __init__(self):
        self.is_connected = False
        self.background_service = BackgroundService()
    
    def connect(self):
        """Подключение к VPN"""
        # В реальном приложении здесь будет интеграция с Android VPN API
        self.is_connected = True
        
        # Запускаем фоновый сервис
        if ANDROID_AVAILABLE:
            self.background_service.start_service()
        
        # Показываем постоянное уведомление
        self._show_persistent_notification("🔒 VPN подключен", "SecureVPN активен")
        
        return True, "Подключено к VPN"
    
    def disconnect(self):
        """Отключение от VPN"""
        self.is_connected = False
        
        # Останавливаем фоновый сервис
        if ANDROID_AVAILABLE:
            self.background_service.stop_service()
        
        # Убираем уведомление
        self._show_notification("🔓 VPN отключен", "SecureVPN деактивирован")
        
        return True, "Отключено от VPN"
    
    def get_status(self):
        """Получение статуса"""
        return {"connected": self.is_connected}
    
    def _show_persistent_notification(self, title, message):
        """Показать постоянное уведомление"""
        try:
            notification.notify(
                title=title,
                message=message,
                timeout=0  # Постоянное уведомление
            )
        except Exception as e:
            Logger.error(f"VPNManager: Failed to show notification - {e}")
    
    def _show_notification(self, title, message):
        """Показать обычное уведомление"""
        try:
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )
        except Exception as e:
            Logger.error(f"VPNManager: Failed to show notification - {e}")

class LoginScreen(MDScreen):
    """Экран авторизации"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "login"
        self.build_ui()
    
    def build_ui(self):
        """Создание интерфейса"""
        layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(20),
            adaptive_height=True,
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        
        # Логотип
        logo_card = MDCard(
            size_hint=(None, None),
            size=(dp(120), dp(120)),
            pos_hint={"center_x": 0.5},
            elevation=3,
            radius=[60],
            md_bg_color="#2196F3"
        )
        
        logo_layout = MDBoxLayout(
            size_hint=(1, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        
        logo = Image(
            source="assets/logo.png",
            size_hint=(0.8, 0.8),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        
        logo_layout.add_widget(logo)
        logo_card.add_widget(logo_layout)
        layout.add_widget(logo_card)
        
        # Заголовок
        title = MDLabel(
            text="SecureVPN",
            theme_text_color="Primary",
            size_hint_y=None,
            height=dp(40),
            font_style="H4",
            halign="center"
        )
        layout.add_widget(title)
        
        # Подзаголовок
        subtitle = MDLabel(
            text="Безопасное VPN подключение",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(30),
            font_style="Body1",
            halign="center"
        )
        layout.add_widget(subtitle)
        
        # Поля ввода
        self.username_field = MDTextField(
            hint_text="Логин",
            text="Medvedushkaa",
            size_hint_x=0.8,
            pos_hint={"center_x": 0.5}
        )
        layout.add_widget(self.username_field)
        
        self.password_field = MDTextField(
            hint_text="Пароль",
            password=True,
            size_hint_x=0.8,
            pos_hint={"center_x": 0.5}
        )
        layout.add_widget(self.password_field)
        
        # Кнопка входа
        self.login_btn = MDRaisedButton(
            text="ВОЙТИ",
            size_hint_x=0.8,
            pos_hint={"center_x": 0.5},
            on_release=self.login
        )
        layout.add_widget(self.login_btn)
        
        # Статус
        self.status_label = MDLabel(
            text="",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(30),
            halign="center"
        )
        layout.add_widget(self.status_label)
        
        self.add_widget(layout)
        
        # Проверка сети при запуске
        self.check_network()
    
    def check_network(self):
        """Проверка сетевого подключения"""
        def check():
            result = NetworkChecker.check_connection()
            Clock.schedule_once(lambda dt: self.on_network_check(result), 0)
        
        self.status_label.text = "Проверка подключения..."
        threading.Thread(target=check).start()
    
    def on_network_check(self, result):
        """Обработка результата проверки сети"""
        if not result.get("internet"):
            self.status_label.text = "❌ Нет подключения к интернету"
            return
        
        if not result.get("server") or not result.get("api"):
            self.status_label.text = "❌ Сервер недоступен"
            return
        
        self.status_label.text = "✅ Готов к работе"
    
    def login(self, instance):
        """Авторизация"""
        username = self.username_field.text.strip()
        password = self.password_field.text.strip()
        
        if not username or not password:
            self.show_notification("Введите логин и пароль", "warning")
            return
        
        def auth():
            result = AuthManager.login(username, password)
            Clock.schedule_once(lambda dt: self.on_auth_result(result), 0)
        
        self.login_btn.disabled = True
        self.status_label.text = "Авторизация..."
        threading.Thread(target=auth).start()
    
    def on_auth_result(self, result):
        """Обработка результата авторизации"""
        self.login_btn.disabled = False
        
        if result.get("success"):
            self.status_label.text = "✅ Авторизация успешна"
            app = MDApp.get_running_app()
            app.token = result["token"]
            app.user_info = result["user_info"]
            app.root.current = "main"
            self.show_notification("Добро пожаловать!", "success")
        else:
            error = result.get("error", "Неизвестная ошибка")
            self.status_label.text = f"❌ {error}"
            self.show_notification(error, "error")
    
    def show_notification(self, message, type_msg):
        """Показать уведомление"""
        notification.notify(
            title="SecureVPN",
            message=message,
            timeout=3
        )

class MainScreen(MDScreen):
    """Главный экран управления VPN"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "main"
        self.vpn_manager = VPNManager()
        self.build_ui()
        self.setup_timer()
    
    def build_ui(self):
        """Создание интерфейса"""
        layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(20),
            padding=dp(20)
        )
        
        # Toolbar
        toolbar = MDTopAppBar(
            title="SecureVPN",
            right_action_items=[["logout", lambda x: self.logout()]]
        )
        layout.add_widget(toolbar)
        
        # Основной контент
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(30),
            adaptive_height=True,
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        
        # Статус подключения
        self.status_card = MDCard(
            size_hint_y=None,
            height=dp(120),
            elevation=3,
            radius=[10],
            md_bg_color="#FFEBEE"
        )
        
        status_layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(20)
        )
        
        self.status_icon = MDLabel(
            text="🔓",
            font_style="H2",
            size_hint_y=None,
            height=dp(50),
            halign="center"
        )
        status_layout.add_widget(self.status_icon)
        
        self.status_text = MDLabel(
            text="Отключено",
            font_style="H6",
            size_hint_y=None,
            height=dp(30),
            halign="center"
        )
        status_layout.add_widget(self.status_text)
        
        self.status_card.add_widget(status_layout)
        content.add_widget(self.status_card)
        
        # Кнопка подключения
        self.connect_btn = MDRaisedButton(
            text="ИСПОЛЬЗОВАТЬ VPN",
            size_hint_y=None,
            height=dp(50),
            md_bg_color="#4CAF50",
            on_release=self.toggle_vpn
        )
        content.add_widget(self.connect_btn)
        
        # Информация о сервере
        server_card = MDCard(
            size_hint_y=None,
            height=dp(150),
            elevation=2,
            radius=[10]
        )
        
        server_layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(5),
            padding=dp(20)
        )
        
        server_layout.add_widget(MDLabel(
            text="Информация о сервере",
            font_style="Subtitle1",
            size_hint_y=None,
            height=dp(30)
        ))
        
        server_layout.add_widget(MDLabel(
            text=f"Сервер: {SERVER_CONFIG['vpn_server']}",
            font_style="Body2",
            size_hint_y=None,
            height=dp(25)
        ))
        
        server_layout.add_widget(MDLabel(
            text=f"Порт: {SERVER_CONFIG['vpn_port']}",
            font_style="Body2",
            size_hint_y=None,
            height=dp(25)
        ))
        
        server_layout.add_widget(MDLabel(
            text="Шифрование: ChaCha20-Poly1305",
            font_style="Body2",
            size_hint_y=None,
            height=dp(25)
        ))
        
        server_card.add_widget(server_layout)
        content.add_widget(server_card)
        
        layout.add_widget(content)
        self.add_widget(layout)
    
    def setup_timer(self):
        """Настройка таймера обновления статуса"""
        Clock.schedule_interval(self.update_status, 2)
    
    def update_status(self, dt):
        """Обновление статуса подключения"""
        status = self.vpn_manager.get_status()
        
        if status.get("connected"):
            self.status_icon.text = "🔒"
            self.status_text.text = "Подключено"
            self.status_card.md_bg_color = "#E8F5E8"
            self.connect_btn.text = "ОТКЛЮЧИТЬ VPN"
            self.connect_btn.md_bg_color = "#F44336"
        else:
            self.status_icon.text = "🔓"
            self.status_text.text = "Отключено"
            self.status_card.md_bg_color = "#FFEBEE"
            self.connect_btn.text = "ИСПОЛЬЗОВАТЬ VPN"
            self.connect_btn.md_bg_color = "#4CAF50"
    
    def toggle_vpn(self, instance):
        """Переключение VPN"""
        status = self.vpn_manager.get_status()
        
        if status.get("connected"):
            success, message = self.vpn_manager.disconnect()
        else:
            success, message = self.vpn_manager.connect()
        
        notification.notify(
            title="SecureVPN",
            message=message,
            timeout=3
        )
    
    def logout(self):
        """Выход из аккаунта"""
        app = MDApp.get_running_app()
        app.token = None
        app.user_info = None
        app.root.current = "login"
        
        notification.notify(
            title="SecureVPN",
            message="Вы вышли из аккаунта",
            timeout=2
        )

class SecureVPNApp(MDApp):
    """Главное приложение"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.token = None
        self.user_info = None
    
    def build(self):
        """Создание приложения"""
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        
        # Запрос разрешений
        request_permissions([
            Permission.INTERNET,
            Permission.ACCESS_NETWORK_STATE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.FOREGROUND_SERVICE,
            Permission.WAKE_LOCK
        ])
        
        # Менеджер экранов
        sm = MDScreenManager()
        
        # Добавляем экраны
        sm.add_widget(LoginScreen())
        sm.add_widget(MainScreen())
        
        return sm
    
    def on_start(self):
        """Запуск приложения"""
        notification.notify(
            title="SecureVPN",
            message="Приложение запущено",
            timeout=2
        )
    
    def on_pause(self):
        """Приложение переходит в фоновый режим"""
        Logger.info("SecureVPN: App paused, continuing in background")
        return True  # Разрешаем работу в фоне
    
    def on_resume(self):
        """Приложение возвращается из фонового режима"""
        Logger.info("SecureVPN: App resumed from background")
        notification.notify(
            title="SecureVPN",
            message="Приложение активно",
            timeout=1
        )
    
    def on_stop(self):
        """Остановка приложения"""
        # Отключаем VPN при закрытии приложения
        Logger.info("SecureVPN: App stopping, cleaning up...")
        
        # Здесь можно добавить логику сохранения состояния
        # и корректного отключения VPN если нужно

if __name__ == "__main__":
    SecureVPNApp().run()
