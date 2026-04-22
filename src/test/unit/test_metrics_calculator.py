import math
import statistics
from datetime import datetime, timedelta
from typing import List

import pytest

from src.main.python.core.metrics_calculator import MetricsCalculator
from src.main.python.models.enums import TradeResult

MC = MetricsCalculator
W, L, B = TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN


# ── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def standard_results():
    return [W, W, L, W, L, B, W]  # 4W 2L 1B


@pytest.fixture
def standard_pnls():
    return [100.0, 150.0, -80.0, 200.0, -60.0, 0.0, 120.0]


@pytest.fixture
def standard_exits():
    base = datetime(2024, 1, 2, 12, 0)
    return [base + timedelta(days=i) for i in range(7)]


# ── Win/Loss/Breakeven Rates ─────────────────────────────────────────────────

class TestRates:
    def test_win_rate_basic(self, standard_results):
        assert MC.win_rate(standard_results) == pytest.approx(4 / 7)

    def test_loss_rate_basic(self, standard_results):
        assert MC.loss_rate(standard_results) == pytest.approx(2 / 7)

    def test_breakeven_rate_basic(self, standard_results):
        assert MC.breakeven_rate(standard_results) == pytest.approx(1 / 7)

    def test_rates_sum_to_one(self, standard_results):
        total = (
            MC.win_rate(standard_results)
            + MC.loss_rate(standard_results)
            + MC.breakeven_rate(standard_results)
        )
        assert total == pytest.approx(1.0)

    def test_empty_returns_none(self):
        assert MC.win_rate([]) is None
        assert MC.loss_rate([]) is None
        assert MC.breakeven_rate([]) is None

    def test_all_wins(self):
        assert MC.win_rate([W, W, W]) == pytest.approx(1.0)

    def test_all_losses_win_rate_zero(self):
        assert MC.win_rate([L, L]) == pytest.approx(0.0)

    def test_breakeven_not_counted_as_win(self):
        assert MC.win_rate([B, B]) == pytest.approx(0.0)


# ── PnL Averages & Ratios ────────────────────────────────────────────────────

class TestPnLAverages:
    def test_avg_win(self, standard_pnls, standard_results):
        # wins: 100, 150, 200, 120 → mean = 142.5
        assert MC.avg_win(standard_pnls, standard_results) == pytest.approx(142.5)

    def test_avg_loss(self, standard_pnls, standard_results):
        # losses: -80, -60 → mean = -70
        assert MC.avg_loss(standard_pnls, standard_results) == pytest.approx(-70.0)

    def test_avg_win_no_wins_returns_none(self):
        assert MC.avg_win([-10.0, -20.0], [L, L]) is None

    def test_avg_loss_no_losses_returns_none(self):
        assert MC.avg_loss([10.0, 20.0], [W, W]) is None

    def test_payoff_ratio(self, standard_pnls, standard_results):
        # abs(142.5) / abs(-70) ≈ 2.036
        assert MC.payoff_ratio(standard_pnls, standard_results) == pytest.approx(
            142.5 / 70.0, rel=1e-3
        )

    def test_payoff_ratio_no_losses_returns_none(self):
        assert MC.payoff_ratio([10.0, 20.0], [W, W]) is None

    def test_avg_r_multiple_skips_none(self):
        assert MC.avg_r_multiple([1.0, None, 2.0, None]) == pytest.approx(1.5)

    def test_avg_r_multiple_all_none_returns_none(self):
        assert MC.avg_r_multiple([None, None]) is None


# ── Profit Factor & Expectancy ───────────────────────────────────────────────

class TestProfitFactorExpectancy:
    def test_profit_factor_basic(self, standard_pnls, standard_results):
        # gross_profit = 100+150+200+120 = 570, gross_loss = 80+60 = 140
        assert MC.profit_factor(standard_pnls, standard_results) == pytest.approx(570 / 140)

    def test_profit_factor_no_losses_returns_none(self):
        assert MC.profit_factor([10.0, 20.0], [W, W]) is None

    def test_profit_factor_no_wins_returns_none(self):
        assert MC.profit_factor([-10.0, -20.0], [L, L]) is None

    def test_profit_factor_empty_returns_none(self):
        assert MC.profit_factor([], []) is None

    def test_expectancy_basic(self, standard_pnls, standard_results):
        wr = 4 / 7
        lr = 2 / 7
        aw = 142.5
        al = -70.0
        expected = (wr * aw) + (lr * al)
        assert MC.expectancy(standard_pnls, standard_results) == pytest.approx(expected)

    def test_expectancy_empty_returns_none(self):
        assert MC.expectancy([], []) is None


# ── Sharpe & Sortino ─────────────────────────────────────────────────────────

class TestRiskAdjusted:
    def test_sharpe_returns_float(self, standard_pnls, standard_exits):
        result = MC.sharpe_ratio(standard_pnls, standard_exits)
        assert isinstance(result, float)

    def test_sharpe_single_trade_returns_none(self, standard_exits):
        assert MC.sharpe_ratio([100.0], standard_exits[:1]) is None

    def test_sharpe_zero_std_returns_none(self, standard_exits):
        # All same PnL → std = 0
        assert MC.sharpe_ratio([50.0, 50.0, 50.0], standard_exits[:3]) is None

    def test_sharpe_empty_returns_none(self):
        assert MC.sharpe_ratio([], []) is None

    def test_sortino_basic(self, standard_pnls, standard_exits):
        result = MC.sortino_ratio(standard_pnls, standard_exits)
        assert isinstance(result, float)

    def test_sortino_no_losses_returns_none(self, standard_exits):
        # No downside returns
        assert MC.sortino_ratio([10.0, 20.0, 30.0], standard_exits[:3]) is None

    def test_std_returns_basic(self, standard_pnls):
        expected = statistics.stdev(standard_pnls)
        assert MC.std_returns(standard_pnls) == pytest.approx(expected)

    def test_std_returns_single_returns_none(self):
        assert MC.std_returns([100.0]) is None


# ── Equity Curve & Drawdown ──────────────────────────────────────────────────

class TestEquityAndDrawdown:
    def test_equity_curve_length(self, standard_pnls):
        eq = MC.equity_curve(standard_pnls, 10000.0)
        assert len(eq) == len(standard_pnls)

    def test_equity_curve_first_value(self):
        eq = MC.equity_curve([100.0, -50.0, 200.0], 10000.0)
        assert eq[0] == pytest.approx(10100.0)

    def test_equity_curve_last_value(self, standard_pnls):
        eq = MC.equity_curve(standard_pnls, 10000.0)
        assert eq[-1] == pytest.approx(10000.0 + sum(standard_pnls))

    def test_equity_curve_empty(self):
        assert MC.equity_curve([], 10000.0) == []

    def test_drawdown_curve_all_lte_zero(self, standard_pnls):
        eq = MC.equity_curve(standard_pnls, 10000.0)
        dd = MC.drawdown_curve(eq)
        assert all(v <= 0 for v in dd)

    def test_drawdown_curve_length(self, standard_pnls):
        eq = MC.equity_curve(standard_pnls, 10000.0)
        dd = MC.drawdown_curve(eq)
        assert len(dd) == len(eq)

    def test_drawdown_resets_at_new_peak(self):
        # Equity goes 100, 150, 120, 200 — resets at 200
        eq = [100.0, 150.0, 120.0, 200.0]
        dd = MC.drawdown_curve(eq)
        assert dd[-1] == pytest.approx(0.0)

    def test_max_drawdown_monotonic_increase(self):
        eq = [100.0, 150.0, 200.0, 250.0]
        dd = MC.drawdown_curve(eq)
        assert MC.max_drawdown(dd) == pytest.approx(0.0)

    def test_max_drawdown_standard(self):
        eq = [100.0, 150.0, 90.0, 120.0, 80.0, 200.0]
        dd = MC.drawdown_curve(eq)
        # Peak=150, min equity=80 → dd = 80-150 = -70
        assert MC.max_drawdown(dd) == pytest.approx(-70.0)

    def test_max_drawdown_empty_returns_none(self):
        assert MC.max_drawdown([]) is None

    def test_max_drawdown_pct(self):
        eq = [100.0, 150.0, 90.0]
        dd = MC.drawdown_curve(eq)
        # Peak=150, dd at idx 2 = 90-150 = -60 → pct = -60/150*100 = -40%
        assert MC.max_drawdown_pct(dd, eq) == pytest.approx(-40.0)


# ── Period Drawdown ──────────────────────────────────────────────────────────

class TestPeriodDrawdown:
    def _make_exits_on_days(self, days_offsets):
        base = datetime(2024, 1, 15, 12, 0)
        return [base + timedelta(days=d) for d in days_offsets]

    def test_daily_drawdown_same_day_summed(self):
        # Two trades on same day: -30 and -20 → daily sum = -50
        exits = [datetime(2024, 1, 15, 10), datetime(2024, 1, 15, 14)]
        result = MetricsCalculator.daily_drawdown([-30.0, -20.0], exits)
        assert result == pytest.approx(-50.0)

    def test_daily_drawdown_win_and_loss_same_day_net(self):
        exits = [datetime(2024, 1, 15, 10), datetime(2024, 1, 15, 14)]
        result = MetricsCalculator.daily_drawdown([100.0, -30.0], exits)
        assert result == pytest.approx(70.0)

    def test_daily_drawdown_all_wins_positive(self):
        exits = [datetime(2024, 1, 15), datetime(2024, 1, 16)]
        result = MetricsCalculator.daily_drawdown([50.0, 80.0], exits)
        assert result > 0

    def test_daily_drawdown_empty_returns_none(self):
        assert MetricsCalculator.daily_drawdown([], []) is None

    def test_weekly_drawdown_groups_correctly(self):
        # Two trades in same week
        exits = [datetime(2024, 1, 15), datetime(2024, 1, 17)]
        result = MetricsCalculator.weekly_drawdown([-30.0, -20.0], exits)
        assert result == pytest.approx(-50.0)

    def test_monthly_drawdown_groups_correctly(self):
        exits = [datetime(2024, 1, 10), datetime(2024, 1, 25), datetime(2024, 2, 5)]
        pnls = [-40.0, -60.0, 100.0]
        result = MetricsCalculator.monthly_drawdown(pnls, exits)
        # Jan: -100, Feb: +100 → worst = -100
        assert result == pytest.approx(-100.0)


# ── Consecutive Streaks ──────────────────────────────────────────────────────

class TestStreaks:
    def test_max_consecutive_wins(self):
        assert MC.max_consecutive_wins([W, W, L, W, W, W, L]) == 3

    def test_max_consecutive_losses(self):
        assert MC.max_consecutive_losses([W, L, L, L, W, L]) == 3

    def test_max_consecutive_wins_empty(self):
        assert MC.max_consecutive_wins([]) == 0

    def test_max_consecutive_wins_no_wins(self):
        assert MC.max_consecutive_wins([L, L, B]) == 0

    def test_avg_losing_streak(self):
        # Streaks: LL (2) and L (1) → avg = 1.5
        results = [W, L, L, W, L, W]
        assert MC.avg_losing_streak(results) == pytest.approx(1.5)

    def test_avg_losing_streak_no_losses_returns_none(self):
        assert MC.avg_losing_streak([W, W, B]) is None

    def test_avg_losing_streak_trailing_streak(self):
        # Streak at end: LLL
        results = [W, L, L, L]
        assert MC.avg_losing_streak(results) == pytest.approx(3.0)


# ── Duration & Frequency ────────────────────────────────────────────────────

class TestDurationFrequency:
    def test_avg_holding_duration(self):
        durations = [timedelta(hours=2), timedelta(hours=4)]
        result = MC.avg_holding_duration(durations)
        assert result == timedelta(hours=3)

    def test_avg_holding_duration_empty_returns_none(self):
        assert MC.avg_holding_duration([]) is None

    def test_trades_per_day_basic(self, standard_exits):
        # 7 trades over 6 days → ≈ 1.17 trades/day
        result = MC.trades_per_day(standard_exits)
        assert isinstance(result, float)
        assert result > 0

    def test_trades_per_day_single_trade_returns_none(self, standard_exits):
        assert MC.trades_per_day(standard_exits[:1]) is None

    def test_trades_per_week_basic(self, standard_exits):
        result = MC.trades_per_week(standard_exits)
        assert result is not None and result > 0

    def test_trades_per_month_basic(self, standard_exits):
        result = MC.trades_per_month(standard_exits)
        assert result is not None and result > 0


# ── Account Totals ───────────────────────────────────────────────────────────

class TestAccountTotals:
    def test_total_net_profit(self, standard_pnls):
        assert MC.total_net_profit(standard_pnls) == pytest.approx(sum(standard_pnls))

    def test_total_gross_profit(self, standard_pnls, standard_results):
        assert MC.total_gross_profit(standard_pnls, standard_results) == pytest.approx(570.0)

    def test_total_gross_loss(self, standard_pnls, standard_results):
        assert MC.total_gross_loss(standard_pnls, standard_results) == pytest.approx(-140.0)

    def test_total_return_pct(self):
        assert MC.total_return_pct(1000.0, 10000.0) == pytest.approx(10.0)

    def test_total_return_pct_zero_balance_returns_none(self):
        assert MC.total_return_pct(1000.0, 0.0) is None

    def test_largest_single_loss(self, standard_pnls, standard_results):
        assert MC.largest_single_loss(standard_pnls, standard_results) == pytest.approx(-80.0)

    def test_largest_single_loss_no_losses_returns_none(self):
        assert MC.largest_single_loss([10.0, 20.0], [W, W]) is None


# ── Exposure ─────────────────────────────────────────────────────────────────

class TestExposure:
    def test_exposure_by_symbol_sums_lots(self):
        result = MC.exposure_by_symbol(
            ["EURUSD", "XAUUSD", "EURUSD"], [0.10, 0.05, 0.20]
        )
        assert result["EURUSD"] == pytest.approx(0.30)
        assert result["XAUUSD"] == pytest.approx(0.05)

    def test_exposure_skips_none_symbol(self):
        result = MC.exposure_by_symbol([None, "EURUSD"], [0.10, 0.20])
        assert "None" not in result
        assert result["EURUSD"] == pytest.approx(0.20)

    def test_exposure_skips_none_lot(self):
        result = MC.exposure_by_symbol(["EURUSD", "EURUSD"], [None, 0.20])
        assert result["EURUSD"] == pytest.approx(0.20)

    def test_exposure_by_direction(self):
        result = MC.exposure_by_direction(["Long", "Short", "Long"], [0.10, 0.05, 0.10])
        assert result["Long"] == pytest.approx(0.20)
        assert result["Short"] == pytest.approx(0.05)


# ── Recovery Factor & Calmar ─────────────────────────────────────────────────

class TestRecoveryAndCalmar:
    def test_recovery_factor_basic(self):
        assert MC.recovery_factor(500.0, -100.0) == pytest.approx(5.0)

    def test_recovery_factor_zero_drawdown_returns_none(self):
        assert MC.recovery_factor(500.0, 0.0) is None

    def test_recovery_factor_none_drawdown_returns_none(self):
        assert MC.recovery_factor(500.0, None) is None

    def test_calmar_ratio_basic(self, standard_exits):
        result = MC.calmar_ratio([50.0] * 7, standard_exits, -100.0)
        assert isinstance(result, float)

    def test_calmar_ratio_zero_drawdown_returns_none(self, standard_exits):
        assert MC.calmar_ratio([50.0] * 7, standard_exits, 0.0) is None

    def test_calmar_ratio_none_drawdown_returns_none(self, standard_exits):
        assert MC.calmar_ratio([50.0] * 7, standard_exits, None) is None

    def test_calmar_ratio_single_trade_returns_none(self):
        assert MC.calmar_ratio([50.0], [datetime(2024, 1, 1)], -100.0) is None
