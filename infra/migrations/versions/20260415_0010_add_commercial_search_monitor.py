"""add commercial search monitor

Revision ID: 20260415_0010
Revises: 20260414_0009
Create Date: 2026-04-15 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260415_0010"
down_revision = "20260414_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commercial_search_monitor",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("search_url", sa.String(length=1000), nullable=False),
        sa.Column("scope_type", sa.String(length=40), server_default="custom", nullable=False),
        sa.Column("development_name_hint", sa.String(length=255), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("with_details", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("detect_withdrawn", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("criteria_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "search_url", name="uq_commercial_search_monitor_source_url"),
    )
    op.create_index(
        "ix_commercial_search_monitor_source_active",
        "commercial_search_monitor",
        ["source", "is_active", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_commercial_search_monitor_source_active", table_name="commercial_search_monitor")
    op.drop_table("commercial_search_monitor")
