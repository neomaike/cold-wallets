@echo off
echo =====================================================
echo   ATIVAR TOR PARA TODO O SISTEMA
echo =====================================================
echo.
echo [!] IMPORTANTE: Tor Browser deve estar aberto!
echo.
echo Isso vai configurar o Windows para usar Tor como proxy.
echo Alguns programas podem nao funcionar.
echo.
pause

echo.
echo [*] Ativando proxy SOCKS5 via Tor...

:: Configura proxy do sistema
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "socks=127.0.0.1:9150" /f

echo.
echo [+] Proxy ativado!
echo.
echo     Proxy: socks=127.0.0.1:9150
echo.
echo [!] AVISO: Nem todos os programas respeitam o proxy do sistema.
echo            Programas que fazem conexoes diretas ainda vazam IP.
echo.
echo     Para desativar, execute: disable_system_tor.bat
echo.
pause
