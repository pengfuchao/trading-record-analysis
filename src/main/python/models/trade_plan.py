from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TradePlan:
    plan_id: str
    account_id: str
    status: str                         # planned | linked | cancelled

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

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
