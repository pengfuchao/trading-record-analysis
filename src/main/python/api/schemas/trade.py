from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from src.main.python.models.enums import AssetClass, Direction, Platform, TradeResult
from src.main.python.models.trade import Trade


class TradeCreate(BaseModel):
    trade_id: str

    # Basic trade info
    symbol: Optional[str] = None
    asset_class: Optional[AssetClass] = None
    direction: Optional[Direction] = None
    platform: Optional[Platform] = None
    raw_trade_type: Optional[str] = None

    # Timing
    entry_datetime: Optional[datetime] = None
    exit_datetime: Optional[datetime] = None
    holding_duration_seconds: Optional[float] = None  # timedelta as seconds

    # Pricing & sizing
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    lot_size: Optional[float] = None

    # PnL
    gross_pnl: Optional[float] = None
    commission: Optional[float] = None
    swap: Optional[float] = None
    net_pnl: Optional[float] = None
    actual_r_multiple: Optional[float] = None
    result: Optional[TradeResult] = None

    # Platform metadata
    magic: Optional[int] = None
    comment: Optional[str] = None

    # Enrichment: strategy / context
    setup_type: Optional[str] = None
    strategy: Optional[str] = None
    session: Optional[str] = None
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
    trade_quality: Optional[str] = None
    problem_source: Optional[str] = None
    mistake_tags: List[str] = []
    lesson_learned: Optional[str] = None
    repeat_next_time: Optional[str] = None
    avoid_next_time: Optional[str] = None

    # Attachments
    screenshot_before: Optional[str] = None
    screenshot_during: Optional[str] = None
    screenshot_after: Optional[str] = None
    notes: Optional[str] = None


class TradeUpdate(BaseModel):
    """Only enrichment + correctable fields. Core execution data is immutable after import."""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trade_plan_id: Optional[str] = None   # set to "" to unlink

    setup_type: Optional[str] = None
    strategy: Optional[str] = None
    session: Optional[str] = None
    higher_tf_bias: Optional[str] = None
    entry_timeframe: Optional[str] = None
    market_condition: Optional[str] = None
    key_levels: Optional[str] = None
    news_context: Optional[str] = None
    pre_trade_bias: Optional[str] = None
    entry_reason: Optional[str] = None
    trigger_confirmation: Optional[str] = None
    stop_loss_logic: Optional[str] = None
    take_profit_logic: Optional[str] = None
    exit_reason: Optional[str] = None
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
    trade_quality: Optional[str] = None
    problem_source: Optional[str] = None
    # None = don't touch; [] = clear all tags
    mistake_tags: Optional[List[str]] = None
    lesson_learned: Optional[str] = None
    repeat_next_time: Optional[str] = None
    avoid_next_time: Optional[str] = None
    screenshot_before: Optional[str] = None
    screenshot_during: Optional[str] = None
    screenshot_after: Optional[str] = None
    notes: Optional[str] = None


class TradeResponse(BaseModel):
    trade_id: str
    account_id: str
    symbol: Optional[str]
    asset_class: Optional[AssetClass]
    direction: Optional[Direction]
    platform: Optional[Platform]
    raw_trade_type: Optional[str]
    entry_datetime: Optional[datetime]
    exit_datetime: Optional[datetime]
    holding_duration_seconds: Optional[float]
    entry_price: Optional[float]
    exit_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    lot_size: Optional[float]
    gross_pnl: Optional[float]
    commission: Optional[float]
    swap: Optional[float]
    net_pnl: Optional[float]
    actual_r_multiple: Optional[float]
    result: Optional[TradeResult]
    magic: Optional[int]
    comment: Optional[str]
    setup_type: Optional[str]
    strategy: Optional[str]
    session: Optional[str]
    higher_tf_bias: Optional[str]
    entry_timeframe: Optional[str]
    market_condition: Optional[str]
    key_levels: Optional[str]
    news_context: Optional[str]
    pre_trade_bias: Optional[str]
    entry_reason: Optional[str]
    trigger_confirmation: Optional[str]
    stop_loss_logic: Optional[str]
    take_profit_logic: Optional[str]
    exit_reason: Optional[str]
    followed_plan: Optional[bool]
    is_a_plus_setup: Optional[bool]
    early_entry: Optional[bool]
    chasing: Optional[bool]
    fomo: Optional[bool]
    emotional_trade: Optional[bool]
    revenge_trade: Optional[bool]
    overtrading: Optional[bool]
    hesitation: Optional[bool]
    moved_stop: Optional[bool]
    premature_exit: Optional[bool]
    held_loser_too_long: Optional[bool]
    trade_quality: Optional[str]
    problem_source: Optional[str]
    mistake_tags: List[str]
    lesson_learned: Optional[str]
    repeat_next_time: Optional[str]
    avoid_next_time: Optional[str]
    screenshot_before: Optional[str]
    screenshot_during: Optional[str]
    screenshot_after: Optional[str]
    notes: Optional[str]
    trade_plan_id: Optional[str]

    @classmethod
    def from_domain(cls, trade: Trade) -> TradeResponse:
        return cls(
            trade_id=trade.trade_id,
            account_id=trade.account_id,
            symbol=trade.symbol,
            asset_class=trade.asset_class,
            direction=trade.direction,
            platform=trade.platform,
            raw_trade_type=trade.raw_trade_type,
            entry_datetime=trade.entry_datetime,
            exit_datetime=trade.exit_datetime,
            holding_duration_seconds=(
                trade.holding_duration.total_seconds()
                if trade.holding_duration is not None else None
            ),
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            lot_size=trade.lot_size,
            gross_pnl=trade.gross_pnl,
            commission=trade.commission,
            swap=trade.swap,
            net_pnl=trade.net_pnl,
            actual_r_multiple=trade.actual_r_multiple,
            result=trade.result,
            magic=trade.magic,
            comment=trade.comment,
            setup_type=trade.setup_type,
            strategy=trade.strategy,
            session=trade.session,
            higher_tf_bias=trade.higher_tf_bias,
            entry_timeframe=trade.entry_timeframe,
            market_condition=trade.market_condition,
            key_levels=trade.key_levels,
            news_context=trade.news_context,
            pre_trade_bias=trade.pre_trade_bias,
            entry_reason=trade.entry_reason,
            trigger_confirmation=trade.trigger_confirmation,
            stop_loss_logic=trade.stop_loss_logic,
            take_profit_logic=trade.take_profit_logic,
            exit_reason=trade.exit_reason,
            followed_plan=trade.followed_plan,
            is_a_plus_setup=trade.is_a_plus_setup,
            early_entry=trade.early_entry,
            chasing=trade.chasing,
            fomo=trade.fomo,
            emotional_trade=trade.emotional_trade,
            revenge_trade=trade.revenge_trade,
            overtrading=trade.overtrading,
            hesitation=trade.hesitation,
            moved_stop=trade.moved_stop,
            premature_exit=trade.premature_exit,
            held_loser_too_long=trade.held_loser_too_long,
            trade_quality=trade.trade_quality,
            problem_source=trade.problem_source,
            mistake_tags=trade.mistake_tags,
            lesson_learned=trade.lesson_learned,
            repeat_next_time=trade.repeat_next_time,
            avoid_next_time=trade.avoid_next_time,
            screenshot_before=trade.screenshot_before,
            screenshot_during=trade.screenshot_during,
            screenshot_after=trade.screenshot_after,
            notes=trade.notes,
            trade_plan_id=trade.trade_plan_id,
        )
