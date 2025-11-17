#!/bin/bash

# SecureVPN Installation Script
# Installs SecureVPN server on Ubuntu/Debian systems

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/securevpn"
CONFIG_DIR="/etc/securevpn"
LOG_DIR="/var/log/securevpn"
SERVICE_NAME="securevpn-server"

# Print colored output
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

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        print_error "Cannot detect OS"
        exit 1
    fi
    
    print_status "Detected OS: $OS $VER"
}

# Install system dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    case $OS in
        "Ubuntu"*|"Debian"*)
            apt-get update
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
                wget
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
                    wget
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
                    wget
            fi
            ;;
        *)
            print_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
    
    print_success "System dependencies installed"
}

# Create directories
create_directories() {
    print_status "Creating directories..."
    
    mkdir -p $INSTALL_DIR
    mkdir -p $CONFIG_DIR
    mkdir -p $LOG_DIR
    
    # Set permissions
    chmod 755 $INSTALL_DIR
    chmod 755 $CONFIG_DIR
    chmod 755 $LOG_DIR
    
    print_success "Directories created"
}

# Install SecureVPN
install_securevpn() {
    print_status "Installing SecureVPN..."
    
    # Copy source code
    cp -r src/ $INSTALL_DIR/
    cp requirements.txt $INSTALL_DIR/
    cp pyproject.toml $INSTALL_DIR/
    
    # Create virtual environment
    cd $INSTALL_DIR
    python3 -m venv venv
    
    # Activate virtual environment and install dependencies
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e .
    
    print_success "SecureVPN installed"
}

# Generate configuration
generate_config() {
    print_status "Generating configuration..."
    
    # Copy default configuration
    cp configs/server.conf $CONFIG_DIR/
    
    # Generate server keys
    cd $CONFIG_DIR
    $INSTALL_DIR/venv/bin/python -m securevpn.cli generate-keys --server --output-dir $CONFIG_DIR --name server
    
    # Set permissions
    chmod 600 server_private.key
    chmod 644 server_public.key
    chmod 644 server.conf
    
    print_success "Configuration generated"
    
    # Show public key
    print_status "Server public key (share with clients):"
    echo -e "${GREEN}$(cat server_public.key)${NC}"
}

# Install systemd service
install_service() {
    print_status "Installing systemd service..."
    
    # Copy service file
    cp systemd/securevpn-server.service /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable $SERVICE_NAME
    
    print_success "Systemd service installed"
}

# Configure firewall
configure_firewall() {
    print_status "Configuring firewall..."
    
    # Check if ufw is installed
    if command -v ufw &> /dev/null; then
        print_status "Configuring UFW..."
        ufw allow 51820/udp
        ufw --force enable
    elif command -v firewall-cmd &> /dev/null; then
        print_status "Configuring firewalld..."
        firewall-cmd --permanent --add-port=51820/udp
        firewall-cmd --permanent --add-masquerade
        firewall-cmd --reload
    else
        print_warning "No firewall detected. Please manually allow port 51820/udp"
    fi
    
    print_success "Firewall configured"
}

# Enable IP forwarding
enable_ip_forwarding() {
    print_status "Enabling IP forwarding..."
    
    # Enable for current session
    echo 1 > /proc/sys/net/ipv4/ip_forward
    
    # Make permanent
    if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
        echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    fi
    
    sysctl -p
    
    print_success "IP forwarding enabled"
}

# Start service
start_service() {
    print_status "Starting SecureVPN service..."
    
    systemctl start $SERVICE_NAME
    
    # Check status
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_success "SecureVPN service started successfully"
    else
        print_error "Failed to start SecureVPN service"
        systemctl status $SERVICE_NAME
        exit 1
    fi
}

# Show status
show_status() {
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}  SecureVPN Installation Complete${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "${BLUE}Installation Directory:${NC} $INSTALL_DIR"
    echo -e "${BLUE}Configuration Directory:${NC} $CONFIG_DIR"
    echo -e "${BLUE}Log Directory:${NC} $LOG_DIR"
    echo ""
    echo -e "${BLUE}Service Status:${NC}"
    systemctl status $SERVICE_NAME --no-pager -l
    echo ""
    echo -e "${BLUE}Server Public Key:${NC}"
    echo -e "${GREEN}$(cat $CONFIG_DIR/server_public.key)${NC}"
    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  Start service:    systemctl start $SERVICE_NAME"
    echo "  Stop service:     systemctl stop $SERVICE_NAME"
    echo "  Restart service:  systemctl restart $SERVICE_NAME"
    echo "  View logs:        journalctl -u $SERVICE_NAME -f"
    echo "  Edit config:      nano $CONFIG_DIR/server.conf"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Share the server public key with clients"
    echo "2. Configure client devices using the public key"
    echo "3. Monitor logs: journalctl -u $SERVICE_NAME -f"
    echo ""
}

# Main installation function
main() {
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║         SecureVPN Installer           ║"
    echo "║   High-Performance Encrypted VPN     ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_root
    detect_os
    install_dependencies
    create_directories
    install_securevpn
    generate_config
    install_service
    configure_firewall
    enable_ip_forwarding
    start_service
    show_status
}

# Run installation
main "$@"
