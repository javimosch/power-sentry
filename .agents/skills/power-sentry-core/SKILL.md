---
name: power-sentry-core
description: Core knowledge about the PowerSentry codebase architecture, components, data flow, and configuration. Use this skill when asked about the codebase structure, how components interact, or general understanding of the project.
---

# PowerSentry Core Skill

## Overview

PowerSentry is a distributed infrastructure power monitoring and cost optimization system. It tracks energy consumption and electricity costs for infrastructure servers, featuring real-time monitoring via WebSocket, cost projections, and a centralized web dashboard.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Control Panel                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ WebSocket    │  │ HTTP Server  │  │  Database    │  │
│  │   Server     │  │   (Web UI)   │  │  (Central)   │  │
│  │   :8765      │  │   :8080      │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │ WebSocket
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼────────┐  ┌──────▼────────┐  ┌──────▼─────────┐
│ Worker Agent  │  │ Worker Agent  │  │ Worker Agent N  │
│  (Target)     │  │  (Target)     │  │   (Target)      │
│  Daemon + WS  │  │  Daemon + WS  │  │  Daemon + WS   │
└────────────────┘  └────────────────┘  └────────────────┘
```

### Components

#### 1. Control Panel
- **WebSocket Server** (`:8765`): Receives real-time metrics from worker agents
- **HTTP Server** (`:8080`): Serves web UI and API endpoints
- **Central Database** (SQLite): Stores all worker data and historical records
- **Web UI** (Vue 3 + Tailwind + DaisyUI): Real-time dashboard
- **Location**: `control-panel/server/server.py` (Python)

#### 2. Worker Agents
- **Daemon** (`daemon.py`): Collects system metrics every minute (CPU, RAM, power)
- **WebSocket Client** (`websocket_client.py`): Sends real-time data to control panel
- **Local Database** (`database.py`): SQLite backup storage
- **CLI** (`cli.py`): Service management (install, start, stop, stats, project)
- **Power Model** (`power.py`): Power calculation (CPU TDP, RAM, base power)
- **Pricing** (`pricing.py`): French electricity rates (EDF Tarif Bleu, peak/off-peak)

## Codebase Structure

```
proxmox-power-monitor/
├── deploy.sh                    # Deploy worker agent to target (direct or via jump)
├── deploy-control-panel.sh      # Deploy control panel to a server
├── cli.py                       # Worker CLI: install, start, stop, stats, project, cleanup
├── daemon.py                    # Worker daemon: metrics collection loop
├── websocket_client.py          # WebSocket client for worker → control panel
├── database.py                  # SQLite database (local worker storage)
├── power.py                     # Power calculation model
├── pricing.py                   # French electricity pricing
├── metrics.py                   # System metrics collection
├── .env.example                 # Configuration template (copy to .env)
├── src/                         # TypeScript version (legacy/alternative)
│   ├── cli.ts
│   ├── daemon.ts
│   ├── database.ts
│   ├── pricing.ts
│   ├── power.ts
│   └── metrics.ts
├── control-panel/
│   ├── server/server.py         # WebSocket + HTTP server
│   └── ui/index.html            # Web dashboard (Vue 3 + Tailwind + DaisyUI)
├── README.md
├── ARCHITECTURE.md
└── .gitignore
```

## Data Flow

1. **Registration**: Worker connects and registers with control panel via WebSocket
2. **Metrics Collection**: Worker collects CPU, RAM, uptime every 60 seconds
3. **Real-time Sync**: Worker sends metrics via WebSocket to control panel
4. **Central Storage**: Control panel stores in central database; worker keeps local copy
5. **UI Updates**: Web dashboard displays live metrics and historical charts
6. **Cost Projection**: CLI can project costs for any period (days, weeks, months)

## Configuration

### Worker (.env or env vars)
```
PROXMOX_HOST=<target-ip>                      # Target server
JUMP_HOST=<jump-ip>                           # Optional: bastion host
JUMP_USER=ubuntu                              # Jump host SSH user
REMOTE_USER=root                              # Target SSH user
DB_PATH=/var/lib/proxmox-power-monitor/data.db
CONTROL_PANEL_URL=ws://<control-panel>:8765/worker
```

### Control Panel (env vars)
```
PYTHONUNBUFFERED=1
```

## CLI Usage

```bash
# Install service
python3 cli.py install
python3 cli.py install --control-panel=ws://<control-panel>:8765/worker

# Manage service
python3 cli.py start
python3 cli.py stop
python3 cli.py status

# View stats
python3 cli.py stats --total
python3 cli.py stats --daily=7
python3 cli.py stats --hourly=24
python3 cli.py stats --recent=60

# Cost projection
python3 cli.py project 14    # Project 14 days

# Cleanup old data
python3 cli.py cleanup --days=90

# Uninstall
python3 cli.py uninstall
```

## WebSocket Protocol

### Worker → Control Panel
- **register**: `{"type":"register","worker_id":"...","hostname":"...","version":"1.0.0","capabilities":["metrics","projection"]}`
- **metrics**: `{"type":"metrics","worker_id":"...","timestamp":...,"data":{...}}`
- **heartbeat**: Every 30 seconds

### Control Panel → Worker
- **ack**: Acknowledgment of received data
- **config**: Configuration updates
- **reconnect**: Reconnection request

## Security

- **Token-based Authentication**: Simple token for WebSocket connections
- **TLS Support**: Use WSS for production deployments
- **Input Validation**: All incoming data validated
- **Worker Isolation**: Each worker can only access its own data
- **No secrets in codebase**: All IPs/credentials loaded via `.env` (gitignored)
