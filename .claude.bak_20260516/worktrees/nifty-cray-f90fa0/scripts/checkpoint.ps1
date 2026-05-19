$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = "backups\checkpoint_$timestamp"

Write-Host "🚧 Starting System Checkpoint: $timestamp" -ForegroundColor Cyan

# 1. Create Backup Directory
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
Write-Host "   [+] Created $backupRoot"

# 2. Backup Critical Configuration
$configDest = "$backupRoot\config"
New-Item -ItemType Directory -Force -Path $configDest | Out-Null
Copy-Item -Path "config\*" -Destination $configDest -Recurse -Force
Write-Host "   [+] Backed up config/"

# 3. Backup Environment Variables
if (Test-Path ".env") {
    Copy-Item -Path ".env" -Destination "$backupRoot\.env"
    Write-Host "   [+] Backed up .env"
} else {
    Write-Warning "   [!] .env file not found!"
}

# 4. Backup Execution Plane (Docker Compose)
$execDest = "$backupRoot\execution_plane"
New-Item -ItemType Directory -Force -Path $execDest | Out-Null
Copy-Item -Path "execution_plane\*" -Destination $execDest -Recurse -Force
Write-Host "   [+] Backed up execution_plane/"

# 5. Backup Agents Source Code
$agentsDest = "$backupRoot\agents"
New-Item -ItemType Directory -Force -Path $agentsDest | Out-Null
Copy-Item -Path "agents\*" -Destination $agentsDest -Recurse -Force
Write-Host "   [+] Backed up agents/"

# 6. Git Status Snapshot (Text file)
if (Get-Command git -ErrorAction SilentlyContinue) {
    git status > "$backupRoot\git_status_snapshot.txt"
    git diff > "$backupRoot\git_diff_snapshot.patch"
    Write-Host "   [+] Captured Git status and diff"
}

Write-Host "✅ Checkpoint Complete. Stored in: $backupRoot" -ForegroundColor Green
Write-Host "   To restore, overwrite current files with contents of this folder."
