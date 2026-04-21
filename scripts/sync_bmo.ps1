param(
    [string]$HostName = "192.168.2.106",
    [string]$Username = "misterobots",
    [string]$RemoteDir = "/home/misterobots/bmo_client",
    [switch]$RestartService,
    [switch]$SkipBackup
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    $sshTarget = "$Username@$HostName"
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

    $remotePrep = if ($SkipBackup) {
        "mkdir -p '$RemoteDir'"
    } else {
        "mkdir -p '$RemoteDir'; if [ -d '$RemoteDir' ]; then backup='$RemoteDir.backup.$timestamp'; rm -rf `"`$backup`"; cp -a '$RemoteDir' `"`$backup`"; echo BACKUP:`"`$backup`"; fi"
    }

    Write-Host "Preparing remote directory $RemoteDir on $sshTarget"
    ssh $sshTarget $remotePrep

    $tarArgs = @(
        "-cf", "-",
        "-C", "agents/bmo_voice", ".",
        "-C", "scripts", "voice_satellite.py",
        "-C", "scripts", "requirements_satellite.txt",
        "-C", ".", "network.env"
    )

    $remoteExtract = "tar -xf - -C '$RemoteDir'"
    Write-Host "Syncing canonical BMO payload to ${sshTarget}:$RemoteDir"
    & tar @tarArgs | ssh $sshTarget $remoteExtract
    if ($LASTEXITCODE -ne 0) {
        throw "BMO sync failed during archive transfer."
    }

    $remoteValidate = "cd '$RemoteDir' && python3 -m py_compile bmo_driver.py voice_satellite.py pi_client.py"
    Write-Host "Validating Python entrypoints on remote host"
    ssh $sshTarget $remoteValidate

    if ($RestartService) {
        $remoteRestart = "sudo systemctl daemon-reload && sudo systemctl restart bmo.service && sudo systemctl status bmo.service --no-pager --lines=20"
        Write-Host "Restarting bmo.service"
        ssh -t $sshTarget $remoteRestart
    } else {
        Write-Host "Sync complete. Restart manually with: ssh -t $sshTarget 'sudo systemctl restart bmo.service'"
    }
}
finally {
    Pop-Location
}