# Start All Private RPC Services
# Convenience script to start the full stack

param(
    [switch]$WithTor,
    [switch]$WithProxy
)

$ErrorActionPreference = "Stop"

Write-Host "=== Starting Private RPC Stack ===" -ForegroundColor Cyan

# Check Docker
$dockerRunning = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerRunning) {
    Write-Host "Starting Docker Desktop..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "Waiting for Docker to start..."
    Start-Sleep -Seconds 30
}

# Verify Docker is responding
try {
    docker ps | Out-Null
} catch {
    Write-Host "Docker not responding. Please start Docker Desktop manually." -ForegroundColor Red
    exit 1
}

Write-Host "Docker is running" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Start Tor (optional, first because Helios might use it)
# -----------------------------------------------------------------------------
if ($WithTor) {
    Write-Host "`n[1/3] Starting Tor Hidden Service..." -ForegroundColor Yellow
    Push-Location "..\infra\tor"
    docker compose up -d
    Pop-Location

    # Wait for Tor to bootstrap
    Write-Host "  Waiting for Tor to bootstrap..."
    Start-Sleep -Seconds 10

    # Get .onion address
    $onionFile = "..\infra\tor\hidden_service\hostname"
    if (Test-Path $onionFile) {
        $onionAddress = Get-Content $onionFile
        Write-Host "  Tor Hidden Service: $onionAddress" -ForegroundColor Green
    } else {
        Write-Host "  Hidden service generating... check later" -ForegroundColor Gray
    }
} else {
    Write-Host "`n[1/3] Tor: Skipped (use -WithTor to enable)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# Start Helios
# -----------------------------------------------------------------------------
Write-Host "`n[2/3] Starting Helios Light Client..." -ForegroundColor Yellow

# Check config exists
$configPath = "..\nodes\helios\config.toml"
if (-not (Test-Path $configPath)) {
    Write-Host "  Config not found. Creating from example..." -ForegroundColor Yellow
    Copy-Item "..\nodes\helios\config.example.toml" $configPath
    Write-Host "  IMPORTANT: Edit $configPath with your RPC API key" -ForegroundColor Red
}

Push-Location "..\nodes\helios"
docker compose up -d
Pop-Location

Write-Host "  Waiting for Helios to start..."
Start-Sleep -Seconds 5

# Check if responding
$maxRetries = 12
$retryCount = 0
$rpcReady = $false

while ($retryCount -lt $maxRetries -and -not $rpcReady) {
    try {
        $body = '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8545" -Method Post `
            -ContentType "application/json" -Body $body -TimeoutSec 5
        if ($response.result) {
            $rpcReady = $true
        }
    } catch {
        $retryCount++
        Write-Host "  Waiting for RPC... ($retryCount/$maxRetries)" -ForegroundColor Gray
        Start-Sleep -Seconds 5
    }
}

if ($rpcReady) {
    $blockHex = $response.result
    $blockNum = [Convert]::ToInt64($blockHex, 16)
    Write-Host "  Helios running - Block: $blockNum" -ForegroundColor Green
} else {
    Write-Host "  Helios started but RPC not responding yet" -ForegroundColor Yellow
    Write-Host "  Check logs: docker logs helios-client" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# Start Nginx Proxy (optional)
# -----------------------------------------------------------------------------
if ($WithProxy) {
    Write-Host "`n[3/3] Starting Nginx Proxy with mTLS..." -ForegroundColor Yellow

    # Check certs exist
    $certsPath = "..\nodes\reverse-proxy\certs"
    if (-not (Test-Path "$certsPath\server.crt")) {
        Write-Host "  Certificates not found. Generating..." -ForegroundColor Yellow
        & ".\generate-certs.ps1"
    }

    Push-Location "..\nodes\reverse-proxy"
    docker compose up -d
    Pop-Location

    Write-Host "  Nginx proxy running on https://127.0.0.1:8443" -ForegroundColor Green
} else {
    Write-Host "`n[3/3] Nginx Proxy: Skipped (use -WithProxy to enable)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Host "`n=== Stack Started ===" -ForegroundColor Cyan

Write-Host "`nRunning containers:" -ForegroundColor Yellow
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`nRPC Endpoint: http://127.0.0.1:8545" -ForegroundColor Green

if ($WithProxy) {
    Write-Host "mTLS Endpoint: https://127.0.0.1:8443" -ForegroundColor Green
}

if ($WithTor -and (Test-Path "..\infra\tor\hidden_service\hostname")) {
    $onion = Get-Content "..\infra\tor\hidden_service\hostname"
    Write-Host "Tor Endpoint: $onion" -ForegroundColor Green
}

Write-Host "`nTest RPC:" -ForegroundColor Gray
Write-Host '  curl http://127.0.0.1:8545 -X POST -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"id\":1}"'

Write-Host "`nRun health check: .\healthcheck.ps1" -ForegroundColor Gray
