---
name: power-sentry-deploy-jump
description: Deploy a PowerSentry worker agent daemon on the jump/bastion host itself (e.g., rb-master). Use when asked to monitor the jump host or deploy a worker agent on a directly-accessible server without a bastion.
---

# PowerSentry Deploy — Jump Host Worker Daemon

## Overview

Deploys the PowerSentry worker agent directly on the jump/bastion host (e.g., rb-master). Unlike deploying to a Proxmox host behind a bastion, the jump host itself is accessed directly (no intermediate hop).

## Prerequisites

- Direct SSH access to the jump host (via Tailscale or public IP)
- SSH key `~/.ssh/id_ed25519`
- Python 3 on the jump host
- `.env` configured with `JUMP_HOST` empty (direct connection)

## .env Configuration

```bash
# proxmox-power-monitor/.env
PROXMOX_HOST=<jump-host-ip>     # The jump host's own IP
JUMP_HOST=                       # Leave empty for direct connection
REMOTE_USER=ubuntu               # Jump host username
```

Or pass directly via CLI (no `.env` needed):

```bash
cd proxmox-power-monitor
./deploy.sh <jump-host-ip>
# Example: ./deploy.sh 100.86.93.41
```

## Deployment Steps

### 1. Run deploy script (direct mode)

```bash
cd proxmox-power-monitor
./deploy.sh <jump-host-ip>
```

Since no `JUMP_HOST` is provided, the script will:
- Connect directly (no proxy jump)
- Check Python 3 availability
- Install `websockets` dependency
- Copy all Python files to `/opt/proxmox-power-monitor`
- Set permissions

### 2. SSH into the jump host

```bash
ssh ubuntu@<jump-host-ip>
```

### 3. Install and start the worker

```bash
cd /opt/proxmox-power-monitor

# Install with control panel connection
python3 cli.py install --control-panel=ws://<control-panel-host>:8765/worker

# Start the daemon
python3 cli.py start

# Verify
python3 cli.py status
python3 cli.py stats --recent=5
```

## Network Considerations

- The jump host needs **outbound** connectivity to the control panel WebSocket port (`:8765`)
- If the control panel is on a public server (e.g., dk1), this should work by default
- If the control panel is on the same LAN, ensure routing is correct

## Service Management

Same as any worker agent:
```bash
systemctl status powersentry-worker
journalctl -u powersentry-worker -f
cd /opt/proxmox-power-monitor && python3 cli.py uninstall
```
