from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional


@dataclass
class PerformanceSummary:
    # ── Counts ─────────────────────────────────────────────────────────────
    total_trades:               int               = 0
    winning_trades:             int               = 0
    losing_trades:              int               = 0
    breakeven_trades:           int               = 0

    # ── Rates ──────────────────────────────────────────────────────────────
    win_rate:                   Optional[float]   = None  # wins / total (0.0–1.0)
    win_rate_ex_be:             Optional[float]   = None  # wins / (wins+losses), excludes BE
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
    largest_single_win:         Optional[float]   = None  # positive float
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
    max_drawdown_pct:           Optional[float]   = None  # % of peak equity (≤ 0)
    max_drawdown_pct_of_starting_balance: Optional[float] = None  # % of starting balance (≤ 0); FTMO-style
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
class PlanAdherenceGroup:
    """Performance stats for one slice of plan adherence (e.g. planned / unplanned)."""
    count:        int
    win_rate:     Optional[float]   # 0.0–1.0
    avg_pnl:      Optional[float]   # average net PnL per trade
    avg_r:        Optional[float]   # average R multiple
    total_pnl:    float             # sum of net PnL
    profit_factor: Optional[float]


@dataclass
class RRComparisonReport:
    """
    Planned R:R vs realized R analytics.

    Inclusion criteria:
      - Trade has a linked plan (trade_plan_id is not None)
      - Linked plan has planned_rr set (float, > 0)
      - Trade has actual_r_multiple set (float, any sign)

    All negative-R trades are included — they are the most diagnostically important.
    avg_r_shortfall < 0 means realized R is below the planned target on average.
    realization_pct < 100 means planned targets are being under-delivered on average.
    """
    sample_count: int                       # trades meeting all inclusion criteria
    avg_planned_rr: Optional[float]         # mean planned_rr across qualifying trades
    avg_actual_r: Optional[float]           # mean actual_r_multiple across qualifying trades
    avg_r_shortfall: Optional[float]        # avg_actual_r - avg_planned_rr (negative = fell short)
    realization_pct: Optional[float]        # (avg_actual_r / avg_planned_rr) * 100; None if planned=0
    met_target_count: int                   # trades where actual_r >= planned_rr
    missed_target_count: int                # trades where actual_r < planned_rr
    pct_met_target: Optional[float]         # met_target_count / sample_count * 100
    coaching_signals: List[str] = field(default_factory=list)


@dataclass
class PlanAdherenceReport:
    """
    Plan-vs-execution analytics for one account over a date range.

    Dimension 1 — formal plan linkage (trade_plan_id):
      planned   = has a linked TradePlan document
      unplanned = no linked TradePlan

    Dimension 2 — self-reported adherence (followed_plan):
      followed  = followed_plan is True
      deviated  = followed_plan is False
      not_tagged = followed_plan is None (not recorded)

    Intersection:
      linked_but_deviated = has trade_plan_id AND followed_plan is False
    """
    total_trades: int

    # Dimension 1
    planned_count:   int
    unplanned_count: int
    planned_pct:     Optional[float]        # planned_count / total_trades * 100
    planned:         PlanAdherenceGroup = field(default_factory=lambda: PlanAdherenceGroup(0, None, None, None, 0.0, None))
    unplanned:       PlanAdherenceGroup = field(default_factory=lambda: PlanAdherenceGroup(0, None, None, None, 0.0, None))

    # Dimension 2
    followed_count:  int = 0
    deviated_count:  int = 0
    not_tagged_count: int = 0
    followed:        PlanAdherenceGroup = field(default_factory=lambda: PlanAdherenceGroup(0, None, None, None, 0.0, None))
    deviated:        PlanAdherenceGroup = field(default_factory=lambda: PlanAdherenceGroup(0, None, None, None, 0.0, None))

    # Intersection
    linked_but_deviated_count: int = 0

    # Planned R:R vs realized R (None when insufficient qualifying trades)
    rr_comparison: Optional[RRComparisonReport] = None

    # Pre-computed coaching signals (plain English sentences)
    coaching_signals: List[str] = field(default_factory=list)


@dataclass
class RRTrendBucket:
    """One time bucket in an R:R realization trend series."""
    bucket: str                      # ISO week label, e.g. "2026-W15"
    bucket_start: datetime           # Monday 00:00 of the ISO week (UTC-naive)
    n: int                           # qualifying trades in this bucket
    avg_planned_rr: float
    avg_actual_r: float
    avg_shortfall: float             # avg_actual_r - avg_planned_rr; negative = fell short
    realization_pct: Optional[float] # (avg_actual_r / avg_planned_rr) * 100; None if planned=0


@dataclass
class RRTrendReport:
    """Time-series R:R realization analysis for an account."""
    buckets: List[RRTrendBucket] = field(default_factory=list)
    total_qualifying: int = 0
    # "improving" | "worsening" | "stable" | None (None when < 4 buckets with data)
    trend_signal: Optional[str] = None


@dataclass
class BehavioralTrendBucket:
    """One ISO week in the behavioral discipline trend series."""
    bucket: str                          # "2026-W15"
    bucket_start: datetime               # Monday 00:00 of that ISO week (UTC-naive)
    n: int                               # total trades with exit_datetime in this bucket
    win_rate: Optional[float]            # wins / n (0.0–1.0); None if n=0
    mistake_rate: Optional[float]        # trades_with_any_mistake / n (0.0–1.0); None if n=0
    plan_link_rate: Optional[float]      # trades_with_trade_plan_id / n (0.0–1.0); None if n=0
    followed_plan_rate: Optional[float]  # followed_plan=True / (fp is not None); None if tagged < 3


@dataclass
class BehavioralTrendReport:
    """Weekly behavioral discipline trend for an account."""
    buckets: List[BehavioralTrendBucket] = field(default_factory=list)
    total_trades: int = 0
    # Per-metric trend: "improving" | "worsening" | "stable" | None (needs >= 4 non-empty buckets)
    win_rate_trend: Optional[str] = None
    mistake_rate_trend: Optional[str] = None
    plan_link_rate_trend: Optional[str] = None
    followed_plan_rate_trend: Optional[str] = None


@dataclass
class ExitBucket:
    """Statistics for one exit outcome category."""
    count: int
    total_pnl: float
    avg_r: Optional[float]          # None if no actual_r_multiple data in bucket
    pct_of_total: Optional[float]   # count / total_classified * 100; None if total=0


@dataclass
class ExitDecompositionReport:
    """
    Exit outcome decomposition.

    Classification uses actual_r_multiple as the primary signal; take_profit /
    planned_take_profit / inferred TP (from planned_rr + SL) as secondary for WIN trades.

    Thresholds (conservative):
      stop_hit:           actual_r ≤ -0.85 (within 15% of full stop distance)
      manual_cut:         LOSS AND actual_r > -0.65 (cut before 65% of stop)
      target_hit:         WIN AND has TP info AND reached ≥90% of TP distance
      exit_before_target: WIN AND has TP info AND reached <90% of TP distance
      unclear:            everything else with actual_r_multiple set

    total_unclassified counts trades where actual_r_multiple is None.
    pct_of_total on each bucket is relative to total_classified.
    """
    total_classified: int
    total_unclassified: int
    stop_hit: ExitBucket
    manual_cut: ExitBucket
    target_hit: ExitBucket
    exit_before_target: ExitBucket
    unclear: ExitBucket
    coaching_signals: List[str] = field(default_factory=list)


@dataclass
class EntryExitQualityReport:
    """
    Entry-quality vs exit-quality diagnostic summary.

    IMPORTANT LIMITATIONS:
    - Exit-quality signals (early_exit_pct) are directly observable from price levels.
    - Entry-quality signals rely on self-reported flags which may be sparsely populated.
    - Without MAE/MFE data, entry quality inference is conservative — a stop hit does
      NOT by itself indicate a bad entry.
    - primary_diagnosis and confidence reflect the weight of available evidence only.
    """
    total_trades: int
    classified_trades: int                   # trades with actual_r_multiple set

    # Exit-quality signals (directly observable from price levels)
    wins_total: int
    wins_with_tp_info: int                   # wins where target classification was possible
    wins_hit_target: int                     # target_hit bucket
    wins_before_target: int                  # exit_before_target bucket
    early_exit_pct: Optional[float]          # wins_before_target / wins_with_tp_info * 100; None if <3 qualifying

    # Loss-side context
    losses_total: int
    stop_hit_count: int                      # full stop losses (actual_r <= -0.85)
    manual_cut_count: int                    # managed losses cut before stop
    stop_hit_pct_of_losses: Optional[float]  # stop_hit_count / losses_total * 100

    # Entry-quality signals (self-reported — check flag_coverage_pct for data quality)
    entry_flagged_losses: int                # losses with ≥1 entry flag
    entry_flagged_stop_hits: int             # stop-hit losses with ≥1 entry flag
    entry_flagged_stop_hit_pct: Optional[float]  # of stop hits; None if stop_hits < 3
    flag_coverage_pct: float                 # % of classified trades with any journal flag

    # Specific flag counts (across all trades)
    flag_early_entry: int
    flag_chasing: int
    flag_fomo: int
    flag_plan_deviation_on_loss: int         # followed_plan=False AND result=LOSS
    flag_weak_setup_on_loss: int             # is_a_plus_setup=False AND result=LOSS
    flag_problem_analysis: int               # problem_source='analysis'
    flag_premature_exit: int                 # premature_exit=True
    flag_moved_stop: int                     # moved_stop=True

    # Primary diagnosis (conservative — reflects available evidence, not certainty)
    primary_diagnosis: str                   # "exit_discipline" | "entry_quality" | "mixed" | "unclear"
    confidence: str                          # "low" | "moderate" | "high"

    coaching_signals: List[str] = field(default_factory=list)


@dataclass
class SetupViolation:
    """One trade that violated a setup rule."""
    trade_id: str
    setup_type: Optional[str]


@dataclass
class DailyAdherenceReport:
    """
    Adherence of actual trades against pre-market DailyPlan rules for one trading day.

    Computed from closed trades whose exit_datetime falls on trading_date.

    Notes:
      - planned_count uses trade_plan_id presence as proxy for 'pre-planned via TradePlan'.
      - Setup checks require trade.setup_type to be set; untagged trades are counted in
        untagged_count and excluded from setup violation counts.
      - daily_max_risk_pct is NOT checked — per-trade risk % requires instrument-specific
        pip values not available in current Trade fields.
    """
    trading_date:               date
    trades_taken:               int

    # Planned vs unplanned (by TradePlan linkage)
    planned_count:              int             # trades with trade_plan_id set
    unplanned_count:            int             # trades without trade_plan_id

    # Max trades rule
    max_trades_limit:           Optional[int]   # None if not configured in plan
    max_trades_exceeded:        bool
    max_trades_exceeded_by:     int             # trades_taken - max_trades_limit; 0 if not exceeded

    # Allowed setup check (only meaningful when allowed_setups non-empty in plan)
    allowed_setups_configured:  bool
    outside_allowed_count:      int             # trades whose setup_type not in allowed list
    outside_allowed_setups:     List[str]       # distinct setup_type values that violated

    # Disallowed setup check
    disallowed_setups_configured: bool
    disallowed_violation_count: int
    disallowed_violations:      List[SetupViolation]   # [{trade_id, setup_type}]

    # Untagged trades — setup_type is None, cannot be checked
    untagged_count:             int

    # Plain-English discipline signals
    discipline_signals:         List[str] = field(default_factory=list)


@dataclass
class AccountReport:
    # ── Identity ───────────────────────────────────────────────────────────
    account_id:          str
    generated_at:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Account State ─────────────────────────────────────────────────────
    starting_balance:    Optional[float]   = None
    current_balance:     Optional[float]   = None   # starting_balance + total_net_profit

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
