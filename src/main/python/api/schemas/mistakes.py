from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from src.main.python.models.mistake_report import MistakeReport, MistakeStats


class MistakeStatsResponse(BaseModel):
    mistake_tag: str
    occurrence_count: int
    occurrence_pct: float
    total_cost: float
    avg_cost_per_trade: float
    win_rate: Optional[float]
    loss_rate: Optional[float]
    avg_net_pnl: Optional[float]
    by_session: Dict[str, int]
    by_symbol: Dict[str, int]
    after_loss_rate: Optional[float]


class MistakeReportResponse(BaseModel):
    account_id: str
    generated_at: datetime
    total_trades_analyzed: int
    trades_with_any_mistake: int
    mistake_rate: Optional[float]
    by_mistake: Dict[str, MistakeStatsResponse]
    ranked_by_frequency: List[str]
    ranked_by_cost: List[str]


def _stats_to_response(s: MistakeStats) -> MistakeStatsResponse:
    return MistakeStatsResponse(
        mistake_tag=s.mistake_tag,
        occurrence_count=s.occurrence_count,
        occurrence_pct=s.occurrence_pct,
        total_cost=s.total_cost,
        avg_cost_per_trade=s.avg_cost_per_trade,
        win_rate=s.win_rate,
        loss_rate=s.loss_rate,
        avg_net_pnl=s.avg_net_pnl,
        by_session=s.by_session,
        by_symbol=s.by_symbol,
        after_loss_rate=s.after_loss_rate,
    )


def mistake_report_to_response(r: MistakeReport) -> MistakeReportResponse:
    return MistakeReportResponse(
        account_id=r.account_id,
        generated_at=r.generated_at,
        total_trades_analyzed=r.total_trades_analyzed,
        trades_with_any_mistake=r.trades_with_any_mistake,
        mistake_rate=r.mistake_rate,
        by_mistake={tag: _stats_to_response(s) for tag, s in r.by_mistake.items()},
        ranked_by_frequency=r.ranked_by_frequency,
        ranked_by_cost=r.ranked_by_cost,
    )
