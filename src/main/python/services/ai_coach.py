from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import List, Optional

from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.core.mistake_analyzer import MistakeAnalyzer
from src.main.python.models.account import Account
from src.main.python.models.trade import Trade
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


class AICoachService:
    """
    Module 7 — AI Coaching (v1).

    Builds a structured prompt from pre-computed analytics + mistake data
    and calls the Anthropic API. All heavy computation is done by the existing
    AccountAnalytics and MistakeAnalyzer classes — this service only assembles
    the prompt and parses the response.

    Requires ANTHROPIC_API_KEY environment variable.
    """

    MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 1024

    def generate_weekly_review(
        self,
        trades: List[Trade],
        account: Account,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict:
        """
        Generate a weekly coaching review for the given trade set.

        Returns a dict with keys:
          summary       — 2-3 sentence week overview
          top_mistakes  — list of {tag, pattern} dicts
          diagnosis     — execution / analysis / psychology / risk diagnosis
          improvement   — one concrete actionable focus for next session

        Raises:
          ValueError if ANTHROPIC_API_KEY is not set.
          ValueError if the AI response cannot be parsed as JSON.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Add it to your .env file to enable AI coaching."
            )

        # Compute report and mistakes from the filtered trade set
        report = AccountAnalytics.generate_report(trades, account)
        mistake_report = MistakeAnalyzer().generate_report(trades, account.account_id)

        # Extract execution quality signals from individual trades
        total = len(trades)
        followed_count = sum(1 for t in trades if t.followed_plan is True)
        a_plus_count = sum(1 for t in trades if t.is_a_plus_setup is True)
        problem_sources = [t.problem_source for t in trades if t.problem_source]
        source_counts: dict = {}
        for src in problem_sources:
            source_counts[src] = source_counts.get(src, 0) + 1

        followed_plan_rate = round(followed_count / total * 100, 1) if total else None
        a_plus_rate = round(a_plus_count / total * 100, 1) if total else None

        prompt = self._build_prompt(
            from_date=from_date,
            to_date=to_date,
            overall=report.overall,
            followed_plan_rate=followed_plan_rate,
            a_plus_rate=a_plus_rate,
            source_counts=source_counts,
            mistake_report=mistake_report,
        )

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        logger.info("AI coach raw response length=%d", len(raw))

        return self._parse_response(raw)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(
        from_date,
        to_date,
        overall,
        followed_plan_rate,
        a_plus_rate,
        source_counts: dict,
        mistake_report,
    ) -> str:
        # Period label
        if from_date and to_date:
            period = f"{from_date} – {to_date}"
        elif from_date:
            period = f"from {from_date}"
        elif to_date:
            period = f"up to {to_date}"
        else:
            period = "all available trades"

        # Performance block
        win_rate_pct = round((overall.win_rate or 0) * 100, 1)
        pf_str = f"{overall.profit_factor:.2f}" if overall.profit_factor is not None else "N/A"
        exp_str = f"${round(overall.expectancy or 0, 2)}/trade"
        dd_str = f"${round(overall.max_drawdown or 0, 2)}"

        # Execution quality block
        exec_parts = []
        if followed_plan_rate is not None:
            exec_parts.append(f"Followed plan: {followed_plan_rate}%")
        if a_plus_rate is not None:
            exec_parts.append(f"A+ setups taken: {a_plus_rate}%")
        exec_str = " | ".join(exec_parts) if exec_parts else "not recorded"

        if source_counts:
            total_src = sum(source_counts.values())
            src_parts = [
                f"{k}: {round(v / total_src * 100)}%"
                for k, v in sorted(source_counts.items(), key=lambda x: -x[1])
            ]
            source_block = ", ".join(src_parts)
        else:
            source_block = "not recorded"

        # Top 3 mistakes by cost
        mistake_lines = []
        for tag in mistake_report.ranked_by_cost[:3]:
            s = mistake_report.by_mistake[tag]
            after_loss = (
                f", after-loss rate: {round((s.after_loss_rate or 0) * 100):.0f}%"
                if s.after_loss_rate is not None
                else ""
            )
            mistake_lines.append(
                f"  - {tag.replace('_', ' ')}: {s.occurrence_count}x, "
                f"${round(s.total_cost, 2)} total cost{after_loss}"
            )
        mistakes_block = "\n".join(mistake_lines) if mistake_lines else "  - None recorded"

        return f"""You are a professional trading coach reviewing a trader's performance.
Analyze the data below and provide a structured JSON coaching review.

PERIOD: {period}

PERFORMANCE:
  Trades: {overall.total_trades} | Win rate: {win_rate_pct}% | Net PnL: ${round(overall.total_net_profit, 2)}
  Profit factor: {pf_str} | Expectancy: {exp_str} | Max drawdown: {dd_str}

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

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Parse JSON from AI response, handling optional markdown fences."""
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                return json.loads(match.group())
            raise ValueError(
                f"AI response could not be parsed as JSON. First 300 chars: {raw[:300]}"
            )
