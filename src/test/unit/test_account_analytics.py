from datetime import datetime, timedelta
from typing import Optional

import pytest

from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.core.performance_summary import AccountReport, PerformanceSummary
from src.main.python.models.account import Account
from src.main.python.models.enums import AssetClass, Direction, Platform, TradeResult
from src.main.python.models.trade import Trade


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_trade(
    trade_id: str,
    net_pnl: float,
    result: TradeResult,
    exit_dt: datetime,
    symbol: str = "EURUSD",
    direction: Direction = Direction.LONG,
    asset_class: AssetClass = AssetClass.FOREX,
    session: Optional[str] = None,
    followed_plan: Optional[bool] = None,
    gross_pnl: Optional[float] = None,
    lot_size: float = 0.10,
    entry_dt: Optional[datetime] = None,
) -> Trade:
    return Trade(
        trade_id=trade_id,
        account_id="TEST",
        symbol=symbol,
        direction=direction,
        asset_class=asset_class,
        result=result,
        net_pnl=net_pnl,
        gross_pnl=gross_pnl if gross_pnl is not None else net_pnl,
        exit_datetime=exit_dt,
        entry_datetime=entry_dt or (exit_dt - timedelta(hours=2)),
        holding_duration=timedelta(hours=2),
        lot_size=lot_size,
        session=session,
        followed_plan=followed_plan,
    )


@pytest.fixture
def account():
    return Account(
        account_id="TEST",
        broker="FTMO",
        platform=Platform.MT5,
        starting_balance=10000.0,
    )


@pytest.fixture
def five_trades():
    base = datetime(2024, 1, 15, 12, 0)
    return [
        make_trade("T1", 100.0, TradeResult.WIN, base + timedelta(days=0), session="London"),
        make_trade("T2", 150.0, TradeResult.WIN, base + timedelta(days=1), session="New York"),
        make_trade("T3", -80.0, TradeResult.LOSS, base + timedelta(days=2), symbol="XAUUSD", asset_class=AssetClass.GOLD, session="London"),
        make_trade("T4", 200.0, TradeResult.WIN, base + timedelta(days=3), direction=Direction.SHORT, followed_plan=True),
        make_trade("T5", -60.0, TradeResult.LOSS, base + timedelta(days=4), followed_plan=False),
    ]


# ── Empty Trade List ─────────────────────────────────────────────────────────

class TestEmptyTrades:
    def test_returns_account_report(self, account):
        report = AccountAnalytics.generate_report([], account)
        assert isinstance(report, AccountReport)

    def test_account_id_set(self, account):
        report = AccountAnalytics.generate_report([], account)
        assert report.account_id == "TEST"

    def test_equity_curve_empty(self, account):
        report = AccountAnalytics.generate_report([], account)
        assert report.equity_curve == []

    def test_overall_total_trades_zero(self, account):
        report = AccountAnalytics.generate_report([], account)
        assert report.overall.total_trades == 0


# ── Basic Report ─────────────────────────────────────────────────────────────

class TestBasicReport:
    def test_returns_account_report_type(self, five_trades, account):
        assert isinstance(AccountAnalytics.generate_report(five_trades, account), AccountReport)

    def test_overall_total_trades(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.overall.total_trades == 5

    def test_overall_win_rate(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.overall.win_rate == pytest.approx(3 / 5)

    def test_equity_curve_length(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert len(report.equity_curve) == 5

    def test_drawdown_curve_length(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert len(report.drawdown_curve) == 5

    def test_trade_dates_length(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert len(report.trade_dates) == 5

    def test_equity_starts_from_starting_balance(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.equity_curve[0] == pytest.approx(10000.0 + 100.0)

    def test_total_net_profit(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.overall.total_net_profit == pytest.approx(310.0)

    def test_total_return_pct(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.overall.total_return_pct == pytest.approx(3.1)

    def test_max_drawdown_is_negative_or_zero(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.overall.max_drawdown <= 0

    def test_profit_factor_positive(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.overall.profit_factor > 0

    def test_winning_losing_counts(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert report.overall.winning_trades == 3
        assert report.overall.losing_trades == 2


# ── Segmentation ─────────────────────────────────────────────────────────────

class TestSegmentation:
    def test_by_symbol_keys(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert "EURUSD" in report.by_symbol
        assert "XAUUSD" in report.by_symbol

    def test_by_direction_keys(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert "Long" in report.by_direction
        assert "Short" in report.by_direction

    def test_by_session_keys(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert "London" in report.by_session
        assert "New York" in report.by_session

    def test_by_weekday_keys_are_day_names(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        for key in report.by_weekday:
            assert key in valid_days

    def test_by_month_keys_are_yyyy_mm(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        for key in report.by_month:
            assert len(key) == 7  # YYYY-MM
            assert key[4] == "-"

    def test_by_followed_plan_has_none_key(self, five_trades, account):
        # T1, T2, T3 have followed_plan=None
        report = AccountAnalytics.generate_report(five_trades, account)
        assert "None" in report.by_followed_plan

    def test_by_followed_plan_true_false_keys(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert "True" in report.by_followed_plan
        assert "False" in report.by_followed_plan

    def test_segment_trade_counts_sum_to_total(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        total = sum(s.total_trades for s in report.by_symbol.values())
        assert total == report.overall.total_trades

    def test_segment_return_pct_is_none(self, five_trades, account):
        # Segments use starting_balance=0 → total_return_pct should be None
        report = AccountAnalytics.generate_report(five_trades, account)
        for seg in report.by_symbol.values():
            assert seg.total_return_pct is None

    def test_by_result_has_win_loss_keys(self, five_trades, account):
        report = AccountAnalytics.generate_report(five_trades, account)
        assert "Win" in report.by_result
        assert "Loss" in report.by_result


# ── Sorting & Edge Cases ─────────────────────────────────────────────────────

class TestSortingAndEdgeCases:
    def test_trades_sorted_by_exit_datetime(self, account):
        base = datetime(2024, 1, 15, 12, 0)
        # Provide trades in reverse order
        trades = [
            make_trade("T3", 100.0, TradeResult.WIN, base + timedelta(days=2)),
            make_trade("T1", -50.0, TradeResult.LOSS, base + timedelta(days=0)),
            make_trade("T2", 80.0, TradeResult.WIN, base + timedelta(days=1)),
        ]
        report = AccountAnalytics.generate_report(trades, account)
        # First equity point should be 10000 + (-50) = 9950, not 10100
        assert report.equity_curve[0] == pytest.approx(9950.0)

    def test_trade_with_none_exit_datetime_excluded(self, account):
        base = datetime(2024, 1, 15)
        trades = [
            make_trade("T1", 100.0, TradeResult.WIN, base),
            Trade(trade_id="T2", account_id="TEST", net_pnl=200.0, exit_datetime=None),
        ]
        report = AccountAnalytics.generate_report(trades, account)
        assert report.overall.total_trades == 1

    def test_single_trade_sharpe_is_none(self, account):
        base = datetime(2024, 1, 15)
        trades = [make_trade("T1", 100.0, TradeResult.WIN, base)]
        report = AccountAnalytics.generate_report(trades, account)
        assert report.overall.sharpe_ratio is None

    def test_all_wins_profit_factor_is_none(self, account):
        base = datetime(2024, 1, 15)
        trades = [
            make_trade("T1", 100.0, TradeResult.WIN, base + timedelta(days=i))
            for i in range(3)
        ]
        report = AccountAnalytics.generate_report(trades, account)
        assert report.overall.profit_factor is None

    def test_zero_starting_balance_return_pct_is_none(self):
        acct = Account(account_id="X", broker="B", platform=Platform.MT5, starting_balance=0.0)
        base = datetime(2024, 1, 15)
        trades = [make_trade("T1", 100.0, TradeResult.WIN, base)]
        report = AccountAnalytics.generate_report(trades, acct)
        assert report.overall.total_return_pct is None
