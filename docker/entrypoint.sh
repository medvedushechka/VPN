#!/bin/bash
set -e

# SecureVPN Docker Entrypoint Script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting SecureVPN Container${NC}"

# Check if running as root (required for TUN interface)
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: SecureVPN requires root privileges for TUN interface management${NC}"
    echo -e "${YELLOW}Please run container with --privileged flag or --cap-add=NET_ADMIN${NC}"
    exit 1
fi

# Ensure TUN device exists
if [ ! -c /dev/net/tun ]; then
    echo -e "${YELLOW}Creating TUN device...${NC}"
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200
    chmod 666 /dev/net/tun
fi

# Enable IP forwarding
echo -e "${YELLOW}Enabling IP forwarding...${NC}"
echo 1 > /proc/sys/net/ipv4/ip_forward

# Setup iptables for NAT (if not exists)
if ! iptables -t nat -C POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE 2>/dev/null; then
    echo -e "${YELLOW}Setting up NAT rules...${NC}"
    iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE
    iptables -A FORWARD -i svpn0 -j ACCEPT
    iptables -A FORWARD -o svpn0 -j ACCEPT
fi

# Generate server keys if they don't exist
if [ ! -f /etc/securevpn/server_private.key ]; then
    echo -e "${YELLOW}Generating server keys...${NC}"
    cd /etc/securevpn
    python -m securevpn.cli generate-keys --server --output-dir /etc/securevpn --name server
fi

# Show server public key
if [ -f /etc/securevpn/server_public.key ]; then
    echo -e "${GREEN}Server Public Key:${NC}"
    cat /etc/securevpn/server_public.key
    echo ""
fi

# Create log directory
mkdir -p /var/log/securevpn
chown -R securevpn:securevpn /var/log/securevpn

# Set Python path
export PYTHONPATH="/app/src:$PYTHONPATH"

# Handle shutdown gracefully
cleanup() {
    echo -e "${YELLOW}Shutting down SecureVPN...${NC}"
    # Kill any background processes
    pkill -f "python.*securevpn" || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start SecureVPN
echo -e "${GREEN}Starting SecureVPN with arguments: $@${NC}"

# Change to app directory
cd /app

# Execute the command
exec python -m securevpn.cli "$@"
