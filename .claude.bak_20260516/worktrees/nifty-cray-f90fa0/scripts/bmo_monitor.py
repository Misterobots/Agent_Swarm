import socket
import sys
import os
import datetime

# Enable ANSI escape codes in Windows Terminal
if sys.platform == 'win32':
    os.system('color')

# ANSI Colors
COLORS = {
    "neutral": "\033[90m",      # Gray
    "listening": "\033[92m",    # Green
    "thinking": "\033[93m",     # Yellow
    "speaking": "\033[96m",     # Cyan
    "excited_speaking": "\033[95m", # Pink
    "happy_speaking": "\033[92m",   # Bright Green
    "sad": "\033[94m",          # Blue
    "surprised": "\033[95m",    # Magenta
    "error": "\033[91m",        # Red
    "RESET": "\033[0m"
}

ICONS = {
    "neutral": "😐",
    "listening": "👂",
    "thinking": "🤔",
    "speaking": "🗣️",
    "excited_speaking": "🎉",
    "happy_speaking": "😊",
    "sad": "😢",
    "surprised": "😲",
    "error": "❌",
}

UDP_IP = "0.0.0.0"
UDP_PORT = 8123

def main():
    print(f"\033[96m--- 🛰️  BMO Telemetry Monitor Online ---\033[0m")
    print(f"Listening for UDP broadcasts on port {UDP_PORT}...\n")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        sock.bind((UDP_IP, UDP_PORT))
    except Exception as e:
        print(f"\033[91m❌ Error binding to port {UDP_PORT}: {e}\033[0m")
        print("Make sure no other monitor is running.")
        sys.exit(1)

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode('utf-8').strip()
            
            if message.startswith("BMO_STATE:"):
                state = message.split(":", 1)[1]
                
                # Format output
                color = COLORS.get(state, COLORS["neutral"])
                icon = ICONS.get(state, "✨")
                timestamp = datetime.datetime.now().strftime("%I:%M:%S %p")
                
                print(f"[{timestamp}] {color}{icon}  BMO is now: {state.upper()}{COLORS['RESET']}")
                
        except KeyboardInterrupt:
            print("\nShutting down monitor...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
