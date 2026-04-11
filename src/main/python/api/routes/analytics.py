from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, get_account_repo, get_trade_repo, require_account
from src.main.python.api.schemas.analytics import (
    AccountReportResponse,
    AnalyticsSummaryResponse,
    FtmoStatusResponse,
    report_to_response,
    report_to_summary,
)
from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.services.account_repository import AccountRepository
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
    trades = trade_repo.get_by_account_filtered(
        account_id,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        result=result,
    )
    report = _analytics.generate_report(trades, account)
    return report_to_summary(report)


@router.get("/{account_id}/ftmo-status", response_model=FtmoStatusResponse)
def get_ftmo_status(
    account_id: str,
    daily_loss_limit_pct: float = 5.0,
    max_loss_limit_pct: float = 10.0,
    db: Session = Depends(get_db),
):
    """FTMO / prop firm challenge status based on closed trades only."""
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)
    trades = trade_repo.get_by_account(account_id)
    status = AccountAnalytics.compute_ftmo_status(
        trades, account,
        daily_loss_limit_pct=daily_loss_limit_pct,
        max_loss_limit_pct=max_loss_limit_pct,
    )
    return FtmoStatusResponse(**status)


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
    trades = trade_repo.get_by_account_filtered(
        account_id,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        result=result,
    )
    report = _analytics.generate_report(trades, account)
    return report_to_response(report)
