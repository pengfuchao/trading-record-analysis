#!/bin/bash
set -e

echo "[entrypoint] Running database migrations..."
# PYTHONPATH=/app causes the local alembic/ migration directory to shadow the
# installed alembic package (ModuleNotFoundError: No module named 'alembic.config').
# Clearing PYTHONPATH for this one command lets the CLI find the real package in
# site-packages. alembic/env.py then adds /app back to sys.path itself so the
# src.main.python.* model imports still work during the migration run.
PYTHONPATH="" alembic upgrade head

echo "[entrypoint] Starting API server..."
exec python -m uvicorn src.main.python.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
