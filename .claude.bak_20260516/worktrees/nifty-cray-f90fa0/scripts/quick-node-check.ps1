param(
    [string]$Action = "verify"
)

$SSH = "C:\Windows\System32\OpenSSH\ssh.exe"
$RESULTS = @{ Errors = @() }

function Test-Simple {
    param([string]$IP)
    
    $pingResult = Test-Connection -ComputerName $IP -Count 1 -Quiet
    if ($pingResult) {
        Write-Host "✓ $IP reachable" -ForegroundColor Green
        return $true
    } else {
        Write-Host "✗ $IP unreachable" -ForegroundColor Red
        return $false
    }
}

Write-Host "`n=== Pioneer Node Quick Check ===" -ForegroundColor Cyan

$nodes = @{
    "Turing" = "192.168.2.103"
    "Hopper" = "192.168.2.102"
    "BMO" = "192.168.2.106"
}

$allOK = $true

foreach ($node in $nodes.GetEnumerator()) {
    Write-Host "`n[$($node.Key)]" -ForegroundColor Yellow
    if (-not (Test-Simple -IP $node.Value)) {
        $allOK = $false
        continue
    }
    
    # Check docker containers
    $containers = & $SSH -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes "misterobots@$($node.Value)" "docker ps --format '{{.Names}}: {{.Status}}'" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Containers:" -ForegroundColor White
        $containers -split "`n" | ForEach-Object {
            if ($_ -ne "") {
                Write-Host "  $_" -ForegroundColor White
            }
        }
    } else {
        Write-Host "  ✗ Could not check containers" -ForegroundColor Red
        $allOK = $false
    }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
if ($allOK) {
    Write-Host "✓ All nodes operational" -ForegroundColor Green
    exit 0
} else {
    Write-Host "✗ Some nodes have issues" -ForegroundColor Red
    exit 1
}
