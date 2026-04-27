"""
Route tests for GET /accounts/{account_id}/mt5-config/password-status (R6).

Covers:
  1. env var missing → present=false, env_var_name correct
  2. env var present (non-empty) → present=true
  3. env var set to empty string → present=false (empty is treated as missing)
  4. response never includes the password value
  5. missing account → 404 (follows require_account convention)
  6. env_var_name uses correct convention (MT5_<UPPER_UNDERSCORED>_PASSWORD)
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from src.main.python.api.dependencies import get_db
from src.main.python.api.routes import accounts
from src.main.python.api.routes.mt5_sync import router as mt5_router
from src.main.python.models.db_models import Base, AccountModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(mt5_router,       prefix="/api/v1")
    _app.include_router(accounts.router,  prefix="/api/v1")
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


def _create_account(client: TestClient, account_id: str = "test-acct1") -> None:
    resp = client.post("/api/v1/accounts", json={
        "account_id": account_id,
        "broker": "TestBroker",
        "platform": "MT5",
    })
    assert resp.status_code in (200, 201), resp.text


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestPasswordStatusEndpoint:

    def test_env_var_missing_returns_present_false(self, client, monkeypatch):
        _create_account(client, "acct-missing")
        env_key = "MT5_ACCT_MISSING_PASSWORD"
        monkeypatch.delenv(env_key, raising=False)

        resp = client.get("/api/v1/accounts/acct-missing/mt5-config/password-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["present"] is False

    def test_env_var_present_returns_present_true(self, client, monkeypatch):
        _create_account(client, "acct-present")
        env_key = "MT5_ACCT_PRESENT_PASSWORD"
        monkeypatch.setenv(env_key, "secret123")

        resp = client.get("/api/v1/accounts/acct-present/mt5-config/password-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["present"] is True

    def test_empty_env_var_returns_present_false(self, client, monkeypatch):
        _create_account(client, "acct-empty")
        env_key = "MT5_ACCT_EMPTY_PASSWORD"
        monkeypatch.setenv(env_key, "")

        resp = client.get("/api/v1/accounts/acct-empty/mt5-config/password-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["present"] is False

    def test_response_includes_env_var_name(self, client, monkeypatch):
        _create_account(client, "acct-name")
        monkeypatch.delenv("MT5_ACCT_NAME_PASSWORD", raising=False)

        resp = client.get("/api/v1/accounts/acct-name/mt5-config/password-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["env_var_name"] == "MT5_ACCT_NAME_PASSWORD"

    def test_response_does_not_contain_password_value(self, client, monkeypatch):
        _create_account(client, "acct-secret")
        env_key = "MT5_ACCT_SECRET_PASSWORD"
        monkeypatch.setenv(env_key, "supersecretvalue")

        resp = client.get("/api/v1/accounts/acct-secret/mt5-config/password-status")
        assert resp.status_code == 200
        data = resp.json()
        # The actual secret must never appear in the response
        assert "supersecretvalue" not in resp.text
        # Response has exactly the two documented fields
        assert set(data.keys()) == {"env_var_name", "present"}

    def test_missing_account_returns_404(self, client, monkeypatch):
        monkeypatch.delenv("MT5_NO_SUCH_ACCOUNT_PASSWORD", raising=False)
        resp = client.get("/api/v1/accounts/no-such-account/mt5-config/password-status")
        assert resp.status_code == 404

    def test_env_var_name_convention_hyphens(self, client, monkeypatch):
        _create_account(client, "ftmo-p1")
        monkeypatch.delenv("MT5_FTMO_P1_PASSWORD", raising=False)

        resp = client.get("/api/v1/accounts/ftmo-p1/mt5-config/password-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["env_var_name"] == "MT5_FTMO_P1_PASSWORD"

    def test_env_var_name_convention_spaces(self, client, monkeypatch):
        _create_account(client, "ic markets 01")
        monkeypatch.delenv("MT5_IC_MARKETS_01_PASSWORD", raising=False)

        resp = client.get("/api/v1/accounts/ic markets 01/mt5-config/password-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["env_var_name"] == "MT5_IC_MARKETS_01_PASSWORD"
