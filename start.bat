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
        echo       Run manually: %PYTHON% -m pip install eth-account bit "requests[socks]" PySocks
        pause
        exit /b 1
    )
    echo       Dependencies installed [OK]
) else (
    echo       All dependencies present [OK]
)

:: ============================================================================
:: [3] START DASHBOARD (Tor check happens inside the dashboard)
:: ============================================================================

echo.
echo [3/3] Starting dashboard...
echo.
echo  ============================================
echo   Dashboard: http://127.0.0.1:8080
echo  ============================================
echo.
echo  Opening browser...
echo  Press Ctrl+C to stop.
echo.

:: Open browser after 1 second
start "" cmd /c "timeout /t 1 /nobreak >nul && start http://127.0.0.1:8080"

:: Start server (blocking)
"%PYTHON%" dashboard\server.py

echo.
echo  Dashboard stopped.
pause
