# Verifica estado do disco - Execute como Admin
Write-Host "`n=== ESTADO ATUAL DO DISCO 1 ===" -ForegroundColor Cyan

# Usa diskpart para mostrar detalhes
$diskpartScript = @"
select disk 1
list partition
"@

$diskpartScript | diskpart

Write-Host "`n=== VOLUMES ===" -ForegroundColor Cyan
Get-Volume | Format-Table DriveLetter, FileSystemLabel, @{N='Size(GB)';E={[math]::Round($_.Size/1GB,2)}}, @{N='Free(GB)';E={[math]::Round($_.SizeRemaining/1GB,2)}} -AutoSize
