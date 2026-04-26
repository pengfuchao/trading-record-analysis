"""
Telegram route tests.

Covers:
  POST /api/v1/telegram/test-ping  — response shape; sent=False when notifier disabled;
                                     sent=True when notifier mocked
  POST /api/v1/telegram/webhook    — request validation (422 on bad payload);
                                     no-message / null-text early exit;
                                     chat_id guard (blocks when unset, blocks wrong id,
                                     passes matching id, always HTTP 200);
                                     command dispatch (/ping, /plan, /journal, /status,
                                     unknown) with DB interactions;
                                     exception safety (always {"ok": True})

Design decisions:
  - TelegramNotifier singleton is disabled in tests (no TELEGRAM_BOT_TOKEN /
    TELEGRAM_CHAT_ID env vars set), so send() returns False without HTTP calls.
  - Guard tests patch get_notifier() via unittest.mock.patch so we can assert
    send() was or was not called — that's the regression we're protecting.
  - TELEGRAM_CHAT_ID is controlled per-test via monkeypatch.setenv/delenv;
    the webhook reads os.environ at request time so monkeypatch works correctly.
  - App fixture includes accounts + trades routers for test-data setup helpers.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main.python.api.dependencies import get_db
from src.main.python.api.routes import accounts, trades
from src.main.python.api.routes.telegram import router as telegram_router
from src.main.python.models.db_models import Base


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(telegram_router, prefix="/api/v1")
    _app.include_router(accounts.router, prefix="/api/v1")
    _app.include_router(trades.router,   prefix="/api/v1")
    return _app


@pytest.fixture()
def client(app: FastAPI):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _update(chat_id: int, text: str, update_id: int = 1) -> dict:
    """Build a minimal _TgUpdate JSON payload."""
    return {
        "update_id": update_id,
        "message": {"message_id": 1, "chat": {"id": chat_id}, "text": text},
    }


def _mk_account(client, account_id: str = "tg-acc") -> dict:
    r = client.post("/api/v1/accounts", json={
        "account_id": account_id,
        "broker": "FTMO",
        "platform": "MT5",
        "starting_balance": 10000.0,
        "account_currency": "USD",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _mk_trade(client, account_id: str = "tg-acc", trade_id: str = "TG-T001") -> dict:
    r = client.post(f"/api/v1/accounts/{account_id}/trades", json={
        "trade_id": trade_id,
        "symbol": "EURUSD",
        "direction": "Long",
        "result": "Win",
        "net_pnl": 100.0,
        "gross_pnl": 110.0,
        "entry_price": 1.0850,
        "exit_price": 1.0950,
        "stop_loss": 1.0800,
        "lot_size": 0.1,
        "entry_datetime": "2024-01-15T09:00:00",
        "exit_datetime": "2024-01-15T11:00:00",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _mock_notifier() -> MagicMock:
    n = MagicMock()
    n.send.return_value = True
    return n


# ── Tests: POST /telegram/test-ping ──────────────────────────────────────────

class TestTelegramTestPing:
    def test_returns_200_with_correct_shape(self, client):
        r = client.post("/api/v1/telegram/test-ping")
        assert r.status_code == 200
        data = r.json()
        assert "sent" in data
        assert "message" in data

    def test_sent_false_when_notifier_not_configured(self, client):
        # No TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in test env →
        # singleton _enabled=False → send() returns False without HTTP call.
        r = client.post("/api/v1/telegram/test-ping")
        assert r.status_code == 200
        assert r.json()["sent"] is False

    def test_sent_true_and_message_when_notifier_mocked(self, client):
        notifier = _mock_notifier()
        with patch("src.main.python.api.routes.telegram.get_notifier", return_value=notifier):
            r = client.post("/api/v1/telegram/test-ping")
        assert r.status_code == 200
        data = r.json()
        assert data["sent"] is True
        assert data["message"] == "ping sent"
        notifier.send.assert_called_once()


# ── Tests: webhook request validation ────────────────────────────────────────

class TestTelegramWebhookValidation:
    def test_rejects_empty_body(self, client):
        r = client.post("/api/v1/telegram/webhook", json={})
        assert r.status_code == 422

    def test_rejects_string_update_id(self, client):
        r = client.post("/api/v1/telegram/webhook", json={"update_id": "bad"})
        assert r.status_code == 422

    def test_no_message_field_returns_ok(self, client):
        r = client.post("/api/v1/telegram/webhook", json={"update_id": 1})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_message_with_null_text_returns_ok(self, client):
        update = {"update_id": 1, "message": {"message_id": 1, "chat": {"id": 123}}}
        r = client.post("/api/v1/telegram/webhook", json=update)
        assert r.status_code == 200
        assert r.json() == {"ok": True}


# ── Tests: chat_id guard ──────────────────────────────────────────────────────

class TestTelegramChatIdGuard:
    def test_no_env_var_blocks_all_chats(self, client, monkeypatch):
        """
        When TELEGRAM_CHAT_ID is not set, authorized_chat_id="" and
        str(any_int) != "" is always True — every message is silently ignored.
        Notifier must NOT be called.
        """
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        notifier = _mock_notifier()
        with patch("src.main.python.api.routes.telegram.get_notifier", return_value=notifier):
            r = client.post("/api/v1/telegram/webhook", json=_update(99999, "/ping"))
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        notifier.send.assert_not_called()

    def test_wrong_chat_id_blocked_and_notifier_not_called(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        notifier = _mock_notifier()
        with patch("src.main.python.api.routes.telegram.get_notifier", return_value=notifier):
            r = client.post("/api/v1/telegram/webhook", json=_update(99999, "/ping"))
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        notifier.send.assert_not_called()

    def test_matching_chat_id_processes_and_calls_send(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        notifier = _mock_notifier()
        with patch("src.main.python.api.routes.telegram.get_notifier", return_value=notifier):
            r = client.post("/api/v1/telegram/webhook", json=_update(12345, "/ping"))
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        notifier.send.assert_called_once()

    def test_always_http_200_on_blocked_message(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        r = client.post("/api/v1/telegram/webhook", json=_update(99999, "/ping"))
        assert r.status_code == 200

    def test_always_ok_body_on_blocked_message(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        r = client.post("/api/v1/telegram/webhook", json=_update(99999, "/ping"))
        assert r.json() == {"ok": True}


# ── Tests: command dispatch ───────────────────────────────────────────────────

_CHAT = 55555  # chat_id used for all command dispatch tests


def _dispatch(client, monkeypatch, text: str) -> tuple[object, MagicMock]:
    """
    Set up TELEGRAM_CHAT_ID, send a webhook update, and return
    (response, mock_notifier) so tests can assert on send call args.
    """
    monkeypatch.setenv("TELEGRAM_CHAT_ID", str(_CHAT))
    notifier = _mock_notifier()
    with patch("src.main.python.api.routes.telegram.get_notifier", return_value=notifier):
        r = client.post("/api/v1/telegram/webhook", json=_update(_CHAT, text))
    return r, notifier


class TestTelegramWebhookCommands:
    def test_ping_sends_online_reply(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/ping")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        notifier.send.assert_called_once()
        assert "online" in notifier.send.call_args[0][0].lower()

    def test_unknown_command_sends_error_reply(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/frobnicate")
        assert r.status_code == 200
        notifier.send.assert_called_once()
        text = notifier.send.call_args[0][0]
        assert "unknown" in text.lower() or "frobnicate" in text.lower()

    def test_plan_no_account_field_sends_error(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/plan\nsymbol: XAUUSD")
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "account" in text.lower()

    def test_plan_unknown_account_sends_not_found(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/plan\naccount: ghost-tg")
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "ghost-tg" in text or "not found" in text.lower()

    def test_plan_valid_account_creates_plan_and_confirms(self, client, monkeypatch):
        _mk_account(client)
        r, notifier = _dispatch(
            client, monkeypatch,
            "/plan\naccount: tg-acc\nsymbol: XAUUSD\ndirection: long\nrr: 2.5",
        )
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "tg-acc" in text
        assert "created" in text.lower() or "✅" in text  # ✅

    def test_journal_no_account_field_sends_error(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/journal\ntrade_id: T001")
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "account" in text.lower()

    def test_journal_no_trade_id_field_sends_error(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/journal\naccount: tg-acc")
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "trade_id" in text.lower()

    def test_journal_unknown_trade_sends_not_found(self, client, monkeypatch):
        _mk_account(client)
        r, notifier = _dispatch(
            client, monkeypatch,
            "/journal\naccount: tg-acc\ntrade_id: ghost-trade",
        )
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "ghost-trade" in text or "not found" in text.lower()

    def test_journal_updates_trade_and_confirms(self, client, monkeypatch):
        _mk_account(client)
        _mk_trade(client)
        r, notifier = _dispatch(
            client, monkeypatch,
            "/journal\naccount: tg-acc\ntrade_id: TG-T001\nfollowed_plan: yes\nlesson: patient entry",
        )
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "tg-acc" in text
        assert "updated" in text.lower() or "✅" in text  # ✅

    def test_status_no_account_field_sends_error(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/status")
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "account" in text.lower()

    def test_status_unknown_account_sends_not_found(self, client, monkeypatch):
        r, notifier = _dispatch(client, monkeypatch, "/status\naccount: ghost-tg")
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "ghost-tg" in text or "not found" in text.lower()

    def test_status_valid_account_returns_account_info(self, client, monkeypatch):
        _mk_account(client)
        r, notifier = _dispatch(client, monkeypatch, "/status\naccount: tg-acc")
        assert r.status_code == 200
        text = notifier.send.call_args[0][0]
        assert "tg-acc" in text

    def test_exception_in_processing_still_returns_ok(self, client, monkeypatch):
        """
        If command parsing raises an unexpected exception the webhook must
        still return HTTP 200 {"ok": True} — Telegram retries on anything else.
        """
        monkeypatch.setenv("TELEGRAM_CHAT_ID", str(_CHAT))
        notifier = _mock_notifier()
        with patch("src.main.python.api.routes.telegram.get_notifier", return_value=notifier):
            with patch(
                "src.main.python.api.routes.telegram.parse_command",
                side_effect=RuntimeError("unexpected boom"),
            ):
                r = client.post("/api/v1/telegram/webhook", json=_update(_CHAT, "/ping"))
        assert r.status_code == 200
        assert r.json() == {"ok": True}
