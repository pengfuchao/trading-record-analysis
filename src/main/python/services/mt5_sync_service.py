"""
MT5SyncService — orchestrates a live MT5 sync run.

Flow:
  1. Record a "running" sync run in mt5_sync_runs
  2. Open MT5Connector → fetch deals → reconstruct closed positions
  3. Normalize positions into Trade domain objects using DerivedFieldCalculator
     (same derived fields computed by the CSV import pipeline)
  4. Upsert via TradeRepository.save_batch_import(duplicate_strategy="update_broker")
     — broker-sourced fields are refreshed; all manual enrichment is preserved
  5. Update the run record to "success" or "error"
  6. Return SyncResult

Reuses:
  - DerivedFieldCalculator (all methods — no changes needed)
  - TradeRepository.save_batch_import + _BROKER_FIELDS (no changes needed)
  - Asset class rules from mt_column_map.yaml (same as CSV parser)
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.main.python.models.db_models import MT5OpenPositionModel, MT5SyncConfigModel, MT5SyncRunModel
from src.main.python.models.enums import Direction, Platform
from src.main.python.models.trade import Trade
from src.main.python.services.derived_field_calculator import DerivedFieldCalculator
from src.main.python.services.mt5_connector import MT5ConnectionConfig, MT5ConnectionError, MT5Connector
from src.main.python.services.trade_repository import TradeRepository
from src.main.python.utils.config_loader import get_app_config, load_yaml

logger = logging.getLogger(__name__)

_calc = DerivedFieldCalculator()


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class SyncResult:
    run_id: str
    account_id: str
    status: str                     # "success" | "error"
    deals_fetched: int = 0
    positions_built: int = 0
    trades_new: int = 0
    trades_updated: int = 0
    trades_skipped: int = 0
    open_positions_count: int = 0
    error_message: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


# ── Service ────────────────────────────────────────────────────────────────────

class MT5SyncService:
    """
    Orchestrates MT5 live sync for a single account.
    Caller provides and owns the SQLAlchemy session — this service does not commit.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._trade_repo = TradeRepository(session)

        # Load asset class rules once — same source the CSV parser uses
        config = get_app_config()
        column_map_path: str = config["paths"]["mt_column_map"]
        self._asset_class_rules: dict = load_yaml(column_map_path).get("asset_class_rules", {})

    # ── Config helpers ─────────────────────────────────────────────────────────

    def get_config(self, account_id: str) -> Optional[MT5SyncConfigModel]:
        """Return the MT5 sync config for an account, or None if not configured."""
        return self._session.get(MT5SyncConfigModel, account_id)

    def save_config(self, account_id: str, data: Dict[str, Any]) -> MT5SyncConfigModel:
        """
        Create or update the MT5 sync config for an account.
        Password is intentionally NOT part of data — it lives in .env.
        """
        existing = self._session.get(MT5SyncConfigModel, account_id)
        if existing is None:
            obj = MT5SyncConfigModel(account_id=account_id, **data)
            self._session.add(obj)
        else:
            for k, v in data.items():
                setattr(existing, k, v)
            obj = existing
        self._session.flush()
        return obj

    def get_recent_runs(self, account_id: str, limit: int = 5) -> List[MT5SyncRunModel]:
        """Return the most recent sync runs for an account, newest first."""
        stmt = (
            select(MT5SyncRunModel)
            .where(MT5SyncRunModel.account_id == account_id)
            .order_by(MT5SyncRunModel.started_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_last_successful_sync_time(self, account_id: str):
        """
        Return the completed_at of the most recent successful sync run, independent
        of any run-history limit. Returns None if no successful run exists.
        """
        from datetime import datetime
        stmt = (
            select(MT5SyncRunModel.completed_at)
            .where(
                MT5SyncRunModel.account_id == account_id,
                MT5SyncRunModel.status == "success",
                MT5SyncRunModel.completed_at.isnot(None),
            )
            .order_by(MT5SyncRunModel.completed_at.desc())
            .limit(1)
        )
        result = self._session.execute(stmt).scalar_one_or_none()
        return result

    # ── Sync orchestration ─────────────────────────────────────────────────────

    def sync_account(
        self,
        account_id: str,
        config: MT5ConnectionConfig,
        from_date: datetime,
        to_date: datetime,
        triggered_by: str = "manual",
    ) -> SyncResult:
        """
        Run a full sync: connect → fetch → normalize → upsert.

        This is synchronous and blocks the caller until complete.
        All exceptions are caught, recorded in the run log, and surfaced as SyncResult.status="error".
        The caller's session is NOT committed here — that remains the caller's responsibility.
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        # Record the run as "running" before we start
        run_row = MT5SyncRunModel(
            run_id=run_id,
            account_id=account_id,
            triggered_by=triggered_by,
            started_at=started_at,
            status="running",
            from_date=from_date,
            to_date=to_date,
        )
        self._session.add(run_row)
        self._session.flush()

        result = SyncResult(
            run_id=run_id,
            account_id=account_id,
            status="error",
            started_at=started_at,
        )

        try:
            with MT5Connector(config) as conn:
                # Fetch raw deals
                deals = conn.fetch_deals(from_date, to_date)
                result.deals_fetched = len(deals)

                # Fetch SL/TP from orders — deals don't carry these fields.
                # Non-fatal: returns {} if history_orders_get fails or is unavailable.
                orders_sl_tp = conn.fetch_orders_sl_tp(from_date, to_date)

                # Reconstruct closed positions from deal groups
                positions = conn.reconstruct_positions(deals, orders_sl_tp=orders_sl_tp)
                result.positions_built = len(positions)

                # Normalize to Trade domain objects
                trades = self._normalize_positions(account_id, run_id, positions, config)

                # Upsert via existing import infrastructure
                counts = self._trade_repo.save_batch_import(
                    trades,
                    import_run_id=run_id,
                    duplicate_strategy="update_broker",
                )

                # Trade counts are captured here so they are correct even if
                # the open-positions fetch below fails.
                result.trades_new = counts.new
                result.trades_updated = counts.updated
                result.trades_skipped = counts.skipped
                result.status = "success"

                logger.info(
                    "MT5 sync complete run=%s account=%s new=%d updated=%d skipped=%d",
                    run_id, account_id, counts.new, counts.updated, counts.skipped,
                )

                # Refresh open positions snapshot — non-fatal: a failure here
                # does not revert the closed-trade sync that already succeeded.
                try:
                    open_pos = conn.fetch_open_positions()
                    self._refresh_open_positions(account_id, open_pos)
                    result.open_positions_count = len(open_pos)
                except Exception as pos_exc:
                    logger.warning(
                        "Open positions refresh failed run=%s account=%s — "
                        "closed-trade sync is unaffected: %s",
                        run_id, account_id, pos_exc,
                    )

        except (MT5ConnectionError, Exception) as exc:
            result.error_message = str(exc)
            result.status = "error"
            logger.error(
                "MT5 sync failed run=%s account=%s error=%s",
                run_id, account_id, exc, exc_info=True,
            )

        finally:
            result.completed_at = datetime.now(timezone.utc)
            # Update the run row regardless of success/failure
            run_row.status = result.status
            run_row.completed_at = result.completed_at
            run_row.deals_fetched = result.deals_fetched
            run_row.positions_built = result.positions_built
            run_row.trades_new = result.trades_new
            run_row.trades_updated = result.trades_updated
            run_row.trades_skipped = result.trades_skipped
            run_row.error_message = result.error_message
            self._session.flush()

        return result

    # ── Normalization ──────────────────────────────────────────────────────────

    def _normalize_positions(
        self,
        account_id: str,
        run_id: str,
        positions: List[Dict[str, Any]],
        config: MT5ConnectionConfig,
    ) -> List[Trade]:
        """
        Convert reconstructed MT5 position dicts into Trade domain objects.
        Uses the same DerivedFieldCalculator methods as the CSV import pipeline.
        """
        trades: List[Trade] = []

        for pos in positions:
            direction = _calc.calc_direction(pos["raw_type"])
            gross_pnl = pos.get("gross_profit")
            commission = pos.get("commission")
            swap = pos.get("swap")
            net_pnl = _calc.calc_net_pnl(gross_pnl, commission, swap)
            result_enum = _calc.calc_result(net_pnl, gross_pnl)
            entry_dt: Optional[datetime] = pos.get("entry_time")
            exit_dt: Optional[datetime] = pos.get("exit_time")
            entry_price = pos.get("entry_price")
            exit_price = pos.get("exit_price")
            sl = pos.get("sl")

            trade = Trade(
                trade_id=str(pos["position_id"]),
                account_id=account_id,
                platform=Platform.MT5,
                symbol=pos.get("symbol"),
                raw_trade_type=pos.get("raw_type"),
                direction=direction,
                asset_class=_calc.calc_asset_class(pos.get("symbol"), self._asset_class_rules),
                entry_datetime=entry_dt,
                exit_datetime=exit_dt,
                holding_duration=_calc.calc_holding_duration(entry_dt, exit_dt),
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=sl,
                take_profit=pos.get("tp"),
                lot_size=pos.get("volume"),
                gross_pnl=gross_pnl,
                commission=commission,
                swap=swap,
                net_pnl=net_pnl,
                actual_r_multiple=_calc.calc_actual_r(exit_price, entry_price, sl, direction),
                result=result_enum,
                session=_calc.calc_session(entry_dt, utc_offset=config.broker_utc_offset),
                magic=pos.get("magic"),
                comment=pos.get("comment") or "",
            )
            trades.append(trade)

        return trades

    def _refresh_open_positions(
        self,
        account_id: str,
        raw_positions: List[Dict[str, Any]],
    ) -> None:
        """
        Replace the open-positions snapshot for this account.

        Deletes all existing rows for the account, then inserts the fresh list.
        This ensures positions that closed since the last sync are removed.
        The caller's session is flushed but not committed.
        """
        synced_at = datetime.now(timezone.utc)

        # Delete the current snapshot for this account
        self._session.execute(
            delete(MT5OpenPositionModel).where(MT5OpenPositionModel.account_id == account_id)
        )

        # Insert new rows
        for pos in raw_positions:
            row = MT5OpenPositionModel(
                account_id=account_id,
                ticket=pos["ticket"],
                symbol=pos["symbol"],
                direction=pos["direction"],
                lot_size=pos["lot_size"],
                entry_price=pos["entry_price"],
                current_price=pos.get("current_price"),
                stop_loss=pos.get("stop_loss"),
                take_profit=pos.get("take_profit"),
                floating_pnl=pos.get("floating_pnl"),
                opened_at=pos.get("opened_at"),
                magic=pos.get("magic"),
                comment=pos.get("comment") or "",
                source="mt5",
                synced_at=synced_at,
            )
            self._session.add(row)

        self._session.flush()
        logger.info(
            "Refreshed %d open position(s) for account=%s",
            len(raw_positions), account_id,
        )

    def get_open_positions(self, account_id: str) -> List[MT5OpenPositionModel]:
        """Return all current open positions for an account, ordered by opened_at."""
        stmt = (
            select(MT5OpenPositionModel)
            .where(MT5OpenPositionModel.account_id == account_id)
            .order_by(MT5OpenPositionModel.opened_at.asc())
        )
        return list(self._session.execute(stmt).scalars().all())


# ── Password loader helper ─────────────────────────────────────────────────────

def load_mt5_password(account_id: str) -> Optional[str]:
    """
    Load the MT5 password for an account from the environment.

    Convention: MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD
    Example: account "ftmo-p1" → env var "MT5_FTMO_P1_PASSWORD"
    """
    env_key = f"MT5_{account_id.upper().replace('-', '_').replace(' ', '_')}_PASSWORD"
    return os.environ.get(env_key)
