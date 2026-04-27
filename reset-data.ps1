# Trading Journal — safe data reset (Windows PowerShell)
#
# Runs a full database backup BEFORE destroying the Docker volume.
# Prompts for explicit confirmation — prevents accidental data loss from
# a mistyped `docker compose down -v`.
#
# Usage:
#   .\reset-data.ps1

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Trading Journal — Data Reset" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will:"
Write-Host "  1. Back up the current database to backups/"
Write-Host "  2. Run: docker compose down -v  (DESTROYS all data)"
Write-Host "  3. You can then run: docker compose up --build  to start fresh"
Write-Host ""
Write-Host "WARNING: After step 2 there is no undo other than the backup." -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Type 'reset' to proceed, anything else to cancel"
if ($confirm -ne "reset") {
    Write-Host "Reset cancelled — no changes made." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "Step 1/2 — Creating backup..." -ForegroundColor Cyan
& "$PSScriptRoot\backup.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backup failed — reset aborted. No data was destroyed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 2/2 — Destroying volume..." -ForegroundColor Cyan
docker compose down -v

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Reset complete." -ForegroundColor Green
    Write-Host "To start fresh: docker compose up --build"
    Write-Host "To restore your data: .\restore.ps1 -BackupFile backups\<your_backup>.sql"
} else {
    Write-Host "ERROR: docker compose down -v failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}
