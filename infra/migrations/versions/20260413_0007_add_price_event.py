"""add price event"""

from alembic import op
import sqlalchemy as sa


revision = "20260413_0007"
down_revision = "20260412_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "NEW_LISTING",
                "PRICE_DROP",
                "PRICE_RAISE",
                "STATUS_CHANGE",
                "SOLD",
                "WITHDRAWN",
                "RELIST",
                name="priceeventtype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("development_id", sa.String(length=36), nullable=False),
        sa.Column("listing_id", sa.String(length=36), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("old_price_hkd", sa.Numeric(15, 2), nullable=True),
        sa.Column("new_price_hkd", sa.Numeric(15, 2), nullable=True),
        sa.Column("old_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["development_id"], ["development.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_event_development_event_at",
        "price_event",
        ["development_id", "event_at"],
        unique=False,
    )
    op.create_index(
        "ix_price_event_listing_event_type",
        "price_event",
        ["listing_id", "event_type"],
        unique=False,
    )
    op.create_index(
        "ix_price_event_source_event_at",
        "price_event",
        ["source", "event_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_price_event_source_event_at", table_name="price_event")
    op.drop_index("ix_price_event_listing_event_type", table_name="price_event")
    op.drop_index("ix_price_event_development_event_at", table_name="price_event")
    op.drop_table("price_event")
