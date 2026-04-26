# Trading Journal — database restore from a pg_dump SQL backup (Windows PowerShell)
#
# Requires: Docker Desktop running with the Compose stack up (at least the db service)
#
# Usage:
#   .\restore.ps1 -BackupFile "backups\backup_20260426_120000.sql"
#   .\restore.ps1 -BackupFile "D:\offsite\backup_20260426_120000.sql" -Force

param(
    [Parameter(Mandatory)]
    [string]$BackupFile,

    [switch]$Force  # skip the confirmation prompt
)

if (-not (Test-Path $BackupFile)) {
    Write-Host "ERROR: Backup file not found: $BackupFile" -ForegroundColor Red
    exit 1
}

$size = (Get-Item $BackupFile).Length
Write-Host "Restore source : $BackupFile ($size bytes)"
Write-Host "Target database: trading_journal (via docker compose db service)"
Write-Host ""
Write-Host "WARNING: This will overwrite ALL existing data in trading_journal." -ForegroundColor Yellow

if (-not $Force) {
    $confirm = Read-Host "Type 'yes' to continue, anything else to cancel"
    if ($confirm -ne "yes") {
        Write-Host "Restore cancelled."
        exit 0
    }
}

Write-Host "Restoring..."

Get-Content $BackupFile | docker compose exec -T db psql -U trading trading_journal

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Restore complete." -ForegroundColor Green
    Write-Host "Restart the backend to pick up the restored data:"
    Write-Host "  docker compose restart backend"
} else {
    Write-Host "ERROR: psql restore failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Make sure the db container is running:  docker compose up -d db"
    exit 1
}
