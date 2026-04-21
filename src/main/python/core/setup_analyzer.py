from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from src.main.python.core.mistake_analyzer import MistakeAnalyzer
from src.main.python.models.enums import TradeResult
from src.main.python.models.setup import SetupReport, SetupStats
from src.main.python.models.trade import Trade
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Minimum trades in a sub-segment to qualify as "best" or "worst" condition.
_MIN_TRADES_FOR_CONDITION = 2


class SetupAnalyzer:
    """
    Stateless service that computes per-setup performance metrics from historical trades.

    Trades link to setups via trade.setup_type. Trades where setup_type is None or empty
    are counted in total_trades_analyzed but excluded from by_setup statistics.
    """

    def generate_report(self, trades: List[Trade], account_id: str) -> SetupReport:
        if not trades:
            return SetupReport(account_id=account_id, total_trades_analyzed=0)

        total = len(trades)
        trades_with_setup = [t for t in trades if t.setup_type]

        # Group by setup_type
        groups: Dict[str, List[Trade]] = {}
        for trade in trades_with_setup:
            groups.setdefault(trade.setup_type, []).append(trade)

        by_setup: Dict[str, SetupStats] = {
            setup_type: self._compute_stats(setup_type, setup_trades)
            for setup_type, setup_trades in groups.items()
        }

        ranked_by_win_rate = sorted(
            by_setup, key=lambda s: by_setup[s].win_rate or 0.0, reverse=True
        )
        ranked_by_expectancy = sorted(
            by_setup, key=lambda s: by_setup[s].expectancy or 0.0, reverse=True
        )
        ranked_by_avg_r = sorted(
            by_setup, key=lambda s: by_setup[s].avg_r_multiple or 0.0, reverse=True
        )
        ranked_by_total_profit = sorted(
            by_setup, key=lambda s: by_setup[s].total_net_profit, reverse=True
        )
        ranked_by_drawdown = sorted(
            by_setup, key=lambda s: by_setup[s].max_drawdown or 0.0
        )
        ranked_by_rr_realization = sorted(
            [s for s in by_setup if by_setup[s].rr_sample_count >= 1],
            key=lambda s: by_setup[s].rr_realization_pct or 0.0,
            reverse=True,
        )

        logger.info(
            "SetupAnalyzer: account=%s trades=%d with_setup=%d unique_setups=%d",
            account_id, total, len(trades_with_setup), len(by_setup),
        )

        return SetupReport(
            account_id=account_id,
            total_trades_analyzed=total,
            trades_with_setup=len(trades_with_setup),
            by_setup=by_setup,
            ranked_by_win_rate=ranked_by_win_rate,
            ranked_by_expectancy=ranked_by_expectancy,
            ranked_by_avg_r=ranked_by_avg_r,
            ranked_by_total_profit=ranked_by_total_profit,
            ranked_by_drawdown=ranked_by_drawdown,
            ranked_by_rr_realization=ranked_by_rr_realization,
        )

    @staticmethod
    def _compute_stats(setup_type: str, trades: List[Trade]) -> SetupStats:
        count = len(trades)
        results = [t.result for t in trades if t.result is not None]
        pnls = [t.net_pnl for t in trades if t.net_pnl is not None]
        r_multiples = [t.actual_r_multiple for t in trades if t.actual_r_multiple is not None]

        # Win / loss / breakeven rates
        wins = sum(1 for r in results if r == TradeResult.WIN)
        losses = sum(1 for r in results if r == TradeResult.LOSS)
        breakevens = sum(1 for r in results if r == TradeResult.BREAKEVEN)
        n_results = len(results)
        win_rate = wins / n_results if n_results else None
        loss_rate = losses / n_results if n_results else None
        breakeven_rate = breakevens / n_results if n_results else None

        # PnL metrics
        total_net_profit = sum(pnls)
        expectancy = total_net_profit / count if count else None
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else None

        win_pnls = [t.net_pnl for t in trades if t.result == TradeResult.WIN and t.net_pnl is not None]
        loss_pnls = [t.net_pnl for t in trades if t.result == TradeResult.LOSS and t.net_pnl is not None]
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else None
        avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else None

        gross_profit = sum(p for p in win_pnls)
        gross_loss = abs(sum(p for p in loss_pnls))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

        # Drawdown (cumulative)
        max_drawdown = SetupAnalyzer._compute_max_drawdown(pnls)

        # Max consecutive losses
        max_consec_losses = SetupAnalyzer._max_consecutive_losses(results)

        # Avg holding duration
        durations = [
            t.holding_duration.total_seconds()
            for t in trades
            if t.holding_duration is not None
        ]
        avg_dur = sum(durations) / len(durations) if durations else None

        # Execution quality
        a_plus_flags = [t.is_a_plus_setup for t in trades if t.is_a_plus_setup is not None]
        a_plus_rate = sum(a_plus_flags) / len(a_plus_flags) if a_plus_flags else None

        plan_flags = [t.followed_plan for t in trades if t.followed_plan is not None]
        followed_plan_rate = sum(plan_flags) / len(plan_flags) if plan_flags else None

        # Condition breakdowns
        by_session = SetupAnalyzer._win_rate_by_key(trades, lambda t: t.session)
        by_market_cond = SetupAnalyzer._win_rate_by_key(trades, lambda t: t.market_condition)
        by_symbol = SetupAnalyzer._win_rate_by_key(trades, lambda t: t.symbol)

        best_session, worst_session = SetupAnalyzer._best_worst(
            by_session, trades, lambda t: t.session
        )
        best_market, worst_market = SetupAnalyzer._best_worst(
            by_market_cond, trades, lambda t: t.market_condition
        )
        best_symbol, worst_symbol = SetupAnalyzer._best_worst(
            by_symbol, trades, lambda t: t.symbol
        )

        # Common mistakes
        common_mistakes = SetupAnalyzer._extract_mistakes(trades)

        # Planned R:R vs realized R for this setup
        # Requires trade.planned_rr to be pre-populated by the calling route
        # (same enrichment pattern as analytics.py get_plan_adherence).
        rr_qualifying = [
            t for t in trades
            if t.trade_plan_id is not None
            and t.planned_rr is not None
            and t.planned_rr > 0
            and t.actual_r_multiple is not None
        ]
        rr_n = len(rr_qualifying)
        rr_avg_planned_rr: Optional[float] = None
        rr_avg_actual_r: Optional[float] = None
        rr_avg_shortfall: Optional[float] = None
        rr_realization_pct: Optional[float] = None
        rr_pct_met_target: Optional[float] = None

        if rr_n >= 1:
            rr_avg_planned_rr = round(sum(t.planned_rr for t in rr_qualifying) / rr_n, 2)
            rr_avg_actual_r = round(sum(t.actual_r_multiple for t in rr_qualifying) / rr_n, 2)
            rr_avg_shortfall = round(rr_avg_actual_r - rr_avg_planned_rr, 2)
            rr_realization_pct = (
                round((rr_avg_actual_r / rr_avg_planned_rr) * 100, 1)
                if rr_avg_planned_rr != 0 else None
            )
            met = sum(1 for t in rr_qualifying if t.actual_r_multiple >= t.planned_rr)
            rr_pct_met_target = round(met / rr_n * 100, 1)

        return SetupStats(
            setup_type=setup_type,
            trade_count=count,
            win_rate=win_rate,
            loss_rate=loss_rate,
            breakeven_rate=breakeven_rate,
            expectancy=expectancy,
            avg_r_multiple=avg_r,
            profit_factor=profit_factor,
            total_net_profit=total_net_profit,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_drawdown,
            max_consecutive_losses=max_consec_losses,
            avg_holding_duration_seconds=avg_dur,
            a_plus_rate=a_plus_rate,
            followed_plan_rate=followed_plan_rate,
            by_session=by_session,
            by_market_condition=by_market_cond,
            by_symbol=by_symbol,
            best_session=best_session,
            worst_session=worst_session,
            best_market_condition=best_market,
            worst_market_condition=worst_market,
            best_symbol=best_symbol,
            worst_symbol=worst_symbol,
            common_mistakes=common_mistakes,
            rr_sample_count=rr_n,
            rr_avg_planned_rr=rr_avg_planned_rr,
            rr_avg_actual_r=rr_avg_actual_r,
            rr_avg_shortfall=rr_avg_shortfall,
            rr_realization_pct=rr_realization_pct,
            rr_pct_met_target=rr_pct_met_target,
        )

    @staticmethod
    def _win_rate_by_key(
        trades: List[Trade],
        key_fn: Callable[[Trade], Optional[str]],
    ) -> Dict[str, float]:
        """Group trades by key_fn; compute win_rate for each group. Excludes None keys."""
        groups: Dict[str, List[Trade]] = {}
        for t in trades:
            key = key_fn(t)
            if key:
                groups.setdefault(key, []).append(t)
        result: Dict[str, float] = {}
        for key, group in groups.items():
            results = [t.result for t in group if t.result is not None]
            if results:
                result[key] = sum(1 for r in results if r == TradeResult.WIN) / len(results)
        return result

    @staticmethod
    def _best_worst(
        breakdown: Dict[str, float],
        trades: List[Trade],
        key_fn: Callable[[Trade], Optional[str]],
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Return (best_key, worst_key) by win_rate.
        A key must have at least _MIN_TRADES_FOR_CONDITION trades to qualify.
        """
        # Count trades per key
        key_counts: Counter = Counter(key_fn(t) for t in trades if key_fn(t))
        qualified = {k: v for k, v in breakdown.items() if key_counts.get(k, 0) >= _MIN_TRADES_FOR_CONDITION}
        if not qualified:
            return None, None
        best = max(qualified, key=lambda k: qualified[k])
        worst = min(qualified, key=lambda k: qualified[k])
        return best, worst

    @staticmethod
    def _extract_mistakes(trades: List[Trade]) -> Dict[str, int]:
        """Count mistake tags across all trades using MistakeAnalyzer's tag extraction."""
        counter: Counter = Counter()
        for trade in trades:
            for tag in MistakeAnalyzer._extract_tags(trade):
                counter[tag] += 1
        return dict(counter)

    @staticmethod
    def _compute_max_drawdown(pnls: List[float]) -> Optional[float]:
        """Running peak drawdown from cumulative PnL sequence."""
        if not pnls:
            return None
        peak = 0.0
        max_dd = 0.0
        cumulative = 0.0
        for p in pnls:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = cumulative - peak
            if dd < max_dd:
                max_dd = dd
        return max_dd if max_dd < 0 else None

    @staticmethod
    def _max_consecutive_losses(results: List[TradeResult]) -> int:
        max_streak = 0
        streak = 0
        for r in results:
            if r == TradeResult.LOSS:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return max_streak
