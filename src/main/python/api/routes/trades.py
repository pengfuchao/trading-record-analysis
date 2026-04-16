from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, get_account_repo, get_trade_repo, require_account
from src.main.python.api.schemas.trade import TradeCreate, TradeResponse, TradeUpdate
from src.main.python.models.trade import Trade
from src.main.python.services.account_repository import AccountRepository
from src.main.python.services.derived_field_calculator import DerivedFieldCalculator
from src.main.python.services.trade_repository import TradeRepository

router = APIRouter(prefix="/accounts", tags=["trades"])


def _require_trade(trade_id: str, account_id: str, repo: TradeRepository) -> Trade:
    """Fetch trade and verify it belongs to the account, or raise 404."""
    trade = repo.get_by_id(trade_id)
    if not trade or trade.account_id != account_id:
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")
    return trade


@router.get("/{account_id}/trades", response_model=List[TradeResponse])
def list_trades(
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
    trades = trade_repo.get_by_account_filtered(
        account_id,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        result=result,
    )
    return [TradeResponse.from_domain(t) for t in trades]


@router.post("/{account_id}/trades", response_model=TradeResponse, status_code=201)
def create_trade(
    account_id: str,
    body: TradeCreate,
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    holding_duration = (
        timedelta(seconds=body.holding_duration_seconds)
        if body.holding_duration_seconds is not None else None
    )
    trade = Trade(
        trade_id=body.trade_id,
        account_id=account_id,
        symbol=body.symbol,
        asset_class=body.asset_class,
        direction=body.direction,
        platform=body.platform,
        raw_trade_type=body.raw_trade_type,
        entry_datetime=body.entry_datetime,
        exit_datetime=body.exit_datetime,
        holding_duration=holding_duration,
        entry_price=body.entry_price,
        exit_price=body.exit_price,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
        lot_size=body.lot_size,
        gross_pnl=body.gross_pnl,
        commission=body.commission,
        swap=body.swap,
        net_pnl=body.net_pnl,
        actual_r_multiple=body.actual_r_multiple,
        result=body.result,
        magic=body.magic,
        comment=body.comment,
        setup_type=body.setup_type,
        strategy=body.strategy,
        session=body.session,
        higher_tf_bias=body.higher_tf_bias,
        entry_timeframe=body.entry_timeframe,
        market_condition=body.market_condition,
        key_levels=body.key_levels,
        news_context=body.news_context,
        pre_trade_bias=body.pre_trade_bias,
        entry_reason=body.entry_reason,
        trigger_confirmation=body.trigger_confirmation,
        stop_loss_logic=body.stop_loss_logic,
        take_profit_logic=body.take_profit_logic,
        exit_reason=body.exit_reason,
        followed_plan=body.followed_plan,
        is_a_plus_setup=body.is_a_plus_setup,
        early_entry=body.early_entry,
        chasing=body.chasing,
        fomo=body.fomo,
        emotional_trade=body.emotional_trade,
        revenge_trade=body.revenge_trade,
        overtrading=body.overtrading,
        hesitation=body.hesitation,
        moved_stop=body.moved_stop,
        premature_exit=body.premature_exit,
        held_loser_too_long=body.held_loser_too_long,
        trade_quality=body.trade_quality,
        problem_source=body.problem_source,
        mistake_tags=body.mistake_tags,
        lesson_learned=body.lesson_learned,
        repeat_next_time=body.repeat_next_time,
        avoid_next_time=body.avoid_next_time,
        screenshot_before=body.screenshot_before,
        screenshot_during=body.screenshot_during,
        screenshot_after=body.screenshot_after,
        notes=body.notes,
    )
    saved = trade_repo.save(trade)
    return TradeResponse.from_domain(saved)


@router.get("/{account_id}/trades/{trade_id}", response_model=TradeResponse)
def get_trade(
    account_id: str,
    trade_id: str,
    db: Session = Depends(get_db),
):
    trade_repo = get_trade_repo(db)
    trade = _require_trade(trade_id, account_id, trade_repo)
    return TradeResponse.from_domain(trade)


@router.patch("/{account_id}/trades/{trade_id}", response_model=TradeResponse)
def update_trade(
    account_id: str,
    trade_id: str,
    body: TradeUpdate,
    db: Session = Depends(get_db),
):
    trade_repo = get_trade_repo(db)
    existing = _require_trade(trade_id, account_id, trade_repo)
    update_data = body.model_dump(exclude_none=True)
    # Empty string for trade_plan_id means "unlink" — treat as explicit None
    if "trade_plan_id" in update_data and update_data["trade_plan_id"] == "":
        update_data["trade_plan_id"] = None
    updated = dataclasses.replace(existing, **update_data)
    # Recompute R when stop_loss is explicitly provided in the update
    if "stop_loss" in update_data:
        updated = dataclasses.replace(
            updated,
            actual_r_multiple=DerivedFieldCalculator.calc_actual_r(
                exit_price=updated.exit_price,
                entry_price=updated.entry_price,
                stop_loss=updated.stop_loss,
                direction=updated.direction,
            ),
        )
    saved = trade_repo.save(updated)
    return TradeResponse.from_domain(saved)


@router.delete("/{account_id}/trades/{trade_id}")
def delete_trade(
    account_id: str,
    trade_id: str,
    db: Session = Depends(get_db),
):
    trade_repo = get_trade_repo(db)
    _require_trade(trade_id, account_id, trade_repo)
    trade_repo.delete(trade_id)
    return {"deleted": True}
