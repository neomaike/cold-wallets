# Generate mTLS Certificates for RPC Proxy
# Creates CA, server cert, and client cert

param(
    [string]$OutputDir = "..\nodes\reverse-proxy\certs",
    [int]$ValidDays = 365,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "=== Generating mTLS Certificates ===" -ForegroundColor Cyan

# Create output directory
$certsPath = Resolve-Path $OutputDir -ErrorAction SilentlyContinue
if (-not $certsPath) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $certsPath = Resolve-Path $OutputDir
}

Write-Host "Output directory: $certsPath" -ForegroundColor Gray

# Check if certs already exist
$existingCerts = Get-ChildItem "$certsPath\*.crt" -ErrorAction SilentlyContinue
if ($existingCerts -and -not $Force) {
    Write-Host "`nCertificates already exist. Use -Force to regenerate." -ForegroundColor Yellow
    Write-Host "Existing certificates:" -ForegroundColor Gray
    $existingCerts | ForEach-Object { Write-Host "  $_" }
    exit 0
}

# Check for OpenSSL
$opensslPath = Get-Command openssl -ErrorAction SilentlyContinue
if (-not $opensslPath) {
    Write-Host "`nOpenSSL not found. Install options:" -ForegroundColor Red
    Write-Host "  1. Git for Windows includes OpenSSL: https://git-scm.com/"
    Write-Host "  2. OpenSSL for Windows: https://slproweb.com/products/Win32OpenSSL.html"
    Write-Host "  3. Use WSL: wsl openssl ..."
    exit 1
}

Write-Host "Using OpenSSL: $($opensslPath.Source)" -ForegroundColor Gray

# -----------------------------------------------------------------------------
# 1. Generate CA (Certificate Authority)
# -----------------------------------------------------------------------------
Write-Host "`n[1/4] Generating Certificate Authority..." -ForegroundColor Yellow

$caKeyPath = "$certsPath\ca.key"
$caCrtPath = "$certsPath\ca.crt"

# Generate CA private key
openssl genrsa -out $caKeyPath 4096 2>&1 | Out-Null

# Generate CA certificate
openssl req -new -x509 -days $ValidDays -key $caKeyPath -out $caCrtPath `
    -subj "/CN=Private RPC CA/O=Private RPC/C=XX" 2>&1 | Out-Null

Write-Host "  Created: ca.key, ca.crt" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 2. Generate Server Certificate
# -----------------------------------------------------------------------------
Write-Host "`n[2/4] Generating Server Certificate..." -ForegroundColor Yellow

$serverKeyPath = "$certsPath\server.key"
$serverCsrPath = "$certsPath\server.csr"
$serverCrtPath = "$certsPath\server.crt"
$serverExtPath = "$certsPath\server.ext"

# Generate server private key
openssl genrsa -out $serverKeyPath 2048 2>&1 | Out-Null

# Generate CSR
openssl req -new -key $serverKeyPath -out $serverCsrPath `
    -subj "/CN=localhost/O=Private RPC/C=XX" 2>&1 | Out-Null

# Create extensions file for SAN
@"
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
IP.1 = 127.0.0.1
IP.2 = 10.0.0.1
"@ | Set-Content $serverExtPath

# Sign server certificate with CA
openssl x509 -req -in $serverCsrPath -CA $caCrtPath -CAkey $caKeyPath `
    -CAcreateserial -out $serverCrtPath -days $ValidDays `
    -extfile $serverExtPath 2>&1 | Out-Null

# Clean up temporary files
Remove-Item $serverCsrPath, $serverExtPath -Force

Write-Host "  Created: server.key, server.crt" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 3. Generate Client Certificate
# -----------------------------------------------------------------------------
Write-Host "`n[3/4] Generating Client Certificate..." -ForegroundColor Yellow

$clientKeyPath = "$certsPath\client.key"
$clientCsrPath = "$certsPath\client.csr"
$clientCrtPath = "$certsPath\client.crt"
$clientP12Path = "$certsPath\client.p12"

# Generate client private key
openssl genrsa -out $clientKeyPath 2048 2>&1 | Out-Null

# Generate CSR
openssl req -new -key $clientKeyPath -out $clientCsrPath `
    -subj "/CN=RPC Client/O=Private RPC/C=XX" 2>&1 | Out-Null

# Sign client certificate with CA
openssl x509 -req -in $clientCsrPath -CA $caCrtPath -CAkey $caKeyPath `
    -CAcreateserial -out $clientCrtPath -days $ValidDays 2>&1 | Out-Null

# Create PKCS12 bundle for browser import
Write-Host "  Enter password for client certificate (PKCS12):" -ForegroundColor Cyan
$p12Password = Read-Host -AsSecureString "  Password"
$p12Plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($p12Password))

if ([string]::IsNullOrEmpty($p12Plain)) {
    Write-Host "  WARNING: Empty password - certificate file will be unprotected" -ForegroundColor Yellow
    openssl pkcs12 -export -out $clientP12Path `
        -inkey $clientKeyPath -in $clientCrtPath -certfile $caCrtPath `
        -passout pass: 2>&1 | Out-Null
} else {
    openssl pkcs12 -export -out $clientP12Path `
        -inkey $clientKeyPath -in $clientCrtPath -certfile $caCrtPath `
        -passout pass:$p12Plain 2>&1 | Out-Null
}

# Clear password from memory
$p12Plain = $null
$p12Password = $null

# Clean up temporary files
Remove-Item $clientCsrPath -Force

Write-Host "  Created: client.key, client.crt, client.p12" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 4. Set File Permissions (Windows)
# -----------------------------------------------------------------------------
Write-Host "`n[4/4] Setting file permissions..." -ForegroundColor Yellow

$privateFiles = @($caKeyPath, $serverKeyPath, $clientKeyPath)
foreach ($file in $privateFiles) {
    # Remove inheritance
    $acl = Get-Acl $file
    $acl.SetAccessRuleProtection($true, $false)

    # Grant only current user full control
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
Write-Host "`n=== Certificate Generation Complete ===" -ForegroundColor Cyan

Write-Host "`nGenerated files:" -ForegroundColor Yellow
Get-ChildItem $certsPath | ForEach-Object {
    $size = "{0:N0} bytes" -f $_.Length
    Write-Host "  $($_.Name) ($size)"
}

Write-Host "`nUsage:" -ForegroundColor Yellow
Write-Host @"

1. Start Nginx proxy:
   cd nodes\reverse-proxy
   docker compose up -d

2. Test with curl:
   curl --cacert certs/ca.crt --cert certs/client.crt --key certs/client.key \
        https://127.0.0.1:8443 -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'

3. For browser import, use client.p12 (PKCS12 format)

"@ -ForegroundColor White

Write-Host "Certificate validity: $ValidDays days" -ForegroundColor Gray
Write-Host "Regenerate with: .\generate-certs.ps1 -Force" -ForegroundColor Gray
