from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import groupby
from typing import Dict, List, Optional

from src.main.python.models.enums import TradeResult
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ── Internal helpers ────────────────────────────────────────────────────────────

def _annualization_factor(exit_datetimes: List[datetime]) -> float:
    """Return sqrt(252 / avg_trading_days_between_trades), fallback sqrt(252)."""
    if len(exit_datetimes) < 2:
        return math.sqrt(252)
    sorted_dts = sorted(exit_datetimes)
    total_days = (sorted_dts[-1] - sorted_dts[0]).days
    avg_days = total_days / (len(exit_datetimes) - 1)
    if avg_days <= 0:
        return math.sqrt(252)
    return math.sqrt(252 / avg_days)


def _group_pnl_by_period(
    pnls: List[float], exit_datetimes: List[datetime], period: str
) -> Dict[str, float]:
    """
    Group net PnLs by calendar period, return {period_key: sum_pnl}.
    period: "day"  → YYYY-MM-DD
            "week" → YYYY-Www (ISO week)
            "month"→ YYYY-MM
    """
    grouped: Dict[str, float] = defaultdict(float)
    for pnl, dt in zip(pnls, exit_datetimes):
        if dt is None:
            continue
        if period == "day":
            key = dt.strftime("%Y-%m-%d")
        elif period == "week":
            key = dt.strftime("%G-W%V")
        else:  # month
            key = dt.strftime("%Y-%m")
        grouped[key] += pnl
    return dict(grouped)


class MetricsCalculator:
    """
    Pure computation class. All methods are @staticmethod and accept plain Python
    lists — no Trade objects. This keeps the math fully unit-testable in isolation.
    """

    # ── Rates ───────────────────────────────────────────────────────────────────

    @staticmethod
    def win_rate(results: List[TradeResult]) -> Optional[float]:
        if not results:
            return None
        return sum(1 for r in results if r == TradeResult.WIN) / len(results)

    @staticmethod
    def win_rate_ex_be(results: List[TradeResult]) -> Optional[float]:
        """Win rate excluding breakeven trades: wins / (wins + losses).

        More meaningful than win_rate when many breakeven trades exist (e.g.
        tight-stop scalping where commissions often push small wins to BE).
        """
        decided = [r for r in results if r in (TradeResult.WIN, TradeResult.LOSS)]
        if not decided:
            return None
        return sum(1 for r in decided if r == TradeResult.WIN) / len(decided)

    @staticmethod
    def loss_rate(results: List[TradeResult]) -> Optional[float]:
        if not results:
            return None
        return sum(1 for r in results if r == TradeResult.LOSS) / len(results)

    @staticmethod
    def breakeven_rate(results: List[TradeResult]) -> Optional[float]:
        if not results:
            return None
        return sum(1 for r in results if r == TradeResult.BREAKEVEN) / len(results)

    # ── PnL Averages ────────────────────────────────────────────────────────────

    @staticmethod
    def avg_win(pnls: List[float], results: List[TradeResult]) -> Optional[float]:
        wins = [p for p, r in zip(pnls, results) if r == TradeResult.WIN]
        return statistics.mean(wins) if wins else None

    @staticmethod
    def avg_loss(pnls: List[float], results: List[TradeResult]) -> Optional[float]:
        losses = [p for p, r in zip(pnls, results) if r == TradeResult.LOSS]
        return statistics.mean(losses) if losses else None

    @staticmethod
    def avg_r_multiple(r_multiples: List[Optional[float]]) -> Optional[float]:
        valid = [r for r in r_multiples if r is not None]
        return statistics.mean(valid) if valid else None

    @staticmethod
    def payoff_ratio(pnls: List[float], results: List[TradeResult]) -> Optional[float]:
        aw = MetricsCalculator.avg_win(pnls, results)
        al = MetricsCalculator.avg_loss(pnls, results)
        if aw is None or al is None or al == 0:
            return None
        return abs(aw) / abs(al)

    # ── Profit Factor & Expectancy ───────────────────────────────────────────────

    @staticmethod
    def profit_factor(pnls: List[float], results: List[TradeResult]) -> Optional[float]:
        gross_profit = sum(p for p, r in zip(pnls, results) if r == TradeResult.WIN)
        gross_loss = abs(sum(p for p, r in zip(pnls, results) if r == TradeResult.LOSS))
        if gross_loss == 0:
            return None  # undefined when no losing trades
        if gross_profit == 0:
            return None  # undefined when no winning trades (all losses)
        return gross_profit / gross_loss

    @staticmethod
    def expectancy(pnls: List[float], results: List[TradeResult]) -> Optional[float]:
        if not results:
            return None
        wr = MetricsCalculator.win_rate(results) or 0.0
        lr = MetricsCalculator.loss_rate(results) or 0.0
        aw = MetricsCalculator.avg_win(pnls, results) or 0.0
        al = MetricsCalculator.avg_loss(pnls, results) or 0.0
        return (wr * aw) + (lr * al)  # al is already negative

    # ── Volatility / Risk-Adjusted ───────────────────────────────────────────────

    @staticmethod
    def std_returns(pnls: List[float]) -> Optional[float]:
        if len(pnls) < 2:
            return None
        try:
            return statistics.stdev(pnls)
        except statistics.StatisticsError:
            return None

    @staticmethod
    def sharpe_ratio(
        pnls: List[float],
        exit_datetimes: List[datetime],
        risk_free_rate: float = 0.0,
    ) -> Optional[float]:
        if len(pnls) < 2:
            return None
        std = MetricsCalculator.std_returns(pnls)
        if not std or std == 0:
            return None
        mean_return = statistics.mean(pnls) - risk_free_rate
        factor = _annualization_factor(exit_datetimes)
        return (mean_return / std) * factor

    @staticmethod
    def sortino_ratio(
        pnls: List[float],
        exit_datetimes: List[datetime],
        risk_free_rate: float = 0.0,
    ) -> Optional[float]:
        if len(pnls) < 2:
            return None
        downside = [p for p in pnls if p < 0]
        if len(downside) < 2:
            return None
        try:
            downside_std = statistics.stdev(downside)
        except statistics.StatisticsError:
            return None
        if downside_std == 0:
            return None
        mean_return = statistics.mean(pnls) - risk_free_rate
        factor = _annualization_factor(exit_datetimes)
        return (mean_return / downside_std) * factor

    @staticmethod
    def calmar_ratio(
        pnls: List[float],
        exit_datetimes: List[datetime],
        max_drawdown_abs: Optional[float],
    ) -> Optional[float]:
        if not pnls or not max_drawdown_abs or max_drawdown_abs == 0:
            return None
        sorted_dts = sorted([dt for dt in exit_datetimes if dt is not None])
        if len(sorted_dts) < 2:
            return None
        years = (sorted_dts[-1] - sorted_dts[0]).days / 365.25
        if years <= 0:
            return None
        annualized_return = sum(pnls) / years
        return annualized_return / abs(max_drawdown_abs)

    @staticmethod
    def recovery_factor(
        total_net_profit: float, max_drawdown_abs: Optional[float]
    ) -> Optional[float]:
        if max_drawdown_abs is None or max_drawdown_abs == 0:
            return None
        return total_net_profit / abs(max_drawdown_abs)

    # ── Equity Curve & Drawdown ──────────────────────────────────────────────────

    @staticmethod
    def equity_curve(pnls: List[float], starting_balance: float) -> List[float]:
        """Cumulative PnL added to starting_balance, one entry per trade."""
        curve = []
        running = starting_balance
        for pnl in pnls:
            running += pnl
            curve.append(running)
        return curve

    @staticmethod
    def drawdown_curve(
        equity: List[float], initial_peak: Optional[float] = None
    ) -> List[float]:
        """drawdown[i] = equity[i] - running_peak_up_to_i (always ≤ 0).

        initial_peak: if provided (e.g. account starting_balance), used as the
        starting high-water mark so that the very first losing trade correctly
        shows a negative drawdown rather than 0.
        """
        if not equity:
            return []
        peak = initial_peak if initial_peak is not None else equity[0]
        result = []
        for val in equity:
            peak = max(peak, val)
            result.append(val - peak)
        return result

    @staticmethod
    def max_drawdown(drawdown_curve: List[float]) -> Optional[float]:
        """Most negative value in the drawdown curve (absolute dollar)."""
        if not drawdown_curve:
            return None
        return min(drawdown_curve)

    @staticmethod
    def max_drawdown_pct(
        drawdown_curve: List[float], equity_curve: List[float]
    ) -> Optional[float]:
        """At the point of max drawdown: (drawdown / peak_equity) * 100."""
        if not drawdown_curve or not equity_curve:
            return None
        min_dd = min(drawdown_curve)
        if min_dd == 0:
            return 0.0
        idx = drawdown_curve.index(min_dd)
        # Peak up to that index
        peak = max(equity_curve[: idx + 1]) if idx > 0 else equity_curve[0]
        if peak == 0:
            return None
        return (min_dd / peak) * 100

    @staticmethod
    def relative_drawdown(
        drawdown_curve: List[float], equity_curve: List[float]
    ) -> Optional[float]:
        """Same as max_drawdown_pct but expressed as a 0.0–1.0 ratio."""
        pct = MetricsCalculator.max_drawdown_pct(drawdown_curve, equity_curve)
        return pct / 100.0 if pct is not None else None

    @staticmethod
    def max_drawdown_pct_of_starting_balance(
        max_drawdown_abs: Optional[float], starting_balance: float
    ) -> Optional[float]:
        """FTMO-style max drawdown: (abs_drawdown / starting_balance) * 100.

        Always ≤ 0.  Returns None if starting_balance is zero or drawdown is None.
        This differs from max_drawdown_pct which divides by the running peak equity.
        FTMO's maximum loss limit (e.g. 10%) is measured against the initial balance.
        """
        if not starting_balance or max_drawdown_abs is None:
            return None
        return (max_drawdown_abs / starting_balance) * 100  # max_drawdown_abs is ≤ 0

    # ── Period Net PnL (worst period, based on closed trades only) ──────────────
    #
    # IMPORTANT — what these metrics measure and do NOT measure:
    #
    # These return the *sum of closed-trade net_pnl* for the worst calendar period.
    # A positive value means the worst period was still a net win.
    # A negative value means the worst period had a net loss.
    #
    # FTMO daily loss limit check: abs(daily_drawdown) >= 0.05 * starting_balance
    # (compare the worst-day loss against the 5% threshold)
    #
    # What these do NOT compute:
    #   - Intraperiod drawdown from that period's high-water mark
    #   - Drawdown from open positions (no unrealized PnL is tracked)
    #   - True equity drawdown within the period (would require tick/minute data)
    #
    # Limitation: if you had a +$500 morning trade and a -$600 afternoon trade on
    # the same day, daily_drawdown = -$100 (net day PnL). The intraday drawdown
    # from the day's peak was -$600, but that cannot be computed from closed-trade
    # data alone.

    @staticmethod
    def daily_drawdown(
        pnls: List[float], exit_datetimes: List[datetime]
    ) -> Optional[float]:
        """Worst (most negative) single calendar day net PnL sum across all closed trades.

        Positive return value = even the worst day was a net win.
        Negative return value = the worst day had a net loss.

        Use abs(result) to compare against FTMO 5% daily loss limit.
        This is NOT intraday drawdown from peak — see class docstring for details.
        """
        if not pnls:
            return None
        grouped = _group_pnl_by_period(pnls, exit_datetimes, "day")
        if not grouped:
            return None
        return min(grouped.values())

    @staticmethod
    def weekly_drawdown(
        pnls: List[float], exit_datetimes: List[datetime]
    ) -> Optional[float]:
        """Worst (most negative) ISO-week net PnL sum across all closed trades.

        Positive return value = even the worst week was a net win.
        Negative return value = the worst week had a net loss.

        This is NOT intraweek drawdown from the week's peak equity.
        """
        if not pnls:
            return None
        grouped = _group_pnl_by_period(pnls, exit_datetimes, "week")
        if not grouped:
            return None
        return min(grouped.values())

    @staticmethod
    def monthly_drawdown(
        pnls: List[float], exit_datetimes: List[datetime]
    ) -> Optional[float]:
        """Worst (most negative) calendar-month net PnL sum across all closed trades.

        Positive return value = even the worst month was a net win.
        Negative return value = the worst month had a net loss.

        This is NOT intramonth drawdown from the month's peak equity.
        """
        if not pnls:
            return None
        grouped = _group_pnl_by_period(pnls, exit_datetimes, "month")
        if not grouped:
            return None
        return min(grouped.values())

    # ── Consecutive Streaks ──────────────────────────────────────────────────────

    @staticmethod
    def max_consecutive_wins(results: List[TradeResult]) -> int:
        return MetricsCalculator._max_streak(results, TradeResult.WIN)

    @staticmethod
    def max_consecutive_losses(results: List[TradeResult]) -> int:
        return MetricsCalculator._max_streak(results, TradeResult.LOSS)

    @staticmethod
    def _max_streak(results: List[TradeResult], target: TradeResult) -> int:
        max_streak = current = 0
        for r in results:
            if r == target:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    @staticmethod
    def avg_losing_streak(results: List[TradeResult]) -> Optional[float]:
        streaks = []
        current = 0
        for r in results:
            if r == TradeResult.LOSS:
                current += 1
            else:
                if current > 0:
                    streaks.append(current)
                current = 0
        if current > 0:
            streaks.append(current)
        return statistics.mean(streaks) if streaks else None

    # ── Duration & Frequency ────────────────────────────────────────────────────

    @staticmethod
    def avg_holding_duration(durations: List[timedelta]) -> Optional[timedelta]:
        if not durations:
            return None
        total_seconds = sum(d.total_seconds() for d in durations)
        return timedelta(seconds=total_seconds / len(durations))

    @staticmethod
    def trades_per_day(exit_datetimes: List[datetime]) -> Optional[float]:
        return MetricsCalculator._trades_per_period(exit_datetimes, 1.0)

    @staticmethod
    def trades_per_week(exit_datetimes: List[datetime]) -> Optional[float]:
        return MetricsCalculator._trades_per_period(exit_datetimes, 7.0)

    @staticmethod
    def trades_per_month(exit_datetimes: List[datetime]) -> Optional[float]:
        return MetricsCalculator._trades_per_period(exit_datetimes, 30.4375)

    @staticmethod
    def _trades_per_period(exit_datetimes: List[datetime], period_days: float) -> Optional[float]:
        if len(exit_datetimes) < 2:
            return None
        sorted_dts = sorted(exit_datetimes)
        total_days = (sorted_dts[-1] - sorted_dts[0]).days
        if total_days <= 0:
            return None
        return len(exit_datetimes) / (total_days / period_days)

    # ── Account-Level Totals ────────────────────────────────────────────────────

    @staticmethod
    def total_net_profit(pnls: List[float]) -> float:
        return sum(pnls)

    @staticmethod
    def total_gross_profit(
        gross_pnls: List[float], results: List[TradeResult]
    ) -> float:
        return sum(p for p, r in zip(gross_pnls, results) if r == TradeResult.WIN)

    @staticmethod
    def total_gross_loss(
        gross_pnls: List[float], results: List[TradeResult]
    ) -> float:
        return sum(p for p, r in zip(gross_pnls, results) if r == TradeResult.LOSS)

    @staticmethod
    def total_return_pct(
        total_net_profit: float, starting_balance: float
    ) -> Optional[float]:
        if not starting_balance:
            return None
        return (total_net_profit / starting_balance) * 100

    @staticmethod
    def largest_single_loss(
        pnls: List[float], results: List[TradeResult]
    ) -> Optional[float]:
        """Most negative net_pnl among losing trades. Always ≤ 0."""
        losses = [p for p, r in zip(pnls, results) if r == TradeResult.LOSS]
        return min(losses) if losses else None

    @staticmethod
    def largest_single_win(
        pnls: List[float], results: List[TradeResult]
    ) -> Optional[float]:
        """Largest net_pnl among winning trades. Always ≥ 0."""
        wins = [p for p, r in zip(pnls, results) if r == TradeResult.WIN]
        return max(wins) if wins else None

    # ── Exposure ────────────────────────────────────────────────────────────────

    @staticmethod
    def exposure_by_symbol(
        symbols: List[Optional[str]], lot_sizes: List[Optional[float]]
    ) -> Dict[str, float]:
        result: Dict[str, float] = defaultdict(float)
        for sym, lot in zip(symbols, lot_sizes):
            if sym is None or lot is None:
                continue
            result[sym] += lot
        return dict(result)

    @staticmethod
    def exposure_by_direction(
        directions: List[Optional[str]], lot_sizes: List[Optional[float]]
    ) -> Dict[str, float]:
        result: Dict[str, float] = defaultdict(float)
        for direction, lot in zip(directions, lot_sizes):
            if direction is None or lot is None:
                continue
            result[direction] += lot
        return dict(result)
