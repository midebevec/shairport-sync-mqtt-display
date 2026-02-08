# -*- mode: python; c-basic-offset: 2; indent-tabs-mode: nil; -*-
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 2.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://gnu.org/licenses/gpl-2.0.txt>

import paho.mqtt.client as mqtt
from shairport_sync_metadata import known_core_metadata_types, known_play_metadata_types
from music import Music
from clock import Clock
from volume import Volume

class MQTTListener:
    """Class to handle MQTT connections and messages."""
    
    _instance_count = 0

    def __init__(self, topic_root, music_client: Music, clock_client: Clock, volume_client: Volume):
        MQTTListener._instance_count += 1
        self.instance_id = MQTTListener._instance_count

        self._music_client = music_client
        self._clock_client = clock_client
        self._volume_client = volume_client
        self._address = None
        
        self.mqtt_client = mqtt.Client()
        self.topic_root = topic_root
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        print(f"MQTTListener #{self.instance_id} initialized for topic root: {topic_root}")

    def start(self):
        self._clock_client.start()
        if self._address:
            self.connect(self._address[0], self._address[1])
        else:
            print("No Host or Port defined for MQTT Connection")

    def stop(self):
        self._clock_client.stop()
        self._music_client.end_session()
        self.disconnect()

    def set_login(self, username, password= None):
        """Set MQTT client login credentials."""
        if password:
            self.mqtt_client.username_pw_set(username, password)
        else:
            self.mqtt_client.username_pw_set(username)
        print(f"MQTT login set for user: {username}")

    def set_tls(self, ca_certs=None, certfile=None, keyfile=None):
        """Set TLS configuration for MQTT client."""
        if ca_certs and certfile and keyfile:
            self.mqtt_client.tls_set(ca_certs=ca_certs, certfile=certfile, keyfile=keyfile)
            print("TLS configuration set for MQTT client")
        else:
            print("No TLS configuration provided, using plain connection")

    def set_address(self, host, port=1883):
        self._address = (host, port)

    def enable_logger(self, logger):
        """Enable MQTT client logging."""
        if logger:
            self.mqtt_client.enable_logger()
            print("MQTT logging enabled")
        else:
            print("MQTT logging not enabled")

    def connect(self, host, port=1883):
        """Connect to the MQTT broker."""
        print(f"MQTT #{self.instance_id} attempting connection to {host}:{port}")
        try:
            self.mqtt_client.connect(host, port)
            self.mqtt_client.loop_start()
            print(f"MQTT #{self.instance_id} loop started")
        except Exception as e:
            print(f"MQTT #{self.instance_id} connection failed: {e}")
            raise

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        print("Disconnected from MQTT broker")

    def on_connect(self, client, userdata, flags, rc):
        """For when MQTT client receives a CONNACK response from the server.

        Adding subscriptions in on_connect() means that they'll be re-subscribed
        for lost/re-connections to MQTT server.
        """

        print(f"MQTT #{self.instance_id} connected with result code {rc} (flags: {flags})")
        
        # Check if this is a reconnection
        if flags.get('session present', False):
            print(f"MQTT #{self.instance_id} reconnected to existing session")
        else:
            print(f"MQTT #{self.instance_id} new session established")

        subtopic_list = list(known_core_metadata_types.keys())
        subtopic_list.extend(list(known_play_metadata_types.keys()))

        for subtopic in subtopic_list:
            topic = self._form_subtopic_topic(subtopic)
            (result, msg_id) = client.subscribe(topic, 0)  # QoS==0 should be fine
            print(f"topic {topic} {msg_id}")  # Print on one line with proper newline

    def on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        if rc != 0:
            print(f"MQTT #{self.instance_id} unexpected disconnection (code: {rc}). Will auto-reconnect.")
        else:
            print(f"MQTT #{self.instance_id} disconnected normally")

    def on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        if message.topic == self._form_subtopic_topic("cover"):
            self._music_client.display_cover_art(message.payload)
        elif message.topic == self._form_subtopic_topic("volume"):
            self._volume_client.update_volume(message.payload)
        elif message.topic == self._form_subtopic_topic("active_end"):
            self._music_client.end_session()
        else:
            print(message.topic, message.payload)
            # Handle other metadata types as needed
            # For example, you could update the display with artist, album, title, etc.
            # This is where you would implement logic to update the display based on the metadata
            # For now, we just print the message payload for debugging purposes

    def _form_subtopic_topic(self, subtopic):
        """Return full topic path given subtopic."""
        topic = self.topic_root + "/" + subtopic
        return topic