"""add refresh job run"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0005"
down_revision = "20260412_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_job_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_name", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("trigger_kind", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                name="jobrunstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_job_run_started_at", "refresh_job_run", ["started_at"], unique=False)
    op.create_index(
        "ix_refresh_job_run_job_status",
        "refresh_job_run",
        ["job_name", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_job_run_job_status", table_name="refresh_job_run")
    op.drop_index("ix_refresh_job_run_started_at", table_name="refresh_job_run")
    op.drop_table("refresh_job_run")
