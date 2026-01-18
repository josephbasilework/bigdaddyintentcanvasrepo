"""add_attachment_link_columns

Revision ID: 20260120_attachment_links
Revises: 20260119_event_schema
Create Date: 2026-01-20 00:00:00.000000

Adds linking columns to attachments for turns, sessions, nodes, and artifacts.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260120_attachment_links"
down_revision: str | Sequence[str] | None = "20260119_event_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    """Upgrade schema."""
    columns: list[sa.Column] = []
    if not _column_exists("attachments", "session_id"):
        columns.append(sa.Column("session_id", sa.String(), nullable=True))
    if not _column_exists("attachments", "turn_id"):
        columns.append(sa.Column("turn_id", sa.Integer(), nullable=True))
    if not _column_exists("attachments", "node_id"):
        columns.append(sa.Column("node_id", sa.Integer(), nullable=True))
    if not _column_exists("attachments", "artifact_id"):
        columns.append(sa.Column("artifact_id", sa.Integer(), nullable=True))

    if columns:
        with op.batch_alter_table("attachments") as batch:
            for column in columns:
                batch.add_column(column)

    if not _index_exists("attachments", "ix_attachments_session_id"):
        op.create_index("ix_attachments_session_id", "attachments", ["session_id"])
    if not _index_exists("attachments", "ix_attachments_turn_id"):
        op.create_index("ix_attachments_turn_id", "attachments", ["turn_id"])
    if not _index_exists("attachments", "ix_attachments_node_id"):
        op.create_index("ix_attachments_node_id", "attachments", ["node_id"])
    if not _index_exists("attachments", "ix_attachments_artifact_id"):
        op.create_index("ix_attachments_artifact_id", "attachments", ["artifact_id"])


def downgrade() -> None:
    """Downgrade schema."""
    if _index_exists("attachments", "ix_attachments_artifact_id"):
        op.drop_index("ix_attachments_artifact_id", table_name="attachments")
    if _index_exists("attachments", "ix_attachments_node_id"):
        op.drop_index("ix_attachments_node_id", table_name="attachments")
    if _index_exists("attachments", "ix_attachments_turn_id"):
        op.drop_index("ix_attachments_turn_id", table_name="attachments")
    if _index_exists("attachments", "ix_attachments_session_id"):
        op.drop_index("ix_attachments_session_id", table_name="attachments")

    with op.batch_alter_table("attachments") as batch:
        if _column_exists("attachments", "artifact_id"):
            batch.drop_column("artifact_id")
        if _column_exists("attachments", "node_id"):
            batch.drop_column("node_id")
        if _column_exists("attachments", "turn_id"):
            batch.drop_column("turn_id")
        if _column_exists("attachments", "session_id"):
            batch.drop_column("session_id")
