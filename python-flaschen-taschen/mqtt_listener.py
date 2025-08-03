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

from PIL import Image
import paho.mqtt.client as mqtt
import io
import os
import ssl

from shairport_sync_metadata import known_core_metadata_types, known_play_metadata_types
from flaschen import Flaschen

def createMatrixImage(fileobj, matrix_size=(64, 64)):
    with Image.open(fileobj) as image:
        if hasattr(fileobj, 'name'):
            print(f"{fileobj.name} {image.format} {image.size} x {image.mode}")
        else:
            print(f"{image.format} {image.size} x {image.mode}")
        image.thumbnail(matrix_size, Image.LANCZOS)
        background = Image.new('RGBA', matrix_size, (0, 0, 0, 0))
        background.paste(image, (int((matrix_size[0] - image.size[0]) / 2), int((matrix_size[1] - image.size[1]) / 2)))
        return background

class MQTTListener:
    """Class to handle MQTT connections and messages."""

    def __init__(self, topic_root, flaschen_client: Flaschen):
        self.mqtt_client = mqtt.Client()
        self.flaschen_client = flaschen_client
        self.topic_root = topic_root
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    def __del__(self):
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

    def enable_logger(self, logger):
        """Enable MQTT client logging."""
        if logger:
            self.mqtt_client.enable_logger()
            print("MQTT logging enabled")
        else:
            print("MQTT logging not enabled")

    def connect(self, host, port=1883):
        """Connect to the MQTT broker."""
        self.mqtt_client.connect(host, port)
        self.mqtt_client.loop_start()

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

        # print("Connected with result code {}".format(rc))

        subtopic_list = list(known_core_metadata_types.keys())
        subtopic_list.extend(list(known_play_metadata_types.keys()))

        for subtopic in subtopic_list:
            topic = self._form_subtopic_topic(subtopic)
            (result, msg_id) = client.subscribe(topic, 0)  # QoS==0 should be fine
            print(f"topic {topic} {msg_id}")  # Print on one line with proper newline

    def on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        if message.topic == self._form_subtopic_topic("cover"):
            self.process_cover_art(message)
        elif message.topic == self._form_subtopic_topic("active_end"):
            self.clear_matrix() 
        else:
            print(message.topic, message.payload)
            # Handle other metadata types as needed
            # For example, you could update the display with artist, album, title, etc.
            # This is where you would implement logic to update the display based on the metadata
            # For now, we just print the message payload for debugging purposes

    def process_cover_art(self, message):
        """Process cover art messages."""
        if message.payload:
            print(message.topic, len(message.payload))
            try:
                image = createMatrixImage(io.BytesIO(message.payload), self.flaschen_client.get_size())
                self.flaschen_client.send_image(image)
            except Exception as e:
                print(f"Error processing cover art: {e}")
                self.clear_matrix()
        else:
            print("No cover art received")
            self.clear_matrix()

    def clear_matrix(self):
        """Clear the matrix display when inactive."""
        image = Image.new('RGBA', self.flaschen_client.get_size(), (0, 0, 0, 0))
        self.flaschen_client.send_image(image)

    def _form_subtopic_topic(self, subtopic):
        """Return full topic path given subtopic."""
        topic = self.topic_root + "/" + subtopic
        return topic