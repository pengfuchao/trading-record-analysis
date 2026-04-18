"""add mt5_open_positions table

Revision ID: 009
Revises: 008
Create Date: 2026-04-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mt5_open_positions",
        sa.Column("account_id",    sa.String(100), nullable=False),
        sa.Column("ticket",        sa.Integer(),   nullable=False),
        sa.Column("symbol",        sa.String(20),  nullable=False),
        sa.Column("direction",     sa.String(10),  nullable=False),
        sa.Column("lot_size",      sa.Float(),     nullable=False),
        sa.Column("entry_price",   sa.Float(),     nullable=False),
        sa.Column("current_price", sa.Float(),     nullable=True),
        sa.Column("stop_loss",     sa.Float(),     nullable=True),
        sa.Column("take_profit",   sa.Float(),     nullable=True),
        sa.Column("floating_pnl",  sa.Float(),     nullable=True),
        sa.Column("opened_at",     sa.DateTime(),  nullable=True),
        sa.Column("magic",         sa.Integer(),   nullable=True),
        sa.Column("comment",       sa.String(255), nullable=True),
        sa.Column("source",        sa.String(20),  nullable=False, server_default="mt5"),
        sa.Column("synced_at",     sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("account_id", "ticket"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_mt5_open_positions_account",
        "mt5_open_positions",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mt5_open_positions_account", "mt5_open_positions")
    op.drop_table("mt5_open_positions")
