"""add scheduler plan override"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0006"
down_revision = "20260412_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduler_plan_override",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_name", sa.String(length=120), nullable=False),
        sa.Column("auto_run", sa.Boolean(), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("task_overrides_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_name"),
    )
    op.create_index(
        "ix_scheduler_plan_override_plan_name",
        "scheduler_plan_override",
        ["plan_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scheduler_plan_override_plan_name", table_name="scheduler_plan_override")
    op.drop_table("scheduler_plan_override")
