from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.main.python.models.account import Account
from src.main.python.models.db_models import AccountModel
from src.main.python.utils.db_converters import account_to_orm, orm_to_account
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


class AccountRepository:
    """
    CRUD operations for Account objects against the accounts table.
    Does NOT manage Session lifecycle — caller provides and commits the session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, account: Account) -> Account:
        """Upsert account by primary key. Returns saved Account."""
        orm_obj = account_to_orm(account)
        merged = self._session.merge(orm_obj)
        self._session.flush()
        return orm_to_account(merged)

    def get_by_id(self, account_id: str) -> Optional[Account]:
        stmt = select(AccountModel).where(AccountModel.account_id == account_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        return orm_to_account(row) if row else None

    def list_all(self) -> List[Account]:
        """Return all accounts ordered by created_at descending."""
        stmt = select(AccountModel).order_by(AccountModel.created_at.desc())
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_account(r) for r in rows]

    def delete(self, account_id: str) -> bool:
        """
        Delete account and all its trades (ON DELETE CASCADE at DB level).
        Returns True if a row was deleted, False if account_id not found.
        """
        stmt = delete(AccountModel).where(AccountModel.account_id == account_id)
        result = self._session.execute(stmt)
        return result.rowcount > 0
