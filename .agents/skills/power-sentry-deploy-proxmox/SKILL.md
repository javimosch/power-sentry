---
name: power-sentry-deploy-proxmox
description: Deploy a PowerSentry worker agent daemon on a Proxmox host (or any target server), optionally via a jump/bastion host. Use when asked to deploy monitoring on a Proxmox server or any remote host behind a bastion.
---

# PowerSentry Deploy — Proxmox Worker Daemon

## Overview

Deploys the PowerSentry worker agent (daemon + CLI) to a Proxmox host or any target server. Supports both direct connections and multi-hop SSH via a jump/bastion host.

## Prerequisites

- SSH access to the target host (via jump host if needed)
- SSH key: `~/.ssh/id_ed25519` (or specify a different key in `SSH_BASE`)
- Python 3 on the target host
- The `.env` file configured with your network specifics OR pass values as CLI args

## .env Configuration

Create or update `proxmox-power-monitor/.env`:

```bash
PROXMOX_HOST=192.168.1.104       # IP of the target Proxmox host
JUMP_HOST=100.86.93.41           # Optional: bastion/jump host IP (leave empty for direct)
JUMP_USER=ubuntu                 # Jump host SSH username
REMOTE_USER=root                 # Target host SSH username (usually root for Proxmox)
```

## Deployment Steps

### 1. Copy .env from template (if not already done)

```bash
cd proxmox-power-monitor
cp .env.example .env
# Edit .env with your actual IPs and credentials
```

### 2. Run deploy script

**With jump host (multi-hop):**
```bash
cd proxmox-power-monitor
./deploy.sh <proxmox-host> <jump-host>
# Example: ./deploy.sh 192.168.1.104 100.86.93.41
```

**Direct connection (no jump host):**
```bash
cd proxmox-power-monitor
./deploy.sh <target-ip>
# Example: ./deploy.sh 192.168.1.104
```

The script will:
1. Load `.env` if present (values can be overridden by CLI args)
2. Check connectivity (jump host if specified, then target)
3. Verify Python 3 availability on target
4. Install `websockets` Python package
5. Create remote directory structure (`/opt/proxmox-power-monitor`)
6. Copy all Python files to the target
7. Set permissions

### 3. SSH into target and install the service

```bash
# Via jump host
ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 \
    -J ubuntu@<jump-host> root@<proxmox-host>

# Or directly
ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 root@<target-ip>
```

### 4. Install and start the worker

```bash
cd /opt/proxmox-power-monitor

# Install as systemd service (standalone mode)
python3 cli.py install

# Install with control panel connection
python3 cli.py install --control-panel=ws://<control-panel-host>:8765/worker

# Start the daemon
python3 cli.py start

# Verify it's running
python3 cli.py status
```

### 5. Verify metrics

```bash
# Check stats
python3 cli.py stats --total
python3 cli.py stats --recent=10

# Project costs
python3 cli.py project 14
```

## What Gets Deployed

| File | Purpose |
|------|---------|
| `daemon.py` | Main metrics collection daemon |
| `cli.py` | CLI for service management |
| `websocket_client.py` | WebSocket client for control panel communication |
| `database.py` | SQLite database management |
| `power.py` | Power calculation model |
| `pricing.py` | Electricity pricing |
| `metrics.py` | System metrics collection |

## Service Management

```bash
# Check status
systemctl status powersentry-worker

# View logs
journalctl -u powersentry-worker -f

# Uninstall
cd /opt/proxmox-power-monitor
python3 cli.py uninstall
```

## Troubleshooting

**Connection refused to control panel:**
- Verify control panel is running: `systemctl status powersency-control-panel`
- Check network connectivity: `ping <control-panel-host>`
- Test WebSocket: `wscat -c ws://<control-panel>:8765/worker`

**No metrics appearing:**
- Check daemon logs: `journalctl -u powersentry-worker -f`
- Verify database permissions: `ls -la /var/lib/proxmox-power-monitor/`
- Restart daemon: `python3 cli.py restart`

**Deploy script fails:**
- Verify jump host connectivity if using one
- Check SSH key permissions: `chmod 600 ~/.ssh/id_ed25519`
- Ensure Python 3 is available on target: `which python3`
