@echo off
:: ============================================================================
:: INICIAR PROXY RPC ETHEREUM VIA TOR
:: ============================================================================

title Proxy RPC Ethereum via Tor
color 0A

echo.
echo  ============================================
echo   PROXY RPC ETHEREUM VIA TOR
echo  ============================================
echo.

cd /d "%~dp0"

:: Verificar Tor
echo [1] Verificando Tor Browser (porta 9150)...
curl -s --socks5 127.0.0.1:9150 --connect-timeout 5 https://check.torproject.org/api/ip >nul 2>&1
if errorlevel 1 (
    echo     [ERRO] Tor Browser nao detectado!
    echo     Abra o Tor Browser primeiro.
    pause
    exit /b 1
)
echo     Tor OK!

:: Mostrar IP do Tor
echo.
echo [2] Seu IP via Tor:
curl -s --socks5 127.0.0.1:9150 https://check.torproject.org/api/ip
echo.

:: Iniciar proxy
echo.
echo [3] Iniciando proxy RPC...
echo.
C:\Python314\python.exe eth_rpc_proxy.py
