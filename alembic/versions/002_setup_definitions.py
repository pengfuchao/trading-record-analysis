"""add setup_definitions table

Revision ID: 002
Revises: 001
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "setup_definitions",
        sa.Column("setup_id",               sa.String(100), primary_key=True, nullable=False),
        sa.Column("name",                   sa.String(200), nullable=False),
        sa.Column("strategy_group",         sa.String(100), nullable=True),
        sa.Column("description",            sa.Text(),      nullable=True),
        sa.Column("market_environment",     sa.String(100), nullable=True),
        sa.Column("preconditions",          sa.Text(),      nullable=True),
        sa.Column("entry_criteria",         sa.Text(),      nullable=True),
        sa.Column("confirmation_rules",     sa.Text(),      nullable=True),
        sa.Column("stop_loss_rules",        sa.Text(),      nullable=True),
        sa.Column("take_profit_rules",      sa.Text(),      nullable=True),
        sa.Column("invalidation_conditions",sa.Text(),      nullable=True),
        sa.Column("common_mistakes",        sa.Text(),      nullable=True),
        sa.Column("screenshot_examples",    sa.JSON(),                     nullable=True),
        sa.Column("notes",                  sa.Text(),      nullable=True),
        sa.Column("created_at",             sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",             sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_setup_definitions_strategy_group",
        "setup_definitions",
        ["strategy_group"],
    )


def downgrade() -> None:
    op.drop_table("setup_definitions")
