#!/usr/bin/env python3

"""
Simple launcher that starts both the flaschen-taschen server and MQTT listener.

This script:
1. Starts a flaschen-taschen server process 
2. Runs the existing MQTT listener app

Usage:
    python3 simple_start.py [--server-path PATH] [--terminal]

Options:
    --server-path: Path to ft-server binary (default: ./ft-server)
    --terminal: Use terminal backend (default: auto-detect)
    --help: Show this help
"""

import argparse
import subprocess
import sys
import time
import signal
import os
from pathlib import Path


def find_ft_server():
    """Try to find the ft-server binary in common locations."""
    possible_paths = [
        './ft-server',
        '../flaschen-taschen/server/ft-server', 
        '~/flaschen-taschen/server/ft-server',
        '/usr/local/bin/ft-server',
        'ft-server'  # In PATH
    ]
    
    for path_str in possible_paths:
        path = Path(path_str).expanduser()
        if path.exists() and path.is_file():
            return path
            
    return None


def start_ft_server(server_path, use_terminal=True, width=32, height=32):
    """Start the flaschen-taschen server."""
    cmd = [str(server_path)]
    
    # Add display size
    cmd.append(f'-D{width}x{height}')
    
    # Add terminal option for testing
    if use_terminal:
        cmd.append('--hd-terminal')
    
    print(f"Starting flaschen-taschen server: {' '.join(cmd)}")
    
    try:
        # Start the server process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Give it a moment to start and check if it's running
        time.sleep(2)
        
        if process.poll() is None:
            print("✓ Flaschen-taschen server started successfully")
            return process
        else:
            # Server exited immediately, something went wrong
            output, _ = process.communicate()
            print(f"✗ Failed to start flaschen-taschen server")
            print(f"Output: {output}")
            return None
            
    except FileNotFoundError:
        print(f"✗ Server binary not found: {server_path}")
        print("Please compile flaschen-taschen server or provide correct path with --server-path")
        return None
    except Exception as e:
        print(f"✗ Error starting server: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Start flaschen-taschen server and MQTT listener',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 simple_start.py                                    # Auto-find server, use terminal
    python3 simple_start.py --server-path ./ft-server          # Specify server path
    python3 simple_start.py --server-path /usr/bin/ft-server   # Use installed server
    
Note: This script starts the flaschen server, then runs the existing app.py
"""
    )
    
    parser.add_argument(
        '--server-path',
        type=Path,
        help='Path to ft-server binary'
    )
    parser.add_argument(
        '--terminal',
        action='store_true',
        help='Force terminal backend (default: auto-detect if no display detected)'
    )
    parser.add_argument(
        '--no-terminal',
        action='store_true', 
        help='Force hardware backend (no terminal)'
    )
    
    args = parser.parse_args()
    
    # Find the server binary
    if args.server_path:
        server_path = args.server_path
        if not server_path.exists():
            print(f"✗ Specified server path does not exist: {server_path}")
            sys.exit(1)
    else:
        server_path = find_ft_server()
        if not server_path:
            print("✗ Could not find ft-server binary")
            print("\nPlease either:")
            print("1. Compile flaschen-taschen server in current directory")
            print("2. Provide path with --server-path /path/to/ft-server")
            print("3. Install ft-server in your PATH")
            print("\nTo compile flaschen-taschen server:")
            print("  git clone --recursive https://github.com/hzeller/flaschen-taschen.git")
            print("  cd flaschen-taschen/server")
            print("  make FT_BACKEND=terminal")
            sys.exit(1)
            
    print(f"Using server: {server_path}")
    
    # Determine if we should use terminal backend
    use_terminal = True
    if args.no_terminal:
        use_terminal = False
    elif args.terminal:
        use_terminal = True
    else:
        # Auto-detect: use terminal if no hardware display detected
        use_terminal = True  # Default to terminal for safety
        
    # Load config to get display dimensions
    try:
        from app import FLASCHEN_COLS, FLASCHEN_ROWS
        width = FLASCHEN_COLS
        height = FLASCHEN_ROWS
    except ImportError:
        print("Warning: Could not import config from app.py, using defaults")
        width = 32
        height = 32
        
    print(f"Display size: {width}x{height}")
    print(f"Backend: {'terminal' if use_terminal else 'hardware'}")
    
    # Start the flaschen server
    server_process = start_ft_server(server_path, use_terminal, width, height)
    
    if not server_process:
        print("Failed to start flaschen-taschen server")
        sys.exit(1)
        
    # Give the server a moment to fully initialize
    print("Waiting for server to initialize...")
    time.sleep(3)
    
    try:
        print("\n" + "="*60)
        print("Starting MQTT listener (app.py)...")
        print("="*60)
        
        # Import and run the existing app
        # The app.py module will handle MQTT connection and start its main loop
        import app
        
        # The app.py should now run its main loop
        # If it doesn't have a main loop, we'll add one
        if hasattr(app, '__name__') and app.__name__ == '__main__':
            # app.py has its own main execution
            pass
        else:
            # We need to keep the process alive
            print("MQTT listener started. Press Ctrl+C to stop all services.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nReceived interrupt signal...")
                
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error running MQTT listener: {e}")
    finally:
        # Clean up: terminate the server process
        if server_process and server_process.poll() is None:
            print("Stopping flaschen-taschen server...")
            server_process.terminate()
            
            # Give it a few seconds to terminate gracefully
            try:
                server_process.wait(timeout=5)
                print("✓ Server stopped gracefully")
            except subprocess.TimeoutExpired:
                print("Server didn't stop gracefully, killing...")
                server_process.kill()
                server_process.wait()
                print("✓ Server killed")
                
        print("All services stopped.")


if __name__ == "__main__":
    main()
