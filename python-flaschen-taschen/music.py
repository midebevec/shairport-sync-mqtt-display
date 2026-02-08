from flaschen import Flaschen
from output import Output
import io

class Music(Output):
    MUSIC_PRIORITY = 0
    def __init__(self, config_path, flaschen_client: Flaschen):
        Output.__init__(self, flaschen_client, Music.MUSIC_PRIORITY)
        self._config_path = config_path
        self._configs = None

        self._reload_configs()
    
    def _reload_configs(self):
        configs = dict()

        # TODO - Load All Configs

        self._configs = configs

    def display_cover_art(self, payload):
        self.send_io_image(io.BytesIO(payload))

    def end_session(self):
        self.clear_image()