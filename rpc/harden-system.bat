@echo off
:: ============================================================================
:: SYSTEM HARDENING - Run as Administrator
:: ============================================================================

title System Hardening
color 0C

echo.
echo  ============================================
echo   SYSTEM HARDENING
echo  ============================================
echo.
echo   This will configure Windows Firewall and
echo   disable UPnP for security.
echo.
echo   REQUIRES ADMINISTRATOR PRIVILEGES
echo.

:: Check admin
net session >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Not running as Administrator!
    echo.
    echo   Right-click this file and select
    echo   "Run as administrator"
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"

echo [1/2] Configuring Windows Firewall...
powershell -ExecutionPolicy Bypass -File "hardening\windows-firewall.ps1"

echo.
echo [2/2] Disabling UPnP...
powershell -ExecutionPolicy Bypass -File "hardening\disable-upnp.ps1"

echo.
echo  ============================================
echo   HARDENING COMPLETE
echo  ============================================
echo.

pause
