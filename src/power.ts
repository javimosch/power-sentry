import { SystemMetrics } from './metrics.js';

interface PowerConfig {
  cpuTDP: number; // CPU Thermal Design Power in watts
  basePower: number; // Base system power (motherboard, disks, etc.) in watts
  cpuPowerEfficiency: number; // How much CPU usage affects power (0-1)
  ramPowerPerGB: number; // Power per GB of RAM in watts
}

const DEFAULT_CONFIG: PowerConfig = {
  cpuTDP: 65, // Typical server CPU TDP
  basePower: 30, // Base power for motherboard, disks, etc.
  cpuPowerEfficiency: 0.8, // 80% of TDP at 100% usage
  ramPowerPerGB: 0.5 // Approx 0.5W per GB of RAM
};

export function calculatePower(metrics: SystemMetrics, config: PowerConfig = DEFAULT_CONFIG): number {
  // CPU power: base + (TDP * efficiency * usage percentage)
  const cpuPower = config.cpuTDP * config.cpuPowerEfficiency * (metrics.cpuUsage / 100);
  
  // RAM power: watts per GB * used GB
  const ramPower = config.ramPowerPerGB * metrics.ramUsedGB;
  
  // Total power: base + cpu + ram
  const totalPower = config.basePower + cpuPower + ramPower;
  
  return Math.round(totalPower * 100) / 100;
}

export function calculateEnergyCost(powerWatts: number, durationSeconds: number, pricePerKWh: number): number {
  // Energy in kWh = (watts * hours) / 1000
  const hours = durationSeconds / 3600;
  const energyKWh = (powerWatts * hours) / 1000;
  
  // Cost = energy * price
  const cost = energyKWh * pricePerKWh;
  
  return Math.round(cost * 10000) / 10000;
}
