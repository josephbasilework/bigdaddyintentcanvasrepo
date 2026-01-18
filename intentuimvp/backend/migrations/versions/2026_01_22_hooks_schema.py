"""add_hooks_table

Revision ID: 20260122_hooks_schema
Revises: 20260121_node_content
Create Date: 2026-01-22 00:00:00.000000

Adds hook table for deterministic lifecycle and scheduled triggers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260122_hooks_schema"
down_revision: str | Sequence[str] | None = "20260121_node_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    """Create hook table with indexes."""
    if _table_exists("hook"):
        return

    op.create_table(
        "hook",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hook_type", sa.String(), nullable=False, index=True),
        sa.Column("event_type", sa.String(), nullable=True, index=True),
        sa.Column("schedule_type", sa.String(), nullable=True, index=True),
        sa.Column("trigger", sa.JSON(), nullable=True),
        sa.Column("action", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("user_id", sa.String(), nullable=True, index=True),
        sa.Column("workspace_id", sa.String(), nullable=True, index=True),
        sa.Column("session_id", sa.String(), nullable=True, index=True),
        sa.Column("last_fired_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop hook table."""
    op.drop_index("ix_hook_next_run_at", table_name="hook")
    op.drop_index("ix_hook_session_id", table_name="hook")
    op.drop_index("ix_hook_workspace_id", table_name="hook")
    op.drop_index("ix_hook_user_id", table_name="hook")
    op.drop_index("ix_hook_schedule_type", table_name="hook")
    op.drop_index("ix_hook_event_type", table_name="hook")
    op.drop_index("ix_hook_hook_type", table_name="hook")
    op.drop_index("ix_hook_name", table_name="hook")
    op.drop_table("hook")
