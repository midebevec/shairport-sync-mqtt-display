from PIL import Image
from PIL import ImageDraw, ImageFont
import threading
from datetime import datetime
import math
import time
from flaschen import Flaschen
from output import Output

class Clock(Output):
    CLOCK_PRIORITY = 1
    def __init__(self, config_path, flaschen_client: Flaschen):
        Output.__init__(self, flaschen_client, Clock.CLOCK_PRIORITY)
        self._config_path = config_path
        self._thread = None
        self._stop_thread = True
        self._blank_clock = False
        self._configs = None

        self._reload_configs()

    def _reload_configs(self):
        configs = dict()

        # TODO - Load All Configs
        configs["type"] = "analog"
        configs["start_str"] = "08:00"
        configs["end_str"] = "18:00"

        self._configs = configs

    def start(self):
        if self._thread is not None:
            # Thread already running
            # Add Logger in the future
            return
        
        self._stop_thread = False
        self._thread = threading.Thread(target=self._thread_func)
        self._thread.start()

    def stop(self):
        if self._thread and self._thread.is_alive():
            self._stop_thread = True
            self._thread.join()
            self._thread = None
            self.clear_image()

    def blank_clock(self):
        self._blank_clock = True

    def show_clock(self):
        self._blank_clock = False

    def _thread_func(self):
        # Implementation depends on the clock application specifics
        print("Clock application started")

        previous_time = ""
        while not self._stop_thread:
            # Reload Configs
            self._reload_configs()
            # Get system time
            current_dt = datetime.now()
            current_time = current_dt.time().replace(microsecond=0)

            # throttle loop based on previous_time stored as a string or time
            current_time_str = current_time.strftime("%H:%M:%S")
            if current_time_str == previous_time:
                time.sleep(0.2)
                continue
            previous_time = current_time_str

            start_time = datetime.strptime(self._configs["start_str"], "%H:%M").time()
            end_time = datetime.strptime(self._configs["end_str"], "%H:%M").time()

            # handle midnight wrap
            if start_time <= end_time:
                in_window = start_time <= current_time <= end_time
            else:
                in_window = (current_time >= start_time) or (current_time <= end_time)

            if not in_window or self._blank_clock:
                self.clear_image()
                time.sleep(1)
                continue
                
            # Create time image
            image = self._create_clock_image(current_time_str, self.get_size())
            # Send time image to display
            try:
                self.send_pil_image(image)
            except Exception as e:
                print(f"Error sending clock image: {e}")
        print("Clock application stopped")


    def _create_clock_image(self, current_time_str, matrix_size=(64, 64)):
        clock_type = self._configs.get("type", "analog")
        if clock_type is "analog":
            return self._create_analog_clock_image(current_time_str, matrix_size)
        elif clock_type is "digital":
            return self._create_digital_clock_image(current_time_str, matrix_size)

    def _create_digital_clock_image(self, current_time_str, matrix_size=(64, 64)):
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

    def _create_analog_clock_image(self, current_time_str, matrix_size=(64, 64)):
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