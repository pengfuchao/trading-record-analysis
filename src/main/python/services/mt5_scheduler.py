"""
MT5PollingScheduler — APScheduler-based background polling for MT5 sync.

One APScheduler IntervalJob per enabled account.  Jobs are created at startup
by scanning all MT5SyncConfigModel rows that have enabled=True, and are
updated in-place whenever the config changes via reload_account().

Overlap protection: a module-level set (_running) tracks account_ids that are
currently mid-sync. If the scheduler fires a job while a previous run for the
same account has not finished, the new invocation is skipped silently.

Alert cooldown: repeated scheduled failures are suppressed after the first
alert for _ERROR_COOLDOWN_HOURS hours to avoid Telegram spam. The cooldown
resets automatically when a sync succeeds.

Polling jitter: each newly registered job starts after a random delay of up to
_JITTER_MAX_SECONDS so multiple accounts do not all fire in lockstep at startup.

Single-worker assumption: the overlap guard (_running set) is in-memory and
only works correctly when the process runs with a single worker. Use
--workers 1 with uvicorn (already set in docker-entrypoint.sh).

Usage:
    scheduler = MT5PollingScheduler()
    scheduler.start()        # called from FastAPI lifespan
    scheduler.stop()         # called on app shutdown
    scheduler.reload_account(account_id)   # call after config PATCH
"""
from __future__ import annotations

import logging
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Set

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.main.python.models.db_models import MT5SyncConfigModel
from src.main.python.services.database import get_session
from src.main.python.services.mt5_connector import MT5ConnectionConfig
from src.main.python.services.mt5_sync_service import MT5SyncService, load_mt5_password
from src.main.python.services.telegram_notifier import get_notifier
import src.main.python.services.runtime_state as _rs

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────

# Accounts currently mid-sync (overlap guard — in-process only, single-worker).
# Intentionally NOT persisted: after a restart any mid-sync is dead.
_running: Set[str] = set()
_running_lock = threading.Lock()

# Per-account timestamp after which the next error alert is allowed.
# Cleared on success so the next failure always triggers a fresh alert.
# Persisted to runtime_state so cooldown survives backend restarts.
_error_suppress_until: dict[str, datetime] = {}

# Tracks which accounts have had their cooldown state loaded from DB.
# Prevents repeated DB reads for the same account within one process lifetime.
_cooldown_loaded: Set[str] = set()

# Repeated failures for the same account are silenced after the first alert
# until this many hours have elapsed (resets on success).
_ERROR_COOLDOWN_HOURS = 4

# Maximum random start-delay (seconds) added when registering a new job,
# so accounts registered at the same time don't all fire in lockstep.
_JITTER_MAX_SECONDS = 30

_KIND_COOLDOWN = "scheduler_error_cooldown"


# ── Sync-lock helpers (shared by scheduled and manual syncs) ──────────────────
#
# The MT5 Python package uses process-level global state: mt5.initialize(),
# mt5.login(), and mt5.shutdown() are not safe to call concurrently from two
# threads for the same account.  Both scheduled and manual syncs must acquire
# this lock before opening an MT5Connector context.

def acquire_sync_lock(account_id: str) -> bool:
    """
    Try to mark account_id as in-progress.

    Returns True if the lock was acquired (caller may proceed).
    Returns False if a sync for this account is already running (caller must abort).
    Thread-safe.
    """
    with _running_lock:
        if account_id in _running:
            return False
        _running.add(account_id)
        return True


def release_sync_lock(account_id: str) -> None:
    """Release the sync lock for account_id. Safe to call even if not held."""
    with _running_lock:
        _running.discard(account_id)


def _poll_account(account_id: str, lookback_days: int = 7) -> None:
    """
    Background job target.  Opens its own DB session; commits independently of
    any HTTP request lifecycle.

    - Skips if another run for this account is already in progress.
    - Skips if config no longer exists or is disabled.
    - Notifies Telegram on error, but suppresses repeated alerts within
      _ERROR_COOLDOWN_HOURS to prevent Telegram spam during outages.
    - Clears the error cooldown on success so the next failure sends a fresh alert.
    """
    if not acquire_sync_lock(account_id):
        logger.debug("Scheduled poll skipped — account=%s already syncing", account_id)
        return

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

            now = datetime.now(timezone.utc)
            svc = MT5SyncService(session)
            result = svc.sync_account(
                account_id=account_id,
                config=conn_config,
                from_date=now - timedelta(days=lookback_days),
                to_date=now,
                triggered_by="scheduled",
            )

        if result.status == "error":
            _maybe_notify_error(account_id, result)
        else:
            # Successful sync — clear error cooldown so the next failure sends a fresh alert
            _error_suppress_until.pop(account_id, None)
            _clear_error_cooldown_db(account_id)

        logger.info(
            "Scheduled poll done account=%s status=%s new=%d updated=%d",
            account_id, result.status, result.trades_new, result.trades_updated,
        )

    except Exception as exc:
        logger.error(
            "Scheduled poll crashed account=%s error=%s", account_id, exc, exc_info=True
        )
    finally:
        release_sync_lock(account_id)


def _load_error_cooldown_db(account_id: str) -> None:
    """
    One-time load of persisted cooldown state from DB into _error_suppress_until.
    Safe to call even if the DB is unavailable — logs and continues silently.
    Marks account as loaded so we only hit the DB once per process lifetime.
    """
    _cooldown_loaded.add(account_id)
    try:
        with get_session() as session:
            saved = _rs.get_state(session, account_id, _KIND_COOLDOWN)
        if saved is not None:
            suppress_until = datetime.fromisoformat(saved)
            now = datetime.now(timezone.utc)
            if suppress_until > now:
                _error_suppress_until[account_id] = suppress_until
                logger.debug(
                    "Cooldown state restored from DB account=%s until=%s",
                    account_id,
                    suppress_until.strftime("%Y-%m-%d %H:%M UTC"),
                )
    except Exception as exc:
        logger.debug("Could not load cooldown state for %s from DB: %s", account_id, exc)


def _clear_error_cooldown_db(account_id: str) -> None:
    """Delete persisted cooldown state from DB (called on successful sync)."""
    try:
        with get_session() as session:
            _rs.delete_state(session, account_id, _KIND_COOLDOWN)
    except Exception as exc:
        logger.debug("Could not clear cooldown state for %s in DB: %s", account_id, exc)


def _maybe_notify_error(account_id: str, result) -> None:
    """
    Send a Telegram failure alert unless one was already sent within the cooldown window.

    The cooldown prevents Telegram spam when MT5 is down for an extended period
    (e.g., broker maintenance) and the scheduler keeps firing at regular intervals.
    Cooldown state is persisted to DB so it survives backend restarts.
    """
    # Lazy-load persisted cooldown from DB on first call for this account
    if account_id not in _cooldown_loaded:
        _load_error_cooldown_db(account_id)

    now = datetime.now(timezone.utc)
    suppress_until = _error_suppress_until.get(account_id)

    if suppress_until is not None and now < suppress_until:
        logger.debug(
            "Scheduled poll error alert suppressed (cooldown) account=%s until=%s",
            account_id,
            suppress_until.strftime("%Y-%m-%d %H:%M UTC"),
        )
        return

    try:
        get_notifier().notify_mt5_sync_result(account_id, result)
    except Exception:
        pass

    new_suppress_until = now + timedelta(hours=_ERROR_COOLDOWN_HOURS)
    _error_suppress_until[account_id] = new_suppress_until

    # Persist so the cooldown survives a backend restart
    try:
        with get_session() as session:
            _rs.set_state(session, account_id, _KIND_COOLDOWN, new_suppress_until.isoformat())
    except Exception as exc:
        logger.warning("Could not persist cooldown state for %s to DB: %s", account_id, exc)

    logger.info(
        "Scheduled poll error alert sent account=%s next_alert_after=%s",
        account_id,
        new_suppress_until.strftime("%Y-%m-%d %H:%M UTC"),
    )


class MT5PollingScheduler:
    """
    Manages one APScheduler IntervalJob per enabled MT5 account.

    Start/stop is driven by FastAPI's lifespan context manager in app.py.
    The scheduler is non-blocking (BackgroundScheduler runs in a daemon thread).

    IMPORTANT: The overlap guard (_running set) is in-memory only.
    This is safe for single-process deployments only.  Always start uvicorn
    with --workers 1 (already enforced in docker-entrypoint.sh).
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
        logger.info(
            "  MT5 overlap guard is in-process only — "
            "start uvicorn with --workers 1 (already set in docker-entrypoint.sh)"
        )
        self._load_all_accounts()

    def stop(self) -> None:
        """Gracefully shut down the scheduler (waits for running jobs to finish)."""
        self._scheduler.shutdown(wait=True)
        logger.info("MT5PollingScheduler stopped")

    # ── Job management ─────────────────────────────────────────────────────────

    def reload_account(
        self,
        account_id: str,
        enabled: Optional[bool] = None,
        interval_minutes: Optional[int] = None,
        lookback_days: Optional[int] = None,
    ) -> None:
        """
        Update the polling job for one account.

        When called from the config-save route, pass ``enabled``,
        ``interval_minutes``, and ``lookback_days`` directly from the request
        body — the route's DB session has not committed yet, so a fresh DB read
        here would see the pre-save state.

        When called without those arguments (e.g. from tests or one-off tooling),
        we fall back to reading the current committed state from the DB.
        """
        if enabled is None or interval_minutes is None or lookback_days is None:
            # Fallback: read from DB (values must already be committed)
            with get_session() as session:
                cfg = session.get(MT5SyncConfigModel, account_id)
            if cfg is None:
                self._remove_job(account_id)
                return
            enabled = cfg.enabled
            interval_minutes = cfg.polling_interval_minutes
            lookback_days = cfg.lookback_days
            logger.debug(
                "reload_account read from DB account=%s enabled=%s interval=%dm lookback=%dd",
                account_id, enabled, interval_minutes, lookback_days,
            )
        else:
            logger.debug(
                "reload_account using caller-supplied values account=%s enabled=%s "
                "interval=%dm lookback=%dd",
                account_id, enabled, interval_minutes, lookback_days,
            )

        if not enabled:
            self._remove_job(account_id)
            return

        self._upsert_job(account_id, interval_minutes, lookback_days)

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
                self._upsert_job(cfg.account_id, cfg.polling_interval_minutes, cfg.lookback_days)
            logger.info("Scheduled %d MT5 polling job(s)", len(configs))
        except Exception as exc:
            # Don't prevent app startup if DB is unavailable at boot
            logger.warning("Could not load MT5 polling configs at startup: %s", exc)

    def _upsert_job(self, account_id: str, interval_minutes: int, lookback_days: int = 7) -> None:
        """Add or replace the IntervalJob for this account."""
        job_id = f"mt5_poll_{account_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.reschedule_job(
                job_id,
                trigger=IntervalTrigger(minutes=interval_minutes),
            )
            # Also update the kwargs so the next run uses the new lookback_days
            self._scheduler.modify_job(
                job_id,
                kwargs={"account_id": account_id, "lookback_days": lookback_days},
            )
            logger.info(
                "Rescheduled MT5 poll job account=%s interval=%dm lookback_days=%d",
                account_id, interval_minutes, lookback_days,
            )
        else:
            # Stagger first-run time so multiple accounts don't fire in lockstep
            jitter_secs = random.randint(0, _JITTER_MAX_SECONDS)
            start_at = datetime.now(timezone.utc) + timedelta(seconds=jitter_secs)
            self._scheduler.add_job(
                _poll_account,
                trigger=IntervalTrigger(minutes=interval_minutes, start_date=start_at),
                id=job_id,
                name=f"MT5 poll — {account_id}",
                kwargs={"account_id": account_id, "lookback_days": lookback_days},
                replace_existing=True,
            )
            logger.info(
                "Registered MT5 poll job account=%s interval=%dm "
                "lookback_days=%d first_run_in=%ds",
                account_id, interval_minutes, lookback_days, jitter_secs,
            )

    def get_next_run_time(self, account_id: str) -> Optional[datetime]:
        """Return the next scheduled fire time for account_id, or None if not scheduled."""
        job = self._scheduler.get_job(f"mt5_poll_{account_id}")
        return job.next_run_time if job is not None else None

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
