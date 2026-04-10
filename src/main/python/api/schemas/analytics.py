from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from src.main.python.core.performance_summary import AccountReport, PerformanceSummary


class PerformanceSummaryResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: Optional[float]
    loss_rate: Optional[float]
    breakeven_rate: Optional[float]
    total_net_profit: float
    total_gross_profit: float
    total_gross_loss: float
    total_return_pct: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]
    largest_single_loss: Optional[float]
    payoff_ratio: Optional[float]
    profit_factor: Optional[float]
    expectancy: Optional[float]
    avg_r_multiple: Optional[float]
    std_returns: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    recovery_factor: Optional[float]
    max_drawdown: Optional[float]
    max_drawdown_pct: Optional[float]
    relative_drawdown: Optional[float]
    daily_drawdown: Optional[float]
    weekly_drawdown: Optional[float]
    monthly_drawdown: Optional[float]
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_losing_streak: Optional[float]
    avg_holding_duration_seconds: Optional[float]  # timedelta serialized as seconds
    trades_per_day: Optional[float]
    trades_per_week: Optional[float]
    trades_per_month: Optional[float]
    exposure_by_symbol: Dict[str, float]
    exposure_by_direction: Dict[str, float]


class AccountReportResponse(BaseModel):
    account_id: str
    generated_at: datetime
    overall: PerformanceSummaryResponse
    equity_curve: List[float]
    drawdown_curve: List[float]
    trade_dates: List[datetime]
    by_symbol: Dict[str, PerformanceSummaryResponse]
    by_direction: Dict[str, PerformanceSummaryResponse]
    by_asset_class: Dict[str, PerformanceSummaryResponse]
    by_session: Dict[str, PerformanceSummaryResponse]
    by_setup_type: Dict[str, PerformanceSummaryResponse]
    by_strategy: Dict[str, PerformanceSummaryResponse]
    by_market_condition: Dict[str, PerformanceSummaryResponse]
    by_weekday: Dict[str, PerformanceSummaryResponse]
    by_hour: Dict[str, PerformanceSummaryResponse]
    by_month: Dict[str, PerformanceSummaryResponse]
    by_followed_plan: Dict[str, PerformanceSummaryResponse]
    by_result: Dict[str, PerformanceSummaryResponse]


def summary_to_response(s: PerformanceSummary) -> PerformanceSummaryResponse:
    return PerformanceSummaryResponse(
        total_trades=s.total_trades,
        winning_trades=s.winning_trades,
        losing_trades=s.losing_trades,
        breakeven_trades=s.breakeven_trades,
        win_rate=s.win_rate,
        loss_rate=s.loss_rate,
        breakeven_rate=s.breakeven_rate,
        total_net_profit=s.total_net_profit,
        total_gross_profit=s.total_gross_profit,
        total_gross_loss=s.total_gross_loss,
        total_return_pct=s.total_return_pct,
        avg_win=s.avg_win,
        avg_loss=s.avg_loss,
        largest_single_loss=s.largest_single_loss,
        payoff_ratio=s.payoff_ratio,
        profit_factor=s.profit_factor,
        expectancy=s.expectancy,
        avg_r_multiple=s.avg_r_multiple,
        std_returns=s.std_returns,
        sharpe_ratio=s.sharpe_ratio,
        sortino_ratio=s.sortino_ratio,
        calmar_ratio=s.calmar_ratio,
        recovery_factor=s.recovery_factor,
        max_drawdown=s.max_drawdown,
        max_drawdown_pct=s.max_drawdown_pct,
        relative_drawdown=s.relative_drawdown,
        daily_drawdown=s.daily_drawdown,
        weekly_drawdown=s.weekly_drawdown,
        monthly_drawdown=s.monthly_drawdown,
        max_consecutive_wins=s.max_consecutive_wins,
        max_consecutive_losses=s.max_consecutive_losses,
        avg_losing_streak=s.avg_losing_streak,
        avg_holding_duration_seconds=(
            s.avg_holding_duration.total_seconds()
            if s.avg_holding_duration is not None else None
        ),
        trades_per_day=s.trades_per_day,
        trades_per_week=s.trades_per_week,
        trades_per_month=s.trades_per_month,
        exposure_by_symbol=s.exposure_by_symbol,
        exposure_by_direction=s.exposure_by_direction,
    )


_SEGMENT_FIELDS = [
    "by_symbol", "by_direction", "by_asset_class", "by_session",
    "by_setup_type", "by_strategy", "by_market_condition", "by_weekday",
    "by_hour", "by_month", "by_followed_plan", "by_result",
]


def report_to_response(r: AccountReport) -> AccountReportResponse:
    segmentations = {
        field: {k: summary_to_response(v) for k, v in getattr(r, field).items()}
        for field in _SEGMENT_FIELDS
    }
    return AccountReportResponse(
        account_id=r.account_id,
        generated_at=r.generated_at,
        overall=summary_to_response(r.overall),
        equity_curve=r.equity_curve,
        drawdown_curve=r.drawdown_curve,
        trade_dates=r.trade_dates,
        **segmentations,
    )
