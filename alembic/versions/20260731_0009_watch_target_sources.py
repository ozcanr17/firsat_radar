import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0009"
down_revision: str | None = "20260731_0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "watch_targets",
        sa.Column(
            "source_name",
            sa.String(length=100),
            nullable=False,
            server_default="hepsiburada",
        ),
    )


def downgrade() -> None:
    op.drop_column("watch_targets", "source_name")
