"""
Service-level tests for MT5SyncService.

Strategy:
  - SQLite in-memory for all DB interactions (same pattern as test_repositories.py)
  - MT5Connector is stubbed via unittest.mock.patch — the real mt5.* package is never called
  - Tests verify orchestration logic, result fields, DB state, and error handling

NOT tested here:
  - mt5.* native calls (Windows-only, can't be called in CI)
  - MT5Connector internal reconnect logic
  - MT5PollingScheduler scheduling intervals
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.main.python.models.db_models import (
    Base, MT5OpenPositionModel, MT5SyncRunModel,
)
from src.main.python.services.mt5_connector import MT5ConnectionConfig, MT5ConnectionError
from src.main.python.services.mt5_sync_service import MT5SyncService, SyncResult, load_mt5_password


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    sess = SessionLocal()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture()
def config():
    return MT5ConnectionConfig(
        login=12345,
        password="test_password",
        server="test-server",
        broker_utc_offset=2,
    )


# ── Sample position data (what MT5Connector would return) ──────────────────────

def _make_position(
    position_id: int = 100001,
    symbol: str = "EURUSD",
    raw_type: str = "buy",
    gross_profit: float = 120.0,
    commission: float = -2.0,
    swap: float = 0.0,
    entry_price: float = 1.0800,
    exit_price: float = 1.0900,
    sl: float = 1.0750,
    tp: float = 1.0950,
    volume: float = 0.10,
    entry_time: datetime = None,
    exit_time: datetime = None,
) -> Dict[str, Any]:
    return {
        "position_id": position_id,
        "symbol": symbol,
        "raw_type": raw_type,
        "gross_profit": gross_profit,
        "commission": commission,
        "swap": swap,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "sl": sl,
        "tp": tp,
        "volume": volume,
        "entry_time": entry_time or datetime(2026, 1, 15, 9, 0),
        "exit_time": exit_time or datetime(2026, 1, 15, 11, 0),
        "magic": 0,
        "comment": "",
    }


def _make_open_position(ticket: int = 200001) -> Dict[str, Any]:
    return {
        "ticket": ticket,
        "symbol": "XAUUSD",
        "direction": "LONG",
        "lot_size": 0.05,
        "entry_price": 1900.0,
        "current_price": 1905.0,
        "stop_loss": 1890.0,
        "take_profit": 1920.0,
        "floating_pnl": 25.0,
        "opened_at": datetime(2026, 1, 15, 10, 0),
        "magic": 0,
        "comment": "",
    }


# ── Context manager to patch MT5Connector ─────────────────────────────────────

@contextmanager
def _stub_connector(positions=None, open_positions=None, raise_on_enter=None):
    """
    Replace MT5Connector with a MagicMock context manager.
    - positions: list returned by conn.reconstruct_positions(deals)
    - open_positions: list returned by conn.fetch_open_positions()
    - raise_on_enter: if set, __enter__ raises this exception
    """
    mock_conn = MagicMock()

    if raise_on_enter is not None:
        mock_conn.__enter__ = MagicMock(side_effect=raise_on_enter)
    else:
        conn_instance = MagicMock()
        conn_instance.fetch_deals.return_value = []
        conn_instance.reconstruct_positions.return_value = positions or []
        conn_instance.fetch_open_positions.return_value = open_positions or []
        mock_conn.__enter__ = MagicMock(return_value=conn_instance)
        mock_conn.__exit__ = MagicMock(return_value=False)

    with patch("src.main.python.services.mt5_sync_service.MT5Connector", return_value=mock_conn):
        yield mock_conn


# ── sync_account — success path ───────────────────────────────────────────────

class TestSyncAccountSuccess:
    def test_returns_sync_result(self, session, config):
        with _stub_connector(positions=[_make_position()]):
            svc = MT5SyncService(session)
            result = svc.sync_account(
                "ACC1", config,
                from_date=datetime(2026, 1, 1),
                to_date=datetime(2026, 1, 31),
            )
        assert isinstance(result, SyncResult)

    def test_status_is_success(self, session, config):
        with _stub_connector(positions=[_make_position()]):
            svc = MT5SyncService(session)
            result = svc.sync_account("ACC1", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        assert result.status == "success"

    def test_positions_built_count(self, session, config):
        positions = [_make_position(100001), _make_position(100002, gross_profit=-50.0)]
        with _stub_connector(positions=positions):
            svc = MT5SyncService(session)
            result = svc.sync_account("ACC2", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        assert result.positions_built == 2

    def test_run_row_written_to_db(self, session, config):
        with _stub_connector(positions=[]):
            svc = MT5SyncService(session)
            result = svc.sync_account("ACC3", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        row = session.execute(
            select(MT5SyncRunModel).where(MT5SyncRunModel.run_id == result.run_id)
        ).scalar_one_or_none()
        assert row is not None
        assert row.status == "success"

    def test_run_row_completed_at_is_set(self, session, config):
        with _stub_connector(positions=[]):
            svc = MT5SyncService(session)
            result = svc.sync_account("ACC4", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        row = session.execute(
            select(MT5SyncRunModel).where(MT5SyncRunModel.run_id == result.run_id)
        ).scalar_one_or_none()
        assert row.completed_at is not None

    def test_triggered_by_stored_in_run_row(self, session, config):
        with _stub_connector(positions=[]):
            svc = MT5SyncService(session)
            result = svc.sync_account("ACC5", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31),
                                      triggered_by="scheduler")
        row = session.execute(
            select(MT5SyncRunModel).where(MT5SyncRunModel.run_id == result.run_id)
        ).scalar_one_or_none()
        assert row.triggered_by == "scheduler"

    def test_open_positions_refreshed(self, session, config):
        open_pos = [_make_open_position(200001), _make_open_position(200002)]
        with _stub_connector(positions=[], open_positions=open_pos):
            svc = MT5SyncService(session)
            result = svc.sync_account("ACC6", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        assert result.status == "success"
        assert result.open_positions_count == 2
        stored = svc.get_open_positions("ACC6")
        assert len(stored) == 2

    def test_result_error_message_is_none_on_success(self, session, config):
        with _stub_connector(positions=[]):
            svc = MT5SyncService(session)
            result = svc.sync_account("ACC7", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        assert result.error_message is None


# ── sync_account — error path ─────────────────────────────────────────────────

class TestSyncAccountError:
    def test_mt5_connection_error_returns_error_status(self, session, config):
        exc = MT5ConnectionError("Terminal not available")
        with _stub_connector(raise_on_enter=exc):
            svc = MT5SyncService(session)
            result = svc.sync_account("ERR1", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        assert result.status == "error"

    def test_error_message_captured(self, session, config):
        exc = MT5ConnectionError("Login rejected")
        with _stub_connector(raise_on_enter=exc):
            svc = MT5SyncService(session)
            result = svc.sync_account("ERR2", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        assert "Login rejected" in (result.error_message or "")

    def test_generic_exception_returns_error_status(self, session, config):
        with _stub_connector(raise_on_enter=RuntimeError("unexpected crash")):
            svc = MT5SyncService(session)
            result = svc.sync_account("ERR3", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        assert result.status == "error"

    def test_run_row_written_on_error(self, session, config):
        exc = MT5ConnectionError("fail")
        with _stub_connector(raise_on_enter=exc):
            svc = MT5SyncService(session)
            result = svc.sync_account("ERR4", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))
        row = session.execute(
            select(MT5SyncRunModel).where(MT5SyncRunModel.run_id == result.run_id)
        ).scalar_one_or_none()
        assert row is not None
        assert row.status == "error"

    def test_open_positions_failure_is_non_fatal(self, session, config):
        """
        If fetch_open_positions() raises after closed trades were synced,
        the sync result should still be 'success'.
        """
        mock_conn = MagicMock()
        conn_instance = MagicMock()
        conn_instance.fetch_deals.return_value = []
        conn_instance.reconstruct_positions.return_value = [_make_position(199999)]
        conn_instance.fetch_open_positions.side_effect = RuntimeError("positions snapshot failed")
        mock_conn.__enter__ = MagicMock(return_value=conn_instance)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("src.main.python.services.mt5_sync_service.MT5Connector", return_value=mock_conn):
            svc = MT5SyncService(session)
            result = svc.sync_account("NONFATAL", config,
                                      from_date=datetime(2026, 1, 1),
                                      to_date=datetime(2026, 1, 31))

        assert result.status == "success"


# ── _normalize_positions ──────────────────────────────────────────────────────

class TestNormalizePositions:
    def _make_service(self, session) -> MT5SyncService:
        return MT5SyncService(session)

    def test_buy_position_has_long_direction(self, session, config):
        svc = self._make_service(session)
        pos = _make_position(raw_type="buy")
        trades = svc._normalize_positions("ACC", "run1", [pos], config)
        assert len(trades) == 1
        from src.main.python.models.enums import Direction
        assert trades[0].direction == Direction.LONG

    def test_sell_position_has_short_direction(self, session, config):
        svc = self._make_service(session)
        pos = _make_position(raw_type="sell", gross_profit=-60.0)
        trades = svc._normalize_positions("ACC", "run1", [pos], config)
        from src.main.python.models.enums import Direction
        assert trades[0].direction == Direction.SHORT

    def test_net_pnl_deducts_commission_and_swap(self, session, config):
        svc = self._make_service(session)
        pos = _make_position(gross_profit=100.0, commission=-5.0, swap=-1.5)
        trades = svc._normalize_positions("ACC", "run1", [pos], config)
        assert trades[0].net_pnl == pytest.approx(100.0 - 5.0 - 1.5)

    def test_win_result_for_positive_net_pnl(self, session, config):
        svc = self._make_service(session)
        pos = _make_position(gross_profit=100.0, commission=0.0, swap=0.0)
        trades = svc._normalize_positions("ACC", "run1", [pos], config)
        from src.main.python.models.enums import TradeResult
        assert trades[0].result == TradeResult.WIN

    def test_loss_result_for_negative_net_pnl(self, session, config):
        svc = self._make_service(session)
        pos = _make_position(gross_profit=-80.0, commission=0.0, swap=0.0)
        trades = svc._normalize_positions("ACC", "run1", [pos], config)
        from src.main.python.models.enums import TradeResult
        assert trades[0].result == TradeResult.LOSS

    def test_symbol_and_account_id_assigned(self, session, config):
        svc = self._make_service(session)
        pos = _make_position(symbol="XAUUSD")
        trades = svc._normalize_positions("MYACCOUNT", "run1", [pos], config)
        assert trades[0].symbol == "XAUUSD"
        assert trades[0].account_id == "MYACCOUNT"

    def test_empty_positions_returns_empty_list(self, session, config):
        svc = self._make_service(session)
        trades = svc._normalize_positions("ACC", "run1", [], config)
        assert trades == []


# ── _refresh_open_positions ───────────────────────────────────────────────────

class TestRefreshOpenPositions:
    def test_inserts_new_positions(self, session):
        svc = MT5SyncService(session)
        svc._refresh_open_positions("REFACC", [_make_open_position(300001)])
        rows = svc.get_open_positions("REFACC")
        assert len(rows) == 1
        assert rows[0].ticket == 300001

    def test_replaces_old_positions(self, session):
        svc = MT5SyncService(session)
        svc._refresh_open_positions("REFACC2", [_make_open_position(400001)])
        # Replace with different set
        svc._refresh_open_positions("REFACC2", [_make_open_position(400002), _make_open_position(400003)])
        rows = svc.get_open_positions("REFACC2")
        tickets = {r.ticket for r in rows}
        assert tickets == {400002, 400003}

    def test_empty_clears_all_positions(self, session):
        svc = MT5SyncService(session)
        svc._refresh_open_positions("REFACC3", [_make_open_position(500001)])
        svc._refresh_open_positions("REFACC3", [])
        rows = svc.get_open_positions("REFACC3")
        assert rows == []

    def test_positions_scoped_to_account(self, session):
        svc = MT5SyncService(session)
        svc._refresh_open_positions("AACC", [_make_open_position(600001)])
        svc._refresh_open_positions("BACC", [_make_open_position(600002)])
        a_rows = svc.get_open_positions("AACC")
        b_rows = svc.get_open_positions("BACC")
        assert len(a_rows) == 1
        assert len(b_rows) == 1
        assert a_rows[0].ticket == 600001
        assert b_rows[0].ticket == 600002


# ── load_mt5_password ─────────────────────────────────────────────────────────

class TestLoadMT5Password:
    def test_returns_password_from_env(self, monkeypatch):
        monkeypatch.setenv("MT5_MYACCOUNT_PASSWORD", "secret123")
        result = load_mt5_password("MYACCOUNT")
        assert result == "secret123"

    def test_account_id_hyphen_becomes_underscore(self, monkeypatch):
        monkeypatch.setenv("MT5_FTMO_P1_PASSWORD", "pw456")
        result = load_mt5_password("ftmo-p1")
        assert result == "pw456"

    def test_account_id_space_becomes_underscore(self, monkeypatch):
        monkeypatch.setenv("MT5_MY_ACCOUNT_PASSWORD", "pw789")
        result = load_mt5_password("my account")
        assert result == "pw789"

    def test_returns_none_when_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("MT5_DOESNOTEXIST_PASSWORD", raising=False)
        result = load_mt5_password("doesnotexist")
        assert result is None
