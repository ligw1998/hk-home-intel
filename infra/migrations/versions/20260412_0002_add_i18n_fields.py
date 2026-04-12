"""add i18n fields"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0002"
down_revision = "20260412_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "development",
        sa.Column("name_translations_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "development",
        sa.Column("address_translations_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "listing",
        sa.Column("title_translations_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "document",
        sa.Column("title_translations_json", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.execute("UPDATE development SET name_translations_json = '{}' WHERE name_translations_json IS NULL")
    op.execute("UPDATE development SET address_translations_json = '{}' WHERE address_translations_json IS NULL")
    op.execute("UPDATE listing SET title_translations_json = '{}' WHERE title_translations_json IS NULL")
    op.execute("UPDATE document SET title_translations_json = '{}' WHERE title_translations_json IS NULL")


def downgrade() -> None:
    op.drop_column("document", "title_translations_json")
    op.drop_column("listing", "title_translations_json")
    op.drop_column("development", "address_translations_json")
    op.drop_column("development", "name_translations_json")
