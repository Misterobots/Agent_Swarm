# Auto-Repair Daemon Status Dashboard
# Quick overview of auto-repair system health and recent activity

param(
    [switch]$Follow
)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $scriptPath ".." "logs" "auto_repair.log"
$pidFile = Join-Path $scriptPath ".." "logs" "auto_repair.pid"

function Show-Header {
    Clear-Host
    Write-Host "═══════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  AUTO-REPAIR DAEMON STATUS DASHBOARD" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Current Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host ""
}

function Show-DaemonStatus {
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  Daemon Status" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    
    if (Test-Path $pidFile) {
        $processId = Get-Content $pidFile
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        
        if ($process) {
            Write-Host "  Status:      " -NoNewline
            Write-Host "RUNNING [OK]" -ForegroundColor Green
            Write-Host "  PID:         $processId"
            Write-Host "  Uptime:      $($process.StartTime.ToString('yyyy-MM-dd HH:mm:ss')) ($([math]::Round(((Get-Date) - $process.StartTime).TotalHours, 1)) hours)"
            Write-Host "  CPU Time:    $([math]::Round($process.CPU, 2))s"
            Write-Host "  Memory:      $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB"
        } else {
            Write-Host "  Status:      " -NoNewline
            Write-Host "STOPPED ✗" -ForegroundColor Red
            Write-Host "  Note:        Stale PID file found"
        }
    } else {
        Write-Host "  Status:      " -NoNewline
        Write-Host "NOT RUNNING ✗" -ForegroundColor Red
        Write-Host "  Note:        Use .\launch_auto_repair.ps1 to start"
    }
    Write-Host ""
}

function Show-RecentActivity {
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  Recent Activity (Last 24 hours)" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    
    if (Test-Path $logFile) {
        $cutoff = (Get-Date).AddHours(-24)
        $lines = Get-Content $logFile | Select-Object -Last 500
        
        # Count health checks
        $healthChecks = $lines | Where-Object { $_ -match "Starting health check cycle" }
        Write-Host "  Health Checks:     $($healthChecks.Count)"
        
        # Count repairs attempted
        $repairsAttempted = $lines | Where-Object { $_ -match "Attempting auto-repair" }
        Write-Host "  Repairs Attempted: $($repairsAttempted.Count)"
        
        # Count successful repairs
        $repairsSuccess = $lines | Where-Object { $_ -match "Repair successful" }
        Write-Host "  Repairs Succeeded: " -NoNewline
        if ($repairsSuccess.Count -gt 0) {
            Write-Host "$($repairsSuccess.Count)" -ForegroundColor Green
        } else {
            Write-Host "0"
        }
        
        # Count failed repairs
        $repairsFailed = $lines | Where-Object { $_ -match "Repair failed" }
        Write-Host "  Repairs Failed:    " -NoNewline
        if ($repairsFailed.Count -gt 0) {
            Write-Host "$($repairsFailed.Count)" -ForegroundColor Red
        } else {
            Write-Host "0"
        }
        
        # Critical alerts
        $criticalAlerts = $lines | Where-Object { $_ -match "CRITICAL" }
        if ($criticalAlerts.Count -gt 0) {
            Write-Host ""
            Write-Host "  ⚠️  CRITICAL ALERTS: $($criticalAlerts.Count)" -ForegroundColor Red
        }
    } else {
        Write-Host "  No log file found" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Show-ServiceHealth {
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  Service Health (Most Recent Check)" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    
    if (Test-Path $logFile) {
        $lines = Get-Content $logFile | Select-Object -Last 100
        
        # Find last health check results
        $services = @("Authentik", "PostgreSQL", "Redis", "Langfuse")
        
        foreach ($service in $services) {
            $healthLine = $lines | Where-Object { $_ -match "$service.*on.*:" } | Select-Object -Last 1
            
            if ($healthLine) {
                Write-Host "  $($service.PadRight(20))" -NoNewline
                if ($healthLine -match "Healthy") {
                    Write-Host 'OK' -NoNewline -ForegroundColor Green
                    Write-Host ' Healthy' -ForegroundColor Green
                } else {
                    Write-Host 'FAIL' -NoNewline -ForegroundColor Red
                    Write-Host ' Unhealthy' -ForegroundColor Red
                    
                    # Show error if available
                    $errorLine = $lines | Where-Object { $_ -match "$service issue detected" } | Select-Object -Last 1
                    if ($errorLine -match "issue detected: (.+)") {
                        Write-Host "     └─ $($matches[1])" -ForegroundColor Yellow
                    }
                }
            } else {
                Write-Host "  $($service.PadRight(20))" -NoNewline
                Write-Host '?' -NoNewline -ForegroundColor Gray
                Write-Host ' Not checked yet' -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "  No log file found" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Show-RecentRepairs {
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  Recent Repairs (Last 10)" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    
    if (Test-Path $logFile) {
        $lines = Get-Content $logFile | Select-Object -Last 500
        $repairs = $lines | Where-Object { $_ -match "Repair (successful|failed)" } | Select-Object -Last 10
        
        if ($repairs.Count -gt 0) {
            foreach ($repair in $repairs) {
                if ($repair -match '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[(.+?)\].*Repair (successful|failed): (.+)') {
                    $timestamp = $matches[1]
                    $level = $matches[2]
                    $status = $matches[3]
                    $details = $matches[4]
                    
                    $statusSymbol = if ($status -eq "successful") { "OK" } else { "FAIL" }
                    $statusColor = if ($status -eq "successful") { "Green" } else { "Red" }
                    
                    Write-Host "  $timestamp " -NoNewline
                    Write-Host "$statusSymbol" -NoNewline -ForegroundColor $statusColor
                    Write-Host " $($details.Substring(0, [Math]::Min(50, $details.Length)))"
                }
            }
        } else {
            Write-Host "  No repairs performed yet"
        }
    } else {
        Write-Host "  No log file found" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Show-Commands {
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  Quick Commands" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  .\launch_auto_repair.ps1          Start daemon"
    Write-Host "  .\launch_auto_repair.ps1 -Stop    Stop daemon"
    Write-Host "  .\launch_auto_repair.ps1 -Logs    View full logs"
    Write-Host "  .\auto_repair_status.ps1 -Follow  Auto-refresh dashboard"
    Write-Host ""
}

# Main display
do {
    Show-Header
    Show-DaemonStatus
    Show-RecentActivity
    Show-ServiceHealth
    Show-RecentRepairs
    Show-Commands
    
    if ($Follow) {
        Write-Host '  Refreshing in 30 seconds... (Ctrl+C to exit)' -ForegroundColor Gray
        Start-Sleep -Seconds 30
    }
} while ($Follow)
