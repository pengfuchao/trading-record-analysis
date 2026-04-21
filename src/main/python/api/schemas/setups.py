from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from src.main.python.models.setup import SetupDefinition, SetupReport, SetupStats


# ── Setup Definition schemas ──────────────────────────────────────────────────

class SetupDefinitionCreate(BaseModel):
    setup_id: str
    name: str
    strategy_group: Optional[str] = None
    description: Optional[str] = None
    market_environment: Optional[str] = None
    preconditions: Optional[str] = None
    entry_criteria: Optional[str] = None
    confirmation_rules: Optional[str] = None
    stop_loss_rules: Optional[str] = None
    take_profit_rules: Optional[str] = None
    invalidation_conditions: Optional[str] = None
    common_mistakes: Optional[str] = None
    screenshot_examples: List[str] = []
    notes: Optional[str] = None


class SetupDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    strategy_group: Optional[str] = None
    description: Optional[str] = None
    market_environment: Optional[str] = None
    preconditions: Optional[str] = None
    entry_criteria: Optional[str] = None
    confirmation_rules: Optional[str] = None
    stop_loss_rules: Optional[str] = None
    take_profit_rules: Optional[str] = None
    invalidation_conditions: Optional[str] = None
    common_mistakes: Optional[str] = None
    screenshot_examples: Optional[List[str]] = None
    notes: Optional[str] = None


class SetupDefinitionResponse(BaseModel):
    setup_id: str
    name: str
    strategy_group: Optional[str]
    description: Optional[str]
    market_environment: Optional[str]
    preconditions: Optional[str]
    entry_criteria: Optional[str]
    confirmation_rules: Optional[str]
    stop_loss_rules: Optional[str]
    take_profit_rules: Optional[str]
    invalidation_conditions: Optional[str]
    common_mistakes: Optional[str]
    screenshot_examples: List[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


def setup_def_to_response(s: SetupDefinition) -> SetupDefinitionResponse:
    return SetupDefinitionResponse(
        setup_id=s.setup_id,
        name=s.name,
        strategy_group=s.strategy_group,
        description=s.description,
        market_environment=s.market_environment,
        preconditions=s.preconditions,
        entry_criteria=s.entry_criteria,
        confirmation_rules=s.confirmation_rules,
        stop_loss_rules=s.stop_loss_rules,
        take_profit_rules=s.take_profit_rules,
        invalidation_conditions=s.invalidation_conditions,
        common_mistakes=s.common_mistakes,
        screenshot_examples=s.screenshot_examples,
        notes=s.notes,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


# ── Setup Analytics schemas ───────────────────────────────────────────────────

class SetupStatsResponse(BaseModel):
    setup_type: str
    trade_count: int
    win_rate: Optional[float]
    loss_rate: Optional[float]
    breakeven_rate: Optional[float]
    expectancy: Optional[float]
    avg_r_multiple: Optional[float]
    profit_factor: Optional[float]
    total_net_profit: float
    avg_win: Optional[float]
    avg_loss: Optional[float]
    max_drawdown: Optional[float]
    max_consecutive_losses: int
    avg_holding_duration_seconds: Optional[float]
    a_plus_rate: Optional[float]
    followed_plan_rate: Optional[float]
    by_session: Dict[str, float]
    by_market_condition: Dict[str, float]
    by_symbol: Dict[str, float]
    best_session: Optional[str]
    worst_session: Optional[str]
    best_market_condition: Optional[str]
    worst_market_condition: Optional[str]
    best_symbol: Optional[str]
    worst_symbol: Optional[str]
    common_mistakes: Dict[str, int]
    # Planned R:R vs realized R (rr_sample_count=0 means no qualifying trades)
    rr_sample_count: int = 0
    rr_avg_planned_rr: Optional[float] = None
    rr_avg_actual_r: Optional[float] = None
    rr_avg_shortfall: Optional[float] = None
    rr_realization_pct: Optional[float] = None
    rr_pct_met_target: Optional[float] = None


class SetupReportResponse(BaseModel):
    account_id: str
    generated_at: datetime
    total_trades_analyzed: int
    trades_with_setup: int
    by_setup: Dict[str, SetupStatsResponse]
    ranked_by_win_rate: List[str]
    ranked_by_expectancy: List[str]
    ranked_by_avg_r: List[str]
    ranked_by_total_profit: List[str]
    ranked_by_drawdown: List[str]
    ranked_by_rr_realization: List[str] = []


def _stats_to_response(s: SetupStats) -> SetupStatsResponse:
    return SetupStatsResponse(
        setup_type=s.setup_type,
        trade_count=s.trade_count,
        win_rate=s.win_rate,
        loss_rate=s.loss_rate,
        breakeven_rate=s.breakeven_rate,
        expectancy=s.expectancy,
        avg_r_multiple=s.avg_r_multiple,
        profit_factor=s.profit_factor,
        total_net_profit=s.total_net_profit,
        avg_win=s.avg_win,
        avg_loss=s.avg_loss,
        max_drawdown=s.max_drawdown,
        max_consecutive_losses=s.max_consecutive_losses,
        avg_holding_duration_seconds=s.avg_holding_duration_seconds,
        a_plus_rate=s.a_plus_rate,
        followed_plan_rate=s.followed_plan_rate,
        by_session=s.by_session,
        by_market_condition=s.by_market_condition,
        by_symbol=s.by_symbol,
        best_session=s.best_session,
        worst_session=s.worst_session,
        best_market_condition=s.best_market_condition,
        worst_market_condition=s.worst_market_condition,
        best_symbol=s.best_symbol,
        worst_symbol=s.worst_symbol,
        common_mistakes=s.common_mistakes,
        rr_sample_count=s.rr_sample_count,
        rr_avg_planned_rr=s.rr_avg_planned_rr,
        rr_avg_actual_r=s.rr_avg_actual_r,
        rr_avg_shortfall=s.rr_avg_shortfall,
        rr_realization_pct=s.rr_realization_pct,
        rr_pct_met_target=s.rr_pct_met_target,
    )


def setup_report_to_response(r: SetupReport) -> SetupReportResponse:
    return SetupReportResponse(
        account_id=r.account_id,
        generated_at=r.generated_at,
        total_trades_analyzed=r.total_trades_analyzed,
        trades_with_setup=r.trades_with_setup,
        by_setup={k: _stats_to_response(v) for k, v in r.by_setup.items()},
        ranked_by_win_rate=r.ranked_by_win_rate,
        ranked_by_expectancy=r.ranked_by_expectancy,
        ranked_by_avg_r=r.ranked_by_avg_r,
        ranked_by_total_profit=r.ranked_by_total_profit,
        ranked_by_drawdown=r.ranked_by_drawdown,
        ranked_by_rr_realization=r.ranked_by_rr_realization,
    )
