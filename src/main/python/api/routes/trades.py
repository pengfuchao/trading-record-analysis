from __future__ import annotations

import csv
import dataclasses
import io
import math
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, get_account_repo, get_trade_repo, require_account
from src.main.python.api.schemas.trade import TradeCreate, TradeListResponse, TradeResponse, TradeUpdate
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


@router.get("/{account_id}/trades", response_model=TradeListResponse)
def list_trades(
    account_id: str,
    symbol: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    result: Optional[str] = None,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Rows per page (max 500)"),
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    items, total = trade_repo.get_by_account_filtered(
        account_id,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        result=result,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, math.ceil(total / page_size))
    return TradeListResponse(
        items=[TradeResponse.from_domain(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{account_id}/trades/unlinked", response_model=List[TradeResponse])
def list_unlinked_trades(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return trades with no linked plan, ordered by entry_datetime descending."""
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    trades = trade_repo.get_unlinked_by_account(account_id, limit=limit)
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


_CSV_FIELDS = [
    "trade_id", "symbol", "direction", "asset_class", "session",
    "entry_datetime", "exit_datetime", "holding_duration_minutes",
    "entry_price", "exit_price", "stop_loss", "take_profit", "lot_size",
    "gross_pnl", "commission", "swap", "net_pnl", "actual_r_multiple", "result",
    "setup_type", "strategy", "trade_quality", "followed_plan", "is_a_plus_setup",
    "early_entry", "chasing", "fomo", "emotional_trade", "revenge_trade",
    "overtrading", "premature_exit", "moved_stop",
    "lesson_learned", "notes", "mistake_tags",
]


@router.get(
    "/{account_id}/trades/export/csv",
    response_class=StreamingResponse,
    summary="Export trade history as CSV",
)
def export_trades_csv(
    account_id: str,
    symbol: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    result: Optional[str] = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Download all trades for an account as a CSV file.
    Accepts the same filters as GET /trades (symbol, result, from_date, to_date).
    No pagination — exports all matching rows in one file.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    trades = trade_repo.get_all_filtered(
        account_id, symbol=symbol, from_date=from_date, to_date=to_date, result=result
    )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for trade in trades:
        dur = trade.holding_duration
        writer.writerow({
            "trade_id":               trade.trade_id,
            "symbol":                 trade.symbol or "",
            "direction":              trade.direction.value if trade.direction else "",
            "asset_class":            trade.asset_class.value if trade.asset_class else "",
            "session":                trade.session or "",
            "entry_datetime":         trade.entry_datetime.isoformat() if trade.entry_datetime else "",
            "exit_datetime":          trade.exit_datetime.isoformat() if trade.exit_datetime else "",
            "holding_duration_minutes": round(dur.total_seconds() / 60, 1) if dur else "",
            "entry_price":            trade.entry_price if trade.entry_price is not None else "",
            "exit_price":             trade.exit_price if trade.exit_price is not None else "",
            "stop_loss":              trade.stop_loss if trade.stop_loss is not None else "",
            "take_profit":            trade.take_profit if trade.take_profit is not None else "",
            "lot_size":               trade.lot_size if trade.lot_size is not None else "",
            "gross_pnl":              trade.gross_pnl if trade.gross_pnl is not None else "",
            "commission":             trade.commission if trade.commission is not None else "",
            "swap":                   trade.swap if trade.swap is not None else "",
            "net_pnl":                trade.net_pnl if trade.net_pnl is not None else "",
            "actual_r_multiple":      trade.actual_r_multiple if trade.actual_r_multiple is not None else "",
            "result":                 trade.result.value if trade.result else "",
            "setup_type":             trade.setup_type or "",
            "strategy":               trade.strategy or "",
            "trade_quality":          trade.trade_quality or "",
            "followed_plan":          "" if trade.followed_plan is None else str(trade.followed_plan),
            "is_a_plus_setup":        "" if trade.is_a_plus_setup is None else str(trade.is_a_plus_setup),
            "early_entry":            "" if trade.early_entry is None else str(trade.early_entry),
            "chasing":                "" if trade.chasing is None else str(trade.chasing),
            "fomo":                   "" if trade.fomo is None else str(trade.fomo),
            "emotional_trade":        "" if trade.emotional_trade is None else str(trade.emotional_trade),
            "revenge_trade":          "" if trade.revenge_trade is None else str(trade.revenge_trade),
            "overtrading":            "" if trade.overtrading is None else str(trade.overtrading),
            "premature_exit":         "" if trade.premature_exit is None else str(trade.premature_exit),
            "moved_stop":             "" if trade.moved_stop is None else str(trade.moved_stop),
            "lesson_learned":         trade.lesson_learned or "",
            "notes":                  trade.notes or "",
            "mistake_tags":           "|".join(trade.mistake_tags) if trade.mistake_tags else "",
        })

    filename = f"trades_{account_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
