"""add_job_artifact_table

Revision ID: 20260107_l35_artifacts
Revises: 20260107_vz6_jobs
Create Date: 2026-01-07 16:45:00.000000

This migration adds the job_artifact table for persistent storage of job artifacts
(files, blobs, documents) produced during job execution.

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260107_l35_artifacts'
down_revision: str | Sequence[str] | None = '20260107_vz6_jobs'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create job_artifact table
    op.create_table(
        'job_artifact',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('job_id', sa.String(), nullable=False, index=True, comment='ARQ job ID (UUID string)'),
        sa.Column('user_id', sa.String(), nullable=True, index=True),
        sa.Column('workspace_id', sa.String(), nullable=True, index=True),
        sa.Column('artifact_type', sa.String(), nullable=False, index=True, comment='Type of artifact (ArtifactType enum)'),
        sa.Column('artifact_name', sa.String(), nullable=False, comment='Human-readable name for the artifact'),
        sa.Column('description', sa.String(), nullable=True, comment='Optional description of the artifact'),
        sa.Column('filename', sa.String(), nullable=True, comment='Original filename (if applicable)'),
        sa.Column('mime_type', sa.String(), nullable=True, comment='MIME type of the content'),
        sa.Column('size_bytes', sa.Integer(), nullable=True, comment='Size of the artifact in bytes'),
        sa.Column('storage_path', sa.String(), nullable=True, comment='Path or URL where the artifact is stored'),
        sa.Column('inline_data', sa.String(), nullable=True, comment='Inline data for small artifacts (JSON, text, etc.)'),
        sa.Column('is_archived', sa.Integer(), nullable=False, default=0, comment='Whether the artifact is archived (0/1)'),
        sa.Column('archive_after_days', sa.Integer(), nullable=True, comment='Days after creation when this should be auto-archived'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('job_artifact')
