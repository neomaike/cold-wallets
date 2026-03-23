# Generate WireGuard Keys for Server and Client
# Requires WireGuard to be installed

param(
    [string]$OutputDir = "..\infra\wireguard",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "=== Generating WireGuard Keys ===" -ForegroundColor Cyan

# Check if wg command is available
$wgPath = Get-Command wg -ErrorAction SilentlyContinue
if (-not $wgPath) {
    Write-Host "`nWireGuard not found in PATH." -ForegroundColor Red
    Write-Host "Install from: https://www.wireguard.com/install/" -ForegroundColor Yellow
    Write-Host "`nAfter installation, the wg command should be available."
    exit 1
}

Write-Host "Using WireGuard: $($wgPath.Source)" -ForegroundColor Gray

# Resolve output directory
$keysPath = Resolve-Path $OutputDir -ErrorAction SilentlyContinue
if (-not $keysPath) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $keysPath = Resolve-Path $OutputDir
}

Write-Host "Output directory: $keysPath" -ForegroundColor Gray

# Check for existing keys
$existingKeys = Get-ChildItem "$keysPath\*.key" -ErrorAction SilentlyContinue
if ($existingKeys -and -not $Force) {
    Write-Host "`nKeys already exist. Use -Force to regenerate." -ForegroundColor Yellow
    Write-Host "WARNING: Regenerating keys will require reconfiguring all peers!" -ForegroundColor Red
    Write-Host "`nExisting keys:" -ForegroundColor Gray
    $existingKeys | ForEach-Object { Write-Host "  $_" }
    exit 0
}

# -----------------------------------------------------------------------------
# Generate Server Keys
# -----------------------------------------------------------------------------
Write-Host "`n[1/3] Generating Server Keys..." -ForegroundColor Yellow

$serverPrivateKey = & wg genkey
$serverPublicKey = $serverPrivateKey | & wg pubkey

$serverPrivateKey | Set-Content "$keysPath\server_private.key"
$serverPublicKey | Set-Content "$keysPath\server_public.key"

Write-Host "  Created: server_private.key, server_public.key" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Generate Client Keys
# -----------------------------------------------------------------------------
Write-Host "`n[2/3] Generating Client Keys..." -ForegroundColor Yellow

$clientPrivateKey = & wg genkey
$clientPublicKey = $clientPrivateKey | & wg pubkey

$clientPrivateKey | Set-Content "$keysPath\client_private.key"
$clientPublicKey | Set-Content "$keysPath\client_public.key"

Write-Host "  Created: client_private.key, client_public.key" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Generate Pre-shared Key (optional extra security)
# -----------------------------------------------------------------------------
Write-Host "`n[3/3] Generating Pre-shared Key..." -ForegroundColor Yellow

$presharedKey = & wg genpsk
$presharedKey | Set-Content "$keysPath\preshared.key"

Write-Host "  Created: preshared.key" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Set File Permissions
# -----------------------------------------------------------------------------
Write-Host "`nSetting file permissions..." -ForegroundColor Yellow

$privateFiles = Get-ChildItem "$keysPath\*private*.key", "$keysPath\preshared.key"
foreach ($file in $privateFiles) {
    $acl = Get-Acl $file
    $acl.SetAccessRuleProtection($true, $false)

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $identity, "FullControl", "Allow")
    $acl.AddAccessRule($rule)

    Set-Acl $file $acl
}

Write-Host "  Private keys secured (current user only)" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Host "`n=== Key Generation Complete ===" -ForegroundColor Cyan

Write-Host "`nServer Public Key (share with clients):" -ForegroundColor Yellow
Write-Host "  $serverPublicKey" -ForegroundColor White

Write-Host "`nClient Public Key (add to server config):" -ForegroundColor Yellow
Write-Host "  $clientPublicKey" -ForegroundColor White

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host @"

1. Edit wg0.conf.example and replace:
   - REPLACE_WITH_SERVER_PRIVATE_KEY -> contents of server_private.key
   - REPLACE_WITH_CLIENT_PUBLIC_KEY -> contents of client_public.key
   - Save as wg0.conf

2. Edit client.conf.example and replace:
   - REPLACE_WITH_CLIENT_PRIVATE_KEY -> contents of client_private.key
   - REPLACE_WITH_SERVER_PUBLIC_KEY -> contents of server_public.key
   - YOUR_HOME_PUBLIC_IP_OR_DOMAIN -> your home IP or DynDNS
   - Save and import into WireGuard on client device

3. (Optional) Add preshared key to both configs for extra security

"@ -ForegroundColor White

Write-Host "Files created:" -ForegroundColor Gray
Get-ChildItem "$keysPath\*.key" | ForEach-Object { Write-Host "  $($_.Name)" }

Write-Host "`nSECURITY WARNING:" -ForegroundColor Red
Write-Host "  - NEVER share *_private.key files" -ForegroundColor Red
Write-Host "  - NEVER commit *.key files to git" -ForegroundColor Red
Write-Host "  - Backup private keys encrypted" -ForegroundColor Red
