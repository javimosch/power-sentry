#!/bin/bash

# Deployment script for PowerSentry Control Panel
# Usage: ./deploy-control-panel.sh [control-panel-host] [control-panel-user]

set -e

# Load configuration from .env file if present
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

DK1_HOST=${DK1_HOST:-${1:-"<control-panel-host>"}}
REMOTE_USER=${DK1_USER:-${2:-"<control-panel-user>"}}
REMOTE_DIR="/home/${REMOTE_USER}/powersentry"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying PowerSentry Control Panel to ${DK1_HOST}..."

# Check if host is reachable
echo "Checking host connectivity..."
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${REMOTE_USER}@${DK1_HOST} "echo 'Connection successful'" || {
  echo "Error: Cannot connect to ${DK1_HOST}"
  exit 1
}

# Check Python3 availability
echo "Checking Python3 availability..."
ssh ${REMOTE_USER}@${DK1_HOST} "which python3" || {
  echo "Error: Python3 is not available on target host"
  exit 1
}

# Install Python dependencies
echo "Installing Python dependencies..."
ssh ${REMOTE_USER}@${DK1_HOST} << 'ENDSSH'
pip3 install websockets || echo "websockets already installed or failed"
ENDSSH

# Create remote directory structure
echo "Creating remote directory structure..."
ssh ${REMOTE_USER}@${DK1_HOST} "mkdir -p ${REMOTE_DIR}/server ${REMOTE_DIR}/ui ~/.local/share/powersentry"

# Copy control panel server files
echo "Copying control panel server files..."
cd ${LOCAL_DIR}/control-panel/server
tar czf - *.py | ssh ${REMOTE_USER}@${DK1_HOST} "tar xzf - -C ${REMOTE_DIR}/server"

# Copy UI files
echo "Copying UI files..."
cd ${LOCAL_DIR}/control-panel/ui
tar czf - *.html | ssh ${REMOTE_USER}@${DK1_HOST} "tar xzf - -C ${REMOTE_DIR}/ui"

# Set permissions
echo "Setting permissions..."
ssh ${REMOTE_USER}@${DK1_HOST} "
chmod -R 755 ${REMOTE_DIR}
chmod +x ${REMOTE_DIR}/server/server.py
chmod 755 ~/.local/share/powersentry
"

# Create systemd user service file
echo "Creating systemd user service..."
ssh ${REMOTE_USER}@${DK1_HOST} "mkdir -p ~/.config/systemd/user && cat > ~/.config/systemd/user/powersency-control-panel.service << 'EOF'
[Unit]
Description=PowerSentry Control Panel
After=network.target

[Service]
Type=simple
WorkingDirectory=${REMOTE_DIR}/server
Environment=\"PYTHONUNBUFFERED=1\"
ExecStart=/usr/bin/python3 ${REMOTE_DIR}/server/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
"

# Reload systemd and enable service
echo "Enabling systemd user service..."
ssh ${REMOTE_USER}@${DK1_HOST} "systemctl --user daemon-reload && systemctl --user enable powersency-control-panel"

echo "Deployment complete!"
echo ""
echo "Next steps on ${DK1_HOST}:"
echo "  1. SSH into the host: ssh ${REMOTE_USER}@${DK1_HOST}"
echo "  2. Start the service: systemctl --user start powersency-control-panel"
echo "  3. Check status: systemctl --user status powersency-control-panel"
echo "  4. Access UI: http://${DK1_HOST}:8080"
echo "  5. WebSocket endpoint: ws://${DK1_HOST}:8765/worker"
echo ""
echo "To manage service:"
echo "  systemctl --user start/stop/restart powersency-control-panel"
