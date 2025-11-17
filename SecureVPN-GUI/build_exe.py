#!/usr/bin/env python3
"""
Простая сборка EXE для SecureVPN
"""

import os
import subprocess
import sys

def build_exe():
    """Сборка EXE файла"""
    print("🔨 Сборка SecureVPN.exe...")
    
    # Команда PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name=SecureVPN',
        '--add-data=assets;assets',
        'main.py'
    ]
    
    # Если есть иконка, добавляем её
    if os.path.exists('assets/icon.ico'):
        cmd.insert(-1, '--icon=assets/icon.ico')
        print("✅ Используем иконку")
    elif os.path.exists('assets/logo.png'):
        cmd.insert(-1, '--icon=assets/logo.png')
        print("✅ Используем PNG как иконку")
    
    try:
        print("⏳ Запускаем PyInstaller...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Сборка завершена успешно!")
            print("📁 EXE файл: dist/SecureVPN.exe")
            
            # Проверяем размер файла
            exe_path = "dist/SecureVPN.exe"
            if os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"📊 Размер файла: {size_mb:.1f} МБ")
            
            return True
        else:
            print("❌ Ошибка сборки:")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("❌ PyInstaller не найден. Установите: py -m pip install pyinstaller")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("🚀 SecureVPN EXE Builder")
    print("=" * 30)
    
    if not os.path.exists("main.py"):
        print("❌ Файл main.py не найден!")
        sys.exit(1)
    
    if build_exe():
        print("\n🎉 Готово! Запустите dist/SecureVPN.exe")
    else:
        print("\n❌ Сборка не удалась")
        sys.exit(1)
