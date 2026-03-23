@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: DOCKER DIAGNOSTICO E CORRECAO
:: Execute como Administrador para corrigir problemas
:: ============================================================================

title Docker - Diagnostico e Correcao
color 0E

echo.
echo  ============================================
echo   DOCKER - DIAGNOSTICO E CORRECAO
echo  ============================================
echo.

:: ============================================================================
:: DIAGNOSTICO
:: ============================================================================

echo [DIAGNOSTICO]
echo.

:: 1. Verificar instalacao
echo [1] Verificando instalacao do Docker...
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    echo     Docker Desktop: INSTALADO
    set DOCKER_INSTALLED=1
) else (
    echo     Docker Desktop: NAO INSTALADO
    set DOCKER_INSTALLED=0
    echo.
    echo     Baixe em: https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

:: 2. Verificar WSL
echo.
echo [2] Verificando WSL...
wsl --status >nul 2>&1
if errorlevel 1 (
    echo     WSL: NAO INSTALADO ou COM PROBLEMA
    set WSL_OK=0
) else (
    echo     WSL: INSTALADO
    set WSL_OK=1
)

:: 3. Verificar distro WSL
echo.
echo [3] Verificando distribuicao WSL...
for /f "tokens=1" %%a in ('wsl -l -q 2^>nul') do (
    echo     Distro encontrada: %%a
    set WSL_DISTRO=1
)
if not defined WSL_DISTRO (
    echo     Nenhuma distro WSL encontrada
    set WSL_DISTRO=0
)

:: 4. Verificar servico Docker
echo.
echo [4] Verificando servico Docker...
sc query com.docker.service 2>nul | findstr "RUNNING" >nul
if errorlevel 1 (
    echo     Servico Docker: PARADO
    set DOCKER_SERVICE=0
) else (
    echo     Servico Docker: RODANDO
    set DOCKER_SERVICE=1
)

:: 5. Verificar processos Docker
echo.
echo [5] Verificando processos Docker...
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>nul | findstr "Docker" >nul
if errorlevel 1 (
    echo     Docker Desktop: NAO RODANDO
    set DOCKER_RUNNING=0
) else (
    echo     Docker Desktop: RODANDO
    set DOCKER_RUNNING=1
)

:: 6. Verificar Hyper-V
echo.
echo [6] Verificando Hyper-V...
dism /online /get-featureinfo /featurename:Microsoft-Hyper-V 2>nul | findstr "State : Enabled" >nul
if errorlevel 1 (
    echo     Hyper-V: DESABILITADO ou NAO DISPONIVEL
    set HYPERV=0
) else (
    echo     Hyper-V: HABILITADO
    set HYPERV=1
)

:: ============================================================================
:: RESUMO
:: ============================================================================

echo.
echo  ============================================
echo   RESUMO DO DIAGNOSTICO
echo  ============================================
echo.
echo   Docker Instalado:  %DOCKER_INSTALLED%
echo   WSL OK:            %WSL_OK%
echo   Servico Docker:    %DOCKER_SERVICE%
echo   Docker Rodando:    %DOCKER_RUNNING%
echo.

:: ============================================================================
:: CORRECAO
:: ============================================================================

echo  ============================================
echo   TENTANDO CORRIGIR
echo  ============================================
echo.

:: Verificar admin
net session >nul 2>&1
if errorlevel 1 (
    echo [!] Este script precisa de privilegios de Administrador
    echo     para corrigir alguns problemas.
    echo.
    echo     Clique com botao direito e "Executar como administrador"
    echo.
    set IS_ADMIN=0
) else (
    set IS_ADMIN=1
)

:: Correcao 1: Iniciar WSL
echo [CORRECAO 1] Iniciando WSL...
wsl --shutdown 2>nul
wsl -d Ubuntu -e echo "WSL OK" 2>nul
if errorlevel 1 (
    echo     Tentando iniciar qualquer distro...
    wsl -e echo "WSL OK" 2>nul
)
echo     WSL iniciado.

:: Correcao 2: Iniciar servico Docker (precisa admin)
if %IS_ADMIN%==1 (
    echo.
    echo [CORRECAO 2] Iniciando servico Docker...
    net start com.docker.service 2>nul
    if errorlevel 1 (
        echo     Servico nao pode ser iniciado diretamente.
        echo     Tentando via Docker Desktop...
    ) else (
        echo     Servico iniciado.
    )
)

:: Correcao 3: Abrir Docker Desktop
echo.
echo [CORRECAO 3] Abrindo Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo     Docker Desktop iniciando...

:: Aguardar
echo.
echo [AGUARDANDO] Docker Desktop iniciar (pode levar 60 segundos)...
echo.

set WAIT_COUNT=0
:wait_loop
set /a WAIT_COUNT+=1
if %WAIT_COUNT% gtr 24 (
    echo.
    echo [!] Docker nao iniciou apos 2 minutos.
    goto :show_manual
)

timeout /t 5 /nobreak >nul
echo     Tentativa %WAIT_COUNT%/24...

docker info >nul 2>&1
if errorlevel 1 (
    goto :wait_loop
)

:: Sucesso!
echo.
echo  ============================================
echo   DOCKER FUNCIONANDO!
echo  ============================================
echo.
docker version
echo.
echo   Agora voce pode executar: start-private-rpc.bat
echo.
pause
exit /b 0

:show_manual
echo.
echo  ============================================
echo   CORRECAO MANUAL NECESSARIA
echo  ============================================
echo.
echo   O Docker nao iniciou automaticamente.
echo   Tente estas solucoes:
echo.
echo   1. REINICIAR O COMPUTADOR
echo      Muitas vezes resolve problemas do WSL/Docker
echo.
echo   2. VERIFICAR VIRTUALIZACAO NA BIOS
echo      - Reinicie e entre na BIOS (F2, F10, Del)
echo      - Ative "Intel VT-x" ou "AMD-V"
echo      - Ative "Hyper-V" se disponivel
echo.
echo   3. REINSTALAR WSL
echo      Abra PowerShell como Admin e execute:
echo      wsl --install
echo.
echo   4. REPARAR DOCKER DESKTOP
echo      - Abra Docker Desktop manualmente
echo      - Va em Settings ^> Troubleshoot ^> Reset to factory
echo.
echo   5. REINSTALAR DOCKER DESKTOP
echo      - Desinstale pelo Painel de Controle
echo      - Baixe novamente: docker.com/products/docker-desktop
echo.
echo  ============================================
echo.
pause
exit /b 1
