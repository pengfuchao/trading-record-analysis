from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Dict, List, Optional

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
        dd = MetricsCalculator.drawdown_curve(eq, initial_peak=starting_balance)
        dates = [t.exit_datetime for t in sorted_trades]

        overall = AccountAnalytics._summarize(sorted_trades, starting_balance)
        current_balance = starting_balance + overall.total_net_profit if starting_balance else None

        return AccountReport(
            account_id=account.account_id,
            starting_balance=starting_balance if starting_balance else None,
            current_balance=current_balance,
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
        # Use starting_balance as initial peak only when non-zero (overall report).
        # Segments pass starting_balance=0.0; for those, default behaviour is fine.
        dd = MetricsCalculator.drawdown_curve(
            eq, initial_peak=starting_balance if starting_balance else None
        )
        mdd = MetricsCalculator.max_drawdown(dd)
        mdd_pct = MetricsCalculator.max_drawdown_pct(dd, eq)

        return PerformanceSummary(
            total_trades=len(trades),
            winning_trades=sum(1 for r in results if r == TradeResult.WIN),
            losing_trades=sum(1 for r in results if r == TradeResult.LOSS),
            breakeven_trades=sum(1 for r in results if r == TradeResult.BREAKEVEN),
            win_rate=MetricsCalculator.win_rate(results),
            win_rate_ex_be=MetricsCalculator.win_rate_ex_be(results),
            loss_rate=MetricsCalculator.loss_rate(results),
            breakeven_rate=MetricsCalculator.breakeven_rate(results),
            total_net_profit=tnp,
            total_gross_profit=MetricsCalculator.total_gross_profit(gross_pnls, results),
            total_gross_loss=MetricsCalculator.total_gross_loss(gross_pnls, results),
            total_return_pct=MetricsCalculator.total_return_pct(tnp, starting_balance),
            avg_win=MetricsCalculator.avg_win(net_pnls, results),
            avg_loss=MetricsCalculator.avg_loss(net_pnls, results),
            largest_single_win=MetricsCalculator.largest_single_win(net_pnls, results),
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
            max_drawdown_pct_of_starting_balance=MetricsCalculator.max_drawdown_pct_of_starting_balance(
                mdd, starting_balance
            ),
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

    @staticmethod
    def compute_ftmo_status(
        trades: List[Trade],
        account: Account,
        daily_loss_limit_pct: float = 5.0,
        max_loss_limit_pct: float = 10.0,
    ) -> dict:
        """
        Compute FTMO / prop firm challenge status based on closed trades only.

        Returns a dict matching FtmoStatusResponse fields.
        Drawdown is measured against starting_balance (not peak equity) per FTMO rules:
          - Daily limit: cannot lose more than daily_loss_limit_pct% of starting_balance in one day.
          - Max limit:   cumulative drawdown from starting_balance cannot exceed max_loss_limit_pct%.

        Status values: SAFE / AT_RISK (>=75% of limit used) / BREACHED (>=100%) / UNKNOWN (no balance).
        """
        starting_balance = account.starting_balance or 0.0
        today = date.today()

        closed_trades = sorted(
            [t for t in trades if t.exit_datetime is not None],
            key=lambda t: t.exit_datetime,
        )

        total_net_pnl = sum(t.net_pnl or 0.0 for t in closed_trades)
        current_balance: Optional[float] = (
            starting_balance + total_net_pnl if starting_balance else None
        )
        total_return_pct: Optional[float] = (
            (total_net_pnl / starting_balance) * 100 if starting_balance else None
        )

        # ── Today's closed PnL ────────────────────────────────────────────────
        today_pnl = sum(
            t.net_pnl or 0.0
            for t in closed_trades
            if t.exit_datetime.date() == today
        )

        # ── Daily loss metrics ────────────────────────────────────────────────
        daily_loss_limit_abs: Optional[float] = (
            starting_balance * daily_loss_limit_pct / 100.0 if starting_balance else None
        )
        daily_loss_used_pct: Optional[float] = None
        daily_loss_remaining: Optional[float] = None
        if starting_balance and today_pnl < 0:
            daily_loss_used_pct = abs(today_pnl) / starting_balance * 100.0
        elif starting_balance:
            daily_loss_used_pct = 0.0
        if daily_loss_limit_abs is not None:
            # remaining = how much more can be lost before breach (positive = room left)
            daily_loss_remaining = daily_loss_limit_abs + today_pnl

        # ── Max (overall) drawdown from starting balance ──────────────────────
        max_loss_limit_abs: Optional[float] = (
            starting_balance * max_loss_limit_pct / 100.0 if starting_balance else None
        )
        # Walk equity curve to find the worst balance relative to starting_balance
        worst_balance_vs_start = 0.0  # most negative equity - starting_balance seen
        if starting_balance:
            running = starting_balance
            for t in closed_trades:
                running += t.net_pnl or 0.0
                diff = running - starting_balance  # negative = drawdown from start
                worst_balance_vs_start = min(worst_balance_vs_start, diff)

        current_max_drawdown: Optional[float] = (
            worst_balance_vs_start if starting_balance and worst_balance_vs_start < 0 else None
        )
        current_max_drawdown_pct: Optional[float] = (
            (worst_balance_vs_start / starting_balance) * 100.0
            if starting_balance and worst_balance_vs_start < 0
            else None
        )
        max_loss_remaining: Optional[float] = None
        if max_loss_limit_abs is not None:
            max_loss_remaining = max_loss_limit_abs + worst_balance_vs_start

        # ── Status classification ─────────────────────────────────────────────
        def _classify(used_pct: Optional[float], limit_pct: float) -> str:
            if not starting_balance:
                return "UNKNOWN"
            if used_pct is None:
                return "UNKNOWN"
            if used_pct >= limit_pct:
                return "BREACHED"
            if used_pct >= limit_pct * 0.75:
                return "AT_RISK"
            return "SAFE"

        daily_loss_used = daily_loss_used_pct or 0.0
        max_loss_used = (
            abs(current_max_drawdown_pct) if current_max_drawdown_pct is not None else 0.0
        )
        daily_status = _classify(daily_loss_used, daily_loss_limit_pct)
        overall_status = _classify(max_loss_used, max_loss_limit_pct)

        if "BREACHED" in (daily_status, overall_status):
            account_status = "BREACHED"
        elif "AT_RISK" in (daily_status, overall_status):
            account_status = "AT_RISK"
        elif "UNKNOWN" in (daily_status, overall_status):
            account_status = "UNKNOWN"
        else:
            account_status = "SAFE"

        return dict(
            account_id=account.account_id,
            generated_at=datetime.utcnow(),
            starting_balance=starting_balance or None,
            estimated_current_balance=current_balance,
            total_net_pnl=total_net_pnl if closed_trades else None,
            total_return_pct=total_return_pct,
            today_date=today,
            today_pnl=today_pnl,
            daily_loss_limit_pct=daily_loss_limit_pct,
            daily_loss_limit_abs=daily_loss_limit_abs,
            daily_loss_used_pct=daily_loss_used_pct,
            daily_loss_remaining=daily_loss_remaining,
            max_loss_limit_pct=max_loss_limit_pct,
            max_loss_limit_abs=max_loss_limit_abs,
            current_max_drawdown=current_max_drawdown,
            current_max_drawdown_pct=current_max_drawdown_pct,
            max_loss_remaining=max_loss_remaining,
            daily_status=daily_status,
            overall_status=overall_status,
            account_status=account_status,
        )
