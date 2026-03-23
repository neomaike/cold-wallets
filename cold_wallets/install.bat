@echo off
cd /d "%~dp0"
echo ============================================
echo  INSTALADOR DE DEPENDENCIAS - COLD WALLETS
echo ============================================
echo.
echo Este script instala as dependencias Python necessarias.
echo.
echo IMPORTANTE: Instale primeiro em um computador COM internet,
echo depois copie a pasta inteira para o computador OFFLINE.
echo.
pause

echo.
echo [1/2] Atualizando pip...
C:\Python314\python.exe -m pip install --upgrade pip

echo.
echo [2/2] Instalando dependencias...
C:\Python314\python.exe -m pip install -r requirements.txt

echo.
echo ============================================
echo  INSTALACAO CONCLUIDA!
echo ============================================
echo.
echo Proximos passos:
echo 1. Copie toda a pasta 'cold_wallets' para um pendrive
echo 2. Transfira para um computador OFFLINE (air-gapped)
echo 3. Execute os scripts de geracao de carteiras OFFLINE
echo.
pause
