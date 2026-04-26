from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from src.main.python.models.db_models import TradeModel
from src.main.python.models.trade import Trade
from src.main.python.utils.db_converters import orm_to_trade, trade_to_orm
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ── Inline helpers for derived-field recomputation ───────────────────────────
# These mirror DerivedFieldCalculator formulas but are inlined here to avoid
# cross-layer imports inside the repository.

def _price_based_r(
    exit_price: Optional[float],
    entry_price: Optional[float],
    stop_loss: Optional[float],
    direction_str: Optional[str],
) -> Optional[float]:
    """Price-based R: signed_price_move / sl_distance. Instrument-independent."""
    if None in (exit_price, entry_price, direction_str) or not stop_loss:
        return None
    sl_distance = abs(entry_price - stop_loss)
    if sl_distance == 0:
        return None
    if direction_str == "Long":
        return round((exit_price - entry_price) / sl_distance, 2)
    if direction_str == "Short":
        return round((entry_price - exit_price) / sl_distance, 2)
    return None


def _derive_session(entry_datetime: Optional[datetime], utc_offset: int = 2) -> Optional[str]:
    """Session derived from entry hour normalised to UTC+2 reference frame."""
    if entry_datetime is None:
        return None
    hour = (entry_datetime.hour - (utc_offset - 2)) % 24
    if hour < 9:
        return "Asia"
    if hour < 13:
        return "London"
    if hour < 17:
        return "London/NY"
    if hour < 21:
        return "New York"
    return "After Hours"


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
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Trade], int]:
        """
        Filtered, paginated query. All filters are additive (AND).
        from_date / to_date filter on exit_datetime (inclusive).
        result should be the enum .value string: "Win", "Loss", or "Breakeven".

        Returns (items, total) where total is the count matching all filters.
        page is 1-based; page_size controls rows per page.
        Ordered newest-first (exit_datetime DESC) so the Trade Log shows recent
        trades at the top.
        """
        # Build the shared WHERE clause
        where_clauses = [TradeModel.account_id == account_id]
        if symbol:
            where_clauses.append(TradeModel.symbol == symbol)
        if from_date:
            where_clauses.append(TradeModel.exit_datetime >= from_date)
        if to_date:
            where_clauses.append(TradeModel.exit_datetime <= to_date)
        if result:
            where_clauses.append(TradeModel.result == result)

        # Count query — same filters, no LIMIT/OFFSET
        count_stmt = (
            select(func.count())
            .select_from(TradeModel)
            .where(*where_clauses)
        )
        total: int = self._session.execute(count_stmt).scalar_one()

        # Paginated data query — newest first, nulls pushed to end
        offset = (max(1, page) - 1) * page_size
        data_stmt = (
            select(TradeModel)
            .where(*where_clauses)
            .order_by(TradeModel.exit_datetime.desc().nulls_last())
            .limit(page_size)
            .offset(offset)
        )
        rows = self._session.execute(data_stmt).scalars().all()
        return [orm_to_trade(r) for r in rows], total

    def get_all_filtered(
        self,
        account_id: str,
        symbol: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        result: Optional[str] = None,
    ) -> List[Trade]:
        """
        Return all matching trades without pagination, ordered by exit_datetime.
        Used by the CSV export route.  Same filter semantics as get_by_account_filtered.
        """
        where_clauses = [TradeModel.account_id == account_id]
        if symbol:
            where_clauses.append(TradeModel.symbol == symbol)
        if from_date:
            where_clauses.append(TradeModel.exit_datetime >= from_date)
        if to_date:
            where_clauses.append(TradeModel.exit_datetime <= to_date)
        if result:
            where_clauses.append(TradeModel.result == result)
        stmt = (
            select(TradeModel)
            .where(*where_clauses)
            .order_by(TradeModel.exit_datetime.asc())
        )
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

    def get_unlinked_by_account(self, account_id: str, limit: int = 200) -> List[Trade]:
        """Return trades with no linked plan, ordered by entry_datetime descending."""
        stmt = (
            select(TradeModel)
            .where(
                TradeModel.account_id == account_id,
                TradeModel.trade_plan_id.is_(None),
            )
            .order_by(TradeModel.entry_datetime.desc().nulls_last())
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_trade(r) for r in rows]

    def count_trades_for_plan(self, plan_id: str) -> int:
        """Return number of trades currently linked to a plan."""
        stmt = select(func.count()).select_from(TradeModel).where(
            TradeModel.trade_plan_id == plan_id
        )
        return self._session.execute(stmt).scalar_one()

    def get_by_plan_id(self, plan_id: str) -> List[Trade]:
        """Return all trades linked to a specific plan, ordered by entry_datetime."""
        stmt = (
            select(TradeModel)
            .where(TradeModel.trade_plan_id == plan_id)
            .order_by(TradeModel.entry_datetime.asc().nulls_last())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_trade(r) for r in rows]

    def get_trades_for_date(self, account_id: str, target_date) -> List[Trade]:
        """Return all closed trades whose exit_datetime falls on target_date (date object)."""
        from datetime import datetime as _dt
        day_start = _dt(target_date.year, target_date.month, target_date.day, 0, 0, 0)
        day_end = _dt(target_date.year, target_date.month, target_date.day, 23, 59, 59)
        stmt = (
            select(TradeModel)
            .where(
                TradeModel.account_id == account_id,
                TradeModel.exit_datetime >= day_start,
                TradeModel.exit_datetime <= day_end,
            )
            .order_by(TradeModel.exit_datetime.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_trade(r) for r in rows]

    def get_import_history(self, account_id: str) -> List[dict]:
        """
        Return one summary dict per import_run_id for this account.
        Each dict contains: import_run_id, trade_count, earliest_trade_date,
        latest_trade_date, symbols (sorted list of unique symbols).
        Only import batches with a non-NULL import_run_id are returned.
        """
        stmt = (
            select(
                TradeModel.import_run_id,
                func.count(TradeModel.trade_id).label("trade_count"),
                func.min(TradeModel.exit_datetime).label("earliest"),
                func.max(TradeModel.exit_datetime).label("latest"),
            )
            .where(
                TradeModel.account_id == account_id,
                TradeModel.import_run_id.isnot(None),
            )
            .group_by(TradeModel.import_run_id)
            .order_by(func.min(TradeModel.exit_datetime).asc())
        )
        rows = self._session.execute(stmt).all()
        history = []
        for row in rows:
            # Fetch distinct symbols for this batch
            sym_stmt = (
                select(TradeModel.symbol)
                .where(
                    TradeModel.account_id == account_id,
                    TradeModel.import_run_id == row.import_run_id,
                    TradeModel.symbol.isnot(None),
                )
                .distinct()
            )
            symbols = sorted(self._session.execute(sym_stmt).scalars().all())
            history.append({
                "import_run_id": row.import_run_id,
                "trade_count": row.trade_count,
                "earliest_trade_date": row.earliest,
                "latest_trade_date": row.latest,
                "symbols": symbols,
            })
        return history

    def recompute_derived_fields(
        self,
        account_id: str,
        recalculate_r: bool = True,
        recalculate_session: bool = False,
        overwrite_session: bool = False,
        broker_utc_offset: int = 2,
    ) -> dict:
        """
        Recompute broker-derived fields for all trades in an account.

        Preserves ALL manual enrichment fields — only recomputes calculated
        fields that can be fully derived from other stored broker-sourced values.

        recalculate_r:
          Recompute actual_r_multiple using the price-based formula:
            LONG:  (exit_price - entry_price) / abs(entry_price - stop_loss)
            SHORT: (entry_price - exit_price) / abs(stop_loss - entry_price)
          Returns None for trades missing exit_price, entry_price, stop_loss,
          or direction, OR where stop_loss == entry_price.
          Safe to run multiple times — idempotent.

        recalculate_session (default False — safe):
          Re-derive session from entry_datetime using broker_utc_offset.
          When overwrite_session=False (default): only fills in trades where
          session IS NULL (never set). Does NOT overwrite manually set sessions.
          When overwrite_session=True: replaces ALL session values, including
          those the user may have set manually.

        Returns a count dict suitable for RecomputeResponse.
        """
        stmt = select(TradeModel).where(TradeModel.account_id == account_id)
        orm_trades = self._session.execute(stmt).scalars().all()

        updated_r = 0
        skipped_r = 0
        updated_session = 0
        skipped_session = 0

        for t in orm_trades:
            if recalculate_r:
                new_r = _price_based_r(t.exit_price, t.entry_price, t.stop_loss, t.direction)
                if new_r is not None or (
                    t.exit_price is None or t.entry_price is None
                    or not t.stop_loss or t.direction is None
                ):
                    if new_r is None:
                        skipped_r += 1
                    else:
                        t.actual_r_multiple = new_r
                        updated_r += 1

            if recalculate_session:
                if not overwrite_session and t.session is not None:
                    skipped_session += 1
                else:
                    new_session = _derive_session(t.entry_datetime, broker_utc_offset)
                    t.session = new_session
                    updated_session += 1

        self._session.flush()
        logger.info(
            "Recompute derived fields (account=%s): r_updated=%d r_skipped=%d "
            "session_updated=%d session_skipped=%d",
            account_id, updated_r, skipped_r, updated_session, skipped_session,
        )
        return {
            "account_id": account_id,
            "trades_processed": len(orm_trades),
            "trades_updated_r": updated_r,
            "trades_skipped_r": skipped_r,
            "trades_updated_session": updated_session,
            "trades_skipped_session": skipped_session,
        }
