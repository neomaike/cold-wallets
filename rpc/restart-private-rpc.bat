@echo off
:: ============================================================================
:: RESTART PRIVATE RPC
:: ============================================================================

title Private RPC - Restarting...
color 0E

echo.
echo  ============================================
echo   RESTARTING PRIVATE RPC
echo  ============================================
echo.

cd /d "%~dp0"

echo [1/2] Stopping...
cd helios
docker compose down
cd ..\..

echo.
echo [2/2] Starting...
cd helios
docker compose up -d
cd ..\..

echo.
echo Waiting for RPC...
timeout /t 10 /nobreak >nul

:: Quick test
curl -s -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"

echo.
echo.
echo  ============================================
echo   RESTART COMPLETE
echo  ============================================
echo.

pause
