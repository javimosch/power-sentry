#!/usr/bin/env python3
import time
from dataclasses import dataclass
from typing import Optional

@dataclass
class SystemMetrics:
    cpu_usage: float  # percentage 0-100
    ram_usage: float  # percentage 0-100
    ram_used_gb: float
    ram_total_gb: float
    uptime: float  # seconds
    timestamp: float

def collect_metrics() -> SystemMetrics:
    """Collect system metrics from /proc files."""
    now = time.time()
    
    # Read CPU stats from /proc/stat
    with open('/proc/stat', 'r') as f:
        cpu_line = f.readline().split()
    idle = int(cpu_line[4])
    total = sum(int(x) for x in cpu_line[1:])
    cpu_usage = ((total - idle) / total) * 100 if total > 0 else 0
    
    # Read memory stats from /proc/meminfo
    mem_stats = {}
    with open('/proc/meminfo', 'r') as f:
        for line in f:
            if line.startswith(('MemTotal:', 'MemAvailable:')):
                parts = line.split()
                mem_stats[parts[0].rstrip(':')] = int(parts[1])
    
    mem_total_kb = mem_stats.get('MemTotal', 0)
    mem_available_kb = mem_stats.get('MemAvailable', 0)
    mem_used_kb = mem_total_kb - mem_available_kb
    ram_usage = (mem_used_kb / mem_total_kb * 100) if mem_total_kb > 0 else 0
    ram_used_gb = mem_used_kb / 1024 / 1024
    ram_total_gb = mem_total_kb / 1024 / 1024
    
    # Read uptime from /proc/uptime
    with open('/proc/uptime', 'r') as f:
        uptime = float(f.read().split()[0])
    
    return SystemMetrics(
        cpu_usage=round(cpu_usage, 2),
        ram_usage=round(ram_usage, 2),
        ram_used_gb=round(ram_used_gb, 2),
        ram_total_gb=round(ram_total_gb, 2),
        uptime=round(uptime),
        timestamp=now
    )
