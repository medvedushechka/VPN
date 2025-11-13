# 📖 SecureVPN User Guide

Краткое руководство по использованию SecureVPN после установки.

## 🚀 Быстрый старт

### На сервере (79.132.136.194)

```bash
# 1. Запуск сервера
sudo systemctl start securevpn-server

# 2. Получение публичного ключа для клиентов
cat /etc/securevpn/server_public.key
```

### На клиенте

```bash
# 1. Создание конфигурации
python -m securevpn.cli create-config --client \
  --server-address 79.132.136.194 \
  --server-public-key "ВАШ_ПУБЛИЧНЫЙ_КЛЮЧ_СЕРВЕРА"

# 2. Генерация ключей клиента
python -m securevpn.cli generate-keys --client

# 3. Подключение
sudo python -m securevpn.cli client --config client.conf
```

## 🔧 Основные команды

### Управление сервером

```bash
# Запуск сервера
sudo securevpn server --config /etc/securevpn/server.conf

# Запуск в фоне (daemon)
sudo securevpn server --config /etc/securevpn/server.conf --daemon

# Через systemd
sudo systemctl start securevpn-server
sudo systemctl stop securevpn-server
sudo systemctl restart securevpn-server
sudo systemctl status securevpn-server
```

### Управление клиентом

```bash
# Подключение к VPN
sudo securevpn client --config client.conf

# С автопереподключением
sudo securevpn client --config client.conf --auto-reconnect

# Проверка статуса подключения
ip addr show svpn0
```

### Генерация ключей

```bash
# Ключи сервера
securevpn generate-keys --server --output-dir /etc/securevpn

# Ключи клиента
securevpn generate-keys --client --output-dir ~/vpn-keys

# Показать публичный ключ
securevpn show-key /path/to/public.key
```

### Создание конфигураций

```bash
# Конфигурация сервера
securevpn create-config --server --output server.conf

# Конфигурация клиента
securevpn create-config --client \
  --server-address IP_СЕРВЕРА \
  --server-public-key ПУБЛИЧНЫЙ_КЛЮЧ \
  --output client.conf
```

### Валидация конфигурации

```bash
# Проверка конфигурации
securevpn validate config.conf
```

## ⚙️ Настройка конфигурации

### Серверная конфигурация (server.conf)

```yaml
mode: server

# Сетевые настройки
server:
  bind_address: 0.0.0.0      # Адрес привязки
  port: 51820                # Порт сервера
  max_clients: 100           # Максимум клиентов

network:
  ipv4_network: 10.8.0.0/24  # Сеть для клиентов
  mtu: 1420                  # MTU
  dns_servers:               # DNS серверы
    - 1.1.1.1
    - 8.8.8.8

# Обфускация трафика
obfuscation:
  enabled: true              # Включить обфускацию
  method: tls                # tls, http, dns
  port_hopping: true         # Смена портов
```

### Клиентская конфигурация (client.conf)

```yaml
mode: client

# Настройки сервера
client:
  server_address: 79.132.136.194  # IP сервера
  server_port: 51820              # Порт сервера
  server_public_key: "..."        # Публичный ключ сервера
  
  # Маршрутизация
  allowed_ips:
    - 0.0.0.0/0              # Весь трафик через VPN
    # - 10.0.0.0/8           # Только приватные сети

# Обфускация (должна совпадать с сервером)
obfuscation:
  enabled: true
  method: tls
```

## 🔒 Методы обфускации

### TLS Obfuscation (Рекомендуется)
```yaml
obfuscation:
  method: tls
```
- Трафик выглядит как HTTPS
- Лучшая совместимость
- Обходит большинство DPI систем

### HTTP Obfuscation
```yaml
obfuscation:
  method: http
```
- Трафик выглядит как веб-запросы
- Хорошо для корпоративных сетей
- Реалистичные HTTP заголовки

### DNS Obfuscation
```yaml
obfuscation:
  method: dns
```
- Трафик выглядит как DNS-запросы
- Обходит DNS-фильтры
- Работает на порту 53

## 📊 Мониторинг

### Проверка статуса сервера

```bash
# Статус systemd сервиса
systemctl status securevpn-server

# Логи в реальном времени
journalctl -u securevpn-server -f

# Проверка порта
ss -tulpn | grep 51820

# Активные подключения
netstat -an | grep 51820
```

### Проверка статуса клиента

```bash
# TUN интерфейс
ip addr show svpn0

# Маршруты
ip route show

# DNS настройки
cat /etc/resolv.conf

# Тест подключения
ping 8.8.8.8
curl ifconfig.me  # Должен показать IP сервера
```

### Статистика трафика

```bash
# Статистика интерфейса
cat /proc/net/dev | grep svpn0

# Мониторинг в реальном времени
watch -n 1 'cat /proc/net/dev | grep svpn0'

# Детальная статистика
iftop -i svpn0
```

## 🛠️ Устранение неполадок

### Сервер не запускается

```bash
# Проверить логи
journalctl -u securevpn-server --no-pager -l

# Проверить конфигурацию
securevpn validate /etc/securevpn/server.conf

# Проверить права на файлы
ls -la /etc/securevpn/

# Проверить порт
netstat -tulpn | grep 51820
```

### Клиент не подключается

```bash
# Проверить доступность сервера
ping 79.132.136.194
telnet 79.132.136.194 51820

# Проверить публичный ключ
securevpn show-key server_public.key

# Проверить конфигурацию клиента
securevpn validate client.conf

# Запустить с отладкой
sudo securevpn client --config client.conf --verbose
```

### Нет интернета через VPN

```bash
# Проверить TUN интерфейс
ip addr show svpn0

# Проверить маршруты
ip route show

# Проверить DNS
nslookup google.com

# Проверить IP forwarding на сервере
cat /proc/sys/net/ipv4/ip_forward

# Проверить iptables на сервере
iptables -t nat -L POSTROUTING
```

## 🔐 Безопасность

### Ротация ключей

```bash
# На сервере - генерация новых ключей
cd /etc/securevpn
securevpn generate-keys --server --name server_new

# Замена ключей
sudo mv server_private.key server_private.key.backup
sudo mv server_public.key server_public.key.backup
sudo mv server_new_server_private.key server_private.key
sudo mv server_new_server_public.key server_public.key

# Перезапуск сервера
sudo systemctl restart securevpn-server

# Обновление клиентов новым публичным ключом
cat /etc/securevpn/server_public.key
```

### Мониторинг безопасности

```bash
# Проверка подключенных клиентов
journalctl -u securevpn-server | grep "authenticated"

# Мониторинг попыток подключения
journalctl -u securevpn-server | grep "handshake"

# Проверка файрвола
ufw status verbose
```

## 📱 Подключение различных устройств

### Linux Desktop
```bash
# Установка и подключение
git clone <repo>
cd SecureVPN
pip install -r requirements.txt
sudo python -m securevpn.cli client --config client.conf
```

### Android (через Termux)
```bash
# В Termux
pkg install python
pip install -r requirements.txt
# Требует root для TUN интерфейса
```

### Windows (через WSL)
```bash
# В WSL
sudo apt update
sudo apt install python3-pip
pip install -r requirements.txt
# Настройка TUN интерфейса в Windows
```

## 💡 Полезные советы

1. **Автозапуск клиента:**
   ```bash
   # Создать systemd сервис для клиента
   sudo cp systemd/securevpn-client.service /etc/systemd/system/
   sudo systemctl enable securevpn-client
   ```

2. **Backup конфигурации:**
   ```bash
   # Создать backup
   tar -czf securevpn-backup.tar.gz /etc/securevpn/
   ```

3. **Мониторинг производительности:**
   ```bash
   # Проверка нагрузки
   htop
   iotop
   nethogs
   ```

4. **Оптимизация производительности:**
   ```yaml
   # В конфигурации
   network:
     mtu: 1420              # Оптимальный MTU
   crypto:
     cipher: chacha20poly1305  # Быстрый шифр
   ```

---

**🎯 Готово! Теперь вы знаете как пользоваться SecureVPN.**

Для получения дополнительной помощи обратитесь к файлу `INSTALLATION.md` или проверьте логи системы.
