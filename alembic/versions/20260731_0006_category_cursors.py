from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0006"
down_revision: str | None = "20260731_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category_cursors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("next_page", sa.Integer(), nullable=False),
        sa.Column("pages_scanned", sa.Integer(), nullable=False),
        sa.Column("sweeps_completed", sa.Integer(), nullable=False),
        sa.Column("last_signature", sa.String(length=64)),
        sa.Column("last_status", sa.String(length=40), nullable=False),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True)),
        sa.Column("last_completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_id", "url"),
    )


def downgrade() -> None:
    op.drop_table("category_cursors")
