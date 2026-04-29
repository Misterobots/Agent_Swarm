# Wake-on-LAN script for Hopper
# Usage: .\wake_hopper.ps1 [-MacAddress "XX:XX:XX:XX:XX:XX"]

param(
    [string]$MacAddress = ""
)

function Send-WakeOnLan {
    param(
        [string]$MacAddress,
        [string]$BroadcastAddress = "192.168.2.255",
        [int]$Port = 9
    )
    
    # Remove common separators and validate
    $mac = $MacAddress -replace '[:\-]', ''
    
    if ($mac.Length -ne 12) {
        Write-Host "[ERROR] Invalid MAC address format. Use XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX" -ForegroundColor Red
        return $false
    }
    
    # Convert MAC to byte array
    try {
        $macBytes = [byte[]]@()
        for ($i = 0; $i -lt 12; $i += 2) {
            $macBytes += [Convert]::ToByte($mac.Substring($i, 2), 16)
        }
    } catch {
        Write-Host "[ERROR] Failed to parse MAC address: $_" -ForegroundColor Red
        return $false
    }
    
    # Build magic packet (6 bytes of 0xFF + 16 repetitions of MAC)
    $packet = [byte[]](,0xFF * 6)
    $packet += $macBytes * 16
    
    # Send magic packet
    try {
        $udpClient = New-Object System.Net.Sockets.UdpClient
        $udpClient.Connect([System.Net.IPAddress]::Parse($BroadcastAddress), $Port)
        $udpClient.Send($packet, $packet.Length) | Out-Null
        $udpClient.Close()
        
        Write-Host "[OK] Magic packet sent to $MacAddress via $BroadcastAddress" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[ERROR] Failed to send magic packet: $_" -ForegroundColor Red
        return $false
    }
}

# Main
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Wake-on-LAN: Hopper (192.168.2.102)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ([string]::IsNullOrWhiteSpace($MacAddress)) {
    Write-Host "MAC address not provided. Checking network.env..." -ForegroundColor Yellow
    
    # Try to load from network.env
    $envFile = Join-Path $PSScriptRoot ".." "network.env"
    if (Test-Path $envFile) {
        $content = Get-Content $envFile | Where-Object { $_ -match "^HOPPER_MAC=" }
        if ($content) {
            $MacAddress = ($content -split "=")[1]
            Write-Host "Found MAC in network.env: $MacAddress" -ForegroundColor Green
        }
    }
}

if ([string]::IsNullOrWhiteSpace($MacAddress)) {
    Write-Host ""
    Write-Host "Please provide Hopper's MAC address:" -ForegroundColor Yellow
    Write-Host "  1. Check your router's DHCP reservation for 192.168.2.102"
    Write-Host "  2. Or run 'ip link' on Hopper when it's online"
    Write-Host ""
    Write-Host "Usage: .\wake_hopper.ps1 -MacAddress 'XX:XX:XX:XX:XX:XX'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To save it permanently, add to network.env:" -ForegroundColor Yellow
    Write-Host "  HOPPER_MAC=XX:XX:XX:XX:XX:XX"
    exit 1
}

# Send WoL packet
Write-Host "Sending Wake-on-LAN packet to Hopper..." -ForegroundColor Cyan
$success = Send-WakeOnLan -MacAddress $MacAddress

if ($success) {
    Write-Host ""
    Write-Host "Waiting for Hopper to boot (30 seconds)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # Check if Hopper responds
    for ($i = 1; $i -le 6; $i++) {
        Write-Host "  Ping attempt $i/6..." -NoNewline
        $ping = Test-Connection -ComputerName 192.168.2.102 -Count 1 -Quiet -ErrorAction SilentlyContinue
        
        if ($ping) {
            Write-Host " [OK]" -ForegroundColor Green
            Write-Host ""
            Write-Host "[SUCCESS] Hopper is online!" -ForegroundColor Green
            Write-Host "  Waiting 10 more seconds for services to start..." -ForegroundColor Yellow
            Start-Sleep -Seconds 10
            
            Write-Host ""
            Write-Host "Services should be starting. Check with:" -ForegroundColor Cyan
            Write-Host "  ssh misterobots@192.168.2.102 'docker ps'"
            exit 0
        } else {
            Write-Host " [FAIL]" -ForegroundColor Red
            Start-Sleep -Seconds 5
        }
    }
    
    Write-Host ""
    Write-Host "[WARNING] Hopper did not respond to ping after 30 seconds" -ForegroundColor Yellow
    Write-Host "  - Check if WoL is enabled in BIOS"
    Write-Host "  - Verify the MAC address is correct"
    Write-Host "  - Try physically powering on the machine"
    exit 1
} else {
    exit 1
}
