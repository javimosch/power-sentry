# PowerSentry Architecture

## Overview

PowerSentry uses a centralized control panel with distributed worker agents communicating via WebSocket.

## Components

### 1. Control Panel
- **WebSocket Server**: Receives real-time metrics from worker agents
- **HTTP Server**: Serves web UI and API endpoints
- **Central Database**: Stores all worker data and historical records
- **Web UI**: Vue 3 + Tailwind + DaisyUI dashboard

### 2. Worker Agents (e.g., Proxmox host)
- **Enhanced Daemon**: Modified to connect to control panel via WebSocket
- **Local Database**: Maintains local copy as backup
- **Metrics Collector**: Collects system metrics every minute
- **WebSocket Client**: Sends real-time data to control panel

## WebSocket Protocol

### Connection
- **URL**: `ws://<control-panel-host>:8765/worker`
- **Authentication**: Simple token-based (configurable)
- **Heartbeat**: Every 30 seconds

### Messages

#### Worker → Control Panel

**Registration**
```json
{
  "type": "register",
  "worker_id": "proxmox-pve-001",
  "hostname": "pve1.example.com",
  "version": "1.0.0",
  "capabilities": ["metrics", "projection"]
}
```

**Metrics Update**
```json
{
  "type": "metrics",
  "worker_id": "proxmox-pve-001",
  "timestamp": 1715270400,
  "data": {
    "cpuUsage": 5.2,
    "ramUsage": 45.1,
    "ramUsedGB": 3.5,
    "ramTotalGB": 7.8,
    "uptime": 123456,
    "powerWatts": 33.5,
    "pricePerKWh": 0.2068,
    "pricePeriod": "off-peak",
    "cost": 0.0001
  }
}
```

**Heartbeat**
```json
{
  "type": "heartbeat",
  "worker_id": "proxmox-pve-001",
  "timestamp": 1715270430
}
```

#### Control Panel → Worker

**Acknowledgment**
```json
{
  "type": "ack",
  "message_id": "msg-123",
  "status": "success"
}
```

**Configuration Update**
```json
{
  "type": "config",
  "collection_interval": 60,
  "enable_projection": true
}
```

**Reconnect Request**
```json
{
  "type": "reconnect",
  "delay": 5000
}
```

## Data Flow

1. **Worker Registration**: Worker connects and registers with control panel
2. **Metrics Collection**: Worker collects local system metrics
3. **Real-time Sync**: Worker sends metrics via WebSocket every minute
4. **Central Storage**: Control panel stores metrics in central database
5. **UI Updates**: Web UI receives updates via WebSocket or polling
6. **Historical Analysis**: Control panel runs projections and analytics

## Database Schema

### Workers Table
```sql
CREATE TABLE workers (
  id TEXT PRIMARY KEY,
  hostname TEXT NOT NULL,
  ip_address TEXT,
  last_seen TIMESTAMP,
  status TEXT DEFAULT 'online',
  version TEXT,
  registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Metrics Table (Central)
```sql
CREATE TABLE metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  worker_id TEXT NOT NULL,
  timestamp REAL NOT NULL,
  cpuUsage REAL,
  ramUsage REAL,
  ramUsedGB REAL,
  ramTotalGB REAL,
  uptime REAL,
  powerWatts REAL,
  pricePerKWh REAL,
  pricePeriod TEXT,
  cost REAL,
  FOREIGN KEY (worker_id) REFERENCES workers(id)
);
```

### Projections Table
```sql
CREATE TABLE projections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  worker_id TEXT NOT NULL,
  period_days INTEGER,
  totalCost REAL,
  totalEnergy REAL,
  avgPower REAL,
  confidence TEXT,
  calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (worker_id) REFERENCES workers(id)
);
```

## Security Considerations

1. **Authentication**: Token-based authentication for WebSocket connections
2. **TLS**: Use WSS for production deployments
3. **Rate Limiting**: Prevent message flooding from workers
4. **Input Validation**: Validate all incoming data
5. **Worker Isolation**: Each worker can only access its own data

## Scalability

- **Horizontal Scaling**: Multiple control panel instances with load balancer
- **Database Sharding**: Separate databases per worker group
- **Message Queue**: Use Redis/RabbitMQ for high-volume deployments
- **CDN**: Serve static UI assets via CDN

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Control Panel                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ WebSocket    │  │ HTTP Server  │  │  Database    │ │
│  │   Server     │  │   (UI/API)   │  │  (SQLite)    │ │
│  │   :8765      │  │   :8080      │  │              │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │ WebSocket
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌───────▼────────┐  ┌──────▼─────────┐
│ Worker Agent 1  │  │ Worker Agent 2  │  │ Worker Agent N │
│  (Proxmox host) │  │   (Other VM)   │  │   (Other VM)   │
│  Daemon + WS    │  │  Daemon + WS   │  │  Daemon + WS   │
└─────────────────┘  └─────────────────┘  └────────────────┘
```

## Failure Handling

1. **Worker Disconnect**: Control panel marks worker as offline after 2 missed heartbeats
2. **Control Panel Down**: Workers buffer data locally and reconnect when available
3. **Network Issues**: Exponential backoff for reconnection attempts
4. **Data Loss**: Workers maintain local database as backup
