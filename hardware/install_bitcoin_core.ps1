# INSTALADOR BITCOIN CORE - COM TOR
# Execute como Administrador

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR BITCOIN CORE + TOR" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# URLs de download
$bitcoinVersion = "27.1"
$downloadUrl = "https://bitcoincore.org/bin/bitcoin-core-$bitcoinVersion/bitcoin-$bitcoinVersion-win64.zip"
$torUrl = "https://www.torproject.org/dist/torbrowser/14.0.3/tor-expert-bundle-windows-x86_64-14.0.3.tar.gz"

# Diretorios - BITCOIN CORE NO F:\
$installDir = "F:\Bitcoin"
$dataDir = "F:\BitcoinData"
$torDir = "F:\Tor"

Write-Host ""
Write-Host "Diretorio de instalacao: $installDir" -ForegroundColor Yellow
Write-Host "Diretorio de dados: $dataDir" -ForegroundColor Yellow
Write-Host "Diretorio do Tor: $torDir" -ForegroundColor Yellow
Write-Host ""

# Verifica espaco em disco F:\
$drive = Get-PSDrive F
$freeGB = [math]::Round($drive.Free / 1GB, 2)
Write-Host "Espaco livre em F:\: $freeGB GB" -ForegroundColor Yellow

if ($freeGB -lt 15) {
    Write-Host "[ALERTA] Menos de 15GB livres. Bitcoin Core pruned precisa ~10GB" -ForegroundColor Red
    $continue = Read-Host "Continuar mesmo assim? (s/n)"
    if ($continue -ne "s") { exit 0 }
}

# Cria diretorios
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path $torDir | Out-Null

Write-Host "[1/5] Baixando Bitcoin Core..." -ForegroundColor Green

$bitcoinZip = "$env:TEMP\bitcoin-core.zip"
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $bitcoinZip
    Write-Host "      Download concluido!" -ForegroundColor Green
}
catch {
    Write-Host "[ERRO] Falha no download. Baixe manualmente:" -ForegroundColor Red
    Write-Host "       $downloadUrl" -ForegroundColor Yellow
    exit 1
}

Write-Host "[2/5] Extraindo Bitcoin Core..." -ForegroundColor Green
Expand-Archive -Path $bitcoinZip -DestinationPath $installDir -Force

Write-Host "[3/5] Baixando Tor Expert Bundle..." -ForegroundColor Green
$torFile = "$env:TEMP\tor-bundle.tar.gz"
try {
    Invoke-WebRequest -Uri $torUrl -OutFile $torFile
    Write-Host "      Download Tor concluido!" -ForegroundColor Green

    # Extrair Tor (requer 7-Zip ou tar)
    if (Get-Command tar -ErrorAction SilentlyContinue) {
        tar -xzf $torFile -C $torDir
        Write-Host "      Tor extraido!" -ForegroundColor Green
    } else {
        Write-Host "      [AVISO] tar nao encontrado. Extraia manualmente:" -ForegroundColor Yellow
        Write-Host "      $torFile -> $torDir" -ForegroundColor Gray
    }
}
catch {
    Write-Host "[AVISO] Falha no download do Tor. Baixe manualmente:" -ForegroundColor Yellow
    Write-Host "        $torUrl" -ForegroundColor Gray
    Write-Host "        Ou use Tor Browser (porta 9150 ao inves de 9050)" -ForegroundColor Gray
}

Write-Host "[4/5] Criando bitcoin.conf..." -ForegroundColor Green

# Gerar senha RPC aleatoria
$rpcPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

$bitcoinConf = @"
# Bitcoin Core Configuration
# Configurado para PRIVACIDADE MAXIMA
# Gerado em: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# Diretorio de dados (Windows usa barras invertidas)
datadir=F:\\BitcoinData

# PRUNED MODE - usa apenas ~10GB ao inves de 500GB+
# Mude para 0 se quiser full node
prune=10000

# ========== TOR - PRIVACIDADE TOTAL ==========
# Usar Tor Expert Bundle (porta 9050) ou Tor Browser (porta 9150)
proxy=127.0.0.1:9050

# Aceitar conexoes apenas via Tor
listen=1
bind=127.0.0.1
onlynet=onion

# Desativa vazamento de DNS
dnsseed=0
dns=0

# Nao anunciar IP real
discover=0
upnp=0
natpmp=0

# ========== PERFORMANCE ==========
dbcache=450
maxconnections=40
maxuploadtarget=500

# ========== RPC LOCAL ==========
server=1
rpcuser=bitcoinrpc
rpcpassword=$rpcPassword
rpcallowip=127.0.0.1
rpcbind=127.0.0.1
rpcport=8332

# ========== WALLET ==========
disablewallet=0
walletbroadcast=1
"@

$confPath = "$dataDir\bitcoin.conf"
$bitcoinConf | Out-File -FilePath $confPath -Encoding UTF8
Write-Host "      Salvo em: $confPath" -ForegroundColor Green

Write-Host "[5/5] Criando scripts de inicializacao..." -ForegroundColor Green

# Script para iniciar Tor
$startTor = @"
@echo off
echo Iniciando Tor...
cd /d $torDir\tor
tor.exe
"@
$startTor | Out-File -FilePath "$torDir\start_tor.bat" -Encoding ASCII

# Script para iniciar Bitcoin Core
$startBitcoin = @"
@echo off
echo Iniciando Bitcoin Core...
echo Certifique-se que o Tor esta rodando na porta 9050
"$installDir\bitcoin-$bitcoinVersion\bin\bitcoin-qt.exe" -datadir="$dataDir"
"@
$startBitcoin | Out-File -FilePath "$installDir\start_bitcoin.bat" -Encoding ASCII

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  INSTALACAO CONCLUIDA!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "ARQUIVOS CRIADOS:" -ForegroundColor Yellow
Write-Host "  Bitcoin Core: $installDir" -ForegroundColor Gray
Write-Host "  Dados:        $dataDir" -ForegroundColor Gray
Write-Host "  Tor:          $torDir" -ForegroundColor Gray
Write-Host "  Config:       $confPath" -ForegroundColor Gray
Write-Host ""
Write-Host "SENHA RPC GERADA:" -ForegroundColor Yellow
Write-Host "  Usuario: bitcoinrpc" -ForegroundColor Gray
Write-Host "  Senha:   $rpcPassword" -ForegroundColor Gray
Write-Host "  GUARDE ESTA SENHA!" -ForegroundColor Red
Write-Host ""
Write-Host "COMO USAR:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. PRIMEIRO inicie o Tor:" -ForegroundColor White
Write-Host "     $torDir\start_tor.bat" -ForegroundColor Gray
Write-Host "     (ou abra Tor Browser - usa porta 9150)" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. DEPOIS inicie o Bitcoin Core:" -ForegroundColor White
Write-Host "     $installDir\start_bitcoin.bat" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Aguarde sincronizacao inicial (~1-3 dias via Tor)" -ForegroundColor White
Write-Host ""
Write-Host "MODO PRUNED: Usando apenas ~10GB" -ForegroundColor Green
Write-Host "Todas conexoes passam pelo Tor (onlynet=onion)" -ForegroundColor Green
Write-Host ""
Write-Host "Se usar Tor Browser ao inves do Expert Bundle:" -ForegroundColor Yellow
Write-Host "  Edite $confPath" -ForegroundColor Gray
Write-Host "  Mude: proxy=127.0.0.1:9050" -ForegroundColor Gray
Write-Host "  Para: proxy=127.0.0.1:9150" -ForegroundColor Gray
Write-Host ""
