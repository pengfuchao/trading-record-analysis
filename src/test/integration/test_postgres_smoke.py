"""
Postgres-specific smoke tests.

Automatically SKIPPED when DATABASE_URL is not set or points at SQLite —
they do not interfere with the standard dev/CI SQLite test run.

These tests are run by the postgres-migration-check CI job, which spins up a
real Postgres 15 service and runs alembic upgrade head before invoking pytest.

Guarantees provided by this suite:
  1. alembic upgrade head applies the full migration chain on real Postgres
     (verified by a schema inspection test).
  2. All expected tables exist after migration (catches missing create_table stmts).
  3. Column-level regression: lookback_days (migration 010) is present and its
     server_default of 7 works correctly — this is the class of bug migration 007
     had to fix retroactively for SQLite.
  4. ORM round-trip (create / read / delete) works on real Postgres — confirms
     that SQLAlchemy ORM operations translate to valid Postgres SQL.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

DB_URL = os.environ.get("DATABASE_URL", "")
IS_POSTGRES = DB_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES,
    reason="Postgres smoke tests require DATABASE_URL=postgresql+...",
)

# Tables that must exist after alembic upgrade head
_EXPECTED_TABLES = {
    "accounts",
    "trades",
    "daily_plans",
    "daily_reviews",
    "coaching_reviews",
    "trade_plans",
    "setup_definitions",
    "mt5_sync_configs",
    "mt5_sync_runs",
    "mt5_open_positions",
    "alembic_version",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(DB_URL)
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    """Per-test session that rolls back after each test to keep the DB clean."""
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    sess = Session()
    yield sess
    sess.rollback()
    sess.close()


# ── Schema / migration checks ─────────────────────────────────────────────────

class TestMigrationSchema:
    """
    Verify the schema produced by `alembic upgrade head` on real Postgres.
    These tests fail loudly when a migration creates wrong/missing columns or
    tables — the class of issue that only shows up on Postgres, not SQLite.
    """

    def test_all_expected_tables_exist(self, pg_engine):
        insp = inspect(pg_engine)
        existing = set(insp.get_table_names())
        missing = _EXPECTED_TABLES - existing
        assert not missing, (
            f"Tables missing after 'alembic upgrade head' on Postgres: {missing}"
        )

    def test_mt5_sync_configs_has_lookback_days(self, pg_engine):
        """Migration 010 added lookback_days; verify it exists on real Postgres."""
        insp = inspect(pg_engine)
        cols = {c["name"] for c in insp.get_columns("mt5_sync_configs")}
        assert "lookback_days" in cols, (
            "Migration 010 (lookback_days column) not applied to mt5_sync_configs"
        )

    def test_trades_has_enrichment_columns(self, pg_engine):
        """Verify core journaling columns are present on the trades table."""
        insp = inspect(pg_engine)
        cols = {c["name"] for c in insp.get_columns("trades")}
        for col in ("setup_type", "notes", "lesson_learned", "mistake_tags", "followed_plan"):
            assert col in cols, (
                f"Expected enrichment column '{col}' missing from trades table"
            )

    def test_accounts_has_currency_column(self, pg_engine):
        insp = inspect(pg_engine)
        cols = {c["name"] for c in insp.get_columns("accounts")}
        assert "account_currency" in cols

    def test_trades_has_trade_plan_id(self, pg_engine):
        """trade_plan_id was added in a migration — ensure it survived on Postgres."""
        insp = inspect(pg_engine)
        cols = {c["name"] for c in insp.get_columns("trades")}
        assert "trade_plan_id" in cols


# ── ORM CRUD on real Postgres ─────────────────────────────────────────────────

class TestPostgresOrmCrud:
    """
    Verify SQLAlchemy ORM operations produce valid Postgres SQL.

    Each test uses a unique account_id prefix ('pg-ci-*') to avoid collisions
    if tests run in parallel or the DB is reused across runs.  The per-test
    session fixture rolls back after each test.
    """

    def test_account_create_read_delete(self, pg_session):
        from src.main.python.models.db_models import AccountModel

        acc = AccountModel(
            account_id="pg-ci-smoke-acc",
            broker="CI Broker",
            platform="MT5",
            account_currency="USD",
        )
        pg_session.add(acc)
        pg_session.flush()

        found = pg_session.get(AccountModel, "pg-ci-smoke-acc")
        assert found is not None
        assert found.broker == "CI Broker"
        assert found.account_currency == "USD"

        pg_session.delete(found)
        pg_session.flush()
        gone = pg_session.get(AccountModel, "pg-ci-smoke-acc")
        assert gone is None

    def test_trade_insert_and_filter_query(self, pg_session):
        from src.main.python.models.db_models import AccountModel, TradeModel

        acc = AccountModel(
            account_id="pg-ci-smoke-trades",
            broker="CI",
            platform="MT5",
            account_currency="USD",
        )
        pg_session.add(acc)
        pg_session.flush()

        for i, symbol in enumerate(["EURUSD", "XAUUSD"]):
            pg_session.add(TradeModel(
                trade_id=f"pg-ci-smoke-t{i}",
                account_id="pg-ci-smoke-trades",
                symbol=symbol,
                platform="MT5",
                result="Win",
                net_pnl=float(100 * (i + 1)),
            ))
        pg_session.flush()

        rows = pg_session.execute(
            select(TradeModel)
            .where(TradeModel.account_id == "pg-ci-smoke-trades")
            .where(TradeModel.symbol == "XAUUSD")
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].net_pnl == 200.0

    def test_mt5_config_server_default_lookback_days(self, pg_session):
        """
        Verify server_default='7' for lookback_days works on real Postgres.
        This is specifically the class of bug migration 007 fixed for SQLite —
        a SQLite server_default that didn't apply to existing rows.  On Postgres,
        the server_default applies correctly at INSERT time if the Python model
        does not supply a value.
        """
        from src.main.python.models.db_models import AccountModel, MT5SyncConfigModel

        acc = AccountModel(
            account_id="pg-ci-smoke-mt5",
            broker="CI",
            platform="MT5",
            account_currency="USD",
        )
        pg_session.add(acc)
        pg_session.flush()

        cfg = MT5SyncConfigModel(
            account_id="pg-ci-smoke-mt5",
            mt5_login=99999,
            mt5_server="CI-Server",
            # lookback_days intentionally omitted — relying on server_default='7'
        )
        pg_session.add(cfg)
        pg_session.flush()
        pg_session.refresh(cfg)

        assert cfg.lookback_days == 7, (
            f"Expected lookback_days=7 from server_default, got {cfg.lookback_days}"
        )

    def test_setup_definition_crud(self, pg_session):
        from src.main.python.models.db_models import SetupDefinitionModel

        # setup_id is a required user-supplied slug (not auto-generated).
        # SetupDefinitionCreate.setup_id is a mandatory field; the ORM column
        # has no default — omitting it is what caused the NOT NULL violation.
        setup = SetupDefinitionModel(
            setup_id="pg-ci-smoke-setup",
            name="CI Test Setup",
            strategy_group="Breakout",
            description="Smoke test",
        )
        pg_session.add(setup)
        pg_session.flush()

        found = pg_session.get(SetupDefinitionModel, "pg-ci-smoke-setup")
        assert found is not None
        assert found.name == "CI Test Setup"
