#!/bin/bash
# Setup Media Archiver Cron Job for Linux
# Run this script on Turing/Hopper servers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=========================================="
echo "Memex Media Archiver - Cron Setup"
echo "=========================================="
echo "Project root: $PROJECT_ROOT"
echo "Python: $PYTHON_BIN"
echo ""

# Verify script exists
if [ ! -f "$SCRIPT_DIR/media_archiver.py" ]; then
    echo "Error: media_archiver.py not found at $SCRIPT_DIR"
    exit 1
fi

# Test script execution
echo "Testing script execution..."
cd "$PROJECT_ROOT"
$PYTHON_BIN "$SCRIPT_DIR/media_archiver.py" --dry-run || {
    echo "Error: Script test failed"
    exit 1
}

echo ""
echo "Script test successful!"
echo ""

# Create log directory
mkdir -p "$PROJECT_ROOT/logs"

# Generate cron entry
CRON_ENTRY="0 2 * * * cd $PROJECT_ROOT && $PYTHON_BIN $SCRIPT_DIR/media_archiver.py >> $PROJECT_ROOT/logs/media_archiver_cron.log 2>&1"

echo "Generated cron entry:"
echo "$CRON_ENTRY"
echo ""

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -q "media_archiver.py"; then
    echo "Cron entry already exists. Skipping installation."
    echo "To update, manually edit crontab with: crontab -e"
else
    echo "Adding cron entry..."
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "Cron entry installed successfully!"
fi

echo ""
echo "=========================================="
echo "Setup Complete"
echo "=========================================="
echo "The media archiver will run daily at 2:00 AM"
echo ""
echo "To view current cron jobs:"
echo "  crontab -l"
echo ""
echo "To view archival logs:"
echo "  tail -f $PROJECT_ROOT/logs/media_archiver_cron.log"
echo ""
echo "To manually run archival:"
echo "  cd $PROJECT_ROOT && $PYTHON_BIN $SCRIPT_DIR/media_archiver.py"
