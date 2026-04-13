"""add search preset

Revision ID: 20260414_0009
Revises: 20260413_0008
Create Date: 2026-04-14 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260414_0009"
down_revision = "20260413_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_preset",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.String(length=60), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("criteria_json", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "name", name="uq_search_preset_scope_name"),
    )
    op.create_index("ix_search_preset_scope_updated", "search_preset", ["scope", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_search_preset_scope_updated", table_name="search_preset")
    op.drop_table("search_preset")
