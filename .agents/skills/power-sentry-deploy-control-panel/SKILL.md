---
name: power-sentry-deploy-control-panel
description: Deploy the PowerSentry control panel (WebSocket server + web UI) on a server like dk1. Use when asked to set up the central dashboard, WebSocket server, or monitoring UI.
---

# PowerSentry Deploy — Control Panel (UI Daemon)

## Overview

Deploys the PowerSentry control panel on a server (e.g., dk1). The control panel includes:
- **WebSocket Server** (`:8765`): Receives real-time metrics from worker agents
- **HTTP Server** (`:8080`): Serves the web dashboard and REST API
- **Central Database** (SQLite): Stores all worker data
- **Web UI** (Vue 3 + Tailwind + DaisyUI): Real-time dashboard

## Prerequisites

- SSH access to the target server (e.g., dk1@92.113.145.178)
- SSH key for the target server
- Python 3 on the target
- WebSocket port `:8765` and HTTP port `:8080` must be open/forwarded

## .env Configuration

```bash
# proxmox-power-monitor/.env
DK1_HOST=<control-panel-ip>         # Public IP or hostname of the control panel server
DK1_USER=<ssh-username>             # SSH username (e.g., dk1 for dk1 VM)
```

## Deployment Steps

### 1. Run deploy-control-panel script

```bash
cd proxmox-power-monitor
./deploy-control-panel.sh <control-panel-host>
# Example: ./deploy-control-panel.sh 92.113.145.178
```

The script will:
1. Load `.env` if present
2. Check connectivity to the target
3. Verify Python 3 availability
4. Install `websockets` Python package
5. Create remote directories
6. Copy `control-panel/server/server.py` to the target
7. Copy `control-panel/ui/index.html` to the target
8. Create a systemd **user** service (`powersency-control-panel`)
9. Reload systemd and enable the service

### 2. SSH into the control panel server

```bash
ssh <user>@<control-panel-host>
```

### 3. Start the control panel

```bash
systemctl --user start powersency-control-panel
systemctl --user status powersency-control-panel
```

### 4. Access the web UI

Open `http://<control-panel-host>:8080` in a browser.

## Service Management

```bash
# Check status
systemctl --user status powersency-control-panel

# View logs
journalctl -u powersency-control-panel -f

# Restart
systemctl --user restart powersency-control-panel

# Stop
systemctl --user stop powersency-control-panel
```

## Connecting Workers

Once the control panel is running, workers can connect by specifying the WebSocket URL:

```bash
# On each worker (Proxmox host, jump host, etc.)
python3 cli.py install --control-panel=ws://<control-panel-host>:8765/worker
python3 cli.py start
```

## Troubleshooting

**Web UI not accessible:**
```bash
# Check HTTP server is listening
netstat -tlnp | grep 8080

# Check service logs
journalctl -u powersency-control-panel -f
```

**Workers not connecting:**
```bash
# Check WebSocket server is listening
netstat -tlnp | grep 8765

# Test WebSocket connection
wscat -c ws://<control-panel>:8765/worker

# Check firewall
iptables -L
```

**Ports not accessible:**
- Ensure ports `8080` and `8765` are open in any firewall
- For cloud VMs, check security group/network ACL rules
- Use SSH port forwarding for testing: `ssh -L 8080:localhost:8080 <user>@<host>`
