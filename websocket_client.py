#!/usr/bin/env python3
"""
WebSocket client for PowerSentry worker agents
Connects to control panel and sends metrics
"""

import asyncio
import websockets
import json
import socket
import logging
from typing import Optional, Callable
import os

logger = logging.getLogger(__name__)

class PowerSentryWebSocketClient:
    """WebSocket client for sending metrics to control panel"""
    
    def __init__(self, control_panel_url: str, worker_id: str, hostname: str):
        self.control_panel_url = control_panel_url
        self.worker_id = worker_id
        self.hostname = hostname
        self.websocket = None
        self.connected = False
        self.reconnect_delay = 5
        self.max_reconnect_delay = 300
        self.metrics_callback: Optional[Callable] = None
    
    async def connect(self):
        """Connect to control panel"""
        while True:
            try:
                logger.info(f"Connecting to control panel: {self.control_panel_url}")
                self.websocket = await websockets.connect(self.control_panel_url)
                self.connected = True
                self.reconnect_delay = 5  # Reset delay on successful connection
                
                # Register worker
                await self.register()
                
                # Start message handler
                await self.handle_messages()
                
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                self.connected = False
                await asyncio.sleep(self.reconnect_delay)
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    async def register(self):
        """Register this worker with control panel"""
        registration = {
            "type": "register",
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "version": "1.0.0",
            "capabilities": ["metrics", "projection"]
        }
        
        await self.websocket.send(json.dumps(registration))
        logger.info(f"Registered worker: {self.worker_id}")
    
    async def send_metrics(self, metrics_data: dict):
        """Send metrics to control panel"""
        if not self.connected or not self.websocket:
            return
        
        try:
            message = {
                "type": "metrics",
                "worker_id": self.worker_id,
                "data": metrics_data
            }
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send metrics: {e}")
            self.connected = False
    
    async def send_heartbeat(self):
        """Send heartbeat to control panel"""
        if not self.connected or not self.websocket:
            return
        
        try:
            import time
            message = {
                "type": "heartbeat",
                "worker_id": self.worker_id,
                "timestamp": time.time()
            }
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            self.connected = False
    
    async def handle_messages(self):
        """Handle incoming messages from control panel"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'ack':
                    logger.debug("Received acknowledgment")
                elif msg_type == 'config':
                    logger.info(f"Received config update: {data}")
                elif msg_type == 'reconnect':
                    delay = data.get('delay', 5)
                    logger.info(f"Reconnect requested, delay: {delay}s")
                    await asyncio.sleep(delay)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
            self.connected = False
        except Exception as e:
            logger.error(f"Error handling messages: {e}")
            self.connected = False
    
    async def start_heartbeat_loop(self):
        """Start periodic heartbeat"""
        while True:
            await asyncio.sleep(30)  # Heartbeat every 30 seconds
            await self.send_heartbeat()

def get_worker_id() -> str:
    """Generate or retrieve worker ID"""
    # Try to get from file
    worker_id_file = "/var/lib/proxmox-power-monitor/worker_id"
    if os.path.exists(worker_id_file):
        with open(worker_id_file, 'r') as f:
            return f.read().strip()
    
    # Generate new ID
    import uuid
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    
    # Save to file
    os.makedirs(os.path.dirname(worker_id_file), exist_ok=True)
    with open(worker_id_file, 'w') as f:
        f.write(worker_id)
    
    return worker_id

def get_hostname() -> str:
    """Get system hostname"""
    return socket.gethostname()
