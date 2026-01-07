"""add_job_table

Revision ID: 20260107_vz6_jobs
Revises: 2026_01_07_s_p3_002
Create Date: 2026-01-07 16:00:00.000000

This migration adds the job table for persistent tracking of background jobs,
enabling job progress streaming via WebSocket.

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260107_vz6_jobs'
down_revision: str | Sequence[str] | None = '2026_01_07_s_p3_002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create job table
    op.create_table(
        'job',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('job_id', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('user_id', sa.String(), nullable=True, index=True),
        sa.Column('workspace_id', sa.String(), nullable=True, index=True),
        sa.Column('job_type', sa.String(), nullable=False, index=True),
        sa.Column('status', sa.String(), nullable=False, default='pending', index=True),
        sa.Column('progress_percent', sa.Float(), nullable=False, default=0.0),
        sa.Column('current_step', sa.String(), nullable=True),
        sa.Column('steps_total', sa.Integer(), nullable=True),
        sa.Column('step_number', sa.Integer(), nullable=True),
        sa.Column('parameters', sa.Text(), nullable=True),
        sa.Column('result_data', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('job_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('job')
