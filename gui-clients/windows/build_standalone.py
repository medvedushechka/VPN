#!/usr/bin/env python3
"""
Сборка автономного SecureVPN приложения
Создает EXE файл со встроенным VPN клиентом
"""

import os
import subprocess
import sys
import shutil

def build_standalone():
    """Сборка автономного приложения"""
    print("🚀 Сборка автономного SecureVPN")
    print("=" * 40)
    
    # Очистка предыдущих сборок
    if os.path.exists("dist"):
        shutil.rmtree("dist")
        print("🧹 Очищена папка dist")
    
    if os.path.exists("build"):
        shutil.rmtree("build")
        print("🧹 Очищена папка build")
    
    # Команда PyInstaller для автономного приложения
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',                    # Один файл
        '--windowed',                   # Без консоли
        '--name=SecureVPN-RealVPN',     # Имя файла
        '--add-data=assets;assets',     # Включить ресурсы
        '--hidden-import=requests',     # Явно включить requests
        '--hidden-import=PyQt6',        # Явно включить PyQt6
        '--hidden-import=psutil',       # Явно включить psutil
        '--hidden-import=ping3',        # Явно включить ping3
        '--hidden-import=winshell',     # Явно включить winshell
        '--clean',                      # Очистить кеш
        'main.py'
    ]
    
    # Добавляем иконку если есть
    if os.path.exists('assets/icon.ico'):
        cmd.insert(-1, '--icon=assets/icon.ico')
        print("✅ Добавлена иконка приложения")
    elif os.path.exists('assets/logo.png'):
        cmd.insert(-1, '--icon=assets/logo.png')
        print("✅ Добавлена PNG иконка")
    
    try:
        print("⏳ Запуск PyInstaller...")
        print(f"📝 Команда: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("\n🎉 Сборка завершена успешно!")
            
            exe_path = "dist/SecureVPN-RealVPN.exe"
            if os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"📁 EXE файл: {exe_path}")
                print(f"📊 Размер: {size_mb:.1f} МБ")
                
                print("\n✨ ГОТОВО К РАСПРОСТРАНЕНИЮ!")
                print("🎯 Особенности:")
                print("   • Не требует установки WireGuard")
                print("   • Встроенный VPN клиент")
                print("   • Работает сразу после скачивания")
                print("   • Подключается к вашему серверу")
                
                return True
            else:
                print("❌ EXE файл не найден после сборки")
                return False
        else:
            print("❌ Ошибка сборки:")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("❌ PyInstaller не найден!")
        print("💡 Установите: py -m pip install pyinstaller")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def create_readme():
    """Создание README для пользователей"""
    readme_content = """# SecureVPN - РЕАЛЬНЫЙ VPN БЕЗ УСТАНОВОК!

## 🚀 Быстрый старт

1. **Скачайте** `SecureVPN-RealVPN.exe`
2. **Запустите КАК АДМИНИСТРАТОР** (ПКМ → "Запуск от имени администратора")
3. **Введите данные:**
   - Логин: `Medvedushkaa`
   - Пароль: `1q2w3e4r5t6y`
4. **Нажмите** "Использовать VPN"
5. **Проверьте IP** на https://2ip.ru/

## ✨ Особенности

- ✅ **РЕАЛЬНЫЙ VPN** - изменяет ваш IP адрес
- ✅ **Не требует WireGuard** - собственная реализация
- ✅ **Туннелирование трафика** через сервер
- ✅ **Изменение DNS** на безопасные серверы
- ✅ **Автоматическое восстановление** настроек при отключении

## ⚠️ ВАЖНО

- **Требуются права администратора** для изменения сетевых настроек
- **Антивирус может блокировать** - добавьте в исключения
- **Firewall должен разрешать** исходящие соединения

## 🔧 Технические детали

- **Сервер:** 79.132.136.194:51820
- **Шифрование:** ChaCha20-Poly1305
- **Протокол:** UDP
- **Совместимость:** Windows 10/11

## 📞 Поддержка

При возникновении проблем проверьте:
1. Подключение к интернету
2. Антивирус не блокирует приложение
3. Файрвол разрешает исходящие соединения

---
**SecureVPN** - Безопасный VPN за одну минуту!
"""
    
    with open("dist/README.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("📄 Создан README.txt для пользователей")

if __name__ == "__main__":
    print("🔨 SecureVPN Standalone Builder")
    print("Создание автономного VPN приложения")
    print()
    
    if not os.path.exists("main.py"):
        print("❌ Файл main.py не найден!")
        sys.exit(1)
    
    success = build_standalone()
    
    if success:
        create_readme()
        print("\n🎉 ВСЕ ГОТОВО!")
        print("📦 Файлы для распространения:")
        print("   • dist/SecureVPN-RealVPN.exe")
        print("   • dist/README.txt")
        print("\n💡 Теперь любой может скачать EXE и получить РЕАЛЬНЫЙ VPN!")
        print("⚠️  ВАЖНО: Запускать нужно от имени администратора!")
    else:
        print("\n❌ Сборка не удалась")
        sys.exit(1)
