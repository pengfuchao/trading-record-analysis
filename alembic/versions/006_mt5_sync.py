"""add mt5_sync_configs and mt5_sync_runs tables

Revision ID: 006
Revises: 005
Create Date: 2026-04-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-account MT5 connection config (password stored in .env, never in DB)
    op.create_table(
        "mt5_sync_configs",
        sa.Column("account_id",               sa.String(100), primary_key=True, nullable=False),
        sa.Column("mt5_login",                sa.Integer(),   nullable=False),
        sa.Column("mt5_server",               sa.String(200), nullable=False),
        sa.Column("terminal_path",            sa.String(500), nullable=True),
        sa.Column("broker_utc_offset",        sa.Integer(),   nullable=False, server_default="2"),
        sa.Column("polling_interval_minutes", sa.Integer(),   nullable=False, server_default="60"),
        sa.Column("enabled",                  sa.Boolean(),   nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"], ondelete="CASCADE"),
    )

    # Audit log — one row per sync attempt
    op.create_table(
        "mt5_sync_runs",
        sa.Column("run_id",          sa.String(100), primary_key=True, nullable=False),
        sa.Column("account_id",      sa.String(100), nullable=False),
        sa.Column("triggered_by",    sa.String(20),  nullable=False),   # "manual" | "scheduled"
        sa.Column("started_at",      sa.DateTime(),  nullable=False),
        sa.Column("completed_at",    sa.DateTime(),  nullable=True),     # NULL while running
        sa.Column("status",          sa.String(20),  nullable=False),   # "running" | "success" | "error"
        sa.Column("from_date",       sa.DateTime(),  nullable=True),
        sa.Column("to_date",         sa.DateTime(),  nullable=True),
        sa.Column("deals_fetched",   sa.Integer(),   nullable=True),
        sa.Column("positions_built", sa.Integer(),   nullable=True),
        sa.Column("trades_new",      sa.Integer(),   nullable=True),
        sa.Column("trades_updated",  sa.Integer(),   nullable=True),
        sa.Column("trades_skipped",  sa.Integer(),   nullable=True),
        sa.Column("error_message",   sa.Text(),      nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_mt5_sync_runs_account_started",
        "mt5_sync_runs",
        ["account_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_mt5_sync_runs_account_started", "mt5_sync_runs")
    op.drop_table("mt5_sync_runs")
    op.drop_table("mt5_sync_configs")
