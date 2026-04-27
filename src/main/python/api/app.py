from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.main.python.api.routes import accounts, analytics, coaching, imports, mistakes, setups, trades
from src.main.python.api.routes.daily_plans import plans_router, reviews_router
from src.main.python.api.routes.health import router as health_router
from src.main.python.api.routes.mt5_sync import router as mt5_sync_router
from src.main.python.api.routes.telegram import router as telegram_router
from src.main.python.api.routes.trade_plans import router as trade_plans_router
from src.main.python.services.mt5_scheduler import get_scheduler
from src.main.python.utils.logging_utils import configure_logging, get_logger


def _safe_db_url(url: str) -> str:
    """Strip credentials from DATABASE_URL for safe logging."""
    if not url:
        return "(not set)"
    if "@" in url:
        return url.split("@", 1)[-1]  # e.g., "localhost:5432/trading_journal"
    return url.split("://", 1)[-1][:60]  # SQLite: show file path


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
    logger = get_logger(__name__)

    db_display = _safe_db_url(os.environ.get("DATABASE_URL", ""))
    cors_origins = os.environ.get("CORS_ORIGINS", "*")
    logger.info("Trading Journal API starting up")
    logger.info("  database : %s", db_display)
    logger.info("  CORS     : %s", cors_origins)
    logger.info("  log level: %s", os.environ.get("LOG_LEVEL", "INFO"))

    # MT5 sync uses an in-memory overlap lock — unsafe with multiple workers.
    workers_env = os.environ.get("UVICORN_WORKERS", "1").strip()
    try:
        if int(workers_env) != 1:
            logger.warning(
                "UVICORN_WORKERS=%s — MT5 sync overlap protection is in-memory only. "
                "Running multiple workers will silently corrupt MT5 sync state. "
                "Set UVICORN_WORKERS=1 (or omit it).",
                workers_env,
            )
    except ValueError:
        pass

    scheduler = get_scheduler()
    scheduler.start()
    logger.info("MT5 background scheduler started")

    try:
        yield
    finally:
        logger.info("Trading Journal API shutting down")
        scheduler.stop()
        logger.info("MT5 background scheduler stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Journal API",
        version="1.0.0",
        description="REST API for the trading journal and account analytics system.",
        lifespan=_lifespan,
    )

    # CORS — set CORS_ORIGINS env var for production (comma-separated)
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ops endpoints at root (no /api/v1 prefix)
    app.include_router(health_router)

    app.include_router(accounts.router, prefix="/api/v1")
    app.include_router(trades.router,   prefix="/api/v1")
    app.include_router(imports.router,  prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")
    app.include_router(mistakes.router,           prefix="/api/v1")
    app.include_router(setups.setup_defs_router,  prefix="/api/v1")
    app.include_router(setups.setup_stats_router, prefix="/api/v1")
    app.include_router(plans_router,              prefix="/api/v1")
    app.include_router(reviews_router,            prefix="/api/v1")
    app.include_router(coaching.router,            prefix="/api/v1")
    app.include_router(trade_plans_router,         prefix="/api/v1")
    app.include_router(mt5_sync_router,            prefix="/api/v1")
    app.include_router(telegram_router,            prefix="/api/v1")

    return app


# Module-level instance for: python -m uvicorn src.main.python.api.app:app
app = create_app()
