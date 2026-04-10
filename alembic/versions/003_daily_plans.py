"""add daily_plans and daily_reviews tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_plans",
        sa.Column("plan_id",            sa.String(100), primary_key=True, nullable=False),
        sa.Column("account_id",         sa.String(100), sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("trading_date",       sa.Date(),      nullable=False),
        sa.Column("market_bias",        sa.String(50),  nullable=True),
        sa.Column("symbols_in_focus",   sa.JSON(),      nullable=True),
        sa.Column("key_levels",         sa.Text(),      nullable=True),
        sa.Column("major_news",         sa.Text(),      nullable=True),
        sa.Column("allowed_setups",     sa.JSON(),      nullable=True),
        sa.Column("disallowed_setups",  sa.JSON(),      nullable=True),
        sa.Column("daily_max_risk_pct", sa.Float(),     nullable=True),
        sa.Column("max_trades",         sa.Integer(),   nullable=True),
        sa.Column("behavioral_focus",   sa.Text(),      nullable=True),
        sa.Column("special_rule",       sa.Text(),      nullable=True),
        sa.Column("created_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_daily_plans_account_date", "daily_plans", ["account_id", "trading_date"], unique=True)

    op.create_table(
        "daily_reviews",
        sa.Column("review_id",          sa.String(100), primary_key=True, nullable=False),
        sa.Column("account_id",         sa.String(100), sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("trading_date",       sa.Date(),      nullable=False),
        sa.Column("plan_id",            sa.String(100), sa.ForeignKey("daily_plans.plan_id", ondelete="SET NULL"), nullable=True),
        sa.Column("total_trades",       sa.Integer(),   nullable=True),
        sa.Column("total_pnl",          sa.Float(),     nullable=True),
        sa.Column("total_r",            sa.Float(),     nullable=True),
        sa.Column("planned_trades",     sa.Integer(),   nullable=True),
        sa.Column("unplanned_trades",   sa.Integer(),   nullable=True),
        sa.Column("best_trade_id",      sa.String(100), nullable=True),
        sa.Column("worst_trade_id",     sa.String(100), nullable=True),
        sa.Column("biggest_mistake",    sa.Text(),      nullable=True),
        sa.Column("emotional_summary",  sa.Text(),      nullable=True),
        sa.Column("improvement_point",  sa.Text(),      nullable=True),
        sa.Column("notes",              sa.Text(),      nullable=True),
        sa.Column("process_success",    sa.Boolean(),   nullable=True),
        sa.Column("pnl_success",        sa.Boolean(),   nullable=True),
        sa.Column("created_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_daily_reviews_account_date", "daily_reviews", ["account_id", "trading_date"], unique=True)


def downgrade() -> None:
    op.drop_table("daily_reviews")
    op.drop_table("daily_plans")
