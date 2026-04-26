#!/usr/bin/env bash
# Trading Journal — database restore from a pg_dump SQL backup (WSL / Linux / macOS)
#
# Requires: Docker running with the Compose stack up (at least the db service)
#
# Usage:
#   ./restore.sh backups/backup_20260426_120000.sql
#   FORCE=1 ./restore.sh backups/backup_20260426_120000.sql   # skip confirmation
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file.sql>"
    echo "       FORCE=1 $0 <backup_file.sql>   # skip confirmation prompt"
    exit 1
fi

BACKUP_FILE="$1"
FORCE="${FORCE:-0}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

size=$(wc -c < "$BACKUP_FILE")
echo "Restore source : $BACKUP_FILE (${size} bytes)"
echo "Target database: trading_journal (via docker compose db service)"
echo ""
echo "WARNING: This will overwrite ALL existing data in trading_journal."

if [ "$FORCE" != "1" ]; then
    read -r -p "Type 'yes' to continue, anything else to cancel: " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

echo "Restoring..."
docker compose exec -T db psql -U trading trading_journal < "$BACKUP_FILE"

echo ""
echo "Restore complete."
echo "Restart the backend to pick up the restored data:"
echo "  docker compose restart backend"
