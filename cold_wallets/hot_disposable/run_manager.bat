@echo off
echo =====================================================
echo   GERENCIADOR DE ENDERECOS DESCARTAVEIS
echo =====================================================
echo.
echo Comandos:
echo   status                    - Ver status do pool
echo   get-address --crypto btc  - Pegar endereco BTC
echo   get-address --crypto eth  - Pegar endereco ETH
echo   mark-funded ^<endereco^>    - Marcar com saldo
echo   list --state funded       - Listar por estado
echo   show ^<endereco^>           - Ver detalhes
echo.
C:\Python314\python.exe "%~dp0disposable_manager.py" %*
pause
