#!/usr/bin/env bash
# Trading Journal — pg_dump backup script (WSL / Linux / macOS)
#
# Requires: Docker running with the Compose stack up (at least the db service)
#
# Usage:
#   ./backup.sh                  # creates backups/backup_YYYYMMDD_HHMMSS.sql
#   OUT_DIR=/mnt/nas ./backup.sh # custom output directory
set -euo pipefail

OUT_DIR="${OUT_DIR:-backups}"
timestamp=$(date +%Y%m%d_%H%M%S)
outfile="${OUT_DIR}/backup_${timestamp}.sql"

mkdir -p "$OUT_DIR"

echo "Backing up trading_journal database..."
docker compose exec -T db pg_dump -U trading trading_journal > "$outfile"

size=$(wc -c < "$outfile")
echo "Backup complete: $outfile (${size} bytes)"
echo ""
echo "To restore:"
echo "  docker compose exec -T db psql -U trading trading_journal < \"$outfile\""
