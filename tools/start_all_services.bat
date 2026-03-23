@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: STARTUP UNIFICADO - Tor + RPC (Helios ou Fallback) + Bitcoin Core
:: ============================================================================

title Servicos de Privacidade
color 0A

echo.
echo  ============================================
echo   INICIANDO SERVICOS DE PRIVACIDADE
echo  ============================================
echo.

cd /d "%~dp0\.."

:: ============================================================================
:: [1] VERIFICAR TOR
:: ============================================================================

echo [1/4] Verificando Tor...

set TOR_OK=0
set TOR_PORT=0

:: Tentar porta 9150 (Tor Browser)
curl -s --socks5 127.0.0.1:9150 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    echo       Tor Browser detectado (porta 9150^)
    set TOR_OK=1
    set TOR_PORT=9150
    goto :tor_done
)

:: Tentar porta 9050 (Docker Tor / servico)
curl -s --socks5 127.0.0.1:9050 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    echo       Tor Service detectado (porta 9050^)
    set TOR_OK=1
    set TOR_PORT=9050
    goto :tor_done
)

:: Nenhum Tor encontrado - tentar abrir Tor Browser
echo       Tor nao detectado. Tentando abrir Tor Browser...

set "TOR_BROWSER=%USERPROFILE%\Desktop\Tor Browser\Browser\firefox.exe"
set "TOR_BROWSER2=%PROGRAMFILES%\Tor Browser\Browser\firefox.exe"
set "TOR_BROWSER3=C:\Tor Browser\Browser\firefox.exe"

set "TOR_PATH="
if exist "%TOR_BROWSER%" set "TOR_PATH=%TOR_BROWSER%"
if exist "%TOR_BROWSER2%" if not defined TOR_PATH set "TOR_PATH=%TOR_BROWSER2%"
if exist "%TOR_BROWSER3%" if not defined TOR_PATH set "TOR_PATH=%TOR_BROWSER3%"

if defined TOR_PATH (
    start "" "%TOR_PATH%"
    echo       Aguardando Tor conectar (30 segundos^)...
    timeout /t 30 /nobreak >nul

    :: Re-verificar
    curl -s --socks5 127.0.0.1:9150 --connect-timeout 5 https://check.torproject.org/api/ip >nul 2>&1
    if not errorlevel 1 (
        set TOR_OK=1
        set TOR_PORT=9150
    )
)

if "!TOR_OK!"=="0" (
    echo.
    echo  [ERRO] Tor nao disponivel!
    echo         Abra o Tor Browser manualmente e tente novamente.
    echo         Download: https://www.torproject.org/download/
    echo.
    pause
    exit /b 1
)

:tor_done
echo       Tor OK (porta !TOR_PORT!^)

:: ============================================================================
:: [2] VERIFICAR DOCKER
:: ============================================================================

echo.
echo [2/4] Verificando Docker...

set DOCKER_OK=0
docker info >nul 2>&1
if not errorlevel 1 (
    echo       Docker detectado e rodando.
    set DOCKER_OK=1
) else (
    echo       Docker nao disponivel.
)

:: ============================================================================
:: [3] INICIAR RPC (Helios ou Fallback)
:: ============================================================================

echo.
set RPC_MODE=none

if "!DOCKER_OK!"=="1" (
    echo [3/4] Iniciando Helios RPC (verificacao criptografica^)...

    cd /d "%~dp0\..\rpc\helios"
    docker compose up -d 2>nul

    if errorlevel 1 (
        echo       [AVISO] Falha ao iniciar Helios. Usando fallback...
        cd /d "%~dp0\.."
        goto :fallback_rpc
    )

    cd /d "%~dp0\.."

    :: Esperar RPC responder (max 60s)
    echo       Aguardando Helios sincronizar...
    set RPC_READY=0
    for /L %%i in (1,1,12) do (
        if "!RPC_READY!"=="0" (
            timeout /t 5 /nobreak >nul
            curl -s -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}" >nul 2>&1
            if not errorlevel 1 (
                set RPC_READY=1
            )
        )
    )

    if "!RPC_READY!"=="1" (
        echo       Helios RPC pronto!
        set RPC_MODE=helios
    ) else (
        echo       [AVISO] Helios iniciado mas RPC ainda nao responde.
        echo       Verifique logs: docker logs helios-client
        set RPC_MODE=helios
    )
) else (
    :fallback_rpc
    echo [3/4] Iniciando Proxy RPC Fallback (via Tor, sem verificacao^)...
    start "ETH RPC Proxy" cmd /k "C:\Python314\python.exe "%~dp0eth_rpc_proxy.py""
    timeout /t 3 /nobreak >nul
    set RPC_MODE=proxy
)

:: ============================================================================
:: [4] BITCOIN CORE
:: ============================================================================

echo.
echo [4/4] Verificando Bitcoin Core...

if exist "F:\Bitcoin\start_bitcoin.bat" (
    start "" "F:\Bitcoin\start_bitcoin.bat"
    echo       Bitcoin Core iniciado!
) else (
    echo       Bitcoin Core nao encontrado em F:\Bitcoin (opcional^)
)

:: ============================================================================
:: RESUMO
:: ============================================================================

echo.
echo  ============================================
echo   SERVICOS INICIADOS
echo  ============================================
echo.
echo   Tor:          Porta !TOR_PORT! [OK]

if "!RPC_MODE!"=="helios" (
    echo   RPC ETH:      http://127.0.0.1:8545 (Helios - trustless^)
) else (
    echo   RPC ETH:      http://127.0.0.1:8545 (Proxy Tor - fallback^)
)

if exist "F:\Bitcoin\start_bitcoin.bat" (
    echo   Bitcoin Core: Sincronizando...
) else (
    echo   Bitcoin Core: Nao configurado
)

echo.
echo   Para usar MetaMask com privacidade:
echo   1. Abra o Brave ou Chrome
echo   2. Configure rede customizada no MetaMask:
echo      - RPC URL: http://127.0.0.1:8545
echo      - Chain ID: 1
echo.
echo   Status detalhado: tools\status.bat
echo   Parar tudo:       tools\stop_all_services.bat
echo.
echo   NAO FECHE ESTA JANELA!
echo.
pause
