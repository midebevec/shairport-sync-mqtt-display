import flaschen
from PIL import Image
import io

class Output:
    def __init__(self, flaschen_client: flaschen.Flaschen, priority):
        self._flaschen_client = flaschen_client
        self._priority = priority

    def get_size(self):
        return self._flaschen_client.get_size()
    
    def clear_image(self):
        image = Image.new('RGBA', self._flaschen_client.get_size(), (0, 0, 0, 0))
        self._flaschen_client.send_image(image, blank= True, priority= self._priority)

    def send_io_image(self, fileobj: io.BytesIO):
        with Image.open(fileobj) as image:
            if hasattr(fileobj, 'name'):
                print(f"{fileobj.name} {image.format} {image.size} x {image.mode}")
            else:
                print(f"{image.format} {image.size} x {image.mode}")
            image.thumbnail(self.get_size(), Image.LANCZOS)
            background = Image.new('RGBA', self.get_size(), (0, 0, 0, 0))
            background.paste(image, (int((self.get_size()[0] - image.size[0]) / 2), int((self.get_size()[1] - image.size[1]) / 2)))
            self._flaschen_client.send_image(background, blank= False, priority= self._priority)

    def send_pil_image(self, image: Image):
        # TODO - Use matrix size to shrink image if needed
        self._flaschen_client.send_image(image, blank= False, priority= self._priority)