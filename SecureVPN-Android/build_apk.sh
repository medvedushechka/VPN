#!/bin/bash
# Скрипт сборки APK для SecureVPN Android

echo "🚀 SecureVPN Android Builder"
echo "============================"

# Проверяем buildozer
if ! command -v buildozer &> /dev/null; then
    echo "❌ Buildozer не установлен"
    echo "📦 Устанавливаем buildozer..."
    
    # Обновляем систему
    sudo apt update
    
    # Устанавливаем зависимости
    sudo apt install -y git zip unzip openjdk-8-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
    
    # Устанавливаем buildozer
    pip3 install --user --upgrade buildozer
    pip3 install --user --upgrade cython
    
    # Добавляем в PATH
    echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
    source ~/.bashrc
fi

echo "✅ Buildozer готов"

# Проверяем файлы
if [ ! -f "main.py" ]; then
    echo "❌ Файл main.py не найден!"
    exit 1
fi

if [ ! -f "buildozer.spec" ]; then
    echo "❌ Файл buildozer.spec не найден!"
    exit 1
fi

echo "📱 Начинаем сборку APK..."

# Очищаем предыдущие сборки
if [ -d ".buildozer" ]; then
    echo "🧹 Очищаем кеш..."
    buildozer android clean
fi

# Собираем debug версию
echo "🔨 Сборка debug APK..."
buildozer android debug

# Проверяем результат
if [ -f "bin/securevpn-1.0-arm64-v8a-debug.apk" ]; then
    echo "✅ APK собран успешно!"
    echo "📁 Файл: bin/securevpn-1.0-arm64-v8a-debug.apk"
    
    # Показываем размер
    size=$(du -h "bin/securevpn-1.0-arm64-v8a-debug.apk" | cut -f1)
    echo "📊 Размер: $size"
    
    echo ""
    echo "🎉 Готово! Установите APK на Android устройство"
    echo "💡 Для установки: adb install bin/securevpn-1.0-arm64-v8a-debug.apk"
else
    echo "❌ Сборка не удалась"
    echo "📋 Проверьте логи выше"
    exit 1
fi
