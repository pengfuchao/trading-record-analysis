from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from src.main.python.models.db_models import TradeModel
from src.main.python.models.trade import Trade
from src.main.python.utils.db_converters import orm_to_trade, trade_to_orm
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Broker-sourced fields: safe to overwrite on re-import.
# Does NOT include any manual enrichment fields (strategy, rationale, flags, etc.).
_BROKER_FIELDS = (
    "symbol", "asset_class", "direction", "platform", "raw_trade_type",
    "entry_datetime", "exit_datetime", "holding_duration",
    "entry_price", "exit_price", "stop_loss", "take_profit", "lot_size",
    "gross_pnl", "commission", "swap", "net_pnl", "actual_r_multiple",
    "result", "magic", "comment", "import_run_id",
)


@dataclass
class ImportCounts:
    new: int = 0
    updated: int = 0
    skipped: int = 0


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

    def get_existing_trade_ids(self, account_id: str, trade_ids: List[str]) -> Set[str]:
        """Return the subset of trade_ids that already exist in DB for this account."""
        if not trade_ids:
            return set()
        stmt = select(TradeModel.trade_id).where(
            TradeModel.account_id == account_id,
            TradeModel.trade_id.in_(trade_ids),
        )
        return set(self._session.execute(stmt).scalars().all())

    def save_batch_import(
        self,
        trades: List[Trade],
        import_run_id: str,
        duplicate_strategy: str = "skip",
    ) -> ImportCounts:
        """
        Import-aware batch save that protects manual enrichment from overwrites.

        duplicate_strategy:
          "skip"          — skip trades whose trade_id already exists (default, safest)
          "update_broker" — overwrite only broker-sourced fields on existing trades;
                            all manual enrichment fields are preserved.

        Returns ImportCounts(new, updated, skipped).
        """
        if not trades:
            return ImportCounts()

        incoming_ids = [t.trade_id for t in trades]
        existing_ids = self.get_existing_trade_ids(trades[0].account_id, incoming_ids)

        counts = ImportCounts()
        for trade in trades:
            if trade.trade_id not in existing_ids:
                # New trade — full insert via upsert
                self._session.merge(trade_to_orm(trade, import_run_id=import_run_id))
                counts.new += 1
            elif duplicate_strategy == "skip":
                counts.skipped += 1
            elif duplicate_strategy == "update_broker":
                # Fetch existing ORM object and update only broker-sourced fields
                orm_obj = self._session.get(TradeModel, trade.trade_id)
                if orm_obj is not None:
                    new_orm = trade_to_orm(trade, import_run_id=import_run_id)
                    for field in _BROKER_FIELDS:
                        setattr(orm_obj, field, getattr(new_orm, field, None))
                counts.updated += 1
            else:
                # Unknown strategy — treat as skip
                counts.skipped += 1

        self._session.flush()
        logger.info(
            "Import batch (run=%s): new=%d updated=%d skipped=%d strategy=%s",
            import_run_id, counts.new, counts.updated, counts.skipped, duplicate_strategy,
        )
        return counts

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
