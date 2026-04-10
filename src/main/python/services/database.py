from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.main.python.utils.config_loader import load_yaml
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)

load_dotenv()  # reads .env into os.environ at import time

_DB_CONFIG_PATH = "src/main/resources/config/database.yaml"
_engine = None
_SessionFactory = None


def _load_db_config() -> dict:
    try:
        return load_yaml(_DB_CONFIG_PATH).get("database", {})
    except FileNotFoundError:
        logger.warning("database.yaml not found — using pool defaults")
        return {}


def get_engine():
    global _engine
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL not set. Copy .env.example to .env and fill in your credentials."
            )
        cfg = _load_db_config()
        _engine = create_engine(
            database_url,
            pool_size=cfg.get("pool_size", 5),
            max_overflow=cfg.get("max_overflow", 10),
            echo=cfg.get("echo", False),
        )
        logger.info(
            "Database engine created (pool_size=%d, echo=%s)",
            cfg.get("pool_size", 5),
            cfg.get("echo", False),
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionFactory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager that yields a Session.
    Commits on clean exit, rolls back on any exception.

    Usage:
        with get_session() as session:
            repo = TradeRepository(session)
            repo.save(trade)
        # session is committed and closed here
    """
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
