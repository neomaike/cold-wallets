# Disable UPnP to prevent automatic port forwarding
# Run as Administrator
# This prevents applications from automatically exposing ports to the internet

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "=== Disabling UPnP (SSDP Discovery Service) ===" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# 1. Stop and disable SSDP Discovery Service
# -----------------------------------------------------------------------------
Write-Host "`n[1/3] Stopping SSDP Discovery Service..." -ForegroundColor Yellow

$ssdpService = Get-Service -Name "SSDPSRV" -ErrorAction SilentlyContinue
if ($ssdpService) {
    if ($ssdpService.Status -eq "Running") {
        Stop-Service -Name "SSDPSRV" -Force
        Write-Host "  Stopped SSDP Discovery Service" -ForegroundColor Green
    }
    Set-Service -Name "SSDPSRV" -StartupType Disabled
    Write-Host "  Disabled SSDP Discovery Service startup" -ForegroundColor Green
} else {
    Write-Host "  SSDP Discovery Service not found (may already be removed)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 2. Stop and disable UPnP Device Host
# -----------------------------------------------------------------------------
Write-Host "`n[2/3] Stopping UPnP Device Host..." -ForegroundColor Yellow

$upnpService = Get-Service -Name "upnphost" -ErrorAction SilentlyContinue
if ($upnpService) {
    if ($upnpService.Status -eq "Running") {
        Stop-Service -Name "upnphost" -Force
        Write-Host "  Stopped UPnP Device Host" -ForegroundColor Green
    }
    Set-Service -Name "upnphost" -StartupType Disabled
    Write-Host "  Disabled UPnP Device Host startup" -ForegroundColor Green
} else {
    Write-Host "  UPnP Device Host not found (may already be removed)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 3. Block UPnP ports in firewall
# -----------------------------------------------------------------------------
Write-Host "`n[3/3] Blocking UPnP ports in firewall..." -ForegroundColor Yellow

# Remove existing UPnP block rules
Get-NetFirewallRule -DisplayName "*UPnP Block*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule

# Block SSDP (UDP 1900)
New-NetFirewallRule -DisplayName "UPnP Block - SSDP UDP 1900" `
    -Direction Outbound -Protocol UDP -RemotePort 1900 -Action Block -Profile Any | Out-Null

New-NetFirewallRule -DisplayName "UPnP Block - SSDP UDP 1900 Inbound" `
    -Direction Inbound -Protocol UDP -LocalPort 1900 -Action Block -Profile Any | Out-Null

Write-Host "  Blocked SSDP port 1900/UDP" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Verification
# -----------------------------------------------------------------------------
Write-Host "`n=== Verification ===" -ForegroundColor Cyan

Write-Host "`nService Status:" -ForegroundColor Yellow
$services = @("SSDPSRV", "upnphost")
foreach ($svc in $services) {
    $service = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "  $svc : Status=$($service.Status), StartType=$($service.StartupType)"
    } else {
        Write-Host "  $svc : Not found"
    }
}

Write-Host "`nFirewall Rules:" -ForegroundColor Yellow
Get-NetFirewallRule -DisplayName "*UPnP Block*" |
    Select-Object DisplayName, Enabled, Direction, Action |
    Format-Table -AutoSize

Write-Host @"

NOTE: Also disable UPnP on your router for complete protection:
1. Access router admin panel (usually 192.168.1.1)
2. Find UPnP settings (usually under Advanced or NAT)
3. Disable UPnP / NAT-PMP

"@ -ForegroundColor White

Write-Host "=== UPnP disabled ===" -ForegroundColor Green
