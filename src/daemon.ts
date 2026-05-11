import { collectMetrics } from './metrics.js';
import { calculatePower } from './power.js';
import { PowerDatabase } from './database.js';

const COLLECTION_INTERVAL = 60000; // 1 minute in milliseconds
const DB_PATH = process.env.DB_PATH || '/var/lib/proxmox-power-monitor/data.db';

let running = true;
let db: PowerDatabase;

async function cleanup() {
  console.log('Shutting down daemon...');
  if (db) {
    db.close();
  }
  process.exit(0);
}

async function main() {
  // Handle shutdown signals
  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
  process.on('uncaughtException', (err) => {
    console.error('Uncaught exception:', err);
    cleanup();
  });

  // Initialize database
  try {
    db = new PowerDatabase(DB_PATH);
    console.log('Power monitor daemon started');
    console.log(`Collection interval: ${COLLECTION_INTERVAL / 1000}s`);
    console.log(`Database: ${DB_PATH}`);
  } catch (error) {
    console.error('Failed to initialize database:', error);
    process.exit(1);
  }

  // Main collection loop
  while (running) {
    try {
      const metrics = await collectMetrics();
      const power = calculatePower(metrics);
      
      db.insertMetrics(metrics, power);
      
      console.log(`[${new Date().toISOString()}] CPU: ${metrics.cpuUsage}%, RAM: ${metrics.ramUsage}%, Power: ${power}W`);
    } catch (error) {
      console.error('Error collecting metrics:', error);
    }

    // Wait for next collection
    await new Promise(resolve => setTimeout(resolve, COLLECTION_INTERVAL));
  }
}

main();
