"""add_dashboard_subscription_table

Revision ID: 20260112_yzb_3_1_dashboard_subscriptions
Revises: 20260112_kn0_2_2_intent_index_schema
Create Date: 2026-01-12 23:30:00.000000

Adds dashboard_subscription table for dashboard state subscriptions (FR-015).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260112_yzb_3_1_dashboard_subscriptions"
down_revision: str | Sequence[str] | None = "20260112_kn0_2_2_intent_index_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "dashboard_subscription",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "canvas_id",
            sa.Integer(),
            sa.ForeignKey("canvas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dashboard_node_id",
            sa.Integer(),
            sa.ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subscription_target", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("subscription_config", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_dashboard_subscription_canvas_id"),
        "dashboard_subscription",
        ["canvas_id"],
    )
    op.create_index(
        op.f("ix_dashboard_subscription_dashboard_node_id"),
        "dashboard_subscription",
        ["dashboard_node_id"],
    )
    op.create_index(
        op.f("ix_dashboard_subscription_subscription_target"),
        "dashboard_subscription",
        ["subscription_target"],
    )
    op.create_index(
        op.f("ix_dashboard_subscription_source_id"),
        "dashboard_subscription",
        ["source_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_dashboard_subscription_source_id"),
        table_name="dashboard_subscription",
    )
    op.drop_index(
        op.f("ix_dashboard_subscription_subscription_target"),
        table_name="dashboard_subscription",
    )
    op.drop_index(
        op.f("ix_dashboard_subscription_dashboard_node_id"),
        table_name="dashboard_subscription",
    )
    op.drop_index(
        op.f("ix_dashboard_subscription_canvas_id"),
        table_name="dashboard_subscription",
    )
    op.drop_table("dashboard_subscription")
