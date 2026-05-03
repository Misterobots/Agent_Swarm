<#
.SYNOPSIS
    Safe deployment wrapper with pre/post validation
.DESCRIPTION
    Wraps deployment with verification checks to prevent common issues
.PARAMETER Component
    What to deploy (hive-ui, agent-runtime, all)
.PARAMETER Target
    Which node to deploy to (Turing, Hopper, All)
.PARAMETER SkipChecks
    Skip pre/post validation (dangerous!)
.EXAMPLE
    .\safe-deploy.ps1 -Component hive-ui -Target Turing
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("hive-ui", "agent-runtime", "postgres", "redis", "all")]
    [string]$Component,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("Turing", "Hopper", "All")]
    [string]$Target,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipChecks,
    
    [Parameter(Mandatory=$false)]
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$SSH = "C:\Windows\System32\OpenSSH\ssh.exe"
$SCP = "C:\Windows\System32\OpenSSH\scp.exe"

# Component to node mapping
$COMPONENT_MAP = @{
    "hive-ui" = @{
        Node = "Turing"
        RepoPath = "/home/misterobots/Home_AI_Lab"
        Service = "hive-ui"
        SyncPath = "ui/"
    }
    "agent-runtime" = @{
        Node = "Turing"
        RepoPath = "/home/misterobots/Home_AI_Lab"
        Service = "agent-runtime"
        SyncPath = "agents/"
    }
    "postgres" = @{
        Node = "Hopper"
        RepoPath = "/home/misterobots/Agent_Swarm"
        Service = "postgres"
        SyncPath = ""
    }
    "redis" = @{
        Node = "Hopper"
        RepoPath = "/home/misterobots/Agent_Swarm"
        Service = "redis"
        SyncPath = ""
    }
}

$NODE_IPS = @{
    "Turing" = "192.168.2.103"
    "Hopper" = "192.168.2.102"
}

function Write-Step {
    param([string]$Message, [string]$Type = "Info")
    $color = switch ($Type) {
        "Success" { "Green" }
        "Error" { "Red" }
        "Warning" { "Yellow" }
        default { "Cyan" }
    }
    Write-Host "`n→ $Message" -ForegroundColor $color
}

function Deploy-Component {
    param([string]$Component, [string]$Node)
    
    $config = $COMPONENT_MAP[$Component]
    $ip = $NODE_IPS[$Node]
    $user = "misterobots"
    
    Write-Step "Deploying $Component to $Node ($ip)"
    
    # Sync files if needed
    if ($config.SyncPath) {
        Write-Host "  Syncing $($config.SyncPath)..." -ForegroundColor Yellow
        $localPath = Join-Path $repoRoot $config.SyncPath
        $remotePath = "$($config.RepoPath)/$($config.SyncPath)"
        
        $syncResult = & $SCP -r -o StrictHostKeyChecking=no "$localPath*" "${user}@${ip}:${remotePath}" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to sync files: $syncResult"
        }
        Write-Host "  ✓ Files synced" -ForegroundColor Green
    }
    
    # Build and restart
    $composeDir = if ($Node -eq "Turing") { "/home/misterobots/Home_AI_Lab/turing_gateway" } else { "/home/misterobots/Agent_Swarm" }
    
    if ($NoBuild) {
        Write-Host "  Restarting container (no build)..." -ForegroundColor Yellow
        $cmd = "cd $composeDir && docker compose restart $($config.Service)"
    }
    else {
        Write-Host "  Building and restarting..." -ForegroundColor Yellow
        $cmd = "cd $composeDir && docker compose build $($config.Service) && docker compose up -d $($config.Service)"
    }
    
    $deployResult = & $SSH -o StrictHostKeyChecking=no -o BatchMode=yes "${user}@${ip}" $cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Deployment failed: $deployResult"
    }
    
    Write-Host "  ✓ Deployment complete" -ForegroundColor Green
}

# Banner
Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                  SAFE DEPLOYMENT                              ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "Component: $Component" -ForegroundColor White
Write-Host "Target: $Target" -ForegroundColor White

try {
    # PRE-DEPLOYMENT CHECKS
    if (-not $SkipChecks) {
        Write-Step "Running pre-deployment checks..." "Info"
        & "$scriptDir\pre-deploy-check.ps1"
        if ($LASTEXITCODE -ne 0) {
            throw "Pre-deployment checks failed"
        }
    }
    else {
        Write-Host "⚠ WARNING: Skipping pre-deployment checks" -ForegroundColor Yellow
    }
    
    # DEPLOYMENT
    Write-Step "Starting deployment..." "Info"
    
    if ($Component -eq "all") {
        # Deploy all components
        foreach ($comp in @("agent-runtime", "hive-ui")) {
            Deploy-Component -Component $comp -Node "Turing"
        }
    }
    else {
        $targetNode = if ($Target -eq "All") { $COMPONENT_MAP[$Component].Node } else { $Target }
        Deploy-Component -Component $Component -Node $targetNode
    }
    
    # POST-DEPLOYMENT VALIDATION
    if (-not $SkipChecks) {
        Write-Step "Running post-deployment validation..." "Info"
        & "$scriptDir\post-deploy-validate.ps1" -Target $Target -WaitSeconds 10
        if ($LASTEXITCODE -ne 0) {
            throw "Post-deployment validation failed"
        }
    }
    else {
        Write-Host "⚠ WARNING: Skipping post-deployment validation" -ForegroundColor Yellow
    }
    
    # SUCCESS
    Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║            ✓ DEPLOYMENT SUCCESSFUL                            ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host "Component: $Component deployed to $Target`n" -ForegroundColor Green
    
    exit 0
}
catch {
    Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║            ✗ DEPLOYMENT FAILED                                ║" -ForegroundColor Red
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)`n" -ForegroundColor Red
    exit 1
}
