from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class PerformanceSummary:
    # ── Counts ─────────────────────────────────────────────────────────────
    total_trades:               int               = 0
    winning_trades:             int               = 0
    losing_trades:              int               = 0
    breakeven_trades:           int               = 0

    # ── Rates ──────────────────────────────────────────────────────────────
    win_rate:                   Optional[float]   = None  # 0.0–1.0
    loss_rate:                  Optional[float]   = None
    breakeven_rate:             Optional[float]   = None

    # ── PnL totals ─────────────────────────────────────────────────────────
    total_net_profit:           float             = 0.0
    total_gross_profit:         float             = 0.0
    total_gross_loss:           float             = 0.0   # negative float
    total_return_pct:           Optional[float]   = None  # None if starting_balance=0

    # ── PnL averages ───────────────────────────────────────────────────────
    avg_win:                    Optional[float]   = None
    avg_loss:                   Optional[float]   = None  # negative float
    largest_single_loss:        Optional[float]   = None  # negative float

    # ── Ratios ─────────────────────────────────────────────────────────────
    payoff_ratio:               Optional[float]   = None
    profit_factor:              Optional[float]   = None
    expectancy:                 Optional[float]   = None

    # ── R-Multiple ─────────────────────────────────────────────────────────
    avg_r_multiple:             Optional[float]   = None

    # ── Volatility / Risk-Adjusted ─────────────────────────────────────────
    std_returns:                Optional[float]   = None
    sharpe_ratio:               Optional[float]   = None
    sortino_ratio:              Optional[float]   = None
    calmar_ratio:               Optional[float]   = None
    recovery_factor:            Optional[float]   = None

    # ── Drawdown ───────────────────────────────────────────────────────────
    max_drawdown:               Optional[float]   = None  # absolute dollar (≤ 0)
    max_drawdown_pct:           Optional[float]   = None  # percentage (≤ 0)
    relative_drawdown:          Optional[float]   = None  # 0.0–1.0 ratio (≤ 0)
    daily_drawdown:             Optional[float]   = None  # worst calendar-day sum
    weekly_drawdown:            Optional[float]   = None  # worst ISO-week sum
    monthly_drawdown:           Optional[float]   = None  # worst calendar-month sum

    # ── Streaks ────────────────────────────────────────────────────────────
    max_consecutive_wins:       int               = 0
    max_consecutive_losses:     int               = 0
    avg_losing_streak:          Optional[float]   = None

    # ── Duration & Frequency ──────────────────────────────────────────────
    avg_holding_duration:       Optional[timedelta] = None
    trades_per_day:             Optional[float]   = None
    trades_per_week:            Optional[float]   = None
    trades_per_month:           Optional[float]   = None

    # ── Exposure ───────────────────────────────────────────────────────────
    exposure_by_symbol:         Dict[str, float]  = field(default_factory=dict)
    exposure_by_direction:      Dict[str, float]  = field(default_factory=dict)


@dataclass
class AccountReport:
    # ── Identity ───────────────────────────────────────────────────────────
    account_id:          str
    generated_at:        datetime = field(default_factory=datetime.utcnow)

    # ── Overall Performance ────────────────────────────────────────────────
    overall:             PerformanceSummary = field(default_factory=PerformanceSummary)

    # ── Time-Series Curves (parallel lists, ordered by exit_datetime) ──────
    equity_curve:        List[float]    = field(default_factory=list)
    drawdown_curve:      List[float]    = field(default_factory=list)
    trade_dates:         List[datetime] = field(default_factory=list)

    # ── Segmentation ───────────────────────────────────────────────────────
    by_symbol:           Dict[str, PerformanceSummary] = field(default_factory=dict)
    by_direction:        Dict[str, PerformanceSummary] = field(default_factory=dict)
    by_asset_class:      Dict[str, PerformanceSummary] = field(default_factory=dict)
    by_session:          Dict[str, PerformanceSummary] = field(default_factory=dict)
    by_setup_type:       Dict[str, PerformanceSummary] = field(default_factory=dict)
    by_strategy:         Dict[str, PerformanceSummary] = field(default_factory=dict)
    by_market_condition: Dict[str, PerformanceSummary] = field(default_factory=dict)
    by_weekday:          Dict[str, PerformanceSummary] = field(default_factory=dict)  # "Monday"…
    by_hour:             Dict[str, PerformanceSummary] = field(default_factory=dict)  # "0"…"23"
    by_month:            Dict[str, PerformanceSummary] = field(default_factory=dict)  # "2024-01"
    by_followed_plan:    Dict[str, PerformanceSummary] = field(default_factory=dict)  # "True"/"False"/"None"
    by_result:           Dict[str, PerformanceSummary] = field(default_factory=dict)  # "Win"/"Loss"/"Breakeven"
