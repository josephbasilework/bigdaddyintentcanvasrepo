"""add_notification_table

Revision ID: 20260125_notification_schema
Revises: 20260124_artifact_linking
Create Date: 2026-01-25 00:00:00.000000

Adds notification table for user-facing alerts and reminders.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260125_notification_schema"
down_revision: str | Sequence[str] | None = "20260124_artifact_linking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    """Create notification table with indexes."""
    if _table_exists("notification"):
        return

    op.create_table(
        "notification",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("canvas.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("session_id", sa.String(), nullable=True, index=True),
        sa.Column("source", sa.String(), nullable=True, index=True),
        sa.Column("level", sa.String(), nullable=False, server_default="info"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            index=True,
        ),
        sa.Column("read_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True, index=True),
        sa.Column(
            "related_node_id",
            sa.Integer(),
            sa.ForeignKey("node.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "related_edge_id",
            sa.Integer(),
            sa.ForeignKey("edge.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Drop notification table."""
    op.drop_index("ix_notification_related_edge_id", table_name="notification")
    op.drop_index("ix_notification_related_node_id", table_name="notification")
    op.drop_index("ix_notification_dismissed_at", table_name="notification")
    op.drop_index("ix_notification_read_at", table_name="notification")
    op.drop_index("ix_notification_created_at", table_name="notification")
    op.drop_index("ix_notification_source", table_name="notification")
    op.drop_index("ix_notification_session_id", table_name="notification")
    op.drop_index("ix_notification_workspace_id", table_name="notification")
    op.drop_index("ix_notification_user_id", table_name="notification")
    op.drop_table("notification")
