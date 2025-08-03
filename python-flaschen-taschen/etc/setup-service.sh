#!/bin/bash

# Shairport Sync MQTT to Flaschen Taschen Service Setup Script
# This script sets up the systemd service for automatic startup

set -e  # Exit on any error

SERVICE_NAME="shairport-sync-flaschen"
SERVICE_FILE="shairport-sync-flaschen.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SYSTEMD_DIR="/etc/systemd/system"
CONFIG_DIR="/etc/shairport-sync-flaschen"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

echo "=== Shairport Sync Flaschen Taschen Service Setup ==="
echo "Project directory: $PROJECT_DIR"
echo "Service file: $SCRIPT_DIR/$SERVICE_FILE"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   echo "Usage: sudo $0 [install|uninstall|status]"
   exit 1
fi

# Function to install the service
install_service() {
    echo "Installing $SERVICE_NAME service..."
    
    # Check if the simple_start.py exists
    if [[ ! -f "$PROJECT_DIR/simple_start.py" ]]; then
        echo "Error: simple_start.py not found in $PROJECT_DIR"
        exit 1
    fi
    
    # Check if virtual environment exists
    if [[ ! -f "$PROJECT_DIR/venv/bin/python" ]]; then
        echo "Warning: Virtual environment not found at $PROJECT_DIR/venv"
        echo "Please create a virtual environment first:"
        echo "  cd $PROJECT_DIR"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check if config.yaml exists in project directory
    if [[ ! -f "$PROJECT_DIR/config.yaml" ]]; then
        echo "Warning: config.yaml not found in project directory"
        echo "Please create it first:"
        echo "  cp $PROJECT_DIR/config.example.yaml $PROJECT_DIR/config.yaml"
        echo "  # Edit config.yaml with your settings"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Create system config directory
    echo "Creating system config directory: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR"
    
    # Copy config file to system location if it exists
    if [[ -f "$PROJECT_DIR/config.yaml" ]]; then
        echo "Copying config.yaml to system location..."
        cp "$PROJECT_DIR/config.yaml" "$CONFIG_FILE"
        chmod 644 "$CONFIG_FILE"
        echo "✓ Config file installed at $CONFIG_FILE"
    else
        echo "Warning: No config.yaml found to copy"
        echo "You'll need to create $CONFIG_FILE manually"
    fi
    
    # Create a customized service file with correct paths
    echo "Creating service file with current paths..."
    sed -e "s|/home/midebevec/projects/shairport-sync-mqtt-display/python-flaschen-taschen|$PROJECT_DIR|g" \
        "$SCRIPT_DIR/$SERVICE_FILE" > "/tmp/$SERVICE_FILE"
    
    # Copy service file to systemd directory
    cp "/tmp/$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_FILE"
    
    # Set correct permissions
    chmod 644 "$SYSTEMD_DIR/$SERVICE_FILE"
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    echo "✓ Service installed successfully"
    echo ""
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "Configuration file: $CONFIG_FILE"
    else
        echo "⚠️  Remember to create configuration file: $CONFIG_FILE"
    fi
    echo ""
    echo "To enable automatic startup:"
    echo "  sudo systemctl enable $SERVICE_NAME"
    echo ""
    echo "To start the service now:"
    echo "  sudo systemctl start $SERVICE_NAME"
    echo ""
    echo "To check service status:"
    echo "  sudo systemctl status $SERVICE_NAME"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u $SERVICE_NAME -f"
}

# Function to uninstall the service
uninstall_service() {
    echo "Uninstalling $SERVICE_NAME service..."
    
    # Stop and disable service if it exists
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "Stopping service..."
        systemctl stop "$SERVICE_NAME"
    fi
    
    if systemctl is-enabled --quiet "$SERVICE_NAME"; then
        echo "Disabling service..."
        systemctl disable "$SERVICE_NAME"
    fi
    
    # Remove service file
    if [[ -f "$SYSTEMD_DIR/$SERVICE_FILE" ]]; then
        rm "$SYSTEMD_DIR/$SERVICE_FILE"
        echo "✓ Service file removed"
    fi
    
    # Ask if user wants to remove config directory
    if [[ -d "$CONFIG_DIR" ]]; then
        echo ""
        echo "Configuration directory $CONFIG_DIR still exists."
        read -p "Remove it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$CONFIG_DIR"
            echo "✓ Configuration directory removed"
        else
            echo "Configuration directory preserved"
        fi
    fi
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    echo "✓ Service uninstalled successfully"
}

# Function to show service status
show_status() {
    echo "=== Service Status ==="
    if [[ -f "$SYSTEMD_DIR/$SERVICE_FILE" ]]; then
        echo "Service file: Installed"
        echo ""
        systemctl status "$SERVICE_NAME" --no-pager || true
        echo ""
        echo "=== Recent Logs ==="
        journalctl -u "$SERVICE_NAME" --no-pager -n 20 || true
    else
        echo "Service file: Not installed"
        echo "Run 'sudo $0 install' to install the service"
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install    Install the systemd service and copy config to /etc"
    echo "  uninstall  Remove the systemd service (optionally remove config)"
    echo "  status     Show service status and recent logs"
    echo "  help       Show this help message"
    echo ""
    echo "The install command will:"
    echo "  - Copy config.yaml to $CONFIG_FILE"
    echo "  - Install systemd service file"
    echo "  - Set up proper permissions"
    echo ""
    echo "Examples:"
    echo "  sudo $0 install"
    echo "  sudo $0 status"
    echo "  sudo $0 uninstall"
}

# Main script logic
case "${1:-install}" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Error: Unknown command '$1'"
        echo ""
        show_help
        exit 1
        ;;
esac
