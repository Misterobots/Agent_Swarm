# Deploy Team Builder to Turing — PowerShell Script

Write-Host "`n╔══════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     TEAM BUILDER DEPLOYMENT — Role-Based Model Assignment          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"
$SSH = "C:\Windows\System32\OpenSSH\ssh.exe"
$TURING = "misterobots@192.168.2.103"
$LOCAL_REPO = "C:\Users\panca\Documents\Github\Agent_Swarm"
$REMOTE_REPO = "/home/misterobots/Home_AI_Lab"

Write-Host "[1/6] Syncing Agent Files to Turing..." -ForegroundColor Yellow

# Sync Python agent files
$filesToSync = @(
    "agents/config.py",
    "agents/lamport.py",
    "agents/team_builder.py",
    "agents/role_model_resolver.py",
    "agents/church.py",
    "agents/main.py"
)

foreach ($file in $filesToSync) {
    Write-Host "  → Copying $file" -ForegroundColor Gray
    scp "$LOCAL_REPO\$file" "$TURING`:$REMOTE_REPO/$file"
}

Write-Host "`n[2/6] Syncing UI Files to Turing..." -ForegroundColor Yellow

# Sync UI files
scp "$LOCAL_REPO\ui\src\components\settings\team-builder.tsx" "$TURING`:$REMOTE_REPO/ui/src/components/settings/team-builder.tsx"
scp "$LOCAL_REPO\ui\src\app\settings\page.tsx" "$TURING`:$REMOTE_REPO/ui/src/app/settings/page.tsx"

Write-Host "`n[3/6] Syncing Docker Compose Configuration..." -ForegroundColor Yellow
scp "$LOCAL_REPO\turing_gateway\docker-compose.yml" "$TURING`:$REMOTE_REPO/turing_gateway/docker-compose.yml"

Write-Host "`n[4/6] Creating Default Team Configuration..." -ForegroundColor Yellow

# Create example .env file on Turing
$envContent = @"
# Team Builder Default Configuration
# Copy to turing_gateway/.env and customize

# Core models
PRIMARY_MODEL=qwen3:8b
COORDINATOR_MODEL=qwen3:14b
ARCHITECT_MODEL=qwen2.5-coder:14b

# Role-specific models (Team Builder)
CODER_MODEL=qwen2.5-coder:14b
DEVOPS_MODEL=qwen3:8b
RESEARCHER_MODEL=llama3.2:3b
ANALYST_MODEL=qwen3:8b
VERIFIER_MODEL=qwen3:8b
"@

$envContent | & $SSH $TURING "cat > $REMOTE_REPO/turing_gateway/.env.team-builder.example"

Write-Host "`n[5/6] Creating User Projects Directory..." -ForegroundColor Yellow
& $SSH $TURING "mkdir -p /workspace/user_projects"

Write-Host "`n[6/6] Restarting Services..." -ForegroundColor Yellow

# Restart agent_runtime (Python-only changes, no rebuild)
Write-Host "  → Restarting agent_runtime container..." -ForegroundColor Gray
& $SSH $TURING "cd $REMOTE_REPO/turing_gateway && docker compose restart agent-runtime"

# Check if UI needs rebuild (detect if package.json changed recently)
$rebuildUI = $false
if ($rebuildUI) {
    Write-Host "  → Rebuilding hive-ui (UI changes detected)..." -ForegroundColor Gray
    & $SSH $TURING "cd $REMOTE_REPO/turing_gateway && docker compose build hive-ui && docker compose up -d hive-ui"
} else {
    Write-Host "  → Restarting hive-ui container..." -ForegroundColor Gray
    & $SSH $TURING "cd $REMOTE_REPO/turing_gateway && docker compose restart hive-ui"
}

Write-Host "`n╔══════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    DEPLOYMENT COMPLETE ✓                             ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "[VERIFICATION STEPS]" -ForegroundColor Cyan
Write-Host "1. Check logs:" -ForegroundColor White
Write-Host "   ssh $TURING 'docker logs --tail=50 agent_runtime'" -ForegroundColor Gray
Write-Host "`n2. Test API endpoint:" -ForegroundColor White
Write-Host "   curl http://192.168.2.103/hive/api/backend/v1/team-builder/config" -ForegroundColor Gray
Write-Host "`n3. Test UI:" -ForegroundColor White
Write-Host "   Open https://hive.shivelymedia.com/settings" -ForegroundColor Gray
Write-Host "   Scroll to 'Team Builder' section" -ForegroundColor Gray
Write-Host "`n4. Test Coordinator Mode:" -ForegroundColor White
Write-Host "   Ask: 'Use coordinator mode to analyze this codebase'" -ForegroundColor Gray
Write-Host "   Check which models are assigned to each role" -ForegroundColor Gray

Write-Host "`n[CONFIGURATION]" -ForegroundColor Cyan
Write-Host "To customize default models:" -ForegroundColor White
Write-Host "  1. SSH to Turing: ssh $TURING" -ForegroundColor Gray
Write-Host "  2. Edit: nano $REMOTE_REPO/turing_gateway/.env" -ForegroundColor Gray
Write-Host "  3. Add/modify CODER_MODEL, DEVOPS_MODEL, etc." -ForegroundColor Gray
Write-Host "  4. Restart: cd $REMOTE_REPO/turing_gateway && docker compose restart agent-runtime`n" -ForegroundColor Gray

Write-Host "[ROLLBACK]" -ForegroundColor Cyan
Write-Host "If issues occur, rollback:" -ForegroundColor White
Write-Host "  ssh $TURING 'cd $REMOTE_REPO && git checkout HEAD -- agents/ ui/ turing_gateway/'" -ForegroundColor Gray
Write-Host "  ssh $TURING 'cd $REMOTE_REPO/turing_gateway && docker compose restart agent-runtime hive-ui'`n" -ForegroundColor Gray
