"""add_node_content_column

Revision ID: 20260121_node_content
Revises: 20260120_attachment_links
Create Date: 2026-01-21 00:00:00.000000

Adds an optional content column to the node table for text/entity nodes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260121_node_content"
down_revision: str | Sequence[str] | None = "20260120_attachment_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Upgrade schema."""
    if _column_exists("node", "content"):
        return

    with op.batch_alter_table("node") as batch:
        batch.add_column(sa.Column("content", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if not _column_exists("node", "content"):
        return

    with op.batch_alter_table("node") as batch:
        batch.drop_column("content")
