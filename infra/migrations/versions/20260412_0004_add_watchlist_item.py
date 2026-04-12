"""add watchlist item"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0004"
down_revision = "20260412_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_item",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("development_id", sa.String(length=36), nullable=False),
        sa.Column(
            "decision_stage",
            sa.Enum(
                "WATCHING",
                "SHORTLISTED",
                "VISIT_PLANNED",
                "NEGOTIATING",
                "PASSED",
                name="watchliststage",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("personal_score", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["development_id"], ["development.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("development_id", name="uq_watchlist_item_development"),
    )
    op.create_index("ix_watchlist_stage", "watchlist_item", ["decision_stage"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_watchlist_stage", table_name="watchlist_item")
    op.drop_table("watchlist_item")
