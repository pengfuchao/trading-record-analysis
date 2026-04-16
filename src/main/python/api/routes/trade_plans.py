from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, get_account_repo, get_trade_repo, require_account
from src.main.python.api.schemas.trade_plan import TradePlanCreate, TradePlanResponse, TradePlanUpdate
from src.main.python.api.schemas.trade import TradeResponse
from src.main.python.models.trade_plan import TradePlan
from src.main.python.services.trade_plan_repository import TradePlanRepository
from src.main.python.services.trade_repository import TradeRepository

router = APIRouter(prefix="/accounts", tags=["trade-plans"])


def _get_plan_repo(db: Session) -> TradePlanRepository:
    return TradePlanRepository(db)


def _require_plan(plan_id: str, account_id: str, repo: TradePlanRepository) -> TradePlan:
    plan = repo.get_by_id(plan_id)
    if not plan or plan.account_id != account_id:
        raise HTTPException(status_code=404, detail=f"Trade plan '{plan_id}' not found")
    return plan


@router.post("/{account_id}/trade-plans", response_model=TradePlanResponse, status_code=201)
def create_trade_plan(
    account_id: str,
    body: TradePlanCreate,
    db: Session = Depends(get_db),
):
    """Create a new pre-trade plan."""
    account_repo = get_account_repo(db)
    require_account(account_id, account_repo)
    repo = _get_plan_repo(db)
    plan = TradePlan(
        plan_id=str(uuid.uuid4()),
        account_id=account_id,
        status="planned",
        symbol=body.symbol,
        intended_direction=body.intended_direction,
        setup_type=body.setup_type,
        strategy=body.strategy,
        bias=body.bias,
        thesis=body.thesis,
        entry_logic=body.entry_logic,
        stop_loss_logic=body.stop_loss_logic,
        take_profit_logic=body.take_profit_logic,
        invalidation_logic=body.invalidation_logic,
        planned_entry_zone=body.planned_entry_zone,
        planned_stop_loss=body.planned_stop_loss,
        planned_take_profit=body.planned_take_profit,
        planned_rr=body.planned_rr,
        is_a_plus_setup=body.is_a_plus_setup,
        notes=body.notes,
    )
    saved = repo.create(account_id, plan)
    return TradePlanResponse.from_domain(saved)


@router.get("/{account_id}/trade-plans", response_model=List[TradePlanResponse])
def list_trade_plans(
    account_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all trade plans for an account. Optionally filter by status."""
    account_repo = get_account_repo(db)
    require_account(account_id, account_repo)
    repo = _get_plan_repo(db)
    plans = repo.list_by_account(account_id, status=status)
    return [TradePlanResponse.from_domain(p) for p in plans]


@router.get("/{account_id}/trade-plans/{plan_id}", response_model=TradePlanResponse)
def get_trade_plan(
    account_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
):
    repo = _get_plan_repo(db)
    plan = _require_plan(plan_id, account_id, repo)
    return TradePlanResponse.from_domain(plan)


@router.patch("/{account_id}/trade-plans/{plan_id}", response_model=TradePlanResponse)
def update_trade_plan(
    account_id: str,
    plan_id: str,
    body: TradePlanUpdate,
    db: Session = Depends(get_db),
):
    repo = _get_plan_repo(db)
    _require_plan(plan_id, account_id, repo)
    updates = body.model_dump(exclude_none=True)
    updated = repo.update(plan_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Trade plan '{plan_id}' not found")
    return TradePlanResponse.from_domain(updated)


@router.delete("/{account_id}/trade-plans/{plan_id}", status_code=204)
def delete_trade_plan(
    account_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
):
    repo = _get_plan_repo(db)
    _require_plan(plan_id, account_id, repo)
    repo.delete(plan_id)


@router.post(
    "/{account_id}/trade-plans/{plan_id}/link/{trade_id}",
    response_model=TradeResponse,
)
def link_plan_to_trade(
    account_id: str,
    plan_id: str,
    trade_id: str,
    db: Session = Depends(get_db),
):
    """
    Manually link a trade plan to an existing trade.
    Sets trade.trade_plan_id = plan_id and marks the plan status as 'linked'.
    """
    plan_repo = _get_plan_repo(db)
    trade_repo: TradeRepository = get_trade_repo(db)

    plan = _require_plan(plan_id, account_id, plan_repo)
    trade = trade_repo.get_by_id(trade_id)
    if not trade or trade.account_id != account_id:
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")

    import dataclasses
    updated_trade = dataclasses.replace(trade, trade_plan_id=plan_id)
    saved_trade = trade_repo.save(updated_trade)

    # Update plan status to linked
    plan_repo.update(plan_id, {"status": "linked"})

    return TradeResponse.from_domain(saved_trade)


@router.delete(
    "/{account_id}/trade-plans/{plan_id}/link/{trade_id}",
    response_model=TradeResponse,
)
def unlink_plan_from_trade(
    account_id: str,
    plan_id: str,
    trade_id: str,
    db: Session = Depends(get_db),
):
    """
    Remove the link between a trade plan and a trade.
    Sets trade.trade_plan_id = None and resets the plan status back to 'planned'.
    """
    plan_repo = _get_plan_repo(db)
    trade_repo: TradeRepository = get_trade_repo(db)

    _require_plan(plan_id, account_id, plan_repo)
    trade = trade_repo.get_by_id(trade_id)
    if not trade or trade.account_id != account_id:
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")

    import dataclasses
    updated_trade = dataclasses.replace(trade, trade_plan_id=None)
    saved_trade = trade_repo.save(updated_trade)

    # Reset plan status back to planned if no other trades are linked
    plan_repo.update(plan_id, {"status": "planned"})

    return TradeResponse.from_domain(saved_trade)
