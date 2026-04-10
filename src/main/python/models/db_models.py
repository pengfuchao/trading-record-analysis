from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index,
    Integer, Interval, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.main.python.utils.types import StringList


class Base(DeclarativeBase):
    pass


class AccountModel(Base):
    __tablename__ = "accounts"

    account_id:       Mapped[str]            = mapped_column(String(100), primary_key=True)
    broker:           Mapped[str]            = mapped_column(String(100), nullable=False)
    platform:         Mapped[str]            = mapped_column(String(10),  nullable=False)
    prop_firm:        Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    challenge_phase:  Mapped[Optional[str]]  = mapped_column(String(20),  nullable=True)
    starting_balance: Mapped[Optional[float]]= mapped_column(Float,       nullable=True)
    account_currency: Mapped[str]            = mapped_column(String(10),  nullable=False, default="USD")
    created_at:       Mapped[datetime]       = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    trades: Mapped[List["TradeModel"]] = relationship(
        "TradeModel", back_populates="account", cascade="all, delete-orphan"
    )


class TradeModel(Base):
    __tablename__ = "trades"

    # ── Identifiers ──────────────────────────────────────────────────────────
    trade_id:   Mapped[str] = mapped_column(String(100), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Basic trade info ─────────────────────────────────────────────────────
    symbol:         Mapped[Optional[str]] = mapped_column(String(20),  nullable=True, index=True)
    asset_class:    Mapped[Optional[str]] = mapped_column(String(20),  nullable=True)
    direction:      Mapped[Optional[str]] = mapped_column(String(10),  nullable=True)
    platform:       Mapped[Optional[str]] = mapped_column(String(10),  nullable=True)
    raw_trade_type: Mapped[Optional[str]] = mapped_column(String(10),  nullable=True)

    # ── Timing ───────────────────────────────────────────────────────────────
    entry_datetime:   Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    exit_datetime:    Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    holding_duration: Mapped[Optional[timedelta]] = mapped_column(Interval, nullable=True)

    # ── Pricing & sizing ─────────────────────────────────────────────────────
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_price:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss:   Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lot_size:    Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── PnL ─────────────────────────────────────────────────────────────────
    gross_pnl:         Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission:        Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    swap:              Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_pnl:           Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_r_multiple: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Result ───────────────────────────────────────────────────────────────
    result: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, index=True)

    # ── Platform metadata ────────────────────────────────────────────────────
    magic:   Mapped[Optional[int]] = mapped_column(Integer,     nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Manual enrichment: strategy / context ────────────────────────────────
    setup_type:       Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    strategy:         Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    session:          Mapped[Optional[str]] = mapped_column(String(30),  nullable=True)
    higher_tf_bias:   Mapped[Optional[str]] = mapped_column(String(20),  nullable=True)
    entry_timeframe:  Mapped[Optional[str]] = mapped_column(String(20),  nullable=True)
    market_condition: Mapped[Optional[str]] = mapped_column(String(50),  nullable=True)
    key_levels:       Mapped[Optional[str]] = mapped_column(Text,         nullable=True)
    news_context:     Mapped[Optional[str]] = mapped_column(Text,         nullable=True)
    pre_trade_bias:   Mapped[Optional[str]] = mapped_column(Text,         nullable=True)

    # ── Trade rationale ──────────────────────────────────────────────────────
    entry_reason:         Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_confirmation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stop_loss_logic:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    take_profit_logic:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_reason:          Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Execution quality flags ───────────────────────────────────────────────
    followed_plan:       Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    is_a_plus_setup:     Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    early_entry:         Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    chasing:             Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    fomo:                Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    emotional_trade:     Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    revenge_trade:       Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    overtrading:         Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    hesitation:          Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    moved_stop:          Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    premature_exit:      Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    held_loser_too_long: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ── Review / reflection ──────────────────────────────────────────────────
    trade_quality:    Mapped[Optional[str]]        = mapped_column(String(50), nullable=True)
    problem_source:   Mapped[Optional[str]]        = mapped_column(String(50), nullable=True)
    mistake_tags:     Mapped[Optional[List[str]]]  = mapped_column(StringList(), nullable=True)
    lesson_learned:   Mapped[Optional[str]]        = mapped_column(Text, nullable=True)
    repeat_next_time: Mapped[Optional[str]]        = mapped_column(Text, nullable=True)
    avoid_next_time:  Mapped[Optional[str]]        = mapped_column(Text, nullable=True)

    # ── Attachments ──────────────────────────────────────────────────────────
    screenshot_before: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    screenshot_during: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    screenshot_after:  Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes:             Mapped[Optional[str]] = mapped_column(Text,         nullable=True)

    # ── Audit / import tracking ───────────────────────────────────────────────
    import_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    created_at:    Mapped[datetime]      = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at:    Mapped[datetime]      = mapped_column(
        DateTime(timezone=False), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    account: Mapped["AccountModel"] = relationship("AccountModel", back_populates="trades")

    __table_args__ = (
        Index("ix_trades_account_exit",   "account_id", "exit_datetime"),
        Index("ix_trades_account_result", "account_id", "result"),
        Index("ix_trades_account_symbol", "account_id", "symbol"),
    )


class SetupDefinitionModel(Base):
    __tablename__ = "setup_definitions"

    setup_id:               Mapped[str]            = mapped_column(String(100), primary_key=True)
    name:                   Mapped[str]            = mapped_column(String(200), nullable=False)
    strategy_group:         Mapped[Optional[str]]  = mapped_column(String(100), nullable=True, index=True)
    description:            Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    market_environment:     Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    preconditions:          Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    entry_criteria:         Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    confirmation_rules:     Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    stop_loss_rules:        Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    take_profit_rules:      Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    invalidation_conditions:Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    common_mistakes:        Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    screenshot_examples:    Mapped[Optional[List[str]]] = mapped_column(StringList(), nullable=True)
    notes:                  Mapped[Optional[str]]  = mapped_column(Text,         nullable=True)
    created_at:             Mapped[datetime]       = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at:             Mapped[datetime]       = mapped_column(
        DateTime(timezone=False), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
