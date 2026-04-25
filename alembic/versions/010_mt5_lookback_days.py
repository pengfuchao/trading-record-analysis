"""add lookback_days to mt5_sync_configs

Revision ID: 010
Revises: 009
Create Date: 2026-04-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mt5_sync_configs",
        sa.Column(
            "lookback_days",
            sa.Integer(),
            nullable=False,
            server_default="7",
        ),
    )


def downgrade() -> None:
    op.drop_column("mt5_sync_configs", "lookback_days")
