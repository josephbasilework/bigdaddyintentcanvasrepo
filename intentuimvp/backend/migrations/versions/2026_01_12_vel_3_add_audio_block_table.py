"""add_audio_block_table

Revision ID: 20260112_vel_3_audio
Revises: 20260107_l35_artifacts
Create Date: 2026-01-12 14:00:00.000000

This migration adds the audio_block table for storing voice recordings
and their transcriptions on canvas nodes (FR-016: Audio Blocks & Transcription).

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260112_vel_3_audio'
down_revision: str | Sequence[str] | None = '20260107_l35_artifacts'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create audio_block table
    op.create_table(
        'audio_block',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('canvas_id', sa.Integer(), sa.ForeignKey('canvas.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('audio_uri', sa.String(), nullable=False, comment='Storage reference (path or URL where the audio file is stored)'),
        sa.Column('transcription', sa.Text(), nullable=True, comment='Transcribed text content'),
        sa.Column('duration', sa.Float(), nullable=True, comment='Duration of the audio recording in seconds'),
        sa.Column('status', sa.String(), nullable=False, default='pending', comment='Processing status (pending, ready, transcribing, transcribed, error)'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if processing failed'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
    )
    # Create index on canvas_id for efficient queries
    op.create_index('ix_audio_block_canvas_id', 'audio_block', ['canvas_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_audio_block_canvas_id', table_name='audio_block')
    op.drop_table('audio_block')
