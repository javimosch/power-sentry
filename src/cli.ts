#!/usr/bin/env bun
import { PowerDatabase } from './database.js';
import { execSync } from 'child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';

const DB_PATH = process.env.DB_PATH || '/var/lib/proxmox-power-monitor/data.db';
const SERVICE_NAME = 'proxmox-power-monitor';
const SERVICE_FILE = `/etc/systemd/system/${SERVICE_NAME}.service`;
const INSTALL_DIR = '/opt/proxmox-power-monitor';
const DATA_DIR = '/var/lib/proxmox-power-monitor';

interface CLIOptions {
  command: string;
  args: string[];
}

function printJSON(data: any) {
  console.log(JSON.stringify(data, null, 2));
}

function ensureDirectories() {
  if (!existsSync(DATA_DIR)) {
    mkdirSync(DATA_DIR, { recursive: true });
    execSync(`chown root:root ${DATA_DIR}`);
    execSync(`chmod 755 ${DATA_DIR}`);
  }
}

function generateServiceFile(): string {
  return `[Unit]
Description=Proxmox Power Monitor Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
Environment="DB_PATH=${DB_PATH}"
ExecStart=/usr/bin/bun run ${INSTALL_DIR}/src/daemon.ts
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
`;
}

async function installService() {
  console.log('Installing proxmox-power-monitor service...');
  
  // Ensure directories exist
  ensureDirectories();
  
  // Create systemd service file
  const serviceContent = generateServiceFile();
  writeFileSync(SERVICE_FILE, serviceContent);
  
  // Reload systemd
  execSync('systemctl daemon-reload');
  
  // Enable service
  execSync(`systemctl enable ${SERVICE_NAME}`);
  
  console.log('Service installed successfully');
  console.log('Run "bun run src/cli.ts start" to start the daemon');
}

async function uninstallService() {
  console.log('Uninstalling proxmox-power-monitor service...');
  
  // Stop service if running
  try {
    execSync(`systemctl stop ${SERVICE_NAME}`);
  } catch (error) {
    // Service might not be running
  }
  
  // Disable service
  execSync(`systemctl disable ${SERVICE_NAME}`);
  
  // Remove service file
  if (existsSync(SERVICE_FILE)) {
    execSync(`rm ${SERVICE_FILE}`);
  }
  
  // Reload systemd
  execSync('systemctl daemon-reload');
  
  console.log('Service uninstalled successfully');
}

async function startService() {
  console.log('Starting proxmox-power-monitor daemon...');
  execSync(`systemctl start ${SERVICE_NAME}`);
  console.log('Daemon started');
}

async function stopService() {
  console.log('Stopping proxmox-power-monitor daemon...');
  execSync(`systemctl stop ${SERVICE_NAME}`);
  console.log('Daemon stopped');
}

async function showStatus() {
  try {
    const output = execSync(`systemctl status ${SERVICE_NAME}`, { encoding: 'utf-8' });
    console.log(output);
  } catch (error) {
    printJSON({
      status: 'not installed or not running',
      error: 'Service check failed'
    });
  }
}

async function showStats(options: any = {}) {
  try {
    const db = new PowerDatabase(DB_PATH);
    
    if (options.total) {
      const stats = db.getTotalStats();
      printJSON({
        type: 'total',
        data: stats
      });
    } else if (options.hourly) {
      const hours = parseInt(options.hourly) || 24;
      const stats = db.getHourlyStats(hours);
      printJSON({
        type: 'hourly',
        hours: hours,
        data: stats
      });
    } else if (options.daily) {
      const days = parseInt(options.daily) || 7;
      const stats = db.getDailyStats(days);
      printJSON({
        type: 'daily',
        days: days,
        data: stats
      });
    } else if (options.recent) {
      const limit = parseInt(options.recent) || 60;
      const stats = db.getRecentMetrics(limit);
      printJSON({
        type: 'recent',
        limit: limit,
        data: stats
      });
    } else {
      // Default: show total stats
      const total = db.getTotalStats();
      const recent = db.getRecentMetrics(5);
      printJSON({
        type: 'summary',
        total: total,
        recent: recent
      });
    }
    
    db.close();
  } catch (error) {
    printJSON({
      error: 'Failed to retrieve stats',
      details: error instanceof Error ? error.message : String(error)
    });
    process.exit(1);
  }
}

async function cleanupDatabase(options: any = {}) {
  const days = parseInt(options.days) || 30;
  try {
    const db = new PowerDatabase(DB_PATH);
    db.cleanup(days);
    db.close();
    printJSON({
      success: true,
      message: `Cleaned up data older than ${days} days`
    });
  } catch (error) {
    printJSON({
      error: 'Failed to cleanup database',
      details: error instanceof Error ? error.message : String(error)
    });
    process.exit(1);
  }
}

function printUsage() {
  printJSON({
    usage: 'bun run src/cli.ts <command> [options]',
    commands: {
      install: 'Install systemd service',
      uninstall: 'Uninstall systemd service',
      start: 'Start the daemon',
      stop: 'Stop the daemon',
      status: 'Show service status',
      stats: 'Show power consumption stats (JSON output)',
      cleanup: 'Cleanup old database records'
    },
    statsOptions: {
      '--total': 'Show total statistics',
      '--hourly=N': 'Show last N hours (default: 24)',
      '--daily=N': 'Show last N days (default: 7)',
      '--recent=N': 'Show last N readings (default: 60)'
    },
    cleanupOptions: {
      '--days=N': 'Delete records older than N days (default: 30)'
    },
    examples: [
      'bun run src/cli.ts install',
      'bun run src/cli.ts start',
      'bun run src/cli.ts stats --total',
      'bun run src/cli.ts stats --daily=30',
      'bun run src/cli.ts cleanup --days=90'
    ]
  });
}

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  const options: any = {};

  // Parse options
  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith('--')) {
      const [key, value] = arg.slice(2).split('=');
      if (value) {
        options[key] = value;
      } else {
        options[key] = true;
      }
    }
  }

  switch (command) {
    case 'install':
      await installService();
      break;
    case 'uninstall':
      await uninstallService();
      break;
    case 'start':
      await startService();
      break;
    case 'stop':
      await stopService();
      break;
    case 'status':
      await showStatus();
      break;
    case 'stats':
      await showStats(options);
      break;
    case 'cleanup':
      await cleanupDatabase(options);
      break;
    default:
      printUsage();
      process.exit(1);
  }
}

main();
