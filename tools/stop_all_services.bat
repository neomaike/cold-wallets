@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: PARAR TODOS OS SERVICOS
:: ============================================================================

title Parando Servicos
color 0C

echo.
echo  ============================================
echo   PARANDO SERVICOS DE PRIVACIDADE
echo  ============================================
echo.

cd /d "%~dp0\.."

:: ============================================================================
:: [1] Parar Helios (se Docker disponivel)
:: ============================================================================

echo [1/3] Parando Helios...

docker info >nul 2>&1
if not errorlevel 1 (
    docker compose -f rpc\helios\docker-compose.yml down 2>nul
    if not errorlevel 1 (
        echo       Helios parado.
    ) else (
        echo       Helios nao estava rodando.
    )
) else (
    echo       Docker nao disponivel (Helios nao estava rodando^).
)

:: ============================================================================
:: [2] Matar eth_rpc_proxy.py (se rodando)
:: ============================================================================

echo.
echo [2/3] Parando Proxy RPC...

tasklist /FI "WINDOWTITLE eq ETH RPC Proxy*" 2>nul | findstr "cmd" >nul 2>&1
if not errorlevel 1 (
    taskkill /FI "WINDOWTITLE eq ETH RPC Proxy*" /F >nul 2>&1
    echo       Proxy RPC parado.
) else (
    :: Tentar matar python rodando eth_rpc_proxy
    for /f "tokens=2" %%p in ('wmic process where "CommandLine like '%%eth_rpc_proxy%%'" get ProcessId 2^>nul ^| findstr /r "[0-9]"') do (
        taskkill /PID %%p /F >nul 2>&1
        echo       Proxy RPC parado (PID %%p^).
    )
)

:: Verificar se porta 8545 foi liberada
timeout /t 2 /nobreak >nul
netstat -an | findstr ":8545" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [AVISO] Porta 8545 ainda em uso.
) else (
    echo       Porta 8545 liberada.
)

:: ============================================================================
:: [3] Resumo
:: ============================================================================

echo.
echo [3/3] Verificando...

set SERVICES_RUNNING=0

docker ps --filter "name=helios" --format "{{.Names}}" 2>nul | findstr "helios" >nul 2>&1
if not errorlevel 1 (
    echo       [!] Helios ainda rodando
    set SERVICES_RUNNING=1
)

netstat -an | findstr ":8545" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       [!] Algo ainda escutando na porta 8545
    set SERVICES_RUNNING=1
)

if "!SERVICES_RUNNING!"=="0" (
    echo       Todos os servicos parados com sucesso.
)

echo.
echo  ============================================
echo   SERVICOS PARADOS
echo  ============================================
echo.
echo   Nota: Tor Browser e Bitcoin Core nao sao
echo   afetados (gerenciados separadamente^).
echo.
pause
