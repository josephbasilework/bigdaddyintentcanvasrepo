"""add_mcp_tables

Revision ID: ec09d9bce846
Revises: c0d47987c07f
Create Date: 2026-01-06 23:42:36.740357

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ec09d9bce846'
down_revision: str | Sequence[str] | None = 'c0d47987c07f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create mcp_servers table
    op.create_table(
        'mcp_servers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('server_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('transport_type', sa.String(), server_default='stdio', nullable=False),
        sa.Column('transport_config', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('version', sa.String(), nullable=True),
        sa.Column('capabilities', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('security_rules', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('rate_limit', sa.Integer(), server_default='60', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mcp_servers_server_id'), 'mcp_servers', ['server_id'], unique=True)

    # Create mcp_execution_logs table
    op.create_table(
        'mcp_execution_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('server_id', sa.String(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('initiated_by', sa.String(), nullable=False),
        sa.Column('confirmed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mcp_execution_logs_server_id'), 'mcp_execution_logs', ['server_id'])
    op.create_index(op.f('ix_mcp_execution_logs_tool_name'), 'mcp_execution_logs', ['tool_name'])
    op.create_index(op.f('ix_mcp_execution_logs_executed_at'), 'mcp_execution_logs', ['executed_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mcp_execution_logs_executed_at'), table_name='mcp_execution_logs')
    op.drop_index(op.f('ix_mcp_execution_logs_tool_name'), table_name='mcp_execution_logs')
    op.drop_index(op.f('ix_mcp_execution_logs_server_id'), table_name='mcp_execution_logs')
    op.drop_table('mcp_execution_logs')

    op.drop_index(op.f('ix_mcp_servers_server_id'), table_name='mcp_servers')
    op.drop_table('mcp_servers')
