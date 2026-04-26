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
    Base, AccountModel, MT5OpenPositionModel, MT5SyncConfigModel, MT5SyncRunModel, TradeModel,
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


# ── backfill_sl_tp ────────────────────────────────────────────────────────────

def _make_trade_row(
    trade_id: str,
    account_id: str = "BF-ACC",
    direction: str = "Long",
    entry_price: float = 1.0800,
    exit_price: float = 1.0900,
    stop_loss=None,
    take_profit=None,
) -> TradeModel:
    return TradeModel(
        trade_id=trade_id,
        account_id=account_id,
        platform="MT5",
        direction=direction,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        result="Win",
        net_pnl=100.0,
    )


@contextmanager
def _stub_backfill_connector(orders_sl_tp: dict):
    """Stub MT5Connector so fetch_orders_sl_tp returns a preset dict."""
    mock_conn = MagicMock()
    conn_instance = MagicMock()
    conn_instance.fetch_orders_sl_tp.return_value = orders_sl_tp
    mock_conn.__enter__ = MagicMock(return_value=conn_instance)
    mock_conn.__exit__ = MagicMock(return_value=False)
    with patch("src.main.python.services.mt5_sync_service.MT5Connector", return_value=mock_conn):
        yield


def _seed_account_and_trade(session, trade_id: str, account_id: str = "BF-ACC", **trade_kwargs):
    if not session.get(AccountModel, account_id):
        session.add(AccountModel(
            account_id=account_id,
            broker="Test",
            platform="MT5",
            account_currency="USD",
        ))
        session.flush()
    row = _make_trade_row(trade_id, account_id=account_id, **trade_kwargs)
    session.add(row)
    session.flush()
    return row


FROM = datetime(2024, 1, 1, tzinfo=timezone.utc)
TO = datetime(2026, 12, 31, tzinfo=timezone.utc)


class TestBackfillSLTP:
    """
    Tests for MT5SyncService.backfill_sl_tp() — each test answers a specific
    diagnostic question about why historical trades may or may not receive
    SL/TP in a backfill pass.
    """

    def test_updates_stop_loss_and_take_profit_when_order_matched(self, session, config):
        """Happy path: matching order with valid SL/TP → trade updated."""
        _seed_account_and_trade(session, "111001", stop_loss=None)
        orders_sl_tp = {111001: (1.0750, 1.0950)}

        with _stub_backfill_connector(orders_sl_tp):
            counts = MT5SyncService(session).backfill_sl_tp("BF-ACC", config, FROM, TO)

        row = session.get(TradeModel, "111001")
        assert row.stop_loss == pytest.approx(1.0750)
        assert row.take_profit == pytest.approx(1.0950)
        assert counts["updated"] == 1
        assert counts["no_order_found"] == 0
        assert counts["sl_zero"] == 0

    def test_computes_r_when_sl_found_and_prices_present(self, session, config):
        """R should be computed when SL is found and entry/exit prices are in DB."""
        _seed_account_and_trade(
            session, "111002",
            entry_price=1.0800, exit_price=1.0900, direction="Long", stop_loss=None,
        )
        # SL dist = 0.005; move = 0.01 → R = 2.0
        orders_sl_tp = {111002: (1.0750, None)}

        with _stub_backfill_connector(orders_sl_tp):
            counts = MT5SyncService(session).backfill_sl_tp("BF-ACC", config, FROM, TO)

        row = session.get(TradeModel, "111002")
        assert row.stop_loss == pytest.approx(1.0750)
        assert row.actual_r_multiple == pytest.approx(2.0)
        assert counts["r_computed"] == 1

    def test_sl_zero_counted_not_updated(self, session, config):
        """Order found but SL=0.0 on the order (broker did not set SL): trade unchanged."""
        _seed_account_and_trade(session, "111003", stop_loss=None)
        # (None, None) simulates the 0.0→None conversion in fetch_orders_sl_tp
        orders_sl_tp = {111003: (None, None)}

        with _stub_backfill_connector(orders_sl_tp):
            counts = MT5SyncService(session).backfill_sl_tp("BF-ACC", config, FROM, TO)

        row = session.get(TradeModel, "111003")
        assert row.stop_loss is None
        assert counts["sl_zero"] == 1
        assert counts["updated"] == 0

    def test_no_order_found_when_position_id_outside_window(self, session, config):
        """Position not in order history (trade outside date window): trade unchanged."""
        _seed_account_and_trade(session, "111004", stop_loss=None)
        orders_sl_tp = {}  # empty — simulates narrow window missing old trades

        with _stub_backfill_connector(orders_sl_tp):
            counts = MT5SyncService(session).backfill_sl_tp("BF-ACC", config, FROM, TO)

        row = session.get(TradeModel, "111004")
        assert row.stop_loss is None
        assert counts["no_order_found"] >= 1
        assert counts["updated"] == 0

    def test_non_integer_trade_id_safely_skipped(self, session, config):
        """CSV-imported trade with non-numeric ID does not crash backfill."""
        _seed_account_and_trade(session, "CSV-IMPORT-XYZ", stop_loss=None)
        orders_sl_tp = {}

        with _stub_backfill_connector(orders_sl_tp):
            counts = MT5SyncService(session).backfill_sl_tp("BF-ACC", config, FROM, TO)

        assert counts["no_order_found"] >= 1  # the CSV trade was skipped gracefully

    def test_trades_already_with_sl_not_included_in_query(self, session, config):
        """Trades that already have stop_loss set are excluded; they are not re-checked."""
        _seed_account_and_trade(session, "111005", stop_loss=1.0700)
        orders_sl_tp = {111005: (1.0600, 1.1000)}  # different SL

        with _stub_backfill_connector(orders_sl_tp):
            counts = MT5SyncService(session).backfill_sl_tp("BF-ACC", config, FROM, TO)

        row = session.get(TradeModel, "111005")
        assert row.stop_loss == pytest.approx(1.0700)  # unchanged

    def test_mixed_outcomes_counted_correctly(self, session, config):
        """updated / sl_zero / no_order_found counts are mutually exclusive and correct."""
        _seed_account_and_trade(session, "111006", stop_loss=None)  # valid order
        _seed_account_and_trade(session, "111007", stop_loss=None)  # sl=0 on order
        _seed_account_and_trade(session, "111008", stop_loss=None)  # no order in window
        orders_sl_tp = {
            111006: (1.0750, 1.0950),
            111007: (None, None),
            # 111008 absent
        }

        with _stub_backfill_connector(orders_sl_tp):
            counts = MT5SyncService(session).backfill_sl_tp("BF-ACC", config, FROM, TO)

        assert counts["updated"] >= 1    # at minimum 111006
        assert counts["sl_zero"] >= 1    # at minimum 111007
        assert counts["no_order_found"] >= 1  # at minimum 111008
