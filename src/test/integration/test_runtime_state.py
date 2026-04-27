"""
Integration tests for the runtime_state persistence layer (R5).

Tests:
  1. Service-layer CRUD (get/set/delete) on RuntimeStateModel
  2. FTMO dedup state: persists across simulated restart (new TelegramNotifier instance)
  3. Scheduler cooldown state: persists across simulated restart (clear in-memory dict)

All DB operations use SQLite in-memory — no real Postgres needed.
Telegram/MT5 calls are patched so no network I/O happens.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.main.python.models.db_models import Base, RuntimeStateModel
from src.main.python.services import runtime_state as rs


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    sess = SessionLocal()
    yield sess
    sess.rollback()
    sess.close()


def _make_session_factory(engine):
    """Return a context-manager get_session() that uses the given engine."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    @contextmanager
    def _get_session() -> Generator[Session, None, None]:
        sess = SessionLocal()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    return _get_session


# ── Service-layer tests ───────────────────────────────────────────────────────

class TestRuntimeStateService:

    def test_get_missing_returns_none(self, session):
        result = rs.get_state(session, "acct1", "ftmo_last_status")
        assert result is None

    def test_set_creates_row(self, session):
        rs.set_state(session, "acct1", "ftmo_last_status", "SAFE")
        session.flush()
        result = rs.get_state(session, "acct1", "ftmo_last_status")
        assert result == "SAFE"

    def test_set_updates_existing_row(self, session):
        rs.set_state(session, "acct1", "ftmo_last_status", "SAFE")
        session.flush()
        rs.set_state(session, "acct1", "ftmo_last_status", "AT_RISK")
        session.flush()
        result = rs.get_state(session, "acct1", "ftmo_last_status")
        assert result == "AT_RISK"

    def test_different_kinds_are_independent(self, session):
        rs.set_state(session, "acct1", "kind_a", "value_a")
        rs.set_state(session, "acct1", "kind_b", "value_b")
        session.flush()
        assert rs.get_state(session, "acct1", "kind_a") == "value_a"
        assert rs.get_state(session, "acct1", "kind_b") == "value_b"

    def test_different_scopes_are_independent(self, session):
        rs.set_state(session, "acct1", "kind", "v1")
        rs.set_state(session, "acct2", "kind", "v2")
        session.flush()
        assert rs.get_state(session, "acct1", "kind") == "v1"
        assert rs.get_state(session, "acct2", "kind") == "v2"

    def test_delete_removes_row(self, session):
        rs.set_state(session, "acct1", "kind", "v")
        session.flush()
        rs.delete_state(session, "acct1", "kind")
        session.flush()
        assert rs.get_state(session, "acct1", "kind") is None

    def test_delete_noop_on_missing(self, session):
        # should not raise
        rs.delete_state(session, "acct1", "nonexistent")

    def test_set_stores_dict(self, session):
        data = {"foo": 1, "bar": [1, 2, 3]}
        rs.set_state(session, "acct1", "complex", data)
        session.flush()
        assert rs.get_state(session, "acct1", "complex") == data

    def test_set_stores_none_value(self, session):
        rs.set_state(session, "acct1", "kind", None)
        session.flush()
        assert rs.get_state(session, "acct1", "kind") is None

    def test_updated_at_is_set(self, session):
        rs.set_state(session, "acct1", "kind", "v")
        session.flush()
        row = session.get(RuntimeStateModel, ("acct1", "kind"))
        assert row is not None
        assert isinstance(row.updated_at, datetime)

    def test_updated_at_changes_on_update(self, session):
        t0 = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        rs.set_state(session, "acct1", "kind", "v1")
        session.flush()
        rs.set_state(session, "acct1", "kind", "v2")
        session.flush()
        row = session.get(RuntimeStateModel, ("acct1", "kind"))
        assert row.updated_at >= t0


# ── FTMO dedup persistence tests ──────────────────────────────────────────────

class TestFTMODedup:
    """
    Simulate a backend restart by creating a new TelegramNotifier instance.
    The new instance must load FTMO status from DB and not re-fire an alert
    if the status hasn't changed.
    """

    def test_ftmo_status_persists_across_restart(self, engine):
        from src.main.python.services.telegram_notifier import TelegramNotifier

        get_session_fn = _make_session_factory(engine)

        # ── "Before restart": first notifier sets FTMO status to SAFE
        with patch(
            "src.main.python.services.telegram_notifier.get_session",
            side_effect=get_session_fn,
        ), patch.object(TelegramNotifier, "send", return_value=True):
            notifier1 = TelegramNotifier()
            status_data = {"account_status": "SAFE", "daily_loss_used_pct": 1.0,
                           "daily_loss_limit_pct": 5.0, "daily_loss_remaining": 200.0,
                           "current_max_drawdown_pct": 2.0, "max_loss_limit_pct": 10.0,
                           "max_loss_remaining": 800.0}
            sent, prev = notifier1.check_and_notify_ftmo("acct1", "Test", status_data)
            assert sent is True    # first call — no prior state → alert sent
            assert prev is None

        # ── "After restart": new notifier instance loads from DB
        with patch(
            "src.main.python.services.telegram_notifier.get_session",
            side_effect=get_session_fn,
        ), patch.object(TelegramNotifier, "send", return_value=True) as mock_send:
            notifier2 = TelegramNotifier()
            # Same status as before restart → should NOT send
            sent2, prev2 = notifier2.check_and_notify_ftmo("acct1", "Test", status_data)
            assert sent2 is False
            assert prev2 == "SAFE"
            mock_send.assert_not_called()

    def test_ftmo_status_change_after_restart_sends_alert(self, engine):
        from src.main.python.services.telegram_notifier import TelegramNotifier

        get_session_fn = _make_session_factory(engine)

        # Before restart: set SAFE
        with patch(
            "src.main.python.services.telegram_notifier.get_session",
            side_effect=get_session_fn,
        ), patch.object(TelegramNotifier, "send", return_value=True):
            notifier1 = TelegramNotifier()
            safe_data = {"account_status": "SAFE", "daily_loss_used_pct": 1.0,
                         "daily_loss_limit_pct": 5.0, "daily_loss_remaining": 200.0,
                         "current_max_drawdown_pct": 2.0, "max_loss_limit_pct": 10.0,
                         "max_loss_remaining": 800.0}
            notifier1.check_and_notify_ftmo("acct1", "Test", safe_data)

        # After restart: status changed to AT_RISK → should fire
        with patch(
            "src.main.python.services.telegram_notifier.get_session",
            side_effect=get_session_fn,
        ), patch.object(TelegramNotifier, "send", return_value=True) as mock_send:
            notifier2 = TelegramNotifier()
            at_risk_data = {"account_status": "AT_RISK", "daily_loss_used_pct": 4.5,
                            "daily_loss_limit_pct": 5.0, "daily_loss_remaining": 25.0,
                            "current_max_drawdown_pct": 3.0, "max_loss_limit_pct": 10.0,
                            "max_loss_remaining": 700.0}
            sent2, prev2 = notifier2.check_and_notify_ftmo("acct1", "Test", at_risk_data)
            assert sent2 is True
            assert prev2 == "SAFE"
            mock_send.assert_called_once()

    def test_no_db_state_treats_as_first_call(self, engine):
        """No prior DB row → behaves as if first call (fires alert)."""
        from src.main.python.services.telegram_notifier import TelegramNotifier

        get_session_fn = _make_session_factory(engine)

        with patch(
            "src.main.python.services.telegram_notifier.get_session",
            side_effect=get_session_fn,
        ), patch.object(TelegramNotifier, "send", return_value=True) as mock_send:
            notifier = TelegramNotifier()
            status_data = {"account_status": "SAFE", "daily_loss_used_pct": 1.0,
                           "daily_loss_limit_pct": 5.0, "daily_loss_remaining": 200.0,
                           "current_max_drawdown_pct": 2.0, "max_loss_limit_pct": 10.0,
                           "max_loss_remaining": 800.0}
            sent, prev = notifier.check_and_notify_ftmo("acct2", "Test", status_data)
            assert sent is True
            assert prev is None


# ── Scheduler cooldown persistence tests ─────────────────────────────────────

class TestSchedulerCooldown:
    """
    Simulate a backend restart by clearing the in-memory _error_suppress_until dict
    and _cooldown_loaded set, then verifying that the cooldown is restored from DB.
    """

    def test_cooldown_persists_across_restart(self, engine):
        import src.main.python.services.mt5_scheduler as sched

        get_session_fn = _make_session_factory(engine)

        # ── "Before restart": record a cooldown in DB directly
        with get_session_fn() as session:
            future = datetime.now(timezone.utc) + timedelta(hours=3)
            rs.set_state(session, "acct1", "scheduler_error_cooldown", future.isoformat())

        # ── "After restart": clear in-memory state, then verify lazy-load restores it
        sched._error_suppress_until.pop("acct1", None)
        sched._cooldown_loaded.discard("acct1")

        with patch(
            "src.main.python.services.mt5_scheduler.get_session",
            side_effect=get_session_fn,
        ):
            sched._load_error_cooldown_db("acct1")

        assert "acct1" in sched._error_suppress_until
        restored = sched._error_suppress_until["acct1"]
        assert restored > datetime.now(timezone.utc)

    def test_expired_cooldown_not_restored(self, engine):
        import src.main.python.services.mt5_scheduler as sched

        get_session_fn = _make_session_factory(engine)

        # Store an already-expired suppress_until
        with get_session_fn() as session:
            past = datetime.now(timezone.utc) - timedelta(hours=1)
            rs.set_state(session, "acct2", "scheduler_error_cooldown", past.isoformat())

        sched._error_suppress_until.pop("acct2", None)
        sched._cooldown_loaded.discard("acct2")

        with patch(
            "src.main.python.services.mt5_scheduler.get_session",
            side_effect=get_session_fn,
        ):
            sched._load_error_cooldown_db("acct2")

        # Expired cooldown must not be restored (alert should fire next time)
        assert "acct2" not in sched._error_suppress_until

    def test_no_db_cooldown_leaves_dict_empty(self, engine):
        import src.main.python.services.mt5_scheduler as sched

        get_session_fn = _make_session_factory(engine)

        sched._error_suppress_until.pop("acct3", None)
        sched._cooldown_loaded.discard("acct3")

        with patch(
            "src.main.python.services.mt5_scheduler.get_session",
            side_effect=get_session_fn,
        ):
            sched._load_error_cooldown_db("acct3")

        assert "acct3" not in sched._error_suppress_until

    def test_cooldown_written_to_db_on_error(self, engine):
        import src.main.python.services.mt5_scheduler as sched

        get_session_fn = _make_session_factory(engine)

        sched._error_suppress_until.pop("acct4", None)
        sched._cooldown_loaded.discard("acct4")

        fake_result = MagicMock()
        fake_result.status = "error"
        fake_result.error_message = "broker offline"
        fake_result.started_at = datetime.now(timezone.utc)

        with patch(
            "src.main.python.services.mt5_scheduler.get_session",
            side_effect=get_session_fn,
        ), patch(
            "src.main.python.services.mt5_scheduler.get_notifier"
        ) as mock_get_notifier:
            mock_get_notifier.return_value.notify_mt5_sync_result.return_value = True
            sched._maybe_notify_error("acct4", fake_result)

        # In-memory cooldown set
        assert "acct4" in sched._error_suppress_until

        # Also written to DB
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        with SessionLocal() as sess:
            value = rs.get_state(sess, "acct4", "scheduler_error_cooldown")
        assert value is not None
        stored_dt = datetime.fromisoformat(value)
        assert stored_dt > datetime.now(timezone.utc)

    def test_cooldown_cleared_from_db_on_success(self, engine):
        import src.main.python.services.mt5_scheduler as sched

        get_session_fn = _make_session_factory(engine)

        # Pre-populate a cooldown in DB
        with get_session_fn() as session:
            future = datetime.now(timezone.utc) + timedelta(hours=2)
            rs.set_state(session, "acct5", "scheduler_error_cooldown", future.isoformat())

        sched._error_suppress_until["acct5"] = future

        with patch(
            "src.main.python.services.mt5_scheduler.get_session",
            side_effect=get_session_fn,
        ):
            sched._clear_error_cooldown_db("acct5")

        # DB row should be gone
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        with SessionLocal() as sess:
            value = rs.get_state(sess, "acct5", "scheduler_error_cooldown")
        assert value is None

    def test_no_secrets_in_runtime_state(self, engine):
        """Verify that runtime_state rows never contain MT5 passwords or tokens."""
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        with SessionLocal() as sess:
            rows = sess.query(RuntimeStateModel).all()

        password_keywords = ["password", "token", "secret", "key"]
        for row in rows:
            for kw in password_keywords:
                assert kw.lower() not in row.kind.lower(), (
                    f"runtime_state kind '{row.kind}' looks like it might store a secret"
                )
                assert kw.lower() not in row.value_json.lower(), (
                    f"runtime_state value for kind '{row.kind}' may contain a secret"
                )
