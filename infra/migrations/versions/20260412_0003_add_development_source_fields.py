"""add development source fields"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0003"
down_revision = "20260412_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("development", sa.Column("source", sa.String(length=80), nullable=True))
    op.add_column("development", sa.Column("source_external_id", sa.String(length=255), nullable=True))
    op.add_column("development", sa.Column("source_url", sa.String(length=1000), nullable=True))
    op.create_index(
        "ix_development_source_external",
        "development",
        ["source", "source_external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_development_source_external", table_name="development")
    op.drop_column("development", "source_url")
    op.drop_column("development", "source_external_id")
    op.drop_column("development", "source")
