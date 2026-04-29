# Setup Media Archiver Scheduled Task for Windows
# Run this script as Administrator

param(
    [string]$PythonPath = "python",
    [string]$TaskTime = "02:00"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Memex Media Archiver - Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ArchiverScript = Join-Path $ScriptDir "media_archiver.py"
$LogDir = Join-Path $ProjectRoot "logs"

Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray
Write-Host "Python: $PythonPath" -ForegroundColor Gray
Write-Host ""

# Verify script exists
if (-not (Test-Path $ArchiverScript)) {
    Write-Host "Error: media_archiver.py not found at $ArchiverScript" -ForegroundColor Red
    exit 1
}

# Create log directory
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# Test script execution
Write-Host "Testing script execution..." -ForegroundColor Yellow
Push-Location $ProjectRoot
try {
    & $PythonPath $ArchiverScript --dry-run
    if ($LASTEXITCODE -ne 0) {
        throw "Script test failed"
    }
} catch {
    Write-Host "Error: Script test failed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Host ""
Write-Host "Script test successful!" -ForegroundColor Green
Write-Host ""

# Check if task already exists
$TaskName = "MemexMediaArchiver"
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($ExistingTask) {
    Write-Host "Task '$TaskName' already exists." -ForegroundColor Yellow
    $response = Read-Host "Do you want to replace it? (y/n)"
    if ($response -ne 'y') {
        Write-Host "Skipping task creation." -ForegroundColor Yellow
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create scheduled task action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "$ArchiverScript" `
    -WorkingDirectory $ProjectRoot

# Create scheduled task trigger (daily at specified time)
$Trigger = New-ScheduledTaskTrigger -Daily -At $TaskTime

# Create scheduled task principal (run whether user is logged on or not)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

# Create scheduled task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

# Register the task
Write-Host "Creating scheduled task..." -ForegroundColor Yellow
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Memex Media Archival System - Compresses and archives media older than 30 days" `
    | Out-Null

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setup Complete" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Task Name: $TaskName" -ForegroundColor Gray
Write-Host "Schedule: Daily at $TaskTime" -ForegroundColor Gray
Write-Host ""
Write-Host "To view the task:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName $TaskName | Format-List" -ForegroundColor Gray
Write-Host ""
Write-Host "To run manually:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName $TaskName" -ForegroundColor Gray
Write-Host ""
Write-Host "To view task history:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTaskInfo -TaskName $TaskName" -ForegroundColor Gray
Write-Host ""
Write-Host "To view archival logs:" -ForegroundColor Yellow
Write-Host "  Get-Content $LogDir\media_archiver.log -Tail 50" -ForegroundColor Gray
