@echo off
echo =====================================================
echo   GERADOR DE ENDERECOS DESCARTAVEIS - OFFLINE
echo =====================================================
echo.
echo IMPORTANTE: Execute como Administrador para desligar
echo             a internet automaticamente!
echo.
echo Uso: --count N --crypto btc/eth/both
echo.
pause
C:\Python314\python.exe "%~dp0generate_disposable.py" %*
pause
