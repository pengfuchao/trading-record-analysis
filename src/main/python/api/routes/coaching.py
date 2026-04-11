from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import (
    get_account_repo, get_db, get_trade_repo, require_account,
)
from src.main.python.api.schemas.coaching import MistakeInsight, WeeklyReviewResponse
from src.main.python.services.ai_coach import AICoachService

router = APIRouter(prefix="/accounts", tags=["coaching"])

_coach = AICoachService()


@router.post("/{account_id}/coaching/weekly-review", response_model=WeeklyReviewResponse)
def generate_weekly_review(
    account_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Generate an AI coaching review for the specified date range.

    Analyzes performance metrics, top recurring mistakes, execution quality
    (followed_plan, is_a_plus_setup, problem_source), and returns a structured
    review with: summary, top_mistakes, diagnosis, and one improvement priority.

    Date range filters on exit_datetime (closed trades only).
    If no dates are supplied, all trades in the account are analyzed.

    Requires ANTHROPIC_API_KEY environment variable.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)
    trades = trade_repo.get_by_account_filtered(
        account_id,
        from_date=from_date,
        to_date=to_date,
    )

    if not trades:
        raise HTTPException(
            status_code=422,
            detail="No closed trades found for the specified date range. Import trades first.",
        )

    try:
        result = _coach.generate_weekly_review(
            trades=trades,
            account=account,
            from_date=from_date.date() if from_date else None,
            to_date=to_date.date() if to_date else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return WeeklyReviewResponse(
        account_id=account_id,
        from_date=from_date.date().isoformat() if from_date else None,
        to_date=to_date.date().isoformat() if to_date else None,
        summary=result.get("summary", ""),
        top_mistakes=[
            MistakeInsight(tag=m.get("tag", ""), pattern=m.get("pattern", ""))
            for m in result.get("top_mistakes", [])
        ],
        diagnosis=result.get("diagnosis", ""),
        improvement=result.get("improvement", ""),
    )
