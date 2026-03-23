@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: STATUS CHECK - Private RPC
:: ============================================================================

title Private RPC - Status
color 0B

echo.
echo  ============================================
echo   PRIVATE RPC STATUS
echo  ============================================
echo.

cd /d "%~dp0"

:: ============================================================================
:: Check Tor
:: ============================================================================
echo [TOR]
set TOR_FOUND=0
curl -s --socks5 127.0.0.1:9050 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    echo   Status: ONLINE (port 9050 - Docker/Service)
    for /f "delims=" %%i in ('curl -s --socks5 127.0.0.1:9050 https://check.torproject.org/api/ip 2^>nul') do echo   Exit: %%i
    set TOR_FOUND=1
)
curl -s --socks5 127.0.0.1:9150 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    echo   Status: ONLINE (port 9150 - Tor Browser)
    for /f "delims=" %%i in ('curl -s --socks5 127.0.0.1:9150 https://check.torproject.org/api/ip 2^>nul') do echo   Exit: %%i
    set TOR_FOUND=1
)
if "!TOR_FOUND!"=="0" (
    echo   Status: OFFLINE (ports 9050 and 9150 not responding)
)

:: ============================================================================
:: Check Docker
:: ============================================================================
echo.
echo [DOCKER]
docker info >nul 2>&1
if errorlevel 1 (
    echo   Status: NOT RUNNING
) else (
    echo   Status: RUNNING
)

:: ============================================================================
:: Check Helios Container
:: ============================================================================
echo.
echo [HELIOS CONTAINER]
for /f "tokens=*" %%i in ('docker ps --filter "name=helios" --format "{{.Status}}" 2^>nul') do set HELIOS_STATUS=%%i
if "!HELIOS_STATUS!"=="" (
    echo   Status: NOT RUNNING
) else (
    echo   Status: !HELIOS_STATUS!
)

:: ============================================================================
:: Check RPC
:: ============================================================================
echo.
echo [RPC ENDPOINT]
curl -s -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}" > "%TEMP%\rpc_response.txt" 2>&1
if errorlevel 1 (
    echo   Status: NOT RESPONDING
) else (
    echo   Status: RESPONDING
    type "%TEMP%\rpc_response.txt"
    echo.
)
del "%TEMP%\rpc_response.txt" >nul 2>&1

:: ============================================================================
:: Check Port Binding (Security)
:: ============================================================================
echo.
echo [SECURITY CHECK]
netstat -an | findstr ":8545" | findstr "LISTENING" > "%TEMP%\port_check.txt"
findstr "0.0.0.0:8545" "%TEMP%\port_check.txt" >nul 2>&1
if not errorlevel 1 (
    echo   WARNING: Port 8545 exposed on all interfaces!
    echo   Run: hardening\windows-firewall.ps1
) else (
    findstr "127.0.0.1:8545" "%TEMP%\port_check.txt" >nul 2>&1
    if not errorlevel 1 (
        echo   Port 8545: Bound to localhost only [SECURE]
    ) else (
        echo   Port 8545: Not listening
    )
)
del "%TEMP%\port_check.txt" >nul 2>&1

echo.
echo  ============================================
echo.

pause
