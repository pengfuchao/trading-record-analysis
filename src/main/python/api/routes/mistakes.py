from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import (
    get_account_repo, get_db, get_trade_repo, require_account,
)
from src.main.python.api.schemas.mistakes import (
    MistakeReportResponse, mistake_report_to_response,
)
from src.main.python.core.mistake_analyzer import MistakeAnalyzer

router = APIRouter(prefix="/accounts", tags=["mistakes"])

_analyzer = MistakeAnalyzer()


@router.get("/{account_id}/mistakes", response_model=MistakeReportResponse)
def get_mistake_report(
    account_id: str,
    symbol: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    result: Optional[str] = None,
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    trades, _ = trade_repo.get_by_account_filtered(
        account_id,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        result=result,
        page_size=10_000,
    )
    report = _analyzer.generate_report(trades, account_id)
    return mistake_report_to_response(report)
