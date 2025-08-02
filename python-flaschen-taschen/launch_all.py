#!/usr/bin/env python3

"""
Launch both flaschen-taschen server and MQTT listener app.

This script starts both processes and manages them together.
When you press Ctrl+C, both processes are stopped cleanly.
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path


class ProcessManager:
    def __init__(self):
        self.processes = []
        self.running = True
        
        # Set up signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop_all()
        sys.exit(0)
        
    def start_process(self, cmd, name, env=None):
        """Start a process and add it to our managed list."""
        try:
            print(f"Starting {name}: {' '.join(map(str, cmd))}")
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            self.processes.append((process, name))
            return process
        except Exception as e:
            print(f"Failed to start {name}: {e}")
            return None
    
    def stop_all(self):
        """Stop all managed processes."""
        self.running = False
        for process, name in self.processes:
            if process.poll() is None:  # Process is still running
                print(f"Stopping {name}...")
                process.terminate()
                
        # Give processes time to terminate gracefully
        time.sleep(2)
        
        # Force kill any that didn't stop
        for process, name in self.processes:
            if process.poll() is None:
                print(f"Force killing {name}...")
                process.kill()
                
    def wait_for_all(self):
        """Wait for all processes to complete or handle interruption."""
        try:
            while self.running:
                # Check if any process has died
                all_running = True
                for process, name in self.processes:
                    if process.poll() is not None:
                        print(f"{name} has stopped")
                        all_running = False
                        
                if not all_running:
                    print("One or more processes stopped, shutting down all...")
                    self.stop_all()
                    break
                    
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            self.stop_all()


def find_ft_server():
    """Find the flaschen-taschen server binary."""
    locations = [
        './ft-server',
        '../flaschen-taschen/server/ft-server',
        '~/flaschen-taschen/server/ft-server',
        '~/projects/flaschen-taschen/server/ft-server',
        'ft-server'  # in PATH
    ]
    
    for location in locations:
        path = Path(location).expanduser().resolve()
        if path.exists() and path.is_file():
            return path
    return None


def main():
    print("Flaschen Taschen + MQTT Launcher")
    print("=================================")
    
    # Get current directory for context
    current_dir = Path.cwd()
    print(f"Working directory: {current_dir}")
    
    # Try to load config for display size
    try:
        sys.path.insert(0, str(current_dir))
        from app import FLASCHEN_COLS, FLASCHEN_ROWS, FLASCHEN_PORT
        width = FLASCHEN_COLS
        height = FLASCHEN_ROWS
        port = FLASCHEN_PORT
        print(f"Loaded config: {width}x{height} display on port {port}")
    except Exception as e:
        print(f"Warning: Could not load config from app.py: {e}")
        width, height, port = 32, 32, 1337
        print(f"Using defaults: {width}x{height} display on port {port}")
    
    # Find the flaschen server
    ft_server_path = find_ft_server()
    if not ft_server_path:
        print("\nError: Could not find ft-server binary")
        print("\nTo compile flaschen-taschen server:")
        print("  git clone --recursive https://github.com/hzeller/flaschen-taschen.git")
        print("  cd flaschen-taschen/server") 
        print("  make FT_BACKEND=terminal")
        print("  cp ft-server /path/to/this/directory/")
        sys.exit(1)
        
    print(f"Found ft-server: {ft_server_path}")
    
    # Create process manager
    manager = ProcessManager()
    
    # Start flaschen-taschen server
    server_cmd = [
        str(ft_server_path),
        f'-D{width}x{height}',
        '--hd-terminal'  # Use terminal display for testing
    ]
    
    server_process = manager.start_process(server_cmd, "flaschen-server")
    if not server_process:
        print("Failed to start flaschen server")
        sys.exit(1)
        
    # Give server time to start
    print("Waiting for flaschen server to initialize...")
    time.sleep(3)
    
    # Start MQTT app
    app_cmd = [sys.executable, 'app.py']
    app_process = manager.start_process(app_cmd, "mqtt-app")
    if not app_process:
        print("Failed to start MQTT app")
        manager.stop_all()
        sys.exit(1)
        
    print("\n" + "="*50)
    print("Both services started successfully!")
    print("Press Ctrl+C to stop all services")
    print("="*50)
    
    # Wait for processes or interruption
    manager.wait_for_all()
    
    print("All services stopped.")


if __name__ == "__main__":
    main()
