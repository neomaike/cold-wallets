@echo off
echo =====================================================
echo   DESATIVAR TOR DO SISTEMA
echo =====================================================
echo.

echo [*] Desativando proxy do sistema...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f

echo.
echo [+] Proxy desativado!
echo     Conexao normal restaurada.
echo.
pause
