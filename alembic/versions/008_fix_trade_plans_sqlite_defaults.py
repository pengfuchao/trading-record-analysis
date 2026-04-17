"""fix server_defaults for SQLite across all tables that used NOW()

Revision ID: 008
Revises: 007
Create Date: 2026-04-17

Migrations 001–005 used sa.func.now() / sa.text("NOW()") for server_default on
created_at/updated_at. NOW() is PostgreSQL syntax; SQLite requires CURRENT_TIMESTAMP.

Python-side defaults (default=datetime.utcnow) were added to all ORM models as the
primary fix. The app works correctly on both SQLite and PostgreSQL after the ORM fix
regardless of the server_default string in the DDL catalog.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables with both created_at and updated_at
_TABLES_BOTH = [
    "trades",
    "trade_plans",
    "daily_plans",
    "daily_reviews",
    "setup_definitions",
]

# Tables with only created_at
_TABLES_CREATED_ONLY = [
    "accounts",
]


def upgrade() -> None:
    for table in _TABLES_BOTH:
        with op.batch_alter_table(table) as batch_op:
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
    for table in _TABLES_CREATED_ONLY:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(),
                existing_nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )


def downgrade() -> None:
    for table in _TABLES_BOTH:
        with op.batch_alter_table(table) as batch_op:
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
    for table in _TABLES_CREATED_ONLY:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(),
                existing_nullable=False,
                server_default=sa.text("NOW()"),
            )
