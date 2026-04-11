from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.main.python.api.routes import accounts, analytics, coaching, imports, mistakes, setups, trades
from src.main.python.api.routes.daily_plans import plans_router, reviews_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Journal API",
        version="1.0.0",
        description="REST API for the trading journal and account analytics system.",
    )

    # CORS — configure CORS_ORIGINS env var for production (comma-separated)
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(accounts.router, prefix="/api/v1")
    app.include_router(trades.router,   prefix="/api/v1")
    app.include_router(imports.router,  prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")
    app.include_router(mistakes.router,           prefix="/api/v1")
    app.include_router(setups.setup_defs_router,  prefix="/api/v1")
    app.include_router(setups.setup_stats_router, prefix="/api/v1")
    app.include_router(plans_router,              prefix="/api/v1")
    app.include_router(reviews_router,            prefix="/api/v1")
    app.include_router(coaching.router,           prefix="/api/v1")

    return app


# Module-level instance for: uvicorn src.main.python.api.app:app
app = create_app()
