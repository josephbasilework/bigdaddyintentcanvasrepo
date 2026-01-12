"""pgvector_embedding_setup

Revision ID: 20260112_kn0_2_1_pgvector
Revises: 20260112_9zg_5_monitoring
Create Date: 2026-01-12 15:30:00.000000

This migration sets up pgvector extension and vector embeddings for the Intent Index.

Per PRD §15.2 (F7.2: Intent Index):
- Enables pgvector extension for PostgreSQL
- Updates user_intents.embedding column to vector(384) for all-MiniLM-L6-v2 model
- Creates ivfflat index for fast cosine similarity search (threshold > 0.7)

Note: This migration only applies to PostgreSQL databases. SQLite databases will
continue using String type for the embedding column (no-op for SQLite).

To enable pgvector features, set DATABASE_URL to a PostgreSQL connection string
with pgvector extension installed:
  export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260112_kn0_2_1_pgvector'
down_revision: str | Sequence[str] | None = '20260112_9zg_5_monitoring'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Embedding dimension for all-MiniLM-L6-v2 sentence transformer model
EMBEDDING_DIM = 384


def _is_postgresql() -> bool:
    """Check if the current database connection is PostgreSQL."""
    conn = op.get_bind()
    return conn.dialect.name == 'postgresql'


def upgrade() -> None:
    """Upgrade schema."""
    if not _is_postgresql():
        # Skip pgvector setup for SQLite (no-op)
        return

    # Enable pgvector extension if not already enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Check if embedding column exists and is String type
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('user_intents')

    embedding_col = next((c for c in columns if c['name'] == 'embedding'), None)
    if embedding_col and embedding_col['type'].python_type is str:
        # Migrate from String to vector(384)
        # First, drop any existing data (embeddings will be regenerated)
        op.execute('UPDATE user_intents SET embedding = NULL WHERE embedding IS NOT NULL')

        # Alter column type to vector(384)
        op.execute(f'ALTER TABLE user_intents ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM}) USING embedding::vector')

    # Create ivfflat index for fast cosine similarity search
    # ivfflat requires at least 1000 rows for training; for smaller tables,
    # consider using exact search (no index) or hnsw
    op.execute('''
        CREATE INDEX IF NOT EXISTS ix_user_intents_embedding_cosine
        ON user_intents
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')


def downgrade() -> None:
    """Downgrade schema."""
    if not _is_postgresql():
        # Skip pgvector teardown for SQLite (no-op)
        return

    # Drop vector index
    op.execute('DROP INDEX IF EXISTS ix_user_intents_embedding_cosine')

    # Revert embedding column back to String (data loss: vectors become strings)
    op.execute(f'ALTER TABLE user_intents ALTER COLUMN embedding TYPE VARCHAR({EMBEDDING_DIM * 4})')

    # Note: pgvector extension is not dropped to avoid affecting other tables
