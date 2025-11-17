# SecureVPN Docker Image
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    iproute2 \
    iptables \
    iputils-ping \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd -r securevpn && useradd -r -g securevpn securevpn

# Create directories
RUN mkdir -p /app /var/log/securevpn /etc/securevpn
RUN chown -R securevpn:securevpn /var/log/securevpn /etc/securevpn

# Copy application
COPY src/ /app/src/
COPY configs/ /etc/securevpn/

# Set working directory
WORKDIR /app

# Create TUN device (requires privileged mode)
RUN mkdir -p /dev/net && \
    mknod /dev/net/tun c 10 200 && \
    chmod 666 /dev/net/tun

# Expose VPN port
EXPOSE 51820/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('0.0.0.0', 51820)); s.close()" || exit 1

# Set entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user for security (will need to run as root for TUN access)
# USER securevpn

ENTRYPOINT ["/entrypoint.sh"]
CMD ["server", "--config", "/etc/securevpn/server.conf"]
