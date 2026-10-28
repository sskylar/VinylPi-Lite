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

            cover_size = height - 16
            cover_x, cover_y = 8, 8
            text_x = cover_x + cover_size + 12

            draw.rectangle([0, 0, width - 1, height - 1], outline=0)
            draw.rectangle(
                [cover_x, cover_y, cover_x + cover_size - 1, cover_y + cover_size - 1],
                outline=0,
            )
            draw.line([text_x, height // 2, width - 8, height // 2], fill=0)

            art = self._load_album_art(network, artist, title)
            if art is not None:
                try:
                    art = art.resize((cover_size - 2, cover_size - 2))
                    image.paste(art, (cover_x + 1, cover_y + 1))
                except Exception:
                    pass

            draw.text(
                (text_x, 24),
                self._fit_text(artist or "Unknown Artist", 15),
                fill=0,
                font=font,
            )
            draw.text(
                (text_x, 78),
                self._fit_text(title or "Unknown Track", 15),
                fill=0,
                font=font,
            )

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
