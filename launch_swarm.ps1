
# Home AI Lab - Swarm Launcher
# Run this script to spin up the entire Execution Plane.

$ErrorActionPreference = "Stop"

function Print-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "   $Title" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host ""
}

Print-Header "INITIALIZING HOME AI LAB SWARM"

# 1. Check Docker Requirement
Write-Host "🔍 Checking Docker status..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "   [OK] Docker is running." -ForegroundColor Green
}
catch {
    Write-Host "   [ERROR] Docker is NOT running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# 2. Paths
$Root = $PSScriptRoot
$ExecPlane = Join-Path $Root "execution_plane"

if (-not (Test-Path $ExecPlane)) {
    Write-Host "   [ERROR] execution_plane directory not found at $ExecPlane" -ForegroundColor Red
    exit 1
}

# 3. Deploy Execution Plane
Push-Location $ExecPlane
Print-Header "DEPLOYING EXECUTION PLANE"

Write-Host "📉 Stopping existing services..." -ForegroundColor Yellow
docker compose down --remove-orphans

Write-Host "🏗️  Rebuilding Swarm Infrastructure (Redis, Agents, UI)..." -ForegroundColor Yellow
docker compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "   [OK] Infrastructure Deployed." -ForegroundColor Green
}
else {
    Write-Host "   [ERROR] Deployment Failed." -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

# 4. Launch ComfyUI (Containerized)
Print-Header "LAUNCHING COMFYUI"
Write-Host "   [INFO] ComfyUI is starting as 'comfyui_gpu' service..." -ForegroundColor Green
Write-Host "   [INFO] Access at http://localhost:8188" -ForegroundColor Cyan


# 5. Wait for Health & Check Connectivity
Print-Header "SYSTEM CHECKS"
Write-Host "⏳ Giving services 10 seconds to warm up..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check Remote Brain (PostgreSQL on Control Plane)
# Read CONTROL_NODE_IP from network.env (single source of truth)
$NetworkEnv = Join-Path $Root "network.env"
$BrainIP = "192.168.2.102"  # fallback
if (Test-Path $NetworkEnv) {
    $match = Select-String -Path $NetworkEnv -Pattern "^CONTROL_NODE_IP=(.+)$"
    if ($match) { $BrainIP = $match.Matches[0].Groups[1].Value.Trim() }
}
if (Test-Connection -ComputerName $BrainIP -Count 1 -Quiet) {
    Write-Host "   [OK] Control Plane ($BrainIP) is Reachable." -ForegroundColor Green
}
else {
    Write-Host "   [WARN] Control Plane ($BrainIP) is UNREACHABLE." -ForegroundColor Magenta
    Write-Host "          Long-term memory features may be disabled." -ForegroundColor Gray
}

# 6. Mission Control
Print-Header "MISSION CONTROL ONLINE"
Write-Host "✅ Swarm is ready for commands." -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard URLs:"
Write-Host "   🖥️  Agent UI:        http://localhost:8501" -ForegroundColor Cyan
Write-Host "   📊 Mission Control: http://localhost:80/d/mission-control-uid" -ForegroundColor Cyan
Write-Host "   🔧 API Metrics:     http://localhost:8000/metrics" -ForegroundColor Cyan
Write-Host "   📦 Portainer (opt): http://localhost:9000" -ForegroundColor DarkGray

# Auto-Open
Start-Process "http://localhost:8501"
Start-Process "http://localhost:80/d/mission-control-uid"

Write-Host ""
Write-Host "To stop the swarm, run: docker compose down in execution_plane" -ForegroundColor Gray
