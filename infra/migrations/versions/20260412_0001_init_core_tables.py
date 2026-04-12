"""init core tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "development",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=True),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("aliases_json", sa.JSON(), nullable=False),
        sa.Column("address_raw", sa.String(length=500), nullable=True),
        sa.Column("address_normalized", sa.String(length=500), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("subdistrict", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("developer_names_json", sa.JSON(), nullable=False),
        sa.Column("completion_year", sa.Integer(), nullable=True),
        sa.Column("listing_segment", sa.Enum("new", "first_hand_remaining", "second_hand", "mixed", name="listingsegment", native_enum=False), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("source_confidence", sa.Enum("high", "medium", "low", name="sourceconfidence", native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_development_district_segment", "development", ["district", "listing_segment"], unique=False)
    op.create_index("ix_development_name_en", "development", ["name_en"], unique=False)
    op.create_index("ix_development_name_zh", "development", ["name_zh"], unique=False)

    op.create_table(
        "source_snapshot",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_external_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("snapshot_kind", sa.Enum("html", "json", "pdf", "image", name="snapshotkind", native_enum=False), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("parse_status", sa.Enum("pending", "parsed", "failed", name="parsestatus", native_enum=False), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_snapshot_fetched_at", "source_snapshot", ["fetched_at"], unique=False)
    op.create_index("ix_snapshot_source_object", "source_snapshot", ["source", "object_type"], unique=False)

    op.create_table(
        "document",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("development_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_doc_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("doc_type", sa.Enum("brochure", "price_list", "sales_arrangement", "transaction_record", "floor_plan", "other", name="documenttype", native_enum=False), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parsed_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["development_id"], ["development.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_doc_id", name="uq_document_source_external"),
    )
    op.create_index("ix_document_development_type", "document", ["development_id", "doc_type"], unique=False)

    op.create_table(
        "listing",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_listing_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("development_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("listing_type", sa.Enum("new", "first_hand_remaining", "second_hand", name="listingtype", native_enum=False), nullable=False),
        sa.Column("asking_price_hkd", sa.Numeric(15, 2), nullable=True),
        sa.Column("price_per_sqft", sa.Numeric(12, 2), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("saleable_area_sqft", sa.Numeric(10, 2), nullable=True),
        sa.Column("gross_area_sqft", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.Enum("active", "pending", "sold", "withdrawn", "unknown", name="listingstatus", native_enum=False), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["development_id"], ["development.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_listing_id", name="uq_listing_source_external"),
    )
    op.create_index("ix_listing_development_status", "listing", ["development_id", "status"], unique=False)
    op.create_index("ix_listing_type_status", "listing", ["listing_type", "status"], unique=False)

    op.create_table(
        "transaction",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("development_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("registration_date", sa.Date(), nullable=True),
        sa.Column("price_hkd", sa.Numeric(15, 2), nullable=True),
        sa.Column("price_per_sqft", sa.Numeric(12, 2), nullable=True),
        sa.Column("transaction_type", sa.Enum("primary", "secondary", name="transactiontype", native_enum=False), nullable=False),
        sa.Column("doc_ref", sa.String(length=255), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["development_id"], ["development.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_record_id", name="uq_transaction_source_external"),
    )
    op.create_index("ix_transaction_development_date", "transaction", ["development_id", "transaction_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transaction_development_date", table_name="transaction")
    op.drop_table("transaction")
    op.drop_index("ix_listing_type_status", table_name="listing")
    op.drop_index("ix_listing_development_status", table_name="listing")
    op.drop_table("listing")
    op.drop_index("ix_document_development_type", table_name="document")
    op.drop_table("document")
    op.drop_index("ix_snapshot_source_object", table_name="source_snapshot")
    op.drop_index("ix_snapshot_fetched_at", table_name="source_snapshot")
    op.drop_table("source_snapshot")
    op.drop_index("ix_development_name_zh", table_name="development")
    op.drop_index("ix_development_name_en", table_name="development")
    op.drop_index("ix_development_district_segment", table_name="development")
    op.drop_table("development")
