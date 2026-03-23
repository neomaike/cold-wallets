@echo off
echo =====================================================
echo   SWEEP PARA COLD WALLET - OFFLINE
echo =====================================================
echo.
echo IMPORTANTE: Execute como Administrador para desligar
echo             a internet automaticamente!
echo.
echo Uso: run_sweep.bat ^<endereco_cold_wallet^>
echo.
if "%1"=="" (
    echo [ERRO] Informe o endereco da cold wallet destino
    pause
    exit /b 1
)
pause
C:\Python314\python.exe "%~dp0sweep_to_cold.py" %*
pause
