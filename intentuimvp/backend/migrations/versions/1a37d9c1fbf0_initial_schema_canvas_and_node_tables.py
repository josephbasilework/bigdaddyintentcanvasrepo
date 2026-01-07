"""Initial schema: canvas and node tables

Revision ID: 1a37d9c1fbf0
Revises:
Create Date: 2026-01-06 20:36:26.402032

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1a37d9c1fbf0'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create canvas table
    op.create_table(
        'canvas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
    )

    # Create node table
    op.create_table(
        'node',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('canvas_id', sa.Integer(), sa.ForeignKey('canvas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('x', sa.Float(), nullable=False, default=0),
        sa.Column('y', sa.Float(), nullable=False, default=0),
        sa.Column('z', sa.Float(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('node')
    op.drop_table('canvas')
