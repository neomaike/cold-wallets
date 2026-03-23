@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: FIRST TIME SETUP - Run this once to configure everything
:: NO API KEY REQUIRED - Uses public RPCs
:: ============================================================================

title Private RPC - First Time Setup
color 0E

echo.
echo  ============================================
echo   PRIVATE RPC - FIRST TIME SETUP
echo  ============================================
echo.
echo   This script will:
echo   1. Configure Windows Firewall
echo   2. Disable UPnP (prevents auto port forwarding)
echo   3. Create Helios configuration
echo   4. Pull Docker images
echo.
echo   NO API KEY REQUIRED - Uses public RPCs
echo.
echo   Press any key to continue or Ctrl+C to cancel...
pause >nul

cd /d "%~dp0"

:: ============================================================================
:: Step 1: Firewall Hardening
:: ============================================================================
echo.
echo [1/4] Configuring Windows Firewall...
echo       (Requires Administrator privileges)
echo.

:: Check if running as admin
net session >nul 2>&1
if errorlevel 1 (
    echo       Not running as Administrator.
    echo       Please right-click this script and "Run as Administrator"
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "hardening\windows-firewall.ps1"

:: ============================================================================
:: Step 2: Disable UPnP
:: ============================================================================
echo.
echo [2/4] Disabling UPnP...

powershell -ExecutionPolicy Bypass -File "hardening\disable-upnp.ps1"

:: ============================================================================
:: Step 3: Create Helios Config
:: ============================================================================
echo.
echo [3/4] Creating Helios configuration...

if exist "helios\config.toml" (
    echo       Config already exists.
    set /p OVERWRITE="       Overwrite with fresh config? (y/N): "
    if /i "!OVERWRITE!"=="y" (
        copy /y "helios\config.example.toml" "helios\config.toml" >nul
        echo       Config reset to defaults.
    ) else (
        echo       Keeping existing config.
    )
) else (
    copy "helios\config.example.toml" "helios\config.toml" >nul
    echo       Config created with public RPCs (no API key needed)
)

:: ============================================================================
:: Step 4: Pull Docker Images
:: ============================================================================
echo.
echo [4/4] Pulling Docker images (this may take a few minutes)...

docker pull ghcr.io/a16z/helios:0.11.0

if errorlevel 1 (
    echo       [WARNING] Could not pull Helios image.
    echo       Make sure Docker is running and try again.
) else (
    echo       Docker images ready.
)

:: ============================================================================
:: Done
:: ============================================================================
echo.
echo  ============================================
echo   SETUP COMPLETE - NO API KEY NEEDED
echo  ============================================
echo.
echo   The config uses public RPCs:
echo   - 1RPC.io (privacy focused, no logging)
echo   - Fallbacks: LlamaRPC, Ankr, PublicNode
echo.
echo   Next steps:
echo.
echo   1. Make sure Tor is running (port 9050)
echo   2. Run: start-private-rpc.bat
echo   3. Configure MetaMask with http://127.0.0.1:8545
echo.
echo   Optional:
echo   - Run test-privacy.bat to verify Tor is working
echo.

pause
