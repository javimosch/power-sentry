# ⚡ PowerSentry

**Infrastructure Power Monitoring & Cost Optimization**

PowerSentry is a distributed power monitoring system that tracks energy consumption and electricity costs for infrastructure servers. It features a centralized web dashboard with real-time monitoring, cost projections, and multi-server support.

## 🌟 Features

- **Real-time Power Monitoring**: Track CPU, RAM, and power consumption every minute
- **Cost Projection**: Estimate costs for any time period (days, weeks, months, years)
- **Centralized Dashboard**: Web UI to monitor multiple servers from one location
- **French Electricity Pricing**: Built-in support for EDF Tarif Bleu with peak/off-peak hours
- **WebSocket Architecture**: Efficient real-time communication between workers and control panel
- **Historical Analysis**: SQLite-based data storage with hourly/daily aggregation
- **Cost Simulation**: Project costs even with limited runtime data
- **Standalone or Distributed**: Use as a single-server monitor or as part of a multi-server fleet

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│              PowerSentry Control Panel                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ WebSocket    │  │ HTTP Server  │  │  Database    │ │
│  │   Server     │  │   (Web UI)   │  │  (Central)   │ │
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

## 📦 Components

### 1. Control Panel
- **WebSocket Server**: Receives real-time metrics from worker agents
- **HTTP Server**: Serves web UI and API endpoints
- **Central Database**: Stores all worker data and historical records
- **Web UI**: Vue 3 + Tailwind + DaisyUI dashboard

### 2. Worker Agents
- **Enhanced Daemon**: Modified to connect to control panel via WebSocket
- **Local Database**: Maintains local copy as backup
- **Metrics Collector**: Collects system metrics every minute
- **WebSocket Client**: Sends real-time data to control panel

## 🚀 Quick Start

### Option 1: Standalone Mode (Single Server)

Deploy on a single server without the control panel:

```bash
# Deploy worker agent
cd proxmox-power-monitor
./deploy.sh <server-ip>

# SSH to server and install
ssh root@<server-ip>
cd /opt/proxmox-power-monitor
python3 cli.py install
python3 cli.py start

# Check stats
python3 cli.py stats --total
python3 cli.py project 14  # Project 14 days
```

### Option 2: Distributed Mode (Multi-Server)

Deploy control panel and multiple worker agents:

#### Step 1: Deploy Control Panel

```bash
# Deploy to control panel server (or your preferred server)
cd proxmox-power-monitor
./deploy-control-panel.sh <dk1-host>

# SSH to control panel server and start service
ssh root@<dk1-host>
systemctl start powersency-control-panel
systemctl status powersency-control-panel

# Access web UI
# http://<dk1-host>:8080
```

#### Step 2: Deploy Worker Agents

```bash
# Deploy worker to Proxmox host (via jump host if needed)
cd proxmox-power-monitor
./deploy.sh <proxmox-host> [jump-host]    # jump-host is optional for direct access

# SSH to worker and install with control panel URL
ssh -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519 -J ubuntu@<jump-host> root@<proxmox-host>
cd /opt/proxmox-power-monitor
python3 cli.py install --control-panel=ws://<dk1-host>:8765/worker
python3 cli.py start
```

## 📊 Usage Examples

### Worker Agent Commands

```bash
# Install service (standalone)
python3 cli.py install

# Install service (with control panel)
python3 cli.py install --control-panel=ws://<control-panel>:8765/worker

# Start/Stop daemon
python3 cli.py start
python3 cli.py stop

# Check service status
python3 cli.py status

# View statistics
python3 cli.py stats --total
python3 cli.py stats --daily=7
python3 cli.py stats --hourly=24
python3 cli.py stats --recent=60

# Cost projection
python3 cli.py project 14   # 14 days
python3 cli.py project 30   # 30 days
python3 cli.py project 365  # 1 year

# Cleanup old data
python3 cli.py cleanup --days=90

# Uninstall service
python3 cli.py uninstall
```

### Control Panel Commands

```bash
# Start control panel
systemctl start powersency-control-panel

# Stop control panel
systemctl stop powersency-control-panel

# Check status
systemctl status powersency-control-panel

# View logs
journalctl -u powersency-control-panel -f
```

## 🔧 Configuration

### Power Model

Edit `power.py` to adjust the power calculation model:

```python
DEFAULT_CONFIG = PowerConfig(
    cpu_tdp=65,        # CPU Thermal Design Power in watts
    base_power=30,     # Base system power (motherboard, disks, etc.)
    cpu_power_efficiency=0.8,  # How much CPU usage affects power (0-1)
    ram_power_per_gb=0.5 # Power per GB of RAM in watts
)
```

### French Pricing

Edit `pricing.py` to adjust electricity rates:

```python
class FrenchPricing:
    peak_price: float = 0.2795      # € per kWh during peak hours
    off_peak_price: float = 0.2068   # € per kWh during off-peak hours
    peak_hours_start: int = 22       # 22h
    peak_hours_end: int = 6          # 6h next day
```

### Environment Variables

```bash
# Worker Agent
DB_PATH=/var/lib/proxmox-power-monitor/data.db
CONTROL_PANEL_URL=ws://control-panel:8765/worker

# Control Panel
PYTHONUNBUFFERED=1
```

## 📈 Cost Projection

PowerSentry can project costs for any time period, even with limited runtime data:

### Example Output

```json
{
  "type": "projected",
  "period_days": 14,
  "totalCost": 0.35,
  "totalCostFormatted": "€0.35",
  "avgDailyCost": 0.025,
  "avgDailyCostFormatted": "€0.03/day",
  "avgHourlyCost": 0.001,
  "avgHourlyCostFormatted": "€0.001/hour",
  "totalEnergy": 10.94,
  "avgPower": 32.56,
  "peakCost": 0.16,
  "offPeakCost": 0.24,
  "confidence": "low",
  "method": "hourly_extrapolation"
}
```

### Confidence Levels

- **High**: Actual data available for the requested period
- **Medium**: Hourly patterns available with reasonable coverage
- **Low**: Limited data, using extrapolation based on current patterns

## 🌐 Web Dashboard

Access the PowerSentry web dashboard at `http://control-panel-host:8080`

### Features

- **Real-time Monitoring**: Live power consumption for all connected workers
- **Worker Status**: Online/offline status and connection information
- **Cost Overview**: Total power, daily cost, and efficiency metrics
- **Detailed Views**: Per-worker metrics with historical charts
- **Cost Projections**: Quick access to cost projections for different time periods

## 🔒 Security

- **Token-based Authentication**: Simple token-based WebSocket authentication (configurable)
- **TLS Support**: Use WSS for production deployments
- **Input Validation**: All incoming data is validated
- **Worker Isolation**: Each worker can only access its own data

## 🛠️ Troubleshooting

### Worker Agent Issues

**Service won't start:**
```bash
journalctl -u powersentry-worker -f
systemctl status powersentry-worker
```

**Can't connect to control panel:**
```bash
# Check control panel is running
systemctl status powersency-control-panel

# Check network connectivity
ping <control-panel-host>
telnet <control-panel-host> 8765

# Check firewall rules
iptables -L
```

**Database errors:**
```bash
# Check database file permissions
ls -la /var/lib/proxmox-power-monitor/

# Reinitialize database (WARNING: deletes all data)
rm /var/lib/proxmox-power-monitor/data.db
systemctl restart powersentry-worker
```

### Control Panel Issues

**Web UI not accessible:**
```bash
# Check HTTP server is running
netstat -tlnp | grep 8080

# Check service status
systemctl status powersency-control-panel

# Check logs
journalctl -u powersency-control-panel -f
```

**Workers not connecting:**
```bash
# Check WebSocket server is running
netstat -tlnp | grep 8765

# Check worker logs
journalctl -u powersentry-worker -f

# Test WebSocket connection
wscat -c ws://control-panel:8765/worker
```

## 📊 Data Storage

### Worker Agent
- **Location**: `/var/lib/proxmox-power-monitor/data.db`
- **Tables**: `metrics`, `hourly_stats`, `daily_stats`
- **Retention**: Configurable (default: 30 days)

### Control Panel
- **Location**: `/var/lib/powersentry/control-panel.db`
- **Tables**: `workers`, `metrics`, `projections`
- **Retention**: Configurable

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- **Vue 3**: Progressive JavaScript framework
- **Tailwind CSS**: Utility-first CSS framework
- **DaisyUI**: Component library for Tailwind CSS
- **Chart.js**: Simple yet flexible JavaScript charting library

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation in `/docs`
- Review architecture in `ARCHITECTURE.md`

---

**PowerSentry** - Monitor. Optimize. Save. ⚡
