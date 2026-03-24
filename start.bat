@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: AUTO-ELEVATE TO ADMIN
:: ============================================================================
net session >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
    exit /b
)

cd /d "%~dp0"
title Cold Wallets Dashboard
color 0A

echo.
echo  ============================================
echo   COLD WALLETS - SETUP ^& LAUNCH
echo  ============================================
echo.
echo  Running as Administrator [OK]
echo.

:: ============================================================================
:: [1] CHECK PYTHON
:: ============================================================================

echo [1/3] Checking Python...

set "PYTHON=C:\Python314\python.exe"
if not exist "%PYTHON%" (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=python"
    ) else (
        echo.
        echo  [ERROR] Python not found!
        echo  Install Python from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%v in ('"%PYTHON%" --version 2^>^&1') do echo       %%v [OK]

:: ============================================================================
:: [2] INSTALL DEPENDENCIES
:: ============================================================================

echo.
echo [2/3] Checking dependencies...

"%PYTHON%" -c "import eth_account, bit, requests, socks" >nul 2>&1
if errorlevel 1 (
    echo       Installing missing dependencies...
    "%PYTHON%" -m pip install --quiet --disable-pip-version-check eth-account bit "requests[socks]" PySocks
    if errorlevel 1 (
        echo       [ERROR] Failed to install dependencies!
        pause
        exit /b 1
    )
    echo       Dependencies installed [OK]
) else (
    echo       All dependencies present [OK]
)

:: ============================================================================
:: [3] START DASHBOARD (Tor handled inside dashboard, not here)
:: ============================================================================

echo.
echo [3/3] Starting dashboard...
echo.
echo  ============================================
echo   Dashboard: http://127.0.0.1:8080
echo  ============================================
echo.
echo  Use the dashboard to manage Tor, wallets,
echo  and transactions.
echo.
echo  Press Ctrl+C to stop.
echo.

:: Start server in background, wait for it, then open browser
start "Cold Wallets Server" /min "%PYTHON%" -B dashboard\server.py

:: Wait for server to be ready (max 10s)
set READY=0
for /L %%i in (1,1,20) do (
    if "!READY!"=="0" (
        timeout /t 1 /nobreak >nul
        curl -s -o nul http://127.0.0.1:8080/ >nul 2>&1
        if not errorlevel 1 set READY=1
    )
)

if "!READY!"=="1" (
    echo  Server ready! Opening browser...
    start "" "http://127.0.0.1:8080"
) else (
    echo  [WARN] Server may not be ready. Open http://127.0.0.1:8080 manually.
)

echo.
echo  Dashboard running in background window.
echo  Close the "Cold Wallets Server" window to stop.
echo.
pause
