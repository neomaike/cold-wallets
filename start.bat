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
echo  Directory: %cd%
echo.

:: ============================================================================
:: [1] CHECK PYTHON
:: ============================================================================

echo [1/4] Checking Python...

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
echo [2/4] Checking dependencies...

"%PYTHON%" -c "import eth_account, bit, requests, socks" >nul 2>&1
if errorlevel 1 (
    echo       Installing missing dependencies...
    "%PYTHON%" -m pip install --quiet --disable-pip-version-check eth-account bit "requests[socks]" PySocks
    if errorlevel 1 (
        echo       [ERROR] Failed to install dependencies!
        echo       Run manually: %PYTHON% -m pip install eth-account bit "requests[socks]" PySocks
        pause
        exit /b 1
    )
    echo       Dependencies installed [OK]
) else (
    echo       All dependencies present [OK]
)

:: ============================================================================
:: [3] AUTO-START TOR IN BACKGROUND
:: ============================================================================

echo.
echo [3/4] Starting Tor...

"%PYTHON%" tools\tor_manager.py status 2>nul | findstr "Running: True" >nul
if not errorlevel 1 (
    echo       Tor already running [OK]
) else (
    echo       Attempting to start Tor...
    "%PYTHON%" tools\tor_manager.py start
)

:: ============================================================================
:: [4] START DASHBOARD
:: ============================================================================

echo.
echo [4/4] Starting dashboard...
echo.
echo  ============================================
echo   Dashboard: http://127.0.0.1:8080
echo   Admin: YES
echo  ============================================
echo.
echo  Opening browser...
echo  Press Ctrl+C to stop.
echo.

start "" "http://127.0.0.1:8080"

"%PYTHON%" dashboard\server.py

echo.
echo  Stopping Tor...
"%PYTHON%" tools\tor_manager.py stop 2>nul

echo  Dashboard stopped.
pause
