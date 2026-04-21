#!/bin/bash
# BMO Face — Pygame X11 Launcher
# Usage: ./launch_face.sh

# Ensure running from correct directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set X11 display target (required for Pygame on Pi OS Bookworm)
export DISPLAY=:0

# Kill any existing instances
pkill -f bmo_driver.py 2>/dev/null

echo "🚀 Launching BMO Face (Pygame X11)..."

# Run with specific hardware device IDs for this setup
# Output: 1 (vc4-hdmi)
# Input: 3 (G933 Headset Mic)
python bmo_driver.py --host 192.168.2.157 --output_device 1 --input_device 3


