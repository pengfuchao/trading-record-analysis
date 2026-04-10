from __future__ import annotations

from typing import Generator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.main.python.models.account import Account
from src.main.python.services.account_repository import AccountRepository
from src.main.python.services.csv_parser import MTCSVParser
from src.main.python.services.database import get_session
from src.main.python.services.trade_repository import TradeRepository


def get_db() -> Generator[Session, None, None]:
    """FastAPI-compatible DB session dependency. Commit/rollback handled by get_session()."""
    with get_session() as session:
        yield session


def get_account_repo(db: Session = None) -> AccountRepository:
    return AccountRepository(db)


def get_trade_repo(db: Session = None) -> TradeRepository:
    return TradeRepository(db)


def get_parser() -> MTCSVParser:
    """New parser instance per request — parser has mutable state (skipped_rows, validation_errors)."""
    return MTCSVParser()


def require_account(account_id: str, repo: AccountRepository) -> Account:
    """Fetch account or raise 404."""
    account = repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")
    return account
