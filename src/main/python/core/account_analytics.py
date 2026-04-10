from __future__ import annotations

from typing import Callable, Dict, List

from src.main.python.core.metrics_calculator import MetricsCalculator
from src.main.python.core.performance_summary import AccountReport, PerformanceSummary
from src.main.python.models.account import Account
from src.main.python.models.enums import TradeResult
from src.main.python.models.trade import Trade
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


class AccountAnalytics:
    """
    Main analytics service. Stateless — all state flows through method arguments.
    Takes a list of Trade objects and an Account, returns a full AccountReport.
    All arithmetic is delegated to MetricsCalculator; this class only extracts
    lists from Trade objects and wires everything together.
    """

    @staticmethod
    def generate_report(trades: List[Trade], account: Account) -> AccountReport:
        if not trades:
            logger.warning(
                "generate_report called with empty trade list for account %s",
                account.account_id,
            )
            return AccountReport(account_id=account.account_id)

        # Sort by exit_datetime; trades without exit_datetime are excluded
        sorted_trades = sorted(
            [t for t in trades if t.exit_datetime is not None],
            key=lambda t: t.exit_datetime,
        )
        skipped = len(trades) - len(sorted_trades)
        if skipped:
            logger.warning(
                "Excluded %d trade(s) with missing exit_datetime from report", skipped
            )

        starting_balance = account.starting_balance or 0.0
        if not starting_balance:
            logger.warning(
                "Account %s has no starting_balance — total_return_pct will be None",
                account.account_id,
            )

        # Build equity/drawdown curves from the full sorted trade list
        pnls = [t.net_pnl if t.net_pnl is not None else 0.0 for t in sorted_trades]
        eq = MetricsCalculator.equity_curve(pnls, starting_balance)
        dd = MetricsCalculator.drawdown_curve(eq)
        dates = [t.exit_datetime for t in sorted_trades]

        overall = AccountAnalytics._summarize(sorted_trades, starting_balance)

        return AccountReport(
            account_id=account.account_id,
            overall=overall,
            equity_curve=eq,
            drawdown_curve=dd,
            trade_dates=dates,
            by_symbol=AccountAnalytics._segment(
                sorted_trades, lambda t: t.symbol or "Unknown"
            ),
            by_direction=AccountAnalytics._segment(
                sorted_trades,
                lambda t: t.direction.value if t.direction else "Unknown",
            ),
            by_asset_class=AccountAnalytics._segment(
                sorted_trades,
                lambda t: t.asset_class.value if t.asset_class else "Unknown",
            ),
            by_session=AccountAnalytics._segment(
                sorted_trades, lambda t: t.session or "Unknown"
            ),
            by_setup_type=AccountAnalytics._segment(
                sorted_trades, lambda t: t.setup_type or "Unknown"
            ),
            by_strategy=AccountAnalytics._segment(
                sorted_trades, lambda t: t.strategy or "Unknown"
            ),
            by_market_condition=AccountAnalytics._segment(
                sorted_trades, lambda t: t.market_condition or "Unknown"
            ),
            by_weekday=AccountAnalytics._segment(
                sorted_trades, lambda t: t.exit_datetime.strftime("%A")
            ),
            by_hour=AccountAnalytics._segment(
                sorted_trades, lambda t: str(t.exit_datetime.hour)
            ),
            by_month=AccountAnalytics._segment(
                sorted_trades, lambda t: t.exit_datetime.strftime("%Y-%m")
            ),
            by_followed_plan=AccountAnalytics._segment(
                sorted_trades, lambda t: str(t.followed_plan)
            ),
            by_result=AccountAnalytics._segment(
                sorted_trades,
                lambda t: t.result.value if t.result else "Unknown",
            ),
        )

    @staticmethod
    def _summarize(trades: List[Trade], starting_balance: float) -> PerformanceSummary:
        """
        Extract typed lists from Trade objects and delegate all computation
        to MetricsCalculator. Never performs arithmetic directly.
        """
        if not trades:
            return PerformanceSummary()

        results = [t.result for t in trades if t.result is not None]
        net_pnls = [t.net_pnl if t.net_pnl is not None else 0.0 for t in trades]
        gross_pnls = [t.gross_pnl if t.gross_pnl is not None else 0.0 for t in trades]
        r_multiples = [t.actual_r_multiple for t in trades]
        durations = [t.holding_duration for t in trades if t.holding_duration is not None]
        exit_dts = [t.exit_datetime for t in trades if t.exit_datetime is not None]
        symbols = [t.symbol for t in trades]
        lot_sizes = [t.lot_size for t in trades]
        directions = [t.direction.value if t.direction else None for t in trades]

        tnp = MetricsCalculator.total_net_profit(net_pnls)
        eq = MetricsCalculator.equity_curve(net_pnls, starting_balance)
        dd = MetricsCalculator.drawdown_curve(eq)
        mdd = MetricsCalculator.max_drawdown(dd)
        mdd_pct = MetricsCalculator.max_drawdown_pct(dd, eq)

        return PerformanceSummary(
            total_trades=len(trades),
            winning_trades=sum(1 for r in results if r == TradeResult.WIN),
            losing_trades=sum(1 for r in results if r == TradeResult.LOSS),
            breakeven_trades=sum(1 for r in results if r == TradeResult.BREAKEVEN),
            win_rate=MetricsCalculator.win_rate(results),
            loss_rate=MetricsCalculator.loss_rate(results),
            breakeven_rate=MetricsCalculator.breakeven_rate(results),
            total_net_profit=tnp,
            total_gross_profit=MetricsCalculator.total_gross_profit(gross_pnls, results),
            total_gross_loss=MetricsCalculator.total_gross_loss(gross_pnls, results),
            total_return_pct=MetricsCalculator.total_return_pct(tnp, starting_balance),
            avg_win=MetricsCalculator.avg_win(net_pnls, results),
            avg_loss=MetricsCalculator.avg_loss(net_pnls, results),
            largest_single_loss=MetricsCalculator.largest_single_loss(net_pnls, results),
            payoff_ratio=MetricsCalculator.payoff_ratio(net_pnls, results),
            profit_factor=MetricsCalculator.profit_factor(net_pnls, results),
            expectancy=MetricsCalculator.expectancy(net_pnls, results),
            avg_r_multiple=MetricsCalculator.avg_r_multiple(r_multiples),
            std_returns=MetricsCalculator.std_returns(net_pnls),
            sharpe_ratio=MetricsCalculator.sharpe_ratio(net_pnls, exit_dts),
            sortino_ratio=MetricsCalculator.sortino_ratio(net_pnls, exit_dts),
            calmar_ratio=MetricsCalculator.calmar_ratio(net_pnls, exit_dts, mdd),
            recovery_factor=MetricsCalculator.recovery_factor(tnp, mdd),
            max_drawdown=mdd,
            max_drawdown_pct=mdd_pct,
            relative_drawdown=MetricsCalculator.relative_drawdown(dd, eq),
            daily_drawdown=MetricsCalculator.daily_drawdown(net_pnls, exit_dts),
            weekly_drawdown=MetricsCalculator.weekly_drawdown(net_pnls, exit_dts),
            monthly_drawdown=MetricsCalculator.monthly_drawdown(net_pnls, exit_dts),
            max_consecutive_wins=MetricsCalculator.max_consecutive_wins(results),
            max_consecutive_losses=MetricsCalculator.max_consecutive_losses(results),
            avg_losing_streak=MetricsCalculator.avg_losing_streak(results),
            avg_holding_duration=MetricsCalculator.avg_holding_duration(durations),
            trades_per_day=MetricsCalculator.trades_per_day(exit_dts),
            trades_per_week=MetricsCalculator.trades_per_week(exit_dts),
            trades_per_month=MetricsCalculator.trades_per_month(exit_dts),
            exposure_by_symbol=MetricsCalculator.exposure_by_symbol(symbols, lot_sizes),
            exposure_by_direction=MetricsCalculator.exposure_by_direction(
                directions, lot_sizes
            ),
        )

    @staticmethod
    def _segment(
        trades: List[Trade],
        key_fn: Callable[[Trade], str],
    ) -> Dict[str, PerformanceSummary]:
        """
        Group trades by key_fn result, then summarize each group.
        Uses starting_balance=0.0 for segments so total_return_pct is None —
        per-segment return percentages against the full account balance would
        be misleading. Use total_net_profit (dollar) for segment comparisons.
        """
        groups: Dict[str, List[Trade]] = {}
        for trade in trades:
            key = key_fn(trade)
            groups.setdefault(key, []).append(trade)
        return {
            key: AccountAnalytics._summarize(group, 0.0)
            for key, group in groups.items()
        }
