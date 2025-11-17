#!/usr/bin/env python3
"""
Упрощенная сборка Windows приложения
"""

import os
import sys
import subprocess

def check_dependencies():
    """Проверка зависимостей"""
    required = ['PyQt6', 'requests', 'psutil', 'pyinstaller']
    missing = []
    
    for package in required:
        try:
            __import__(package.lower().replace('-', '_'))
            print(f"✅ {package} установлен")
        except ImportError:
            missing.append(package)
            print(f"❌ {package} не найден")
    
    return missing

def install_dependencies(packages):
    """Установка зависимостей"""
    for package in packages:
        print(f"📦 Устанавливаем {package}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✅ {package} установлен")
        except subprocess.CalledProcessError:
            print(f"❌ Не удалось установить {package}")
            return False
    return True

def build_exe():
    """Сборка EXE файла"""
    print("🔨 Начинаем сборку...")
    
    # Команда PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name=SecureVPN',
        '--icon=assets/logo.png',  # Используем PNG как иконку
        'main.py'
    ]
    
    try:
        subprocess.check_call(cmd)
        print("✅ Сборка завершена успешно!")
        print("📁 EXE файл находится в папке dist/")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка сборки: {e}")
        return False

def main():
    """Главная функция"""
    print("🚀 SecureVPN Windows Builder")
    print("=" * 40)
    
    # Проверяем зависимости
    missing = check_dependencies()
    
    if missing:
        print(f"\n📦 Нужно установить: {', '.join(missing)}")
        if input("Установить автоматически? (y/n): ").lower() == 'y':
            if not install_dependencies(missing):
                print("❌ Не удалось установить зависимости")
                return False
        else:
            print("❌ Установите зависимости вручную")
            return False
    
    # Собираем EXE
    if build_exe():
        print("\n🎉 Готово! Запустите dist/SecureVPN.exe")
        return True
    else:
        print("\n❌ Сборка не удалась")
        return False

if __name__ == "__main__":
    main()
