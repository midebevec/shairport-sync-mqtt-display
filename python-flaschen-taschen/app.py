#!/usr/bin/env python3

# read README.md for pre-reqs, and customize config.yaml

# to run:
#     python3 app.py

from pathlib import Path
import time

from yaml import safe_load

# https://github.com/hzeller/flaschen-taschen/raw/master/api/python/flaschen.py
import flaschen
import mqtt_listener

CONFIG_FILE = Path("/etc/shairport-sync-flaschen/config.yaml")

def load_configs():
    """Load configuration from YAML file."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Configuration file {CONFIG_FILE} does not exist.")
    
    with CONFIG_FILE.open() as f:
        config = safe_load(f)
    
    print(f"Loaded configuration from {CONFIG_FILE}")
    return config

def main(configs):
    mqtt_config = configs["mqtt"]
    flaschen_config = configs["flaschen"]
    clock_config = configs["clock"]

    flaschen_client = create_flaschen_client(flaschen_config)
    mqtt_listener = create_mqtt_listener(mqtt_config, flaschen_client, clock_config)

    # Connect to MQTT broker
    mqtt_host = mqtt_config["host"]
    mqtt_port = mqtt_config["port"]
    mqtt_listener.connect(mqtt_host, mqtt_port)
    
    # Return the listener to keep it in scope
    return mqtt_listener

def create_flaschen_client(flaschen_config):
    """Create and return a Flaschen client instance."""
    return flaschen.Flaschen(
        flaschen_config.get("server", 'localhost'),
        flaschen_config.get("port", 1337),
        flaschen_config.get("led-columns", 64),
        flaschen_config.get("led-rows", 64)
    )

def create_mqtt_listener(mqtt_config, flaschen_client, clock_config):
    """Create and return an MQTTListener instance."""
    topic_root = mqtt_config.get("topic", "shairport-sync")
    listener = mqtt_listener.MQTTListener(topic_root, flaschen_client, clock_config)
    
    # Set login credentials if provided
    username = mqtt_config.get("username")
    password = mqtt_config.get("password")
    if username:
        listener.set_login(username, password)
    
    # Set TLS configuration if provided
    tls_config = mqtt_config.get("tls")
    if tls_config:
        listener.set_tls(
            ca_certs=tls_config.get("ca_certs_path"),
            certfile=tls_config.get("certfile_path"),
            keyfile=tls_config.get("keyfile_path")
        )

    listener.enable_logger(mqtt_config.get("logger", False))
    
    return listener 

# This is the entry point for the script
if __name__ == "__main__":
    try:
        configs = load_configs()
        mqtt_listener =main(configs)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    else:
        print("MQTT listener started successfully.")

    print("Press Ctrl+C to stop the listener")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down")
        mqtt_listener.disconnect()
        print("Disconnected from MQTT broker")
