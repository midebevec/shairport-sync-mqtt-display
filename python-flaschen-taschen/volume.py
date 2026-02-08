from flaschen import Flaschen
from output import Output
from PIL import Image, ImageDraw
import threading
import time

def rescale(value, old_min, old_max, new_min, new_max):
    """
    Linearly rescale a value from one range to another.

    Args:
        value: The input value to rescale
        old_min: Minimum of original range
        old_max: Maximum of original range
        new_min: Minimum of new range
        new_max: Maximum of new range

    Returns:
        Rescaled value in the new range
    """
    if old_max == old_min:
        raise ValueError("old_max and old_min cannot be the same")

    return new_min + (value - old_min) * (new_max - new_min) / (old_max - old_min)

class Volume(Output):
    VOLUME_PRIORITY = 0
    def __init__(self, config_path, flaschen_client: Flaschen):
        Output.__init__(self, flaschen_client, Volume.VOLUME_PRIORITY)
        self._config_path = config_path
        self._configs = None
        self._cancel_event = None
        self._lock = threading.Lock()

        self._reload_configs()
    
    def _reload_configs(self):
        configs = dict()

        # TODO - Load All Configs
        configs["timeout"] = 5
        configs["width"] = 4

        self._configs = configs

    def _rescale_volume(self, current, min, max):
        if min == max:
            return 0

        return rescale(current, min, max, 0, self.get_size()[1])

    def _create_volume_image(self, volume):

        bar_width = self._configs.get("width", 4)

        width, height = self.get_size()

        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Clamp
        volume = max(0.0, min(float(height), volume))

        full_pixels = int(volume)
        frac = volume - full_pixels

        bar_x1 = width - bar_width
        bar_x2 = width - 1

        BORDER = (40, 40, 40, 255)
        WHITE = (255, 255, 255, 255)

        # No bar -> nothing to draw
        if volume <= 0:
            return image

        # Top of bar
        bar_top = height - int(volume)
        if frac > 0:
            bar_top -= 1

        bar_bottom = height - 1

        # ---- Draw outline only around active bar ----
        draw.rectangle(
            [bar_x1, bar_top, bar_x2, bar_bottom],
            outline=BORDER,
            width=1
        )

        # ---- Draw full pixels ----
        for i in range(full_pixels):
            y = height - 1 - i

            draw.rectangle(
                [bar_x1 + 1, y, bar_x2 - 1, y],
                fill=WHITE
            )

        # ---- Draw fractional pixel ----
        if frac > 0 and full_pixels < height:
            y = height - 1 - full_pixels

            brightness = int(255 * frac)
            color = (brightness, brightness, brightness, 255)

            draw.rectangle(
                [bar_x1 + 1, y, bar_x2 - 1, y],
                fill=color
            )

        return image

    def _display_volume(self, image):
        with self._lock:
            # Cancel any existing timeout
            if self._cancel_event is not None:
                self._cancel_event.set()

            # Create a new cancel event
            self._cancel_event = threading.Event()
            
            # Update Image
            self.send_pil_image(image)

            # Start timeout thread
            thread = threading.Thread(
                target=self._volume_timeout_thread,
                args=(self._cancel_event, self._configs.get("timeout", 5)),
                daemon=True
            )
            thread.start()

    def _volume_timeout_thread(self, cancel_event, timeout = 5):
        # Wait for timeout OR cancellation
        finished = cancel_event.wait(timeout=timeout)

        if not finished:
            # Timeout expired normally
            self.clear_image()

    def update_volume(self, payload):
        # Get Latest Configs
        self._reload_configs()

        # Extrace and scale volume
        volume_tuple = tuple(float(x.strip()) for x in payload.decode().split(","))
        rescaled_volume = self._rescale_volume(volume_tuple[1], volume_tuple[2], volume_tuple[3])

        # Create and display image
        self._display_volume(self._create_volume_image(rescaled_volume))