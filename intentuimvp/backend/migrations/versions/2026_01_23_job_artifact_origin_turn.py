"""add_job_artifact_origin_turn

Revision ID: 20260123_job_artifact_origin_turn
Revises: 20260122_hooks_schema
Create Date: 2026-01-23 00:00:00.000000

Adds origin_turn_id to job_artifact for linking artifacts to the originating turn.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260123_job_artifact_origin_turn"
down_revision: str | Sequence[str] | None = "20260122_hooks_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema."""
    if _column_exists("job_artifact", "origin_turn_id"):
        return

    op.add_column(
        "job_artifact",
        sa.Column(
            "origin_turn_id",
            sa.Integer(),
            sa.ForeignKey("turn.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_job_artifact_origin_turn_id",
        "job_artifact",
        ["origin_turn_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_job_artifact_origin_turn_id", table_name="job_artifact")
    op.drop_column("job_artifact", "origin_turn_id")
