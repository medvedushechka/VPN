# 🚀 SecureVPN Server Deployment Guide

Пошаговое руководство по развертыванию SecureVPN на вашем сервере через Git.

## 📋 Предварительные требования

- **Сервер:** Ubuntu 24.04.3 LTS (или совместимая ОС)
- **IP:** 79.132.136.194 (ваш сервер в Германии)
- **Доступ:** SSH root доступ
- **Git:** Установлен на сервере

## 🔧 Быстрое развертывание

### 1. Подключение к серверу

```bash
ssh root@79.132.136.194
```

### 2. Клонирование репозитория

```bash
# Клонируем репозиторий
git clone https://github.com/YOUR_USERNAME/SecureVPN.git /opt/securevpn-source
cd /opt/securevpn-source

# Делаем скрипт исполняемым
chmod +x deploy.sh

# Запускаем автоматическое развертывание
./deploy.sh
```

### 3. Получение публичного ключа сервера

После успешной установки скрипт покажет публичный ключ сервера:

```bash
# Или получить ключ вручную:
cat /etc/securevpn/server_public.key
```

**Сохраните этот ключ! Он понадобится для GUI приложения.**

## 🔑 Система авторизации

### Встроенный пользователь

После установки автоматически создается пользователь:
- **Логин:** `Medvedushkaa`
- **Пароль:** `1q2w3e4r5t6y`

### API для GUI приложения

Сервер запускает HTTP API на `http://127.0.0.1:8080` для взаимодействия с GUI приложением:

**Endpoints:**
- `POST /auth/login` - Авторизация пользователя
- `GET /auth/validate` - Проверка токена
- `GET /vpn/config` - Получение конфигурации VPN
- `GET /vpn/server-key` - Получение публичного ключа сервера

### Пример авторизации

```bash
# Тест авторизации
curl -X POST http://127.0.0.1:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "Medvedushkaa", "password": "1q2w3e4r5t6y"}'
```

## 📊 Проверка работы

### Статус сервиса

```bash
# Проверка статуса VPN сервера
systemctl status securevpn-server

# Проверка логов
journalctl -u securevpn-server -f

# Проверка портов
ss -tulpn | grep -E "(51820|8080)"
```

### Тестирование API

```bash
# Проверка API авторизации
curl http://127.0.0.1:8080/health

# Получение публичного ключа
curl http://127.0.0.1:8080/vpn/server-key
```

## 🔧 Управление сервером

### Основные команды

```bash
# Запуск
systemctl start securevpn-server

# Остановка
systemctl stop securevpn-server

# Перезапуск
systemctl restart securevpn-server

# Автозапуск
systemctl enable securevpn-server

# Отключение автозапуска
systemctl disable securevpn-server
```

### Обновление из Git

```bash
cd /opt/securevpn-source
git pull origin main
./deploy.sh update
```

### Просмотр логов

```bash
# Логи VPN сервера
journalctl -u securevpn-server -f

# Логи файлом
tail -f /var/log/securevpn/server.log

# Логи за последний час
journalctl -u securevpn-server --since "1 hour ago"
```

## 🔒 Безопасность

### Firewall настройки

Скрипт автоматически настраивает firewall:

```bash
# Проверка UFW
ufw status

# Ручная настройка (если нужно)
ufw allow 51820/udp  # VPN порт
ufw allow 22/tcp     # SSH
ufw enable
```

### Мониторинг подключений

```bash
# Активные VPN подключения
journalctl -u securevpn-server | grep "authenticated"

# Статистика подключений
journalctl -u securevpn-server | grep "Active peers"

# Мониторинг трафика
watch -n 1 'cat /proc/net/dev | grep svpn0'
```

## 🐛 Устранение неполадок

### Сервис не запускается

```bash
# Проверить статус
systemctl status securevpn-server

# Проверить конфигурацию
/opt/securevpn/venv/bin/python -m securevpn.cli validate /etc/securevpn/server.conf

# Проверить логи
journalctl -u securevpn-server --no-pager -l
```

### API не отвечает

```bash
# Проверить порт 8080
ss -tulpn | grep 8080

# Проверить процессы
ps aux | grep securevpn

# Перезапустить сервис
systemctl restart securevpn-server
```

### Проблемы с сетью

```bash
# Проверить IP forwarding
cat /proc/sys/net/ipv4/ip_forward

# Проверить TUN интерфейс
ip addr show svpn0

# Проверить iptables
iptables -t nat -L POSTROUTING
```

## 📁 Структура файлов на сервере

```
/opt/securevpn/          # Установка приложения
├── src/                 # Исходный код
├── venv/                # Python окружение
├── configs/             # Шаблоны конфигураций
└── systemd/             # Systemd сервисы

/etc/securevpn/          # Конфигурация
├── server.conf          # Основная конфигурация
├── server_private.key   # Приватный ключ сервера
├── server_public.key    # Публичный ключ сервера
└── users.db            # База данных пользователей

/var/log/securevpn/      # Логи
└── server.log          # Лог файл сервера
```

## 🔄 Обновление системы

### Обновление SecureVPN

```bash
cd /opt/securevpn-source
git pull origin main
./deploy.sh update
```

### Обновление системы

```bash
apt update && apt upgrade -y
systemctl restart securevpn-server
```

## 📞 Поддержка

### Полезные команды диагностики

```bash
# Полная диагностика
echo "=== SecureVPN Status ==="
systemctl status securevpn-server
echo "=== Network Interfaces ==="
ip addr show
echo "=== Listening Ports ==="
ss -tulpn | grep -E "(51820|8080)"
echo "=== Recent Logs ==="
journalctl -u securevpn-server --since "10 minutes ago"
```

### Сбор информации для отладки

```bash
# Создать отчет о системе
{
  echo "=== System Info ==="
  uname -a
  echo "=== SecureVPN Status ==="
  systemctl status securevpn-server
  echo "=== Configuration ==="
  cat /etc/securevpn/server.conf
  echo "=== Recent Logs ==="
  journalctl -u securevpn-server --since "1 hour ago"
} > securevpn-debug.txt
```

---

## ✅ Готово!

После выполнения этих шагов ваш SecureVPN сервер будет:

1. ✅ Запущен и работает на порту 51820
2. ✅ API авторизации доступен на порту 8080
3. ✅ Пользователь `Medvedushkaa` создан и готов к использованию
4. ✅ Публичный ключ сервера готов для настройки клиентов
5. ✅ Система логирования и мониторинга настроена

**Следующий шаг:** Создание GUI приложения для подключения к VPN!
