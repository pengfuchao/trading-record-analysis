#!/usr/bin/env bash
# start-local-backend.sh
#
# Starts the FastAPI backend natively (WSL or Linux) for local dev mode.
#
# For MT5 live sync use start-local-backend.ps1 in a native Windows PowerShell
# terminal instead — MetaTrader5 is Windows-only. This script is useful for
# local development without Docker when you don't need MT5 sync.
#
# Prerequisites:
#   - Postgres reachable (Docker Compose `db` service or local Postgres)
#   - Python venv at ./venv (run `python -m venv venv && pip install -r requirements.txt` once)
#   - .env file at repo root with DATABASE_URL and any optional keys
#
# Usage (from repo root):
#   bash start-local-backend.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- 1. (Optional) stop Docker backend to free port 8000 ---
if command -v docker &>/dev/null; then
    echo "Stopping Docker backend container (frees port 8000)..."
    docker compose stop backend 2>/dev/null || true
fi

# --- 2. Activate venv ---
VENV="$REPO_ROOT/venv/bin/activate"
if [[ ! -f "$VENV" ]]; then
    echo "ERROR: Python venv not found at ./venv"
    echo "Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
echo "Activating virtual environment..."
# shellcheck disable=SC1090
source "$VENV"

# --- 3. Set PYTHONPATH to repo root ---
export PYTHONPATH="$REPO_ROOT"
echo "PYTHONPATH=$PYTHONPATH"

# --- 4. Run migrations ---
echo "Running Alembic migrations..."
python -m alembic upgrade head

# --- 5. Start backend ---
echo ""
echo "Starting backend on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop."
echo ""
exec python -m uvicorn src.main.python.api.app:app --reload --host 0.0.0.0 --port 8000 --workers 1
