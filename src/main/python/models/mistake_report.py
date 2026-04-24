from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class MistakeStats:
    """Per-mistake-tag aggregated statistics across a set of trades."""
    mistake_tag: str
    occurrence_count: int
    occurrence_pct: float               # occurrence_count / total_trades_analyzed
    total_cost: float                   # sum(net_pnl) for tagged trades (negative = costly)
    avg_cost_per_trade: float           # total_cost / occurrence_count
    win_rate: Optional[float]           # fraction of tagged trades that were wins
    loss_rate: Optional[float]          # fraction of tagged trades that were losses
    avg_net_pnl: Optional[float]        # avg net_pnl across tagged trades
    by_session: Dict[str, int]          # session label → occurrence count
    by_symbol: Dict[str, int]           # symbol → occurrence count
    after_loss_rate: Optional[float]    # fraction of occurrences immediately following a losing trade


@dataclass
class MistakeReport:
    """Account-level mistake analysis report."""
    account_id: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_trades_analyzed: int = 0
    trades_with_any_mistake: int = 0
    mistake_rate: Optional[float] = None    # trades_with_any_mistake / total_trades_analyzed
    by_mistake: Dict[str, MistakeStats] = field(default_factory=dict)
    ranked_by_frequency: List[str] = field(default_factory=list)  # tags desc by occurrence_count
    ranked_by_cost: List[str] = field(default_factory=list)       # tags asc by total_cost (worst first)
