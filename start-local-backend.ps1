# start-local-backend.ps1
#
# Starts the FastAPI backend natively on Windows for MT5 live sync mode.
#
# Use this when you need MT5 live sync. The Docker Compose stack must already
# be running (at minimum the `db` service for Postgres on port 5432).
# The Docker `backend` container must be stopped first to free port 8000.
#
# Prerequisites:
#   - Docker Desktop running with `docker compose up -d` (or at least `db` + `frontend`)
#   - Python venv created at .\venv (run `python -m venv venv` once if missing)
#   - pip install -r requirements.txt already done inside the venv
#   - .env file at repo root with DATABASE_URL, API keys, MT5 passwords
#
# Usage (from repo root in PowerShell):
#   .\start-local-backend.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- 1. Stop the Docker backend to free port 8000 ---
Write-Host "Stopping Docker backend container (frees port 8000)..."
docker compose stop backend
if ($LASTEXITCODE -ne 0) {
    Write-Warning "docker compose stop backend failed — the container may not be running. Continuing."
}

# --- 2. Activate venv ---
$venvActivate = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Error "Python venv not found at .\venv — run: python -m venv venv && .\venv\Scripts\activate && pip install -r requirements.txt"
}
Write-Host "Activating virtual environment..."
. $venvActivate

# --- 3. Set PYTHONPATH to repo root (required for src.main.python.* imports) ---
$env:PYTHONPATH = $PSScriptRoot
Write-Host "PYTHONPATH = $env:PYTHONPATH"

# --- 4. Run migrations ---
Write-Host "Running Alembic migrations..."
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Error "Alembic upgrade failed — check DATABASE_URL in .env and that the db container is running."
}

# --- 5. Start backend ---
Write-Host ""
Write-Host "Starting backend on http://localhost:8000  (MT5 sync enabled)"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host "Press Ctrl+C to stop."
Write-Host ""
python -m uvicorn src.main.python.api.app:app --reload --host 0.0.0.0 --port 8000 --workers 1
