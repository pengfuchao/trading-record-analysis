"""
HTTP route integration tests — Phase 8.

Uses FastAPI TestClient with dependency_overrides to inject a fresh in-memory
SQLite session per test.  No external services are touched (no Anthropic API,
no MT5, no Telegram, no real Postgres).

The test app is created without the scheduler lifespan to keep tests fast and
self-contained.  All route groups except import (multipart), MT5, and Telegram
are covered here.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main.python.api.dependencies import get_db
from src.main.python.api.routes import accounts, analytics, coaching, mistakes, setups, trades
from src.main.python.api.routes.daily_plans import plans_router, reviews_router
from src.main.python.api.routes.health import router as health_router
from src.main.python.api.routes.trade_plans import router as trade_plans_router
from src.main.python.models.db_models import Base


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app() -> FastAPI:
    """
    Lightweight test app: same routers as create_app() but without the MT5
    scheduler lifespan.  Created once per module and shared across tests.
    """
    _app = FastAPI()
    _app.include_router(health_router)
    _app.include_router(accounts.router,           prefix="/api/v1")
    _app.include_router(trades.router,             prefix="/api/v1")
    _app.include_router(analytics.router,          prefix="/api/v1")
    _app.include_router(mistakes.router,           prefix="/api/v1")
    _app.include_router(setups.setup_defs_router,  prefix="/api/v1")
    _app.include_router(setups.setup_stats_router, prefix="/api/v1")
    _app.include_router(plans_router,              prefix="/api/v1")
    _app.include_router(reviews_router,            prefix="/api/v1")
    _app.include_router(coaching.router,           prefix="/api/v1")
    _app.include_router(trade_plans_router,        prefix="/api/v1")
    return _app


@pytest.fixture()
def client(app: FastAPI):
    """
    Per-test TestClient with a fresh in-memory SQLite database.

    get_db is overridden to yield from a clean session factory so each test
    starts with an empty database and no cross-test data bleed.
    """
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


# ── Request body builders ─────────────────────────────────────────────────────

def _account_body(**overrides) -> dict:
    return {
        "account_id": "acc001",
        "broker": "FTMO",
        "platform": "MT5",
        "starting_balance": 10000.0,
        "account_currency": "USD",
        **overrides,
    }


def _trade_body(**overrides) -> dict:
    return {
        "trade_id": "T001",
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
        **overrides,
    }


def _plan_body(**overrides) -> dict:
    return {
        "symbol": "EURUSD",
        "intended_direction": "long",
        "setup_type": "BOS",
        "thesis": "Break of structure above resistance",
        "planned_rr": 2.0,
        **overrides,
    }


def _daily_plan_body(**overrides) -> dict:
    return {
        "trading_date": "2024-01-15",
        "market_bias": "bullish",
        "symbols_in_focus": ["EURUSD"],
        "allowed_setups": ["BOS"],
        "disallowed_setups": [],
        **overrides,
    }


def _setup_body(**overrides) -> dict:
    return {
        "setup_id": "S001",
        "name": "BOS Retest",
        "strategy_group": "SMC",
        "description": "Break of structure retest entry",
        **overrides,
    }


# ── Setup helpers ─────────────────────────────────────────────────────────────

def _mk_account(client, **overrides) -> dict:
    r = client.post("/api/v1/accounts", json=_account_body(**overrides))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_trade(client, account_id="acc001", **overrides) -> dict:
    r = client.post(f"/api/v1/accounts/{account_id}/trades", json=_trade_body(**overrides))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_plan(client, account_id="acc001", **overrides) -> dict:
    r = client.post(f"/api/v1/accounts/{account_id}/trade-plans", json=_plan_body(**overrides))
    assert r.status_code == 201, r.text
    return r.json()


# ── Tests: health ─────────────────────────────────────────────────────────────

class TestHealth:
    def test_liveness_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── Tests: accounts ───────────────────────────────────────────────────────────

class TestAccounts:
    def test_list_empty(self, client):
        r = client.get("/api/v1/accounts")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_returns_201_and_correct_shape(self, client):
        r = client.post("/api/v1/accounts", json=_account_body())
        assert r.status_code == 201
        data = r.json()
        assert data["account_id"] == "acc001"
        assert data["broker"] == "FTMO"
        assert data["platform"] == "MT5"
        assert data["starting_balance"] == pytest.approx(10000.0)
        assert data["account_currency"] == "USD"
        assert "created_at" in data

    def test_created_account_appears_in_list(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts")
        assert r.status_code == 200
        ids = [a["account_id"] for a in r.json()]
        assert "acc001" in ids

    def test_get_account_200(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001")
        assert r.status_code == 200
        assert r.json()["account_id"] == "acc001"

    def test_get_account_404_unknown(self, client):
        r = client.get("/api/v1/accounts/ghost")
        assert r.status_code == 404

    def test_patch_account_updates_broker(self, client):
        _mk_account(client)
        r = client.patch("/api/v1/accounts/acc001", json={"broker": "MyFundedFX"})
        assert r.status_code == 200
        assert r.json()["broker"] == "MyFundedFX"

    def test_patch_account_404(self, client):
        r = client.patch("/api/v1/accounts/ghost", json={"broker": "X"})
        assert r.status_code == 404

    def test_delete_account_removes_it(self, client):
        _mk_account(client)
        r = client.delete("/api/v1/accounts/acc001")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        assert client.get("/api/v1/accounts/acc001").status_code == 404

    def test_delete_account_404_unknown(self, client):
        r = client.delete("/api/v1/accounts/ghost")
        assert r.status_code == 404


# ── Tests: trades ─────────────────────────────────────────────────────────────

class TestTrades:
    def test_list_trades_empty(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/trades")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["page"] == 1
        assert data["total_pages"] == 1

    def test_list_trades_404_unknown_account(self, client):
        r = client.get("/api/v1/accounts/ghost/trades")
        assert r.status_code == 404

    def test_create_trade_201_and_shape(self, client):
        _mk_account(client)
        r = client.post("/api/v1/accounts/acc001/trades", json=_trade_body())
        assert r.status_code == 201
        data = r.json()
        assert data["trade_id"] == "T001"
        assert data["symbol"] == "EURUSD"
        assert data["net_pnl"] == pytest.approx(100.0)
        assert data["result"] == "Win"
        assert data["account_id"] == "acc001"

    def test_create_trade_404_no_account(self, client):
        r = client.post("/api/v1/accounts/ghost/trades", json=_trade_body())
        assert r.status_code == 404

    def test_get_trade_200(self, client):
        _mk_account(client)
        _mk_trade(client)
        r = client.get("/api/v1/accounts/acc001/trades/T001")
        assert r.status_code == 200
        assert r.json()["trade_id"] == "T001"

    def test_get_trade_404(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/trades/ghost")
        assert r.status_code == 404

    def test_list_shows_created_trade(self, client):
        _mk_account(client)
        _mk_trade(client)
        r = client.get("/api/v1/accounts/acc001/trades")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["trade_id"] == "T001"

    def test_list_filter_by_symbol(self, client):
        _mk_account(client)
        _mk_trade(client, trade_id="T001", symbol="EURUSD")
        _mk_trade(client, trade_id="T002", symbol="GBPUSD")
        r = client.get("/api/v1/accounts/acc001/trades?symbol=EURUSD")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "EURUSD"

    def test_list_filter_by_result(self, client):
        _mk_account(client)
        _mk_trade(client, trade_id="T001", result="Win")
        _mk_trade(client, trade_id="T002", result="Loss", net_pnl=-50.0, gross_pnl=-40.0)
        r = client.get("/api/v1/accounts/acc001/trades?result=Win")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_pagination(self, client):
        _mk_account(client)
        for i in range(1, 4):
            _mk_trade(client, trade_id=f"T{i:03d}", result="Win")
        r = client.get("/api/v1/accounts/acc001/trades?page=1&page_size=2")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["total_pages"] == 2
        assert len(data["items"]) == 2

    def test_patch_trade_journal_fields(self, client):
        _mk_account(client)
        _mk_trade(client)
        r = client.patch("/api/v1/accounts/acc001/trades/T001", json={
            "notes": "Good entry off OB",
            "setup_type": "BOS",
            "followed_plan": True,
            "fomo": False,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["notes"] == "Good entry off OB"
        assert data["setup_type"] == "BOS"
        assert data["followed_plan"] is True
        assert data["fomo"] is False

    def test_delete_trade_removes_it(self, client):
        _mk_account(client)
        _mk_trade(client)
        r = client.delete("/api/v1/accounts/acc001/trades/T001")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        assert client.get("/api/v1/accounts/acc001/trades/T001").status_code == 404


# ── Tests: trade plans ────────────────────────────────────────────────────────

class TestTradePlans:
    def test_list_plans_empty(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/trade-plans")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_plan_201_and_shape(self, client):
        _mk_account(client)
        r = client.post("/api/v1/accounts/acc001/trade-plans", json=_plan_body())
        assert r.status_code == 201
        data = r.json()
        assert data["symbol"] == "EURUSD"
        assert data["planned_rr"] == pytest.approx(2.0)
        assert data["status"] == "planned"
        assert data["account_id"] == "acc001"
        assert "plan_id" in data

    def test_create_plan_404_no_account(self, client):
        r = client.post("/api/v1/accounts/ghost/trade-plans", json=_plan_body())
        assert r.status_code == 404

    def test_get_plan_200(self, client):
        _mk_account(client)
        plan = _mk_plan(client)
        r = client.get(f"/api/v1/accounts/acc001/trade-plans/{plan['plan_id']}")
        assert r.status_code == 200
        assert r.json()["plan_id"] == plan["plan_id"]

    def test_get_plan_404(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/trade-plans/does-not-exist")
        assert r.status_code == 404

    def test_list_plans_after_create(self, client):
        _mk_account(client)
        _mk_plan(client)
        r = client.get("/api/v1/accounts/acc001/trade-plans")
        assert r.status_code == 200
        plans = r.json()
        assert len(plans) == 1
        assert plans[0]["symbol"] == "EURUSD"

    def test_update_plan(self, client):
        _mk_account(client)
        plan = _mk_plan(client)
        r = client.patch(
            f"/api/v1/accounts/acc001/trade-plans/{plan['plan_id']}",
            json={"notes": "Wait for pullback", "planned_rr": 3.0},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["notes"] == "Wait for pullback"
        assert data["planned_rr"] == pytest.approx(3.0)

    def test_delete_plan_204(self, client):
        _mk_account(client)
        plan = _mk_plan(client)
        r = client.delete(f"/api/v1/accounts/acc001/trade-plans/{plan['plan_id']}")
        assert r.status_code == 204
        # Verify gone
        assert client.get(
            f"/api/v1/accounts/acc001/trade-plans/{plan['plan_id']}"
        ).status_code == 404

    def test_link_trade_updates_both_sides(self, client):
        _mk_account(client)
        _mk_trade(client)
        plan = _mk_plan(client)
        pid = plan["plan_id"]

        r = client.post(f"/api/v1/accounts/acc001/trade-plans/{pid}/link/T001")
        assert r.status_code == 200
        assert r.json()["trade_plan_id"] == pid

        # Plan status must be "linked"
        plan_data = client.get(f"/api/v1/accounts/acc001/trade-plans/{pid}").json()
        assert plan_data["status"] == "linked"

    def test_unlink_trade_resets_both_sides(self, client):
        _mk_account(client)
        _mk_trade(client)
        plan = _mk_plan(client)
        pid = plan["plan_id"]

        # Link first
        client.post(f"/api/v1/accounts/acc001/trade-plans/{pid}/link/T001")

        # Then unlink
        r = client.delete(f"/api/v1/accounts/acc001/trade-plans/{pid}/link/T001")
        assert r.status_code == 200
        assert r.json()["trade_plan_id"] is None

        # Plan status must revert to "planned"
        plan_data = client.get(f"/api/v1/accounts/acc001/trade-plans/{pid}").json()
        assert plan_data["status"] == "planned"

    def test_get_linked_trades(self, client):
        _mk_account(client)
        _mk_trade(client)
        plan = _mk_plan(client)
        pid = plan["plan_id"]
        client.post(f"/api/v1/accounts/acc001/trade-plans/{pid}/link/T001")

        r = client.get(f"/api/v1/accounts/acc001/trade-plans/{pid}/trades")
        assert r.status_code == 200
        trades = r.json()
        assert len(trades) == 1
        assert trades[0]["trade_id"] == "T001"


# ── Tests: analytics ─────────────────────────────────────────────────────────

class TestAnalytics:
    def test_analytics_empty_account(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/analytics")
        assert r.status_code == 200
        data = r.json()
        assert data["total_trades"] == 0
        assert data["winning_trades"] == 0
        assert isinstance(data["equity_curve"], list)
        assert isinstance(data["drawdown_curve"], list)

    def test_analytics_with_trades_counts_correctly(self, client):
        _mk_account(client)
        _mk_trade(client, trade_id="T001", result="Win",  net_pnl=100.0)
        _mk_trade(client, trade_id="T002", result="Loss", net_pnl=-50.0, gross_pnl=-40.0)
        r = client.get("/api/v1/accounts/acc001/analytics")
        assert r.status_code == 200
        data = r.json()
        assert data["total_trades"] == 2
        assert data["winning_trades"] == 1
        assert data["losing_trades"] == 1

    def test_analytics_total_pnl(self, client):
        _mk_account(client)
        _mk_trade(client, trade_id="T001", net_pnl=200.0, result="Win")
        _mk_trade(client, trade_id="T002", net_pnl=-80.0, result="Loss", gross_pnl=-70.0)
        r = client.get("/api/v1/accounts/acc001/analytics")
        assert r.status_code == 200
        assert r.json()["total_net_pnl"] == pytest.approx(120.0)

    def test_analytics_404_unknown_account(self, client):
        r = client.get("/api/v1/accounts/ghost/analytics")
        assert r.status_code == 404

    def test_ftmo_status_shape(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/ftmo-status")
        assert r.status_code == 200
        data = r.json()
        assert "daily_status" in data
        assert "overall_status" in data
        assert "account_status" in data
        assert "today_pnl" in data
        assert data["daily_loss_limit_pct"] == pytest.approx(5.0)

    def test_ftmo_status_404(self, client):
        r = client.get("/api/v1/accounts/ghost/ftmo-status")
        assert r.status_code == 404

    def test_plan_adherence_empty(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/plan-adherence")
        assert r.status_code == 200
        data = r.json()
        assert data["total_trades"] == 0
        assert data["planned_count"] == 0
        assert "coaching_signals" in data

    def test_plan_adherence_404(self, client):
        r = client.get("/api/v1/accounts/ghost/plan-adherence")
        assert r.status_code == 404

    def test_mistakes_report_empty(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/mistakes")
        assert r.status_code == 200
        data = r.json()
        assert data["total_trades_analyzed"] == 0
        assert isinstance(data["ranked_by_frequency"], list)

    def test_mistakes_report_404(self, client):
        r = client.get("/api/v1/accounts/ghost/mistakes")
        assert r.status_code == 404


# ── Tests: daily plans ────────────────────────────────────────────────────────

class TestDailyPlans:
    def test_list_plans_empty(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/daily-plans")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_plan_201_and_shape(self, client):
        _mk_account(client)
        r = client.post("/api/v1/accounts/acc001/daily-plans", json=_daily_plan_body())
        assert r.status_code == 201
        data = r.json()
        assert data["trading_date"] == "2024-01-15"
        assert data["market_bias"] == "bullish"
        assert data["symbols_in_focus"] == ["EURUSD"]
        assert data["allowed_setups"] == ["BOS"]
        assert "plan_id" in data

    def test_duplicate_date_returns_409(self, client):
        _mk_account(client)
        client.post("/api/v1/accounts/acc001/daily-plans", json=_daily_plan_body())
        r = client.post("/api/v1/accounts/acc001/daily-plans", json=_daily_plan_body())
        assert r.status_code == 409

    def test_get_plan_by_id_200(self, client):
        _mk_account(client)
        created = client.post(
            "/api/v1/accounts/acc001/daily-plans", json=_daily_plan_body()
        ).json()
        r = client.get(f"/api/v1/accounts/acc001/daily-plans/{created['plan_id']}")
        assert r.status_code == 200
        assert r.json()["plan_id"] == created["plan_id"]

    def test_get_plan_404(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/daily-plans/ghost")
        assert r.status_code == 404

    def test_delete_plan(self, client):
        _mk_account(client)
        created = client.post(
            "/api/v1/accounts/acc001/daily-plans", json=_daily_plan_body()
        ).json()
        r = client.delete(f"/api/v1/accounts/acc001/daily-plans/{created['plan_id']}")
        assert r.status_code == 204


# ── Tests: setups ─────────────────────────────────────────────────────────────

class TestSetups:
    def test_list_setups_empty(self, client):
        r = client.get("/api/v1/setups")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_setup_201_and_shape(self, client):
        r = client.post("/api/v1/setups", json=_setup_body())
        assert r.status_code == 201
        data = r.json()
        assert data["setup_id"] == "S001"
        assert data["name"] == "BOS Retest"
        assert data["strategy_group"] == "SMC"
        assert "created_at" in data

    def test_setup_appears_in_list(self, client):
        client.post("/api/v1/setups", json=_setup_body())
        r = client.get("/api/v1/setups")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["name"] == "BOS Retest"

    def test_get_setup_200(self, client):
        client.post("/api/v1/setups", json=_setup_body())
        r = client.get("/api/v1/setups/S001")
        assert r.status_code == 200
        assert r.json()["setup_id"] == "S001"

    def test_get_setup_404(self, client):
        r = client.get("/api/v1/setups/ghost")
        assert r.status_code == 404

    def test_patch_setup(self, client):
        client.post("/api/v1/setups", json=_setup_body())
        r = client.patch("/api/v1/setups/S001", json={"description": "Updated description"})
        assert r.status_code == 200
        assert r.json()["description"] == "Updated description"

    def test_delete_setup(self, client):
        client.post("/api/v1/setups", json=_setup_body())
        r = client.delete("/api/v1/setups/S001")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        assert client.get("/api/v1/setups/S001").status_code == 404


# ── Tests: coaching (list/get only, no generation) ────────────────────────────

class TestCoaching:
    def test_list_reviews_empty(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/coaching/reviews")
        assert r.status_code == 200
        data = r.json()
        assert data["account_id"] == "acc001"
        assert data["total"] == 0
        assert data["reviews"] == []

    def test_list_reviews_404_unknown_account(self, client):
        r = client.get("/api/v1/accounts/ghost/coaching/reviews")
        assert r.status_code == 404

    def test_get_review_404(self, client):
        _mk_account(client)
        r = client.get("/api/v1/accounts/acc001/coaching/reviews/no-such-review")
        assert r.status_code == 404
