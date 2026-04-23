# BMO Voice Satellite Setup

To run the BMO Voice Satellite on the BMO device, install the system audio dependencies first, then sync the current client payload from this repo.

## 1. Install System Dependencies

Run these commands on BMO (`misterobots@192.168.2.106`):

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv portaudio19-dev libasound2-dev
```

- `portaudio19-dev`: Required for `sounddevice` and `pyaudio`.
- `libasound2-dev`: ALSA development headers.

## 2. Set up Python Environment (Recommended)

It is best practice to use a virtual environment in `/home/misterobots/bmo_client`:

```bash
cd /home/misterobots/bmo_client
python3 -m venv venv
source venv/bin/activate
```

## 3. Install Python Requirements

From the repo root on your workstation, sync the canonical payload first:

```powershell
.\scripts\sync_bmo.ps1
```

Then on the BMO device, if you copied `requirements_satellite.txt`:

```bash
pip install -r requirements_satellite.txt
```

If you didn't copy the requirements file, run:

```bash
pip install sounddevice numpy requests openwakeword soundfile
```

## 4. Run the Client

Make sure `/home/misterobots/bmo_client/network.env` contains the current `LOVELACE_IP`, then run:

```bash
cd /home/misterobots/bmo_client
source venv/bin/activate
python voice_satellite.py
```

## Troubleshooting

- **"No module named sounddevice"**: You missed Step 3.
- **"PortAudio not found"**: You missed Step 1.
- **"Connection Refused"**: Check `LOVELACE_IP` in `network.env` and verify the execution node is reachable.
