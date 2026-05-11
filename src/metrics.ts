interface SystemMetrics {
  cpuUsage: number; // percentage 0-100
  ramUsage: number; // percentage 0-100
  ramUsedGB: number;
  ramTotalGB: number;
  uptime: number; // seconds
  timestamp: number;
}

export async function collectMetrics(): Promise<SystemMetrics> {
  const now = Date.now();
  
  // Read CPU stats from /proc/stat
  const cpuStats = await Bun.file('/proc/stat').text();
  const cpuLines = cpuStats.split('\n')[0].split(/\s+/);
  const idle = parseInt(cpuLines[4]);
  const total = cpuLines.slice(1).reduce((sum, val) => sum + parseInt(val), 0);
  const cpuUsage = ((total - idle) / total) * 100;
  
  // Read memory stats from /proc/meminfo
  const memStats = await Bun.file('/proc/meminfo').text();
  const memLines = memStats.split('\n');
  const memTotal = parseInt(memLines[0].split(/\s+/)[1]); // in KB
  const memAvailable = parseInt(memLines[2].split(/\s+/)[1]); // in KB
  const memUsed = memTotal - memAvailable;
  const ramUsage = (memUsed / memTotal) * 100;
  const ramUsedGB = memUsed / 1024 / 1024;
  const ramTotalGB = memTotal / 1024 / 1024;
  
  // Read uptime from /proc/uptime
  const uptimeContent = await Bun.file('/proc/uptime').text();
  const uptime = parseFloat(uptimeContent.split(' ')[0]);
  
  return {
    cpuUsage: Math.round(cpuUsage * 100) / 100,
    ramUsage: Math.round(ramUsage * 100) / 100,
    ramUsedGB: Math.round(ramUsedGB * 100) / 100,
    ramTotalGB: Math.round(ramTotalGB * 100) / 100,
    uptime: Math.round(uptime),
    timestamp: now
  };
}
