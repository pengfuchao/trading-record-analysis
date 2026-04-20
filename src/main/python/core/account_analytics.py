from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from src.main.python.core.metrics_calculator import MetricsCalculator
from src.main.python.core.performance_summary import (
    AccountReport, PerformanceSummary, PlanAdherenceGroup, PlanAdherenceReport,
    RRComparisonReport,
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
