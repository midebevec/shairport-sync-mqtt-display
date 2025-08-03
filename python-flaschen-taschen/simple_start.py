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
import os
import signal
from pathlib import Path
from yaml import safe_load


# Global variable to track server process for signal handling
server_process = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global server_process
    print("\nReceived shutdown signal, cleaning up...")
    if server_process and server_process.poll() is None:
        print("Stopping flaschen-taschen server...")
        try:
            # Try to terminate gracefully first
            server_process.terminate()
            server_process.wait(timeout=3)
            print("✓ Server stopped gracefully")
        except subprocess.TimeoutExpired:
            print("Server didn't stop gracefully, killing...")
            server_process.kill()
            server_process.wait()
            print("✓ Server killed")
    print("Cleanup complete.")
    sys.exit(0)


def load_flaschen_config():
    """Load flaschen hardware configuration from YAML file."""
    config_file = Path("flaschen_config.yaml")
    
    # Default configuration
    default_config = {
        'hardware': {
            'led_gpio_mapping': 'adafruit-hat',
            'led_slowdown_gpio': 2,
            'led_brightness': 50,
            'led_show_refresh': True
        },
        'terminal': {
            'hd_terminal': True
        },
        'server': {
            'daemon': False
        }
    }
    
    if config_file.exists():
        try:
            with config_file.open() as f:
                config = safe_load(f)
                # Merge with defaults
                for section in default_config:
                    if section in config:
                        default_config[section].update(config[section])
                print(f"Loaded flaschen config from {config_file}")
                return default_config
        except Exception as e:
            print(f"Warning: Could not load {config_file}: {e}")
            print("Using default flaschen configuration")
    else:
        print(f"No {config_file} found, using defaults")
    
    return default_config


def find_ft_server():
    """Try to find the ft-server binary in common locations."""
    possible_paths = [
        './ft-server',
        '../flaschen-taschen/server/ft-server', 
        '~/flaschen-taschen/server/ft-server',
        '/usr/local/bin/ft-server',
        '~/projects/flaschen-taschen/server/ft-server',
        'ft-server'  # In PATH
    ]
    
    for path_str in possible_paths:
        path = Path(path_str).expanduser()
        if path.exists() and path.is_file():
            return path
            
    return None


def start_ft_server(server_path, use_terminal=True, width=64, height=64, flaschen_config=None, verbose=False):
    """Start the flaschen-taschen server."""
    if flaschen_config is None:
        flaschen_config = load_flaschen_config()

    cmd = ['sudo', str(server_path)]

    # Add display size
    cmd.append(f'-D{width}x{height}')

    if not use_terminal:
        # Hardware mode - use config from YAML
        hw_config = flaschen_config['hardware']
        
        cmd.append(f'--led-rows={height}')
        cmd.append(f'--led-cols={width}')
        
        if hw_config.get('led_show_refresh', False):
            cmd.append('--led-show-refresh')
        
        # Add any additional hardware options from config
        for key, value in hw_config.items():
            if key.startswith('led_') and key not in ['led_show_refresh']:
                if isinstance(value, bool):
                    if value:
                        cmd.append(f'--{key.replace("_", "-")}')
                else:
                    cmd.append(f'--{key.replace("_", "-")}={value}')
    
    else:
        # Terminal mode - use config from YAML
        term_config = flaschen_config['terminal']
        if term_config.get('hd_terminal', True):
            cmd.append('--hd-terminal')
    
    # Add server options
    server_config = flaschen_config['server']
    if server_config.get('layer_timeout'):
        cmd.append(f'--layer-timeout={server_config["layer_timeout"]}')
    
    if server_config.get('daemon', False):
        cmd.append('-d')
    
    print(f"Starting flaschen-taschen server: {' '.join(cmd)}")
    
    try:        
        # Redirect output to prevent terminal control sequences from interfering
        if verbose:
            # Show server output (may interfere with formatting)
            process = subprocess.Popen(cmd)
        else:
            # Start server completely isolated
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=dict(os.environ, TERM='dumb', DISPLAY=''),  # Disable terminal features
                start_new_session=True,  # Start in new session
            )
        
        # Give it a moment to start and check if it's running
        time.sleep(3)
        
        if process.poll() is None:
            print("✓ Flaschen-taschen server started successfully")
            sys.stdout.flush()
            return process
        else:
            # Server exited immediately, something went wrong
            print(f"✗ Failed to start flaschen-taschen server")
            if verbose:
                print("Check the output above for error details")
            else:
                print("Run with --verbose-server to see error details")
            sys.stdout.flush()
            return None
            
    except FileNotFoundError:
        print(f"✗ Server binary not found: {server_path}")
        print("Please compile flaschen-taschen server or provide correct path with --server-path")
        return None
    except Exception as e:
        print(f"✗ Error starting server: {e}")
        return None


def main():
    global server_process
    
    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parser = argparse.ArgumentParser(
        description='Start flaschen-taschen server and MQTT listener',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 simple_start.py                                    # Auto-find server, use terminal
    python3 simple_start.py --server-path ./ft-server          # Specify server path
    python3 simple_start.py --server-path /usr/bin/ft-server   # Use installed server
    python3 simple_start.py --no-terminal                      # Use hardware backend
    
Note: This script starts the flaschen server, then runs the existing app.py

Hardware options are loaded from flaschen_config.yaml. Create this file to 
customize LED matrix settings like GPIO mapping, brightness, etc.
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
    parser.add_argument(
        '--verbose-server',
        action='store_true',
        help='Show server output (may interfere with terminal formatting)'
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
    from app import load_configs
    configs = load_configs()
    flaschen_config_1 = configs.get('flaschen', {})
    width = flaschen_config_1.get('led-columns', 64)
    height = flaschen_config_1.get('led-rows', 64)

    print(f"Display size: {width}x{height}")
    print(f"Backend: {'terminal' if use_terminal else 'hardware'}")
    sys.stdout.flush()
    
    # Load flaschen hardware configuration
    flaschen_config = load_flaschen_config()
    
    # Start the flaschen server
    server_process = start_ft_server(server_path, use_terminal, width, height, flaschen_config, args.verbose_server)
    
    if not server_process:
        print("Failed to start flaschen-taschen server")
        sys.exit(1)
        
    # Give the server a moment to fully initialize
    print("Waiting for server to initialize...")
    sys.stdout.flush()
    time.sleep(5)
    
    try:
        print("\n" + "="*60)
        print("Starting MQTT listener (app.py)...")
        print("="*60)
        sys.stdout.flush()
        
        # Import and run the existing app
        # The app.py module will handle MQTT connection and start its main loop
        from app import main as app_main
        app_main(configs)

        print("✓ MQTT listener started successfully")
        print("\nServices running. Press Ctrl+C to stop.")
        sys.stdout.flush()
        
        # Keep the application running until interrupted
        # This is necessary because MQTT uses background threads
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        # This should be handled by signal_handler now
        pass
    except Exception as e:
        print(f"Error: {e}")
        signal_handler(None, None)  # Clean shutdown


if __name__ == "__main__":
    # Force line buffering for clean output
    sys.stdout.reconfigure(line_buffering=True)
    main()
