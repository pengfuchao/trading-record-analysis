from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Set

from src.main.python.models.enums import TradeResult
from src.main.python.models.mistake_report import MistakeReport, MistakeStats
from src.main.python.models.trade import Trade
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Boolean Trade fields that represent mistakes when True.
# Maps attribute name → canonical tag string.
_BOOLEAN_FLAG_MAP: Dict[str, str] = {
    "early_entry":         "early_entry",
    "chasing":             "chasing",
    "fomo":                "fomo",
    "emotional_trade":     "emotional_trade",
    "revenge_trade":       "revenge_trade",
    "overtrading":         "overtrading",
    "hesitation":          "hesitation",
    "moved_stop":          "moved_stop",
    "premature_exit":      "premature_exit",
    "held_loser_too_long": "held_loser_too_long",
}


class MistakeAnalyzer:
    """
    Stateless service that analyzes mistake patterns across a list of trades.

    Mistake tags are sourced from two places and unified:
      1. Boolean flags on the Trade (e.g. fomo=True → "fomo")
      2. Free-text items in Trade.mistake_tags list

    followed_plan=False → adds "plan_violation" tag.
    is_a_plus_setup=False is NOT a mistake (absence of excellence ≠ mistake).
    """

    def generate_report(self, trades: List[Trade], account_id: str) -> MistakeReport:
        if not trades:
            return MistakeReport(account_id=account_id, total_trades_analyzed=0)

        # Sort by exit_datetime for after-loss sequencing; trades without exit go last.
        sorted_trades = sorted(
            trades,
            key=lambda t: t.exit_datetime or datetime.max,
        )
        total = len(sorted_trades)

        # Map each trade → its effective tags (deduplicated)
        trade_tags: List[List[str]] = [
            self._extract_tags(t) for t in sorted_trades
        ]

        # Group trades by tag
        tag_to_trades: Dict[str, List[Trade]] = {}
        for trade, tags in zip(sorted_trades, trade_tags):
            for tag in tags:
                tag_to_trades.setdefault(tag, []).append(trade)

        trades_with_mistake = sum(1 for tags in trade_tags if tags)
        mistake_rate = trades_with_mistake / total if total > 0 else None

        by_mistake: Dict[str, MistakeStats] = {}
        for tag, tagged in tag_to_trades.items():
            by_mistake[tag] = self._compute_stats(
                tag=tag,
                tagged_trades=tagged,
                sorted_trades=sorted_trades,
                total_trades=total,
            )

        ranked_by_frequency = sorted(
            by_mistake,
            key=lambda t: by_mistake[t].occurrence_count,
            reverse=True,
        )
        ranked_by_cost = sorted(
            by_mistake,
            key=lambda t: by_mistake[t].total_cost,
        )

        logger.info(
            "MistakeAnalyzer: account=%s trades=%d mistakes=%d unique_tags=%d",
            account_id, total, trades_with_mistake, len(by_mistake),
        )

        return MistakeReport(
            account_id=account_id,
            total_trades_analyzed=total,
            trades_with_any_mistake=trades_with_mistake,
            mistake_rate=mistake_rate,
            by_mistake=by_mistake,
            ranked_by_frequency=ranked_by_frequency,
            ranked_by_cost=ranked_by_cost,
        )

    @staticmethod
    def _extract_tags(trade: Trade) -> List[str]:
        """
        Return deduplicated list of all effective mistake tags for a trade.
        Sources: True boolean flags + trade.mistake_tags list.
        """
        tags: Set[str] = set()

        for attr, canonical in _BOOLEAN_FLAG_MAP.items():
            if getattr(trade, attr, None) is True:
                tags.add(canonical)

        if trade.followed_plan is False:
            tags.add("plan_violation")

        for tag in (trade.mistake_tags or []):
            if tag:
                tags.add(tag.strip())

        return sorted(tags)  # deterministic order

    @staticmethod
    def _compute_stats(
        tag: str,
        tagged_trades: List[Trade],
        sorted_trades: List[Trade],
        total_trades: int,
    ) -> MistakeStats:
        count = len(tagged_trades)
        pnls = [t.net_pnl or 0.0 for t in tagged_trades]
        total_cost = sum(pnls)
        avg_cost = total_cost / count if count else 0.0
        avg_net_pnl = sum(pnls) / count if count else None

        results = [t.result for t in tagged_trades if t.result is not None]
        win_rate: Optional[float] = None
        loss_rate: Optional[float] = None
        if results:
            wins = sum(1 for r in results if r == TradeResult.WIN)
            losses = sum(1 for r in results if r == TradeResult.LOSS)
            win_rate = wins / len(results)
            loss_rate = losses / len(results)

        by_session: Dict[str, int] = dict(
            Counter(t.session for t in tagged_trades if t.session)
        )
        by_symbol: Dict[str, int] = dict(
            Counter(t.symbol for t in tagged_trades if t.symbol)
        )

        after_loss_rate = MistakeAnalyzer._compute_after_loss_rate(
            tagged_trades=tagged_trades,
            sorted_trades=sorted_trades,
        )

        return MistakeStats(
            mistake_tag=tag,
            occurrence_count=count,
            occurrence_pct=count / total_trades if total_trades else 0.0,
            total_cost=total_cost,
            avg_cost_per_trade=avg_cost,
            win_rate=win_rate,
            loss_rate=loss_rate,
            avg_net_pnl=avg_net_pnl,
            by_session=by_session,
            by_symbol=by_symbol,
            after_loss_rate=after_loss_rate,
        )

    @staticmethod
    def _compute_after_loss_rate(
        tagged_trades: List[Trade],
        sorted_trades: List[Trade],
    ) -> Optional[float]:
        """
        Fraction of tagged-trade occurrences where the immediately preceding trade
        (by exit_datetime position in sorted_trades) was a LOSS.
        Returns None if there are no tagged trades.
        """
        if not tagged_trades:
            return None

        tagged_ids: Set[str] = {t.trade_id for t in tagged_trades}
        after_loss_count = 0

        for i, trade in enumerate(sorted_trades):
            if trade.trade_id not in tagged_ids:
                continue
            if i == 0:
                # First trade — no preceding trade
                continue
            prev = sorted_trades[i - 1]
            if prev.result == TradeResult.LOSS:
                after_loss_count += 1

        return after_loss_count / len(tagged_trades)
