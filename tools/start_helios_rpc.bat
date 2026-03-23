@echo off
:: ============================================================================
:: INICIAR HELIOS RPC PRIVADO
:: Substitui o eth_rpc_proxy.py com verificacao criptografica
:: ============================================================================

title Helios RPC Privado
color 0A

echo.
echo  ============================================
echo   HELIOS RPC PRIVADO
echo  ============================================
echo.
echo   Vantagem sobre eth_rpc_proxy.py:
echo   - Verifica TODAS as respostas criptograficamente
echo   - Mesmo se o RPC mentir, Helios detecta
echo.

:: Verificar Docker
docker info >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Docker nao esta rodando!
    echo         Inicie o Docker Desktop primeiro.
    echo         Ou use: tools\start_all_services.bat (fallback automatico^)
    echo.
    pause
    exit /b 1
)

:: Iniciar Helios
cd /d "%~dp0\..\rpc\helios"
docker compose up -d

if errorlevel 1 (
    echo.
    echo  [ERRO] Falha ao iniciar Helios.
    echo         Execute rpc\fix-docker.bat para diagnostico.
    echo.
    pause
    exit /b 1
)

echo.
echo  Aguardando Helios sincronizar...
timeout /t 10 /nobreak >nul

:: Testar RPC
curl -s -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"

echo.
echo.
echo  ============================================
echo   HELIOS RPC ATIVO
echo  ============================================
echo.
echo   RPC: http://127.0.0.1:8545 (trustless)
echo   Logs: docker logs helios-client -f
echo   Stop: tools\stop_all_services.bat
echo.
pause
