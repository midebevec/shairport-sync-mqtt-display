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

import time as time_module
from datetime import datetime
import threading
from PIL import Image
import paho.mqtt.client as mqtt
import io
from PIL import ImageDraw, ImageFont
import math
from PIL import ImageDraw

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
    
def createTimeImage(current_time_str, matrix_size=(64, 64)):
    """Create an image displaying the current time."""

    # Create a blank image with transparent background
    image = Image.new('RGBA', matrix_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Load a TrueType font
    font_size = 12
    font = ImageFont.truetype("truetype/dejavu/DejaVuSansMono.ttf", font_size)

    # Use Pillow >= 8.0 textbbox to measure text and center it
    bbox = draw.textbbox((0, 0), current_time_str, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    position = ((matrix_size[0] - text_width) // 2, (matrix_size[1] - text_height) // 2)

    # Draw the time string onto the image
    draw.text(position, current_time_str, font=font, fill=(255, 255, 255, 255))

    return image

def createAnalogClockImage(current_time_str, matrix_size=(64, 64)):
    """Create an analog clock image: black background, white hands."""

    # Parse time string "HH:MM:SS", fall back to now() on parse error
    try:
        h, m, s = map(int, current_time_str.split(':'))
    except Exception:
        now = datetime.now()
        h, m, s = now.hour, now.minute, now.second

    # Use a higher-resolution canvas and downscale for smoother rendering
    scale = 4
    w, h_px = matrix_size[0] * scale, matrix_size[1] * scale
    img = Image.new('RGBA', (w, h_px), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    cx, cy = w / 2.0, h_px / 2.0
    radius = min(cx, cy) * 0.9

    # Outer rim
    rim_width = max(1, scale // 1)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                    outline=(255, 255, 255, 255), width=rim_width)

    # Minute and hour ticks
    for i in range(60):
        angle = (i / 60.0) * 2 * math.pi - math.pi / 2
        outer_x = cx + radius * math.cos(angle)
        outer_y = cy + radius * math.sin(angle)
        if i % 5 == 0:
            inner_r = radius * 0.80
            tick_w = max(1, scale // 1)
        else:
            inner_r = radius * 0.88
            tick_w = max(1, scale // 3)
        inner_x = cx + inner_r * math.cos(angle)
        inner_y = cy + inner_r * math.sin(angle)
        draw.line((inner_x, inner_y, outer_x, outer_y), fill=(255, 255, 255, 255), width=tick_w)

    # Compute hand angles
    sec_angle = (s / 60.0) * 2 * math.pi - math.pi / 2
    min_angle = ((m + s / 60.0) / 60.0) * 2 * math.pi - math.pi / 2
    hour_angle = (((int(current_time_str.split(':')[0]) % 12) if ':' in current_time_str else (datetime.now().hour % 12)) + m / 60.0) / 12.0 * 2 * math.pi - math.pi / 2

    # Hand lengths
    hour_len = radius * 0.55
    min_len = radius * 0.75
    sec_len = radius * 0.90

    # Draw hour hand (thick)
    draw.line((cx, cy, cx + hour_len * math.cos(hour_angle), cy + hour_len * math.sin(hour_angle)),
                fill=(255, 255, 255, 255), width=max(1, int(scale * 2)))

    # Draw minute hand
    draw.line((cx, cy, cx + min_len * math.cos(min_angle), cy + min_len * math.sin(min_angle)),
                fill=(255, 255, 255, 255), width=max(1, int(scale * 1.5)))

    # Draw second hand (thin)
    draw.line((cx, cy, cx + sec_len * math.cos(sec_angle), cy + sec_len * math.sin(sec_angle)),
                fill=(255, 255, 255, 255), width=max(1, int(scale * 0.6)))

    # Center cap
    cap_r = max(1, int(scale * 1.5))
    draw.ellipse((cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r), fill=(255, 255, 255, 255))

    # Downscale to target size with antialiasing
    img = img.resize(matrix_size, Image.LANCZOS)
    return img

class MQTTListener:
    """Class to handle MQTT connections and messages."""
    
    _instance_count = 0
    _clock_thread = None
    _stop_clock_thread = False

    def __init__(self, topic_root, flaschen_client: Flaschen, clock_config):
        MQTTListener._instance_count += 1
        self.instance_id = MQTTListener._instance_count
        
        self.mqtt_client = mqtt.Client()
        self.flaschen_client = flaschen_client
        self.topic_root = topic_root
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.clock_config = clock_config
        self.clock_update_func = createAnalogClockImage if clock_config.get("type", "digital") == "analog" else createTimeImage
        print(f"MQTTListener #{self.instance_id} initialized for topic root: {topic_root}")

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

        self.delegate_to_clock()

    def on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        if rc != 0:
            print(f"MQTT #{self.instance_id} unexpected disconnection (code: {rc}). Will auto-reconnect.")
        else:
            print(f"MQTT #{self.instance_id} disconnected normally")

        self.reclaim_from_clock()

    def on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        if message.topic == self._form_subtopic_topic("cover"):
            self.reclaim_from_clock()
            self.process_cover_art(message)
        elif message.topic == self._form_subtopic_topic("active_end"):
            self.clear_matrix()
            self.delegate_to_clock()
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
    
    def delegate_to_clock(self):
        """Delegate display to clock application."""
        # Implementation depends on the clock application specifics
        if not self.clock_config.get("enabled", False):
            return
        self._stop_clock_thread = False
        self._clock_thread = threading.Thread(target=self._run_clock_application)
        self._clock_thread.start()

    def reclaim_from_clock(self):
        """Reclaim display from clock application."""
        # Implementation depends on the clock application specifics
        if not self.clock_config.get("enabled", False):
            return
        if self._clock_thread and self._clock_thread.is_alive():
            print("Reclaiming display from clock application")
            # Logic to stop the clock application would go here
            self._stop_clock_thread = True
            self._clock_thread.join()
            self._clock_thread = None
            self.clear_matrix()
        else:
            print("No active clock application to reclaim from")
            self._clock_thread = None
            self._stop_clock_thread = False
            self.clear_matrix()

    def _run_clock_application(self):
        """Clock application logic."""
        # Implementation depends on the clock application specifics
        print("Clock application started")

        # parse configured window ("HH:MM")
        start_str = self.clock_config.get("time_window", {}).get("start")
        end_str = self.clock_config.get("time_window", {}).get("end")
        if start_str is None or end_str is None:
            print("Clock application time window not properly configured, exiting clock application")
            return

        previous_time = ""
        while not self._stop_clock_thread:
            # Get system time
            current_dt = datetime.now()
            current_time = current_dt.time().replace(microsecond=0)

            # throttle loop based on previous_time stored as a string or time
            current_time_str = current_time.strftime("%H:%M:%S")
            if current_time_str == previous_time:
                time_module.sleep(0.2)
                continue
            previous_time = current_time_str

            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()

            # handle midnight wrap
            if start_time <= end_time:
                in_window = start_time <= current_time <= end_time
            else:
                in_window = (current_time >= start_time) or (current_time <= end_time)

            if not in_window:
                self.clear_matrix()
                time_module.sleep(1)
                continue
                
            # Create time image
            image = self.clock_update_func(current_time_str, self.flaschen_client.get_size())
            # Send time image to display
            try:
                self.flaschen_client.send_image(image)
            except Exception as e:
                print(f"Error sending clock image: {e}")
        print("Clock application stopped")