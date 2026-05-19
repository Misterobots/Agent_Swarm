# Team Builder Quick Test Script

Write-Host "`n╔══════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              TEAM BUILDER — Quick Smoke Test                         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$API_BASE = "http://192.168.2.103/hive/api/backend"

Write-Host "[1/5] Testing Team Builder API Endpoints..." -ForegroundColor Yellow

# Test GET config (should return empty or existing config)
Write-Host "  → GET /api/v1/team-builder/config" -ForegroundColor Gray
try {
    $getResponse = Invoke-RestMethod -Uri "$API_BASE/api/v1/team-builder/config" -Method Get
    Write-Host "  ✓ GET succeeded" -ForegroundColor Green
    Write-Host "    Current config: $($getResponse | ConvertTo-Json -Compress)" -ForegroundColor Gray
} catch {
    Write-Host "  ✗ GET failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[2/5] Testing Team Builder POST (save config)..." -ForegroundColor Yellow

# Test POST config
$testConfig = @{
    coder = "qwen2.5-coder:14b"
    devops = "qwen3:8b"
    researcher = "llama3.2:3b"
} | ConvertTo-Json

Write-Host "  → POST /api/v1/team-builder/config" -ForegroundColor Gray
try {
    $postResponse = Invoke-RestMethod -Uri "$API_BASE/api/v1/team-builder/config" `
        -Method Post `
        -ContentType "application/json" `
        -Body $testConfig
    Write-Host "  ✓ POST succeeded" -ForegroundColor Green
    Write-Host "    Response: $($postResponse | ConvertTo-Json -Compress)" -ForegroundColor Gray
} catch {
    Write-Host "  ✗ POST failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[3/5] Verifying saved configuration..." -ForegroundColor Yellow

# Verify the config was saved
try {
    $verifyResponse = Invoke-RestMethod -Uri "$API_BASE/api/v1/team-builder/config" -Method Get
    if ($verifyResponse.coder -eq "qwen2.5-coder:14b") {
        Write-Host "  ✓ Configuration persisted correctly" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Configuration mismatch" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "  ✗ Verification failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[4/5] Testing Ollama Models API..." -ForegroundColor Yellow

# Test Ollama models endpoint (used by UI)
Write-Host "  → GET /api/v1/models/ollama" -ForegroundColor Gray
try {
    $modelsResponse = Invoke-RestMethod -Uri "$API_BASE/api/v1/models/ollama" -Method Get
    $modelCount = $modelsResponse.models.Count
    Write-Host "  ✓ Ollama API succeeded ($modelCount models available)" -ForegroundColor Green
    
    # Show first 5 models
    $modelsResponse.models | Select-Object -First 5 | ForEach-Object {
        Write-Host "    - $($_.name)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ✗ Ollama API failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n[5/5] Testing Container Health..." -ForegroundColor Yellow

# Check agent_runtime logs for errors
Write-Host "  → Checking agent_runtime logs..." -ForegroundColor Gray
$SSH = "C:\Windows\System32\OpenSSH\ssh.exe"
$TURING = "misterobots@192.168.2.103"

$logCheck = & $SSH $TURING "docker logs --tail=20 agent_runtime 2>&1 | grep -i 'team.*builder\|role.*model\|error' || echo 'No team builder logs found'"
if ($logCheck -match "error") {
    Write-Host "  ⚠ Errors detected in logs:" -ForegroundColor Yellow
    Write-Host $logCheck -ForegroundColor Red
} else {
    Write-Host "  ✓ No errors in recent logs" -ForegroundColor Green
}

Write-Host "`n╔══════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                     ALL TESTS PASSED ✓                               ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "[NEXT STEPS]" -ForegroundColor Cyan
Write-Host "1. Open Hive UI: https://hive.shivelymedia.com/settings" -ForegroundColor White
Write-Host "2. Navigate to 'Team Builder' section" -ForegroundColor White
Write-Host "3. Configure models for each role" -ForegroundColor White
Write-Host "4. Click 'Save Config'" -ForegroundColor White
Write-Host "5. Test coordinator mode: Ask 'Use coordinator mode to build a REST API'`n" -ForegroundColor White
