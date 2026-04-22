from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from src.main.python.models.trade_plan import TradePlan
from src.main.python.api.schemas.trade import TradeResponse


class TradePlanCreate(BaseModel):
    symbol: Optional[str] = None
    intended_direction: Optional[str] = None   # long | short

    setup_type: Optional[str] = None
    strategy: Optional[str] = None

    bias: Optional[str] = None
    thesis: Optional[str] = None
    entry_logic: Optional[str] = None
    stop_loss_logic: Optional[str] = None
    take_profit_logic: Optional[str] = None
    invalidation_logic: Optional[str] = None

    planned_entry_zone: Optional[str] = None
    planned_stop_loss: Optional[float] = None
    planned_take_profit: Optional[float] = None
    planned_rr: Optional[float] = None

    is_a_plus_setup: Optional[bool] = None
    notes: Optional[str] = None


class TradePlanUpdate(BaseModel):
    status: Optional[str] = None            # planned | linked | cancelled
    symbol: Optional[str] = None
    intended_direction: Optional[str] = None

    setup_type: Optional[str] = None
    strategy: Optional[str] = None

    bias: Optional[str] = None
    thesis: Optional[str] = None
    entry_logic: Optional[str] = None
    stop_loss_logic: Optional[str] = None
    take_profit_logic: Optional[str] = None
    invalidation_logic: Optional[str] = None

    planned_entry_zone: Optional[str] = None
    planned_stop_loss: Optional[float] = None
    planned_take_profit: Optional[float] = None
    planned_rr: Optional[float] = None

    is_a_plus_setup: Optional[bool] = None
    notes: Optional[str] = None


class TradePlanResponse(BaseModel):
    plan_id: str
    account_id: str
    status: str

    symbol: Optional[str]
    intended_direction: Optional[str]

    setup_type: Optional[str]
    strategy: Optional[str]

    bias: Optional[str]
    thesis: Optional[str]
    entry_logic: Optional[str]
    stop_loss_logic: Optional[str]
    take_profit_logic: Optional[str]
    invalidation_logic: Optional[str]

    planned_entry_zone: Optional[str]
    planned_stop_loss: Optional[float]
    planned_take_profit: Optional[float]
    planned_rr: Optional[float]

    is_a_plus_setup: Optional[bool]
    notes: Optional[str]

    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    @classmethod
    def from_domain(cls, plan: TradePlan) -> TradePlanResponse:
        return cls(
            plan_id=plan.plan_id,
            account_id=plan.account_id,
            status=plan.status,
            symbol=plan.symbol,
            intended_direction=plan.intended_direction,
            setup_type=plan.setup_type,
            strategy=plan.strategy,
            bias=plan.bias,
            thesis=plan.thesis,
            entry_logic=plan.entry_logic,
            stop_loss_logic=plan.stop_loss_logic,
            take_profit_logic=plan.take_profit_logic,
            invalidation_logic=plan.invalidation_logic,
            planned_entry_zone=plan.planned_entry_zone,
            planned_stop_loss=plan.planned_stop_loss,
            planned_take_profit=plan.planned_take_profit,
            planned_rr=plan.planned_rr,
            is_a_plus_setup=plan.is_a_plus_setup,
            notes=plan.notes,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )


class TradePlanSuggestionItem(BaseModel):
    """A scored candidate trade for plan linking."""
    trade: TradeResponse
    score: float
    reasons: List[str]
