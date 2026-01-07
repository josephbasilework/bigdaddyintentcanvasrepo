"""add backups table

Revision ID: 20260106_s011_backups
Revises: 132435cd556d
Create Date: 2026-01-06 22:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260106_s011_backups'
down_revision: str | Sequence[str] | None = '132435cd556d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create backups table
    op.create_table(
        'backups',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(), nullable=False, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False, index=True),
        sa.Column('encrypted_data', sa.LargeBinary(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('backups')
