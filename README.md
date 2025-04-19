# VinylPi-Lite

This is an extremely stripped down version of <https://github.com/powerpcme/VinylPi> aimed to work on a Raspberry Pi Zero (or ancient hardware like my 2011 Mac Mini).

All credit to @powerpcme for creating the original version, which is more feature rich and probably what you should be using (this version is mostly for my personal needs).

In this version, songs are checked 3 times on a rolling basis, if 2 of 3 checks detect the same song, it will get logged to Last.fm. It also has a minimum RMS threshold to avoid Shazaming silence.

It also uses Shazamio's (older) `recognize_song` function with 15 second recording, which I personally get better results with ([see related issue](https://github.com/powerpcme/VinylPi/issues/2)). 

### Ideal gear needed

- Raspberry Pi Zero or whatever you have ([I like this kit](https://amzn.to/42FGDlo))
- USB audio dongle with mic input ([this one is tested](https://a.co/d/51iTuLf))
- RCA to 3.5mm adapter cable ([like this one](https://a.co/d/3N1qybu))
- Depending on your setup an [RCA splitter](https://a.co/d/3O8gUSX) might be helpful

### Dependencies

```
sudo apt-get update
sudo apt-get install python3 python3-pip portaudio19-dev ffmpeg libasound2-dev libopenblas-dev vim -y
```

### Install instructions

First, go to [Last.FM API Create](https://www.last.fm/api/account/create) And fill out the form (You do not have to have a Callback URL or Application Homepage, You can leave that empty).

Save your keys to "lastfm_user_info.json" (see example file) with your username and md5 password hash.

```
pip install -r requirements.txt --break-system-packages

python vinylpi.py -v
```

### Post install

To run as a service first create a service file
```
sudo vim /etc/systemd/system/vinylpi.service
```

Then paste this as an example, Replace the user and script location with your script location

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

Then enable the service to run on boot and start it.

```
sudo systemctl enable vinylpi.service

sudo systemctl start vinylpi.service
```


### Command examples

```
python VinylPi.py -v - Verbose output
python VinylPi.py -l - List avalible devices for use
python VinylPi.py -d 1 - Using the number assigned to the device from the list command, this will set the script to use that device
```