#!/bin/bash

# Deployment script for proxmox-power-monitor (Python version)
# Usage: ./deploy.sh <proxmox-host> [jump-host]
#   <proxmox-host>  - Required: IP or hostname of target Proxmox server
#   [jump-host]     - Optional: Bastion/jump host for multi-hop SSH. Omit for direct access.

set -e

# Load configuration from .env file if present
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

PROXMOX_HOST=${PROXMOX_HOST:-${1:-"<proxmox-host>"}}
JUMP_HOST=${JUMP_HOST:-${2:-}}
JUMP_USER=${JUMP_USER:-"ubuntu"}
REMOTE_USER=${REMOTE_USER:-"root"}
REMOTE_DIR="/opt/proxmox-power-monitor"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SSH_BASE="ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 -o StrictHostKeyChecking=no"

# Build SSH command: use ProxyJump (-J) if jump host is provided, direct otherwise
if [ -n "$JUMP_HOST" ]; then
    echo "Deploying to ${PROXMOX_HOST} via jump host ${JUMP_HOST}..."
    SSH_CMD="${SSH_BASE} -J ${JUMP_USER}@${JUMP_HOST} ${REMOTE_USER}@${PROXMOX_HOST}"
    SSH_PROXY_CHECK="${SSH_BASE} ${JUMP_USER}@${JUMP_HOST}"
else
    echo "Deploying to ${PROXMOX_HOST} (direct connection)..."
    SSH_CMD="${SSH_BASE} ${REMOTE_USER}@${PROXMOX_HOST}"
    SSH_PROXY_CHECK=""
fi

# If jump host is set, check its connectivity first
if [ -n "$SSH_PROXY_CHECK" ]; then
    echo "Checking jump host connectivity..."
    ${SSH_PROXY_CHECK} "echo 'Jump host connection successful'" || {
        echo "Error: Cannot connect to jump host ${JUMP_HOST}"
        exit 1
    }
fi

# Check if target host is reachable (directly or via jump)
echo "Checking target host connectivity..."
${SSH_CMD} "echo 'Target host connection successful'" || {
    echo "Error: Cannot connect to ${PROXMOX_HOST}"
    exit 1
}

# Check if Python3 is available
echo "Checking Python3 availability..."
${SSH_CMD} "which python3" || {
    echo "Error: Python3 is not available on target host"
    exit 1
}

# Install websockets dependency
echo "Installing websockets dependency..."
${SSH_CMD} "pip3 install websockets || echo websockets already installed"

# Create remote directory structure
echo "Creating remote directory structure..."
${SSH_CMD} "mkdir -p ${REMOTE_DIR} /var/lib/proxmox-power-monitor"

# Copy application files (Python version only)
echo "Copying application files..."
cd ${LOCAL_DIR}
tar czf - --exclude='node_modules' --exclude='.git' --exclude='src' --exclude='package.json' \
  *.py | ${SSH_CMD} "tar xzf - -C ${REMOTE_DIR}"

# Set permissions
echo "Setting permissions..."
${SSH_CMD} '
chown -R root:root '${REMOTE_DIR}'
chmod -R 755 '${REMOTE_DIR}'
chmod +x '${REMOTE_DIR}'/daemon.py
chmod +x '${REMOTE_DIR}'/cli.py
chown -R root:root /var/lib/proxmox-power-monitor
chmod 755 /var/lib/proxmox-power-monitor
'

echo "Deployment complete!"
echo ""
echo "Next steps on ${PROXMOX_HOST}:"
if [ -n "$JUMP_HOST" ]; then
    echo "  1. SSH into the host: ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 -J ${JUMP_USER}@${JUMP_HOST} ${REMOTE_USER}@${PROXMOX_HOST}"
else
    echo "  1. SSH into the host: ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 ${REMOTE_USER}@${PROXMOX_HOST}"
fi
echo "  2. Install the service: cd ${REMOTE_DIR} && python3 cli.py install"
echo "  3. Start the daemon: python3 cli.py start"
echo "  4. Check stats: python3 cli.py stats"
echo ""
echo "To uninstall:"
echo "  python3 cli.py uninstall"
