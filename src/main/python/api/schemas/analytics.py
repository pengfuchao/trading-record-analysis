from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from src.main.python.core.performance_summary import AccountReport, PerformanceSummary


class PerformanceSummaryResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: Optional[float]
    win_rate_ex_be: Optional[float]
    loss_rate: Optional[float]
    breakeven_rate: Optional[float]
    total_net_profit: float
    total_gross_profit: float
    total_gross_loss: float
    total_return_pct: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]
    largest_single_win: Optional[float]
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
    max_drawdown_pct_of_starting_balance: Optional[float]
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
    starting_balance: Optional[float]
    current_balance: Optional[float]
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
        win_rate_ex_be=s.win_rate_ex_be,
        loss_rate=s.loss_rate,
        breakeven_rate=s.breakeven_rate,
        total_net_profit=s.total_net_profit,
        total_gross_profit=s.total_gross_profit,
        total_gross_loss=s.total_gross_loss,
        total_return_pct=s.total_return_pct,
        avg_win=s.avg_win,
        avg_loss=s.avg_loss,
        largest_single_win=s.largest_single_win,
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
        max_drawdown_pct_of_starting_balance=s.max_drawdown_pct_of_starting_balance,
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
        starting_balance=r.starting_balance,
        current_balance=r.current_balance,
        overall=summary_to_response(r.overall),
        equity_curve=r.equity_curve,
        drawdown_curve=r.drawdown_curve,
        trade_dates=r.trade_dates,
        **segmentations,
    )


# ── Flat analytics summary (used by dashboard) ────────────────────────────────

class AnalyticsSummaryResponse(BaseModel):
    """
    Flat, dashboard-friendly summary of account performance.
    A subset of PerformanceSummaryResponse — no segmentations or curves.
    All PnL values are in account currency. All rates are 0.0–1.0.
    Negative drawdown values indicate losses below the running peak.
    """
    account_id: str
    generated_at: datetime

    # Account state
    starting_balance: Optional[float]
    current_balance: Optional[float]        # starting_balance + total_net_profit

    # Counts
    total_trades: int
    winning_trades: int
    losing_trades: int

    # Rates (0.0–1.0)
    win_rate: Optional[float]
    win_rate_ex_be: Optional[float]         # win rate excluding breakevens
    loss_rate: Optional[float]

    # PnL
    total_net_pnl: Optional[float]
    total_gross_pnl: Optional[float]
    total_return_pct: Optional[float]       # (total_net_pnl / starting_balance) * 100

    # Averages
    average_win: Optional[float]
    average_loss: Optional[float]           # negative value
    largest_win: Optional[float]
    largest_loss: Optional[float]           # negative value

    # Quality
    profit_factor: Optional[float]
    expectancy: Optional[float]             # avg $ per trade
    payoff_ratio: Optional[float]
    average_r_multiple: Optional[float]     # indicative; unreliable for indices

    # Drawdown / period loss
    max_drawdown: Optional[float]                       # peak-to-trough absolute $ (≤ 0)
    max_drawdown_pct: Optional[float]                   # peak-to-trough % of peak equity (≤ 0)
    max_drawdown_pct_of_starting_balance: Optional[float]  # peak-to-trough % of starting balance (≤ 0); FTMO-style
    # NOTE: daily/weekly values below are *worst-period closed-trade net PnL sums*,
    # NOT intraperiod drawdown from the period's high-water mark.
    # Negative = net losing period. Use abs() to compare against FTMO daily loss limit.
    daily_drawdown: Optional[float]                     # worst calendar-day net PnL (closed trades only)
    weekly_drawdown: Optional[float]                    # worst ISO-week net PnL (closed trades only)

    # Risk-adjusted
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]

    # Streaks
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Equity / drawdown curves (aligned by trade index)
    equity_curve: List[float]
    drawdown_curve: List[float]
    trade_dates: List[datetime]


def report_to_summary(r: AccountReport) -> AnalyticsSummaryResponse:
    o = r.overall
    return AnalyticsSummaryResponse(
        account_id=r.account_id,
        generated_at=r.generated_at,
        starting_balance=r.starting_balance,
        current_balance=r.current_balance,
        total_trades=o.total_trades,
        winning_trades=o.winning_trades,
        losing_trades=o.losing_trades,
        win_rate=o.win_rate,
        win_rate_ex_be=o.win_rate_ex_be,
        loss_rate=o.loss_rate,
        total_net_pnl=o.total_net_profit if o.total_trades else None,
        total_gross_pnl=o.total_gross_profit + o.total_gross_loss if o.total_trades else None,
        total_return_pct=o.total_return_pct,
        average_win=o.avg_win,
        average_loss=o.avg_loss,
        largest_win=o.largest_single_win,
        largest_loss=o.largest_single_loss,
        profit_factor=o.profit_factor,
        expectancy=o.expectancy,
        payoff_ratio=o.payoff_ratio,
        average_r_multiple=o.avg_r_multiple,
        max_drawdown=o.max_drawdown,
        max_drawdown_pct=o.max_drawdown_pct,
        max_drawdown_pct_of_starting_balance=o.max_drawdown_pct_of_starting_balance,
        daily_drawdown=o.daily_drawdown,
        weekly_drawdown=o.weekly_drawdown,
        sharpe_ratio=o.sharpe_ratio,
        sortino_ratio=o.sortino_ratio,
        max_consecutive_wins=o.max_consecutive_wins,
        max_consecutive_losses=o.max_consecutive_losses,
        equity_curve=r.equity_curve,
        drawdown_curve=r.drawdown_curve,
        trade_dates=r.trade_dates,
    )


# ── FTMO status ────────────────────────────────────────────────────────────────

class FtmoStatusResponse(BaseModel):
    """
    Real-time FTMO / prop firm challenge status.
    Based on closed trades only (open trade equity not tracked).

    Limit definitions (FTMO Challenge Phase 1 defaults):
      daily_loss_limit_pct: 5% of initial balance  (configurable via query param)
      max_loss_limit_pct:  10% of initial balance  (configurable via query param)

    Status values:
      SAFE     — current drawdown < 75% of limits
      AT_RISK  — current drawdown >= 75% of limits
      BREACHED — current drawdown >= 100% of limits (challenge failed)
      UNKNOWN  — starting_balance not set on account
    """
    account_id: str
    generated_at: datetime

    # Account state
    starting_balance: Optional[float]
    estimated_current_balance: Optional[float]      # starting_balance + total_net_pnl
    total_net_pnl: Optional[float]
    total_return_pct: Optional[float]

    # Daily loss (closed trades today)
    today_date: date
    today_pnl: float                                # sum of today's closed trade PnLs
    daily_loss_limit_pct: float                     # configured limit (e.g. 5.0)
    daily_loss_limit_abs: Optional[float]           # limit in $ (None if no starting_balance)
    daily_loss_used_pct: Optional[float]            # |today_pnl| / starting_balance * 100
    daily_loss_remaining: Optional[float]           # $ remaining before breach

    # Max (overall) drawdown
    max_loss_limit_pct: float                       # configured limit (e.g. 10.0)
    max_loss_limit_abs: Optional[float]             # limit in $
    current_max_drawdown: Optional[float]           # absolute $ drawdown from peak
    current_max_drawdown_pct: Optional[float]       # as % of starting_balance
    max_loss_remaining: Optional[float]             # $ remaining before breach

    # Account status
    daily_status: str                               # SAFE / AT_RISK / BREACHED / UNKNOWN
    overall_status: str                             # SAFE / AT_RISK / BREACHED / UNKNOWN
    account_status: str                             # worst of daily/overall


# ── Import history ─────────────────────────────────────────────────────────────

class ImportHistoryEntry(BaseModel):
    """One import batch summary."""
    import_run_id: str
    trade_count: int
    earliest_trade_date: Optional[datetime]
    latest_trade_date: Optional[datetime]
    symbols: List[str]


class ImportHistoryResponse(BaseModel):
    account_id: str
    total_imports: int
    entries: List[ImportHistoryEntry]
