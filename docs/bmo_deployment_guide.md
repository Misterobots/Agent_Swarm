# BMO Voice: Raspberry Pi Deployment Guide

This guide will help you install the BMO Client on your Raspberry Pi so it can talk to your Home AI Lab.

## 1. Prerequisites

- **Raspberry Pi** (3B+ or 4 recommended) running Raspberry Pi OS.
- **USB Microphone** and **Speaker** (or HDMI audio).
- **Network Access**: The Pi must be on the same network as your PC (or connected via Tailscale).

## 2. Installation on Raspberry Pi

Open a terminal on your Raspberry Pi and run:

```bash
# 1. Update System
sudo apt update && sudo apt install -y python3-pip python3-venv portaudio19-dev libsndfile1

# 2. Create Project Directory
mkdir -p ~/bmo_client
cd ~/bmo_client

# 3. Create Virtual Environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Dependencies
pip install requests sounddevice soundfile numpy
```

## 3. Copy the Client Script

You can copy the `pi_client.py` from your PC to the Pi using `scp` (replace `pi@raspberrypi.local` with your Pi's address):

**From your PC (PowerShell):**

```powershell
scp agents/bmo_voice/pi_client.py pi@raspberrypi.local:~/bmo_client/
```

**Or create manually on Pi:**

```bash
nano pi_client.py
# Paste the content of agents/bmo_voice/pi_client.py based on the file on your PC
# Press Ctrl+X, Y, Enter to save.
```

## 4. Usage (Classic Client)

Activate the environment (if not already):

```bash
cd ~/bmo_client
source venv/bin/activate
```

### 🤖 Text-to-Speech (Test)

Replace `192.168.1.X` with your PC's IP address.

```bash
python pi_client.py --host 192.168.1.X --text "Hello! I am BMO. Who wants to play video games?" --device 4
```

### 🎤 Voice-to-Voice (Talk to BMO)

This will record your microphone for 5 seconds, send it to the server, and play back the response in BMO's voice.

```bash
python pi_client.py --host 192.168.1.X --record --duration 5
```

### 🎛️ Parameters

- `--pitch`: Adjust pitch shift (Default: 3). Use `--pitch 0` for natural voice.
- `--duration`: Set recording time in seconds.

---

## 5. 🌟 BMO Experience (Face + Voice)

This runs the full BMO experience with the animated face UI.

### Step 1: Install Extra Dependencies

Update your virtual environment to include `aiohttp` (for the web server):

```bash
pip install aiohttp
```

### Step 2: Update Files

Copy the new `bmo_driver.py` and the `face/` directory to your Pi.

**From PC (PowerShell):**

```powershell
# Copy Driver
scp agents/bmo_voice/bmo_driver.py pi@raspberrypi.local:~/bmo_client/

# Copy Face Assets (Recursive)
scp -r agents/bmo_voice/face pi@raspberrypi.local:~/bmo_client/
```

### Step 3: Run the Driver

Run the driver. It will start a web server on port 8080 and listen for console input.

```bash
python bmo_driver.py --host 192.168.1.X --device 4
```

_You can type `talk` to record voice (5s) or just type a sentence to make BMO speak._

### Step 4: Show the Face (Kiosk Mode)

On the Raspberry Pi desktop (or via SSH if you set `DISPLAY=:0`), launch Chromium in full screen:

```bash
DISPLAY=:0 chromium-browser --kiosk --app=http://localhost:8080
```

---

## 6. Troubleshooting

### 🔇 No Audio / "Sample format not supported"

If you get errors about sample formats or hear no sound:

1.  **Use Device 4 (Default):**
    The raw HDMI hardware (Device 0) often rejects Mono audio. Use the "default" ALSA device (usually ID 4) which handles stereo conversion automatically.
    ```bash
    python pi_client.py --host <IP> --text "Test" --device 4
    ```
2.  **Force HDMI Audio:**
    If still silent, edit `/boot/firmware/config.txt` and ensure:
    ```ini
    dtparam=audio=on
    hdmi_drive=2
    ```

### 🚫 Permission Denied

If you see `Permission denied` or cannot save files:

1.  **Fix Ownership:** You likely ran `sudo` by mistake. Fix it:
    ```bash
    sudo chown -R $USER:$USER ~/bmo_client
    ```

### 📦 "Module Not Found" (Audio won't play)

If the script runs but doesn't play audio (only saves it):

1.  **Activate Venv:** You must execute `source venv/bin/activate` _every time_ you open a new terminal or reboot.
    ```bash
    cd ~/bmo_client
    source venv/bin/activate
    ```

---

## Source References

<details markdown>
<summary><strong>Source of Truth — Canonical Files</strong> (click to expand)</summary>

| Source | Type | Relevance |
|--------|------|----------|
| `bmo_client/` | Implementation | BMO Voice client source |
| `network.env` | Configuration | Backend API URLs |
| `voice_satellite.py` | Implementation | Wake word listener, audio pipeline |

</details>

<details markdown>
<summary><strong>Changelog</strong> (click to expand)</summary>

| Date | Author | Changes |
|------|--------|--------|
| 2026-04-16 | AI-Copilot | Added source references, changelog, maintenance guide, testing section |
| 2026-02-01 | AI-Copilot | Initial BMO deployment guide |

</details>

---

## Maintenance & Update Guide

- Update when BMO hardware requirements change (e.g., new microphone HAT).
- Update when backend API endpoints change (update `network.env` instructions).
- Update when new Python dependencies are required.

---

## Functionality Testing

| Step | Expected Result |
|------|----------------|
| Say "Hey BMO" | Wake word triggers, audio capture begins |
| Ask a question | Backend processes query, TTS plays response |
| Run `arecord -d 3 test.wav && aplay test.wav` | Mic + speaker hardware verified |
