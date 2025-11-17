#!/usr/bin/env python3
"""
Простой тест UDP соединения с сервером
"""

import socket
import time

SERVER_IP = "79.132.136.194"
SERVER_PORT = 51823

print(f"🔍 Тестирование UDP соединения с {SERVER_IP}:{SERVER_PORT}")

try:
    # Создаём UDP сокет
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    
    # Отправляем тестовый пакет
    test_data = b"TEST_PACKET_12345"
    print(f"📤 Отправляю тестовый пакет: {test_data}")
    
    sock.sendto(test_data, (SERVER_IP, SERVER_PORT))
    print(f"✅ Пакет отправлен")
    
    # Ждём ответ
    print(f"⏳ Ожидаю ответ (timeout 5 сек)...")
    response, addr = sock.recvfrom(1024)
    print(f"✅ Получен ответ от {addr}: {response}")
    
except socket.timeout:
    print(f"❌ Timeout: сервер не ответил за 5 секунд")
except ConnectionRefusedError:
    print(f"❌ Соединение отказано")
except Exception as e:
    print(f"❌ Ошибка: {e}")
finally:
    sock.close()
    print("🔌 Сокет закрыт")
