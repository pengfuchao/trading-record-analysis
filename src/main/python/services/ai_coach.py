from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.models.enums import TradeResult
from src.main.python.core.mistake_analyzer import MistakeAnalyzer
from src.main.python.core.performance_summary import ExitDecompositionReport, PlanAdherenceGroup, RRComparisonReport
from src.main.python.core.setup_analyzer import SetupAnalyzer
from src.main.python.models.account import Account
from src.main.python.models.trade import Trade
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ── Coaching context (shared between AI and fallback paths) ────────────────────

@dataclass
class CoachingContext:
    """Pre-computed coaching signals extracted from trades. Both paths use this."""
    from_date: Optional[date]
    to_date: Optional[date]
    total_trades: int
    win_rate_pct: float
    total_net_pnl: float
    profit_factor: Optional[float]
    expectancy: float
    max_drawdown: float
    followed_plan_rate: Optional[float]
    a_plus_rate: Optional[float]
    source_counts: dict            # {problem_source: count}
    top_mistakes: list             # [{tag, count, total_cost, after_loss_rate}]
    mistake_report: object         # MistakeReport domain object

    # Plan-awareness signals
    planned_trade_count: int = 0           # trades with a linked trade plan
    unplanned_trade_count: int = 0         # trades without a linked trade plan

    # Plan-vs-execution performance differentials (populated when n >= 3 per group)
    planned_win_rate:     Optional[float] = None   # win rate for planned trades
    unplanned_win_rate:   Optional[float] = None
    planned_avg_pnl:      Optional[float] = None   # avg PnL per planned trade
    unplanned_avg_pnl:    Optional[float] = None
    followed_win_rate:    Optional[float] = None   # win rate for followed_plan=True
    deviated_win_rate:    Optional[float] = None   # win rate for followed_plan=False
    followed_avg_pnl:     Optional[float] = None
    deviated_avg_pnl:     Optional[float] = None
    deviated_total_pnl:   Optional[float] = None   # total PnL cost of deviations
    deviated_count:       int = 0                  # count of followed_plan=False trades
    linked_but_deviated_count: int = 0             # has plan AND followed_plan=False

    # Planned R:R vs realized R (populated when >= 3 qualifying trades exist)
    rr_sample_count:    int = 0
    avg_planned_rr:     Optional[float] = None     # mean planned_rr across qualifying trades
    avg_actual_r:       Optional[float] = None     # mean actual_r_multiple across qualifying trades
    realization_pct:    Optional[float] = None     # (avg_actual_r / avg_planned_rr) * 100
    pct_met_rr_target:  Optional[float] = None     # % of linked trades that reached planned_rr

    # Per-setup R:R breakdown (populated when >= 3 qualifying trades per setup)
    worst_rr_setup:                 Optional[str]   = None  # setup with lowest realization_pct
    worst_rr_setup_realization_pct: Optional[float] = None
    best_rr_setup:                  Optional[str]   = None  # setup with highest realization_pct
    best_rr_setup_realization_pct:  Optional[float] = None

    # R:R realization trend (populated when >= 4 weekly buckets with data)
    rr_trend_signal: Optional[str] = None   # "improving" | "worsening" | "stable" | None

    # Per-symbol / per-session edge signals (n >= 3 per slot)
    best_symbol: Optional[str] = None
    worst_symbol: Optional[str] = None
    worst_symbol_total_pnl: Optional[float] = None
    worst_symbol_win_rate_pct: Optional[float] = None
    best_session: Optional[str] = None
    worst_session: Optional[str] = None
    worst_session_pf: Optional[float] = None
    best_session_pf: Optional[float] = None

    # Exit outcome decomposition (populated when total_classified >= 3)
    exit_stop_hit_pct: Optional[float] = None        # % of classified trades that hit stop
    exit_manual_cut_pct: Optional[float] = None      # % of losses that were manual cuts
    exit_target_hit_pct: Optional[float] = None      # % of TP-eligible wins that reached target
    exit_unclear_pct: Optional[float] = None         # % of classified trades that are unclear
    exit_decomp_signals: List[str] = field(default_factory=list)


# ── Generation result ──────────────────────────────────────────────────────────

@dataclass
class ReviewResult:
    """
    Structured output from one generation attempt.
    source: "ai" | "fallback"
    status: "success" | "fallback" | "error"
    """
    summary: str
    top_mistakes: List[dict]       # [{tag, pattern}]
    diagnosis: str
    improvement: str
    source: str                    # "ai" | "fallback"
    status: str                    # "success" | "fallback" | "error"
    model_used: str
    raw_response: Optional[str] = None
    error_message: Optional[str] = None

    def to_output_dict(self) -> dict:
        return {
            "summary": self.summary,
            "top_mistakes": self.top_mistakes,
            "diagnosis": self.diagnosis,
            "improvement": self.improvement,
        }


# ── Main service ───────────────────────────────────────────────────────────────

class AICoachService:
    """
    Module 7 — AI Coaching (v1.5).

    Generation flow:
      1. Build CoachingContext from trades (common path).
      2. Attempt AI generation (Claude Haiku).
         - One retry on transient connection errors.
         - Falls back to rule-based generator on:
             • missing ANTHROPIC_API_KEY
             • any Anthropic API error (auth, rate limit, server error)
             • JSON parse failure after all recovery attempts
      3. Return ReviewResult with source/status metadata.

    Callers (routes) are responsible for persistence.
    """

    AI_MODEL = "claude-haiku-4-5-20251001"
    FALLBACK_MODEL = "rule_based_fallback"
    MAX_TOKENS = 1024

    def generate(
        self,
        trades: List[Trade],
        account: Account,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> ReviewResult:
        """
        Generate a coaching review. Always returns a ReviewResult — never raises.
        Falls back to rule-based output if AI is unavailable or fails.
        """
        ctx = self._build_context(trades, account, from_date, to_date)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set — using rule-based fallback")
            return self._fallback(ctx, error="ANTHROPIC_API_KEY not set")

        return self._try_ai(ctx, api_key)

    # ── Context builder (shared) ───────────────────────────────────────────────

    @staticmethod
    def _build_context(
        trades: List[Trade],
        account: Account,
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> CoachingContext:
        report = AccountAnalytics.generate_report(trades, account)
        mistake_report = MistakeAnalyzer().generate_report(trades, account.account_id)
        o = report.overall
        total = len(trades)

        followed_count = sum(1 for t in trades if t.followed_plan is True)
        a_plus_count = sum(1 for t in trades if t.is_a_plus_setup is True)
        planned_count = sum(1 for t in trades if t.trade_plan_id is not None)
        source_counts: dict = {}
        for t in trades:
            if t.problem_source:
                source_counts[t.problem_source] = source_counts.get(t.problem_source, 0) + 1

        top_mistakes = []
        for tag in mistake_report.ranked_by_cost[:3]:
            s = mistake_report.by_mistake[tag]
            top_mistakes.append({
                "tag": tag,
                "count": s.occurrence_count,
                "total_cost": round(s.total_cost, 2),
                "after_loss_rate": s.after_loss_rate,
            })

        # Plan-vs-execution performance differentials
        plan_report = AccountAnalytics.compute_plan_adherence(trades)
        MIN_N = 3

        def _wr(g: PlanAdherenceGroup) -> Optional[float]:
            return round((g.win_rate or 0) * 100, 1) if g.count >= MIN_N else None

        def _pnl(g: PlanAdherenceGroup) -> Optional[float]:
            return g.avg_pnl if g.count >= MIN_N else None

        rr = plan_report.rr_comparison

        # R:R realization trend (weekly buckets)
        trend = AccountAnalytics.compute_rr_trend(trades)

        # Per-setup R:R breakdown — find best and worst setups by realization_pct
        # Trades already have planned_rr pre-populated by the calling route.
        setup_report = SetupAnalyzer().generate_report(trades, account.account_id)
        rr_setups = {
            k: v for k, v in setup_report.by_setup.items()
            if v.rr_sample_count >= MIN_N and v.rr_realization_pct is not None
        }
        best_rr_setup: Optional[str] = None
        best_rr_setup_pct: Optional[float] = None
        worst_rr_setup: Optional[str] = None
        worst_rr_setup_pct: Optional[float] = None
        if rr_setups:
            best_key = max(rr_setups, key=lambda k: rr_setups[k].rr_realization_pct or 0.0)
            worst_key = min(rr_setups, key=lambda k: rr_setups[k].rr_realization_pct or 0.0)
            best_rr_setup = best_key
            best_rr_setup_pct = rr_setups[best_key].rr_realization_pct
            worst_rr_setup = worst_key
            worst_rr_setup_pct = rr_setups[worst_key].rr_realization_pct
            # Only report best/worst when they are meaningfully different setups
            if best_rr_setup == worst_rr_setup:
                best_rr_setup = None
                best_rr_setup_pct = None

        # Symbol/session edge signals
        _MIN_SEG = 3
        sym_rows = [
            (name, s) for name, s in report.by_symbol.items()
            if s.total_trades >= _MIN_SEG
        ]
        sess_rows = [
            (name, s) for name, s in report.by_session.items()
            if s.total_trades >= _MIN_SEG and name != "Unknown"
        ]

        best_symbol: Optional[str] = None
        worst_symbol: Optional[str] = None
        worst_symbol_total_pnl: Optional[float] = None
        worst_symbol_win_rate_pct: Optional[float] = None
        if len(sym_rows) >= 2:
            best_sym = max(sym_rows, key=lambda x: x[1].total_net_profit)
            worst_sym = min(sym_rows, key=lambda x: x[1].total_net_profit)
            if best_sym[0] != worst_sym[0]:
                best_symbol = best_sym[0]
                worst_symbol = worst_sym[0]
                worst_symbol_total_pnl = round(worst_sym[1].total_net_profit, 2)
                worst_symbol_win_rate_pct = (
                    round((worst_sym[1].win_rate or 0) * 100, 1)
                    if worst_sym[1].win_rate is not None else None
                )

        best_session: Optional[str] = None
        worst_session: Optional[str] = None
        worst_session_pf: Optional[float] = None
        best_session_pf: Optional[float] = None
        if len(sess_rows) >= 2:
            best_sess = max(sess_rows, key=lambda x: x[1].profit_factor or 0.0)
            worst_sess = min(sess_rows, key=lambda x: x[1].profit_factor or 0.0)
            if best_sess[0] != worst_sess[0]:
                best_session = best_sess[0]
                worst_session = worst_sess[0]
                worst_session_pf = worst_sess[1].profit_factor
                best_session_pf = best_sess[1].profit_factor

        # Exit outcome decomposition
        exit_report = AccountAnalytics.compute_exit_decomposition(trades)
        exit_stop_hit_pct: Optional[float] = None
        exit_manual_cut_pct: Optional[float] = None
        exit_target_hit_pct: Optional[float] = None
        exit_unclear_pct: Optional[float] = None
        if exit_report.total_classified >= 3:
            exit_stop_hit_pct = exit_report.stop_hit.pct_of_total
            exit_unclear_pct = exit_report.unclear.pct_of_total
            # Denominator: all classified LOSS-result trades (includes unclear losses
            # in the grey zone, not just stop_hit + manual_cut).
            n_classified_losses = sum(
                1 for t in trades
                if t.actual_r_multiple is not None and t.result == TradeResult.LOSS
            )
            if n_classified_losses > 0 and exit_report.manual_cut.count > 0:
                exit_manual_cut_pct = round(exit_report.manual_cut.count / n_classified_losses * 100, 1)
            tp_wins = exit_report.target_hit.count + exit_report.exit_before_target.count
            if tp_wins > 0:
                exit_target_hit_pct = round(exit_report.target_hit.count / tp_wins * 100, 1)

        return CoachingContext(
            from_date=from_date,
            to_date=to_date,
            total_trades=o.total_trades,
            win_rate_pct=round((o.win_rate or 0) * 100, 1),
            total_net_pnl=round(o.total_net_profit, 2),
            profit_factor=o.profit_factor,
            expectancy=round(o.expectancy or 0, 2),
            max_drawdown=round(o.max_drawdown or 0, 2),
            followed_plan_rate=round(followed_count / total * 100, 1) if total else None,
            a_plus_rate=round(a_plus_count / total * 100, 1) if total else None,
            source_counts=source_counts,
            top_mistakes=top_mistakes,
            mistake_report=mistake_report,
            planned_trade_count=planned_count,
            unplanned_trade_count=total - planned_count,
            planned_win_rate=_wr(plan_report.planned),
            unplanned_win_rate=_wr(plan_report.unplanned),
            planned_avg_pnl=_pnl(plan_report.planned),
            unplanned_avg_pnl=_pnl(plan_report.unplanned),
            followed_win_rate=_wr(plan_report.followed),
            deviated_win_rate=_wr(plan_report.deviated),
            followed_avg_pnl=_pnl(plan_report.followed),
            deviated_avg_pnl=_pnl(plan_report.deviated),
            deviated_total_pnl=(
                plan_report.deviated.total_pnl
                if plan_report.deviated_count >= MIN_N else None
            ),
            deviated_count=plan_report.deviated_count,
            linked_but_deviated_count=plan_report.linked_but_deviated_count,
            rr_sample_count=rr.sample_count if rr else 0,
            avg_planned_rr=rr.avg_planned_rr if rr and rr.sample_count >= MIN_N else None,
            avg_actual_r=rr.avg_actual_r if rr and rr.sample_count >= MIN_N else None,
            realization_pct=rr.realization_pct if rr and rr.sample_count >= MIN_N else None,
            pct_met_rr_target=rr.pct_met_target if rr and rr.sample_count >= MIN_N else None,
            worst_rr_setup=worst_rr_setup,
            worst_rr_setup_realization_pct=worst_rr_setup_pct,
            best_rr_setup=best_rr_setup,
            best_rr_setup_realization_pct=best_rr_setup_pct,
            rr_trend_signal=trend.trend_signal,
            best_symbol=best_symbol,
            worst_symbol=worst_symbol,
            worst_symbol_total_pnl=worst_symbol_total_pnl,
            worst_symbol_win_rate_pct=worst_symbol_win_rate_pct,
            best_session=best_session,
            worst_session=worst_session,
            worst_session_pf=worst_session_pf,
            best_session_pf=best_session_pf,
            exit_stop_hit_pct=exit_stop_hit_pct,
            exit_manual_cut_pct=exit_manual_cut_pct,
            exit_target_hit_pct=exit_target_hit_pct,
            exit_unclear_pct=exit_unclear_pct,
            exit_decomp_signals=exit_report.coaching_signals,
        )

    # ── AI path ────────────────────────────────────────────────────────────────

    def _try_ai(self, ctx: CoachingContext, api_key: str) -> ReviewResult:
        import anthropic

        prompt = self._build_prompt(ctx)
        client = anthropic.Anthropic(api_key=api_key)
        raw: Optional[str] = None

        try:
            raw = self._call_api(client, prompt)
        except anthropic.APIConnectionError as exc:
            # One retry for transient network errors
            logger.warning("AI coach connection error, retrying once: %s", exc)
            try:
                raw = self._call_api(client, prompt)
            except Exception as exc2:
                logger.error("AI coach retry failed: %s", exc2)
                return self._fallback(ctx, error=str(exc2), raw=raw)
        except Exception as exc:
            # Auth, rate limit, server error — go straight to fallback
            logger.error("AI coach API error: %s", exc)
            return self._fallback(ctx, error=str(exc))

        # Parse response
        try:
            parsed = self._parse_response(raw)
        except ValueError as exc:
            logger.error("AI coach parse failed: %s", exc)
            return self._fallback(ctx, error=str(exc), raw=raw)

        # Validate required keys
        for key in ("summary", "top_mistakes", "diagnosis", "improvement"):
            if key not in parsed:
                err = f"AI response missing required key '{key}'"
                logger.error(err)
                return self._fallback(ctx, error=err, raw=raw)

        logger.info(
            "AI coach success: model=%s top_mistakes=%d",
            self.AI_MODEL, len(parsed.get("top_mistakes", [])),
        )
        return ReviewResult(
            summary=str(parsed["summary"]),
            top_mistakes=parsed.get("top_mistakes", []),
            diagnosis=str(parsed["diagnosis"]),
            improvement=str(parsed["improvement"]),
            source="ai",
            status="success",
            model_used=self.AI_MODEL,
            raw_response=raw,
        )

    def _call_api(self, client, prompt: str) -> str:
        message = client.messages.create(
            model=self.AI_MODEL,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        logger.info("AI coach raw response length=%d", len(raw))
        return raw

    # ── Fallback (rule-based) ──────────────────────────────────────────────────

    def _fallback(
        self,
        ctx: CoachingContext,
        error: Optional[str] = None,
        raw: Optional[str] = None,
    ) -> ReviewResult:
        logger.info("Using rule-based fallback coaching review (reason: %s)", error or "unknown")
        sections = self._generate_fallback_sections(ctx)
        return ReviewResult(
            summary=sections["summary"],
            top_mistakes=sections["top_mistakes"],
            diagnosis=sections["diagnosis"],
            improvement=sections["improvement"],
            source="fallback",
            status="fallback",
            model_used=self.FALLBACK_MODEL,
            raw_response=raw,
            error_message=error,
        )

    @staticmethod
    def _generate_fallback_sections(ctx: CoachingContext) -> dict:
        """
        Deterministic, template-based coaching review.
        Always produces valid output for the 4 required sections.
        """
        # ── Summary ────────────────────────────────────────────────────────────
        pnl_str = f"+${ctx.total_net_pnl:.2f}" if ctx.total_net_pnl >= 0 else f"-${abs(ctx.total_net_pnl):.2f}"
        pf_str = f"{ctx.profit_factor:.2f}" if ctx.profit_factor is not None else "N/A"
        plan_str = (
            f" {ctx.followed_plan_rate}% of trades followed the plan."
            if ctx.followed_plan_rate is not None else ""
        )
        summary = (
            f"This period covered {ctx.total_trades} trades with a {ctx.win_rate_pct}% win rate "
            f"and net PnL of {pnl_str} (profit factor: {pf_str})."
            f"{plan_str}"
            f" Max drawdown reached ${abs(ctx.max_drawdown):.2f}."
        )

        # ── Top mistakes ───────────────────────────────────────────────────────
        fallback_mistakes = []
        for m in ctx.top_mistakes:
            tag = m["tag"]
            count = m["count"]
            cost = m["total_cost"]
            alr = m.get("after_loss_rate")

            pattern = (
                f"Occurred {count} time{'s' if count != 1 else ''}, "
                f"costing ${abs(cost):.2f} in total."
            )
            if alr is not None and alr >= 0.5:
                pattern += " Strongly correlated with trades placed after a loss — likely revenge-trading trigger."
            elif alr is not None and alr >= 0.3:
                pattern += " Moderately elevated after losing trades."

            fallback_mistakes.append({"tag": tag, "pattern": pattern})

        # ── Diagnosis ──────────────────────────────────────────────────────────
        dominant_source = None
        if ctx.source_counts:
            dominant_source = max(ctx.source_counts, key=lambda k: ctx.source_counts[k])

        source_map = {
            "execution":  "execution discipline",
            "psychology": "psychological control",
            "analysis":   "analysis quality",
            "risk":       "risk management",
        }

        # Plan adherence diagnosis signals
        followed_worse = (
            ctx.followed_avg_pnl is not None
            and ctx.deviated_avg_pnl is not None
            and ctx.deviated_avg_pnl > ctx.followed_avg_pnl
        )
        planned_worse = (
            ctx.planned_avg_pnl is not None
            and ctx.unplanned_avg_pnl is not None
            and ctx.unplanned_avg_pnl > ctx.planned_avg_pnl
        )

        # R:R realization diagnosis — checked before generic fallbacks
        rr_below_50 = (
            ctx.realization_pct is not None and ctx.realization_pct < 50
            and ctx.rr_sample_count >= 3
        )
        rr_below_80 = (
            ctx.realization_pct is not None and ctx.realization_pct < 80
            and ctx.rr_sample_count >= 3
        )
        rr_above_100 = (
            ctx.realization_pct is not None and ctx.realization_pct >= 100
            and ctx.rr_sample_count >= 3
        )

        if dominant_source and dominant_source in source_map:
            area = source_map[dominant_source]
            pct = round(ctx.source_counts[dominant_source] / sum(ctx.source_counts.values()) * 100)
            diagnosis = (
                f"Your recorded problem_source data points to {area} as the primary issue "
                f"({pct}% of reviewed trades). Focus here before addressing other areas."
            )
        elif rr_below_50:
            diagnosis = (
                f"Severe R:R leakage: you are realizing only {ctx.realization_pct:.0f}% of "
                f"your planned R:R on average ({ctx.avg_actual_r:+.2f}R actual vs "
                f"{ctx.avg_planned_rr:.2f}R planned). "
                f"This level of shortfall is usually driven by premature exits — "
                f"fear of giving back open profit before the planned target is reached. "
                f"Your planning is sound; the gap is in execution at the exit."
            )
        elif rr_below_80:
            diagnosis = (
                f"Execution leakage on exits: you are capturing {ctx.realization_pct:.0f}% of "
                f"your planned R:R ({ctx.avg_actual_r:+.2f}R realized vs "
                f"{ctx.avg_planned_rr:.2f}R planned, n={ctx.rr_sample_count}). "
                f"The most common cause is adjusting take-profits during the trade "
                f"rather than holding to the pre-defined level."
            )
        elif ctx.deviated_avg_pnl is not None and ctx.followed_avg_pnl is not None and not followed_worse:
            diff = (ctx.followed_avg_pnl or 0) - (ctx.deviated_avg_pnl or 0)
            diagnosis = (
                f"Execution discipline is the clearest gap: trades where you deviated from the plan "
                f"underperform by ${diff:.2f}/trade on average. "
                f"Closing this gap is the highest-leverage improvement available."
            )
        elif planned_worse:
            diff = (ctx.unplanned_avg_pnl or 0) - (ctx.planned_avg_pnl or 0)
            diagnosis = (
                f"Unplanned trades are outperforming planned ones by ${diff:.2f}/trade on average. "
                f"This can mean the formal plans are being applied with less conviction than they "
                f"were written with, or that over-analysis is causing hesitation. "
                f"Review whether your planned entries are being executed at the intended levels."
            )
        elif ctx.linked_but_deviated_count > 0:
            n = ctx.linked_but_deviated_count
            trade_word = "trades" if n != 1 else "trade"
            diagnosis = (
                f"You had {n} {trade_word} with a linked plan that "
                f"{'were' if n != 1 else 'was'} then deviated from. "
                f"The gap between planning and execution is the most actionable signal in your data — "
                f"identify the specific rule you broke in each case before the next session."
            )
        elif ctx.followed_plan_rate is not None and ctx.followed_plan_rate < 70:
            diagnosis = (
                f"Plan adherence is low at {ctx.followed_plan_rate}% — execution discipline "
                f"is the main area to address. Trades taken outside the plan are the leading "
                f"source of preventable losses."
            )
        elif ctx.profit_factor is not None and ctx.profit_factor < 1.0:
            diagnosis = (
                "Profit factor is below 1.0, indicating losses exceed gross profits. "
                "Review whether trade entries are based on high-probability analysis "
                "or whether stops are being set too close relative to targets."
            )
        elif ctx.worst_symbol and ctx.worst_symbol_total_pnl is not None and ctx.worst_symbol_total_pnl < 0:
            wr_str = f" ({ctx.worst_symbol_win_rate_pct}% win rate)" if ctx.worst_symbol_win_rate_pct is not None else ""
            diagnosis = (
                f"{ctx.worst_symbol} is your weakest symbol this period, "
                f"costing ${abs(ctx.worst_symbol_total_pnl):.2f} net{wr_str}. "
                f"Consider whether your edge applies to this instrument or whether "
                f"it is better skipped until you identify a clearer setup."
            )
        elif ctx.worst_session and ctx.worst_session_pf is not None and ctx.worst_session_pf < 1.0:
            pf_str = f"{ctx.worst_session_pf:.2f}"
            best_str = (
                f" {ctx.best_session} is your strongest session (PF {ctx.best_session_pf:.2f})."
                if ctx.best_session and ctx.best_session_pf is not None else ""
            )
            diagnosis = (
                f"{ctx.worst_session} session is unprofitable this period (profit factor {pf_str}).{best_str} "
                f"Review whether your setup criteria are genuinely valid during {ctx.worst_session} "
                f"or whether session conditions do not suit your strategy."
            )
        else:
            diagnosis = (
                "No dominant problem source is recorded for this period. "
                "Prioritize tagging trades with problem_source (analysis/execution/psychology/risk) "
                "to enable data-driven coaching diagnosis in future reviews."
            )

        # ── Improvement ────────────────────────────────────────────────────────
        if ctx.linked_but_deviated_count > 0:
            cost = ctx.deviated_total_pnl
            cost_str = f" (total cost: ${abs(cost):.2f})" if cost is not None and cost < 0 else ""
            improvement = (
                f"You wrote {ctx.linked_but_deviated_count} pre-trade plan(s) but then deviated "
                f"from them{cost_str}. "
                f"Before your next trade, re-read the plan and identify the specific rule you broke. "
                f"Add that to your pre-trade checklist."
            )
        elif rr_below_80 and ctx.avg_planned_rr is not None:
            setup_note = ""
            if (
                ctx.worst_rr_setup
                and ctx.worst_rr_setup_realization_pct is not None
                and ctx.worst_rr_setup_realization_pct < 60
            ):
                setup_note = (
                    f" Your biggest R:R leakage is on '{ctx.worst_rr_setup}' "
                    f"({ctx.worst_rr_setup_realization_pct:.0f}% realization) — start there."
                )
            trend_note = ""
            if ctx.rr_trend_signal == "improving":
                trend_note = " R:R realization is improving week-over-week — the work is paying off."
            elif ctx.rr_trend_signal == "worsening":
                trend_note = " R:R realization is declining week-over-week — this needs immediate attention."
            improvement = (
                f"Stop adjusting take-profits during the trade. "
                f"Your planned R:R is {ctx.avg_planned_rr:.2f}R on average; you are only realizing "
                f"{ctx.avg_actual_r:+.2f}R ({ctx.realization_pct:.0f}%).{setup_note}{trend_note} "
                f"For the next 5 trades, set your TP at the planned level and do not move it until "
                f"price either hits it or the position is stopped out."
            )
        elif rr_above_100 and ctx.avg_planned_rr is not None:
            trend_note = ""
            if ctx.rr_trend_signal == "improving":
                trend_note = " R:R realization is trending upward week-over-week — keep it up."
            elif ctx.rr_trend_signal == "worsening":
                trend_note = " Note: R:R realization has been declining recently — watch for complacency."
            improvement = (
                f"Strong R:R execution — you are delivering {ctx.realization_pct:.0f}% of planned "
                f"R:R ({ctx.avg_actual_r:+.2f}R vs {ctx.avg_planned_rr:.2f}R planned).{trend_note} "
                f"Keep recording planned_rr on every trade plan and continue holding to targets."
            )
        elif ctx.top_mistakes:
            worst = ctx.top_mistakes[0]
            tag_label = worst["tag"].replace("_", " ")
            improvement = (
                f"Eliminate '{tag_label}' from your trading this week. "
                f"It cost ${abs(worst['total_cost']):.2f} over {worst['count']} occurrence(s). "
                f"Before entering any trade, explicitly confirm you are not making this mistake."
            )
        elif planned_worse:
            diff = (ctx.unplanned_avg_pnl or 0) - (ctx.planned_avg_pnl or 0)
            improvement = (
                f"Unplanned trades are outperforming planned ones by ${diff:.2f}/trade. "
                f"Before your next planned trade, re-read the plan at entry time and confirm you are "
                f"executing at the specified level — over-analysis or hesitation may be causing slippage from the plan."
            )
        elif ctx.deviated_count > 0 and ctx.followed_plan_rate is not None and ctx.followed_plan_rate < 80 and not followed_worse:
            improvement = (
                f"Bring plan adherence above 80% (currently {ctx.followed_plan_rate}%). "
                f"After each trade, immediately tag whether it followed the plan or deviated."
            )
        elif ctx.planned_trade_count == 0 and ctx.total_trades >= 5:
            improvement = (
                "No trades have a linked pre-trade plan this period. "
                "Write a trade plan (in the Trade Plans section) before your next trade — "
                "planning ahead is one of the highest-leverage improvements for discretionary traders."
            )
        else:
            improvement = (
                "Record problem_source and mistake_tags on every trade this week. "
                "Without this data, rule-based and AI coaching cannot provide specific guidance."
            )

        return {
            "summary": summary,
            "top_mistakes": fallback_mistakes,
            "diagnosis": diagnosis,
            "improvement": improvement,
        }

    # ── Prompt builder ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(ctx: CoachingContext) -> str:
        if ctx.from_date and ctx.to_date:
            period = f"{ctx.from_date} – {ctx.to_date}"
        elif ctx.from_date:
            period = f"from {ctx.from_date}"
        elif ctx.to_date:
            period = f"up to {ctx.to_date}"
        else:
            period = "all available trades"

        pf_str = f"{ctx.profit_factor:.2f}" if ctx.profit_factor is not None else "N/A"

        exec_parts = []
        if ctx.followed_plan_rate is not None:
            exec_parts.append(f"Followed plan: {ctx.followed_plan_rate}%")
        if ctx.a_plus_rate is not None:
            exec_parts.append(f"A+ setups taken: {ctx.a_plus_rate}%")
        exec_str = " | ".join(exec_parts) if exec_parts else "not recorded"

        if ctx.source_counts:
            total_src = sum(ctx.source_counts.values())
            src_parts = [
                f"{k}: {round(v / total_src * 100)}%"
                for k, v in sorted(ctx.source_counts.items(), key=lambda x: -x[1])
            ]
            source_block = ", ".join(src_parts)
        else:
            source_block = "not recorded"

        mistake_lines = []
        for m in ctx.top_mistakes:
            alr = m.get("after_loss_rate")
            after_loss = (
                f", after-loss rate: {round((alr or 0) * 100):.0f}%"
                if alr is not None else ""
            )
            mistake_lines.append(
                f"  - {m['tag'].replace('_', ' ')}: {m['count']}x, "
                f"${m['total_cost']} total cost{after_loss}"
            )
        mistakes_block = "\n".join(mistake_lines) if mistake_lines else "  - None recorded"

        # ── Plan-vs-execution block (only rendered when data is available) ────
        total_planned = ctx.planned_trade_count + ctx.unplanned_trade_count
        plan_lines = []
        if total_planned > 0:
            plan_pct = round(ctx.planned_trade_count / total_planned * 100)
            plan_lines.append(
                f"  Pre-planned trades: {ctx.planned_trade_count}/{total_planned} ({plan_pct}%)"
            )
        if ctx.planned_win_rate is not None and ctx.unplanned_win_rate is not None:
            p_pnl = f"${ctx.planned_avg_pnl:+.2f}" if ctx.planned_avg_pnl is not None else "n/a"
            u_pnl = f"${ctx.unplanned_avg_pnl:+.2f}" if ctx.unplanned_avg_pnl is not None else "n/a"
            plan_lines.append(
                f"  Planned: win rate {ctx.planned_win_rate}%, avg PnL {p_pnl} | "
                f"Unplanned: win rate {ctx.unplanned_win_rate}%, avg PnL {u_pnl}"
            )
        if ctx.followed_win_rate is not None and ctx.deviated_win_rate is not None:
            f_pnl = f"${ctx.followed_avg_pnl:+.2f}" if ctx.followed_avg_pnl is not None else "n/a"
            d_pnl = f"${ctx.deviated_avg_pnl:+.2f}" if ctx.deviated_avg_pnl is not None else "n/a"
            plan_lines.append(
                f"  Followed plan: win rate {ctx.followed_win_rate}%, avg PnL {f_pnl} | "
                f"Deviated: win rate {ctx.deviated_win_rate}%, avg PnL {d_pnl}"
            )
        if ctx.linked_but_deviated_count > 0:
            plan_lines.append(
                f"  Linked plan but deviated: {ctx.linked_but_deviated_count} trade(s)"
            )
        plan_block = "\n".join(plan_lines) if plan_lines else "  not recorded"

        # ── Planned R:R vs realized R block ──────────────────────────────────
        rr_lines = []
        if ctx.rr_sample_count >= 3:
            rr_lines.append(
                f"  Qualifying trades (linked plan with planned_rr + actual_r): {ctx.rr_sample_count}"
            )
            if ctx.avg_planned_rr is not None and ctx.avg_actual_r is not None:
                shortfall = round(ctx.avg_actual_r - ctx.avg_planned_rr, 2)
                rr_lines.append(
                    f"  Avg planned R:R: {ctx.avg_planned_rr:.2f}R | "
                    f"Avg realized R: {ctx.avg_actual_r:+.2f}R | "
                    f"Shortfall: {shortfall:+.2f}R"
                )
            if ctx.realization_pct is not None:
                rr_lines.append(f"  R:R realization: {ctx.realization_pct:.0f}% of planned target")
            if ctx.pct_met_rr_target is not None:
                rr_lines.append(f"  Trades that met or exceeded planned R:R: {ctx.pct_met_rr_target:.0f}%")
        rr_block = "\n".join(rr_lines) if rr_lines else "  not enough data (need >= 3 linked trades with planned_rr set)"

        # Per-setup R:R block
        setup_rr_lines = []
        if ctx.worst_rr_setup and ctx.worst_rr_setup_realization_pct is not None:
            setup_rr_lines.append(
                f"  Weakest R:R execution: {ctx.worst_rr_setup} "
                f"— {ctx.worst_rr_setup_realization_pct:.0f}% realization"
            )
        if ctx.best_rr_setup and ctx.best_rr_setup_realization_pct is not None:
            setup_rr_lines.append(
                f"  Strongest R:R execution: {ctx.best_rr_setup} "
                f"— {ctx.best_rr_setup_realization_pct:.0f}% realization"
            )
        setup_rr_block = "\n".join(setup_rr_lines) if setup_rr_lines else "  not enough per-setup data"

        # ── Symbol / session edge block ───────────────────────────────────────
        sym_lines = []
        if ctx.best_symbol:
            sym_lines.append(f"  Best symbol by total PnL: {ctx.best_symbol}")
        if ctx.worst_symbol:
            wr_str = f", win rate {ctx.worst_symbol_win_rate_pct}%" if ctx.worst_symbol_win_rate_pct is not None else ""
            pnl_str = f"${ctx.worst_symbol_total_pnl:+.2f}" if ctx.worst_symbol_total_pnl is not None else "?"
            sym_lines.append(
                f"  Weakest symbol: {ctx.worst_symbol} — total PnL {pnl_str}{wr_str}"
            )
        symbol_block = "\n".join(sym_lines) if sym_lines else "  not enough per-symbol data (need >= 3 trades per symbol)"

        sess_lines = []
        if ctx.best_session:
            pf_str = f"{ctx.best_session_pf:.2f}" if ctx.best_session_pf is not None else "?"
            sess_lines.append(f"  Best session: {ctx.best_session} — profit factor {pf_str}")
        if ctx.worst_session:
            pf_str = f"{ctx.worst_session_pf:.2f}" if ctx.worst_session_pf is not None else "?"
            sess_lines.append(f"  Worst session: {ctx.worst_session} — profit factor {pf_str}")
        session_block = "\n".join(sess_lines) if sess_lines else "  not enough per-session data (need >= 3 trades per session)"

        # ── R:R trend block ───────────────────────────────────────────────────
        if ctx.rr_trend_signal:
            rr_trend_block = f"  Trend direction (first-half vs second-half weekly buckets): {ctx.rr_trend_signal.upper()}"
        else:
            rr_trend_block = "  not enough weekly buckets to determine trend (need >= 4)"

        # ── Exit decomposition block ──────────────────────────────────────────
        exit_lines = []
        if ctx.exit_stop_hit_pct is not None:
            exit_lines.append(f"  Stop hit: {ctx.exit_stop_hit_pct:.0f}% of classified exits")
        if ctx.exit_manual_cut_pct is not None:
            exit_lines.append(f"  Manual cut (before stop): {ctx.exit_manual_cut_pct:.0f}% of losses")
        if ctx.exit_target_hit_pct is not None:
            exit_lines.append(f"  Target hit (≥90% of TP): {ctx.exit_target_hit_pct:.0f}% of TP-eligible wins")
        if ctx.exit_unclear_pct is not None:
            exit_lines.append(f"  Unclear exits: {ctx.exit_unclear_pct:.0f}% (no TP info or grey zone)")
        for sig in ctx.exit_decomp_signals:
            exit_lines.append(f"  Signal: {sig}")
        exit_block = "\n".join(exit_lines) if exit_lines else "  not enough data (need actual_r_multiple set on trades)"

        return f"""You are a professional trading coach reviewing a trader's performance.
Analyze the data below and provide a structured JSON coaching review.

PERIOD: {period}

PERFORMANCE:
  Trades: {ctx.total_trades} | Win rate: {ctx.win_rate_pct}% | Net PnL: ${ctx.total_net_pnl}
  Profit factor: {pf_str} | Expectancy: ${ctx.expectancy}/trade | Max drawdown: ${ctx.max_drawdown}

EXECUTION QUALITY:
  {exec_str}
  Problem source breakdown: {source_block}

PLAN ADHERENCE:
{plan_block}

PLANNED R:R vs REALIZED R:
{rr_block}

PER-SETUP R:R EXECUTION:
{setup_rr_block}

R:R REALIZATION TREND (weekly):
{rr_trend_block}

EXIT OUTCOME DECOMPOSITION:
{exit_block}

SYMBOL EDGE:
{symbol_block}

SESSION EDGE:
{session_block}

TOP MISTAKES (by total cost):
{mistakes_block}

Respond with ONLY a JSON object — no markdown fences, no explanation outside the JSON:
{{
  "summary": "2-3 sentence overview of this period",
  "top_mistakes": [
    {{"tag": "mistake_name", "pattern": "specific observation about this pattern in the data"}},
    ...
  ],
  "diagnosis": "Which area needs most attention: analysis quality, execution discipline, psychological control, or risk management? Be specific about what the data shows.",
  "improvement": "One concrete, actionable focus for the next trading session. Make it specific and measurable."
}}"""

    # ── Response parser ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """
        Parse JSON from AI response. Three attempts:
        1. Direct json.loads on stripped text.
        2. Extract largest {...} block via regex.
        3. Raise ValueError — caller will trigger fallback.
        """
        stripped = raw.strip()

        # Attempt 1: direct parse
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # Attempt 2: extract outermost JSON object
        match = re.search(r"\{[\s\S]*\}", stripped)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"AI response could not be parsed as JSON. First 300 chars: {raw[:300]}"
        )
