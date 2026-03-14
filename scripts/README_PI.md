# Raspberry Pi Voice Satellite Setup

To run the Voice Satellite on a Raspberry Pi, you need to install system-level audio dependencies before installing the Python libraries.

## 1. Install System Dependencies

Run these commands in your Pi terminal:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv portaudio19-dev libasound2-dev
```

- `portaudio19-dev`: Required for `sounddevice` and `pyaudio`.
- `libasound2-dev`: ALSA development headers.

## 2. Set up Python Environment (Recommended)

It is best practice to use a virtual environment:

```bash
cd ~/bmo_client  # Or wherever you put the scripts
python3 -m venv venv
source venv/bin/activate
```

## 3. Install Python Requirements

If you copied `requirements_satellite.txt`:

```bash
pip install -r requirements_satellite.txt
```

If you didn't copy the requirements file, run:

```bash
pip install sounddevice numpy requests openwakeword soundfile
```

## 4. Run the Client

Make sure to configure the `HOST_IP` in `voice_satellite.py` to point to your PC's IP address (not localhost), then run:

```bash
python voice_satellite.py
```

## Troubleshooting

- **"No module named sounddevice"**: You missed Step 3.
- **"PortAudio not found"**: You missed Step 1.
- **"Connection Refused"**: Check the `VOICE_ENGINE_URL` and `AGENT_URL` IPs in the python script.
