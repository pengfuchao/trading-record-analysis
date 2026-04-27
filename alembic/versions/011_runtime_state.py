"""add runtime_state table for persistent alert/cooldown state

Revision ID: 011
Revises: 010
Create Date: 2026-04-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runtime_state",
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("scope", "kind"),
    )


def downgrade() -> None:
    op.drop_table("runtime_state")
