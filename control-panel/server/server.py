#!/usr/bin/env python3
"""
PowerSentry Control Panel Server
WebSocket server for receiving metrics from worker agents
HTTP server for serving web UI
"""

import asyncio
import websockets
import json
import sqlite3
import logging
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import os
import signal
import sys

# Configuration
WS_HOST = "0.0.0.0"
WS_PORT = 8765
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8083
DB_PATH = os.environ.get('DB_PATH', os.path.expanduser('~/.local/share/powersentry/control-panel.db'))
UI_DIR = os.environ.get('UI_DIR', os.path.expanduser('~/powersentry/ui'))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PowerSentryDatabase:
    """Central database for control panel"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database schema"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Workers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL,
                ip_address TEXT,
                last_seen REAL,
                status TEXT DEFAULT 'offline',
                version TEXT,
                registered_at REAL,
                capabilities TEXT
            )
        ''')
        
        # Metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
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
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_metrics_worker_timestamp 
            ON metrics(worker_id, timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
            ON metrics(timestamp)
        ''')
        
        conn.commit()
        conn.close()
    
    def register_worker(self, worker_id: str, hostname: str, ip_address: str, 
                       version: str, capabilities: list):
        """Register or update a worker"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().timestamp()
        
        cursor.execute('''
            INSERT OR REPLACE INTO workers 
            (id, hostname, ip_address, last_seen, status, registered_at, version, capabilities)
            VALUES (?, ?, ?, ?, 'online', COALESCE((SELECT registered_at FROM workers WHERE id = ?), ?), ?, ?)
        ''', (worker_id, hostname, ip_address, now, worker_id, now, version, json.dumps(capabilities)))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Worker registered: {worker_id} ({hostname})")
    
    def update_worker_heartbeat(self, worker_id: str):
        """Update worker last seen timestamp"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().timestamp()
        cursor.execute('''
            UPDATE workers SET last_seen = ?, status = 'online' WHERE id = ?
        ''', (now, worker_id))
        
        conn.commit()
        conn.close()
    
    def store_metrics(self, worker_id: str, metrics_data: dict):
        """Store metrics from worker"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO metrics (
                worker_id, timestamp, cpuUsage, ramUsage, ramUsedGB, ramTotalGB,
                uptime, powerWatts, pricePerKWh, pricePeriod, cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            worker_id,
            metrics_data.get('timestamp'),
            metrics_data.get('cpuUsage'),
            metrics_data.get('ramUsage'),
            metrics_data.get('ramUsedGB'),
            metrics_data.get('ramTotalGB'),
            metrics_data.get('uptime'),
            metrics_data.get('powerWatts'),
            metrics_data.get('pricePerKWh'),
            metrics_data.get('pricePeriod'),
            metrics_data.get('cost')
        ))
        
        conn.commit()
        conn.close()
    
    def get_workers(self):
        """Get all workers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, hostname, ip_address, last_seen, status, version, capabilities FROM workers')
        workers = []
        for row in cursor.fetchall():
            workers.append({
                'id': row[0],
                'hostname': row[1],
                'ip_address': row[2],
                'last_seen': row[3],
                'status': row[4],
                'version': row[5],
                'capabilities': json.loads(row[6]) if row[6] else []
            })
        
        conn.close()
        return workers
    
    def get_worker_metrics(self, worker_id: str, limit: int = 60):
        """Get recent metrics for a worker"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, cpuUsage, ramUsage, ramUsedGB, ramTotalGB,
                   uptime, powerWatts, pricePerKWh, pricePeriod, cost
            FROM metrics WHERE worker_id = ?
            ORDER BY timestamp DESC LIMIT ?
        ''', (worker_id, limit))
        
        metrics = []
        for row in cursor.fetchall():
            metrics.append({
                'timestamp': row[0],
                'cpuUsage': row[1],
                'ramUsage': row[2],
                'ramUsedGB': row[3],
                'ramTotalGB': row[4],
                'uptime': row[5],
                'powerWatts': row[6],
                'pricePerKWh': row[7],
                'pricePeriod': row[8],
                'cost': row[9]
            })
        
        conn.close()
        return metrics

class PowerSentryWebSocketServer:
    """WebSocket server for worker communication"""
    
    def __init__(self, db: PowerSentryDatabase):
        self.db = db
        self.connected_workers = {}
    
    async def handle_worker(self, websocket, path):
        """Handle worker connection"""
        worker_id = None
        
        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'register':
                    worker_id = data.get('worker_id')
                    hostname = data.get('hostname')
                    ip_address = websocket.remote_address[0] if websocket.remote_address else None
                    version = data.get('version')
                    capabilities = data.get('capabilities', [])
                    
                    self.db.register_worker(worker_id, hostname, ip_address, version, capabilities)
                    self.connected_workers[worker_id] = websocket
                    
                    response = {
                        "type": "ack",
                        "status": "success",
                        "message": "Registered successfully"
                    }
                    await websocket.send(json.dumps(response))
                
                elif msg_type == 'metrics':
                    worker_id = data.get('worker_id')
                    metrics_data = data.get('data', {})
                    
                    self.db.update_worker_heartbeat(worker_id)
                    self.db.store_metrics(worker_id, metrics_data)
                    
                    response = {
                        "type": "ack",
                        "status": "success"
                    }
                    await websocket.send(json.dumps(response))
                
                elif msg_type == 'heartbeat':
                    worker_id = data.get('worker_id')
                    self.db.update_worker_heartbeat(worker_id)
                    
                    response = {
                        "type": "ack",
                        "status": "success"
                    }
                    await websocket.send(json.dumps(response))
                
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Worker disconnected: {worker_id}")
        except Exception as e:
            logger.error(f"Error handling worker: {e}")
        finally:
            if worker_id and worker_id in self.connected_workers:
                del self.connected_workers[worker_id]
                # Mark worker as offline
                conn = sqlite3.connect(self.db.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE workers SET status = 'offline' WHERE id = ?", (worker_id,))
                conn.commit()
                conn.close()

class HTTPHandler(SimpleHTTPRequestHandler):
    """HTTP handler for serving UI and API endpoints"""

    # Global reference to database (set in main)
    db = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/api/workers':
            self.send_api_workers()
        elif self.path.startswith('/api/workers/') and '/metrics' in self.path:
            # Extract worker ID from path: /api/workers/{worker_id}/metrics
            parts = self.path.split('/')
            if len(parts) >= 5:
                worker_id = parts[3]
                self.send_api_worker_metrics(worker_id)
            else:
                self.send_error(400, "Invalid worker ID")
        elif self.path.startswith('/api/'):
            self.send_error(404, "API endpoint not found")
        else:
            # Serve static files
            super().do_GET()

    def send_api_workers(self):
        """Send workers data as JSON"""
        if not self.db:
            self.send_error(500, "Database not initialized")
            return

        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            # Get all workers
            cursor.execute("SELECT * FROM workers")
            workers = cursor.fetchall()

            # Convert to list of dicts
            columns = ['id', 'hostname', 'ip_address', 'last_seen', 'status', 'version', 'registered_at', 'capabilities']
            workers_data = []
            for worker in workers:
                worker_dict = dict(zip(columns, worker))
                workers_data.append(worker_dict)

            conn.close()

            # Send JSON response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(workers_data).encode())
        except Exception as e:
            logger.error(f"Error serving /api/workers: {e}")
            self.send_error(500, str(e))

    def send_api_worker_metrics(self, worker_id):
        """Send worker metrics as JSON"""
        if not self.db:
            self.send_error(500, "Database not initialized")
            return

        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            # Get recent metrics for this worker (last 100 readings)
            cursor.execute(
                "SELECT * FROM metrics WHERE worker_id = ? ORDER BY timestamp DESC LIMIT 100",
                (worker_id,)
            )
            metrics = cursor.fetchall()

            # Convert to list of dicts
            columns = ['id', 'worker_id', 'timestamp', 'cpu_usage', 'ram_usage', 'ram_used_gb', 'ram_total_gb', 'uptime', 'power_watts', 'price_per_kwh', 'price_period', 'cost']
            metrics_data = []
            for metric in metrics:
                metric_dict = dict(zip(columns, metric))
                metrics_data.append(metric_dict)

            conn.close()

            # Send JSON response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(metrics_data).encode())
        except Exception as e:
            logger.error(f"Error serving /api/workers/{worker_id}/metrics: {e}")
            self.send_error(500, str(e))

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def run_http_server():
    """Run HTTP server in separate thread"""
    os.makedirs(UI_DIR, exist_ok=True)
    
    server = HTTPServer((HTTP_HOST, HTTP_PORT), HTTPHandler)
    logger.info(f"HTTP server running on http://{HTTP_HOST}:{HTTP_PORT}")
    server.serve_forever()

async def run_websocket_server(db: PowerSentryDatabase):
    """Run WebSocket server"""
    ws_server = PowerSentryWebSocketServer(db)
    
    logger.info(f"WebSocket server running on ws://{WS_HOST}:{WS_PORT}")
    
    async with websockets.serve(ws_server.handle_worker, WS_HOST, WS_PORT):
        await asyncio.Future()  # Run forever

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Shutting down PowerSentry Control Panel...")
    sys.exit(0)

def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize database
    db = PowerSentryDatabase()

    # Set database reference for HTTP handler
    HTTPHandler.db = db

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # Start WebSocket server
    asyncio.run(run_websocket_server(db))

if __name__ == '__main__':
    main()
