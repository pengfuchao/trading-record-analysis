from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.main.python.models.daily_plan import DailyPlan, DailyReview
from src.main.python.core.performance_summary import DailyAdherenceReport


# ── Pre-market Plan schemas ────────────────────────────────────────────────────

class DailyPlanCreate(BaseModel):
    trading_date:       date
    market_bias:        Optional[str]   = None
    symbols_in_focus:   List[str]       = Field(default_factory=list)
    key_levels:         Optional[str]   = None
    major_news:         Optional[str]   = None
    allowed_setups:     List[str]       = Field(default_factory=list)
    disallowed_setups:  List[str]       = Field(default_factory=list)
    daily_max_risk_pct: Optional[float] = None
    max_trades:         Optional[int]   = None
    behavioral_focus:   Optional[str]   = None
    special_rule:       Optional[str]   = None


class DailyPlanUpdate(BaseModel):
    market_bias:        Optional[str]   = None
    symbols_in_focus:   Optional[List[str]] = None
    key_levels:         Optional[str]   = None
    major_news:         Optional[str]   = None
    allowed_setups:     Optional[List[str]] = None
    disallowed_setups:  Optional[List[str]] = None
    daily_max_risk_pct: Optional[float] = None
    max_trades:         Optional[int]   = None
    behavioral_focus:   Optional[str]   = None
    special_rule:       Optional[str]   = None


class DailyPlanResponse(BaseModel):
    plan_id:            str
    account_id:         str
    trading_date:       date
    market_bias:        Optional[str]
    symbols_in_focus:   List[str]
    key_levels:         Optional[str]
    major_news:         Optional[str]
    allowed_setups:     List[str]
    disallowed_setups:  List[str]
    daily_max_risk_pct: Optional[float]
    max_trades:         Optional[int]
    behavioral_focus:   Optional[str]
    special_rule:       Optional[str]
    created_at:         Optional[datetime]
    updated_at:         Optional[datetime]


# ── Post-market Review schemas ─────────────────────────────────────────────────

class DailyReviewCreate(BaseModel):
    trading_date:       date
    plan_id:            Optional[str]   = None
    total_trades:       Optional[int]   = None
    total_pnl:          Optional[float] = None
    total_r:            Optional[float] = None
    planned_trades:     Optional[int]   = None
    unplanned_trades:   Optional[int]   = None
    best_trade_id:      Optional[str]   = None
    worst_trade_id:     Optional[str]   = None
    biggest_mistake:    Optional[str]   = None
    emotional_summary:  Optional[str]   = None
    improvement_point:  Optional[str]   = None
    notes:              Optional[str]   = None
    process_success:    Optional[bool]  = None
    pnl_success:        Optional[bool]  = None


class DailyReviewUpdate(BaseModel):
    plan_id:            Optional[str]   = None
    total_trades:       Optional[int]   = None
    total_pnl:          Optional[float] = None
    total_r:            Optional[float] = None
    planned_trades:     Optional[int]   = None
    unplanned_trades:   Optional[int]   = None
    best_trade_id:      Optional[str]   = None
    worst_trade_id:     Optional[str]   = None
    biggest_mistake:    Optional[str]   = None
    emotional_summary:  Optional[str]   = None
    improvement_point:  Optional[str]   = None
    notes:              Optional[str]   = None
    process_success:    Optional[bool]  = None
    pnl_success:        Optional[bool]  = None


class DailyReviewResponse(BaseModel):
    review_id:          str
    account_id:         str
    trading_date:       date
    plan_id:            Optional[str]
    total_trades:       Optional[int]
    total_pnl:          Optional[float]
    total_r:            Optional[float]
    planned_trades:     Optional[int]
    unplanned_trades:   Optional[int]
    best_trade_id:      Optional[str]
    worst_trade_id:     Optional[str]
    biggest_mistake:    Optional[str]
    emotional_summary:  Optional[str]
    improvement_point:  Optional[str]
    notes:              Optional[str]
    process_success:    Optional[bool]
    pnl_success:        Optional[bool]
    created_at:         Optional[datetime]
    updated_at:         Optional[datetime]


# ── Converters ─────────────────────────────────────────────────────────────────

def plan_to_response(p: DailyPlan) -> DailyPlanResponse:
    return DailyPlanResponse(
        plan_id=p.plan_id,
        account_id=p.account_id,
        trading_date=p.trading_date,
        market_bias=p.market_bias,
        symbols_in_focus=p.symbols_in_focus,
        key_levels=p.key_levels,
        major_news=p.major_news,
        allowed_setups=p.allowed_setups,
        disallowed_setups=p.disallowed_setups,
        daily_max_risk_pct=p.daily_max_risk_pct,
        max_trades=p.max_trades,
        behavioral_focus=p.behavioral_focus,
        special_rule=p.special_rule,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# ── Daily adherence schemas ────────────────────────────────────────────────────

class SetupViolationResponse(BaseModel):
    trade_id: str
    setup_type: Optional[str]


class DailyAdherenceResponse(BaseModel):
    trading_date:               date
    trades_taken:               int

    planned_count:              int
    unplanned_count:            int

    max_trades_limit:           Optional[int]
    max_trades_exceeded:        bool
    max_trades_exceeded_by:     int

    allowed_setups_configured:  bool
    outside_allowed_count:      int
    outside_allowed_setups:     List[str]

    disallowed_setups_configured: bool
    disallowed_violation_count: int
    disallowed_violations:      List[SetupViolationResponse]

    untagged_count:             int
    discipline_signals:         List[str]

    # Plan context (for UI display)
    plan_allowed_setups:        List[str]
    plan_disallowed_setups:     List[str]
    plan_max_trades:            Optional[int]


def adherence_to_response(report: DailyAdherenceReport, plan) -> DailyAdherenceResponse:
    return DailyAdherenceResponse(
        trading_date=report.trading_date,
        trades_taken=report.trades_taken,
        planned_count=report.planned_count,
        unplanned_count=report.unplanned_count,
        max_trades_limit=report.max_trades_limit,
        max_trades_exceeded=report.max_trades_exceeded,
        max_trades_exceeded_by=report.max_trades_exceeded_by,
        allowed_setups_configured=report.allowed_setups_configured,
        outside_allowed_count=report.outside_allowed_count,
        outside_allowed_setups=report.outside_allowed_setups,
        disallowed_setups_configured=report.disallowed_setups_configured,
        disallowed_violation_count=report.disallowed_violation_count,
        disallowed_violations=[
            SetupViolationResponse(trade_id=v.trade_id, setup_type=v.setup_type)
            for v in report.disallowed_violations
        ],
        untagged_count=report.untagged_count,
        discipline_signals=report.discipline_signals,
        plan_allowed_setups=plan.allowed_setups,
        plan_disallowed_setups=plan.disallowed_setups,
        plan_max_trades=plan.max_trades,
    )


def review_to_response(r: DailyReview) -> DailyReviewResponse:
    return DailyReviewResponse(
        review_id=r.review_id,
        account_id=r.account_id,
        trading_date=r.trading_date,
        plan_id=r.plan_id,
        total_trades=r.total_trades,
        total_pnl=r.total_pnl,
        total_r=r.total_r,
        planned_trades=r.planned_trades,
        unplanned_trades=r.unplanned_trades,
        best_trade_id=r.best_trade_id,
        worst_trade_id=r.worst_trade_id,
        biggest_mistake=r.biggest_mistake,
        emotional_summary=r.emotional_summary,
        improvement_point=r.improvement_point,
        notes=r.notes,
        process_success=r.process_success,
        pnl_success=r.pnl_success,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )
