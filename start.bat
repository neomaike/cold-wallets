@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

title Cold Wallets Dashboard
color 0A

echo.
echo  ============================================
echo   COLD WALLETS - SETUP ^& LAUNCH
echo  ============================================
echo.

:: ============================================================================
:: [1] CHECK PYTHON
:: ============================================================================

echo [1/4] Checking Python...

set "PYTHON=C:\Python314\python.exe"
if not exist "%PYTHON%" (
    echo       Python 3.14 not found at %PYTHON%
    echo       Trying system python...
    set "PYTHON=python"
)

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Python not found!
    echo  Install Python 3.14 from https://www.python.org/downloads/
    pause
    exit /b 1
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
:: [3] CHECK TOR
:: ============================================================================

echo.
echo [3/4] Checking Tor...

set TOR_STATUS=not connected
curl -s --socks5 127.0.0.1:9150 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    set TOR_STATUS=connected (port 9150^)
    goto :tor_ok
)

curl -s --socks5 127.0.0.1:9050 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    set TOR_STATUS=connected (port 9050^)
    goto :tor_ok
)

echo       Tor not detected. Trying to open Tor Browser...
set "TOR_BROWSER=%USERPROFILE%\Desktop\Tor Browser\Browser\firefox.exe"
set "TOR_BROWSER2=%PROGRAMFILES%\Tor Browser\Browser\firefox.exe"
set "TOR_BROWSER3=C:\Tor Browser\Browser\firefox.exe"

set "TOR_PATH="
if exist "%TOR_BROWSER%" set "TOR_PATH=%TOR_BROWSER%"
if exist "%TOR_BROWSER2%" if not defined TOR_PATH set "TOR_PATH=%TOR_BROWSER2%"
if exist "%TOR_BROWSER3%" if not defined TOR_PATH set "TOR_PATH=%TOR_BROWSER3%"

if defined TOR_PATH (
    start "" "%TOR_PATH%"
    echo       Waiting for Tor to connect (30s^)...
    timeout /t 30 /nobreak >nul
    curl -s --socks5 127.0.0.1:9150 --connect-timeout 5 https://check.torproject.org/api/ip >nul 2>&1
    if not errorlevel 1 (
        set TOR_STATUS=connected (port 9150^)
    )
) else (
    echo       [WARN] Tor Browser not found.
    echo       Download: https://www.torproject.org/download/
    echo       Dashboard will work but network features require Tor.
)

:tor_ok
echo       Tor: !TOR_STATUS!

:: ============================================================================
:: [4] START DASHBOARD
:: ============================================================================

echo.
echo [4/4] Starting dashboard...
echo.
echo  ============================================
echo   Dashboard: http://127.0.0.1:8080
echo  ============================================
echo.

:: Open browser after short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8080"

:: Start server (blocking)
"%PYTHON%" dashboard\server.py
pause
