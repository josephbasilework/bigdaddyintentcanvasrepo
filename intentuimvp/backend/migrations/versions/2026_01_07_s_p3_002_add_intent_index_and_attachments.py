"""add_intent_index_and_attachments

Revision ID: 2026_01_07_s_p3_002
Revises: ec09d9bce846
Create Date: 2026-01-07 00:00:00.000000

This migration adds:
1. user_intents table with pgvector embedding support for intent indexing
2. attachments table for file attachment handling
3. assumption_resolutions table for tracking user assumption confirmations

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2026_01_07_s_p3_002'
down_revision: str | Sequence[str] | None = 'ec09d9bce846'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # Enable pgvector extension if not already enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create user_intents table for intent meaning index with pgvector
    op.create_table(
        'user_intents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('intent_text', sa.String(), nullable=False),
        sa.Column('intent_type', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('embedding', sa.String(), nullable=True),  # Stored as vector(1536) or similar
        sa.Column('context', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('handler', sa.String(), nullable=True),
        sa.Column('executed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_intents_user_id'), 'user_intents', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_intents_created_at'), 'user_intents', ['created_at'], unique=False)

    # Add vector index for similarity search
    # Note: The actual vector column type and index depends on pgvector setup
    # This is a placeholder - in production, you'd use:
    # op.execute('ALTER TABLE user_intents ADD COLUMN embedding vector(1536)')
    # op.execute('CREATE INDEX ix_user_intents_embedding ON user_intents USING ivfflat (embedding vector_cosine_ops)')

    # Create attachments table for file handling
    op.create_table(
        'attachments',
        sa.Column('id', sa.String(), nullable=False),  # UUID as string
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('attachment_type', sa.String(), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('transcription', sa.Text(), nullable=True),  # For audio
        sa.Column('description', sa.Text(), nullable=True),  # AI-generated for images
        sa.Column('status', sa.String(), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('context_id', sa.String(), nullable=True),  # Link to context/session
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_attachments_id'), 'attachments', ['id'], unique=True)
    op.create_index(op.f('ix_attachments_user_id'), 'attachments', ['user_id'], unique=False)
    op.create_index(op.f('ix_attachments_context_id'), 'attachments', ['context_id'], unique=False)

    # Create assumption_resolutions table for tracking user confirmations
    op.create_table(
        'assumption_resolutions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('assumption_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),  # accept, reject, edit
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('final_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_assumption_resolutions_session_id'),
        'assumption_resolutions',
        ['session_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_assumption_resolutions_assumption_id'),
        'assumption_resolutions',
        ['assumption_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Drop tables in reverse order
    op.drop_index(op.f('ix_assumption_resolutions_assumption_id'), table_name='assumption_resolutions')
    op.drop_index(op.f('ix_assumption_resolutions_session_id'), table_name='assumption_resolutions')
    op.drop_table('assumption_resolutions')

    op.drop_index(op.f('ix_attachments_context_id'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_user_id'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_id'), table_name='attachments')
    op.drop_table('attachments')

    op.drop_index(op.f('ix_user_intents_created_at'), table_name='user_intents')
    op.drop_index(op.f('ix_user_intents_user_id'), table_name='user_intents')
    op.drop_table('user_intents')

    # Note: pgvector extension is not dropped to avoid affecting other tables
