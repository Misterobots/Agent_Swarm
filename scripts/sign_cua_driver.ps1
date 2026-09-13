<#
.SYNOPSIS
  Locally sign Qwen Code's UIAccess worker so @qwen-code/cua-sdk will install.

.DESCRIPTION
  qwen-code ships qwen-cua-driver-uia.exe UNSIGNED on Windows (confirmed on both 0.20.5 and
  0.20.6). Its own installer refuses to proceed unless the binary has a Valid Authenticode
  signature, because it is a UIAccess worker - a process permitted to bypass User Interface
  Privilege Isolation and send input to higher-integrity (elevated) windows. Windows requires
  signing for exactly that reason. The vendor has no Windows code-signing certificate, so their
  documented model is that the deployer signs it on the target machine.

  This script does that: creates a self-signed code-signing certificate, trusts it, and signs
  the worker in place. The installer then verifies it and copies it to
  %ProgramFiles%\Qwen\CuaDriver\<version>\ - the "secure location" UIAccess also requires.

.NOTES
  RUN ELEVATED. Steps 2 and 3 write to LocalMachine certificate stores.

  READ THIS BEFORE RUNNING
  ------------------------
  Step 3 installs a self-signed CA into LocalMachine\Root. After that, Windows will trust ANY
  binary signed with this certificate, not just this one. That is a real and durable expansion
  of what your machine will run without question. The private key stays in your user store, so
  the practical risk is someone with access to your account signing something with it - but it
  is not zero, and it is why this is a deliberate decision rather than a default.

  Verified prerequisites on this machine (2026-09-13):
    - Smart App Control: OFF. If it were ON, a self-signed certificate would NOT satisfy it,
      and SAC can only be turned off, never back on without reinstalling Windows.
    - signtool: C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe

  TO UNDO, see Remove-CuaSigningTrust at the bottom of this file.
#>

[CmdletBinding()]
param(
    [string]$Version  = "0.20.5",
    [string]$Subject  = "CN=Qwen CUA Local Signing",
    [string]$SignTool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
)

$ErrorActionPreference = "Stop"

# --- 0. Preconditions ---------------------------------------------------------------------
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal $identity).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this in an ELEVATED PowerShell - it writes to LocalMachine certificate stores."
}
if (-not (Test-Path $SignTool)) { throw "signtool not found at $SignTool" }

$exe = Join-Path $env:LOCALAPPDATA "Qwen\cua-sdk\$Version\windows-x86_64\qwen-cua-driver-uia.exe"
if (-not (Test-Path $exe)) {
    throw "Worker not found at $exe - run the npm install once first so it downloads and extracts."
}

# Smart App Control would reject a self-signed certificate outright.
$sac = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' `
        -Name VerifiedAndReputablePolicyState -ErrorAction SilentlyContinue
       ).VerifiedAndReputablePolicyState
if ($sac -eq 1) {
    throw "Smart App Control is ON. A self-signed certificate will not satisfy it, and turning SAC off is irreversible without reinstalling Windows. Stopping."
}

Write-Host "Target : $exe"
Write-Host "Current: $((Get-AuthenticodeSignature -LiteralPath $exe).Status)"

# --- 1. Create the signing certificate ----------------------------------------------------
# Private key lands in CurrentUser\My; only the PUBLIC certificate gets trusted below.
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject $Subject `
    -KeyAlgorithm RSA -KeyLength 3072 `
    -KeyUsage DigitalSignature `
    -CertStoreLocation Cert:\CurrentUser\My `
    -NotAfter (Get-Date).AddYears(3)
Write-Host "1/4 certificate created - thumbprint $($cert.Thumbprint)"

# --- 2. Export the public half ------------------------------------------------------------
$cer = Join-Path $env:TEMP "qwen-cua-signing.cer"
Export-Certificate -Cert $cert -FilePath $cer -Force | Out-Null
Write-Host "2/4 public certificate exported to $cer"

# --- 3. Trust it (THE security-significant step) -------------------------------------------
# Root      -> makes the chain valid, which is what Get-AuthenticodeSignature checks.
# TrustedPublisher -> suppresses the "unknown publisher" prompt for binaries signed with it.
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
Write-Host "3/4 certificate trusted in LocalMachine Root + TrustedPublisher"

# --- 4. Sign and verify --------------------------------------------------------------------
# Timestamping is best-effort: it keeps the signature valid past certificate expiry, but a
# network failure here should not fail the signing itself.
& $SignTool sign /fd SHA256 /sha1 $cert.Thumbprint /t http://timestamp.digicert.com $exe
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Timestamped signing failed; retrying without a timestamp."
    & $SignTool sign /fd SHA256 /sha1 $cert.Thumbprint $exe
    if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }
}

$status = (Get-AuthenticodeSignature -LiteralPath $exe).Status
Write-Host "4/4 signature status: $status"
if ($status -ne "Valid") { throw "Signature is '$status', expected 'Valid'." }

Write-Host ""
Write-Host "Done. Now re-run the install - it will skip the download (complete.json is present),"
Write-Host "verify this signature, and copy the worker to:"
Write-Host "  $env:ProgramFiles\Qwen\CuaDriver\$Version\qwen-cua-driver-uia.exe"
Write-Host ""
Write-Host "  npm install --no-save --package-lock=false @qwen-code/cua-sdk@$Version"


<#
Remove-CuaSigningTrust - undo everything this script did.

    $subject = "CN=Qwen CUA Local Signing"
    # Remove the trusted public certificate (elevated)
    Get-ChildItem Cert:\LocalMachine\Root, Cert:\LocalMachine\TrustedPublisher |
        Where-Object Subject -eq $subject | Remove-Item -Force
    # Remove the private key
    Get-ChildItem Cert:\CurrentUser\My | Where-Object Subject -eq $subject | Remove-Item -Force
    # Remove the installed worker
    Remove-Item "$env:ProgramFiles\Qwen\CuaDriver" -Recurse -Force -ErrorAction SilentlyContinue

Removing the trust is the part that matters - it revokes the machine's willingness to run
anything else signed with that certificate.
#>
