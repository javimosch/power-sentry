#!/usr/bin/env python3
import signal
import sys
import time
import os
import asyncio
import threading

# Unbuffer stdout for systemd logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from metrics import collect_metrics
from power import calculate_power
from database import PowerDatabase

COLLECTION_INTERVAL = 60  # 1 minute in seconds
DB_PATH = os.environ.get('DB_PATH', '/var/lib/proxmox-power-monitor/data.db')
CONTROL_PANEL_URL = os.environ.get('CONTROL_PANEL_URL', '')

running = True
db = None
ws_client = None

# Import websocket_client only if control panel URL is set
if CONTROL_PANEL_URL:
    try:
        from websocket_client import PowerSentryWebSocketClient, get_worker_id, get_hostname
        WEBSOCKET_AVAILABLE = True
    except ImportError:
        print('Warning: websockets module not found, running in standalone mode')
        WEBSOCKET_AVAILABLE = False
else:
    WEBSOCKET_AVAILABLE = False

def cleanup(signum=None, frame=None):
    """Cleanup function for graceful shutdown."""
    global running
    print('Shutting down daemon...')
    running = False
    if db:
        db.close()
    sys.exit(0)

def run_websocket_client():
    """Run WebSocket client in background thread"""
    global ws_client

    if not WEBSOCKET_AVAILABLE:
        print('WebSocket client not available, skipping')
        return

    worker_id = get_worker_id()
    hostname = get_hostname()

    ws_client = PowerSentryWebSocketClient(CONTROL_PANEL_URL, worker_id, hostname)

    # Run async event loop in this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(asyncio.gather(
            ws_client.connect(),
            ws_client.start_heartbeat_loop()
        ))
    except Exception as e:
        print(f'WebSocket client error: {e}')
    finally:
        loop.close()

def main():
    global db, running, ws_client

    # Handle shutdown signals
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Initialize database
    try:
        db = PowerDatabase(DB_PATH)
        print('PowerSentry daemon started')
        print(f'Collection interval: {COLLECTION_INTERVAL}s')
        print(f'Database: {DB_PATH}')
        if CONTROL_PANEL_URL:
            print(f'Control Panel: {CONTROL_PANEL_URL}')
            print(f'Mode: Connected to control panel' if WEBSOCKET_AVAILABLE else 'Mode: Standalone (websockets unavailable)')
        else:
            print('Mode: Standalone (no control panel configured)')
    except Exception as e:
        print(f'Failed to initialize database: {e}')
        sys.exit(1)

    # Start WebSocket client in background thread if available
    if WEBSOCKET_AVAILABLE:
        try:
            ws_thread = threading.Thread(target=run_websocket_client, daemon=True)
            ws_thread.start()
            print('WebSocket client started')
        except Exception as e:
            print(f'Failed to start WebSocket client: {e}')
            print('Continuing without control panel connection...')

    # Main collection loop
    while running:
        try:
            metrics = collect_metrics()
            power = calculate_power(metrics)

            print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Collected: CPU: {metrics.cpu_usage}%, RAM: {metrics.ram_usage}%, Power: {power}W')

            # Store in local database
            db.insert_metrics(metrics, power)
            print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Inserted into database')

            # Send to control panel if connected
            if ws_client and ws_client.connected:
                from pricing import get_current_price, get_price_period
                from power import calculate_energy_cost

                price_per_kwh = get_current_price(metrics.timestamp)
                price_period = get_price_period(metrics.timestamp)
                cost = calculate_energy_cost(power, 60, price_per_kwh)  # 1 minute

                metrics_data = {
                    'timestamp': metrics.timestamp,
                    'cpuUsage': metrics.cpu_usage,
                    'ramUsage': metrics.ram_usage,
                    'ramUsedGB': metrics.ram_used_gb,
                    'ramTotalGB': metrics.ram_total_gb,
                    'uptime': metrics.uptime,
                    'powerWatts': power,
                    'pricePerKWh': price_per_kwh,
                    'pricePeriod': price_period,
                    'cost': cost
                }

                # Use asyncio to send metrics
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(ws_client.send_metrics(metrics_data))
                    loop.close()
                    print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Sent to control panel')
                except Exception as e:
                    print(f'Failed to send to control panel: {e}')

        except Exception as e:
            import traceback
            print(f'Error collecting metrics: {e}')
            traceback.print_exc()

        # Wait for next collection
        time.sleep(COLLECTION_INTERVAL)

if __name__ == '__main__':
    main()
