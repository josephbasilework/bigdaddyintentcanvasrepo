"""add_runtime_monitoring_to_mcp_execution_logs

Revision ID: 20260112_9zg_5_monitoring
Revises: 20260112_vel_3_audio
Create Date: 2026-01-12 14:00:00.000000

Adds runtime monitoring fields to mcp_execution_logs per FR-019:
- input_hash: SHA256 hash of tool arguments for deduplication/analysis
- output_size: Approximate size of tool output in bytes
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260112_9zg_5_monitoring'
down_revision: str | Sequence[str] | None = '20260112_vel_3_audio'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add input_hash column for SHA256 hash of tool arguments
    op.add_column(
        'mcp_execution_logs',
        sa.Column('input_hash', sa.String(), nullable=True)
    )
    op.create_index(
        op.f('ix_mcp_execution_logs_input_hash'),
        'mcp_execution_logs',
        ['input_hash']
    )

    # Add output_size column for approximate size of tool output in bytes
    op.add_column(
        'mcp_execution_logs',
        sa.Column('output_size', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('mcp_execution_logs', 'output_size')
    op.drop_index(op.f('ix_mcp_execution_logs_input_hash'), table_name='mcp_execution_logs')
    op.drop_column('mcp_execution_logs', 'input_hash')
