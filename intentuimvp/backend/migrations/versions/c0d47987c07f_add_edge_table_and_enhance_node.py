"""add_edge_table_and_enhance_node

Revision ID: c0d47987c07f
Revises: 20260106_s011_backups
Create Date: 2026-01-06 23:09:32.446336

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import reflection

# revision identifiers, used by Alembic.
revision: str = 'c0d47987c07f'
down_revision: str | Sequence[str] | None = '20260106_s011_backups'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # For SQLite, we need to recreate the node table with the new schema
    # Get the current database connection
    conn = op.get_bind()
    inspector = reflection.Inspector.from_engine(conn)

    # Check if node_id column already exists (might be re-running)
    existing_columns = [col['name'] for col in inspector.get_columns('node')]

    if 'node_id' not in existing_columns:
        # Create a new node table with all the desired columns using SQLAlchemy API
        op.create_table(
            'node_new',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('node_id', sa.String(), nullable=False, unique=True),
            sa.Column('canvas_id', sa.Integer(), sa.ForeignKey('canvas.id', ondelete='CASCADE'), nullable=False),
            sa.Column('type', sa.String(), nullable=False, server_default='text'),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('node_metadata', sa.Text(), nullable=True),
            sa.Column('x', sa.Float(), nullable=False, default=0),
            sa.Column('y', sa.Float(), nullable=False, default=0),
            sa.Column('z', sa.Float(), nullable=False, default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        )

        # Copy existing data to new table with defaults for new columns
        op.execute("""
            INSERT INTO node_new (id, node_id, canvas_id, type, title, content, node_metadata, x, y, z, created_at)
            SELECT id, 'node-' || id, canvas_id, 'text', label, NULL, NULL, x, y, z, created_at
            FROM node
        """)

        # Drop old table and rename new one
        op.execute("DROP TABLE node")
        op.execute("ALTER TABLE node_new RENAME TO node")

        # Create index on node_id
        op.create_index('ix_node_node_id', 'node', ['node_id'], unique=True)

    # Create edge table
    op.create_table(
        'edge',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('edge_id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.Integer(), sa.ForeignKey('canvas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_node_id', sa.String(), nullable=False),
        sa.Column('target_node_id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False, server_default='solid'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    )

    # Create indexes for edge table
    op.create_index('ix_edge_edge_id', 'edge', ['edge_id'], unique=True)
    op.create_index('ix_edge_canvas_id', 'edge', ['canvas_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop edge table
    op.drop_index('ix_edge_canvas_id', table_name='edge')
    op.drop_index('ix_edge_edge_id', table_name='edge')
    op.drop_table('edge')

    # Recreate old node table without the new columns
    op.create_table(
        'node_new',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('canvas_id', sa.Integer(), sa.ForeignKey('canvas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('x', sa.Float(), nullable=False, default=0),
        sa.Column('y', sa.Float(), nullable=False, default=0),
        sa.Column('z', sa.Float(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    )

    # Copy data back to old format
    op.execute("""
        INSERT INTO node_new (id, canvas_id, label, x, y, z, created_at)
        SELECT id, canvas_id, title, x, y, z, created_at
        FROM node
    """)

    # Drop new table and rename
    op.execute("DROP TABLE node")
    op.execute("ALTER TABLE node_new RENAME TO node")
