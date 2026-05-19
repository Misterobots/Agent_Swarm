#!/bin/bash
# Deploy Auto-Repair Daemon to Turing node
# Run from: scripts/deploy/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REMOTE_USER="misterobots"
REMOTE_HOST="192.168.2.103"
REMOTE_PATH="/home/misterobots/Home_AI_Lab"

echo "════════════════════════════════════════════════════════════════════════════"
echo "  Auto-Repair Daemon Deployment"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Target: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"
echo ""

# Check if SSH is configured
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" echo "SSH OK" &>/dev/null; then
    echo "❌ ERROR: Cannot connect to $REMOTE_HOST via SSH"
    echo "   Please ensure SSH key authentication is configured"
    exit 1
fi

echo "✓ SSH connection verified"
echo ""

# Copy the auto_repair_daemon.py to remote node
echo "📦 Copying auto_repair_daemon.py to $REMOTE_HOST..."
scp "$PROJECT_ROOT/agents/auto_repair_daemon.py" \
    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/agents/" || {
    echo "❌ Failed to copy auto_repair_daemon.py"
    exit 1
}

echo "✓ auto_repair_daemon.py copied"
echo ""

# Copy systemd service file
echo "📦 Copying systemd service file..."
scp "$SCRIPT_DIR/auto_repair_daemon.service" \
    "$REMOTE_USER@$REMOTE_HOST:/tmp/" || {
    echo "❌ Failed to copy service file"
    exit 1
}

echo "✓ Service file copied"
echo ""

# Install systemd service
echo "🔧 Installing systemd service..."
ssh "$REMOTE_USER@$REMOTE_HOST" << 'EOF'
    # Move service file to systemd directory
    sudo mv /tmp/auto_repair_daemon.service /etc/systemd/system/
    sudo chmod 644 /etc/systemd/system/auto_repair_daemon.service
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    echo "✓ Systemd service installed"
EOF

echo ""

# Check if service is already running
echo "🔍 Checking service status..."
if ssh "$REMOTE_USER@$REMOTE_HOST" "systemctl is-active --quiet auto_repair_daemon.service"; then
    echo "⚠️  Auto-Repair Daemon is already running"
    echo ""
    read -p "Do you want to restart it? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔄 Restarting service..."
        ssh "$REMOTE_USER@$REMOTE_HOST" "sudo systemctl restart auto_repair_daemon.service"
        echo "✓ Service restarted"
    fi
else
    echo "🚀 Starting Auto-Repair Daemon..."
    ssh "$REMOTE_USER@$REMOTE_HOST" "sudo systemctl start auto_repair_daemon.service"
    echo "✓ Service started"
fi

echo ""

# Enable service to start on boot
echo "🔧 Enabling service to start on boot..."
ssh "$REMOTE_USER@$REMOTE_HOST" "sudo systemctl enable auto_repair_daemon.service"
echo "✓ Service enabled"
echo ""

# Show status
echo "📊 Service Status:"
echo "════════════════════════════════════════════════════════════════════════════"
ssh "$REMOTE_USER@$REMOTE_HOST" "systemctl status auto_repair_daemon.service --no-pager" || true
echo ""

# Show recent logs
echo "📋 Recent Logs:"
echo "════════════════════════════════════════════════════════════════════════════"
ssh "$REMOTE_USER@$REMOTE_HOST" "tail -n 20 $REMOTE_PATH/logs/auto_repair.log 2>/dev/null || echo 'No logs yet'"
echo ""

echo "════════════════════════════════════════════════════════════════════════════"
echo "✓ Deployment complete!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status auto_repair_daemon    # Check status"
echo "  sudo systemctl restart auto_repair_daemon   # Restart service"
echo "  sudo systemctl stop auto_repair_daemon      # Stop service"
echo "  tail -f $REMOTE_PATH/logs/auto_repair.log   # Follow logs"
echo "  sudo journalctl -u auto_repair_daemon -f    # Follow systemd logs"
echo "════════════════════════════════════════════════════════════════════════════"
