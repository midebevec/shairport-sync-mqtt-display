#!/usr/bin/env python3

"""
Unified starter for Flaschen Taschen server and MQTT listener.

This script starts both:
1. A flaschen-taschen server (either terminal-based for testing or LED matrix for production)
2. The MQTT listener that receives shairport-sync metadata and displays cover art

Requirements:
- For terminal display: No additional requirements (pure Python implementation)
- For external server: flaschen-taschen compiled server binary

Usage:
    python3 start_all.py [--mode terminal|external] [--external-server-path PATH]

Modes:
    terminal: Uses a built-in Python terminal display server (default for testing)
    external: Starts an external flaschen-taschen server binary (for production)
"""

import argparse
import subprocess
import sys
import threading
import time
import signal
import socket
from pathlib import Path

# Import the existing MQTT app functionality
from app import (
    config, MQTT_CONF, FLASCHEN_CONF, FLASCHEN_SERVER, FLASCHEN_PORT,
    FLASCHEN_ROWS, FLASCHEN_COLS, FLASCHEN_SIZE, DEFAULT_IMAGE,
    mqttc, on_connect, on_message, createMatrixImage, flaschenSendThumbnailImage
)
import flaschen


class TerminalFlaschenServer:
    """A simple terminal-based Flaschen Taschen server implementation."""
    
    def __init__(self, width=32, height=32, port=1337):
        self.width = width
        self.height = height
        self.port = port
        self.running = False
        self.server_socket = None
        self.display_buffer = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]
        
    def start(self):
        """Start the terminal server in a separate thread."""
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        print(f"Terminal Flaschen server started on port {self.port}")
        print(f"Display size: {self.width}x{self.height}")
        
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
            
    def _run_server(self):
        """Run the UDP server."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            print(f"UDP server listening on port {self.port}")
            
            while self.running:
                try:
                    data, addr = self.server_socket.recvfrom(65535)
                    self._process_packet(data)
                except socket.timeout:
                    continue
                except OSError:
                    break
                    
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
                
    def _process_packet(self, data):
        """Process incoming flaschen packet and update terminal display."""
        try:
            # Parse the header to find where pixel data starts
            data_str = data.decode('latin-1')
            lines = data_str.split('\n')
            
            if len(lines) < 3 or lines[0] != 'P6':
                return
                
            # Parse dimensions
            dimensions = lines[1].split()
            if len(dimensions) != 2:
                return
            width, height = int(dimensions[0]), int(dimensions[1])
            
            # Look for the '255' line that ends the header
            header_lines = 0
            for i, line in enumerate(lines):
                if line == '255':
                    header_lines = i + 1
                    break
            else:
                return
                
            # Calculate where pixel data starts
            header_text = '\n'.join(lines[:header_lines]) + '\n'
            header_len = len(header_text.encode('latin-1'))
            
            # Extract pixel data
            pixel_data = data[header_len:]
            
            # Update display buffer
            for y in range(min(height, self.height)):
                for x in range(min(width, self.width)):
                    pixel_offset = (y * width + x) * 3
                    if pixel_offset + 2 < len(pixel_data):
                        r = pixel_data[pixel_offset]
                        g = pixel_data[pixel_offset + 1]
                        b = pixel_data[pixel_offset + 2]
                        self.display_buffer[y][x] = (r, g, b)
                        
            # Update terminal display
            self._update_terminal_display()
            
        except Exception as e:
            print(f"Error processing packet: {e}")
            
    def _update_terminal_display(self):
        """Update the terminal display with current buffer."""
        # Clear screen and move cursor to top
        print('\033[2J\033[H', end='')
        
        # Print the display
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = self.display_buffer[y][x]
                # Use 24-bit color escape sequence
                print(f'\033[48;2;{r};{g};{b}m  \033[0m', end='')
            print()  # New line after each row
            
        # Print some info
        print(f"\nFlaschen Taschen Terminal Display ({self.width}x{self.height})")
        print("Press Ctrl+C to stop")
        sys.stdout.flush()


def start_external_server(server_path, width, height, backend='terminal'):
    """Start an external flaschen-taschen server."""
    cmd = [
        str(server_path),
        f'-D{width}x{height}',
    ]
    
    if backend == 'terminal':
        cmd.append('--hd-terminal')
        
    print(f"Starting external flaschen server: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if it started successfully
        if process.poll() is None:
            print("External flaschen server started successfully")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"Failed to start external server:")
            print(f"stdout: {stdout}")
            print(f"stderr: {stderr}")
            return None
            
    except FileNotFoundError:
        print(f"External server not found at: {server_path}")
        print("Please compile the flaschen-taschen server or provide correct path")
        return None
    except Exception as e:
        print(f"Error starting external server: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Start Flaschen Taschen server and MQTT listener')
    parser.add_argument(
        '--mode', 
        choices=['terminal', 'external'], 
        default='terminal',
        help='Server mode: terminal (built-in Python) or external (compiled binary)'
    )
    parser.add_argument(
        '--external-server-path',
        type=Path,
        help='Path to external flaschen-taschen server binary'
    )
    parser.add_argument(
        '--server-backend',
        choices=['terminal', 'rgb-matrix'],
        default='terminal',
        help='Backend for external server (terminal or rgb-matrix)'
    )
    
    args = parser.parse_args()
    
    # Get display dimensions from config
    width = FLASCHEN_COLS
    height = FLASCHEN_ROWS
    port = FLASCHEN_PORT
    
    print(f"Starting Flaschen Taschen display system...")
    print(f"Display size: {width}x{height}")
    print(f"Port: {port}")
    print(f"Mode: {args.mode}")
    
    # Start the appropriate server
    server_process = None
    terminal_server = None
    
    try:
        if args.mode == 'terminal':
            # Start built-in Python terminal server
            terminal_server = TerminalFlaschenServer(width, height, port)
            terminal_server.start()
            
        elif args.mode == 'external':
            # Start external server
            if not args.external_server_path:
                print("External server path required for external mode")
                print("Use --external-server-path /path/to/ft-server")
                sys.exit(1)
                
            server_process = start_external_server(
                args.external_server_path, 
                width, 
                height, 
                args.server_backend
            )
            
            if not server_process:
                print("Failed to start external server")
                sys.exit(1)
        
        # Give server time to start
        time.sleep(1)
        
        # Test connection to flaschen server
        print("Testing connection to flaschen server...")
        try:
            test_client = flaschen.Flaschen(FLASCHEN_SERVER, FLASCHEN_PORT, width, height)
            # Send a test pattern
            for x in range(min(5, width)):
                for y in range(min(5, height)):
                    test_client.set(x, y, (50, 50, 50))
            test_client.send()
            print("Successfully connected to flaschen server")
        except Exception as e:
            print(f"Warning: Could not test flaschen connection: {e}")
        
        # Start MQTT client
        print("\nStarting MQTT listener...")
        print(f"MQTT broker: {MQTT_CONF['host']}:{MQTT_CONF['port']}")
        print(f"MQTT topic root: {MQTT_CONF['topic']}")
        
        # Register MQTT callbacks (already set in imported app module)
        mqttc.loop_start()
        
        print("\nAll services started successfully!")
        print("Listening for shairport-sync metadata...")
        print("Press Ctrl+C to stop all services")
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            
    except KeyboardInterrupt:
        print("\nShutting down...")
        
    finally:
        # Clean up
        print("Stopping services...")
        
        if mqttc:
            mqttc.loop_stop()
            mqttc.disconnect()
            
        if terminal_server:
            terminal_server.stop()
            
        if server_process:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                
        print("All services stopped")


if __name__ == "__main__":
    main()
