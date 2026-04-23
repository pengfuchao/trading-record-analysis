from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from src.main.python.services.database import get_engine

router = APIRouter(tags=["ops"])


@router.get("/health", include_in_schema=False)
def liveness():
    """Liveness — returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
def readiness():
    """Readiness — confirms DB is reachable before accepting traffic."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")
