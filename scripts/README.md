# Pioneer Node Sync & Verification System

## Overview

Comprehensive system to prevent deployment failures by verifying all Pioneer nodes before and after changes. Catches common issues like:
- Containers down
- Changes not pushed/synced
- Network connectivity problems
- Service health issues

## Components

### 1. Core Scripts (in `scripts/`)

#### `sync-verify-nodes.ps1`
Main verification script that checks all nodes.

**Usage:**
```powershell
# Verify all nodes (connectivity, containers, services)
.\scripts\sync-verify-nodes.ps1 -Action verify

# Sync repos from Lovelace to remote nodes
.\scripts\sync-verify-nodes.ps1 -Action sync

# Both sync and verify
.\scripts\sync-verify-nodes.ps1 -Action full

# Quiet mode (minimal output)
.\scripts\sync-verify-nodes.ps1 -Action verify -Quiet
```

**What it checks:**
- **Connectivity**: Ping + SSH to each node
- **Containers**: Docker ps status for critical containers
- **Services**: HTTP endpoints and port availability
- **Repo sync**: Git status and uncommitted changes

#### `pre-deploy-check.ps1`
Runs before deployment to validate safety.

**Usage:**
```powershell
.\scripts\pre-deploy-check.ps1
```

**Checks:**
- Uncommitted changes in local repo
- Current git branch (warns if not on `main`)
- All nodes connectivity and health
- Prompts for confirmation if issues found

#### `post-deploy-validate.ps1`
Runs after deployment to ensure success.

**Usage:**
```powershell
# After deploying to Turing
.\scripts\post-deploy-validate.ps1 -Target Turing

# Custom wait time (default 10s)
.\scripts\post-deploy-validate.ps1 -Target All -WaitSeconds 15
```

**What it does:**
- Waits for services to stabilize
- Re-runs full node verification
- Reports any failures with actionable steps

#### `safe-deploy.ps1`
Complete deployment wrapper with pre/post checks.

**Usage:**
```powershell
# Deploy hive-ui to Turing with full checks
.\scripts\safe-deploy.ps1 -Component hive-ui -Target Turing

# Deploy agent-runtime without rebuild (Python-only changes)
.\scripts\safe-deploy.ps1 -Component agent-runtime -Target Turing -NoBuild

# Emergency deploy without checks (dangerous!)
.\scripts\safe-deploy.ps1 -Component hive-ui -Target Turing -SkipChecks

# Deploy all services
.\scripts\safe-deploy.ps1 -Component all -Target All
```

**Components:**
- `hive-ui` → Turing
- `agent-runtime` → Turing
- `postgres` → Hopper
- `redis` → Hopper

**Process:**
1. Runs pre-deployment checks
2. Syncs files from Lovelace to target node
3. Builds and restarts services
4. Runs post-deployment validation
5. Reports success or failure

### 2. Backend API (in `agents/main.py`)

Three new endpoints added:

#### `POST /api/v1/nodes/verify`
Trigger verification from API.

**Request:**
```json
{
  "action": "verify"  // or "sync" or "full"
}
```

**Response:**
```json
{
  "success": true,
  "results": {
    "Connectivity": { "Turing": "OK", "Hopper": "OK", "BMO": "OK" },
    "Containers": { 
      "Turing": { "agent_runtime": "HEALTHY", "hive_ui": "HEALTHY" }
    },
    "Services": { "Turing": { "Hive UI": "OK (200)" } },
    "Errors": []
  },
  "action": "verify"
}
```

#### `POST /api/v1/nodes/deploy`
Safe deployment via API.

**Request:**
```json
{
  "component": "hive-ui",
  "target": "Turing",
  "skip_checks": false,
  "no_build": false
}
```

**Response:**
```json
{
  "success": true,
  "component": "hive-ui",
  "target": "Turing",
  "output": "Build logs...",
  "errors": null
}
```

#### `GET /api/v1/nodes/status`
Quick lightweight status check.

**Response:**
```json
{
  "available": true,
  "healthy": true,
  "results": { ... }
}
```

### 3. UI Integration

**Location:** Dev workspace Quick Actions toolbar

**Button:** "Verify All Nodes"
- Shows as primary action in toolbar
- One-click verification
- Alert on success/failure
- Console logs detailed results

## Usage Workflows

### Before Making Changes
```powershell
# Verify everything is healthy
.\scripts\sync-verify-nodes.ps1 -Action verify
```

### After Making Changes (Recommended)
```powershell
# Safe deployment with automatic checks
.\scripts\safe-deploy.ps1 -Component hive-ui -Target Turing
```

### Manual Deployment (When you want control)
```powershell
# 1. Pre-check
.\scripts\pre-deploy-check.ps1

# 2. Manual deploy
scp ui/src/... misterobots@192.168.2.103:...
ssh misterobots@192.168.2.103 "cd ... && docker compose build hive-ui && docker compose up -d hive-ui"

# 3. Post-verify
.\scripts\post-deploy-validate.ps1 -Target Turing
```

### From Dev UI
1. Open http://192.168.2.103/hive/dev
2. Click **"Verify All Nodes"** in Quick Actions toolbar
3. Wait for alert confirmation
4. Check console for detailed results

## Node Configuration

Edit `scripts/sync-verify-nodes.ps1` to update:

```powershell
$NODES = @{
    Turing = @{
        IP = "192.168.2.103"
        RepoPath = "/home/misterobots/Home_AI_Lab"
        Containers = @("agent_runtime", "hive_ui", "traefik")
        Services = @(
            @{ Name = "Hive UI"; URL = "http://192.168.2.103/hive/" }
        )
    }
    # ... add more nodes
}
```

## Troubleshooting

### Script not found
Ensure scripts are in: `C:\Users\panca\Documents\Github\Agent_Swarm\scripts\`

### SSH failures
- Verify SSH key is set up for misterobots@<node>
- Test manually: `C:\Windows\System32\OpenSSH\ssh.exe misterobots@192.168.2.103 "echo test"`

### Container DOWN
1. Check logs: `ssh misterobots@192.168.2.103 "docker logs <container>"`
2. Restart: `docker restart <container>`
3. Re-verify: `.\scripts\sync-verify-nodes.ps1 -Action verify`

### Service check fails
- Verify URL/port in node configuration
- Check Traefik routing if using reverse proxy
- Test directly: `curl http://192.168.2.103/hive/`

## Best Practices

1. **Always verify before deploying** - Run pre-deploy check
2. **Use safe-deploy.ps1** - Automated checks prevent mistakes
3. **Check UI Quick Actions** - One-click verification during dev
4. **Monitor post-deploy** - Watch for container startup issues
5. **Keep repos synced** - Run sync action periodically

## Integration Points

- **Git workflows**: Add pre-deploy-check to pre-push hooks
- **CI/CD**: Call verify endpoint before automated deploys
- **Monitoring**: Poll /api/v1/nodes/status for dashboard
- **Alerts**: Parse verification results for failure notifications

## Exit Codes

- `0` - Success, all checks passed
- `1` - Failure, errors detected

## Environment Variables

- `RETURN_JSON` - Set to "1" to output JSON instead of colored text
- Standard PowerShell variables work normally

## Security Notes

- Scripts run from **Lovelace** (local machine) - has SSH access
- Backend endpoints run from **agent_runtime container** - needs mounted scripts or file sync
- SSH uses BatchMode (no password prompts) - requires key-based auth
- No secrets in scripts - uses existing SSH credentials
