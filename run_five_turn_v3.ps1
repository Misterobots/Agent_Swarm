$SESSION = "diag-five-turn-v3-$(Get-Date -Format 'HHmmss')"
$API = "http://192.168.2.101:8008/v1/chat/completions"
$MODEL = "Home-AI-Swarm"
$TURNS = @(
  "I run a home AI lab. Remember this constraint for later turns: maintenance window is 02:00-03:00 UTC and avoid downtime.",
  "Write a short operations runbook section for tonight based on my earlier constraint and include one risk and mitigation.",
  "Give a brief historical reason why strict maintenance windows reduce incidents, then tie it to my earlier constraint.",
  "Create a devops rollout checklist for restarting the runtime and postgres tonight, respecting the earlier maintenance window and no-downtime requirement.",
  "Now produce a compact shell-style pseudo-script that follows your checklist and explicitly references the original maintenance window constraint."
)

$results = @()
$history = @()

foreach ($i in 0..4) {
  $turn = $i + 1
  $userMsg = $TURNS[$i]
  $messages = $history + @(@{role="user"; content=$userMsg})
  
  $bodyJson = @{model=$MODEL; messages=$messages; stream=$false} | ConvertTo-Json -Depth 10 -Compress
  $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)
  
  try {
    $resp = Invoke-RestMethod -Uri $API -Method POST -Body $bodyBytes -ContentType "application/json; charset=utf-8" -TimeoutSec 120
    $content = $resp.choices[0].message.content
    
    $intent = if ($content -match '\[Router\] Intent: ([A-Z_]+)') { $matches[1] } else { "UNKNOWN" }
    $reviewed = $content -match '\[(?:DevOps|TechnicalWriter|Librarian|MarsRL|Cortex)\] Reviewed prior turns'
    $constraints = $content -match '\[(?:DevOps|TechnicalWriter|Librarian|MarsRL)\] Injected active user constraints'
    $mars = $content -match 'MarsRL.*Solver|Solver.*generating'
    $mw = $content -match '02:00|maintenance window'
    $trainOverride = $content -match 'Keyword override: explicit training directive'
    $downgraded = $content -match 'TRAIN intent downgraded'
    
    $results += [PSCustomObject]@{
      turn=$turn; intent=$intent; reviewed_history=$reviewed;
      injected_constraints=$constraints; mars=$mars; mentions_mw=$mw;
      train_override=$trainOverride; downgraded=$downgraded
    }
    
    $history += @(@{role="user"; content=$userMsg}, @{role="assistant"; content=$content})
    Write-Host "T$turn [$intent] rev=$reviewed con=$constraints mars=$mars mw=$mw"
  } catch {
    Write-Host "T$turn ERROR: $_"
    $results += [PSCustomObject]@{turn=$turn; intent="ERROR"; reviewed_history=$false; injected_constraints=$false; mars=$false; mentions_mw=$false; train_override=$false; downgraded=$false}
  }
}

$results | ConvertTo-Json -Depth 5 | Out-File "diagnostics_v3_summary.json" -Encoding utf8 -Force
Write-Host "SESSION:$SESSION DONE"
$results | Format-Table
