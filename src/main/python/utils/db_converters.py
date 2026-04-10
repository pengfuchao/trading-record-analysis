from __future__ import annotations

from src.main.python.models.account import Account
from src.main.python.models.db_models import AccountModel, TradeModel
from src.main.python.models.enums import (
    AssetClass, ChallengePhase, Direction, Platform, TradeResult,
)
from src.main.python.models.trade import Trade


def trade_to_orm(trade: Trade, import_run_id: str = None) -> TradeModel:
    """
    Convert a Trade dataclass to a TradeModel ORM object.
    import_run_id is optional — set it to tag which import batch produced this trade.
    Empty mistake_tags list is stored as NULL (None) in DB to distinguish "not set" from "no tags".
    """
    return TradeModel(
        trade_id=trade.trade_id,
        account_id=trade.account_id,
        symbol=trade.symbol,
        asset_class=trade.asset_class.value if trade.asset_class else None,
        direction=trade.direction.value if trade.direction else None,
        platform=trade.platform.value if trade.platform else None,
        raw_trade_type=trade.raw_trade_type,
        entry_datetime=trade.entry_datetime,
        exit_datetime=trade.exit_datetime,
        holding_duration=trade.holding_duration,
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
        result=trade.result.value if trade.result else None,
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
        # Store empty list as NULL; populated list stored as-is
        mistake_tags=trade.mistake_tags if trade.mistake_tags else None,
        lesson_learned=trade.lesson_learned,
        repeat_next_time=trade.repeat_next_time,
        avoid_next_time=trade.avoid_next_time,
        screenshot_before=trade.screenshot_before,
        screenshot_during=trade.screenshot_during,
        screenshot_after=trade.screenshot_after,
        notes=trade.notes,
        import_run_id=import_run_id,
    )


def orm_to_trade(orm: TradeModel) -> Trade:
    """
    Convert a TradeModel ORM object to a Trade dataclass.
    NULL mistake_tags → empty list [] (Trade default).
    """
    return Trade(
        trade_id=orm.trade_id,
        account_id=orm.account_id,
        symbol=orm.symbol,
        asset_class=AssetClass(orm.asset_class) if orm.asset_class else None,
        direction=Direction(orm.direction) if orm.direction else None,
        platform=Platform(orm.platform) if orm.platform else None,
        raw_trade_type=orm.raw_trade_type,
        entry_datetime=orm.entry_datetime,
        exit_datetime=orm.exit_datetime,
        holding_duration=orm.holding_duration,
        entry_price=orm.entry_price,
        exit_price=orm.exit_price,
        stop_loss=orm.stop_loss,
        take_profit=orm.take_profit,
        lot_size=orm.lot_size,
        gross_pnl=orm.gross_pnl,
        commission=orm.commission,
        swap=orm.swap,
        net_pnl=orm.net_pnl,
        actual_r_multiple=orm.actual_r_multiple,
        result=TradeResult(orm.result) if orm.result else None,
        magic=orm.magic,
        comment=orm.comment,
        setup_type=orm.setup_type,
        strategy=orm.strategy,
        session=orm.session,
        higher_tf_bias=orm.higher_tf_bias,
        entry_timeframe=orm.entry_timeframe,
        market_condition=orm.market_condition,
        key_levels=orm.key_levels,
        news_context=orm.news_context,
        pre_trade_bias=orm.pre_trade_bias,
        entry_reason=orm.entry_reason,
        trigger_confirmation=orm.trigger_confirmation,
        stop_loss_logic=orm.stop_loss_logic,
        take_profit_logic=orm.take_profit_logic,
        exit_reason=orm.exit_reason,
        followed_plan=orm.followed_plan,
        is_a_plus_setup=orm.is_a_plus_setup,
        early_entry=orm.early_entry,
        chasing=orm.chasing,
        fomo=orm.fomo,
        emotional_trade=orm.emotional_trade,
        revenge_trade=orm.revenge_trade,
        overtrading=orm.overtrading,
        hesitation=orm.hesitation,
        moved_stop=orm.moved_stop,
        premature_exit=orm.premature_exit,
        held_loser_too_long=orm.held_loser_too_long,
        trade_quality=orm.trade_quality,
        problem_source=orm.problem_source,
        # NULL in DB → empty list in dataclass (Trade field default)
        mistake_tags=list(orm.mistake_tags) if orm.mistake_tags is not None else [],
        lesson_learned=orm.lesson_learned,
        repeat_next_time=orm.repeat_next_time,
        avoid_next_time=orm.avoid_next_time,
        screenshot_before=orm.screenshot_before,
        screenshot_during=orm.screenshot_during,
        screenshot_after=orm.screenshot_after,
        notes=orm.notes,
    )


def account_to_orm(account: Account) -> AccountModel:
    return AccountModel(
        account_id=account.account_id,
        broker=account.broker,
        platform=account.platform.value,
        prop_firm=account.prop_firm,
        challenge_phase=account.challenge_phase.value if account.challenge_phase else None,
        starting_balance=account.starting_balance,
        account_currency=account.account_currency,
        created_at=account.created_at,
    )


def orm_to_account(orm: AccountModel) -> Account:
    return Account(
        account_id=orm.account_id,
        broker=orm.broker,
        platform=Platform(orm.platform),
        prop_firm=orm.prop_firm,
        challenge_phase=ChallengePhase(orm.challenge_phase) if orm.challenge_phase else None,
        starting_balance=orm.starting_balance,
        account_currency=orm.account_currency,
        created_at=orm.created_at,
    )
