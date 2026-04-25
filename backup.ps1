# Trading Journal — pg_dump backup script (Windows PowerShell)
#
# Requires: Docker Desktop running with the Compose stack up (at least the db service)
#
# Usage:
#   .\backup.ps1                      # creates backups\backup_YYYYMMDD_HHMMSS.sql
#   .\backup.ps1 -OutDir "D:\backups" # custom output directory

param(
    [string]$OutDir = "backups"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$filename  = "backup_$timestamp.sql"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$outpath = Join-Path $OutDir $filename

Write-Host "Backing up trading_journal database..."

docker compose exec -T db pg_dump -U trading trading_journal | Out-File -Encoding utf8 -FilePath $outpath

if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item $outpath).Length
    Write-Host "Backup complete: $outpath ($size bytes)"
    Write-Host ""
    Write-Host "To restore:"
    Write-Host "  Get-Content `"$outpath`" | docker compose exec -T db psql -U trading trading_journal"
} else {
    Write-Host "ERROR: pg_dump failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Make sure the db container is running:  docker compose up -d db"
    exit 1
}
