# SCRIPT DE REDIMENSIONAMENTO DE PARTICOES
# Execute como Administrador!
#
# OBJETIVO:
# - Usar os 194,67GB nao alocados
# - Aumentar F: (projects) de 254,74GB para 449,41GB
# - Manter G: (mem) intacto

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  REDIMENSIONAMENTO DE PARTICOES" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Verifica se esta rodando como admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERRO] Execute este script como ADMINISTRADOR!" -ForegroundColor Red
    Write-Host "Clique direito no PowerShell -> Executar como administrador" -ForegroundColor Yellow
    exit 1
}

Write-Host "[*] Listando discos e particoes atuais..." -ForegroundColor Yellow
Write-Host ""

# Lista todos os discos
Get-Disk | Format-Table -AutoSize

Write-Host ""
Write-Host "[*] Particoes do Disco 1:" -ForegroundColor Yellow

# Lista particoes do disco 1
Get-Partition -DiskNumber 1 | Format-Table PartitionNumber, DriveLetter, Size, Type -AutoSize

Write-Host ""
Write-Host "[*] Volumes:" -ForegroundColor Yellow
Get-Volume | Where-Object { $_.DriveLetter } | Format-Table DriveLetter, FileSystemLabel, Size, SizeRemaining -AutoSize

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ANALISE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Pega info da particao F:
$partitionF = Get-Partition -DriveLetter F -ErrorAction SilentlyContinue
if ($partitionF) {
    $sizeGB = [math]::Round($partitionF.Size / 1GB, 2)
    Write-Host "F: (projects) = $sizeGB GB" -ForegroundColor Green
}

# Verifica espaco nao alocado
$disk1 = Get-Disk -Number 1
$totalSize = $disk1.Size
$allocatedSize = (Get-Partition -DiskNumber 1 | Measure-Object -Property Size -Sum).Sum
$unallocated = $totalSize - $allocatedSize
$unallocatedGB = [math]::Round($unallocated / 1GB, 2)

Write-Host "Espaco nao alocado = $unallocatedGB GB" -ForegroundColor Yellow

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  PROBLEMA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "O Windows NAO consegue estender F: para a esquerda." -ForegroundColor Red
Write-Host "O espaco nao alocado (194GB) esta ANTES de F:, nao depois." -ForegroundColor Red
Write-Host ""
Write-Host "SOLUCOES:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. [RECOMENDADO] Usar GParted (Linux Live USB)" -ForegroundColor Green
Write-Host "   - Baixe: https://gparted.org/download.php"
Write-Host "   - Crie USB bootavel com Rufus"
Write-Host "   - Boot pelo USB e redimensione"
Write-Host ""
Write-Host "2. Usar MiniTool Partition Wizard (gratis)" -ForegroundColor Green
Write-Host "   - Baixe: https://www.partitionwizard.com/free-partition-manager.html"
Write-Host "   - Permite mover e redimensionar particoes"
Write-Host ""
Write-Host "3. Criar nova particao no espaco livre" -ForegroundColor Green
Write-Host "   - Nao aumenta F:, mas usa o espaco"
Write-Host ""

$choice = Read-Host "Deseja criar nova particao no espaco livre? (s/N)"

if ($choice -eq 's' -or $choice -eq 'S') {
    Write-Host ""
    Write-Host "[*] Criando nova particao no espaco nao alocado..." -ForegroundColor Yellow

    try {
        # Cria nova particao usando todo espaco nao alocado
        $newPartition = New-Partition -DiskNumber 1 -UseMaximumSize -AssignDriveLetter

        # Formata como NTFS
        Format-Volume -DriveLetter $newPartition.DriveLetter -FileSystem NTFS -NewFileSystemLabel "BTC_Node" -Confirm:$false

        Write-Host "[+] Particao criada com sucesso!" -ForegroundColor Green
        Write-Host "    Letra: $($newPartition.DriveLetter):" -ForegroundColor Green
        Write-Host "    Use esta particao para o Bitcoin Full Node" -ForegroundColor Green
    }
    catch {
        Write-Host "[ERRO] Falha ao criar particao: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  PARA BITCOIN FULL NODE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Espaco necessario: ~550GB (blockchain + indices)" -ForegroundColor Yellow
Write-Host "Espaco disponivel: $unallocatedGB GB + F: $sizeGB GB" -ForegroundColor Yellow
Write-Host ""
Write-Host "Se criar particao separada para o node:" -ForegroundColor Green
Write-Host "  - Nova particao (~194GB) NAO e suficiente sozinha"
Write-Host "  - Precisara usar F: tambem, ou"
Write-Host "  - Usar pruned node (apenas ~5-10GB)"
Write-Host ""
