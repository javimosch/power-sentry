#!/usr/bin/env python3
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from metrics import SystemMetrics
from power import calculate_power, calculate_energy_cost
from pricing import get_current_price, get_price_period

DB_PATH = '/var/lib/proxmox-power-monitor/data.db'

class PowerDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.init()
    
    def init(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()
        
        # Create metrics table
        cursor.execute('''
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
        ''')
        
        # Create hourly aggregated table
        cursor.execute('''
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
        ''')
        
        # Create daily aggregated table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                totalEnergy REAL,
                totalCost REAL,
                avgPower REAL,
                peakCost REAL,
                offPeakCost REAL,
                uptime REAL
            )
        ''')
        
        # Create index for better query performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
            ON metrics(timestamp)
        ''')
        
        self.conn.commit()
    
    def insert_metrics(self, metrics: SystemMetrics, power_watts: float):
        """Insert metrics into database and trigger aggregation."""
        price_per_kwh = get_current_price(metrics.timestamp)
        price_period = get_price_period(metrics.timestamp)
        cost = calculate_energy_cost(power_watts, 60, price_per_kwh)  # 1 minute = 60 seconds
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO metrics (
                timestamp, cpuUsage, ramUsage, ramUsedGB, ramTotalGB,
                uptime, powerWatts, pricePerKWh, pricePeriod, cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(metrics.timestamp),
            float(metrics.cpu_usage),
            float(metrics.ram_usage),
            float(metrics.ram_used_gb),
            float(metrics.ram_total_gb),
            float(metrics.uptime),
            float(power_watts),
            float(price_per_kwh),
            str(price_period),
            float(cost)
        ))
        self.conn.commit()
        
        # Trigger aggregation
        self.aggregate_hourly(metrics.timestamp)
        self.aggregate_daily(metrics.timestamp)
    
    def aggregate_hourly(self, timestamp: float):
        """Aggregate metrics into hourly stats."""
        date = datetime.fromtimestamp(timestamp)
        hour_key = f"{date.year}-{date.month:02d}-{date.day:02d} {date.hour:02d}:00"
        
        hour_start = datetime(date.year, date.month, date.day, date.hour, 0, 0).timestamp()
        hour_end = hour_start + 3600  # 1 hour in seconds
        
        cursor = self.conn.cursor()
        cursor.execute('''
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
        ''', (hour_start, hour_end))
        
        stats = cursor.fetchone()
        if stats and stats[0] is not None:
            cursor.execute('''
                INSERT OR REPLACE INTO hourly_stats (
                    hour, avgPower, totalEnergy, totalCost, avgCpuUsage, avgRamUsage, peakHours, offPeakHours
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                hour_key,
                round(stats[0], 2) if stats[0] else 0,
                round(stats[1], 4) if stats[1] else 0,
                round(stats[2], 4) if stats[2] else 0,
                round(stats[3], 2) if stats[3] else 0,
                round(stats[4], 2) if stats[4] else 0,
                stats[5] if stats[5] else 0,
                stats[6] if stats[6] else 0
            ))
            self.conn.commit()
    
    def aggregate_daily(self, timestamp: float):
        """Aggregate metrics into daily stats."""
        date = datetime.fromtimestamp(timestamp)
        date_key = f"{date.year}-{date.month:02d}-{date.day:02d}"
        
        day_start = datetime(date.year, date.month, date.day, 0, 0, 0).timestamp()
        day_end = day_start + 86400  # 24 hours in seconds
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                SUM(powerWatts * 60 / 1000 / 3600) as totalEnergy,
                SUM(cost) as totalCost,
                AVG(powerWatts) as avgPower,
                SUM(CASE WHEN pricePeriod = 'peak' THEN cost ELSE 0 END) as peakCost,
                SUM(CASE WHEN pricePeriod = 'off-peak' THEN cost ELSE 0 END) as offPeakCost,
                MAX(uptime) as uptime
            FROM metrics
            WHERE timestamp >= ? AND timestamp < ?
        ''', (day_start, day_end))
        
        stats = cursor.fetchone()
        if stats and stats[0] is not None:
            cursor.execute('''
                INSERT OR REPLACE INTO daily_stats (
                    date, totalEnergy, totalCost, avgPower, peakCost, offPeakCost, uptime
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                date_key,
                round(stats[0], 4) if stats[0] else 0,
                round(stats[1], 4) if stats[1] else 0,
                round(stats[2], 2) if stats[2] else 0,
                round(stats[3], 4) if stats[3] else 0,
                round(stats[4], 4) if stats[4] else 0,
                round(stats[5]) if stats[5] else 0
            ))
            self.conn.commit()
    
    def get_recent_metrics(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Get recent metrics."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM metrics
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_hourly_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get hourly statistics."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM hourly_stats
            ORDER BY hour DESC
            LIMIT ?
        ''', (hours,))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily statistics."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM daily_stats
            ORDER BY date DESC
            LIMIT ?
        ''', (days,))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_total_stats(self) -> Dict[str, Any]:
        """Get total statistics."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as totalReadings,
                SUM(cost) as totalCost,
                SUM(powerWatts * 60 / 1000 / 3600) as totalEnergy,
                AVG(powerWatts) as avgPower,
                MIN(timestamp) as firstReading,
                MAX(timestamp) as lastReading
            FROM metrics
        ''')
        
        stats = cursor.fetchone()
        return {
            'totalReadings': stats[0] if stats[0] else 0,
            'totalCost': round(stats[1], 4) if stats[1] else 0,
            'totalEnergy': round(stats[2], 4) if stats[2] else 0,
            'avgPower': round(stats[3], 2) if stats[3] else 0,
            'firstReading': stats[4] if stats[4] else 0,
            'lastReading': stats[5] if stats[5] else 0
        }
    
    def cleanup(self, days_to_keep: int = 30):
        """Clean up old records."""
        cutoff = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff,))
        cursor.execute('DELETE FROM hourly_stats WHERE hour < datetime(?, "unixepoch", "-" || ? || " days")', 
                      (cutoff, days_to_keep))
        cursor.execute('DELETE FROM daily_stats WHERE date < date(?, "unixepoch", "-" || ? || " days")', 
                      (cutoff, days_to_keep))
        self.conn.commit()
    
    def project_cost(self, days: int) -> Dict[str, Any]:
        """Project cost for a given number of days based on existing data patterns."""
        cursor = self.conn.cursor()
        
        # Get current data statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                AVG(powerWatts) as avgPower,
                AVG(cost) as avgCostPerMinute,
                AVG(cpuUsage) as avgCpu,
                AVG(ramUsage) as avgRam,
                MIN(timestamp) as firstReading,
                MAX(timestamp) as lastReading
            FROM metrics
        ''')
        
        stats = cursor.fetchone()
        
        if not stats or stats[0] == 0:
            # No data available
            return {
                'error': 'No data available for projection',
                'message': 'Run the daemon longer to collect data'
            }
        
        count, avg_power, avg_cost_per_minute, avg_cpu, avg_ram, first_ts, last_ts = stats
        
        # Calculate data coverage
        data_duration_minutes = (last_ts - first_ts) / 60 if first_ts and last_ts else 0
        requested_duration_minutes = days * 24 * 60
        
        # Get hourly pattern if available
        cursor.execute('''
            SELECT 
                AVG(avgPower) as avgPower,
                AVG(totalCost) as avgCostPerHour,
                COUNT(*) as hours
            FROM hourly_stats
        ''')
        
        hourly_stats = cursor.fetchone()
        
        # Get peak/off-peak distribution
        cursor.execute('''
            SELECT 
                pricePeriod,
                AVG(powerWatts) as avgPower,
                AVG(cost) as avgCost,
                COUNT(*) as count
            FROM metrics
            GROUP BY pricePeriod
        ''')
        
        period_stats = {}
        for row in cursor.fetchall():
            period_stats[row[0]] = {
                'avgPower': row[1],
                'avgCost': row[2],
                'count': row[3]
            }
        
        # Calculate projection
        if data_duration_minutes >= requested_duration_minutes:
            # We have actual data for the requested period
            cursor.execute('''
                SELECT 
                    SUM(cost) as totalCost,
                    SUM(powerWatts * 60 / 1000 / 3600) as totalEnergy,
                    AVG(powerWatts) as avgPower,
                    COUNT(*) as readings
                FROM metrics
                WHERE timestamp >= ?
            ''', (datetime.now().timestamp() - requested_duration_minutes * 60,))
            
            actual_stats = cursor.fetchone()
            
            total_cost = round(actual_stats[0], 4) if actual_stats[0] else 0
            avg_daily_cost = round(total_cost / days, 4) if days > 0 else 0
            avg_hourly_cost = round(total_cost / (days * 24), 4) if days > 0 else 0
            
            return {
                'type': 'actual',
                'period_days': days,
                'totalCost': total_cost,
                'totalCostFormatted': f'€{total_cost:.2f}',
                'avgDailyCost': avg_daily_cost,
                'avgDailyCostFormatted': f'€{avg_daily_cost:.2f}/day',
                'avgHourlyCost': avg_hourly_cost,
                'avgHourlyCostFormatted': f'€{avg_hourly_cost:.3f}/hour',
                'totalEnergy': round(actual_stats[1], 4) if actual_stats[1] else 0,
                'avgPower': round(actual_stats[2], 2) if actual_stats[2] else 0,
                'readings': actual_stats[3] if actual_stats[3] else 0,
                'confidence': 'high',
                'method': 'actual_data'
            }
        else:
            # Extrapolate based on available data
            if hourly_stats and hourly_stats[2] > 0:
                # Use hourly patterns for better accuracy
                avg_hourly_cost = hourly_stats[1] if hourly_stats[1] else avg_cost_per_minute * 60
                projected_hours = days * 24
                projected_cost = avg_hourly_cost * projected_hours
                projected_energy = (hourly_stats[0] if hourly_stats[0] else avg_power) * projected_hours / 1000
                
                method = 'hourly_extrapolation'
                confidence = 'medium' if hourly_stats[2] >= 24 else 'low'
            else:
                # Use minute-level extrapolation
                projected_cost = avg_cost_per_minute * requested_duration_minutes
                projected_energy = avg_power * requested_duration_minutes / 1000 / 60
                
                method = 'minute_extrapolation'
                confidence = 'low' if data_duration_minutes < 60 else 'medium'
            
            # Calculate peak/off-peak breakdown
            peak_hours_per_day = 8  # 22h-6h = 8 hours
            off_peak_hours_per_day = 16  # 6h-22h = 16 hours
            total_peak_hours = days * peak_hours_per_day
            total_off_peak_hours = days * off_peak_hours_per_day
            
            peak_cost = 0
            off_peak_cost = 0
            
            if 'peak' in period_stats and 'off-peak' in period_stats:
                # Use observed period-specific costs
                peak_cost = period_stats['peak']['avgCost'] * total_peak_hours * 60  # cost per minute * minutes
                off_peak_cost = period_stats['off-peak']['avgCost'] * total_off_peak_hours * 60
            else:
                # Use overall average with pricing ratio
                peak_ratio = total_peak_hours / (days * 24)
                off_peak_ratio = total_off_peak_hours / (days * 24)
                from pricing import FrenchPricing
                peak_cost = projected_cost * peak_ratio * (FrenchPricing.peak_price / FrenchPricing.off_peak_price)
                off_peak_cost = projected_cost * off_peak_ratio
            
            total_cost = round(projected_cost, 4)
            avg_daily_cost = round(total_cost / days, 4) if days > 0 else 0
            avg_hourly_cost = round(total_cost / (days * 24), 4) if days > 0 else 0
            
            return {
                'type': 'projected',
                'period_days': days,
                'totalCost': total_cost,
                'totalCostFormatted': f'€{total_cost:.2f}',
                'avgDailyCost': avg_daily_cost,
                'avgDailyCostFormatted': f'€{avg_daily_cost:.2f}/day',
                'avgHourlyCost': avg_hourly_cost,
                'avgHourlyCostFormatted': f'€{avg_hourly_cost:.3f}/hour',
                'totalEnergy': round(projected_energy, 4),
                'avgPower': round(avg_power, 2) if avg_power else 0,
                'peakCost': round(peak_cost, 4),
                'peakCostFormatted': f'€{round(peak_cost, 2)}',
                'offPeakCost': round(off_peak_cost, 4),
                'offPeakCostFormatted': f'€{round(off_peak_cost, 2)}',
                'dataCoverage': {
                    'availableMinutes': int(data_duration_minutes),
                    'requestedMinutes': int(requested_duration_minutes),
                    'coveragePercentage': round((data_duration_minutes / requested_duration_minutes) * 100, 2)
                },
                'observedPatterns': {
                    'avgCpuUsage': round(avg_cpu, 2) if avg_cpu else 0,
                    'avgRamUsage': round(avg_ram, 2) if avg_ram else 0,
                    'periods': period_stats
                },
                'confidence': confidence,
                'method': method,
                'readings': int(count)
            }
    
    def close(self):
        """Close database connection."""
        self.conn.close()
