# Health Check Script for Private RPC Stack
# Validates security configuration and service status

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"

# Resolve project root relative to script location
$scriptDir = $PSScriptRoot
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")

Write-Host "=== Private RPC Health Check ===" -ForegroundColor Cyan
Write-Host "Running at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

$passed = 0
$failed = 0
$warnings = 0

function Test-Check {
    param(
        [string]$Name,
        [scriptblock]$Test,
        [string]$FailMessage = "",
        [switch]$Critical
    )

    Write-Host -NoNewline "  $Name... "

    try {
        $result = & $Test
        if ($result) {
            Write-Host "[PASS]" -ForegroundColor Green
            $script:passed++
            return $true
        } else {
            if ($Critical) {
                Write-Host "[FAIL]" -ForegroundColor Red
                $script:failed++
            } else {
                Write-Host "[WARN]" -ForegroundColor Yellow
                $script:warnings++
            }
            if ($FailMessage) { Write-Host "    $FailMessage" -ForegroundColor Gray }
            return $false
        }
    } catch {
        Write-Host "[ERROR]" -ForegroundColor Red
        Write-Host "    $_" -ForegroundColor Gray
        $script:failed++
        return $false
    }
}

# =============================================================================
# 1. Service Status Checks
# =============================================================================
Write-Host "[1/5] Service Status" -ForegroundColor Yellow

Test-Check "Docker running" {
    $dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
    $null -ne $dockerProcess
} -FailMessage "Start Docker Desktop" -Critical

Test-Check "Helios container exists" {
    $container = docker ps -a --filter "name=helios" --format "{{.Names}}" 2>$null
    $container -match "helios"
} -FailMessage "Run: docker compose up -d in helios"

Test-Check "Helios container running" {
    $status = docker ps --filter "name=helios" --filter "status=running" --format "{{.Names}}" 2>$null
    $status -match "helios"
} -FailMessage "Container stopped. Check: docker logs helios-client" -Critical

# =============================================================================
# 2. Network Security Checks
# =============================================================================
Write-Host "`n[2/5] Network Security" -ForegroundColor Yellow

Test-Check "Port 8545 bound to localhost only" {
    $listening = netstat -an | Select-String ":8545"
    if ($listening) {
        # Should show 127.0.0.1:8545, NOT 0.0.0.0:8545
        $exposed = $listening | Select-String "0.0.0.0:8545"
        $null -eq $exposed
    } else {
        # Port not listening at all - could be docker network mode
        $true
    }
} -FailMessage "RPC exposed on all interfaces! Fix docker-compose.yml" -Critical

Test-Check "Port 8545 not accessible from LAN" {
    # Get local IP
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.IPAddress -notmatch "^169" } |
        Select-Object -First 1).IPAddress

    if ($localIP) {
        # Try to connect to RPC on LAN IP - should fail
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        try {
            $tcpClient.Connect($localIP, 8545)
            $tcpClient.Close()
            $false  # Connection succeeded = bad
        } catch {
            $true   # Connection failed = good
        }
    } else {
        $true  # No LAN IP found, can't test
    }
} -FailMessage "RPC accessible from LAN! Check firewall rules" -Critical

Test-Check "Windows Firewall enabled" {
    $profiles = Get-NetFirewallProfile | Where-Object { $_.Enabled -eq $true }
    $profiles.Count -ge 1
} -FailMessage "Enable Windows Firewall"

Test-Check "RPC firewall rule exists" {
    $rule = Get-NetFirewallRule -DisplayName "*Private RPC*" -ErrorAction SilentlyContinue
    $null -ne $rule
} -FailMessage "Run: rpc\hardening\windows-firewall.ps1"

# =============================================================================
# 3. RPC Functionality Checks
# =============================================================================
Write-Host "`n[3/5] RPC Functionality" -ForegroundColor Yellow

Test-Check "RPC responding on localhost" {
    $body = '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8545" -Method Post `
            -ContentType "application/json" -Body $body -TimeoutSec 5
        $null -ne $response.result
    } catch {
        $false
    }
} -FailMessage "RPC not responding. Check Helios logs" -Critical

Test-Check "Helios synced (recent block)" {
    $body = '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8545" -Method Post `
            -ContentType "application/json" -Body $body -TimeoutSec 5
        $blockHex = $response.result
        $blockNum = [Convert]::ToInt64($blockHex, 16)
        # Block number should be reasonable (> 18 million for mainnet as of 2024)
        $blockNum -gt 18000000
    } catch {
        $false
    }
} -FailMessage "Block number seems wrong. Check sync status"

Test-Check "Not exposing admin APIs" {
    $body = '{"jsonrpc":"2.0","method":"admin_nodeInfo","params":[],"id":1}'
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8545" -Method Post `
            -ContentType "application/json" -Body $body -TimeoutSec 5
        # Should return error (method not found)
        $response.error -ne $null
    } catch {
        $true  # Error is expected
    }
}

# =============================================================================
# 4. Optional Services
# =============================================================================
Write-Host "`n[4/5] Optional Services" -ForegroundColor Yellow

Test-Check "Tor container (if configured)" {
    $container = docker ps --filter "name=tor" --filter "status=running" --format "{{.Names}}" 2>$null
    if ($container) {
        $true
    } else {
        $true  # Not a failure if not configured
    }
}

Test-Check "Nginx proxy (if configured)" {
    $container = docker ps --filter "name=rpc-proxy" --filter "status=running" --format "{{.Names}}" 2>$null
    if ($container) {
        $true
    } else {
        $true  # Not a failure if not configured
    }
}

# =============================================================================
# 5. Security Hardening
# =============================================================================
Write-Host "`n[5/5] Security Hardening" -ForegroundColor Yellow

Test-Check "UPnP service disabled" {
    $ssdp = Get-Service -Name "SSDPSRV" -ErrorAction SilentlyContinue
    if ($ssdp) {
        $ssdp.Status -ne "Running"
    } else {
        $true
    }
} -FailMessage "Run: rpc\hardening\disable-upnp.ps1"

Test-Check "No private keys in project" {
    $keyFiles = Get-ChildItem -Path $projectRoot -Recurse -Include "*.key" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "\\(infra|nodes)\\.*\\(wireguard|certs)\\" }
    $keyFiles.Count -eq 0
} -FailMessage "Found .key files outside expected directories"

Test-Check "Git not tracking secrets" {
    $gitignore = Get-Content (Join-Path $projectRoot ".gitignore") -ErrorAction SilentlyContinue
    if ($gitignore) {
        $gitignore -match "\.key" -and $gitignore -match "hidden_service"
    } else {
        $false
    }
} -FailMessage "Add *.key and hidden_service to .gitignore"

# =============================================================================
# Summary
# =============================================================================
Write-Host "`n=== Health Check Summary ===" -ForegroundColor Cyan
Write-Host "  Passed:   $passed" -ForegroundColor Green
Write-Host "  Warnings: $warnings" -ForegroundColor Yellow
Write-Host "  Failed:   $failed" -ForegroundColor Red

if ($failed -gt 0) {
    Write-Host "`nCRITICAL ISSUES FOUND - Review and fix before using RPC" -ForegroundColor Red
    exit 1
} elseif ($warnings -gt 0) {
    Write-Host "`nSome warnings - Review recommended" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "`nAll checks passed - RPC stack is healthy" -ForegroundColor Green
    exit 0
}
