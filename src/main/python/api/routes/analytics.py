from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, get_account_repo, get_trade_repo, require_account
from src.main.python.api.schemas.analytics import (
    AccountReportResponse,
    AnalyticsSummaryResponse,
    FtmoCheckResponse,
    FtmoStatusResponse,
    PlanAdherenceResponse,
    RRTrendBucketResponse,
    RRTrendReportResponse,
    SegmentAnalyticsResponse,
    SegmentRowResponse,
    plan_adherence_to_response,
    report_to_response,
    report_to_summary,
)
from src.main.python.services.telegram_notifier import get_notifier
from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.services.account_repository import AccountRepository
from src.main.python.services.trade_plan_repository import TradePlanRepository
from src.main.python.services.trade_repository import TradeRepository

router = APIRouter(prefix="/accounts", tags=["analytics"])

_analytics = AccountAnalytics()


@router.get("/{account_id}/analytics", response_model=AnalyticsSummaryResponse)
def get_analytics(
    account_id: str,
    symbol: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    result: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Flat, dashboard-friendly summary used by the frontend."""
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)
    trades, _ = trade_repo.get_by_account_filtered(
        account_id,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        result=result,
        page_size=10_000,
    )
    report = _analytics.generate_report(trades, account)
    return report_to_summary(report)


@router.get("/{account_id}/ftmo-status", response_model=FtmoStatusResponse)
def get_ftmo_status(
    account_id: str,
    daily_loss_limit_pct: float = 5.0,
    max_loss_limit_pct: float = 10.0,
    broker_utc_offset: int = 2,
    db: Session = Depends(get_db),
):
    """FTMO / prop firm challenge status based on closed trades only.

    broker_utc_offset: UTC offset of the broker server (default 2 = EET winter).
    Must match the timezone offset used by your broker's MT4/MT5 server so that
    'today_pnl' is computed against the correct calendar day.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)
    trades = trade_repo.get_by_account(account_id)
    status = AccountAnalytics.compute_ftmo_status(
        trades, account,
        daily_loss_limit_pct=daily_loss_limit_pct,
        max_loss_limit_pct=max_loss_limit_pct,
        broker_utc_offset=broker_utc_offset,
    )
    return FtmoStatusResponse(**status)


@router.post("/{account_id}/ftmo-check", response_model=FtmoCheckResponse)
def check_ftmo_and_notify(
    account_id: str,
    daily_loss_limit_pct: float = 5.0,
    max_loss_limit_pct: float = 10.0,
    broker_utc_offset: int = 2,
    db: Session = Depends(get_db),
):
    """
    Recompute FTMO status and send a Telegram alert only if the status changed.

    Use this from a cron job or external scheduler — NOT from the frontend on
    every page load. Returns full status data plus notification_sent / prev_status.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)
    trades = trade_repo.get_by_account(account_id)
    status = AccountAnalytics.compute_ftmo_status(
        trades, account,
        daily_loss_limit_pct=daily_loss_limit_pct,
        max_loss_limit_pct=max_loss_limit_pct,
        broker_utc_offset=broker_utc_offset,
    )
    notification_sent, prev_status = get_notifier().check_and_notify_ftmo(
        account_id=account_id,
        account_name=account_id,
        status_data=status,
    )
    return FtmoCheckResponse(
        notification_sent=notification_sent,
        prev_status=prev_status,
        **status,
    )


@router.get("/{account_id}/plan-adherence", response_model=PlanAdherenceResponse)
def get_plan_adherence(
    account_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Plan-vs-execution analytics for the account.

    Returns two comparison dimensions:
      1. Planned (has linked TradePlan) vs Unplanned — measures formal planning habit
      2. Followed plan vs Deviated — measures execution discipline (self-reported)

    Also returns pre-computed coaching signal sentences.
    Accepts the same date filters as /analytics.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    trades, _ = trade_repo.get_by_account_filtered(
        account_id,
        from_date=from_date,
        to_date=to_date,
        page_size=10_000,
    )

    # Enrich trades with planned_rr from their linked plans so that
    # compute_rr_analysis() inside compute_plan_adherence() can compare
    # planned vs realized R without needing a DB join at the analytics layer.
    plan_repo = TradePlanRepository(db)
    linked_plan_ids = {t.trade_plan_id for t in trades if t.trade_plan_id is not None}
    if linked_plan_ids:
        plans_by_id = {
            p.plan_id: p
            for p in plan_repo.list_by_account(account_id)
            if p.plan_id in linked_plan_ids
        }
        for trade in trades:
            if trade.trade_plan_id and trade.trade_plan_id in plans_by_id:
                trade.planned_rr = plans_by_id[trade.trade_plan_id].planned_rr

    report = AccountAnalytics.compute_plan_adherence(trades)
    return plan_adherence_to_response(report)


@router.get("/{account_id}/rr-trend", response_model=RRTrendReportResponse)
def get_rr_trend(
    account_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Weekly R:R realization trend for the account.

    Buckets qualifying trades (linked plan + planned_rr > 0 + actual_r_multiple)
    by ISO week and returns realization_pct per bucket.  Sparse weeks are skipped.
    trend_signal is "improving" | "worsening" | "stable" | None (needs >= 4 buckets).
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    trades, _ = trade_repo.get_by_account_filtered(
        account_id,
        from_date=from_date,
        to_date=to_date,
        page_size=10_000,
    )

    plan_repo = TradePlanRepository(db)
    linked_plan_ids = {t.trade_plan_id for t in trades if t.trade_plan_id is not None}
    if linked_plan_ids:
        plans_by_id = {
            p.plan_id: p
            for p in plan_repo.list_by_account(account_id)
            if p.plan_id in linked_plan_ids
        }
        for trade in trades:
            if trade.trade_plan_id and trade.trade_plan_id in plans_by_id:
                trade.planned_rr = plans_by_id[trade.trade_plan_id].planned_rr

    report = AccountAnalytics.compute_rr_trend(trades)
    return RRTrendReportResponse(
        buckets=[
            RRTrendBucketResponse(
                bucket=b.bucket,
                bucket_start=b.bucket_start,
                n=b.n,
                avg_planned_rr=b.avg_planned_rr,
                avg_actual_r=b.avg_actual_r,
                avg_shortfall=b.avg_shortfall,
                realization_pct=b.realization_pct,
            )
            for b in report.buckets
        ],
        total_qualifying=report.total_qualifying,
        trend_signal=report.trend_signal,
    )


@router.get("/{account_id}/segment-analytics", response_model=SegmentAnalyticsResponse)
def get_segment_analytics(
    account_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Per-symbol and per-session performance breakdown.

    Rows are sorted by total_pnl descending.  low_sample=True when count < 3.
    Callouts (best/worst symbol/session) require n >= 3 per row and exclude
    the "Unknown" session bucket.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)
    trades, _ = trade_repo.get_by_account_filtered(
        account_id,
        from_date=from_date,
        to_date=to_date,
        page_size=10_000,
    )
    report = _analytics.generate_report(trades, account)

    MIN_SIGNAL_N = 3

    def _to_row(name: str, s) -> SegmentRowResponse:
        avg_pnl = round(s.total_net_profit / s.total_trades, 2) if s.total_trades else None
        return SegmentRowResponse(
            name=name,
            count=s.total_trades,
            win_rate=s.win_rate,
            avg_pnl=avg_pnl,
            total_pnl=round(s.total_net_profit, 2),
            profit_factor=s.profit_factor,
            avg_r=s.avg_r_multiple,
            low_sample=s.total_trades < MIN_SIGNAL_N,
        )

    by_symbol = sorted(
        [_to_row(name, s) for name, s in report.by_symbol.items()],
        key=lambda r: r.total_pnl, reverse=True,
    )
    by_session = sorted(
        [_to_row(name, s) for name, s in report.by_session.items()],
        key=lambda r: r.total_pnl, reverse=True,
    )

    qualified_symbols = [r for r in by_symbol if not r.low_sample]
    qualified_sessions = [r for r in by_session if not r.low_sample and r.name != "Unknown"]

    best_symbol = max(qualified_symbols, key=lambda r: r.total_pnl).name if qualified_symbols else None
    worst_symbol = min(qualified_symbols, key=lambda r: r.total_pnl).name if qualified_symbols else None
    best_session = (
        max(qualified_sessions, key=lambda r: r.profit_factor or 0.0).name
        if qualified_sessions else None
    )
    worst_session = (
        min(qualified_sessions, key=lambda r: r.profit_factor or 0.0).name
        if qualified_sessions else None
    )

    if best_symbol == worst_symbol:
        best_symbol = worst_symbol = None
    if best_session == worst_session:
        best_session = worst_session = None

    return SegmentAnalyticsResponse(
        by_symbol=by_symbol,
        by_session=by_session,
        best_symbol=best_symbol,
        worst_symbol=worst_symbol,
        best_session=best_session,
        worst_session=worst_session,
    )


@router.get("/{account_id}/report", response_model=AccountReportResponse)
def get_report(
    account_id: str,
    symbol: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    result: Optional[str] = None,
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)
    trades, _ = trade_repo.get_by_account_filtered(
        account_id,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        result=result,
        page_size=10_000,
    )
    report = _analytics.generate_report(trades, account)
    return report_to_response(report)
