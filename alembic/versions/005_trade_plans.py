"""add trade_plans table and link column on trades

Revision ID: 005
Revises: 004
Create Date: 2026-04-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create trade_plans table first (trades FK references it)
    op.create_table(
        "trade_plans",
        sa.Column("plan_id",             sa.String(100), primary_key=True, nullable=False),
        sa.Column("account_id",          sa.String(100),
                  sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status",              sa.String(20),  nullable=False, server_default="planned"),
        sa.Column("symbol",              sa.String(20),  nullable=True),
        sa.Column("intended_direction",  sa.String(10),  nullable=True),
        sa.Column("setup_type",          sa.String(100), nullable=True),
        sa.Column("strategy",            sa.String(100), nullable=True),
        sa.Column("bias",                sa.String(50),  nullable=True),
        sa.Column("thesis",              sa.Text(),      nullable=True),
        sa.Column("entry_logic",         sa.Text(),      nullable=True),
        sa.Column("stop_loss_logic",     sa.Text(),      nullable=True),
        sa.Column("take_profit_logic",   sa.Text(),      nullable=True),
        sa.Column("invalidation_logic",  sa.Text(),      nullable=True),
        sa.Column("planned_entry_zone",  sa.String(100), nullable=True),
        sa.Column("planned_stop_loss",   sa.Float(),     nullable=True),
        sa.Column("planned_take_profit", sa.Float(),     nullable=True),
        sa.Column("planned_rr",          sa.Float(),     nullable=True),
        sa.Column("is_a_plus_setup",     sa.Boolean(),   nullable=True),
        sa.Column("notes",               sa.Text(),      nullable=True),
        sa.Column("created_at",          sa.DateTime(),  nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at",          sa.DateTime(),  nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_trade_plans_account",        "trade_plans", ["account_id"])
    op.create_index("ix_trade_plans_account_status", "trade_plans", ["account_id", "status"])

    # 2. Add trade_plan_id column to trades table
    # Note: SQLite does not support adding FK constraints via ALTER TABLE.
    # The column is added as a plain nullable string; referential integrity is
    # handled at the application layer. On PostgreSQL the FK is enforced by the ORM.
    op.add_column(
        "trades",
        sa.Column("trade_plan_id", sa.String(100), nullable=True),
    )
    op.create_index("ix_trades_trade_plan_id", "trades", ["trade_plan_id"])


def downgrade() -> None:
    op.drop_index("ix_trades_trade_plan_id", table_name="trades")
    op.drop_column("trades", "trade_plan_id")
    op.drop_table("trade_plans")
