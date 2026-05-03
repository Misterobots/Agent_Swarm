<#
.SYNOPSIS
    Pre-deployment check - validates all nodes before making changes
.DESCRIPTION
    Runs comprehensive checks before deployment to catch issues early
.EXAMPLE
    .\pre-deploy-check.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              PRE-DEPLOYMENT VALIDATION                        ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# Check if we're in the repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

if (-not (Test-Path "$repoRoot\.git")) {
    Write-Host "✗ Not in a git repository" -ForegroundColor Red
    exit 1
}

# Check for uncommitted changes
Write-Host "→ Checking for uncommitted changes..." -ForegroundColor Yellow
Set-Location $repoRoot
$gitStatus = git status --porcelain

if ($gitStatus) {
    Write-Host "⚠ WARNING: You have uncommitted changes:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor White
    
    $response = Read-Host "`nContinue anyway? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "✗ Deployment cancelled" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "✓ Working directory clean" -ForegroundColor Green
}

# Check current branch
Write-Host "`n→ Checking git branch..." -ForegroundColor Yellow
$currentBranch = git branch --show-current

if ($currentBranch -ne "main") {
    Write-Host "⚠ WARNING: You are on branch '$currentBranch', not 'main'" -ForegroundColor Yellow
    
    $response = Read-Host "Continue deployment from '$currentBranch'? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "✗ Deployment cancelled" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "✓ On main branch" -ForegroundColor Green
}

# Run node verification
Write-Host "`n→ Verifying all nodes..." -ForegroundColor Yellow
& "$scriptDir\sync-verify-nodes.ps1" -Action verify

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n✗ Node verification failed" -ForegroundColor Red
    Write-Host "Fix errors above before deploying" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         ✓ PRE-DEPLOYMENT CHECKS PASSED                        ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host "Safe to proceed with deployment`n" -ForegroundColor Green

exit 0
