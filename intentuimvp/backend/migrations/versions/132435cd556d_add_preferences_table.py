"""add preferences table

Revision ID: 132435cd556d
Revises: 1a37d9c1fbf0
Create Date: 2026-01-06 22:19:45.040483

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '132435cd556d'
down_revision: str | Sequence[str] | None = '1a37d9c1fbf0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create preferences table
    op.create_table(
        'preferences',
        sa.Column('user_id', sa.String(), primary_key=True),
        sa.Column('preferences', sa.JSON(), nullable=False, default='{}'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('preferences')
