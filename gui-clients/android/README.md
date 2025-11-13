# 📱 SecureVPN Android Client

Мобильное приложение для Android с красивым Material Design интерфейсом.

## ✨ Возможности

- 🔐 **Авторизация** через API сервер
- 📱 **Material Design** - современный Android интерфейс
- 🌐 **Проверка подключения** к интернету и серверу
- 🔘 **Кнопка "Использовать VPN"** - подключение одним касанием
- 📲 **Push уведомления** о статусе подключения
- 🎨 **Ваш логотип** в интерфейсе
- ⚡ **Быстрая работа** - оптимизировано для мобильных устройств

## 🚀 Установка и сборка

### Требования:
- Python 3.8+
- Buildozer (для сборки APK)
- Android SDK
- Android NDK

### Установка Buildozer:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y git zip unzip openjdk-8-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev

# Установка Buildozer
pip3 install --user --upgrade buildozer
pip3 install --user --upgrade cython
```

### Сборка APK:
```bash
# Инициализация (первый раз)
buildozer init

# Сборка debug версии
buildozer android debug

# Сборка release версии
buildozer android release
```

## 📋 Структура проекта

```
SecureVPN-Android/
├── main.py              # Главный файл приложения
├── buildozer.spec       # Конфигурация сборки
├── assets/
│   ├── logo.png         # Логотип в интерфейсе
│   └── icon.png         # Иконка приложения
└── README.md           # Документация
```

## 🎨 Интерфейс

### Экран авторизации:
- Логотип приложения
- Поля ввода логина/пароля
- Проверка подключения к серверу
- Красивые уведомления об ошибках

### Главный экран:
- Статус подключения с иконками
- Кнопка "Использовать VPN"
- Информация о сервере
- Toolbar с кнопкой выхода

## 🔧 Технические детали

### Используемые библиотеки:
- **Kivy** - кроссплатформенный GUI фреймворк
- **KivyMD** - Material Design компоненты
- **Requests** - HTTP запросы к API
- **Plyer** - доступ к функциям Android
- **Pyjnius** - интеграция с Java/Android API

### Архитектура:
```
Android App → API Server (авторизация) → VPN Server (подключение)
```

### Разрешения Android:
- `INTERNET` - доступ к интернету
- `ACCESS_NETWORK_STATE` - проверка сетевого состояния
- `WRITE_EXTERNAL_STORAGE` - сохранение конфигурации

## 📱 Использование

### Первый запуск:
1. Установите APK файл на Android устройство
2. Разрешите установку из неизвестных источников
3. Запустите приложение
4. Введите логин: `Medvedushkaa`, пароль: `1q2w3e4r5t6y`

### Подключение к VPN:
1. После авторизации нажмите "ИСПОЛЬЗОВАТЬ VPN"
2. Статус изменится на "🔒 Подключено"
3. Для отключения нажмите "ОТКЛЮЧИТЬ VPN"

## 🔍 Отладка

### Логи сборки:
```bash
# Просмотр логов
buildozer android debug -v

# Очистка кеша
buildozer android clean
```

### Тестирование на устройстве:
```bash
# Установка на подключенное устройство
adb install bin/securevpn-1.0-arm64-v8a-debug.apk

# Просмотр логов приложения
adb logcat | grep python
```

## 📦 Готовые файлы

После сборки в папке `bin/` появятся:
- `securevpn-1.0-arm64-v8a-debug.apk` - debug версия
- `securevpn-1.0-arm64-v8a-release-unsigned.apk` - release версия

## 🔐 Подпись APK (для публикации)

```bash
# Генерация ключа
keytool -genkey -v -keystore securevpn.keystore -alias securevpn -keyalg RSA -keysize 2048 -validity 10000

# Подпись APK
jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 -keystore securevpn.keystore securevpn-release-unsigned.apk securevpn

# Оптимизация
zipalign -v 4 securevpn-release-unsigned.apk securevpn-release.apk
```

## 🌟 Особенности Android версии

- **Адаптивный дизайн** под разные размеры экранов
- **Material Design** компоненты
- **Системные уведомления** о статусе VPN
- **Автоматическая проверка** разрешений
- **Оптимизация батареи** - минимальное потребление
- **Поддержка темной темы** (автоматически)

---

**SecureVPN Android** - безопасность в вашем кармане! 📱🔒
