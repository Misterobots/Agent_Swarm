# Memex Media Archival System

## Overview

The Media Archival System automatically compresses and archives generated media (images, videos, 3D models) that are older than 30 days. This helps manage storage while preserving all generated content for long-term retention.

## Features

- **Automatic Archival**: Media older than 30 days is automatically compressed and archived
- **Smart Compression**: Uses gzip compression (typically 70-90% size reduction for images)
- **Organized Storage**: Archives are organized by year-month for easy navigation
- **Metadata Preservation**: Sidecars metadata files are archived alongside media files
- **Server-Only Access**: Archives are only accessible on the server, not through Memex UI
- **Detailed Reporting**: Generates JSON reports for each archival run

## Directory Structure

```
/workspace/
├── delivered_artifacts/          # Active media (< 30 days)
│   ├── image_001.png
│   ├── image_001.png.json       # Metadata sidecar
│   └── ...
│
└── media_archives/                # Archived media (> 30 days)
    ├── 2026-03/                   # Year-month organization
    │   ├── delivered_artifacts/
    │   │   ├── image_old.png.gz
    │   │   └── image_old.png.json.gz
    │   └── output/
    │       └── ...
    ├── 2026-04/
    │   └── ...
    └── reports/                   # Archival reports
        ├── archive_report_1234567890.json
        └── ...
```

## Configuration

Environment variables (optional):

```bash
# Age threshold for archival (default: 30 days)
export MEDIA_ARCHIVE_AGE_DAYS=30

# Directory containing active media
export DELIVERED_ARTIFACTS_DIR=/workspace/delivered_artifacts

# Archive root directory
export MEDIA_ARCHIVE_ROOT=/workspace/media_archives
```

## Usage

### Manual Execution

```bash
# Preview what would be archived (dry run)
python scripts/media_archiver.py --dry-run

# Execute archival
python scripts/media_archiver.py

# Custom age threshold (e.g., 60 days)
python scripts/media_archiver.py --age-days 60
```

### Automated Scheduling

#### Linux/Unix (Cron)

Add to crontab (`crontab -e`):

```cron
# Run media archival daily at 2 AM
0 2 * * * cd /home/misterobots/Agent_Swarm && /usr/bin/python3 scripts/media_archiver.py >> logs/media_archiver_cron.log 2>&1
```

Or use the provided setup script:

```bash
# On Turing/Hopper servers
cd /home/misterobots/Agent_Swarm
chmod +x scripts/setup_media_archiver_cron.sh
./scripts/setup_media_archiver_cron.sh
```

#### Windows (Task Scheduler)

PowerShell script provided: `scripts/setup_media_archiver_task.ps1`

```powershell
# Run as Administrator
cd C:\Users\panca\OneDrive\Documents\GitHub\Agent_Swarm
.\scripts\setup_media_archiver_task.ps1
```

This creates a scheduled task that runs daily at 2 AM.

## Retrieving Archived Media

Archives are compressed with gzip. To extract:

```bash
# Extract a single file
gunzip /workspace/media_archives/2026-03/delivered_artifacts/image_old.png.gz

# Extract all files in a month
cd /workspace/media_archives/2026-03
find . -name "*.gz" -exec gunzip {} \;

# View compressed file without extracting
zcat /workspace/media_archives/2026-03/delivered_artifacts/image_old.png.gz > /tmp/preview.png
```

## Monitoring

### Check Last Archival Run

```bash
# View latest report
python -m json.tool /workspace/media_archives/reports/archive_report_*.json | tail -50

# View archival log
tail -f media_archiver.log
```

### Archive Statistics

```python
import json
from pathlib import Path

# Load latest report
reports = sorted(Path("/workspace/media_archives/reports").glob("*.json"))
if reports:
    with open(reports[-1]) as f:
        data = json.load(f)
        report = data['report']
        print(f"Files archived: {report['archived']}")
        print(f"Space saved: {report['total_savings_mb']:.1f} MB")
        print(f"Compression: {report.get('total_savings_percent', 0):.1f}%")
```

## Disaster Recovery

To restore archived media to active storage:

```bash
# Restore specific month
cd /workspace/media_archives/2026-03/delivered_artifacts
for file in *.gz; do
    gunzip -c "$file" > "/workspace/delivered_artifacts/${file%.gz}"
done

# Restore all archives (use with caution!)
find /workspace/media_archives -name "*.gz" -type f | while read file; do
    target="/workspace/delivered_artifacts/$(basename ${file%.gz})"
    gunzip -c "$file" > "$target"
done
```

## Troubleshooting

### Permission Errors

Ensure the script has write access to archive directories:

```bash
chmod +x scripts/media_archiver.py
chown -R misterobots:misterobots /workspace/media_archives
```

### Disk Space Issues

Check available space:

```bash
df -h /workspace
du -sh /workspace/delivered_artifacts
du -sh /workspace/media_archives
```

Clear old archives (older than 1 year):

```bash
find /workspace/media_archives -type f -mtime +365 -delete
```

## Security Notes

- Archives are stored server-side only (not mounted in Docker containers)
- No web-facing endpoint exposes archived media
- Only users with SSH access can retrieve archives
- Archives inherit filesystem permissions from parent directory

## Future Enhancements

- [ ] Web UI for browsing archives (admin only)
- [ ] Selective restore via API
- [ ] Cloud backup integration (S3/B2)
- [ ] Configurable retention policies
- [ ] Email notifications for archival runs
