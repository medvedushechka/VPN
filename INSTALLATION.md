# 🚀 SecureVPN Installation Guide

Пошаговое руководство по установке и настройке SecureVPN на вашем сервере в Германии.

## 📋 Системные требования

### Сервер (Ubuntu 24.04.3 LTS)
- **ОС:** Ubuntu 24.04.3 LTS или новее
- **Архитектура:** x86_64
- **RAM:** Минимум 1 ГБ (рекомендуется 2 ГБ)
- **Диск:** Минимум 10 ГБ свободного места
- **Сеть:** Публичный IP-адрес
- **Права:** Root доступ

### Клиенты
- **Linux:** Ubuntu 20.04+, Debian 11+, CentOS 8+
- **Windows:** Windows 10/11 (с WSL для разработки)
- **macOS:** macOS 11+ (экспериментальная поддержка)

## 🛠️ Автоматическая установка (Рекомендуется)

### На сервере (79.132.136.194):

```bash
# 1. Подключитесь к серверу
ssh root@79.132.136.194

# 2. Скачайте и запустите установочный скрипт
curl -fsSL https://raw.githubusercontent.com/your-repo/SecureVPN/main/install.sh | bash

# Или если файлы уже загружены:
chmod +x install.sh
sudo ./install.sh
```

Скрипт автоматически:
- Установит все зависимости
- Создаст необходимые директории
- Сгенерирует ключи сервера
- Настроит firewall
- Запустит VPN сервер как systemd сервис

## ⚙️ Ручная установка

### 1. Установка зависимостей

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Python и зависимости
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential libffi-dev libssl-dev iproute2 iptables git

# Устанавливаем дополнительные пакеты
sudo apt install -y curl wget htop nano
```

### 2. Создание пользователя и директорий

```bash
# Создаем пользователя для VPN (опционально)
sudo useradd -r -s /bin/false securevpn

# Создаем директории
sudo mkdir -p /opt/securevpn
sudo mkdir -p /etc/securevpn
sudo mkdir -p /var/log/securevpn

# Устанавливаем права
sudo chown -R root:root /opt/securevpn
sudo chmod 755 /opt/securevpn /etc/securevpn
sudo chmod 755 /var/log/securevpn
```

### 3. Установка SecureVPN

```bash
# Переходим в директорию установки
cd /opt/securevpn

# Копируем исходный код (если у вас есть архив)
# Или клонируем репозиторий:
# git clone https://github.com/your-repo/SecureVPN.git .

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 4. Генерация ключей сервера

```bash
# Переходим в директорию конфигурации
cd /etc/securevpn

# Генерируем ключи сервера
/opt/securevpn/venv/bin/python -m securevpn.cli generate-keys --server --output-dir /etc/securevpn --name server

# Копируем конфигурацию
cp /opt/securevpn/configs/server.conf /etc/securevpn/

# Устанавливаем права на ключи
chmod 600 server_private.key
chmod 644 server_public.key server.conf
```

### 5. Настройка сети

```bash
# Включаем IP forwarding
echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
sysctl -p

# Настраиваем firewall (UFW)
ufw allow 51820/udp
ufw allow ssh
ufw --force enable

# Или для iptables:
iptables -A INPUT -p udp --dport 51820 -j ACCEPT
iptables -A FORWARD -i svpn0 -j ACCEPT
iptables -A FORWARD -o svpn0 -j ACCEPT
iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE
```

### 6. Установка systemd сервиса

```bash
# Копируем файл сервиса
cp /opt/securevpn/systemd/securevpn-server.service /etc/systemd/system/

# Перезагружаем systemd
systemctl daemon-reload

# Включаем автозапуск
systemctl enable securevpn-server

# Запускаем сервис
systemctl start securevpn-server

# Проверяем статус
systemctl status securevpn-server
```

## 🐳 Docker установка (Альтернатива)

### Использование Docker Compose

```bash
# Клонируем репозиторий
git clone https://github.com/your-repo/SecureVPN.git
cd SecureVPN

# Запускаем с Docker Compose
docker-compose -f docker/docker-compose.yml up -d

# Проверяем логи
docker-compose -f docker/docker-compose.yml logs -f securevpn-server
```

### Ручная сборка Docker образа

```bash
# Собираем образ
docker build -f docker/Dockerfile -t securevpn:latest .

# Запускаем контейнер
docker run -d \
  --name securevpn-server \
  --privileged \
  --cap-add NET_ADMIN \
  -p 51820:51820/udp \
  -v /etc/securevpn:/etc/securevpn \
  -v /var/log/securevpn:/var/log/securevpn \
  securevpn:latest
```

## 🔧 Настройка сервера

### Редактирование конфигурации

```bash
# Редактируем основную конфигурацию
nano /etc/securevpn/server.conf
```

Основные параметры для изменения:
- `server.bind_address` - адрес привязки (оставьте 0.0.0.0)
- `server.port` - порт сервера (по умолчанию 51820)
- `network.ipv4_network` - сеть для клиентов (по умолчанию 10.8.0.0/24)
- `obfuscation.method` - метод обфускации (tls, http, dns)

### Получение публичного ключа сервера

```bash
# Показать публичный ключ сервера
cat /etc/securevpn/server_public.key

# Или через CLI
/opt/securevpn/venv/bin/python -m securevpn.cli show-key /etc/securevpn/server_public.key
```

**Сохраните этот ключ! Он понадобится для настройки клиентов.**

## 👥 Настройка клиентов

### 1. Установка клиента (Linux)

```bash
# На клиентской машине
# Установите те же зависимости, что и на сервере
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential

# Создайте директорию для клиента
mkdir -p ~/securevpn-client
cd ~/securevpn-client

# Скопируйте исходный код SecureVPN
# Установите зависимости (как на сервере)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Создание конфигурации клиента

```bash
# Создайте конфигурацию клиента
python -m securevpn.cli create-config --client \
  --server-address 79.132.136.194 \
  --server-public-key "ПУБЛИЧНЫЙ_КЛЮЧ_СЕРВЕРА" \
  --output client.conf

# Сгенерируйте ключи клиента
python -m securevpn.cli generate-keys --client --name client
```

### 3. Подключение к VPN

```bash
# Подключение к VPN (требует sudo для TUN интерфейса)
sudo python -m securevpn.cli client --config client.conf --auto-reconnect
```

## 📊 Мониторинг и управление

### Полезные команды

```bash
# Статус сервиса
systemctl status securevpn-server

# Просмотр логов
journalctl -u securevpn-server -f

# Перезапуск сервиса
systemctl restart securevpn-server

# Остановка сервиса
systemctl stop securevpn-server

# Проверка конфигурации
/opt/securevpn/venv/bin/python -m securevpn.cli validate /etc/securevpn/server.conf
```

### Мониторинг подключений

```bash
# Просмотр активных подключений
ss -tulpn | grep 51820

# Мониторинг TUN интерфейса
ip addr show svpn0

# Статистика трафика
cat /proc/net/dev | grep svpn0
```

## 🔒 Безопасность

### Рекомендации по безопасности

1. **Регулярно обновляйте систему:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Настройте fail2ban:**
   ```bash
   sudo apt install fail2ban
   sudo systemctl enable fail2ban
   ```

3. **Отключите SSH по паролю:**
   ```bash
   # В /etc/ssh/sshd_config
   PasswordAuthentication no
   sudo systemctl restart ssh
   ```

4. **Настройте автоматические обновления:**
   ```bash
   sudo apt install unattended-upgrades
   sudo dpkg-reconfigure unattended-upgrades
   ```

### Ротация ключей

```bash
# Генерация новых ключей сервера
cd /etc/securevpn
/opt/securevpn/venv/bin/python -m securevpn.cli generate-keys --server --name server_new

# Замена ключей (требует перезапуск сервиса)
mv server_private.key server_private.key.old
mv server_public.key server_public.key.old
mv server_new_server_private.key server_private.key
mv server_new_server_public.key server_public.key

# Перезапуск сервиса
systemctl restart securevpn-server
```

## 🐛 Устранение неполадок

### Частые проблемы

1. **Сервис не запускается:**
   ```bash
   # Проверьте логи
   journalctl -u securevpn-server --no-pager -l
   
   # Проверьте конфигурацию
   /opt/securevpn/venv/bin/python -m securevpn.cli validate /etc/securevpn/server.conf
   ```

2. **Клиент не может подключиться:**
   ```bash
   # Проверьте firewall на сервере
   sudo ufw status
   
   # Проверьте, слушает ли сервер порт
   ss -tulpn | grep 51820
   
   # Проверьте публичный ключ сервера
   cat /etc/securevpn/server_public.key
   ```

3. **Нет интернета через VPN:**
   ```bash
   # Проверьте IP forwarding
   cat /proc/sys/net/ipv4/ip_forward
   
   # Проверьте iptables правила
   iptables -t nat -L POSTROUTING
   
   # Проверьте TUN интерфейс
   ip addr show svpn0
   ```

### Логи и диагностика

```bash
# Логи сервера
tail -f /var/log/securevpn/server.log

# Системные логи
journalctl -u securevpn-server -f

# Сетевая диагностика
tcpdump -i any port 51820

# Проверка TUN интерфейса
ip route show table all | grep svpn0
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи сервиса
2. Убедитесь, что все зависимости установлены
3. Проверьте сетевые настройки
4. Обратитесь к разделу "Устранение неполадок"

---

**🎉 Поздравляем! Ваш SecureVPN сервер готов к работе!**

Теперь вы можете подключать клиентов и наслаждаться безопасным и быстрым VPN-соединением с продвинутой обфускацией трафика.
