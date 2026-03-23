@echo off
:: ============================================================================
:: STOP PRIVATE RPC
:: ============================================================================

title Private RPC - Stopping...
color 0C

echo.
echo  ============================================
echo   STOPPING PRIVATE RPC
echo  ============================================
echo.

cd /d "%~dp0"

echo [1/2] Stopping Helios...
cd helios
docker compose down
cd ..\..

echo.
echo [2/2] Checking status...
docker ps --filter "name=helios" --format "{{.Names}}: {{.Status}}"

echo.
echo  ============================================
echo   PRIVATE RPC STOPPED
echo  ============================================
echo.
echo   Note: Tor is still running (managed separately)
echo.

pause
