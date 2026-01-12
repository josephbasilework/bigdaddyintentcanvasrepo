"""intent_index_schema_updates

Revision ID: 20260112_kn0_2_2_intent_index_schema
Revises: 20260112_kn0_2_1_pgvector
Create Date: 2026-01-12 18:30:00.000000

Adds intent index schema fields per PRD section 15.2:
- resolution JSONB for approved assumptions/actions
- outcome ENUM('success', 'failure', 'modified') for learning/pruning
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260112_kn0_2_2_intent_index_schema"
down_revision: str | Sequence[str] | None = "20260112_kn0_2_1_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OUTCOME_ENUM = sa.Enum("success", "failure", "modified", name="intent_outcome")


def _is_postgresql() -> bool:
    """Check if the current database connection is PostgreSQL."""
    return op.get_bind().dialect.name == "postgresql"


def _resolution_column_type() -> sa.TypeEngine:
    if _is_postgresql():
        from sqlalchemy.dialects import postgresql

        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if _is_postgresql():
        OUTCOME_ENUM.create(bind, checkfirst=True)

    with op.batch_alter_table("user_intents") as batch:
        batch.add_column(sa.Column("resolution", _resolution_column_type(), nullable=True))
        batch.add_column(sa.Column("outcome", OUTCOME_ENUM, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    with op.batch_alter_table("user_intents") as batch:
        batch.drop_column("outcome")
        batch.drop_column("resolution")

    if _is_postgresql():
        OUTCOME_ENUM.drop(bind, checkfirst=True)
