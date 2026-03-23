@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: STATUS DE TODOS OS SERVICOS
:: ============================================================================

title Status dos Servicos
color 0B

echo.
echo  ============================================
echo   STATUS DOS SERVICOS
echo  ============================================
echo.

:: ============================================================================
:: [1] Tor
:: ============================================================================

echo [TOR]
set TOR_STATUS=OFFLINE

curl -s --socks5 127.0.0.1:9150 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    echo   Status: ONLINE (porta 9150 - Tor Browser^)
    set TOR_STATUS=ONLINE
)

curl -s --socks5 127.0.0.1:9050 --connect-timeout 3 https://check.torproject.org/api/ip >nul 2>&1
if not errorlevel 1 (
    echo   Status: ONLINE (porta 9050 - Docker/Service^)
    set TOR_STATUS=ONLINE
)

if "!TOR_STATUS!"=="OFFLINE" (
    echo   Status: OFFLINE (portas 9050 e 9150 nao respondem^)
)

:: ============================================================================
:: [2] RPC (Helios ou Proxy?)
:: ============================================================================

echo.
echo [RPC ETHEREUM]

set RPC_MODE=none

:: Verificar se Helios container esta rodando
docker ps --filter "name=helios" --filter "status=running" --format "{{.Names}}" 2>nul | findstr "helios" >nul 2>&1
if not errorlevel 1 (
    set RPC_MODE=helios
    echo   Modo: HELIOS (verificacao criptografica^)
    for /f "tokens=*" %%i in ('docker ps --filter "name=helios" --format "{{.Status}}" 2^>nul') do echo   Container: %%i
) else (
    :: Verificar se eth_rpc_proxy esta rodando
    wmic process where "CommandLine like '%%eth_rpc_proxy%%'" get ProcessId 2>nul | findstr /r "[0-9]" >nul 2>&1
    if not errorlevel 1 (
        set RPC_MODE=proxy
        echo   Modo: PROXY FALLBACK (via Tor, sem verificacao^)
    )
)

:: Testar RPC
curl -s -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}" > "%TEMP%\rpc_status.txt" 2>&1
if errorlevel 1 (
    echo   Endpoint: NAO RESPONDE
) else (
    echo   Endpoint: RESPONDENDO (http://127.0.0.1:8545^)
    type "%TEMP%\rpc_status.txt"
    echo.
)
del "%TEMP%\rpc_status.txt" >nul 2>&1

if "!RPC_MODE!"=="none" (
    echo   Status: OFFLINE
)

:: ============================================================================
:: [3] Bitcoin Core
:: ============================================================================

echo.
echo [BITCOIN CORE]

netstat -an | findstr ":8332" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   Status: ONLINE (porta 8332^)
) else (
    echo   Status: OFFLINE
)

:: ============================================================================
:: [4] Seguranca
:: ============================================================================

echo.
echo [SEGURANCA]

netstat -an | findstr ":8545" | findstr "LISTENING" > "%TEMP%\port_check.txt" 2>&1
findstr "0.0.0.0:8545" "%TEMP%\port_check.txt" >nul 2>&1
if not errorlevel 1 (
    echo   [!] ALERTA: Porta 8545 exposta em todas as interfaces!
    echo   Execute: rpc\harden-system.bat como Admin
) else (
    findstr "127.0.0.1:8545" "%TEMP%\port_check.txt" >nul 2>&1
    if not errorlevel 1 (
        echo   Porta 8545: Apenas localhost [SEGURO]
    ) else (
        echo   Porta 8545: Nao esta escutando
    )
)
del "%TEMP%\port_check.txt" >nul 2>&1

:: ============================================================================
:: Resumo
:: ============================================================================

echo.
echo  ============================================
echo.

pause
