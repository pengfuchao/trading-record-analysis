"""add coaching_reviews table

Revision ID: 004
Revises: 003
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaching_reviews",
        sa.Column("review_id",     sa.String(100), primary_key=True, nullable=False),
        sa.Column("account_id",    sa.String(100),
                  sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_date",     sa.Date(),       nullable=True),
        sa.Column("to_date",       sa.Date(),       nullable=True),
        sa.Column("generated_at",  sa.DateTime(),   nullable=False),
        sa.Column("model_used",    sa.String(100),  nullable=False),
        sa.Column("source",        sa.String(20),   nullable=False),   # ai | fallback
        sa.Column("status",        sa.String(20),   nullable=False),   # success | fallback | error
        sa.Column("output_json",   sa.Text(),       nullable=True),
        sa.Column("raw_response",  sa.Text(),       nullable=True),
        sa.Column("error_message", sa.Text(),       nullable=True),
    )
    op.create_index("ix_coaching_reviews_account", "coaching_reviews", ["account_id"])
    op.create_index(
        "ix_coaching_reviews_account_generated",
        "coaching_reviews",
        ["account_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_table("coaching_reviews")
