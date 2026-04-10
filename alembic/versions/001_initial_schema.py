"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── accounts ─────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("account_id",       sa.String(100), primary_key=True, nullable=False),
        sa.Column("broker",            sa.String(100), nullable=False),
        sa.Column("platform",          sa.String(10),  nullable=False),
        sa.Column("prop_firm",         sa.String(100), nullable=True),
        sa.Column("challenge_phase",   sa.String(20),  nullable=True),
        sa.Column("starting_balance",  sa.Float(),     nullable=True),
        sa.Column("account_currency",  sa.String(10),  nullable=False, server_default="USD"),
        sa.Column("created_at",        sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )

    # ── trades ────────────────────────────────────────────────────────────────
    op.create_table(
        "trades",
        # Identifiers
        sa.Column("trade_id",          sa.String(100), primary_key=True, nullable=False),
        sa.Column("account_id",        sa.String(100), nullable=False),

        # Basic trade info
        sa.Column("symbol",            sa.String(20),  nullable=True),
        sa.Column("asset_class",       sa.String(20),  nullable=True),
        sa.Column("direction",         sa.String(10),  nullable=True),
        sa.Column("platform",          sa.String(10),  nullable=True),
        sa.Column("raw_trade_type",    sa.String(10),  nullable=True),

        # Timing
        sa.Column("entry_datetime",    sa.DateTime(),  nullable=True),
        sa.Column("exit_datetime",     sa.DateTime(),  nullable=True),
        sa.Column("holding_duration",  sa.Interval(),  nullable=True),

        # Pricing & sizing
        sa.Column("entry_price",       sa.Float(),     nullable=True),
        sa.Column("exit_price",        sa.Float(),     nullable=True),
        sa.Column("stop_loss",         sa.Float(),     nullable=True),
        sa.Column("take_profit",       sa.Float(),     nullable=True),
        sa.Column("lot_size",          sa.Float(),     nullable=True),

        # PnL
        sa.Column("gross_pnl",         sa.Float(),     nullable=True),
        sa.Column("commission",        sa.Float(),     nullable=True),
        sa.Column("swap",              sa.Float(),     nullable=True),
        sa.Column("net_pnl",           sa.Float(),     nullable=True),
        sa.Column("actual_r_multiple", sa.Float(),     nullable=True),

        # Result
        sa.Column("result",            sa.String(15),  nullable=True),

        # Platform metadata
        sa.Column("magic",             sa.Integer(),   nullable=True),
        sa.Column("comment",           sa.String(255), nullable=True),

        # Manual enrichment: strategy / context
        sa.Column("setup_type",        sa.String(100), nullable=True),
        sa.Column("strategy",          sa.String(100), nullable=True),
        sa.Column("session",           sa.String(30),  nullable=True),
        sa.Column("higher_tf_bias",    sa.String(20),  nullable=True),
        sa.Column("entry_timeframe",   sa.String(20),  nullable=True),
        sa.Column("market_condition",  sa.String(50),  nullable=True),
        sa.Column("key_levels",        sa.Text(),      nullable=True),
        sa.Column("news_context",      sa.Text(),      nullable=True),
        sa.Column("pre_trade_bias",    sa.Text(),      nullable=True),

        # Trade rationale
        sa.Column("entry_reason",         sa.Text(), nullable=True),
        sa.Column("trigger_confirmation", sa.Text(), nullable=True),
        sa.Column("stop_loss_logic",      sa.Text(), nullable=True),
        sa.Column("take_profit_logic",    sa.Text(), nullable=True),
        sa.Column("exit_reason",          sa.Text(), nullable=True),

        # Execution quality flags
        sa.Column("followed_plan",        sa.Boolean(), nullable=True),
        sa.Column("is_a_plus_setup",      sa.Boolean(), nullable=True),
        sa.Column("early_entry",          sa.Boolean(), nullable=True),
        sa.Column("chasing",              sa.Boolean(), nullable=True),
        sa.Column("fomo",                 sa.Boolean(), nullable=True),
        sa.Column("emotional_trade",      sa.Boolean(), nullable=True),
        sa.Column("revenge_trade",        sa.Boolean(), nullable=True),
        sa.Column("overtrading",          sa.Boolean(), nullable=True),
        sa.Column("hesitation",           sa.Boolean(), nullable=True),
        sa.Column("moved_stop",           sa.Boolean(), nullable=True),
        sa.Column("premature_exit",       sa.Boolean(), nullable=True),
        sa.Column("held_loser_too_long",  sa.Boolean(), nullable=True),

        # Review / reflection
        sa.Column("trade_quality",    sa.String(50),  nullable=True),
        sa.Column("problem_source",   sa.String(50),  nullable=True),
        sa.Column("mistake_tags",     sa.JSON(),                     nullable=True),
        sa.Column("lesson_learned",   sa.Text(),      nullable=True),
        sa.Column("repeat_next_time", sa.Text(),      nullable=True),
        sa.Column("avoid_next_time",  sa.Text(),      nullable=True),

        # Attachments
        sa.Column("screenshot_before", sa.String(500), nullable=True),
        sa.Column("screenshot_during", sa.String(500), nullable=True),
        sa.Column("screenshot_after",  sa.String(500), nullable=True),
        sa.Column("notes",             sa.Text(),      nullable=True),

        # Audit / import tracking
        sa.Column("import_run_id", sa.String(100), nullable=True),
        sa.Column("created_at",    sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",    sa.DateTime(),  nullable=False, server_default=sa.func.now()),

        # Foreign key
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.account_id"],
            name="fk_trades_account_id",
            ondelete="CASCADE",
        ),
    )

    # Single-column indexes
    op.create_index("ix_trades_account_id",     "trades", ["account_id"])
    op.create_index("ix_trades_symbol",         "trades", ["symbol"])
    op.create_index("ix_trades_entry_datetime", "trades", ["entry_datetime"])
    op.create_index("ix_trades_exit_datetime",  "trades", ["exit_datetime"])
    op.create_index("ix_trades_result",         "trades", ["result"])
    op.create_index("ix_trades_import_run_id",  "trades", ["import_run_id"])

    # Composite indexes for common query patterns
    op.create_index("ix_trades_account_exit",   "trades", ["account_id", "exit_datetime"])
    op.create_index("ix_trades_account_result", "trades", ["account_id", "result"])
    op.create_index("ix_trades_account_symbol", "trades", ["account_id", "symbol"])


def downgrade() -> None:
    op.drop_table("trades")
    op.drop_table("accounts")
