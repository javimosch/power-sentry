#!/usr/bin/env python3
import sys
import os
import json
import subprocess
from database import PowerDatabase
from typing import Dict, Any

DB_PATH = os.environ.get('DB_PATH', '/var/lib/proxmox-power-monitor/data.db')
SERVICE_NAME = 'powersentry-worker'
SERVICE_FILE = f'/etc/systemd/system/{SERVICE_NAME}.service'
INSTALL_DIR = '/opt/proxmox-power-monitor'
DATA_DIR = '/var/lib/proxmox-power-monitor'

def print_json(data: Any):
    """Print data as JSON."""
    print(json.dumps(data, indent=2))

def ensure_directories():
    """Ensure required directories exist."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        subprocess.run(['chown', 'root:root', DATA_DIR], check=True)
        subprocess.run(['chmod', '755', DATA_DIR], check=True)

def generate_service_file(control_panel_url: str = "") -> str:
    """Generate systemd service file content."""
    env_vars = f'"DB_PATH={DB_PATH}"'
    if control_panel_url:
        env_vars += f' "CONTROL_PANEL_URL={control_panel_url}"'
    
    return f'''[Unit]
Description=PowerSentry Worker Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={INSTALL_DIR}
Environment={env_vars}
ExecStart=/usr/bin/python3 {INSTALL_DIR}/daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
'''

def install_service(control_panel_url: str = ""):
    """Install systemd service."""
    print('Installing PowerSentry worker agent service...')
    
    # Ensure directories exist
    ensure_directories()
    
    # Create systemd service file
    service_content = generate_service_file(control_panel_url)
    with open(SERVICE_FILE, 'w') as f:
        f.write(service_content)
    
    # Reload systemd
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    
    # Enable service
    subprocess.run(['systemctl', 'enable', SERVICE_NAME], check=True)
    
    if control_panel_url:
        print(f'Service installed successfully with control panel: {control_panel_url}')
    else:
        print('Service installed successfully (standalone mode)')
    print('Run "python3 cli.py start" to start the daemon')

def uninstall_service():
    """Uninstall systemd service."""
    print('Uninstalling proxmox-power-monitor service...')
    
    # Stop service if running
    try:
        subprocess.run(['systemctl', 'stop', SERVICE_NAME], check=True)
    except subprocess.CalledProcessError:
        pass  # Service might not be running
    
    # Disable service
    subprocess.run(['systemctl', 'disable', SERVICE_NAME], check=True)
    
    # Remove service file
    if os.path.exists(SERVICE_FILE):
        os.remove(SERVICE_FILE)
    
    # Reload systemd
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    
    print('Service uninstalled successfully')

def start_service():
    """Start the daemon."""
    print('Starting proxmox-power-monitor daemon...')
    subprocess.run(['systemctl', 'start', SERVICE_NAME], check=True)
    print('Daemon started')

def stop_service():
    """Stop the daemon."""
    print('Stopping proxmox-power-monitor daemon...')
    subprocess.run(['systemctl', 'stop', SERVICE_NAME], check=True)
    print('Daemon stopped')

def show_status():
    """Show service status."""
    try:
        result = subprocess.run(['systemctl', 'status', SERVICE_NAME], 
                              capture_output=True, text=True)
        print(result.stdout)
    except subprocess.CalledProcessError:
        print_json({
            'status': 'not installed or not running',
            'error': 'Service check failed'
        })

def show_stats(options: Dict[str, Any] = None):
    """Show power consumption stats."""
    if options is None:
        options = {}
    
    try:
        db = PowerDatabase(DB_PATH)
        
        if options.get('total'):
            stats = db.get_total_stats()
            print_json({
                'type': 'total',
                'data': stats
            })
        elif options.get('hourly'):
            hours = int(options['hourly']) if options['hourly'] else 24
            stats = db.get_hourly_stats(hours)
            print_json({
                'type': 'hourly',
                'hours': hours,
                'data': stats
            })
        elif options.get('daily'):
            days = int(options['daily']) if options['daily'] else 7
            stats = db.get_daily_stats(days)
            print_json({
                'type': 'daily',
                'days': days,
                'data': stats
            })
        elif options.get('recent'):
            limit = int(options['recent']) if options['recent'] else 60
            stats = db.get_recent_metrics(limit)
            print_json({
                'type': 'recent',
                'limit': limit,
                'data': stats
            })
        else:
            # Default: show total stats
            total = db.get_total_stats()
            recent = db.get_recent_metrics(5)
            print_json({
                'type': 'summary',
                'total': total,
                'recent': recent
            })
        
        db.close()
    except Exception as e:
        print_json({
            'error': 'Failed to retrieve stats',
            'details': str(e)
        })
        sys.exit(1)

def cleanup_database(options: Dict[str, Any] = None):
    """Cleanup old database records."""
    if options is None:
        options = {}
    
    days = int(options.get('days', 30))
    try:
        db = PowerDatabase(DB_PATH)
        db.cleanup(days)
        db.close()
        print_json({
            'success': True,
            'message': f'Cleaned up data older than {days} days'
        })
    except Exception as e:
        print_json({
            'error': 'Failed to cleanup database',
            'details': str(e)
        })
        sys.exit(1)

def project_cost(days: int):
    """Project cost for a given number of days."""
    try:
        db = PowerDatabase(DB_PATH)
        projection = db.project_cost(days)
        db.close()
        print_json(projection)
    except Exception as e:
        print_json({
            'error': 'Failed to project cost',
            'details': str(e)
        })
        sys.exit(1)

def print_usage():
    """Print usage information."""
    print_json({
        'usage': 'python3 cli.py <command> [options]',
        'commands': {
            'install': 'Install systemd service',
            'uninstall': 'Uninstall systemd service',
            'start': 'Start the daemon',
            'stop': 'Stop the daemon',
            'status': 'Show service status',
            'stats': 'Show power consumption stats (JSON output)',
            'project': 'Project cost for N days (simulation based on current data)',
            'cleanup': 'Cleanup old database records'
        },
        'install_options': {
            '--control-panel=URL': 'Connect to control panel (e.g., ws://<control-panel>:8765/worker)'
        },
        'stats_options': {
            '--total': 'Show total statistics',
            '--hourly=N': 'Show last N hours (default: 24)',
            '--daily=N': 'Show last N days (default: 7)',
            '--recent=N': 'Show last N readings (default: 60)'
        },
        'project_options': {
            '<days>': 'Number of days to project (required)'
        },
        'cleanup_options': {
            '--days=N': 'Delete records older than N days (default: 30)'
        },
        'examples': [
            'python3 cli.py install',
            'python3 cli.py install --control-panel=ws://<control-panel>:8765/worker',
            'python3 cli.py start',
            'python3 cli.py stats --total',
            'python3 cli.py stats --daily=30',
            'python3 cli.py project 14',
            'python3 cli.py project 30',
            'python3 cli.py cleanup --days=90'
        ]
    })

def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1]
    options = {}
    
    # Parse options
    for arg in sys.argv[2:]:
        if arg.startswith('--'):
            if '=' in arg:
                key, value = arg[2:].split('=', 1)
                options[key] = value
            else:
                options[arg[2:]] = True
    
    switch = {
        'install': lambda: install_service(options.get('control-panel', '')),
        'uninstall': uninstall_service,
        'start': start_service,
        'stop': stop_service,
        'status': show_status,
        'stats': lambda: show_stats(options),
        'project': lambda: project_cost(int(sys.argv[2])) if len(sys.argv) > 2 else (print_usage(), sys.exit(1)),
        'cleanup': lambda: cleanup_database(options)
    }
    
    if command in switch:
        switch[command]()
    else:
        print_usage()
        sys.exit(1)

if __name__ == '__main__':
    main()
