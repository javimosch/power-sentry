#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Optional
from metrics import SystemMetrics

@dataclass
class PowerConfig:
    cpu_tdp: float  # CPU Thermal Design Power in watts
    base_power: float  # Base system power (motherboard, disks, etc.) in watts
    cpu_power_efficiency: float  # How much CPU usage affects power (0-1)
    ram_power_per_gb: float  # Power per GB of RAM in watts

DEFAULT_CONFIG = PowerConfig(
    cpu_tdp=65,  # Typical server CPU TDP
    base_power=30,  # Base power for motherboard, disks, etc.
    cpu_power_efficiency=0.8,  # 80% of TDP at 100% usage
    ram_power_per_gb=0.5  # Approx 0.5W per GB of RAM
)

def calculate_power(metrics: SystemMetrics, config: PowerConfig = DEFAULT_CONFIG) -> float:
    """Calculate power consumption based on system metrics."""
    # CPU power: base + (TDP * efficiency * usage percentage)
    cpu_power = config.cpu_tdp * config.cpu_power_efficiency * (metrics.cpu_usage / 100)
    
    # RAM power: watts per GB * used GB
    ram_power = config.ram_power_per_gb * metrics.ram_used_gb
    
    # Total power: base + cpu + ram
    total_power = config.base_power + cpu_power + ram_power
    
    return round(total_power, 2)

def calculate_energy_cost(power_watts: float, duration_seconds: float, price_per_kwh: float) -> float:
    """Calculate energy cost from power consumption."""
    # Energy in kWh = (watts * hours) / 1000
    hours = duration_seconds / 3600
    energy_kwh = (power_watts * hours) / 1000
    
    # Cost = energy * price
    cost = energy_kwh * price_per_kwh
    
    return round(cost, 4)
