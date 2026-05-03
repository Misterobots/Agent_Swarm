<#
.SYNOPSIS
    Post-deployment validation - verifies deployment success
.DESCRIPTION
    Runs after deployment to ensure all services are healthy
.PARAMETER Target
    Which node was deployed to (Turing, Hopper, BMO, or All)
.EXAMPLE
    .\post-deploy-validate.ps1 -Target Turing
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("Turing", "Hopper", "BMO", "All")]
    [string]$Target,
    
    [Parameter(Mandatory=$false)]
    [int]$WaitSeconds = 10
)

$ErrorActionPreference = "Stop"

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║            POST-DEPLOYMENT VALIDATION                         ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

Write-Host "Target: $Target" -ForegroundColor White
Write-Host "Waiting $WaitSeconds seconds for services to stabilize..." -ForegroundColor Yellow
Start-Sleep -Seconds $WaitSeconds

# Run full verification
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$scriptDir\sync-verify-nodes.ps1" -Action verify

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║            ✗ DEPLOYMENT VERIFICATION FAILED                   ║" -ForegroundColor Red
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host "`nAction required:" -ForegroundColor Yellow
    Write-Host "  1. Check container logs: docker logs <container-name>" -ForegroundColor White
    Write-Host "  2. Restart failed containers: docker restart <container-name>" -ForegroundColor White
    Write-Host "  3. Re-run validation: .\post-deploy-validate.ps1 -Target $Target`n" -ForegroundColor White
    exit 1
}

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         ✓ DEPLOYMENT VERIFIED SUCCESSFULLY                    ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host "All services are healthy and running`n" -ForegroundColor Green

exit 0
