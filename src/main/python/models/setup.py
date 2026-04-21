from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SetupDefinition:
    """Playbook record — the static description of a named trading setup."""
    setup_id: str                              # PK slug, e.g. "ict-bos-retest"
    name: str                                  # Display name
    strategy_group: Optional[str] = None       # "ICT", "SMC", "Price Action"
    description: Optional[str] = None
    market_environment: Optional[str] = None   # "Trending", "Ranging", "High Volatility"
    preconditions: Optional[str] = None
    entry_criteria: Optional[str] = None
    confirmation_rules: Optional[str] = None
    stop_loss_rules: Optional[str] = None
    take_profit_rules: Optional[str] = None
    invalidation_conditions: Optional[str] = None
    common_mistakes: Optional[str] = None      # free text
    screenshot_examples: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SetupStats:
    """Per-setup aggregated performance, computed on-demand from historical trades."""
    setup_type: str
    trade_count: int

    # Win/loss breakdown
    win_rate: Optional[float] = None
    loss_rate: Optional[float] = None
    breakeven_rate: Optional[float] = None

    # PnL metrics
    expectancy: Optional[float] = None        # avg net_pnl per trade (dollar)
    avg_r_multiple: Optional[float] = None
    profit_factor: Optional[float] = None
    total_net_profit: float = 0.0
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None

    # Risk metrics
    max_drawdown: Optional[float] = None       # absolute dollar (≤ 0)
    max_consecutive_losses: int = 0

    # Duration
    avg_holding_duration_seconds: Optional[float] = None

    # Execution quality
    a_plus_rate: Optional[float] = None        # fraction where is_a_plus_setup=True
    followed_plan_rate: Optional[float] = None

    # Condition breakdowns (segment key → win_rate for that segment)
    by_session: Dict[str, float] = field(default_factory=dict)
    by_market_condition: Dict[str, float] = field(default_factory=dict)
    by_symbol: Dict[str, float] = field(default_factory=dict)

    # Best/worst conditions (≥2 trades required to qualify)
    best_session: Optional[str] = None
    worst_session: Optional[str] = None
    best_market_condition: Optional[str] = None
    worst_market_condition: Optional[str] = None
    best_symbol: Optional[str] = None
    worst_symbol: Optional[str] = None

    # Common mistakes on this setup (tag → count)
    common_mistakes: Dict[str, int] = field(default_factory=dict)

    # Planned R:R vs realized R (only populated when trades have a linked plan +
    # planned_rr > 0 + actual_r_multiple set; rr_sample_count=0 means no data)
    rr_sample_count: int = 0
    rr_avg_planned_rr: Optional[float] = None
    rr_avg_actual_r: Optional[float] = None
    rr_avg_shortfall: Optional[float] = None    # negative = fell short of plan
    rr_realization_pct: Optional[float] = None  # (avg_actual / avg_planned) * 100
    rr_pct_met_target: Optional[float] = None   # % trades where actual_r >= planned_rr


@dataclass
class SetupReport:
    """Account-level setup performance report."""
    account_id: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    total_trades_analyzed: int = 0
    trades_with_setup: int = 0            # trades where setup_type is not None
    by_setup: Dict[str, SetupStats] = field(default_factory=dict)
    ranked_by_win_rate: List[str] = field(default_factory=list)    # desc
    ranked_by_expectancy: List[str] = field(default_factory=list)  # desc
    ranked_by_avg_r: List[str] = field(default_factory=list)       # desc
    ranked_by_total_profit: List[str] = field(default_factory=list)  # desc
    ranked_by_drawdown: List[str] = field(default_factory=list)    # worst first (most negative)
    ranked_by_rr_realization: List[str] = field(default_factory=list)  # desc, only setups with rr_sample_count >= 1
