<#
.SYNOPSIS
    Sync and verify all Pioneer nodes before/after deployment
.DESCRIPTION
    Checks connectivity, container health, syncs repos, and validates services
    across all nodes (Turing, Hopper, BMO). Run from Lovelace.
.PARAMETER Action
    sync - Sync repos from Lovelace to remote nodes
    verify - Check all nodes and container health
    full - Both sync and verify
.EXAMPLE
    .\sync-verify-nodes.ps1 -Action full
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("sync", "verify", "full")]
    [string]$Action = "full",
    
    [Parameter(Mandatory=$false)]
    [switch]$Quiet
)

$ErrorActionPreference = "Continue"
$SSH = "C:\Windows\System32\OpenSSH\ssh.exe"
$SCP = "C:\Windows\System32\OpenSSH\scp.exe"

# Pioneer node configuration
$NODES = @{
    Turing = @{
        IP = "192.168.2.103"
        RepoPath = "/home/misterobots/Home_AI_Lab"
        Containers = @("agent_runtime", "hive_ui", "traefik")
        Services = @(
            @{ Name = "Hive UI"; URL = "http://192.168.2.103/hive/" }
            @{ Name = "Agent Runtime"; URL = "http://192.168.2.103/hive/api/backend/health" }
        )
    }
    Hopper = @{
        IP = "192.168.2.102"
        RepoPath = "/home/misterobots/Agent_Swarm"
        Containers = @("postgres", "redis", "langfuse", "mempalace")
        Services = @(
            @{ Name = "PostgreSQL"; Port = 5432 }
            @{ Name = "Redis"; Port = 6379 }
        )
    }
    BMO = @{
        IP = "192.168.2.106"
        RepoPath = "/home/misterobots/Home_AI_Lab"
        Containers = @()
        Services = @()
    }
}

$USER = "misterobots"
$LOCAL_REPO = "C:\Users\panca\Documents\Github\Agent_Swarm"
$RESULTS = @{
    Connectivity = @{}
    Containers = @{}
    Services = @{}
    Sync = @{}
    Errors = @()
}

function Write-Status {
    param([string]$Message, [string]$Type = "Info")
    if ($Quiet) { return }
    
    $color = switch ($Type) {
        "Success" { "Green" }
        "Error" { "Red" }
        "Warning" { "Yellow" }
        "Info" { "Cyan" }
        default { "White" }
    }
    Write-Host $Message -ForegroundColor $color
}

function Test-NodeConnectivity {
    param([string]$Node, [string]$IP)
    
    Write-Status "[$Node] Testing connectivity..." "Info"
    
    $pingResult = Test-Connection -ComputerName $IP -Count 2 -Quiet
    if (-not $pingResult) {
        $RESULTS.Connectivity[$Node] = "UNREACHABLE"
        $RESULTS.Errors += "[$Node] Node unreachable at $IP"
        Write-Status "[$Node] ✗ Unreachable" "Error"
        return $false
    }
    
    $sshTest = & $SSH -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes "$USER@$IP" "echo OK" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $RESULTS.Connectivity[$Node] = "SSH_FAILED"
        $RESULTS.Errors += "[$Node] SSH authentication failed"
        Write-Status "[$Node] ✗ SSH failed" "Error"
        return $false
    }
    
    $RESULTS.Connectivity[$Node] = "OK"
    Write-Status "[$Node] ✓ Connected" "Success"
    return $true
}

function Test-ContainerHealth {
    param([string]$Node, [string]$IP, [string[]]$Containers)
    
    if ($Containers.Count -eq 0) {
        Write-Status "[$Node] No containers to check" "Info"
        return $true
    }
    
    Write-Status "[$Node] Checking containers..." "Info"
    $RESULTS.Containers[$Node] = @{}
    $allHealthy = $true
    
    foreach ($container in $Containers) {
        $status = & $SSH -o StrictHostKeyChecking=no -o BatchMode=yes "$USER@$IP" "docker ps --filter name=$container --format '{{.Status}}'" 2>&1
        
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($status)) {
            $RESULTS.Containers[$Node][$container] = "DOWN"
            $RESULTS.Errors += "[$Node] Container '$container' is DOWN"
            Write-Status "[$Node]   ✗ $container - DOWN" "Error"
            $allHealthy = $false
        } elseif ($status -like "*Up*") {
            $healthStatus = if ($status -like "*healthy*") { "HEALTHY" } else { "UP" }
            $RESULTS.Containers[$Node][$container] = $healthStatus
            Write-Status "[$Node]   ✓ $container - $healthStatus" "Success"
        } else {
            $RESULTS.Containers[$Node][$container] = "UNKNOWN: $status"
            $RESULTS.Errors += "[$Node] Container '$container' status unknown: $status"
            Write-Status "[$Node]   ? $container - UNKNOWN" "Warning"
            $allHealthy = $false
        }
    }
    
    return $allHealthy
}

function Test-ServiceHealth {
    param([string]$Node, [string]$IP, [array]$Services)
    
    if ($Services.Count -eq 0) {
        return $true
    }
    
    Write-Status "[$Node] Checking services..." "Info"
    $RESULTS.Services[$Node] = @{}
    $allHealthy = $true
    
    foreach ($service in $Services) {
        if ($service.URL) {
            try {
                $response = Invoke-WebRequest -Uri $service.URL -Method Head -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                $RESULTS.Services[$Node][$service.Name] = "OK ($($response.StatusCode))"
                Write-Status "[$Node]   ✓ $($service.Name) - OK" "Success"
            } catch {
                $RESULTS.Services[$Node][$service.Name] = "FAILED"
                $RESULTS.Errors += "[$Node] Service '$($service.Name)' check failed: $($_.Exception.Message)"
                Write-Status "[$Node]   ✗ $($service.Name) - FAILED" "Error"
                $allHealthy = $false
            }
        } elseif ($service.Port) {
            $portTest = & $SSH -o StrictHostKeyChecking=no -o BatchMode=yes "$USER@$IP" "nc -zv localhost $($service.Port) 2>&1" 2>&1
            if ($LASTEXITCODE -eq 0) {
                $RESULTS.Services[$Node][$service.Name] = "OK"
                Write-Status "[$Node]   ✓ $($service.Name) (port $($service.Port)) - OK" "Success"
            } else {
                $RESULTS.Services[$Node][$service.Name] = "FAILED"
                $RESULTS.Errors += "[$Node] Service '$($service.Name)' port $($service.Port) not accessible"
                Write-Status "[$Node]   ✗ $($service.Name) (port $($service.Port)) - FAILED" "Error"
                $allHealthy = $false
            }
        }
    }
    
    return $allHealthy
}

function Sync-NodeRepo {
    param([string]$Node, [string]$IP, [string]$RepoPath)
    
    Write-Status "[$Node] Syncing repository..." "Info"
    
    # Check if remote repo exists
    $repoCheck = & $SSH -o StrictHostKeyChecking=no -o BatchMode=yes "$USER@$IP" "test -d $RepoPath && echo EXISTS" 2>&1
    if ($repoCheck -notlike "*EXISTS*") {
        $RESULTS.Sync[$Node] = "REPO_NOT_FOUND"
        $RESULTS.Errors += "[$Node] Repository not found at $RepoPath"
        Write-Status "[$Node]   ✗ Repo not found at $RepoPath" "Error"
        return $false
    }
    
    # Git fetch and status
    $gitStatus = & $SSH -o StrictHostKeyChecking=no -o BatchMode=yes "$USER@$IP" "cd $RepoPath && git fetch origin && git status --porcelain" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        $RESULTS.Sync[$Node] = "GIT_ERROR"
        $RESULTS.Errors += "[$Node] Git command failed: $gitStatus"
        Write-Status "[$Node]   ✗ Git sync failed" "Error"
        return $false
    }
    
    # Check for uncommitted changes
    if (-not [string]::IsNullOrWhiteSpace($gitStatus)) {
        $RESULTS.Sync[$Node] = "UNCOMMITTED_CHANGES"
        Write-Status "[$Node]   ⚠ Has uncommitted changes" "Warning"
    } else {
        $RESULTS.Sync[$Node] = "CLEAN"
        Write-Status "[$Node]   ✓ Repo clean and synced" "Success"
    }
    
    return $true
}

# Main execution
Write-Status "`n╔═══════════════════════════════════════════════════════════════╗" "Info"
Write-Status "║          PIONEER NODE SYNC & VERIFICATION                    ║" "Info"
Write-Status "╚═══════════════════════════════════════════════════════════════╝`n" "Info"

$overallSuccess = $true

foreach ($nodeEntry in $NODES.GetEnumerator()) {
    $nodeName = $nodeEntry.Key
    $nodeConfig = $nodeEntry.Value
    
    Write-Status "`n━━━ $nodeName ($($nodeConfig.IP)) ━━━" "Info"
    
    # Test connectivity first
    if (-not (Test-NodeConnectivity -Node $nodeName -IP $nodeConfig.IP)) {
        $overallSuccess = $false
        continue
    }
    
    # Sync repos if requested
    if ($Action -eq "sync" -or $Action -eq "full") {
        if (-not (Sync-NodeRepo -Node $nodeName -IP $nodeConfig.IP -RepoPath $nodeConfig.RepoPath)) {
            $overallSuccess = $false
        }
    }
    
    # Verify health if requested
    if ($Action -eq "verify" -or $Action -eq "full") {
        if (-not (Test-ContainerHealth -Node $nodeName -IP $nodeConfig.IP -Containers $nodeConfig.Containers)) {
            $overallSuccess = $false
        }
        
        if (-not (Test-ServiceHealth -Node $nodeName -IP $nodeConfig.IP -Services $nodeConfig.Services)) {
            $overallSuccess = $false
        }
    }
}

# Summary
Write-Status "`n╔═══════════════════════════════════════════════════════════════╗" "Info"
Write-Status "║                         SUMMARY                               ║" "Info"
Write-Status "╚═══════════════════════════════════════════════════════════════╝" "Info"

$errorCount = $RESULTS.Errors.Count
if ($errorCount -eq 0) {
    Write-Status "`n✓ All nodes verified successfully" "Success"
} else {
    Write-Status "`n✗ $errorCount error(s) detected:" "Error"
    foreach ($error in $RESULTS.Errors) {
        Write-Status "  • $error" "Error"
    }
}

# Return results as JSON for programmatic use
if ($env:RETURN_JSON) {
    $RESULTS | ConvertTo-Json -Depth 5
}

if ($overallSuccess) {
    exit 0
} else {
    exit 1
}
