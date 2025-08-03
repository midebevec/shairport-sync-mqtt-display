# Service Installation

This directory contains files for setting up the Shairport Sync MQTT to Flaschen Taschen display as a systemd service.

## Files

- `shairport-sync-flaschen.service` - Systemd service file
- `setup-service.sh` - Script to install/uninstall the service
- `README.md` - This file

## Prerequisites

1. **Virtual Environment**: Create a Python virtual environment in the project directory:
   ```bash
   cd /path/to/python-flaschen-taschen
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration**: Create your config file in the project directory:
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your MQTT broker and display settings
   ```
   
   The setup script will copy this to `/etc/shairport-sync-flaschen/config.yaml` for system-wide access.

3. **Flaschen-Taschen Server**: Ensure the ft-server binary is available (compiled or in PATH)

## Installation

Run the setup script as root:

```bash
sudo ./etc/setup-service.sh install
```

This will:
- Create `/etc/shairport-sync-flaschen/` directory
- Copy `config.yaml` to `/etc/shairport-sync-flaschen/config.yaml`
- Install the systemd service file
- Validate prerequisites
- Provide instructions for enabling and starting the service

## Usage

### Enable automatic startup:
```bash
sudo systemctl enable shairport-sync-flaschen
```

### Start the service:
```bash
sudo systemctl start shairport-sync-flaschen
```

### Check service status:
```bash
sudo systemctl status shairport-sync-flaschen
```

### View logs:
```bash
sudo journalctl -u shairport-sync-flaschen -f
```

### Stop the service:
```bash
sudo systemctl stop shairport-sync-flaschen
```

### Disable automatic startup:
```bash
sudo systemctl disable shairport-sync-flaschen
```

## Uninstallation

```bash
sudo ./etc/setup-service.sh uninstall
```

## Service Configuration

The service is configured to:
- Run as root (required for LED matrix hardware access)
- Use the virtual environment Python interpreter
- Start automatically after network and MQTT broker
- Restart automatically if it crashes
- Use hardware backend (`--no-terminal` flag)
- Log to systemd journal

## Troubleshooting

### Service won't start
1. Check that the virtual environment exists and has required packages
2. Verify `/etc/shairport-sync-flaschen/config.yaml` exists and is valid
3. Ensure the ft-server binary is available
4. Check logs: `sudo journalctl -u shairport-sync-flaschen -n 50`

### Permission issues
The service runs as root to access GPIO pins for LED matrices. Ensure file permissions allow root access.

### Network issues
The service waits for network.target and mosquitto.service. If using a different MQTT broker, you may need to modify the service dependencies.
