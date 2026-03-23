# Windows Firewall Hardening for Private RPC
# Run as Administrator
# Idempotent - safe to run multiple times

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "=== Windows Firewall Hardening for Private RPC ===" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# 1. Ensure Windows Firewall is enabled
# -----------------------------------------------------------------------------
Write-Host "`n[1/5] Ensuring Windows Firewall is enabled..." -ForegroundColor Yellow

$firewallProfiles = Get-NetFirewallProfile
foreach ($profile in $firewallProfiles) {
    if (-not $profile.Enabled) {
        Set-NetFirewallProfile -Name $profile.Name -Enabled True
        Write-Host "  Enabled firewall for profile: $($profile.Name)" -ForegroundColor Green
    } else {
        Write-Host "  Firewall already enabled for: $($profile.Name)" -ForegroundColor Gray
    }
}

# -----------------------------------------------------------------------------
# 2. Block inbound RPC port (8545) from all sources except localhost
# -----------------------------------------------------------------------------
Write-Host "`n[2/5] Configuring RPC port (8545) rules..." -ForegroundColor Yellow

# Remove any existing rules for port 8545
$existingRules = Get-NetFirewallRule -DisplayName "*RPC*8545*" -ErrorAction SilentlyContinue
if ($existingRules) {
    $existingRules | Remove-NetFirewallRule
    Write-Host "  Removed existing RPC port rules" -ForegroundColor Gray
}

# Block all inbound on 8545
$blockRule = @{
    DisplayName = "Block RPC 8545 Inbound (Private RPC)"
    Description = "Block all inbound connections to Ethereum RPC port"
    Direction = "Inbound"
    Protocol = "TCP"
    LocalPort = 8545
    Action = "Block"
    Profile = "Any"
}
New-NetFirewallRule @blockRule | Out-Null
Write-Host "  Created rule: Block all inbound on port 8545" -ForegroundColor Green

# Allow localhost only (for apps using 127.0.0.1)
$allowLocalRule = @{
    DisplayName = "Allow RPC 8545 Localhost Only (Private RPC)"
    Description = "Allow localhost connections to Ethereum RPC"
    Direction = "Inbound"
    Protocol = "TCP"
    LocalPort = 8545
    RemoteAddress = "127.0.0.1"
    Action = "Allow"
    Profile = "Any"
}
New-NetFirewallRule @allowLocalRule | Out-Null
Write-Host "  Created rule: Allow localhost on port 8545" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 3. Block WebSocket port (8546) similarly
# -----------------------------------------------------------------------------
Write-Host "`n[3/5] Configuring WebSocket port (8546) rules..." -ForegroundColor Yellow

$existingWsRules = Get-NetFirewallRule -DisplayName "*RPC*8546*" -ErrorAction SilentlyContinue
if ($existingWsRules) {
    $existingWsRules | Remove-NetFirewallRule
}

New-NetFirewallRule -DisplayName "Block RPC 8546 Inbound (Private RPC)" `
    -Direction Inbound -Protocol TCP -LocalPort 8546 -Action Block -Profile Any | Out-Null

New-NetFirewallRule -DisplayName "Allow RPC 8546 Localhost Only (Private RPC)" `
    -Direction Inbound -Protocol TCP -LocalPort 8546 -RemoteAddress 127.0.0.1 -Action Allow -Profile Any | Out-Null

Write-Host "  Configured WebSocket port rules" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 4. Optional: WireGuard port (51820) - only if using remote access
# -----------------------------------------------------------------------------
Write-Host "`n[4/5] WireGuard port (51820) configuration..." -ForegroundColor Yellow

$wgRuleExists = Get-NetFirewallRule -DisplayName "*WireGuard*51820*" -ErrorAction SilentlyContinue
if (-not $wgRuleExists) {
    # By default, block WireGuard port
    # Uncomment the allow rule if you're setting up remote access
    New-NetFirewallRule -DisplayName "Block WireGuard 51820 (Private RPC)" `
        -Direction Inbound -Protocol UDP -LocalPort 51820 -Action Block -Profile Any | Out-Null
    Write-Host "  WireGuard port blocked by default" -ForegroundColor Gray
    Write-Host "  (Edit this script to allow if setting up remote access)" -ForegroundColor Gray
} else {
    Write-Host "  WireGuard rules already exist" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 5. Display current rules for verification
# -----------------------------------------------------------------------------
Write-Host "`n[5/5] Current firewall rules for Private RPC:" -ForegroundColor Yellow

Get-NetFirewallRule -DisplayName "*Private RPC*" |
    Select-Object DisplayName, Enabled, Direction, Action |
    Format-Table -AutoSize

# -----------------------------------------------------------------------------
# Verification commands
# -----------------------------------------------------------------------------
Write-Host "`n=== Verification Commands ===" -ForegroundColor Cyan
Write-Host @"

Run these commands to verify configuration:

1. Check listening ports (should show 127.0.0.1:8545, not 0.0.0.0:8545):
   netstat -an | findstr 8545

2. Test from another device on LAN (should FAIL):
   curl http://YOUR_LAN_IP:8545

3. Test from localhost (should WORK):
   curl http://127.0.0.1:8545 -X POST -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"id\":1}"

"@ -ForegroundColor White

Write-Host "=== Firewall hardening complete ===" -ForegroundColor Green
