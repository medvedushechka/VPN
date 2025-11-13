#!/usr/bin/env python3
"""
Скрипт для сборки SecureVPN GUI в исполняемый файл
"""

import PyInstaller.__main__
import os
import sys
from pathlib import Path

def build_exe():
    """Сборка приложения в EXE файл"""
    
    # Параметры сборки
    args = [
        'main.py',
        '--onefile',                    # Один файл
        '--windowed',                   # Без консоли
        '--name=SecureVPN',             # Имя файла
        '--icon=icon.ico',              # Иконка (если есть)
        '--add-data=requirements.txt;.', # Дополнительные файлы
        '--hidden-import=PyQt6',
        '--hidden-import=requests',
        '--hidden-import=psutil',
        '--hidden-import=ping3',
        '--hidden-import=winshell',
        '--hidden-import=win32api',
        '--hidden-import=win32con',
        '--clean',                      # Очистка перед сборкой
        '--noconfirm',                  # Без подтверждения
    ]
    
    print("🚀 Начинаем сборку SecureVPN...")
    print("📦 Параметры:", ' '.join(args))
    
    try:
        PyInstaller.__main__.run(args)
        print("✅ Сборка завершена успешно!")
        print("📁 Исполняемый файл: dist/SecureVPN.exe")
        
        # Информация о файле
        exe_path = Path("dist/SecureVPN.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📊 Размер файла: {size_mb:.1f} МБ")
        
    except Exception as e:
        print(f"❌ Ошибка сборки: {e}")
        return False
    
    return True

if __name__ == "__main__":
    build_exe()
