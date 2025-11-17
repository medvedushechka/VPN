#!/usr/bin/env python3
"""
Тестовая версия Android приложения для запуска на ПК
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import threading
import time

# Конфигурация сервера
SERVER_CONFIG = {
    "api_url": "http://79.132.136.194:8080",
    "vpn_server": "79.132.136.194", 
    "vpn_port": 51820,
    "server_public_key": "yzY1xSqfLP6AIlf6l8NKIJ4MKuN/Ay4zcXjwVoXQV1w="
}

class SecureVPNApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SecureVPN Android (Test)")
        self.root.geometry("400x600")
        self.root.configure(bg='#f0f0f0')
        
        self.token = None
        self.is_connected = False
        
        self.create_widgets()
        self.check_server()
    
    def create_widgets(self):
        # Заголовок
        title = tk.Label(self.root, text="SecureVPN", font=("Arial", 24, "bold"), 
                        bg='#f0f0f0', fg='#2196F3')
        title.pack(pady=20)
        
        subtitle = tk.Label(self.root, text="Android Test Version", font=("Arial", 12), 
                           bg='#f0f0f0', fg='#666')
        subtitle.pack(pady=(0, 30))
        
        # Рамка для авторизации
        auth_frame = tk.Frame(self.root, bg='white', relief='raised', bd=2)
        auth_frame.pack(pady=10, padx=20, fill='x')
        
        tk.Label(auth_frame, text="Авторизация", font=("Arial", 14, "bold"), 
                bg='white').pack(pady=10)
        
        # Поля ввода
        tk.Label(auth_frame, text="Логин:", bg='white').pack()
        self.username_entry = tk.Entry(auth_frame, font=("Arial", 12))
        self.username_entry.insert(0, "Medvedushkaa")
        self.username_entry.pack(pady=5, padx=20, fill='x')
        
        tk.Label(auth_frame, text="Пароль:", bg='white').pack()
        self.password_entry = tk.Entry(auth_frame, show="*", font=("Arial", 12))
        self.password_entry.pack(pady=5, padx=20, fill='x')
        
        # Кнопка входа
        self.login_btn = tk.Button(auth_frame, text="ВОЙТИ", font=("Arial", 12, "bold"),
                                  bg='#2196F3', fg='white', command=self.login)
        self.login_btn.pack(pady=15)
        
        # Статус подключения
        self.status_frame = tk.Frame(self.root, bg='#ffebee', relief='raised', bd=2)
        self.status_frame.pack(pady=20, padx=20, fill='x')
        
        self.status_icon = tk.Label(self.status_frame, text="🔓", font=("Arial", 32), 
                                   bg='#ffebee')
        self.status_icon.pack(pady=10)
        
        self.status_text = tk.Label(self.status_frame, text="Отключено", 
                                   font=("Arial", 16, "bold"), bg='#ffebee', fg='#f44336')
        self.status_text.pack()
        
        # Кнопка VPN
        self.vpn_btn = tk.Button(self.root, text="ИСПОЛЬЗОВАТЬ VPN", 
                                font=("Arial", 14, "bold"), bg='#4CAF50', fg='white',
                                command=self.toggle_vpn, state='disabled')
        self.vpn_btn.pack(pady=20, padx=20, fill='x')
        
        # Информация о сервере
        info_frame = tk.Frame(self.root, bg='white', relief='raised', bd=2)
        info_frame.pack(pady=10, padx=20, fill='x')
        
        tk.Label(info_frame, text="Информация о сервере", font=("Arial", 12, "bold"), 
                bg='white').pack(pady=5)
        
        tk.Label(info_frame, text=f"Сервер: {SERVER_CONFIG['vpn_server']}", 
                bg='white').pack()
        tk.Label(info_frame, text=f"Порт: {SERVER_CONFIG['vpn_port']}", 
                bg='white').pack()
        tk.Label(info_frame, text="Шифрование: ChaCha20-Poly1305", 
                bg='white').pack(pady=(0, 10))
        
        # Статус сервера
        self.server_status = tk.Label(self.root, text="Проверка сервера...", 
                                     font=("Arial", 10), bg='#f0f0f0', fg='#666')
        self.server_status.pack(pady=10)
    
    def check_server(self):
        """Проверка доступности сервера"""
        def check():
            try:
                response = requests.get(f"{SERVER_CONFIG['api_url']}/health", timeout=5)
                if response.status_code == 200:
                    self.root.after(0, lambda: self.server_status.config(
                        text="✅ Сервер доступен", fg='#4CAF50'))
                else:
                    self.root.after(0, lambda: self.server_status.config(
                        text="❌ Сервер недоступен", fg='#f44336'))
            except:
                self.root.after(0, lambda: self.server_status.config(
                    text="❌ Нет подключения к серверу", fg='#f44336'))
        
        threading.Thread(target=check, daemon=True).start()
    
    def login(self):
        """Авторизация"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            messagebox.showwarning("Ошибка", "Введите логин и пароль")
            return
        
        def auth():
            try:
                response = requests.post(
                    f"{SERVER_CONFIG['api_url']}/auth/login",
                    json={"username": username, "password": password},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self.token = data.get("token")
                        self.root.after(0, self.on_login_success)
                    else:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Ошибка", "Неверные учетные данные"))
                else:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Ошибка", "Ошибка авторизации"))
                        
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Ошибка", f"Ошибка подключения: {str(e)}"))
        
        self.login_btn.config(state='disabled', text='Авторизация...')
        threading.Thread(target=auth, daemon=True).start()
    
    def on_login_success(self):
        """Успешная авторизация"""
        messagebox.showinfo("Успех", "Авторизация успешна!")
        self.login_btn.config(state='normal', text='ВОЙТИ')
        self.vpn_btn.config(state='normal')
    
    def toggle_vpn(self):
        """Переключение VPN"""
        if self.is_connected:
            self.disconnect_vpn()
        else:
            self.connect_vpn()
    
    def connect_vpn(self):
        """Подключение к VPN"""
        self.is_connected = True
        self.status_icon.config(text="🔒")
        self.status_text.config(text="Подключено", fg='#4CAF50')
        self.status_frame.config(bg='#e8f5e8')
        self.status_icon.config(bg='#e8f5e8')
        self.status_text.config(bg='#e8f5e8')
        self.vpn_btn.config(text="ОТКЛЮЧИТЬ VPN", bg='#f44336')
        messagebox.showinfo("VPN", "🔒 VPN подключен!\n(Тестовый режим)")
    
    def disconnect_vpn(self):
        """Отключение от VPN"""
        self.is_connected = False
        self.status_icon.config(text="🔓")
        self.status_text.config(text="Отключено", fg='#f44336')
        self.status_frame.config(bg='#ffebee')
        self.status_icon.config(bg='#ffebee')
        self.status_text.config(bg='#ffebee')
        self.vpn_btn.config(text="ИСПОЛЬЗОВАТЬ VPN", bg='#4CAF50')
        messagebox.showinfo("VPN", "🔓 VPN отключен")

if __name__ == "__main__":
    root = tk.Tk()
    app = SecureVPNApp(root)
    root.mainloop()
