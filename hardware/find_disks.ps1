# Encontra informacoes sobre discos e particoes
Write-Host "=== DISCOS ===" -ForegroundColor Cyan
Get-Disk | Format-Table Number, FriendlyName, Size, PartitionStyle -AutoSize

Write-Host "`n=== PARTICOES ===" -ForegroundColor Cyan
Get-Partition | Format-Table DiskNumber, PartitionNumber, DriveLetter, @{N='Size_GB';E={[math]::Round($_.Size/1GB,2)}}, Type -AutoSize

Write-Host "`n=== VOLUMES ===" -ForegroundColor Cyan
Get-Volume | Where-Object { $_.DriveLetter } | Format-Table DriveLetter, FileSystemLabel, @{N='Size_GB';E={[math]::Round($_.Size/1GB,2)}}, @{N='Free_GB';E={[math]::Round($_.SizeRemaining/1GB,2)}} -AutoSize

Write-Host "`n=== ESPACO NAO ALOCADO ===" -ForegroundColor Cyan
foreach ($disk in Get-Disk) {
    $totalSize = $disk.Size
    $allocatedSize = (Get-Partition -DiskNumber $disk.Number -ErrorAction SilentlyContinue | Measure-Object -Property Size -Sum).Sum
    if (-not $allocatedSize) { $allocatedSize = 0 }
    $unallocated = $totalSize - $allocatedSize
    $unallocatedGB = [math]::Round($unallocated / 1GB, 2)
    if ($unallocatedGB -gt 0.1) {
        Write-Host "Disco $($disk.Number): $unallocatedGB GB nao alocados" -ForegroundColor Yellow
    }
}
