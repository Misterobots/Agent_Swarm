#!/bin/bash
set -e

# Logs
LOG_FILE="bootstrap.log"
exec > >(tee -a ${LOG_FILE}) 2>&1

echo "--- [Swarm Control Plane] Bootstrap Sequence Initiated ---"

# 1. Timezone (Critical for SPIRE context)
echo "[1/4] Setting Timezone to America/Chicago..."
sudo timedatectl set-timezone America/Chicago
timedatectl | grep "Time zone"

# 2. Firewall (UFW)
echo "[2/4] Configuring Firewall..."
# Reset to sane defaults first
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow Critical Ports
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 5432/tcp comment 'Postgres'
sudo ufw allow 8081/tcp comment 'SPIRE'

# Enable non-interactively
echo "y" | sudo ufw enable
sudo ufw status verbose

# 3. Install Docker
echo "[3/4] Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    
    # Add current user to docker group
    echo "Adding $USER to docker group..."
    sudo usermod -aG docker $USER
else
    echo "Docker already installed."
fi

# 4. Agent Architecture
echo "[4/4] Preparing Directories..."
mkdir -p ~/home_ai_lab/control_plane

echo "--- Bootstrap Complete ---"
echo "WARNING: You must LOG OUT and LOG BACK IN for Docker permissions to work."
echo "Command: exit"

