import Database from 'better-sqlite3';
import { SystemMetrics } from './metrics.js';
import { calculatePower, calculateEnergyCost } from './power.js';
import { getCurrentPrice, getPricePeriod } from './pricing.js';

const DB_PATH = '/var/lib/proxmox-power-monitor/data.db';

interface MetricRecord {
  timestamp: number;
  cpuUsage: number;
  ramUsage: number;
  ramUsedGB: number;
  ramTotalGB: number;
  uptime: number;
  powerWatts: number;
  pricePerKWh: number;
  pricePeriod: string;
  cost: number;
}

interface HourlyStats {
  hour: string;
  avgPower: number;
  totalEnergy: number;
  totalCost: number;
  avgCpuUsage: number;
  avgRamUsage: number;
  peakHours: number;
  offPeakHours: number;
}

interface DailyStats {
  date: string;
  totalEnergy: number;
  totalCost: number;
  avgPower: number;
  peakCost: number;
  offPeakCost: number;
  uptime: number;
}

export class PowerDatabase {
  private db: Database.Database;

  constructor(dbPath: string = DB_PATH) {
    this.db = new Database(dbPath);
    this.init();
  }

  private init() {
    // Create metrics table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS metrics (
        timestamp INTEGER PRIMARY KEY,
        cpuUsage REAL,
        ramUsage REAL,
        ramUsedGB REAL,
        ramTotalGB REAL,
        uptime REAL,
        powerWatts REAL,
        pricePerKWh REAL,
        pricePeriod TEXT,
        cost REAL
      )
    `);

    // Create hourly aggregated table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS hourly_stats (
        hour TEXT PRIMARY KEY,
        avgPower REAL,
        totalEnergy REAL,
        totalCost REAL,
        avgCpuUsage REAL,
        avgRamUsage REAL,
        peakHours INTEGER,
        offPeakHours INTEGER
      )
    `);

    // Create daily aggregated table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS daily_stats (
        date TEXT PRIMARY KEY,
        totalEnergy REAL,
        totalCost REAL,
        avgPower REAL,
        peakCost REAL,
        offPeakCost REAL,
        uptime REAL
      )
    `);

    // Create indexes for better query performance
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)
    `);
  }

  insertMetrics(metrics: SystemMetrics, powerWatts: number) {
    const pricePerKWh = getCurrentPrice(metrics.timestamp);
    const pricePeriod = getPricePeriod(metrics.timestamp);
    const cost = calculateEnergyCost(powerWatts, 60, pricePerKWh); // 1 minute = 60 seconds

    const stmt = this.db.prepare(`
      INSERT INTO metrics (
        timestamp, cpuUsage, ramUsage, ramUsedGB, ramTotalGB,
        uptime, powerWatts, pricePerKWh, pricePeriod, cost
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      metrics.timestamp,
      metrics.cpuUsage,
      metrics.ramUsage,
      metrics.ramUsedGB,
      metrics.ramTotalGB,
      metrics.uptime,
      powerWatts,
      pricePerKWh,
      pricePeriod,
      cost
    );

    // Trigger aggregation
    this.aggregateHourly(metrics.timestamp);
    this.aggregateDaily(metrics.timestamp);
  }

  private aggregateHourly(timestamp: number) {
    const date = new Date(timestamp);
    const hourKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:00`;

    const hourStart = new Date(date.getFullYear(), date.getMonth(), date.getDate(), date.getHours(), 0, 0).getTime();
    const hourEnd = hourStart + 3600000; // 1 hour in milliseconds

    const stats = this.db.prepare(`
      SELECT 
        AVG(powerWatts) as avgPower,
        SUM(powerWatts * 60 / 1000 / 3600) as totalEnergy,
        SUM(cost) as totalCost,
        AVG(cpuUsage) as avgCpuUsage,
        AVG(ramUsage) as avgRamUsage,
        SUM(CASE WHEN pricePeriod = 'peak' THEN 1 ELSE 0 END) as peakHours,
        SUM(CASE WHEN pricePeriod = 'off-peak' THEN 1 ELSE 0 END) as offPeakHours
      FROM metrics
      WHERE timestamp >= ? AND timestamp < ?
    `).get(hourStart, hourEnd) as any;

    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO hourly_stats (
        hour, avgPower, totalEnergy, totalCost, avgCpuUsage, avgRamUsage, peakHours, offPeakHours
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      hourKey,
      Math.round(stats.avgPower * 100) / 100,
      Math.round(stats.totalEnergy * 10000) / 10000,
      Math.round(stats.totalCost * 10000) / 10000,
      Math.round(stats.avgCpuUsage * 100) / 100,
      Math.round(stats.avgRamUsage * 100) / 100,
      stats.peakHours,
      stats.offPeakHours
    );
  }

  private aggregateDaily(timestamp: number) {
    const date = new Date(timestamp);
    const dateKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

    const dayStart = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0).getTime();
    const dayEnd = dayStart + 86400000; // 24 hours in milliseconds

    const stats = this.db.prepare(`
      SELECT 
        SUM(powerWatts * 60 / 1000 / 3600) as totalEnergy,
        SUM(cost) as totalCost,
        AVG(powerWatts) as avgPower,
        SUM(CASE WHEN pricePeriod = 'peak' THEN cost ELSE 0 END) as peakCost,
        SUM(CASE WHEN pricePeriod = 'off-peak' THEN cost ELSE 0 END) as offPeakCost,
        MAX(uptime) as uptime
      FROM metrics
      WHERE timestamp >= ? AND timestamp < ?
    `).get(dayStart, dayEnd) as any;

    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO daily_stats (
        date, totalEnergy, totalCost, avgPower, peakCost, offPeakCost, uptime
      ) VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      dateKey,
      Math.round(stats.totalEnergy * 10000) / 10000,
      Math.round(stats.totalCost * 10000) / 10000,
      Math.round(stats.avgPower * 100) / 100,
      Math.round(stats.peakCost * 10000) / 10000,
      Math.round(stats.offPeakCost * 10000) / 10000,
      Math.round(stats.uptime)
    );
  }

  getRecentMetrics(limit: number = 60): MetricRecord[] {
    const stmt = this.db.prepare(`
      SELECT * FROM metrics
      ORDER BY timestamp DESC
      LIMIT ?
    `);
    return stmt.all(limit) as MetricRecord[];
  }

  getHourlyStats(hours: number = 24): HourlyStats[] {
    const stmt = this.db.prepare(`
      SELECT * FROM hourly_stats
      ORDER BY hour DESC
      LIMIT ?
    `);
    return stmt.all(hours) as HourlyStats[];
  }

  getDailyStats(days: number = 7): DailyStats[] {
    const stmt = this.db.prepare(`
      SELECT * FROM daily_stats
      ORDER BY date DESC
      LIMIT ?
    `);
    return stmt.all(days) as DailyStats[];
  }

  getTotalStats(): any {
    const stats = this.db.prepare(`
      SELECT 
        COUNT(*) as totalReadings,
        SUM(cost) as totalCost,
        SUM(powerWatts * 60 / 1000 / 3600) as totalEnergy,
        AVG(powerWatts) as avgPower,
        MIN(timestamp) as firstReading,
        MAX(timestamp) as lastReading
      FROM metrics
    `).get() as any;

    return {
      totalReadings: stats.totalReadings,
      totalCost: Math.round(stats.totalCost * 10000) / 10000,
      totalEnergy: Math.round(stats.totalEnergy * 10000) / 10000,
      avgPower: Math.round(stats.avgPower * 100) / 100,
      firstReading: stats.firstReading,
      lastReading: stats.lastReading
    };
  }

  cleanup(daysToKeep: number = 30) {
    const cutoff = Date.now() - (daysToKeep * 24 * 60 * 60 * 1000);
    
    this.db.prepare(`
      DELETE FROM metrics
      WHERE timestamp < ?
    `).run(cutoff);

    this.db.prepare(`
      DELETE FROM hourly_stats
      WHERE hour < datetime(?/1000, 'unixepoch', '-' || ? || ' days')
    `).run(cutoff, daysToKeep);

    this.db.prepare(`
      DELETE FROM daily_stats
      WHERE date < date(?/1000, 'unixepoch', '-' || ? || ' days')
    `).run(cutoff, daysToKeep);
  }

  close() {
    this.db.close();
  }
}
