"""add_turn_origin_sequence_and_unique_constraint

Revision ID: 20260118_turn_origin_sequence
Revises: 20260117_workspace_session
Create Date: 2026-01-18 00:00:00.000000

Adds origin_sequence_number to turns and enforces unique session sequencing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260118_turn_origin_sequence"
down_revision: str | Sequence[str] | None = "20260117_workspace_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    """Add origin sequence column and unique constraint to turn table."""
    if not _table_exists("turn"):
        return

    op.add_column(
        "turn",
        sa.Column(
            "origin_sequence_number",
            sa.Integer(),
            nullable=True,
            comment="Sequence number of prior turn being modified/deleted",
        ),
    )
    op.create_index(
        "ix_turn_origin_sequence_number",
        "turn",
        ["origin_sequence_number"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_turn_session_sequence",
        "turn",
        ["session_id", "sequence_number"],
    )


def downgrade() -> None:
    """Remove origin sequence column and unique constraint from turn table."""
    op.drop_constraint("uq_turn_session_sequence", "turn", type_="unique")
    op.drop_index("ix_turn_origin_sequence_number", table_name="turn")
    op.drop_column("turn", "origin_sequence_number")
