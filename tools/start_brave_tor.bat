@echo off
echo =====================================================
echo   INICIANDO BRAVE COM PROXY TOR
echo =====================================================
echo.
echo [!] IMPORTANTE: Tor Browser deve estar aberto primeiro!
echo.

:: Caminhos comuns do Brave
set "BRAVE1=%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
set "BRAVE2=%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"
set "BRAVE3=%PROGRAMFILES(X86)%\BraveSoftware\Brave-Browser\Application\brave.exe"

:: Encontra Brave
if exist "%BRAVE1%" (
    set "BRAVE_PATH=%BRAVE1%"
    goto :found_brave
)
if exist "%BRAVE2%" (
    set "BRAVE_PATH=%BRAVE2%"
    goto :found_brave
)
if exist "%BRAVE3%" (
    set "BRAVE_PATH=%BRAVE3%"
    goto :found_brave
)

echo [!] Brave nao encontrado!
echo     Baixe em: https://brave.com/download/
echo.
echo     Ou use Chrome com proxy manual:
echo     chrome.exe --proxy-server="socks5://127.0.0.1:9150"
echo.
pause
exit /b 1

:found_brave
echo [+] Brave encontrado: %BRAVE_PATH%
echo.
echo [*] Iniciando Brave com proxy SOCKS5 via Tor (porta 9150)...
echo.

:: Inicia Brave com proxy Tor
:: --proxy-server configura o proxy SOCKS5 do Tor Browser
:: --proxy-bypass-list permite localhost para o proxy RPC local
start "" "%BRAVE_PATH%" --proxy-server="socks5://127.0.0.1:9150" --proxy-bypass-list="127.0.0.1;localhost;<local>"

echo [+] Brave iniciado com proxy Tor!
echo.
echo [!] VERIFIQUE: Acesse https://check.torproject.org
echo     Deve mostrar "Congratulations. This browser is configured to use Tor."
echo.
echo [*] Agora voce pode usar MetaMask com privacidade.
echo     Configure a rede:
echo     - RPC URL: http://127.0.0.1:8545 (se proxy RPC estiver rodando)
echo     - Ou use RPCs publicos (passarao pelo Tor)
echo.
pause
