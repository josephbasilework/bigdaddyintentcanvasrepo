"""add_event_table

Revision ID: 20260119_event_schema
Revises: 20260118_turn_origin_sequence
Create Date: 2026-01-19 00:00:00.000000

Adds event table for unified event logging and audit trails.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260119_event_schema"
down_revision: str | Sequence[str] | None = "20260118_turn_origin_sequence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    """Create event table with indexes."""
    if _table_exists("event"):
        return

    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_type",
            sa.String(),
            nullable=False,
            index=True,
            comment="Namespaced event type (e.g., node.created)",
        ),
        sa.Column(
            "actor",
            sa.String(),
            nullable=False,
            index=True,
            comment="Actor responsible for the event",
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            index=True,
            comment="Event timestamp",
        ),
        sa.Column(
            "event_payload",
            sa.Text(),
            nullable=True,
            comment="JSON payload for the event",
        ),
        sa.Column(
            "related_turn_id",
            sa.Integer(),
            sa.ForeignKey("turn.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Related turn identifier",
        ),
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


def downgrade() -> None:
    """Drop event table."""
    op.drop_index("ix_event_related_edge_id", table_name="event")
    op.drop_index("ix_event_related_node_id", table_name="event")
    op.drop_index("ix_event_related_turn_id", table_name="event")
    op.drop_index("ix_event_timestamp", table_name="event")
    op.drop_index("ix_event_actor", table_name="event")
    op.drop_index("ix_event_event_type", table_name="event")
    op.drop_table("event")

