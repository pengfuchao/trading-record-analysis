from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.core.mistake_analyzer import MistakeAnalyzer
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

        if dominant_source and dominant_source in source_map:
            area = source_map[dominant_source]
            pct = round(ctx.source_counts[dominant_source] / sum(ctx.source_counts.values()) * 100)
            diagnosis = (
                f"Your recorded problem_source data points to {area} as the primary issue "
                f"({pct}% of reviewed trades). Focus here before addressing other areas."
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
        else:
            diagnosis = (
                "No dominant problem source is recorded for this period. "
                "Prioritize tagging trades with problem_source (analysis/execution/psychology/risk) "
                "to enable data-driven coaching diagnosis in future reviews."
            )

        # ── Improvement ────────────────────────────────────────────────────────
        if ctx.top_mistakes:
            worst = ctx.top_mistakes[0]
            tag_label = worst["tag"].replace("_", " ")
            improvement = (
                f"Eliminate '{tag_label}' from your trading this week. "
                f"It cost ${abs(worst['total_cost']):.2f} over {worst['count']} occurrence(s). "
                f"Before entering any trade, explicitly confirm you are not making this mistake."
            )
        elif ctx.followed_plan_rate is not None and ctx.followed_plan_rate < 80:
            improvement = (
                f"Bring plan adherence above 80% (currently {ctx.followed_plan_rate}%). "
                f"After each trade, immediately tag whether it was planned or unplanned."
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

        return f"""You are a professional trading coach reviewing a trader's performance.
Analyze the data below and provide a structured JSON coaching review.

PERIOD: {period}

PERFORMANCE:
  Trades: {ctx.total_trades} | Win rate: {ctx.win_rate_pct}% | Net PnL: ${ctx.total_net_pnl}
  Profit factor: {pf_str} | Expectancy: ${ctx.expectancy}/trade | Max drawdown: ${ctx.max_drawdown}

EXECUTION QUALITY:
  {exec_str}
  Problem source breakdown: {source_block}

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
