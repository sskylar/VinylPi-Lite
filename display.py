import importlib
import io
import logging
from urllib.request import urlopen

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

logger = logging.getLogger(__name__)


class WaveshareDisplay:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.epd = None
        self.ready = False

        if not self.enabled:
            return

        module_names = ["TP_lib.epd2in13_V4", "TP_lib.epd2in13_V3"]

        last_error = None
        for module_name in module_names:
            try:
                module = importlib.import_module(module_name)
                epd_cls = getattr(module, "EPD")
                epd = epd_cls()
                epd.init(epd.FULL_UPDATE)
                epd.Clear(0xFF)
                self.epd = epd
                self.ready = True
                break
            except Exception as exc:
                last_error = exc
                continue

        if not self.ready:
            logger.warning("Touch e-Paper HAT requested but no supported driver was found: %s", last_error)
            self.enabled = False

    def _fit_text(self, text, max_chars):
        if not text:
            return ""
        return (text[: max_chars - 1] + "…") if len(text) > max_chars else text

    def _draw_box(self, draw, x, y, w, h, title):
        draw.rectangle([x, y, x + w, y + h], outline=0)
        draw.text((x + 6, y + 4), title, fill=0)

    def _load_album_art(self, network, artist, title):
        if network is None:
            return None

        try:
            track = network.get_track(artist, title)
            image = track.get_cover_image()
            if not image:
                return None
            with urlopen(image) as response:
                return Image.open(io.BytesIO(response.read())).convert("L")
        except Exception as exc:
            logger.warning("Unable to load album art from Last.fm: %s", exc)
            return None

    def show_song(self, artist, title, network=None):
        if not self.enabled or not self.ready:
            return

        if Image is None or ImageDraw is None or ImageFont is None:
            logger.warning("Pillow is required to render to the Touch e-Paper HAT")
            return

        try:
            width, height = 250, 122
            image = Image.new("1", (width, height), 255)
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except Exception:
                font = ImageFont.load_default()

            draw.rectangle([0, 0, width - 1, height - 1], outline=0)
            draw.line([0, 24, width - 1, 24], fill=0)
            draw.line([0, height - 24, width - 1, height - 24], fill=0)

            self._draw_box(draw, 8, 32, 70, 70, "Album")
            self._draw_box(draw, 92, 32, 150, 70, "Art")

            art = self._load_album_art(network, artist, title)
            if art is not None:
                try:
                    art = art.resize((132, 62))
                    image.paste(art, (100, 40))
                except Exception:
                    pass

            draw.text((8, 8), "Now Playing", fill=0, font=font)
            draw.text((90, 8), self._fit_text(artist or "Unknown Artist", 18), fill=0, font=font)
            draw.text((92, 54), self._fit_text(title or "Unknown Track", 20), fill=0, font=font)

            self.epd.display(self.epd.getbuffer(image))
        except Exception as exc:
            logger.warning("Unable to update Waveshare display: %s", exc)

    def clear(self):
        if not self.enabled or not self.ready:
            return

        try:
            self.epd.init(self.epd.FULL_UPDATE)
            self.epd.Clear(0xFF)
        except Exception as exc:
            logger.warning("Unable to clear Waveshare display: %s", exc)

    def close(self):
        if self.epd is not None:
            try:
                self.epd.sleep()
            except Exception:
                pass
            try:
                self.epd.Dev_exit()
            except Exception:
                pass
