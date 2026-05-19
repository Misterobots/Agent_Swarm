#!/bin/bash
# BMO Face — High Performance Execution (KMSDRM)
# This script stops the desktop environment to allow direct hardware access (60 FPS).
# Usage: ./launch_face_fast.sh

# Ensure we are in the right directory
cd "$(dirname "$0")"

if [ -f ../../network.env ]; then
	set -a
	. ../../network.env
	set +a
fi

echo "🛑 Stopping Desktop (X11) to free up GPU... (Screen will flicker)"
sudo systemctl stop lightdm

# Give it a moment to release resources
sleep 2

# Set Audio/Video drivers for direct hardware access
export SDL_VIDEODRIVER=kmsdrm
export SDL_AUDIODRIVER=alsa

# Activate Venv
source venv/bin/activate

echo "🚀 Launching BMO Face (KMSDRM Mode)..."
# Run with typical hardware args
python bmo_driver.py --host "${LOVELACE_IP:-192.168.2.101}" --output_device 1 --input_device 3

echo "✅ Specific process finished. Restoring Desktop..."
sudo systemctl start lightdm

