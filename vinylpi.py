import argparse
import asyncio
import audioop
import io
import json
import logging
import numpy as np
import os
import pyaudio
import pylast
import time
import wave
from shazamio import Shazam

CHUNK = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

MINIMUM_RMS = 100

RECORD_SECONDS = 15
CHECK_INTERVAL = 5
USER_INFO_FILE = "lastfm_user_info.json"

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
  python vinylpi.py -m                # Display sound meter
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-d", "--device", type=int, default=None, help="Select audio device index")
    parser.add_argument("-l", "--list-devices", action="store_true", help="List available audio devices and exit")
    parser.add_argument("-m", "--meter", action="store_true", help="Show sound meter for selected device")
    return parser

args = create_parser().parse_args()

# Configure logging
logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def store_user_info():
    if not os.path.exists(USER_INFO_FILE):
        api_key = input("Enter your Last.fm API key: ")
        api_secret = input("Enter your Last.fm API secret: ")
        username = input("Enter your Last.fm username: ")
        password = input("Enter your Last.fm password: ")
        password_hash = pylast.md5(password)

        user_info = {
            "api_key": api_key,
            "api_secret": api_secret,
            "username": username,
            "password_hash": password_hash
        }

        with open(USER_INFO_FILE, "w") as f:
            json.dump(user_info, f)
        return user_info
    else:
        return load_user_info()

def load_user_info():
    if os.path.exists(USER_INFO_FILE):
        with open(USER_INFO_FILE, "r") as f:
            return json.load(f)
    else:
        return store_user_info()

def list_audio_devices():
    p = pyaudio.PyAudio()
    device_count = p.get_device_count()
    for i in range(device_count):
        device_info = p.get_device_info_by_index(i)
        if device_info["maxInputChannels"] > 0:
            device_name = device_info["name"]
            print(f"Device Index {i}: {device_name}")
    p.terminate()

def get_usb_audio_device():
    p = pyaudio.PyAudio()
    usb_device = None
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if "usb" in device_info["name"].lower() and device_info["maxInputChannels"] > 0:
            usb_device = i
            break
    p.terminate()
    return usb_device

def get_device_channels(i):
    p = pyaudio.PyAudio()
    device_info = p.get_device_info_by_index(i)
    return device_info["maxInputChannels"]

def get_lastfm_network(logger):
    try:
        user_info = load_user_info()
        return pylast.LastFMNetwork(
            api_key=user_info["api_key"],
            api_secret=user_info["api_secret"],
            username=user_info["username"],
            password_hash=user_info["password_hash"]
        )
    except Exception as e:
        logger.error(f"Error logging into Last.fm: {e}")

def log_song_to_lastfm(network, artist, title, logger):
    try:
        network.scrobble(artist=artist, title=title, timestamp=int(time.time()))
        logger.info(f"Logged to Last.fm: {title} by {artist}")
        return (artist, title)
    except Exception as e:
        logger.error(f"Error logging to Last.fm: {e}")

async def recognize_song(audio_data, verbose, logger):
    shazam = Shazam()
    with io.BytesIO() as wav_file:
        with wave.open(wav_file, 'wb') as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wav.setframerate(RATE)
            wav.writeframes(audio_data)
        wav_data = wav_file.getvalue()
    
    try:
        result = await shazam.recognize_song(wav_data)
        if result and 'track' in result:
            return result['track']['subtitle'], result['track']['title']
    except Exception as e:
        if verbose:
            logger.error(f"Error in song recognition: {e}")
    return None, None

async def check_song(audio_stream, verbose, logger):
    audio_stream.stop_stream(), audio_stream.start_stream()

    frames = []
    rms = []
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = audio_stream.read(CHUNK, exception_on_overflow=False)
        rms_val = audioop.rms(data, 2)
        rms.append(rms_val)
        frames.append(data)

    audio_data = b''.join(frames)

    # convert stereo to mono
    p = pyaudio.PyAudio()
    device_info = p.get_default_input_device_info()
    if device_info['maxInputChannels'] > 1:
        audio_stereo = np.frombuffer(audio_data, dtype=np.int16).reshape(-1, 2)
        audio_data = audio_stereo.mean(axis=1).astype(np.int16)
    
    # check data for silence
    avg_rms = sum(rms) / len(rms)
    logger.debug(f"Average RMS: {avg_rms}")

    if avg_rms > MINIMUM_RMS:
        return await recognize_song(audio_data, verbose, logger)
    else:
        if verbose:
            logger.info("Too quiet, skipping detection")
        return None, None

def display_sound_meter(audio_stream, max_rms=7071, bar_width=20):
    while True:
        data = audio_stream.read(CHUNK, exception_on_overflow=False)
        rms = audioop.rms(data, 2)
        rms = max(0.0, min(rms, max_rms))
        level = int((rms / max_rms) * (bar_width - 1)) + 1
        print('\r' + '■' * level + '□' * (bar_width - level), f"{rms:>4} RMS", end='')
    print('')

async def main() -> None:
    if args.list_devices:
        list_audio_devices()
        return

    selected_device = args.device if args.device is not None else get_usb_audio_device()
    if selected_device is None:
        logger.error("No USB audio device found. Exiting.")
        return

    logger.info(f"Using audio device index: {selected_device}")

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=get_device_channels(selected_device),
        rate=RATE,
        input=True,
        input_device_index=selected_device,
        frames_per_buffer=CHUNK
    )

    if args.meter:
        display_sound_meter(stream)
        return
    
    lastfm_network = get_lastfm_network(logger)

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
        stream.stop_stream(), stream.close(), p.terminate()

if __name__ == "__main__":
    asyncio.run(main())
