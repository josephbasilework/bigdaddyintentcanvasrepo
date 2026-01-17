"""add_workspace_session_table

Revision ID: 20260117_workspace_session
Revises: 20260117_turns_schema
Create Date: 2026-01-17 08:00:00.000000

Adds workspace_session table for Global Session Identity.

A WorkspaceSession represents a persistent session identity that spans across
WebSocket reconnections. Sessions are workspace-scoped and tie together:
- WebSocket connections
- Turn timelines (via session_id reference)
- Context routing decisions

Per task requirements:
- session_id: Unique identifier used externally (UUID)
- workspace_id: Links session to canvas/workspace
- user_id: Owner of the session (denormalized for efficient queries)
- created_at: When session was first created
- last_active_at: Updated on reconnect for session health monitoring
- resumed_count: Tracks reconnection frequency
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260117_workspace_session"
down_revision: str | Sequence[str] | None = "20260117_turns_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    """Create workspace_session table with indexes."""
    if _table_exists("workspace_session"):
        return

    op.create_table(
        "workspace_session",
        # Primary key
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # Session identity
        sa.Column(
            "session_id",
            sa.String(),
            nullable=False,
            unique=True,
            index=True,
            comment="Unique session identifier (UUID)",
        ),
        # Workspace relationship
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("canvas.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Foreign key to canvas/workspace",
        ),
        # User ownership
        sa.Column(
            "user_id",
            sa.String(),
            nullable=False,
            index=True,
            comment="User who owns this session",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="When this session was created",
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            index=True,
            comment="When this session was last active",
        ),
        # Session metrics
        sa.Column(
            "resumed_count",
            sa.Integer(),
            nullable=False,
            default=0,
            server_default="0",
            comment="Number of times session has been resumed",
        ),
    )

    # Create composite index for user + workspace efficient lookups
    op.create_index(
        "ix_workspace_session_user_workspace",
        "workspace_session",
        ["user_id", "workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop workspace_session table and indexes."""
    # Drop composite index
    op.drop_index("ix_workspace_session_user_workspace", table_name="workspace_session")

    # Drop single-column indexes (created via index=True)
    op.drop_index("ix_workspace_session_last_active_at", table_name="workspace_session")
    op.drop_index("ix_workspace_session_user_id", table_name="workspace_session")
    op.drop_index("ix_workspace_session_workspace_id", table_name="workspace_session")
    op.drop_index("ix_workspace_session_session_id", table_name="workspace_session")

    # Drop the table
    op.drop_table("workspace_session")
