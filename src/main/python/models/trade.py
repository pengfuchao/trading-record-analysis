from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from src.main.python.models.enums import AssetClass, Direction, Platform, TradeResult


@dataclass
class Trade:
    # --- Identifiers ---
    trade_id: str
    account_id: str

    # --- Basic trade info ---
    symbol: Optional[str] = None
    asset_class: Optional[AssetClass] = None
    direction: Optional[Direction] = None
    platform: Optional[Platform] = None
    raw_trade_type: Optional[str] = None  # original "buy"/"sell" string

    # --- Timing ---
    entry_datetime: Optional[datetime] = None
    exit_datetime: Optional[datetime] = None
    holding_duration: Optional[timedelta] = None

    # --- Pricing & sizing ---
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    lot_size: Optional[float] = None

    # --- PnL ---
    gross_pnl: Optional[float] = None
    commission: Optional[float] = None
    swap: Optional[float] = None
    net_pnl: Optional[float] = None

    # --- Risk metrics ---
    # NOTE: actual_r_multiple uses a simplified formula (gross_pnl / SL distance).
    # True R requires pip/contract values which are broker-specific and not in CSV exports.
    actual_r_multiple: Optional[float] = None
    result: Optional[TradeResult] = None

    # --- Platform metadata ---
    magic: Optional[int] = None
    comment: Optional[str] = None

    # -------------------------------------------------------------------------
    # Manual enrichment fields (filled in by the trader after import)
    # -------------------------------------------------------------------------

    # Strategy / context
    setup_type: Optional[str] = None
    strategy: Optional[str] = None
    session: Optional[str] = None          # Asia / London / New York
    higher_tf_bias: Optional[str] = None
    entry_timeframe: Optional[str] = None
    market_condition: Optional[str] = None
    key_levels: Optional[str] = None
    news_context: Optional[str] = None
    pre_trade_bias: Optional[str] = None

    # Trade rationale
    entry_reason: Optional[str] = None
    trigger_confirmation: Optional[str] = None
    stop_loss_logic: Optional[str] = None
    take_profit_logic: Optional[str] = None
    exit_reason: Optional[str] = None

    # Execution quality flags
    followed_plan: Optional[bool] = None
    is_a_plus_setup: Optional[bool] = None
    early_entry: Optional[bool] = None
    chasing: Optional[bool] = None
    fomo: Optional[bool] = None
    emotional_trade: Optional[bool] = None
    revenge_trade: Optional[bool] = None
    overtrading: Optional[bool] = None
    hesitation: Optional[bool] = None
    moved_stop: Optional[bool] = None
    premature_exit: Optional[bool] = None
    held_loser_too_long: Optional[bool] = None

    # Review / reflection
    trade_quality: Optional[str] = None    # "good trade" / "bad trade"
    problem_source: Optional[str] = None   # analysis / execution / psychology / risk
    mistake_tags: List[str] = field(default_factory=list)
    lesson_learned: Optional[str] = None
    repeat_next_time: Optional[str] = None
    avoid_next_time: Optional[str] = None

    # Attachments (file paths or URLs)
    screenshot_before: Optional[str] = None
    screenshot_during: Optional[str] = None
    screenshot_after: Optional[str] = None
    notes: Optional[str] = None

    # Plan linking
    trade_plan_id: Optional[str] = None
