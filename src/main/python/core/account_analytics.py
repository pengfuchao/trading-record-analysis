from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from src.main.python.core.metrics_calculator import MetricsCalculator
from src.main.python.core.performance_summary import (
    AccountReport, BehavioralTrendBucket, BehavioralTrendReport, DailyAdherenceReport,
    EntryExitQualityReport, ExitBucket, ExitDecompositionReport, PerformanceSummary,
    PlanAdherenceGroup, PlanAdherenceReport, RRComparisonReport, RRTrendBucket,
    RRTrendReport, SetupViolation,
)
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
        broker_utc_offset: int = 2,
    ) -> dict:
        """
        Compute FTMO / prop firm challenge status based on closed trades only.

        Returns a dict matching FtmoStatusResponse fields.

        Drawdown rules (FTMO standard):
          - Daily limit:   cannot lose > daily_loss_limit_pct% of starting_balance on one calendar day.
          - Maximum limit: cumulative drawdown from starting_balance cannot exceed max_loss_limit_pct%.

        today_pnl definition:
          Sum of net_pnl for all trades whose exit_datetime falls on today's date in
          broker server local time (UTC + broker_utc_offset). This is *realized* PnL only
          — open positions and unrealized gains/losses are NOT included.

          broker_utc_offset must match the UTC offset used by your broker's server.
          Default is 2 (EET winter, UTC+2), used by most MT4/MT5 brokers.
          Use 3 for EET summer (UTC+3), or 0 for UTC.

        Status values: SAFE / AT_RISK (>=75% of limit used) / BREACHED (>=100%) / UNKNOWN (no balance).
        """
        starting_balance = account.starting_balance or 0.0
        # Compute "today" in broker server local time so exit_datetime comparisons are consistent.
        # exit_datetime in the DB is stored in broker local time (no timezone info attached).
        # Using date.today() (machine local) can diverge from broker date around midnight.
        today = (datetime.utcnow() + timedelta(hours=broker_utc_offset)).date()

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

    # ── Plan-vs-execution analytics ────────────────────────────────────────────

    @staticmethod
    def compute_plan_adherence(trades: List[Trade]) -> PlanAdherenceReport:
        """
        Compute plan-vs-execution analytics from a list of trades.

        No schema changes required — uses existing trade fields:
          trade_plan_id  → formal plan linkage (planned / unplanned)
          followed_plan  → self-reported adherence (followed / deviated / not tagged)
        """
        if not trades:
            return PlanAdherenceReport(
                total_trades=0,
                planned_count=0,
                unplanned_count=0,
                planned_pct=None,
            )

        # ── Dimension 1: formal plan linkage ─────────────────────────────────
        planned_trades   = [t for t in trades if t.trade_plan_id is not None]
        unplanned_trades = [t for t in trades if t.trade_plan_id is None]

        planned_pct = (
            round(len(planned_trades) / len(trades) * 100, 1) if trades else None
        )

        # ── Dimension 2: self-reported adherence ──────────────────────────────
        followed_trades  = [t for t in trades if t.followed_plan is True]
        deviated_trades  = [t for t in trades if t.followed_plan is False]
        not_tagged       = [t for t in trades if t.followed_plan is None]

        # ── Intersection ──────────────────────────────────────────────────────
        linked_but_deviated = [
            t for t in trades
            if t.trade_plan_id is not None and t.followed_plan is False
        ]

        # ── Build groups ──────────────────────────────────────────────────────
        planned_grp   = AccountAnalytics._adherence_group(planned_trades)
        unplanned_grp = AccountAnalytics._adherence_group(unplanned_trades)
        followed_grp  = AccountAnalytics._adherence_group(followed_trades)
        deviated_grp  = AccountAnalytics._adherence_group(deviated_trades)

        signals = AccountAnalytics._adherence_signals(
            total=len(trades),
            planned=planned_grp,
            unplanned=unplanned_grp,
            followed=followed_grp,
            deviated=deviated_grp,
            linked_but_deviated_count=len(linked_but_deviated),
        )

        rr = AccountAnalytics.compute_rr_analysis(trades)

        return PlanAdherenceReport(
            total_trades=len(trades),
            planned_count=len(planned_trades),
            unplanned_count=len(unplanned_trades),
            planned_pct=planned_pct,
            planned=planned_grp,
            unplanned=unplanned_grp,
            followed_count=len(followed_trades),
            deviated_count=len(deviated_trades),
            not_tagged_count=len(not_tagged),
            followed=followed_grp,
            deviated=deviated_grp,
            linked_but_deviated_count=len(linked_but_deviated),
            rr_comparison=rr if rr.sample_count > 0 else None,
            coaching_signals=signals,
        )

    # ── Planned R:R vs Realized R analytics ───────────────────────────────────────

    @staticmethod
    def compute_rr_analysis(trades: List[Trade]) -> RRComparisonReport:
        """
        Compare planned R:R (from linked TradePlan) against realized R multiple.

        Requires Trade.planned_rr to be pre-populated from the linked plan before
        calling (the analytics route does this via TradePlanRepository lookup).

        Inclusion criteria:
          - trade.trade_plan_id is not None  (has a linked plan)
          - trade.planned_rr is not None and > 0  (plan has an R:R target)
          - trade.actual_r_multiple is not None   (realized R was computed)

        All negative-R trades are included — they are diagnostically important.
        """
        MIN_N = 3

        qualifying = [
            t for t in trades
            if t.trade_plan_id is not None
            and t.planned_rr is not None
            and t.planned_rr > 0
            and t.actual_r_multiple is not None
        ]

        n = len(qualifying)
        if n == 0:
            return RRComparisonReport(
                sample_count=0,
                avg_planned_rr=None,
                avg_actual_r=None,
                avg_r_shortfall=None,
                realization_pct=None,
                met_target_count=0,
                missed_target_count=0,
                pct_met_target=None,
                coaching_signals=[],
            )

        avg_planned = round(sum(t.planned_rr for t in qualifying) / n, 2)
        avg_actual = round(sum(t.actual_r_multiple for t in qualifying) / n, 2)
        shortfall = round(avg_actual - avg_planned, 2)
        realization_pct = round((avg_actual / avg_planned) * 100, 1) if avg_planned != 0 else None

        met = [t for t in qualifying if t.actual_r_multiple >= t.planned_rr]
        missed = [t for t in qualifying if t.actual_r_multiple < t.planned_rr]
        pct_met = round(len(met) / n * 100, 1) if n > 0 else None

        signals = []
        if n >= MIN_N:
            if realization_pct is not None and realization_pct < 50:
                signals.append(
                    f"On average you are realizing only {realization_pct:.0f}% of your planned R:R "
                    f"({avg_actual:+.2f}R actual vs {avg_planned:.2f}R planned across {n} linked trades). "
                    f"The most likely cause is premature exits — consider holding to your original TP level."
                )
            elif realization_pct is not None and realization_pct < 80:
                signals.append(
                    f"You are capturing {realization_pct:.0f}% of your planned R:R on average "
                    f"({avg_actual:+.2f}R realized vs {avg_planned:.2f}R planned, n={n}). "
                    f"There is execution leakage between plan and outcome — review where exits deviate from the plan."
                )
            elif realization_pct is not None and realization_pct >= 100:
                signals.append(
                    f"Your realized R ({avg_actual:+.2f}R) equals or exceeds your planned R:R "
                    f"({avg_planned:.2f}R planned, n={n}). "
                    f"Strong hold discipline — you are executing to or beyond your intended targets."
                )
            else:
                if shortfall < 0:
                    signals.append(
                        f"Average R shortfall: {shortfall:.2f}R below planned target "
                        f"({avg_actual:+.2f}R realized vs {avg_planned:.2f}R planned, n={n})."
                    )

            if pct_met is not None and pct_met < 40:
                signals.append(
                    f"Only {pct_met:.0f}% of linked trades ({len(met)}/{n}) reached their planned R:R target. "
                    f"Review whether planned take-profits are set at realistic levels "
                    f"or whether exits are being triggered by fear before targets are hit."
                )
            elif pct_met is not None and pct_met >= 60:
                signals.append(
                    f"{pct_met:.0f}% of linked trades ({len(met)}/{n}) met or exceeded their planned R:R. "
                )

        return RRComparisonReport(
            sample_count=n,
            avg_planned_rr=avg_planned,
            avg_actual_r=avg_actual,
            avg_r_shortfall=shortfall,
            realization_pct=realization_pct,
            met_target_count=len(met),
            missed_target_count=len(missed),
            pct_met_target=pct_met,
            coaching_signals=signals,
        )

    @staticmethod
    def _adherence_group(trades: List[Trade]) -> PlanAdherenceGroup:
        """Summarize a subset of trades into a PlanAdherenceGroup."""
        if not trades:
            return PlanAdherenceGroup(
                count=0, win_rate=None, avg_pnl=None, avg_r=None,
                total_pnl=0.0, profit_factor=None,
            )
        summary = AccountAnalytics._summarize(trades, 0.0)
        avg_pnl = summary.total_net_profit / len(trades)
        return PlanAdherenceGroup(
            count=len(trades),
            win_rate=summary.win_rate,
            avg_pnl=round(avg_pnl, 2),
            avg_r=summary.avg_r_multiple,
            total_pnl=round(summary.total_net_profit, 2),
            profit_factor=summary.profit_factor,
        )

    @staticmethod
    def _adherence_signals(
        total: int,
        planned: PlanAdherenceGroup,
        unplanned: PlanAdherenceGroup,
        followed: PlanAdherenceGroup,
        deviated: PlanAdherenceGroup,
        linked_but_deviated_count: int,
    ) -> List[str]:
        """
        Generate plain-English coaching signal sentences from plan adherence data.
        Only generates a signal when sample size is >= 3 for both sides of a comparison.
        """
        MIN_N = 3
        signals: List[str] = []

        # Signal 1: overall plan coverage
        if total > 0 and planned.count > 0:
            planned_pct = round(planned.count / total * 100)
            signals.append(
                f"{planned_pct}% of your trades ({planned.count}/{total}) "
                f"have a formal pre-trade plan linked."
            )
        elif total >= MIN_N:
            signals.append(
                "No trades have a linked pre-trade plan yet. "
                "Writing a plan before each trade is the highest-leverage journaling habit."
            )

        # Signal 2: planned vs unplanned performance comparison
        if planned.count >= MIN_N and unplanned.count >= MIN_N:
            p_wr  = round((planned.win_rate or 0) * 100, 1)
            u_wr  = round((unplanned.win_rate or 0) * 100, 1)
            p_pnl = planned.avg_pnl or 0.0
            u_pnl = unplanned.avg_pnl or 0.0
            diff  = p_pnl - u_pnl

            if diff > 0:
                signals.append(
                    f"Planned trades outperform unplanned: "
                    f"win rate {p_wr}% vs {u_wr}%, "
                    f"avg PnL ${p_pnl:+.2f} vs ${u_pnl:+.2f} (+${diff:.2f}/trade edge from planning)."
                )
            elif diff < 0:
                signals.append(
                    f"Unplanned trades are performing better than planned this period "
                    f"(win rate {u_wr}% vs {p_wr}%, avg PnL ${u_pnl:+.2f} vs ${p_pnl:+.2f}). "
                    f"Review whether your plans are too rigid or your setups are stronger without them."
                )

        # Signal 3: followed vs deviated performance comparison
        if followed.count >= MIN_N and deviated.count >= MIN_N:
            f_wr  = round((followed.win_rate or 0) * 100, 1)
            d_wr  = round((deviated.win_rate or 0) * 100, 1)
            f_pnl = followed.avg_pnl or 0.0
            d_pnl = deviated.avg_pnl or 0.0
            diff  = f_pnl - d_pnl

            if diff > 0:
                signals.append(
                    f"Trades where you followed the plan outperform deviations: "
                    f"win rate {f_wr}% vs {d_wr}%, "
                    f"avg PnL ${f_pnl:+.2f} vs ${d_pnl:+.2f}."
                )
            else:
                signals.append(
                    f"Trades where you deviated from the plan are performing better "
                    f"(avg PnL ${d_pnl:+.2f} vs ${f_pnl:+.2f}). "
                    f"Consider whether your in-session adjustments are an edge or luck."
                )
        elif followed.count >= MIN_N and deviated.count == 0:
            signals.append(
                f"All tagged trades followed the plan ({followed.count} trades). "
                f"Great execution discipline."
            )
        elif deviated.count >= MIN_N:
            d_cost = abs(deviated.total_pnl) if deviated.total_pnl < 0 else 0
            if d_cost > 0:
                signals.append(
                    f"{deviated.count} trades were marked as plan deviations, "
                    f"costing ${d_cost:.2f} total."
                )
        return signals

    # ── R:R realization trend ─────────────────────────────────────────────────

    @staticmethod
    def compute_rr_trend(trades: List[Trade]) -> RRTrendReport:
        """
        Bucket qualifying trades by ISO week and compute R:R realization per bucket.

        Inclusion criteria (same as compute_rr_analysis):
          - trade.trade_plan_id is not None
          - trade.planned_rr is not None and > 0
          - trade.actual_r_multiple is not None
          - trade.exit_datetime is not None

        Buckets with 0 qualifying trades are omitted.
        Trend signal compares first vs second half of non-empty buckets (>= 4 required).
        """
        from collections import defaultdict

        qualifying = [
            t for t in trades
            if t.trade_plan_id is not None
            and t.planned_rr is not None
            and t.planned_rr > 0
            and t.actual_r_multiple is not None
            and t.exit_datetime is not None
        ]

        if not qualifying:
            return RRTrendReport(buckets=[], total_qualifying=0, trend_signal=None)

        groups: Dict[str, List[Trade]] = defaultdict(list)
        for t in qualifying:
            year, week, _ = t.exit_datetime.isocalendar()
            groups[f"{year}-W{week:02d}"].append(t)

        def _week_start(key: str) -> datetime:
            year, w = int(key[:4]), int(key[6:])
            jan4 = datetime(year, 1, 4)
            return jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=w - 1)

        buckets = []
        for key in sorted(groups):
            group = groups[key]
            n = len(group)
            avg_planned = round(sum(t.planned_rr for t in group) / n, 2)  # type: ignore[arg-type]
            avg_actual = round(sum(t.actual_r_multiple for t in group) / n, 2)  # type: ignore[arg-type]
            shortfall = round(avg_actual - avg_planned, 2)
            realization_pct = (
                round((avg_actual / avg_planned) * 100, 1) if avg_planned != 0 else None
            )
            buckets.append(RRTrendBucket(
                bucket=key,
                bucket_start=_week_start(key),
                n=n,
                avg_planned_rr=avg_planned,
                avg_actual_r=avg_actual,
                avg_shortfall=shortfall,
                realization_pct=realization_pct,
            ))

        trend_signal: Optional[str] = None
        valid = [b for b in buckets if b.realization_pct is not None]
        if len(valid) >= 4:
            mid = len(valid) // 2
            first_avg = sum(b.realization_pct for b in valid[:mid]) / mid  # type: ignore[arg-type]
            second_avg = sum(b.realization_pct for b in valid[mid:]) / (len(valid) - mid)  # type: ignore[arg-type]
            diff = second_avg - first_avg
            if diff >= 5:
                trend_signal = "improving"
            elif diff <= -5:
                trend_signal = "worsening"
            else:
                trend_signal = "stable"

        return RRTrendReport(
            buckets=buckets,
            total_qualifying=len(qualifying),
            trend_signal=trend_signal,
        )

    # ── Behavioral trend (weekly series) ──────────────────────────────────────

    @staticmethod
    def _has_any_mistake(trade: Trade) -> bool:
        """Return True if the trade has at least one recorded mistake."""
        boolean_flags = (
            "early_entry", "chasing", "fomo", "emotional_trade", "revenge_trade",
            "overtrading", "hesitation", "moved_stop", "premature_exit", "held_loser_too_long",
        )
        if any(getattr(trade, flag, None) is True for flag in boolean_flags):
            return True
        if trade.mistake_tags and any(t.strip() for t in trade.mistake_tags):
            return True
        return False

    @staticmethod
    def _trend_signal(values: List[Optional[float]], higher_is_better: bool) -> Optional[str]:
        """
        Compare first-half vs second-half averages of a series.
        Returns "improving" | "worsening" | "stable" | None (< 4 non-None values).
        Threshold: >= 5 percentage-point change (values assumed 0–1 scale → multiply by 100).
        """
        non_none = [v for v in values if v is not None]
        if len(non_none) < 4:
            return None
        mid = len(non_none) // 2
        first_avg = sum(non_none[:mid]) / mid * 100
        second_avg = sum(non_none[mid:]) / (len(non_none) - mid) * 100
        diff = second_avg - first_avg
        if higher_is_better:
            if diff >= 5:
                return "improving"
            elif diff <= -5:
                return "worsening"
            return "stable"
        else:
            if diff <= -5:
                return "improving"
            elif diff >= 5:
                return "worsening"
            return "stable"

    @staticmethod
    def compute_behavioral_trend(trades: List[Trade]) -> BehavioralTrendReport:
        """
        Bucket all trades with exit_datetime by ISO week and compute four
        behavioral discipline metrics per bucket:

          win_rate            = wins / n                    (higher is better)
          mistake_rate        = trades_with_mistake / n     (lower is better)
          plan_link_rate      = trades_with_plan_id / n     (higher is better)
          followed_plan_rate  = followed=True / tagged      (higher is better;
                                None if tagged < 3)

        Trend signal per metric: "improving" | "worsening" | "stable" | None
        (None when fewer than 4 non-empty buckets exist for that metric).
        """
        from collections import defaultdict

        dated = [t for t in trades if t.exit_datetime is not None]
        if not dated:
            return BehavioralTrendReport()

        groups: Dict[str, List[Trade]] = defaultdict(list)
        for t in dated:
            year, week, _ = t.exit_datetime.isocalendar()
            groups[f"{year}-W{week:02d}"].append(t)

        def _week_start(key: str) -> datetime:
            year, w = int(key[:4]), int(key[6:])
            jan4 = datetime(year, 1, 4)
            return jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=w - 1)

        MIN_FP_TAGGED = 3  # min trades with followed_plan set to compute followed_plan_rate

        buckets: List[BehavioralTrendBucket] = []
        for key in sorted(groups):
            group = groups[key]
            n = len(group)

            wins = sum(1 for t in group if t.result == TradeResult.WIN)
            win_rate = round(wins / n, 4) if n else None

            mistakes = sum(1 for t in group if AccountAnalytics._has_any_mistake(t))
            mistake_rate = round(mistakes / n, 4) if n else None

            linked = sum(1 for t in group if t.trade_plan_id is not None)
            plan_link_rate = round(linked / n, 4) if n else None

            tagged = [t for t in group if t.followed_plan is not None]
            followed_plan_rate: Optional[float] = None
            if len(tagged) >= MIN_FP_TAGGED:
                followed = sum(1 for t in tagged if t.followed_plan is True)
                followed_plan_rate = round(followed / len(tagged), 4)

            buckets.append(BehavioralTrendBucket(
                bucket=key,
                bucket_start=_week_start(key),
                n=n,
                win_rate=win_rate,
                mistake_rate=mistake_rate,
                plan_link_rate=plan_link_rate,
                followed_plan_rate=followed_plan_rate,
            ))

        return BehavioralTrendReport(
            buckets=buckets,
            total_trades=len(dated),
            win_rate_trend=AccountAnalytics._trend_signal(
                [b.win_rate for b in buckets], higher_is_better=True
            ),
            mistake_rate_trend=AccountAnalytics._trend_signal(
                [b.mistake_rate for b in buckets], higher_is_better=False
            ),
            plan_link_rate_trend=AccountAnalytics._trend_signal(
                [b.plan_link_rate for b in buckets], higher_is_better=True
            ),
            followed_plan_rate_trend=AccountAnalytics._trend_signal(
                [b.followed_plan_rate for b in buckets], higher_is_better=True
            ),
        )

    # ── Exit outcome decomposition ─────────────────────────────────────────────

    @staticmethod
    def _get_tp_level(trade: Trade) -> Optional[float]:
        """Return the best available take-profit level for exit classification."""
        if trade.take_profit is not None:
            return trade.take_profit
        if trade.planned_take_profit is not None:
            return trade.planned_take_profit
        # Infer TP from planned_rr + entry_price + stop_loss
        if (
            trade.planned_rr is not None
            and trade.planned_rr > 0
            and trade.entry_price is not None
            and trade.stop_loss is not None
            and trade.direction is not None
        ):
            from src.main.python.models.enums import Direction
            sl_dist = abs(trade.entry_price - trade.stop_loss)
            if sl_dist > 0:
                if trade.direction == Direction.LONG:
                    return trade.entry_price + trade.planned_rr * sl_dist
                else:
                    return trade.entry_price - trade.planned_rr * sl_dist
        return None

    @staticmethod
    def _classify_exit(trade: Trade) -> str:
        """
        Classify one trade exit. Returns:
          "stop_hit" | "manual_cut" | "target_hit" | "exit_before_target" | "unclear"
        """
        from src.main.python.models.enums import Direction

        r = trade.actual_r_multiple
        if r is None:
            return "unclear"

        # Stop hit: R ≤ -0.85 (within 15% of full stop)
        if r <= -0.85:
            return "stop_hit"

        # Manual cut (loss side): lost money but cut well before stop
        if trade.result == TradeResult.LOSS and r > -0.65:
            return "manual_cut"

        # Win side: classify against TP level
        if trade.result == TradeResult.WIN:
            tp = AccountAnalytics._get_tp_level(trade)
            if (
                tp is not None
                and trade.entry_price is not None
                and trade.exit_price is not None
                and trade.direction is not None
            ):
                if trade.direction == Direction.LONG:
                    tp_dist = tp - trade.entry_price
                    actual_dist = trade.exit_price - trade.entry_price
                elif trade.direction == Direction.SHORT:
                    tp_dist = trade.entry_price - tp
                    actual_dist = trade.entry_price - trade.exit_price
                else:
                    return "unclear"
                if tp_dist > 0:
                    reach_pct = actual_dist / tp_dist
                    return "target_hit" if reach_pct >= 0.90 else "exit_before_target"

        return "unclear"

    @staticmethod
    def compute_exit_decomposition(trades: List[Trade]) -> "ExitDecompositionReport":
        """
        Decompose exit outcomes across all provided trades.
        Trades without actual_r_multiple are excluded from buckets; their count is
        reported in total_unclassified.
        """
        from src.main.python.core.performance_summary import ExitBucket, ExitDecompositionReport

        classified = [t for t in trades if t.actual_r_multiple is not None]
        total_unclassified = len(trades) - len(classified)

        bucket_trades: Dict[str, List[Trade]] = {
            k: [] for k in ("stop_hit", "manual_cut", "target_hit", "exit_before_target", "unclear")
        }
        for trade in classified:
            bucket_trades[AccountAnalytics._classify_exit(trade)].append(trade)

        total = len(classified)

        def _make_bucket(tlist: List[Trade]) -> ExitBucket:
            count = len(tlist)
            total_pnl = sum(t.net_pnl or 0.0 for t in tlist)
            r_vals = [t.actual_r_multiple for t in tlist if t.actual_r_multiple is not None]
            avg_r = round(sum(r_vals) / len(r_vals), 2) if r_vals else None
            pct = round(count / total * 100, 1) if total else None
            return ExitBucket(count=count, total_pnl=round(total_pnl, 2), avg_r=avg_r, pct_of_total=pct)

        stop_b = _make_bucket(bucket_trades["stop_hit"])
        cut_b = _make_bucket(bucket_trades["manual_cut"])
        target_b = _make_bucket(bucket_trades["target_hit"])
        early_b = _make_bucket(bucket_trades["exit_before_target"])
        unclear_b = _make_bucket(bucket_trades["unclear"])

        signals: List[str] = []
        n_losses = sum(1 for t in classified if t.result == TradeResult.LOSS)
        tp_wins = target_b.count + early_b.count

        if cut_b.count >= 2 and n_losses > 0:
            cut_pct = round(cut_b.count / n_losses * 100)
            avg_r_str = f" (avg {cut_b.avg_r:+.2f}R)" if cut_b.avg_r is not None else ""
            signals.append(
                f"{cut_pct}% of losses were manual cuts before stop{avg_r_str}. "
                f"Review whether these were disciplined risk management or fear-based exits."
            )

        if tp_wins >= 3:
            hit_pct = round(target_b.count / tp_wins * 100)
            if hit_pct < 50:
                signals.append(
                    f"Only {hit_pct}% of wins with a known target reached it. "
                    f"Consider holding longer or reviewing whether targets are set at realistic levels."
                )
            elif hit_pct >= 80:
                signals.append(
                    f"{hit_pct}% of wins with a known target reached or exceeded it — "
                    f"strong target-following discipline."
                )

        if total >= 5 and unclear_b.count / total >= 0.5:
            signals.append(
                f"{round(unclear_b.count / total * 100)}% of trades are 'unclear' exits. "
                f"Add take_profit levels to trades or link plans with planned_rr to improve classification."
            )

        return ExitDecompositionReport(
            total_classified=total,
            total_unclassified=total_unclassified,
            stop_hit=stop_b,
            manual_cut=cut_b,
            target_hit=target_b,
            exit_before_target=early_b,
            unclear=unclear_b,
            coaching_signals=signals,
        )

    # ── Entry vs exit quality decomposition ───────────────────────────────────

    @staticmethod
    def compute_entry_exit_quality(trades: List[Trade]) -> "EntryExitQualityReport":
        """
        Decompose whether underperformance is driven by entry quality or exit discipline.

        Exit-quality signals are directly observable (early exits vs. target).
        Entry-quality signals rely on self-reported flags — check flag_coverage_pct.
        Without MAE/MFE data, entry quality inference is conservative.
        """
        from src.main.python.core.performance_summary import EntryExitQualityReport

        classified = [t for t in trades if t.actual_r_multiple is not None]
        total = len(classified)

        _empty = EntryExitQualityReport(
            total_trades=len(trades), classified_trades=0,
            wins_total=0, wins_with_tp_info=0, wins_hit_target=0, wins_before_target=0,
            early_exit_pct=None,
            losses_total=0, stop_hit_count=0, manual_cut_count=0,
            stop_hit_pct_of_losses=None,
            entry_flagged_losses=0, entry_flagged_stop_hits=0,
            entry_flagged_stop_hit_pct=None, flag_coverage_pct=0.0,
            flag_early_entry=0, flag_chasing=0, flag_fomo=0,
            flag_plan_deviation_on_loss=0, flag_weak_setup_on_loss=0,
            flag_problem_analysis=0, flag_premature_exit=0, flag_moved_stop=0,
            primary_diagnosis="unclear", confidence="low",
        )
        if total == 0:
            return _empty

        classified_exits = [(t, AccountAnalytics._classify_exit(t)) for t in classified]

        # Win-side: exit quality (directly observable)
        wins = [t for t, _ in classified_exits if t.result == TradeResult.WIN]
        wins_hit_tgt = [t for t, ec in classified_exits if ec == "target_hit"]
        wins_before_tgt = [t for t, ec in classified_exits if ec == "exit_before_target"]
        wins_with_tp = wins_hit_tgt + wins_before_tgt
        early_exit_pct: Optional[float] = None
        if len(wins_with_tp) >= 3:
            early_exit_pct = round(len(wins_before_tgt) / len(wins_with_tp) * 100, 1)

        # Loss-side context
        losses = [t for t, _ in classified_exits if t.result == TradeResult.LOSS]
        stop_hits = [t for t, ec in classified_exits if ec == "stop_hit"]
        manual_cuts = [t for t, ec in classified_exits if ec == "manual_cut"]
        stop_hit_pct: Optional[float] = None
        if losses:
            stop_hit_pct = round(len(stop_hits) / len(losses) * 100, 1)

        # Entry quality flags (self-reported — coverage may be low)
        def _has_entry_flag(t: Trade) -> bool:
            return bool(
                t.early_entry
                or t.chasing
                or t.fomo
                or t.emotional_trade
                or t.revenge_trade
                or t.followed_plan is False
                or t.is_a_plus_setup is False
                or t.problem_source == "analysis"
            )

        def _has_any_flag(t: Trade) -> bool:
            return bool(
                _has_entry_flag(t)
                or t.premature_exit
                or t.moved_stop
                or t.held_loser_too_long
            )

        entry_flagged_losses = [t for t in losses if _has_entry_flag(t)]
        entry_flagged_stop_hits = [t for t in stop_hits if _has_entry_flag(t)]

        entry_flagged_stop_hit_pct: Optional[float] = None
        if len(stop_hits) >= 3:
            entry_flagged_stop_hit_pct = round(
                len(entry_flagged_stop_hits) / len(stop_hits) * 100, 1
            )

        flag_coverage_pct = round(
            sum(1 for t in classified if _has_any_flag(t)) / total * 100, 1
        )

        flag_early_entry = sum(1 for t in trades if t.early_entry is True)
        flag_chasing = sum(1 for t in trades if t.chasing is True)
        flag_fomo = sum(1 for t in trades if t.fomo is True)
        flag_plan_dev = sum(1 for t in losses if t.followed_plan is False)
        flag_weak_setup = sum(1 for t in losses if t.is_a_plus_setup is False)
        flag_problem_analysis = sum(1 for t in trades if t.problem_source == "analysis")
        flag_premature_exit = sum(1 for t in trades if t.premature_exit is True)
        flag_moved_stop = sum(1 for t in trades if t.moved_stop is True)

        # Primary diagnosis — conservative thresholds
        exit_concern = early_exit_pct is not None and early_exit_pct >= 40
        # entry_concern requires >= 3 losses to avoid micro-sample over-inference
        entry_concern = (
            stop_hit_pct is not None and stop_hit_pct >= 60
            and len(losses) >= 3
            and (
                (entry_flagged_stop_hit_pct is not None and entry_flagged_stop_hit_pct >= 25)
                or flag_plan_dev >= 2
                or flag_problem_analysis >= 2
            )
        )
        # Sparse flags (< 20% coverage) reduce confidence on any entry-side inference
        flags_sparse = flag_coverage_pct < 20

        if total < 5:
            primary_diagnosis = "unclear"
            confidence = "low"
        elif exit_concern and entry_concern:
            primary_diagnosis = "mixed"
            # Sparse flags undermine the entry side of a mixed diagnosis
            confidence = "low" if (total < 10 or flags_sparse) else "moderate"
        elif exit_concern:
            primary_diagnosis = "exit_discipline"
            confidence = "high" if (total >= 10 and (early_exit_pct or 0) >= 50) else "moderate"
        elif entry_concern:
            primary_diagnosis = "entry_quality"
            # Always moderate at best — entry inference requires self-reporting;
            # downgrade to low when flag coverage is sparse
            confidence = "low" if flags_sparse else "moderate"
        else:
            primary_diagnosis = "unclear"
            confidence = "low"

        # Coaching signals
        signals: List[str] = []

        if flag_coverage_pct < 20 and total >= 5:
            signals.append(
                f"Journal flag coverage is {flag_coverage_pct:.0f}% of classified trades. "
                f"Tagging early_entry, chasing, followed_plan, and problem_source will improve "
                f"entry-side inference."
            )

        if early_exit_pct is not None:
            n_early = len(wins_before_tgt)
            n_tp = len(wins_with_tp)
            if early_exit_pct >= 50:
                signals.append(
                    f"{early_exit_pct:.0f}% of wins with a known target were exited before the "
                    f"target ({n_early}/{n_tp} trades). Exit discipline is the primary source of "
                    f"R leakage visible in this data."
                )
            elif early_exit_pct >= 40:
                signals.append(
                    f"{early_exit_pct:.0f}% of wins with a known target were exited early "
                    f"({n_early}/{n_tp} trades). Exit discipline is a visible drag on realized R."
                )
            elif early_exit_pct < 25 and len(wins_with_tp) >= 3:
                signals.append(
                    f"Most wins with a known target ({100 - early_exit_pct:.0f}%) reached it — "
                    f"exit discipline on winners appears solid."
                )

        if stop_hit_pct is not None and stop_hit_pct >= 60:
            n_sh = len(stop_hits)
            n_l = len(losses)
            if entry_concern and entry_flagged_stop_hit_pct is not None:
                signals.append(
                    f"{stop_hit_pct:.0f}% of losses hit the full stop ({n_sh}/{n_l}). "
                    f"{entry_flagged_stop_hit_pct:.0f}% of those had entry quality flags — "
                    f"entry selection or timing may be a contributing factor. "
                    f"Note: without MAE data this remains inferential."
                )
            else:
                signals.append(
                    f"{stop_hit_pct:.0f}% of losses hit the full stop ({n_sh}/{n_l}). "
                    f"Without max adverse excursion (MAE) data, it is not possible to determine "
                    f"whether these are bad entries or good entries reversed by the market."
                )

        if flag_premature_exit >= 2:
            signals.append(
                f"{flag_premature_exit} trades self-tagged as premature exits — "
                f"exit discipline is explicitly recognized in the trade journal."
            )

        if flag_moved_stop >= 2:
            signals.append(
                f"{flag_moved_stop} trades had a moved stop. "
                f"Stop placement or management discipline may be a contributing factor."
            )

        return EntryExitQualityReport(
            total_trades=len(trades),
            classified_trades=total,
            wins_total=len(wins),
            wins_with_tp_info=len(wins_with_tp),
            wins_hit_target=len(wins_hit_tgt),
            wins_before_target=len(wins_before_tgt),
            early_exit_pct=early_exit_pct,
            losses_total=len(losses),
            stop_hit_count=len(stop_hits),
            manual_cut_count=len(manual_cuts),
            stop_hit_pct_of_losses=stop_hit_pct,
            entry_flagged_losses=len(entry_flagged_losses),
            entry_flagged_stop_hits=len(entry_flagged_stop_hits),
            entry_flagged_stop_hit_pct=entry_flagged_stop_hit_pct,
            flag_coverage_pct=flag_coverage_pct,
            flag_early_entry=flag_early_entry,
            flag_chasing=flag_chasing,
            flag_fomo=flag_fomo,
            flag_plan_deviation_on_loss=flag_plan_dev,
            flag_weak_setup_on_loss=flag_weak_setup,
            flag_problem_analysis=flag_problem_analysis,
            flag_premature_exit=flag_premature_exit,
            flag_moved_stop=flag_moved_stop,
            primary_diagnosis=primary_diagnosis,
            confidence=confidence,
            coaching_signals=signals,
        )

    # ── Daily plan adherence ────────────────────────────────────────────────────

    @staticmethod
    def compute_daily_adherence(
        plan: object,  # DailyPlan — avoid circular import; duck-typed
        trades: List[Trade],
    ) -> DailyAdherenceReport:
        """
        Compare closed trades for plan.trading_date against the DailyPlan rules.

        Rules checked:
          - max_trades: trades_taken vs plan.max_trades
          - allowed_setups: trade.setup_type must be in the allowed list
          - disallowed_setups: trade.setup_type must NOT be in the disallowed list

        NOT checked:
          - daily_max_risk_pct: requires per-trade risk % which needs instrument-specific
            pip values not currently available in Trade fields.

        trades should already be filtered to the plan's trading_date by the caller.
        """
        total = len(trades)
        planned_count = sum(1 for t in trades if t.trade_plan_id is not None)
        unplanned_count = total - planned_count

        # Normalize for case-insensitive matching
        allowed: set = {s.strip().lower() for s in (plan.allowed_setups or [])}
        disallowed: set = {s.strip().lower() for s in (plan.disallowed_setups or [])}

        # Max trades check
        max_limit = plan.max_trades
        exceeded = (max_limit is not None) and (total > max_limit)
        exceeded_by = (total - max_limit) if exceeded else 0

        # Per-trade setup checks
        outside_allowed: List[str] = []
        disallowed_violations: List[SetupViolation] = []
        untagged = 0

        for t in trades:
            st = t.setup_type
            if st is None:
                untagged += 1
                continue
            st_norm = st.strip().lower()
            if allowed and st_norm not in allowed:
                outside_allowed.append(st)
            if disallowed and st_norm in disallowed:
                disallowed_violations.append(SetupViolation(trade_id=t.trade_id, setup_type=st))

        outside_allowed_setups = sorted(set(outside_allowed))
        outside_allowed_count = len(outside_allowed)

        # Build plain-English signals
        signals: List[str] = []
        if exceeded:
            signals.append(
                f"Daily max trades exceeded: took {total} trades against a limit of "
                f"{max_limit} (+{exceeded_by})."
            )
        if allowed and outside_allowed_count > 0:
            pct = round(outside_allowed_count / total * 100) if total else 0
            setups_str = ", ".join(f'"{s}"' for s in outside_allowed_setups[:3])
            more = f" and {len(outside_allowed_setups) - 3} more" if len(outside_allowed_setups) > 3 else ""
            signals.append(
                f"{outside_allowed_count}/{total} trade(s) used setups outside the daily "
                f"allowed list ({pct}%): {setups_str}{more}."
            )
        if disallowed_violations:
            n = len(disallowed_violations)
            types_str = ", ".join(f'"{s}"' for s in sorted({v.setup_type for v in disallowed_violations}))
            signals.append(
                f"{n} trade(s) used explicitly disallowed setups: {types_str}."
            )
        if unplanned_count > 0 and total > 0:
            if planned_count == 0:
                signals.append(f"All {total} trade(s) were unplanned (no linked TradePlan).")
            else:
                signals.append(
                    f"{unplanned_count} unplanned trade(s) (no linked TradePlan), "
                    f"{planned_count} planned."
                )
        if untagged > 0 and (allowed or disallowed):
            signals.append(
                f"{untagged} trade(s) missing setup_type — could not check setup adherence for them."
            )

        return DailyAdherenceReport(
            trading_date=plan.trading_date,
            trades_taken=total,
            planned_count=planned_count,
            unplanned_count=unplanned_count,
            max_trades_limit=max_limit,
            max_trades_exceeded=exceeded,
            max_trades_exceeded_by=exceeded_by,
            allowed_setups_configured=bool(allowed),
            outside_allowed_count=outside_allowed_count,
            outside_allowed_setups=outside_allowed_setups,
            disallowed_setups_configured=bool(disallowed),
            disallowed_violation_count=len(disallowed_violations),
            disallowed_violations=disallowed_violations,
            untagged_count=untagged,
            discipline_signals=signals,
        )
