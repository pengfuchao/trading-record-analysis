from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import (
    get_account_repo, get_db, get_trade_repo, require_account,
)
from src.main.python.services.daily_plan_repository import DailyPlanRepository
from src.main.python.services.trade_plan_repository import TradePlanRepository
from src.main.python.api.schemas.coaching import (
    CoachingReviewDetailResponse,
    CoachingReviewListItem,
    CoachingReviewListResponse,
    MistakeInsight,
    WeeklyReviewResponse,
)
from src.main.python.models.db_models import CoachingReviewModel
from src.main.python.services.ai_coach import AICoachService
from src.main.python.services.coaching_review_repository import CoachingReviewRepository
from src.main.python.services.telegram_notifier import get_notifier

router = APIRouter(prefix="/accounts", tags=["coaching"])

_coach = AICoachService()


def _get_coaching_repo(db: Session) -> CoachingReviewRepository:
    return CoachingReviewRepository(db)


@router.post("/{account_id}/coaching/weekly-review", response_model=WeeklyReviewResponse)
def generate_weekly_review(
    account_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Generate an AI coaching review for the specified date range.

    Always returns a result — falls back to a rule-based review if the AI is
    unavailable, the API key is missing, or the response cannot be parsed.

    The review is persisted to the coaching_reviews table.
    source="ai" for Claude-generated; source="fallback" for rule-based.

    Date range filters on exit_datetime (closed trades only).
    If no dates are supplied, all trades in the account are analyzed.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    coaching_repo = _get_coaching_repo(db)
    account = require_account(account_id, account_repo)

    trades, _ = trade_repo.get_by_account_filtered(
        account_id,
        from_date=from_date,
        to_date=to_date,
        page_size=10_000,
    )
    if not trades:
        raise HTTPException(
            status_code=422,
            detail="No closed trades found for the specified date range. Import trades first.",
        )

    # Enrich trades with planned_rr so coaching can include R:R vs planned signals
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

    # Load daily plans for the period (for discipline signals in coaching)
    daily_plan_repo = DailyPlanRepository(db)
    daily_plans = daily_plan_repo.list_plans(
        account_id,
        from_date=from_date.date() if from_date else None,
        to_date=to_date.date() if to_date else None,
    )

    # Generate (AI or fallback — never raises)
    result = _coach.generate(
        trades=trades,
        account=account,
        from_date=from_date.date() if from_date else None,
        to_date=to_date.date() if to_date else None,
        daily_plans=daily_plans or None,
    )

    # Persist
    review_id = str(uuid.uuid4())
    generated_at = datetime.utcnow()
    orm = CoachingReviewModel(
        review_id=review_id,
        account_id=account_id,
        from_date=from_date.date() if from_date else None,
        to_date=to_date.date() if to_date else None,
        generated_at=generated_at,
        model_used=result.model_used,
        source=result.source,
        status=result.status,
        output_json=json.dumps(result.to_output_dict()),
        raw_response=result.raw_response,
        error_message=result.error_message,
    )
    coaching_repo.save(orm)

    try:
        get_notifier().notify_coaching_generated(
            account_name=account_id,
            from_date=from_date.date().isoformat() if from_date else None,
            to_date=to_date.date().isoformat() if to_date else None,
            result=result,
        )
    except Exception:
        pass  # notification failure must never affect coaching response

    return WeeklyReviewResponse(
        review_id=review_id,
        account_id=account_id,
        from_date=from_date.date().isoformat() if from_date else None,
        to_date=to_date.date().isoformat() if to_date else None,
        generated_at=generated_at.isoformat(),
        model_used=result.model_used,
        source=result.source,
        status=result.status,
        summary=result.summary,
        top_mistakes=[
            MistakeInsight(tag=m.get("tag", ""), pattern=m.get("pattern", ""))
            for m in result.top_mistakes
        ],
        diagnosis=result.diagnosis,
        improvement=result.improvement,
    )


@router.get("/{account_id}/coaching/reviews", response_model=CoachingReviewListResponse)
def list_coaching_reviews(
    account_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """
    Return the most recent coaching reviews for an account, newest first.
    Each item includes a summary_preview (first 120 chars) for quick scanning.
    """
    account_repo = get_account_repo(db)
    coaching_repo = _get_coaching_repo(db)
    require_account(account_id, account_repo)

    rows = coaching_repo.list_by_account(account_id, limit=limit)
    items = []
    for row in rows:
        # Recover summary from output_json if available
        summary_preview = ""
        if row.output_json:
            try:
                data = json.loads(row.output_json)
                summary_preview = (data.get("summary") or "")[:120]
            except (json.JSONDecodeError, AttributeError):
                pass

        items.append(CoachingReviewListItem(
            review_id=row.review_id,
            account_id=row.account_id,
            from_date=row.from_date.isoformat() if row.from_date else None,
            to_date=row.to_date.isoformat() if row.to_date else None,
            generated_at=row.generated_at.isoformat(),
            model_used=row.model_used,
            source=row.source,
            status=row.status,
            summary_preview=summary_preview,
        ))

    return CoachingReviewListResponse(
        account_id=account_id,
        total=len(items),
        reviews=items,
    )


@router.get("/{account_id}/coaching/reviews/{review_id}", response_model=CoachingReviewDetailResponse)
def get_coaching_review(
    account_id: str,
    review_id: str,
    db: Session = Depends(get_db),
):
    """
    Return the full content of a single saved coaching review.
    Reconstructs the review sections from the stored output_json.
    """
    account_repo = get_account_repo(db)
    coaching_repo = _get_coaching_repo(db)
    require_account(account_id, account_repo)

    row = coaching_repo.get_by_id(review_id)
    if not row or row.account_id != account_id:
        raise HTTPException(status_code=404, detail=f"Coaching review '{review_id}' not found")

    output: dict = {}
    if row.output_json:
        try:
            output = json.loads(row.output_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return CoachingReviewDetailResponse(
        review_id=row.review_id,
        account_id=row.account_id,
        from_date=row.from_date.isoformat() if row.from_date else None,
        to_date=row.to_date.isoformat() if row.to_date else None,
        generated_at=row.generated_at.isoformat(),
        model_used=row.model_used or "",
        source=row.source or "fallback",
        status=row.status or "fallback",
        summary=output.get("summary", ""),
        top_mistakes=[
            MistakeInsight(tag=m.get("tag", ""), pattern=m.get("pattern", ""))
            for m in (output.get("top_mistakes") or [])
            if isinstance(m, dict)
        ],
        diagnosis=output.get("diagnosis", ""),
        improvement=output.get("improvement", ""),
    )
