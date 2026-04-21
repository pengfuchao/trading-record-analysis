from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import (
    get_account_repo, get_db, get_trade_repo, require_account,
)
from src.main.python.api.schemas.setups import (
    SetupDefinitionCreate, SetupDefinitionResponse, SetupDefinitionUpdate,
    SetupReportResponse, setup_def_to_response, setup_report_to_response,
)
from src.main.python.core.setup_analyzer import SetupAnalyzer
from src.main.python.models.setup import SetupDefinition
from src.main.python.services.setup_repository import SetupRepository
from src.main.python.services.trade_plan_repository import TradePlanRepository

# ── Setup Definitions (CRUD) ──────────────────────────────────────────────────
setup_defs_router = APIRouter(prefix="/setups", tags=["setups"])

# ── Setup Analytics (account-scoped) ─────────────────────────────────────────
setup_stats_router = APIRouter(prefix="/accounts", tags=["setups"])

_analyzer = SetupAnalyzer()


def _get_setup_repo(db: Session) -> SetupRepository:
    return SetupRepository(db)


def _require_setup(setup_id: str, repo: SetupRepository) -> SetupDefinition:
    setup = repo.get_by_id(setup_id)
    if not setup:
        raise HTTPException(status_code=404, detail=f"Setup '{setup_id}' not found")
    return setup


# ── Definition routes ─────────────────────────────────────────────────────────

@setup_defs_router.get("", response_model=List[SetupDefinitionResponse])
def list_setups(db: Session = Depends(get_db)):
    return [setup_def_to_response(s) for s in _get_setup_repo(db).list_all()]


@setup_defs_router.post("", response_model=SetupDefinitionResponse, status_code=201)
def create_setup(body: SetupDefinitionCreate, db: Session = Depends(get_db)):
    setup = SetupDefinition(
        setup_id=body.setup_id,
        name=body.name,
        strategy_group=body.strategy_group,
        description=body.description,
        market_environment=body.market_environment,
        preconditions=body.preconditions,
        entry_criteria=body.entry_criteria,
        confirmation_rules=body.confirmation_rules,
        stop_loss_rules=body.stop_loss_rules,
        take_profit_rules=body.take_profit_rules,
        invalidation_conditions=body.invalidation_conditions,
        common_mistakes=body.common_mistakes,
        screenshot_examples=body.screenshot_examples,
        notes=body.notes,
    )
    saved = _get_setup_repo(db).save(setup)
    return setup_def_to_response(saved)


@setup_defs_router.get("/{setup_id}", response_model=SetupDefinitionResponse)
def get_setup(setup_id: str, db: Session = Depends(get_db)):
    repo = _get_setup_repo(db)
    return setup_def_to_response(_require_setup(setup_id, repo))


@setup_defs_router.patch("/{setup_id}", response_model=SetupDefinitionResponse)
def update_setup(
    setup_id: str,
    body: SetupDefinitionUpdate,
    db: Session = Depends(get_db),
):
    repo = _get_setup_repo(db)
    existing = _require_setup(setup_id, repo)
    update_data = body.model_dump(exclude_none=True)
    updated = dataclasses.replace(existing, **update_data, updated_at=datetime.utcnow())
    saved = repo.save(updated)
    return setup_def_to_response(saved)


@setup_defs_router.delete("/{setup_id}")
def delete_setup(setup_id: str, db: Session = Depends(get_db)):
    repo = _get_setup_repo(db)
    _require_setup(setup_id, repo)
    repo.delete(setup_id)
    return {"deleted": True}


# ── Analytics route ───────────────────────────────────────────────────────────

@setup_stats_router.get("/{account_id}/setups", response_model=SetupReportResponse)
def get_setup_report(
    account_id: str,
    symbol: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
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
        page_size=10_000,
    )

    # Enrich trades with planned_rr from linked plans so SetupAnalyzer can
    # compute per-setup R:R realization (same pattern as analytics.py).
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

    report = _analyzer.generate_report(trades, account_id)
    return setup_report_to_response(report)
