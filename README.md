# VinylPi-Lite

This is an extremely stripped down version of <https://github.com/powerpcme/VinylPi> aimed to work on a Raspberry Pi Zero (or ancient hardware like my 2011 Mac Mini).

All credit to [@powerpcme](https://github.com/powerpcme) for creating the original version, which is more feature rich and probably what you should be using (this version is mostly for my personal needs).

In this version, songs are checked 3 times on a rolling basis, if 2 of 3 checks detect the same song, it will get logged to Last.fm. It also has a minimum RMS threshold to avoid Shazaming silence.

It also uses Shazamio's (older) `recognize_song` function with 15 second recording, which I personally get better results with ([see related issue](https://github.com/powerpcme/VinylPi/issues/2)). 

### Ideal gear needed

- Raspberry Pi Zero or whatever you have ([I like this kit](https://amzn.to/42FGDlo))
- USB audio dongle with mic input ([this one is tested](https://a.co/d/51iTuLf))
- A splitter like this [RCA-to-3.5mm piggyback](https://amzn.to/442hPpP) might be helpful

### Dependencies

```
sudo apt-get update
sudo apt-get install python3 python3-pip portaudio19-dev ffmpeg libasound2-dev libopenblas-dev vim -y
```

### Install instructions

First, go to [Last.FM API Create](https://www.last.fm/api/account/create) and fill out the form (can leave Callback URL and Application Homepage empty).

Save your keys to "lastfm_user_info.json" (see example file) with your username and password hash (just an MD5 of your password).

```
pip install -r requirements.txt --break-system-packages

python vinylpi.py -v
```

### Post install

To run as a service first create a service file:
```
sudo vim /etc/systemd/system/vinylpi.service
```

Then paste this as an example:

```
[Unit]
Description=VinylPi
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/vinylpi/vinylpi.py -v
WorkingDirectory=/home/vinylpi/
StandardOutput=inherit
StandardError=inherit
Restart=always
TimeoutStartSec=300
TimeoutStopSec=300
StartLimitBurst=3
StartLimitIntervalSec=300
User=vinylpi

[Install]
WantedBy=multi-user.target
```

Then enable the service to run on boot and start it:

```
sudo systemctl enable vinylpi.service

sudo systemctl start vinylpi.service
```

To view the log while running as a service:

```
journalctl --follow -u vinylpi.service
```

### Command examples

```
python VinylPi.py -v - Verbose output
python VinylPi.py -l - List avalible devices for use
python VinylPi.py -d 1 - Using the number assigned to the device from the list command, this will set the script to use that device
```