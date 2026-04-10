from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.main.python.models.db_models import TradeModel
from src.main.python.models.trade import Trade
from src.main.python.utils.db_converters import orm_to_trade, trade_to_orm
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


class TradeRepository:
    """
    CRUD operations for Trade objects against the trades table.
    Does NOT manage Session lifecycle — caller provides and commits the session.
    All public methods accept and return domain dataclasses (Trade), not ORM models.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, trade: Trade, import_run_id: str = None) -> Trade:
        """
        Upsert a single trade by primary key (trade_id).
        Uses session.merge() for idempotent save-or-update.
        Returns the saved Trade with any DB-generated values reflected.
        """
        orm_obj = trade_to_orm(trade, import_run_id=import_run_id)
        merged = self._session.merge(orm_obj)
        self._session.flush()
        return orm_to_trade(merged)

    def save_batch(self, trades: List[Trade], import_run_id: str = None) -> int:
        """
        Bulk upsert. Returns count of saved trades.
        The surrounding session is committed by the caller.
        """
        count = 0
        for trade in trades:
            self._session.merge(trade_to_orm(trade, import_run_id=import_run_id))
            count += 1
        self._session.flush()
        logger.info("Batch saved %d trades (import_run_id=%s)", count, import_run_id)
        return count

    def get_by_id(self, trade_id: str) -> Optional[Trade]:
        stmt = select(TradeModel).where(TradeModel.trade_id == trade_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        return orm_to_trade(row) if row else None

    def get_by_account(self, account_id: str) -> List[Trade]:
        """Return all trades for an account ordered by exit_datetime ascending."""
        stmt = (
            select(TradeModel)
            .where(TradeModel.account_id == account_id)
            .order_by(TradeModel.exit_datetime.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_trade(r) for r in rows]

    def get_by_account_filtered(
        self,
        account_id: str,
        symbol: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        result: Optional[str] = None,
    ) -> List[Trade]:
        """
        Filtered query. All filters are additive (AND).
        from_date / to_date filter on exit_datetime (inclusive).
        result should be the enum .value string: "Win", "Loss", or "Breakeven".
        """
        stmt = (
            select(TradeModel)
            .where(TradeModel.account_id == account_id)
        )
        if symbol:
            stmt = stmt.where(TradeModel.symbol == symbol)
        if from_date:
            stmt = stmt.where(TradeModel.exit_datetime >= from_date)
        if to_date:
            stmt = stmt.where(TradeModel.exit_datetime <= to_date)
        if result:
            stmt = stmt.where(TradeModel.result == result)
        stmt = stmt.order_by(TradeModel.exit_datetime.asc())
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_trade(r) for r in rows]

    def delete(self, trade_id: str) -> bool:
        """Returns True if a row was deleted, False if trade_id not found."""
        stmt = delete(TradeModel).where(TradeModel.trade_id == trade_id)
        result = self._session.execute(stmt)
        return result.rowcount > 0

    def count(self, account_id: str) -> int:
        stmt = select(func.count()).select_from(TradeModel).where(
            TradeModel.account_id == account_id
        )
        return self._session.execute(stmt).scalar_one()
