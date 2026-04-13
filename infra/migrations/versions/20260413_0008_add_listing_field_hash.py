"""add listing field hash

Revision ID: 20260413_0008
Revises: 20260413_0007
Create Date: 2026-04-13 18:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0008"
down_revision: str | Sequence[str] | None = "20260413_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listing", sa.Column("field_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("listing", "field_hash")
