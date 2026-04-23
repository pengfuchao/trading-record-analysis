#!/bin/bash
set -e

echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Starting API server..."
exec python -m uvicorn src.main.python.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
