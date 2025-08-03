# Flaschen Taschen + MQTT Launcher Script

This directory contains a launcher script to help you start both the flaschen-taschen server and the MQTT listener together.

## Quick Start

Use the `simple_start.py` script to launch everything:

```bash
python3 simple_start.py
```

This will:
1. Find the flaschen-taschen server binary
2. Start it in terminal mode for testing
3. Start the MQTT listener
4. Handle clean shutdown when you press Ctrl+C

## The Launcher Script

### `simple_start.py` (Main Launcher)
- Comprehensive launcher with many options
- Can auto-find the flaschen server binary in common locations
- Supports both terminal and hardware backends
- Excellent error handling and diagnostics
- Configurable via YAML files

## Prerequisites

### Option 1: Use Compiled Flaschen-Taschen Server (Recommended)

1. **Clone and compile flaschen-taschen:**
```bash
# In a separate directory (e.g., ~/projects/)
git clone --recursive https://github.com/hzeller/flaschen-taschen.git
cd flaschen-taschen/server
make FT_BACKEND=terminal
```

2. **Copy the server binary to this directory:**
```bash
cp ft-server /path/to/this/shairport-sync-mqtt-display/python-flaschen-taschen/
```

3. **Run the launcher:**
```bash
cd /path/to/shairport-sync-mqtt-display/python-flaschen-taschen/
python3 simple_start.py
```

### Option 2: Specify Server Path

If you have the server compiled elsewhere:

```bash
python3 simple_start.py --server-path /path/to/flaschen-taschen/server/ft-server
```

## Configuration

The script automatically reads configuration from a single file:

### `config.yaml` (All Settings)
This file contains all configuration including:
- **MQTT broker settings** (host, port, credentials, TLS)
- **Display dimensions** (`led-rows`, `led-columns`) 
- **Server connection** (`server`, `port`)
- **Hardware LED matrix options** (GPIO mapping, brightness, etc.)
- **Terminal display settings**
- **Server options** (layer timeout, daemon mode)

**To create your config:**
```bash
cp config.example.yaml config.yaml
# Edit config.yaml for your setup
```

**Key sections:**
- `mqtt`: MQTT broker connection and topic settings
- `flaschen.server/port`: Connection to flaschen-taschen server  
- `flaschen.hardware`: LED matrix hardware options (GPIO mapping, brightness, etc.)
- `flaschen.terminal`: Terminal display settings
- `flaschen.server`: Server behavior options

## Usage Examples

### Basic usage with auto-detection:
```bash
python3 simple_start.py
```

### Using specific server path:
```bash
python3 simple_start.py --server-path ./ft-server --terminal
```

### Force hardware backend (for LED matrices):
```bash
python3 simple_start.py --server-path ./ft-server --no-terminal
```

### Show server output for debugging:
```bash
python3 simple_start.py --verbose-server
```

## Display Modes

### Terminal Mode (Default)
- Shows the LED matrix display as colored blocks in your terminal
- Great for testing and development
- Requires a modern terminal with 24-bit color support (iTerm2, newer xterm, etc.)

### Hardware Mode  
- Outputs to actual LED matrix hardware
- Requires proper hardware setup and usually root privileges
- Use `--no-terminal` flag

## Stopping the Services

Press `Ctrl+C` to stop both services cleanly. The scripts will:
1. Stop the MQTT listener
2. Terminate the flaschen server
3. Clean up any resources

## Troubleshooting

### "Could not find ft-server binary"
- Make sure you've compiled the flaschen-taschen server
- Check that the binary is in the current directory or provide path with `--server-path`

### "Failed to start flaschen-taschen server"
- Check that port 1337 (or your configured port) is not already in use
- For hardware mode, you may need to run with `sudo`
- Check the server compilation (different backends need different compile flags)

### MQTT connection issues
- Verify your `config.yaml` MQTT settings
- Check that your MQTT broker is running and accessible
- Ensure your shairport-sync is configured to publish to MQTT

### Display not showing
- For terminal mode: Make sure your terminal supports 24-bit color
- For hardware mode: Check physical connections and permissions
- Test the flaschen server independently first

## Testing

To test that everything works:

1. Start the services:
   ```bash
   python3 simple_start.py
   ```

2. In another terminal, send a test image:
   ```bash
   echo "P6\n32 32\n255\n" | cat - <(head -c 3072 /dev/urandom) > /dev/udp/localhost/1337
   ```

3. Play some music via AirPlay to see cover art display

## Original Scripts

- `app.py` - Original MQTT listener (still works independently if server is running)
- Use `simple_start.py` instead of running `app.py` directly for convenience

## For Production

For production deployment:
1. Use `simple_start.py` with `--no-terminal` for hardware display
2. Set up as a systemd service
3. Run with appropriate privileges for hardware access
