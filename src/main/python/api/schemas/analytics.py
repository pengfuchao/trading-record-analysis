from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from src.main.python.core.performance_summary import (
    AccountReport, PerformanceSummary, PlanAdherenceGroup, PlanAdherenceReport,
    RRComparisonReport,
)


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

class FtmoCheckResponse(FtmoStatusResponse):
    """FtmoStatusResponse extended with notification metadata for /ftmo-check."""
    notification_sent: bool
    prev_status: Optional[str]


# ── Planned R:R vs Realized R ─────────────────────────────────────────────────

class RRComparisonResponse(BaseModel):
    """
    Planned R:R (from linked TradePlan) vs realized R multiple (from Trade).

    Only trades with a linked plan, a positive planned_rr, and a non-null
    actual_r_multiple are included.  All signs of actual_r are kept.

    realization_pct: (avg_actual_r / avg_planned_rr) * 100.
      < 100 → under-delivering on plan targets on average.
      >= 100 → meeting or exceeding planned targets on average.

    avg_r_shortfall: avg_actual_r - avg_planned_rr.
      Negative → falling short of planned R:R on average.
    """
    sample_count: int
    avg_planned_rr: Optional[float]
    avg_actual_r: Optional[float]
    avg_r_shortfall: Optional[float]
    realization_pct: Optional[float]
    met_target_count: int
    missed_target_count: int
    pct_met_target: Optional[float]
    coaching_signals: List[str]


# ── Plan adherence analytics ──────────────────────────────────────────────────

class PlanAdherenceGroupResponse(BaseModel):
    """Performance stats for one plan adherence slice."""
    count:         int
    win_rate:      Optional[float]
    avg_pnl:       Optional[float]
    avg_r:         Optional[float]
    total_pnl:     float
    profit_factor: Optional[float]


class PlanAdherenceResponse(BaseModel):
    """
    Plan-vs-execution analytics.

    Dimension 1 (trade_plan_id): planned / unplanned
    Dimension 2 (followed_plan): followed / deviated / not_tagged
    Intersection: linked_but_deviated_count
    """
    total_trades: int

    # Dimension 1 — formal plan linkage
    planned_count:   int
    unplanned_count: int
    planned_pct:     Optional[float]    # planned_count / total_trades * 100
    planned:         PlanAdherenceGroupResponse
    unplanned:       PlanAdherenceGroupResponse

    # Dimension 2 — self-reported adherence
    followed_count:   int
    deviated_count:   int
    not_tagged_count: int
    followed:         PlanAdherenceGroupResponse
    deviated:         PlanAdherenceGroupResponse

    # Intersection
    linked_but_deviated_count: int

    # Planned R:R vs realized R (None when <1 qualifying trade)
    rr_comparison: Optional[RRComparisonResponse]

    # Pre-computed coaching signal sentences
    coaching_signals: List[str]


def _adherence_group_to_response(g: PlanAdherenceGroup) -> PlanAdherenceGroupResponse:
    return PlanAdherenceGroupResponse(
        count=g.count,
        win_rate=g.win_rate,
        avg_pnl=g.avg_pnl,
        avg_r=g.avg_r,
        total_pnl=g.total_pnl,
        profit_factor=g.profit_factor,
    )


def _rr_comparison_to_response(rr: RRComparisonReport) -> RRComparisonResponse:
    return RRComparisonResponse(
        sample_count=rr.sample_count,
        avg_planned_rr=rr.avg_planned_rr,
        avg_actual_r=rr.avg_actual_r,
        avg_r_shortfall=rr.avg_r_shortfall,
        realization_pct=rr.realization_pct,
        met_target_count=rr.met_target_count,
        missed_target_count=rr.missed_target_count,
        pct_met_target=rr.pct_met_target,
        coaching_signals=rr.coaching_signals,
    )


def plan_adherence_to_response(r: PlanAdherenceReport) -> PlanAdherenceResponse:
    return PlanAdherenceResponse(
        total_trades=r.total_trades,
        planned_count=r.planned_count,
        unplanned_count=r.unplanned_count,
        planned_pct=r.planned_pct,
        planned=_adherence_group_to_response(r.planned),
        unplanned=_adherence_group_to_response(r.unplanned),
        followed_count=r.followed_count,
        deviated_count=r.deviated_count,
        not_tagged_count=r.not_tagged_count,
        followed=_adherence_group_to_response(r.followed),
        deviated=_adherence_group_to_response(r.deviated),
        linked_but_deviated_count=r.linked_but_deviated_count,
        rr_comparison=(
            _rr_comparison_to_response(r.rr_comparison) if r.rr_comparison is not None else None
        ),
        coaching_signals=r.coaching_signals,
    )


# ── Import history ─────────────────────────────────────────────────────────────

# ── R:R realization trend ─────────────────────────────────────────────────────

class RRTrendBucketResponse(BaseModel):
    """One ISO-week bucket in the R:R realization trend series."""
    bucket: str                      # "2026-W15"
    bucket_start: datetime
    n: int
    avg_planned_rr: float
    avg_actual_r: float
    avg_shortfall: float
    realization_pct: Optional[float]


class RRTrendReportResponse(BaseModel):
    buckets: List[RRTrendBucketResponse]
    total_qualifying: int
    trend_signal: Optional[str]      # "improving" | "worsening" | "stable" | None


# ── Per-symbol / per-session segment analytics ────────────────────────────────

class SegmentRowResponse(BaseModel):
    """
    Compact performance summary for one symbol or session slice.
    low_sample=True when count < 3 — treat callouts for these rows with caution.
    """
    name: str
    count: int
    win_rate: Optional[float]           # 0.0–1.0 including breakevens
    avg_pnl: Optional[float]            # total_pnl / count
    total_pnl: float
    profit_factor: Optional[float]
    avg_r: Optional[float]              # None if no actual_r_multiple data
    low_sample: bool                    # count < 3


class SegmentAnalyticsResponse(BaseModel):
    """
    Symbol and session segmentation — rows sorted by total_pnl descending.
    Callout fields are None when no row has n >= 3 (or when all are tied).
    """
    by_symbol: List[SegmentRowResponse]
    by_session: List[SegmentRowResponse]
    best_symbol: Optional[str]          # highest total_pnl, n >= 3
    worst_symbol: Optional[str]         # lowest total_pnl, n >= 3
    best_session: Optional[str]         # highest profit_factor, n >= 3, != "Unknown"
    worst_session: Optional[str]        # lowest profit_factor, n >= 3, != "Unknown"


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
