"""
Integration tests for TradeRepository and AccountRepository using SQLite in-memory.

ARRAY(String) is PostgreSQL-only, so we patch the mistake_tags column type to JSON
before calling Base.metadata.create_all(). This lets us test all repository logic
without a real PostgreSQL instance.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import sessionmaker

from src.main.python.models.account import Account
from src.main.python.models.db_models import Base, TradeModel
from src.main.python.models.enums import (
    AssetClass, ChallengePhase, Direction, Platform, TradeResult,
)
from src.main.python.models.trade import Trade
from src.main.python.services.account_repository import AccountRepository
from src.main.python.services.trade_repository import TradeRepository


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    """
    One SQLite in-memory engine for the whole test session.
    Patch mistake_tags column to JSON before creating tables (ARRAY not supported in SQLite).
    """
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Patch PostgreSQL ARRAY column to JSON for SQLite compatibility
    TradeModel.__table__.c["mistake_tags"].type = JSON()
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Fresh session for each test, auto-rolled back after the test."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    sess = SessionLocal()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture()
def account_repo(session):
    return AccountRepository(session)


@pytest.fixture()
def trade_repo(session):
    return TradeRepository(session)


# ── Builder helpers ───────────────────────────────────────────────────────────

def make_account(account_id="ACC001", broker="FTMO", platform=Platform.MT5, **kwargs) -> Account:
    defaults = dict(
        account_id=account_id,
        broker=broker,
        platform=platform,
        prop_firm="FTMO",
        challenge_phase=ChallengePhase.PHASE_1,
        starting_balance=10000.0,
        account_currency="USD",
        created_at=datetime(2024, 1, 1),
    )
    defaults.update(kwargs)
    return Account(**defaults)


def make_trade(trade_id="T001", account_id="ACC001", **kwargs) -> Trade:
    defaults = dict(
        trade_id=trade_id,
        account_id=account_id,
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        direction=Direction.LONG,
        platform=Platform.MT5,
        raw_trade_type="buy",
        entry_datetime=datetime(2024, 1, 15, 9, 0),
        exit_datetime=datetime(2024, 1, 15, 11, 0),
        holding_duration=timedelta(hours=2),
        entry_price=1.0850,
        exit_price=1.0920,
        stop_loss=1.0800,
        take_profit=1.0950,
        lot_size=0.10,
        gross_pnl=70.0,
        commission=-7.0,
        swap=0.0,
        net_pnl=63.0,
        actual_r_multiple=1.4,
        result=TradeResult.WIN,
        followed_plan=True,
        mistake_tags=[],
    )
    defaults.update(kwargs)
    return Trade(**defaults)


# ── AccountRepository tests ───────────────────────────────────────────────────

class TestAccountRepository:
    def test_save_and_get_by_id(self, account_repo, session):
        acc = make_account()
        saved = account_repo.save(acc)
        session.commit()

        found = account_repo.get_by_id("ACC001")
        assert found is not None
        assert found.account_id == "ACC001"
        assert found.broker == "FTMO"
        assert found.platform == Platform.MT5

    def test_get_by_id_missing(self, account_repo):
        result = account_repo.get_by_id("NONEXISTENT")
        assert result is None

    def test_save_upsert(self, account_repo, session):
        acc = make_account(broker="FTMO")
        account_repo.save(acc)
        session.commit()

        # Update the broker
        updated = make_account(broker="MyForexFunds")
        account_repo.save(updated)
        session.commit()

        found = account_repo.get_by_id("ACC001")
        assert found.broker == "MyForexFunds"

    def test_list_all_empty(self, account_repo):
        assert account_repo.list_all() == []

    def test_list_all(self, account_repo, session):
        account_repo.save(make_account("ACC001", created_at=datetime(2024, 1, 1)))
        account_repo.save(make_account("ACC002", created_at=datetime(2024, 2, 1)))
        session.commit()

        accounts = account_repo.list_all()
        assert len(accounts) == 2
        # list_all orders by created_at DESC
        assert accounts[0].account_id == "ACC002"
        assert accounts[1].account_id == "ACC001"

    def test_delete_existing(self, account_repo, session):
        account_repo.save(make_account())
        session.commit()

        deleted = account_repo.delete("ACC001")
        session.commit()

        assert deleted is True
        assert account_repo.get_by_id("ACC001") is None

    def test_delete_nonexistent(self, account_repo):
        deleted = account_repo.delete("GHOST")
        assert deleted is False

    def test_challenge_phase_roundtrip(self, account_repo, session):
        acc = make_account(challenge_phase=ChallengePhase.PHASE_2)
        account_repo.save(acc)
        session.commit()

        found = account_repo.get_by_id("ACC001")
        assert found.challenge_phase == ChallengePhase.PHASE_2

    def test_optional_fields_none(self, account_repo, session):
        acc = make_account(prop_firm=None, challenge_phase=None)
        account_repo.save(acc)
        session.commit()

        found = account_repo.get_by_id("ACC001")
        assert found.prop_firm is None
        assert found.challenge_phase is None


# ── TradeRepository tests ─────────────────────────────────────────────────────

class TestTradeRepository:
    @pytest.fixture(autouse=True)
    def setup_account(self, account_repo, session):
        """Each test needs at least ACC001 to satisfy the FK constraint."""
        account_repo.save(make_account())
        session.commit()

    def test_save_and_get_by_id(self, trade_repo, session):
        trade = make_trade()
        trade_repo.save(trade)
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found is not None
        assert found.trade_id == "T001"
        assert found.symbol == "EURUSD"
        assert found.direction == Direction.LONG

    def test_get_by_id_missing(self, trade_repo):
        assert trade_repo.get_by_id("GHOST") is None

    def test_save_upsert(self, trade_repo, session):
        trade_repo.save(make_trade(net_pnl=63.0))
        session.commit()

        trade_repo.save(make_trade(net_pnl=100.0))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.net_pnl == pytest.approx(100.0)

    def test_save_with_import_run_id(self, trade_repo, session):
        trade_repo.save(make_trade(), import_run_id="batch-001")
        session.commit()

        # We verify import_run_id via the ORM model directly
        from sqlalchemy import select
        from src.main.python.models.db_models import TradeModel
        row = session.execute(
            select(TradeModel).where(TradeModel.trade_id == "T001")
        ).scalar_one()
        assert row.import_run_id == "batch-001"

    def test_save_batch(self, trade_repo, session):
        trades = [make_trade(f"T{i:03d}") for i in range(1, 6)]
        count = trade_repo.save_batch(trades, import_run_id="bulk-run")
        session.commit()

        assert count == 5
        assert trade_repo.count("ACC001") == 5

    def test_get_by_account(self, trade_repo, session):
        trade_repo.save(make_trade("T001", exit_datetime=datetime(2024, 1, 15, 11, 0)))
        trade_repo.save(make_trade("T002", exit_datetime=datetime(2024, 1, 10, 11, 0)))
        trade_repo.save(make_trade("T003", exit_datetime=datetime(2024, 1, 20, 11, 0)))
        session.commit()

        trades = trade_repo.get_by_account("ACC001")
        assert len(trades) == 3
        # Should be ordered by exit_datetime ascending
        assert trades[0].trade_id == "T002"
        assert trades[1].trade_id == "T001"
        assert trades[2].trade_id == "T003"

    def test_get_by_account_empty(self, trade_repo):
        assert trade_repo.get_by_account("ACC001") == []

    def test_get_by_account_filtered_symbol(self, trade_repo, session):
        trade_repo.save(make_trade("T001", symbol="EURUSD"))
        trade_repo.save(make_trade("T002", symbol="GBPUSD"))
        trade_repo.save(make_trade("T003", symbol="EURUSD"))
        session.commit()

        results = trade_repo.get_by_account_filtered("ACC001", symbol="EURUSD")
        assert len(results) == 2
        assert all(t.symbol == "EURUSD" for t in results)

    def test_get_by_account_filtered_date_range(self, trade_repo, session):
        trade_repo.save(make_trade("T001", exit_datetime=datetime(2024, 1, 5)))
        trade_repo.save(make_trade("T002", exit_datetime=datetime(2024, 1, 15)))
        trade_repo.save(make_trade("T003", exit_datetime=datetime(2024, 1, 25)))
        session.commit()

        results = trade_repo.get_by_account_filtered(
            "ACC001",
            from_date=datetime(2024, 1, 10),
            to_date=datetime(2024, 1, 20),
        )
        assert len(results) == 1
        assert results[0].trade_id == "T002"

    def test_get_by_account_filtered_result(self, trade_repo, session):
        trade_repo.save(make_trade("T001", result=TradeResult.WIN))
        trade_repo.save(make_trade("T002", result=TradeResult.LOSS))
        trade_repo.save(make_trade("T003", result=TradeResult.WIN))
        session.commit()

        results = trade_repo.get_by_account_filtered("ACC001", result="Win")
        assert len(results) == 2
        assert all(t.result == TradeResult.WIN for t in results)

    def test_get_by_account_filtered_combined(self, trade_repo, session):
        trade_repo.save(make_trade(
            "T001", symbol="EURUSD", result=TradeResult.WIN,
            exit_datetime=datetime(2024, 1, 15)
        ))
        trade_repo.save(make_trade(
            "T002", symbol="GBPUSD", result=TradeResult.WIN,
            exit_datetime=datetime(2024, 1, 15)
        ))
        trade_repo.save(make_trade(
            "T003", symbol="EURUSD", result=TradeResult.LOSS,
            exit_datetime=datetime(2024, 1, 15)
        ))
        session.commit()

        results = trade_repo.get_by_account_filtered(
            "ACC001", symbol="EURUSD", result="Win"
        )
        assert len(results) == 1
        assert results[0].trade_id == "T001"

    def test_delete_existing(self, trade_repo, session):
        trade_repo.save(make_trade())
        session.commit()

        deleted = trade_repo.delete("T001")
        session.commit()

        assert deleted is True
        assert trade_repo.get_by_id("T001") is None

    def test_delete_nonexistent(self, trade_repo):
        deleted = trade_repo.delete("GHOST")
        assert deleted is False

    def test_count(self, trade_repo, session):
        assert trade_repo.count("ACC001") == 0
        trade_repo.save(make_trade("T001"))
        trade_repo.save(make_trade("T002"))
        session.commit()
        assert trade_repo.count("ACC001") == 2

    def test_count_different_account(self, trade_repo, session, account_repo):
        account_repo.save(make_account("ACC002"))
        session.commit()

        trade_repo.save(make_trade("T001", account_id="ACC001"))
        trade_repo.save(make_trade("T002", account_id="ACC002"))
        session.commit()

        assert trade_repo.count("ACC001") == 1
        assert trade_repo.count("ACC002") == 1

    def test_mistake_tags_empty_roundtrip(self, trade_repo, session):
        """Empty list stored as NULL, retrieved as []."""
        trade_repo.save(make_trade(mistake_tags=[]))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.mistake_tags == []

    def test_mistake_tags_populated_roundtrip(self, trade_repo, session):
        trade_repo.save(make_trade(mistake_tags=["fomo", "overtrading"]))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.mistake_tags == ["fomo", "overtrading"]

    def test_holding_duration_roundtrip(self, trade_repo, session):
        td = timedelta(hours=4, minutes=35, seconds=12)
        trade_repo.save(make_trade(holding_duration=td))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.holding_duration == td

    def test_holding_duration_none(self, trade_repo, session):
        trade_repo.save(make_trade(holding_duration=None))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.holding_duration is None

    def test_enum_roundtrip(self, trade_repo, session):
        trade_repo.save(make_trade(
            asset_class=AssetClass.GOLD,
            direction=Direction.SHORT,
            result=TradeResult.LOSS,
        ))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.asset_class == AssetClass.GOLD
        assert found.direction == Direction.SHORT
        assert found.result == TradeResult.LOSS

    def test_boolean_flags_roundtrip(self, trade_repo, session):
        trade_repo.save(make_trade(
            followed_plan=True,
            fomo=True,
            emotional_trade=False,
            premature_exit=None,
        ))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.followed_plan is True
        assert found.fomo is True
        assert found.emotional_trade is False
        assert found.premature_exit is None

    def test_text_enrichment_fields_roundtrip(self, trade_repo, session):
        trade_repo.save(make_trade(
            entry_reason="BOS + OB",
            lesson_learned="Wait for pullback",
            notes="Good setup",
        ))
        session.commit()

        found = trade_repo.get_by_id("T001")
        assert found.entry_reason == "BOS + OB"
        assert found.lesson_learned == "Wait for pullback"
        assert found.notes == "Good setup"

    def test_all_optional_none(self, trade_repo, session):
        """Minimal trade — only required fields, everything else None."""
        minimal = Trade(trade_id="MIN001", account_id="ACC001")
        trade_repo.save(minimal)
        session.commit()

        found = trade_repo.get_by_id("MIN001")
        assert found is not None
        assert found.trade_id == "MIN001"
        assert found.symbol is None
        assert found.net_pnl is None
        assert found.mistake_tags == []
