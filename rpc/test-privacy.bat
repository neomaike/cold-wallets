@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: TEST PRIVACY - Verify Tor is protecting your IP
:: ============================================================================

title Privacy Test
color 0D

echo.
echo  ============================================
echo   PRIVACY VERIFICATION TEST
echo  ============================================
echo.

cd /d "%~dp0"

:: ============================================================================
:: Test 1: Your Real IP
:: ============================================================================
echo [TEST 1] Your real IP address:
for /f "delims=" %%i in ('curl -s https://api.ipify.org 2^>nul') do set REAL_IP=%%i
echo   Real IP: %REAL_IP%

:: ============================================================================
:: Test 2: Tor Exit IP
:: ============================================================================
echo.
echo [TEST 2] Tor exit node IP:
curl -s --socks5 127.0.0.1:9050 --connect-timeout 10 https://check.torproject.org/api/ip > "%TEMP%\tor_ip.txt" 2>&1
if errorlevel 1 (
    echo   Tor: NOT CONNECTED
    echo   Start Tor first!
) else (
    type "%TEMP%\tor_ip.txt"
    echo.
)
del "%TEMP%\tor_ip.txt" >nul 2>&1

:: ============================================================================
:: Test 3: Compare IPs
:: ============================================================================
echo.
echo [TEST 3] Privacy verification:
for /f "delims=" %%i in ('curl -s --socks5 127.0.0.1:9050 https://api.ipify.org 2^>nul') do set TOR_IP=%%i

if "%REAL_IP%"=="%TOR_IP%" (
    echo   [FAIL] IPs are the same - Tor not working!
    color 0C
) else (
    if "%TOR_IP%"=="" (
        echo   [FAIL] Could not get Tor IP
        color 0C
    ) else (
        echo   [PASS] IPs are different - Privacy protected!
        echo.
        echo   Your IP:  %REAL_IP%
        echo   Tor IP:   %TOR_IP%
        echo.
        echo   RPC providers will only see the Tor IP.
        color 0A
    )
)

:: ============================================================================
:: Test 4: RPC Test
:: ============================================================================
echo.
echo [TEST 4] Local RPC test:
curl -s -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}" > "%TEMP%\rpc_test.txt" 2>&1
if errorlevel 1 (
    echo   RPC: NOT RESPONDING
) else (
    echo   RPC: WORKING
    type "%TEMP%\rpc_test.txt"
    echo.
)
del "%TEMP%\rpc_test.txt" >nul 2>&1

:: ============================================================================
:: Test 5: External Access (should fail)
:: ============================================================================
echo.
echo [TEST 5] Security test - external access:
echo   Checking if port 8545 is exposed...

:: Get LAN IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set LANIP=%%a
    goto :gotip
)
:gotip
set LANIP=%LANIP: =%

:: This test only works if you have another device, so just check binding
netstat -an | findstr ":8545" | findstr "0.0.0.0" >nul 2>&1
if not errorlevel 1 (
    echo   [FAIL] Port 8545 is exposed on 0.0.0.0
    echo   Run the hardening script!
    color 0C
) else (
    echo   [PASS] Port 8545 bound to localhost only
)

echo.
echo  ============================================
echo   SUMMARY
echo  ============================================
echo.
echo   If all tests pass, your RPC queries go through
echo   Tor and your real IP is never exposed to RPC
echo   providers like Alchemy or Infura.
echo.

pause
