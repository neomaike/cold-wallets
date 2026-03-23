# Backup Script for Private RPC Configuration
# Creates encrypted backup of sensitive files

param(
    [string]$BackupDir = "..\backups",
    [switch]$IncludeData,
    [switch]$NoEncrypt
)

$ErrorActionPreference = "Stop"

Write-Host "=== Private RPC Backup ===" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray

# Create backup directory
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = "$BackupDir\backup-$timestamp"
New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
$backupPath = Resolve-Path $backupPath

Write-Host "Backup location: $backupPath" -ForegroundColor Gray

# =============================================================================
# Define what to backup
# =============================================================================

$configFiles = @(
    # Helios configuration
    "..\nodes\helios\config.toml",
    "..\nodes\helios\docker-compose.yml",

    # Reverse proxy
    "..\nodes\reverse-proxy\nginx.conf",
    "..\nodes\reverse-proxy\docker-compose.yml",

    # L2 templates (if customized)
    "..\nodes\l2-templates\optimism\docker-compose.yml",
    "..\nodes\l2-templates\arbitrum\docker-compose.yml",

    # Hardening scripts
    "..\infra\hardening\*.ps1"
)

$sensitiveFiles = @(
    # WireGuard keys
    "..\infra\wireguard\*.key",
    "..\infra\wireguard\wg0.conf",

    # Tor hidden service
    "..\infra\tor\hidden_service\*",

    # mTLS certificates
    "..\nodes\reverse-proxy\certs\*.key",
    "..\nodes\reverse-proxy\certs\*.crt",
    "..\nodes\reverse-proxy\certs\*.p12"
)

# =============================================================================
# Backup non-sensitive config files
# =============================================================================
Write-Host "`n[1/3] Backing up configuration files..." -ForegroundColor Yellow

$configBackupDir = "$backupPath\config"
New-Item -ItemType Directory -Path $configBackupDir -Force | Out-Null

foreach ($pattern in $configFiles) {
    $files = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        $relativePath = $file.FullName -replace [regex]::Escape((Resolve-Path "..").Path), ""
        $destDir = Split-Path "$configBackupDir$relativePath" -Parent

        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }

        Copy-Item $file.FullName "$configBackupDir$relativePath" -Force
        Write-Host "  $relativePath" -ForegroundColor Gray
    }
}

# =============================================================================
# Backup sensitive files (encrypted)
# =============================================================================
Write-Host "`n[2/3] Backing up sensitive files..." -ForegroundColor Yellow

$sensitiveBackupDir = "$backupPath\sensitive"
New-Item -ItemType Directory -Path $sensitiveBackupDir -Force | Out-Null

$sensitiveFilesToBackup = @()
foreach ($pattern in $sensitiveFiles) {
    $files = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue
    $sensitiveFilesToBackup += $files
}

if ($sensitiveFilesToBackup.Count -eq 0) {
    Write-Host "  No sensitive files found to backup" -ForegroundColor Gray
} else {
    Write-Host "  Found $($sensitiveFilesToBackup.Count) sensitive files" -ForegroundColor Gray

    if ($NoEncrypt) {
        Write-Host "  WARNING: Backing up without encryption (not recommended)" -ForegroundColor Yellow
        foreach ($file in $sensitiveFilesToBackup) {
            Copy-Item $file.FullName $sensitiveBackupDir -Force
            Write-Host "    $($file.Name)" -ForegroundColor Gray
        }
    } else {
        # Check for 7-Zip
        $sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
        if (-not $sevenZip) {
            $sevenZipPath = "C:\Program Files\7-Zip\7z.exe"
            if (Test-Path $sevenZipPath) {
                $sevenZip = Get-Command $sevenZipPath
            }
        }

        if ($sevenZip) {
            # Create encrypted archive
            $archivePath = "$sensitiveBackupDir\secrets.7z"

            Write-Host "`n  Enter encryption password for backup:" -ForegroundColor Cyan
            $password = Read-Host -AsSecureString "  Password"
            $password2 = Read-Host -AsSecureString "  Confirm"

            $pwd1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))
            $pwd2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password2))

            if ($pwd1 -ne $pwd2) {
                Write-Host "  Passwords do not match!" -ForegroundColor Red
                exit 1
            }

            # Create temp directory for files to archive
            $tempDir = "$env:TEMP\rpc-backup-$timestamp"
            New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

            foreach ($file in $sensitiveFilesToBackup) {
                Copy-Item $file.FullName $tempDir -Force
            }

            # Create encrypted archive
            & $sevenZip.Source a -p"$pwd1" -mhe=on $archivePath "$tempDir\*" | Out-Null

            # Clean up temp directory
            Remove-Item $tempDir -Recurse -Force

            # Clear password from memory (best effort in PowerShell)
            if ($pwd1) {
                $charArray = $pwd1.ToCharArray()
                [Array]::Clear($charArray, 0, $charArray.Length)
            }
            if ($pwd2) {
                $charArray2 = $pwd2.ToCharArray()
                [Array]::Clear($charArray2, 0, $charArray2.Length)
            }
            $pwd1 = $null
            $pwd2 = $null
            $charArray = $null
            $charArray2 = $null
            [GC]::Collect()

            Write-Host "  Created encrypted archive: secrets.7z" -ForegroundColor Green
        } else {
            Write-Host "  7-Zip not found. Install from: https://7-zip.org/" -ForegroundColor Yellow
            Write-Host "  Falling back to unencrypted backup" -ForegroundColor Yellow
            foreach ($file in $sensitiveFilesToBackup) {
                Copy-Item $file.FullName $sensitiveBackupDir -Force
            }
        }
    }
}

# =============================================================================
# Backup data (optional)
# =============================================================================
if ($IncludeData) {
    Write-Host "`n[3/3] Backing up data directories..." -ForegroundColor Yellow
    Write-Host "  WARNING: This may take a long time and use significant disk space" -ForegroundColor Yellow

    $dataDir = "$backupPath\data"
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null

    # Helios data (small, just checkpoints)
    if (Test-Path "..\nodes\helios\data") {
        Copy-Item "..\nodes\helios\data" "$dataDir\helios" -Recurse -Force
        Write-Host "  Backed up Helios data" -ForegroundColor Gray
    }

    # Note: L2 data is too large to backup this way
    Write-Host "  Note: L2 node data is too large for this backup method" -ForegroundColor Gray
    Write-Host "  Use disk snapshots or sync from scratch for L2 data" -ForegroundColor Gray
} else {
    Write-Host "`n[3/3] Skipping data backup (use -IncludeData to include)" -ForegroundColor Gray
}

# =============================================================================
# Create backup manifest
# =============================================================================
$manifest = @{
    Timestamp = $timestamp
    Machine = $env:COMPUTERNAME
    User = $env:USERNAME
    Contents = @{
        ConfigFiles = (Get-ChildItem $configBackupDir -Recurse -File).Count
        SensitiveFiles = $sensitiveFilesToBackup.Count
        DataIncluded = $IncludeData
        Encrypted = (-not $NoEncrypt)
    }
}

$manifest | ConvertTo-Json | Set-Content "$backupPath\manifest.json"

# =============================================================================
# Summary
# =============================================================================
Write-Host "`n=== Backup Complete ===" -ForegroundColor Cyan

$backupSize = (Get-ChildItem $backupPath -Recurse | Measure-Object -Property Length -Sum).Sum
$backupSizeMB = [math]::Round($backupSize / 1MB, 2)

Write-Host "Location: $backupPath" -ForegroundColor White
Write-Host "Size: $backupSizeMB MB" -ForegroundColor White

Write-Host "`nBackup contents:" -ForegroundColor Gray
Get-ChildItem $backupPath | ForEach-Object { Write-Host "  $($_.Name)" }

Write-Host "`nREMINDER:" -ForegroundColor Yellow
Write-Host "  - Store backup in secure location (encrypted drive, password manager)" -ForegroundColor Yellow
Write-Host "  - Test restore procedure periodically" -ForegroundColor Yellow
Write-Host "  - Delete old backups securely" -ForegroundColor Yellow

Write-Host "`nTo restore, see: docs\runbook.md" -ForegroundColor Gray
