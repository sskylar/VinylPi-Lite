import argparse
import sys
import os
import asyncio
import pyaudio
import shutil
import logging
from typing import Tuple, Optional

from vinylpi_lib import (
    CHUNK, FORMAT, CHANNELS, RATE, CHECK_INTERVAL,
    get_usb_audio_device, get_device_channels, get_lastfm_network, clear_console,
    check_song, recognize_song,
    log_song_to_lastfm, list_audio_devices
)

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="VinylPi: Last.fm scrobbler for vinyl records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vinylpi.py                   # Run with default settings
  python vinylpi.py -v                # Run in verbose mode
  python vinylpi.py -d 2              # Use audio device with index 2
  python vinylpi.py -l                # List available audio devices
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-d", "--device", type=int, default=None, help="Select audio device index")
    parser.add_argument("-l", "--list-devices", action="store_true", help="List available audio devices and exit")
    return parser

args = create_parser().parse_args()

# Configure logging
logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main() -> None:
    if args.list_devices:
        list_audio_devices()
        return

    selected_device = args.device if args.device is not None else get_usb_audio_device()
    if selected_device is None:
        logger.error("No USB audio device found. Exiting.")
        return

    logger.info(f"Using audio device index: {selected_device}")

    lastfm_network = get_lastfm_network(logger)

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=get_device_channels(selected_device),
        rate=RATE,
        input=True,
        input_device_index=selected_device,
        frames_per_buffer=CHUNK
    )

    recent_songs = []
    last_logged_song = None

    try:
        while True:
            try:
                logger.info("Starting song detection...")

                song = artist, title = await check_song(stream, args.verbose, logger)

                if artist and title:
                    recent_songs = recent_songs[-2:] + [song]
                    if recent_songs.count(song) >= 2:
                        logger.info(f"Second match: {title} by {artist}")
                        if song == last_logged_song:
                            logger.info(f"Duplicate song detected. Not logging: {title} by {artist}")
                        else:
                            last_logged_song = log_song_to_lastfm(lastfm_network, artist, title, logger)
                        recent_songs = []
                    else:
                        logger.info(f"First match: {title} by {artist}")
                else:
                    logger.info("No valid song detected")
                
                await asyncio.sleep(CHECK_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"An error occurred: {e}", exc_info=True)

    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    asyncio.run(main())
