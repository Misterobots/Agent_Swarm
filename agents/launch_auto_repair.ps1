# Auto-Repair Daemon Launcher for Windows
# Run this script to start the auto-repair daemon in the background

param(
    [switch]$Stop,
    [switch]$Status,
    [switch]$Logs
)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptPath "auto_repair_daemon.py"
$projectRoot = Split-Path -Parent $scriptPath
$logsDir = Join-Path $projectRoot "logs"
$logFile = Join-Path $logsDir "auto_repair.log"
$pidFile = Join-Path $logsDir "auto_repair.pid"

# Create logs directory if it doesn't exist
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

function Get-DaemonStatus {
    if (Test-Path $pidFile) {
        $processId = Get-Content $pidFile
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        
        if ($process) {
            Write-Host "[OK] Auto-Repair Daemon is running (PID: $processId)" -ForegroundColor Green
            Write-Host "  Started: $($process.StartTime)"
            Write-Host "  CPU: $([math]::Round($process.CPU, 2))s"
            Write-Host "  Memory: $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB"
            return $true
        } else {
            Write-Host "[X] Auto-Repair Daemon is not running (stale PID file)" -ForegroundColor Yellow
            Remove-Item $pidFile -ErrorAction SilentlyContinue
            return $false
        }
    } else {
        Write-Host "[X] Auto-Repair Daemon is not running" -ForegroundColor Red
        return $false
    }
}

function Stop-Daemon {
    if (Test-Path $pidFile) {
        $processId = Get-Content $pidFile
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        
        if ($process) {
            Write-Host "Stopping Auto-Repair Daemon (PID: $processId)..." -ForegroundColor Yellow
            Stop-Process -Id $processId -Force
            Start-Sleep -Seconds 2
            Remove-Item $pidFile -ErrorAction SilentlyContinue
            Write-Host "[OK] Daemon stopped" -ForegroundColor Green
        } else {
            Write-Host "Daemon is not running" -ForegroundColor Yellow
            Remove-Item $pidFile -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "Daemon is not running (no PID file)" -ForegroundColor Yellow
    }
}

function Show-Logs {
    if (Test-Path $logFile) {
        Write-Host "=== Auto-Repair Daemon Logs (last 50 lines) ===" -ForegroundColor Cyan
        Get-Content $logFile -Tail 50
    } else {
        Write-Host "No log file found at: $logFile" -ForegroundColor Yellow
    }
}

# Handle commands
if ($Stop) {
    Stop-Daemon
    exit 0
}

if ($Status) {
    Get-DaemonStatus
    exit 0
}

if ($Logs) {
    Show-Logs
    exit 0
}

# Start the daemon
Write-Host "Starting Auto-Repair Daemon..." -ForegroundColor Cyan

# Check if already running
if (Get-DaemonStatus) {
    Write-Host "Daemon is already running. Use -Stop to stop it first." -ForegroundColor Yellow
    exit 1
}

# Load environment from .env file if present
$envFile = Join-Path $projectRoot "turing_gateway"
$envFile = Join-Path $envFile ".env"
if (Test-Path $envFile) {
    Write-Host "Loading environment from $envFile" -ForegroundColor Gray
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Start Python script in background
$process = Start-Process -FilePath "python" `
    -ArgumentList $pythonScript `
    -WindowStyle Hidden `
    -PassThru `
    -WorkingDirectory $scriptPath

# Save PID
$process.Id | Out-File $pidFile

Write-Host "[OK] Auto-Repair Daemon started (PID: $($process.Id))" -ForegroundColor Green
Write-Host "  Log file: $logFile"
Write-Host ""
Write-Host "Commands:"
Write-Host "  .\launch_auto_repair.ps1 -Status    # Check daemon status"
Write-Host "  .\launch_auto_repair.ps1 -Logs      # View recent logs"
Write-Host "  .\launch_auto_repair.ps1 -Stop      # Stop the daemon"
