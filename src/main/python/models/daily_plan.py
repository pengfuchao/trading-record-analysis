from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass
class DailyPlan:
    """Pre-market plan for a single trading day."""

    plan_id:            str
    account_id:         str
    trading_date:       date

    # Market context
    market_bias:        Optional[str]        = None   # bullish / bearish / neutral
    symbols_in_focus:   List[str]            = field(default_factory=list)
    key_levels:         Optional[str]        = None
    major_news:         Optional[str]        = None

    # Rules for the day
    allowed_setups:     List[str]            = field(default_factory=list)
    disallowed_setups:  List[str]            = field(default_factory=list)
    daily_max_risk_pct: Optional[float]      = None
    max_trades:         Optional[int]        = None

    # Behavioral goals
    behavioral_focus:   Optional[str]        = None
    special_rule:       Optional[str]        = None

    created_at:         Optional[datetime]   = None
    updated_at:         Optional[datetime]   = None


@dataclass
class DailyReview:
    """Post-market review for a single trading day."""

    review_id:          str
    account_id:         str
    trading_date:       date

    # Optional link to the pre-market plan
    plan_id:            Optional[str]        = None

    # Summary numbers
    total_trades:       Optional[int]        = None
    total_pnl:          Optional[float]      = None
    total_r:            Optional[float]      = None
    planned_trades:     Optional[int]        = None
    unplanned_trades:   Optional[int]        = None

    # Highlight trades (IDs pointing at trades table)
    best_trade_id:      Optional[str]        = None
    worst_trade_id:     Optional[str]        = None

    # Qualitative reflection
    biggest_mistake:    Optional[str]        = None
    emotional_summary:  Optional[str]        = None
    improvement_point:  Optional[str]        = None
    notes:              Optional[str]        = None

    # Outcome flags
    process_success:    Optional[bool]       = None   # was process good regardless of PnL?
    pnl_success:        Optional[bool]       = None   # was the PnL positive?

    created_at:         Optional[datetime]   = None
    updated_at:         Optional[datetime]   = None
