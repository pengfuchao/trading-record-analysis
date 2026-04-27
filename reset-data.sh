#!/usr/bin/env bash
# Trading Journal — safe data reset (WSL / Linux / macOS)
#
# Runs a full database backup BEFORE destroying the Docker volume.
# Prompts for explicit confirmation — prevents accidental data loss from
# a mistyped `docker compose down -v`.
#
# Usage:
#   ./reset-data.sh
set -euo pipefail

echo "================================================================"
echo "  Trading Journal — Data Reset"
echo "================================================================"
echo ""
echo "This script will:"
echo "  1. Back up the current database to backups/"
echo "  2. Run: docker compose down -v  (DESTROYS all data)"
echo "  3. You can then run: docker compose up --build  to start fresh"
echo ""
echo "WARNING: After step 2 there is no undo other than the backup."
echo ""

read -r -p "Type 'reset' to proceed, anything else to cancel: " confirm
if [ "$confirm" != "reset" ]; then
    echo "Reset cancelled — no changes made."
    exit 0
fi

echo ""
echo "Step 1/2 — Creating backup..."
bash "$(dirname "$0")/backup.sh"

echo ""
echo "Step 2/2 — Destroying volume..."
docker compose down -v

echo ""
echo "Reset complete."
echo "To start fresh: docker compose up --build"
echo "To restore your data: bash restore.sh backups/<your_backup_file>.sql"
