"""fix mt5 sync table server_defaults for SQLite compatibility

Revision ID: 007
Revises: 006
Create Date: 2026-04-16

Migration 006 used sa.text("NOW()") for server_default on mt5_sync_configs
created_at / updated_at. NOW() is PostgreSQL syntax; SQLite requires
CURRENT_TIMESTAMP. This migration recreates the affected columns using the
correct cross-database default.

Python-side defaults (default=datetime.utcnow) were added to the ORM models
as the primary fix, so this migration only matters for tools that inspect the
raw DDL. The app works correctly on both SQLite and PostgreSQL after the ORM
fix regardless of which server_default string is stored in the catalog.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQLite does not support ALTER COLUMN; the batch_alter_table context manager
# rewrites the table transparently for SQLite while emitting standard ALTER
# for other dialects (PostgreSQL, MySQL).

def upgrade() -> None:
    with op.batch_alter_table("mt5_sync_configs") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )


def downgrade() -> None:
    with op.batch_alter_table("mt5_sync_configs") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.text("NOW()"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.text("NOW()"),
        )
