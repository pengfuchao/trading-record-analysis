"""
MT5PollingScheduler — APScheduler-based background polling for MT5 sync.

One APScheduler IntervalJob per enabled account.  Jobs are created at startup
by scanning all MT5SyncConfigModel rows that have enabled=True, and are
updated in-place whenever the config changes via reload_account().

Overlap protection: a module-level set (_running) tracks account_ids that are
currently mid-sync. If the scheduler fires a job while a previous run for the
same account has not finished, the new invocation is skipped silently.

Telegram notifications fire only on error (never on scheduled success) to avoid
noise.  Manual syncs retain their original notification behaviour.

Usage:
    scheduler = MT5PollingScheduler()
    scheduler.start()        # called from FastAPI lifespan
    scheduler.stop()         # called on app shutdown
    scheduler.reload_account(account_id)   # call after config PATCH
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Set

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from src.main.python.models.db_models import MT5SyncConfigModel
from src.main.python.services.database import get_session
from src.main.python.services.mt5_connector import MT5ConnectionConfig
from src.main.python.services.mt5_sync_service import MT5SyncService, load_mt5_password
from src.main.python.services.telegram_notifier import get_notifier

logger = logging.getLogger(__name__)

# Accounts currently mid-sync (overlap guard)
_running: Set[str] = set()
_running_lock = threading.Lock()


def _poll_account(account_id: str, lookback_days: int = 7) -> None:
    """
    Background job target.  Opens its own DB session; commits independently of
    any HTTP request lifecycle.

    - Skips if another run for this account is already in progress.
    - Skips if config no longer exists or is disabled.
    - Notifies Telegram only on error.
    """
    with _running_lock:
        if account_id in _running:
            logger.debug("Scheduled poll skipped — account=%s already syncing", account_id)
            return
        _running.add(account_id)

    try:
        with get_session() as session:
            cfg = session.get(MT5SyncConfigModel, account_id)
            if cfg is None or not cfg.enabled:
                logger.debug(
                    "Scheduled poll skipped — account=%s config missing or disabled", account_id
                )
                return

            password = load_mt5_password(account_id)
            if not password:
                logger.warning(
                    "Scheduled poll skipped — no MT5 password env var for account=%s", account_id
                )
                return

            conn_config = MT5ConnectionConfig(
                login=cfg.mt5_login,
                password=password,
                server=cfg.mt5_server,
                terminal_path=cfg.terminal_path,
                broker_utc_offset=cfg.broker_utc_offset,
            )

            now = datetime.utcnow()
            svc = MT5SyncService(session)
            result = svc.sync_account(
                account_id=account_id,
                config=conn_config,
                from_date=now - timedelta(days=lookback_days),
                to_date=now,
                triggered_by="scheduled",
            )

        # Notify only on error — success notifications would be too noisy for scheduled runs
        if result.status == "error":
            try:
                get_notifier().notify_mt5_sync_result(account_id, result)
            except Exception:
                pass

        logger.info(
            "Scheduled poll done account=%s status=%s new=%d updated=%d",
            account_id, result.status, result.trades_new, result.trades_updated,
        )

    except Exception as exc:
        logger.error(
            "Scheduled poll crashed account=%s error=%s", account_id, exc, exc_info=True
        )
    finally:
        with _running_lock:
            _running.discard(account_id)


class MT5PollingScheduler:
    """
    Manages one APScheduler IntervalJob per enabled MT5 account.

    Start/stop is driven by FastAPI's lifespan context manager in app.py.
    The scheduler is non-blocking (BackgroundScheduler runs in a daemon thread).
    """

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 60, "coalesce": True},
            timezone="UTC",
        )

    def start(self) -> None:
        """Start the scheduler and register jobs for all enabled accounts."""
        self._scheduler.start()
        logger.info("MT5PollingScheduler started")
        self._load_all_accounts()

    def stop(self) -> None:
        """Gracefully shut down the scheduler (waits for running jobs to finish)."""
        self._scheduler.shutdown(wait=True)
        logger.info("MT5PollingScheduler stopped")

    # ── Job management ─────────────────────────────────────────────────────────

    def reload_account(self, account_id: str) -> None:
        """
        Re-read the config for one account and update its job accordingly.
        Call this from the upsert_mt5_config route after saving new settings.
        """
        with get_session() as session:
            cfg = session.get(MT5SyncConfigModel, account_id)

        if cfg is None or not cfg.enabled:
            self._remove_job(account_id)
            return

        self._upsert_job(account_id, cfg.polling_interval_minutes)

    def _load_all_accounts(self) -> None:
        """Scan DB for enabled configs and register one job each."""
        try:
            with get_session() as session:
                configs = (
                    session.query(MT5SyncConfigModel)
                    .filter(MT5SyncConfigModel.enabled.is_(True))
                    .all()
                )
            for cfg in configs:
                self._upsert_job(cfg.account_id, cfg.polling_interval_minutes)
            logger.info("Scheduled %d MT5 polling job(s)", len(configs))
        except Exception as exc:
            # Don't prevent app startup if DB is unavailable at boot
            logger.warning("Could not load MT5 polling configs at startup: %s", exc)

    def _upsert_job(self, account_id: str, interval_minutes: int) -> None:
        """Add or replace the IntervalJob for this account."""
        job_id = f"mt5_poll_{account_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.reschedule_job(
                job_id,
                trigger=IntervalTrigger(minutes=interval_minutes),
            )
            logger.info(
                "Rescheduled MT5 poll job account=%s interval=%dm", account_id, interval_minutes
            )
        else:
            self._scheduler.add_job(
                _poll_account,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id=job_id,
                name=f"MT5 poll — {account_id}",
                kwargs={"account_id": account_id},
                replace_existing=True,
            )
            logger.info(
                "Registered MT5 poll job account=%s interval=%dm", account_id, interval_minutes
            )

    def _remove_job(self, account_id: str) -> None:
        job_id = f"mt5_poll_{account_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            logger.info("Removed MT5 poll job account=%s", account_id)


# Module-level singleton — imported by app.py lifespan and by the config route
_scheduler: Optional[MT5PollingScheduler] = None


def get_scheduler() -> MT5PollingScheduler:
    """Return the singleton scheduler (created on first call)."""
    global _scheduler
    if _scheduler is None:
        _scheduler = MT5PollingScheduler()
    return _scheduler
