#!/bin/bash

# SecureVPN Server Deployment Script
# Автоматическое развертывание VPN сервера из Git репозитория

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
REPO_URL="https://github.com/YOUR_USERNAME/SecureVPN.git"  # Замените на ваш репозиторий
INSTALL_DIR="/opt/securevpn"
CONFIG_DIR="/etc/securevpn"
LOG_DIR="/var/log/securevpn"
SERVICE_NAME="securevpn-server"

# Функции для вывода
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Этот скрипт должен быть запущен с правами root"
        exit 1
    fi
}

# Определение ОС
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        print_error "Не удается определить ОС"
        exit 1
    fi
    
    print_status "Обнаружена ОС: $OS $VER"
}

# Обновление системы
update_system() {
    print_status "Обновление системы..."
    
    case $OS in
        "Ubuntu"*|"Debian"*)
            apt-get update
            apt-get upgrade -y
            ;;
        "CentOS"*|"Red Hat"*|"Fedora"*)
            if command -v dnf &> /dev/null; then
                dnf update -y
            else
                yum update -y
            fi
            ;;
        *)
            print_warning "Неизвестная ОС, пропускаем обновление"
            ;;
    esac
    
    print_success "Система обновлена"
}

# Установка зависимостей
install_dependencies() {
    print_status "Установка зависимостей..."
    
    case $OS in
        "Ubuntu"*|"Debian"*)
            apt-get install -y \
                python3 \
                python3-pip \
                python3-venv \
                python3-dev \
                build-essential \
                libffi-dev \
                libssl-dev \
                iproute2 \
                iptables \
                git \
                curl \
                wget \
                htop \
                nano \
                ufw
            ;;
        "CentOS"*|"Red Hat"*|"Fedora"*)
            if command -v dnf &> /dev/null; then
                dnf install -y \
                    python3 \
                    python3-pip \
                    python3-devel \
                    gcc \
                    gcc-c++ \
                    libffi-devel \
                    openssl-devel \
                    iproute \
                    iptables \
                    git \
                    curl \
                    wget \
                    htop \
                    nano \
                    firewalld
            else
                yum install -y \
                    python3 \
                    python3-pip \
                    python3-devel \
                    gcc \
                    gcc-c++ \
                    libffi-devel \
                    openssl-devel \
                    iproute \
                    iptables \
                    git \
                    curl \
                    wget \
                    htop \
                    nano \
                    firewalld
            fi
            ;;
        *)
            print_error "Неподдерживаемая ОС: $OS"
            exit 1
            ;;
    esac
    
    print_success "Зависимости установлены"
}

# Создание директорий
create_directories() {
    print_status "Создание директорий..."
    
    mkdir -p $INSTALL_DIR
    mkdir -p $CONFIG_DIR
    mkdir -p $LOG_DIR
    
    # Установка прав
    chmod 755 $INSTALL_DIR
    chmod 755 $CONFIG_DIR
    chmod 755 $LOG_DIR
    
    print_success "Директории созданы"
}

# Клонирование репозитория
clone_repository() {
    print_status "Клонирование репозитория SecureVPN..."
    
    # Удаляем старую установку если есть
    if [ -d "$INSTALL_DIR/.git" ]; then
        print_status "Обновление существующего репозитория..."
        cd $INSTALL_DIR
        git pull origin main
    else
        print_status "Клонирование нового репозитория..."
        rm -rf $INSTALL_DIR/*
        git clone $REPO_URL $INSTALL_DIR
        cd $INSTALL_DIR
    fi
    
    print_success "Репозиторий клонирован/обновлен"
}

# Установка SecureVPN
install_securevpn() {
    print_status "Установка SecureVPN..."
    
    cd $INSTALL_DIR
    
    # Создание виртуального окружения
    python3 -m venv venv
    
    # Активация и установка зависимостей
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e .
    
    print_success "SecureVPN установлен"
}

# Генерация конфигурации
generate_config() {
    print_status "Генерация конфигурации сервера..."
    
    # Копирование конфигурации
    cp $INSTALL_DIR/configs/server.conf $CONFIG_DIR/
    
    # Генерация ключей сервера
    cd $CONFIG_DIR
    $INSTALL_DIR/venv/bin/python -m securevpn.cli generate-keys --server --output-dir $CONFIG_DIR --name server
    
    # Установка прав
    chmod 600 server_private.key
    chmod 644 server_public.key server.conf
    
    print_success "Конфигурация сгенерирована"
    
    # Показать публичный ключ
    print_status "Публичный ключ сервера (сохраните для клиентов):"
    echo -e "${GREEN}$(cat server_public.key)${NC}"
}

# Настройка сети
configure_network() {
    print_status "Настройка сети..."
    
    # Включение IP forwarding
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
    sysctl -p
    
    # Настройка firewall
    if command -v ufw &> /dev/null; then
        print_status "Настройка UFW..."
        ufw allow 51820/udp
        ufw allow ssh
        ufw --force enable
    elif command -v firewall-cmd &> /dev/null; then
        print_status "Настройка firewalld..."
        firewall-cmd --permanent --add-port=51820/udp
        firewall-cmd --permanent --add-masquerade
        firewall-cmd --reload
    else
        print_warning "Firewall не обнаружен. Настройте вручную порт 51820/udp"
    fi
    
    print_success "Сеть настроена"
}

# Установка systemd сервиса
install_service() {
    print_status "Установка systemd сервиса..."
    
    # Копирование файла сервиса
    cp $INSTALL_DIR/systemd/securevpn-server.service /etc/systemd/system/
    
    # Перезагрузка systemd
    systemctl daemon-reload
    
    # Включение автозапуска
    systemctl enable $SERVICE_NAME
    
    print_success "Systemd сервис установлен"
}

# Запуск сервиса
start_service() {
    print_status "Запуск SecureVPN сервиса..."
    
    systemctl start $SERVICE_NAME
    
    # Проверка статуса
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_success "SecureVPN сервис запущен успешно"
    else
        print_error "Не удалось запустить SecureVPN сервис"
        systemctl status $SERVICE_NAME
        exit 1
    fi
}

# Показать статус
show_status() {
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}  SecureVPN развернут успешно!${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "${BLUE}Директория установки:${NC} $INSTALL_DIR"
    echo -e "${BLUE}Директория конфигурации:${NC} $CONFIG_DIR"
    echo -e "${BLUE}Директория логов:${NC} $LOG_DIR"
    echo ""
    echo -e "${BLUE}Статус сервиса:${NC}"
    systemctl status $SERVICE_NAME --no-pager -l
    echo ""
    echo -e "${BLUE}Публичный ключ сервера:${NC}"
    echo -e "${GREEN}$(cat $CONFIG_DIR/server_public.key)${NC}"
    echo ""
    echo -e "${BLUE}Полезные команды:${NC}"
    echo "  Статус:           systemctl status $SERVICE_NAME"
    echo "  Остановка:        systemctl stop $SERVICE_NAME"
    echo "  Перезапуск:       systemctl restart $SERVICE_NAME"
    echo "  Логи:             journalctl -u $SERVICE_NAME -f"
    echo "  Конфигурация:     nano $CONFIG_DIR/server.conf"
    echo ""
    echo -e "${YELLOW}Следующие шаги:${NC}"
    echo "1. Сохраните публичный ключ сервера для настройки клиентов"
    echo "2. Настройте клиентские устройства"
    echo "3. Мониторьте логи: journalctl -u $SERVICE_NAME -f"
    echo ""
}

# Основная функция развертывания
main() {
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║       SecureVPN Auto Deploy           ║"
    echo "║   Автоматическое развертывание VPN    ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_root
    detect_os
    update_system
    install_dependencies
    create_directories
    clone_repository
    install_securevpn
    generate_config
    configure_network
    install_service
    start_service
    show_status
}

# Обработка аргументов
case "${1:-}" in
    "update")
        print_status "Обновление SecureVPN..."
        clone_repository
        install_securevpn
        systemctl restart $SERVICE_NAME
        print_success "SecureVPN обновлен"
        ;;
    "uninstall")
        print_status "Удаление SecureVPN..."
        systemctl stop $SERVICE_NAME || true
        systemctl disable $SERVICE_NAME || true
        rm -f /etc/systemd/system/$SERVICE_NAME.service
        rm -rf $INSTALL_DIR
        print_warning "Конфигурация сохранена в $CONFIG_DIR"
        print_success "SecureVPN удален"
        ;;
    "status")
        systemctl status $SERVICE_NAME
        ;;
    *)
        main "$@"
        ;;
esac
