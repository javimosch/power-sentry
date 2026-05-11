#!/bin/bash

# Deployment script for proxmox-power-monitor (Python version)
# Usage: ./deploy.sh <proxmox-host> [jump-host]

set -e

# Load configuration from .env file if present
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

PROXMOX_HOST=${PROXMOX_HOST:-${1:-"<proxmox-host>"}}
JUMP_HOST=${JUMP_HOST:-${2:-"<jump-host>"}}
JUMP_USER=${JUMP_USER:-"ubuntu"}
REMOTE_USER=${REMOTE_USER:-"root"}
REMOTE_DIR="/opt/proxmox-power-monitor"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying proxmox-power-monitor to ${PROXMOX_HOST} via jump host ${JUMP_HOST}..."

# Base SSH command
SSH_BASE="ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 -o StrictHostKeyChecking=no"
SSH_JUMP="${SSH_BASE} ${JUMP_USER}@${JUMP_HOST}"

# Check if jump host is reachable
echo "Checking jump host connectivity..."
${SSH_JUMP} "echo 'Jump host connection successful'" || {
  echo "Error: Cannot connect to jump host ${JUMP_HOST}"
  exit 1
}

# Check if target host is reachable via jump
echo "Checking target host connectivity..."
${SSH_JUMP} "ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${PROXMOX_HOST} 'echo Target host connection successful'" || {
  echo "Error: Cannot connect to ${PROXMOX_HOST} via jump host"
  exit 1
}

# Check if Python3 is available
echo "Checking Python3 availability..."
${SSH_JUMP} "ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${PROXMOX_HOST} 'which python3'" || {
  echo "Error: Python3 is not available on target host"
  exit 1
}

# Install websockets dependency
echo "Installing websockets dependency..."
${SSH_JUMP} "ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${PROXMOX_HOST} 'pip3 install websockets || echo websockets already installed'"

# Create remote directory structure
echo "Creating remote directory structure..."
${SSH_JUMP} "ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${PROXMOX_HOST} 'mkdir -p ${REMOTE_DIR} /var/lib/proxmox-power-monitor'"

# Copy application files (Python version only)
echo "Copying application files..."
cd ${LOCAL_DIR}
tar czf - --exclude='node_modules' --exclude='.git' --exclude='src' --exclude='package.json' \
  *.py | ${SSH_JUMP} "ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${PROXMOX_HOST} 'tar xzf - -C ${REMOTE_DIR}'"

# Set permissions
echo "Setting permissions..."
${SSH_JUMP} "ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${PROXMOX_HOST} '
chown -R root:root ${REMOTE_DIR}
chmod -R 755 ${REMOTE_DIR}
chmod +x ${REMOTE_DIR}/daemon.py
chmod +x ${REMOTE_DIR}/cli.py
chown -R root:root /var/lib/proxmox-power-monitor
chmod 755 /var/lib/proxmox-power-monitor
'"

echo "Deployment complete!"
echo ""
echo "Next steps on ${PROXMOX_HOST}:"
echo "  1. SSH into the host: ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 -J ${JUMP_USER}@${JUMP_HOST} ${REMOTE_USER}@${PROXMOX_HOST}"
echo "  2. Install the service: cd ${REMOTE_DIR} && python3 cli.py install"
echo "  3. Start the daemon: python3 cli.py start"
echo "  4. Check stats: python3 cli.py stats"
echo ""
echo "To uninstall:"
echo "  python3 cli.py uninstall"
