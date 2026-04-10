"""
Unit tests for db_converters.py — no database required.
Tests pure in-memory conversion between dataclasses and ORM objects.
"""
from datetime import datetime, timedelta

import pytest

from src.main.python.models.account import Account
from src.main.python.models.db_models import AccountModel, TradeModel
from src.main.python.models.enums import (
    AssetClass, ChallengePhase, Direction, Platform, TradeResult,
)
from src.main.python.models.trade import Trade
from src.main.python.utils.db_converters import (
    account_to_orm, orm_to_account, orm_to_trade, trade_to_orm,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_trade(**overrides) -> Trade:
    defaults = dict(
        trade_id="T001",
        account_id="ACC001",
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        direction=Direction.LONG,
        platform=Platform.MT5,
        raw_trade_type="buy",
        entry_datetime=datetime(2024, 1, 15, 9, 0),
        exit_datetime=datetime(2024, 1, 15, 11, 30),
        holding_duration=timedelta(hours=2, minutes=30),
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
        magic=12345,
        comment="EA trade",
        setup_type="BOS",
        strategy="ICT",
        session="London",
        higher_tf_bias="bullish",
        entry_timeframe="15m",
        market_condition="trending",
        key_levels="1.0850 support",
        news_context="NFP tomorrow",
        pre_trade_bias="long bias",
        entry_reason="BOS + OB",
        trigger_confirmation="M15 close above",
        stop_loss_logic="Below OB",
        take_profit_logic="Next liquidity",
        exit_reason="TP hit",
        followed_plan=True,
        is_a_plus_setup=True,
        early_entry=False,
        chasing=False,
        fomo=False,
        emotional_trade=False,
        revenge_trade=False,
        overtrading=False,
        hesitation=False,
        moved_stop=False,
        premature_exit=False,
        held_loser_too_long=False,
        trade_quality="good trade",
        problem_source=None,
        mistake_tags=["fomo", "oversize"],
        lesson_learned="Wait for confirmation",
        repeat_next_time="Entry on OB",
        avoid_next_time="Chasing",
        screenshot_before="/imgs/before.png",
        screenshot_during="/imgs/during.png",
        screenshot_after="/imgs/after.png",
        notes="Good trade",
    )
    defaults.update(overrides)
    return Trade(**defaults)


def make_account(**overrides) -> Account:
    defaults = dict(
        account_id="ACC001",
        broker="FTMO",
        platform=Platform.MT5,
        prop_firm="FTMO",
        challenge_phase=ChallengePhase.PHASE_1,
        starting_balance=10000.0,
        account_currency="USD",
        created_at=datetime(2024, 1, 1, 0, 0),
    )
    defaults.update(overrides)
    return Account(**defaults)


# ── Trade → ORM ───────────────────────────────────────────────────────────────

class TestTradeToOrm:
    def test_identifiers(self):
        orm = trade_to_orm(make_trade())
        assert orm.trade_id == "T001"
        assert orm.account_id == "ACC001"

    def test_enums_stored_as_strings(self):
        orm = trade_to_orm(make_trade())
        assert orm.asset_class == "Forex"
        assert orm.direction == "Long"
        assert orm.platform == "MT5"
        assert orm.result == "Win"

    def test_none_enum_stored_as_none(self):
        trade = make_trade(asset_class=None, direction=None, result=None, platform=None)
        orm = trade_to_orm(trade)
        assert orm.asset_class is None
        assert orm.direction is None
        assert orm.result is None
        assert orm.platform is None

    def test_holding_duration_preserved(self):
        td = timedelta(hours=3, minutes=15, seconds=30)
        orm = trade_to_orm(make_trade(holding_duration=td))
        assert orm.holding_duration == td

    def test_holding_duration_none(self):
        orm = trade_to_orm(make_trade(holding_duration=None))
        assert orm.holding_duration is None

    def test_mistake_tags_populated(self):
        orm = trade_to_orm(make_trade(mistake_tags=["fomo", "chasing"]))
        assert orm.mistake_tags == ["fomo", "chasing"]

    def test_mistake_tags_empty_list_becomes_none(self):
        orm = trade_to_orm(make_trade(mistake_tags=[]))
        assert orm.mistake_tags is None

    def test_import_run_id_default_none(self):
        orm = trade_to_orm(make_trade())
        assert orm.import_run_id is None

    def test_import_run_id_set(self):
        orm = trade_to_orm(make_trade(), import_run_id="run-2024-001")
        assert orm.import_run_id == "run-2024-001"

    def test_boolean_flags(self):
        orm = trade_to_orm(make_trade(followed_plan=True, fomo=False, emotional_trade=None))
        assert orm.followed_plan is True
        assert orm.fomo is False
        assert orm.emotional_trade is None

    def test_numeric_fields(self):
        orm = trade_to_orm(make_trade())
        assert orm.entry_price == pytest.approx(1.0850)
        assert orm.net_pnl == pytest.approx(63.0)
        assert orm.lot_size == pytest.approx(0.10)
        assert orm.actual_r_multiple == pytest.approx(1.4)

    def test_datetime_fields(self):
        orm = trade_to_orm(make_trade())
        assert orm.entry_datetime == datetime(2024, 1, 15, 9, 0)
        assert orm.exit_datetime == datetime(2024, 1, 15, 11, 30)

    def test_text_fields(self):
        orm = trade_to_orm(make_trade())
        assert orm.setup_type == "BOS"
        assert orm.entry_reason == "BOS + OB"
        assert orm.lesson_learned == "Wait for confirmation"

    def test_screenshot_fields(self):
        orm = trade_to_orm(make_trade())
        assert orm.screenshot_before == "/imgs/before.png"
        assert orm.screenshot_during == "/imgs/during.png"
        assert orm.screenshot_after == "/imgs/after.png"

    def test_all_optional_none(self):
        """Minimal trade with only required fields — all optional fields None/empty."""
        trade = Trade(trade_id="MIN001", account_id="ACC001")
        orm = trade_to_orm(trade)
        assert orm.trade_id == "MIN001"
        assert orm.symbol is None
        assert orm.net_pnl is None
        assert orm.mistake_tags is None  # empty list → None


# ── ORM → Trade ───────────────────────────────────────────────────────────────

def _make_orm_trade(**overrides) -> TradeModel:
    """Build a TradeModel with sensible defaults (no DB session needed)."""
    defaults = dict(
        trade_id="T001",
        account_id="ACC001",
        symbol="EURUSD",
        asset_class="Forex",
        direction="Long",
        platform="MT5",
        raw_trade_type="buy",
        entry_datetime=datetime(2024, 1, 15, 9, 0),
        exit_datetime=datetime(2024, 1, 15, 11, 30),
        holding_duration=timedelta(hours=2, minutes=30),
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
        result="Win",
        magic=12345,
        comment="EA trade",
        setup_type="BOS",
        strategy="ICT",
        session="London",
        higher_tf_bias="bullish",
        entry_timeframe="15m",
        market_condition="trending",
        key_levels="1.0850 support",
        news_context="NFP tomorrow",
        pre_trade_bias="long bias",
        entry_reason="BOS + OB",
        trigger_confirmation="M15 close above",
        stop_loss_logic="Below OB",
        take_profit_logic="Next liquidity",
        exit_reason="TP hit",
        followed_plan=True,
        is_a_plus_setup=True,
        early_entry=False,
        chasing=False,
        fomo=False,
        emotional_trade=False,
        revenge_trade=False,
        overtrading=False,
        hesitation=False,
        moved_stop=False,
        premature_exit=False,
        held_loser_too_long=False,
        trade_quality="good trade",
        problem_source=None,
        mistake_tags=["fomo", "oversize"],
        lesson_learned="Wait for confirmation",
        repeat_next_time="Entry on OB",
        avoid_next_time="Chasing",
        screenshot_before="/imgs/before.png",
        screenshot_during="/imgs/during.png",
        screenshot_after="/imgs/after.png",
        notes="Good trade",
        import_run_id=None,
        created_at=datetime(2024, 1, 15, 12, 0),
        updated_at=datetime(2024, 1, 15, 12, 0),
    )
    defaults.update(overrides)
    return TradeModel(**defaults)


class TestOrmToTrade:
    def test_enums_reconstructed(self):
        trade = orm_to_trade(_make_orm_trade())
        assert trade.asset_class == AssetClass.FOREX
        assert trade.direction == Direction.LONG
        assert trade.platform == Platform.MT5
        assert trade.result == TradeResult.WIN

    def test_none_string_enums_become_none(self):
        trade = orm_to_trade(_make_orm_trade(
            asset_class=None, direction=None, result=None, platform=None
        ))
        assert trade.asset_class is None
        assert trade.direction is None
        assert trade.result is None
        assert trade.platform is None

    def test_mistake_tags_null_becomes_empty_list(self):
        trade = orm_to_trade(_make_orm_trade(mistake_tags=None))
        assert trade.mistake_tags == []

    def test_mistake_tags_populated(self):
        trade = orm_to_trade(_make_orm_trade(mistake_tags=["fomo", "oversize"]))
        assert trade.mistake_tags == ["fomo", "oversize"]

    def test_holding_duration_preserved(self):
        td = timedelta(hours=5, minutes=10)
        trade = orm_to_trade(_make_orm_trade(holding_duration=td))
        assert trade.holding_duration == td

    def test_holding_duration_none(self):
        trade = orm_to_trade(_make_orm_trade(holding_duration=None))
        assert trade.holding_duration is None

    def test_numeric_fields(self):
        trade = orm_to_trade(_make_orm_trade())
        assert trade.entry_price == pytest.approx(1.0850)
        assert trade.net_pnl == pytest.approx(63.0)
        assert trade.actual_r_multiple == pytest.approx(1.4)

    def test_import_run_id_not_on_trade(self):
        """import_run_id is an ORM-only field — Trade dataclass has no such attribute."""
        trade = orm_to_trade(_make_orm_trade(import_run_id="run-001"))
        assert not hasattr(trade, "import_run_id")


# ── Account → ORM ─────────────────────────────────────────────────────────────

class TestAccountToOrm:
    def test_basic_fields(self):
        orm = account_to_orm(make_account())
        assert orm.account_id == "ACC001"
        assert orm.broker == "FTMO"
        assert orm.account_currency == "USD"
        assert orm.starting_balance == pytest.approx(10000.0)

    def test_platform_stored_as_string(self):
        orm = account_to_orm(make_account(platform=Platform.MT4))
        assert orm.platform == "MT4"

    def test_challenge_phase_stored_as_string(self):
        orm = account_to_orm(make_account(challenge_phase=ChallengePhase.PHASE_1))
        assert isinstance(orm.challenge_phase, str)

    def test_challenge_phase_none(self):
        orm = account_to_orm(make_account(challenge_phase=None))
        assert orm.challenge_phase is None

    def test_created_at_preserved(self):
        dt = datetime(2024, 3, 1, 8, 0, 0)
        orm = account_to_orm(make_account(created_at=dt))
        assert orm.created_at == dt


# ── ORM → Account ─────────────────────────────────────────────────────────────

def _make_orm_account(**overrides) -> AccountModel:
    defaults = dict(
        account_id="ACC001",
        broker="FTMO",
        platform="MT5",
        prop_firm="FTMO",
        challenge_phase=ChallengePhase.PHASE_1.value,
        starting_balance=10000.0,
        account_currency="USD",
        created_at=datetime(2024, 1, 1, 0, 0),
    )
    defaults.update(overrides)
    return AccountModel(**defaults)


class TestOrmToAccount:
    def test_platform_reconstructed(self):
        account = orm_to_account(_make_orm_account(platform="MT5"))
        assert account.platform == Platform.MT5

    def test_challenge_phase_reconstructed(self):
        account = orm_to_account(_make_orm_account())
        assert account.challenge_phase == ChallengePhase.PHASE_1

    def test_challenge_phase_none(self):
        account = orm_to_account(_make_orm_account(challenge_phase=None))
        assert account.challenge_phase is None

    def test_basic_fields(self):
        account = orm_to_account(_make_orm_account())
        assert account.account_id == "ACC001"
        assert account.broker == "FTMO"
        assert account.starting_balance == pytest.approx(10000.0)
        assert account.account_currency == "USD"


# ── Round-trip tests ──────────────────────────────────────────────────────────

class TestRoundTrip:
    def test_trade_round_trip(self):
        original = make_trade()
        orm = trade_to_orm(original, import_run_id="run-001")
        reconstructed = orm_to_trade(orm)

        assert reconstructed.trade_id == original.trade_id
        assert reconstructed.asset_class == original.asset_class
        assert reconstructed.direction == original.direction
        assert reconstructed.result == original.result
        assert reconstructed.platform == original.platform
        assert reconstructed.holding_duration == original.holding_duration
        assert reconstructed.mistake_tags == original.mistake_tags
        assert reconstructed.net_pnl == pytest.approx(original.net_pnl)
        assert reconstructed.followed_plan == original.followed_plan

    def test_trade_round_trip_empty_mistake_tags(self):
        """Empty mistake_tags → None in ORM → [] in Trade."""
        original = make_trade(mistake_tags=[])
        orm = trade_to_orm(original)
        assert orm.mistake_tags is None  # stored as NULL
        reconstructed = orm_to_trade(orm)
        assert reconstructed.mistake_tags == []  # restored to empty list

    def test_account_round_trip(self):
        original = make_account()
        orm = account_to_orm(original)
        reconstructed = orm_to_account(orm)

        assert reconstructed.account_id == original.account_id
        assert reconstructed.broker == original.broker
        assert reconstructed.platform == original.platform
        assert reconstructed.challenge_phase == original.challenge_phase
        assert reconstructed.starting_balance == pytest.approx(original.starting_balance)
        assert reconstructed.created_at == original.created_at

    def test_account_round_trip_no_phase(self):
        original = make_account(challenge_phase=None, prop_firm=None)
        orm = account_to_orm(original)
        reconstructed = orm_to_account(orm)
        assert reconstructed.challenge_phase is None
        assert reconstructed.prop_firm is None
