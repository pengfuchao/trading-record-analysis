from __future__ import annotations

import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_account_repo, get_db, require_account
from src.main.python.api.schemas.daily_plan import (
    DailyAdherenceResponse, DailyPlanCreate, DailyPlanResponse, DailyPlanUpdate,
    DailyReviewCreate, DailyReviewResponse, DailyReviewUpdate,
    adherence_to_response, plan_to_response, review_to_response,
)
from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.models.daily_plan import DailyPlan, DailyReview
from src.main.python.services.daily_plan_repository import DailyPlanRepository
from src.main.python.services.trade_repository import TradeRepository

plans_router = APIRouter(prefix="/accounts", tags=["daily-plans"])
reviews_router = APIRouter(prefix="/accounts", tags=["daily-reviews"])


def _get_repo(db: Session) -> DailyPlanRepository:
    return DailyPlanRepository(db)


# ── Pre-market Plans ───────────────────────────────────────────────────────────

@plans_router.post("/{account_id}/daily-plans", response_model=DailyPlanResponse, status_code=201)
def create_plan(
    account_id: str,
    body: DailyPlanCreate,
    db: Session = Depends(get_db),
):
    require_account(account_id, get_account_repo(db))
    repo = _get_repo(db)
    existing = repo.get_plan_by_date(account_id, body.trading_date)
    if existing:
        raise HTTPException(status_code=409, detail=f"Plan for {body.trading_date} already exists (id={existing.plan_id})")
    plan = DailyPlan(
        plan_id=str(uuid.uuid4()),
        account_id=account_id,
        trading_date=body.trading_date,
        market_bias=body.market_bias,
        symbols_in_focus=body.symbols_in_focus,
        key_levels=body.key_levels,
        major_news=body.major_news,
        allowed_setups=body.allowed_setups,
        disallowed_setups=body.disallowed_setups,
        daily_max_risk_pct=body.daily_max_risk_pct,
        max_trades=body.max_trades,
        behavioral_focus=body.behavioral_focus,
        special_rule=body.special_rule,
    )
    saved = repo.create_plan(account_id, plan)
    return plan_to_response(saved)


@plans_router.get("/{account_id}/daily-plans", response_model=List[DailyPlanResponse])
def list_plans(
    account_id: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    require_account(account_id, get_account_repo(db))
    plans = _get_repo(db).list_plans(account_id, from_date=from_date, to_date=to_date)
    return [plan_to_response(p) for p in plans]


@plans_router.get("/{account_id}/daily-plans/{plan_id}", response_model=DailyPlanResponse)
def get_plan(account_id: str, plan_id: str, db: Session = Depends(get_db)):
    require_account(account_id, get_account_repo(db))
    plan = _get_repo(db).get_plan_by_id(plan_id)
    if not plan or plan.account_id != account_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan_to_response(plan)


@plans_router.patch("/{account_id}/daily-plans/{plan_id}", response_model=DailyPlanResponse)
def update_plan(
    account_id: str,
    plan_id: str,
    body: DailyPlanUpdate,
    db: Session = Depends(get_db),
):
    require_account(account_id, get_account_repo(db))
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    updated = _get_repo(db).update_plan(plan_id, updates)
    if not updated or updated.account_id != account_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan_to_response(updated)


@plans_router.delete("/{account_id}/daily-plans/{plan_id}", status_code=204)
def delete_plan(account_id: str, plan_id: str, db: Session = Depends(get_db)):
    require_account(account_id, get_account_repo(db))
    deleted = _get_repo(db).delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")


@plans_router.get("/{account_id}/daily-plans/{plan_id}/adherence", response_model=DailyAdherenceResponse)
def get_daily_adherence(account_id: str, plan_id: str, db: Session = Depends(get_db)):
    """
    Compute daily plan adherence for the given plan's trading_date.

    Compares closed trades (exit_datetime on plan.trading_date) against:
      - max_trades limit
      - allowed_setups list (if configured)
      - disallowed_setups list (if configured)
      - planned vs unplanned trade counts (via TradePlan linkage)

    daily_max_risk_pct is NOT checked — per-trade risk % requires instrument-specific
    pip values not available in current Trade fields.
    """
    require_account(account_id, get_account_repo(db))
    repo = _get_repo(db)
    plan = repo.get_plan_by_id(plan_id)
    if not plan or plan.account_id != account_id:
        raise HTTPException(status_code=404, detail="Plan not found")

    trades = TradeRepository(db).get_trades_for_date(account_id, plan.trading_date)
    report = AccountAnalytics.compute_daily_adherence(plan, trades)
    return adherence_to_response(report, plan)


# ── Post-market Reviews ────────────────────────────────────────────────────────

@reviews_router.post("/{account_id}/daily-reviews", response_model=DailyReviewResponse, status_code=201)
def create_review(
    account_id: str,
    body: DailyReviewCreate,
    db: Session = Depends(get_db),
):
    require_account(account_id, get_account_repo(db))
    repo = _get_repo(db)
    existing = repo.get_review_by_date(account_id, body.trading_date)
    if existing:
        raise HTTPException(status_code=409, detail=f"Review for {body.trading_date} already exists (id={existing.review_id})")
    review = DailyReview(
        review_id=str(uuid.uuid4()),
        account_id=account_id,
        trading_date=body.trading_date,
        plan_id=body.plan_id,
        total_trades=body.total_trades,
        total_pnl=body.total_pnl,
        total_r=body.total_r,
        planned_trades=body.planned_trades,
        unplanned_trades=body.unplanned_trades,
        best_trade_id=body.best_trade_id,
        worst_trade_id=body.worst_trade_id,
        biggest_mistake=body.biggest_mistake,
        emotional_summary=body.emotional_summary,
        improvement_point=body.improvement_point,
        notes=body.notes,
        process_success=body.process_success,
        pnl_success=body.pnl_success,
    )
    saved = repo.create_review(account_id, review)
    return review_to_response(saved)


@reviews_router.get("/{account_id}/daily-reviews", response_model=List[DailyReviewResponse])
def list_reviews(
    account_id: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    require_account(account_id, get_account_repo(db))
    reviews = _get_repo(db).list_reviews(account_id, from_date=from_date, to_date=to_date)
    return [review_to_response(r) for r in reviews]


@reviews_router.get("/{account_id}/daily-reviews/{review_id}", response_model=DailyReviewResponse)
def get_review(account_id: str, review_id: str, db: Session = Depends(get_db)):
    require_account(account_id, get_account_repo(db))
    review = _get_repo(db).get_review_by_id(review_id)
    if not review or review.account_id != account_id:
        raise HTTPException(status_code=404, detail="Review not found")
    return review_to_response(review)


@reviews_router.patch("/{account_id}/daily-reviews/{review_id}", response_model=DailyReviewResponse)
def update_review(
    account_id: str,
    review_id: str,
    body: DailyReviewUpdate,
    db: Session = Depends(get_db),
):
    require_account(account_id, get_account_repo(db))
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    updated = _get_repo(db).update_review(review_id, updates)
    if not updated or updated.account_id != account_id:
        raise HTTPException(status_code=404, detail="Review not found")
    return review_to_response(updated)


@reviews_router.delete("/{account_id}/daily-reviews/{review_id}", status_code=204)
def delete_review(account_id: str, review_id: str, db: Session = Depends(get_db)):
    require_account(account_id, get_account_repo(db))
    deleted = _get_repo(db).delete_review(review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Review not found")
