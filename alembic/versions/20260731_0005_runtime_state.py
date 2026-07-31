from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0005"
down_revision: str | None = "20260731_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheduler_status", sa.String(length=40), nullable=False),
        sa.Column("last_job_started_at", sa.DateTime(timezone=True)),
        sa.Column("last_job_finished_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("circuit_open_until", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(length=120)),
        sa.Column("last_backup_at", sa.DateTime(timezone=True)),
        sa.Column("last_retention_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("runtime_state")
