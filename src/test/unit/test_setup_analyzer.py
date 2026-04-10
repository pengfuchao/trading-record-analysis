"""
Unit tests for SetupAnalyzer — no database required.
All tests use plain Trade dataclasses.
"""
from datetime import datetime, timedelta

import pytest

from src.main.python.core.setup_analyzer import SetupAnalyzer
from src.main.python.models.enums import TradeResult
from src.main.python.models.trade import Trade

analyzer = SetupAnalyzer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_trade(
    trade_id: str = "T001",
    account_id: str = "ACC001",
    setup_type: str = "BOS",
    result: TradeResult = TradeResult.WIN,
    net_pnl: float = 100.0,
    actual_r_multiple: float = 2.0,
    session: str = "London",
    symbol: str = "EURUSD",
    market_condition: str = "Trending",
    exit_datetime: datetime = None,
    holding_duration: timedelta = None,
    is_a_plus_setup: bool = None,
    followed_plan: bool = None,
    mistake_tags=None,
    **flags,
) -> Trade:
    return Trade(
        trade_id=trade_id,
        account_id=account_id,
        setup_type=setup_type,
        result=result,
        net_pnl=net_pnl,
        actual_r_multiple=actual_r_multiple,
        session=session,
        symbol=symbol,
        market_condition=market_condition,
        exit_datetime=exit_datetime or datetime(2024, 1, 15, 10, 0),
        holding_duration=holding_duration,
        is_a_plus_setup=is_a_plus_setup,
        followed_plan=followed_plan,
        mistake_tags=mistake_tags or [],
        **flags,
    )


# ── Empty / no setup ──────────────────────────────────────────────────────────

def test_empty_trades():
    report = analyzer.generate_report([], "ACC001")
    assert report.account_id == "ACC001"
    assert report.total_trades_analyzed == 0
    assert report.by_setup == {}
    assert report.ranked_by_win_rate == []


def test_trades_without_setup_excluded():
    trades = [
        make_trade("T1", setup_type=None),
        make_trade("T2", setup_type=""),
        make_trade("T3", setup_type="BOS"),
    ]
    trades[0].setup_type = None
    report = analyzer.generate_report(trades, "ACC001")
    assert report.total_trades_analyzed == 3
    assert report.trades_with_setup == 1
    assert "BOS" in report.by_setup
    assert len(report.by_setup) == 1


def test_all_trades_without_setup():
    trades = [make_trade("T1", setup_type=None), make_trade("T2", setup_type=None)]
    for t in trades:
        t.setup_type = None
    report = analyzer.generate_report(trades, "ACC001")
    assert report.trades_with_setup == 0
    assert report.by_setup == {}


# ── Basic metrics ─────────────────────────────────────────────────────────────

def test_basic_win_rate():
    trades = [
        make_trade("T1", result=TradeResult.WIN),
        make_trade("T2", result=TradeResult.WIN),
        make_trade("T3", result=TradeResult.LOSS),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].win_rate == pytest.approx(2 / 3)
    assert report.by_setup["BOS"].loss_rate == pytest.approx(1 / 3)


def test_expectancy():
    trades = [
        make_trade("T1", net_pnl=200.0),
        make_trade("T2", net_pnl=-50.0, result=TradeResult.LOSS),
        make_trade("T3", net_pnl=100.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].expectancy == pytest.approx(250.0 / 3)
    assert report.by_setup["BOS"].total_net_profit == pytest.approx(250.0)


def test_avg_r_multiple():
    trades = [
        make_trade("T1", actual_r_multiple=2.0),
        make_trade("T2", actual_r_multiple=1.0),
        make_trade("T3", actual_r_multiple=None),  # None excluded
    ]
    trades[2].actual_r_multiple = None
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].avg_r_multiple == pytest.approx(1.5)


def test_profit_factor():
    trades = [
        make_trade("T1", net_pnl=300.0, result=TradeResult.WIN),
        make_trade("T2", net_pnl=-100.0, result=TradeResult.LOSS),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].profit_factor == pytest.approx(3.0)


def test_max_consecutive_losses():
    trades = [
        make_trade("T1", result=TradeResult.LOSS, net_pnl=-50.0),
        make_trade("T2", result=TradeResult.LOSS, net_pnl=-50.0),
        make_trade("T3", result=TradeResult.WIN,  net_pnl=100.0),
        make_trade("T4", result=TradeResult.LOSS, net_pnl=-50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].max_consecutive_losses == 2


def test_avg_holding_duration():
    trades = [
        make_trade("T1", holding_duration=timedelta(hours=2)),
        make_trade("T2", holding_duration=timedelta(hours=4)),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].avg_holding_duration_seconds == pytest.approx(3 * 3600)


# ── Ranking ───────────────────────────────────────────────────────────────────

def test_ranked_by_win_rate():
    trades = [
        make_trade("T1", setup_type="BOS",  result=TradeResult.WIN, net_pnl=100.0),
        make_trade("T2", setup_type="BOS",  result=TradeResult.WIN, net_pnl=100.0),
        make_trade("T3", setup_type="FVGR", result=TradeResult.WIN, net_pnl=100.0),
        make_trade("T4", setup_type="FVGR", result=TradeResult.LOSS, net_pnl=-50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.ranked_by_win_rate[0] == "BOS"   # 100% win rate
    assert report.ranked_by_win_rate[1] == "FVGR"  # 50% win rate


def test_ranked_by_expectancy():
    trades = [
        make_trade("T1", setup_type="BOS",  net_pnl=200.0),
        make_trade("T2", setup_type="FVGR", net_pnl=50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.ranked_by_expectancy[0] == "BOS"


def test_ranked_by_avg_r():
    trades = [
        make_trade("T1", setup_type="BOS",  actual_r_multiple=3.0),
        make_trade("T2", setup_type="FVGR", actual_r_multiple=1.5),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.ranked_by_avg_r[0] == "BOS"


def test_ranked_by_total_profit():
    trades = [
        make_trade("T1", setup_type="BOS",  net_pnl=500.0),
        make_trade("T2", setup_type="FVGR", net_pnl=100.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.ranked_by_total_profit[0] == "BOS"


def test_ranked_by_drawdown():
    trades = [
        make_trade("T1", setup_type="BOS",  result=TradeResult.LOSS, net_pnl=-200.0),
        make_trade("T2", setup_type="FVGR", result=TradeResult.LOSS, net_pnl=-50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    # BOS has worse (more negative) drawdown → ranked first
    assert report.ranked_by_drawdown[0] == "BOS"


# ── Condition breakdowns ──────────────────────────────────────────────────────

def test_by_session_win_rate():
    trades = [
        make_trade("T1", session="London",   result=TradeResult.WIN),
        make_trade("T2", session="London",   result=TradeResult.WIN),
        make_trade("T3", session="New York", result=TradeResult.LOSS, net_pnl=-50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    by_session = report.by_setup["BOS"].by_session
    assert by_session["London"] == pytest.approx(1.0)
    assert by_session["New York"] == pytest.approx(0.0)


def test_best_worst_session():
    trades = [
        make_trade("T1", session="London",   result=TradeResult.WIN),
        make_trade("T2", session="London",   result=TradeResult.WIN),
        make_trade("T3", session="New York", result=TradeResult.LOSS, net_pnl=-50.0),
        make_trade("T4", session="New York", result=TradeResult.LOSS, net_pnl=-50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    stats = report.by_setup["BOS"]
    assert stats.best_session == "London"
    assert stats.worst_session == "New York"


def test_best_worst_requires_min_trades():
    """A segment with only 1 trade should not qualify as best/worst."""
    trades = [
        make_trade("T1", session="London",   result=TradeResult.WIN),
        make_trade("T2", session="London",   result=TradeResult.WIN),
        make_trade("T3", session="New York", result=TradeResult.WIN),  # only 1
    ]
    report = analyzer.generate_report(trades, "ACC001")
    stats = report.by_setup["BOS"]
    # Only London has ≥2 trades; New York has 1 → excluded
    assert stats.best_session == "London"
    assert stats.worst_session == "London"  # only qualified segment


def test_by_market_condition_win_rate():
    trades = [
        make_trade("T1", market_condition="Trending", result=TradeResult.WIN),
        make_trade("T2", market_condition="Trending", result=TradeResult.WIN),
        make_trade("T3", market_condition="Ranging",  result=TradeResult.LOSS, net_pnl=-50.0),
        make_trade("T4", market_condition="Ranging",  result=TradeResult.LOSS, net_pnl=-50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    stats = report.by_setup["BOS"]
    assert stats.best_market_condition == "Trending"
    assert stats.worst_market_condition == "Ranging"


# ── Execution quality ─────────────────────────────────────────────────────────

def test_a_plus_rate():
    trades = [
        make_trade("T1", is_a_plus_setup=True),
        make_trade("T2", is_a_plus_setup=True),
        make_trade("T3", is_a_plus_setup=False),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].a_plus_rate == pytest.approx(2 / 3)


def test_followed_plan_rate():
    trades = [
        make_trade("T1", followed_plan=True),
        make_trade("T2", followed_plan=False),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].followed_plan_rate == pytest.approx(0.5)


# ── Common mistakes ───────────────────────────────────────────────────────────

def test_common_mistakes_from_flags():
    trades = [
        make_trade("T1", fomo=True),
        make_trade("T2", fomo=True, chasing=True),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    cm = report.by_setup["BOS"].common_mistakes
    assert cm["fomo"] == 2
    assert cm["chasing"] == 1


def test_common_mistakes_from_tags():
    trades = [
        make_trade("T1", mistake_tags=["poor_location"]),
        make_trade("T2", mistake_tags=["poor_location", "late_entry"]),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    cm = report.by_setup["BOS"].common_mistakes
    assert cm["poor_location"] == 2
    assert cm["late_entry"] == 1


def test_common_mistakes_empty_when_clean():
    trades = [make_trade("T1"), make_trade("T2")]
    report = analyzer.generate_report(trades, "ACC001")
    assert report.by_setup["BOS"].common_mistakes == {}


# ── Isolation between setups ──────────────────────────────────────────────────

def test_multiple_setups_isolated():
    trades = [
        make_trade("T1", setup_type="BOS",  result=TradeResult.WIN,  net_pnl=200.0),
        make_trade("T2", setup_type="BOS",  result=TradeResult.WIN,  net_pnl=100.0),
        make_trade("T3", setup_type="FVGR", result=TradeResult.LOSS, net_pnl=-50.0),
    ]
    report = analyzer.generate_report(trades, "ACC001")
    bos = report.by_setup["BOS"]
    fvgr = report.by_setup["FVGR"]

    assert bos.trade_count == 2
    assert fvgr.trade_count == 1
    assert bos.win_rate == pytest.approx(1.0)
    assert fvgr.win_rate == pytest.approx(0.0)
    assert bos.total_net_profit == pytest.approx(300.0)
    assert fvgr.total_net_profit == pytest.approx(-50.0)
