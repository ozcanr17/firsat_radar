import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0012"
down_revision: str | None = "20260731_0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("price_spread", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "price_spread")
