"""add_turn_table

Revision ID: 20260117_turns_schema
Revises: 20260112_yzb_3_1_dashboard_subscriptions
Create Date: 2026-01-17 00:00:00.000000

This migration adds the turn table for the Turns System.

A Turn represents any state change: user input, canvas CRUD, job lifecycle,
system responses, and assumption reconciliation. Turns are forward-only
(append-only) and grow indefinitely - no branching/undo at DB level.

Per PRD requirements:
- session_id: Links turns to a session/conversation
- sequence_number: Monotonic order within session
- actor: Who created the turn (user, system, agent, mcp)
- type: What kind of state change occurred
- payload: JSON for turn-specific data
- Indexes for session, type, actor, and time range queries
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260117_turns_schema"
down_revision: str | Sequence[str] | None = "20260112_yzb_3_1_dashboard_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    """Create turn table with indexes."""
    if _table_exists("turn"):
        return

    op.create_table(
        "turn",
        # Primary key
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # Session and sequencing
        sa.Column(
            "session_id",
            sa.String(),
            nullable=False,
            index=True,
            comment="Session/conversation identifier",
        ),
        sa.Column(
            "sequence_number",
            sa.Integer(),
            nullable=False,
            comment="Monotonic sequence number within session",
        ),
        # Timing
        sa.Column(
            "timestamp",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            index=True,
            comment="When this turn occurred",
        ),
        # Turn classification
        sa.Column(
            "actor",
            sa.String(),
            nullable=False,
            index=True,
            comment="Who/what created this turn (user, system, agent, mcp)",
        ),
        sa.Column(
            "type",
            sa.String(),
            nullable=False,
            index=True,
            comment="Type of state change",
        ),
        # Content
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
            comment="Human-readable summary of the turn",
        ),
        sa.Column(
            "turn_payload",
            sa.Text(),
            nullable=True,
            comment="JSON object with turn-specific data",
        ),
        # Related entities (optional foreign keys)
        sa.Column(
            "related_node_id",
            sa.Integer(),
            sa.ForeignKey("node.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
            comment="Optional reference to related node",
        ),
        sa.Column(
            "related_edge_id",
            sa.Integer(),
            sa.ForeignKey("edge.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
            comment="Optional reference to related edge",
        ),
    )

    # Create composite index for efficient session + sequence queries
    op.create_index(
        "ix_turn_session_sequence",
        "turn",
        ["session_id", "sequence_number"],
        unique=False,
    )

    # Create composite index for time range + session queries
    op.create_index(
        "ix_turn_session_timestamp",
        "turn",
        ["session_id", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    """Drop turn table and indexes."""
    # Drop composite indexes first
    op.drop_index("ix_turn_session_timestamp", table_name="turn")
    op.drop_index("ix_turn_session_sequence", table_name="turn")

    # Drop single-column indexes (created via index=True)
    op.drop_index("ix_turn_related_edge_id", table_name="turn")
    op.drop_index("ix_turn_related_node_id", table_name="turn")
    op.drop_index("ix_turn_type", table_name="turn")
    op.drop_index("ix_turn_actor", table_name="turn")
    op.drop_index("ix_turn_timestamp", table_name="turn")
    op.drop_index("ix_turn_session_id", table_name="turn")

    # Drop the table
    op.drop_table("turn")
